# Description

A cloud-based, high-volume market data and risk assessment system for trading firms. The system ingests real-time market data and internal trade records, calculates risk metrics such as total exposure and Value at Risk (VaR), and displays the results on a risk dashboard that users can customize. When a risk limit is exceeded, it generates alerts for the users responsible for the affected asset. The system must keep a traceable audit trail to comply with SEC Rule 15c3-5 and related record-keeping guidelines. The minimum viable product implements FR-001 through FR-005 in that order with FR-006 through FR-009 as supporting requirements.

# Goals

- G1 Informed trading decisions: Give traders accurate, timely, and readable market and risk information so they can make informed trading decisions.
- G2 Acceptable risk exposure: Keep the firm's total risk exposure within approved risk limits and risk policies.
- G3 Rapid detection of violations: Detect risk limit violations and conflicts quickly and notify the users who need to act on them.
- G4 Collaborative mitigation: Let traders, risk analysts, and risk managers identify, discuss, and carry out mitigation of identified risks.
- G5 Regulatory compliance: Meet SEC Rule 15c3-5 requirements, with full traceability of trades, risk assessments, and policy changes.

# Domain Model

## Actors

- Trader: Enters and manages trades. Needs real-time market data and risk visibility before entering or leaving positions. (Subclass of Person)
- Risk Analyst: Monitors risk positions, creates risk assessments, and provides risk portfolios to managers and traders. (Subclass of Person)
- Risk Manager: Sets risk policies and limits, responds to over-exposure events, and selects mitigation strategies. (Subclass of Person)
- Auditor (external): Requests trade and source records from firm for external audits like SEC or other organizations.
- Legacy Systems (external): Existing internal systems, such as trade records and internal data, that the new system must integrate with and not replace.

## Objects

- Trade: An executed trade. It is the source record for risk calculations and audit history.
- Asset: A financial instrument that the firm holds or trades. Has a current price set by `MarketData`.
- MarketData: Market information from external sources, such as prices and market trends.
- RiskExposure: The financial risk the firm faces from trades, assets, and portfolios. Expressed as a monetary value or as a percentage of the total portfolio.
- RiskAssessment: The output of evaluating the risk of given positions or trades using predefined metrics and firm rules. Created by a `Risk Analyst`.
- RiskLimit: A preset maximum threshold for a risk metric, set by `Risk Manager` policies. When it is exceeded, an `Alert` is triggered. The ontology gives it a data property `totalExposure`.
- RiskPolicy: Management-defined rules and standards, including risk limits, that the firm follows.
- MitigationStrategy: A plan or set of options for reducing an identified risk.
- Alert: A notification the system generates when a risk limit is exceeded for an asset. Severity levels from the wireframe: Critical, Warning, Informative. The lifecycle from the source text is Created, then Acknowledged, then Resolved. The source state diagram is not in text form, so verify this against it.
- Dashboard: The central view for a user's portfolio risk. Shows market information and risk information. It is the hub for navigating to alerts and audit trails.

## Relationships

| Subject --> Relationship --> Object |

| Trader --> hasActiveTrade --> Trade |
| Trader --> hasRiskConflict --> RiskLimit |
| Trader --> receivedAlert --> Alert |
| RiskAnalyst --> receivedAlert --> Alert |
| RiskAnalyst --> createRiskAssessment --> RiskAssessment |
| RiskManager --> setLimit --> RiskPolicy |
| RiskManager --> managesPolicy --> RiskPolicy |
| RiskManager --> hasStrategy --> MitigationStrategy |
| RiskLimit --> triggersAlert --> Alert |
| Trade  -->hasRiskExposure --> RiskExposure |
| RiskExposure --> calculatedFrom --> Trade |
| Dashboard --> hasRiskInfo --> RiskExposure |
| Dashboard --> hasMarketInfo --> MarketData |
| Asset --> hasCurrentPrice --> MarketData |

# Functional Requirements

## Overview

The functional requirements fall into five logical groups:

- Data ingestion: FR-001, FR-007
- Risk calculation: FR-002
- Visualization and alerts: FR-003, FR-004
- Compliance and traceability: FR-005, FR-009
- Security and operations: FR-006, FR-008

## User Stories

### FR-001: Ingest Real-Time Market Data

Linked goals: G1 (Trader: access market information) G2 (Risk Analyst: maintain acceptable risk positions)

User story: As a Trader, I want the system to continuously receive market data from various sectors, regions, and data types, so that I can make the most informed trading decisions based on the information.

### FR-002: Calculate Risk Metrics

Linked goals: G1 (Trader: assess trade risk analysis) G2 (Risk Analyst: assess exposure and analyze and manage current risk)

User story: As a Risk Analyst, I want the system to automatically calculate risk metrics, so that I can assess current risk exposure and identify which positions pose the most risk.

### FR-003: Display Risk Dashboard

Linked goals: G1 (Trader: make informed trading decisions) G2 (Risk Analyst: maintain acceptable risk positions)

