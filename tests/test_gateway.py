from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from llmgateway import (
    Gateway,
    LLMService,
    load_provider_state,
    TaskRequest,
    load_runtime_spec,
    load_user_config,
    resolve_provider_state_file,
    resolve_user_config_file,
    runtime_spec_from_dict,
    user_config_dir,
    write_user_config,
)
from llmgateway.runtime import prefers_openai_responses
from llmgateway.transport import _decode_response_payload
from llmgateway.transport_payloads import build_openai_responses_payload


def test_load_runtime_spec_from_yaml(tmp_path: Path):
    cfg = tmp_path / "llmgateway.yaml"
    cfg.write_text(
        """
version: 1
provider:
  provider_type: glm
  api_style: openai_responses
  base_url: https://backend.example
  api_key: secret
settings:
  strong_model: gpt-5.4
  weak_model: gpt-5.4-mini
  strong_reasoning_effort: high
  weak_reasoning_effort: low
  max_concurrent: 8
tasks:
  analysis:
    tier: strong
""".strip()
        + "\n",
        encoding="utf-8",
    )
    runtime = load_runtime_spec(cfg)
    assert runtime.provider.base_url == "https://backend.example"
    assert runtime.providers == (runtime.provider,)
    assert runtime.max_concurrent == 8
    assert runtime.task("analysis").tier == "strong"
    assert runtime.strong_model == "gpt-5.4"
    assert runtime.weak_reasoning_effort == "low"


def test_runtime_spec_supports_multiple_providers_in_order():
    runtime = runtime_spec_from_dict(
        {
            "providers": [
                {
                    "provider_type": "glm",
                    "api_style": "openai_responses",
                    "base_url": "https://primary.example",
                    "api_key": "primary-secret",
                },
                {
                    "provider_type": "openai",
                    "api_style": "responses",
                    "base_url": "https://secondary.example",
                    "api_key": "secondary-secret",
                },
            ],
            "settings": {"strong_model": "gpt-5.4"},
        }
    )

    assert len(runtime.providers) == 2
    assert runtime.provider.base_url == "https://primary.example"
    assert runtime.providers[1].base_url == "https://secondary.example"


def test_prefers_openai_responses_accepts_responses_alias():
    assert prefers_openai_responses({"api_style": "responses"}) is True
    assert prefers_openai_responses({"api_style": "openai_responses"}) is True


def test_build_openai_responses_payload_forces_non_streaming():
    payload = build_openai_responses_payload(
        model="gpt-5.4",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=64,
        temperature=1.0,
        reasoning_effort="high",
    )

    assert payload["stream"] is False


def test_decode_response_payload_supports_sse_completed_response():
    import httpx

    sse_body = "\n".join(
        [
            "event: response.created",
            'data: {"type":"response.created","response":{"id":"resp_1","status":"in_progress"}}',
            "",
            "event: response.completed",
            'data: {"type":"response.completed","response":{"id":"resp_1","status":"completed","output_text":"OK","output":[{"content":[{"type":"output_text","text":"OK"}]}]}}',
            "",
        ]
    )
    resp = httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse_body)

    payload = _decode_response_payload(resp)

    assert payload["status"] == "completed"
    assert payload["output_text"] == "OK"


def test_decode_response_payload_supports_sse_deltas_without_completed_response():
    import httpx

    sse_body = "\n".join(
        [
            "event: response.output_text.delta",
            'data: {"type":"response.output_text.delta","delta":"O"}',
            "",
            "event: response.output_text.delta",
            'data: {"type":"response.output_text.delta","delta":"K"}',
            "",
        ]
    )
    resp = httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse_body)

    payload = _decode_response_payload(resp)

    assert payload["output_text"] == "OK"


