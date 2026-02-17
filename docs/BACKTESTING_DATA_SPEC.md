# Backtesting Data Specification

**Purpose:** This document describes the data columns required to backtest the TACV Quota Scenario Modeling application.

**Companion File:** `backtesting_template.csv`

---

## Quick Start

1. Populate `backtesting_template.csv` with historical account data
2. Ensure you have at least the **Required Input Columns** filled
3. Include **Actual Outcome Columns** to measure model accuracy
4. Run historical data through the model and compare predictions vs actuals

---

## Column Definitions

### Identifiers & Context

| Column | Required | Data Type | Description | Example |
|--------|----------|-----------|-------------|---------|
| `account_id` | ✅ Yes | String | Unique account identifier (Ult-Parent ID) | `001ABC001` |
| `account_name` | ✅ Yes | String | Customer name (Ult-Parent Name) | `ACME Corporation` |
| `planning_fy` | ✅ Yes | String | Fiscal year being predicted | `FY26` |
| `prediction_date` | ✅ Yes | Date | When the prediction was/would be made (point-in-time) | `2024-10-15` |

---

### Required Input Columns (Tier 1)

These are **mandatory** for the model to generate predictions.

| Column | Data Type | Description | Notes |
|--------|-----------|-------------|-------|
| `contract_end_date` | Date (YYYY-MM-DD) | When the contract expires/expired | Use actual contract end date |
| `capacity_remaining` | Currency ($) | Dollar amount remaining in contract at prediction_date | Whole dollars, no commas |
| `l90d_burn_rate` | Currency ($/year) | **ANNUALIZED** consumption rate based on last 90 days | ⚠️ Already annualized - do NOT multiply by 12 |
| `prior_renewal_base` | Currency ($) | Previous annual contract value | The base ACV from prior contract |
| `contract_structure` | Enum | Contract term type | `Single-year` or `Multi-year` |

**⚠️ CRITICAL:** The `l90d_burn_rate` and `l30d_burn_rate` values from Pigment are labeled "Annualized Run Rate" - they are **already annualized values**. Do NOT multiply by 12.

---

### Recommended Input Columns (Tier 2)

These **improve model accuracy** and enable testing of enhancement scenarios.

| Column | Data Type | Description | Fallback if Missing |
|--------|-----------|-------------|---------------------|
| `l30d_burn_rate` | Currency ($/year) | **ANNUALIZED** consumption rate based on last 30 days | Model uses L90D (assumes no acceleration) |
| `contract_year_position` | String | For multi-year contracts, which year | `Year 1 of 3`, `Year 2 of 3`, `Year 3 of 3` |
| `planning_fy_prediction` | Currency ($) | DS model's FY consumption prediction | Falls back to L90D |
| `prior_fy_actuals` | Currency ($) | Actual consumption from prior FY | Weakens multi-year validation |
| `prior_fy_minus_1_actuals` | Currency ($) | Actual consumption from FY-2 | Weakens multi-year validation |
| `account_segment` | String | Customer segment | `Enterprise`, `Majors`, `Commercial`, `Select` |
| `account_owner` | String | Account executive name | Display only |
| `is_consecutive_downsell` | Boolean | Had 2+ consecutive renewal downsells | `TRUE` or `FALSE` |

---

### Actual Outcome Columns (Ground Truth)

These are the **actual results** used to measure model accuracy.

| Column | Data Type | Description | How It's Used |
|--------|-----------|-------------|---------------|
| `actual_total_tacv` | Currency ($) | Total TACV that was actually booked | Compare to model's scenario predictions |
| `actual_renewal_acv` | Currency ($) | Renewal ACV component of actual deal | Validate Renewal/Growth split logic |
| `actual_growth_acv` | Currency ($) | Growth ACV component of actual deal | Validate growth predictions |
| `actual_consumption_fy` | Currency ($) | Actual consumption during the FY | Validate consumption predictions |
| `actual_renewal_date` | Date | When renewal actually occurred | Validate timing predictions |
| `renewal_type` | String | What type of deal occurred | See values below |
| `was_bookable` | Boolean | Was this TACV quota-bearing? | Validate bookability logic |
| `actual_scenario_outcome` | Enum | Which model scenario was closest | `Conservative`, `Base`, `Stretch`, or `N/A` |

**`renewal_type` values:**
- `Renewal` - Standard contract renewal
- `Early Renewal` - Renewal executed before contract end
- `Amendment` - Contract amendment/upsell
- `Pull Forward (Not Bookable)` - Re-timing of existing capacity (not quota-bearing)
- `Churn` - Customer did not renew

---

## Data Quality Guidelines

### Currency Values
- Use whole dollars (no cents): `17600000` not `17,600,000.00`
- Do not include currency symbols: `17600000` not `$17,600,000`
- Use positive values for all amounts

### Dates
- Use ISO format: `YYYY-MM-DD`
- Example: `2025-01-15`

### Fiscal Year Alignment
- Snowflake FY runs **February 1 through January 31**
- FY26 = Feb 1, 2025 – Jan 31, 2026
- FY27 = Feb 1, 2026 – Jan 31, 2027

### Point-in-Time Data
For valid backtesting, use the data that **was available at `prediction_date`**, not current values. This means:
- `capacity_remaining` should reflect the balance as of `prediction_date`
- `l90d_burn_rate` should be calculated from the 90 days prior to `prediction_date`
- `l30d_burn_rate` should be calculated from the 30 days prior to `prediction_date`

---

## Sample Validation Metrics

Once you run predictions and compare to actuals, compute these metrics:

| Metric | Formula | Target |
|--------|---------|--------|
| **TACV Accuracy** | `1 - ABS(predicted_tacv - actual_tacv) / actual_tacv` | >80% |
| **Scenario Hit Rate** | Percentage where recommended scenario was closest to actual | >60% |
| **Directional Accuracy** | Whether growth/decline direction was predicted correctly | >85% |
| **MAPE** | `AVG(ABS(predicted - actual) / actual) × 100` | <25% |
| **Renewal/Growth Split Accuracy** | Compare predicted vs actual ACV split ratios | Within 10% |

---

## Model Outputs to Capture

When running historical data through the model, capture these outputs for comparison:

```
predicted_scenario          # Conservative, Base, or Stretch
conservative_tacv           # Conservative scenario total TACV
base_tacv                   # Base scenario total TACV  
stretch_tacv                # Stretch scenario total TACV
conservative_renewal_acv    # Renewal component - Conservative
conservative_growth_acv     # Growth component - Conservative
base_renewal_acv            # Renewal component - Base
base_growth_acv             # Growth component - Base
stretch_renewal_acv         # Renewal component - Stretch
stretch_growth_acv          # Growth component - Stretch
confidence_level            # HIGH, MEDIUM-HIGH, MEDIUM, LOW
recommended_option          # Renewal Only, Amendment, Early Renewal, etc.
```

---

## Questions?

Contact the Field Operations Tools team for clarification on data definitions or model behavior.

