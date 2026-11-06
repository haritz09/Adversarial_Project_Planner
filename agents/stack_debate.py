from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from core.models import BaseVerdict, DebateConfig, DebateModels, DebateTurn, RoleSpec
from core.prompt_loader import load_prompt, render_prompt

DEBATE_NAME = "tech_stack"

class StackVerdict(BaseVerdict):
    winning_stack: str = "undetermined"

class StackInput(BaseModel):

    project_context: dict[str, Any] = {}
    user_provided_fields: dict[str, Any] = {}

ROLE_A = RoleSpec(label="A", system_prompt=load_prompt("tech_stack/agent_a.md"))

ROLE_B = RoleSpec(label="B", system_prompt=load_prompt("tech_stack/agent_b.md"))

JUDGE_RUBRIC = load_prompt("tech_stack/judge_rubric.md")

def build_brief(data: Mapping[str, Any]) -> str:
    ctx = (data or {}).get("project_context") or {}
    provided = (data or {}).get("user_provided_fields") or {}
    constraints = ", ".join(ctx.get("constraints") or []) or "none"

    template = (
        "tech_stack/brief_challenge.md"
        if provided.get("stack") and ctx.get("stack")
        else "tech_stack/brief.md"
    )
    return render_prompt(
        template,
        goal=ctx.get("goal") or "not specified",
        timeline=ctx.get("timeline") or "not specified",
        team_size=ctx.get("team_size") or "not specified",
        constraints=constraints,
        user_stack=ctx.get("stack") or "",
    )

def fallback_verdict(turns: Sequence[DebateTurn]) -> dict[str, Any]:
    if not turns:
        return {"winning_stack": "undetermined"}
    last = str(turns[-1].get("content", ""))
    return {"winning_stack": last[:200] + ("..." if len(last) > 200 else "")}

def debate_input(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "project_context": state.get("project_context") or {},
        "user_provided_fields": state.get("user_provided_fields") or {},
    }

def build_stack_debate(models: DebateModels) -> DebateConfig:
    return DebateConfig(
        name=DEBATE_NAME,
        topic="Which technology stack should this project use?",
        role_a=ROLE_A,
        role_b=ROLE_B,
        judge_rubric=JUDGE_RUBRIC,
        verdict_model=StackVerdict,
        models=models,
        brief=build_brief,
        prepare_input=debate_input,
        min_rounds=2,
        max_rounds=3,
        fallback_verdict=fallback_verdict,
    )
