from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from .transport_payloads import (
    build_anthropic_headers,
    build_anthropic_payload,
    build_openai_chat_url,
    build_openai_headers,
    build_openai_responses_payload,
    build_openai_responses_url,
)
from .transport_text import (
    extract_anthropic_text,
    extract_openai_chat_text,
    extract_openai_responses_text,
    extract_text_from_litellm_response,
)


_SYNC_HTTP_CLIENT = None
_SYNC_HTTP_CLIENT_LOCK = threading.Lock()


def _get_sync_http_client():
    import httpx

    global _SYNC_HTTP_CLIENT
    with _SYNC_HTTP_CLIENT_LOCK:
        if _SYNC_HTTP_CLIENT is None or _SYNC_HTTP_CLIENT.is_closed:
            _SYNC_HTTP_CLIENT = httpx.Client(
                timeout=httpx.Timeout(90.0),
                http2=True,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0),
            )
    return _SYNC_HTTP_CLIENT


def _sync_post_json(*, url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> object:
    client = _get_sync_http_client()
    resp = client.post(url, headers=headers, json=payload, timeout=float(timeout))
    try:
        resp.raise_for_status()
    except Exception as exc:
        body_text = (resp.text or "").strip()
        if body_text:
            snippet = body_text[:1000]
            raise type(exc)(f"{exc}\nResponse body: {snippet}", request=exc.request, response=exc.response) from exc
        raise
    return _decode_response_payload(resp)


def _decode_response_payload(resp) -> object:
    content_type = str(resp.headers.get("content-type", "") or "").strip().lower()
    try:
        return resp.json()
    except json.JSONDecodeError:
        body_text = str(resp.text or "")
        if "text/event-stream" in content_type or body_text.lstrip().startswith(("event:", "data:")):
            return _decode_sse_payload(body_text)
        raise


def _decode_sse_payload(body_text: str) -> object:
    payloads: list[dict[str, Any]] = []
    current_data_lines: list[str] = []

    def flush_event() -> None:
        if not current_data_lines:
            return
        raw_data = "\n".join(current_data_lines).strip()
        current_data_lines.clear()
        if not raw_data or raw_data == "[DONE]":
            return
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            return
        if isinstance(payload, dict):
            payloads.append(payload)

    for raw_line in body_text.splitlines():
        line = raw_line.rstrip("\r")
        if not line:
            flush_event()
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            current_data_lines.append(line[5:].lstrip())
    flush_event()

    if not payloads:
        raise json.JSONDecodeError("No JSON payload found in SSE response", body_text, 0)

    output_text_parts: list[str] = []
    done_text: str = ""
    latest_response: dict[str, Any] | None = None
    for payload in payloads:
        payload_type = str(payload.get("type", "") or "").strip().lower()
        response = payload.get("response")
        if isinstance(response, dict):
            latest_response = response
        if payload_type.endswith("output_text.delta"):
            delta = payload.get("delta")
            if isinstance(delta, str) and delta:
                output_text_parts.append(delta)
        if payload_type.endswith("output_text.done"):
            text = payload.get("text")
            if isinstance(text, str) and text:
                done_text = text

    if latest_response is not None:
        if not latest_response.get("output_text"):
            latest_response = dict(latest_response)
            if done_text:
                latest_response["output_text"] = done_text
            elif output_text_parts:
                latest_response["output_text"] = "".join(output_text_parts)
        return latest_response

    if done_text:
        return {"output_text": done_text}

    if output_text_parts:
        return {"output_text": "".join(output_text_parts)}

    return payloads[-1]


async def _post_json(*, url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> object:
    return await asyncio.to_thread(
        _sync_post_json,
        url=url,
        headers=headers,
        payload=payload,
        timeout=timeout,
    )


async def openai_chat_completion(*, provider: dict[str, Any], model: str, messages: list[dict[str, str]], max_tokens: int, timeout: float, temperature: float, reasoning_effort: str = "") -> str:
    url = build_openai_chat_url(provider)
    if not url:
        return ""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "stream": False,
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    data = await _post_json(
        url=url,
        headers=build_openai_headers(provider),
        payload=payload,
        timeout=timeout,
    )
    return extract_openai_chat_text(data)


async def openai_responses_completion(*, provider: dict[str, Any], model: str, messages: list[dict[str, str]], max_tokens: int, timeout: float, temperature: float, reasoning_effort: str = "") -> str:
    url = build_openai_responses_url(provider)
    if not url:
        return ""
    data = await _post_json(
        url=url,
        headers=build_openai_headers(provider),
        payload=build_openai_responses_payload(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
        ),
        timeout=timeout,
    )
    return extract_openai_responses_text(data)


async def anthropic_messages_completion(*, provider: dict[str, Any], model: str, messages: list[dict[str, str]], max_tokens: int, timeout: float, temperature: float) -> str:
    base_url = str(provider.get("base_url", "") or "").strip().rstrip("/")
    if not base_url:
        return ""
    url = base_url if base_url.endswith("/v1/messages") else f"{base_url}/v1/messages"
    data = await _post_json(
        url=url,
        headers=build_anthropic_headers(provider),
        payload=build_anthropic_payload(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        ),
        timeout=timeout,
    )
    return extract_anthropic_text(data)


async def litellm_completion(*, provider: dict[str, Any], model: str, messages: list[dict[str, str]], max_tokens: int, timeout: float, temperature: float) -> str:
    import litellm

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "timeout": float(timeout),
    }
    base_url = str(provider.get("base_url", "") or "").strip()
    api_key = str(provider.get("api_key", "") or "").strip()
    headers = provider.get("headers", {}) or {}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    if isinstance(headers, dict) and headers:
        kwargs["extra_headers"] = headers

    resp = await litellm.acompletion(**kwargs)
    return extract_text_from_litellm_response(resp)


async def close_http_clients() -> None:
    global _SYNC_HTTP_CLIENT
    with _SYNC_HTTP_CLIENT_LOCK:
        client = _SYNC_HTTP_CLIENT
        _SYNC_HTTP_CLIENT = None
    if client is not None and not client.is_closed:
        await asyncio.to_thread(client.close)


__all__ = [
    "anthropic_messages_completion",
    "close_http_clients",
    "litellm_completion",
    "openai_chat_completion",
    "openai_responses_completion",
]
