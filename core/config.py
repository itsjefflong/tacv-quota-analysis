"""
TACV App Configuration
======================
Constants, field definitions, model names, Snowflake session, and CSS.
"""

import logging

# ============================================
# LOGGING
# ============================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tacv_app")

# ============================================
# SNOWFLAKE SESSION
# ============================================
try:
    from snowflake.snowpark.context import get_active_session
    session = get_active_session()
    IS_SNOWFLAKE = True
    logger.info("Running inside Snowflake – Cortex and SFDC queries enabled.")
except Exception:
    IS_SNOWFLAKE = False
    session = None
    logger.info("Running locally – mock mode enabled.")

# ============================================
# MODEL CONFIGURATION
# ============================================
MODEL_ANALYSIS = "claude-opus-4-5"        # Complex reasoning, scenario modeling
MODEL_PARSING = "claude-haiku-4-5"        # Fast, cheap structured extraction
MODEL_FALLBACK_PARSING = "claude-sonnet-4-5"  # Fallback if Haiku unavailable

# ============================================
# TIMING ESTIMATES (seconds)
# ============================================
GENERATION_TIME_MIN = 60
GENERATION_TIME_MAX = 90

# ============================================
# GUARDRAIL THRESHOLDS
# ============================================
BCR_MAX_PERCENT = 25
MIN_TACV_AMOUNT = 1_000_000
CHURN_MAX_PERCENT = 10
GROWTH_REVIEW_PERCENT = 100  # Flag if growth exceeds this %

# ============================================
# BRANDING
# ============================================
SNOWFLAKE_BLUE = "#29B5E8"
SNOWFLAKE_DARK = "#0C2340"
SNOWFLAKE_LIGHT = "#E8F4F8"
SNOWFLAKE_BLUE_DARKER = "#1a9dcc"
SNOWFLAKE_BLUE_LIGHTER = "#5DADE2"
COLOR_SUCCESS = "#4CAF50"
COLOR_WARNING = "#FFC107"
COLOR_ERROR = "#F44336"
COLOR_NEUTRAL = "#9E9E9E"

# ============================================
# TIER 1 FIELDS (REQUIRED)
# ============================================
TIER_1_FIELDS = {
    'account_name': {
        'label': 'Account Name',
        'description': 'Customer identifier',
        'type': 'text',
        'required': True,
    },
    'contract_end_date': {
        'label': 'Contract End Date',
        'description': 'When current contract expires',
        'type': 'date',
        'required': True,
    },
    'capacity_remaining': {
        'label': 'Capacity Remaining',
        'description': '$ remaining in contract',
        'type': 'currency',
        'required': True,
    },
    'l90d_burn_rate': {
        'label': 'L90D Burn Rate',
        'description': 'Annualized consumption rate (based on last 90 days)',
        'type': 'currency',
        'required': True,
    },
    'prior_renewal_base': {
        'label': 'Prior Renewal Base',
        'description': 'Previous renewal ACV',
        'type': 'currency',
        'required': True,
    },
    'contract_structure': {
        'label': 'Contract Structure',
        'description': 'Single-year or Multi-year',
        'type': 'select',
        'options': ['-- Select --', 'Single-year', 'Multi-year'],
        'required': True,
    },
}

