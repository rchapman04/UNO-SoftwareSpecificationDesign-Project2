"""Access Control.

Architecture: may depend on Position & Trade Store (user and role tables).
Serves: FR-006, NFR-002.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from app.position_trade_store import PositionTradeStore, UserRecord


class Role(str, Enum):
    TRADER = "Trader"
    RISK_ANALYST = "Risk Analyst"
    RISK_MANAGER = "Risk Manager"
    AUDITOR = "Auditor"
    ADMINISTRATOR = "Administrator"


class AuthenticationFailed(Exception):
    """Credentials are wrong, or the token is missing, invalid or expired."""


class AuthorizationDenied(Exception):
    """The authenticated principal's role is not allowed this action."""


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: Role


@dataclass(frozen=True)
class Session:
    token: str
    principal: Principal
    expires_at: datetime


@dataclass
class AccessControl:
    store: PositionTradeStore
    signing_key: str
    now: Callable[[], datetime]
    token_ttl: timedelta = timedelta(hours=8)

    def authenticate_credentials(self, username: str, password: str) -> Session:
        raise NotImplementedError("AccessControl.authenticate_credentials is not implemented")

    def authenticate_request(self, authorization_header: str | None) -> Principal:
        raise NotImplementedError("AccessControl.authenticate_request is not implemented")

    def authorize(self, principal: Principal, allowed_roles: frozenset[Role]) -> Principal:
        raise NotImplementedError("AccessControl.authorize is not implemented")

    def assign_role(self, actor: Principal, user_id: str, role: Role) -> UserRecord:
        raise NotImplementedError("AccessControl.assign_role is not implemented")
