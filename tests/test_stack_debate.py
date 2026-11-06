from __future__ import annotations

from dataclasses import replace

from agents.stack_debate import (
    StackVerdict,
    build_brief,
    build_stack_debate,
    fallback_verdict,
)
from core.models import DebateModels
from core.prompts import render_judge_prompt, render_turn_prompt
from tests.helpers import fake_model

CONTEXT = {
    "goal": "real-time chat app",
    "timeline": "3 weeks",
    "team_size": 2,
    "constraints": ["must use existing auth system"],
    "stack": None,
}

INPUT = {
    "project_context": CONTEXT,
    "user_provided_fields": {"goal": True, "stack": False},
}

STATE = {
    "debate_inputs": {"tech_stack": INPUT},
    "_turns": [
        {"agent": "A", "round": 1, "content": "React + Node.js + Socket.io"},
        {"agent": "B", "round": 1, "content": "Firebase is simpler for two devs"},
    ],
    "_rounds_completed": 1,
    "_continue_reason": "Neither addressed scalability.",
}

def stack_cfg(**overrides):
    cfg = build_stack_debate(
        DebateModels(a=fake_model(), b=fake_model(), judge=fake_model())
    )
    return replace(cfg, **overrides) if overrides else cfg

def test_brief_contains_project_constraints():
    brief = build_brief(INPUT)
    assert "real-time chat app" in brief
    assert "3 weeks" in brief
    assert "must use existing auth system" in brief
    assert "Propose the best tech stack" in brief

def test_brief_challenges_a_user_supplied_stack():
    brief = build_brief(
        {
            "project_context": {**CONTEXT, "stack": "Firebase"},
            "user_provided_fields": {"stack": True},
        }
    )
    assert "Firebase" in brief
    assert "REJECT" in brief and "VALIDATE" in brief

def test_prompts_include_context_and_the_opponent_argument():
    cfg = stack_cfg()
    prompt_a = render_turn_prompt(cfg, "A", STATE, round_index=2)
    prompt_b = render_turn_prompt(cfg, "B", STATE, round_index=2)

    assert "real-time chat app" in prompt_a
    assert "Firebase is simpler for two devs" in prompt_a
    assert "Neither addressed scalability." in prompt_a
    assert "do not repeat points you already made" in prompt_a
    assert "EVIDENCE (deterministic, do not contradict it)" in prompt_a
    assert "React + Node.js + Socket.io" in prompt_b

def test_prompts_include_empty_history_guidance():
    cfg = stack_cfg()
    prompt = render_turn_prompt(cfg, "A", {"debate_inputs": {}}, round_index=1)

    assert "if empty, no arguments have been made yet" in prompt

def test_judge_prompt_contains_history_and_final_warning():
    cfg = stack_cfg(max_rounds=2)
    prompt = render_judge_prompt(cfg, {**STATE, "_rounds_completed": 2})

    assert "Agent A" in prompt
    assert "Agent B" in prompt
    assert "FINAL round" in prompt
    assert "JSON Schema" in prompt
    assert "EVIDENCE (facts, not opinions)" in prompt

def test_stack_verdict_defaults_and_clamps():
    verdict = StackVerdict.model_validate({"winner": "b", "agent_b_score": 42})
    assert verdict.winner == "B"
    assert verdict.agent_b_score == 10.0
    assert verdict.winning_stack == "undetermined"

def test_fallback_verdict_uses_the_last_argument():
    verdict = fallback_verdict(
        [{"agent": "B", "round": 1, "content": "Use Postgres for relational integrity"}]
    )
    assert "Postgres" in verdict["winning_stack"]

def test_stack_config_is_wired_for_the_engine():
    cfg = stack_cfg()
    assert cfg.name == "tech_stack"
    assert cfg.min_rounds == 2
    assert cfg.max_rounds == 3
    assert cfg.verdict_model is StackVerdict
    assert cfg.prepare_input is not None
