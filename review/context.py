from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROFILES = ("local", "ci")

# Probing and the container lab are not built yet: every run is code-only.
CODE_ONLY = "code-only"


@dataclass(frozen=True)
class RunContext:
    repo: Path
    ref: str
    dirty: bool | None
    profile: str
    scope: str
    started: str

    @classmethod
    def capture(
        cls,
        repo: str | Path,
        *,
        profile: str = "auto",
        env: Mapping[str, str] | None = None,
    ) -> RunContext:
        path = Path(repo).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"repository not found: {path}")

        return cls(
            repo=path,
            ref=_git(path, "rev-parse", "HEAD") or "unknown",
            dirty=_dirty(path),
            profile=_profile(profile, os.environ if env is None else env),
            scope=CODE_ONLY,
            started=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )


def _profile(requested: str, env: Mapping[str, str]) -> str:
    if requested != "auto":
        if requested not in PROFILES:
            raise ValueError(f"profile must be one of auto, {', '.join(PROFILES)}")
        return requested
    return "ci" if env.get("GITHUB_ACTIONS", "").lower() == "true" else "local"


def _git(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ("git", *args),
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _dirty(repo: Path) -> bool | None:
    status = _git(repo, "status", "--porcelain")
    return None if status is None else bool(status)
