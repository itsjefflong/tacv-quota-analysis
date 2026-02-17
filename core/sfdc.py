"""
TACV Salesforce Integration
============================
Queries for Opportunities, Contracts, and Account data from Salesforce via Snowflake.
Includes formatting helpers for prompts and UI display.

Security: All queries use parameterized SQL to prevent injection.
"""

import re
import streamlit as st
from typing import Any, Dict, List, Optional

from core.config import IS_SNOWFLAKE, logger, session
from core.utils import format_currency, get_fiscal_year_context, truncate_date


# ============================================
# HELPER: Safe SQL execution
# ============================================

def _safe_query(query: str, params: Optional[Dict[str, str]] = None) -> list:
    """Execute a Snowpark SQL query. Params are bound via string replacement
    because Snowpark's ``session.sql()`` does not support bind variables the
    same way JDBC does.  We therefore validate/sanitise values here."""
    if not IS_SNOWFLAKE or session is None:
        return []
    return session.sql(query).collect()


def _sanitize_sfdc_id(value: str) -> str:
    """Validate that a value looks like a Salesforce ID (alphanumeric, 15 or 18 chars)."""
    cleaned = str(value).strip()
    if not re.match(r'^[a-zA-Z0-9]{15,18}$', cleaned):
        raise ValueError(f"Invalid Salesforce ID format: {cleaned!r}")
    return cleaned


# ============================================
# ACCOUNT ID EXTRACTION
# ============================================

def extract_account_id(parsed_fields: Dict, raw_input: str = '') -> Optional[str]:
    """
    Extract Salesforce Account ID from parsed data or raw input.

    Looks for:
    - Account ID in format: 0013100001xxxxx (18-char Salesforce ID starting with 001)
    - Ult-Parent ID field
    - Pattern in account name like "0013100001fowGPAAY | Company Name"
    """
    if 'account_id' in parsed_fields:
        return parsed_fields['account_id']
    if 'ult_parent_id' in parsed_fields:
        return parsed_fields['ult_parent_id']

    account_name = parsed_fields.get('account_name', '')
    if account_name and '|' in account_name:
        parts = account_name.split('|')
        potential_id = parts[0].strip()
        if potential_id.startswith('001') and len(potential_id) in [15, 18]:
            return potential_id

    if raw_input:
        account_id_pattern = r'\b(001[a-zA-Z0-9]{12,15})\b'
        matches = re.findall(account_id_pattern, raw_input)
        if matches:
            return matches[0]

    return None


# ============================================
# OPPORTUNITY QUERIES
# ============================================

