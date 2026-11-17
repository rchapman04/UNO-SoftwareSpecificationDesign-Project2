# plan.md: Implementation slices (v2, against the real suite)

**Baseline run** (`python -m pytest tests/`, Python 3.12, FastAPI 0.163, pydantic 2.14):
`22 failed, 1 skipped`. This matches the README. Causes: 18 `NotImplementedError` from the module under test, and 4 status-code assertions where the route stub returns 501.

**Done-when rule (every slice):** the listed tests pass, and no test that passed in the previous slice fails.

---

## Failing tests grouped by acceptance criterion ID (as the suite names them)

| Criterion (suite ID) | Failing | Skipped | Cause |
|---|---|---|---|
| AC-001 | 3 | 1 (refresh, UI) | 3 × status 501 (route stub) |
| AC-002 | 6 | 0 | 6 × `NotImplementedError` |
| AC-003 | 3 | 0 | 3 × `NotImplementedError` |
| AC-004 | 3 | 0 | 3 × `NotImplementedError` |
| AC-005 | 1 | 0 | `NotImplementedError` |
| AC-006 | 1 | 0 | status 501 (route stub) |
| AC-007 | 1 | 0 | `NotImplementedError` |
| AC-008 | 1 | 0 | `NotImplementedError` |
| AC-009 | 1 | 0 | `NotImplementedError` |
| AC-010 | 1 | 0 | `NotImplementedError` |
| AC-012 | 1 | 0 | `NotImplementedError` |
| **Total** | **22** | **1** | 18 `NotImplementedError`, 4 status 501 |

Full per-test list, exact names:

- `test_AT01_dashboard_returns_value_limit_status_and_concentration` (status 501 ≠ 200)
- `test_AT01_dashboard_loads_within_5_seconds` (status 501 ≠ 200)
- `test_AT01_no_token_rejected_with_no_data_and_control_accepted` (status 501 ≠ 401)
- `test_AT02_breach_creates_alert_with_policy_severity_and_excess`
- `test_AT02_inside_and_outside_var_boundary[499999.99-False-None]`
- `test_AT02_inside_and_outside_var_boundary[500000.01-True-excess1]`
- `test_AT02_banner_frame_is_emitted_for_the_alert`
- `test_AT02_alert_created_within_60_seconds[59-True]`
- `test_AT02_alert_created_within_60_seconds[61-False]`
- `test_AT03_invalid_record_discarded_logged_and_control_stored`
- `test_AT03_validate_record_rejects_bad_price_and_accepts_control`
- `test_AT03_mixed_batch_stores_only_the_valid_record`
- `test_AT04_order_over_threshold_is_blocked_with_no_side_effects_and_control_allowed`
- `test_AT04_inside_and_outside_credit_boundary[499.9999-allow]`
- `test_AT04_inside_and_outside_credit_boundary[500.0001-block]`
- `test_AT05_reupload_updates_the_trade_and_does_not_duplicate_it`
- `test_AT06_request_without_token_is_rejected_with_no_data` (status 501 ≠ 401)
- `test_AT07_auditor_cannot_acknowledge_and_alert_stays_created`
- `test_AT08_acknowledge_resolved_alert_rejected_and_control_created_accepted`
- `test_AT09_concurrent_acknowledgment_first_applied_second_rejected`
- `test_AT10_fail_open_when_risk_engine_down_and_control_blocked`
- `test_AT12_trader_list_excludes_policy_alert_and_risk_manager_sees_it`
- Skipped: `test_AT01_dashboard_refreshes_every_60_seconds` (UI behaviour, out of REST scope)

---

## Slices

