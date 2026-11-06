from __future__ import annotations

import json
from pathlib import Path

from graph.pipeline import build_graph
from tests.helpers import demo_config, fake_model, verdict_json

INTAKE_JSON = json.dumps(
    {
        "goal": "real-time chat app",
        "timeline": "3 weeks",
        "team_size": 2,
        "constraints": ["must use existing auth"],
        "stack": None,
        "methodology": None,
    }
)

class ScriptedResolver:

    def __init__(self, model):
        self.model = model

    def resolve(self, spec):
        return self.model

def test_graph_runs_end_to_end_and_writes_markdown(tmp_path: Path):
    resolver = ScriptedResolver(
        fake_model(
            INTAKE_JSON,
            "## Chosen Stack\nFastAPI + Postgres",
            "## Objectives\nShip chat",
            "## Phases\n1. Build",
        )
    )
    cfg = demo_config(name="tech_stack")

    graph = build_graph(resolver=resolver, configs=[cfg], checkpointer=False)
    final = graph.invoke(
        {
            "raw_input": "Build a chat app in 3 weeks with 2 devs",
            "run_id": "smoke-run",
            "export_config": {"sink": "markdown", "output_dir": str(tmp_path)},
        }
    )

    assert set(final["docs"]) == {"architecture", "scope", "plan", "debate_flow"}
    assert final["project_context"]["goal"] == "real-time chat app"
    assert final["debates"]["tech_stack"]["winner"] == "A"

    result = final["export_result"]
    assert result["sink"] == "markdown"
    folder = Path(result["location"])
    files = {path.name for path in folder.glob("*.md")}
    assert files == {
        "INDEX.md",
        "01-architectural-overview.md",
        "02-scope-objectives.md",
        "03-1-full-plan.md",
        "04-debate-flow.md",
    }
    index = (folder / "INDEX.md").read_text(encoding="utf-8")
    assert "[1. Architectural Overview](01-architectural-overview.md)" in index
    assert "real-time chat app" in index

    flow = (folder / "04-debate-flow.md").read_text(encoding="utf-8")
    assert "### Round 1" in flow
    assert "Agent A" in flow

def test_graph_uses_the_second_debate_without_code_changes(tmp_path: Path):
    resolver = ScriptedResolver(
        fake_model(
            INTAKE_JSON,
            "arch",
            "scope",
            "plan",
        )
    )
    extra = demo_config(name="scope_check", judge=(verdict_json(),))

    graph = build_graph(
        resolver=resolver,
        configs=[demo_config(name="tech_stack"), extra],
        checkpointer=False,
    )
    final = graph.invoke(
        {
            "raw_input": "Build a chat app",
            "run_id": "two-debates",
            "export_config": {"sink": "markdown", "output_dir": str(tmp_path)},
        }
    )

    assert set(final["debates"]) == {"tech_stack", "scope_check"}
    assert "Pick one option" in final["docs"]["debate_flow"]
