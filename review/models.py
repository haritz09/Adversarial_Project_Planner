from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from core.models import BaseVerdict

Severity = Literal["critical", "high", "medium", "low", "info"]
FindingStatus = Literal["open", "resolved", "accepted_risk", "not_applicable"]

SEVERITIES: tuple[str, ...] = ("critical", "high", "medium", "low", "info")
SEVERITY_RANK = {name: index for index, name in enumerate(SEVERITIES)}

EVIDENCE_REQUIRED = ("critical", "high")


class Finding(BaseModel):
    id: str
    title: str
    severity: Severity
    category: str = ""
    evidence: str = ""
    impact: str = ""
    recommendation: str = ""
    status: FindingStatus = "open"
    rationale: str = ""

    @model_validator(mode="after")
    def _contract(self) -> Finding:
        if not self.id.strip():
            raise ValueError("id is required")
        if not self.title.strip():
            raise ValueError("title is required")
        if self.severity in EVIDENCE_REQUIRED and not self.evidence.strip():
            raise ValueError(
                f"{self.severity} findings need evidence: a path:line, a request, "
                "a log line or a quote"
            )
        if self.status == "accepted_risk" and not self.rationale.strip():
            raise ValueError("accepted_risk needs a rationale")
        return self


class ReviewVerdict(BaseVerdict):

    lens: str = ""
    findings: list[Finding] = Field(default_factory=list)
    coverage: str = ""
    evidence_gaps: list[str] = Field(default_factory=list)
