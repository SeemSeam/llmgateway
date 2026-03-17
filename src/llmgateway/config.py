from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from .spec import ProviderSpec, RuntimeSpec, TaskSpec


USER_CONFIG_NAME = "config.yaml"
_ENV_REF_RE = re.compile(
    r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-?(?P<default>[^}]*))?\}$"
)


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
            tier=str(task_raw.get("tier", "") or "").strip().lower(),
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
        strong_model=str(settings_raw.get("strong_model", "") or "").strip(),
        weak_model=str(settings_raw.get("weak_model", "") or "").strip(),
        strong_reasoning_effort=str(
            settings_raw.get("strong_reasoning_effort", "") or ""
        ).strip().lower(),
        weak_reasoning_effort=str(
            settings_raw.get("weak_reasoning_effort", "") or ""
        ).strip().lower(),
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


def user_config_dir() -> Path:
    override = str(os.environ.get("LLMGATEWAY_USER_CONFIG_DIR", "") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".llmgateway").resolve()


def resolve_user_config_file(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path).expanduser().resolve()
    explicit = str(os.environ.get("LLMGATEWAY_CONFIG", "") or "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    return user_config_dir() / USER_CONFIG_NAME


def resolve_env_value(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("env:") and len(text) > 4:
        return str(os.environ.get(text[4:].strip(), "") or "").strip()
    match = _ENV_REF_RE.match(text)
    if match is None:
        return text
    name = str(match.group("name") or "").strip()
    default = str(match.group("default") or "")
    return str(os.environ.get(name, default) or "").strip()


def resolve_env_refs(value: Any) -> Any:
    if isinstance(value, str):
        return resolve_env_value(value)
    if isinstance(value, list):
        return [resolve_env_refs(item) for item in value]
    if isinstance(value, dict):
        return {key: resolve_env_refs(item) for key, item in value.items()}
    return value


def load_user_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = resolve_user_config_file(path)
    if not config_path.exists():
        return {}
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(loaded, dict):
        return {}
    resolved = resolve_env_refs(loaded)
    return resolved if isinstance(resolved, dict) else {}


def write_user_config(
    payload: dict[str, Any],
    path: str | Path | None = None,
) -> Path:
    config_path = resolve_user_config_file(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(payload, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return config_path


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
            "strong_model": runtime.strong_model,
            "weak_model": runtime.weak_model,
            "strong_reasoning_effort": runtime.strong_reasoning_effort,
            "weak_reasoning_effort": runtime.weak_reasoning_effort,
            "max_concurrent": runtime.max_concurrent,
            "retry_max": runtime.retry_max,
            "transport_retries": runtime.transport_retries,
            "timeout": runtime.timeout,
        },
        "tasks": {
            task_name: {
                "model": task.model,
                "tier": task.tier,
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


__all__ = [
    "USER_CONFIG_NAME",
    "dump_runtime_spec",
    "load_runtime_spec",
    "load_user_config",
    "resolve_env_refs",
    "resolve_env_value",
    "resolve_user_config_file",
    "runtime_spec_from_dict",
    "user_config_dir",
    "write_user_config",
]
