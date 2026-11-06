from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sinks.base import (
    Document,
    ExportResult,
    ProjectDocument,
    SinkConfigError,
    slugify,
)

NOTION_LANGUAGES = {
    "abap", "arduino", "bash", "basic", "c", "clojure", "coffeescript",
    "c++", "c#", "css", "dart", "diff", "docker", "elixir", "elm",
    "erlang", "flow", "fortran", "f#", "gherkin", "glsl", "go", "graphql",
    "groovy", "haskell", "html", "java", "javascript", "json", "julia",
    "kotlin", "latex", "less", "lisp", "livescript", "lua", "makefile",
    "markdown", "markup", "matlab", "mermaid", "nix", "objective-c",
    "ocaml", "pascal", "perl", "php", "plain text", "powershell", "prolog",
    "protobuf", "python", "r", "reason", "ruby", "rust", "sass", "scala",
    "scheme", "scss", "shell", "sql", "swift", "typescript", "vb.net",
    "verilog", "vhdl", "visual basic", "webassembly", "xml", "yaml",
}

NOTION_MAX_BLOCKS = 100
NOTION_MAX_CELL = 2000

@dataclass(frozen=True)
class NotionConfig:
    token: str
    parent_page_id: str

def load_notion_config(env: Mapping[str, str] | None = None) -> NotionConfig:
    env = env if env is not None else os.environ
    token = env.get("NOTION_CONNECTION_TOKEN") or env.get("NOTION_TOKEN")
    if not token:
        raise SinkConfigError(
            "Notion sink selected but NOTION_TOKEN / NOTION_CONNECTION_TOKEN is missing."
        )
    parent = env.get("NOTION_PARENT_PAGE_ID")
    if not parent:
        raise SinkConfigError(
            "Notion sink selected but NOTION_PARENT_PAGE_ID is missing."
        )
    return NotionConfig(token=token, parent_page_id=parent)

def _text(content: str) -> dict:
    return {"type": "text", "text": {"content": content}}

def _rich_text(content: str) -> list:
    return [_text(content)]

def _parse_code_block(lines: list[str], i: int) -> tuple[dict, int]:
    lang = lines[i][3:].strip() or "plain text"
    code_lines: list[str] = []
    i += 1
    while i < len(lines) and not lines[i].startswith("```"):
        code_lines.append(lines[i])
        i += 1
    block = {
        "object": "block",
        "type": "code",
        "code": {
            "language": lang if lang in NOTION_LANGUAGES else "plain text",
            "rich_text": _rich_text("\n".join(code_lines)),
        },
    }
    return block, i

def _is_table_separator(row: str) -> bool:
    return bool(re.match(r"^\|[\s\-\|:]+\|$", row))

def _is_bold_header_row(cells: list[str]) -> bool:
    return all(c.startswith("**") and c.endswith("**") for c in cells if c)

def _parse_table(lines: list[str], i: int) -> tuple[dict | None, int]:
    rows: list[list[str]] = []
    while i < len(lines) and lines[i].startswith("|"):
        row = lines[i]
        i += 1
        if _is_table_separator(row):
            continue
        cells = [c.strip()[:NOTION_MAX_CELL] for c in row.strip("|").split("|")]
        if _is_bold_header_row(cells):
            continue
        rows.append(cells)

    if not rows:
        return None, i

    width = max(len(row) for row in rows)
    children = [
        {
            "type": "table_row",
            "table_row": {"cells": [[_text(cell)] for cell in row + [""] * (width - len(row))]},
        }
        for row in rows
    ]
    block = {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": children,
        },
    }
    return block, i

def _parse_list_item(line: str) -> dict | None:
    if line.startswith("- ") or line.startswith("* "):
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": _rich_text(line[2:].strip())},
        }
    match = re.match(r"^\d+\. ", line)
    if match:
        return {
            "object": "block",
            "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": _rich_text(line[match.end():].strip())},
        }
    return None

