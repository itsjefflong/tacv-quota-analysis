---
name: tacv-quota-analysis
description: "Generate TACV (Total Annual Contract Value) quota recommendations for Snowflake customer accounts. Use when asked about quota, TACV, renewal analysis, account planning, consumption analysis, capacity remaining, burn rate, contract structure, or quota-bearing classification. Triggers: tacv, quota, renewal, account plan, consumption, capacity, burn rate, overage, contract structure, quota-bearing, growth acv, renewal acv, pull-forward, amendment, early renewal."
---

# TACV Quota Scenario Modeling Skill

## Overview

This skill generates data-driven TACV quota recommendations for individual Snowflake customer accounts. It pulls data from multiple Snowflake tables, determines contract structure, calculates consumption trajectories, evaluates strategic options, and produces Conservative / Base / Stretch scenarios with quota-bearing classification.

**Snowflake Fiscal Year**: Feb 1 – Jan 31. FY27 = Feb 1, 2026 → Jan 31, 2027.

---

## Step 1: Identify the Account

**Goal:** Get the account name or Salesforce Account ID from the user.

Accept any of: Salesforce Account ID (18-char, starts with `001`), account name (exact or partial), or Ult-Parent name.

If the user provides a name, search for the Account ID:

```sql
SELECT ACCOUNT_ID, ACCOUNT_NAME, SEGMENT, PATCH, OWNER_NAME
FROM SALES.PLANNING.GLOBAL_PLANNING
WHERE ACCOUNT_NAME ILIKE '%{user_input}%'
  AND SNAPSHOT_DATE = (SELECT MAX(SNAPSHOT_DATE) FROM SALES.PLANNING.GLOBAL_PLANNING)
LIMIT 10;
```

⚠️ **STOP** — If multiple matches, show results and ask user to confirm which account.

---

## Step 2: Pull Account Data from All Sources

**Goal:** Assemble the complete data profile from 5 sources using the confirmed Account ID.

### 2A. Primary Data — SALES.PLANNING.GLOBAL_PLANNING

Main source. Values are in **ACTUAL DOLLARS** (not $K). Use the most recent snapshot.

```sql
SELECT
    ACCOUNT_ID, ACCOUNT_NAME, ACCOUNT_CATEGORY, SEGMENT,
    OWNER_NAME, PATCH, INDUSTRY_CATEGORY, EMPLOYEE_COUNT,
    -- Consumption & Capacity (ACTUAL $)
    CAPACITY_USAGE_REMAINING,
    ANNUAL_CONSUMPTION_RUN_RATE_L90D,
    ANNUAL_CONSUMPTION_RUN_RATE_L30D,
    PRIOR_RENEWAL_BASE,
    FY26_CONSUMPTION_ACTUALS,
    FY25_CONSUMPTION_ACTUALS,
    FY24_CONSUMPTION_ACTUALS,
    -- Contract
    CONTRACT_END_DATE, OUT_YEAR_SEGMENT_INDEX,
    CAPACITY_OVERAGE_DATE, FY26_PREDICTED_OVERAGE,
    IS_CONSECUTIVE_DOWNSELL,
    -- Territory
    AREA, THEATER, REGION, SUBREGION, DISTRICT,
    -- Location
    BILLING_COUNTRY, BILLING_STATE, BILLING_CITY, BILLING_POSTAL_CODE,
    SNAPSHOT_DATE
FROM SALES.PLANNING.GLOBAL_PLANNING
WHERE ACCOUNT_ID = '{account_id}'
  AND SNAPSHOT_DATE = (SELECT MAX(SNAPSHOT_DATE) FROM SALES.PLANNING.GLOBAL_PLANNING)
LIMIT 1;
```

### 2B. Contract Structure — FIVETRAN.SALESFORCE.CONTRACT

**CRITICAL** for determining quota-bearing classification.

