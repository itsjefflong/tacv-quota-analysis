"""
TACV App Utilities
==================
Pure utility functions: currency/date parsing, formatting, fiscal year logic.
No Streamlit or Snowflake dependencies.
"""

import re
from datetime import date, datetime
from typing import Optional


# ============================================
# FISCAL YEAR HELPERS
# ============================================

def get_fiscal_year_context(planning_fy: str) -> dict:
    """
    Given a planning FY (e.g., 'FY27'), return all derived date values.
    Snowflake FY runs Feb 1 - Jan 31.
    """
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
        'fy_num': fy_num,
        'start_year': start_year,
        'end_year': end_year,
    }


def get_default_planning_fy() -> str:
    """
    Determine default FY based on current date.
    Oct-Jan: Default to next FY (planning season)
    Feb-Sep: Default to current FY
    """
    today = date.today()
    current_month = today.month
    current_year = today.year

    if current_month >= 2:  # Feb-Dec
        current_fy = current_year + 1
    else:  # Jan
        current_fy = current_year

    if current_month in [10, 11, 12, 1]:
        return f'FY{current_fy + 1 - 2000}'
    else:
        return f'FY{current_fy - 2000}'


def get_available_planning_fy_options() -> list:
    """Generate available FY options: current FY and next 3 fiscal years."""
    today = date.today()
    current_month = today.month
    current_year = today.year

    if current_month >= 2:
        current_fy_num = current_year + 1 - 2000
    else:
        current_fy_num = current_year - 2000

    return [f'FY{current_fy_num + i}' for i in range(4)]


# ============================================
# CURRENCY PARSING & FORMATTING
# ============================================

def parse_currency(value: str) -> Optional[float]:
    """Parse various currency formats to float."""
    if not value:
        return None
    # Handle pandas NA
    try:
        import pandas as pd
        if pd.isna(value):
            return None
    except (ImportError, TypeError):
        pass

    value_str = str(value).strip().upper()
    value_str = re.sub(r'[$,]', '', value_str)

    multiplier = 1
    if value_str.endswith('M'):
        multiplier = 1_000_000
        value_str = value_str[:-1]
    elif value_str.endswith('K'):
        multiplier = 1_000
        value_str = value_str[:-1]
    elif value_str.endswith('B'):
        multiplier = 1_000_000_000
        value_str = value_str[:-1]

    try:
        return float(value_str) * multiplier
    except ValueError:
        return None


def format_currency(value: Optional[float], abbreviated: bool = True) -> str:
    """Format a number as currency."""
    if value is None:
        return "—"
    if abbreviated:
        if abs(value) >= 1_000_000_000:
            return f"${value / 1_000_000_000:.1f}B"
        elif abs(value) >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        elif abs(value) >= 1_000:
            return f"${value / 1_000:.0f}K"
        else:
            return f"${value:,.0f}"
    else:
        return f"${value:,.2f}"


def extract_dollar_amount(value: str) -> Optional[float]:
    """Extract a numeric dollar amount from a string like '$48.0M' or '$65M'."""
    if not value or value == 'N/A':
        return None
    try:
        cleaned = value.replace('$', '').replace(',', '').strip()
        multiplier = 1
        if cleaned.upper().endswith('M'):
            multiplier = 1_000_000
            cleaned = cleaned[:-1]
        elif cleaned.upper().endswith('K'):
            multiplier = 1_000
            cleaned = cleaned[:-1]
        elif cleaned.upper().endswith('B'):
            multiplier = 1_000_000_000
            cleaned = cleaned[:-1]
        return float(cleaned) * multiplier
    except (ValueError, AttributeError):
        return None


# ============================================
# DATE PARSING & HELPERS
# ============================================

def parse_date(value: str) -> Optional[str]:
    """Parse various date formats to YYYY-MM-DD string."""
    if not value:
        return None
    try:
        import pandas as pd
        if pd.isna(value):
            return None
    except (ImportError, TypeError):
        pass

    value_str = str(value).strip()

    formats = [
        '%m/%d/%Y',      # 1/15/2027
        '%Y-%m-%d',      # 2027-01-15
        '%m-%d-%Y',      # 01-15-2027
        '%b %d, %Y',     # Jan 15, 2027
        '%B %d, %Y',     # January 15, 2027
        '%d/%m/%Y',      # 15/01/2027
        '%m/%d/%y',      # 1/15/27
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(value_str, fmt)
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            continue

    return None


def truncate_date(value: Optional[str]) -> str:
    """Truncate a date/datetime string to just the YYYY-MM-DD portion."""
    if not value:
        return 'N/A'
    s = str(value)
    return s[:10] if len(s) > 10 else s


# ============================================
# TEXT HELPERS
# ============================================

def escape_dollars(text: str) -> str:
    """Escape dollar signs in text to prevent LaTeX interpretation in Streamlit markdown."""
    if text is None:
        return ""
    return str(text).replace('$', '\\$')


def calculate_months_to_overage(capacity: float, monthly_burn: float) -> Optional[float]:
    """Calculate months until capacity is exhausted."""
    if monthly_burn <= 0 or capacity <= 0:
        return None
    return capacity / monthly_burn


def get_column_multiplier(col_name: str) -> float:
    """
    Detect if column header indicates a unit multiplier.
    E.g., ($K) means thousands, ($M) means millions.
    """
    col_upper = col_name.upper()
    if '($K)' in col_upper or '(K)' in col_upper or '$K' in col_upper:
        return 1_000
    elif '($M)' in col_upper or '(M)' in col_upper or '$M' in col_upper:
        return 1_000_000
    elif '($B)' in col_upper or '(B)' in col_upper or '$B' in col_upper:
        return 1_000_000_000
    return 1
