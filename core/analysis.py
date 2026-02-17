"""
TACV Analysis Engine
====================
Prompt construction, Cortex API calls, and structured response parsing.
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.config import (
    IS_SNOWFLAKE,
    MODEL_ANALYSIS,
    TIER_1_FIELDS,
    TIER_2_FIELDS,
    logger,
    session,
)
from core.sfdc import (
    format_account_for_prompt,
    format_selected_contracts_for_prompt,
    format_selected_opportunities_for_prompt,
)
from core.utils import format_currency, parse_currency


def get_analysis_prompt(fields: Dict, fy_context: Dict, qualitative_context: str, selected_opportunities: List[Dict[str, Any]] = None, selected_contracts: List[Dict[str, Any]] = None, sfdc_account: Dict[str, Any] = None) -> str:
    """Construct the analysis prompt with structured output format for easy parsing."""
    
    # Build account data string
    account_data_lines = []
    for key, value in fields.items():
        label = TIER_1_FIELDS.get(key, TIER_2_FIELDS.get(key, {})).get('label', key)
        if isinstance(value, float):
            account_data_lines.append(f"- {label}: {format_currency(value)}")
        else:
            account_data_lines.append(f"- {label}: {value}")
    
    account_data_str = '\n'.join(account_data_lines)
    
    # Build opportunity context if provided
    opportunity_context = ""
    if selected_opportunities:
        opportunity_context = "\n\n" + format_selected_opportunities_for_prompt(selected_opportunities)
    
    # Build contract context if provided
    contract_context = ""
    if selected_contracts:
        contract_context = "\n\n" + format_selected_contracts_for_prompt(selected_contracts)
    
    # Build SFDC account context if provided (auto-fetched, enriches analysis)
    sfdc_account_context = ""
    if sfdc_account:
        sfdc_account_context = "\n\n" + format_account_for_prompt(sfdc_account)
    
    prompt = f"""You are analyzing a Snowflake customer account to generate TACV (Total Annual Contract Value) quota recommendations.

FISCAL YEAR CONTEXT:
- Planning FY: {fy_context['planning_fy']} ({fy_context['fy_start']} through {fy_context['fy_end']})
- 1H: {fy_context['1h_start']} - {fy_context['1h_end']} | 2H: {fy_context['2h_start']} - {fy_context['2h_end']}
- Prior FY: {fy_context['prior_fy']} | Prior FY-1: {fy_context['prior_fy_minus_1']}

DEFINITIONS:
- Renewal ACV = Prior Renewal Base value (the amount being renewed from previous contract)
- Growth ACV = Any increase over Prior Renewal Base (New Contract Value - Prior Renewal Base)
- Total TACV = Renewal ACV + Growth ACV
- Example: If prior contract was $15M and new contract is $65M → Renewal ACV = $15M, Growth ACV = $50M
- Overages, renewals, amendments = IS bookable TACV
- Pull-forward = NOT bookable (re-timing), but ALWAYS categorized as Renewal ACV (not Growth)
- Early renewals = IS bookable, split using formula (Renewal = prior base, Growth = increase)

TACV CLASSIFICATION - CONTRACTED VS NON-CONTRACTED:

RENEWAL ACV splits into:
- Contracted Renewal = Multi-year segment auto-renewing (e.g., Year 1 → Year 2 of a 3-year deal). Happens automatically, NOT quota-bearing for sales.
- Non-Contracted Renewal = Single-year renewal OR final segment of multi-year (e.g., Year 3 of 3). Sales must execute the renewal, IS quota-bearing.

GROWTH ACV splits into:
- Contracted Growth = Built-in step-ups in multi-year agreements (e.g., Year 1: $100K → Year 2: $120K = $20K contracted growth). Already signed, NOT quota-bearing.
- Non-Contracted Growth = Upsells on renewals, amendments, co-terms, expansion deals. Sales must close, IS quota-bearing.

QUOTA IMPLICATIONS:
- Quota-Bearing TACV = Non-Contracted Renewal + Non-Contracted Growth (what sales must SELL)
- Non-Quota TACV = Contracted Renewal + Contracted Growth (happens automatically)

HOW TO DETERMINE CONTRACTED VS NON-CONTRACTED:
- IF contract_structure = "Multi-year" AND NOT final segment (e.g., "Year 1 of 3" or "Year 2 of 3"):
  → Renewal = Contracted (auto-renews to next segment)
  → Check for built-in step-ups → Contracted Growth
- IF contract_structure = "Single-year" OR final multi-year segment (e.g., "Year 3 of 3"):
  → Renewal = Non-Contracted (must be sold)
  → All growth = Non-Contracted (must be sold)

IMPORTANT - L90D AND L30D BURN RATES ARE ALREADY ANNUALIZED:
- The L90D and L30D burn rate values provided are ALREADY ANNUALIZED (annual run rates)
- They come from "Annualized Run Rate (L90D/L30D)" columns in Pigment
- DO NOT multiply them by 12 or otherwise re-annualize them
- To calculate monthly burn: divide by 12 (e.g., $469K annual ÷ 12 = $39K/month)
- To calculate daily burn: divide by 365 (e.g., $469K annual ÷ 365 = $1,285/day)
- Example: If L90D = $469K, this IS the annual rate, not 90 days of consumption

