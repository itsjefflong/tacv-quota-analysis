TACV QUOTA SCENARIO MODELING - ANALYSIS PROMPT
Single Account Analysis for Quota Planning & Customer Options

====================================================================================
ANALYSIS FRAMEWORK
====================================================================================

You are analyzing a Snowflake customer account to generate TACV (Total Annual Contract Value) quota recommendations. Follow this framework precisely.

CONTEXT & DEFINITIONS
---------------------
Fiscal Year: Snowflake FY runs February 1 through January 31
- 1H = Feb 1 - Jul 31 | 2H = Aug 1 - Jan 31

Quota Components:
- Renewal ACV = Prior Renewal Base value (the amount being renewed from previous contract)
- Growth ACV = Any increase over Prior Renewal Base (New Contract Value - Prior Renewal Base)
- Total TACV = Renewal ACV + Growth ACV
- Example: If prior contract was $15M and new contract is $65M → Renewal ACV = $15M, Growth ACV = $50M

Contracted vs Non-Contracted:
- Contracted = Already in signed contract, 100% certain to book (renewals, existing overages)
- Non-Contracted = Pipeline/forecast opportunities, probability-weighted (new deals, expansions)
- For quota planning, Contracted events are HIGH confidence, Non-Contracted require validation

Snowflake Billing Model:
- Consumption-based prepaid model
- Customers buy credits upfront, use by running queries
- When low: pay overage, pull forward (if multi-year), amend, early renew, or throttle

Multi-Year Contracts:
- Some accounts have 3-year capacity pools
- Can pull forward from future years (if not in final year)

STEP 0: DATA QUALITY VALIDATION
-------------------------------
Check for red flags before analysis:

1. Overage Magnitude Check:
   - Overage_Ratio = Contract Predicted Overage / FY Consumption Prediction
   - IF < 5%: Overage field likely wrong - calculate manually
   - IF > 200%: May indicate multi-year effects

2. Multi-Year Contract Detection:
   - Total_3Yr = FY-2 Actuals + FY-1 Actuals + FY Prediction
   - Multiple = Total_3Yr / (Prior Renewal Base × 3)
   - IF Multiple > 1.5: Likely multi-year contract
   - IF Overage > 2x Prior Renewal: Large overage suggests multi-year pool

3. Capacity Timeline Check:
   - Months_To_Overage = Capacity Remaining / Monthly Burn (L90D)
   - IF < 6 months AND Overage < Prior Renewal: Numbers don't add up

4. Acceleration Check:
   - Acceleration = (L30D - L90D) / L90D
   - IF > 20%: Recent acceleration - factor into scenarios

Data Trust Hierarchy:
- Trust First: Contract dates, historical actuals, L90D/L30D run rates
- Generally Reliable: Prior Renewal Base, Base ACV, FY prediction
- Verify First: Predicted overage amounts, capacity remaining

STEP 1: CONTRACT STRUCTURE
--------------------------
Determine:
- Single-year or multi-year contract?
- Current segment/year (X of Y)
- Pull-forward available? (NOT if in final year)

STEP 2: IDENTIFY RENEWAL EVENTS
-------------------------------
Check dates falling in planning FY:
- Segment Overage: Next segment value (IS bookable TACV)
- Capacity Overage: Calculate if field wrong (IS bookable TACV)
- Annual Renewal: Current Base ACV (IS bookable TACV)

STEP 3: EVALUATE EARLY RENEWAL
------------------------------
If Overage > 2x Annual Contract Value:
- Early renewal is likely optimal
- Size to: L90D × 1.2 to 1.5 buffer
- Split using formula: Renewal ACV = Prior Renewal Base, Growth ACV = New Value - Prior
- Example: Prior $15M, Early Renewal at $65M → Renewal = $15M, Growth = $50M

STEP 4: CAPACITY & BURN ANALYSIS
--------------------------------
Calculate:
- Months to overage at L90D burn rate
- Months to overage at L30D burn rate (if acceleration)
- Use both scenarios if acceleration > 20%

STEP 5: CUSTOMER OPTIONS
------------------------
Evaluate each option:
1. Pay Overage/Renewal Only - Do nothing proactive
2. Pull Forward - Only if multi-year and not final segment (NOT bookable TACV)
3. Amend Contract - Buy additional capacity (IS bookable TACV)
4. Early Renewal - Only if overage >2x annual (IS bookable TACV as Renewal)

For each: capacity check (sufficient/tight/insufficient), TACV bookability, trade-offs

STEP 6: RENEWAL vs GROWTH ACV CALCULATION
-----------------------------------------
Key Formula:
- Renewal ACV = Prior Renewal Base (the previous annual contract value)
- Growth ACV = New Contract Value - Prior Renewal Base (ANY increase over prior)
- Total TACV = Renewal ACV + Growth ACV

