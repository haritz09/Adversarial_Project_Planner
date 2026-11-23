from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping

from core.cli.check import main as check_main
from core.cli.config import ProviderConfigError, load_models_config
from core.llm import ModelSpec
from core.models import DebateModels
from review.context import PROFILES, RunContext
from review.gate import LensReport, decide
from review.lenses import BY_ID, LENSES
from review.models import SEVERITIES
from review.report import write_report
from review.runner import prior_findings, run_lens

USAGE_ERROR = 3

DEFAULT_LENSES = tuple(lens.id for lens in LENSES if not lens.needs_target)

SEAT_ENV = {
    "red": "REVIEW_MODEL_RED",
    "blue": "REVIEW_MODEL_BLUE",
    "judge": "REVIEW_MODEL_JUDGE",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="review.py",
        description="Adversarial release review: GO, CONDITIONAL or NO-GO.",
    )
    parser.add_argument("--repo", default=".", help="Checkout to review")
    parser.add_argument(
        "--lens",
        action="append",
        default=None,
        metavar="ID",
        help=f"Lens to run, repeatable, or 'all'. Default: {', '.join(DEFAULT_LENSES)}",
    )
    parser.add_argument("--out", default="review-output", help="Report directory")
    parser.add_argument("--fail-on", default="high", choices=SEVERITIES)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--profile", default="auto", choices=("auto", *PROFILES))
    parser.add_argument("--models", default=None, help="Path to models.toml")
    parser.add_argument(
        "--check-models", action="store_true", help="Probe the review seats and exit"
    )
    return parser.parse_args(argv)


def select_lenses(requested: list[str] | None) -> tuple[str, ...]:
    if not requested:
        return DEFAULT_LENSES

    selected: list[str] = []
    for name in requested:
        if name == "all":
            selected.extend(DEFAULT_LENSES)
            continue
        lens = BY_ID.get(name)
        if lens is None:
            raise ValueError(
                f"unknown lens {name!r}; choose from {', '.join(BY_ID)} or 'all'"
            )
        if lens.needs_target:
            raise ValueError(f"lens {name!r} needs a running target; not available yet")
        selected.append(name)
    return tuple(dict.fromkeys(selected))


def models_from_env(env: Mapping[str, str] | None = None) -> DebateModels:
    source = os.environ if env is None else env
    seats: dict[str, ModelSpec] = {}
    for role, key in SEAT_ENV.items():
        raw = (source.get(key) or "").strip()
        if not raw:
            raise ValueError(f"{key} is not set (expected provider:model)")
        seats[role] = ModelSpec.parse(raw)
    return DebateModels(a=seats["red"], b=seats["blue"], judge=seats["judge"])


def _fail(message: str) -> int:
    print(f"review: {message}", file=sys.stderr)
    return USAGE_ERROR


def _run_and_print(
    lens: str, models: DebateModels, context: RunContext, prior: str
) -> LensReport:
    report = run_lens(lens, models, context, prior)
    found = len(report.verdict.findings) if report.verdict else 0
    print(f"  {lens}: {report.status}, {found} finding(s)")
    if report.note:
        print(f"    {report.note}")
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.check_models:
        return check_main(["--models", args.models] if args.models else [])

    try:
        load_models_config(args.models)
    except ProviderConfigError as exc:
        return _fail(f"models config: {exc}")

    try:
        lenses = select_lenses(args.lens)
        context = RunContext.capture(args.repo, profile=args.profile)
        models = models_from_env()
    except ValueError as exc:
        return _fail(str(exc))

    reports: list[LensReport] = []
    for lens in lenses:
        reports.append(
            _run_and_print(lens, models, context, prior_findings(reports))
        )
    gate = decide(
        reports, scope=context.scope, fail_on=args.fail_on, strict=args.strict
    )
    json_path, md_path = write_report(
        args.out,
        context,
        gate,
        reports,
        models,
        fail_on=args.fail_on,
        strict=args.strict,
    )

    print(f"\n{gate.verdict} (exit {gate.exit_code})")
    for reason in gate.reasons:
        print(f"  - {reason}")
    print(f"  {json_path}")
    print(f"  {md_path}")
    return gate.exit_code
