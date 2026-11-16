from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CheckId = Literal["title", "language", "headings", "images", "tables", "links"]
CheckResult = Literal["passed", "issues", "needs_review", "not_evaluated"]
Severity = Literal["high", "medium", "low"]
Confidence = Literal["high", "medium", "low"]
FindingStatus = Literal["open", "fixed_unverified", "verified_fixed", "needs_review", "dismissed"]
FixType = Literal["set_title", "set_language", "set_alt_text", "set_link_text", "set_table_header", "set_heading"]


class Finding(BaseModel):
    id: str
    check_id: CheckId
    location: str
    locator: dict[str, int | float | str]
    evidence: str
    barrier: str
    suggestion: str
    severity: Severity
    confidence: Confidence
    status: FindingStatus
    fixable: Literal["teacher_approved", "recommendation_only"]
    preview: str | None = Field(default=None, exclude_if=lambda value: value is None)
    suggested_value: str | None = Field(default=None, exclude_if=lambda value: value is None)


class Check(BaseModel):
    id: CheckId
    label: str
    result: CheckResult
    summary: str
    finding_ids: list[str]


class AuditProgress(BaseModel):
    passed: int
    evaluated: int
    percent: int | None


class Audit(BaseModel):
    audit_id: UUID
    document_id: UUID
    created_at: datetime
    checks: list[Check]
    findings: list[Finding]
    progress: AuditProgress


class FixPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str | None = None
    lang: str | None = None
    alt_text: str | None = None
    decorative: bool | None = None
    new_text: str | None = None
    heading_level: int | None = Field(default=None, ge=1, le=6)


class Fix(BaseModel):
    finding_id: str
    type: FixType
    payload: FixPayload


class FixRequest(BaseModel):
    fixes: list[Fix]


class AppliedFix(BaseModel):
    finding_id: str
    status: Literal["fixed_unverified"]


class SkippedFix(BaseModel):
    finding_id: str
    reason: str


class FixResponse(BaseModel):
    applied: list[AppliedFix]
    skipped: list[SkippedFix]


class AuditDiff(BaseModel):
    verified_fixed: list[str]
    still_open: list[str]
    new_findings: list[str]
    needs_review: list[str]
    progress_before: AuditProgress
    progress_after: AuditProgress


class ReauditResponse(BaseModel):
    audit: Audit
    diff: AuditDiff


class UploadResponse(BaseModel):
    document_id: UUID
    filename: str = Field(min_length=1)
    audit: Audit


class ReaderItem(BaseModel):
    type: str
    text: str
    issue: str | None = None
    finding_id: str | None = None


class ReaderPreview(BaseModel):
    version: Literal["original", "repaired"]
    items: list[ReaderItem]
