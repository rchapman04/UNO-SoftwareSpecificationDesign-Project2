"""Position & Trade Store.

Architecture: may depend on the database only.
Serves: FR-001, FR-002, FR-005, FR-006 (user and role tables).
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


class TradeNotFound(LookupError):
    """No trade exists with the given trade ID."""


class UserNotFound(LookupError):
    """No user exists with the given ID or username."""


class InvalidTradeFile(ValueError):
    """An uploaded trade CSV could not be parsed."""


class StoreUnavailable(RuntimeError):
    """The database cannot be reached."""


@dataclass(frozen=True)
class MarketDataRecord:
    asset_id: str
    price: Decimal
    currency: str
    sector: str
    region: str
    data_type: str
    observed_at: datetime  # vendor timestamp, UTC
    received_at: datetime  # server timestamp, UTC, assigned at ingestion


@dataclass(frozen=True)
class Trade:
    trade_id: str
    portfolio_id: str
    trader_id: str
    asset_id: str
    quantity: Decimal
    price: Decimal
    traded_at: datetime


@dataclass(frozen=True)
class Position:
    portfolio_id: str
    asset_id: str
    sector: str
    quantity: Decimal


@dataclass(frozen=True)
class UploadResult:
    inserted: int
    updated: int
    affected_portfolio_ids: tuple[str, ...]
    affected_asset_ids: tuple[str, ...]


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    username: str
    password_hash: str
    role: str  # value of access_control.Role


@dataclass
class PositionTradeStore:
    database_url: str

    def transaction(self) -> AbstractContextManager[None]:
        raise NotImplementedError("PositionTradeStore.transaction is not implemented")

    def save_market_data(self, records: Sequence[MarketDataRecord]) -> int:
        raise NotImplementedError("PositionTradeStore.save_market_data is not implemented")

    def upsert_trades(self, trades: Sequence[Trade]) -> UploadResult:
        raise NotImplementedError("PositionTradeStore.upsert_trades is not implemented")

    def upload_trade_csv(self, content: bytes, source: str) -> UploadResult:
        raise NotImplementedError("PositionTradeStore.upload_trade_csv is not implemented")

    def get_trade(self, trade_id: str) -> Trade:
        raise NotImplementedError("PositionTradeStore.get_trade is not implemented")

    def list_trades(self, portfolio_id: str) -> list[Trade]:
        raise NotImplementedError("PositionTradeStore.list_trades is not implemented")

    def list_trades_for_trader(self, trader_id: str) -> list[Trade]:
        raise NotImplementedError("PositionTradeStore.list_trades_for_trader is not implemented")

    def list_positions(self, portfolio_id: str) -> list[Position]:
        raise NotImplementedError("PositionTradeStore.list_positions is not implemented")

    def list_positions_for_assets(self, asset_ids: Sequence[str]) -> list[Position]:
        raise NotImplementedError("PositionTradeStore.list_positions_for_assets is not implemented")

    def get_latest_market_data(self, asset_ids: Sequence[str]) -> dict[str, MarketDataRecord]:
        raise NotImplementedError("PositionTradeStore.get_latest_market_data is not implemented")

    def get_user_by_username(self, username: str) -> UserRecord:
        raise NotImplementedError("PositionTradeStore.get_user_by_username is not implemented")

    def get_user(self, user_id: str) -> UserRecord:
        raise NotImplementedError("PositionTradeStore.get_user is not implemented")

    def set_user_role(self, user_id: str, role: str) -> UserRecord:
        raise NotImplementedError("PositionTradeStore.set_user_role is not implemented")
