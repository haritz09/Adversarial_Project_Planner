from __future__ import annotations

from typing import Any, TypedDict

from core.models import DebateResult


class PlannerState(TypedDict, total=False):

    raw_input: str
    project_context: dict[str, Any]
    user_provided_fields: dict[str, bool]

    debate_inputs: dict[str, dict[str, Any]]
    debates: dict[str, DebateResult]

    docs: dict[str, str]
    export_config: dict[str, Any]
    export_result: dict[str, Any]

    run_id: str
    current_node: str
    trace_id: str | None
