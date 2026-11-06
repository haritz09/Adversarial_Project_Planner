from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from core.json_utils import message_text
from core.llm import ModelResolver, resolve_model
from core.models import AGENT_A, AGENT_B, DebateConfig, DebateResult, DebateTurn
from core.prompts import render_judge_prompt, render_turn_prompt
from core.structured import VerdictParseError, invoke_verdict
from core.usage import estimate_cost, extract_usage, model_name_of

logger = logging.getLogger(__name__)

class DebateState(TypedDict, total=False):

    debate_inputs: dict[str, dict[str, Any]]
    debates: dict[str, DebateResult]

    _turns: list[DebateTurn]
    _rounds_completed: int
    _needs_another_round: bool
    _continue_reason: str | None
    _cost_usd: float

def _cost_of(model_ref: Any, message: Any) -> tuple[float, int, int]:
    input_tokens, output_tokens = extract_usage(message)
    cost = estimate_cost(model_name_of(model_ref), input_tokens, output_tokens) or 0.0
    return cost, input_tokens, output_tokens

def _make_turn_node(cfg: DebateConfig, agent: str, resolver: ModelResolver | None):
    model_ref = cfg.models.a if agent == AGENT_A else cfg.models.b

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        turns = list(state.get("_turns") or [])
        round_index = int(state.get("_rounds_completed", 0)) + 1

        llm = resolve_model(model_ref, resolver)
        prompt = render_turn_prompt(cfg, agent, state, round_index)
        message = llm.invoke(prompt)
        content = message_text(message).strip()
        if not content:
            raise ValueError(f"Agent {agent} returned an empty argument")

        cost, input_tokens, output_tokens = _cost_of(model_ref, message)
        turn: DebateTurn = {
            "agent": agent,
            "round": round_index,
            "content": content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost or None,
        }

        update: dict[str, Any] = {
            "_turns": turns + [turn],
            "_cost_usd": float(state.get("_cost_usd", 0.0)) + cost,
        }

        if agent == AGENT_B:
            update["_rounds_completed"] = round_index
        return update

    return node

def _fallback_verdict(cfg: DebateConfig, turns: Sequence[DebateTurn], reason: str):
    payload: dict[str, Any] = {
        "needs_another_round": False,
        "winner": "tie",
        "rationale": reason,
    }
    if cfg.fallback_verdict:
        payload.update(cfg.fallback_verdict(turns))
    return cfg.verdict_model.model_validate(payload)

def _make_judge_node(cfg: DebateConfig, resolver: ModelResolver | None):
    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        turns = list(state.get("_turns") or [])
        rounds = int(state.get("_rounds_completed", 0))

        if rounds < cfg.min_rounds:
            return {
                "_needs_another_round": True,
                "_continue_reason": (
                    f"Minimum of {cfg.min_rounds} rounds not reached yet."
                ),
            }

        llm = resolve_model(cfg.models.judge, resolver)
        prompt = render_judge_prompt(cfg, state)
        status = "decided"
        message = None
        try:
            verdict, message = invoke_verdict(llm, prompt, cfg.verdict_model)
        except VerdictParseError as exc:
            logger.warning("Judge verdict unreadable, using fallback: %s", exc)
            verdict = _fallback_verdict(cfg, turns, f"Judge output could not be parsed: {exc}")
            status = "fallback"

        if rounds >= cfg.max_rounds and verdict.needs_another_round:

            verdict.needs_another_round = False
            status = "max_rounds"

        cost, _, _ = _cost_of(cfg.models.judge, message) if message is not None else (0.0, 0, 0)
        total_cost = float(state.get("_cost_usd", 0.0)) + cost

        result: DebateResult = {
            "name": cfg.name,
            "topic": cfg.topic,
            "turns": turns,
            "rounds_completed": rounds,
            "winner": verdict.winner,
            "verdict": verdict.model_dump(),
            "scores": {
                "agent_a": float(verdict.agent_a_score),
                "agent_b": float(verdict.agent_b_score),
            },
            "status": status,
            "skipped": False,
            "needs_another_round": verdict.needs_another_round,
            "cost_usd": round(total_cost, 8),
        }
        debates = dict(state.get("debates") or {})
        debates[cfg.name] = result

        return {
            "debates": debates,
            "_needs_another_round": verdict.needs_another_round,
            "_continue_reason": verdict.reason_for_continuing,
            "_cost_usd": total_cost,
        }

    return node

def _make_skip_node(cfg: DebateConfig):
    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        verdict = _fallback_verdict(cfg, [], cfg.skip_reason)
        verdict.winner = "tie"
        result: DebateResult = {
            "name": cfg.name,
            "topic": cfg.topic,
            "turns": [],
            "rounds_completed": 0,
            "winner": None,
            "verdict": verdict.model_dump(),
            "scores": {
                "agent_a": float(verdict.agent_a_score),
                "agent_b": float(verdict.agent_b_score),
            },
            "status": "skipped",
            "skipped": True,
            "needs_another_round": False,
            "cost_usd": 0.0,
        }
        debates = dict(state.get("debates") or {})
        debates[cfg.name] = result
        return {"debates": debates, "_needs_another_round": False}

    return node

def _route(state: Mapping[str, Any]) -> str:
    return "continue" if state.get("_needs_another_round") else "conclude"

def build_debate(
    cfg: DebateConfig, resolver: ModelResolver | None = None
) -> Any:

    graph = StateGraph(DebateState)
    graph.add_node("debater_a", _make_turn_node(cfg, AGENT_A, resolver))
    graph.add_node("debater_b", _make_turn_node(cfg, AGENT_B, resolver))
    graph.add_node("judge", _make_judge_node(cfg, resolver))

    if cfg.skip_when is not None:
        graph.add_node("skip", _make_skip_node(cfg))
        graph.add_conditional_edges(
            START,
            lambda state: "skip" if cfg.skip_when(state) else "debate",
            {"skip": "skip", "debate": "debater_a"},
        )
        graph.add_edge("skip", END)
    else:
        graph.add_edge(START, "debater_a")

    graph.add_edge("debater_a", "debater_b")
    graph.add_edge("debater_b", "judge")
    graph.add_conditional_edges(
        "judge", _route, {"continue": "debater_a", "conclude": END}
    )
    return graph.compile()
