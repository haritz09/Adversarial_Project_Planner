from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator

ModelLike = Any

AGENT_A = "A"
AGENT_B = "B"

def _blank_to_empty(value: Any) -> Any:
    return "" if value is None else value

class BaseVerdict(BaseModel):

    model_config = ConfigDict(extra="ignore")

    needs_another_round: bool = False
    reason_for_continuing: str = ""
    winner: str = "tie"
    rationale: str = ""
    agent_a_score: float = Field(default=5.0, ge=0, le=10)
    agent_b_score: float = Field(default=5.0, ge=0, le=10)

    @field_validator("winner", mode="before")
    @classmethod
    def _normalise_winner(cls, value: Any) -> str:
        if value is None:
            return "tie"
        text = str(value).strip().lower()
        if text in {"a", "agent a", "agenta", "agent_a"}:
            return AGENT_A
        if text in {"b", "agent b", "agentb", "agent_b"}:
            return AGENT_B
        return "tie"

    @field_validator("needs_another_round", mode="before")
    @classmethod
    def _coerce_bool(cls, value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"true", "yes", "1"}
        return bool(value)

    @field_validator("agent_a_score", "agent_b_score", mode="before")
    @classmethod
    def _clamp_score(cls, value: Any) -> float:
        try:
            return min(10.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return 5.0

    @field_validator("reason_for_continuing", "rationale", mode="before")
    @classmethod
    def _coerce_text(cls, value: Any) -> str:
        return _blank_to_empty(value)

class DebateTurn(TypedDict, total=False):
    agent: str
    round: int
    content: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None

class DebateResult(TypedDict, total=False):
    name: str
    topic: str
    turns: list[DebateTurn]
    rounds_completed: int
    winner: str | None
    verdict: dict[str, Any]
    scores: dict[str, float]
    status: str
    skipped: bool
    needs_another_round: bool
    cost_usd: float | None

@dataclass(frozen=True)
class RoleSpec:

    label: str
    system_prompt: str

@dataclass(frozen=True)
class DebateModels:

    a: ModelLike
    b: ModelLike
    judge: ModelLike

@dataclass(frozen=True)
class DebateConfig:

    name: str
    topic: str
    role_a: RoleSpec
    role_b: RoleSpec
    judge_rubric: str
    verdict_model: type[BaseVerdict]
    models: DebateModels

    brief: Callable[[Mapping[str, Any]], str]

    prepare_input: Callable[[Mapping[str, Any]], dict[str, Any]] | None = None

    evidence: Callable[[Mapping[str, Any]], str] | None = None

    min_rounds: int = 2
    max_rounds: int = 3

    history_rounds: int = 2
    max_turn_chars: int = 4000

    fallback_verdict: Callable[[Sequence[DebateTurn]], dict[str, Any]] | None = None

    skip_when: Callable[[Mapping[str, Any]], bool] | None = None
    skip_reason: str = "Predefined by the user; no debate required."

    def with_models(self, models: DebateModels) -> DebateConfig:
        from dataclasses import replace

        return replace(self, models=models)

    def __post_init__(self) -> None:
        if self.min_rounds < 1:
            raise ValueError("min_rounds must be >= 1")
        if self.max_rounds < self.min_rounds:
            raise ValueError("max_rounds must be >= min_rounds")
        if self.role_a.label != AGENT_A or self.role_b.label != AGENT_B:
            raise ValueError("roles must be labelled 'A' and 'B'")