### S1. Thin path: accept one valid market data batch
- **Goal:** An Administrator logs in, posts one valid record to `POST /market-data/batches`, and gets 202 with `accepted = 1`.
- **Spec sources:** FR-001, FR-006, NFR-002 (token check only), NFR-004 (accepted path).
- **Criteria:** none.
- **Tests:** none in the suite. No route-level accepted-path test exists, so this slice is verified by the S4 tests.
- **Skeleton:** route 1 `POST /auth/login` and route 6 (accepted path only). `AccessControl.authenticate_credentials`, `authenticate_request`, `authorize` (happy path). `PositionTradeStore.get_user_by_username`, `get_user`, `transaction`, `save_market_data`. `MarketDataIngestion.ingest_batch` and `validate_record` (accepted path). `HealthMonitor.record_activity`.
- **Depends on:** none.
- **Done when:** the proposed route-level test passes (it does not exist yet). No suite test is assigned.
- **Status:** not started.

### S2. Health, readiness, and pipeline status
- **Goal:** Liveness, readiness, and pipeline status reflect the probes and recorded activity. Readiness returns 503 when a dependency is down.
- **Spec sources:** FR-008, NFR-006.
- **Criteria:** none.
- **Tests:** none in the suite. NFR-006 states that health and readiness endpoint tests are required.
- **Skeleton:** routes 3, 4, 5. `HealthMonitor.check_liveness`, `check_readiness`, `get_pipeline_status`. Also fix route 4 (see Skeleton issues 1).
- **Depends on:** S1 (route 5 needs `authorize`).
- **Done when:** health tests pass. None assigned in the suite.
- **Status:** not started.

### S3. Authentication: missing token rejected
- **Goal:** A request with no token gets 401 and no data. A valid token is then accepted.
- **Spec sources:** FR-006, NFR-002.
- **Criteria:** AC-006 .
- **Tests:**
  - `test_AT01_no_token_rejected_with_no_data_and_control_accepted`
  - `test_AT06_request_without_token_is_rejected_with_no_data`
- **Skeleton:** `AccessControl.authenticate_request` (missing and invalid header paths). `AccessControl.assign_role` and route 2 `PUT /users/{user_id}/role` (Administrator only). `PositionTradeStore.set_user_role`. Route `require_principal` is already in `create_app`.
- **Depends on:** S1.
- **Notes:** `test_AT06` repeats `test_AT01`'s request and assertions (Test issues 9). Both must pass here. The `route_client()` fixture builds `DashboardApi` with every collaborator set to `None`, so `authenticate_request` will raise `AttributeError` (500) rather than 401 once implemented unless the fixture is wired (Test issues 3).
- **Done when:** both tests pass after Test issues 3 is resolved.
- **Status:** blocked on test wiring.

### S4. Market data validation and rejected-record audit
- **Goal:** Invalid records are discarded, a failure is logged, and the rejection is written to the Audit Log. Valid records in the same batch are stored.
- **Spec sources:** FR-007, NFR-004, FR-005, NFR-001 (audit write).
- **Criteria:** AC-003.
- **Tests:**
  - `test_AT03_validate_record_rejects_bad_price_and_accepts_control`
  - `test_AT03_invalid_record_discarded_logged_and_control_stored`
  - `test_AT03_mixed_batch_stores_only_the_valid_record`
- **Skeleton:** `MarketDataIngestion.validate_record` (full rules), `ingest_batch` (rejection path). `AuditLog.append`, `list_rejected_market_data`. Route 7 `GET /market-data/rejections`.
- **Depends on:** S1. `validate_record` alone needs nothing else, so `test_AT03_validate_record_rejects_bad_price_and_accepts_control` can turn green first.
- **Notes:** the rule is "price must be numeric", which the spec does not define (Design question 6, Test issues 4).
- **Done when:** the three AT03 tests pass.
- **Status:** not started.

