"""Position & Trade Store.

Architecture: may depend on the database only.
Serves: FR-001, FR-002, FR-005, FR-006 (user and role tables).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
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


_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a random salt. Returns a self-describing string."""
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a hash produced by hash_password."""
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p),
        )
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


@dataclass
class PositionTradeStore:
    database_url: str

    def __post_init__(self) -> None:
        # Interim in-memory storage. PostgreSQL is deferred (decision 2B). Data is lost on restart.
        self._users: dict[str, UserRecord] = {}
        self._market_data: list[MarketDataRecord] = []
        # Development seed (decision 3A): one Administrator. Change this before any shared use.
        self._users["U-admin"] = UserRecord(
            user_id="U-admin",
            username="admin",
            password_hash=hash_password("dev-only-change-me"),
            role="Administrator",
        )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        users_before = dict(self._users)
        market_before = list(self._market_data)
        try:
            yield
        except BaseException:
            self._users = users_before
            self._market_data = market_before
            raise

    def save_market_data(self, records: Sequence[MarketDataRecord]) -> int:
        self._market_data.extend(records)
        return len(records)

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
        for user in self._users.values():
            if user.username == username:
                return user
        raise UserNotFound(username)

    def get_user(self, user_id: str) -> UserRecord:
        try:
            return self._users[user_id]
        except KeyError:
            raise UserNotFound(user_id)

    def set_user_role(self, user_id: str, role: str) -> UserRecord:
        raise NotImplementedError("PositionTradeStore.set_user_role is not implemented")