def test_decode_response_payload_prefers_done_text_over_accumulated_deltas():
    import httpx

    sse_body = "\n".join(
        [
            "event: response.output_text.delta",
            'data: {"type":"response.output_text.delta","delta":"O"}',
            "",
            "event: response.output_text.delta",
            'data: {"type":"response.output_text.delta","delta":"K"}',
            "",
            "event: response.output_text.done",
            'data: {"type":"response.output_text.done","text":"OK"}',
            "",
        ]
    )
    resp = httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse_body)

    payload = _decode_response_payload(resp)

    assert payload["output_text"] == "OK"


def test_user_config_dir_env_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LLMGATEWAY_USER_CONFIG_DIR", str(tmp_path / "gateway-home"))
    assert user_config_dir() == (tmp_path / "gateway-home").resolve()


def test_write_and_load_user_config(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    payload = {
        "version": 1,
        "provider": {
            "provider_type": "openai",
            "api_style": "responses",
            "base_url": "https://api.example",
            "api_key": "secret-key",
        },
        "settings": {
            "max_concurrent": 12,
            "strong_model": "gpt-5.4",
            "weak_model": "gpt-5.4-mini",
            "strong_reasoning_effort": "high",
            "weak_reasoning_effort": "low",
        },
    }
    written = write_user_config(payload, cfg_path)
    loaded = load_user_config(cfg_path)

    assert written == cfg_path.resolve()
    assert loaded["settings"]["max_concurrent"] == 12
    assert loaded["provider"]["api_key"] == "secret-key"
    assert loaded["settings"]["strong_model"] == "gpt-5.4"


def test_load_user_config_resolves_env_refs(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TEST_GATEWAY_KEY", "env-secret")
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
providers:
  main:
    api_key: ${TEST_GATEWAY_KEY}
    base_url: env:TEST_GATEWAY_URL
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_GATEWAY_URL", "https://env.example")

    loaded = load_user_config(cfg_path)

    assert loaded["providers"]["main"]["api_key"] == "env-secret"
    assert loaded["providers"]["main"]["base_url"] == "https://env.example"


def test_resolve_user_config_file_prefers_explicit_env(monkeypatch, tmp_path: Path):
    explicit = tmp_path / "gateway.yaml"
    monkeypatch.setenv("LLMGATEWAY_CONFIG", str(explicit))
    assert resolve_user_config_file() == explicit.resolve()


def test_resolve_provider_state_file_prefers_user_config_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LLMGATEWAY_USER_CONFIG_DIR", str(tmp_path / "gateway-home"))
    assert resolve_provider_state_file() == (
        tmp_path / "gateway-home" / "provider-state.json"
    ).resolve()


@pytest.mark.asyncio
async def test_gateway_run_json_task_parses_fenced_json(monkeypatch):
    runtime = runtime_spec_from_dict(
        {
            "provider": {
                "provider_type": "glm",
                "api_style": "openai_responses",
                "base_url": "https://backend.example",
                "api_key": "secret",
            },
            "tasks": {
                "analysis": {"tier": "strong"},
            },
            "settings": {"strong_model": "gpt-5.4"},
        }
    )
    gateway = Gateway(runtime)

    async def fake_generate_text(request):
        assert request.task == "analysis"
        return '```json\n{"summary":"ok"}\n```'

    monkeypatch.setattr(gateway.service, "generate_text", fake_generate_text)

    result = await gateway.run_json_task(
        "analysis",
        [{"role": "user", "content": "hello"}],
    )
    assert result.data == {"summary": "ok"}


@pytest.mark.asyncio
async def test_service_run_many_respects_max_concurrent(monkeypatch):
    runtime = runtime_spec_from_dict(
        {
            "provider": {
                "provider_type": "glm",
                "api_style": "openai_responses",
                "base_url": "https://backend.example",
                "api_key": "secret",
            },
            "settings": {"max_concurrent": 2, "strong_model": "gpt-5.4"},
            "tasks": {"analysis": {"tier": "strong"}},
        }
    )
    service = LLMService(runtime)
    state = {"inflight": 0, "max_seen": 0}

    async def fake_complete_once(**kwargs):
        state["inflight"] += 1
        state["max_seen"] = max(state["max_seen"], state["inflight"])
        await asyncio.sleep(0.01)
        state["inflight"] -= 1
        return f"OK {kwargs['model']}"

    monkeypatch.setattr(service, "_complete_once", fake_complete_once)

    results = await service.run_many(
        [TaskRequest(task="analysis", messages=[{"role": "user", "content": str(i)}]) for i in range(5)]
    )

    assert len(results) == 5
    assert state["max_seen"] == 2


@pytest.mark.asyncio
async def test_service_uses_litellm_transport(monkeypatch):
    runtime = runtime_spec_from_dict(
        {
            "provider": {
                "provider_type": "litellm",
                "api_style": "litellm",
                "base_url": "https://backend.example",
                "api_key": "secret",
            },
            "tasks": {"analysis": {"tier": "strong"}},
            "settings": {"strong_model": "gpt-5.4"},
        }
    )
    service = LLMService(runtime)
    seen: dict[str, object] = {}

    async def fake_litellm_completion(**kwargs):
        seen.update(kwargs)
        return "OK litellm"

    monkeypatch.setattr("llmgateway.service.litellm_completion", fake_litellm_completion)

    result = await service.generate(
        TaskRequest(
            task="analysis",
            messages=[{"role": "user", "content": "hello"}],
        )
    )

    assert result.text == "OK litellm"
    assert result.normalized_model == "gpt-5.4"
    assert seen["model"] == "gpt-5.4"


@pytest.mark.asyncio
async def test_service_resolves_model_and_reasoning_effort_from_task_tier(monkeypatch):
    runtime = runtime_spec_from_dict(
        {
            "provider": {
                "provider_type": "glm",
                "api_style": "openai_responses",
                "base_url": "https://backend.example",
                "api_key": "secret",
            },
            "settings": {
                "strong_model": "gpt-5.4",
                "strong_reasoning_effort": "high",
            },
            "tasks": {"analysis": {"tier": "strong"}},
        }
    )
    service = LLMService(runtime)
    seen: dict[str, object] = {}

    async def fake_complete_once(**kwargs):
        seen.update(kwargs)
        return "OK"

    monkeypatch.setattr(service, "_complete_once", fake_complete_once)

    result = await service.generate(
        TaskRequest(task="analysis", messages=[{"role": "user", "content": "hello"}])
    )

    assert result.requested_model == "gpt-5.4"
    assert result.reasoning_effort == "high"
    assert seen["model"] == "gpt-5.4"
    assert seen["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_service_fails_over_to_next_provider(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LLMGATEWAY_USER_CONFIG_DIR", str(tmp_path / "gateway-home"))
    runtime = runtime_spec_from_dict(
        {
            "providers": [
                {
                    "provider_type": "glm",
                    "api_style": "openai_responses",
                    "base_url": "https://primary.example",
                    "api_key": "primary-secret",
                },
                {
                    "provider_type": "openai",
                    "api_style": "responses",
                    "base_url": "https://secondary.example",
                    "api_key": "secondary-secret",
                },
            ],
            "tasks": {"analysis": {"tier": "strong"}},
            "settings": {
                "strong_model": "gpt-5.4",
                "transport_retries": 1,
            },
        }
    )
    service = LLMService(runtime)
    seen_base_urls: list[str] = []

    async def fake_complete_once(**kwargs):
        provider = kwargs["provider"]
        base_url = str(provider["base_url"])
        seen_base_urls.append(base_url)
        if base_url == "https://primary.example":
            raise RuntimeError("primary unavailable")
        return "OK secondary"

    monkeypatch.setattr(service, "_complete_once", fake_complete_once)
    monkeypatch.setattr(service, "_sleep", lambda _: asyncio.sleep(0))

    result = await service.generate(
        TaskRequest(task="analysis", messages=[{"role": "user", "content": "hello"}])
    )

    assert result.text == "OK secondary"
    assert seen_base_urls == [
        "https://primary.example",
        "https://secondary.example",
    ]


@pytest.mark.asyncio
async def test_service_remembers_successful_provider_with_dynamic_priority(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LLMGATEWAY_USER_CONFIG_DIR", str(tmp_path / "gateway-home"))
    runtime = runtime_spec_from_dict(
        {
            "providers": [
                {
                    "provider_type": "glm",
                    "api_style": "openai_responses",
                    "base_url": "https://primary.example",
                    "api_key": "primary-secret",
                },
                {
                    "provider_type": "openai",
                    "api_style": "responses",
                    "base_url": "https://secondary.example",
                    "api_key": "secondary-secret",
                },
            ],
            "tasks": {"analysis": {"tier": "strong"}},
            "settings": {
                "strong_model": "gpt-5.4",
                "transport_retries": 1,
            },
        }
    )
    service = LLMService(runtime)
    seen_base_urls: list[str] = []
    state = {"first_request": True}

    async def fake_complete_once(**kwargs):
        provider = kwargs["provider"]
        base_url = str(provider["base_url"])
        seen_base_urls.append(base_url)
        if state["first_request"] and base_url == "https://primary.example":
            raise RuntimeError("primary unavailable")
        return f"OK {base_url}"

    monkeypatch.setattr(service, "_complete_once", fake_complete_once)
    monkeypatch.setattr(service, "_sleep", lambda _: asyncio.sleep(0))

    first_result = await service.generate(
        TaskRequest(task="analysis", messages=[{"role": "user", "content": "first"}])
    )
    state["first_request"] = False
    second_result = await service.generate(
        TaskRequest(task="analysis", messages=[{"role": "user", "content": "second"}])
    )

    assert first_result.text == "OK https://secondary.example"
    assert second_result.text == "OK https://secondary.example"
    assert seen_base_urls == [
        "https://primary.example",
        "https://secondary.example",
        "https://secondary.example",
    ]

    state_path = resolve_provider_state_file()
    assert state_path.exists()
    saved_state = load_provider_state()
    assert len(saved_state) == 1


@pytest.mark.asyncio
async def test_service_loads_dynamic_priority_from_state(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LLMGATEWAY_USER_CONFIG_DIR", str(tmp_path / "gateway-home"))
    runtime = runtime_spec_from_dict(
        {
            "providers": [
                {
                    "provider_type": "glm",
                    "api_style": "openai_responses",
                    "base_url": "https://primary.example",
                    "api_key": "primary-secret",
                },
                {
                    "provider_type": "openai",
                    "api_style": "responses",
                    "base_url": "https://secondary.example",
                    "api_key": "secondary-secret",
                },
            ],
            "tasks": {"analysis": {"tier": "strong"}},
            "settings": {
                "strong_model": "gpt-5.4",
                "transport_retries": 1,
            },
        }
    )
    bootstrap_service = LLMService(runtime)

    async def bootstrap_complete_once(**kwargs):
        provider = kwargs["provider"]
        if str(provider["base_url"]) == "https://primary.example":
            raise RuntimeError("primary unavailable")
        return "OK secondary"

    monkeypatch.setattr(bootstrap_service, "_complete_once", bootstrap_complete_once)
    monkeypatch.setattr(bootstrap_service, "_sleep", lambda _: asyncio.sleep(0))

    await bootstrap_service.generate(
        TaskRequest(task="analysis", messages=[{"role": "user", "content": "bootstrap"}])
    )

    resumed_service = LLMService(runtime)
    seen_base_urls: list[str] = []

    async def resumed_complete_once(**kwargs):
        provider = kwargs["provider"]
        base_url = str(provider["base_url"])
        seen_base_urls.append(base_url)
        return "OK"

    monkeypatch.setattr(resumed_service, "_complete_once", resumed_complete_once)

    await resumed_service.generate(
        TaskRequest(task="analysis", messages=[{"role": "user", "content": "follow-up"}])
    )

    assert seen_base_urls == ["https://secondary.example"]