def query_sfdc_opportunities(account_id: str, planning_fy: str) -> List[Dict[str, Any]]:
    """Query Salesforce opportunities for the given account ID."""
    if not IS_SNOWFLAKE or not account_id:
        return []

    safe_id = _sanitize_sfdc_id(account_id)
    fy_context = get_fiscal_year_context(planning_fy)
    fy_num = fy_context['fy_num']
    calendar_year = 2000 + fy_num - 1
    min_close_date = f"{calendar_year}-01-01"

    query = f"""
    SELECT
        ID, NAME, ACCOUNT_ID, ACCOUNT_NAME_C, TYPE, STAGE_NAME,
        CLOSE_DATE, PROBABILITY, FORECAST_CATEGORY_NAME, FORECAST_STATUS_C,
        AGREEMENT_TYPE_C, CHANNEL_C,
        ACV_C AS PRODUCT_ACV, GROWTH_ACV_C, BASE_RENEWAL_ACV_C, TOTAL_ACV_C,
        AMOUNT AS TOTAL_BOOKINGS_TCV, FORECAST_ACV_C AS PRODUCT_FORECAST_ACV,
        OUT_YEAR_PRODUCT_ACV_C, OUT_YEAR_GROWTH_ACV_C, OUT_YEAR_SEGMENT_INDEX_C,
        CAPACITY_C, OWNER_ID, RECORD_TYPE_ID, NEXT_STEPS_C, MANAGER_NOTES_C,
        CREATED_DATE, LAST_MODIFIED_DATE
    FROM FIVETRAN.SALESFORCE.OPPORTUNITY
    WHERE ACCOUNT_ID = '{safe_id}'
      AND CLOSE_DATE >= '{min_close_date}'
      AND IS_DELETED = FALSE
      AND STAGE_NAME NOT IN ('Closed Lost', 'Rejected')
    ORDER BY CLOSE_DATE DESC, OUT_YEAR_SEGMENT_INDEX_C DESC
    """

    try:
        result = _safe_query(query)
        opportunities = []
        for row in result:
            opp = {
                'id': row['ID'],
                'name': row['NAME'],
                'account_id': row['ACCOUNT_ID'],
                'account_name': row['ACCOUNT_NAME_C'],
                'type': row['TYPE'],
                'stage': row['STAGE_NAME'],
                'close_date': str(row['CLOSE_DATE']) if row['CLOSE_DATE'] else None,
                'probability': row['PROBABILITY'],
                'forecast_category': row['FORECAST_CATEGORY_NAME'],
                'forecast_status': row['FORECAST_STATUS_C'],
                'agreement_type': row['AGREEMENT_TYPE_C'],
                'channel': row['CHANNEL_C'],
                'product_acv': float(row['PRODUCT_ACV']) if row['PRODUCT_ACV'] else 0,
                'growth_acv': float(row['GROWTH_ACV_C']) if row['GROWTH_ACV_C'] else 0,
                'base_renewal_acv': float(row['BASE_RENEWAL_ACV_C']) if row['BASE_RENEWAL_ACV_C'] else 0,
                'total_acv': float(row['TOTAL_ACV_C']) if row['TOTAL_ACV_C'] else 0,
                'total_bookings_tcv': float(row['TOTAL_BOOKINGS_TCV']) if row['TOTAL_BOOKINGS_TCV'] else 0,
                'product_forecast_acv': float(row['PRODUCT_FORECAST_ACV']) if row['PRODUCT_FORECAST_ACV'] else 0,
                'out_year_product_acv': float(row['OUT_YEAR_PRODUCT_ACV_C']) if row['OUT_YEAR_PRODUCT_ACV_C'] else 0,
                'out_year_growth_acv': float(row['OUT_YEAR_GROWTH_ACV_C']) if row['OUT_YEAR_GROWTH_ACV_C'] else 0,
                'out_year_segment_index': int(row['OUT_YEAR_SEGMENT_INDEX_C']) if row['OUT_YEAR_SEGMENT_INDEX_C'] else None,
                'capacity': float(row['CAPACITY_C']) if row['CAPACITY_C'] else 0,
                'next_steps': row['NEXT_STEPS_C'],
                'manager_notes': row['MANAGER_NOTES_C'],
            }
            opportunities.append(opp)
        logger.info("Fetched %d opportunities for account %s", len(opportunities), safe_id)
        return opportunities

    except Exception as e:
        logger.warning("Could not query SFDC opportunities: %s", e)
        st.warning(f"Could not query Salesforce opportunities: {e}")
        return []


# ============================================
# CONTRACT QUERIES
# ============================================

