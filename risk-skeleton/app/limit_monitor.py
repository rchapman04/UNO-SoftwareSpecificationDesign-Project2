"""Limit Monitor.

Architecture: may depend on Risk Engine, Position & Trade Store, Alert Service.
Serves: FR-004, FR-010 (credit thresholds in RiskPolicy), AC-002.

The source of the active RiskPolicy is not assigned in architecture.md.
It is injected as policy_source (see contracts.md, open question 2).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.alert_service import Alert, AlertKind, AlertService, Breach, Severity
from app.risk_engine import RiskEngine, RiskMetrics


class Metric(str, Enum):
    TOTAL_EXPOSURE = "total_exposure"
    VAR = "var"


@dataclass(frozen=True)
class RiskLimit:
    limit_id: str
    metric: Metric
    scope_id: str  # portfolio ID
    threshold: Decimal
    severity: Severity  # set by RiskPolicy for this limit (AC-002)
    alert_kind: AlertKind


@dataclass(frozen=True)
class RiskPolicy:
    policy_id: str
    version: int
    limits: tuple[RiskLimit, ...]
    var_confidence: float  # at least 0.95 (FR-002)
    var_horizon_days_by_instrument_type: Mapping[str, int]
    credit_thresholds_by_trader: Mapping[str, Decimal]  # FR-010


@dataclass(frozen=True)
class LimitStatus:
    limit: RiskLimit
    measured_value: Decimal
    within_limit: bool


@dataclass
class LimitMonitor:
    risk_engine: RiskEngine
    alert_service: AlertService
    policy_source: Callable[[], RiskPolicy]

    def get_active_policy(self) -> RiskPolicy:
        raise NotImplementedError("LimitMonitor.get_active_policy is not implemented")

    def evaluate(self, metrics: RiskMetrics, policy: RiskPolicy) -> list[Breach]:
        raise NotImplementedError("LimitMonitor.evaluate is not implemented")

    def limit_statuses(self, metrics: RiskMetrics, policy: RiskPolicy) -> list[LimitStatus]:
        raise NotImplementedError("LimitMonitor.limit_statuses is not implemented")

    def evaluate_and_alert(self, metrics: RiskMetrics, policy: RiskPolicy) -> list[Alert]:
        raise NotImplementedError("LimitMonitor.evaluate_and_alert is not implemented")