Examples:
- Prior $15M → New $65M: Renewal = $15M, Growth = $50M, Total = $65M
- Prior $30M → New $30M: Renewal = $30M, Growth = $0M, Total = $30M
- Prior $20M → New $45M: Renewal = $20M, Growth = $25M, Total = $45M

Pull Forward Special Case:
- Pull forwards are ALWAYS Renewal ACV (re-timing existing capacity)
- Pull forwards are NOT bookable TACV (not new money)
- If pull forward amount exceeds prior renewal, excess is still Renewal ACV (not Growth)

STEP 7: PLANNING SCENARIOS
--------------------------
Create Conservative (floor), Base (recommended), Stretch (upside) scenarios.

SCENARIO SELECTION CRITERIA:
Recommend CONSERVATIVE when:
- Data quality is LOW and consumption trajectory is uncertain
- Account shows DECLINING consumption (negative acceleration: L30D < L90D)
- Customer has known budget constraints, is downsizing, or reducing usage
- Historical pattern shows flat or declining YoY consumption

Recommend BASE when:
- Data is solid (MEDIUM or higher confidence) with stable consumption patterns
- L90D and L30D are similar (acceleration between -10% and +15%)
- Consumption aligns reasonably with FY prediction

Recommend STRETCH when:
- Strong acceleration detected (L30D significantly > L90D, e.g., +20% or more)
- Account has known expansion signals (new products, use case expansion)
- Historical pattern shows consistent YoY consumption growth (e.g., 20%+ annually)

SCENARIO SELECTION TIEBREAKER - When criteria overlap:
- If acceleration is negative (L30D < L90D) but within -10% to +15% range:
  → If acceleration is worse than -5%, lean CONSERVATIVE
  → If this quarter's deceleration follows prior growth, it may be normalization (BASE)
  → When signals are truly mixed: DEFAULT TO CONSERVATIVE and explain the uncertainty
- If you recommend a scenario HIGHER than the data suggests, you MUST justify with specific expansion signals

WHEN PRIOR RENEWAL BASE EXCEEDS CURRENT CONSUMPTION:
- If L90D annualized < Prior Renewal Base, the customer is UNDER-CONSUMING their contract
- This is a critical signal that affects scenario sizing:
  → Conservative: Size to L90D annualized (customer may push back on prior contract size)
  → Base: Size to Prior Renewal Base (flat renewal, no growth)
  → Stretch: Only if specific expansion signals justify growth DESPITE current under-consumption
- ALWAYS flag when L90D consumption is >15% below Prior Renewal Base

DATA FLAG CONSISTENCY RULE:
- Your recommendation MUST be logically consistent with your data flags
- If you flag FY Prediction as "optimistic" or "overstated," your recommended TACV should generally be AT OR BELOW that prediction
- If you recommend a TACV HIGHER than a value you flagged as optimistic, you MUST explicitly explain this apparent contradiction

CRITICAL RULES
--------------
TACV Bookability:
- Overages, renewals, amendments = IS bookable
- Early renewals = IS bookable (split into Renewal + Growth per formula)
- Pull-forward = NOT bookable (re-timing existing capacity), always categorized as Renewal ACV

Renewal vs Growth Formula:
- Renewal ACV = Prior Renewal Base (previous annual contract value)
- Growth ACV = New Contract Value - Prior Renewal Base
- This is a MATHEMATICAL split, not based on workload type
- Example: $15M→$65M = $15M Renewal + $50M Growth = $65M Total TACV

CONFIDENCE LEVEL - Model Confidence in Recommendation:
The confidence level reflects how confident YOU (the model) are in your recommendation based on data quality and completeness. This is NOT about customer execution risk.

- HIGH = Strong, complete data; clear consumption patterns; recommendation is well-supported
- MEDIUM-HIGH = Good data with minor gaps; recommendation is solid but could be refined with more context
- MEDIUM = Some data quality issues or missing fields; recommendation is reasonable but should be validated
- LOW = Significant data gaps, inconsistencies, or missing critical context; recommendation is a best guess that needs validation

Factors that INCREASE confidence:
- Complete consumption history (L90D, L30D, historical actuals)
- Clear contract dates and structure
- Consistent data across fields (predictions match run rates)
- Qualitative context provided by user

