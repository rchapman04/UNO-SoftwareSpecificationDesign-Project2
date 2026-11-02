# Architecture: Market Data and Risk Assessment System

## 1. Overview

The system is one Python service with a TypeScript (React) front end, backed by PostgreSQL and deployed on Microsoft Azure. It takes market data from a vendor API and trades from CSV uploads, stores them, calculates exposure and VaR, compares results to risk limits, and raises alerts. Users see results on a dashboard, an alert view, and an audit trail view. A pre-trade check gates new orders. Audit records are archived to immutable Azure Blob Storage.

## 2. Modules

| Module | Responsibility | May depend on |
|---|---|---|
| Market Data Ingestion | Receive market data from the vendor API, validate each record, store accepted records, and record rejected records in the Audit Log (FR-001, FR-007). | Position & Trade Store, Audit Log, Health Monitor |
| Position & Trade Store | Persist accepted market data, trades (upserted by trade ID, so repeated uploads do not duplicate trades), and asset positions (FR-001, FR-002, FR-005). | None (database only) |
| Risk Engine | Compute exposure, concentration, and VaR using historical simulation (FR-002). | Position & Trade Store |
| Limit Monitor | Compare each metric with the RiskLimit values in the active RiskPolicy, and emit a breach with its severity (FR-004). | Risk Engine, Position & Trade Store, Alert Service |
| Alert Service | Create alerts, route them to roles (FR-004), manage the lifecycle (Created, Acknowledged, Resolved), record the user and time of each acknowledgment and resolution, and push alerts to the dashboard (FR-004, AC-002). | Audit Log, Access Control |
| Mitigation Tracker | Store mitigation plans linked to alerts, each with an owner, a status, and a change history (FR-011). | Alert Service, Audit Log |
| Alert Digest | Once a month, send a digest of alerts to stakeholders in the affected area (FR-012). Scheduled Python Azure Function. | Alert Service |
| Pre-Trade Check | Decide whether an order would exceed the Trader's credit threshold. If the Risk Engine is unavailable, allow the order and alert management (FR-010, AC-004). | Risk Engine, Alert Service, Audit Log |
| Audit Log | Write append-only, system-timestamped records of trades, assessments, alerts, acknowledgments, resolutions, plan changes, blocked and fail-open orders, rejected market data, and policy changes (FR-005, NFR-001). | Position & Trade Store |
| Archiver | Move audit records older than 1 year to immutable (WORM) Azure Blob Storage, and keep them for 7 years (FR-009, NFR-001). Scheduled Python Azure Function. | Audit Log |
| Access Control | Authenticate users and check each request against the user's role (FR-006, NFR-002). | Position & Trade Store (user and role tables) |
| Health Monitor | Report pipeline status, connectivity, activity, and readiness and health checks (FR-008, NFR-006). | None |
| Dashboard API | Serve dashboard, alert, and audit views, accept trade uploads, alert actions, and plan updates, and stream alerts to the UI using server-sent events. Each request is checked by Access Control first (FR-003, FR-004, FR-005, FR-011). | Access Control, Risk Engine, Alert Service, Mitigation Tracker, Audit Log, Position & Trade Store |
| Dashboard UI | Render the dashboard, alert banner, and audit trail, and send user actions to the Dashboard API (FR-003, AC-001, AC-002, NFR-007). | Dashboard API |

## 3. Request flow: limit breach to resolved alert

This flow follows AC-002. Numbers show the order of events.

1. The vendor API delivers a market data batch to Market Data Ingestion, or a user or scheduled job uploads a trade CSV through the Dashboard API (FR-001).
2. Ingestion validates each record. Failing records are discarded, and the rejected record is written to the Audit Log (FR-007, AC-003).
3. Risk Engine recalculates exposure and VaR for the affected assets and portfolios (FR-002).
4. Limit Monitor compares each result with the RiskLimit values in the active RiskPolicy.
5. On a breach, Limit Monitor sends the limit, asset, measured value, and severity from RiskPolicy to Alert Service (AC-002).
6. Alert Service creates the Alert in state Created, routes it by type (FR-004), and writes the event to the Audit Log in the same transaction (FR-005). Steps 1 to 6 must finish within 1 minute (AC-002, NFR-003).
7. Alert Service pushes the alert to connected dashboards over server-sent events. The banner appears immediately, even if details are still loading (AC-002, FR-004).
8. A user acknowledges the alert. Alert Service records the user and time, and the Audit Log entry is written in the same transaction (FR-004).
9. The user adds a mitigation plan through Mitigation Tracker (FR-011), and resolves the alert, which records the user and time. Resolution is the outcome the system works toward (FR-004, FR-011).
10. Each month, Alert Digest sends alert copies to stakeholders in the affected area (FR-012).