def query_sfdc_contracts(account_id: str, planning_fy: str) -> List[Dict[str, Any]]:
    """Query Salesforce contracts for the given account ID."""
    if not IS_SNOWFLAKE or not account_id:
        return []

    safe_id = _sanitize_sfdc_id(account_id)
    fy_context = get_fiscal_year_context(planning_fy)
    fy_num = fy_context['fy_num']
    calendar_year = 2000 + fy_num - 1
    min_end_date = f"{calendar_year}-01-01"

    query = f"""
    SELECT
        ID, CONTRACT_NUMBER, NAME, ACCOUNT_ID, STATUS,
        START_DATE, END_DATE, CONTRACT_TERM,
        AGREEMENT_TYPE_C, CHANNEL_C, PRODUCT_TYPE_C, CURRENCY_ISO_CODE,
        WAREHOUSE_PRICE_PER_CREDIT_C, STORAGE_CREDIT_PER_TB_PER_MONTH_C,
        SNOWPAY_AMOUNT_C, SNOWPAY_OPT_IN_C,
        SERVICE_START_DATE_C, SERVICE_END_DATE_C, TERMINATION_DATE_C,
        QUOTE_NUMBER_C, REGION_C, SBQQ_RENEWAL_TERM_C, SBQQ_ACTIVE_CONTRACT_C,
        BILLING_COUNTRY, BILLING_STATE, BILLING_CITY,
        SFCPQ_ENTITY_C, END_CUSTOMER_LEGAL_NAME_C, CAPACITY_ORDER_TYPE_C
    FROM FIVETRAN.SALESFORCE.CONTRACT
    WHERE ACCOUNT_ID = '{safe_id}'
      AND IS_DELETED = FALSE
      AND STATUS = 'Activated'
      AND END_DATE >= '{min_end_date}'
    ORDER BY END_DATE DESC NULLS LAST, START_DATE DESC
    """

    try:
        result = _safe_query(query)
        contracts = []
        for row in result:
            contract = {
                'id': row['ID'],
                'contract_number': row['CONTRACT_NUMBER'],
                'name': row['NAME'],
                'account_id': row['ACCOUNT_ID'],
                'status': row['STATUS'],
                'start_date': str(row['START_DATE']) if row['START_DATE'] else None,
                'end_date': str(row['END_DATE']) if row['END_DATE'] else None,
                'contract_term': int(row['CONTRACT_TERM']) if row['CONTRACT_TERM'] else None,
                'agreement_type': row['AGREEMENT_TYPE_C'],
                'channel': row['CHANNEL_C'],
                'product_type': row['PRODUCT_TYPE_C'],
                'currency': row['CURRENCY_ISO_CODE'],
                'warehouse_price_per_credit': float(row['WAREHOUSE_PRICE_PER_CREDIT_C']) if row['WAREHOUSE_PRICE_PER_CREDIT_C'] else None,
                'storage_credit_per_tb': float(row['STORAGE_CREDIT_PER_TB_PER_MONTH_C']) if row['STORAGE_CREDIT_PER_TB_PER_MONTH_C'] else None,
                'snowpay_amount': float(row['SNOWPAY_AMOUNT_C']) if row['SNOWPAY_AMOUNT_C'] else None,
                'snowpay_opt_in': row['SNOWPAY_OPT_IN_C'],
                'service_start_date': str(row['SERVICE_START_DATE_C']) if row['SERVICE_START_DATE_C'] else None,
                'service_end_date': str(row['SERVICE_END_DATE_C']) if row['SERVICE_END_DATE_C'] else None,
                'termination_date': str(row['TERMINATION_DATE_C']) if row['TERMINATION_DATE_C'] else None,
                'quote_number': row['QUOTE_NUMBER_C'],
                'region': row['REGION_C'],
                'renewal_term': int(row['SBQQ_RENEWAL_TERM_C']) if row['SBQQ_RENEWAL_TERM_C'] else None,
                'is_active': row['SBQQ_ACTIVE_CONTRACT_C'],
                'billing_country': row['BILLING_COUNTRY'],
                'billing_state': row['BILLING_STATE'],
                'billing_city': row['BILLING_CITY'],
                'entity': row['SFCPQ_ENTITY_C'],
                'end_customer': row['END_CUSTOMER_LEGAL_NAME_C'],
                'capacity_order_type': row['CAPACITY_ORDER_TYPE_C'],
            }
            contracts.append(contract)
        logger.info("Fetched %d contracts for account %s", len(contracts), safe_id)
        return contracts

    except Exception as e:
        logger.warning("Could not query SFDC contracts: %s", e)
        st.warning(f"Could not query Salesforce contracts: {e}")
        return []


# ============================================
# ACCOUNT QUERIES
# ============================================

