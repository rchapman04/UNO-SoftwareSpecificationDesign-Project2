"""Acceptance tests for AT-01 to AT-12 (AT-nn matches AC-nnn; AT-11 retired).

Expected values come from test_plan.md. HTTP status codes come from the
proposed error mapping in contracts.md section 3, because the spec defines
none (G-01). Fake collaborators live in tests/fakes.py.
"""

import asyncio
import threading
import time
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.access_control import AuthorizationDenied, Principal, Role
from app.alert_service import (
    Alert, AlertKind, AlertService, AlertState, AlertVersionConflict, Breach, Severity,
)
from app.audit_log import EventType
from app.dashboard_api import AcknowledgeRequest, DashboardApi, create_app
from app.limit_monitor import LimitMonitor, Metric, RiskLimit, RiskPolicy
from app.market_data_ingestion import MarketDataIngestion, ValidationFailed
from app.position_trade_store import PositionTradeStore
from app.pre_trade_check import Decision, OrderRequest, PreTradeCheck
from app.risk_engine import RiskMetrics
from tests.fakes import (
    T0, FakeAlertRepository, FakeAlertService, FakeAuditLog, FakeClock,
    FakeHealth, FakeRiskEngine, FakeStore,
)

T1_AUTH = {"Authorization": "Bearer fake-token-T1"}


# ---------- helpers -------------------------------------------------------

def make_breach(severity=Severity.CRITICAL, kind=AlertKind.POLICY_DESIGN, excess=Decimal("25000")):
    return Breach(
        limit_id="VAR-1", metric="var", scope_id="P1", asset_ids=("A", "B"),
        measured_value=Decimal("525000"), threshold=Decimal("500000"), excess=excess,
        severity=severity, kind=kind, description="Portfolio VaR above limit",
        responsible_user_ids=("T1",),
    )


def make_alert(alert_id="AL-1", state=AlertState.CREATED, version=1,
               kind=AlertKind.POLICY_DESIGN, routed_to=frozenset({Role.RISK_MANAGER, Role.RISK_ANALYST})):
    return Alert(
        alert_id=alert_id, state=state, breach=make_breach(kind=kind), routed_to=routed_to,
        created_at=T0, version=version, acknowledged_by=None, acknowledged_at=None,
        resolved_by=None, resolved_at=None, plan_id=None,
    )


def var_policy():
    limit = RiskLimit(
        limit_id="VAR-1", metric=Metric.VAR, scope_id="P1", threshold=Decimal("500000"),
        severity=Severity.CRITICAL, alert_kind=AlertKind.POLICY_DESIGN,
    )
    return RiskPolicy(
        policy_id="POL-1", version=1, limits=(limit,), var_confidence=0.95,
        var_horizon_days_by_instrument_type={}, credit_thresholds_by_trader={"T1": Decimal("1000000")},
    )


def var_metrics(var_value):
    return RiskMetrics(
        portfolio_id="P1", computed_at=T0, portfolio_value=Decimal("1000000"),
        total_exposure=Decimal("1000000"), var_value=Decimal(var_value), var_confidence=0.95,
        var_horizon_days_by_instrument_type={}, concentration_by_sector={},
    )


def order(quantity, price="100", order_id="O-1"):
    return OrderRequest(
        order_id=order_id, trader_id="T1", portfolio_id="P1", asset_id="A",
        quantity=Decimal(quantity), price=Decimal(price),
    )


def assert_rejected(call):
    """Run call() and return the exception it raised.

    NotImplementedError is re-raised, so an unimplemented module cannot pass
    as a rejection.
    """
    try:
        call()
    except NotImplementedError:
        raise
    except Exception as exc:  # any other exception is a rejection
        return exc
    pytest.fail("expected a rejection, but the call succeeded")


def route_client():
    """App with a DashboardApi whose methods are the unimplemented skeleton."""
    fields = {f: None for f in DashboardApi.__dataclass_fields__}
    return TestClient(create_app(DashboardApi(**fields)), raise_server_exceptions=False)


# ---------- AT-01 (AC-001): dashboard -----------------------------------