### S5. Trade upload with idempotent upsert
- **Goal:** Re-uploading a trade ID updates the trade and does not duplicate it.
- **Spec sources:** FR-001.
- **Criteria:** AC-005 .
- **Tests:** `test_AT05_reupload_updates_the_trade_and_does_not_duplicate_it`
- **Skeleton:** `PositionTradeStore.upload_trade_csv`, `upsert_trades`, `list_trades`, `get_trade`. Route 8 `POST /trades/uploads` (store step only). 422 for `InvalidTradeFile`.
- **Depends on:** S3.
- **Notes:** the test uses `PositionTradeStore(database_url="sqlite:///:memory:")`. Architecture says PostgreSQL, and an in-memory SQLite database is not shared across connections (Test issues 6).
- **Done when:** the test passes against a store that persists between calls.
- **Status:** blocked on Test issues 6.

### S6. Risk metrics and trader exposure
- **Goal:** Compute portfolio value, exposure, historical-simulation VaR, sector concentration, and trader exposure. Reject VaR confidence below 95%.
- **Spec sources:** FR-002, FR-005 (trade metrics), FR-010 (exposure input).
- **Criteria:** none.
- **Tests:** none in the suite. The 95% confidence limit (94.99% rejected) is in test_plan.md Section 2 but not in the suite (Test issues 2).
- **Skeleton:** `RiskEngine.calculate_metrics`, `get_trade_metrics`, `get_trader_exposure`. `PositionTradeStore.list_trades_for_trader`. Routes 10 and 22.
- **Depends on:** S5.
- **Blocked:** the confidence and horizon values come from RiskPolicy, which has no owner (Design question 1).
- **Status:** not started.

### S7. Dashboard view (AC-001)
- **Goal:** The dashboard returns portfolio value, exposure, within-limits status, and sector concentration for P1.
- **Spec sources:** FR-003, AC-001.
- **Criteria:** AC-001.
- **Tests:**
  - `test_AT01_dashboard_returns_value_limit_status_and_concentration`
  - `test_AT01_dashboard_loads_within_5_seconds`
- **Skeleton:** route 11 `GET /dashboard`. `LimitMonitor.limit_statuses`, `get_active_policy`. `PositionTradeStore.list_positions`, `get_latest_market_data`. `RiskEngine.calculate_metrics`.
- **Depends on:** S6, S3.
- **Notes:** `get_active_policy` still raises because `policy_source` is `_unassigned_policy` (Design question 1). The fixture P1 has no VaR, so `within_limits = true` is not supported by the fixtures (Test issues 5). The timing test measures a stub request, not a page load (Test issues 7).
- **Done when:** both tests pass after Test issues 3 and 5 are resolved.
- **Status:** blocked.

### S8. Dashboard layout save and load
- **Goal:** A user's layout is saved to their account and returned on load.
- **Spec sources:** FR-003 (customization), G-25.
- **Criteria:** none.
- **Tests:** none in the suite.
- **Skeleton:** routes 12 and 13. `DashboardApi.get_dashboard_layout`, `save_dashboard_layout`. Repository is `DashboardLayoutRepository` (defined in `dashboard_api.py`).
- **Depends on:** S7.
- **Blocked:** Design question 2 (no module owns the layout repository; `layouts=None` in `build_api`).
- **Status:** blocked.

### S9. Limit evaluation and alert creation (AC-002 part 1)
- **Goal:** A breached limit produces a Breach with the policy severity and the excess. The VaR limit boundary is $500,000. Alert creation is timed from the breach.
- **Spec sources:** FR-004, FR-005, NFR-001, NFR-003, AC-002.
- **Criteria:** none. AC-002 is completed in S10.
- **Tests:**
  - `test_AT02_breach_creates_alert_with_policy_severity_and_excess`
  - `test_AT02_inside_and_outside_var_boundary[499999.99-False-None]`
  - `test_AT02_inside_and_outside_var_boundary[500000.01-True-excess1]`
  - `test_AT02_alert_created_within_60_seconds[59-True]`
  - `test_AT02_alert_created_within_60_seconds[61-False]`