# ============================================
# TIER 2 FIELDS (RECOMMENDED)
# ============================================
TIER_2_FIELDS = {
    'l30d_burn_rate': {
        'label': 'L30D Burn Rate',
        'description': 'Annualized consumption rate (based on last 30 days)',
        'type': 'currency',
        'fallback': 'Uses L90D (assumes no acceleration)',
    },
    'planning_fy_prediction': {
        'label': 'FY Prediction',
        'description': 'Predicted consumption for planning FY',
        'type': 'currency',
        'fallback': 'Falls back to L90D (already annualized)',
    },
    'contract_predicted_overage': {
        'label': 'Contract Predicted Overage',
        'description': 'Calculated overage amount',
        'type': 'currency',
        'fallback': 'Calculated from capacity ÷ burn rate',
    },
    'prior_fy_prediction': {
        'label': 'Prior FY Prediction',
        'description': 'Predicted consumption in prior FY (useful before actuals available)',
        'type': 'currency',
        'fallback': 'Falls back to L90D if not available',
    },
    'prior_fy_actuals': {
        'label': 'Prior FY Actuals',
        'description': 'Actual consumption in prior FY',
        'type': 'currency',
        'fallback': 'Weakens multi-year validation',
    },
    'prior_fy_minus_1_actuals': {
        'label': 'Prior FY-1 Actuals',
        'description': 'Actual consumption two FYs ago',
        'type': 'currency',
        'fallback': 'Weakens multi-year validation',
    },
    'account_segment': {
        'label': 'Account Segment',
        'description': 'Enterprise, Majors, etc.',
        'type': 'text',
        'fallback': 'Defaults to conservative growth assumptions',
    },
    'account_owner': {
        'label': 'Account Owner',
        'description': 'AE or account executive name',
        'type': 'text',
        'fallback': 'Display only',
    },
}

# ============================================
# GUARDRAIL CONTEXT FIELDS
# ============================================
GUARDRAIL_FIELDS = {
    'territory_tacv_target': {
        'label': 'Territory TACV Target',
        'description': 'Total TACV quota target for the territory/patch',
        'type': 'currency',
        'help': 'Used to calculate BCR (Book-to-Capacity Ratio). Account TACV should be ≤25% of territory target.',
    },
    'account_type': {
        'label': 'Account Type',
        'description': 'Acquisition, Expansion, or Hybrid',
        'type': 'select',
        'options': ['Expansion', 'Acquisition', 'Hybrid'],
        'help': 'Determines which guardrail rules apply. Expansion = existing customer, Acquisition = new logo.',
    },
    'is_declining_account': {
        'label': 'Declining Account?',
        'description': 'Forecast below L30D by 10%+ AND consecutive downsells',
        'type': 'checkbox',
        'help': 'Flag if this account has consecutive downsells (2+ renewals). Declining accounts should be ≤10% of territory TACV.',
    },
}

# ============================================
# BULK ANALYSIS COLUMNS
# ============================================
BULK_REQUIRED_COLUMNS = [
    'Account Name',
    'Contract End Date',
    'Capacity Remaining',
    'L90D Burn Rate',
    'Prior Renewal Base',
    'Contract Structure',
]

BULK_OPTIONAL_COLUMNS = [
    'L30D Burn Rate',
    'FY Prediction',
    'Account Segment',
    'Account Owner',
    'Qualitative Context',
]

# Pigment indicator columns (used to auto-detect format)
PIGMENT_INDICATOR_COLUMNS = [
    'ult-parent name',
    'capacity usage remaining ($k)',
    'annualized run rate (l90d) ($k)',
    'prior renewal base ($k)',
]

# Full Pigment column mapping: 'pigment_column_pattern' -> ('field_name', multiplier)
PIGMENT_COLUMN_MAPPING = {
    # Account identifiers
    'ult-parent name': ('account_name', 1),
    'acct name': ('account_name', 1),
    # Contract info
    'contract end date': ('contract_end_date', 1),
    # Capacity & Consumption
    'capacity usage remaining ($k)': ('capacity_remaining', 1000),
    'capacity usage remaining': ('capacity_remaining', 1),
    # Burn rates
    'annualized run rate (l90d) ($k)': ('l90d_burn_rate', 1000),
    'annualized run rate (l30d) ($k)': ('l30d_burn_rate', 1000),
    'fy27 trailing 91d consumption_average ($k)': ('l90d_burn_rate', 1000),
    # Prior renewal base
    'prior renewal base ($k)': ('prior_renewal_base', 1000),
    'prior renewal base': ('prior_renewal_base', 1),
    # FY Predictions
    'fy27 consumption prediction ($k)': ('planning_fy_prediction', 1000),
    'fy26 consumption prediction ($k)': ('prior_fy_prediction', 1000),
    # Prior FY actuals
    'fy26 consumption actuals ($k)': ('prior_fy_actuals', 1000),
    'fy25 consumption actuals ($k)': ('prior_fy_minus_1_actuals', 1000),
    'fy24 consumption actuals ($k)': ('prior_fy_minus_2_actuals', 1000),
    # Overage predictions
    'contract predicted overage ($k)': ('contract_predicted_overage', 1000),
    'fy27 predicted overage ($k)': ('fy_predicted_overage', 1000),
    # Segment and owner
    'proposed segment': ('account_segment', 1),
    'fy27 owner name': ('account_owner', 1),
    'fy26 owner name': ('account_owner', 1),
    # Account classification
    'acct category': ('account_category', 1),
    'acct subtype': ('account_subtype', 1),
    # Guardrail-related
    'is consecutive downsell?': ('is_consecutive_downsell', 1),
    'churn risk suggested?': ('churn_risk_suggested', 1),
    'flag high churn risk': ('high_churn_risk', 1),
    # Territory/Patch info
    'fy27 patch name': ('patch_name', 1),
    'fy27 theater': ('theater', 1),
    'fy27 region': ('region', 1),
    'fy27 district': ('district', 1),
    # Industry info
    'industry category': ('industry_category', 1),
    'industry': ('industry', 1),
}

