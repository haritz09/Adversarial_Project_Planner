from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from core.cli.process import ProviderError, run_process

PROMPT_TRANSPORTS = ("stdin", "arg")
NO_MODEL = "default"


@dataclass(frozen=True)
class CliConfig:
    name: str
    command: tuple[str, ...]
    args: tuple[str, ...] = ()
    prompt_transport: str = "stdin"
    timeout: float = 600.0
    cwd: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.command:
            raise ProviderError(f"Provider {self.name!r}: `command` is empty.")
        if self.prompt_transport not in PROMPT_TRANSPORTS:
            raise ProviderError(
                f"Provider {self.name!r}: `prompt` must be one of "
                f"{', '.join(PROMPT_TRANSPORTS)}, got {self.prompt_transport!r}."
            )
        if self.prompt_transport == "stdin" and any("{prompt}" in a for a in self.args):
            raise ProviderError(
                f"Provider {self.name!r}: `{{prompt}}` in args needs "
                '`prompt = "arg"`.'
            )


class CliProvider:
    """Adapter for every headless CLI agent (BYO agent)."""

    def __init__(self, config: CliConfig, model: str = NO_MODEL) -> None:
        self.config = config
        self.model = model or NO_MODEL

    def __repr__(self) -> str:
        return f"CliProvider({self.config.name!r}, model={self.model!r})"

    def _argv(self, prompt: str, model: str) -> tuple[list[str], str]:
        args = [arg.replace("{model}", model) for arg in self.config.args]

        if "{model}" not in "".join(self.config.args) and model != NO_MODEL:
            raise ProviderError(
                f"Provider {self.config.name!r} ignores the model {model!r}. "
                'Add `{model}` to its `args` (for example "--model", "{model}") '
                f'or select the seat as `{self.config.name}:{NO_MODEL}`.'
            )

        if self.config.prompt_transport == "arg":
            has_placeholder = any("{prompt}" in arg for arg in args)
            args = [arg.replace("{prompt}", prompt) for arg in args]
            if not has_placeholder:
                args.append(prompt)
            return [*self.config.command, *args], ""

        return [*self.config.command, *args], prompt

    def invoke(self, prompt: str) -> Any:
        argv, stdin_text = self._argv(prompt, self.model)

        result = run_process(
            argv,
            stdin_text=stdin_text,
            timeout=self.config.timeout,
            cwd=self.config.cwd,
            env=self.config.env,
        )

        content = (result.stdout or "").strip()
        if not content:
            raise ProviderError(
                f"Provider {self.config.name!r} returned no output. "
                f"stderr: {(result.stderr or '').strip()[-800:] or '<empty>'}"
            )

        from langchain_core.messages import AIMessage

        return AIMessage(content=content)