def test_AT01_dashboard_returns_value_limit_status_and_concentration():
    client = route_client()
    r = client.get("/dashboard", params={"portfolio_id": "P1"}, headers=T1_AUTH)
    assert r.status_code == 200
    body = r.json()
    assert Decimal(str(body["portfolio_value"])) == Decimal("1000000.00")
    assert body["within_limits"] is True
    conc = body["concentration_by_sector"]
    assert Decimal(str(conc["Technology"])) == Decimal("60.0")
    assert Decimal(str(conc["Energy"])) == Decimal("40.0")


def test_AT01_dashboard_loads_within_5_seconds():
    client = route_client()
    start = time.monotonic()
    r = client.get("/dashboard", params={"portfolio_id": "P1"}, headers=T1_AUTH)
    elapsed = time.monotonic() - start
    assert r.status_code == 200
    assert elapsed <= 5.0


@pytest.mark.skip(reason="AT-01 C3 is UI behaviour (refresh); REST-only scope per instruction 3")
def test_AT01_dashboard_refreshes_every_60_seconds():
    pass


def test_AT01_no_token_rejected_with_no_data_and_control_accepted():
    client = route_client()
    r = client.get("/dashboard", params={"portfolio_id": "P1"})
    assert r.status_code == 401
    assert "portfolio_value" not in r.json()
    # Control: same request with a valid token is accepted.
    ok = client.get("/dashboard", params={"portfolio_id": "P1"}, headers=T1_AUTH)
    assert ok.status_code == 200


# ---------- AT-02 (AC-002): alert on VaR breach -------------------------

def test_AT02_breach_creates_alert_with_policy_severity_and_excess():
    alerts = FakeAlertService()
    monitor = LimitMonitor(risk_engine=FakeRiskEngine(), alert_service=alerts, policy_source=var_policy)
    raised = monitor.evaluate_and_alert(var_metrics("525000"), var_policy())
    assert len(raised) == 1
    breach = alerts.breaches[0]
    assert breach.severity == Severity.CRITICAL          # set by RiskPolicy
    assert breach.excess == Decimal("25000")             # 525,000 - 500,000
    assert breach.excess / breach.threshold * 100 == Decimal("5")  # 5.0% of limit


@pytest.mark.parametrize("var_value, expect_alert, excess", [
    ("499999.99", False, None),   # inside: no alert
    ("500000.01", True, Decimal("0.01")),  # outside: alert with $0.01 excess
])
def test_AT02_inside_and_outside_var_boundary(var_value, expect_alert, excess):
    alerts = FakeAlertService()
    monitor = LimitMonitor(risk_engine=FakeRiskEngine(), alert_service=alerts, policy_source=var_policy)
    monitor.evaluate_and_alert(var_metrics(var_value), var_policy())
    if expect_alert:
        assert len(alerts.breaches) == 1
        assert alerts.breaches[0].excess == excess
    else:
        assert alerts.breaches == []


def test_AT02_banner_frame_is_emitted_for_the_alert():
    alert = make_alert(routed_to=frozenset({Role.RISK_MANAGER}))
    service = AlertService(
        alerts=FakeAlertRepository([alert]), audit_log=FakeAuditLog(),
        routing={AlertKind.POLICY_DESIGN: frozenset({Role.RISK_MANAGER})}, now=FakeClock(),
    )
    stream = service.open_alert_stream("RM1", Role.RISK_MANAGER)
    frame = asyncio.run(stream.__anext__())
    assert isinstance(frame, bytes)
    assert b"AL-1" in frame


@pytest.mark.parametrize("seconds, within", [(59, True), (61, False)])
def test_AT02_alert_created_within_60_seconds(seconds, within):
    clock = FakeClock(now=T0 + timedelta(seconds=seconds))
    service = AlertService(
        alerts=FakeAlertRepository(), audit_log=FakeAuditLog(), routing={}, now=clock,
    )
    alert = service.create_alert(make_breach())
    latency = (alert.created_at - T0).total_seconds()
    assert (latency <= 60) is within


# ---------- AT-03 (AC-003): market data validation ----------------------