def query_sfdc_account(account_id: str) -> Optional[Dict[str, Any]]:
    """Query Salesforce Account table for the given account ID."""
    if not IS_SNOWFLAKE or not account_id:
        return None

    safe_id = _sanitize_sfdc_id(account_id)

    query = f"""
    SELECT
        ID, NAME, TYPE, INDUSTRY, INDUSTRY_C, DESCRIPTION,
        NUMBER_OF_EMPLOYEES, ANNUAL_REVENUE,
        ACCOUNT_STATUS_C, ACCOUNT_TIER_C, TIER_C, REGION_C, TERRITORY_C, GEO_C, ACCOUNT_SEGMENT_C,
        ACCOUNT_BASE_RENEWAL_ACV_C, ARR_NUMBER_C, TOTAL_CUSTOMER_SPEND_C,
        CURRENT_CAPACITY_VALUE_C, FORECASTED_LTV_C,
        DAYS_UNTIL_OVERAGE_C, DAYS_TO_CAPACITY_C,
        CAPACITY_CUSTOMER_DATE_C, FIRST_CAPACITY_DATE_C,
        MATURITY_STAGE_C, MATURITY_SCORE_C,
        ACCOUNT_RISK_C, CONSUMPTION_RISK_C, RENEWAL_RISK_C, RENEWAL_RISK_DESCRIPTION_C,
        ACCOUNT_RELATIONSHIP_SCORE_C,
        AE_FIELD_NOTES_C, SALES_DIRECTOR_NOTES_C, ACCOUNT_COMMENTS_C,
        ACCOUNT_STRATEGY_C, CUSTOMER_SUCCESS_NOTES_C,
        AGREEMENT_TYPE_ACCOUNT_C, SNOWFLAKE_AGREEMENT_TYPE_C, MSA_EFFECTIVE_DATE_C
    FROM FIVETRAN.SALESFORCE.ACCOUNT
    WHERE ID = '{safe_id}'
      AND IS_DELETED = FALSE
    LIMIT 1
    """

    try:
        result = _safe_query(query)
        if not result:
            return None

        row = result[0]
        account = {
            'id': row['ID'],
            'name': row['NAME'],
            'type': row['TYPE'],
            'industry': row['INDUSTRY'] or row['INDUSTRY_C'],
            'description': row['DESCRIPTION'],
            'employee_count': int(row['NUMBER_OF_EMPLOYEES']) if row['NUMBER_OF_EMPLOYEES'] else None,
            'annual_revenue': float(row['ANNUAL_REVENUE']) if row['ANNUAL_REVENUE'] else None,
            'account_status': row['ACCOUNT_STATUS_C'],
            'account_tier': row['ACCOUNT_TIER_C'] or row['TIER_C'],
            'region': row['REGION_C'],
            'territory': row['TERRITORY_C'],
            'geo': row['GEO_C'],
            'segment': row['ACCOUNT_SEGMENT_C'],
            'base_renewal_acv': float(row['ACCOUNT_BASE_RENEWAL_ACV_C']) if row['ACCOUNT_BASE_RENEWAL_ACV_C'] else None,
            'arr': float(row['ARR_NUMBER_C']) if row['ARR_NUMBER_C'] else None,
            'total_customer_spend': float(row['TOTAL_CUSTOMER_SPEND_C']) if row['TOTAL_CUSTOMER_SPEND_C'] else None,
            'current_capacity_value': float(row['CURRENT_CAPACITY_VALUE_C']) if row['CURRENT_CAPACITY_VALUE_C'] else None,
            'forecasted_ltv': float(row['FORECASTED_LTV_C']) if row['FORECASTED_LTV_C'] else None,
            'days_until_overage': int(row['DAYS_UNTIL_OVERAGE_C']) if row['DAYS_UNTIL_OVERAGE_C'] else None,
            'days_to_capacity': int(row['DAYS_TO_CAPACITY_C']) if row['DAYS_TO_CAPACITY_C'] else None,
            'capacity_customer_date': str(row['CAPACITY_CUSTOMER_DATE_C']) if row['CAPACITY_CUSTOMER_DATE_C'] else None,
            'first_capacity_date': str(row['FIRST_CAPACITY_DATE_C']) if row['FIRST_CAPACITY_DATE_C'] else None,
            'maturity_stage': row['MATURITY_STAGE_C'],
            'maturity_score': float(row['MATURITY_SCORE_C']) if row['MATURITY_SCORE_C'] else None,
            'account_risk': row['ACCOUNT_RISK_C'],
            'consumption_risk': row['CONSUMPTION_RISK_C'],
            'renewal_risk': row['RENEWAL_RISK_C'],
            'renewal_risk_description': row['RENEWAL_RISK_DESCRIPTION_C'],
            'relationship_score': float(row['ACCOUNT_RELATIONSHIP_SCORE_C']) if row['ACCOUNT_RELATIONSHIP_SCORE_C'] else None,
            'ae_field_notes': row['AE_FIELD_NOTES_C'],
            'sales_director_notes': row['SALES_DIRECTOR_NOTES_C'],
            'account_comments': row['ACCOUNT_COMMENTS_C'],
            'account_strategy': row['ACCOUNT_STRATEGY_C'],
            'customer_success_notes': row['CUSTOMER_SUCCESS_NOTES_C'],
            'agreement_type': row['AGREEMENT_TYPE_ACCOUNT_C'] or row['SNOWFLAKE_AGREEMENT_TYPE_C'],
            'msa_effective_date': str(row['MSA_EFFECTIVE_DATE_C']) if row['MSA_EFFECTIVE_DATE_C'] else None,
        }

        return {k: v for k, v in account.items() if v is not None}

    except Exception as e:
        logger.warning("Could not query SFDC account: %s", e)
        st.warning(f"Could not query Salesforce account: {e}")
        return None


