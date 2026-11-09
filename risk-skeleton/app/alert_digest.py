"""Alert Digest.

Architecture: may depend on Alert Service. Scheduled monthly (Azure timer
trigger, not yet wired). Serves: FR-012.

Delivery method is open (architecture.md, section 5). Injected as DigestDelivery.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.alert_service import Alert, AlertService
from app.audit_log import AuditLog


@dataclass(frozen=True)
class DigestEntry:
    alert_id: str
    state: str
    severity: str
    description: str
    created_at: datetime


@dataclass(frozen=True)
class Digest:
    period_start: datetime
    period_end: datetime
    entries: tuple[DigestEntry, ...]


@dataclass(frozen=True)
class DigestRun:
    period_start: datetime
    period_end: datetime
    recipient_count: int
    delivered_at: datetime


class DigestDelivery(Protocol):
    def deliver(self, recipient_id: str, digest: Digest) -> None: ...


@dataclass
class AlertDigest:
    alert_service: AlertService
    audit_log: AuditLog
    delivery: DigestDelivery | None
    recipients_for: Callable[[Alert], Sequence[str]] | None  # stakeholders in affected area
    now: Callable[[], datetime]

    def build_digest(self, period_start: datetime, period_end: datetime) -> Digest:
        raise NotImplementedError("AlertDigest.build_digest is not implemented")

    def send_monthly_digest(self, period_end: datetime | None) -> DigestRun:
        raise NotImplementedError("AlertDigest.send_monthly_digest is not implemented")
