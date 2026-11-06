from __future__ import annotations

from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@cache
def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def render_prompt(name: str, **values: object) -> str:
    return load_prompt(name).format(**values)

