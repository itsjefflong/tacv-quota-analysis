# TACV Quota Scenario Modeling App — Build Specification

## Overview

A Streamlit app that enables Field Operations teams to generate TACV quota analysis for individual Snowflake customer accounts. The app accepts raw account data (pasted from Google Sheets), parses it using Snowflake Cortex (Opus 4.5), allows users to add qualitative context, then generates a structured analysis following the framework defined in `prompt.md`.

### Related Files
- `prompt.md` — Contains the full TACV analysis prompt/framework the LLM uses to generate output
- `SNOWFLAKE_STREAMLIT_GUIDE.md` — Snowflake-specific Streamlit best practices

---

## User Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: Select Planning Year + Paste Data                         │
│  ↓                                                                  │
│  STEP 2: Confirm Parsed Fields (edit/fill gaps)                    │
│  ↓                                                                  │
│  STEP 3: Add Qualitative Context                                   │
│  ↓                                                                  │
│  STEP 4: Generate Analysis                                         │
│  ↓                                                                  │
│  STEP 5: Review Output + Optionally Refine                         │
│  ↓                                                                  │
│  STEP 6: Export                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Planning Year Selection + Data Input

### Planning Year Dropdown
User selects which fiscal year they are planning for. This selection drives all date logic throughout the app.

**Dropdown Options:**
- FY27 (Feb 2026 - Jan 2027)
- FY28 (Feb 2027 - Jan 2028)
- FY29 (Feb 2028 - Jan 2029)

**Derived Values Based on Selection:**
```
Selected: FY27
├─ planning_fy: "FY27"
├─ fy_start: "2026-02-01"
├─ fy_end: "2027-01-31"
├─ 1h_start: "2026-02-01"
├─ 1h_end: "2026-07-31"
├─ 2h_start: "2026-08-01"
├─ 2h_end: "2027-01-31"
├─ prior_fy: "FY26"
├─ prior_fy_minus_1: "FY25"
```

**Default Behavior:**
- Oct–Jan: Default to next FY (planning season)
- Feb–Sep: Default to current FY

### Data Paste Area
Large text input where user pastes tab-delimited data copied from Google Sheets.

**Expected Input Format:**
```
Account Name	Contract End	Capacity Remaining	L90D	L30D	FY27 Prediction	Prior Renewal Base
BigCorp Inc.	1/15/2027	$18,000,000	$2,300,000	$2,900,000	$63,000,000	$15,000,000
```

**Parse Logic Requirements:**
- Handle tab-delimited format (standard Google Sheets copy behavior)
- Normalize currency formats ($18M, $18,000,000, 18000000)
- Normalize date formats (1/15/2027, 2027-01-15, Jan 15, 2027)
- Map column names flexibly (e.g., "90D Burn" → L90D, "Contract End Date" → Contract End)
- Detect FY## patterns in column names and map relative to selected planning year

---

## Step 2: Field Confirmation Card

After parsing, display extracted values for user confirmation. User can edit any field inline before proceeding.

### Tier 1: Required Fields (Block Progression If Missing)

| Field | Description | Validation |
|-------|-------------|------------|
| Account Name | Customer identifier | Non-empty string |
| Contract End Date | When current contract expires | Valid date |
| Capacity Remaining | $ remaining in contract | Positive number |
| L90D Burn Rate | Monthly consumption (last 90 days) | Positive number |
| Prior Renewal Base | Previous renewal ACV | Positive number |
| Contract Structure | Single-year or Multi-year | Selection required |
| Current Segment | Which year of multi-year (X of Y) | Required if multi-year |
| Total Segments | Total years in contract | Required if multi-year |

### Tier 2: Recommended Fields (Flag If Missing, Allow Proceeding)

| Field | Fallback If Missing |
|-------|---------------------|
| L30D Burn Rate | Assumes no acceleration (uses L90D) |
| [Planning FY] Prediction | Falls back to L90D × 12 |
| Contract Predicted Overage | Calculated from capacity ÷ burn rate |
| [Prior FY] Actuals | Weakens multi-year validation |
| [Prior FY - 1] Actuals | Weakens multi-year validation |
| Account Segment | Defaults to conservative growth assumptions |
| Account Owner | Display only |

### UI Behavior
- Show parsed values with green checkmarks for Tier 1 fields found
- Show yellow warning icons for Tier 2 fields missing
- Show red X with required input for Tier 1 fields missing
- Editable fields inline (click to edit)
- "Proceed to Context" button disabled until all Tier 1 fields populated

---

## Step 3: Qualitative Context Capture

Dedicated step (not a buried optional field) for user to provide context not found in source data.

### Prompt Text
> **What else should I know about this account?**
> 
> This context significantly improves the analysis. Include anything the data doesn't capture.

