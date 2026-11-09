"""Pre-Trade Check.

Architecture: may depend on Risk Engine, Alert Service, Audit Log.
Serves: FR-010, AC-004.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.alert_service import AlertService
from app.audit_log import AuditLog
from app.risk_engine import RiskEngine


class Decision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True)
class OrderRequest:
    order_id: str
    trader_id: str
    portfolio_id: str
    asset_id: str
    quantity: Decimal
    price: Decimal


@dataclass(frozen=True)
class PreTradeResult:
    order_id: str
    decision: Decision
    reason: str
    fail_open: bool
    exposure_before: Decimal | None
    exposure_after: Decimal | None
    credit_threshold: Decimal | None


@dataclass
class PreTradeCheck:
    risk_engine: RiskEngine
    alert_service: AlertService
    audit_log: AuditLog
    credit_threshold_for: Callable[[str], Decimal | None]  # trader_id -> threshold from RiskPolicy

    def check_order(self, order: OrderRequest) -> PreTradeResult:
        raise NotImplementedError("PreTradeCheck.check_order is not implemented")
