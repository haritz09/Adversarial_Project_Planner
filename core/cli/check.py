from __future__ import annotations

import argparse
import os
from collections.abc import Mapping, Sequence

from core.cli.config import (
    ProviderConfigError,
    load_models_config,
    load_review_seats,
    provider_hints,
    resolve_models_path,
)
from core.json_utils import message_text
from core.llm import ModelSpec, available_providers, resolve_model

SEAT_PREFIXES = ("PLANNER_MODEL_", "REVIEW_MODEL_")
DEFAULT_PROMPT = "Reply with the single word OK."


def read_seats(
    env: Mapping[str, str] | None = None,
    review_seats: Mapping[str, str] | None = None,
) -> dict[str, ModelSpec]:
    """Every environment seat plus any reviewer seats configured in TOML."""
    source = env if env is not None else os.environ
    seats: dict[str, ModelSpec] = {}
    for key in sorted(source):
        if not key.startswith(SEAT_PREFIXES):
            continue
        raw = (source[key] or "").strip()
        if not raw:
            continue
        try:
            seats[key] = ModelSpec.parse(raw)
        except ValueError as exc:
            print(f"SKIP  {key}: {exc}")

    for role, raw in (review_seats or {}).items():
        key = f"REVIEW_MODEL_{role.upper()}"
        if not (source.get(key) or "").strip():
            seats[key] = ModelSpec.parse(raw)
    return seats


def _short(text: str, limit: int = 70) -> str:
    line = " ".join((text or "").split())
    return line if len(line) <= limit else line[: limit - 3] + "..."


def _probe(spec: ModelSpec, prompt: str) -> str:
    message = resolve_model(spec).invoke(prompt)
    content = message_text(message).strip()
    if not content:
        raise ProviderConfigError("empty response")
    return content


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.cli.check",
        description="Probe every configured model seat and report what works.",
    )
    parser.add_argument("--models", default=None, help="Path to models.toml")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument(
        "--quiet", action="store_true", help="Only print failures and a summary"
    )
    args = parser.parse_args(argv)

    try:
        path = resolve_models_path(args.models)
        load_models_config(path)
        review_seats = load_review_seats(path)
    except ProviderConfigError as exc:
        print(f"CONFIG ERROR: {exc}")
        return 2

    if path is not None and not args.quiet:
        print(f"Models config: {path}")

    seats = read_seats(review_seats=review_seats)
    if not seats:
        print("No seats configured. Set PLANNER_MODEL_* / REVIEW_MODEL_*.")
        print(f"Available providers: {', '.join(available_providers())}")
        return 2

    groups: dict[tuple[str, str], list[str]] = {}
    for seat, spec in seats.items():
        groups.setdefault((spec.provider, spec.model), []).append(seat)

    hints = provider_hints()
    failures = 0
    for (provider, model), seat_names in sorted(groups.items()):
        label = ", ".join(seat_names)
        spec = seats[seat_names[0]]
        try:
            content = _probe(spec, args.prompt)
        except Exception as exc:  # noqa: BLE001 - report, never abort the sweep
            failures += 1
            print(f"FAIL  {provider}:{model}  ({label})")
            print(f"      {_short(str(exc), 300)}")
            hint = hints.get(provider)
            if hint:
                print(f"      login: {hint}")
        else:
            if not args.quiet:
                print(f"OK    {provider}:{model}  ({label})  -> {_short(content)!r}")

    total = len(groups)
    print(f"\n{total - failures}/{total} model seats answered.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
