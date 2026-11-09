"""Audit Log.

Architecture: may depend on Position & Trade Store.
Serves: FR-005, FR-007, FR-009, FR-010, FR-011, NFR-001, NFR-002.
Append-only. There is no update or delete operation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from app.position_trade_store import PositionTradeStore


class EventType(str, Enum):
    TRADE_RECORDED = "trade_recorded"
    RISK_ASSESSMENT = "risk_assessment"
    ALERT_CREATED = "alert_created"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    ALERT_RESOLVED = "alert_resolved"
    PLAN_CHANGED = "plan_changed"
    ORDER_BLOCKED = "order_blocked"
    ORDER_FAILED_OPEN = "order_failed_open"
    MARKET_DATA_REJECTED = "market_data_rejected"
    POLICY_CHANGED = "policy_changed"
    AUTH_SUCCEEDED = "auth_succeeded"
    AUTH_FAILED = "auth_failed"
    AUDIT_RECORDS_ACCESSED = "audit_records_accessed"
    RECORDS_ARCHIVED = "records_archived"


@dataclass(frozen=True)
class AuditRecord:
    record_id: str
    event_type: EventType
    subject_id: str
    actor_id: str | None
    occurred_at: datetime  # server UTC, assigned by the Audit Log
    payload: Mapping[str, Any]
    archive_ref: str | None  # set once moved to WORM storage


@dataclass
class AuditLog:
    store: PositionTradeStore
    now: Callable[[], datetime]

    def append(
        self,
        event_type: EventType,
        subject_id: str,
        actor_id: str | None,
        payload: Mapping[str, Any],
    ) -> AuditRecord:
        raise NotImplementedError("AuditLog.append is not implemented")

    def get_trail(self, subject_id: str) -> list[AuditRecord]:
        raise NotImplementedError("AuditLog.get_trail is not implemented")

    def list_rejected_market_data(
        self, limit: int, after: datetime | None
    ) -> list[AuditRecord]:
        raise NotImplementedError("AuditLog.list_rejected_market_data is not implemented")

    def list_records_before(self, cutoff: datetime) -> list[AuditRecord]:
        raise NotImplementedError("AuditLog.list_records_before is not implemented")

    def mark_archived(self, record_ids: Sequence[str], archive_ref: str) -> int:
        raise NotImplementedError("AuditLog.mark_archived is not implemented")
