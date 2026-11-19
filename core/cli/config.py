from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from core.cli.process import ProviderError
from core.cli.provider import CliConfig, CliProvider
from core.llm import ModelSpec, register_provider

ENV_PATH = "MODELS_TOML"
DEFAULT_FILENAME = "models.toml"

KNOWN_TYPES = ("cli", "openai_compatible")

_HINTS: dict[str, str] = {}


class ProviderConfigError(ProviderError):
    """A provider block in the models config is missing or malformed."""


def _toml_module():
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError as exc:
            raise ProviderConfigError(
                "Reading models.toml needs Python 3.11+ (tomllib) or "
                "`pip install tomli`."
            ) from exc
    return tomllib


def resolve_models_path(path: str | os.PathLike[str] | None = None) -> Path | None:
    if path is not None:
        candidate = Path(path)
        if not candidate.is_file():
            raise ProviderConfigError(f"Models config not found: {candidate}")
        return candidate

    from_env = os.environ.get(ENV_PATH, "").strip()
    if from_env:
        candidate = Path(from_env)
        if not candidate.is_file():
            raise ProviderConfigError(f"{ENV_PATH} points to a missing file: {candidate}")
        return candidate

    default = Path(DEFAULT_FILENAME)
    return default if default.is_file() else None


def _strings(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ProviderConfigError(f"{where} must be a list of strings.")
    return tuple(value)


def _cli_factory(
    name: str, block: Mapping[str, Any], where: str
) -> Callable[[ModelSpec], CliProvider]:
    command = _strings(block.get("command"), f"{where}.command")
    if not command:
        raise ProviderConfigError(f"{where}.command must not be empty.")

    config = CliConfig(
        name=name,
        command=command,
        args=_strings(block.get("args"), f"{where}.args"),
        prompt_transport=str(block.get("prompt", "stdin")),
        timeout=float(block.get("timeout", 600)),
        cwd=block.get("cwd"),
        env={str(key): str(value) for key, value in (block.get("env") or {}).items()},
    )

    login = str(block.get("login", "") or "").strip()
    if login:
        _HINTS[name] = login

    return lambda spec: CliProvider(config, model=spec.model)


def _openai_compatible_factory(
    _name: str, block: Mapping[str, Any], where: str
) -> Callable[[ModelSpec], Any]:
    try:
        from langchain_openai import ChatOpenAI
    except ModuleNotFoundError as exc:
        raise ProviderConfigError(
            f'{where}: type "openai_compatible" needs the langchain-openai '
            "package.\nInstall it with: pip install langchain-openai"
        ) from exc

    base_url = block.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    api_key_env = str(block.get("api_key_env", "OPENAI_API_KEY"))
    api_key_literal = str(block.get("api_key", "") or "")
    temperature = block.get("temperature")

    def build(spec: ModelSpec) -> Any:
        api_key = api_key_literal or os.environ.get(api_key_env, "").strip()
        if not api_key:
            raise ProviderConfigError(
                f"{where}: needs {api_key_env} in the environment "
                '(or a literal `api_key`, e.g. "ollama" for a local server).'
            )
        return ChatOpenAI(
            model=spec.model,
            base_url=base_url,
            api_key=api_key,
            temperature=(
                float(temperature) if temperature is not None else spec.temperature
            ),
            max_tokens=spec.max_tokens,
        )

    return build


_FACTORIES: dict[
    str, Callable[[str, Mapping[str, Any], str], Callable[[ModelSpec], Any]]
] = {
    "cli": _cli_factory,
    "openai_compatible": _openai_compatible_factory,
}


def load_models_config(
    path: str | os.PathLike[str] | None = None,
) -> tuple[str, ...]:
    target = resolve_models_path(path)
    if target is None:
        return ()

    toml = _toml_module()
    try:
        data = toml.loads(target.read_text(encoding="utf-8"))
    except (toml.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ProviderConfigError(f"{target}: invalid TOML: {exc}") from exc

    providers = data.get("providers") or {}
    if not isinstance(providers, dict):
        raise ProviderConfigError(f"{target}: `providers` must be a table.")

    registered: list[str] = []
    for name, block in providers.items():
        where = f"{target}: providers.{name}"
        if not isinstance(block, dict):
            raise ProviderConfigError(f"{where} must be a table.")
        kind = str(block.get("type", "cli"))
        factory = _FACTORIES.get(kind)
        if factory is None:
            raise ProviderConfigError(
                f"{where}: unknown type {kind!r}. Known: {', '.join(KNOWN_TYPES)}."
            )
        register_provider(str(name))(factory(str(name), block, where))
        registered.append(str(name))

    return tuple(sorted(registered))


def provider_hints() -> dict[str, str]:
    """Configured login hints, keyed by provider name."""
    return dict(_HINTS)
