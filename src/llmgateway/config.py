from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .spec import ProviderSpec, RuntimeSpec, TaskSpec


def runtime_spec_from_dict(raw: dict[str, Any]) -> RuntimeSpec:
    provider_raw = raw.get("provider", {}) if isinstance(raw.get("provider"), dict) else {}
    settings_raw = raw.get("settings", {}) if isinstance(raw.get("settings"), dict) else {}
    tasks_raw = raw.get("tasks", {}) if isinstance(raw.get("tasks"), dict) else {}

    tasks: dict[str, TaskSpec] = {}
    for task_name, task_raw in tasks_raw.items():
        if not isinstance(task_name, str) or not isinstance(task_raw, dict):
            continue
        tasks[task_name] = TaskSpec(
            model=str(task_raw.get("model", "") or "").strip(),
            temperature=float(task_raw.get("temperature", 0.0) or 0.0),
            reasoning_effort=str(task_raw.get("reasoning_effort", "") or "").strip().lower(),
            max_tokens=max(1, int(task_raw.get("max_tokens", 4000) or 4000)),
        )

    return RuntimeSpec(
        provider=ProviderSpec(
            provider_type=str(provider_raw.get("provider_type", "") or "").strip(),
            api_style=str(provider_raw.get("api_style", "") or "").strip(),
            base_url=str(provider_raw.get("base_url", "") or "").strip(),
            api_key=str(provider_raw.get("api_key", "") or "").strip(),
            headers=_normalized_headers(provider_raw.get("headers", {})),
            model_map=_normalized_headers(provider_raw.get("model_map", {})),
        ),
        fallback_model=str(settings_raw.get("fallback_model", "") or "").strip(),
        max_concurrent=max(1, int(settings_raw.get("max_concurrent", 20) or 20)),
        retry_max=max(0, int(settings_raw.get("retry_max", 3) or 3)),
        timeout=float(settings_raw.get("timeout", 30) or 30),
        transport_retries=max(1, int(settings_raw.get("transport_retries", 5) or 5)),
        tasks=tasks,
    )


def load_runtime_spec(path: Path) -> RuntimeSpec:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Invalid llmgateway config: {path}")
    return runtime_spec_from_dict(loaded)


def dump_runtime_spec(runtime: RuntimeSpec) -> dict[str, Any]:
    return {
        "version": 1,
        "provider": {
            "provider_type": runtime.provider.provider_type,
            "api_style": runtime.provider.api_style,
            "base_url": runtime.provider.base_url,
            "api_key": runtime.provider.api_key,
            "headers": dict(runtime.provider.headers),
            "model_map": dict(runtime.provider.model_map),
        },
        "settings": {
            "fallback_model": runtime.fallback_model,
            "max_concurrent": runtime.max_concurrent,
            "retry_max": runtime.retry_max,
            "transport_retries": runtime.transport_retries,
            "timeout": runtime.timeout,
        },
        "tasks": {
            task_name: {
                "model": task.model,
                "temperature": task.temperature,
                "reasoning_effort": task.reasoning_effort,
                "max_tokens": task.max_tokens,
            }
            for task_name, task in runtime.tasks.items()
        },
    }


def _normalized_headers(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw.items()
        if str(key).strip()
    }


__all__ = ["dump_runtime_spec", "load_runtime_spec", "runtime_spec_from_dict"]
