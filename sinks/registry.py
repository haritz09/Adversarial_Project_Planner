from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Mapping
from typing import Any

from sinks.base import ExportSink, SinkConfigError

SinkFactory = Callable[..., ExportSink]

_FACTORIES: dict[str, str | SinkFactory] = {
    "markdown": "sinks.markdown:MarkdownSink",
    "obsidian": "sinks.obsidian:ObsidianSink",
    "notion": "sinks.notion:NotionSink",
}

def register_sink(name: str, factory: str | SinkFactory) -> None:
    _FACTORIES[name] = factory

def available_sinks() -> list[str]:
    return sorted(_FACTORIES)

def notion_configured(env: Mapping[str, str] | None = None) -> bool:
    env = env if env is not None else os.environ
    token = env.get("NOTION_TOKEN") or env.get("NOTION_CONNECTION_TOKEN")
    return bool(token and env.get("NOTION_PARENT_PAGE_ID"))

def resolve_sink_name(requested: str | None = None, env: Mapping[str, str] | None = None) -> str:
    name = (requested or "auto").strip().lower()
    if name in {"", "auto"}:
        return "notion" if notion_configured(env) else "markdown"
    if name not in _FACTORIES:
        raise SinkConfigError(
            f"Unknown sink {name!r}. Available: {', '.join(available_sinks())}"
        )
    return name

def create_sink(name: str, **options: Any) -> ExportSink:
    if name not in _FACTORIES:
        raise SinkConfigError(
            f"Unknown sink {name!r}. Available: {', '.join(available_sinks())}"
        )
    factory = _FACTORIES[name]
    if isinstance(factory, str):
        module_name, _, attribute = factory.partition(":")
        factory = getattr(importlib.import_module(module_name), attribute)
    return factory(**options)
