"""
TACV UI Steps
=============
Render functions for the 6-step single-account analysis workflow.
"""

import json
import threading
import time
from datetime import date, datetime
from typing import Dict

import pandas as pd
import streamlit as st

from core.analysis import call_cortex_complete, get_analysis_prompt, parse_analysis_response
from core.config import TIER_1_FIELDS, TIER_2_FIELDS, GENERATION_TIME_MIN, GENERATION_TIME_MAX
from core.guardrails import validate_guardrails
from core.parsing import (
    extract_data_with_haiku,
    get_missing_required_fields,
    parse_uploaded_file,
    smart_parse,
)
from core.sfdc import (
    extract_account_id,
    format_contract_summary,
    format_opportunity_summary,
    get_contract_details_markdown,
    get_opportunity_details_markdown,
    query_sfdc_account,
    query_sfdc_contracts,
    query_sfdc_opportunities,
)
from ui.components import reset_app
from core.utils import (
    escape_dollars,
    format_currency,
    get_available_planning_fy_options,
    get_default_planning_fy,
    get_fiscal_year_context,
    parse_currency,
)


def render_step_1():
    """Step 1: Planning Year Selection + Data Input"""
    
    st.markdown('<p class="section-header">📅 Planning Year Selection</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        fy_options = get_available_planning_fy_options()
        default_fy = get_default_planning_fy()
        current_idx = fy_options.index(default_fy) if default_fy in fy_options else 0
        if st.session_state.selected_planning_fy in fy_options:
            current_idx = fy_options.index(st.session_state.selected_planning_fy)
        
        selected_fy = st.selectbox(
            "Select Planning Year",
            options=fy_options,
            index=current_idx,
            help="Select the fiscal year you are planning for"
        )
        st.session_state.selected_planning_fy = selected_fy
        
        # Show FY context
        fy_context = get_fiscal_year_context(selected_fy)
        st.caption(f"**{selected_fy}**: {fy_context['fy_start']} to {fy_context['fy_end']}")
    
    with col2:
        with st.expander("📖 Fiscal Year Details", expanded=False):
            fy_context = get_fiscal_year_context(selected_fy)
            st.markdown(f"""
            - **Planning FY**: {fy_context['planning_fy']}
            - **1H**: {fy_context['1h_start']} to {fy_context['1h_end']}
            - **2H**: {fy_context['2h_start']} to {fy_context['2h_end']}
            - **Prior FY**: {fy_context['prior_fy']}
            - **Prior FY-1**: {fy_context['prior_fy_minus_1']}
            """)
    
    st.markdown("---")
    st.markdown('<p class="section-header">📋 Account Data Input</p>', unsafe_allow_html=True)
    
    # Expected Data Points section
    with st.expander("📊 Expected Data Points", expanded=False):
        st.markdown("""
        The app will attempt to parse the following fields from your data. **Bold** fields are required.
        
        #### 🔴 Required Fields
        | Field | Description | Example Values |
        |-------|-------------|----------------|
        | **Account Name** | Customer name | "DTCC", "BigCorp Inc." |
        | **Contract End Date** | When contract expires | "1/15/2027", "2027-01-15" |
        | **Capacity Remaining** | Remaining \\$ capacity | "\\$17.6M", "\\$17,600,000" |
        | **L90D Run Rate** | Last 90 days annualized | "\\$27.1M", "\\$469K" (already annual) |
        | **Prior Renewal Base** | Previous annual contract value | "\\$15M", "\\$15,000,000" |
        
        #### 🟡 Recommended Fields
        | Field | Description | Example Values |
        |-------|-------------|----------------|
        | L30D Run Rate | Last 30 days annualized | "\\$35.1M" |
        | FY Consumption Prediction | Predicted FY consumption | "\\$63.4M" |
        | Account Owner | Rep/owner name | "Spencer Ellingson" |
        | Account Segment | Customer tier | "Majors", "Enterprise" |
        """)
    
    # ============================================
    # INPUT METHOD TABS
    # ============================================
    tab_paste, tab_upload, tab_manual = st.tabs(["📋 Paste Data", "📁 Upload File", "✏️ Manual Entry"])
    
    with tab_paste:
        st.info("""
        **Paste your account data below.** The app uses AI to intelligently extract fields from any format:
        tab-delimited (Google Sheets), CSV, or key-value pairs. All column variations are automatically recognized.
        """)
        
        with st.expander("📝 Supported Formats", expanded=False):
            st.markdown("**Tab-delimited (Google Sheets copy-paste)** - Most common format")
            st.code("""Ult-Parent Name\tContract End Date\tCapacity Usage Remaining ($K)\tAnnualized Run Rate (L90D) ($K)\tPrior Renewal Base ($K)
Voya Services Company\t6/30/2027\t483\t469\t460""", language="text")
            
            st.markdown("**CSV format:**")
            st.code("""Account Name,Contract End,Capacity Remaining,L90D,Prior Renewal Base
BigCorp Inc.,1/15/2027,$18000000,$2300000,$15000000""", language="text")
            
            st.markdown("**Key-value format:**")
            st.code("""Account Name: BigCorp Inc.
Contract End Date: 1/15/2027
Capacity Remaining: $18M
L90D Burn Rate: $2.3M
Prior Renewal Base: $15M""", language="text")
            
            st.markdown("---")
            st.markdown("**Recognized column variations include:**")
            st.markdown("""
            - Account Name: `Ult-Parent Name`, `Acct Name`, `Customer Name`
            - Contract End: `Contract End Date`, `Contract End`
            - Capacity: `Capacity Usage Remaining ($K)`, `Capacity Remaining`
            - L90D: `Annualized Run Rate (L90D) ($K)`, `Trailing 91D Consumption_Average`
            - L30D: `Annualized Run Rate (L30D) ($K)`
            - Prior Renewal: `Prior Renewal Base ($K)`
            - Prediction: `FY27 Consumption Prediction ($K)`
            - Actuals: `FY26 Consumption Actuals ($K)`, `FY25 Consumption Actuals ($K)`
            - Owner: `FY27 Owner Name`, `FY26 Owner Name`
            - Segment: `Proposed Segment`, `Account Segment`
            """)
        
        raw_input = st.text_area(
            "Paste your data here",
            value=st.session_state.raw_paste_input,
            height=200,
            placeholder="Paste data with headers and values - any format works (tabs, CSV, key-value)...",
            key="data_input"
        )
        st.session_state.raw_paste_input = raw_input
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if st.button("🤖 Parse Data", type="primary", use_container_width=True,
                        help="Uses AI to intelligently extract and normalize fields from any format"):
                if raw_input.strip():
                    with st.spinner("Extracting data with AI..."):
                        # Use Haiku for fast, cheap semantic parsing
                        # Handles column variations, empty headers, format changes
                        parsed, warnings = extract_data_with_haiku(
                            raw_input,
                            st.session_state.selected_planning_fy
                        )
                    
                    st.session_state.parsed_fields = parsed
                    st.session_state.parse_warnings = warnings
                    st.session_state.detected_format = 'ai'
                    st.session_state.ai_extraction_attempted = True
                    st.session_state.user_confirmed_fields = parsed.copy()
                    
                    # Extract Account ID for SFDC opportunity lookup
                    if parsed.get('account_id'):
                        st.session_state.sfdc_account_id = parsed['account_id']
                        st.session_state.sfdc_opportunities_loaded = False
                    
                    if parsed:
                        # Check for missing required
                        missing = get_missing_required_fields(parsed)
                        if missing:
                            st.session_state.missing_required_fields = missing
                            st.warning(f"Parsed {len(parsed)} fields. Missing required: {', '.join(missing)}")
                        else:
                            st.session_state.missing_required_fields = []
                        
                        st.session_state.current_step = 2
                        st.rerun()
                    else:
                        st.session_state.missing_required_fields = list(TIER_1_FIELDS.keys())
                        st.error("Could not parse any fields. Please check your data format or use manual entry.")
                else:
                    st.warning("Please paste data before parsing.")
        
        with col2:
            if st.button("🔧 Legacy Parse", use_container_width=True, 
                        help="Use regex-based parsing (faster but less flexible)"):
                if raw_input.strip():
                    # Use smart parsing
                    parsed, warnings, detected_format = smart_parse(
                        raw_input, 
                        st.session_state.selected_planning_fy
                    )
                    
                    st.session_state.parsed_fields = parsed
                    st.session_state.parse_warnings = warnings
                    st.session_state.detected_format = detected_format
                    st.session_state.user_confirmed_fields = parsed.copy()
                    
                    if parsed:
                        # Check for missing required
                        missing = get_missing_required_fields(parsed)
                        if missing:
                            st.session_state.missing_required_fields = missing
                            st.warning(f"Parsed {len(parsed)} fields. Missing required: {', '.join(missing)}")
                        else:
                            st.session_state.missing_required_fields = []
                        
                        st.session_state.current_step = 2
                        st.rerun()
                    else:
                        st.session_state.missing_required_fields = list(TIER_1_FIELDS.keys())
                        st.error("Could not parse any fields. Try the AI Parse button instead.")
                else:
                    st.warning("Please paste data before parsing.")
        
        # Show format detection feedback
        if st.session_state.get('detected_format'):
            format_labels = {
                'tab': '📊 Tab-delimited (spreadsheet)',
                'csv': '📄 CSV (comma-separated)',
                'pipe': '📋 Pipe-delimited (table)',
                'key_value': '🔑 Key-value pairs',
                'ai': '🤖 AI extraction',
                'unknown': '❓ Unknown format'
            }
            detected = st.session_state.detected_format
            st.caption(f"Format detected: {format_labels.get(detected, detected)}")
    
    with tab_upload:
        st.info("Upload a CSV, Excel (.xlsx), or TSV file with account data.")
        
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['csv', 'xlsx', 'xls', 'tsv', 'txt'],
            help="Supports CSV, Excel, and tab-separated files"
        )
        
        if uploaded_file:
            st.caption(f"📁 {uploaded_file.name} ({uploaded_file.size:,} bytes)")
            
            if st.button("📥 Parse Uploaded File", type="primary"):
                with st.spinner("Parsing file..."):
                    parsed, warnings = parse_uploaded_file(
                        uploaded_file,
                        st.session_state.selected_planning_fy
                    )
                
                st.session_state.parsed_fields = parsed
                st.session_state.parse_warnings = warnings
                st.session_state.detected_format = 'file'
                st.session_state.user_confirmed_fields = parsed.copy()
                
                if parsed:
                    missing = get_missing_required_fields(parsed)
                    st.session_state.missing_required_fields = missing
                    
                    if missing:
                        st.warning(f"Parsed {len(parsed)} fields. Missing: {', '.join(missing)}")
                    else:
                        st.success(f"Successfully parsed {len(parsed)} fields!")
                    
                    st.session_state.current_step = 2
                    st.rerun()
                else:
                    st.error("Could not parse any fields from the file.")
                    for w in warnings:
                        st.warning(w)
    
    with tab_manual:
        st.info("Skip parsing and enter all fields manually on the next screen.")
        
        if st.button("✏️ Start Manual Entry", type="primary", use_container_width=True):
            st.session_state.parsed_fields = {}
            st.session_state.parse_warnings = []
            st.session_state.user_confirmed_fields = {}
            st.session_state.detected_format = 'manual'
            st.session_state.current_step = 2
            st.rerun()
    
    # ============================================
    # PARSING FEEDBACK SECTION
    # ============================================
    if st.session_state.parse_warnings and st.session_state.parsed_fields:
        with st.expander("⚠️ Parsing Notes", expanded=True):
            for warning in st.session_state.parse_warnings:
                if "AI" in warning or "extracted" in warning.lower():
                    st.info(warning)
                elif "Missing required" in warning:
                    st.warning(warning)
                else:
                    st.caption(warning)