```sql
SELECT
    ID, CONTRACT_NUMBER, STATUS, START_DATE, END_DATE, CONTRACT_TERM,
    AGREEMENT_TYPE_C, CHANNEL_C, PRODUCT_TYPE_C, CURRENCY_ISO_CODE,
    WAREHOUSE_PRICE_PER_CREDIT_C, SNOWPAY_OPT_IN_C, SNOWPAY_AMOUNT_C,
    SBQQ_RENEWAL_TERM_C, SBQQ_ACTIVE_CONTRACT_C, CAPACITY_ORDER_TYPE_C
FROM FIVETRAN.SALESFORCE.CONTRACT
WHERE ACCOUNT_ID = '{account_id}'
  AND IS_DELETED = FALSE AND STATUS = 'Activated'
ORDER BY END_DATE DESC;
```

**Contract Structure Logic:**
```
Total Segments = CONTRACT_TERM / 12
Current Segment = OUT_YEAR_SEGMENT_INDEX (from GLOBAL_PLANNING)
Is Final Segment = (Current Segment >= Total Segments) OR (Total Segments == 1)

EDGE CASES:
  - CONTRACT_TERM not divisible by 12 (e.g., 18 months): treat as CEIL(CONTRACT_TERM/12) segments
  - OUT_YEAR_SEGMENT_INDEX is NULL: fall back to single-year assumption
  - No active contract found: flag as data gap, ask user to confirm structure
  - CONTRACT_TERM = 12 or missing: Single-year (1 segment)

CLASSIFICATION:
  Final Segment or Single-year → Renewal is NON-CONTRACTED (quota-bearing)
  Mid-Contract Multi-year → Renewal is CONTRACTED (automatic, non-quota)
```

### 2C. Opportunities — FIVETRAN.SALESFORCE.OPPORTUNITY

```sql
SELECT
    ID, NAME, TYPE, STAGE_NAME, CLOSE_DATE, PROBABILITY,
    FORECAST_CATEGORY_NAME, FORECAST_STATUS_C, AGREEMENT_TYPE_C,
    ACV_C, GROWTH_ACV_C, BASE_RENEWAL_ACV_C, TOTAL_ACV_C,
    FORECAST_ACV_C, OUT_YEAR_PRODUCT_ACV_C, OUT_YEAR_GROWTH_ACV_C,
    OUT_YEAR_SEGMENT_INDEX_C, CAPACITY_C, NEXT_STEPS_C, MANAGER_NOTES_C
FROM FIVETRAN.SALESFORCE.OPPORTUNITY
WHERE ACCOUNT_ID = '{account_id}'
  AND IS_DELETED = FALSE
  AND STAGE_NAME NOT IN ('Closed Lost', 'Rejected')
  AND CLOSE_DATE >= DATEADD('month', -6, CURRENT_DATE())
ORDER BY CLOSE_DATE DESC;
```

### 2D. Account Enrichment — FIVETRAN.SALESFORCE.ACCOUNT

```sql
SELECT
    ACCOUNT_RISK_C, CONSUMPTION_RISK_C, RENEWAL_RISK_C,
    RENEWAL_RISK_DESCRIPTION_C, ACCOUNT_RELATIONSHIP_SCORE_C,
    MATURITY_STAGE_C, MATURITY_SCORE_C,
    ACCOUNT_BASE_RENEWAL_ACV_C, ARR_NUMBER_C, TOTAL_CUSTOMER_SPEND_C,
    CURRENT_CAPACITY_VALUE_C, FORECASTED_LTV_C,
    DAYS_UNTIL_OVERAGE_C, DAYS_TO_CAPACITY_C,
    AE_FIELD_NOTES_C, SALES_DIRECTOR_NOTES_C, ACCOUNT_STRATEGY_C,
    ACCOUNT_COMMENTS_C, CUSTOMER_SUCCESS_NOTES_C,
    AGREEMENT_TYPE_ACCOUNT_C, SNOWFLAKE_AGREEMENT_TYPE_C, MSA_EFFECTIVE_DATE_C
FROM FIVETRAN.SALESFORCE.ACCOUNT
WHERE ID = '{account_id}' AND IS_DELETED = FALSE;
```

### 2E. FY27 Consumption Prediction (supplementary)