User story: As a Trader, I want to view a comprehensive risk dashboard of my portfolios, so that I can make quick decisions about positions to enter or leave.

Dashboard elements:

- Portfolio Value (display): current monetary value of the selected portfolio
- Risk Exposure (display): current risk exposure calculated for the portfolio
- Risk Limit (display): whether the portfolio is within current limits
- Portfolio Concentration (display): current concentration of assets by sector
- Refresh Button (button): allows user to refresh screen

Navigation: The Dashboard is the central hub. A user normally logs in and starts here. When an alert is generated, a red flashing banner appears at the top of the Dashboard and prompts the user to open the Alert Notification. From the Dashboard, the user can open the Audit Trail Interface for a given trade, either by clicking an active trade or from a future item.

### FR-004: Generate Risk Alerts for Conflicts and Violations

Linked goals: G2 (Risk Manager: resolve over-exposure events) G3 (Trader: resolve conflicts and alerts) G4 (Risk Analyst: mitigate identified risks)

User story: As a Risk Manager, I want the system to automatically send alerts from the dashboard when risks exceed limits, so that I can take immediate action and reduce exposure.

Alert notification elements:

- Alert Severity (status): Critical, Warning, or Informative
- Alert Description (display): the risk conditions that caused the alert
- Breach Information (display): how much the limit was exceeded
- Acknowledge Alert Button: acknowledges the alert and removes the pop-up
- View Positions Button: shows the positions and portfolios affected
- Full Details Button: shows a detailed breakdown of current risk and key metrics

### FR-005: Maintain a Trail of Trade Information for Compliance

Linked goals: G5 (all stakeholders: comply with regulatory rules and laws)

User story: As a stakeholder, I want the system to verify that trades, risk assessments, and policy changes are properly recorded and kept for full traceability, so that we can prove compliance with all SEC rules.

Audit Trail Interface elements:

- Security Information (display): information about the trade and the asset
- Risk Metrics (display): metrics calculated for the trade
- Audit Trail (display): the full history of the trade, kept for auditing

## Supporting Requirements

### FR-006: Authentication and Authorization

Linked goals: Supports all goals (access control).

The system shall authenticate user roles and valid credentials before granting access to any system data. A system administrator assigns roles based on each user's job. Each role has specific permissions and visibility.

### FR-007: Data Validation and Error Handling

Linked goals: G1, G5

The system shall validate all incoming market data before storing it. Any record that fails validation is discarded, and a failure message is logged.

### FR-008: System Health and Monitoring

Linked goals: G1 (supports reliable market information)

The system shall monitor data pipeline status, connectivity, and activity. System status is available to engineering staff and administrators. The system shall use readiness and health checks to monitor API health.

### FR-009: Data Archiving

Linked goals: G5

The system shall keep all audit records for a minimum of 7 years to comply with SEC and other federal regulations. Information older than 1 year shall be moved to archive-level cloud storage.

# Acceptance Criteria

Each scenario is tagged with its requirement ID so it can be traced back to the functional requirement it verifies.

### FR-010: Pre-trade credit check

Linked goals: G5

The system shall block any order that would raise a Trader's exposure above the pre-set credit threshold. The system shall then notify the Trader and log the blocked order information. 


## Source Scenarios

### AC-001 (verifies FR-003)

gherkin
Feature: Display Risk Dashboard
  Scenario: Trader reviews portfolio risk before a trade decision
    Given a Trader logs into the system
    When the risk dashboard loads
    Then the dashboard shall display the portfolio value
    And the dashboard shall display whether the portfolio is within its limits
    And the dashboard shall display asset concentration by sector
    And the dashboard shall load completely within 5 seconds
    And the dashboard shall refresh automatically every 60 seconds


### AC-002 (verifies FR-004)

gherkin
Feature: Generate Risk Alert for Limit Violation
  Scenario: Portfolio VaR exceeds the risk limit
    Given the firm has set a maximum portfolio VaR limit of $500,000
    And the portfolio VaR is calculated at $525,000
    When risk calculations determine the limit has been exceeded
    Then the system shall generate an alert within 1 minute
    And the alert severity shall be set by the RiskPolicy for that limit
    And the system shall display the alert as a banner on the Dashboard
    And the system shall log the alert event in the audit trail


### AC-003 (verifies FR-007)

gherkin
Feature: Validate Incoming Market Data
  Scenario: Market data record fails validation
    Given an incoming market data record that fails validation rules
    When the system ingests the record
    Then the system shall discard the record
    And the system shall log a failure message



### AC-004 (verifies FR-002)

gherkin
Feature: Pre-Trade Credit Threshold Check
  Scenario: Order would exceed a pre-set credit threshold
    Given a pre-set credit threshold of $1,000,000 for a Trader
    And the Trader's current exposure is $950,000
    When the Trader submits an order that would add $100,000 of exposure
    Then the system shall block the order before it is entered
    And the system shall notify the Trader that the order was 