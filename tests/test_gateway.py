from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from llmgateway import Gateway, LLMService, TaskRequest, load_runtime_spec, runtime_spec_from_dict


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
  fallback_model: gpt-5.4
  max_concurrent: 8
tasks:
  analysis:
    model: gpt-5.4
    reasoning_effort: low
""".strip()
        + "\n",
        encoding="utf-8",
    )
    runtime = load_runtime_spec(cfg)
    assert runtime.provider.base_url == "https://backend.example"
    assert runtime.max_concurrent == 8
    assert runtime.task("analysis").reasoning_effort == "low"


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
                "analysis": {"model": "gpt-5.4"},
            },
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
            "settings": {"max_concurrent": 2},
            "tasks": {"analysis": {"model": "gpt-5.4"}},
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