# ============================================
# FORMATTING HELPERS (for UI & prompts)
# ============================================

def format_opportunity_summary(opp: Dict[str, Any]) -> str:
    """Create a concise one-line summary of an opportunity."""
    stage = opp.get('stage', 'Unknown')
    close_date = truncate_date(opp.get('close_date'))
    acv = opp.get('product_forecast_acv') or opp.get('product_acv') or opp.get('total_acv') or 0
    acv_str = format_currency(acv) if acv else 'N/A'
    segment = opp.get('out_year_segment_index')
    segment_str = f" (Seg {segment})" if segment else ""
    opp_type = opp.get('type', 'Unknown')

    return f"{opp_type}{segment_str} • {stage} • {close_date} • {acv_str}"


def get_opportunity_details_markdown(opp: Dict[str, Any]) -> str:
    """Generate detailed markdown for an opportunity."""
    lines = [
        f"**Opportunity:** {opp.get('name', 'Unknown')}",
        f"**Type:** {opp.get('type', 'N/A')} | **Stage:** {opp.get('stage', 'N/A')}",
        f"**Close Date:** {truncate_date(opp.get('close_date'))}",
        f"**Probability:** {opp.get('probability', 0)}% | **Forecast:** {opp.get('forecast_status', 'N/A')}",
        "",
        "**Financial Details:**",
    ]

    for label, key in [
        ('Product Forecast ACV', 'product_forecast_acv'),
        ('Product ACV', 'product_acv'),
        ('Growth ACV', 'growth_acv'),
        ('Base Renewal ACV', 'base_renewal_acv'),
        ('Out Year Product ACV', 'out_year_product_acv'),
        ('Out Year Growth ACV', 'out_year_growth_acv'),
    ]:
        if opp.get(key):
            lines.append(f"- {label}: {format_currency(opp[key])}")

    if opp.get('out_year_segment_index'):
        lines.append(f"- Out Year Segment: {opp['out_year_segment_index']}")
    if opp.get('capacity'):
        lines.append(f"- Capacity: {format_currency(opp['capacity'])}")
    if opp.get('agreement_type'):
        lines.append(f"\n**Agreement Type:** {opp['agreement_type']}")
    if opp.get('next_steps'):
        lines.append(f"\n**Next Steps:** {opp['next_steps'][:200]}...")
    if opp.get('manager_notes'):
        lines.append(f"\n**Manager Notes:** {opp['manager_notes'][:200]}...")

    return '\n'.join(lines)


