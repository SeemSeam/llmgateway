from __future__ import annotations

import asyncio

from .runtime import (
    normalize_model_request,
    prefers_anthropic_messages,
    prefers_litellm,
    prefers_openai_chat,
    prefers_openai_responses,
    resolve_temperature,
)
from .spec import CallResult, RuntimeSpec, TaskRequest, Validator
from .transport import (
    anthropic_messages_completion,
    litellm_completion,
    openai_chat_completion,
    openai_responses_completion,
)


class LLMService:
    def __init__(self, runtime: RuntimeSpec):
        self.runtime = runtime
        self._semaphore = asyncio.Semaphore(max(1, int(runtime.max_concurrent)))
        self._sleep = asyncio.sleep

    def _provider_dict(self) -> dict[str, object]:
        provider = self.runtime.provider
        return {
            "provider_type": provider.provider_type,
            "api_style": provider.api_style,
            "base_url": provider.base_url,
            "api_key": provider.api_key,
            "headers": dict(provider.headers),
            "model_map": dict(provider.model_map),
        }

    def _validate_provider(self, provider: dict[str, object]) -> None:
        base_url = str(provider.get("base_url", "") or "").strip()
        if not base_url:
            raise RuntimeError("LLM base_url is not configured.")

    def _resolved_request(self, request: TaskRequest) -> tuple[str, str, float, int]:
        task = self.runtime.task(request.task)
        requested_tier = str(request.tier or task.tier or "").strip().lower()
        requested_model = str(
            request.model
            or task.model
            or self.runtime.model_for_tier(requested_tier)
            or self.runtime.fallback_model
            or ""
        ).strip()
        if not requested_model:
            raise RuntimeError(f"No model configured for task '{request.task}'.")

        provider = self._provider_dict()
        normalized_model, inferred_reasoning_effort = normalize_model_request(provider, requested_model)
        temperature = resolve_temperature(
            normalized_model,
            task.temperature if request.temperature is None else float(request.temperature),
        )
        reasoning_effort = str(
            request.reasoning_effort
            or task.reasoning_effort
            or self.runtime.reasoning_effort_for_tier(requested_tier)
            or inferred_reasoning_effort
            or ""
        ).strip().lower()
        max_tokens = int(request.max_tokens or task.max_tokens or 4000)
        return normalized_model, reasoning_effort, temperature, max_tokens

    def _requested_model_text(self, request: TaskRequest) -> str:
        task = self.runtime.task(request.task)
        requested_tier = str(request.tier or task.tier or "").strip().lower()
        return str(
            request.model
            or task.model
            or self.runtime.model_for_tier(requested_tier)
            or self.runtime.fallback_model
            or ""
        ).strip()

    async def _complete_once(
        self,
        *,
        provider: dict[str, object],
        model: str,
        messages: list[dict[str, str]],
        timeout: float,
        temperature: float,
        max_tokens: int,
        reasoning_effort: str = "",
    ) -> str:
        if prefers_openai_responses(provider):
            return await openai_responses_completion(
                provider=provider,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=timeout,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
            )
        if prefers_openai_chat(provider):
            return await openai_chat_completion(
                provider=provider,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=timeout,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
            )
        if prefers_anthropic_messages(provider, model):
            return await anthropic_messages_completion(
                provider=provider,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=timeout,
                temperature=temperature,
            )
        if prefers_litellm(provider):
            return await litellm_completion(
                provider=provider,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=timeout,
                temperature=temperature,
            )
        return await openai_responses_completion(
            provider=provider,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
        )

    async def generate(self, request: TaskRequest) -> CallResult:
        provider = self._provider_dict()
        self._validate_provider(provider)
        normalized_model, reasoning_effort, temperature, max_tokens = self._resolved_request(request)
        timeout_sec = float(self.runtime.timeout)
        request_deadline = max(timeout_sec + 5.0, timeout_sec * 1.25)

        async with self._semaphore:
            for attempt in range(max(1, int(self.runtime.transport_retries))):
                try:
                    text = await asyncio.wait_for(
                        self._complete_once(
                            provider=provider,
                            model=normalized_model,
                            messages=request.messages,
                            timeout=timeout_sec,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            reasoning_effort=reasoning_effort,
                        ),
                        timeout=request_deadline,
                    )
                    if text.strip():
                        return CallResult(
                            task=request.task,
                            text=text,
                            requested_model=self._requested_model_text(request),
                            normalized_model=normalized_model,
                            reasoning_effort=reasoning_effort,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                    raise RuntimeError("LLM response text was empty. Check provider api_style/response format.")
                except asyncio.TimeoutError as exc:
                    requested_model = self._requested_model_text(request) or normalized_model
                    raise RuntimeError(
                        f"LLM request timed out for task '{request.task}' "
                        f"after {request_deadline:.1f}s "
                        f"(model='{requested_model}', timeout={timeout_sec:.1f}s)."
                    ) from exc
                except Exception:
                    if attempt >= max(1, int(self.runtime.transport_retries)) - 1:
                        raise
                    await self._sleep(2 ** attempt + 1)
        raise RuntimeError("LLM request failed unexpectedly.")

    async def generate_text(self, request: TaskRequest) -> str:
        result = await self.generate(request)
        return result.text

    async def generate_text_with_retry(
        self,
        request: TaskRequest,
        validator: Validator | None = None,
    ) -> tuple[str, list[str]]:
        text = ""
        errors: list[str] = []
        messages = list(request.messages)

        for attempt in range(max(0, int(self.runtime.retry_max)) + 1):
            try:
                text = await self.generate_text(
                    TaskRequest(
                            task=request.task,
                            messages=messages,
                            model=request.model,
                            tier=request.tier,
                            temperature=request.temperature,
                            reasoning_effort=request.reasoning_effort,
                            max_tokens=request.max_tokens,
                        )
                )
            except Exception as exc:
                if attempt >= int(self.runtime.retry_max):
                    raise
                errors = [str(exc)]
                await self._sleep(2 ** attempt + 1)
                continue

            if validator is None:
                return text, []

            errors = validator(text)
            if not errors:
                return text, []

            retry_msg = (
                "Your previous output had the following issues:\n"
                + "\n".join(f"- {error}" for error in errors)
                + "\n\nPlease regenerate the full JSON only."
            )
            if attempt < int(self.runtime.retry_max):
                messages = messages + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": retry_msg},
                ]

        return text, errors

    async def run_many(self, requests: list[TaskRequest]) -> list[CallResult]:
        tasks = [asyncio.create_task(self.generate(request)) for request in requests]
        return list(await asyncio.gather(*tasks))

    async def run_many_with_retry(
        self,
        requests: list[TaskRequest],
        validators: list[Validator | None] | None = None,
    ) -> list[tuple[str, list[str]]]:
        validator_items = validators or [None] * len(requests)
        if len(validator_items) != len(requests):
            raise ValueError("validators length must match requests length")
        tasks = [
            asyncio.create_task(self.generate_text_with_retry(request, validator))
            for request, validator in zip(requests, validator_items)
        ]
        return list(await asyncio.gather(*tasks))


__all__ = ["LLMService"]