IMPORTANT - FY PREDICTION GUIDANCE:
- FY Prediction values come from data science models and should be treated with CAUTION
- These predictions are often inaccurate and should have MINIMAL influence on your TACV recommendation
- BASE your recommendation primarily on ACTUAL consumption data: L90D burn rate, L30D burn rate, capacity remaining, and historical actuals
- Only reference FY Prediction as a directional signal, NOT as a target to size the deal to
- If FY Prediction seems unrealistic compared to actual consumption patterns, FLAG it and explain the discrepancy
- When FY Prediction conflicts with L90D/L30D data, TRUST the actual consumption data

CONFIDENCE LEVEL - Your confidence in this recommendation based on DATA QUALITY:
- HIGH = Strong, complete data; clear patterns; recommendation well-supported
- MEDIUM-HIGH = Good data with minor gaps; solid recommendation
- MEDIUM = Some data issues or missing fields; recommendation reasonable but should be validated
- LOW = Significant data gaps or inconsistencies; recommendation is best guess, needs validation
Be honest: If data is weak or incomplete, say confidence is LOW and explain why. Field Ops needs to know when to validate.

SCENARIO SELECTION CRITERIA - Choose the scenario that BEST FITS THE DATA, not the "safe middle ground":

Recommend CONSERVATIVE when:
- Data quality is LOW and consumption trajectory is uncertain
- Account shows DECLINING consumption (negative acceleration: L30D < L90D)
- Customer has known budget constraints, is downsizing, or reducing usage
- Contract end is far out (12+ months) with ample capacity remaining (no urgency)
- Historical pattern shows flat or declining YoY consumption

Recommend BASE when:
- Data is solid (MEDIUM or higher confidence) with stable consumption patterns
- L90D and L30D are similar (acceleration between -10% and +15%)
- Consumption aligns reasonably with FY prediction
- Standard renewal cycle with predictable, modest growth expected

Recommend STRETCH when:
- Strong acceleration detected (L30D significantly > L90D, e.g., +20% or more)
- FY prediction significantly exceeds L90D extrapolation (suggesting expected growth)
- Account has known expansion signals (new products, use case expansion, growth initiatives in qualitative context)
- Historical pattern shows consistent YoY consumption growth (e.g., 20%+ annually)
- Customer is in growth phase with capacity that will run out before contract end

SCENARIO SELECTION TIEBREAKER - When criteria overlap:
- If acceleration is negative (L30D < L90D) but within -10% to +15% range:
  → Look at the MAGNITUDE: If acceleration is worse than -5%, lean CONSERVATIVE
  → Look at HISTORICAL PATTERN: If this quarter's deceleration follows prior growth, it may be normalization (BASE)
  → When signals are truly mixed: DEFAULT TO CONSERVATIVE and explain the uncertainty
- If you recommend a scenario HIGHER than the data suggests, you MUST justify with specific expansion signals or qualitative context

WHEN PRIOR RENEWAL BASE EXCEEDS CURRENT CONSUMPTION:
- If L90D annualized < Prior Renewal Base, the customer is UNDER-CONSUMING their contract
- This is a critical signal that affects scenario sizing:
  → Conservative: Size to L90D annualized (customer may push back on prior contract size)
  → Base: Size to Prior Renewal Base (flat renewal, no growth - customer is already over-contracted)
  → Stretch: Only if specific expansion signals justify growth DESPITE current under-consumption
- ALWAYS flag when L90D consumption is >15% below Prior Renewal Base
- Do NOT use historical YoY growth to justify growth if current consumption is declining

DATA FLAG CONSISTENCY RULE:
- Your recommendation MUST be logically consistent with your data flags
- If you flag FY Prediction as "optimistic" or "overstated," your recommended TACV should generally be AT OR BELOW that prediction
- If you recommend a TACV HIGHER than a value you flagged as optimistic, you MUST explicitly explain this apparent contradiction
- Example of INCONSISTENCY to avoid: "FY Prediction of $2.8M is optimistic vs. $2.3M consumption... recommend $3.5M" (contradictory without explanation)

ACCOUNT DATA:
{account_data_str}
{opportunity_context}
{contract_context}
{sfdc_account_context}

ADDITIONAL CONTEXT:
{qualitative_context if qualitative_context else "None provided"}

ANALYSIS STEPS:
1. Check data quality - flag any red flags (overage magnitude, multi-year indicators, capacity timeline issues, acceleration)
2. Determine contract structure (single vs multi-year, segment position)
3. Identify renewal events in {fy_context['planning_fy']}
4. Evaluate if early renewal makes sense (if overage > 2x annual)
5. Analyze capacity & burn rates
6. Evaluate customer options with capacity math
7. Create Conservative/Base/Stretch scenarios
8. Make recommendation with rationale

