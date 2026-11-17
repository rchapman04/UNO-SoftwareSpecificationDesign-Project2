"""Market Data Ingestion.

Architecture: may depend on Position & Trade Store, Audit Log, Health Monitor.
Serves: FR-001, FR-007, NFR-004, AC-003.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.audit_log import AuditLog
from app.health_monitor import HealthMonitor
from app.position_trade_store import MarketDataRecord, PositionTradeStore


_REQUIRED_FIELDS = ("asset_id", "price", "currency", "sector", "region", "data_type", "observed_at")
_CURRENCY = re.compile(r"[A-Z]{3}")


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
        # Rules approved for slice 1 (decision 1A). All failures are collected, then raised together.
        reasons: list[str] = []
        missing = [f for f in _REQUIRED_FIELDS if raw.get(f) in (None, "")]
        if missing:
            reasons.append("missing fields: " + ", ".join(missing))

        def text_field(name: str) -> str | None:
            value = raw.get(name)
            if name in missing:
                return None
            if not isinstance(value, str) or not value.strip():
                reasons.append(f"{name} must be a non-empty string")
                return None
            return value.strip()

        asset_id = text_field("asset_id")
        sector = text_field("sector")
        region = text_field("region")
        data_type = text_field("data_type")

        currency = None
        if "currency" not in missing:
            if isinstance(raw.get("currency"), str) and _CURRENCY.fullmatch(raw["currency"]):
                currency = raw["currency"]
            else:
                reasons.append("currency must be a three-letter uppercase code")

        price = None
        if "price" not in missing:
            value = raw.get("price")
            try:
                if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
                    raise InvalidOperation
                price = Decimal(str(value))
                if not price.is_finite() or price <= 0:
                    raise InvalidOperation
            except InvalidOperation:
                reasons.append("price must be a positive number")

        observed_at = None
        if "observed_at" not in missing:
            value = raw.get("observed_at")
            try:
                if isinstance(value, datetime):
                    parsed = value
                elif isinstance(value, str):
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                else:
                    raise ValueError
                if parsed.tzinfo is None:
                    raise ValueError
                observed_at = parsed.astimezone(timezone.utc)
            except ValueError:
                reasons.append("observed_at must be an ISO 8601 timestamp with a timezone")

        if reasons:
            error = ValidationFailed("; ".join(reasons))
            error.reasons = tuple(reasons)
            raise error

        return MarketDataRecord(
            asset_id=asset_id,
            price=price,
            currency=currency,
            sector=sector,
            region=region,
            data_type=data_type,
            observed_at=observed_at,
            received_at=self.now(),
        )

    def ingest_batch(self, raw_records: Sequence[Mapping[str, Any]]) -> IngestionResult:
        # Interim (slice 1): any invalid record fails the whole batch before anything is stored.
        # Slice 4 replaces this with per-record discard and audit.
        records = [self.validate_record(raw) for raw in raw_records]
        stored = self.store.save_market_data(records)
        self.health.record_activity("market_data", stored)
        return IngestionResult(accepted=stored, rejected=0, rejection_record_ids=())