### Suggested Prompts (Helper Text or Chips)
- Customer budget constraints or approval dynamics
- AE relationship insights
- Known expansion or contraction plans
- Competitive pressure (evaluating alternatives?)
- Unusual contract history (prior pull-forwards, amendments)
- Timing considerations (reorgs, budget cycles, exec changes)

### Input
Multi-line text area, no character limit, optional but encouraged.

---

## Step 4: Generate Analysis

### Prompt Assembly
Combine:
1. The full analysis framework from `prompt.md`
2. Fiscal year context (dates, relative year labels)
3. Parsed + confirmed field values
4. User-provided qualitative context

### Cortex Call
Send assembled prompt to Snowflake Cortex using Opus 4.5.

### Loading State
Show progress indicator during generation. Analysis may take 15-30 seconds.

---

## Step 5: Output Display

Display the generated analysis in a structured, scannable format.

### Recommended Structure: Tabbed or Collapsible Sections

**Tab/Section 1: Executive Summary**
- Account info, contract status, consumption metrics
- Recommended TACV with confidence level
- Quick-scan format

**Tab/Section 2: Data Quality Flags**
- Red flags detected during analysis
- Assumptions made
- Validation needs before quota use
- Only show if flags exist

**Tab/Section 3: FY[XX] Renewal Events**
- List of bookable events with dates, amounts, confidence
- Total Base Renewal ACV
- Early renewal alternative if applicable

**Tab/Section 4: Customer Options**
- Option cards (Pay Overage, Pull Forward, Amend, Early Renewal)
- Each with: action, capacity check, TACV bookability, trade-offs
- Visual indicators: ✅ ⚠️ ❌

**Tab/Section 5: Planning Scenarios**
- Conservative / Base / Stretch table
- Recommendation with rationale
- Confidence assessment

**Tab/Section 6: Risks & Validation**
- Top risks with mitigations
- Priority 1 / Priority 2 validations
- Usage guidance based on confidence level

### Refinement Option
Below output, provide option to refine:

> **Want to refine this analysis?**
> 
> Add additional context or correct assumptions, then regenerate.

Text input + "Regenerate Analysis" button. New context appends to original, re-runs analysis, displays updated output.

---

## Step 6: Export

### Primary Export: Document Download
Generate a clean, formatted document from the analysis output.

**Format Options:**
- Markdown (.md) — simplest
- Google Doc (if integration available)
- PDF (if rendering available)

### Export Button
Prominent placement below output. Downloads file named:
`TACV_Analysis_[AccountName]_[PlanningFY]_[Date].md`

---

## Technical Notes

### Fiscal Year Calculation Helper

```python
def get_fiscal_year_context(planning_fy: str) -> dict:
    """
    Given a planning FY (e.g., 'FY27'), return all derived date values.
    Snowflake FY runs Feb 1 - Jan 31.
    """
    # Extract year number (FY27 → 27 → 2027 for end year)
    fy_num = int(planning_fy.replace('FY', ''))
    end_year = 2000 + fy_num
    start_year = end_year - 1
    
    return {
        'planning_fy': planning_fy,
        'fy_start': f'{start_year}-02-01',
        'fy_end': f'{end_year}-01-31',
        '1h_start': f'{start_year}-02-01',
        '1h_end': f'{start_year}-07-31',
        '2h_start': f'{start_year}-08-01',
        '2h_end': f'{end_year}-01-31',
        'prior_fy': f'FY{fy_num - 1}',
        'prior_fy_minus_1': f'FY{fy_num - 2}',
    }
```

### Field Name Mapping Examples

The parser should handle common variations:

| Possible Input Names | Maps To |
|---------------------|---------|
| L90D, 90D Burn, L90D Burn Rate, Last 90 Day | l90d_burn_rate |
| Contract End, Contract End Date, End Date, Renewal Date | contract_end_date |
| Capacity Remaining, Remaining Capacity, Capacity Left | capacity_remaining |
| FY27 Prediction, FY27 Forecast, FY27 Consumption | planning_fy_prediction |

### Session State Management

Key state to maintain across steps:
- `selected_planning_fy` — User's FY selection
- `raw_paste_input` — Original pasted text
- `parsed_fields` — Dict of extracted field values
- `user_confirmed_fields` — Dict after user edits
- `qualitative_context` — User's additional context
- `generated_analysis` — LLM output
- `refinement_context` — Additional context from refinement step

---

## Out of Scope for MVP

- Multi-account batch processing
- Direct data source connections (Salesforce, Pigment, Snowflake tables)
- Persistent storage of analyses
- User authentication / access control
- Analysis history / versioning
- Comparison between analysis runs

---

## Success Criteria

1. Field Ops can paste messy Google Sheets data and get accurate field extraction
2. Missing/ambiguous fields are clearly flagged before analysis runs
3. Qualitative context meaningfully influences the output
4. Output is scannable — user finds recommended TACV within 10 seconds
5. Export produces a clean document ready for planning use
6. Fiscal year logic works correctly when FY28 planning begins