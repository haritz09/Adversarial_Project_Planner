# tools/notion.py
import asyncio
import json
import os
import re
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from graph.state import DebateState

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_CONNECTION_TOKEN") or os.getenv("NOTION_TOKEN")
if not NOTION_TOKEN:
    raise RuntimeError(".env must define NOTION_CONNECTION_TOKEN or NOTION_TOKEN")

NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID")
if not NOTION_PARENT_PAGE_ID:
    raise RuntimeError(".env must define NOTION_PARENT_PAGE_ID")

server_params = StdioServerParameters(
    command="npx",
    args=["-y", "@notionhq/notion-mcp-server"],
    env={"NOTION_TOKEN": NOTION_TOKEN},
)


# ── Markdown → Notion blocks ──────────────────────────────────────────────────

def _text(content: str) -> dict:
    return {"type": "text", "text": {"content": content}}


def _rich_text(content: str) -> list:
    return [_text(content)]


def _parse_code_block(lines: list[str], i: int) -> tuple[dict, int]:
    """
    Parses a fenced code block starting at lines[i].
    Returns (block, new_index) where new_index points past the closing fence.
    """
    lang = lines[i][3:].strip() or "plain text"
    code_lines = []
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
    return block, i  # caller increments i past the closing ```


def _is_table_separator(row: str) -> bool:
    """Returns True for rows like |---|---| that are just separators."""
    return bool(re.match(r"^\|[\s\-\|:]+\|$", row))


def _is_bold_header_row(cells: list[str]) -> bool:
    """Detect rows like | **Milestone** | **Target Date** | that duplicate the header."""
    return all(c.startswith("**") and c.endswith("**") for c in cells if c)


def _parse_table(lines: list[str], i: int) -> tuple[dict | None, int]:
    """
    Parses a Markdown table starting at lines[i].
    Returns (block, new_index) where new_index points past the last table row.
    Returns (None, new_index) if no valid rows were found.
    """
    table_rows = []
    NOTION_MAX_CELL_LENGTH = 2000
    while i < len(lines) and lines[i].startswith("|"):
        row = lines[i]
        i += 1
        if _is_table_separator(row):
            continue
        cells = [c.strip() for c in row.strip("|").split("|")]
        cells = [c[:NOTION_MAX_CELL_LENGTH] for c in cells]
        if _is_bold_header_row(cells):
            continue
        table_rows.append(cells)
 
    if not table_rows:
        return None, i
 
    width = max(len(r) for r in table_rows)
    children = []
    for row in table_rows:
        padded = row + [""] * (width - len(row))
        children.append({
            "type": "table_row",
            "table_row": {"cells": [[_text(cell)] for cell in padded]},
        })
 
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
    """Returns a list block for bullet or numbered lines, or None."""
    if line.startswith("- ") or line.startswith("* "):
        return {"object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _rich_text(line[2:].strip())}}
 
    m = re.match(r"^\d+\. ", line)
    if m:
        text = line[m.end():].strip()
        return {"object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": _rich_text(text)}}
 
    return None 


def _parse_paragraph(line: str) -> dict | None:
    """Returns a paragraph block for any non-empty line."""
    if line.strip():
        return {"object": "block", "type": "paragraph",
                "paragraph": {"rich_text": _rich_text(line.strip())}}
    return None


def _parse_heading(line: str) -> dict | None:
    """Returns a heading block for # / ## / ### lines, or None if not a heading."""
    if line.startswith("### "):
        return {"object": "block", "type": "heading_3",
                "heading_3": {"rich_text": _rich_text(line[4:].strip())}}
    if line.startswith("## "):
        return {"object": "block", "type": "heading_2",
                "heading_2": {"rich_text": _rich_text(line[3:].strip())}}
    if line.startswith("# "):
        return {"object": "block", "type": "heading_1",
                "heading_1": {"rich_text": _rich_text(line[2:].strip())}}
    return None

def _clean_markdown(md: str) -> str:
    """Normalize LLM markdown quirks before parsing."""
    # Strip bold markers from text content (keep structure, remove **)
    md = re.sub(r'\*\*(.+?)\*\*', r'\1', md)
    # Normalize * bullets to - bullets  
    md = re.sub(r'^\* ', '- ', md, flags=re.MULTILINE)
    # Strip leading * without space (orphan asterisks)
    md = re.sub(r'^\*\s+', '- ', md, flags=re.MULTILINE)
    return md


