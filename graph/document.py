from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sinks.base import Document, ProjectDocument


def project_title(state: Mapping[str, Any]) -> str:
    goal = (state.get("project_context") or {}).get("goal") or "Project"
    return f"{str(goal).strip().title()} — Adversarial Planner"

def build_project_document(state: Mapping[str, Any]) -> ProjectDocument:
    docs = state.get("docs") or {}
    children: list[Document] = []

    if docs.get("architecture"):
        children.append(Document("1. Architectural Overview", docs["architecture"]))
    if docs.get("scope"):
        children.append(Document("2. Scope & Objectives", docs["scope"]))
    if docs.get("plan"):
        children.append(
            Document(
                "3. Project Plan",
                "",
                (Document("3.1 Full Plan", docs["plan"]),),
            )
        )
    if docs.get("debate_flow"):
        children.append(Document("4. Debate Flow", docs["debate_flow"]))

    ctx = state.get("project_context") or {}
    metadata = {
        "goal": ctx.get("goal"),
        "timeline": ctx.get("timeline"),
        "team_size": ctx.get("team_size"),
        "run_id": state.get("run_id"),
    }
    return ProjectDocument(
        title=project_title(state),
        children=tuple(children),
        metadata=metadata,
    )
