"""Risk Engine.

Architecture: may depend on Position & Trade Store.
Serves: FR-002, FR-003, FR-005 (risk metrics for trades), FR-010 (trader exposure).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.position_trade_store import PositionTradeStore


class RiskEngineUnavailable(RuntimeError):
    """The Risk Engine cannot compute. Pre-Trade Check fails open on this."""


@dataclass(frozen=True)
class RiskMetrics:
    portfolio_id: str
    computed_at: datetime
    portfolio_value: Decimal
    total_exposure: Decimal
    var_value: Decimal
    var_confidence: float
    var_horizon_days_by_instrument_type: Mapping[str, int]
    concentration_by_sector: Mapping[str, Decimal]


@dataclass(frozen=True)
class TradeRiskMetrics:
    trade_id: str
    computed_at: datetime
    exposure: Decimal
    var_value: Decimal


@dataclass
class RiskEngine:
    store: PositionTradeStore
    now: Callable[[], datetime]

    def calculate_metrics(
        self,
        portfolio_id: str,
        var_confidence: float,
        horizon_days_by_instrument_type: Mapping[str, int],
    ) -> RiskMetrics:
        raise NotImplementedError("RiskEngine.calculate_metrics is not implemented")

    def get_trade_metrics(self, trade_id: str) -> TradeRiskMetrics:
        raise NotImplementedError("RiskEngine.get_trade_metrics is not implemented")

    def get_trader_exposure(self, trader_id: str) -> Decimal:
        raise NotImplementedError("RiskEngine.get_trader_exposure is not implemented")
