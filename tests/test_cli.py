from __future__ import annotations

import json
from pathlib import Path

import main
from graph.pipeline import build_graph
from tests.helpers import demo_config, fake_model, verdict_json

INTAKE_JSON = json.dumps(
    {
        "goal": "chat app",
        "timeline": "3 weeks",
        "team_size": 2,
        "constraints": [],
        "stack": None,
        "methodology": None,
    }
)

class ScriptedResolver:
    def __init__(self, model):
        self.model = model

    def resolve(self, spec):
        return self.model

def test_cli_runs_pipeline_and_reports_export(monkeypatch, tmp_path: Path, capsys):
    resolver = ScriptedResolver(fake_model(INTAKE_JSON, "arch", "scope", "plan"))
    cfg = demo_config(name="tech_stack", judge=(verdict_json(),))

    monkeypatch.setattr(
        main,
        "build_graph",
        lambda: build_graph(resolver=resolver, configs=[cfg]),
    )

    main.main(
        [
            "--describe",
            "Build a chat app in 3 weeks with 2 devs",
            "--sink",
            "markdown",
            "--output-dir",
            str(tmp_path),
            "--thread-id",
            "cli-smoke",
            "--no-trace",
        ]
    )

    output = capsys.readouterr().out
    assert "Exported with 'markdown'" in output
    assert "Winner:  Agent A" in output
    assert (tmp_path / "cli-smoke" / "INDEX.md").exists()
