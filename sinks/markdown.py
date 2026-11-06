from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sinks.base import Document, ExportResult, ProjectDocument, slugify


@dataclass(frozen=True)
class IndexEntry:
    title: str
    path: str
    depth: int
    stem: str

class MarkdownSink:

    name = "markdown"

    def __init__(
        self,
        output_dir: str | Path = "output",
        index_name: str = "INDEX.md",
        link_style: str = "markdown",
        frontmatter: bool = False,
        tags: tuple[str, ...] = ("adversarial-planner",),
    ) -> None:
        self.output_dir = Path(output_dir)
        self.index_name = index_name
        self.link_style = link_style
        self.frontmatter = frontmatter
        self.tags = tags

    def render_document(self, document: Document) -> str:
        body = f"# {document.title}\n\n{document.markdown}".rstrip() + "\n"
        return self._with_frontmatter(document, body)

    def render_link(self, entry: IndexEntry) -> str:
        if self.link_style == "wikilink":
            return f"[[{entry.stem}|{entry.title}]]"
        return f"[{entry.title}]({entry.path.replace(' ', '%20')})"

    def _with_frontmatter(self, document: Document, body: str) -> str:
        if not self.frontmatter:
            return body
        tag_list = ", ".join(self.tags)
        return f"---\ntitle: {document.title}\ntags: [{tag_list}]\n---\n\n{body}"

    def export(self, document: ProjectDocument, run_id: str = "") -> ExportResult:
        folder = self.output_dir / slugify(run_id or document.title)
        folder.mkdir(parents=True, exist_ok=True)

        entries: list[IndexEntry] = []
        self._write_children(document.children, folder, "", 0, entries)
        index_path = folder / self.index_name
        index_path.write_text(self._render_index(document, entries), encoding="utf-8")

        return ExportResult(
            sink=self.name,
            location=str(folder),
            urls={entry.stem: str(entry.path) for entry in entries},
        )

    def _write_children(
        self,
        children: tuple[Document, ...],
        folder: Path,
        prefix: str,
        depth: int,
        entries: list[IndexEntry],
    ) -> None:
        for index, child in enumerate(children, start=1):
            label = f"{prefix}{index:02d}" if not prefix else f"{prefix}-{index}"
            if child.markdown:
                stem = f"{label}-{slugify(child.title)}"
                filename = f"{stem}.md"
                (folder / filename).write_text(self.render_document(child), encoding="utf-8")
                entries.append(
                    IndexEntry(title=child.title, path=filename, depth=depth, stem=stem)
                )
            self._write_children(child.children, folder, label, depth + 1, entries)

    def _render_index(self, document: ProjectDocument, entries: list[IndexEntry]) -> str:
        lines = [f"# {document.title}", ""]
        metadata = document.metadata or {}
        if metadata.get("goal"):
            lines += [f"**Goal:** {metadata['goal']}", ""]
        for entry in entries:
            indent = "  " * entry.depth
            lines.append(f"{indent}- {self.render_link(entry)}")
        return "\n".join(lines).rstrip() + "\n"