BAD_RECORD = {"asset_id": "A", "price": "abc", "currency": "USD", "sector": "Technology",
              "region": "US", "data_type": "price", "observed_at": "2026-11-09T14:00:00+00:00"}
GOOD_RECORD = dict(BAD_RECORD, price="101.25")


def ingestion(store, audit):
    return MarketDataIngestion(store=store, audit_log=audit, health=FakeHealth(), now=FakeClock())


def test_AT03_invalid_record_discarded_logged_and_control_stored():
    store, audit = FakeStore(), FakeAuditLog()
    result = ingestion(store, audit).ingest_batch([BAD_RECORD])
    assert result.accepted == 0 and result.rejected == 1
    assert store.market_data == []                                   # nothing stored
    rejected = audit.of_type(EventType.MARKET_DATA_REJECTED)
    assert len(rejected) == 1 and rejected[0]["payload"]             # reason recorded
    # Control: the same record with a numeric price is accepted.
    store2, audit2 = FakeStore(), FakeAuditLog()
    ok = ingestion(store2, audit2).ingest_batch([GOOD_RECORD])
    assert ok.accepted == 1 and ok.rejected == 0
    assert len(store2.market_data) == 1
    assert audit2.of_type(EventType.MARKET_DATA_REJECTED) == []


def test_AT03_validate_record_rejects_bad_price_and_accepts_control():
    ing = ingestion(FakeStore(), FakeAuditLog())
    with pytest.raises(ValidationFailed):
        ing.validate_record(BAD_RECORD)
    assert ing.validate_record(GOOD_RECORD).price == Decimal("101.25")


def test_AT03_mixed_batch_stores_only_the_valid_record():
    store, audit = FakeStore(), FakeAuditLog()
    result = ingestion(store, audit).ingest_batch([GOOD_RECORD, BAD_RECORD])
    assert result.accepted == 1 and result.rejected == 1
    assert len(store.market_data) == 1
    assert store.market_data[0].price == Decimal("101.25")


# ---------- AT-04 (AC-004): pre-trade credit check ----------------------

def test_AT04_order_over_threshold_is_blocked_with_no_side_effects_and_control_allowed():
    alerts, audit = FakeAlertService(), FakeAuditLog()
    check = PreTradeCheck(risk_engine=FakeRiskEngine(exposure=Decimal("950000")),
                          alert_service=alerts, audit_log=audit,
                          credit_threshold_for=lambda t: Decimal("1000000"))
    result = check.check_order(order("1000"))                     # adds $100,000
    assert result.decision == Decision.BLOCK
    assert result.exposure_before == Decimal("950000")
    assert result.exposure_after == Decimal("1050000")
    assert result.credit_threshold == Decimal("1000000")
    assert result.fail_open is False
    assert any(rid == "T1" for rid, _ in alerts.notifications)    # Trader notified
    blocked = audit.of_type(EventType.ORDER_BLOCKED)
    assert len(blocked) == 1 and blocked[0]["subject_id"] == "O-1"
    assert alerts.breaches == []                                  # no alert created

    # Control: an order adding $40,000 is allowed, with no block record or notice.
    alerts2, audit2 = FakeAlertService(), FakeAuditLog()
    check2 = PreTradeCheck(risk_engine=FakeRiskEngine(exposure=Decimal("950000")),
                           alert_service=alerts2, audit_log=audit2,
                           credit_threshold_for=lambda t: Decimal("1000000"))
    ok = check2.check_order(order("400"))
    assert ok.decision == Decision.ALLOW
    assert ok.exposure_after == Decimal("990000")
    assert audit2.of_type(EventType.ORDER_BLOCKED) == []
    assert alerts2.notifications == []


@pytest.mark.parametrize("quantity, decision", [
    ("499.9999", Decision.ALLOW),    # adds $49,999.99 -> $999,999.99: inside
    ("500.0001", Decision.BLOCK),    # adds $50,000.01 -> $1,000,000.01: outside
])
def test_AT04_inside_and_outside_credit_boundary(quantity, decision):
    check = PreTradeCheck(risk_engine=FakeRiskEngine(exposure=Decimal("950000")),
                          alert_service=FakeAlertService(), audit_log=FakeAuditLog(),
                          credit_threshold_for=lambda t: Decimal("1000000"))
    assert check.check_order(order(quantity)).decision == decision