# ============================================
# CSS (Snowflake Branding)
# ============================================
APP_CSS = """
<style>
    /* ============================================
       SNOWFLAKE BRAND VARIABLES
       ============================================ */
    :root {
        --snowflake-blue: #29B5E8;
        --snowflake-dark: #0C2340;
        --snowflake-light: #E8F4F8;
        --snowflake-blue-darker: #1a9dcc;
        --snowflake-blue-lighter: #5DADE2;
    }

    /* ============================================
       MAIN HEADER - Hero Section
       ============================================ */
    .main-header {
        background: linear-gradient(135deg, #29B5E8 0%, #1a9dcc 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 12px rgba(41, 181, 232, 0.3);
    }
    .main-header h1 {
        color: white;
        font-size: 2rem;
        margin: 0;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .main-header p {
        color: rgba(255, 255, 255, 0.9);
        font-size: 1rem;
        margin: 0.5rem 0 0 0;
        font-weight: 400;
    }

    /* ============================================
       SECTION CARDS
       ============================================ */
    .section-card {
        background: rgba(41, 181, 232, 0.05);
        border: 2px solid rgba(41, 181, 232, 0.2);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
    .section-header {
        color: #29B5E8;
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(41, 181, 232, 0.3);
    }

    /* ============================================
       FIELD VALIDATION INDICATORS
       ============================================ */
    .field-status {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        margin: 0.25rem;
        font-size: 0.9rem;
    }
    .field-valid {
        background: rgba(76, 175, 80, 0.15);
        border: 1px solid rgba(76, 175, 80, 0.4);
        color: #4CAF50;
    }
    .field-warning {
        background: rgba(255, 193, 7, 0.15);
        border: 1px solid rgba(255, 193, 7, 0.4);
        color: #FFC107;
    }
    .field-error {
        background: rgba(244, 67, 54, 0.15);
        border: 1px solid rgba(244, 67, 54, 0.4);
        color: #F44336;
    }

    /* ============================================
       OPTION CARDS
       ============================================ */
    .option-card {
        background: rgba(41, 181, 232, 0.05);
        border: 2px solid rgba(41, 181, 232, 0.2);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .option-header {
        font-weight: 700;
        font-size: 1.1rem;
        color: #29B5E8;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(41, 181, 232, 0.2);
    }

    /* ============================================
       CONTEXT PROMPT CHIPS
       ============================================ */
    .context-chip {
        display: inline-block;
        padding: 0.5rem 1rem;
        margin: 0.25rem;
        background: rgba(41, 181, 232, 0.1);
        border: 1px solid rgba(41, 181, 232, 0.3);
        border-radius: 20px;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .context-chip:hover {
        background: rgba(41, 181, 232, 0.2);
        border-color: #29B5E8;
    }

    /* ============================================
       METRICS & VALUES
       ============================================ */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        color: #29B5E8;
        font-weight: 700;
    }
    [data-testid="stMetricLabel"] {
        font-weight: 500;
        font-size: 0.9rem;
    }

    /* ============================================
       TABS
       ============================================ */
    .stTabs {
        background: rgba(41, 181, 232, 0.05);
        padding: 1rem;
        border-radius: 12px;
        border: 2px solid rgba(41, 181, 232, 0.2);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: rgba(41, 181, 232, 0.05);
        padding: 0.5rem;
        border-radius: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        padding: 0 20px;
        background: rgba(128, 128, 128, 0.1);
        border-radius: 6px;
        font-weight: 500;
        border: 2px solid transparent;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #29B5E8 0%, #1a9dcc 100%) !important;
        color: white !important;
        border: 2px solid #29B5E8 !important;
        box-shadow: 0 4px 8px rgba(41, 181, 232, 0.3) !important;
    }

    /* ============================================
       BUTTONS
       ============================================ */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #29B5E8 0%, #1a9dcc 100%);
        border: none;
        color: white;
    }

    /* ============================================
       EXPANDERS
       ============================================ */
    .streamlit-expanderHeader {
        font-weight: 600;
        color: #29B5E8;
    }

    /* ============================================
       CODE BLOCKS FOR OUTPUT
       ============================================ */
    .analysis-output {
        font-family: 'Monaco', 'Consolas', monospace;
        background: rgba(0, 0, 0, 0.05);
        padding: 1.5rem;
        border-radius: 8px;
        border-left: 4px solid #29B5E8;
        white-space: pre-wrap;
        line-height: 1.6;
    }

    /* ============================================
       CONFIDENCE BADGES
       ============================================ */
    .confidence-high {
        background: rgba(76, 175, 80, 0.2);
        color: #4CAF50;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .confidence-medium {
        background: rgba(255, 193, 7, 0.2);
        color: #FFC107;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .confidence-low {
        background: rgba(244, 67, 54, 0.2);
        color: #F44336;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }

    /* Hide anchor links */
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a {
        display: none !important;
    }
</style>
"""


