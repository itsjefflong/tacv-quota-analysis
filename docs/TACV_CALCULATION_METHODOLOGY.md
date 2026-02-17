# TACV Calculation Methodology Document

**Prepared for:** Finance Data Science Team  
**Version:** 1.1  
**Last Updated:** December 10, 2024  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core Definitions](#2-core-definitions)
3. [Input Data Fields](#3-input-data-fields)
4. [Calculation Formulas](#4-calculation-formulas)
5. [Data Quality Validation](#5-data-quality-validation)
6. [TACV Component Calculations](#6-tacv-component-calculations)
7. [Scenario Modeling Methodology](#7-scenario-modeling-methodology)
8. [Contracted vs Non-Contracted Classification](#8-contracted-vs-non-contracted-classification)
9. [Example Calculations](#9-example-calculations)
10. [Data Trust Hierarchy](#10-data-trust-hierarchy)
11. [Appendix: Technical Implementation Details](#appendix-technical-implementation-details)

---

## 1. Executive Summary

This document outlines the calculation methodology used by the TACV (Total Annual Contract Value) Quota Scenario Modeling system to generate quota recommendations for Snowflake customer accounts. The system analyzes consumption patterns, contract structures, and capacity data to produce Renewal ACV, Growth ACV, and Total TACV recommendations across three planning scenarios (Conservative, Base, Stretch).

### Key Methodology Principles

1. **Consumption-Based Sizing**: TACV recommendations are primarily derived from actual consumption data (L90D/L30D burn rates), not predictions
2. **Mathematical Renewal/Growth Split**: Renewal vs Growth ACV is a deterministic calculation, not a qualitative assessment
3. **Multi-Scenario Planning**: Three scenarios provide a range for quota planning flexibility
4. **Bookability Classification**: Clear rules determine which TACV is quota-bearing (bookable) vs non-quota

---

## 2. Core Definitions

### 2.1 TACV Components

| Term | Definition | Formula |
|------|------------|---------|
| **Total TACV** | Total Annual Contract Value - the full value of the contract for a fiscal year | `Renewal ACV + Growth ACV` |
| **Renewal ACV** | The value carried forward from the prior contract (prior renewal base amount) | `= Prior Renewal Base` |
| **Growth ACV** | Any increase in contract value over the prior renewal base | `= New Contract Value - Prior Renewal Base` |
| **Prior Renewal Base** | The annual contract value from the previous contract term | Sourced from contract data |

### 2.2 Fiscal Year Definitions

Snowflake fiscal year runs **February 1 through January 31**:

| Period | Date Range |
|--------|------------|
| Fiscal Year (FY27) | Feb 1, 2026 – Jan 31, 2027 |
| 1H | Feb 1 – Jul 31 |
| 2H | Aug 1 – Jan 31 |

### 2.3 Contract Classifications

| Classification | Definition |
|----------------|------------|
| **Single-Year** | One-year contract term; renewal requires new sales execution |
| **Multi-Year** | Multi-year contract (typically 3 years) with annual segments |
| **Contracted** | Already in signed contract; 100% certain to book |
| **Non-Contracted** | Pipeline/forecast opportunities; probability-weighted |

---

## 3. Input Data Fields

### 3.1 Tier 1 Fields (Required)

| Field | Description | Data Type | Validation |
|-------|-------------|-----------|------------|
| `account_name` | Customer identifier | String | Non-empty |
| `contract_end_date` | When current contract expires | Date | Valid date format |
| `capacity_remaining` | Dollar amount remaining in contract | Currency ($) | Positive number |
| `l90d_burn_rate` | **Annualized** consumption based on last 90 days | Currency ($/year) | Positive number |
| `prior_renewal_base` | Previous annual contract value | Currency ($) | Positive number |
| `contract_structure` | Single-year or Multi-year | Enum | Required selection |

> **⚠️ IMPORTANT**: The `l90d_burn_rate` and `l30d_burn_rate` fields from Pigment are labeled "Annualized Run Rate" - they are **already annualized values**, not monthly consumption. Do not multiply by 12.

### 3.2 Tier 2 Fields (Recommended)

| Field | Description | Fallback If Missing |
|-------|-------------|---------------------|
| `l30d_burn_rate` | **Annualized** consumption based on last 30 days | Uses L90D (assumes no acceleration) |
| `planning_fy_prediction` | Predicted consumption for planning FY | Falls back to L90D (already annualized) |
| `prior_fy_prediction` | Predicted consumption in prior FY (useful before actuals available) | Falls back to L90D if not available |
| `contract_predicted_overage` | Calculated overage amount | Calculated from `capacity ÷ burn rate` |
| `prior_fy_actuals` | Actual consumption in prior FY | Weakens multi-year validation |
| `prior_fy_minus_1_actuals` | Actual consumption two FYs ago | Weakens multi-year validation |
| `account_segment` | Enterprise, Majors, Commercial, etc. | Defaults to conservative growth assumptions |
| `account_owner` | AE or account executive name | Display only |

---

## 4. Calculation Formulas

### 4.1 Understanding L90D/L30D Values from Pigment

> **⚠️ CRITICAL**: The L90D and L30D values from Pigment's "Annualized Run Rate (L90D/L30D)" columns are **ALREADY ANNUALIZED**. They represent the annual consumption rate projected from the last 90/30 days of actual consumption.

**What Pigment Provides:**
- `Annualized Run Rate (L90D)` = Annual consumption rate based on last 90 days
- `Annualized Run Rate (L30D)` = Annual consumption rate based on last 30 days

**Do NOT re-annualize these values.** They are already annual rates.

**To derive monthly burn from annual values:**
```
Monthly L90D Burn = L90D Annual Rate ÷ 12
Monthly L30D Burn = L30D Annual Rate ÷ 12
```

**Example:**
- L90D Annual Rate (from Pigment): $27.1M/year
- L90D Monthly Burn: $27.1M ÷ 12 = **$2.26M/month**

### 4.2 Acceleration Calculation

```
Acceleration % = (L30D Annual - L90D Annual) / L90D Annual × 100
```

**Interpretation:**
- Acceleration > 0%: Consumption is increasing (recent burn exceeds medium-term trend)
- Acceleration > +20%: Significant acceleration; factor into upside scenarios
- Acceleration < 0%: Consumption is declining

**Example:**
- L30D Annual Rate: $35.1M
- L90D Annual Rate: $27.1M
- Acceleration: ($35.1M - $27.1M) / $27.1M = **+29.5%**

### 4.3 Months to Overage Calculation

```
Months to Overage = Capacity Remaining / Monthly Burn Rate
                  = Capacity Remaining / (L90D Annual ÷ 12)
```

Calculate using both L90D and L30D burn rates for range:

```
Months to Overage (L90D) = Capacity Remaining / (L90D Annual ÷ 12)
Months to Overage (L30D) = Capacity Remaining / (L30D Annual ÷ 12)
```

**Example:**
- Capacity Remaining: $17.6M
- L90D Annual Rate: $27.1M → Monthly: $27.1M ÷ 12 = $2.26M/month
- L30D Annual Rate: $35.1M → Monthly: $35.1M ÷ 12 = $2.93M/month
- Months to Overage (L90D): $17.6M / $2.26M = **7.8 months**
- Months to Overage (L30D): $17.6M / $2.93M = **6.0 months**

### 4.4 Predicted Overage Calculation

```
Predicted Overage = FY Consumption Prediction - Capacity Remaining
```

**Example:**
- FY Prediction: $63.4M
- Capacity Remaining: $17.6M
- Predicted Overage: $63.4M - $17.6M = **$45.8M**

---

## 5. Data Quality Validation

Before analysis, the system performs four validation checks:

### 5.1 Overage Magnitude Check

```
Overage_Ratio = Contract Predicted Overage / FY Consumption Prediction
```

| Condition | Interpretation | Action |
|-----------|----------------|--------|
| < 5% | Overage field likely incorrect | Calculate manually from consumption |
| 5% – 200% | Normal range | Use provided value |
| > 200% | May indicate multi-year effects | Flag for review |

### 5.2 Multi-Year Contract Detection

```
Total_3Yr = FY-2 Actuals + FY-1 Actuals + FY Prediction
Multiple = Total_3Yr / (Prior Renewal Base × 3)
```

| Condition | Interpretation |
|-----------|----------------|
| Multiple > 1.5 | Likely multi-year contract |
| Overage > 2× Prior Renewal | Large overage suggests multi-year pool |

### 5.3 Capacity Timeline Check

```
Months_To_Overage = Capacity Remaining / Monthly Burn (L90D)
```

| Condition | Flag |
|-----------|------|
| < 6 months AND Overage < Prior Renewal | Numbers don't add up; investigate |

### 5.4 Acceleration Check

```
Acceleration = (L30D - L90D) / L90D
```

| Condition | Action |
|-----------|--------|
| > +20% | Recent acceleration detected; factor into Stretch scenario |
| < -20% | Deceleration detected; factor into Conservative scenario |

---

## 6. TACV Component Calculations

### 6.1 Core TACV Formula

```
Total TACV = Renewal ACV + Growth ACV
```

Where:
```
Renewal ACV = Prior Renewal Base
Growth ACV = New Contract Value - Prior Renewal Base
```

**This is a MATHEMATICAL split, not based on workload type or customer intent.**

### 6.2 TACV Calculation Examples

| Scenario | Prior Renewal Base | New Contract Value | Renewal ACV | Growth ACV | Total TACV |
|----------|-------------------|-------------------|-------------|------------|------------|
| Growth | $15M | $65M | $15M | $50M | $65M |
| Flat | $30M | $30M | $30M | $0M | $30M |
| Moderate Growth | $20M | $45M | $20M | $25M | $45M |
| Decline | $25M | $20M | $20M | $0M | $20M |

### 6.3 Bookability Rules

| Event Type | Bookable? | TACV Treatment |
|------------|-----------|----------------|
| Overages | ✅ YES | Bookable TACV |
| Renewals | ✅ YES | Bookable TACV |
| Amendments | ✅ YES | Bookable TACV |
| Early Renewals | ✅ YES | Split into Renewal + Growth per formula |
| Pull-Forward | ❌ NO | NOT bookable (re-timing existing capacity); always categorized as Renewal ACV |

### 6.4 Pull-Forward Special Case

Pull-forwards have specific treatment:
- **Always classified as Renewal ACV** (re-timing existing capacity, not new money)
- **Not bookable TACV** (not new revenue)
- If pull-forward amount exceeds prior renewal, excess is **still Renewal ACV** (not Growth)

---

## 7. Scenario Modeling Methodology

### 7.1 Three-Scenario Framework

| Scenario | Purpose | Confidence |
|----------|---------|------------|
| **Conservative** | Floor/minimum commitment - what we're almost certain to achieve | HIGH |
| **Base** | Standard planning target - recommended for quota setting | MEDIUM-HIGH |
| **Stretch** | Upside/aggressive target - requires favorable conditions | MEDIUM |

### 7.2 Scenario Selection Criteria

#### Recommend CONSERVATIVE when:
- Data quality is LOW and consumption trajectory is uncertain
- Account shows DECLINING consumption (L30D < L90D, negative acceleration)
- Customer has known budget constraints or is downsizing
- Contract end is far out (12+ months) with ample capacity remaining
- Historical pattern shows flat or declining YoY consumption

#### Recommend BASE when:
- Data is solid (MEDIUM or higher confidence) with stable consumption patterns
- L90D and L30D are similar (acceleration between -10% and +15%)
- Consumption aligns reasonably with FY prediction
- Standard renewal cycle with predictable, modest growth expected

#### Recommend STRETCH when:
- Strong acceleration detected (L30D significantly > L90D, e.g., +20% or more)
- FY prediction significantly exceeds L90D extrapolation
- Account has known expansion signals (new products, use case expansion)
- Historical pattern shows consistent YoY consumption growth (e.g., 20%+ annually)
- Customer is in growth phase with capacity running out before contract end

### 7.3 TACV Sizing Methodology

The recommended TACV is derived from consumption data with situational buffers:

```
Base TACV = L90D Annualized
Buffer = Based on acceleration, risk factors, and account trajectory
Recommended TACV = Base TACV × (1 + Buffer)
```

**Buffer Approach:**

Buffers are determined dynamically based on account-specific factors rather than fixed ranges. The AI analyst considers:

| Factor | Buffer Impact |
|--------|---------------|
| Acceleration trend (L30D vs L90D) | Higher acceleration → larger buffer |
| FY prediction alignment | If prediction supports higher consumption → larger buffer |
| Capacity runway | Shorter runway → size for immediate needs |
| Historical consumption patterns | Consistent growth → buffer for continuation |
| Customer expansion signals | Known expansion → larger buffer |

**Example:** An account with +29% acceleration (L30D vs L90D) might warrant an 85% buffer on Base scenario to account for the sustained growth trajectory, rather than a fixed 10-30% buffer.

> **Note:** The system provides transparency on buffer calculations in the `tacv_derivation` section of each analysis, showing the Base Amount Source, Buffer Applied, and Total Recommended with full math.

---

## 8. Contracted vs Non-Contracted Classification

### 8.1 Renewal ACV Classification

| Contract Type | Classification | Quota-Bearing? |
|--------------|----------------|----------------|
| Multi-year, NOT final segment (e.g., Year 1 of 3, Year 2 of 3) | **Contracted Renewal** | ❌ NO |
| Single-year OR final multi-year segment (e.g., Year 3 of 3) | **Non-Contracted Renewal** | ✅ YES |

### 8.2 Growth ACV Classification

| Contract Type | Classification | Quota-Bearing? |
|--------------|----------------|----------------|
| Built-in step-ups in multi-year (e.g., Year 1: $100K → Year 2: $120K) | **Contracted Growth** | ❌ NO |
| Upsells, amendments, co-terms, expansion deals | **Non-Contracted Growth** | ✅ YES |

### 8.3 Quota Implications Formula

```
Quota-Bearing TACV = Non-Contracted Renewal + Non-Contracted Growth
Non-Quota TACV = Contracted Renewal + Contracted Growth
```

### 8.4 Classification Decision Tree

```
Is contract Multi-year?
├── YES → Is this the final segment (e.g., Year 3 of 3)?
│   ├── YES → Renewal = Non-Contracted, Growth = Non-Contracted (QUOTA-BEARING)
│   └── NO → Renewal = Contracted (NON-QUOTA)
│            → Check for step-ups → Contracted Growth (NON-QUOTA)
│            → Any additional growth → Non-Contracted Growth (QUOTA-BEARING)
└── NO (Single-year) → All Renewal = Non-Contracted (QUOTA-BEARING)
                     → All Growth = Non-Contracted (QUOTA-BEARING)
```

---

## 9. Example Calculations

### 9.1 Complete Calculation Example

**Input Data (from Pigment):**
| Field | Pigment Column | Value |
|-------|----------------|-------|
| Account Name | Ult-Parent Name | ACME Corp |
| Contract End Date | Contract End Date | January 15, 2027 |
| Capacity Remaining | Capacity Usage Remaining ($K) | $17.6M |
| L90D Annual Rate | Annualized Run Rate (L90D) ($K) | $27.1M ← *already annualized* |
| L30D Annual Rate | Annualized Run Rate (L30D) ($K) | $35.1M ← *already annualized* |
| Prior Renewal Base | Prior Renewal Base ($K) | $15.0M |
| FY27 Prediction | FY27 Consumption Prediction ($K) | $63.4M |
| Contract Structure | (user selected) | Multi-year (Year 3 of 3) |

> **Note**: L90D and L30D values from Pigment are labeled "Annualized Run Rate" - they are **already annual values**, not monthly. Do not multiply by 12.

**Step 1: Derive Monthly Burn (for capacity calculations)**
```
L90D Monthly Burn = L90D Annual ÷ 12 = $27.1M ÷ 12 = $2.26M/month
L30D Monthly Burn = L30D Annual ÷ 12 = $35.1M ÷ 12 = $2.93M/month
```

**Step 2: Calculate Acceleration**
```
Acceleration = (L30D Annual - L90D Annual) / L90D Annual
             = ($35.1M - $27.1M) / $27.1M = +29.5%
```

**Step 3: Calculate Months to Overage**
```
Months to Overage (L90D) = Capacity / Monthly L90D = $17.6M / $2.26M = 7.8 months
Months to Overage (L30D) = Capacity / Monthly L30D = $17.6M / $2.93M = 6.0 months
```

**Step 4: Scenario TACV Calculation**

*Conservative Scenario:*
```
Total TACV = $30.0M (overage + standard renewal)
Renewal ACV = $15.0M (Prior Renewal Base)
Growth ACV = $30.0M - $15.0M = $15.0M
```

*Base Scenario (Recommended):*
```
Base Amount = L90D Annualized = $27.1M
Buffer = +85% (accounting for +29% acceleration)
Total TACV = $50.0M
Renewal ACV = $15.0M (Prior Renewal Base)
Growth ACV = $50.0M - $15.0M = $35.0M
```

*Stretch Scenario:*
```
Total TACV = $60.0M (aligned with FY prediction)
Renewal ACV = $15.0M (Prior Renewal Base)
Growth ACV = $60.0M - $15.0M = $45.0M
```

**Step 5: Classification (Year 3 of 3 = Final Segment)**
```
Contract Type: Multi-year, Final Segment
All Renewal = Non-Contracted (Quota-Bearing)
All Growth = Non-Contracted (Quota-Bearing)
Quota-Bearing TACV = $50.0M (100% of recommended TACV)
```

---

## 10. Data Trust Hierarchy

When data conflicts exist, trust data sources in this order:

| Priority | Data Source | Trust Level |
|----------|-------------|-------------|
| 1 | Contract dates, historical actuals | **Trust First** |
| 2 | L90D/L30D run rates | **Trust First** |
| 3 | Prior Renewal Base, Base ACV | **Generally Reliable** |
| 4 | FY Prediction | **Generally Reliable** (but validate) |
| 5 | Predicted overage amounts | **Verify First** |
| 6 | Capacity remaining | **Verify First** |

### Important Guidance on FY Predictions

FY Prediction values come from data science models and should be treated with **CAUTION**:
- These predictions can be inaccurate
- Should have **minimal influence** on TACV recommendations
- Base recommendations primarily on **actual consumption data** (L90D, L30D)
- Only reference FY Prediction as a **directional signal**, not as a sizing target
- When FY Prediction conflicts with L90D/L30D data, **trust the actual consumption data**

---

## Appendix: Technical Implementation Details

### A.1 Currency Normalization

The system handles multiple currency formats:
- `$18,000,000` → $18,000,000
- `$18M` → $18,000,000
- `18000000` → $18,000,000
- `$18.5M` → $18,500,000
- `($K)` suffix indicates thousands multiplier

### A.2 Date Normalization

Supported date formats:
- `1/15/2027` → 2027-01-15
- `2027-01-15` → 2027-01-15
- `Jan 15, 2027` → 2027-01-15
- `January 15, 2027` → 2027-01-15

### A.3 Column Name Mapping

| Input Variations | Maps To |
|-----------------|---------|
| L90D, 90D Burn, L90D Burn Rate, Last 90 Day, Trailing 91D | `l90d_burn_rate` |
| L30D, 30D Burn, L30D Burn Rate, Last 30 Day | `l30d_burn_rate` |
| Contract End, Contract End Date, End Date | `contract_end_date` |
| Capacity Remaining, Remaining Capacity, Capacity Left | `capacity_remaining` |
| FY27 Prediction, FY27 Forecast, FY27 Consumption Prediction | `planning_fy_prediction` |
| FY26 Prediction, FY26 Consumption Prediction | `prior_fy_prediction` |
| Prior Renewal Base, Renewal Base, Prior Base, Base ACV | `prior_renewal_base` |
| Account ID, Ult-Parent ID | `account_id` |
| Owner Name, Account Owner, AE, Account Executive | `account_owner` |

### A.4 Confidence Level Definitions

| Level | Description | Recommendation |
|-------|-------------|----------------|
| **HIGH** | Strong, complete data; clear patterns; recommendation well-supported | Use directly for quota |
| **MEDIUM-HIGH** | Good data with minor gaps; solid recommendation | Use with minor validation |
| **MEDIUM** | Some data issues or missing fields; recommendation reasonable | Validate before quota use |
| **LOW** | Significant data gaps or inconsistencies; best guess | Requires full validation |

---

## Document Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Finance Data Science | | | |
| Field Operations | | | |
| Product/Engineering | | | |

---

*For questions about this methodology, contact the Field Operations Tools team.*

