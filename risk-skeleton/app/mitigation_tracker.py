"""Mitigation Tracker.

Architecture: may depend on Alert Service and Audit Log.
Serves: FR-011, G4.

Plan storage is not assigned in architecture.md. It is injected as
PlanRepository (see contracts.md, open question 1).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from app.alert_service import AlertService
from app.audit_log import AuditLog, AuditRecord


class PlanStatus(str, Enum):
    PLANNED = "Planned"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class PlanNotFound(LookupError):
    """No mitigation plan exists with the given ID."""


class PlanVersionConflict(RuntimeError):
    """The plan changed since the caller read it."""


@dataclass(frozen=True)
class MitigationPlan:
    plan_id: str
    alert_id: str
    owner_id: str
    status: PlanStatus
    description: str
    created_by: str
    created_at: datetime
    version: int


class PlanRepository(Protocol):
    def get(self, plan_id: str) -> MitigationPlan: ...
    def find_by_alert(self, alert_id: str) -> list[MitigationPlan]: ...
    def save(self, plan: MitigationPlan, expected_version: int | None) -> MitigationPlan: ...


@dataclass
class MitigationTracker:
    plans: PlanRepository | None
    alert_service: AlertService
    audit_log: AuditLog
    now: Callable[[], datetime]

    def create_plan(
        self, alert_id: str, owner_id: str, actor_id: str, description: str
    ) -> MitigationPlan:
        raise NotImplementedError("MitigationTracker.create_plan is not implemented")

    def update_plan(
        self,
        plan_id: str,
        actor_id: str,
        expected_version: int,
        status: PlanStatus | None,
        owner_id: str | None,
    ) -> MitigationPlan:
        raise NotImplementedError("MitigationTracker.update_plan is not implemented")

    def list_plans_for_alert(self, alert_id: str) -> list[MitigationPlan]:
        raise NotImplementedError("MitigationTracker.list_plans_for_alert is not implemented")

    def get_plan_history(self, plan_id: str) -> list[AuditRecord]:
        raise NotImplementedError("MitigationTracker.get_plan_history is not implemented")
