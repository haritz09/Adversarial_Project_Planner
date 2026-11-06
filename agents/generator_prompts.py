from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from core.models import DebateTurn
from core.prompt_loader import render_prompt


def _debate(state: Mapping[str, Any], debate_name: str) -> dict[str, Any]:
    return (state.get("debates") or {}).get(debate_name) or {}


def _verdict(state: Mapping[str, Any], debate_name: str) -> dict[str, Any]:
    return _debate(state, debate_name).get("verdict") or {}


def project_block(ctx: Mapping[str, Any]) -> str:
    constraints = ", ".join(ctx.get("constraints") or []) or "none"
    return (
        f"Goal: {ctx.get('goal', 'n/a')} | "
        f"Timeline: {ctx.get('timeline', 'n/a')} | "
        f"Team: {ctx.get('team_size', 'n/a')} devs | "
        f"Constraints: {constraints}"
    )


def debate_block(turns: Sequence[DebateTurn]) -> str:
    if not turns:
        return "No debate arguments available."
    return "\n".join(
        f"[Round {turn.get('round')} - Agent {turn.get('agent')}]: {turn.get('content', '')}"
        for turn in turns
    )


def summarise(text: str, max_chars: int = 800) -> str:
    if not text or len(text) <= max_chars:
        return text or "not available"
    return text[:max_chars] + "\n... [truncated for brevity]"


def build_architecture_prompt(state: Mapping[str, Any], debate_name: str) -> str:
    verdict = _verdict(state, debate_name)
    return render_prompt(
        "generators/architecture.md",
        project_block=project_block(state.get("project_context") or {}),
        debate_block=debate_block(_debate(state, debate_name).get("turns") or []),
        decision=verdict.get("winning_stack") or "not specified",
        rationale=verdict.get("rationale") or "not specified",
    )


def build_scope_prompt(state: Mapping[str, Any]) -> str:
    return render_prompt(
        "generators/scope.md",
        project_block=project_block(state.get("project_context") or {}),
        architecture_summary=summarise((state.get("docs") or {}).get("architecture", ""), 600),
    )


def build_plan_prompt(state: Mapping[str, Any], debate_name: str) -> str:
    return render_prompt(
        "generators/plan.md",
        project_block=project_block(state.get("project_context") or {}),
        decision=_verdict(state, debate_name).get("winning_stack") or "not specified",
        scope_summary=summarise((state.get("docs") or {}).get("scope", ""), 600),
        today=date.today().strftime("%Y-%m-%d"),
    )
