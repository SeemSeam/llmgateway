from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from llmgateway import (
    Gateway,
    LLMService,
    TaskRequest,
    load_runtime_spec,
    load_user_config,
    resolve_user_config_file,
    runtime_spec_from_dict,
    user_config_dir,
    write_user_config,
)


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
    assert runtime.max_concurrent == 8
    assert runtime.task("analysis").tier == "strong"
    assert runtime.strong_model == "gpt-5.4"
    assert runtime.weak_reasoning_effort == "low"


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
