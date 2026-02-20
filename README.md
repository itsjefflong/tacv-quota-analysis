# TACV Quota Scenario Modeling Skill

A Cortex Code skill that generates data-driven TACV (Total Annual Contract Value) quota recommendations for Snowflake customer accounts.

## What It Does

Given an account name or Salesforce Account ID, this skill:

1. **Pulls data** from 5 Snowflake/Salesforce sources (consumption, capacity, contracts, opportunities, account enrichment)
2. **Determines contract structure** (single-year vs multi-year, current segment position)
3. **Calculates derived metrics** (acceleration, months to overage, urgency, confidence)
4. **Evaluates strategic options** (Overage, Pull-Forward, Amend, Early Renewal)
5. **Generates 3 TACV scenarios** (Conservative / Base / Stretch) with full quota-bearing classification
6. **Validates against guardrails** (BCR, minimum TACV, consumption floor, churn concentration)
7. **Cross-validates** against existing SFDC pipeline opportunities

## Installation

### Prerequisites

- Snowflake Cortex Code access
- Read access to the following tables:
  - `SALES.PLANNING.GLOBAL_PLANNING`
  - `FIVETRAN.SALESFORCE.CONTRACT`
  - `FIVETRAN.SALESFORCE.OPPORTUNITY`
  - `FIVETRAN.SALESFORCE.ACCOUNT`
  - `SALES.SALES_BI.GLOBAL_ACCOUNT_DATA`

### Step 1: Download the Skill

