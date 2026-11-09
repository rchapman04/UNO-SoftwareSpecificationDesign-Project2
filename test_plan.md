# Test Plan: Acceptance Criteria, Extra Cases, Limits, and Gaps

**Sources:** spec.md and architecture.md only. No implementation code was read.
**Scope:** the four acceptance criteria (AC-001 to AC-004), eight extra cases that cover requirements and checklist categories the criteria miss, every numeric limit in the requirements, and the spec gaps that affect testing.

## 0. Conventions and fixtures

**Outcomes.** Each check ends in one of: *accepted*, *rejected*, *blocked*, or *allowed*. The spec does not define HTTP status codes or error formats (G-01), so no row gives a status code.

**"Nothing created".** For every rejection, the check confirms that none of these exist: a new trade, market data row, alert, plan, order entry, or position change. The only new records allowed are the ones the spec requires for that outcome (for example, the audit entry for a blocked order).

**Units.** USD to the cent. Durations in seconds, or in minutes and seconds where the spec uses minutes.

**Fixtures.** All expected values come from these fixtures.

| Fixture | Definition |
|---|---|
| F1 Portfolio P1 | Asset A (Technology): 6,000 units × $100 = $600,000. Asset B (Energy): 4,000 units × $100 = $400,000. Total **$1,000,000**. Concentration: Technology **60.0%**, Energy **40.0%**. |
| F2 VaR limit | Portfolio VaR limit **$500,000**. Severity is set by the test RiskPolicy to *Critical* (test input; the spec does not fix it for this limit). |
| F3 Credit threshold | Trader T1 threshold **$1,000,000**. Current exposure **$950,000**. |
| F4 Valid market data | Record for asset A: price 101.25, currency USD, sector Technology, region US, data type price, observed at a valid UTC time. |
| F5 Users | T1 (Trader), RA1 (Risk Analyst), RM1 (Risk Manager), AUD1 (Auditor), ADM1 (Administrator). |

---

## 1. Test cases

One row per acceptance criterion (AC-001 to AC-004), followed by eight rows marked **EXTRA**. Each EXTRA row names the requirement it probes in the Requirement column, because most of those requirements have no acceptance criterion.

Each rejection has a **Control**: a valid request of the same shape that is accepted, so the rejection can only come from the requirement under test. Each rejected request is wrong in exactly one way. No case here depends on an open gap.

