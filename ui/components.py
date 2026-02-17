"""
TACV UI Components
==================
Shared UI components: step indicator, session state initialization, reset helpers.
"""

import streamlit as st
from datetime import date

from core.utils import get_default_planning_fy


# ============================================
# STEP INDICATOR
# ============================================

def render_step_indicator(current_step: int):
    """Render the step progress indicator using Streamlit columns."""
    steps = [
        ("1", "Data Input"),
        ("2", "Confirm Fields"),
        ("3", "Add Context"),
        ("4", "Generate"),
        ("5", "Review"),
        ("6", "Export"),
    ]

    cols = st.columns(len(steps))

    for i, (num, label) in enumerate(steps, 1):
        with cols[i - 1]:
            if i < current_step:
                st.markdown(f"""
                <div style="text-align: center;">
                    <div style="width: 40px; height: 40px; border-radius: 50%; background: #4CAF50; color: white; display: inline-flex; align-items: center; justify-content: center; font-weight: 600; font-size: 1rem; margin-bottom: 0.5rem;">✓</div>
                    <div style="font-size: 0.75rem; opacity: 0.8;">{label}</div>
                </div>
                """, unsafe_allow_html=True)
            elif i == current_step:
                st.markdown(f"""
                <div style="text-align: center;">
                    <div style="width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #29B5E8 0%, #1a9dcc 100%); color: white; display: inline-flex; align-items: center; justify-content: center; font-weight: 600; font-size: 1rem; margin-bottom: 0.5rem; box-shadow: 0 4px 12px rgba(41, 181, 232, 0.4);">{num}</div>
                    <div style="font-size: 0.75rem; font-weight: 600; color: #29B5E8;">{label}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="text-align: center;">
                    <div style="width: 40px; height: 40px; border-radius: 50%; background: rgba(128, 128, 128, 0.2); display: inline-flex; align-items: center; justify-content: center; font-weight: 600; font-size: 1rem; margin-bottom: 0.5rem;">{num}</div>
                    <div style="font-size: 0.75rem; opacity: 0.5;">{label}</div>
                </div>
                """, unsafe_allow_html=True)


# ============================================
# SESSION STATE
# ============================================

def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        'current_step': 1,
        'selected_planning_fy': get_default_planning_fy(),
        'raw_paste_input': '',
        'parsed_fields': {},
        'parse_warnings': [],
        'user_confirmed_fields': {},
        'qualitative_context': '',
        'generated_analysis': '',
        'refinement_context': '',
        'analysis_history': [],
        'input_method': 'paste',
        'uploaded_images': [],
        'image_extracted_data': '',
        # Layered parsing state
        'detected_format': None,
        'ai_extraction_attempted': False,
        'partial_parse_fields': {},
        'missing_required_fields': [],
        # Bulk analysis state
        'bulk_uploaded_df': None,
        'bulk_results': [],
        'bulk_processing_status': 'idle',
        'bulk_current_index': 0,
        'bulk_errors': [],
        'bulk_planning_fy': None,
        'bulk_detected_format': 'simple',
        # Guardrail validation context
        'guardrail_context': {
            'territory_tacv_target': None,
            'account_type': 'Expansion',
            'is_declining_account': False,
        },
        # Salesforce opportunity integration
        'sfdc_account_id': None,
        'sfdc_opportunities': [],
        'sfdc_opportunities_loaded': False,
        'selected_opportunities': [],
        # Salesforce contract integration
        'sfdc_contracts': [],
        'sfdc_contracts_loaded': False,
        'selected_contracts': [],
        # Salesforce account integration
        'sfdc_account': None,
        'sfdc_account_loaded': False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_app():
    """Reset all session state to start fresh."""
    st.session_state.current_step = 1
    st.session_state.raw_paste_input = ''
    st.session_state.parsed_fields = {}
    st.session_state.parse_warnings = []
    st.session_state.user_confirmed_fields = {}
    st.session_state.qualitative_context = ''
    st.session_state.generated_analysis = ''
    st.session_state.refinement_context = ''
    st.session_state.generation_started = False
    st.session_state.generation_cancelled = False
    # Reset SFDC opportunity state
    st.session_state.sfdc_account_id = None
    st.session_state.sfdc_opportunities = []
    st.session_state.sfdc_opportunities_loaded = False
    st.session_state.selected_opportunities = []
    # Reset SFDC contract state
    st.session_state.sfdc_contracts = []
    st.session_state.sfdc_contracts_loaded = False
    st.session_state.selected_contracts = []
    # Reset SFDC account state
    st.session_state.sfdc_account = None
    st.session_state.sfdc_account_loaded = False


def reset_bulk_state():
    """Reset bulk analysis session state."""
    st.session_state.bulk_uploaded_df = None
    st.session_state.bulk_results = []
    st.session_state.bulk_processing_status = 'idle'
    st.session_state.bulk_current_index = 0
    st.session_state.bulk_errors = []
    st.session_state.bulk_planning_fy = None
    st.session_state.bulk_detected_format = 'simple'
