import pytest

from core.engine import build_debate
from core.models import BaseVerdict
from tests.helpers import demo_config, verdict_json


class SecondDomainVerdict(BaseVerdict):
    hired: bool = False

def run(cfg, inputs=None):
    graph = build_debate(cfg)
    return graph.invoke({"debate_inputs": {cfg.name: inputs or {"x": 1}}})

def test_engine_concludes_after_min_rounds():
    cfg = demo_config()
    result = run(cfg)["debates"]["demo"]

    assert result["rounds_completed"] == 2
    assert result["status"] == "decided"
    assert result["winner"] == "A"
    assert result["verdict"]["decision"] == "undetermined"
    assert len(result["turns"]) == 4
    assert [turn["round"] for turn in result["turns"]] == [1, 1, 2, 2]

def test_engine_runs_extra_round_when_judge_asks():
    cfg = demo_config(
        a=("A1", "A2", "A3"),
        b=("B1", "B2", "B3"),
        judge=(
            verdict_json(needs_another_round=True, reason_for_continuing="Unproven claim"),
            verdict_json(winner="B"),
        ),
    )
    result = run(cfg)["debates"]["demo"]

    assert result["rounds_completed"] == 3
    assert result["winner"] == "B"
    assert len(result["turns"]) == 6

def test_engine_never_exceeds_max_rounds():
    cfg = demo_config(
        a=("A1", "A2", "A3"),
        b=("B1", "B2", "B3"),
        judge=(
            verdict_json(needs_another_round=True),
            verdict_json(needs_another_round=True),
        ),
        max_rounds=3,
    )
    result = run(cfg)["debates"]["demo"]

    assert result["rounds_completed"] == 3
    assert result["needs_another_round"] is False
    assert result["status"] == "max_rounds"

def test_min_round_gate_does_not_call_the_judge():
    cfg = demo_config(
        a=("A1", "A2", "A3"),
        b=("B1", "B2", "B3"),
        judge=(verdict_json(),),
        min_rounds=3,
        max_rounds=3,
    )
    result = run(cfg)["debates"]["demo"]

    assert result["rounds_completed"] == 3
    assert result["status"] == "decided"

def test_engine_skip_when_does_not_call_models():
    cfg = demo_config(judge=(), skip_when=lambda state: True)
    result = run(cfg)["debates"]["demo"]

    assert result["skipped"] is True
    assert result["status"] == "skipped"
    assert result["turns"] == []
    assert result["cost_usd"] == 0.0

def test_engine_validates_verdict_and_survives_markdown_fences():
    cfg = demo_config(
        judge=(
            "Sure! Here is my decision:\n"
            "```json\n" + verdict_json(winner="b", agent_a_score=99) + "\n```",
        )
    )
    verdict = run(cfg)["debates"]["demo"]["verdict"]

    assert verdict["winner"] == "B"
    assert verdict["agent_a_score"] == 10.0

def test_engine_falls_back_when_judge_is_unreadable():
    cfg = demo_config(judge=("I refuse to answer in JSON.",))
    result = run(cfg)["debates"]["demo"]

    assert result["status"] == "fallback"
    assert result["verdict"]["needs_another_round"] is False
    assert "could not be parsed" in result["verdict"]["rationale"]

def test_same_engine_runs_a_second_domain_config():
    cfg = demo_config(name="second_domain", verdict_model=SecondDomainVerdict)
    result = run(cfg)["debates"]["second_domain"]

    assert result["name"] == "second_domain"
    assert {"name", "turns", "rounds_completed", "verdict", "scores", "status"} <= set(result)

def test_debate_config_rejects_impossible_rounds():
    with pytest.raises(ValueError):
        demo_config(min_rounds=4, max_rounds=3)
