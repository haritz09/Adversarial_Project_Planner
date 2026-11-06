from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any

from graph.document import build_project_document
from sinks.base import SinkConfigError
from sinks.registry import create_sink, resolve_sink_name

logger = logging.getLogger(__name__)

def make_export_node(
    sink_factory: Callable[..., Any] = create_sink,
):
    def export_node(state: Mapping[str, Any]) -> dict[str, Any]:
        config = dict(state.get("export_config") or {})
        requested = str(config.pop("sink", "auto"))
        output_dir = config.pop("output_dir", "output")
        sink_name = resolve_sink_name(requested)

        document = build_project_document(state)
        run_id = state.get("run_id") or document.title

        def run(name: str) -> Any:
            options: dict[str, Any] = dict(config)
            if name != "notion":
                options["output_dir"] = output_dir
            return sink_factory(name, **options).export(document, run_id)

        try:
            result = run(sink_name)
            payload = result.as_dict()
        except SinkConfigError:
            raise
        except Exception as exc:

            if requested.lower() not in {"auto", ""}:
                raise
            logger.warning("Sink %r failed (%s); falling back to markdown", sink_name, exc)
            payload = run("markdown").as_dict()
            payload["fallback_from"] = sink_name
            payload["fallback_reason"] = str(exc)

        return {"export_result": payload, "current_node": "export_node"}

    return export_node

export_node = make_export_node()
