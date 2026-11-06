from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, field_validator

from core.json_utils import message_text, parse_json_object
from core.llm import ModelResolver, PlannerModels, resolve_model
from core.prompt_loader import render_prompt

REQUIRED_FIELDS = ["goal", "timeline", "team_size"]
MAX_INTERRUPT_ATTEMPTS = 3

FIELD_DEFAULTS: dict[str, Any] = {
    "team_size": 1,
    "timeline": "undefined",
    "goal": "undefined project",
}

class ProjectContext(BaseModel):

    model_config = ConfigDict(extra="ignore")

    goal: str | None = None
    timeline: str | None = None
    team_size: int | None = None
    constraints: list[str] = []
    stack: str | None = None
    methodology: str | None = None

    @field_validator("goal", "timeline", "stack", "methodology", mode="before")
    @classmethod
    def _empty_to_none(cls, value: Any) -> Any:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("team_size", mode="before")
    @classmethod
    def _coerce_team_size(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        try:
            return int(str(value).strip().split()[0])
        except (TypeError, ValueError, IndexError):
            return None

    @field_validator("constraints", mode="before")
    @classmethod
    def _coerce_constraints(cls, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        return [str(item).strip() for item in value if str(item).strip()]

def extract_context(raw_input: str, llm: Any | None = None) -> dict[str, Any]:
    model = llm or resolve_model(PlannerModels.from_env().intake)
    message = model.invoke(render_prompt("intake/extraction.md", raw_input=raw_input))
    data = parse_json_object(message_text(message)) or {}
    return ProjectContext.model_validate(data).model_dump()

def check_missing(context: Mapping[str, Any]) -> list[str]:
    return [
        field
        for field in REQUIRED_FIELDS
        if context.get(field) is None or context.get(field) == ""
    ]

def apply_defaults(context: dict[str, Any], missing: list[str]) -> dict[str, Any]:
    for field in missing:
        context[field] = FIELD_DEFAULTS.get(field, "undefined")
    return context

def detect_user_provided(context: Mapping[str, Any]) -> dict[str, bool]:
    def provided(key: str) -> bool:
        value = context.get(key)
        return value is not None and value not in ("", "undefined", "undefined project")

    return {
        "goal": provided("goal"),
        "timeline": provided("timeline"),
        "team_size": provided("team_size"),
        "stack": provided("stack"),
        "methodology": provided("methodology"),
    }

def _build_interrupt_message(missing: list[str], attempt: int) -> str:
    questions = {
        "goal": "What does the project build? (e.g. 'a real-time chat app')",
        "timeline": "What is the expected timeline? (e.g. '3 weeks', '2 months')",
        "team_size": "How many developers will work on this? (e.g. '1', '2', 'solo')",
    }
    if attempt == 1:
        header = "I need a bit more context before we start:\n"
    else:
        header = (
            f"I still need the following information "
            f"(attempt {attempt}/{MAX_INTERRUPT_ATTEMPTS}):\n"
        )
    return header + "\n".join(f"- {questions.get(f, f)}" for f in missing)

def make_intake_node(llm: Any | None = None, resolver: ModelResolver | None = None):

    def intake_node(state: Mapping[str, Any]) -> dict[str, Any]:
        model = llm or resolve_model(PlannerModels.from_env().intake, resolver)
        accumulated = state["raw_input"]
        context = extract_context(accumulated, llm=model)

        for attempt in range(1, MAX_INTERRUPT_ATTEMPTS + 1):
            missing = check_missing(context)
            if not missing:
                break
            if attempt == MAX_INTERRUPT_ATTEMPTS:
                context = apply_defaults(context, missing)
                break

            answer = interrupt(_build_interrupt_message(missing, attempt))
            accumulated = f"{accumulated}\n{answer}"
            context = extract_context(accumulated, llm=model)

        return {
            "project_context": context,
            "user_provided_fields": detect_user_provided(context),
            "current_node": "intake_node",
        }

    return intake_node
