from __future__ import annotations

import sys
from pathlib import Path

import pytest

from graph.document import build_project_document
from sinks.base import Document, ProjectDocument, SinkConfigError, slugify
from sinks.markdown import MarkdownSink
from sinks.notion import NotionSink, load_notion_config
from sinks.obsidian import ObsidianSink
from sinks.registry import (
    available_sinks,
    create_sink,
    notion_configured,
    resolve_sink_name,
)

STATE = {
    "project_context": {"goal": "chat app", "timeline": "3 weeks", "team_size": 2},
    "run_id": "run-1",
    "docs": {
        "architecture": "## Chosen Stack\nFastAPI",
        "scope": "## Objectives\nShip it",
        "plan": "## Phases\n1. Build",
        "debate_flow": "# Debate Flow\n\n### Round 1",
    },
}

def test_slugify_drops_numbering_and_accents():
    assert slugify("3.1 Full Plan") == "full-plan"
    assert slugify("Diseño & Café") == "diseno-cafe"

def test_project_document_tree_matches_notion_hierarchy():
    document = build_project_document(STATE)

    assert document.title == "Chat App — Adversarial Planner"
    assert [child.title for child in document.children] == [
        "1. Architectural Overview",
        "2. Scope & Objectives",
        "3. Project Plan",
        "4. Debate Flow",
    ]
    assert document.children[2].children[0].title == "3.1 Full Plan"
    assert document.children[2].markdown == ""

def test_markdown_sink_writes_numbered_tree_and_index(tmp_path: Path):
    result = MarkdownSink(output_dir=tmp_path).export(build_project_document(STATE), "run-1")

    folder = Path(result.location)
    assert result.sink == "markdown"
    assert {p.name for p in folder.glob("*.md")} == {
        "INDEX.md",
        "01-architectural-overview.md",
        "02-scope-objectives.md",
        "03-1-full-plan.md",
        "04-debate-flow.md",
    }
    assert "[[1. Architectural Overview]]" not in (folder / "INDEX.md").read_text(encoding="utf-8")
    assert "[1. Architectural Overview](01-architectural-overview.md)" in (
        folder / "INDEX.md"
    ).read_text(encoding="utf-8")
    assert (folder / "01-architectural-overview.md").read_text(encoding="utf-8").startswith(
        "# 1. Architectural Overview"
    )

def test_obsidian_sink_changes_format_without_touching_the_pipeline(tmp_path: Path):
    result = ObsidianSink(output_dir=tmp_path).export(
        ProjectDocument(
            "Vault",
            (Document("Architecture", "## Stack\nFastAPI"),),
        ),
        "run",
    )

    folder = Path(result.location)
    note = (folder / "01-architecture.md").read_text(encoding="utf-8")
    index = (folder / "_index.md").read_text(encoding="utf-8")
    assert note.startswith("---\ntitle: Architecture\n")
    assert "[[01-architecture|Architecture]]" in index

def test_registry_auto_prefers_notion_only_when_configured():
    assert resolve_sink_name("auto", env={}) == "markdown"
    env = {"NOTION_TOKEN": "t", "NOTION_PARENT_PAGE_ID": "p"}
    assert resolve_sink_name("auto", env=env) == "notion"
    assert notion_configured(env) is True
    assert resolve_sink_name("obsidian", env={}) == "obsidian"

def test_registry_rejects_unknown_sink():
    with pytest.raises(SinkConfigError):
        resolve_sink_name("pdf", env={})
    assert "markdown" in available_sinks()

def test_markdown_sink_is_created_without_touching_notion_or_mcp():
    sink = create_sink("markdown", output_dir="unused")
    assert isinstance(sink, MarkdownSink)

    assert "mcp" not in sys.modules or "sinks.notion" not in sys.modules

def test_notion_config_is_lazy_and_explicit():
    with pytest.raises(SinkConfigError, match="NOTION_TOKEN"):
        load_notion_config({})
    with pytest.raises(SinkConfigError, match="NOTION_PARENT_PAGE_ID"):
        load_notion_config({"NOTION_TOKEN": "t"})

    sink = NotionSink(env={})
    with pytest.raises(SinkConfigError):
        sink._config()

def test_notion_walk_creates_the_same_tree_in_order(monkeypatch):
    import asyncio

    from sinks import notion as notion_module

    created = []

    async def fake_create(session, parent_id, title, content=""):
        created.append((parent_id, title, content))
        return f"id-{len(created)}"

    monkeypatch.setattr(notion_module, "_create_page", fake_create)

    document = ProjectDocument(
        "Root",
        (
            Document("1. Architectural Overview", "# A"),
            Document("3. Project Plan", "", (Document("3.1 Full Plan", "# P"),)),
        ),
    )
    urls, ids = {}, {}
    sink = NotionSink(token="t", parent_page_id="p")
    asyncio.run(sink._walk(None, "root-id", document.children, urls, ids))

    assert [title for _, title, _ in created] == [
        "1. Architectural Overview",
        "3. Project Plan",
        "3.1 Full Plan",
    ]
    assert created[2][0] == "id-2"
    assert ids["full-plan"] == "id-3"
    assert urls["project-plan"].startswith("https://notion.so/")
