from __future__ import annotations

import json

from agents.intake import (
    ProjectContext,
    detect_user_provided,
    extract_context,
    make_intake_node,
)
from tests.helpers import fake_model

FULL = json.dumps(
    {
        "goal": "chat app",
        "timeline": "3 weeks",
        "team_size": 2,
        "constraints": [],
        "stack": "Firebase",
        "methodology": None,
    }
)

def test_extract_context_uses_the_schema():
    context = extract_context("Build a chat app", llm=fake_model(FULL))

    assert context["goal"] == "chat app"
    assert context["team_size"] == 2
    assert context["constraints"] == []

def test_extraction_tolerates_prose_and_fences():
    raw = f"Here you go:\n```json\n{FULL}\n```"
    assert extract_context("x", llm=fake_model(raw))["goal"] == "chat app"

def test_project_context_normalises_sloppy_values():
    context = ProjectContext.model_validate(
        {
            "goal": "  ",
            "timeline": None,
            "team_size": "solo",
            "constraints": "must use SSO",
            "stack": "",
        }
    ).model_dump()

    assert context["goal"] is None
    assert context["team_size"] is None
    assert context["constraints"] == ["must use SSO"]
    assert context["stack"] is None

def test_intake_does_not_interrupt_when_context_is_complete():
    node = make_intake_node(llm=fake_model(FULL))
    result = node({"raw_input": "Build a chat app in 3 weeks with 2 devs using Firebase"})

    assert result["project_context"]["goal"] == "chat app"
    assert result["user_provided_fields"]["stack"] is True
    assert result["current_node"] == "intake_node"

def test_intake_interrupts_then_reextracts(monkeypatch):
    answers = iter(["It is a web app for 1 dev in 1 month"])
    monkeypatch.setattr("agents.intake.interrupt", lambda message: next(answers))

    node = make_intake_node(
        llm=fake_model(
            '{"goal": null, "timeline": null, "team_size": null}',
            '{"goal": "web app", "timeline": "1 month", "team_size": 1}',
        )
    )
    result = node({"raw_input": "Help me plan"})

    assert result["project_context"]["goal"] == "web app"
    assert result["user_provided_fields"]["goal"] is True

def test_intake_applies_defaults_after_max_attempts(monkeypatch):
    monkeypatch.setattr("agents.intake.interrupt", lambda message: "still vague")
    node = make_intake_node(llm=fake_model("{}", "{}", "{}"))

    result = node({"raw_input": "plan something"})

    assert result["project_context"]["goal"] == "undefined project"
    assert result["project_context"]["timeline"] == "undefined"
    assert result["project_context"]["team_size"] == 1
    assert detect_user_provided(result["project_context"]) == {
        "goal": False,
        "timeline": False,
        "team_size": True,
        "stack": False,
        "methodology": False,
    }