## 4. Design decisions

| Decision | Reason |
|---|---|
| Every data endpoint requires authentication, and the role is checked on each request. | FR-006, NFR-002 |
| Roles are Trader, Risk Analyst, Risk Manager, Auditor (read-only), and Administrator (assigns roles). | FR-006 |
| The pre-trade check runs before an order is entered and returns block or allow. | FR-010, AC-004 |
| If the Risk Engine is unavailable, the pre-trade check fails open: the order is allowed, and management is alerted. | FR-010 |
| Blocked orders and fail-open orders are written to the Audit Log. | FR-010, FR-005 |
| Alerts are routed by type: trade-level alerts go to the responsible Trader and Risk Analysts where relevant; policy and design alerts go to the Risk Manager and Risk Analysts. | FR-004 |
| The alert banner is pushed immediately using server-sent events, not polled. | AC-002, FR-004. Replaces the 60-second polling in earlier drafts. |
| Dashboard figures refresh every 60 seconds, and the dashboard loads within 5 seconds. | AC-001 |
| Alert severity comes from the RiskPolicy for the breached limit. | AC-002, Domain Model (RiskPolicy) |
| Server-side UTC timestamps are assigned at ingestion, and each audit record is written in the same transaction as the event it records. | FR-005, NFR-001. Preference: the spec does not name a time standard. |
| Rejected market data is kept in the Audit Log, not only in application logs. | FR-007, FR-005 |
| Acknowledgment and resolution record the user and time. | FR-004, NFR-001 |
| If two users act on the same alert at once, the first action is applied and the second is rejected. | FR-004 |
| Mitigation plans are stored separately from alerts. Resolution does not require a plan, but plans are tracked. | FR-011 |
| Risk metrics are recalculated on each accepted market data batch and each trade upload. | FR-002, AC-002. Preference: the spec does not set a recalculation schedule. |
| VaR uses historical simulation at 95% confidence (higher if feasible). The horizon is set per instrument type in RiskPolicy. | FR-002. Horizon values are preferences: 1 day for short-term options, 10 days for longer-term bonds. |
| Trade uploads are idempotent: each trade is keyed by trade ID. | FR-001 |
| Audit records are stored on Azure Blob Storage with immutable WORM retention. | FR-009, NFR-001. WORM is the longer-established of the two methods in SEC Rule 17a-4(f) |
| The monthly alert digest is a scheduled job. | FR-012 |
| Each user's dashboard layout is saved to their account. | FR-003 |
| The market data vendor is Finnhub on its free tier. | FR-001 |
| Front end and API are deployed as one service behind one load balancer. | Preference. Keeps operations simple. |

## 5. Constraints and known limits

### Constraints

- Implementation constraints in Section 2.
- NFR-003 (alert within 1 minute) and AC-001 (dashboard loads within 5 seconds) set the latency budget for Section 4.
- FR-009 and NFR-001 require 7-year retention, which sets storage size and the archive tier.
- The fail-open rule in FR-010 means a Risk Engine outage can let orders through, so the management alert is the only safeguard.

### Known limits

- The Finnhub free tier restricts commercial use and has rate limits. Acceptable for a student project.
- Only one region is planned.
- VaR uses historical data and does not capture scenarios missing from that history.
- Server-sent events work for one server instance. Scaling out would need a shared message channel.
- Monthly digests are not yet defined as email or document. The delivery method is open.

### What would have to change if requirements grew

- **Higher message volume:** add a message queue in front of Ingestion, and partition market data storage.
- **Multi-region availability (NFR-005):** replicate the database and add a failover procedure.
- **Many dashboard users:** add a shared message channel behind the server-sent events.
- **More asset classes or metrics:** extend RiskLimit and add a Risk Engine method for each.
- **Stricter regulatory rules:** switch to the audit-trail alternative or add third-party access, if required.

## 6. Out of scope

Copied from the Non-Goals section of spec.md:

- NG-001: Legacy system integration. Trades are loaded by CSV upload.
- NG-002: Order execution. The system can block orders but does not route, place, or fill them.
- NG-003: External auditor portal. Auditors receive records on request.
- NG-004: Broker trade feeds.
- NG-005: Production-scale operation, including production throughput and multi-region availability.
