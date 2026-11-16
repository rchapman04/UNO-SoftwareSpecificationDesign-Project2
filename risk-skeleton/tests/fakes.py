"""Fake collaborators for the acceptance tests.

These are test doubles only. They hold data in memory and record calls.
They do not implement the behaviour under test. Each module under test is
the real skeleton module, which currently raises NotImplementedError.
"""

import threading
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from app.alert_service import AlertNotFound, AlertVersionConflict
from app.audit_log import EventType
from app.risk_engine import RiskEngineUnavailable

UTC = timezone.utc
T0 = datetime(2026, 11, 9, 14, 0, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


class FakeAuditLog:
    """Stands in for AuditLog. Stores entries as dicts."""

    def __init__(self):
        self.entries = []

    def append(self, event_type, subject_id, actor_id, payload):
        entry = {
            "event_type": event_type,
            "subject_id": subject_id,
            "actor_id": actor_id,
            "payload": dict(payload),
        }
        self.entries.append(entry)
        return entry

    def get_trail(self, subject_id):
        return [e for e in self.entries if e["subject_id"] == subject_id]

    def list_rejected_market_data(self, limit, after):
        rows = [e for e in self.entries if e["event_type"] == EventType.MARKET_DATA_REJECTED]
        return rows[:limit]

    def of_type(self, event_type):
        return [e for e in self.entries if e["event_type"] == event_type]


class FakeStore:
    """Stands in for PositionTradeStore for the ingestion tests."""

    def __init__(self):
        self.market_data = []
        self.trades = {}
        self.positions = []
        self.latest = {}

    def list_positions(self, portfolio_id):
        return [p for p in self.positions if p.portfolio_id == portfolio_id]

    def get_latest_market_data(self, asset_ids):
        return {a: self.latest[a] for a in asset_ids if a in self.latest}

    def save_market_data(self, records):
        self.market_data.extend(records)
        return len(records)

    def list_trades(self, portfolio_id):
        return [t for t in self.trades.values() if t.portfolio_id == portfolio_id]


class FakeHealth:
    def __init__(self):
        self.activity = []

    def record_activity(self, component, count):
        self.activity.append((component, count))


class FakeRiskEngine:
    """Stands in for RiskEngine. Returns configured values, or raises when down."""

    def __init__(self, exposure=Decimal("950000"), unavailable=False):
        self.exposure = exposure
        self.unavailable = unavailable

    def get_trader_exposure(self, trader_id):
        if self.unavailable:
            raise RiskEngineUnavailable("risk engine down (fake)")
        return self.exposure


class FakeAlertService:
    """Stands in for AlertService for LimitMonitor and PreTradeCheck tests."""

    def __init__(self):
        self.breaches = []
        self.notifications = []

    def create_alert(self, breach):
        self.breaches.append(breach)
        return breach

    def send_notification(self, recipient_id, message):
        self.notifications.append((recipient_id, message))


class FakeAlertRepository:
    """In-memory alert storage with optimistic version checking on save.

    The version check stands in for the repository's responsibility under
    FR-004 (second concurrent action is rejected). The fake increments the
    version on each successful save.
    """

    def __init__(self, alerts=()):
        self._alerts = {a.alert_id: a for a in alerts}
        self._lock = threading.Lock()

    def get(self, alert_id):
        try:
            return self._alerts[alert_id]
        except KeyError:
            raise AlertNotFound(alert_id)

    def find_by_state(self, state):
        return [a for a in self._alerts.values() if state is None or a.state == state]

    def find_created_between(self, start, end):
        return [a for a in self._alerts.values() if start <= a.created_at <= end]

    def save(self, alert, expected_version):
        with self._lock:
            current = self._alerts[alert.alert_id]
            if expected_version is not None and current.version != expected_version:
                raise AlertVersionConflict(alert.alert_id)
            stored = replace(alert, version=current.version + 1)
            self._alerts[alert.alert_id] = stored
            return stored

    def current(self, alert_id):
        return self._alerts[alert_id]


# ---- Fakes for DashboardApi collaborators --------------------------------
#
# DashboardApi is the module under test in the route tests. Its collaborators
# are fakes, so no collaborator is None. The fakes hold the fixture data for
# portfolio P1 (test_plan.md F1) and record calls. They do not implement
# behaviour, so the DashboardApi stubs still raise NotImplementedError.

from app.access_control import AuthenticationFailed, AuthorizationDenied, Principal, Role  # noqa: E402
from app.position_trade_store import MarketDataRecord, Position  # noqa: E402

FAKE_TOKENS = {"Bearer fake-token-T1": Principal(user_id="T1", role=Role.TRADER)}


class FakeAccessControl:
    """Knows one test token (T1, Trader). Does not enforce roles on its own."""

    def authenticate_request(self, authorization_header):
        try:
            return FAKE_TOKENS[authorization_header]
        except (KeyError, TypeError):
            raise AuthenticationFailed("missing or unknown token (fake)")

    def authorize(self, principal, allowed_roles):
        if principal.role not in allowed_roles:
            raise AuthorizationDenied(principal.role.value)
        return principal


class FakeIngestion:
    def ingest_batch(self, raw_records):
        raise NotImplementedError("FakeIngestion has no behaviour")


class FakeLimitMonitor:
    def limit_statuses(self, metrics, policy):
        raise NotImplementedError("FakeLimitMonitor has no behaviour")


class FakeMitigation:
    pass


class FakeDigest:
    pass


class FakePreTrade:
    pass


class FakeArchiver:
    pass


class FakeLayouts:
    """Dict-backed layout store, keyed by user ID."""

    def __init__(self):
        self.layouts = {}

    def get(self, user_id):
        return self.layouts.get(user_id)

    def save(self, user_id, layout):
        self.layouts[user_id] = dict(layout)


def seeded_store():
    """FakeStore with portfolio P1 (test_plan.md F1) and its market data."""
    store = FakeStore()
    store.positions = [
        Position(portfolio_id="P1", asset_id="A", sector="Technology", quantity=Decimal("6000")),
        Position(portfolio_id="P1", asset_id="B", sector="Energy", quantity=Decimal("4000")),
    ]
    store.latest = {
        asset: MarketDataRecord(
            asset_id=asset, price=Decimal("100"), currency="USD", sector=sector, region="US",
            data_type="price", observed_at=T0, received_at=T0,
        )
        for asset, sector in (("A", "Technology"), ("B", "Energy"))
    }
    return store


def fake_dashboard_api(alert_service=None):
    """A DashboardApi whose collaborators are all fakes (none is None)."""
    from app.dashboard_api import DashboardApi  # local import: avoids a load-order cycle
    return DashboardApi(
        access_control=FakeAccessControl(),
        ingestion=FakeIngestion(),
        store=seeded_store(),
        risk_engine=FakeRiskEngine(),
        limit_monitor=FakeLimitMonitor(),
        alert_service=alert_service or FakeAlertService(),
        mitigation=FakeMitigation(),
        digest=FakeDigest(),
        pre_trade=FakePreTrade(),
        audit_log=FakeAuditLog(),
        archiver=FakeArchiver(),
        health=FakeHealth(),
        layouts=FakeLayouts(),
    )