from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage


from core.llm import ModelSpec
from core.models import DebateModels
from review.cli import models_from_env, select_lenses
from review.context import RunContext
from review.gate import CONDITIONAL, LensReport, decide
from review.lenses import build_lens_debate
from review.models import Finding, ReviewVerdict
from review.report import write_report
from review.runner import prior_findings, run_lens
from tests.helpers import fake_model, verdict_json


def context() -> RunContext:
    return RunContext(
        repo=Path("C:/repo"),
        ref="abc123",
        dirty=False,
        profile="local",
        scope="code-only",
        started="2026-11-23T00:00:00+00:00",
    )


def seats() -> DebateModels:
    return DebateModels(
        a=ModelSpec.parse("cli:red"),
        b=ModelSpec.parse("cli:blue"),
        judge=ModelSpec.parse("cli:judge"),
    )


def judge_json() -> str:
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
                "evidence": "app/auth/session.py:41",
            }
        ],
        evidence_gaps=["no running instance"],
    )


def test_a_lens_reaches_the_report_files(tmp_path):
    models = DebateModels(
        a=fake_model("1. `app/auth/session.py:41` sets no HttpOnly."),
        b=fake_model("Confirmed at `app/auth/session.py:41`."),
        judge=fake_model(judge_json()),
    )

    report = run_lens("general", models, context())
    gate = decide([report], scope="code-only")
    json_path, md_path = write_report(
        tmp_path, context(), gate, [report], seats(), fail_on="high", strict=False
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")

    assert payload["schema_version"] == 1
    assert payload["gate"]["verdict"] == "NO-GO"
    assert payload["findings"][0]["id"] == "gen-1"
    assert payload["lenses"][0]["status"] == "decided"
    assert "gen-1" in markdown and "NO-GO" in markdown


def test_a_dead_seat_does_not_lose_the_run():
    models = DebateModels(a=fake_model(), b=fake_model(), judge=fake_model())

    report = run_lens("general", models, context())
    gate = decide([report], scope="code-only")

    assert report.status == "error"
    assert report.verdict is None
    assert gate.verdict == CONDITIONAL
    assert any("general: no usable verdict (error)" in gap for gap in gate.gaps)


def test_defaults_cover_every_lens_but_frontend():
    default = select_lenses(None)

    assert default == (
        "general",
        "security",
        "reliability",
        "correctness",
        "cost_perf",
    )
    assert select_lenses(["all"]) == default
    assert select_lenses(["general", "general"]) == ("general",)


def test_bad_input_fails_before_any_model_call():
    with pytest.raises(ValueError, match="running target"):
        select_lenses(["frontend"])
    with pytest.raises(ValueError, match="unknown lens"):
        select_lenses(["nope"])
    with pytest.raises(ValueError, match="REVIEW_MODEL_RED"):
        models_from_env({})

def test_prior_findings_feed_the_next_brief():
    earlier = LensReport(
        "security",
        ReviewVerdict(
            lens="security",
            findings=[
                Finding(
                    id="1",
                    title="Session cookie is not HttpOnly",
                    severity="high",
                    evidence="app/auth/session.py:41",
                )
            ],
        ),
    )

    prior = prior_findings([earlier])
    brief = build_lens_debate("reliability", seats()).brief(
        {"repo": "C:/repo", "prior": prior}
    )

    assert prior_findings([]) == ""
    assert "ALREADY REPORTED" in brief
    assert "Session cookie is not HttpOnly" in brief
    assert "app/auth/session.py:41" in brief


class CapturingModel:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> AIMessage:
        self.prompts.append(prompt)
        return AIMessage(content=self.response)


def test_the_next_lens_prompt_carries_the_earlier_findings():
    red = CapturingModel("1. New issue at `app/x.py:2`.")
    models = DebateModels(
        a=red,
        b=CapturingModel("Confirmed."),
        judge=CapturingModel(
            verdict_json(
                winner="tie",
                agent_a_score=5,
                agent_b_score=5,
                rationale="Nothing new.",
                findings=[],
            )
        ),
    )

    run_lens("security", models, context(), prior="- [high, open] Cookie - a.py:1")

    assert "ALREADY REPORTED" in red.prompts[0]
    assert "Cookie - a.py:1" in red.prompts[0]