- **Skeleton:** `LimitMonitor.evaluate`, `evaluate_and_alert`. `AlertService.create_alert` (state Created, audit entry). Route 9 `POST /risk-assessments`. Route 16 `GET /alerts/{alert_id}`. Recalculation hook in route 8.
- **Depends on:** S4 (audit). These tests use `FakeAlertService`, so they do not need S6 or S7 to run.
- **Notes:** the latency start point is the test's fixed `T0`, not a breach event (Test issues 8). The severity and excess come from the policy the test supplies, so the policy owner question (Design question 1) does not block these tests.
- **Done when:** the five tests pass.
- **Status:** not started.

### S10. Alert banner stream (AC-002 part 2)
- **Goal:** A new alert is pushed to open streams.
- **Spec sources:** FR-004, AC-002.
- **Criteria:** AC-002.
- **Tests:** `test_AT02_banner_frame_is_emitted_for_the_alert`
- **Skeleton:** `AlertService.open_alert_stream`. Route 15 `GET /alerts/stream`. The push step in `create_alert`.
- **Depends on:** S9.
- **Notes:** the test expects an existing alert to be sent when a viewer connects. Contract §1.8 says frames are sent when alerts are created or change (Test issues 10). The test does not check that the banner arrives before details (AC-002 C2). Neither is covered yet.
- **Done when:** the test passes after Test issues 10 is decided.
- **Status:** blocked on Test issues 10.

### S11. Alert positions and full details
- **Goal:** An alert returns the positions it affects and a breakdown of its risk.
- **Spec sources:** FR-004 (View Positions, Full Details).
- **Criteria:** none.
- **Tests:** none in the suite.
- **Skeleton:** routes 17 and 18. `PositionTradeStore.list_positions_for_assets`. Details assembly uses `AlertDetails` (defined in `dashboard_api.py`) and `RiskEngine` metrics.
- **Depends on:** S9, S6.
- **Status:** not started.

### S12. Alert list visibility by role (AC-012)
- **Goal:** Each role sees only the alerts routed to it. A trader does not see policy alerts. A Risk Manager does.
- **Spec sources:** FR-004 (routing).
- **Criteria:** AC-012 .
- **Tests:** `test_AT12_trader_list_excludes_policy_alert_and_risk_manager_sees_it`
- **Skeleton:** `AlertService.list_alerts` (viewer and state filters). Route 14 `GET /alerts`.
- **Depends on:** S9.
- **Notes:** portfolio-level routing is open (Design question 7). This test uses policy and trade-level alerts only.
- **Done when:** the test passes.
- **Status:** not started.

### S13. Alert acknowledgment: authorization, lifecycle, concurrency
- **Goal:**
  - An Auditor cannot acknowledge (AC-007).
  - A resolved alert cannot be acknowledged (AC-008).
  - Two simultaneous acknowledgments: the first is applied, the second is rejected (AC-009).
- **Spec sources:** FR-004, FR-006, AC-002 (acknowledgment step).
- **Criteria:** AC-007, AC-008, AC-009.
- **Tests:**
  - `test_AT07_auditor_cannot_acknowledge_and_alert_stays_created`
  - `test_AT08_acknowledge_resolved_alert_rejected_and_control_created_accepted`
  - `test_AT09_concurrent_acknowledgment_first_applied_second_rejected`
- **Skeleton:** `AlertService.acknowledge_alert`. Route 19 `POST /alerts/{alert_id}/acknowledge` and `DashboardApi.acknowledge_alert`. `AlertVersionConflict` → 409.
- **Depends on:** S9, S3.
- **Notes:**
  - `test_AT07` sets only `api.alert_service`. `DashboardApi.acknowledge_alert` must check roles through `access_control`, which is `None` in the test (Test issues 3).
  - `test_AT08` uses `assert_rejected`, which accepts any exception (Test issues 4).
  - Who may acknowledge is still open (G-11). Only the Auditor denial and the Trader acceptance are tested.
- **Done when:** the three tests pass after Test issues 3 and 4 are resolved.
- **Status:** blocked on test wiring and assertion strength.

