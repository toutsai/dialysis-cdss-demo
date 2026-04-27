from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class Shift(str, Enum):
    MORNING = "早班"
    AFTERNOON = "午班"
    EVENING = "晚班"
    UNKNOWN = "未知"

    @classmethod
    def parse(cls, raw: object) -> "Shift":
        text = "" if raw is None else str(raw).strip()
        if any(token in text for token in ("早", "上午", "第一班")):
            return cls.MORNING
        if any(token in text for token in ("午", "下午", "第二班")):
            return cls.AFTERNOON
        if any(token in text for token in ("晚", "夜", "第三班")):
            return cls.EVENING
        return cls.UNKNOWN


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    OK = "ok"


class RecommendationStatus(str, Enum):
    DRAFT = "draft"
    PENDING_PHYSICIAN_REVIEW = "pending_physician_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISED = "revised"
    PENDING_NURSING_ACTION = "pending_nursing_action"
    DONE = "done"


@dataclass(frozen=True)
class Patient:
    chart_no: str
    name: str
    frequency: str
    shift: Shift
    bed: str | None = None
    identity: str = ""
    active: bool = True
    source: str = "schedule_excel"


@dataclass(frozen=True)
class DialysisSchedule:
    chart_no: str
    name: str
    frequency: str
    shift: Shift
    bed: str | None
    dialyzer: str | None = None
    dialysate_ca: str | None = None
    source_sheet: str = ""
    source_updated_at: datetime | None = None


@dataclass(frozen=True)
class LabResult:
    chart_no: str
    year_month: str
    item_key: str
    value: float | None
    unit: str = ""
    report_date: date | None = None
    source: str = "mock"


@dataclass(frozen=True)
class Medication:
    chart_no: str
    year_month: str
    order_code: str
    name: str
    dose: str = ""
    frequency: str = ""
    drug_class: str = "OTHER"
    source: str = "mock"


@dataclass(frozen=True)
class Recommendation:
    recommendation_id: str
    chart_no: str
    year_month: str
    severity: Severity
    rule_id: str
    title: str
    detail: str
    evidence: list[str] = field(default_factory=list)
    status: RecommendationStatus = RecommendationStatus.DRAFT
    claude_summary: str = ""

    def to_record(self, deid: str | None = None) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "chart_no": self.chart_no,
            "deid": deid or "",
            "year_month": self.year_month,
            "status": self.status.value,
            "severity": self.severity.value,
            "rule_id": self.rule_id,
            "title": self.title,
            "detail": self.detail,
            "evidence_json": self.evidence,
            "claude_summary": self.claude_summary,
        }
