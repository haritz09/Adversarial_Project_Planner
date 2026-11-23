from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.models import DebateModels
from review.context import RunContext
from review.gate import GateResult, LensReport
from review.models import Finding

SCHEMA_VERSION = 1


def seat_names(models: DebateModels) -> dict[str, str]:
    def seat(spec: Any) -> str:
        return f"{spec.provider}:{spec.model}"

    return {"red": seat(models.a), "blue": seat(models.b), "judge": seat(models.judge)}


def _finding_count(report: LensReport) -> int:
    return len(report.verdict.findings) if report.verdict else 0


def _summary(report: LensReport) -> str:
    if report.verdict is None:
        return report.note
    return report.verdict.rationale or report.note


def _lens_payload(report: LensReport) -> dict[str, Any]:
    return {
        "id": report.lens,
        "status": report.status,
        "rounds": report.rounds,
        "findings": _finding_count(report),
        "cost_usd": report.cost_usd,
        "summary": _summary(report),
    }


def build_payload(
    context: RunContext,
    gate: GateResult,
    reports: list[LensReport],
    models: DebateModels,
    *,
    fail_on: str,
    strict: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "repo": str(context.repo),
            "ref": context.ref,
            "dirty": context.dirty,
            "profile": context.profile,
            "started": context.started,
        },
        "scope": context.scope,
        "models": seat_names(models),
        "lenses": [_lens_payload(report) for report in reports],
        "findings": [finding.model_dump() for finding in gate.findings],
        "gate": {
            "verdict": gate.verdict,
            "exit_code": gate.exit_code,
            "fail_on": fail_on,
            "strict": strict,
            "reasons": list(gate.reasons),
        },
        "coverage": {"gaps": list(gate.gaps)},
    }


def _cell(value: str) -> str:
    return " ".join(str(value).split()).replace("|", "\\|")


def _finding_row(finding: Finding) -> str:
    return (
        f"| {finding.id} | {finding.severity} | {finding.status} "
        f"| {_cell(finding.title)} | {_cell(finding.evidence)} |"
    )


def to_markdown(
    context: RunContext,
    gate: GateResult,
    reports: list[LensReport],
    *,
    fail_on: str,
    strict: bool,
) -> str:
    lines = [
        f"# Adversarial review - {gate.verdict}",
        "",
        f"`{context.repo}` @ `{context.ref}`"
        f"{' (dirty)' if context.dirty else ''} | profile `{context.profile}`"
        f" | scope `{context.scope}` | fail on `{fail_on}`"
        f"{' | strict' if strict else ''}",
        "",
        "## Why",
        "",
        *(f"- {reason}" for reason in gate.reasons),
        "",
        f"## Findings ({len(gate.findings)})",
        "",
    ]

    if gate.findings:
        lines += [
            "| id | severity | status | finding | evidence |",
            "| --- | --- | --- | --- | --- |",
            *(_finding_row(finding) for finding in gate.findings),
        ]
    else:
        lines.append("No open findings.")

    lines += ["", "## Coverage gaps", ""]
    lines += [f"- {_cell(gap)}" for gap in gate.gaps] or ["- none recorded"]
    lines += [
        "",
        "## Lenses",
        "",
        "| lens | status | rounds | findings | cost |",
        "| --- | --- | --- | --- | --- |",
    ]
    for report in reports:
        cost = f"${report.cost_usd:.6f}" if report.cost_usd else "unknown"
        lines.append(
            f"| {report.lens} | {report.status} | {report.rounds} "
            f"| {_finding_count(report)} | {cost} |"
        )
    return "\n".join(lines) + "\n"


def write_report(
    out: str | Path,
    context: RunContext,
    gate: GateResult,
    reports: list[LensReport],
    models: DebateModels,
    *,
    fail_on: str,
    strict: bool,
) -> tuple[Path, Path]:
    directory = Path(out)
    directory.mkdir(parents=True, exist_ok=True)

    payload = build_payload(
        context, gate, reports, models, fail_on=fail_on, strict=strict
    )
    json_path = directory / "review.json"
    md_path = directory / "review.md"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md_path.write_text(
        to_markdown(context, gate, reports, fail_on=fail_on, strict=strict),
        encoding="utf-8",
    )
    return json_path, md_path
