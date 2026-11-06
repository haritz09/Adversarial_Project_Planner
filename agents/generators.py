from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.generator_prompts import (
    build_architecture_prompt,
    build_plan_prompt,
    build_scope_prompt,
)
from agents.stack_debate import DEBATE_NAME
from core.json_utils import message_text
from core.llm import ModelResolver, PlannerModels, resolve_model
from core.render import render_debate_flow


def _with_doc(state: Mapping[str, Any], key: str, value: str, node: str) -> dict[str, Any]:
    docs = dict(state.get("docs") or {})
    docs[key] = value
    return {"docs": docs, "current_node": node}


def _invoke(model: Any, prompt: str) -> str:
    return message_text(model.invoke(prompt))


def make_architecture_generator(llm: Any | None = None, resolver: ModelResolver | None = None):
    def architecture_generator(state: Mapping[str, Any]) -> dict[str, Any]:
        model = llm or resolve_model(PlannerModels.from_env().generator, resolver)
        prompt = build_architecture_prompt(state, DEBATE_NAME)
        return _with_doc(state, "architecture", _invoke(model, prompt), "architecture_generator")

    return architecture_generator


def make_scope_generator(llm: Any | None = None, resolver: ModelResolver | None = None):
    def scope_generator(state: Mapping[str, Any]) -> dict[str, Any]:
        model = llm or resolve_model(PlannerModels.from_env().generator, resolver)
        prompt = build_scope_prompt(state)
        return _with_doc(state, "scope", _invoke(model, prompt), "scope_generator")

    return scope_generator


def make_plan_generator(llm: Any | None = None, resolver: ModelResolver | None = None):
    def plan_generator(state: Mapping[str, Any]) -> dict[str, Any]:
        model = llm or resolve_model(PlannerModels.from_env().generator, resolver)
        prompt = build_plan_prompt(state, DEBATE_NAME)
        return _with_doc(state, "plan", _invoke(model, prompt), "plan_generator")

    return plan_generator


def debate_flow_generator(state: Mapping[str, Any]) -> dict[str, Any]:
    flow = render_debate_flow(
        state.get("debates") or {},
        titles={DEBATE_NAME: "Technical Stack Debate"},
    )
    return _with_doc(state, "debate_flow", flow, "debate_flow_generator")