def render_step_2():
    """Step 2: Field Confirmation"""
    
    st.markdown('<p class="section-header">✅ Confirm Parsed Fields</p>', unsafe_allow_html=True)
    
    fy_context = get_fiscal_year_context(st.session_state.selected_planning_fy)
    
    # Show parse warnings if any
    if st.session_state.parse_warnings:
        with st.expander("⚠️ Parse Warnings", expanded=True):
            for warning in st.session_state.parse_warnings:
                st.warning(warning)
    
    # Tier 1 Fields (Required)
    st.markdown("### 🔴 Required Fields (Tier 1)")
    st.caption("All required fields must be populated to proceed with analysis.")
    
    tier1_complete = True
    confirmed = st.session_state.user_confirmed_fields
    
    cols = st.columns(2)
    col_idx = 0
    
    for field_key, field_info in TIER_1_FIELDS.items():
        with cols[col_idx % 2]:
            current_value = confirmed.get(field_key, '')
            
            # Determine field status
            has_value = current_value not in [None, '', 0]
            status_class = "field-valid" if has_value else "field-error"
            status_icon = "✅" if has_value else "❌"
            
            st.markdown(f"**{field_info['label']}** {status_icon}")
            
            if field_info['type'] == 'text':
                new_value = st.text_input(
                    field_info['description'],
                    value=str(current_value) if current_value else '',
                    key=f"field_{field_key}",
                    label_visibility="collapsed"
                )
                confirmed[field_key] = new_value
                
            elif field_info['type'] == 'date':
                if current_value:
                    try:
                        default_date = datetime.strptime(current_value, '%Y-%m-%d').date()
                    except Exception:
                        default_date = date.today()
                else:
                    default_date = date.today()
                
                new_value = st.date_input(
                    field_info['description'],
                    value=default_date,
                    key=f"field_{field_key}",
                    label_visibility="collapsed"
                )
                confirmed[field_key] = new_value.strftime('%Y-%m-%d')
                
            elif field_info['type'] == 'currency':
                # Convert to number input
                if isinstance(current_value, (int, float)):
                    default_val = float(current_value)
                else:
                    default_val = 0.0
                
                new_value = st.number_input(
                    field_info['description'],
                    value=default_val,
                    min_value=0.0,
                    step=100000.0,
                    format="%.2f",
                    key=f"field_{field_key}",
                    label_visibility="collapsed"
                )
                confirmed[field_key] = new_value
                st.caption(f"Formatted: {format_currency(new_value)}")
                
            elif field_info['type'] == 'select':
                options = field_info['options']
                default_idx = options.index(current_value) if current_value in options else 0
                new_value = st.selectbox(
                    field_info['description'],
                    options=options,
                    index=default_idx,
                    key=f"field_{field_key}",
                    label_visibility="collapsed"
                )
                # Treat "-- Select --" as no value
                if new_value and new_value != '-- Select --':
                    confirmed[field_key] = new_value
                    has_value = True
                else:
                    confirmed[field_key] = None
                    has_value = False
            
            st.caption(field_info['description'])
            
            if not has_value and field_info.get('required', True):
                tier1_complete = False
        
        col_idx += 1
    
    # Multi-year specific fields
    if confirmed.get('contract_structure') == 'Multi-year':
        st.markdown("### 📊 Multi-Year Contract Details")
        col1, col2 = st.columns(2)
        
        with col1:
            current_segment = confirmed.get('current_segment', 1)
            confirmed['current_segment'] = st.number_input(
                "Current Segment (Year X of contract)",
                min_value=1,
                max_value=10,
                value=int(current_segment) if current_segment else 1,
                key="current_segment"
            )
        
        with col2:
            total_segments = confirmed.get('total_segments', 3)
            confirmed['total_segments'] = st.number_input(
                "Total Segments (Total years in contract)",
                min_value=1,
                max_value=10,
                value=int(total_segments) if total_segments else 3,
                key="total_segments"
            )
        
        if confirmed.get('current_segment') and confirmed.get('total_segments'):
            if confirmed['current_segment'] >= confirmed['total_segments']:
                st.info("🔒 Final year of contract - Pull-forward NOT available")
    
    st.markdown("---")
    
    # Tier 2 Fields (Recommended)
    st.markdown("### 🟡 Recommended Fields (Tier 2)")
    st.caption("These fields improve analysis quality. Missing fields will use fallback calculations.")
    
    cols = st.columns(2)
    col_idx = 0
    
    for field_key, field_info in TIER_2_FIELDS.items():
        # Update label for FY-specific fields
        label = field_info['label']
        if 'FY' in label and 'Prior' not in label:
            label = label.replace('FY', st.session_state.selected_planning_fy)
        elif 'Prior FY-1' in label:
            label = label.replace('Prior FY-1', fy_context['prior_fy_minus_1'])
        elif 'Prior FY' in label:
            label = label.replace('Prior FY', fy_context['prior_fy'])
        
        with cols[col_idx % 2]:
            current_value = confirmed.get(field_key, '')
            has_value = current_value not in [None, '', 0]
            status_icon = "✅" if has_value else "⚠️"
            
            st.markdown(f"**{label}** {status_icon}")
            
            if field_info['type'] == 'currency':
                if isinstance(current_value, (int, float)):
                    default_val = float(current_value)
                else:
                    default_val = 0.0
                
                new_value = st.number_input(
                    field_info['description'],
                    value=default_val,
                    min_value=0.0,
                    step=100000.0,
                    format="%.2f",
                    key=f"field_{field_key}",
                    label_visibility="collapsed"
                )
                confirmed[field_key] = new_value if new_value > 0 else None
                if new_value > 0:
                    st.caption(f"Formatted: {format_currency(new_value)}")
            else:
                new_value = st.text_input(
                    field_info['description'],
                    value=str(current_value) if current_value else '',
                    key=f"field_{field_key}",
                    label_visibility="collapsed"
                )
                confirmed[field_key] = new_value if new_value else None
            
            if not has_value:
                st.caption(f"⚡ Fallback: {field_info['fallback']}")
        
        col_idx += 1
    
    st.session_state.user_confirmed_fields = confirmed
    
    # ============================================
    # GUARDRAIL CONTEXT SECTION
    # ============================================
    st.markdown("---")
    st.markdown("### 🛡️ Guardrail Validation Context")
    st.caption("Optional: Provide territory context to validate recommendations against quota plan guardrails.")
    
    with st.expander("📋 What are Guardrails?", expanded=False):
        st.markdown("""
        **Quota Plan Guardrails** are organizational rules that ensure quota assignments are reasonable:
        
        | Guardrail | Rule | Negotiable? |
        |-----------|------|-------------|
        | **Max BCR** | Account TACV ≤ 25% of Territory Target | ❌ No |
        | **Minimum TACV** | ≥ $1M when assigning renewal quota | ✅ Yes |
        | **Consumption Floor** | TACV ≥ Prior FY Consumption (Expansion) | ✅ Yes |
        | **Churn Concentration** | Declining accounts ≤ 10% of territory | ✅ Yes |
        
        🔴 Red = Fails non-negotiable guardrail (requires GVP/SVP approval)  
        🟡 Yellow = Fails negotiable guardrail (requires RVP/Field Ops approval)
        """)
    
    # Initialize guardrail context if not present
    if 'guardrail_context' not in st.session_state:
        st.session_state.guardrail_context = {}
    
    guardrail_ctx = st.session_state.guardrail_context
    
    cols = st.columns(3)
    
    with cols[0]:
        st.markdown("**Territory TACV Target** ℹ️")
        territory_val = guardrail_ctx.get('territory_tacv_target', 0.0)
        if not isinstance(territory_val, (int, float)):
            territory_val = 0.0
        new_territory = st.number_input(
            "Total TACV quota for the territory/patch",
            value=float(territory_val),
            min_value=0.0,
            step=1000000.0,
            format="%.2f",
            key="guardrail_territory_target",
            label_visibility="collapsed",
            help="Used to calculate BCR. Leave at 0 to skip this validation."
        )
        guardrail_ctx['territory_tacv_target'] = new_territory if new_territory > 0 else None
        if new_territory > 0:
            st.caption(f"Territory: {format_currency(new_territory)}")
    
    with cols[1]:
        st.markdown("**Account Type**")
        account_type_options = ['Expansion', 'Acquisition', 'Hybrid']
        current_type = guardrail_ctx.get('account_type', 'Expansion')
        if current_type not in account_type_options:
            current_type = 'Expansion'
        new_type = st.selectbox(
            "Account classification",
            options=account_type_options,
            index=account_type_options.index(current_type),
            key="guardrail_account_type",
            label_visibility="collapsed",
            help="Expansion = existing customer, Acquisition = new logo, Hybrid = mix"
        )
        guardrail_ctx['account_type'] = new_type
    
    with cols[2]:
        st.markdown("**Declining Account?**")
        is_declining = guardrail_ctx.get('is_declining_account', False)
        new_declining = st.checkbox(
            "Consecutive downsells (2+ renewals)",
            value=bool(is_declining),
            key="guardrail_is_declining",
            help="Check if this account has had 2+ consecutive renewal downsells AND forecast is below L30D by 10%+"
        )
        guardrail_ctx['is_declining_account'] = new_declining
        if new_declining:
            st.caption("⚠️ Flagged for churn risk review")
    
    st.session_state.guardrail_context = guardrail_ctx
    
    # ============================================
    # SALESFORCE OPPORTUNITY INTEGRATION
    # ============================================
    st.markdown("---")
    st.markdown("### 🔗 Salesforce Opportunities")
    st.caption("Existing opportunities linked to this account to inform TACV analysis")
    
    # Try to extract Account ID from parsed data
    if not st.session_state.sfdc_account_id:
        raw_input = st.session_state.get('raw_paste_input', '')
        account_id = extract_account_id(confirmed, raw_input)
        if account_id:
            st.session_state.sfdc_account_id = account_id
    
    account_id = st.session_state.sfdc_account_id
    
    # AUTO-QUERY: If we have an Account ID and haven't loaded opportunities yet, query now
    if account_id and not st.session_state.sfdc_opportunities_loaded:
        with st.spinner("🔍 Finding Salesforce opportunities..."):
            opportunities = query_sfdc_opportunities(
                account_id, 
                st.session_state.selected_planning_fy
            )
            st.session_state.sfdc_opportunities = opportunities
            st.session_state.sfdc_opportunities_loaded = True
    
    # AUTO-QUERY ACCOUNT: Fetch account data automatically (no user selection needed)
    if account_id and not st.session_state.sfdc_account_loaded:
        # Query account in background - this enriches the analysis without user interaction
        sfdc_account = query_sfdc_account(account_id)
        st.session_state.sfdc_account = sfdc_account
        st.session_state.sfdc_account_loaded = True
    
    # Show Account ID field (editable) with refresh button
    col1, col2 = st.columns([3, 1])
    with col1:
        new_account_id = st.text_input(
            "Salesforce Account ID",
            value=account_id or '',
            placeholder="e.g., 0013100001fowGPAAY",
            help="18-character Salesforce Account ID (starts with 001)",
            key="sfdc_account_id_input"
        )
        if new_account_id != account_id:
            st.session_state.sfdc_account_id = new_account_id
            st.session_state.sfdc_opportunities_loaded = False
            st.session_state.sfdc_opportunities = []
            st.session_state.selected_opportunities = []
            st.session_state.sfdc_contracts_loaded = False
            st.session_state.sfdc_contracts = []
            st.session_state.selected_contracts = []
            # Reset account data when ID changes
            st.session_state.sfdc_account_loaded = False
            st.session_state.sfdc_account = None
            account_id = new_account_id
            st.rerun()  # Re-run to trigger auto-query with new ID
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)  # Spacing
        if st.button("🔄 Refresh", disabled=not account_id, use_container_width=True, help="Re-query opportunities"):
            st.session_state.sfdc_opportunities_loaded = False
            st.rerun()
    
    # Display opportunities if loaded
    if st.session_state.sfdc_opportunities_loaded and st.session_state.sfdc_opportunities:
        opps = st.session_state.sfdc_opportunities
        fy_context_display = get_fiscal_year_context(st.session_state.selected_planning_fy)
        cal_year = 2000 + fy_context_display['fy_num'] - 1
        st.success(f"Found {len(opps)} opportunities (close dates {cal_year}+, sorted by most future first)")
        
        # Initialize selected opportunities if not set
        if 'selected_opportunities' not in st.session_state:
            st.session_state.selected_opportunities = []
        
        st.markdown("**Select opportunities to include in analysis:**")
        
        for opp in opps:
            opp_id = opp['id']
            is_selected = opp_id in st.session_state.selected_opportunities
            
            # Create a container for each opportunity
            with st.container():
                col_check, col_summary = st.columns([0.08, 0.92])
                
                with col_check:
                    # Checkbox for selection
                    if st.checkbox(
                        "",
                        value=is_selected,
                        key=f"opp_select_{opp_id}",
                        label_visibility="collapsed"
                    ):
                        if opp_id not in st.session_state.selected_opportunities:
                            st.session_state.selected_opportunities.append(opp_id)
                    else:
                        if opp_id in st.session_state.selected_opportunities:
                            st.session_state.selected_opportunities.remove(opp_id)
                
                with col_summary:
                    # Summary line with expander for details - show FULL opportunity name
                    summary = format_opportunity_summary(opp)
                    with st.expander(f"📋 **{opp['name']}** — {summary}"):
                        st.markdown(get_opportunity_details_markdown(opp))
        
        # Show selection summary
        selected_count = len(st.session_state.selected_opportunities)
        if selected_count > 0:
            selected_opps = [o for o in opps if o['id'] in st.session_state.selected_opportunities]
            total_acv = sum(o.get('product_forecast_acv') or o.get('product_acv') or 0 for o in selected_opps)
            st.info(f"✅ {selected_count} opportunity(ies) selected • Combined ACV: {format_currency(total_acv)}")
    
    elif st.session_state.sfdc_opportunities_loaded:
        fy_context = get_fiscal_year_context(st.session_state.selected_planning_fy)
        fy_num = fy_context['fy_num']
        calendar_year = 2000 + fy_num - 1
        st.info(f"No opportunities found for this account with close dates in {calendar_year} or later.")
    
    elif not account_id:
        st.caption("💡 Enter an Account ID above to find related opportunities, or proceed without.")
    
    # ============================================
    # SALESFORCE CONTRACT INTEGRATION
    # ============================================
    st.markdown("---")
    st.markdown("### 📄 Salesforce Contracts")
    st.caption("Active contracts linked to this account (current/future end dates)")
    
    # Add refresh button for contracts
    col_contract_spacer, col_contract_refresh = st.columns([3, 1])
    with col_contract_refresh:
        if st.button("🔄 Refresh Contracts", disabled=not account_id, use_container_width=True, help="Re-query contracts"):
            st.session_state.sfdc_contracts_loaded = False
            st.session_state.sfdc_contracts = []
            st.session_state.selected_contracts = []
            st.rerun()
    
    # AUTO-QUERY: If we have an Account ID and haven't loaded contracts yet, query now
    if account_id and not st.session_state.sfdc_contracts_loaded:
        with st.spinner("🔍 Finding Salesforce contracts..."):
            contracts = query_sfdc_contracts(
                account_id, 
                st.session_state.selected_planning_fy
            )
            st.session_state.sfdc_contracts = contracts
            st.session_state.sfdc_contracts_loaded = True
    
    # Display contracts if loaded
    if st.session_state.sfdc_contracts_loaded and st.session_state.sfdc_contracts:
        contracts = st.session_state.sfdc_contracts
        fy_context_display = get_fiscal_year_context(st.session_state.selected_planning_fy)
        cal_year = 2000 + fy_context_display['fy_num'] - 1
        st.success(f"Found {len(contracts)} active contracts (end dates {cal_year}+, sorted by most future first)")
        
        # Initialize selected contracts if not set
        if 'selected_contracts' not in st.session_state:
            st.session_state.selected_contracts = []
        
        st.markdown("**Select contracts to include in analysis:**")
        
        for contract in contracts:
            contract_id = contract['id']
            is_selected = contract_id in st.session_state.selected_contracts
            
            # Create a container for each contract
            with st.container():
                col_check, col_summary = st.columns([0.08, 0.92])
                
                with col_check:
                    # Checkbox for selection
                    if st.checkbox(
                        "",
                        value=is_selected,
                        key=f"contract_select_{contract_id}",
                        label_visibility="collapsed"
                    ):
                        if contract_id not in st.session_state.selected_contracts:
                            st.session_state.selected_contracts.append(contract_id)
                    else:
                        if contract_id in st.session_state.selected_contracts:
                            st.session_state.selected_contracts.remove(contract_id)
                
                with col_summary:
                    # Summary line with expander for details
                    summary = format_contract_summary(contract)
                    contract_num = contract.get('contract_number', 'Unknown')
                    with st.expander(f"📄 **{contract_num}** — {summary}"):
                        st.markdown(get_contract_details_markdown(contract))
        
        # Show selection summary
        selected_count = len(st.session_state.selected_contracts)
        if selected_count > 0:
            st.info(f"✅ {selected_count} contract(s) selected for analysis context")
    
    elif st.session_state.sfdc_contracts_loaded:
        fy_context = get_fiscal_year_context(st.session_state.selected_planning_fy)
        fy_num = fy_context['fy_num']
        calendar_year = 2000 + fy_num - 1
        st.info(f"No active contracts found for this account with end dates in {calendar_year} or later.")
    
    elif not account_id:
        st.caption("💡 Enter an Account ID above to find related contracts, or proceed without.")
    
    # Navigation buttons
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.current_step = 1
            st.rerun()
    
    with col2:
        if st.button("Proceed to Context →", type="primary", disabled=not tier1_complete, use_container_width=True):
            st.session_state.current_step = 3
            st.rerun()
    
    if not tier1_complete:
        st.warning("⚠️ Please complete all required (Tier 1) fields before proceeding.")


