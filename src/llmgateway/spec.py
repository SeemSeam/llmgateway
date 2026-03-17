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
    model: str = ""
    tier: str = ""
    temperature: float = 0.0
    reasoning_effort: str = ""
    max_tokens: int = 4000


@dataclass(slots=True, frozen=True)
class RuntimeSpec:
    provider: ProviderSpec
    fallback_model: str = ""
    strong_model: str = ""
    weak_model: str = ""
    strong_reasoning_effort: str = ""
    weak_reasoning_effort: str = ""
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

    def model_for_tier(self, tier: str) -> str:
        tier_text = str(tier or "").strip().lower()
        if tier_text == "strong":
            return str(self.strong_model or self.fallback_model or "").strip()
        if tier_text == "weak":
            return str(self.weak_model or self.strong_model or self.fallback_model or "").strip()
        return str(self.fallback_model or self.strong_model or self.weak_model or "").strip()

    def reasoning_effort_for_tier(self, tier: str) -> str:
        tier_text = str(tier or "").strip().lower()
        if tier_text == "strong":
            return str(self.strong_reasoning_effort or "").strip().lower()
        if tier_text == "weak":
            return str(self.weak_reasoning_effort or "").strip().lower()
        return ""


@dataclass(slots=True, frozen=True)
class TaskRequest:
    task: str
    messages: list[Message]
    model: str = ""
    tier: str = ""
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