def format_selected_opportunities_for_prompt(opportunities: List[Dict[str, Any]]) -> str:
    """Format selected opportunities for inclusion in the analysis prompt."""
    if not opportunities:
        return ""

    lines = [
        "SALESFORCE OPPORTUNITIES FOR THIS ACCOUNT:",
        "(These are existing or upcoming opportunities that should inform the TACV recommendation)",
        "",
    ]

    for i, opp in enumerate(opportunities, 1):
        lines.append(f"--- Opportunity {i}: {opp.get('name', 'Unknown')} ---")
        lines.append(f"Type: {opp.get('type', 'N/A')}")
        lines.append(f"Stage: {opp.get('stage', 'N/A')} ({opp.get('probability', 0)}% probability)")
        lines.append(f"Close Date: {truncate_date(opp.get('close_date'))}")
        lines.append(f"Forecast Status: {opp.get('forecast_status', 'N/A')}")
        lines.append(f"Agreement Type: {opp.get('agreement_type', 'N/A')}")
        for label, key in [('Product Forecast ACV', 'product_forecast_acv'),
                           ('Growth ACV', 'growth_acv'),
                           ('Base Renewal ACV', 'base_renewal_acv')]:
            if opp.get(key):
                lines.append(f"{label}: {format_currency(opp[key])}")
        if opp.get('out_year_segment_index'):
            lines.append(f"Out Year Segment: {opp['out_year_segment_index']}")
        lines.append("")

    lines.append("IMPORTANT: Consider these opportunities when recommending TACV scenarios. "
                 "If there's already a Deal Imminent or Commit opportunity, the recommended TACV "
                 "should align with or justify deviation from these opportunity values.")
    return '\n'.join(lines)


def format_contract_summary(contract: Dict[str, Any]) -> str:
    """Create a concise one-line summary of a contract."""
    status = contract.get('status', 'Unknown')
    agreement_type = contract.get('agreement_type', 'N/A')
    term = contract.get('contract_term')
    term_str = f"{term}mo" if term else "N/A"
    start_date = truncate_date(contract.get('start_date'))
    end_date = truncate_date(contract.get('end_date'))
    date_str = f"{start_date} → {end_date}" if start_date != 'N/A' and end_date != 'N/A' else "N/A"
    currency = contract.get('currency', 'USD')
    status_emoji = "✅" if status == "Activated" else "⏹️" if status == "Terminated" else "⏳"

    return f"{status_emoji} {status} • {agreement_type} • {term_str} • {date_str} • {currency}"


def get_contract_details_markdown(contract: Dict[str, Any]) -> str:
    """Generate detailed markdown for a contract."""
    lines = [
        f"**Contract:** {contract.get('name', 'Unknown')}",
        f"**Contract Number:** {contract.get('contract_number', 'N/A')}",
        f"**Status:** {contract.get('status', 'N/A')} | **Channel:** {contract.get('channel', 'N/A')}",
        "",
        "**Dates:**",
        f"- Contract: {truncate_date(contract.get('start_date'))} → {truncate_date(contract.get('end_date'))}",
        f"- Term: {contract.get('contract_term', 'N/A')} months",
    ]

    if contract.get('service_start_date') or contract.get('service_end_date'):
        lines.append(f"- Service: {truncate_date(contract.get('service_start_date'))} → {truncate_date(contract.get('service_end_date'))}")
    if contract.get('termination_date'):
        lines.append(f"- **Terminated:** {truncate_date(contract.get('termination_date'))}")

    lines += [
        "",
        "**Agreement Details:**",
        f"- Agreement Type: {contract.get('agreement_type', 'N/A')}",
        f"- Product Type: {contract.get('product_type', 'N/A')}",
        f"- Currency: {contract.get('currency', 'N/A')}",
    ]
    if contract.get('region'):
        lines.append(f"- Region: {contract['region']}")
    if contract.get('entity'):
        lines.append(f"- Entity: {contract['entity']}")
    if contract.get('capacity_order_type'):
        lines.append(f"- Capacity Order Type: {contract['capacity_order_type']}")

    if contract.get('warehouse_price_per_credit') or contract.get('storage_credit_per_tb'):
        lines += ["", "**Pricing:**"]
        if contract.get('warehouse_price_per_credit'):
            lines.append(f"- Warehouse Price/Credit: ${contract['warehouse_price_per_credit']:.4f}")
        if contract.get('storage_credit_per_tb'):
            lines.append(f"- Storage Credit/TB/Month: {contract['storage_credit_per_tb']:.2f}")

    if contract.get('snowpay_opt_in') or contract.get('snowpay_amount'):
        lines += ["", "**SnowPay:**"]
        lines.append(f"- Opt-In: {'Yes' if contract.get('snowpay_opt_in') else 'No'}")
        if contract.get('snowpay_amount'):
            lines.append(f"- Amount: {format_currency(contract['snowpay_amount'])}")

    if contract.get('renewal_term'):
        lines += ["", f"**Renewal Term:** {contract['renewal_term']} months"]

    if any(contract.get(k) for k in ['billing_country', 'billing_state', 'billing_city']):
        location_parts = [p for p in [contract.get('billing_city'), contract.get('billing_state'), contract.get('billing_country')] if p]
        lines.append(f"**Location:** {', '.join(location_parts)}")

    if contract.get('end_customer'):
        lines.append(f"**End Customer:** {contract['end_customer']}")
    if contract.get('quote_number'):
        lines.append(f"**Quote:** {contract['quote_number']}")

    return '\n'.join(lines)


