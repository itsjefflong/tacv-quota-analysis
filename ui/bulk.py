"""
TACV Bulk Analysis UI
=====================
Streamlit rendering for bulk account upload, processing, and export.
All business logic (parsing, validation, templates) lives in other modules.
"""

import io
import time
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from core.analysis import (
    call_cortex_complete,
    extract_bulk_summary,
    get_analysis_prompt,
    parse_analysis_response,
)
from core.config import (
    BULK_OPTIONAL_COLUMNS,
    BULK_REQUIRED_COLUMNS,
    get_bulk_template,
    get_pigment_template,
)
from core.parsing import row_to_fields, validate_bulk_upload
from ui.components import reset_bulk_state
from core.utils import (
    escape_dollars,
    format_currency,
    get_available_planning_fy_options,
    get_default_planning_fy,
    get_fiscal_year_context,
)


# ============================================
# MAIN ENTRY POINT
# ============================================

def render_bulk_analysis():
    """Render the bulk analysis tab."""

    st.markdown("### 📁 Bulk Account Analysis")
    st.markdown("""
    Upload a spreadsheet with multiple accounts to generate TACV analysis for all of them at once.
    Results will be displayed in a table and can be exported to CSV/Excel.
    """)

    col1, col2 = st.columns([1, 3])
    with col1:
        fy_options = get_available_planning_fy_options()
        default_fy = get_default_planning_fy()
        default_idx = fy_options.index(default_fy) if default_fy in fy_options else 0

        planning_fy = st.selectbox(
            "Planning FY",
            options=fy_options,
            index=default_idx,
            key="bulk_fy_selector"
        )
        st.session_state.bulk_planning_fy = planning_fy

    st.markdown("---")

    if st.session_state.bulk_processing_status == 'complete' and st.session_state.bulk_results:
        _render_results()
    elif st.session_state.bulk_uploaded_df is not None:
        _render_preview_and_process()
    else:
        _render_upload()


# ============================================
# UPLOAD VIEW
# ============================================

