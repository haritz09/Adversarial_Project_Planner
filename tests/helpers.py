from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from core.models import BaseVerdict, DebateConfig, DebateModels, RoleSpec


def fake_model(*responses: str) -> GenericFakeChatModel:
    return GenericFakeChatModel(
        messages=iter([AIMessage(content=response) for response in responses])
    )

def verdict_json(**overrides: Any) -> str:
    payload = {
        "needs_another_round": False,
        "winner": "A",
        "rationale": "Agent A grounded the choice in the deadline.",
        "agent_a_score": 8,
        "agent_b_score": 6,
        **overrides,
    }
    return json.dumps(payload)

class DemoVerdict(BaseVerdict):
    decision: str = "undetermined"

def demo_config(
    *,
    name: str = "demo",
    a: Sequence[str] = ("A opens", "A refines"),
    b: Sequence[str] = ("B counters", "B refines"),
    judge: Sequence[str] = (verdict_json(),),
    verdict_model: type[BaseVerdict] = DemoVerdict,
    min_rounds: int = 2,
    max_rounds: int = 3,
    skip_when=None,
    brief=lambda data: "Demo context",
    evidence=None,
) -> DebateConfig:
    return DebateConfig(
        name=name,
        topic="Pick one option",
        role_a=RoleSpec("A", "You are Agent A."),
        role_b=RoleSpec("B", "You are Agent B."),
        judge_rubric="Judge the debate.",
        verdict_model=verdict_model,
        models=DebateModels(a=fake_model(*a), b=fake_model(*b), judge=fake_model(*judge)),
        brief=brief,
        min_rounds=min_rounds,
        max_rounds=max_rounds,
        skip_when=skip_when,
        evidence=evidence,
    )
