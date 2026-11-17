"""Access Control.

Architecture: may depend on Position & Trade Store (user and role tables).
Serves: FR-006, NFR-002.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

import jwt

from app.position_trade_store import PositionTradeStore, UserNotFound, UserRecord, verify_password

_ALGORITHM = "HS256"
_BEARER = "Bearer "


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
        # Unknown user and wrong password give the same error, so the response does not reveal which.
        try:
            user = self.store.get_user_by_username(username)
        except UserNotFound:
            raise AuthenticationFailed("unknown user or wrong password")
        if not verify_password(password, user.password_hash):
            raise AuthenticationFailed("unknown user or wrong password")
        issued_at = self.now()
        expires_at = issued_at + self.token_ttl
        token = jwt.encode(
            {
                "sub": user.user_id,
                "iat": int(issued_at.timestamp()),
                "exp": int(expires_at.timestamp()),
            },
            self.signing_key,
            algorithm=_ALGORITHM,
        )
        return Session(
            token=token,
            principal=Principal(user_id=user.user_id, role=Role(user.role)),
            expires_at=expires_at,
        )

    def authenticate_request(self, authorization_header: str | None) -> Principal:
        if not authorization_header or not authorization_header.startswith(_BEARER):
            raise AuthenticationFailed("missing bearer token")
        token = authorization_header[len(_BEARER):]
        try:
            # Expiry is checked below against the injected clock, not the system clock.
            claims = jwt.decode(
                token, self.signing_key, algorithms=[_ALGORITHM], options={"verify_exp": False}
            )
        except jwt.PyJWTError:
            raise AuthenticationFailed("invalid token")
        exp = claims.get("exp")
        subject = claims.get("sub")
        if exp is None or subject is None:
            raise AuthenticationFailed("invalid token")
        if self.now() >= datetime.fromtimestamp(exp, tz=timezone.utc):
            raise AuthenticationFailed("token expired")
        try:
            user = self.store.get_user(subject)
        except UserNotFound:
            raise AuthenticationFailed("token subject no longer exists")
        return Principal(user_id=user.user_id, role=Role(user.role))

    def authorize(self, principal: Principal, allowed_roles: frozenset[Role]) -> Principal:
        if principal.role not in allowed_roles:
            raise AuthorizationDenied(f"role {principal.role.value} may not perform this action")
        return principal

    def assign_role(self, actor: Principal, user_id: str, role: Role) -> UserRecord:
        self.authorize(actor, frozenset({Role.ADMINISTRATOR}))
        return self.store.set_user_role(user_id, role.value)