def test_AT10_fail_open_when_risk_engine_down_and_control_blocked():
    alerts, audit = FakeAlertService(), FakeAuditLog()
    check = PreTradeCheck(risk_engine=FakeRiskEngine(unavailable=True),
                          alert_service=alerts, audit_log=audit,
                          credit_threshold_for=lambda t: Decimal("1000000"))
    result = check.check_order(order("1000"))                     # adds $100,000
    assert result.decision == Decision.ALLOW
    assert result.fail_open is True
    assert len(alerts.notifications) >= 1                         # management alerted
    assert len(audit.of_type(EventType.ORDER_FAILED_OPEN)) == 1
    assert audit.of_type(EventType.ORDER_BLOCKED) == []
    # Control: the same order with the Risk Engine available is blocked.
    up = PreTradeCheck(risk_engine=FakeRiskEngine(exposure=Decimal("950000")),
                       alert_service=FakeAlertService(), audit_log=FakeAuditLog(),
                       credit_threshold_for=lambda t: Decimal("1000000"))
    assert up.check_order(order("1000")).decision == Decision.BLOCK


# ---------- AT-05 (AC-005): trade upload is repeatable ------------------

TRADE_CSV_HEADER = b"trade_id,portfolio_id,trader_id,asset_id,quantity,price,traded_at\n"


def test_AT05_reupload_updates_the_trade_and_does_not_duplicate_it():
    # Module under test is the real store. database_url is a test setting;
    # the store is not implemented, so this test fails with NotImplementedError.
    store = PositionTradeStore(database_url="sqlite:///:memory:")
    first = TRADE_CSV_HEADER + b"T-100,P1,T1,A,10,100,2026-11-09T14:00:00+00:00\n"
    second = TRADE_CSV_HEADER + b"T-100,P1,T1,A,12,100,2026-11-09T14:00:00+00:00\n"
    r1 = store.upload_trade_csv(first, source="manual")
    r2 = store.upload_trade_csv(second, source="manual")
    assert r1.inserted == 1
    assert r2.updated == 1 and r2.inserted == 0
    trades = [t for t in store.list_trades("P1") if t.trade_id == "T-100"]
    assert len(trades) == 1
    assert trades[0].quantity == Decimal("12")


# ---------- AT-06 (AC-006): no token ------------------------------------
# Covered by AT-01 test_AT01_no_token_rejected_with_no_data_and_control_accepted
# (same request shape; see AT-01 section). Listed here for the row.


def test_AT06_request_without_token_is_rejected_with_no_data():
    client = route_client()
    r = client.get("/dashboard", params={"portfolio_id": "P1"})
    assert r.status_code == 401
    assert r.json().get("portfolio_value") is None
    ok = client.get("/dashboard", params={"portfolio_id": "P1"}, headers=T1_AUTH)
    assert ok.status_code == 200


# ---------- AT-07 (AC-007): auditor cannot acknowledge ------------------

def test_AT07_auditor_cannot_acknowledge_and_alert_stays_created():
    repo = FakeAlertRepository([make_alert(state=AlertState.CREATED, version=1)])
    service = AlertService(alerts=repo, audit_log=FakeAuditLog(), routing={}, now=FakeClock())
    api = DashboardApi(**{f: None for f in DashboardApi.__dataclass_fields__})
    api.alert_service = service
    auditor = Principal(user_id="AUD1", role=Role.AUDITOR)
    exc = assert_rejected(
        lambda: api.acknowledge_alert(auditor, "AL-1", AcknowledgeRequest(expected_version=1))
    )
    assert isinstance(exc, AuthorizationDenied)   # contracts.md 1.4
    assert repo.current("AL-1").state == AlertState.CREATED
    # Control: the Trader can acknowledge the same alert.
    trader = Principal(user_id="T1", role=Role.TRADER)
    done = api.acknowledge_alert(trader, "AL-1", AcknowledgeRequest(expected_version=1))
    assert done.state == AlertState.ACKNOWLEDGED


