"""Dashboard API: the HTTP surface for FR-001 to FR-012.

Architecture: serves dashboard, alert and audit views, accepts trade uploads,
alert actions and plan updates, and streams alerts over server-sent events.
Each request is checked by Access Control first.

Every route calls one public method on DashboardApi. Every method raises
NotImplementedError, which the app returns as HTTP 501.

Run: uvicorn app.dashboard_api:app --reload
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, Protocol

from fastapi import Body, Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.access_control import AccessControl, Principal, Role, Session
from app.alert_digest import AlertDigest, DigestRun
from app.alert_service import Alert, AlertService, AlertState
from app.archiver import ArchiveRun, Archiver
from app.audit_log import AuditLog, AuditRecord
from app.health_monitor import HealthMonitor, LivenessResult, PipelineStatus, ReadinessResult
from app.limit_monitor import LimitMonitor
from app.market_data_ingestion import IngestionResult, MarketDataIngestion
from app.mitigation_tracker import MitigationPlan, MitigationTracker, PlanStatus
from app.position_trade_store import Position, PositionTradeStore, Trade, UploadResult, UserRecord
from app.pre_trade_check import PreTradeCheck, PreTradeResult
from app.risk_engine import RiskEngine, RiskMetrics, TradeRiskMetrics


# ---- Response types -------------------------------------------------------

@dataclass(frozen=True)
class DashboardView:
    portfolio_id: str
    portfolio_value: Decimal
    risk_exposure: Decimal
    within_limits: bool
    concentration_by_sector: Mapping[str, Decimal]
    generated_at: datetime


@dataclass(frozen=True)
class AlertDetails:
    alert: Alert
    metrics: RiskMetrics


class DashboardLayoutRepository(Protocol):
    def get(self, user_id: str) -> Optional[dict[str, Any]]: ...
    def save(self, user_id: str, layout: dict[str, Any]) -> None: ...


# ---- Request bodies -------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class RoleAssignment(BaseModel):
    role: Role


class AssessmentRequest(BaseModel):
    portfolio_id: str


class AcknowledgeRequest(BaseModel):
    expected_version: int


class ResolveRequest(BaseModel):
    expected_version: int
    plan_id: Optional[str] = None


class PlanCreateRequest(BaseModel):
    description: str
    owner_id: str


class PlanUpdateRequest(BaseModel):
    expected_version: int
    status: Optional[PlanStatus] = None
    owner_id: Optional[str] = None


class DigestRequest(BaseModel):
    period_end: Optional[datetime] = None


class ArchiveRequest(BaseModel):
    cutoff: Optional[datetime] = None


class PreTradeRequest(BaseModel):
    order_id: str
    portfolio_id: str
    asset_id: str
    quantity: Decimal
    price: Decimal


# ---- The public surface: one method per route ----------------------------

@dataclass
class DashboardApi:
    access_control: AccessControl
    ingestion: MarketDataIngestion
    store: PositionTradeStore
    risk_engine: RiskEngine
    limit_monitor: LimitMonitor
    alert_service: AlertService
    mitigation: MitigationTracker
    digest: AlertDigest
    pre_trade: PreTradeCheck
    audit_log: AuditLog
    archiver: Archiver
    health: HealthMonitor
    layouts: Optional[DashboardLayoutRepository]

    # Access control (FR-006)
    def login(self, body: LoginRequest) -> Session:
        raise NotImplementedError("DashboardApi.login is not implemented")

    def authenticate_request(self, authorization_header: Optional[str]) -> Principal:
        raise NotImplementedError("DashboardApi.authenticate_request is not implemented")

    def assign_role(self, principal: Principal, user_id: str, role: Role) -> UserRecord:
        raise NotImplementedError("DashboardApi.assign_role is not implemented")

    # Health (FR-008, NFR-006)
    def get_liveness(self) -> LivenessResult:
        raise NotImplementedError("DashboardApi.get_liveness is not implemented")

    def get_readiness(self) -> ReadinessResult:
        raise NotImplementedError("DashboardApi.get_readiness is not implemented")

    def get_pipeline_status(self, principal: Principal) -> PipelineStatus:
        raise NotImplementedError("DashboardApi.get_pipeline_status is not implemented")

    # Market data and trades (FR-001, FR-007)
    def ingest_market_data(
        self, principal: Principal, batch: list[dict[str, Any]]
    ) -> IngestionResult:
        raise NotImplementedError("DashboardApi.ingest_market_data is not implemented")

    def list_rejected_market_data(
        self, principal: Principal, limit: int, after: Optional[datetime]
    ) -> list[AuditRecord]:
        raise NotImplementedError("DashboardApi.list_rejected_market_data is not implemented")

    def upload_trades(self, principal: Principal, content: bytes, source: str) -> UploadResult:
        raise NotImplementedError("DashboardApi.upload_trades is not implemented")

    # Risk calculation (FR-002)
    def run_risk_assessment(self, principal: Principal, portfolio_id: str) -> list[Alert]:
        raise NotImplementedError("DashboardApi.run_risk_assessment is not implemented")

    def get_portfolio_metrics(self, principal: Principal, portfolio_id: str) -> RiskMetrics:
        raise NotImplementedError("DashboardApi.get_portfolio_metrics is not implemented")

    # Dashboard (FR-003)
    def get_dashboard(self, principal: Principal, portfolio_id: str) -> DashboardView:
        raise NotImplementedError("DashboardApi.get_dashboard is not implemented")

    def get_dashboard_layout(self, principal: Principal) -> dict[str, Any]:
        raise NotImplementedError("DashboardApi.get_dashboard_layout is not implemented")

    def save_dashboard_layout(self, principal: Principal, layout: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("DashboardApi.save_dashboard_layout is not implemented")

    # Alerts (FR-004)
    def list_alerts(self, principal: Principal, state: Optional[AlertState]) -> list[Alert]:
        raise NotImplementedError("DashboardApi.list_alerts is not implemented")

    def get_alert(self, principal: Principal, alert_id: str) -> Alert:
        raise NotImplementedError("DashboardApi.get_alert is not implemented")

    def get_alert_positions(self, principal: Principal, alert_id: str) -> list[Position]:
        raise NotImplementedError("DashboardApi.get_alert_positions is not implemented")

    def get_alert_details(self, principal: Principal, alert_id: str) -> AlertDetails:
        raise NotImplementedError("DashboardApi.get_alert_details is not implemented")

    def acknowledge_alert(
        self, principal: Principal, alert_id: str, body: AcknowledgeRequest
    ) -> Alert:
        raise NotImplementedError("DashboardApi.acknowledge_alert is not implemented")

    def resolve_alert(self, principal: Principal, alert_id: str, body: ResolveRequest) -> Alert:
        raise NotImplementedError("DashboardApi.resolve_alert is not implemented")

    def open_alert_stream(self, principal: Principal) -> AsyncIterator[bytes]:
        raise NotImplementedError("DashboardApi.open_alert_stream is not implemented")

    # Audit trail (FR-005)
    def get_trade_security_info(self, principal: Principal, trade_id: str) -> Trade:
        raise NotImplementedError("DashboardApi.get_trade_security_info is not implemented")

    def get_trade_risk_metrics(self, principal: Principal, trade_id: str) -> TradeRiskMetrics:
        raise NotImplementedError("DashboardApi.get_trade_risk_metrics is not implemented")

    def get_trade_audit_trail(self, principal: Principal, trade_id: str) -> list[AuditRecord]:
        raise NotImplementedError("DashboardApi.get_trade_audit_trail is not implemented")

    # Pre-trade credit check (FR-010)
    def check_order(self, principal: Principal, body: PreTradeRequest) -> PreTradeResult:
        raise NotImplementedError("DashboardApi.check_order is not implemented")

    # Mitigation plans (FR-011)
    def create_mitigation_plan(
        self, principal: Principal, alert_id: str, body: PlanCreateRequest
    ) -> MitigationPlan:
        raise NotImplementedError("DashboardApi.create_mitigation_plan is not implemented")

    def list_mitigation_plans(self, principal: Principal, alert_id: str) -> list[MitigationPlan]:
        raise NotImplementedError("DashboardApi.list_mitigation_plans is not implemented")

    def update_mitigation_plan(
        self, principal: Principal, plan_id: str, body: PlanUpdateRequest
    ) -> MitigationPlan:
        raise NotImplementedError("DashboardApi.update_mitigation_plan is not implemented")

    def get_mitigation_plan_history(self, principal: Principal, plan_id: str) -> list[AuditRecord]:
        raise NotImplementedError("DashboardApi.get_mitigation_plan_history is not implemented")

    # Monthly digest (FR-012)
    def send_monthly_digest(self, principal: Principal, body: DigestRequest) -> DigestRun:
        raise NotImplementedError("DashboardApi.send_monthly_digest is not implemented")

    # Archiving (FR-009)
    def run_archive(self, principal: Principal, body: ArchiveRequest) -> ArchiveRun:
        raise NotImplementedError("DashboardApi.run_archive is not implemented")


# ---- Composition root and HTTP routes -------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/risk")
JWT_SIGNING_KEY = os.environ.get("JWT_SIGNING_KEY", "dev-only-change-me")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_api() -> DashboardApi:
    """Wire the modules together. Constructors only store their arguments.

    Dependencies marked None are not yet assigned in architecture.md.
    See contracts.md, open questions.
    """
    now = _utc_now
    store = PositionTradeStore(database_url=DATABASE_URL)
    audit = AuditLog(store=store, now=now)
    health = HealthMonitor(probes={}, now=now)
    access = AccessControl(store=store, signing_key=JWT_SIGNING_KEY, now=now)
    ingestion = MarketDataIngestion(store=store, audit_log=audit, health=health, now=now)
    risk = RiskEngine(store=store, now=now)
    alerts = AlertService(alerts=None, audit_log=audit, routing={}, now=now)
    limits = LimitMonitor(risk_engine=risk, alert_service=alerts, policy_source=_unassigned_policy)
    mitigation = MitigationTracker(plans=None, alert_service=alerts, audit_log=audit, now=now)
    digest = AlertDigest(
        alert_service=alerts, audit_log=audit, delivery=None, recipients_for=None, now=now
    )
    pre_trade = PreTradeCheck(
        risk_engine=risk,
        alert_service=alerts,
        audit_log=audit,
        credit_threshold_for=lambda trader_id: None,
    )
    archiver = Archiver(audit_log=audit, blob=None, now=now)
    return DashboardApi(
        access_control=access,
        ingestion=ingestion,
        store=store,
        risk_engine=risk,
        limit_monitor=limits,
        alert_service=alerts,
        mitigation=mitigation,
        digest=digest,
        pre_trade=pre_trade,
        audit_log=audit,
        archiver=archiver,
        health=health,
        layouts=None,
    )


def _unassigned_policy():
    raise NotImplementedError(
        "Risk policy storage is not assigned in architecture.md (see contracts.md)"
    )


def create_app(api: DashboardApi) -> FastAPI:
    app = FastAPI(title="Market Data and Risk Assessment API (skeleton)")

    @app.exception_handler(NotImplementedError)
    async def not_implemented(_: Request, exc: NotImplementedError) -> JSONResponse:
        return JSONResponse(
            status_code=501,
            content={"error": "not_implemented", "message": str(exc)},
        )

    def require_principal(authorization: Optional[str] = Header(default=None)) -> Principal:
        return api.authenticate_request(authorization)

    Auth = Depends(require_principal)

    # Health (no authentication: these are not system data)
    @app.get("/health/live")
    def health_live() -> Any:
        return api.get_liveness()

    @app.get("/health/ready")
    def health_ready() -> Any:
        return api.get_readiness()

    @app.get("/pipeline/status")
    def pipeline_status(principal: Principal = Auth) -> Any:
        return api.get_pipeline_status(principal)

    # Access control (FR-006)
    @app.post("/auth/login")
    def login(body: LoginRequest) -> Any:
        return api.login(body)

    @app.put("/users/{user_id}/role")
    def put_user_role(user_id: str, body: RoleAssignment, principal: Principal = Auth) -> Any:
        return api.assign_role(principal, user_id, body.role)

    # Market data and trades (FR-001, FR-007)
    @app.post("/market-data/batches", status_code=202)
    def post_market_data(batch: list[dict[str, Any]] = Body(...), principal: Principal = Auth) -> Any:
        return api.ingest_market_data(principal, batch)

    @app.get("/market-data/rejections")
    def get_rejections(
        limit: int = 100, after: Optional[datetime] = None, principal: Principal = Auth
    ) -> Any:
        return api.list_rejected_market_data(principal, limit, after)

    @app.post("/trades/uploads", status_code=202)
    async def post_trade_upload(
        request: Request, source: str = "manual", principal: Principal = Auth
    ) -> Any:
        content = await request.body()
        return api.upload_trades(principal, content, source)

    # Risk calculation (FR-002)
    @app.post("/risk-assessments", status_code=201)
    def post_risk_assessment(body: AssessmentRequest, principal: Principal = Auth) -> Any:
        return api.run_risk_assessment(principal, body.portfolio_id)

    @app.get("/portfolios/{portfolio_id}/metrics")
    def get_metrics(portfolio_id: str, principal: Principal = Auth) -> Any:
        return api.get_portfolio_metrics(principal, portfolio_id)

    # Dashboard (FR-003)
    @app.get("/dashboard")
    def get_dashboard(portfolio_id: str, principal: Principal = Auth) -> Any:
        return api.get_dashboard(principal, portfolio_id)

    @app.get("/dashboard/layout")
    def get_layout(principal: Principal = Auth) -> Any:
        return api.get_dashboard_layout(principal)

    @app.put("/dashboard/layout")
    def put_layout(layout: dict[str, Any] = Body(...), principal: Principal = Auth) -> Any:
        return api.save_dashboard_layout(principal, layout)

    # Alerts (FR-004)
    @app.get("/alerts")
    def get_alerts(state: Optional[AlertState] = None, principal: Principal = Auth) -> Any:
        return api.list_alerts(principal, state)

    @app.get("/alerts/stream")
    def get_alert_stream(principal: Principal = Auth) -> Any:
        # open_alert_stream raises before the response starts, so a
        # not-implemented call returns 501 rather than an empty 200 stream.
        events = api.open_alert_stream(principal)
        return StreamingResponse(events, media_type="text/event-stream")

    @app.get("/alerts/{alert_id}")
    def get_alert(alert_id: str, principal: Principal = Auth) -> Any:
        return api.get_alert(principal, alert_id)

    @app.get("/alerts/{alert_id}/positions")
    def get_alert_positions(alert_id: str, principal: Principal = Auth) -> Any:
        return api.get_alert_positions(principal, alert_id)

    @app.get("/alerts/{alert_id}/details")
    def get_alert_details(alert_id: str, principal: Principal = Auth) -> Any:
        return api.get_alert_details(principal, alert_id)

    @app.post("/alerts/{alert_id}/acknowledge")
    def post_acknowledge(
        alert_id: str, body: AcknowledgeRequest, principal: Principal = Auth
    ) -> Any:
        return api.acknowledge_alert(principal, alert_id, body)

    @app.post("/alerts/{alert_id}/resolve")
    def post_resolve(alert_id: str, body: ResolveRequest, principal: Principal = Auth) -> Any:
        return api.resolve_alert(principal, alert_id, body)

    # Audit trail (FR-005)
    @app.get("/trades/{trade_id}")
    def get_trade(trade_id: str, principal: Principal = Auth) -> Any:
        return api.get_trade_security_info(principal, trade_id)

    @app.get("/trades/{trade_id}/risk-metrics")
    def get_trade_metrics(trade_id: str, principal: Principal = Auth) -> Any:
        return api.get_trade_risk_metrics(principal, trade_id)

    @app.get("/trades/{trade_id}/audit-trail")
    def get_trade_trail(trade_id: str, principal: Principal = Auth) -> Any:
        return api.get_trade_audit_trail(principal, trade_id)

    # Pre-trade credit check (FR-010)
    @app.post("/pre-trade-checks")
    def post_pre_trade(body: PreTradeRequest, principal: Principal = Auth) -> Any:
        return api.check_order(principal, body)

    # Mitigation plans (FR-011)
    @app.post("/alerts/{alert_id}/mitigation-plans", status_code=201)
    def post_plan(alert_id: str, body: PlanCreateRequest, principal: Principal = Auth) -> Any:
        return api.create_mitigation_plan(principal, alert_id, body)

    @app.get("/alerts/{alert_id}/mitigation-plans")
    def get_plans(alert_id: str, principal: Principal = Auth) -> Any:
        return api.list_mitigation_plans(principal, alert_id)

    @app.patch("/mitigation-plans/{plan_id}")
    def patch_plan(plan_id: str, body: PlanUpdateRequest, principal: Principal = Auth) -> Any:
        return api.update_mitigation_plan(principal, plan_id, body)

    @app.get("/mitigation-plans/{plan_id}/history")
    def get_plan_history(plan_id: str, principal: Principal = Auth) -> Any:
        return api.get_mitigation_plan_history(principal, plan_id)

    # Monthly digest (FR-012)
    @app.post("/alert-digests")
    def post_digest(body: DigestRequest, principal: Principal = Auth) -> Any:
        return api.send_monthly_digest(principal, body)

    # Archiving (FR-009)
    @app.post("/archive-runs")
    def post_archive(body: ArchiveRequest, principal: Principal = Auth) -> Any:
        return api.run_archive(principal, body)

    return app


app = create_app(build_api())