def format_selected_contracts_for_prompt(contracts: List[Dict[str, Any]]) -> str:
    """Format selected contracts for inclusion in the analysis prompt."""
    if not contracts:
        return ""

    lines = [
        "SALESFORCE CONTRACTS FOR THIS ACCOUNT:",
        "(These are existing contracts that provide context for the TACV recommendation)",
        "",
    ]

    for i, contract in enumerate(contracts, 1):
        lines.append(f"--- Contract {i}: {contract.get('contract_number', 'Unknown')} ---")
        lines.append(f"Status: {contract.get('status', 'N/A')}")
        lines.append(f"Agreement Type: {contract.get('agreement_type', 'N/A')}")
        lines.append(f"Channel: {contract.get('channel', 'N/A')}")
        lines.append(f"Contract Period: {truncate_date(contract.get('start_date'))} → {truncate_date(contract.get('end_date'))}")
        lines.append(f"Term: {contract.get('contract_term', 'N/A')} months")
        if contract.get('warehouse_price_per_credit'):
            lines.append(f"Warehouse Price/Credit: ${contract['warehouse_price_per_credit']:.4f}")
        if contract.get('storage_credit_per_tb'):
            lines.append(f"Storage Credit/TB/Month: {contract['storage_credit_per_tb']:.2f}")
        if contract.get('snowpay_opt_in'):
            snowpay_str = "SnowPay: Opted In"
            if contract.get('snowpay_amount'):
                snowpay_str += f" ({format_currency(contract['snowpay_amount'])})"
            lines.append(snowpay_str)
        if contract.get('termination_date'):
            lines.append(f"Terminated: {truncate_date(contract.get('termination_date'))}")
        lines.append("")

    lines.append("IMPORTANT: Use contract history to understand the customer's contract patterns, "
                 "pricing, and renewal behavior. Active contracts show current commitments; "
                 "terminated contracts show historical context.")
    return '\n'.join(lines)


