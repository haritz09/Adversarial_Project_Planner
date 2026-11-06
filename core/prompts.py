from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from core.models import AGENT_A, AGENT_B, DebateConfig, DebateTurn
from core.prompt_loader import render_prompt


def _input_of(cfg: DebateConfig, state: Mapping[str, Any]) -> Mapping[str, Any]:
    return (state.get("debate_inputs") or {}).get(cfg.name) or {}


def _truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + "\n... [truncated]"


def _last_round(turns: Sequence[DebateTurn]) -> int:
    return max((int(t.get("round", 0)) for t in turns), default=0)


def render_history(cfg: DebateConfig, turns: Sequence[DebateTurn]) -> str:
    if not turns:
        return ""
    newest = _last_round(turns)
    oldest = max(1, newest - cfg.history_rounds + 1)
    entries: list[str] = []
    for turn in turns:
        round_index = int(turn.get("round", 0))
        if round_index < oldest:
            continue
        entries.append(
            f"--- Round {round_index} ---\n"
            f"Agent {turn['agent']}: "
            f"{_truncate(str(turn.get('content', '')), cfg.max_turn_chars)}"
        )
    return "\n".join(entries)


def _evidence(cfg: DebateConfig, data: Mapping[str, Any]) -> str:
    if not cfg.evidence:
        return ""
    value = cfg.evidence(data).strip()
    return value


def render_turn_prompt(
    cfg: DebateConfig,
    agent: str,
    state: Mapping[str, Any],
    round_index: int,
) -> str:
    role = cfg.role_a if agent == AGENT_A else cfg.role_b
    opponent = AGENT_B if agent == AGENT_A else AGENT_A
    data = _input_of(cfg, state)
    turns: Sequence[DebateTurn] = state.get("_turns", [])

    return render_prompt(
        "debate/turn_opening.md" if not turns else "debate/turn_response.md",
        role=role.system_prompt.strip(),
        topic=cfg.topic,
        context=cfg.brief(data).strip(),
        evidence=_evidence(cfg, data),
        history=render_history(cfg, turns),
        opponent=opponent,
        continue_reason=state.get("_continue_reason") or "None.",
    )


def render_judge_prompt(cfg: DebateConfig, state: Mapping[str, Any]) -> str:
    data = _input_of(cfg, state)
    turns: Sequence[DebateTurn] = state.get("_turns", [])
    rounds = int(state.get("_rounds_completed", 0))
    template = (
        "debate/judge_final.md"
        if rounds >= cfg.max_rounds
        else "debate/judge_round.md"
    )
    schema = json.dumps(cfg.verdict_model.model_json_schema(), separators=(",", ":"))

    return render_prompt(
        template,
        rubric=cfg.judge_rubric.strip(),
        topic=cfg.topic,
        context=cfg.brief(data).strip(),
        evidence=_evidence(cfg, data),
        history=render_history(cfg, turns),
        schema=schema,
    )