```sql
SELECT FY27_CONSUMPTION_PREDICTION
FROM SALES.SALES_BI.GLOBAL_ACCOUNT_DATA
WHERE ACCOUNT_ID = '{account_id}'
LIMIT 1;
```

**IMPORTANT: FY Predictions should have MINIMAL influence on the recommendation.** They are often inaccurate. Always base TACV recommendations primarily on L90D/L30D consumption data and capacity remaining. Use the prediction only as a secondary data point, never as the primary driver.

⚠️ **STOP** — Display the assembled data profile to the user. Ask: *"Here's the data I found for {account_name}. Does this look correct? Should I proceed with the TACV analysis?"*

---

## Step 3: Calculate Derived Metrics

**Goal:** Compute key derived values. All GLOBAL_PLANNING values are in **actual dollars** — do NOT apply any $K multiplier.

```
Acceleration %      = (L30D - L90D) / L90D × 100
Monthly Burn (L90D) = L90D / 12
Monthly Burn (L30D) = L30D / 12
Months to Overage   = Capacity Remaining / Monthly Burn (L90D)
Projected Overage   = Today + Months to Overage

EDGE CASE: If L90D = 0 (new account, no consumption):
  Cannot compute burn rate or overage date. Flag as "Insufficient consumption history."
  Use Prior Renewal Base or FY Prediction as fallback for scenario sizing.

EDGE CASE: If Capacity Remaining is negative (already in overage):
  Months to Overage = 0, Urgency = CRITICAL

Action Urgency:
  < 3 months  → CRITICAL     6-12 months → MEDIUM
  3-6 months  → HIGH         12+ months  → LOW

Contract Structure:
  Total Segments   = CONTRACT_TERM / 12 (or CEIL if not divisible)
  Current Segment  = OUT_YEAR_SEGMENT_INDEX
  Is Final Segment = (Current Segment >= Total Segments) OR (Total Segments == 1)

Overage Interpretation:
  FY26_PREDICTED_OVERAGE > 0  → Account will exceed capacity by this amount
  FY26_PREDICTED_OVERAGE < 0  → Account has SURPLUS capacity (abs value = unused $)
  FY26_PREDICTED_OVERAGE = 0  → Capacity will be roughly exhausted at contract end

Growth Analysis:
  YoY Growth = (FY26 Actuals - FY25 Actuals) / FY25 Actuals × 100
  If L90D < Prior Renewal Base → account is UNDER-CONSUMING vs. contract (flag this)

Confidence Level:
  HIGH   = All Tier 1 + 3+ Tier 2 fields present, L30D/L90D within 30% of each other
  MEDIUM = All Tier 1 present, 1-2 Tier 2 missing, or L30D/L90D diverge >30%
  LOW    = Any Tier 1 field missing/imputed, or major data anomalies
```

---

## Step 4: Evaluate Strategic Options

**Goal:** Before generating scenarios, identify which strategic booking paths are available.

Evaluate these 4 options and flag which are viable:

### Option 1: OVERAGE
Customer exhausts capacity before contract end, creating a booking event.
- Viable if: Months to Overage < Months to Contract End
- Booking: Growth ACV only (no renewal event)
- Quota impact: Non-Contracted Growth (quota-bearing)

### Option 2: PULL-FORWARD
Accelerate a future renewal into the current FY.
- Viable if: Multi-year contract AND **NOT in the final segment**
- **NOT AVAILABLE in the final segment of a multi-year contract**
- **NOT AVAILABLE for single-year contracts**
- Booking: Brings forward next segment's renewal event
- Quota impact: Creates additional Non-Contracted Renewal quota

### Option 3: AMEND
Expand capacity within the current contract term.
- Viable if: Customer consuming faster than contract capacity supports
- Booking: Growth ACV (amendment to existing contract)
- Quota impact: Non-Contracted Growth (quota-bearing)
- Often combined with overage management

### Option 4: EARLY RENEWAL
Renew the contract before its natural end date.
- Viable if: Customer has strong consumption and willingness to commit early
- Booking: Full renewal + growth (new contract replaces current)
- Quota impact: Full TACV becomes quota-bearing
- Best when overage approaching AND strong customer relationship

