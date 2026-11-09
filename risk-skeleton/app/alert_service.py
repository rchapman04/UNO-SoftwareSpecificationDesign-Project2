"""Alert Service.

Architecture: may depend on Audit Log and Access Control.
Serves: FR-004, AC-002, NFR-003, NFR-007.

Alert storage is not assigned in architecture.md. It is injected as
AlertRepository (see contracts.md, open question 1).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol

from app.access_control import Role
from app.audit_log import AuditLog


class Severity(str, Enum):
    CRITICAL = "Critical"
    WARNING = "Warning"
    INFORMATIVE = "Informative"


class AlertState(str, Enum):
    CREATED = "Created"
    ACKNOWLEDGED = "Acknowledged"
    RESOLVED = "Resolved"


class AlertKind(str, Enum):
    TRADE_LEVEL = "trade_level"
    POLICY_DESIGN = "policy_design"


class AlertNotFound(LookupError):
    """No alert exists with the given ID."""


class AlertVersionConflict(RuntimeError):
    """The alert changed since the caller read it. The second action is rejected."""


@dataclass(frozen=True)
class Breach:
    limit_id: str
    metric: str
    scope_id: str
    asset_ids: tuple[str, ...]
    measured_value: Decimal
    threshold: Decimal
    excess: Decimal
    severity: Severity
    kind: AlertKind
    description: str
    responsible_user_ids: tuple[str, ...]


@dataclass(frozen=True)
class Alert:
    alert_id: str
    state: AlertState
    breach: Breach
    routed_to: frozenset[Role]
    created_at: datetime
    version: int
    acknowledged_by: str | None
    acknowledged_at: datetime | None
    resolved_by: str | None
    resolved_at: datetime | None
    plan_id: str | None


@dataclass(frozen=True)
class AlertEvent:
    alert_id: str
    state: AlertState
    severity: Severity
    description: str
    occurred_at: datetime


class AlertRepository(Protocol):
    def get(self, alert_id: str) -> Alert: ...
    def find_by_state(self, state: AlertState | None) -> list[Alert]: ...
    def find_created_between(self, start: datetime, end: datetime) -> list[Alert]: ...
    def save(self, alert: Alert, expected_version: int | None) -> Alert: ...


@dataclass
class AlertService:
    alerts: AlertRepository | None
    audit_log: AuditLog
    routing: Mapping[AlertKind, frozenset[Role]]
    now: Callable[[], datetime]

    def create_alert(self, breach: Breach) -> Alert:
        raise NotImplementedError("AlertService.create_alert is not implemented")

    def get_alert(self, alert_id: str) -> Alert:
        raise NotImplementedError("AlertService.get_alert is not implemented")

    def list_alerts(
        self, viewer_id: str, viewer_role: Role, state: AlertState | None
    ) -> list[Alert]:
        raise NotImplementedError("AlertService.list_alerts is not implemented")

    def list_alerts_created_between(self, start: datetime, end: datetime) -> list[Alert]:
        raise NotImplementedError("AlertService.list_alerts_created_between is not implemented")

    def acknowledge_alert(self, alert_id: str, actor_id: str, expected_version: int) -> Alert:
        raise NotImplementedError("AlertService.acknowledge_alert is not implemented")

    def resolve_alert(
        self,
        alert_id: str,
        actor_id: str,
        expected_version: int,
        plan_id: str | None,
    ) -> Alert:
        raise NotImplementedError("AlertService.resolve_alert is not implemented")

    def open_alert_stream(self, viewer_id: str, viewer_role: Role) -> AsyncIterator[bytes]:
        raise NotImplementedError("AlertService.open_alert_stream is not implemented")

    def send_notification(self, recipient_id: str, message: str) -> None:
        raise NotImplementedError("AlertService.send_notification is not implemented")
