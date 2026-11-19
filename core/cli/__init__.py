"""Bring-your-own model providers.

There is exactly one adapter for command-line agents (``CliProvider``) and one
config file that describes it. Nothing here is vendor-specific: a CLI logs in,
picks its model and uses its tools; this package only feeds it a prompt and reads
the reply.
"""

from core.cli.config import (
    ProviderConfigError,
    load_models_config,
    provider_hints,
    resolve_models_path,
)
from core.cli.process import ProcessResult, ProviderError, ProviderTimeout, run_process
from core.cli.provider import CliConfig, CliProvider

__all__ = [
    "CliConfig",
    "CliProvider",
    "ProcessResult",
    "ProviderConfigError",
    "ProviderError",
    "ProviderTimeout",
    "load_models_config",
    "provider_hints",
    "resolve_models_path",
    "run_process",
]
