from __future__ import annotations

import json
import re
from typing import Any

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


def last_json_object(text: str) -> str | None:
    """Return the last balanced ``{...}`` object, ignoring braces in strings."""
    depth = 0
    start = -1
    found: str | None = None
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start != -1:
                found = text[start : index + 1]

    return found


def parse_json_object(text: Any) -> dict[str, Any] | None:
    if not isinstance(text, str):
        text = str(text)

    candidates = [text.strip()]
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        candidates.append(fenced.group(1).strip())
    block = _JSON_BLOCK.search(text)
    if block:
        candidates.append(block.group(0))
    trailing = last_json_object(text)
    if trailing:
        candidates.append(trailing)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return None

def message_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)
