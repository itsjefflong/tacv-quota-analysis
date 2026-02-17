"""
TACV Quota Scenario Modeling App
================================
A Streamlit app that enables Field Operations teams to generate TACV quota analysis
for individual Snowflake customer accounts.

User Flow:
1. Select Planning Year + Paste Data
2. Confirm Parsed Fields
3. Add Qualitative Context
4. Generate Analysis
5. Review Output + Optionally Refine
6. Export

This is the application entry point. All business logic lives in dedicated modules:
  - config.py        : Constants, field definitions, CSS, session
  - utils.py         : Currency/date parsing, formatting, FY logic
  - parsing.py       : Data parsing (deterministic + AI)
  - sfdc.py          : Salesforce queries & formatting
  - analysis.py      : Prompt construction, Cortex calls, response parsing
  - guardrails.py    : Guardrail validation
  - ui_components.py : Step indicator, session state, reset
  - ui_steps.py      : Step 1–6 render functions
  - ui_bulk.py       : Bulk analysis UI
"""

import streamlit as st

from core.config import APP_CSS
from ui.bulk import render_bulk_analysis
from ui.components import init_session_state, render_step_indicator, reset_app, reset_bulk_state
from ui.steps import (
    render_step_1,
    render_step_2,
    render_step_3,
    render_step_4,
    render_step_5,
    render_step_6,
)

# ============================================
# PAGE CONFIGURATION
# ============================================
st.set_page_config(
    page_title="TACV Quota Scenario Modeling",
    layout="wide",
    page_icon="❄️",
    initial_sidebar_state="collapsed",
)

# Inject branded CSS
st.markdown(APP_CSS, unsafe_allow_html=True)


# ============================================
# MAIN
# ============================================

def main():
    """Main application entry point."""
    init_session_state()

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("### ⚙️ Session")

        if st.session_state.user_confirmed_fields.get('account_name'):
            st.markdown(f"**Account:** {st.session_state.user_confirmed_fields['account_name'][:30]}")

        step_names = {
            1: "Data Input", 2: "Confirm Fields", 3: "Add Context",
            4: "Generate", 5: "Review", 6: "Export",
        }
        st.markdown(f"**Step:** {st.session_state.current_step}/6 – {step_names.get(st.session_state.current_step, '')}")

        st.markdown("---")

        if st.button("🔄 Start Over", use_container_width=True, type="secondary"):
            reset_app()
            reset_bulk_state()
            st.rerun()

        st.caption("Reset and begin a new analysis")

    # ── Header ──
    st.markdown("""
        <div class="main-header">
            <h1>
                <img src="https://companieslogo.com/img/orig/SNOW-35164165.png"
                     alt="Snowflake"
                     style="height: 42px; vertical-align: middle; margin-right: 12px; filter: brightness(0) invert(1);"
                     onerror="this.style.display='none'">
                TACV Quota Scenario Modeling
            </h1>
            <p>Generate data-driven quota analysis for customer accounts</p>
        </div>
    """, unsafe_allow_html=True)

    # ── Top-level tabs ──
    tab_single, tab_bulk = st.tabs(["📊 Single Account", "📁 Bulk Analysis"])

    with tab_single:
        render_step_indicator(st.session_state.current_step)

        step = st.session_state.current_step
        if step == 1:
            render_step_1()
        elif step == 2:
            render_step_2()
        elif step == 3:
            render_step_3()
        elif step == 4:
            render_step_4()
        elif step == 5:
            render_step_5()
        elif step == 6:
            render_step_6()

    with tab_bulk:
        render_bulk_analysis()

    # ── Footer ──
    st.markdown("---")
    footer_col1, footer_col2 = st.columns([4, 1])
    with footer_col1:
        st.caption("TACV Quota Scenario Modeling App • Built for Snowflake Field Operations")
    with footer_col2:
        if st.button("🔄 Start Over", key="footer_reset"):
            reset_app()
            reset_bulk_state()
            st.rerun()


if __name__ == "__main__":
    main()