Present available options with reasoning for viability/non-viability.

---

## Step 5: Generate TACV Scenarios

**Goal:** Produce Conservative, Base, and Stretch TACV recommendations.

### Key Definitions

| Term | Definition |
|------|-----------|
| **Renewal ACV** | = Prior Renewal Base (the amount being renewed) |
| **Growth ACV** | = Total TACV − Prior Renewal Base |
| **Total TACV** | = Renewal ACV + Growth ACV |
| **Contracted Renewal** | Multi-year auto-renewing segment (not final). Non-quota. |
| **Non-Contracted Renewal** | Single-year OR final multi-year segment. Quota-bearing. |
| **Contracted Growth** | Built-in step-ups in multi-year. Non-quota. |
| **Non-Contracted Growth** | Upsells, amendments, expansion. Quota-bearing. |
| **Quota-Bearing TACV** | Non-Contracted Renewal + Non-Contracted Growth |

### Scenario Selection

**CONSERVATIVE** — declining consumption, budget constraints, 12+ months to overage, low data quality, L30D < L90D

**BASE** — stable consumption (acceleration −10% to +15%), standard renewal, solid data quality. **Default recommendation unless clear signals point elsewhere.**

**STRETCH** — strong acceleration (L30D > L90D by 20%+), known expansion, consistent 20%+ YoY growth, approaching capacity exhaustion

### Scenario Sizing

**CRITICAL: Base all sizing on L90D and L30D consumption data, NOT FY Predictions.**

```
CONSERVATIVE:
  Total TACV = L90D annualized (or lower if declining — use L30D if L30D < L90D)

BASE:
  Total TACV = L90D + acceleration buffer
    Acceleration > 0: add 10-20% of the L30D-L90D delta
    Acceleration flat: use L90D as-is
    Acceleration slightly negative: weighted avg (70% L90D + 30% L30D)

STRETCH:
  Total TACV = L30D annualized (or higher if strong sustained growth)
  Account for continued acceleration using YoY growth trends

ALL SCENARIOS:
  Renewal ACV = Prior Renewal Base
  Growth ACV = Total TACV − Renewal ACV (may be negative = downsell)
```

### Quota Classification (apply to each scenario)

```
If Single-year OR Final Segment:
  Contracted Renewal     = $0
  Non-Contracted Renewal = Renewal ACV        ← QUOTA-BEARING
  Contracted Growth      = $0
  Non-Contracted Growth  = Growth ACV         ← QUOTA-BEARING
  Quota-Bearing TACV     = Total TACV

If Mid-Contract Multi-year (not final):
  Contracted Renewal     = Renewal ACV        ← automatic, non-quota
  Non-Contracted Renewal = $0
  Contracted Growth      = built-in step-ups  ← non-quota
  Non-Contracted Growth  = Growth ACV − Contracted Growth ← QUOTA-BEARING
  Quota-Bearing TACV     = Non-Contracted Growth only
```

---

## Step 6: Validate Against Guardrails

| Guardrail | Rule | Negotiable? | Approval Required |
|-----------|------|-------------|-------------------|
| Max BCR | Account TACV ≤ 25% of Territory Target | ❌ No | GVP + SVP |
| Minimum TACV | ≥ $1M when assigning renewal quota | ✅ Yes | RVP + Field Ops |
| Consumption Floor | TACV ≥ Prior FY Consumption (Expansion only) | ✅ Yes | RVP + Field Ops |
| Churn Concentration | Declining accounts ≤ 10% of territory | ✅ Yes | RVP + Field Ops |
| Growth Reasonability | Flag if growth > 100% over prior base | ✅ Yes | Info only |

`IS_CONSECUTIVE_DOWNSELL = 1` → flag for churn concentration.
`ACCOUNT_CATEGORY = "Customer"` → Expansion. `"Prospect"` → Acquisition.
BCR = (Recommended TACV / Territory Target) × 100 — only if user provides target.

---

## Step 7: Cross-Validate with Opportunities