| ID | Requirement (spec section tested) | Cases (request or call → expected outcome, body fields, side effects) | Inside / outside | Control |
|---|---|---|---|---|
| **AC-001** | **FR-003** Display Risk Dashboard | **C1.** T1 calls `GET` dashboard for P1 (F1). Expected: *accepted*. Body: `portfolio_value` = 1,000,000.00 USD; `concentration_by_sector` = {Technology: 60.0%, Energy: 40.0%}; `within_limits` = true (no limit breached in fixture). Side effects: none; read-only.<br>**C2.** Load time for C1, from request to complete render. Expected: ≤ 5 s.<br>**C3.** Dashboard open for 3 minutes with no user action. Expected: a refresh at each 60 s interval (3 refreshes), with values re-read from the system.<br>**C4 (rejection).** Same request with no token. Expected: *rejected*; no dashboard data in the body. Side effects: no data read. | Load time: 4.9 s inside, 5.1 s outside.<br>Refresh interval: 60 s inside; 61 s outside (tolerance undefined, G-07). | C4: same request with T1's valid token → *accepted* (C1 result). |
| **AC-002** | **FR-004** Generate Risk Alerts; with **NFR-003** (1-minute latency) | **C1.** Calculation yields portfolio VaR **$525,000** against F2 limit **$500,000**. Expected: alert created, state *Created*, severity *Critical* (from policy). Breach info: exceeded by **$25,000**, which is **5.0%** of the limit. Description present. Routing by alert kind (routing for a portfolio VaR breach is undefined, G-09). Side effects: an alert record and an audit entry for the creation, timestamped by the system.<br>**C2.** Same breach, with the details service delayed by 30 s. Expected: the dashboard banner event arrives before details finish loading.<br>**C3.** Measure from the breach-causing calculation to alert creation. Expected: ≤ 60 s. | VaR: **$499,999.99** inside (expected: no alert). **$500,000.01** outside (expected: alert, excess $0.01).<br>Latency: 59 s inside; 61 s outside. Start point and equality undefined (G-04, G-08). | The inside case is a non-breach, so it has no rejection control. Its control is the outside case of the same fixture (an alert is created). |
| **AC-003** | **FR-007** Data Validation; with **NFR-004** | **C1.** Ingest a batch containing one record with price `"abc"` (other fields as F4). Expected: that record *rejected*; no market data row stored for it. Audit entry of type rejected market data, with the reason. A failure message is logged. Side effects: only the audit entry and the log message.<br>**C2.** Same batch with one valid record (F4) and the rejected one. Expected: valid record stored; invalid one discarded; batch result shows 1 accepted, 1 rejected.<br>The rule used here (*price must be numeric*) is an illustrative placeholder. The spec defines no rules (G-02). | Not applicable; the spec gives no numeric limit for validation. | C1: F4 with price `101.25` → *accepted*, stored, no audit rejection entry. Only the price value differs. |
| **AC-004** | **FR-010** Pre-trade credit check; with **NFR-001** (audit of blocked orders) | **C1.** T1 submits an order that adds **$100,000** (F3). Expected: *blocked* before entry. Projected exposure **$1,050,000**, which is **$50,000** over the $1,000,000 threshold. T1 notified of the block. Side effects: an audit entry for the blocked order with order details; no trade record, no position change.<br>**C2 (fail-open).** Same order while the Risk Engine is unavailable. Expected: *allowed*, flagged fail-open. Management alert raised. Audit entry for fail-open. | Post-order exposure: **$999,999.99** inside (order adds $49,999.99 → allowed). **$1,000,000.01** outside (order adds $50,000.01 → blocked). Equality at $1,000,000.00 undefined (G-04). | C1: order adds **$40,000** → projected $990,000 → *allowed*; no block entry; no notification. Only the order size differs. |
| **EXTRA-01** | **FR-001** Trade upload is repeatable (no AC) | Upload trade `T-100` with quantity 10, then re-upload `T-100` with quantity 12. Expected: both *accepted*; trade count for `T-100` is 1; quantity is 12. Side effects: one trade row. Handling of prior values is undefined (G-23). | n/a | n/a (not a rejection) |
| **EXTRA-02** | **NFR-002**, **FR-006** Authentication (no AC) | Data request (`GET` dashboard) with no token. Expected: *rejected*; no data returned. Side effects: failed authentication logged (NFR-002). | n/a | Same request with T1's token → *accepted* |
| **EXTRA-03** | **FR-006** Authorization (no AC) | AUD1 (Auditor) acknowledges an alert in *Created*. Expected: *rejected* (Auditor is read-only). Side effects: alert stays *Created*; no acknowledgment recorded. | n/a | T1 acknowledges the same alert → *accepted* |
| **EXTRA-04** | **FR-004** Alert lifecycle (state) | Acknowledge an alert already in *Resolved*. Expected: *rejected* (lifecycle is Created → Acknowledged → Resolved). Side effects: alert stays *Resolved*; acknowledgment fields unchanged. | n/a | Acknowledge an alert in *Created* → *accepted* |
| **EXTRA-05** | **FR-004** Concurrent actions on one alert (concurrency) | T1 and RA1 acknowledge the same alert at the same moment. Expected: first *accepted*; second *rejected*. Side effects: alert records the first user and time only; one acknowledgment audit entry. | n/a | Single acknowledgment by T1 → *accepted* |
| **EXTRA-06** | **FR-010**, **NFR-005** Fail-open when the Risk Engine is down (errors and precedence) | T1 submits an order adding $100,000 while the Risk Engine is unavailable (T1 at $950,000). Expected: *allowed*, fail-open; management alerted. Side effects: audit entry for fail-open; no block entry. | n/a | Same order with Risk Engine available → *blocked* (AC-004 C1) |
| **EXTRA-07** | **NFR-001** Audit records are immutable (listing and immutability) | ADM1 attempts to edit or delete an existing audit record. Expected: *rejected* (audit records are append-only). Side effects: record and record count unchanged. | n/a | ADM1 triggers a normal event that appends a record → *accepted* |
| **EXTRA-08** | **FR-004** Alert routing visibility (listing) | T1 lists alerts; a policy-kind alert exists. Expected: the policy alert is not in T1's list. Side effects: none. | n/a | RM1 lists alerts → policy alert listed |

---

## 2. Limits

Every numeric limit in the requirements. Each has the case just inside and the case just outside. Where the spec is silent on equality, the exact value is left out and listed as a gap.