def render_step_3():
    """Step 3: Qualitative Context Capture"""
    
    st.markdown('<p class="section-header">💡 Add Qualitative Context</p>', unsafe_allow_html=True)
    
    st.markdown("""
    > **What else should I know about this account?**
    > 
    > This context significantly improves the analysis. Include anything the data doesn't capture.
    """)
    
    # Suggested prompts as helper text
    st.markdown("### Suggested topics to consider:")
    
    suggestions = [
        "💰 Customer budget constraints or approval dynamics",
        "🤝 AE relationship insights",
        "📈 Known expansion or contraction plans",
        "⚔️ Competitive pressure (evaluating alternatives?)",
        "📝 Unusual contract history (prior pull-forwards, amendments)",
        "⏰ Timing considerations (reorgs, budget cycles, exec changes)",
        "🎯 Strategic initiatives driving consumption",
        "⚠️ Any risks or concerns about the account",
    ]
    
    cols = st.columns(2)
    for i, suggestion in enumerate(suggestions):
        with cols[i % 2]:
            st.markdown(f'<div class="context-chip">{suggestion}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Context input
    context = st.text_area(
        "Additional Context",
        value=st.session_state.qualitative_context,
        height=200,
        placeholder="Enter any additional context about this account that would help the analysis...\n\nFor example:\n- The customer is planning a major data warehouse migration in Q2\n- They've been evaluating competitors but AE has strong exec relationships\n- Budget approval typically takes 6-8 weeks at this company",
        key="context_input"
    )
    st.session_state.qualitative_context = context
    
    st.caption("💡 This field is optional but highly recommended. The more context you provide, the more tailored the analysis will be.")
    
    # Navigation buttons
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.current_step = 2
            st.rerun()
    
    with col2:
        if st.button("Continue to Generate →", type="primary", use_container_width=True):
            st.session_state.current_step = 4
            st.rerun()


def render_step_4():
    """Step 4: Generate Analysis"""
    
    st.markdown('<p class="section-header">🔄 Generate Analysis</p>', unsafe_allow_html=True)
    
    fy_context = get_fiscal_year_context(st.session_state.selected_planning_fy)
    fields = st.session_state.user_confirmed_fields
    context = st.session_state.qualitative_context
    
    # Initialize generation state if not present
    if 'generation_started' not in st.session_state:
        st.session_state.generation_started = False
    
    # Show what we're analyzing
    with st.expander("📊 Analysis Input Summary", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Account Details:**")
            st.markdown(f"- **Account**: {fields.get('account_name', 'N/A')}")
            st.markdown(f"- **Planning FY**: {fy_context['planning_fy']}")
            st.markdown(f"- **Contract End**: {fields.get('contract_end_date', 'N/A')}")
            st.markdown(f"- **Structure**: {fields.get('contract_structure', 'N/A')}")
        
        with col2:
            st.markdown("**Financial Metrics:**")
            st.markdown(f"- **Capacity Remaining**: {format_currency(fields.get('capacity_remaining'))}")
            st.markdown(f"- **L90D Burn**: {format_currency(fields.get('l90d_burn_rate'))}")
            st.markdown(f"- **Prior Renewal Base**: {format_currency(fields.get('prior_renewal_base'))}")
            if fields.get('planning_fy_prediction'):
                st.markdown(f"- **{fy_context['planning_fy']} Prediction**: {format_currency(fields.get('planning_fy_prediction'))}")
    
    # ============================================
    # STEP 4A: Confirmation before generating
    # ============================================
    if not st.session_state.generated_analysis and not st.session_state.generation_started:
        st.info("📋 Review the summary above. Click **Generate Analysis** when ready, or go back to make changes.")
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            if st.button("🚀 Generate Analysis", type="primary", use_container_width=True):
                st.session_state.generation_started = True
                st.rerun()
        
        with col2:
            if st.button("← Back to Add Context", use_container_width=True):
                st.session_state.current_step = 3
                st.rerun()
        
        with col3:
            if st.button("🔄 Start Over", use_container_width=True, type="secondary"):
                reset_app()
                st.rerun()
        
        return  # Don't proceed until they click Generate
    
    # ============================================
    # STEP 4B: Generation in progress
    # ============================================
    if not st.session_state.generated_analysis and st.session_state.generation_started:
        # Check if cancelled before starting
        if st.session_state.get('generation_cancelled'):
            st.session_state.generation_started = False
            st.session_state.generation_cancelled = False
            st.session_state.current_step = 3
            st.rerun()
            return
        
        # Cancel button
        cancel_col1, cancel_col2 = st.columns([3, 1])
        with cancel_col2:
            if st.button("⏹️ Cancel & Go Back", type="secondary", use_container_width=True, 
                        help="Cancel will take effect after current generation completes"):
                st.session_state.generation_cancelled = True
        
            # Get selected opportunities if any
            selected_opps = []
            if st.session_state.get('selected_opportunities') and st.session_state.get('sfdc_opportunities'):
                selected_ids = st.session_state.selected_opportunities
                selected_opps = [o for o in st.session_state.sfdc_opportunities if o['id'] in selected_ids]
            
            # Get selected contracts if any
            selected_contracts = []
            if st.session_state.get('selected_contracts') and st.session_state.get('sfdc_contracts'):
                selected_contract_ids = st.session_state.selected_contracts
                selected_contracts = [c for c in st.session_state.sfdc_contracts if c['id'] in selected_contract_ids]
            
            # Get SFDC account data (auto-fetched, no selection needed)
            sfdc_account = st.session_state.get('sfdc_account')
            
            prompt = get_analysis_prompt(fields, fy_context, context, selected_opps, selected_contracts, sfdc_account)
            
            # Add refinement context if present
            if st.session_state.refinement_context:
                prompt += f"\n\nADDITIONAL REFINEMENT CONTEXT:\n{st.session_state.refinement_context}"
            
        # ============================================
        # PROGRESS BAR WITH ESTIMATED TIME
        # ============================================
        # Status messages that rotate during generation
        status_messages = [
            "🔍 Analyzing contract structure...",
            "📊 Calculating consumption patterns...",
            "📅 Evaluating renewal events...",
            "🎯 Building scenario recommendations...",
            "🛡️ Validating guardrails...",
            "✨ Finalizing analysis..."
        ]
        
        # Estimated timing from config constants
        estimated_min = GENERATION_TIME_MIN
        estimated_max = GENERATION_TIME_MAX
        
        # Progress display containers
        st.markdown("""
        <div style="background: rgba(41, 181, 232, 0.05); border: 2px solid rgba(41, 181, 232, 0.2); border-radius: 12px; padding: 1.5rem; margin: 1rem 0;">
            <h4 style="color: #29B5E8; margin: 0 0 1rem 0;">🤖 AI Analysis in Progress</h4>
            <p style="color: #666; margin: 0 0 0.5rem 0;">Using Claude to generate your TACV analysis. This typically takes 60-90 seconds.</p>
        </div>
        """, unsafe_allow_html=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        time_text = st.empty()
        
        # Track start time
        start_time = time.time()
        
        # Run the Cortex call in a background thread
        analysis_result = [None]  # Use list to allow mutation from thread
        analysis_error = [None]
        
        def run_cortex_call():
            try:
                analysis_result[0] = call_cortex_complete(prompt)
            except Exception as e:
                analysis_error[0] = str(e)
        
        # Start the background thread
        thread = threading.Thread(target=run_cortex_call)
        thread.start()
        
        # Update progress while waiting
        message_idx = 0
        while thread.is_alive():
            elapsed = time.time() - start_time
            
            # Calculate progress (non-linear: faster at start, slower toward end)
            # At 60s -> ~60%, at 90s -> ~85%, caps at 95% until complete
            if elapsed <= estimated_min:
                # Linear progress for first 60 seconds (0% to 60%)
                progress = (elapsed / estimated_min) * 0.60
            elif elapsed <= estimated_max:
                # Slower progress from 60s to 90s (60% to 85%)
                extra_time = elapsed - estimated_min
                progress = 0.60 + (extra_time / (estimated_max - estimated_min)) * 0.25
            else:
                # Very slow progress after 90s, caps at 95%
                extra_time = elapsed - estimated_max
                progress = min(0.85 + (extra_time / 60) * 0.10, 0.95)
            
            # Update progress bar
            progress_bar.progress(progress)
            
            # Rotate status message every 10 seconds
            current_msg_idx = int(elapsed / 10) % len(status_messages)
            status_text.markdown(f"**{status_messages[current_msg_idx]}**")
            
            # Calculate and display time information
            elapsed_int = int(elapsed)
            if elapsed <= estimated_min:
                remaining_est = f"~{int(estimated_max - elapsed)}-{int(estimated_max + 15 - elapsed)}s remaining"
            elif elapsed <= estimated_max:
                remaining_est = f"~{int(estimated_max - elapsed + 10)}-{int(estimated_max + 20 - elapsed)}s remaining"
            else:
                remaining_est = "Almost there..."
            
            time_text.markdown(f"⏱️ Elapsed: **{elapsed_int}s** | {remaining_est}")
            
            # Small sleep to avoid hammering the UI
            time.sleep(0.5)
        
        # Thread completed - get results
        thread.join()
        
        # Complete the progress bar
        progress_bar.progress(1.0)
        status_text.markdown("**✅ Analysis complete!**")
        time_text.markdown(f"⏱️ Total time: **{int(time.time() - start_time)}s**")
        
        # Small delay to show completion
        time.sleep(0.5)
        
        # Check for errors
        if analysis_error[0]:
            st.error(f"Error generating analysis: {analysis_error[0]}")
            st.session_state.generation_started = False
            st.rerun()
            return
        
        analysis = analysis_result[0]
        
        # Check if cancelled after generation
        if st.session_state.get('generation_cancelled'):
            st.session_state.generation_started = False
            st.session_state.generation_cancelled = False
            st.session_state.current_step = 3
            st.warning("Analysis cancelled. Returning to previous step...")
            st.rerun()
            return
        
        st.session_state.generated_analysis = analysis
        st.session_state.generation_started = False
        st.session_state.analysis_history.append({
            'timestamp': datetime.now().isoformat(),
            'analysis': analysis,
            'context': context,
            'refinement': st.session_state.refinement_context,
            'selected_opportunities': selected_opps,
            'selected_contracts': selected_contracts
        })
        
        # Auto-navigate to results page
        st.session_state.current_step = 5
        st.rerun()
    
    # ============================================
    # STEP 4C: Generation complete (fallback - shouldn't normally reach here)
    # ============================================
    if st.session_state.generated_analysis:
        # If we have a generated analysis but didn't auto-navigate, do it now
        st.session_state.current_step = 5
        st.rerun()
    
    elif st.session_state.generation_started:
        # Generation failed
        st.error("Failed to generate analysis. Please try again.")
        st.session_state.generation_started = False
        
        if st.button("🔄 Retry Generation", type="primary"):
            st.session_state.generated_analysis = ''
            st.session_state.generation_started = True
            st.rerun()
        
        if st.button("← Back to Context"):
            st.session_state.current_step = 3
            st.rerun()


def render_step_5():
    """Step 5: Review Output + Optionally Refine"""
    
    analysis = st.session_state.generated_analysis
    fields = st.session_state.user_confirmed_fields
    fy_context = get_fiscal_year_context(st.session_state.selected_planning_fy)
    
    # Parse the structured analysis
    parsed = parse_analysis_response(analysis)
    summary = parsed.get('summary', {})
    rec = parsed.get('recommendation', {})
    
    # Get recommended TACV - always from RECOMMENDATION section (single source of truth)
    recommended_tacv = rec.get('total_tacv', 'N/A')
    confidence = summary.get('confidence_level', 'N/A')
    scenario = rec.get('scenario') or summary.get('recommended_scenario', 'Base')
    
    # Confidence color
    conf_color = "#4CAF50" if confidence == "HIGH" else "#FFC107" if "MEDIUM" in confidence else "#F44336"
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #29B5E8 0%, #1a9dcc 100%); padding: 2rem; border-radius: 12px; margin-bottom: 1.5rem; text-align: center;">
        <p style="color: rgba(255,255,255,0.8); margin: 0; font-size: 0.9rem;">RECOMMENDED {fy_context['planning_fy']} TACV</p>
        <h1 style="color: white; margin: 0.5rem 0; font-size: 3rem; font-weight: 700;">{recommended_tacv}</h1>
        <p style="margin: 0;">
            <span style="background: rgba(255,255,255,0.2); padding: 0.3rem 0.8rem; border-radius: 20px; color: white; font-weight: 500;" title="Conservative = lower risk, Base = balanced, Stretch = aggressive growth">{scenario} Scenario</span>
            <span style="background: {conf_color}; padding: 0.3rem 0.8rem; border-radius: 20px; color: white; font-weight: 500; margin-left: 0.5rem; cursor: help;" title="Analysis Confidence: How confident the AI is in this recommendation based on data quality and completeness. HIGH = complete data, clear patterns. LOW = missing data or inconsistencies.">{confidence} Analysis Confidence</span>
        </p>
        <p style="color: rgba(255,255,255,0.9); margin-top: 1rem; font-size: 0.95rem;">📊 {summary.get('confidence_reason', '')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Helper text for understanding the output
    with st.expander("ℹ️ Understanding This Analysis", expanded=False):
        st.markdown("""
        **Key Terms:**
        
        | Term | Definition |
        |------|------------|
        | **TACV** | Total Annual Contract Value - the total bookable contract value for the fiscal year |
        | **Renewal ACV** | The portion of TACV that renews the prior contract base |
        | **Growth ACV** | The portion of TACV representing net new value over prior base |
        | **Analysis Confidence** | The AI's confidence in this recommendation based on **data quality and completeness** (not probability of achieving the target) |
        | **Scenario Confidence** | The likelihood the account will actually **achieve that TACV target** based on consumption patterns |
        
        **Contracted vs Non-Contracted:**
        
        | Type | Definition | Quota? |
        |------|------------|--------|
        | **Contracted Renewal** | Multi-year segment auto-renewing (Year 1 → Year 2) | ❌ No - automatic |
        | **Non-Contracted Renewal** | Single-year or final multi-year segment requiring sales | ✅ Yes |
        | **Contracted Growth** | Built-in step-ups in multi-year deals | ❌ No - already signed |
        | **Non-Contracted Growth** | Upsells, amendments, expansions | ✅ Yes |
        | **Quota-Bearing TACV** | Non-Contracted Renewal + Non-Contracted Growth | ✅ What sales must SELL |
        | **Non-Quota TACV** | Contracted Renewal + Contracted Growth | ❌ Happens automatically |
        
        **Confidence Levels:**
        - 🟢 **HIGH** = Complete data, clear patterns, well-supported recommendation
        - 🟡 **MEDIUM-HIGH** = Good data with minor gaps, solid recommendation
        - 🟠 **MEDIUM** = Some data issues, recommendation should be validated
        - 🔴 **LOW** = Significant data gaps, recommendation needs validation
        
        **Scenarios Explained:**
        - **Conservative** = Lower-risk target with high likelihood of achievement
        - **Base** = Balanced target based on current consumption trajectory
        - **Stretch** = Aggressive target requiring acceleration or upsell
        """)
    
    # Account info bar
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Account", summary.get('account_name', fields.get('account_name', 'N/A'))[:25])
    with col2:
        st.metric("Contract End", summary.get('contract_end_date', 'N/A'))
    with col3:
        st.metric("Capacity Remaining", summary.get('capacity_remaining', format_currency(fields.get('capacity_remaining'))))
    with col4:
        st.metric("Structure", summary.get('contract_structure', 'N/A')[:20])
    
    st.markdown("---")
    
    # ============================================
    # QUICK-GLANCE SUMMARY SECTION (At-a-Glance)
    # ============================================
    st.markdown("### 📊 At-a-Glance Summary")
    st.caption("Quick overview of key findings. Click 'See details' to expand, or explore the tabs below for full analysis.")
    
    # Pre-compute guardrails for summary display
    recommended_tacv_str = rec.get('total_tacv', '$0')
    try:
        recommended_tacv_num = parse_currency(recommended_tacv_str.replace('$', '').replace(',', ''))
        if recommended_tacv_num is None:
            recommended_tacv_num = 0.0
    except (ValueError, AttributeError):
        recommended_tacv_num = 0.0
    
    guardrail_ctx = st.session_state.get('guardrail_context', {})
    guardrail_results = validate_guardrails(recommended_tacv_num, fields, guardrail_ctx)
    
    # Get data flags
    data_flags = parsed.get('data_flags', [])
    has_flags = data_flags and data_flags != ['None detected'] and data_flags != [''] and any(f.strip() for f in data_flags)
    flag_count = len([f for f in data_flags if f.strip()]) if has_flags else 0
    
    # Get scenarios
    scenarios = parsed.get('scenarios', {})
    
    # Create three column layout for mini cards
    summary_col1, summary_col2, summary_col3 = st.columns(3)
    
    # ---- GUARDRAILS MINI CARD ----
    with summary_col1:
        passed = guardrail_results['passed']
        failed = guardrail_results['failed']
        warnings = guardrail_results['warnings']
        
        if failed > 0:
            card_bg = "rgba(244, 67, 54, 0.1)"
            card_border = "#F44336"
            status_icon = "❌"
            status_text = f"{failed} Failed"
            status_color = "#F44336"
        elif warnings > 0:
            card_bg = "rgba(255, 193, 7, 0.1)"
            card_border = "#FFC107"
            status_icon = "⚠️"
            status_text = f"{warnings} Warning{'s' if warnings > 1 else ''}"
            status_color = "#FFC107"
        else:
            card_bg = "rgba(76, 175, 80, 0.1)"
            card_border = "#4CAF50"
            status_icon = "✅"
            status_text = "All Passed"
            status_color = "#4CAF50"
        
        st.markdown(f"""
        <div style="background: {card_bg}; border: 2px solid {card_border}; border-radius: 12px; padding: 1rem; height: 100%;">
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">🛡️</span>
                <span style="font-weight: 600; font-size: 1rem;">Guardrails</span>
            </div>
            <div style="font-size: 1.3rem; font-weight: 700; color: {status_color};">
                {status_icon} {status_text}
            </div>
            <div style="font-size: 0.8rem; color: #666; margin-top: 0.3rem;">
                {passed} passed, {failed} failed, {warnings} warnings
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("See details", expanded=False):
            if guardrail_results['checks']:
                for check in guardrail_results['checks'][:3]:
                    st.markdown(f"{check['icon']} **{escape_dollars(check['name'])}**: {escape_dollars(str(check['value']))}")
                if len(guardrail_results['checks']) > 3:
                    st.caption(f"...and {len(guardrail_results['checks']) - 3} more in Guardrails tab")
            else:
                st.info("Add territory context in Step 2 for guardrail validation.")
    
    # ---- DATA FLAGS MINI CARD ----
    with summary_col2:
        if has_flags:
            card_bg = "rgba(255, 193, 7, 0.1)"
            card_border = "#FFC107"
            status_icon = "🚩"
            status_text = f"{flag_count} Flag{'s' if flag_count > 1 else ''} Detected"
            status_color = "#FFC107"
        else:
            card_bg = "rgba(76, 175, 80, 0.1)"
            card_border = "#4CAF50"
            status_icon = "✅"
            status_text = "Data Quality OK"
            status_color = "#4CAF50"
        
        st.markdown(f"""
        <div style="background: {card_bg}; border: 2px solid {card_border}; border-radius: 12px; padding: 1rem; height: 100%;">
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">⚠️</span>
                <span style="font-weight: 600; font-size: 1rem;">Data Flags</span>
            </div>
            <div style="font-size: 1.3rem; font-weight: 700; color: {status_color};">
                {status_icon} {status_text}
            </div>
            <div style="font-size: 0.8rem; color: #666; margin-top: 0.3rem;">
                {'Review flags before finalizing' if has_flags else 'No major data issues detected'}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("See details", expanded=False):
            if has_flags:
                for flag in [f for f in data_flags if f.strip()][:3]:
                    st.markdown(f"🚩 {escape_dollars(flag)}")
                if flag_count > 3:
                    st.caption(f"...and {flag_count - 3} more in Data Flags tab")
            else:
                st.success("No data quality issues detected.")
    
    # ---- SCENARIOS MINI CARD ----
    with summary_col3:
        has_scenarios = bool(scenarios)
        
        st.markdown(f"""
        <div style="background: rgba(41, 181, 232, 0.1); border: 2px solid #29B5E8; border-radius: 12px; padding: 1rem; height: 100%;">
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">📈</span>
                <span style="font-weight: 600; font-size: 1rem;">Scenarios</span>
            </div>
            <div style="font-size: 1.3rem; font-weight: 700; color: #29B5E8;">
                ⭐ {scenario} Recommended
            </div>
            <div style="font-size: 0.8rem; color: #666; margin-top: 0.3rem;">
                Compare Conservative, Base, Stretch
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("See details", expanded=False):
            if has_scenarios:
                for name in ['conservative', 'base', 'stretch']:
                    scen = scenarios.get(name, {})
                    if scen:
                        is_rec = scenario.lower() == name
                        marker = "⭐ " if is_rec else ""
                        tacv_val = escape_dollars(str(scen.get('total_tacv', 'N/A')))
                        conf_val = scen.get('confidence', 'N/A')
                        st.markdown(f"{marker}**{name.title()}**: {tacv_val} ({conf_val})")
            else:
                st.info("See Scenarios tab for details.")
    
    st.markdown("---")
    
    # Tabbed output display
    tabs = st.tabs([
        "💰 Recommendation",
        "🛡️ Guardrails",
        "🧮 Calculations",
        "⚠️ Data Flags",
        "📅 Events",
        "🔧 Options",
        "📈 Scenarios",
        "📋 Full Output"
    ])
    
    with tabs[0]:
        # Recommendation tab
        rec = parsed.get('recommendation', {})
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 📊 Recommendation Details")
            
            # Headline - the recommendation summary
            headline = rec.get('headline', '')
            if headline:
                st.markdown(f"""
                <div style="background: rgba(41, 181, 232, 0.1); border: 2px solid rgba(41, 181, 232, 0.3); border-radius: 12px; padding: 1.5rem; margin: 1rem 0;">
                    <h3 style="color: #29B5E8; margin-top: 0;">📋 Recommendation</h3>
                    <p style="font-size: 1.1rem; line-height: 1.6; font-weight: 500;">{headline}</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Capacity Exhaustion Date - Prominent Deadline Callout
            overage_date = summary.get('projected_overage_date', '')
            action_urgency = summary.get('action_urgency', '')
            if overage_date and overage_date != 'N/A':
                # Set colors based on urgency
                if action_urgency == 'CRITICAL':
                    urgency_bg = "rgba(244, 67, 54, 0.15)"
                    urgency_border = "#F44336"
                    urgency_icon = "🚨"
                    urgency_text = "CRITICAL - Immediate action required"
                elif action_urgency == 'HIGH':
                    urgency_bg = "rgba(255, 152, 0, 0.15)"
                    urgency_border = "#FF9800"
                    urgency_icon = "⚠️"
                    urgency_text = "HIGH - Action needed soon"
                elif action_urgency == 'MEDIUM':
                    urgency_bg = "rgba(255, 193, 7, 0.15)"
                    urgency_border = "#FFC107"
                    urgency_icon = "📅"
                    urgency_text = "MEDIUM - Plan ahead"
                else:
                    urgency_bg = "rgba(76, 175, 80, 0.15)"
                    urgency_border = "#4CAF50"
                    urgency_icon = "✅"
                    urgency_text = "LOW - No immediate pressure"
                
                st.markdown(f"""
                <div style="background: {urgency_bg}; border: 2px solid {urgency_border}; border-radius: 12px; padding: 1.25rem; margin: 1rem 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                        <div>
                            <span style="font-size: 0.85rem; color: #666; text-transform: uppercase; letter-spacing: 1px;">Contract Deadline</span>
                            <h3 style="margin: 0.25rem 0 0 0; color: {urgency_border}; font-size: 1.4rem;">{urgency_icon} {overage_date}</h3>
                        </div>
                        <div style="text-align: right;">
                            <span style="background: {urgency_border}; color: white; padding: 0.4rem 0.8rem; border-radius: 20px; font-size: 0.85rem; font-weight: 600;">
                                {urgency_text}
                            </span>
                        </div>
                    </div>
                    <p style="margin: 0.75rem 0 0 0; font-size: 0.9rem; color: #555;">
                        New contract must be signed before this date to avoid capacity overage.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            # Why This Number section
            why_this_number = rec.get('why_this_number', '')
            if why_this_number:
                st.markdown("#### 🎯 Why This Number?")
                # Parse bullet points
                bullets = [b.strip().lstrip('•').lstrip('-').strip() for b in why_this_number.split('•') if b.strip()]
                if len(bullets) <= 1:
                    bullets = [b.strip().lstrip('-').strip() for b in why_this_number.split('\n') if b.strip()]
                for bullet in bullets[:4]:
                    if bullet:
                        st.markdown(f"• {escape_dollars(bullet)}")
            
            # Breakdown
            st.markdown("#### 💵 TACV Breakdown")
            breakdown_col1, breakdown_col2, breakdown_col3 = st.columns(3)
            with breakdown_col1:
                st.metric("Renewal ACV", rec.get('renewal_acv', 'N/A'), help="Prior contract base amount being renewed - carries forward from previous deal")
            with breakdown_col2:
                st.metric("Growth ACV", rec.get('growth_acv', '$0'), help="Net new value above prior base - represents expansion or upsell")
            with breakdown_col3:
                st.metric("Total TACV", rec.get('total_tacv', recommended_tacv), help="Total Annual Contract Value = Renewal + Growth")
            
            # Growth calculation explanation
            growth_calc = rec.get('growth_calculation', '')
            prior_base = rec.get('prior_renewal_base', '')
            if growth_calc or prior_base:
                st.caption(f"📐 **Growth Calculation:** {escape_dollars(growth_calc) if growth_calc else f'Total TACV - {escape_dollars(prior_base)} Prior = Growth ACV'}")
            
            # Quota Classification Section
            st.markdown("#### 📊 Quota Classification")
            st.caption("Contracted = automatic, Non-Contracted = sales must close")
            
            quota_bearing = rec.get('quota_bearing_tacv', 'N/A')
            non_quota = rec.get('non_quota_tacv', '$0')
            contracted_renewal = rec.get('contracted_renewal', '$0')
            non_contracted_renewal = rec.get('non_contracted_renewal', 'N/A')
            contracted_growth = rec.get('contracted_growth', '$0')
            non_contracted_growth = rec.get('non_contracted_growth', 'N/A')
            
            quota_col1, quota_col2 = st.columns(2)
            
            with quota_col1:
                st.markdown(f"""
                <div style="background: rgba(76, 175, 80, 0.1); border: 2px solid #4CAF50; border-radius: 8px; padding: 1rem;">
                    <h4 style="color: #4CAF50; margin: 0 0 0.5rem 0;">✅ Quota-Bearing (Must Sell)</h4>
                    <p style="font-size: 1.8rem; font-weight: bold; margin: 0; color: #4CAF50;">{quota_bearing}</p>
                    <hr style="margin: 0.75rem 0; border-color: rgba(76, 175, 80, 0.3);">
                    <p style="font-size: 0.85rem; color: #666; margin: 0; line-height: 1.6;">
                        <strong>Non-Contracted Renewal:</strong> {non_contracted_renewal}<br>
                        <strong>Non-Contracted Growth:</strong> {non_contracted_growth}
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            with quota_col2:
                st.markdown(f"""
                <div style="background: rgba(158, 158, 158, 0.1); border: 2px solid #9E9E9E; border-radius: 8px; padding: 1rem;">
                    <h4 style="color: #9E9E9E; margin: 0 0 0.5rem 0;">🔒 Non-Quota (Automatic)</h4>
                    <p style="font-size: 1.8rem; font-weight: bold; margin: 0; color: #9E9E9E;">{non_quota}</p>
                    <hr style="margin: 0.75rem 0; border-color: rgba(158, 158, 158, 0.3);">
                    <p style="font-size: 0.85rem; color: #666; margin: 0; line-height: 1.6;">
                        <strong>Contracted Renewal:</strong> {contracted_renewal}<br>
                        <strong>Contracted Growth:</strong> {contracted_growth}
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            # Why This Scenario section
            why_this = rec.get('why_this_scenario', '')
            if why_this:
                st.markdown("#### 🎯 Why This Scenario?")
                st.markdown(f"{escape_dollars(why_this)}")
            
            # Alternative Scenarios - collapsible
            alt_scenario = rec.get('alternative_scenario', '')
            if alt_scenario:
                with st.expander("🔄 When to consider alternatives"):
                    st.markdown(f"{escape_dollars(alt_scenario)}")
        
        with col2:
            st.markdown("### ⚡ Quick Facts")
            st.caption("Hover over metrics for definitions")
            
            # Get values (no escape needed for HTML context)
            l90d_val = summary.get('l90d_annual', 'N/A')
            l30d_val = summary.get('l30d_annual', 'N/A')
            accel_val = summary.get('acceleration_pct', 'N/A')
            cap_months = summary.get('capacity_months', 'N/A')
            overage_date_qf = summary.get('projected_overage_date', '')
            fy_pred = summary.get('planning_fy_prediction', 'N/A')
            
            # Format capacity runway with date
            capacity_display = f"{cap_months}"
            if overage_date_qf and overage_date_qf != 'N/A':
                capacity_display = f"{cap_months} → <strong style='color: #FF9800;'>{overage_date_qf}</strong>"
            
            st.markdown(f"""
            <div style="line-height: 1.8;">
            <span title="Last 90 days consumption annualized - stable baseline">📊 <strong>L90D Annual</strong>: {l90d_val}</span><br>
            <span title="Last 30 days consumption annualized - recent trend indicator">📈 <strong>L30D Annual</strong>: {l30d_val}</span><br>
            <span title="Percentage change between L30D and L90D - positive = growing, negative = declining">⚡ <strong>Acceleration</strong>: {accel_val}</span><br>
            <span title="Months until capacity runs out at current burn rate - DATE shows when contract must be signed">⏱️ <strong>Capacity Runway</strong>: {capacity_display}</span><br>
            <span title="System-predicted consumption for the planning fiscal year">🔮 <strong>FY Prediction</strong>: {fy_pred}</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Risks summary
            if parsed.get('risks'):
                st.markdown("### ⚠️ Key Risks")
                for risk in parsed['risks'][:2]:
                    if 'RISK_HIGH' in risk:
                        st.error(escape_dollars(risk.replace('RISK_HIGH:', '🔴')))
                    else:
                        st.warning(escape_dollars(risk.replace('RISK_MEDIUM:', '🟡')))
    
    with tabs[1]:
        # Guardrails tab - Quota Plan Validation
        # NOTE: guardrail_results already computed above for the At-a-Glance summary
        st.markdown("### 🛡️ Quota Plan Guardrail Validation")
        st.caption("Validates the recommended TACV against organizational quota plan guardrails.")
        
        # Summary metrics (using pre-computed guardrail_results)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("✅ Passed", guardrail_results['passed'])
        with col2:
            st.metric("❌ Failed", guardrail_results['failed'])
        with col3:
            st.metric("⚠️ Warnings", guardrail_results['warnings'])
        with col4:
            st.metric("➖ N/A", guardrail_results['not_applicable'])
        
        st.markdown("---")
        
        # Detail each guardrail check
        if guardrail_results['checks']:
            for check in guardrail_results['checks']:
                status = check['status']
                
                # Color coding
                if status == 'pass':
                    bg_color = 'rgba(76, 175, 80, 0.1)'
                    border_color = '#4CAF50'
                elif status == 'fail':
                    bg_color = 'rgba(244, 67, 54, 0.1)'
                    border_color = '#F44336'
                elif status == 'warning':
                    bg_color = 'rgba(255, 193, 7, 0.1)'
                    border_color = '#FFC107'
                else:  # na or info
                    bg_color = 'rgba(158, 158, 158, 0.1)'
                    border_color = '#9E9E9E'
                
                negotiable_badge = '<span style="background: #E3F2FD; color: #1976D2; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; margin-left: 0.5rem;">Negotiable</span>' if check.get('negotiable') else '<span style="background: #FFEBEE; color: #C62828; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; margin-left: 0.5rem;">Non-Negotiable</span>'
                
                st.markdown(f"""
                <div style="background: {bg_color}; border-left: 4px solid {border_color}; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0; color: {border_color};">{check['icon']} {check['name']}</h4>
                        {negotiable_badge}
                    </div>
                    <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem;">
                        <strong>Value:</strong> {check['value']} | <strong>Threshold:</strong> {check['threshold']}
                    </p>
                    <p style="margin: 0.5rem 0 0 0; font-size: 0.85rem; color: #666;">{check['detail']}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No guardrail checks to display. Provide territory context in Step 2 for validation.")
        
        # Approval guidance
        if guardrail_results['failed'] > 0:
            st.error("""
            **❌ Non-Negotiable Guardrail Failure**  
            This recommendation requires exception review and approval by **GVP and SVP of GTM Strategy & Ops** 
            before it can be assigned as quota.
            """)
        elif guardrail_results['warnings'] > 0:
            st.warning("""
            **⚠️ Negotiable Guardrail Warning**  
            This recommendation may require rationale documentation and approval by **RVP and Field Ops Director**.
            """)
        else:
            st.success("✅ All applicable guardrails passed!")
        
        # Link to update guardrail context
        if not guardrail_ctx.get('territory_tacv_target'):
            st.info("💡 **Tip:** Add your Territory TACV Target in Step 2 to enable BCR and churn concentration validation.")
    
    with tabs[2]:
        # Calculations tab - Transparency
        st.markdown("### 🧮 Calculation Transparency")
        st.caption("This section shows how the TACV recommendation was calculated, providing full transparency into the analysis.")
        
        calculations = parsed.get('calculations', {})
        
        if calculations:
            # Data Sources
            if 'data_sources' in calculations:
                st.markdown("#### 📊 Data Sources Used")
                for item in calculations['data_sources']:
                    # Parse field: value | SOURCE: source format
                    if '|' in item:
                        parts = item.split('|')
                        field_val = parts[0].strip()
                        source = parts[1].replace('SOURCE:', '').strip() if len(parts) > 1 else 'Provided'
                        source_color = "#4CAF50" if "Provided" in source else "#FFC107" if "Calculated" in source else "#F44336"
                        st.markdown(f"- {field_val} — <span style='color: {source_color};'>*{source}*</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"- {item}")
            
            # Key Calculations
            if 'key_calculations' in calculations:
                st.markdown("#### 🔢 Key Calculations")
                for calc in calculations['key_calculations']:
                    st.markdown(f"- {escape_dollars(calc)}")
            
            # TACV Derivation
            if 'tacv_derivation' in calculations:
                st.markdown("#### 💵 How the TACV Was Derived")
                # No escape_dollars needed - this is HTML context, not markdown
                derivation_items = "".join([f"<li>{item}</li>" for item in calculations['tacv_derivation']])
                st.markdown(f"""
                <div style="background: rgba(41, 181, 232, 0.1); border: 1px solid rgba(41, 181, 232, 0.3); border-radius: 8px; padding: 1rem; margin: 0.5rem 0;">
                    <ul style="margin: 0; padding-left: 1.5rem;">{derivation_items}</ul>
                </div>
                """, unsafe_allow_html=True)
            
            # Renewal vs Growth Split
            if 'renewal_vs_growth_split' in calculations:
                st.markdown("#### 📈 Renewal vs Growth Split")
                for item in calculations['renewal_vs_growth_split']:
                    st.markdown(f"- {escape_dollars(item)}")
            
            # Assumptions
            if 'assumptions_made' in calculations:
                st.markdown("#### 💭 Assumptions Made")
                for assumption in calculations['assumptions_made']:
                    st.markdown(f"""
                    <div style="background: rgba(255, 193, 7, 0.1); border-left: 3px solid #FFC107; padding: 0.5rem 1rem; margin: 0.3rem 0;">
                        ⚠️ {assumption}
                    </div>
                    """, unsafe_allow_html=True)
            
            # Data Gaps
            if 'data_gaps' in calculations:
                st.markdown("#### 🔍 Data Gaps")
                gaps = calculations['data_gaps']
                if gaps and not any('None' in g for g in gaps):
                    for gap in gaps:
                        st.warning(f"📋 {gap}")
                else:
                    st.success("✅ All key data points were available for this analysis.")
        else:
            st.info("Calculation details not available. See Full Output tab for raw analysis.")
    
    with tabs[3]:
        # Data Flags tab
        st.markdown("### ⚠️ Data Quality Flags")
        st.caption("💡 These flags indicate potential data issues or anomalies that may affect the analysis accuracy. Review and validate if needed.")
        
        flags = parsed.get('data_flags', [])
        if flags and flags != ['None detected'] and flags != ['']:
            for flag in flags:
                if flag.strip():
                    st.markdown(f"""
                    <div style="background: rgba(255, 193, 7, 0.1); border-left: 4px solid #FFC107; padding: 1rem; margin: 0.5rem 0; border-radius: 0 8px 8px 0;">
                        🚩 {flag}
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.success("✅ No major data quality flags detected.")
        
        # Validation needed
        st.markdown("### ✅ Validation Needed")
        validations = parsed.get('validation', [])
        if validations:
            for val in validations:
                priority = "🔴" if "PRIORITY_1" in val else "🟡"
                st.markdown(f"{priority} {escape_dollars(val.replace('PRIORITY_1:', '').replace('PRIORITY_2:', '').strip())}")
        else:
            st.info("No specific validations identified.")
        
        # Consistency Check section
        st.markdown("### 🔍 Recommendation Consistency Check")
        st.caption("💡 Validates that the recommendation aligns with the data flags and consumption analysis.")
        
        consistency = parsed.get('consistency_check', {})
        if consistency:
            status = consistency.get('consistency_status', 'UNKNOWN')
            
            if status == 'CONSISTENT':
                st.success(f"✅ **Recommendation is consistent with data analysis**")
            elif status == 'NEEDS_EXPLANATION':
                st.warning(f"⚠️ **Recommendation requires explanation** - see note below")
            else:
                st.info("Consistency status not determined.")
            
            # Display the details
            col1, col2 = st.columns(2)
            with col1:
                l90d_vs_prior = consistency.get('l90d_vs_prior_renewal', 'N/A')
                st.markdown(f"**L90D vs Prior Renewal:** {escape_dollars(l90d_vs_prior)}")
                
                fy_assessment = consistency.get('fy_prediction_assessment', 'N/A')
                st.markdown(f"**FY Prediction Assessment:** {escape_dollars(fy_assessment)}")
            
            with col2:
                tacv_vs_fy = consistency.get('recommended_tacv_vs_fy_prediction', 'N/A')
                st.markdown(f"**Recommended TACV vs FY Prediction:** {escape_dollars(tacv_vs_fy)}")
            
            # Show the note if present
            note = consistency.get('consistency_note', '')
            if note:
                note_bg = "rgba(255, 193, 7, 0.1)" if status == 'NEEDS_EXPLANATION' else "rgba(76, 175, 80, 0.1)"
                note_border = "#FFC107" if status == 'NEEDS_EXPLANATION' else "#4CAF50"
                st.markdown(f"""
                <div style="background: {note_bg}; border-left: 4px solid {note_border}; padding: 1rem; margin: 0.5rem 0; border-radius: 0 8px 8px 0;">
                    <strong>Note:</strong> {escape_dollars(note)}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Consistency check not available in this analysis.")
    
    with tabs[4]:
        # Renewal Events tab
        st.markdown(f"### 📅 {fy_context['planning_fy']} Renewal Events")
        st.caption("💡 Key contract events in the planning fiscal year. **Bookable = YES** means this event generates quota-eligible TACV.")
        
        events = parsed.get('renewal_events', [])
        if events:
            for event in events:
                parts = event.split('|')
                if len(parts) >= 3:
                    event_type = parts[0].strip()
                    date_str = parts[1].replace('DATE:', '').strip() if len(parts) > 1 else ''
                    amount = parts[2].replace('AMOUNT:', '').strip() if len(parts) > 2 else ''
                    bookable = 'YES' in event.upper()
                    
                    bookable_badge = '<span style="background: #4CAF50; color: white; padding: 0.2rem 0.5rem; border-radius: 10px; font-size: 0.8rem;">✓ BOOKABLE</span>' if bookable else '<span style="background: #F44336; color: white; padding: 0.2rem 0.5rem; border-radius: 10px; font-size: 0.8rem;">✗ NOT BOOKABLE</span>'
                    
                    st.markdown(f"""
                    <div style="background: rgba(41, 181, 232, 0.05); border: 1px solid rgba(41, 181, 232, 0.2); border-radius: 8px; padding: 1rem; margin: 0.5rem 0;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <strong>{event_type}</strong><br>
                                <span style="color: #666;">📅 {date_str}</span>
                            </div>
                            <div style="text-align: right;">
                                <span style="font-size: 1.3rem; font-weight: 600; color: #29B5E8;">{amount}</span><br>
                                {bookable_badge}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Total
            total = parsed.get('total_base_renewal', '')
            if total:
                st.markdown(f"""
                <div style="background: #29B5E8; color: white; padding: 1rem; border-radius: 8px; margin-top: 1rem; text-align: center;">
                    <strong>Total Base Renewal ACV: {total}</strong>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No renewal events found in analysis.")
    
    with tabs[5]:
        # Options tab
        st.markdown("### 🔧 Customer Options")
        st.caption("💡 These are the strategic options available for this account. **Bookable** means it counts toward TACV quota.")
        
        options = parsed.get('options', [])
        if options:
            for i, opt in enumerate(options):
                name = opt.get('name', f'Option {i+1}')
                available = opt.get('available', 'YES')
                
                # Skip unavailable options or show them differently
                if available == 'NO':
                    st.markdown(f"""
                    <div style="background: rgba(128, 128, 128, 0.1); border: 1px solid rgba(128, 128, 128, 0.3); border-radius: 8px; padding: 1rem; margin: 0.5rem 0; opacity: 0.7;">
                        <strong>{name}</strong> - Not Available<br>
                        <span style="color: #666;">{opt.get('reason', opt.get('reason_if_unavailable', ''))}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    continue
                
                # Capacity result color
                cap_result = opt.get('capacity_result', 'N/A')
                cap_color = "#4CAF50" if cap_result == "SUFFICIENT" else "#FFC107" if cap_result == "TIGHT" else "#F44336"
                
                tacv_bookable = opt.get('tacv_bookable', 'NO')
                tacv_badge = "✓ Bookable" if tacv_bookable == 'YES' else "✗ Not Bookable"
                tacv_color = "#4CAF50" if tacv_bookable == 'YES' else "#F44336"
                
                # Check if this option is recommended
                is_recommended = opt.get('recommended', False)
                rec_badge = " ⭐ RECOMMENDED" if is_recommended else ""
                
                # Expand recommended option by default, otherwise expand first
                should_expand = is_recommended or (i == 0 and not any(o.get('recommended', False) for o in options))
                
                with st.expander(f"**{name}{rec_badge}** - TACV: {escape_dollars(opt.get('tacv_amount', 'N/A'))}", expanded=should_expand):
                    # Show recommended banner if this is the recommended option
                    if is_recommended:
                        st.markdown("""
                        <div style="background: linear-gradient(135deg, rgba(41, 181, 232, 0.15) 0%, rgba(41, 181, 232, 0.05) 100%); border: 2px solid #29B5E8; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem;">
                            ⭐ <strong style="color: #29B5E8;">This is the recommended option based on the analysis</strong>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown(f"**Action:** {escape_dollars(opt.get('action', 'N/A'))}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"""
                        <div style="background: {cap_color}20; border-left: 4px solid {cap_color}; padding: 0.5rem 1rem; border-radius: 0 4px 4px 0;">
                            <strong>Capacity:</strong> {cap_result}
                        </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"""
                        <div style="background: {tacv_color}20; border-left: 4px solid {tacv_color}; padding: 0.5rem 1rem; border-radius: 0 4px 4px 0;">
                            <strong>TACV:</strong> {opt.get('tacv_amount', 'N/A')} ({tacv_badge})
                        </div>
                        """, unsafe_allow_html=True)
                    
                    if opt.get('pros'):
                        st.markdown(f"**✅ Pros:** {escape_dollars(opt.get('pros'))}")
                    if opt.get('cons'):
                        st.markdown(f"**❌ Cons:** {escape_dollars(opt.get('cons'))}")
        else:
            st.info("Customer options not parsed. See full output tab.")
    
    with tabs[6]:
        # Scenarios tab
        st.markdown("### 📈 Planning Scenarios")
        st.caption("💡 **Scenario Confidence** = likelihood of achieving that TACV based on consumption patterns and account trajectory")
        
        scenarios = parsed.get('scenarios', {})
        
        if scenarios:
            # Create comparison table
            scenario_data = []
            for name in ['conservative', 'base', 'stretch']:
                scen = scenarios.get(name, {})
                if scen:
                    scenario_data.append({
                        'Scenario': name.title(),
                        'Total TACV': scen.get('total_tacv', 'N/A'),
                        'Quota-Bearing': scen.get('quota_bearing', scen.get('total_tacv', 'N/A')),
                        'Renewal ACV': scen.get('renewal_acv', 'N/A'),
                        'Growth ACV': scen.get('growth_acv', 'N/A'),
                        'Confidence': scen.get('confidence', 'N/A'),
                    })
            
            if scenario_data:
                df = pd.DataFrame(scenario_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.caption("💡 **Quota-Bearing** = Non-Contracted Renewal + Non-Contracted Growth (what sales must close)")
            
            # Show details for each scenario
            for name in ['conservative', 'base', 'stretch']:
                scen = scenarios.get(name, {})
                if scen:
                    is_recommended = scenario.lower() == name
                    badge = " ⭐ RECOMMENDED" if is_recommended else ""
                    bg_color = "rgba(41, 181, 232, 0.1)" if is_recommended else "rgba(128, 128, 128, 0.05)"
                    border_color = "#29B5E8" if is_recommended else "rgba(128, 128, 128, 0.2)"
                    
                    st.markdown(f"""
                    <div style="background: {bg_color}; border: 2px solid {border_color}; border-radius: 8px; padding: 1rem; margin: 0.5rem 0;">
                        <strong>{name.title()}{badge}</strong><br>
                        <span style="color: #666;">{scen.get('basis', '')}</span>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Scenarios not parsed. See full output tab.")
    
    with tabs[7]:
        # Full output tab
        st.markdown("### 📋 Full Analysis Output")
        st.text_area("Raw Output", analysis, height=500, disabled=True)
    
    st.markdown("---")
    
    # Refinement option
    with st.expander("🔄 Want to refine this analysis?", expanded=False):
        st.markdown("""
        Add additional context or correct assumptions, then regenerate.
        The new context will be appended to your original input.
        """)
        
        refinement = st.text_area(
            "Additional context or corrections",
            value=st.session_state.refinement_context,
            height=100,
            placeholder="Enter any corrections or additional context..."
        )
        st.session_state.refinement_context = refinement
        
        if st.button("🔄 Regenerate Analysis", type="secondary"):
            st.session_state.generated_analysis = ''
            st.session_state.current_step = 4
            st.rerun()
    
    # Navigation buttons
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("← Back to Context", use_container_width=True):
            st.session_state.current_step = 3
            st.rerun()
    
    with col2:
        if st.button("Export Analysis →", type="primary", use_container_width=True):
            st.session_state.current_step = 6
            st.rerun()


def render_step_6():
    """Step 6: Export"""
    
    st.markdown('<p class="section-header">📥 Export Analysis</p>', unsafe_allow_html=True)
    
    analysis = st.session_state.generated_analysis
    fields = st.session_state.user_confirmed_fields
    fy_context = get_fiscal_year_context(st.session_state.selected_planning_fy)
    
    account_name = fields.get('account_name', 'Account').replace(' ', '_').replace('/', '-')
    planning_fy = fy_context['planning_fy']
    today = datetime.now().strftime('%Y%m%d')
    
    # Build export content
    export_content = f"""# TACV Quota Analysis: {fields.get('account_name', 'Account')}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Planning FY: {planning_fy}

## Input Summary

**Account Details:**
- Account Name: {fields.get('account_name', 'N/A')}
- Contract End Date: {fields.get('contract_end_date', 'N/A')}
- Contract Structure: {fields.get('contract_structure', 'N/A')}

**Financial Metrics:**
- Capacity Remaining: {format_currency(fields.get('capacity_remaining'))}
- L90D Burn Rate: {format_currency(fields.get('l90d_burn_rate'))}
- L30D Burn Rate: {format_currency(fields.get('l30d_burn_rate'))}
- Prior Renewal Base: {format_currency(fields.get('prior_renewal_base'))}
- {planning_fy} Prediction: {format_currency(fields.get('planning_fy_prediction'))}

**User Context:**
{st.session_state.qualitative_context if st.session_state.qualitative_context else 'None provided'}

---

## Analysis

{analysis}

---

*Generated by TACV Quota Scenario Modeling App*
"""
    
    # Export options
    st.markdown("### Export Format")
    
    filename = f"TACV_Analysis_{account_name}_{planning_fy}_{today}"
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button(
            label="📄 Download Markdown (.md)",
            data=export_content,
            file_name=f"{filename}.md",
            mime="text/markdown",
            type="primary",
            use_container_width=True
        )
    
    with col2:
        # Plain text version
        st.download_button(
            label="📝 Download Text (.txt)",
            data=export_content,
            file_name=f"{filename}.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col3:
        # JSON export for data
        export_data = {
            'account_name': fields.get('account_name'),
            'planning_fy': planning_fy,
            'generated_at': datetime.now().isoformat(),
            'fields': fields,
            'qualitative_context': st.session_state.qualitative_context,
            'analysis': analysis,
        }
        st.download_button(
            label="📊 Download JSON (.json)",
            data=json.dumps(export_data, indent=2, default=str),
            file_name=f"{filename}.json",
            mime="application/json",
            use_container_width=True
        )
    
    st.markdown("---")
    
    # Preview
    with st.expander("📋 Export Preview", expanded=True):
        st.markdown(export_content)
    
    # Navigation / Start Over
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("← Back to Review", use_container_width=True):
            st.session_state.current_step = 5
            st.rerun()
    
    with col2:
        if st.button("🔄 New Analysis", type="primary", use_container_width=True):
            reset_app()
            st.rerun()
    
    st.success("✅ Analysis complete! Download your preferred format above.")
