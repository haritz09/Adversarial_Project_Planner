from __future__ import annotations

import pytest

from core.engine import build_debate
from core.models import DebateModels
from core.prompts import render_judge_prompt, render_turn_prompt
from review.gate import NO_GO, LensReport, decide
from review.lenses import LENSES, build_lens_debate
from review.models import ReviewVerdict
from tests.helpers import fake_model, verdict_json

RED = "1. `app/auth/session.py:41` sets the session cookie without HttpOnly."
BLUE = "Confirmed at `app/auth/session.py:41`; no mitigation in middleware."


def judge_json(**overrides):
    return verdict_json(
        winner="tie",
        agent_a_score=5,
        agent_b_score=5,
        rationale="One confirmed finding.",
        findings=[
            {
                "id": "1",
                "title": "Session cookie is readable by JavaScript",
                "severity": "high",
                "category": "authentication",
                "evidence": "app/auth/session.py:41",
                "impact": "Any XSS steals the session.",
                "recommendation": "Set HttpOnly.",
            }
        ],
        coverage="auth reviewed",
        evidence_gaps=["no running instance: cookie flags not observed"],
        **overrides,
    )


def models(**overrides) -> DebateModels:
    return DebateModels(
        a=overrides.get("a", fake_model(RED)),
        b=overrides.get("b", fake_model(BLUE)),
        judge=overrides.get("judge", fake_model(judge_json())),
    )


def test_general_lens_reaches_the_gate_with_a_real_verdict():
    cfg = build_lens_debate("general", models())
    state = build_debate(cfg).invoke(
        {"debate_inputs": {cfg.name: {"repo": "C:/repo", "ref": "abc123"}}}
    )
    result = state["debates"]["general"]
    verdict = ReviewVerdict.model_validate(result["verdict"])

    gate = decide([LensReport("general", verdict)], scope="code-only")

    assert result["status"] == "decided"
    assert verdict.coverage == "auth reviewed"
    assert gate.verdict == NO_GO
    assert [finding.id for finding in gate.findings] == ["gen-1"]
    assert gate.findings[0].severity == "high"
    assert "general: no running instance: cookie flags not observed" in gate.gaps


@pytest.mark.parametrize("lens", LENSES, ids=lambda lens: lens.id)
def test_every_lens_builds_a_review_debate(lens):
    cfg = build_lens_debate(lens, models())
    state = {"debate_inputs": {cfg.name: {"repo": "C:/repo", "ref": "abc123"}}}

    opening = render_turn_prompt(cfg, "A", state, 1)
    judge = render_judge_prompt(cfg, state)

    assert cfg.name == lens.id
    assert cfg.verdict_model is ReviewVerdict
    assert (cfg.min_rounds, cfg.max_rounds) == (1, 2)
    assert cfg.max_turn_chars >= 8000
    assert lens.focus[0] in opening and "C:/repo" in opening
    assert '"findings"' in judge


def test_unknown_lens_fails_with_the_valid_ids():
    with pytest.raises(ValueError, match="unknown lens 'securty'"):
        build_lens_debate("securty", models())