### S14. Trade audit trail and audit immutability
- **Goal:** Trade security information, risk metrics, and the audit history are returned to all five roles. Audit records cannot be edited.
- **Spec sources:** FR-005, NFR-001.
- **Criteria:** none.
- **Tests:** none in the suite. EXTRA-07 (audit immutability) from test_plan.md is absent from the suite (Test issues 2).
- **Skeleton:** `AuditLog.get_trail`. Routes 21 and 23. The `AUDIT_RECORDS_ACCESSED` record.
- **Depends on:** S5, S9, S4.
- **Status:** not started.

### S15. Mitigation plans (FR-011)
- **Goal:** Traders, Risk Analysts, and Risk Managers create, update, list, and review plans linked to an alert. Each change is recorded.
- **Spec sources:** FR-011.
- **Criteria:** none.
- **Tests:** none in the suite.
- **Skeleton:** `MitigationTracker.create_plan`, `update_plan`, `list_plans_for_alert`, `get_plan_history`. Routes 25 to 28.
- **Depends on:** S9, S14.
- **Blocked in part:** `PlanStatus` values (Planned, In Progress, Completed, Cancelled) are chosen in code. The spec does not give them (Design question 10).
- **Status:** not started.

### S16. Alert resolution with optional plan link
- **Goal:** Resolving records the user and time and can link a plan.
- **Spec sources:** FR-004, FR-011.
- **Criteria:** none.
- **Tests:** none in the suite. Resolution is not tested directly (it appears only in `test_AT08`'s setup).
- **Skeleton:** `AlertService.resolve_alert`. Route 20 `POST /alerts/{alert_id}/resolve` (plan check through `MitigationTracker`).
- **Depends on:** S13, S15.
- **Status:** not started.

### S17. Pre-trade check: block path (AC-004)
- **Goal:** An order that would take a trader above the credit threshold is blocked before entry. The trader is notified and the block is logged.
- **Spec sources:** FR-010, NFR-001, AC-004.
- **Criteria:** AC-004.
- **Tests:**
  - `test_AT04_order_over_threshold_is_blocked_with_no_side_effects_and_control_allowed`
  - `test_AT04_inside_and_outside_credit_boundary[499.9999-allow]`
  - `test_AT04_inside_and_outside_credit_boundary[500.0001-block]`
- **Skeleton:** `PreTradeCheck.check_order` (block path). `AlertService.send_notification`. Route 24 `POST /pre-trade-checks`. `credit_threshold_for` (source undefined).
- **Depends on:** S6, S4. Tests use `FakeRiskEngine` and `FakeAlertService`.
- **Notes:** `build_api` passes `credit_threshold_for=lambda trader_id: None`, so the real app blocks nothing until the policy owner is decided (Design question 1).
- **Done when:** the three tests pass.
- **Status:** not started.

### S18. Pre-trade check: fail-open path (AC-010)
- **Goal:** If the Risk Engine is unavailable, the order is allowed, flagged fail-open, logged, and management is alerted.
- **Spec sources:** FR-010, NFR-005.
- **Criteria:** AC-010 (the same behaviour is test-plan EXTRA-06).
- **Tests:** `test_AT10_fail_open_when_risk_engine_down_and_control_blocked`
- **Skeleton:** `PreTradeCheck.check_order` (fail-open path, writes `ORDER_FAILED_OPEN`). Management alert via `AlertService`.
- **Depends on:** S17.
- **Notes:** management recipients are undefined (Design question 8). The test checks only that some notification was sent, which the Trader alone would satisfy (Test issues 7).
- **Done when:** the test passes after Test issues 7 is resolved.
- **Status:** blocked on Test issues 7 and Design question 8.

### S19. Archiver (FR-009)
- **Goal:** Audit records older than 1 year move to WORM storage with 7-year retention. Nothing is deleted.
- **Spec sources:** FR-009, NFR-001.
- **Criteria:** none.
- **Tests:** none in the suite. The retention and archive-after-1-year limits in test_plan.md Section 2 are absent (Test issues 2).
- **Skeleton:** `Archiver.run_archive`. `AuditLog.list_records_before`, `mark_archived`. Route 30 `POST /archive-runs`.
- **Depends on:** S14.
- **Blocked:** `BlobWriteFailed` is referenced by the contract but not defined (Design question 3).
- **Status:** blocked.

### S20. Monthly alert digest (FR-012)
- **Goal:** Once a month, each recipient receives one digest of the alerts created in the previous month.
- **Spec sources:** FR-012.
- **Criteria:** none.
- **Tests:** none in the suite.
- **Skeleton:** `AlertDigest.build_digest`, `send_monthly_digest`. `AlertService.list_alerts_created_between`. Route 29 `POST /alert-digests`.
- **Depends on:** S9, S12.
- **Blocked:** `DeliveryFailed` is not defined. `delivery` and `recipients_for` are `None` in `build_api` (Design question 4).
- **Status:** blocked.

---

## Coverage check

**Suite tests (23 total, 22 failing, 1 skipped), each in one slice:**

| Slice | Tests |
|---|---|
| S3 | `test_AT01_no_token_rejected_with_no_data_and_control_accepted`, `test_AT06_request_without_token_is_rejected_with_no_data` |
| S4 | `test_AT03_validate_record_rejects_bad_price_and_accepts_control`, `test_AT03_invalid_record_discarded_logged_and_control_stored`, `test_AT03_mixed_batch_stores_only_the_valid_record` |
| S5 | `test_AT05_reupload_updates_the_trade_and_does_not_duplicate_it` |
| S7 | `test_AT01_dashboard_returns_value_limit_status_and_concentration`, `test_AT01_dashboard_loads_within_5_seconds` |
| S9 | the five `test_AT02_…` tests except the banner (breach, two boundary cases, two latency cases) |
| S10 | `test_AT02_banner_frame_is_emitted_for_the_alert` |
| S12 | `test_AT12_trader_list_excludes_policy_alert_and_risk_manager_sees_it` |
| S13 | `test_AT07_…`, `test_AT08_…`, `test_AT09_…` |
| S17 | `test_AT04_order_over_threshold_…`, `test_AT04_inside_and_outside_credit_boundary[499.9999-allow]`, `test_AT04_inside_and_outside_credit_boundary[500.0001-block]` |
| S18 | `test_AT10_fail_open_when_risk_engine_down_and_control_blocked` |
| — | `test_AT01_dashboard_refreshes_every_60_seconds` (skipped; UI, out of REST scope) |

**Acceptance criteria:** AC-001 → S7. AC-002 → S10. AC-003 → S4. AC-004 → S17. AC-005 → S5. AC-006 → S3. AC-007, AC-008, AC-009 → S13. AC-010 → S18. AC-012 → S12. AC-011 is retired (no test; not in the plan).

**Routes (all 30 exist in `dashboard_api.py`):** 1 S1; 2 S3; 3, 4, 5 S2; 6 S1 and S4; 7 S4; 8 S5 and S9; 9 S9; 10 S6; 11 S7; 12, 13 S8; 14 S12; 15 S10; 16 S9; 17, 18 S11; 19 S13; 20 S16; 21, 23 S14; 22 S6; 24 S17; 25 to 28 S15; 29 S20; 30 S19.

**Functions:** every `AccessControl`, `AuditLog`, `HealthMonitor`, `MarketDataIngestion`, `RiskEngine`, `LimitMonitor`, `AlertService`, `MitigationTracker`, `AlertDigest`, `PreTradeCheck`, `Archiver`, and `PositionTradeStore` method is assigned to at least one slice. `AccessControl.assign_role` is in S3 (added to its skeleton list).

---

## Fits no slice

- `test_AT01_dashboard_refreshes_every_60_seconds` (skipped). UI behaviour.
- NFR-005 uptime (99.99%). Operational measurement, no test, no mechanism.
- NFR-007 readability. UI behaviour.
- NFR-001 timestamps (server UTC on audit writes). No test.
- NFR-002 encryption at rest and in transit. Infrastructure.
- No suite test exists for: FR-002 VaR confidence limit (S6); alert severity values (S9); retention and archive limits (S19); EXTRA-07 audit immutability (S14); FR-008 and NFR-006 health tests (S2). These are gaps in the suite, not in the plan.

---

## Design questions

Status after reviewing the code: several types now exist in code, so their "undefined" status is resolved. The status column says what is still open.

| # | Question | Status |
|---|---|---|
| 1 | **RiskPolicy owner: decided as the Risk Manager role.** Risk Managers create and change policies and limits (spec, Domain Model: RiskManager setLimit, managesPolicy). Still open: where policies are stored (no module in architecture.md; `policy_source` is `_unassigned_policy` in `build_api`), and the routes for managing them. None of the 30 routes creates or changes a policy, so new Risk Manager routes are needed. Each change is audited as `POLICY_CHANGED` (the event type exists). Blocks S6, S7, S9, S17 until storage is chosen. Proposal, not decided: a policy repository inside Position & Trade Store, with create and update routes limited to Risk Manager. Not added to architecture.md or contracts.md. |
| 2 | **Dashboard layout repository.** `DashboardLayoutRepository` is a Protocol in `dashboard_api.py`. architecture.md has no module for it, and `layouts=None`. Blocks S8. | Partly resolved. Interface exists. Needs an architecture entry and an owner. |
| 3 | **Blob archive.** `BlobArchive` is a Protocol in `archiver.py`. `BlobWriteFailed` is still not defined. `blob=None` in `build_api`. Blocks S19. | Partly resolved. Define `BlobWriteFailed`. Choose the blob client. |
| 4 | **Digest delivery.** `DigestDelivery` is a Protocol in `alert_digest.py`. `DeliveryFailed` is not defined. `delivery` and `recipients_for` are `None`. Blocks S20. | Partly resolved. Define `DeliveryFailed`. Choose the delivery method (architecture.md says it is open). |
| 5 | **Access Control logging.** NFR-002 requires logging authentication successes and failures. `AccessControl` injects `store`, `signing_key`, `now`, `token_ttl`, not `audit_log`. | Open. Adding `audit_log` changes the architecture (Access Control gains a dependency on Audit Log). Decision needed. |
| 6 | **Validation rules.** FR-007 and AC-003 refer to validation rules the spec does not define. Contract §1.5 points to "section 4", which does not exist. Blocks completion of S4. | Open. Spec decision needed. |
| 7 | **Routing for portfolio-level breaches.** `AlertKind` has `TRADE_LEVEL` and `POLICY_DESIGN` only. `RiskLimit` already has `alert_kind`, so a portfolio VaR limit can be routed by its policy. | Open, with a proposed answer: route by `RiskLimit.alert_kind`, and record that in architecture.md. Decision needed. |
| 8 | **Management recipients for fail-open alerts** (G-17). | Open. Blocks S18. |
| 9 | **AlertDetails.** Now defined in `dashboard_api.py` as `AlertDetails(alert, metrics)`. Not in architecture.md. | Partly resolved. Needs an architecture entry. |
| 10 | **Plan status values.** `PlanStatus` (Planned, In Progress, Completed, Cancelled) is defined in code, but the spec does not give these values. Transitions are still undefined (G-22). | Partly resolved. Values are invented in code, so they need confirmation. |
| 11 | **Engineering staff role** (route 5, FR-008). `Role` has five members and none is engineering staff. | Open. |
| 12 | **Service accounts** (route 6, scheduled uploads, G-26). Not defined. | Open. |
| 13 | **contracts.md section 4 is missing.** Still referenced at lines 96, 105, 120, 210. The file has sections 0 to 3 only. | Open. Content is needed, or the references must be removed. |
| 14 | **Repositories and types.** All error types referenced by contracts are now defined except `BlobWriteFailed` and `DeliveryFailed` (see 3 and 4). `AlertRepository` and `PlanRepository` exist as Protocols but are `None` in `build_api`. | Mostly resolved. Wiring is missing. |
| 15 | **Recalculation after upload.** Route 8 calls Risk Engine and Limit Monitor. No module orchestrates it. | Open. Affects S5 and S9. |

---

## Test issues

Status after this round. Numbers match the references elsewhere in this file. No assertion has been changed.
2. **Suite gaps: open, new tests to be written in their slices.** These are additions, not corrections: a route-level accepted-path test (S1); health and readiness tests, which NFR-006 requires (S2); the 94.99% VaR confidence rejection (S6); the severity values (S9); audit immutability, EXTRA-07 (S14); retention and archive limits (S19).
4. **`assert_rejected` accepts any exception.** Correct in S13 with `test_AT08_...`. Needs a named lifecycle error (for example `InvalidAlertTransition`). The contracts do not define one, so contracts.md needs an entry first.
5. **AT-01 `within_limits is True` with no VaR for P1.** The fakes now seed P1 positions and prices, but not a VaR. Correct in S7 (add a VaR below $500,000 to the fixture).
6. **AT-05 uses `sqlite:///:memory:`.** Correct in S5: use a test PostgreSQL database, or a fake store.
7. **AT-10 checks only that some notification was sent.** Correct in S18, after Design question 8 names the management recipients.
8. **AT-02 latency measures from a fixed `T0`.** Correct in S9, once a breach event time is defined (G-08).
9. **AT-06 repeats AT-01's no-token test.** Correct in S3: keep one.
10. **AT-02 banner test assumes an existing alert is sent on connect.** Correct in S10, after contract §1.8 is decided. The test also does not check that the banner arrives before details (AC-002 C2).
11. **AT-03 uses an illustrative rule ("price must be numeric").** Correct in S4, once the spec defines a validation rule (G-02).
12. **AT-01 timing test measures a stub request.** Correct in S7 (G-07 sets how load time is measured).

## Skeleton issues

Found while reading the code. Not test issues; fix in the relevant slice.

1. **Readiness returns 200 when not ready.** Route 4 (`health_ready`) returns `api.get_readiness()` with no status mapping. Contract §2 says 503 when not ready. Fix in S2.
2. **`build_api` wires `None` for every repository and delivery.** `alerts`, `plans`, `delivery`, `recipients_for`, `blob`, `layouts` are `None`, and the policy source and credit threshold return nothing. The running app cannot create, store, or check alerts until these are wired. Each is tied to a design question above.
3. **Access Control has no `audit_log`** (Design question 5). Authentication failures cannot be logged as NFR-002 requires.
4. **`AccessControl.assign_role` has no slice owner.** Now listed in S3.
5. **Python 3.9 is untested.** The README says the code runs on 3.9. This environment has 3.12 only. The code uses `from __future__ import annotations` throughout, so 3.9 may work, but nothing here proves it.
6. **Packaging.** The README expects `app/`, `tests/`, and `requirements-dev.txt`. The uploads are flat, `fakes.py` and `test_acceptance.py` are at the top level, and `requirements-dev.txt` is missing. The tests were run from a rebuilt layout (`/home/claude/risk-skeleton`). `httpx` emits a deprecation warning under `starlette.testclient`.

---

## Next action

Start S1 (thin path). The first suite test to turn green is `test_AT03_validate_record_rejects_bad_price_and_accepts_control`, which needs only `MarketDataIngestion.validate_record`. Open decisions before S1 is complete: the Risk Manager policy store (Design question 1) and the spec entries for AC-005 to AC-012 (Test issues 1).
