"""Market Data Ingestion.

Architecture: may depend on Position & Trade Store, Audit Log, Health Monitor.
Serves: FR-001, FR-007, NFR-004, AC-003.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.audit_log import AuditLog
from app.health_monitor import HealthMonitor
from app.position_trade_store import MarketDataRecord, PositionTradeStore


class ValidationFailed(ValueError):
    """A market data record failed validation. Carries the reasons."""

    reasons: tuple[str, ...]


@dataclass(frozen=True)
class IngestionResult:
    accepted: int
    rejected: int
    rejection_record_ids: tuple[str, ...]


@dataclass
class MarketDataIngestion:
    store: PositionTradeStore
    audit_log: AuditLog
    health: HealthMonitor
    now: Callable[[], datetime]

    def validate_record(self, raw: Mapping[str, Any]) -> MarketDataRecord:
        raise NotImplementedError("MarketDataIngestion.validate_record is not implemented")

    def ingest_batch(self, raw_records: Sequence[Mapping[str, Any]]) -> IngestionResult:
        raise NotImplementedError("MarketDataIngestion.ingest_batch is not implemented")