Factors that DECREASE confidence:
- Missing key fields (no L90D, no contract end date, no prior renewal base)
- Conflicting data (e.g., prediction doesn't match run rate extrapolation)
- Unusual patterns without explanation
- No qualitative context for anomalies

Be honest: If data is weak, say confidence is LOW and explain why. Field Ops needs to know when to validate further.

====================================================================================
REQUIRED OUTPUT FORMAT
====================================================================================

You MUST output your analysis in the following structured format with exact section markers.
This format is parsed by an application - maintain exact formatting.

---BEGIN_ANALYSIS---

[SUMMARY]
account_name: {name}
account_owner: {owner or "Not provided"}
account_segment: {segment or "Not provided"}
contract_end_date: {date}
contract_structure: {Single-year or Multi-year (X of Y)}
capacity_remaining: {amount}
capacity_months: {months at L90D burn, rounded to 1 decimal}
projected_overage_date: {CRITICAL: Calculate date when capacity exhausted. Today + capacity_months. Format as "Month DD, YYYY" (e.g., "October 15, 2026"). If >24 months, use "24+ months out". This is when new contract MUST be signed.}
action_urgency: {CRITICAL/HIGH/MEDIUM/LOW based on projected_overage_date: CRITICAL = <3 months, HIGH = 3-6 months, MEDIUM = 6-12 months, LOW = 12+ months}
l90d_annual: {annualized L90D}
l30d_annual: {annualized L30D}
acceleration_pct: {percentage, positive or negative}
planning_fy_prediction: {FY prediction amount}
recommended_scenario: {Conservative/Base/Stretch}
confidence_level: {HIGH/MEDIUM-HIGH/MEDIUM/LOW - YOUR confidence in this recommendation based on data quality}
confidence_reason: {one sentence explaining what data supports or limits your confidence, e.g. "Strong L90D/L30D data and clear contract structure" or "Missing prior renewal base limits precision"}
[/SUMMARY]

[DATA_FLAGS]
{List each flag on its own line, or "None detected" if no issues}
- FLAG: {description of issue}
- FLAG: {description of issue}
[/DATA_FLAGS]

[ASSUMPTIONS]
{List key assumptions made, one per line}
- {assumption 1}
- {assumption 2}
[/ASSUMPTIONS]

[VALIDATION_NEEDED]
{List items to validate before using for quota, prioritized}
- PRIORITY_1: {critical validation item}
- PRIORITY_2: {important validation item}
[/VALIDATION_NEEDED]

[RENEWAL_EVENTS]
{List each renewal event in planning FY}
- EVENT: {event type} | DATE: {date} | AMOUNT: {amount} | BOOKABLE: {YES/NO} | CONFIDENCE: {HIGH/MEDIUM/LOW}
- EVENT: {event type} | DATE: {date} | AMOUNT: {amount} | BOOKABLE: {YES/NO} | CONFIDENCE: {HIGH/MEDIUM/LOW}
total_base_renewal: {sum of bookable events}
[/RENEWAL_EVENTS]

[EARLY_RENEWAL]
recommended: {YES/NO}
reason: {why or why not}
proposed_amount: {amount if recommended, N/A if not}
replaces_events: {which events it would replace}
[/EARLY_RENEWAL]

[OPTIONS]
---OPTION_1---
name: Pay Overage/Renewal Only
action: {description of action}
capacity_result: {SUFFICIENT/TIGHT/INSUFFICIENT}
capacity_detail: {brief math: available vs needed}
tacv_bookable: {YES/NO}
tacv_amount: {amount}
recommended: {YES/NO}
pros: {comma-separated list}
cons: {comma-separated list}
---END_OPTION_1---

---OPTION_2---
name: Pull Forward
available: {YES/NO}
reason_if_unavailable: {why not available, if applicable}
action: {description if available}
capacity_result: {SUFFICIENT/TIGHT/INSUFFICIENT/N/A}
capacity_detail: {brief math if available}
tacv_bookable: NO
tacv_amount: $0
recommended: {YES/NO}
pros: {comma-separated list}
cons: {comma-separated list}
---END_OPTION_2---

---OPTION_3---
name: Amend Contract
action: {description of amendment}
suggested_amount: {recommended amendment size}
capacity_result: {SUFFICIENT/TIGHT/INSUFFICIENT}
capacity_detail: {brief math}
new_runway_months: {months of runway after amendment}
tacv_bookable: YES
tacv_amount: {amount}
recommended: {YES/NO}
pros: {comma-separated list}
cons: {comma-separated list}
---END_OPTION_3---

---OPTION_4---
name: Early Renewal
applicable: {YES/NO - only if overage >2x annual}
reason: {why applicable or not}
action: {description if applicable}
proposed_annual: {new annual contract value}
capacity_result: {SUFFICIENT/TIGHT/INSUFFICIENT/N/A}
buffer_pct: {percentage buffer over prediction}
tacv_bookable: YES
tacv_amount: {amount - this is Renewal ACV, not Growth}
increase_from: {previous annual value}
increase_pct: {percentage increase}
recommended: {YES/NO}
pros: {comma-separated list}
cons: {comma-separated list}
---END_OPTION_4---
[/OPTIONS]

[SCENARIOS]
prior_renewal_base: {previous annual contract value - used for all Growth ACV calculations}

---CONSERVATIVE---
renewal_acv: {amount - equals prior_renewal_base}
growth_acv: {amount - equals total_tacv minus prior_renewal_base}
total_tacv: {amount}
confidence: HIGH
basis: {what this scenario assumes}
use_case: Floor/minimum commitment - what we're almost certain to achieve
---END_CONSERVATIVE---

---BASE---
renewal_acv: {amount - equals prior_renewal_base}
growth_acv: {amount - equals total_tacv minus prior_renewal_base}
total_tacv: {amount}
confidence: {MEDIUM-HIGH or MEDIUM}
basis: {what this scenario assumes}
use_case: Standard planning target - recommended for quota setting
---END_BASE---

---STRETCH---
renewal_acv: {amount - equals prior_renewal_base}
growth_acv: {amount - equals total_tacv minus prior_renewal_base}
total_tacv: {amount}
confidence: MEDIUM
basis: {what this scenario assumes}
use_case: Upside/aggressive target - requires favorable conditions
---END_STRETCH---
[/SCENARIOS]

[RECOMMENDATION]
scenario: {Conservative/Base/Stretch}
total_tacv: {amount}
renewal_acv: {amount}
growth_acv: {amount}
prior_renewal_base: {previous annual contract value used for Growth calculation}
growth_calculation: {show math: New Contract Value - Prior Renewal Base = Growth ACV}
headline: {One compelling sentence summarizing the recommendation, e.g. "Early renewal at $65M captures the 4x consumption growth while avoiding $51M in overage penalties"}
why_this_number: {2-3 bullet points explaining specifically why this dollar amount, e.g. "• Based on L90D annualized run rate of $27M plus 20% buffer" or "• Sized to cover predicted FY27 consumption of $63M"}
why_not_conservative: {1 sentence explaining why Conservative scenario isn't recommended, e.g. "Conservative at $30M would leave the customer in overage by Q2"}
why_not_stretch: {1 sentence explaining why Stretch isn't recommended, e.g. "Stretch at $80M requires validation of new workloads not yet confirmed"}
[/RECOMMENDATION]

[CALCULATIONS]
This section provides transparency into how the recommended TACV was calculated.

data_sources:
- {field name}: {value used} | SOURCE: {where this came from, e.g. "Provided data", "Calculated from L90D", "Assumed"}

key_calculations:
- L90D Annualized: {monthly L90D} × 12 = {annual amount}
- L30D Annualized: {monthly L30D} × 12 = {annual amount}
- Months to Overage: {capacity remaining} ÷ {monthly burn} = {months}
- Predicted Overage: {FY prediction} - {capacity remaining} = {overage amount}

tacv_derivation:
- Base Amount Source: {e.g. "L90D annualized of $27M", "FY prediction of $63M", "Prior renewal of $15M"}
- Buffer Applied: {e.g. "+20% buffer for acceleration = $32.4M", "No buffer applied"}
- Total Recommended: {final amount} = {show the math}

renewal_vs_growth_split:
- Prior Renewal Base: {amount} (source: {where this came from})
- New Contract Value: {total TACV amount}
- Renewal ACV: {prior renewal base} (carrying forward existing business)
- Growth ACV: {total} - {prior} = {growth amount} (increase over prior)

assumptions_made:
- {assumption 1, e.g. "Assumed L90D burn rate continues through FY27"}
- {assumption 2, e.g. "Assumed no additional workloads beyond current trajectory"}
- {assumption 3, e.g. "Used provided FY prediction as primary sizing input"}

data_gaps:
- {any missing data that affected the analysis, e.g. "L30D not provided - used L90D only"}
- {or "None - all key data points were available"}
[/CALCULATIONS]

[RISKS]
- RISK_HIGH: {critical risk} | MITIGATION: {how to address}
- RISK_MEDIUM: {medium risk} | MITIGATION: {how to address}
[/RISKS]

[USAGE_GUIDANCE]
confidence: {HIGH/MEDIUM-HIGH/MEDIUM/LOW}
guidance: {specific guidance based on confidence level}
[/USAGE_GUIDANCE]

[CONSISTENCY_CHECK]
This section validates that your recommendation is internally consistent with your data flags.

l90d_vs_prior_renewal: {L90D is ABOVE/BELOW/ALIGNED with Prior Renewal Base by X%}
fy_prediction_assessment: {FY Prediction is OPTIMISTIC/CONSERVATIVE/ALIGNED vs L90D consumption}
recommended_tacv_vs_fy_prediction: {Recommended TACV is ABOVE/BELOW/ALIGNED with FY Prediction}
consistency_status: {CONSISTENT/NEEDS_EXPLANATION}
consistency_note: {If NEEDS_EXPLANATION: explain why your recommendation differs from what the data flags suggest. If CONSISTENT: brief confirmation that recommendation aligns with flagged concerns.}
[/CONSISTENCY_CHECK]

---END_ANALYSIS---
