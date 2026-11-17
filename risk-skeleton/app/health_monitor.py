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

    def __post_init__(self) -> None:
        self._activity_counts: dict[str, int] = {}
        self._last_activity: dict[str, datetime] = {}

    def record_activity(self, component: str, count: int) -> None:
        self._activity_counts[component] = self._activity_counts.get(component, 0) + count
        self._last_activity[component] = self.now()

    def check_liveness(self) -> LivenessResult:
        # Does not call the probes (contracts.md §1.3).
        return LivenessResult(alive=True, checked_at=self.now())

    def check_readiness(self) -> ReadinessResult:
        checked_at = self.now()
        components: list[ComponentHealth] = []
        for name, probe in self.probes.items():
            try:
                reachable = bool(probe())
                state = ComponentState.UP if reachable else ComponentState.DOWN
                detail = "reachable" if reachable else "probe reported unreachable"
            except Exception as exc:
                # A probe error means the dependency is down. Only the exception type is
                # reported: this endpoint has no authentication, so messages may hold internals.
                state = ComponentState.DOWN
                detail = f"probe failed ({type(exc).__name__})"
            components.append(
                ComponentHealth(name=name, state=state, detail=detail, checked_at=self.now())
            )
        ready = all(c.state is not ComponentState.DOWN for c in components)
        return ReadinessResult(ready=ready, components=tuple(components), checked_at=checked_at)

    def get_pipeline_status(self) -> PipelineStatus:
        # Component names are fixed: "market_data", "trade_upload", "risk_calculation" (decision 3A).
        return PipelineStatus(
            last_market_data_at=self._last_activity.get("market_data"),
            last_trade_upload_at=self._last_activity.get("trade_upload"),
            last_risk_calculation_at=self._last_activity.get("risk_calculation"),
            activity_counts=dict(self._activity_counts),
            components=self.check_readiness().components,
        )