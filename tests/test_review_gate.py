from __future__ import annotations

import pytest
from pydantic import ValidationError

from review.gate import CONDITIONAL, EXIT_CODES, GO, NO_GO, GateResult, LensReport, decide
from review.models import Finding, ReviewVerdict

# Each case is a tiny scenario: which lens ran, what it found, how it ended, and
# the decide() options. One row per rule that can regress.
CASES = [
    ("nothing reviewed", {"lens": None}, CONDITIONAL),
    ("clean", {"lens": "general"}, GO),
    ("info only", {"lens": "general", "severities": ("info",)}, GO),
    ("low only", {"lens": "general", "severities": ("low",)}, GO),
    (
        "low blocks when the bar is low",
        {"lens": "general", "severities": ("low",), "fail_on": "low"},
        NO_GO,
    ),
    ("medium only", {"lens": "general", "severities": ("medium",)}, CONDITIONAL),
    (
        "medium blocks when asked",
        {"lens": "general", "severities": ("medium",), "fail_on": "medium"},
        NO_GO,
    ),
    ("high blocks by default", {"lens": "general", "severities": ("high",)}, NO_GO),
    (
        "high only warns when the bar is critical",
        {"lens": "general", "severities": ("high",), "fail_on": "critical"},
        CONDITIONAL,
    ),
    (
        "critical always blocks",
        {"lens": "general", "severities": ("critical",), "fail_on": "critical"},
        NO_GO,
    ),
    (
        "accepted risk does not block",
        {"lens": "general", "severities": ("high",), "finding_status": "accepted_risk"},
        GO,
    ),
    (
        "resolved does not block",
        {"lens": "general", "severities": ("critical",), "finding_status": "resolved"},
        GO,
    ),
    ("fallback is conditional", {"lens": "general", "lens_status": "fallback"}, CONDITIONAL),
    (
        "fallback is no-go when strict",
        {"lens": "general", "lens_status": "fallback", "strict": True},
        NO_GO,
    ),
    ("security without a target is conditional", {"lens": "security"}, CONDITIONAL),
    (
        "security passes with a full scope",
        {"lens": "security", "scope": "full"},
        GO,
    ),
]

DECIDE_OPTIONS = ("scope", "fail_on", "strict")


def run(case: dict) -> GateResult:
    reports: list[LensReport] = []
    if case["lens"] is not None:
        findings = [
            Finding(
                id=str(index),
                title=f"{severity} issue",
                severity=severity,
                evidence="app/handler.py:42",
                status=case.get("finding_status", "open"),
                rationale=(
                    "covered by the gateway"
                    if case.get("finding_status") == "accepted_risk"
                    else ""
                ),
            )
            for index, severity in enumerate(case.get("severities", ()), start=1)
        ]
        status = case.get("lens_status", "decided")
        verdict = (
            None
            if status in {"fallback", "skipped"}
            else ReviewVerdict(lens=case["lens"], findings=findings)
        )
        reports.append(LensReport(case["lens"], verdict, status=status))

    options = {key: case[key] for key in DECIDE_OPTIONS if key in case}
    return decide(reports, **options)


@pytest.mark.parametrize(
    "case, expected", [(case[1], case[2]) for case in CASES], ids=[case[0] for case in CASES]
)
def test_decision_matrix(case, expected):
    result = run(case)
    assert result.verdict == expected
    assert result.exit_code == EXIT_CODES[expected]


def test_findings_are_namespaced_per_lens_and_sorted_by_severity():
    security = ReviewVerdict(
        lens="security",
        findings=[
            Finding(id="2", title="medium", severity="medium", evidence="x:1"),
            Finding(id="1", title="critical", severity="critical", evidence="x:2"),
        ],
    )
    reliability = ReviewVerdict(
        lens="reliability",
        findings=[Finding(id="sec-1", title="already prefixed", severity="low")],
    )

    result = decide(
        [LensReport("security", security), LensReport("reliability", reliability)],
        scope="full",
    )

    assert [finding.id for finding in result.findings] == ["sec-1", "sec-2", "ops-sec-1"]


def test_finding_contract_rejects_guesses():
    with pytest.raises(ValidationError):
        Finding(id="1", title="no evidence", severity="high")

    with pytest.raises(ValidationError):
        Finding(
            id="1",
            title="accepted without a reason",
            severity="high",
            evidence="app/x.py:1",
            status="accepted_risk",
        )

    with pytest.raises(ValidationError):
        Finding(id=" ", title="no id", severity="low")

    assert Finding(id="1", title="fine", severity="medium").status == "open"