def _render_upload():
    """Render the upload interface for bulk analysis."""

    st.markdown("#### 📋 Step 1: Choose Your Format")

    format_tabs = st.tabs(["📊 Pigment Export (Recommended)", "📝 Simple Template"])

    with format_tabs[0]:
        st.markdown("""
        **Export directly from Pigment** — The app automatically recognizes Pigment column names and applies
        the correct unit multipliers ($K → actual dollars).
        """)

        pigment_df = get_pigment_template()

        col1, col2 = st.columns(2)
        with col1:
            csv_data = pigment_df.to_csv(index=False)
            st.download_button(
                label="📄 Download Pigment-Format CSV",
                data=csv_data,
                file_name="tacv_pigment_template.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col2:
            buf = io.BytesIO()
            pigment_df.to_excel(buf, index=False, engine='openpyxl')
            st.download_button(
                label="📊 Download Pigment-Format Excel",
                data=buf.getvalue(),
                file_name="tacv_pigment_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        with st.expander("📋 Recognized Pigment Columns", expanded=False):
            st.markdown("""
            **Key columns automatically mapped:**

            | Pigment Column | Maps To | Multiplier |
            |----------------|---------|------------|
            | `Ult-Parent Name` or `Acct Name` | Account Name | - |
            | `Contract End Date` | Contract End | - |
            | `Capacity Usage Remaining ($K)` | Capacity Remaining | ×1,000 |
            | `Annualized Run Rate (L90D) ($K)` | L90D Burn Rate | ×1,000 |
            | `Annualized Run Rate (L30D) ($K)` | L30D Burn Rate | ×1,000 |
            | `Prior Renewal Base ($K)` | Prior Renewal Base | ×1,000 |
            | `FY27 Consumption Prediction ($K)` | FY Prediction | ×1,000 |
            | `FY26 Consumption Actuals ($K)` | Prior FY Actuals | ×1,000 |
            | `Proposed Segment` | Account Segment | - |
            | `FY27 Owner Name` | Account Owner | - |
            | `Is Consecutive Downsell?` | Declining Account Flag | - |
            | `Acct Category` | Account Type (Expansion/Acquisition) | - |

            **All columns with `($K)` are automatically multiplied by 1,000.**
            """)
            st.dataframe(pigment_df, use_container_width=True, hide_index=True)

    with format_tabs[1]:
        st.markdown("Use this simplified template if you're not exporting from Pigment.")

        template_df = get_bulk_template()

        col1, col2 = st.columns(2)
        with col1:
            csv_data = template_df.to_csv(index=False)
            st.download_button(
                label="📄 Download Simple CSV Template",
                data=csv_data,
                file_name="tacv_simple_template.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col2:
            buf = io.BytesIO()
            template_df.to_excel(buf, index=False, engine='openpyxl')
            st.download_button(
                label="📊 Download Simple Excel Template",
                data=buf.getvalue(),
                file_name="tacv_simple_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        with st.expander("Preview Simple Template Columns", expanded=False):
            st.markdown("**Required Columns:**")
            for col in BULK_REQUIRED_COLUMNS:
                st.markdown(f"- `{col}`")
            st.markdown("**Optional Columns:**")
            for col in BULK_OPTIONAL_COLUMNS:
                st.markdown(f"- `{col}`")
            st.markdown("---")
            st.markdown("**Example Data:**")
            st.dataframe(template_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    st.markdown("#### 📤 Step 2: Upload Your Data")
    st.info("💡 **Hybrid Parsing:** The app tries fast regex parsing first, then falls back to AI for any rows that fail.")

    uploaded_file = st.file_uploader(
        "Upload CSV or Excel file",
        type=['csv', 'xlsx', 'xls'],
        help="Upload a file with account data. Supports both Pigment exports and simple templates.",
    )

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            is_valid, messages, detected_format = validate_bulk_upload(df)

            format_labels = {
                'pigment': '📊 Pigment Export',
                'simple': '📝 Simple Template',
                'unknown': '❓ Unknown Format',
            }
            st.info(f"**Detected format:** {format_labels.get(detected_format, detected_format)}")

            if is_valid:
                st.success(f"✅ File validated successfully! Found {len(df)} accounts.")
                for msg in messages:
                    if msg.startswith("Warning"):
                        st.warning(msg)
                st.session_state.bulk_uploaded_df = df
                st.session_state.bulk_detected_format = detected_format
                st.rerun()
            else:
                st.error("❌ Validation errors found:")
                for error in messages:
                    if error.startswith("Warning"):
                        st.warning(error)
                    else:
                        st.markdown(f"- {error}")
                st.info("Please fix the errors and re-upload.")

        except Exception as e:
            st.error(f"❌ Error reading file: {e}")


# ============================================
# PREVIEW & PROCESS VIEW
# ============================================

def _render_preview_and_process():
    """Render the preview and processing interface."""

    df = st.session_state.bulk_uploaded_df

    st.markdown("#### 📋 Step 3: Review & Process")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Accounts", len(df))
    with col2:
        st.metric("Planning FY", st.session_state.bulk_planning_fy or get_default_planning_fy())
    with col3:
        est_time = len(df) * 10
        if est_time > 60:
            st.metric("Est. Time", f"~{est_time // 60} min {est_time % 60} sec")
        else:
            st.metric("Est. Time", f"~{est_time} seconds")

    st.markdown("**Data Preview (first 5 rows):**")
    st.dataframe(df.head(), use_container_width=True, hide_index=True)

    st.markdown("---")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔄 Upload Different File", use_container_width=True):
            st.session_state.bulk_uploaded_df = None
            st.rerun()
    with col2:
        if st.button("🚀 Start Processing", type="primary", use_container_width=True):
            _process_accounts()


# ============================================
# PROCESSING
# ============================================

def _process_accounts():
    """Process all accounts in the uploaded DataFrame."""

    df = st.session_state.bulk_uploaded_df
    planning_fy = st.session_state.bulk_planning_fy or get_default_planning_fy()
    fy_context = get_fiscal_year_context(planning_fy)
    detected_format = st.session_state.get('bulk_detected_format', 'simple')

    total_accounts = len(df)
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    ai_parsed_count = 0

    st.session_state.bulk_processing_status = 'processing'

    progress_bar = st.progress(0)
    status_text = st.empty()
    current_account = st.empty()
    parsing_info = st.empty()

    for idx, row in df.iterrows():
        progress = (idx + 1) / total_accounts
        progress_bar.progress(progress)

        account_name = None
        for col in ['Account Name', 'Ult-Parent Name', 'Acct Name']:
            if col in row.index and pd.notna(row[col]):
                account_name = str(row[col])
                if '|' in account_name:
                    account_name = account_name.split('|')[-1].strip()
                break
        if not account_name:
            account_name = row.iloc[0] if len(row) > 0 else f'Row {idx + 1}'

        status_text.markdown(f"**Processing:** {idx + 1} of {total_accounts}")
        current_account.markdown(f"📊 Analyzing: **{account_name}**")

        try:
            fields = row_to_fields(row, planning_fy, detected_format)

            if fields.get('_parsed_with_ai'):
                ai_parsed_count += 1
                parsing_info.caption(f"🤖 AI fallback used for {ai_parsed_count} account(s)")

            qual_context = ''
            for col in row.index:
                if col.lower().strip() == 'qualitative context':
                    qual_context = str(row[col]) if pd.notna(row[col]) else ''
                    break

            prompt = get_analysis_prompt(fields, fy_context, qual_context)
            analysis = call_cortex_complete(prompt)
            parsed = parse_analysis_response(analysis)

            summary = extract_bulk_summary(parsed, fields)
            summary['_row_index'] = idx
            results.append(summary)

        except Exception as e:
            errors.append({'row': idx + 1, 'account': account_name, 'error': str(e)})
            results.append({
                'Account Name': account_name,
                'Contract End': 'ERROR',
                'Overage Date': 'N/A',
                'Urgency': 'N/A',
                'Recommended Scenario': 'ERROR',
                'Total TACV': 'N/A',
                'Renewal ACV': 'N/A',
                'Growth ACV': 'N/A',
                'Quota-Bearing TACV': 'N/A',
                'Non-Quota TACV': 'N/A',
                'Confidence': 'N/A',
                'Key Flags': f'Error: {str(e)[:50]}',
                'Rationale': f'Processing failed: {e}',
                '_raw_analysis': '',
                '_parse_error': True,
                '_row_index': idx,
            })

        time.sleep(0.5)

    st.session_state.bulk_results = results
    st.session_state.bulk_errors = errors
    st.session_state.bulk_processing_status = 'complete'

    progress_bar.empty()
    status_text.empty()
    current_account.empty()
    st.rerun()


# ============================================
# RESULTS VIEW
# ============================================

def _render_results():
    """Render the results table and export options."""

    results = st.session_state.bulk_results

    st.markdown("#### ✅ Analysis Complete")

    total = len(results)
    failed = len([r for r in results if r.get('_parse_error', False)])
    succeeded = total - failed

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Processed", total)
    with col2:
        st.metric("Succeeded", succeeded, delta=None if succeeded == total else f"-{failed}")
    with col3:
        st.metric("Failed", failed, delta=None if failed == 0 else None, delta_color="inverse")
    with col4:
        st.metric("Planning FY", st.session_state.bulk_planning_fy or get_default_planning_fy())

    st.markdown("---")

    st.markdown("### 📊 Results")

    display_columns = [
        'Account Name', 'Overage Date', 'Urgency', 'Recommended Scenario',
        'Total TACV', 'Quota-Bearing TACV', 'Confidence', 'Key Flags',
    ]
    display_df = pd.DataFrame(results)[display_columns] if results else pd.DataFrame()

    if not display_df.empty:
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Account Name': st.column_config.TextColumn('Account Name', width='medium'),
                'Overage Date': st.column_config.TextColumn('Overage Date', width='small', help='Date when capacity runs out'),
                'Urgency': st.column_config.TextColumn('Urgency', width='small', help='CRITICAL = <3mo, HIGH = 3-6mo, MEDIUM = 6-12mo, LOW = 12+mo'),
                'Recommended Scenario': st.column_config.TextColumn('Scenario', width='small'),
                'Total TACV': st.column_config.TextColumn('Total TACV', width='small'),
                'Quota-Bearing TACV': st.column_config.TextColumn('Quota-Bearing', width='small'),
                'Confidence': st.column_config.TextColumn('Confidence', width='small'),
            },
        )

    st.markdown("### 🔍 Detailed Analysis")
    st.caption("Click on an account to view its full analysis")

    for result in results:
        if result.get('_parse_error'):
            with st.expander(f"❌ {result['Account Name']} (ERROR)", expanded=False):
                st.error(result.get('Rationale', 'Unknown error'))
        else:
            scenario = result.get('Recommended Scenario', 'N/A')
            tacv = result.get('Total TACV', 'N/A')
            with st.expander(f"📊 {result['Account Name']} → {scenario} ({tacv})", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total TACV", result.get('Total TACV', 'N/A'))
                with col2:
                    st.metric("Quota-Bearing", result.get('Quota-Bearing TACV', 'N/A'))
                with col3:
                    st.metric("Confidence", result.get('Confidence', 'N/A'))

                st.markdown("**TACV Breakdown:**")
                st.markdown(f"- Renewal ACV: {result.get('Renewal ACV', 'N/A')}")
                st.markdown(f"- Growth ACV: {result.get('Growth ACV', 'N/A')}")
                st.markdown(f"- Non-Quota TACV: {result.get('Non-Quota TACV', 'N/A')}")

                st.markdown("**Rationale:**")
                st.markdown(escape_dollars(result.get('Rationale', 'N/A')))

                if result.get('Key Flags') and result.get('Key Flags') != 'None':
                    st.markdown("**Flags:**")
                    st.warning(result.get('Key Flags'))

                raw = result.get('_raw_analysis', '')
                if raw:
                    with st.expander("View Full Analysis", expanded=False):
                        st.text_area("Raw Output", raw, height=300, disabled=True)

    st.markdown("---")

    st.markdown("### 📥 Export Results")
    _render_export(results)

    st.markdown("---")

    if st.button("🔄 Start New Bulk Analysis", type="primary", use_container_width=True):
        reset_bulk_state()
        st.rerun()


# ============================================
# EXPORT VIEW
# ============================================

def _render_export(results: List[Dict[str, Any]]):
    """Render export buttons for bulk results."""

    if not results:
        st.warning("No results to export.")
        return

    export_columns = [
        'Account Name', 'Contract End', 'Recommended Scenario',
        'Total TACV', 'Renewal ACV', 'Growth ACV',
        'Quota-Bearing TACV', 'Non-Quota TACV',
        'Confidence', 'Key Flags', 'Rationale',
    ]
    export_df = pd.DataFrame(results)[export_columns]

    planning_fy = st.session_state.bulk_planning_fy or get_default_planning_fy()
    today = datetime.now().strftime('%Y%m%d')
    filename = f"TACV_Bulk_Analysis_{planning_fy}_{today}"

    col1, col2 = st.columns(2)
    with col1:
        csv_data = export_df.to_csv(index=False)
        st.download_button(
            label="📄 Download CSV",
            data=csv_data,
            file_name=f"{filename}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col2:
        buf = io.BytesIO()
        export_df.to_excel(buf, index=False, engine='openpyxl')
        st.download_button(
            label="📊 Download Excel",
            data=buf.getvalue(),
            file_name=f"{filename}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