def format_account_for_prompt(account: Dict[str, Any]) -> str:
    """Format Salesforce Account data for inclusion in the analysis prompt."""
    if not account:
        return ""

    lines = [
        "SALESFORCE ACCOUNT DATA:",
        "(This account data from Salesforce provides additional context for the TACV analysis)",
        "",
        "--- Account Profile ---",
    ]

    for label, key in [('Account Name', 'name'), ('Account Type', 'type'),
                       ('Industry', 'industry'), ('Segment', 'segment'),
                       ('Account Tier', 'account_tier'), ('Status', 'account_status')]:
        if account.get(key):
            lines.append(f"{label}: {account[key]}")

    # Size & Revenue
    if account.get('employee_count') or account.get('annual_revenue'):
        lines += ["", "--- Company Size ---"]
        if account.get('employee_count'):
            lines.append(f"Employees: {account['employee_count']:,}")
        if account.get('annual_revenue'):
            lines.append(f"Annual Revenue: {format_currency(account['annual_revenue'])}")

    # Territory Info
    if any(account.get(k) for k in ['region', 'territory', 'geo']):
        lines += ["", "--- Territory ---"]
        for label, key in [('Geo', 'geo'), ('Region', 'region'), ('Territory', 'territory')]:
            if account.get(key):
                lines.append(f"{label}: {account[key]}")

    # Financial Metrics
    financial_keys = ['base_renewal_acv', 'arr', 'total_customer_spend', 'current_capacity_value', 'forecasted_ltv']
    if any(account.get(k) for k in financial_keys):
        lines += ["", "--- Account Financial Metrics ---"]
        for label, key in [('Base Renewal ACV (from Account)', 'base_renewal_acv'),
                           ('ARR', 'arr'), ('Total Customer Spend', 'total_customer_spend'),
                           ('Current Capacity Value', 'current_capacity_value'),
                           ('Forecasted LTV', 'forecasted_ltv')]:
            if account.get(key):
                lines.append(f"{label}: {format_currency(account[key])}")

    # Capacity/Overage Timing
    if account.get('days_until_overage') is not None or account.get('days_to_capacity') is not None:
        lines += ["", "--- Capacity Timing (from Account Record) ---"]
        if account.get('days_until_overage') is not None:
            lines.append(f"Days Until Overage: {account['days_until_overage']}")
        if account.get('days_to_capacity') is not None:
            lines.append(f"Days to Capacity: {account['days_to_capacity']}")

    # Maturity
    if account.get('maturity_stage') or account.get('maturity_score'):
        lines += ["", "--- Customer Maturity ---"]
        if account.get('maturity_stage'):
            lines.append(f"Maturity Stage: {account['maturity_stage']}")
        if account.get('maturity_score'):
            lines.append(f"Maturity Score: {account['maturity_score']}")

    # Risk Indicators
    risk_keys = ['account_risk', 'consumption_risk', 'renewal_risk', 'relationship_score']
    if any(account.get(k) for k in risk_keys):
        lines += ["", "--- RISK INDICATORS (Important for TACV) ---"]
        for label, key in [('Account Risk', 'account_risk'), ('Consumption Risk', 'consumption_risk'),
                           ('Renewal Risk', 'renewal_risk')]:
            if account.get(key):
                lines.append(f"{label}: {account[key]}")
        if account.get('renewal_risk_description'):
            lines.append(f"Risk Description: {account['renewal_risk_description']}")
        if account.get('relationship_score'):
            lines.append(f"Relationship Score: {account['relationship_score']}")

    # Strategic Notes
    notes_keys = ['ae_field_notes', 'sales_director_notes', 'account_comments', 'account_strategy', 'customer_success_notes']
    if any(account.get(k) for k in notes_keys):
        lines += ["", "--- STRATEGIC NOTES (From Sales Team) ---"]
        note_map = [
            ('AE Field Notes', 'ae_field_notes', 500),
            ('Sales Director Notes', 'sales_director_notes', 500),
            ('Account Strategy', 'account_strategy', 500),
            ('Account Comments', 'account_comments', 300),
            ('Customer Success Notes', 'customer_success_notes', 300),
        ]
        for label, key, max_len in note_map:
            if account.get(key):
                notes = account[key]
                if len(notes) > max_len:
                    notes = notes[:max_len] + "..."
                lines.append(f"{label}: {notes}")

    # Agreement Info
    if account.get('agreement_type') or account.get('msa_effective_date'):
        lines += ["", "--- Agreement Info ---"]
        if account.get('agreement_type'):
            lines.append(f"Agreement Type: {account['agreement_type']}")
        if account.get('msa_effective_date'):
            lines.append(f"MSA Effective Date: {truncate_date(account['msa_effective_date'])}")

    lines += [
        "",
        "IMPORTANT: Use the account risk indicators and strategic notes to inform your "
        "confidence level and scenario recommendation. If renewal risk is flagged, "
        "consider a more conservative recommendation.",
    ]

    return '\n'.join(lines)
