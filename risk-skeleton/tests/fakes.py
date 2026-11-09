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