OUTPUT YOUR ANALYSIS IN THIS EXACT STRUCTURED FORMAT:

---BEGIN_ANALYSIS---

[SUMMARY]
account_name: {{extracted account name}}
account_owner: {{owner or "Not provided"}}
account_segment: {{segment or "Not provided"}}
contract_end_date: {{date}}
contract_structure: {{Single-year or Multi-year (X of Y)}}
capacity_remaining: {{dollar amount}}
capacity_months: {{months at L90D burn, rounded to 1 decimal}}
projected_overage_date: {{CRITICAL: Calculate the date when capacity will be exhausted. Use today's date + capacity_months. Format as Month DD, YYYY (e.g., "October 15, 2026"). If capacity_months > 24, use "24+ months out". This is when a new contract MUST be signed.}}
action_urgency: {{CRITICAL/HIGH/MEDIUM/LOW based on projected_overage_date: CRITICAL = <3 months, HIGH = 3-6 months, MEDIUM = 6-12 months, LOW = 12+ months}}
l90d_annual: {{annualized L90D}}
l30d_annual: {{annualized L30D or "Not provided"}}
acceleration_pct: {{percentage like +15% or -5% or "N/A"}}
planning_fy_prediction: {{FY prediction or "Not provided"}}
recommended_scenario: {{Conservative/Base/Stretch}}
confidence_level: {{HIGH/MEDIUM-HIGH/MEDIUM/LOW - YOUR confidence based on data quality}}
confidence_reason: {{one sentence on what data supports or limits your confidence}}
[/SUMMARY]

[DATA_FLAGS]
{{List each flag, or "None detected"}}
- FLAG: {{description}}
[/DATA_FLAGS]

[RENEWAL_EVENTS]
{{List each event}}
- EVENT: {{type}} | DATE: {{date}} | AMOUNT: {{amount}} | BOOKABLE: {{YES/NO}}
total_base_renewal: {{sum}}
[/RENEWAL_EVENTS]

[OPTIONS]
---OPTION_1---
name: Pay Overage/Renewal Only
action: {{description}}
capacity_result: {{SUFFICIENT/TIGHT/INSUFFICIENT}}
tacv_bookable: YES
tacv_amount: {{amount}}
recommended: {{YES/NO}}
pros: {{comma list}}
cons: {{comma list}}
---END_OPTION_1---

---OPTION_2---
name: Pull Forward
available: {{YES/NO}}
reason: {{why or why not}}
tacv_bookable: NO
tacv_amount: $0
recommended: {{YES/NO}}
---END_OPTION_2---

---OPTION_3---
name: Amend Contract  
action: {{description}}
suggested_amount: {{amount}}
capacity_result: {{SUFFICIENT/TIGHT/INSUFFICIENT}}
tacv_bookable: YES
tacv_amount: {{amount}}
recommended: {{YES/NO}}
pros: {{comma list}}
cons: {{comma list}}
---END_OPTION_3---

---OPTION_4---
name: Early Renewal
applicable: {{YES/NO}}
reason: {{why}}
proposed_annual: {{amount if applicable}}
tacv_bookable: YES
tacv_amount: {{amount}}
recommended: {{YES/NO}}
pros: {{comma list}}
cons: {{comma list}}
---END_OPTION_4---
[/OPTIONS]

[SCENARIOS]
prior_renewal_base: {{previous annual contract value - used for all Growth ACV calculations}}
contract_type: {{Single-year OR Multi-year segment X of Y}}

---CONSERVATIVE---
renewal_acv: {{amount - equals prior_renewal_base}}
contracted_renewal: {{amount if multi-year not final segment, else $0}}
non_contracted_renewal: {{amount if single-year or final segment, else $0}}
growth_acv: {{amount - equals total_tacv minus prior_renewal_base}}
contracted_growth: {{amount if multi-year has built-in step-ups, else $0}}
non_contracted_growth: {{remainder of growth_acv}}
total_tacv: {{amount}}
quota_bearing: {{non_contracted_renewal + non_contracted_growth}}
confidence: {{HIGH/MEDIUM-HIGH/MEDIUM/LOW - likelihood account achieves this target}}
basis: {{what consumption pattern/data supports this scenario}}
---END_CONSERVATIVE---

---BASE---
renewal_acv: {{amount - equals prior_renewal_base}}
contracted_renewal: {{amount if multi-year not final segment, else $0}}
non_contracted_renewal: {{amount if single-year or final segment, else $0}}
growth_acv: {{amount - equals total_tacv minus prior_renewal_base}}
contracted_growth: {{amount if multi-year has built-in step-ups, else $0}}
non_contracted_growth: {{remainder of growth_acv}}
total_tacv: {{amount}}
quota_bearing: {{non_contracted_renewal + non_contracted_growth}}
confidence: {{HIGH/MEDIUM-HIGH/MEDIUM/LOW - likelihood account achieves this target}}
basis: {{what consumption pattern/data supports this scenario}}
---END_BASE---

---STRETCH---
renewal_acv: {{amount - equals prior_renewal_base}}
contracted_renewal: {{amount if multi-year not final segment, else $0}}
non_contracted_renewal: {{amount if single-year or final segment, else $0}}
growth_acv: {{amount - equals total_tacv minus prior_renewal_base}}
contracted_growth: {{amount if multi-year has built-in step-ups, else $0}}
non_contracted_growth: {{remainder of growth_acv}}
total_tacv: {{amount}}
quota_bearing: {{non_contracted_renewal + non_contracted_growth}}
confidence: {{HIGH/MEDIUM-HIGH/MEDIUM/LOW - likelihood account achieves this target}}
basis: {{what consumption pattern/data supports this scenario}}
---END_STRETCH---
[/SCENARIOS]

[RECOMMENDATION]
scenario: {{Conservative/Base/Stretch - choose based on SCENARIO SELECTION CRITERIA above}}
total_tacv: {{amount}}
renewal_acv: {{amount}}
contracted_renewal: {{amount if multi-year not final segment, else $0}}
non_contracted_renewal: {{amount if single-year or final segment, else $0}}
growth_acv: {{amount}}
contracted_growth: {{amount if multi-year has built-in step-ups, else $0}}
non_contracted_growth: {{remainder of growth_acv - upsells, amendments, expansion}}
quota_bearing_tacv: {{non_contracted_renewal + non_contracted_growth - what sales must SELL}}
non_quota_tacv: {{contracted_renewal + contracted_growth - happens automatically}}
prior_renewal_base: {{previous annual contract value}}
growth_calculation: {{show math: Total TACV - Prior Renewal Base = Growth ACV}}
headline: {{2-3 sentences: Start with the recommended action and TACV amount, then explain the key driver (consumption pattern, overage risk, growth opportunity), and end with the expected outcome or benefit. Be specific with numbers.}}
why_this_scenario: {{1-2 sentences explaining WHY this scenario fits the data better than the alternatives. Reference specific metrics like acceleration %, capacity runway, or consumption trends.}}
why_this_number: {{2-3 bullet points explaining specifically why this dollar amount}}
alternative_scenario: {{If recommending Conservative or Stretch, briefly note when Base might be appropriate. If recommending Base, note what would trigger Conservative or Stretch.}}
[/RECOMMENDATION]

[CALCULATIONS]
This section provides transparency into how the TACV was calculated.

data_sources:
- {{field}}: {{value}} | SOURCE: {{where from - "Provided", "Calculated", "Assumed"}}

key_calculations:
- L90D Annual Rate: {{L90D value - already annualized, use as-is}}
- L30D Annual Rate: {{L30D value or "Not provided" - already annualized, use as-is}}
- L90D Monthly Burn: {{L90D}} ÷ 12 = {{monthly}}
- Acceleration: ({{L30D}} - {{L90D}}) ÷ {{L90D}} = {{percentage}}
- Months to Overage: {{capacity}} ÷ ({{L90D}} ÷ 12) = {{months}}
- Predicted Overage: {{prediction}} - {{capacity}} = {{overage}}

tacv_derivation:
- Base Amount Source: {{what the TACV is based on - MUST be L90D or L30D consumption data, NOT FY prediction}}
- Buffer Applied: {{e.g. "+20% = $X" or "None" - explain why this buffer is appropriate}}
- Total Recommended: {{amount}} = {{show the math}}

renewal_vs_growth_split:
- Prior Renewal Base: {{amount}} (source: {{where from}})
- Renewal ACV: {{amount}} = Prior Renewal Base
- Growth ACV: {{total}} - {{prior}} = {{growth}}

assumptions_made:
- {{assumption 1}}
- {{assumption 2}}

data_gaps:
- {{missing data or "None - all key data available"}}
[/CALCULATIONS]

[RISKS]
- RISK_HIGH: {{risk}} | MITIGATION: {{how to address}}
- RISK_MEDIUM: {{risk}} | MITIGATION: {{how to address}}
[/RISKS]

[VALIDATION_NEEDED]
- PRIORITY_1: {{critical item}}
- PRIORITY_2: {{important item}}
[/VALIDATION_NEEDED]

[CONSISTENCY_CHECK]
This section validates that your recommendation is internally consistent with your data flags.

l90d_vs_prior_renewal: {{L90D is ABOVE/BELOW/ALIGNED with Prior Renewal Base by X%}}
fy_prediction_assessment: {{FY Prediction is OPTIMISTIC/CONSERVATIVE/ALIGNED vs L90D consumption}}
recommended_tacv_vs_fy_prediction: {{Recommended TACV is ABOVE/BELOW/ALIGNED with FY Prediction}}
consistency_status: {{CONSISTENT/NEEDS_EXPLANATION}}
consistency_note: {{If NEEDS_EXPLANATION: explain why your recommendation differs from what the data flags suggest. If CONSISTENT: brief confirmation that recommendation aligns with flagged concerns.}}
[/CONSISTENCY_CHECK]

---END_ANALYSIS---

IMPORTANT: Use actual dollar amounts from the account data. Show your math. Be specific. Be transparent about calculations."""

    return prompt


def parse_analysis_response(response: str) -> Dict[str, Any]:
    """Parse the structured analysis response into a dictionary with validation."""
    parsed = {
        'raw': response,
        'summary': {},
        'data_flags': [],
        'renewal_events': [],
        'options': [],
        'scenarios': {},
        'recommendation': {},
        'calculations': {},  # Transparency section
        'risks': [],
        'validation': [],
        'consistency_warnings': [],  # Track any inconsistencies found
        'consistency_check': {},  # New structured consistency validation
    }
    
    # Check if response has structured format
    if '---BEGIN_ANALYSIS---' not in response:
        parsed['parse_error'] = True
        return parsed
    
    try:
        # Extract SUMMARY section
        if '[SUMMARY]' in response and '[/SUMMARY]' in response:
            summary_text = response.split('[SUMMARY]')[1].split('[/SUMMARY]')[0]
            for line in summary_text.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    parsed['summary'][key.strip()] = value.strip()
        
        # Extract DATA_FLAGS section
        if '[DATA_FLAGS]' in response and '[/DATA_FLAGS]' in response:
            flags_text = response.split('[DATA_FLAGS]')[1].split('[/DATA_FLAGS]')[0]
            for line in flags_text.strip().split('\n'):
                if line.strip().startswith('- FLAG:'):
                    parsed['data_flags'].append(line.replace('- FLAG:', '').strip())
                elif 'None detected' in line:
                    pass  # No flags
        
        # Extract RENEWAL_EVENTS section
        if '[RENEWAL_EVENTS]' in response and '[/RENEWAL_EVENTS]' in response:
            events_text = response.split('[RENEWAL_EVENTS]')[1].split('[/RENEWAL_EVENTS]')[0]
            for line in events_text.strip().split('\n'):
                if line.strip().startswith('- EVENT:'):
                    parsed['renewal_events'].append(line.replace('- EVENT:', '').strip())
                elif line.strip().startswith('total_base_renewal:'):
                    parsed['total_base_renewal'] = line.split(':')[1].strip()
        
        # Extract OPTIONS section
        if '[OPTIONS]' in response and '[/OPTIONS]' in response:
            options_text = response.split('[OPTIONS]')[1].split('[/OPTIONS]')[0]
            for i in range(1, 5):
                if f'---OPTION_{i}---' in options_text and f'---END_OPTION_{i}---' in options_text:
                    opt_text = options_text.split(f'---OPTION_{i}---')[1].split(f'---END_OPTION_{i}---')[0]
                    opt = {}
                    for line in opt_text.strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip()
                            value = value.strip()
                            # Convert recommended field to boolean
                            if key == 'recommended':
                                opt[key] = value.upper() == 'YES'
                            else:
                                opt[key] = value
                    parsed['options'].append(opt)
        
        # Extract SCENARIOS section
        if '[SCENARIOS]' in response and '[/SCENARIOS]' in response:
            scenarios_text = response.split('[SCENARIOS]')[1].split('[/SCENARIOS]')[0]
            
            # Extract prior_renewal_base from scenarios header (before first scenario)
            if '---CONSERVATIVE---' in scenarios_text:
                header_text = scenarios_text.split('---CONSERVATIVE---')[0]
                for line in header_text.strip().split('\n'):
                    if 'prior_renewal_base:' in line.lower():
                        parsed['prior_renewal_base'] = line.split(':', 1)[1].strip()
            
            for scenario_name in ['CONSERVATIVE', 'BASE', 'STRETCH']:
                if f'---{scenario_name}---' in scenarios_text and f'---END_{scenario_name}---' in scenarios_text:
                    scen_text = scenarios_text.split(f'---{scenario_name}---')[1].split(f'---END_{scenario_name}---')[0]
                    scen = {}
                    for line in scen_text.strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            scen[key.strip()] = value.strip()
                    parsed['scenarios'][scenario_name.lower()] = scen
        
        # Extract RECOMMENDATION section
        if '[RECOMMENDATION]' in response and '[/RECOMMENDATION]' in response:
            rec_text = response.split('[RECOMMENDATION]')[1].split('[/RECOMMENDATION]')[0]
            for line in rec_text.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    parsed['recommendation'][key.strip()] = value.strip()
        
        # Extract CALCULATIONS section (transparency)
        if '[CALCULATIONS]' in response and '[/CALCULATIONS]' in response:
            calc_text = response.split('[CALCULATIONS]')[1].split('[/CALCULATIONS]')[0]
            current_section = None
            
            for line in calc_text.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # Detect section headers
                if line.endswith(':') and not line.startswith('-'):
                    current_section = line[:-1].strip()
                    parsed['calculations'][current_section] = []
                elif line.startswith('-') and current_section:
                    parsed['calculations'][current_section].append(line.lstrip('- ').strip())
                elif ':' in line and current_section:
                    parsed['calculations'][current_section].append(line.strip())
                elif current_section and line:
                    # Continuation of previous item
                    if parsed['calculations'][current_section]:
                        parsed['calculations'][current_section][-1] += ' ' + line
                    else:
                        parsed['calculations'][current_section].append(line)
        
        # Extract RISKS section
        if '[RISKS]' in response and '[/RISKS]' in response:
            risks_text = response.split('[RISKS]')[1].split('[/RISKS]')[0]
            for line in risks_text.strip().split('\n'):
                if 'RISK_HIGH:' in line or 'RISK_MEDIUM:' in line:
                    parsed['risks'].append(line.strip().lstrip('- '))
        
        # Extract VALIDATION section
        if '[VALIDATION_NEEDED]' in response and '[/VALIDATION_NEEDED]' in response:
            val_text = response.split('[VALIDATION_NEEDED]')[1].split('[/VALIDATION_NEEDED]')[0]
            for line in val_text.strip().split('\n'):
                if 'PRIORITY_' in line:
                    parsed['validation'].append(line.strip().lstrip('- '))
        
        # Extract CONSISTENCY_CHECK section
        if '[CONSISTENCY_CHECK]' in response and '[/CONSISTENCY_CHECK]' in response:
            cc_text = response.split('[CONSISTENCY_CHECK]')[1].split('[/CONSISTENCY_CHECK]')[0]
            for line in cc_text.strip().split('\n'):
                if ':' in line and not line.strip().startswith('This section'):
                    key, value = line.split(':', 1)
                    parsed['consistency_check'][key.strip()] = value.strip()
        
        # ============================================
        # VALIDATION: Basic data quality checks
        # ============================================
        # Recommended TACV now comes solely from [RECOMMENDATION] section
        # No cross-validation needed since there's no redundancy
        
        # Sync the breakdown values from recommendation if available
        if parsed['recommendation'].get('renewal_acv'):
            parsed['summary']['_validated_renewal_acv'] = parsed['recommendation']['renewal_acv']
        if parsed['recommendation'].get('growth_acv'):
            parsed['summary']['_validated_growth_acv'] = parsed['recommendation']['growth_acv']
        if parsed['recommendation'].get('total_tacv'):
            parsed['summary']['_validated_total_tacv'] = parsed['recommendation']['total_tacv']
        
        # Mark validation as performed
        parsed['_validation_performed'] = True
    
    except Exception as e:
        parsed['parse_error'] = str(e)
    
    return parsed


def call_cortex_complete(prompt: str) -> str:
    """Call Snowflake Cortex Complete for analysis generation."""
    if IS_SNOWFLAKE:
        try:
            # Using Snowflake Cortex Complete function
            # Escape single quotes in the prompt for SQL
            escaped_prompt = prompt.replace("'", "''")
            
            result = session.sql(f"""
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    '{MODEL_ANALYSIS}',
                    '{escaped_prompt}'
                ) AS response
            """).collect()
            return result[0]['RESPONSE']
        except Exception as e:
            return f"Error calling Cortex: {str(e)}"
    else:
        # For local development, return a mock response
        return generate_mock_analysis()


def generate_mock_analysis() -> str:
    """Generate a mock analysis in the structured format for local development."""
    return """---BEGIN_ANALYSIS---

[SUMMARY]
account_name: DTCC (The Depository Trust & Clearing Corporation)
account_owner: Spencer Ellingson
account_segment: Majors
contract_end_date: 1/15/2027
contract_structure: Multi-year (Year 3 of 3)
capacity_remaining: $17.6M
capacity_months: 7.8 months
projected_overage_date: August 15, 2026
action_urgency: HIGH
l90d_annual: $27.1M
l30d_annual: $35.1M
acceleration_pct: +29%
planning_fy_prediction: $63.4M
recommended_scenario: Base
confidence_level: HIGH
confidence_reason: Complete consumption data (L90D, L30D, 3-year history), clear contract structure, and consistent run rate patterns provide strong foundation for recommendation
[/SUMMARY]

[DATA_FLAGS]
- FLAG: Contract Predicted Overage field shows $149K but calculation indicates ~$8M based on consumption trajectory
- FLAG: Multi-year indicator detected - 3-year consumption ($96M) is 2.1x the contract value ($45M)
- FLAG: Acceleration of +29% detected (L30D vs L90D) - consumption accelerating
[/DATA_FLAGS]

[RENEWAL_EVENTS]
- EVENT: Capacity Overage | DATE: 4/20/2026 | AMOUNT: $15.0M | BOOKABLE: YES
- EVENT: Annual Renewal | DATE: 1/15/2027 | AMOUNT: $15.0M | BOOKABLE: YES
total_base_renewal: $30.0M
[/RENEWAL_EVENTS]

[OPTIONS]
---OPTION_1---
name: Pay Overage/Renewal Only
action: Pay overages as they occur at contract rates, renew at current base
capacity_result: TIGHT
tacv_bookable: YES
tacv_amount: $30.0M
recommended: NO
pros: Simple approach, no proactive decisions needed
cons: At risk if 29% acceleration continues, no buffer for consumption spikes
---END_OPTION_1---

---OPTION_2---
name: Pull Forward
available: NO
reason: Account is in final year (Year 3 of 3) of multi-year contract - no future capacity to pull
tacv_bookable: NO
tacv_amount: $0
recommended: NO
---END_OPTION_2---

---OPTION_3---
name: Amend Contract
action: Add $20M capacity amendment to cover acceleration through renewal
suggested_amount: $20.0M
capacity_result: SUFFICIENT
tacv_bookable: YES
tacv_amount: $35.0M
recommended: NO
pros: Addresses immediate capacity gap, sized to projected needs
cons: Partial solution - may need additional amendments if acceleration continues
---END_OPTION_3---

---OPTION_4---
name: Early Renewal
applicable: YES
reason: Consumption at 2.1x contract rate justifies right-sizing via early renewal
proposed_annual: $50.0M
tacv_bookable: YES
tacv_amount: $50.0M
recommended: YES
pros: Simplifies capacity management, provides clean TACV event, locks in pricing
cons: Large commitment (233% increase) requires executive approval
---END_OPTION_4---
[/OPTIONS]

[SCENARIOS]
prior_renewal_base: $15.0M
contract_type: Multi-year (Year 3 of 3) - Final segment, renewal is Non-Contracted

---CONSERVATIVE---
renewal_acv: $15.0M
contracted_renewal: $0
non_contracted_renewal: $15.0M
growth_acv: $15.0M
contracted_growth: $0
non_contracted_growth: $15.0M
total_tacv: $30.0M
quota_bearing: $30.0M
confidence: MEDIUM
basis: Standard overage + renewal only ($30M), assumes no proactive upsizing. Would leave account capacity-constrained given +29% acceleration.
---END_CONSERVATIVE---

---BASE---
renewal_acv: $15.0M
contracted_renewal: $0
non_contracted_renewal: $15.0M
growth_acv: $35.0M
contracted_growth: $0
non_contracted_growth: $35.0M
total_tacv: $50.0M
quota_bearing: $50.0M
confidence: HIGH
basis: Early renewal at $50M/year right-sizes for 2.1x overconsumption. Aligns with L90D annualized ($27M) plus buffer for acceleration. Best fit for current trajectory.
---END_BASE---

---STRETCH---
renewal_acv: $15.0M
contracted_renewal: $0
non_contracted_renewal: $15.0M
growth_acv: $45.0M
contracted_growth: $0
non_contracted_growth: $45.0M
total_tacv: $60.0M
quota_bearing: $60.0M
confidence: MEDIUM-HIGH
basis: Accounts for full FY27 prediction of $63M if acceleration continues. Would require validation of sustained growth beyond current trends.
---END_STRETCH---
[/SCENARIOS]

[RECOMMENDATION]
scenario: Base
total_tacv: $50.0M
renewal_acv: $15.0M
contracted_renewal: $0
non_contracted_renewal: $15.0M
growth_acv: $35.0M
contracted_growth: $0
non_contracted_growth: $35.0M
quota_bearing_tacv: $50.0M
non_quota_tacv: $0
prior_renewal_base: $15.0M
growth_calculation: $50.0M Total TACV - $15.0M Prior Renewal Base = $35.0M Growth ACV
headline: Recommend early renewal at $50M to right-size the contract for actual consumption patterns. The account is consuming at 2.1x the current $15M contract value, with L90D annualized at $27M and accelerating +29% to $35M L30D. This proactive approach avoids costly overage penalties, provides capacity runway through FY27, and creates a clean TACV booking event.
why_this_scenario: Base is the best fit because the +29% acceleration (L30D vs L90D) is significant but not extreme. The consumption pattern is clear and stable enough to project with confidence, but not accelerating fast enough to warrant Stretch. Conservative would leave the account in overage within 6 months.
why_this_number: • Sized to cover L90D annualized consumption of $27M with 85% buffer for acceleration • Aligns with FY27 consumption prediction of $63M with room for variability • 233% increase from $15M reflects actual usage patterns, not arbitrary uplift
alternative_scenario: Consider Stretch ($60M) if customer confirms additional expansion plans or if L30D acceleration continues for another quarter. Conservative ($30M) would only be appropriate if customer signals budget constraints or usage reduction.
[/RECOMMENDATION]

[CALCULATIONS]
This section provides transparency into how the TACV was calculated.

data_sources:
- Account Name: DTCC | SOURCE: Provided
- Contract End: 1/15/2027 | SOURCE: Provided
- Capacity Remaining: $17.6M | SOURCE: Provided
- L90D Annual Rate: $27.1M | SOURCE: Provided (already annualized)
- L30D Annual Rate: $35.1M | SOURCE: Provided (already annualized)
- Prior Renewal Base: $15.0M | SOURCE: Provided
- FY27 Prediction: $63.4M | SOURCE: Provided

key_calculations:
- L90D Annual Rate: $27.1M (provided as annualized value)
- L30D Annual Rate: $35.1M (provided as annualized value)
- L90D Monthly Burn: $27.1M ÷ 12 = $2.26M/month
- L30D Monthly Burn: $35.1M ÷ 12 = $2.93M/month
- Acceleration: ($35.1M - $27.1M) ÷ $27.1M = +29%
- Months to Overage: $17.6M ÷ $2.26M = 7.8 months at L90D burn
- Months to Overage: $17.6M ÷ $2.93M = 6.0 months at L30D burn

tacv_derivation:
- Base Amount Source: L90D annualized of $27.1M as consumption baseline
- Buffer Applied: +85% buffer to account for +29% acceleration trend (L30D at $35.1M) = $50M
- Sizing Rationale: Midpoint between L90D ($27M) and L30D ($35M) with headroom for continued growth
- Total Recommended: $50.0M = L90D base ($27M) + acceleration buffer (~$23M)

renewal_vs_growth_split:
- Prior Renewal Base: $15.0M (source: Provided data)
- New Contract Value: $50.0M (recommended TACV)
- Renewal ACV: $15.0M = Prior Renewal Base (carrying forward)
- Growth ACV: $50.0M - $15.0M = $35.0M (increase over prior)

assumptions_made:
- Assumed L90D burn rate of $27.1M continues as baseline consumption
- Assumed +29% acceleration (L30D vs L90D) indicates sustained growth trend
- FY27 prediction of $63.4M noted but NOT used as primary sizing input (data science predictions can be unreliable)
- Assumed customer will engage on early renewal given overage magnitude

data_gaps:
- None - all key data points were available for this analysis
[/CALCULATIONS]

[RISKS]
- RISK_HIGH: Customer budget approval - 233% increase from $15M to $50M requires executive buy-in | MITIGATION: Build business case showing consumption trajectory and cost of alternatives
- RISK_MEDIUM: Consumption exceeds $63M prediction - may need mid-year amendment | MITIGATION: Monitor consumption monthly, have amendment ready if needed
[/RISKS]

[VALIDATION_NEEDED]
- PRIORITY_1: Confirm contract structure and total capacity pool with deal desk
- PRIORITY_2: Understand FY27 prediction drivers - 338% YoY growth is extraordinary, validate with AE
[/VALIDATION_NEEDED]

[CONSISTENCY_CHECK]
This section validates that your recommendation is internally consistent with your data flags.

l90d_vs_prior_renewal: L90D ($27.1M) is ABOVE Prior Renewal Base ($15.0M) by 81%
fy_prediction_assessment: FY Prediction ($63.4M) is OPTIMISTIC vs L90D consumption ($27.1M) by 134%
recommended_tacv_vs_fy_prediction: Recommended TACV ($50.0M) is BELOW FY Prediction ($63.4M) by 21%
consistency_status: CONSISTENT
consistency_note: Recommendation of $50M is below the optimistic FY Prediction of $63.4M, aligning with the data flag that predictions may be unreliable. The recommendation is instead anchored to actual consumption (L90D/L30D) with appropriate growth buffer for the +29% acceleration trend.
[/CONSISTENCY_CHECK]

---END_ANALYSIS---"""


# ============================================
# BULK SUMMARY EXTRACTION
# ============================================

def extract_bulk_summary(parsed_analysis: Dict[str, Any], row_fields: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key metrics from parsed analysis for bulk results table."""
    summary = parsed_analysis.get('summary', {})
    recommendation = parsed_analysis.get('recommendation', {})

    flags = parsed_analysis.get('data_flags', [])
    flags_str = ', '.join(flags[:3]) if flags and flags != ['None detected'] else 'None'

    headline = recommendation.get('headline', '')
    if len(headline) > 250:
        headline = headline[:247] + '...'

    return {
        'Account Name': row_fields.get('account_name', summary.get('account_name', 'Unknown')),
        'Contract End': summary.get('contract_end_date', row_fields.get('contract_end_date', 'N/A')),
        'Overage Date': summary.get('projected_overage_date', 'N/A'),
        'Urgency': summary.get('action_urgency', 'N/A'),
        'Recommended Scenario': summary.get('recommended_scenario', recommendation.get('scenario', 'N/A')),
        'Total TACV': recommendation.get('total_tacv', 'N/A'),
        'Renewal ACV': recommendation.get('renewal_acv', 'N/A'),
        'Growth ACV': recommendation.get('growth_acv', 'N/A'),
        'Quota-Bearing TACV': recommendation.get('quota_bearing_tacv', 'N/A'),
        'Non-Quota TACV': recommendation.get('non_quota_tacv', '$0'),
        'Confidence': summary.get('confidence_level', 'N/A'),
        'Key Flags': flags_str,
        'Rationale': headline,
        '_raw_analysis': parsed_analysis.get('raw', ''),
        '_parse_error': parsed_analysis.get('parse_error', False),
    }
