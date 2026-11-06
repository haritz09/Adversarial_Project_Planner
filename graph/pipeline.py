from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.generators import (
    debate_flow_generator,
    make_architecture_generator,
    make_plan_generator,
    make_scope_generator,
)
from agents.intake import make_intake_node
from agents.stack_debate import build_stack_debate
from core.engine import build_debate
from core.llm import ModelResolver, PlannerModels
from core.models import DebateConfig, DebateModels
from graph.state import PlannerState
from tools.export import make_export_node


def default_debates(models: PlannerModels) -> tuple[DebateConfig, ...]:
    return (
        build_stack_debate(
            DebateModels(
                a=models.debater_a,
                b=models.debater_b,
                judge=models.judge,
            )
        ),
    )

def make_prepare_node(configs: Sequence[DebateConfig]):

    def prepare_debates(state: Mapping[str, Any]) -> dict[str, Any]:
        inputs: dict[str, dict[str, Any]] = {}
        for cfg in configs:
            inputs[cfg.name] = cfg.prepare_input(state) if cfg.prepare_input else {}
        return {"debate_inputs": inputs, "current_node": "prepare_debates"}

    return prepare_debates

def build_graph(
    resolver: ModelResolver | None = None,
    configs: Sequence[DebateConfig] | None = None,
    models: PlannerModels | None = None,
    checkpointer: bool = True,
):
    models = models or PlannerModels.from_env()
    debates = tuple(configs) if configs is not None else default_debates(models)

    builder = StateGraph(PlannerState)
    builder.add_node("intake_node", make_intake_node(resolver=resolver))
    builder.add_node("prepare_debates", make_prepare_node(debates))

    for cfg in debates:
        builder.add_node(f"debate_{cfg.name}", build_debate(cfg, resolver))

    builder.add_node("architecture_generator", make_architecture_generator(resolver=resolver))
    builder.add_node("scope_generator", make_scope_generator(resolver=resolver))
    builder.add_node("plan_generator", make_plan_generator(resolver=resolver))
    builder.add_node("debate_flow_generator", debate_flow_generator)
    builder.add_node("export_node", make_export_node())

    builder.add_edge(START, "intake_node")
    builder.add_edge("intake_node", "prepare_debates")

    previous = "prepare_debates"
    for cfg in debates:
        node = f"debate_{cfg.name}"
        builder.add_edge(previous, node)
        previous = node

    builder.add_edge(previous, "architecture_generator")
    builder.add_edge("architecture_generator", "scope_generator")
    builder.add_edge("scope_generator", "plan_generator")
    builder.add_edge("plan_generator", "debate_flow_generator")
    builder.add_edge("debate_flow_generator", "export_node")
    builder.add_edge("export_node", END)

    return builder.compile(checkpointer=MemorySaver() if checkpointer else None)
