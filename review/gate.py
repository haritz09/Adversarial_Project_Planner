from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from review.lenses import BY_ID, PROBED_LENSES
from review.models import SEVERITIES, SEVERITY_RANK, Finding, ReviewVerdict

GO = "GO"
CONDITIONAL = "CONDITIONAL"
NO_GO = "NO-GO"

EXIT_CODES = {GO: 0, CONDITIONAL: 1, NO_GO: 2}
SCOPES = ("code-only", "full")

UNUSABLE = frozenset({"fallback", "skipped"})

NOTABLE = frozenset({"high", "medium"})


@dataclass(frozen=True)
class LensReport:

    lens: str
    verdict: ReviewVerdict | None = None
    status: str = "decided"
    note: str = ""
    rounds: int = 0
    cost_usd: float | None = None


@dataclass(frozen=True)
class GateResult:
    verdict: str
    exit_code: int
    reasons: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()
    gaps: tuple[str, ...] = ()
    scope: str = "code-only"


def _validate(scope: str, fail_on: str) -> None:
    if fail_on not in SEVERITIES:
        raise ValueError(f"fail_on must be one of {', '.join(SEVERITIES)}")
    if scope not in SCOPES:
        raise ValueError(f"scope must be one of {', '.join(SCOPES)}")


def _qualify(lens_id: str, finding_id: str) -> str:
    prefix = BY_ID[lens_id].prefix if lens_id in BY_ID else lens_id
    return finding_id if finding_id.startswith(f"{prefix}-") else f"{prefix}-{finding_id}"


def _is_unverified(report: LensReport) -> bool:
    return report.verdict is None or report.status in UNUSABLE


def _findings_of(report: LensReport) -> list[Finding]:
    if report.verdict is None:
        return []
    return [
        finding.model_copy(update={"id": _qualify(report.lens, finding.id)})
        for finding in report.verdict.findings
    ]


def _gaps_of(report: LensReport) -> list[str]:
    if report.verdict is None:
        return [f"{report.lens}: no usable verdict ({report.status})"]

    gaps = [f"{report.lens}: stopped at the round limit"] if report.status == "max_rounds" else []
    if report.note:
        gaps.append(f"{report.lens}: {report.note}")
    gaps.extend(f"{report.lens}: {gap}" for gap in report.verdict.evidence_gaps)
    return gaps


def _all_findings(reports: Sequence[LensReport]) -> list[Finding]:
    findings = [finding for report in reports for finding in _findings_of(report)]
    return sorted(findings, key=lambda item: (SEVERITY_RANK[item.severity], item.id))


def _all_gaps(reports: Sequence[LensReport], scope: str) -> list[str]:
    if not reports:
        return ["no lenses executed"]
    gaps = [gap for report in reports for gap in _gaps_of(report)]
    probing = _probing_gap(reports, scope)
    if probing:
        gaps.append(probing)
    return gaps


def _blocking(findings: Sequence[Finding], fail_on: str) -> list[Finding]:
    threshold = SEVERITY_RANK[fail_on]
    return [
        item
        for item in findings
        if item.status == "open" and SEVERITY_RANK[item.severity] <= threshold
    ]


def _notable(findings: Sequence[Finding], fail_on: str) -> list[Finding]:
    threshold = SEVERITY_RANK[fail_on]
    return [
        item
        for item in findings
        if item.status == "open"
        and item.severity in NOTABLE
        and SEVERITY_RANK[item.severity] > threshold
    ]


def _unprobed(reports: Sequence[LensReport], scope: str) -> list[str]:
    if scope == "full":
        return []
    return [report.lens for report in reports if report.lens in PROBED_LENSES]


def _probing_gap(reports: Sequence[LensReport], scope: str) -> str:
    unprobed = _unprobed(reports, scope)
    if not unprobed:
        return ""
    return f"scope={scope}: active probing not executed for " + ", ".join(unprobed)


def _incomplete_reasons(
    unverified: Sequence[str], strict: bool
) -> tuple[str, list[str]]:
    return (
        NO_GO if strict else CONDITIONAL,
        ["unverified lenses: " + ", ".join(unverified)],
    )


def _verdict(
    findings: Sequence[Finding],
    reports: Sequence[LensReport],
    *,
    scope: str,
    fail_on: str,
    strict: bool,
) -> tuple[str, list[str]]:
    if not reports:
        return CONDITIONAL, ["no lenses ran: nothing was reviewed"]

    blocking = _blocking(findings, fail_on)
    if blocking:
        details = [f"{item.id} [{item.severity}] {item.title}" for item in blocking]
        return NO_GO, [f"{len(blocking)} open finding(s) at or above '{fail_on}'", *details]

    unverified = [report.lens for report in reports if _is_unverified(report)]
    if unverified:
        return _incomplete_reasons(unverified, strict)

    probing = _probing_gap(reports, scope)
    if probing and strict:
        return NO_GO, [probing]

    notable = _notable(findings, fail_on)
    if notable:
        return CONDITIONAL, [f"{len(notable)} open high/medium finding(s) below '{fail_on}'"]

    return GO, ["no open findings at or above the threshold"]


def decide(
    reports: Sequence[LensReport],
    *,
    scope: str = "code-only",
    fail_on: str = "high",
    strict: bool = False,
) -> GateResult:
    _validate(scope, fail_on)
    findings = _all_findings(reports)
    verdict, reasons = _verdict(
        findings, reports, scope=scope, fail_on=fail_on, strict=strict
    )
    return GateResult(
        verdict=verdict,
        exit_code=EXIT_CODES[verdict],
        reasons=tuple(reasons),
        findings=tuple(findings),
        gaps=tuple(_all_gaps(reports, scope)),
        scope=scope,
    )