def _parse_heading(line: str) -> dict | None:
    if line.startswith("### "):
        return {
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": _rich_text(line[4:].strip())},
        }
    if line.startswith("## "):
        return {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": _rich_text(line[3:].strip())},
        }
    if line.startswith("# "):
        return {
            "object": "block",
            "type": "heading_1",
            "heading_1": {"rich_text": _rich_text(line[2:].strip())},
        }
    return None

def _parse_paragraph(line: str) -> dict | None:
    if line.strip():
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": _rich_text(line.strip())},
        }
    return None

def _clean_markdown(md: str) -> str:
    md = re.sub(r"\*\*(.+?)\*\*", r"\1", md)
    md = re.sub(r"^\* ", "- ", md, flags=re.MULTILINE)
    md = re.sub(r"^\*\s+", "- ", md, flags=re.MULTILINE)
    return md

def markdown_to_blocks(md: str) -> list[dict]:
    blocks: list[dict] = []
    lines = _clean_markdown(md or "").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            block, i = _parse_code_block(lines, i)
            blocks.append(block)
        elif line.startswith("|"):
            block, i = _parse_table(lines, i)
            if block:
                blocks.append(block)
            continue
        else:
            block = _parse_heading(line) or _parse_list_item(line) or _parse_paragraph(line)
            if block:
                blocks.append(block)
        i += 1
    return blocks

async def _create_page(
    session: Any, parent_id: str, title: str, content: str = ""
) -> str:
    children = markdown_to_blocks(content) if content else []
    first_batch, remaining = children[:NOTION_MAX_BLOCKS], children[NOTION_MAX_BLOCKS:]

    payload = {
        "parent": {"type": "page_id", "page_id": parent_id},
        "properties": {"title": [{"text": {"content": title}}]},
        "children": first_batch,
    }
    result = await session.call_tool("API-post-page", payload)

    page_id = None
    try:
        page_id = json.loads(result.content[0].text).get("id")
    except Exception:
        page_id = None
    if not page_id:
        raise SinkConfigError(f"Failed to create Notion page {title!r}: {result}")

    for start in range(0, len(remaining), NOTION_MAX_BLOCKS):
        await session.call_tool(
            "API-patch-block-children",
            {"block_id": page_id, "children": remaining[start : start + NOTION_MAX_BLOCKS]},
        )
    return page_id

class NotionSink:
    name = "notion"

    def __init__(
        self,
        parent_page_id: str | None = None,
        token: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._token = token
        self._parent_page_id = parent_page_id
        self._env = env

    def _config(self) -> NotionConfig:
        if self._token and self._parent_page_id:
            return NotionConfig(token=self._token, parent_page_id=self._parent_page_id)
        return load_notion_config(self._env)

    def export(self, document: ProjectDocument, run_id: str = "") -> ExportResult:
        return asyncio.run(self._export(document, self._config()))

    async def _export(self, document: ProjectDocument, config: NotionConfig) -> ExportResult:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@notionhq/notion-mcp-server"],
            env={"NOTION_TOKEN": config.token},
        )
        urls: dict[str, str] = {}
        ids: dict[str, str] = {}

        async with stdio_client(server_params) as (read, write), ClientSession(
            read, write
        ) as session:
            await session.initialize()
            root_id = await _create_page(session, config.parent_page_id, document.title)
            ids["root"] = root_id
            urls["root"] = f"https://notion.so/{root_id.replace('-', '')}"
            await self._walk(session, root_id, document.children, urls, ids)

        return ExportResult(sink=self.name, location=urls["root"], urls=urls, page_ids=ids)

    async def _walk(
        self,
        session: Any,
        parent_id: str,
        children: tuple[Document, ...],
        urls: dict[str, str],
        ids: dict[str, str],
    ) -> None:
        for child in children:
            page_id = await _create_page(session, parent_id, child.title, child.markdown)
            key = slugify(child.title)
            ids[key] = page_id
            urls[key] = f"https://notion.so/{page_id.replace('-', '')}"
            await self._walk(session, page_id, child.children, urls, ids)