Compare recommendation against SFDC pipeline:
- Recommended TACV vs. opportunity `FORECAST_ACV_C` — explain significant gaps
- `OUT_YEAR_SEGMENT_INDEX_C` confirms segment position
- Opportunity `BASE_RENEWAL_ACV_C` vs. `PRIOR_RENEWAL_BASE` from GLOBAL_PLANNING
- Flag if `GROWTH_ACV_C` implies expansion the consumption data doesn't support
- "Commit" or "Closed Won" stage → recommendation should closely align

---

## Step 8: Present Results

### Account Summary
Account name, segment, owner, contract end date. Contract structure (segment X of Y). Capacity remaining + months to overage. L90D/L30D rates, acceleration %. Confidence level with justification.

### Data Flags
Anomalies: under-consumption, negative overage (surplus), L30D/L90D divergence >30%, missing fields. Risk indicators from SFDC.

### Renewal Events
Timeline of bookable events in the planning FY. Each: type, timing, bookability (quota-bearing vs contracted), conditions.

### Strategic Options
Which of 4 options are viable and why. Explicitly state if Pull-Forward is blocked (final segment or single-year).

### Scenarios Table

| | Conservative | Base | Stretch |
|---|---|---|---|
| Total TACV | $ | $ | $ |
| Renewal ACV | $ | $ | $ |
| Growth ACV | $ | $ | $ |
| Contracted | $ | $ | $ |
| Non-Contracted (Quota-Bearing) | $ | $ | $ |
| Confidence | HIGH/MED/LOW | | |

### Recommendation
Which scenario and why. Full TACV breakdown. Quota-bearing amount. Key assumptions with data sources. Primary driver: L90D, L30D, or blended — never FY Prediction alone.

### Guardrail Results
Pass/fail per guardrail. Required approvers if any fail.

### Validation Needed
Priority items for Field Ops/AE to verify, ordered by impact.

### Consistency Check
Does recommendation align with data flags? Does scenario match urgency? Does quota classification match contract structure?

⚠️ **STOP** — Ask: *"Would you like me to adjust assumptions, run a different scenario, or look up additional accounts?"*

---

## Data Source Reference

| Source | Table | Units | Join Key |
|--------|-------|-------|----------|
| Primary | `SALES.PLANNING.GLOBAL_PLANNING` | Actual $ | ACCOUNT_ID |
| Contract | `FIVETRAN.SALESFORCE.CONTRACT` | — | ACCOUNT_ID |
| Opportunity | `FIVETRAN.SALESFORCE.OPPORTUNITY` | Actual $ | ACCOUNT_ID |
| Account | `FIVETRAN.SALESFORCE.ACCOUNT` | Actual $ | ID |
| Prediction | `SALES.SALES_BI.GLOBAL_ACCOUNT_DATA` | Actual $ | ACCOUNT_ID |

### Critical Rules
- **GLOBAL_PLANNING** = actual dollars. Do NOT multiply by 1,000.
- **L90D and L30D** are already annualized. Do NOT multiply by 12.
- **FY Predictions** = MINIMAL influence. Base scenarios on L90D/L30D.
- **Negative overage** = capacity SURPLUS, not deficit.
- **Pull-Forward NOT available** in final segment or single-year contracts.

---

## Common Patterns

**Ample capacity, no urgency** — Months > 12, no overage. BASE at L90D. Low urgency.

**Fast burn** — Months < 6, positive acceleration. Evaluate Amend/Early Renewal. BASE or STRETCH.

**Declining / downsell** — `IS_CONSECUTIVE_DOWNSELL = 1`, L30D < L90D. CONSERVATIVE. Flag churn guardrail.

**Mid-contract multi-year** — Most TACV contracted/automatic. Only upsells quota-bearing. Pull-Forward available.

**Final segment multi-year** — ALL renewal non-contracted (quota-bearing). Pull-Forward NOT available. Full TACV quota-bearing.

**New/early account** — Near-zero FY25, ramping FY26. L90D may understate. Weight L30D more. Consider STRETCH if acceleration > 30%.
