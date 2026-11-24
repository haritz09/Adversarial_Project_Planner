from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from core.engine import build_debate
from core.models import DebateModels
from review.context import RunContext
from review.gate import LensReport
from review.lenses import build_lens_debate
from review.models import ReviewVerdict


def _inputs(context: RunContext, lens: str, prior: str) -> dict[str, Any]:
    return {
        "debate_inputs": {
            lens: {
                "repo": str(context.repo),
                "ref": context.ref,
                "scope": context.scope,
                "prior": prior,
            }
        }
    }


def prior_findings(reports: Sequence[LensReport]) -> str:
    return "\n".join(
        f"- [{finding.severity}, {finding.status}] {finding.title}"
        + (f" - {finding.evidence}" if finding.evidence else "")
        for report in reports
        if report.verdict is not None
        for finding in report.verdict.findings
    )


def _report_of(lens: str, result: dict[str, Any]) -> LensReport:
    try:
        verdict = ReviewVerdict.model_validate(result.get("verdict") or {})
    except ValidationError as exc:
        return LensReport(lens, None, status="error", note=f"unreadable verdict: {exc}")
    return LensReport(
        lens,
        verdict,
        status=str(result.get("status") or "decided"),
        rounds=int(result.get("rounds_completed") or 0),
        cost_usd=result.get("cost_usd"),
    )


def run_lens(
    lens: str, models: DebateModels, context: RunContext, prior: str = ""
) -> LensReport:
    cfg = build_lens_debate(lens, models)
    try:
        state = build_debate(cfg).invoke(_inputs(context, cfg.name, prior))
        result = state["debates"][cfg.name]
    except Exception as exc:  # noqa: BLE001 - one dead seat must not hide the others
        return LensReport(
            cfg.name, None, status="error", note=f"{type(exc).__name__}: {exc}"
        )
    return _report_of(cfg.name, result)