# ---------- AT-08 (AC-008): acknowledge a resolved alert ----------------

def test_AT08_acknowledge_resolved_alert_rejected_and_control_created_accepted():
    resolved = make_alert(state=AlertState.RESOLVED, version=2)
    repo = FakeAlertRepository([resolved])
    audit = FakeAuditLog()
    service = AlertService(alerts=repo, audit_log=audit, routing={}, now=FakeClock())
    # The contract does not name an error for an invalid lifecycle step.
    # The test only requires that the call is rejected. See report.
    assert_rejected(lambda: service.acknowledge_alert("AL-1", "T1", expected_version=2))
    assert repo.current("AL-1").state == AlertState.RESOLVED
    assert audit.of_type(EventType.ALERT_ACKNOWLEDGED) == []
    # Control: an alert in Created is acknowledged.
    repo2 = FakeAlertRepository([make_alert(state=AlertState.CREATED, version=1)])
    ok = AlertService(alerts=repo2, audit_log=FakeAuditLog(), routing={}, now=FakeClock())
    done = ok.acknowledge_alert("AL-1", "T1", expected_version=1)
    assert done.state == AlertState.ACKNOWLEDGED


# ---------- AT-09 (AC-009): concurrent acknowledgment -------------------

def test_AT09_concurrent_acknowledgment_first_applied_second_rejected():
    repo = FakeAlertRepository([make_alert(state=AlertState.CREATED, version=1)])
    audit = FakeAuditLog()
    service = AlertService(alerts=repo, audit_log=audit, routing={}, now=FakeClock())
    barrier = threading.Barrier(2)
    outcomes = []

    errors = []

    def act(actor):
        barrier.wait()
        try:
            service.acknowledge_alert("AL-1", actor, expected_version=1)
            outcomes.append(("ok", actor))
        except AlertVersionConflict:
            outcomes.append(("conflict", actor))
        except Exception as exc:          # not expected: surface it in the test
            errors.append(exc)

    threads = [threading.Thread(target=act, args=(a,)) for a in ("T1", "RA1")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise errors[0]
    assert sorted(kind for kind, _ in outcomes) == ["conflict", "ok"]
    winner = next(actor for kind, actor in outcomes if kind == "ok")
    stored = repo.current("AL-1")
    assert stored.acknowledged_by == winner
    assert len(audit.of_type(EventType.ALERT_ACKNOWLEDGED)) == 1
    # Control: a single acknowledgment on a fresh alert is accepted.
    solo_repo = FakeAlertRepository([make_alert(state=AlertState.CREATED, version=1)])
    solo = AlertService(alerts=solo_repo, audit_log=FakeAuditLog(), routing={}, now=FakeClock())
    assert solo.acknowledge_alert("AL-1", "T1", expected_version=1).state == AlertState.ACKNOWLEDGED


# ---------- AT-12 (AC-012): listing visibility --------------------------

def test_AT12_trader_list_excludes_policy_alert_and_risk_manager_sees_it():
    policy_alert = make_alert(alert_id="AL-POL", kind=AlertKind.POLICY_DESIGN,
                              routed_to=frozenset({Role.RISK_MANAGER, Role.RISK_ANALYST}))
    trade_alert = make_alert(alert_id="AL-TRD", kind=AlertKind.TRADE_LEVEL,
                             routed_to=frozenset({Role.TRADER, Role.RISK_ANALYST}))
    service = AlertService(
        alerts=FakeAlertRepository([policy_alert, trade_alert]), audit_log=FakeAuditLog(),
        routing={}, now=FakeClock(),
    )
    trader_ids = {a.alert_id for a in service.list_alerts("T1", Role.TRADER, None)}
    assert "AL-POL" not in trader_ids
    assert "AL-TRD" in trader_ids
    # Control: the Risk Manager sees the policy alert.
    rm_ids = {a.alert_id for a in service.list_alerts("RM1", Role.RISK_MANAGER, None)}
    assert "AL-POL" in rm_ids
