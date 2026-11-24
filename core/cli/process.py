from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
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


def _feed(stream, text: str) -> None:
    try:
        if text:
            stream.write(text)
        stream.close()
    except OSError:
        pass


def _drain(stream, chunks: list[str], echo: bool) -> None:
    try:
        for line in stream:
            chunks.append(line)
            if echo and sys.stderr is not None:
                sys.stderr.write(line)
                sys.stderr.flush()
    finally:
        stream.close()


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

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    threads: list[threading.Thread] = []

    try:
        threads = [
            threading.Thread(
                target=_feed, args=(process.stdin, stdin_text), daemon=True
            ),
            threading.Thread(
                target=_drain, args=(process.stdout, stdout_chunks, False), daemon=True
            ),
            threading.Thread(
                target=_drain, args=(process.stderr, stderr_chunks, True), daemon=True
            ),
        ]
        for thread in threads:
            thread.start()

        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        process.wait()
        raise ProviderTimeout(
            f"{Path(executable).name} timed out after {timeout:.0f}s. "
            f"stderr: {_tail(''.join(stderr_chunks))}"
        ) from None
    except KeyboardInterrupt:
        _kill_tree(process)
        raise
    finally:
        for thread in threads:
            thread.join()

    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)

    if process.returncode != 0:
        raise ProviderError(
            f"{Path(executable).name} exited with code {process.returncode}. "
            f"stderr: {_tail(stderr)}"
        )

    return ProcessResult(stdout=stdout, stderr=stderr, returncode=process.returncode)
