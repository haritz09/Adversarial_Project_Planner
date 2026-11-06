from __future__ import annotations

import pytest

from sinks.base import ExportResult
from tools.export import make_export_node

STATE = {
    "project_context": {"goal": "chat app"},
    "run_id": "run-1",
    "docs": {"architecture": "# Arch", "scope": "# Scope", "plan": "# Plan"},
}

class OkSink:
    def export(self, document, run_id):
        return ExportResult("markdown", f"out/{run_id}", {"index": "out/INDEX.md"})

class BrokenSink:
    def export(self, document, run_id):
        raise RuntimeError("npx is not installed")

def factory(name, **options):
    return BrokenSink() if name == "notion" else OkSink()

def test_auto_falls_back_to_markdown_when_notion_breaks(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "token")
    monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "page")

    result = make_export_node(factory)(STATE)["export_result"]

    assert result["sink"] == "markdown"
    assert result["fallback_from"] == "notion"
    assert "npx" in result["fallback_reason"]

def test_auto_uses_markdown_without_notion_credentials():
    result = make_export_node(factory)(STATE)["export_result"]

    assert result["sink"] == "markdown"
    assert "fallback_from" not in result

def test_explicit_notion_failure_is_not_hidden():
    with pytest.raises(RuntimeError, match="npx"):
        make_export_node(factory)({**STATE, "export_config": {"sink": "notion"}})
