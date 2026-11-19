from __future__ import annotations

import os
import shutil
import signal
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


class ProviderError(RuntimeError):
    """A model provider could not produce a response."""


class ProviderTimeout(ProviderError):
    """A provider exceeded its time budget and its process tree was killed."""


@dataclass(frozen=True)
class ProcessResult:
    stdout: str
    stderr: str
    returncode: int


def _tail(text: str, limit: int = 800) -> str:
    value = (text or "").strip()
    if not value:
        return "<empty>"
    return value if len(value) <= limit else "..." + value[-limit:]


def _kill_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        process.kill()


def run_process(
    command: Sequence[str],
    *,
    stdin_text: str = "",
    timeout: float = 600.0,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> ProcessResult:

    if not command:
        raise ProviderError("Empty command: nothing to execute.")
    
    executable = shutil.which(command[0])
    if executable is None:
        raise ProviderError(
            f"Executable not found: {command[0]!r}. Install it or fix `command` "
            "in your models config."
        )

    argv = [executable, *command[1:]]

    merged_env = dict(os.environ)
    for key, value in (env or {}).items():
        if value == "":
            merged_env.pop(key, None)
        else:
            merged_env[key] = value

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd is not None else None,
        env=merged_env,
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )

    try:
        stdout, stderr = process.communicate(input=stdin_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        _, stderr = process.communicate()
        raise ProviderTimeout(
            f"{Path(executable).name} timed out after {timeout:.0f}s. "
            f"stderr: {_tail(stderr)}"
        ) from None
    except KeyboardInterrupt:
        _kill_tree(process)
        raise

    if process.returncode != 0:
        raise ProviderError(
            f"{Path(executable).name} exited with code {process.returncode}. "
            f"stderr: {_tail(stderr)}"
        )

    return ProcessResult(stdout=stdout, stderr=stderr, returncode=process.returncode)