| Limit | Source | Inside | Outside | Equality / note |
|---|---|---|---|---|
| VaR limit $500,000 | AC-002, FR-004 | $499,999.99 → no alert | $500,000.01 → alert | $500,000.00 undefined (G-04) |
| Credit threshold $1,000,000 | AC-004, FR-010 | Post-order exposure $999,999.99 → allowed | $1,000,000.01 → blocked | $1,000,000.00 undefined (G-04); "above" suggests strictly greater, but this is not stated |
| Dashboard load ≤ 5 s | AC-001 | 4.9 s | 5.1 s | "within 5 seconds" at exactly 5.0 s undefined (G-07) |
| Dashboard refresh every 60 s | AC-001 | 60 s interval | 61 s interval | Tolerance undefined (G-07) |
| Alert generated ≤ 1 min | AC-002, NFR-003 | 59 s from breach | 61 s from breach | 60 s undefined; start point undefined (G-08) |
| VaR confidence ≥ 95% | FR-002 | 95.00% → accepted | 94.99% → rejected | How confidence is set (RiskPolicy interface) is undefined (G-21). Control for the rejection: 95.00%. |
| Uptime 99.99% (≤ 4.32 min in a 30-day month) | NFR-005 | 259 s of downtime in a 30-day month | 260 s (fails 99.99%); 300 s (fails the spec's "< 5 min") | **Conflict:** 99.99% permits 4.32 min per 30-day month, but NFR-005 says < 5 min. The test uses 259 s (inside both) and 260 s (outside the 99.99% figure). See G-05. |
| Uptime 99.99% (≤ 52.56 min in 365 days) | NFR-005 | 3,153 s of downtime per year | 3,154 s (fails 99.99%); 3,600 s (fails "< 1 hour") | Consistent with the spec's 1-hour limit. |
| Audit retention ≥ 7 years | FR-009, NFR-001 | Record at age 7 years minus 1 day still exists | Deletion at 7 years plus 1 day | No deletion rule in the spec (G-06). Only the inside case is testable. |
| Archive after 1 year | FR-009 | Record at 364 days stays in primary store | Record at 366 days moved to archive storage | 365 days undefined (G-04) |
| Alert severity values | FR-004, NFR-007 | "Critical", "Warning", "Informative" accepted | Any other value (for example "Severe") rejected | Control: "Warning" accepted. |

---

## 3. Spec gaps

Gaps are not resolved here. Each one that affects a test says so.

### 3.1 Requirements with no acceptance criterion

- **FR-001** Ingest market data (trade CSV upload): no AC. Covered only by EXTRA-01.
- **FR-002** Calculate risk metrics: no AC. Covered only by the 95% confidence limit in Section 2.
- **FR-005** Audit trail: no AC. Covered only by EXTRA-07 (no edits to audit records).
- **FR-006** Authentication and authorization: no AC. Covered only by EXTRA-02 and EXTRA-03.
- **FR-008** Health and monitoring: no AC. No test in this plan.
- **FR-009** Data archiving: no AC. Covered only by the retention and archive limits in Section 2.
- **FR-011** Mitigation plan tracking: no AC. No test in this plan.
- **FR-012** Monthly digest: no AC. No test in this plan.
- **NFR-001** Auditability: links AC-002 and AC-004 but has no test of its own. Its append-only rule is covered by EXTRA-07. The timestamp rule is not tested.
- **NFR-002** Security and access control: links FR-005 and FR-006 only; no AC. Encryption at rest and in transit has no test here (not testable from the spec alone).
- **NFR-005** Availability (99.99%): no AC. Limits only.
- **NFR-006** Observability: no AC. No test in this plan.
- **NFR-007** Readability: no AC. No test in this plan (see G-28). Colours and the red flashing banner are UI properties and cannot be checked by API tests.

NFR-003 and NFR-004 link to AC-002 and AC-003, so those criteria cover them.

### 3.2 Acceptance criteria with no requirement statement

- **AC-001** asserts a 5-second load time and a 60-second refresh. Neither appears in the text of FR-003. The architecture cites AC-001 for them, but the spec's requirement text does not state them.
- **AC-002** asserts that the alert event is logged in the audit trail. FR-005 lists trades, risk assessments, and policy changes, not alerts. Only NFR-001 names alerts. The audit assertion traces to NFR-001, not to FR-004 or FR-005.

All other criteria trace to a requirement statement.

### 3.3 Gaps that block or change tests

| ID | Gap | Effect on this plan |
|---|---|---|
| G-01 | The spec defines no HTTP status codes, error format, or response bodies. | Outcomes are stated as accepted, rejected, blocked, or allowed, not as status codes. |
| G-02 | "Validation rules" in AC-003 are not defined. | AC-003 uses an illustrative numeric-price rule. |
| G-03 | FR-001 defines no validation for trade records. | No trade-validation case is in the plan. |
| G-04 | Equality at a limit is not stated: VaR "exceeds" $500,000; credit "above" $1,000,000; "within 5 seconds"; "within 1 minute"; "older than 1 year". | Each limit tests only values one cent or one tick away. Exact-limit cases are left out. |
| G-05 | 99.99% uptime gives 4.32 min per 30-day month, but NFR-005 says less than 5 min. | Both thresholds are tested (259 s inside, 260 s outside the 99.99% figure). The conflict needs a decision. |
| G-06 | Retention says "minimum 7 years" but gives no rule for deletion after that. | Only the inside case is tested. |
| G-07 | Refresh tolerance and load-time measurement (start and end points) are not defined. | Limits table uses the stated values only. |
| G-08 | The alert latency clock starts at "the risk limit breach", which is not defined as an event. Equality at 60 s is undefined. | Measurement point must be set before AC-002 C3 can run. |
| G-09 | Routing for a portfolio-level breach is not defined. Trade-level and policy/design kinds do not cover it. The "roles responsible for the affected asset" wording is not mapped to a route. | AC-002 C1 cannot assert a specific recipient list. |
| G-10 | The alert lifecycle state diagram is missing. The spec says so: "verify this against it". Whether a step can be skipped is unknown. | Skipping acknowledgment is not tested. |
| G-11 | Who may acknowledge or resolve an alert: only the responsible roles, or any role? | Only the Auditor denial (EXTRA-03) is tested. |
| G-12 | Concurrent orders against the same credit threshold. The spec does not say how they are checked. | Concurrent orders are not tested. |
| G-13 | Whether an order that reduces exposure while the trader is already over the threshold is blocked. | Not tested. |
| G-14 | Negative quantities and buy/sell side for exposure are not defined. | No test. |
| G-15 | Trade timestamps in the future, and the time zone for all timestamps, are not defined. | No test. |
| G-16 | "Once a month" has no day or period definition, and no time zone. | Digest period is not tested. |
| G-17 | Management recipients for the fail-open alert (FR-010) are not named. | Only "management is alerted" is tested. |
| G-18 | Role permissions are not listed beyond Auditor (read-only) and Administrator (assigns roles). There is no engineering-staff role, though FR-008 refers to one. | Pipeline status access is not tested. |
| G-19 | Format and content of the audit entry for failed or denied access (NFR-002). | Only "logged" is tested. |
| G-20 | Ordering of audit trail entries, and how archived records are retrieved. | Audit trail retrieval is not tested. |
| G-21 | How RiskPolicy is set: who sets VaR confidence and horizons, and the policy-change interface. | VaR confidence cases cannot run until an input path is defined. |
| G-22 | Mitigation plan status values and transition rules. FR-011 says "a status" without listing values. | No plan test in this plan. |
| G-23 | "Full history of the trade" (FR-005) and upsert-by-ID (FR-001) conflict: the spec does not say whether prior trade values must be kept in the audit history. | EXTRA-01 checks the update only. |
| G-24 | Prior values after re-upload: same as G-23. | Linked to G-23. |
| G-25 | Dashboard layout is saved to the account (FR-003), but no criterion tests it. | No test. |
| G-26 | The identity of a scheduled upload job (service account) is not defined. | No test for scheduled uploads. |
| G-27 | Whether a Trader may see another trader's trades or portfolios. | No test. |
| G-28 | Dashboard values need units and consistent severity markers (NFR-007). The spec does not define the unit format. | Not tested in this plan. |
| G-29 | The order of checks when a request fails both authentication and validation is not stated. FR-006 says authentication comes first before access to data, but does not say whether validation falls under that rule. | Not tested. Each fault is tested alone, and no double-fault case is included. |

---

## 4. Checks on this plan

- Each rejection in Section 1 has exactly one wrong input, and a control of the same request shape that is accepted.
- Every expected value is hand-computed from a fixture (Section 0) or a limit in the spec.
- Every numeric limit in the requirements appears in Section 2.
- The eight EXTRA rows cover identity, state, concurrency, errors and precedence, and listing. Time, input types, and what is returned have no extra case in this version. Boundaries are covered in Section 2.
- FR-008, FR-011, and FR-012 have no test in this plan. Section 3.1 lists them.
