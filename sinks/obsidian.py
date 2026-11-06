from __future__ import annotations

from pathlib import Path

from sinks.markdown import MarkdownSink


class ObsidianSink(MarkdownSink):
    name = "obsidian"

    def __init__(self, output_dir: str | Path = "vault", **kwargs) -> None:
        kwargs.setdefault("index_name", "_index.md")
        kwargs.setdefault("link_style", "wikilink")
        kwargs.setdefault("frontmatter", True)
        super().__init__(output_dir=output_dir, **kwargs)