# ============================================
# BULK TEMPLATE GENERATORS
# ============================================

def get_bulk_template():
    """Create a SIMPLE template DataFrame for bulk upload."""
    import pandas as pd

    example_data = {
        'Account Name': ['Acme Corp', 'TechStart Inc'],
        'Contract End Date': ['2027-03-15', '2027-06-30'],
        'Capacity Remaining': [5000000, 2500000],
        'L90D Burn Rate': [450000, 180000],
        'Prior Renewal Base': [4000000, 2000000],
        'Contract Structure': ['Single-year', 'Multi-year'],
        'L30D Burn Rate': [480000, 175000],
        'FY Prediction': [5500000, 2200000],
        'Account Segment': ['Enterprise', 'Commercial'],
        'Account Owner': ['Jane Smith', 'John Doe'],
        'Qualitative Context': ['Expanding into new use cases', 'Stable consumption expected'],
    }
    return pd.DataFrame(example_data)


def get_pigment_template():
    """Create a Pigment-format template DataFrame for bulk upload."""
    import pandas as pd

    example_data = {
        'Ult-Parent Name': ['Acme Corp', 'TechStart Inc'],
        'Acct Category': ['Customer', 'Customer'],
        'Proposed Segment': ['Enterprise', 'Commercial'],
        'FY27 Owner Name': ['Jane Smith', 'John Doe'],
        'Contract End Date': ['6/30/2027', '3/15/2027'],
        'Capacity Usage Remaining ($K)': [5000, 2500],
        'Annualized Run Rate (L90D) ($K)': [450, 180],
        'Annualized Run Rate (L30D) ($K)': [480, 175],
        'Prior Renewal Base ($K)': [4000, 2000],
        'FY27 Consumption Prediction ($K)': [5500, 2200],
        'FY26 Consumption Actuals ($K)': [4200, 1900],
        'FY25 Consumption Actuals ($K)': [3800, 1700],
        'Contract Predicted Overage ($K)': [500, 200],
        'Is Consecutive Downsell?': ['FALSE', 'FALSE'],
        'Acct Name': ['Acme Corp', 'TechStart Inc'],
    }
    return pd.DataFrame(example_data)