1. Go to: [`https://github.com/itsjefflong/tacv-quota-analysis`](https://github.com/itsjefflong/tacv-quota-analysis)
2. Click the green **Code** button
3. Select **Download ZIP**
4. Extract the ZIP file

You should see this structure after extraction:

```
tacv-quota-analysis/
├── skill.yaml      # Skill manifest (triggers, data sources, metadata)
├── prompt.md       # Main skill instructions (8-step workflow)
└── README.md       # This file
```

### Step 2: Install to Cortex Code

Move the extracted folder to your Cortex skills directory.

**macOS / Linux:**

```bash
mkdir -p ~/.cortex/skills
mv ~/Downloads/tacv-quota-analysis ~/.cortex/skills/
ls ~/.cortex/skills/tacv-quota-analysis/
```

**Windows:**

```powershell
mkdir %USERPROFILE%\.cortex\skills
move %USERPROFILE%\Downloads\tacv-quota-analysis %USERPROFILE%\.cortex\skills\
dir %USERPROFILE%\.cortex\skills\tacv-quota-analysis\
```

> **Note:** If your Cortex Code installation uses a custom skills directory, replace the path above with your configured location. Check your Cortex Code settings or ask your admin.

### Step 3: Verify Installation

1. Restart Cortex Code or open a new chat session
2. Test by asking: *"Run a TACV analysis for [any account name]"*
3. If the skill activates and begins searching `SALES.PLANNING.GLOBAL_PLANNING`, you're good

### Step 4: Verify Data Access

If the skill activates but queries fail, check your Snowflake role has SELECT access:

```sql
SELECT COUNT(*) FROM SALES.PLANNING.GLOBAL_PLANNING WHERE SNAPSHOT_DATE = CURRENT_DATE();
SELECT COUNT(*) FROM FIVETRAN.SALESFORCE.CONTRACT WHERE IS_DELETED = FALSE;
SELECT COUNT(*) FROM FIVETRAN.SALESFORCE.OPPORTUNITY WHERE IS_DELETED = FALSE;
SELECT COUNT(*) FROM FIVETRAN.SALESFORCE.ACCOUNT WHERE IS_DELETED = FALSE;
SELECT COUNT(*) FROM SALES.SALES_BI.GLOBAL_ACCOUNT_DATA;
```

If any query returns a permission error, contact your Snowflake admin for the appropriate role grants.

## How to Use

Ask Cortex Code any of these:

- *"Run a TACV analysis for Gigapower, LLC"*
- *"What should the quota be for account 001Do00000LZFsgIAH?"*
- *"Analyze the renewal for [account name]"*
- *"What's the burn rate and capacity remaining for [account]?"*
- *"Is [account] quota-bearing or contracted?"*

The skill walks through each step, pausing for confirmation before proceeding.

## Data Sources

| Source | Table | What It Provides |
|--------|-------|------------------|
| Primary | `SALES.PLANNING.GLOBAL_PLANNING` | Consumption (L90D/L30D), capacity, territory, contract dates |
| Contract | `FIVETRAN.SALESFORCE.CONTRACT` | Contract term, agreement type, segment structure |
| Opportunity | `FIVETRAN.SALESFORCE.OPPORTUNITY` | Pipeline ACV, forecast, stage, growth validation |
| Account | `FIVETRAN.SALESFORCE.ACCOUNT` | Risk scores, strategic notes, maturity, financials |
| Prediction | `SALES.SALES_BI.GLOBAL_ACCOUNT_DATA` | FY27 consumption prediction (supplementary) |

## Key Concepts

### TACV Breakdown

| Term | Definition |
|------|-----------|
| **Renewal ACV** | Prior Renewal Base (what's being renewed) |
| **Growth ACV** | Total TACV − Prior Renewal Base (net new value) |
| **Contracted** | Auto-renewing multi-year segments (non-quota) |
| **Non-Contracted** | Single-year or final segment (quota-bearing — sales must close) |
| **Quota-Bearing TACV** | Non-Contracted Renewal + Non-Contracted Growth |

### Contract Structure

Determined from `CONTRACT_TERM` in SFDC:

| Term (months) | Structure | Total Segments |
|---------------|-----------|----------------|
| 12 | Single-year | 1 |
| 24 | Multi-year | 2 |
| 36 | Multi-year | 3 |

Combined with `OUT_YEAR_SEGMENT_INDEX`, this determines if the account is in its final segment (all TACV quota-bearing) or mid-contract (only growth is quota-bearing).

### Strategic Options

| Option | When Available | Quota Impact |
|--------|---------------|--------------|
| **Overage** | Capacity exhausts before contract end | Growth ACV (quota-bearing) |
| **Pull-Forward** | Multi-year, NOT final segment | Additional renewal quota |
| **Amend** | Customer needs more capacity | Growth ACV (quota-bearing) |
| **Early Renewal** | Strong consumption + relationship | Full TACV (quota-bearing) |

**Pull-Forward is NOT available** for single-year contracts or final segments of multi-year deals.

### Guardrails

| Rule | Threshold | Approval If Failed |
|------|-----------|-------------------|
| Max BCR | ≤ 25% of territory target | GVP + SVP |
| Minimum TACV | ≥ $1M | RVP + Field Ops |
| Consumption Floor | ≥ Prior FY actuals (Expansion) | RVP + Field Ops |
| Churn Concentration | ≤ 10% of territory (declining) | RVP + Field Ops |
| Growth Reasonability | Flag if > 100% growth | Info only |

## Critical Data Rules

| Rule | Why It Matters |
|------|---------------|
| GLOBAL_PLANNING values are **actual dollars** | Don't multiply by 1,000 — that's for Pigment $K exports |
| L90D and L30D are **already annualized** | Don't multiply by 12 — they represent full-year run rates |
| FY Predictions have **minimal influence** | Scenarios are based on L90D/L30D consumption, not predictions |
| Negative overage = **surplus** | A value like -$54K means $54K of unused capacity, not a deficit |

## Snowflake Fiscal Year

| FY | Start | End |
|----|-------|-----|
| FY26 | 2025-02-01 | 2026-01-31 |
| FY27 | 2026-02-01 | 2027-01-31 |
| FY28 | 2027-02-01 | 2028-01-31 |

## Output Format

The skill produces a structured report with these sections:

1. **Account Summary** — Key metrics, contract structure, urgency, confidence
2. **Data Flags** — Anomalies, missing data, risk indicators
3. **Renewal Events** — Timeline of bookable events in the planning FY
4. **Strategic Options** — Viable booking paths with reasoning
5. **Scenarios Table** — Conservative / Base / Stretch with full TACV splits
6. **Recommendation** — Selected scenario, rationale, quota-bearing amount
7. **Guardrail Results** — Pass/fail with required approvers
8. **Validation Needed** — Priority items for Field Ops/AE to verify
9. **Consistency Check** — Cross-validation of recommendation vs. data

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Skill doesn't appear after restart | Verify `skill.yaml` is in the skill folder root, not nested in a subfolder |
| Skill triggers but no data returns | Check Snowflake role permissions (see Verify Data Access above) |
| Incorrect dollar amounts (too high/low) | Confirm GLOBAL_PLANNING values are actual $ — do NOT multiply by 1,000 |
| Contract structure shows "unknown" | Verify `FIVETRAN.SALESFORCE.CONTRACT` is accessible and has active contracts |
| "Insufficient consumption history" | Account has zero L90D — likely a new account with no usage yet |

## Updating the Skill

To update to a newer version:

1. Download the latest release from [`https://github.com/itsjefflong/tacv-quota-analysis`](https://github.com/itsjefflong/tacv-quota-analysis)
2. Replace the files in your skills directory:

```bash
# macOS / Linux
rm -rf ~/.cortex/skills/tacv-quota-analysis
mv ~/Downloads/tacv-quota-analysis ~/.cortex/skills/

# Windows
rmdir /s %USERPROFILE%\.cortex\skills\tacv-quota-analysis
move %USERPROFILE%\Downloads\tacv-quota-analysis %USERPROFILE%\.cortex\skills\
```

3. Restart Cortex Code

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2026-02-20 | Added strategic options, pull-forward rules, edge case handling, confidence scoring, negative overage interpretation, full output sections, approval routing |
| 1.0 | 2026-02-20 | Initial skill with 7-step workflow, 5 data sources, 3 scenarios |

## Support

For questions about the skill logic, data sources, or TACV methodology, contact GTM Operations.

For Cortex Code platform issues, refer to the [Snowflake Cortex documentation](https://docs.snowflake.com/en/user-guide/snowflake-cortex).

## Maintainer

Jeff — Senior Technical GTM Operations Manager, Snowflake Field Operations
