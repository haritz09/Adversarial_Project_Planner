from __future__ import annotations

import ast
from pathlib import Path

# The one architectural invariant that cannot regress quietly: the reviewer is a
# second consumer of core/, not a second entry into the planner.
FORBIDDEN = {"agents", "graph"}


def test_review_does_not_import_the_planner():
    root = Path(__file__).resolve().parents[1] / "review"
    offenders = []

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]

            offenders.extend(
                f"{path.relative_to(root)}: {module}"
                for module in modules
                if module.split(".")[0] in FORBIDDEN
            )

    assert not offenders, f"review/ must not import the planner: {offenders}"