def markdown_to_blocks(md: str) -> list[dict]:
    """
    Converts a Markdown string to a list of Notion block objects.
    Supports: h1/h2/h3, bullet lists, numbered lists, code blocks, tables, paragraphs.
    """
    md = _clean_markdown(md)
    blocks = []
    lines = md.split("\n")
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
            continue  # i already advanced inside _parse_table
 
        else:
            block = (
                _parse_heading(line)
                or _parse_list_item(line)
                or _parse_paragraph(line)
            )
            if block:
                blocks.append(block)
 
        i += 1
 
    return blocks

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


# ── MCP helpers ───────────────────────────────────────────────────────────────

async def _create_page(
    session: ClientSession,
    parent_id: str,
    title: str,
    content: str = "",
) -> str:
    """Creates a Notion page and returns its ID."""
    children = markdown_to_blocks(content) if content else []

    # Notion API limits: max 100 blocks per request
    # Send first 100 blocks on creation, append the rest after
    first_batch = children[:100]
    remaining = children[100:]

    payload = {
        "parent": {"type": "page_id", "page_id": parent_id},
        "properties": {
            "title": [{"text": {"content": title}}]
        },
        "children": first_batch,
    }

    result = await session.call_tool("API-post-page", payload)

    page_id = None
    try:
        data = json.loads(result.content[0].text)
        page_id = data.get("id")
    except Exception:
        pass

    if not page_id:
        raise RuntimeError(f"Failed to create Notion page '{title}': {result}")

    # Append remaining blocks if any
    if remaining and page_id:
        for batch_start in range(0, len(remaining), 100):
            batch = remaining[batch_start:batch_start + 100]
            await session.call_tool("API-patch-block-children", {
                "block_id": page_id,
                "children": batch,
            })

    return page_id


async def _write_all_pages(state: DebateState) -> dict:
    """
    Creates the full Notion page hierarchy sequentially.
    MVP structure:
        [root]
            ├── 1. Architectural Overview
            ├── 2. Scope & Objectives
            └── 3. Project Plan
    """
    ctx = state["project_context"]
    project_name = ctx.get("goal", "Project").title()
    root_title = f"{project_name} — Adversarial Planner"

    urls = {}
    page_ids = {}

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Root page
            root_id = await _create_page(
                session,
                parent_id=NOTION_PARENT_PAGE_ID,
                title=root_title,
            )
            page_ids["root"] = root_id
            urls["root"] = f"https://notion.so/{root_id.replace('-', '')}"

            # 2. Architectural Overview
            if state.get("architecture_doc"):
                arch_id = await _create_page(
                    session,
                    parent_id=root_id,
                    title="1. Architectural Overview",
                    content=state["architecture_doc"],
                )
                page_ids["architecture"] = arch_id
                urls["architecture"] = f"https://notion.so/{arch_id.replace('-', '')}"

            # 3. Scope & Objectives
            if state.get("scope_doc"):
                scope_id = await _create_page(
                    session,
                    parent_id=root_id,
                    title="2. Scope & Objectives",
                    content=state["scope_doc"],
                )
                page_ids["scope"] = scope_id
                urls["scope"] = f"https://notion.so/{scope_id.replace('-', '')}"

            # 4. Project Plan (parent page)
            plan_parent_id = await _create_page(
                session,
                parent_id=root_id,
                title="3. Project Plan",
            )
            page_ids["plan_root"] = plan_parent_id
            urls["plan_root"] = f"https://notion.so/{plan_parent_id.replace('-', '')}"

            # 5. Project plan content as single page (MVP)
            if state.get("project_plan_doc"):
                plan_id = await _create_page(
                    session,
                    parent_id=plan_parent_id,
                    title="3.1 Full Plan",
                    content=state["project_plan_doc"],
                )
                page_ids["plan"] = plan_id
                urls["plan"] = f"https://notion.so/{plan_id.replace('-', '')}"

            # 6. Debate Flow
            if state.get("debate_flow_doc"):
                flow_id = await _create_page(
                    session,
                    parent_id=root_id,
                    title="4. Debate Flow",
                    content=state["debate_flow_doc"],
                )
                page_ids["flow"] = flow_id
                urls["flow"] = f"https://notion.so/{flow_id.replace('-', '')}"

    return {"notion_page_ids": page_ids, "notion_urls": urls}


# ── LangGraph node ────────────────────────────────────────────────────────────

def notion_writer(state: DebateState) -> dict:
    """
    LangGraph node — writes all generated documents to Notion.
    Runs synchronously by wrapping the async MCP calls.
    """
    result = asyncio.run(_write_all_pages(state))
    return {
        **result,
        "current_node": "notion_writer",
    }