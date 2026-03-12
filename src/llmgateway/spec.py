from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


Message = dict[str, str]
Validator = Callable[[str], list[str]]


@dataclass(slots=True, frozen=True)
class ProviderSpec:
    provider_type: str = ""
    api_style: str = ""
    base_url: str = ""
    api_key: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    model_map: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class TaskSpec:
    model: str
    temperature: float = 0.0
    reasoning_effort: str = ""
    max_tokens: int = 4000


@dataclass(slots=True, frozen=True)
class RuntimeSpec:
    provider: ProviderSpec
    fallback_model: str = ""
    max_concurrent: int = 20
    retry_max: int = 3
    timeout: float = 30.0
    transport_retries: int = 5
    tasks: dict[str, TaskSpec] = field(default_factory=dict)

    def task(self, name: str) -> TaskSpec:
        selected = self.tasks.get(str(name or "").strip())
        if selected is not None:
            return selected
        return TaskSpec(model=self.fallback_model)


@dataclass(slots=True, frozen=True)
class TaskRequest:
    task: str
    messages: list[Message]
    model: str = ""
    temperature: float | None = None
    reasoning_effort: str = ""
    max_tokens: int | None = None


@dataclass(slots=True, frozen=True)
class CallResult:
    task: str
    text: str
    requested_model: str
    normalized_model: str
    reasoning_effort: str
    temperature: float
    max_tokens: int


@dataclass(slots=True, frozen=True)
class JSONResult:
    task: str
    text: str
    data: dict | list | None
    errors: list[str] = field(default_factory=list)


__all__ = [
    "CallResult",
    "JSONResult",
    "Message",
    "ProviderSpec",
    "RuntimeSpec",
    "TaskRequest",
    "TaskSpec",
    "Validator",
]
