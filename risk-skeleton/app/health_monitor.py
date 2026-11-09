"""Health Monitor.

Architecture: depends on nothing.
Serves: FR-008, NFR-006.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ComponentState(str, Enum):
    UP = "up"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    state: ComponentState
    detail: str
    checked_at: datetime


@dataclass(frozen=True)
class LivenessResult:
    alive: bool
    checked_at: datetime


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    components: tuple[ComponentHealth, ...]
    checked_at: datetime


@dataclass(frozen=True)
class PipelineStatus:
    last_market_data_at: datetime | None
    last_trade_upload_at: datetime | None
    last_risk_calculation_at: datetime | None
    activity_counts: Mapping[str, int]
    components: tuple[ComponentHealth, ...]


@dataclass
class HealthMonitor:
    probes: Mapping[str, Callable[[], bool]]  # dependency name -> reachability probe
    now: Callable[[], datetime]

    def record_activity(self, component: str, count: int) -> None:
        raise NotImplementedError("HealthMonitor.record_activity is not implemented")

    def check_liveness(self) -> LivenessResult:
        raise NotImplementedError("HealthMonitor.check_liveness is not implemented")

    def check_readiness(self) -> ReadinessResult:
        raise NotImplementedError("HealthMonitor.check_readiness is not implemented")

    def get_pipeline_status(self) -> PipelineStatus:
        raise NotImplementedError("HealthMonitor.get_pipeline_status is not implemented")
