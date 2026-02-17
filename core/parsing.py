"""
TACV Data Parsing
=================
All data parsing logic: deterministic, AI-powered, and smart multi-format parsing.
Handles tab-delimited, CSV, pipe-delimited, key-value, and Pigment export formats.
"""

import io
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from core.config import IS_SNOWFLAKE, MODEL_PARSING, MODEL_FALLBACK_PARSING, TIER_1_FIELDS, logger, session
from core.utils import get_column_multiplier, get_fiscal_year_context, parse_currency, parse_date


def normalize_column_name(col: str, planning_fy: str) -> Optional[str]:
    """Map column names to standardized field names based on actual field rep data formats."""
    col_lower = col.lower().strip()
    col_no_spaces = col_lower.replace(' ', '')
    
    # Get FY context for dynamic year matching
    fy_context = get_fiscal_year_context(planning_fy)
    fy_num = fy_context['fy_num']
    
    # ============================================
    # Account Name - check first, be specific
    # ============================================
    # Match: "Ult-Parent Name", "Acct Name", "Account Name", "Customer Name"
    if col_lower in ['ult-parent name', 'acct name', 'account name', 'customer name']:
        return 'account_name'
    if col_lower == 'account' or col_lower == 'customer':
        return 'account_name'
    
    # ============================================
    # Contract End Date
    # ============================================
    if any(x in col_lower for x in ['contract end date', 'contract end', 'end date']):
        if 'segment' not in col_lower:  # Exclude "Segment Capacity Overage Date"
            return 'contract_end_date'
    
    # ============================================
    # Capacity Remaining
    # ============================================
    # Match: "Capacity Usage Remaining ($K)", "Capacity Remaining"
    if 'capacity' in col_lower and 'remaining' in col_lower:
        return 'capacity_remaining'
    
    # ============================================
    # L90D Burn Rate / Annualized Run Rate
    # ============================================
    # Match: "Annualized Run Rate (L90D) ($K)", "L90D", "90D Burn"
    if 'l90d' in col_lower or '(l90d)' in col_lower:
        return 'l90d_burn_rate'
    if 'run rate' in col_lower and '90' in col_lower:
        return 'l90d_burn_rate'
    if '90d burn' in col_lower or '90 day' in col_lower:
        return 'l90d_burn_rate'
    # Match: "FY27 Trailing 91D Consumption_Average" as backup for L90D
    if 'trailing 91d' in col_lower and 'average' in col_lower:
        return 'l90d_burn_rate'
    
    # ============================================
    # L30D Burn Rate / Annualized Run Rate
    # ============================================
    # Match: "Annualized Run Rate (L30D) ($K)", "L30D", "30D Burn"
    if 'l30d' in col_lower or '(l30d)' in col_lower:
        return 'l30d_burn_rate'
    if 'run rate' in col_lower and '30' in col_lower:
        return 'l30d_burn_rate'
    if '30d burn' in col_lower or '30 day' in col_lower:
        return 'l30d_burn_rate'
    
    # ============================================
    # Prior Renewal Base
    # ============================================
    # Match: "Prior Renewal Base ($K)", "Renewal Base", "Prior Base"
    if 'prior renewal base' in col_lower or 'renewal base' in col_lower:
        return 'prior_renewal_base'
    if 'prior base' in col_lower or 'base acv' in col_lower:
        return 'prior_renewal_base'
    
    # ============================================
    # FY Prediction (Planning Year)
    # ============================================
    # Match: "FY27 Consumption Prediction ($K)" for FY27 planning
    # Be specific: must have "prediction" and the planning FY
    if f'fy{fy_num}' in col_no_spaces and 'consumption prediction' in col_lower:
        return 'planning_fy_prediction'
    if f'fy{fy_num}' in col_no_spaces and 'prediction' in col_lower and 'overage' not in col_lower:
        return 'planning_fy_prediction'
    
    # ============================================
    # Prior FY Actuals
    # ============================================
    # Match: "FY26 Consumption Actuals ($K)" when planning FY27
    if f'fy{fy_num - 1}' in col_no_spaces and 'consumption actuals' in col_lower:
        return 'prior_fy_actuals'
    if f'fy{fy_num - 1}' in col_no_spaces and 'actuals' in col_lower:
        return 'prior_fy_actuals'
    
    # ============================================
    # Prior FY - 1 Actuals (two years back)
    # ============================================
    # Match: "FY25 Consumption Actuals ($K)" when planning FY27
    if f'fy{fy_num - 2}' in col_no_spaces and 'consumption actuals' in col_lower:
        return 'prior_fy_minus_1_actuals'
    if f'fy{fy_num - 2}' in col_no_spaces and 'actuals' in col_lower:
        return 'prior_fy_minus_1_actuals'
    
    # ============================================
    # Contract Predicted Overage
    # ============================================
    # Match: "Contract Predicted Overage ($K)" - must have "contract" to distinguish
    if 'contract' in col_lower and 'predicted overage' in col_lower:
        return 'contract_predicted_overage'
    if 'contract' in col_lower and 'overage' in col_lower and 'date' not in col_lower:
        return 'contract_predicted_overage'
    
    # ============================================
    # Account Segment - be very specific to avoid false matches
    # ============================================
    # Match: "Proposed Segment", "Account Segment", "Acct Segment"
    # Exclude: "Segment Capacity Overage", "Segment Capacity Overage Date"
    if col_lower == 'proposed segment' or col_lower == 'account segment' or col_lower == 'acct segment':
        return 'account_segment'
    # General "segment" match but exclude capacity/overage columns
    if 'segment' in col_lower:
        if 'capacity' not in col_lower and 'overage' not in col_lower and 'date' not in col_lower:
            if col_lower in ['segment', 'tier', 'account tier']:
                return 'account_segment'
    
    # ============================================
    # Account Owner
    # ============================================
    # Match: "FY26 Owner Name", "FY27 Owner Name", "Account Owner", "AE"
    if 'owner name' in col_lower:
        return 'account_owner'
    if col_lower in ['owner', 'ae', 'account owner', 'account executive', 'rep']:
        return 'account_owner'
    
    return None


def parse_pasted_data(raw_text: str, planning_fy: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parse tab-delimited data from Google Sheets.
    Returns (parsed_fields dict, list of warnings)
    """
    warnings = []
    parsed_fields = {}
    
    if not raw_text or not raw_text.strip():
        return parsed_fields, ["No data provided"]
    
    lines = raw_text.strip().split('\n')
    
    if len(lines) < 2:
        return parsed_fields, ["Expected at least 2 lines (header + data)"]
    
    # Parse header and data rows
    headers = lines[0].split('\t')
    data_row = lines[1].split('\t')
    
    # Map columns to standardized names
    for i, col in enumerate(headers):
        if i >= len(data_row):
            continue
        
        std_name = normalize_column_name(col, planning_fy)
        if std_name:
            raw_value = data_row[i].strip()
            
            # Parse based on field type
            if std_name == 'contract_end_date':
                parsed_value = parse_date(raw_value)
                if parsed_value:
                    parsed_fields[std_name] = parsed_value
                else:
                    warnings.append(f"Could not parse date: {raw_value}")
            elif std_name == 'account_name':
                parsed_fields[std_name] = raw_value
            elif std_name in ['account_segment', 'account_owner']:
                parsed_fields[std_name] = raw_value
            else:
                # Assume currency for other fields
                parsed_value = parse_currency(raw_value)
                if parsed_value is not None:
                    # Check if column header indicates a unit multiplier ($K, $M, etc.)
                    multiplier = get_column_multiplier(col)
                    parsed_fields[std_name] = parsed_value * multiplier
                elif raw_value:
                    warnings.append(f"Could not parse currency value for {col}: {raw_value}")
    
    return parsed_fields, warnings


# ============================================
# LAYERED PARSING SYSTEM
# ============================================

def detect_delimiter(text: str) -> str:
    """Detect the most likely delimiter in the text."""
    lines = text.strip().split('\n')
    if not lines:
        return 'unknown'
    
    first_line = lines[0]
    
    # Count potential delimiters
    tab_count = first_line.count('\t')
    comma_count = first_line.count(',')
    pipe_count = first_line.count('|')
    colon_count = first_line.count(':')
    
    # Tab-delimited (from spreadsheets)
    if tab_count >= 2:
        return 'tab'
    
    # CSV (but avoid counting commas in currency values)
    # Remove currency patterns before counting
    cleaned = re.sub(r'\$[\d,]+', '', first_line)
    real_comma_count = cleaned.count(',')
    if real_comma_count >= 2:
        return 'csv'
    
    # Pipe-delimited (from markdown tables or some exports)
    if pipe_count >= 2:
        return 'pipe'
    
    # Key-value pairs (Account Name: Acme Corp)
    if colon_count >= 1 and len(lines) >= 3:
        # Check if multiple lines have colons
        colon_lines = sum(1 for line in lines if ':' in line)
        if colon_lines >= 3:
            return 'key_value'
    
    return 'unknown'


def parse_dataframe_to_fields(df: pd.DataFrame, planning_fy: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Convert a DataFrame (from any source) to standardized parsed fields.
    Handles the first data row only.
    """
    warnings = []
    parsed_fields = {}
    
    if df.empty:
        return parsed_fields, ["DataFrame is empty"]
    
    # Use first row of data
    data_row = df.iloc[0]
    
    for col in df.columns:
        std_name = normalize_column_name(str(col), planning_fy)
        if not std_name:
            continue
        
        raw_value = str(data_row[col]).strip() if pd.notna(data_row[col]) else ''
        if not raw_value:
            continue
        
        # Parse based on field type
        if std_name == 'contract_end_date':
            parsed_value = parse_date(raw_value)
            if parsed_value:
                parsed_fields[std_name] = parsed_value
            else:
                warnings.append(f"Could not parse date: {raw_value}")
        elif std_name in ['account_name', 'account_segment', 'account_owner']:
            parsed_fields[std_name] = raw_value
        else:
            # Currency fields
            parsed_value = parse_currency(raw_value)
            if parsed_value is not None:
                multiplier = get_column_multiplier(str(col))
                parsed_fields[std_name] = parsed_value * multiplier
            elif raw_value:
                warnings.append(f"Could not parse currency for {col}: {raw_value}")
    
    return parsed_fields, warnings


def parse_csv_data(raw_text: str, planning_fy: str) -> Tuple[Dict[str, Any], List[str]]:
    """Parse comma-separated data."""
    try:
        df = pd.read_csv(io.StringIO(raw_text))
        return parse_dataframe_to_fields(df, planning_fy)
    except Exception as e:
        return {}, [f"CSV parsing failed: {str(e)}"]


def parse_pipe_delimited(raw_text: str, planning_fy: str) -> Tuple[Dict[str, Any], List[str]]:
    """Parse pipe-delimited data (common in markdown tables)."""
    lines = raw_text.strip().split('\n')
    
    # Filter out separator lines (like |---|---|)
    lines = [l for l in lines if not re.match(r'^[\s|:-]+$', l)]
    
    if len(lines) < 2:
        return {}, ["Expected at least 2 lines (header + data)"]
    
    # Parse by splitting on pipes
    def clean_cell(cell):
        return cell.strip().strip('|').strip()
    
    headers = [clean_cell(c) for c in lines[0].split('|') if clean_cell(c)]
    data_values = [clean_cell(c) for c in lines[1].split('|') if clean_cell(c)]
    
    # Build a DataFrame
    if len(headers) != len(data_values):
        # Try to align
        min_len = min(len(headers), len(data_values))
        headers = headers[:min_len]
        data_values = data_values[:min_len]
    
    df = pd.DataFrame([data_values], columns=headers)
    return parse_dataframe_to_fields(df, planning_fy)


def parse_key_value(raw_text: str, planning_fy: str) -> Tuple[Dict[str, Any], List[str]]:
    """Parse key-value format (Account Name: Acme Corp)."""
    warnings = []
    parsed_fields = {}
    
    lines = raw_text.strip().split('\n')
    
    for line in lines:
        if ':' not in line:
            continue
        
        # Split on first colon only
        parts = line.split(':', 1)
        if len(parts) != 2:
            continue
        
        key = parts[0].strip()
        value = parts[1].strip()
        
        std_name = normalize_column_name(key, planning_fy)
        if not std_name or not value:
            continue
        
        # Parse based on field type
        if std_name == 'contract_end_date':
            parsed_value = parse_date(value)
            if parsed_value:
                parsed_fields[std_name] = parsed_value
            else:
                warnings.append(f"Could not parse date: {value}")
        elif std_name in ['account_name', 'account_segment', 'account_owner']:
            parsed_fields[std_name] = value
        else:
            parsed_value = parse_currency(value)
            if parsed_value is not None:
                multiplier = get_column_multiplier(key)
                parsed_fields[std_name] = parsed_value * multiplier
            elif value:
                warnings.append(f"Could not parse currency for {key}: {value}")
    
    return parsed_fields, warnings


def smart_parse(raw_text: str, planning_fy: str) -> Tuple[Dict[str, Any], List[str], str]:
    """
    Intelligently detect format and parse data.
    Returns: (parsed_fields, warnings, detected_format)
    """
    if not raw_text or not raw_text.strip():
        return {}, ["No data provided"], 'unknown'
    
    # Detect format
    detected_format = detect_delimiter(raw_text)
    
    # Route to appropriate parser
    if detected_format == 'tab':
        parsed, warnings = parse_pasted_data(raw_text, planning_fy)
    elif detected_format == 'csv':
        parsed, warnings = parse_csv_data(raw_text, planning_fy)
    elif detected_format == 'pipe':
        parsed, warnings = parse_pipe_delimited(raw_text, planning_fy)
    elif detected_format == 'key_value':
        parsed, warnings = parse_key_value(raw_text, planning_fy)
    else:
        # Try all parsers in order of likelihood
        parsed, warnings = parse_pasted_data(raw_text, planning_fy)
        if not parsed:
            parsed, warnings = parse_csv_data(raw_text, planning_fy)
        if not parsed:
            parsed, warnings = parse_key_value(raw_text, planning_fy)
        if not parsed:
            detected_format = 'unknown'
    
    # Check for missing required fields
    required = set(TIER_1_FIELDS.keys())
    found = set(parsed.keys())
    missing = required - found
    
    if missing and parsed:  # Partial success
        missing_labels = [TIER_1_FIELDS[f]['label'] for f in missing if f in TIER_1_FIELDS]
        warnings.append(f"Missing required fields: {', '.join(missing_labels)}")
    
    return parsed, warnings, detected_format


# ============================================
# DETERMINISTIC COLUMN EXTRACTION FOR PIGMENT EXPORTS
# ============================================

def extract_columns_deterministically(raw_text: str, planning_fy: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Deterministically extract fields from tab-delimited or CSV data by matching column headers.
    This is more reliable than AI for wide data (70+ columns) like Pigment exports.
    
    Returns: (extracted_fields, notes)
    """
    notes = []
    extracted = {}
    
    if not raw_text or not raw_text.strip():
        return {}, notes
    
    lines = raw_text.strip().split('\n')
    if len(lines) < 2:
        return {}, notes
    
    # Detect delimiter
    first_line = lines[0]
    if '\t' in first_line:
        delimiter = '\t'
    elif ',' in first_line:
        delimiter = ','
    else:
        return {}, ["Could not detect delimiter for deterministic extraction"]
    
    # Parse headers and data
    headers = first_line.split(delimiter)
    data_parts = lines[1].split(delimiter)
    
    # ============================================
    # PIGMENT EXPORT ALIGNMENT FIX
    # ============================================
    # Pigment exports can have several patterns:
    # Pattern A: Header starts with TAB (empty first), data starts with ID|Name
    # Pattern B: Header starts normally, data has extra ID|Name reference at start
    # Pattern C: Both have same count but misaligned
    
    def looks_like_pigment_reference(value: str) -> bool:
        """Detect if a value looks like a Pigment reference column (ID | Name pattern)."""
        if not value:
            return False
        value = value.strip()
        # Pattern 1: Salesforce ID (18 chars starting with 001)
        if value.startswith('001') and len(value) >= 15:
            return True
        # Pattern 2: "ID | Name" format where ID is a Salesforce ID
        if '|' in value:
            parts = value.split('|')
            first_part = parts[0].strip()
            if first_part.startswith('001') and len(first_part) >= 15:
                return True
        return False
    
    first_header = headers[0].strip() if headers else ''
    first_data = data_parts[0].strip() if data_parts else ''
    
    # ============================================
    # CASE A: Data has MORE columns than headers
    # ============================================
    if len(data_parts) > len(headers):
        if looks_like_pigment_reference(first_data):
            data_parts = data_parts[1:]
        elif first_data == '' or first_data.replace('-', '').replace('.', '').isdigit():
            data_parts = data_parts[1:]
    
    # ============================================
    # CASE B: Headers have empty first column
    # ============================================
    elif first_header == '':
        if len(headers) > len(data_parts):
            headers = headers[1:]
        
        elif len(headers) == len(data_parts):
            if looks_like_pigment_reference(first_data):
                headers = headers[1:]
                data_parts = data_parts[1:]
            elif first_data == '' or first_data.replace('-', '').replace('.', '').isdigit():
                headers = headers[1:]
                data_parts = data_parts[1:]
            else:
                # Verify alignment by checking capacity column
                test_column_values = {}
                for i, header in enumerate(headers):
                    h = ' '.join(header.strip().lower().split())
                    if h and i < len(data_parts):
                        test_column_values[h] = data_parts[i].strip()
                
                capacity_col = 'capacity usage remaining ($k)'
                if capacity_col in test_column_values:
                    cap_val = test_column_values[capacity_col]
                    cap_clean = cap_val.replace('$', '').replace(',', '').replace('.', '').replace('-', '')
                    if not (cap_val and cap_clean.isdigit()):
                        headers = headers[1:]
                        data_parts = data_parts[1:]
    
    # ============================================
    # CASE C: Same count, no empty header, but first data is ID|Name
    # ============================================
    elif len(headers) == len(data_parts) and looks_like_pigment_reference(first_data):
        test_column_values = {}
        for i, header in enumerate(headers):
            h = ' '.join(header.strip().lower().split())
            if h and i < len(data_parts):
                test_column_values[h] = data_parts[i].strip()
        
        capacity_col = 'capacity usage remaining ($k)'
        if capacity_col in test_column_values:
            cap_val = test_column_values[capacity_col]
            cap_clean = cap_val.replace('$', '').replace(',', '').replace('.', '').replace('-', '')
            if not (cap_val and cap_clean.isdigit()):
                pass  # Possible misalignment, but can't fix automatically
    
    # Build column name -> value mapping
    # Normalize headers: lowercase, strip whitespace, normalize unicode
    column_values = {}
    for i, header in enumerate(headers):
        # Clean header: strip, lowercase, normalize whitespace
        header_clean = ' '.join(header.strip().lower().split())
        if header_clean and i < len(data_parts):
            column_values[header_clean] = data_parts[i].strip()
    
    if not column_values:
        return {}, ["No column values extracted"]
    
    
    # Get FY context
    fy_context = get_fiscal_year_context(planning_fy)
    fy_num = fy_context['fy_num']
    
    # Column matching rules with multipliers
    # Format: (field_name, [(column_pattern, multiplier), ...])
    field_mappings = [
        ('account_name', [
            ('ult-parent name', 1),
            ('acct name', 1),
            ('account name', 1),
        ]),
        ('account_id', [
            ('account id', 1),
            ('ult-parent id', 1),
        ]),
        ('contract_end_date', [
            ('contract end date', 1),
            ('contract end', 1),
        ]),
        ('capacity_remaining', [
            ('capacity usage remaining ($k)', 1000),
            ('capacity usage remaining', 1),
            ('capacity remaining ($k)', 1000),
            ('capacity remaining', 1),
        ]),
        ('l90d_burn_rate', [
            ('annualized run rate (l90d) ($k)', 1000),
            (f'fy{fy_num} trailing 91d consumption_average ($k)', 1000),
            ('trailing 91d consumption_average ($k)', 1000),
        ]),
        ('l30d_burn_rate', [
            ('annualized run rate (l30d) ($k)', 1000),
        ]),
        ('prior_renewal_base', [
            ('prior renewal base ($k)', 1000),
            ('prior renewal base', 1),
        ]),
        ('planning_fy_prediction', [
            (f'fy{fy_num} consumption prediction ($k)', 1000),
        ]),
        ('prior_fy_prediction', [
            (f'fy{fy_num - 1} consumption prediction ($k)', 1000),
        ]),
        ('prior_fy_actuals', [
            (f'fy{fy_num - 1} consumption actuals ($k)', 1000),
        ]),
        ('prior_fy_minus_1_actuals', [
            (f'fy{fy_num - 2} consumption actuals ($k)', 1000),
        ]),
        ('account_segment', [
            ('proposed segment', 1),
            ('account segment', 1),
        ]),
        ('account_owner', [
            (f'fy{fy_num} owner name', 1),
            (f'fy{fy_num - 1} owner name', 1),
            ('owner name', 1),
        ]),
        ('account_category', [
            ('acct category', 1),
        ]),
        ('is_consecutive_downsell', [
            ('is consecutive downsell?', 1),
        ]),
        ('contract_predicted_overage', [
            ('contract predicted overage ($k)', 1000),
            (f'fy{fy_num} predicted overage ($k)', 1000),
        ]),
    ]
    
    # Extract each field
    for field_name, patterns in field_mappings:
        for pattern, multiplier in patterns:
            if pattern in column_values:
                raw_value = column_values[pattern]
                
                # Skip empty values
                if not raw_value or raw_value in ['', '—', '-']:
                    continue
                
                # Parse based on field type
                if field_name == 'contract_end_date':
                    parsed_date = parse_date(raw_value)
                    if parsed_date:
                        extracted[field_name] = parsed_date
                        break
                
                elif field_name in ['account_name', 'account_segment', 'account_owner', 'account_category', 'account_id']:
                    val_str = raw_value.strip()
                    # Handle "ID | Name" format
                    if field_name == 'account_name' and '|' in val_str:
                        val_str = val_str.split('|')[-1].strip()
                    elif field_name == 'account_id' and '|' in val_str:
                        val_str = val_str.split('|')[0].strip()
                    extracted[field_name] = val_str
                    break
                
                elif field_name == 'is_consecutive_downsell':
                    extracted[field_name] = raw_value.upper() in ['TRUE', 'YES', '1']
                    break
                
                else:
                    # Numeric field with multiplier
                    parsed = parse_currency(raw_value)
                    if parsed is not None:
                        extracted[field_name] = parsed * multiplier
                        break
    
    return extracted, notes


# ============================================
# PRE-PROCESSING FOR PIGMENT EXPORTS
# ============================================

def preprocess_input_text(raw_text: str) -> Tuple[str, List[str]]:
    """
    Pre-process input text to handle common Pigment export issues.
    
    Fixes:
    - Empty first column header (shifts data alignment)
    - Leading/trailing whitespace
    - Inconsistent delimiters
    
    Returns: (cleaned_text, list of preprocessing notes)
    """
    notes = []
    
    if not raw_text or not raw_text.strip():
        return raw_text, notes
    
    lines = raw_text.strip().split('\n')
    if len(lines) < 2:
        return raw_text, notes
    
    # Detect delimiter
    first_line = lines[0]
    if '\t' in first_line:
        delimiter = '\t'
    elif ',' in first_line:
        delimiter = ','
    else:
        return raw_text, notes  # Can't pre-process unknown format
    
    # Check for empty first column header (common Pigment issue)
    headers = first_line.split(delimiter)
    
    if headers and headers[0].strip() == '':
        # Empty first column header detected
        data_parts = lines[1].split(delimiter) if len(lines) > 1 else []
        
        if len(headers) > len(data_parts):
            # CASE 1: Headers have MORE columns than data - remove empty first header
            headers = headers[1:]
            lines[0] = delimiter.join(headers)
            return '\n'.join(lines), notes
        
        elif len(data_parts) == len(headers):
            # CASE 2: Same column count - remove empty first column from both
            cleaned_lines = []
            for line in lines:
                parts = line.split(delimiter)
                if parts and (parts[0].strip() == '' or parts[0].strip().isdigit()):
                    cleaned_lines.append(delimiter.join(parts[1:]))
                else:
                    cleaned_lines.append(line)
            return '\n'.join(cleaned_lines), notes
        
        elif len(data_parts) > len(headers):
            # CASE 3: Data has more columns - add placeholder header
            headers[0] = '_row_index'
            lines[0] = delimiter.join(headers)
            return '\n'.join(lines), notes
    
    return raw_text, notes


def preprocess_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Pre-process a DataFrame to handle Pigment export issues.
    
    Fixes:
    - Unnamed columns (empty headers become 'Unnamed: 0', etc.)
    - Row index columns
    
    Returns: (cleaned_df, list of preprocessing notes)
    """
    notes = []
    df = df.copy()
    
    # Check for Unnamed columns (pandas creates these for empty headers)
    unnamed_cols = [col for col in df.columns if str(col).startswith('Unnamed:')]
    
    if unnamed_cols:
        # Check if these columns contain just row indices
        for col in unnamed_cols:
            # If column contains sequential integers or is empty, drop it
            col_values = df[col].dropna()
            if col_values.empty:
                df = df.drop(columns=[col])
            elif col_values.apply(lambda x: str(x).isdigit()).all():
                # Likely a row index column
                df = df.drop(columns=[col])
    
    return df, notes


# ============================================
# AI-POWERED DATA EXTRACTION (HAIKU - FAST & CHEAP)
# ============================================

def extract_data_with_haiku(raw_text: str, planning_fy: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Use Claude Haiku 4.5 via Cortex for fast, cheap semantic parsing.
    Haiku is optimized for structured extraction tasks and costs ~10x less than Sonnet.
    
    Model usage:
    - Haiku 4.5: Data parsing (this function) - fast, cheap, great for structured extraction
    - Sonnet 4.5: TACV analysis - complex reasoning, scenario modeling
    
    This is the PRIMARY parsing method - semantic understanding handles:
    - Column name variations from Pigment
    - Column order changes
    - Empty/missing headers
    - Format variations in exports
    
    Strategy:
    1. Try deterministic column extraction first (more reliable for wide Pigment data)
    2. Fall back to AI parsing if deterministic extraction returns insufficient fields
    """
    # ============================================
    # STEP 1: Try deterministic extraction first (more reliable for wide data)
    # ============================================
    det_extracted, det_notes = extract_columns_deterministically(raw_text, planning_fy)
    
    # Check if deterministic extraction got the key required fields
    required_fields = {'capacity_remaining', 'l90d_burn_rate', 'prior_renewal_base', 'contract_end_date'}
    det_required_found = required_fields.intersection(det_extracted.keys())
    
    if len(det_required_found) >= 3:
        # Deterministic extraction successful - use it
        return det_extracted, det_notes
    
    # ============================================
    # STEP 2: Fall back to AI parsing
    # ============================================
    # Note: Deterministic extraction only found {len(det_required_found)} of 4 required fields
    # Falling back to AI for better field extraction
    
    # Pre-process the input first
    cleaned_text, preprocess_notes = preprocess_input_text(raw_text)
    preprocess_notes.extend([n for n in det_notes if n])  # Include deterministic notes
    
    fy_context = get_fiscal_year_context(planning_fy)
    fy_num = fy_context['fy_num']
    
    # Compact prompt optimized for Haiku
    prompt = f"""Extract account data from this text and return valid JSON.

IMPORTANT: The input may have column alignment issues (empty first column header, shifted data). 
You MUST match values to columns by COLUMN NAME, not by position. Find each column header and extract its corresponding value.

FIELD MAPPINGS (use these exact output field names):
- account_name: from "Ult-Parent Name", "Acct Name", "Account Name" (if "ID | Name" format, extract just the Name part after the |)
- account_id: from "Account ID", "Ult-Parent ID", or if "Ult-Parent Name" has format "001xxxxx | Name", extract the ID part (18-char starting with 001)
- contract_end_date: from "Contract End Date" → format as YYYY-MM-DD
- capacity_remaining: from "Capacity Usage Remaining ($K)" - this is remaining capacity, NOT consumption actuals
- l90d_burn_rate: from "Annualized Run Rate (L90D) ($K)", "FY27 Trailing 91D Consumption_Average ($K)"
- l30d_burn_rate: from "Annualized Run Rate (L30D) ($K)"
- prior_renewal_base: from "Prior Renewal Base ($K)"
- planning_fy_prediction: from "FY{fy_num} Consumption Prediction ($K)"
- prior_fy_prediction: from "FY{fy_num - 1} Consumption Prediction ($K)"
- prior_fy_actuals: from "FY{fy_num - 1} Consumption Actuals ($K)"
- prior_fy_minus_1_actuals: from "FY{fy_num - 2} Consumption Actuals ($K)"
- account_segment: from "Proposed Segment", "Account Segment"
- account_owner: from "FY{fy_num} Owner Name", "FY{fy_num - 1} Owner Name", "Owner Name"
- is_consecutive_downsell: from "Is Consecutive Downsell?" (true/false)
- account_category: from "Acct Category"

CRITICAL RULES:
1. SEMANTIC MATCHING: Find column headers by name, then extract their values. DO NOT use column positions.
2. Apply multipliers from headers: ($K)=×1000, ($M)=×1000000. Example: "Capacity Usage Remaining ($K)" with value "$1,157" = 1157000
3. Parse currencies: "$460"→460, "$1,157"→1157, "2,652"→2652
4. Dates: "9/14/2026"→"2026-09-14", "6/30/2027"→"2027-06-30"
5. Skip empty/"—" values
6. For tab-delimited data: first line is headers, second line is values. Match them by counting tabs.

INPUT:
{cleaned_text}

JSON:"""

    if IS_SNOWFLAKE:
        try:
            escaped_prompt = prompt.replace("'", "''")
            # Use MODEL_PARSING for fast, cheap semantic parsing
            # Sonnet is reserved for TACV analysis (more complex reasoning)
            result = session.sql(f"""
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    '{MODEL_PARSING}',
                    '{escaped_prompt}'
                ) AS response
            """).collect()
            
            response = result[0]['RESPONSE']
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                parsed = json.loads(json_match.group())
                warnings = preprocess_notes.copy()
                validated = validate_extracted_fields(parsed)
                
                if validated:
                    return validated, warnings
                else:
                    return {}, ["AI extraction returned no valid fields"]
            else:
                return {}, ["AI extraction failed: Could not parse JSON response"]
                
        except Exception as e:
            error_msg = str(e)
            # If Haiku fails for any reason, fall back to Sonnet
            if 'model' in error_msg.lower() or 'haiku' in error_msg.lower():
                return extract_data_with_ai(raw_text, planning_fy)
            return {}, [f"AI extraction error: {error_msg}"]
    else:
        # Mock for local development
        return {
            'account_name': 'AI Extracted Account (Mock)',
            'contract_end_date': '2027-01-15',
            'capacity_remaining': 17600000.0,
            'l90d_burn_rate': 2260000.0,
            'prior_renewal_base': 15000000.0,
        }, []


def validate_extracted_fields(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize fields extracted by AI."""
    validated = {}
    
    for key, value in parsed.items():
        if value is None:
            continue
            
        if key == 'contract_end_date' and value:
            parsed_date = parse_date(str(value))
            validated[key] = parsed_date if parsed_date else value
            
        elif key in ['account_name', 'account_segment', 'account_owner', 'account_category', 'account_id']:
            validated[key] = str(value) if value else None
            
        elif key == 'is_consecutive_downsell':
            if isinstance(value, bool):
                validated[key] = value
            elif isinstance(value, str):
                validated[key] = value.upper() in ['TRUE', 'YES', '1']
            else:
                validated[key] = bool(value)
                
        else:
            # Numeric fields
            try:
                validated[key] = float(value)
            except (ValueError, TypeError):
                parsed_val = parse_currency(str(value))
                if parsed_val is not None:
                    validated[key] = parsed_val
    
    # Remove None values
    return {k: v for k, v in validated.items() if v is not None}


def extract_data_with_ai(raw_text: str, planning_fy: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Use Cortex AI to extract structured data from any input format.
    This is now the primary parsing method for single account analysis.
    Handles tab-delimited, CSV, pipe-delimited, and unstructured formats.
    """
    fy_context = get_fiscal_year_context(planning_fy)
    fy_num = fy_context['fy_num']
    
    prompt = f"""You are a data extraction assistant for Snowflake account analysis. Extract account data from the input text and return it as valid JSON.

The input may be in various formats:
- Tab-delimited data with column headers (common from Google Sheets/Excel)
- CSV data
- Key-value pairs
- Unstructured text

COLUMN NAME MAPPINGS - Map these common column variations to the standardized field names:

REQUIRED FIELDS (always extract if present):
- account_name: Look for "Ult-Parent Name", "Acct Name", "Account Name", "Customer Name", "Company Name"
- contract_end_date: Look for "Contract End Date", "Contract End", "End Date" (return as YYYY-MM-DD)
- capacity_remaining: Look for "Capacity Usage Remaining", "Capacity Remaining" 
- l90d_burn_rate: Look for "Annualized Run Rate (L90D)", "L90D", "90D Burn Rate", "Trailing 91D Consumption_Average"
- prior_renewal_base: Look for "Prior Renewal Base"

OPTIONAL FIELDS (extract if found):
- l30d_burn_rate: Look for "Annualized Run Rate (L30D)", "L30D", "30D Burn Rate"
- planning_fy_prediction: Look for "FY{fy_num} Consumption Prediction", "FY{fy_num} Prediction"
- prior_fy_prediction: Look for "FY{fy_num - 1} Consumption Prediction", "FY{fy_num - 1} Prediction"
- account_segment: Look for "Proposed Segment", "Account Segment", "Segment" (e.g., "Enterprise", "Majors", "Commercial")
- account_owner: Look for "FY{fy_num} Owner Name", "FY{fy_num - 1} Owner Name", "Owner Name", "Account Owner", "AE"
- contract_predicted_overage: Look for "Contract Predicted Overage", "FY{fy_num} Predicted Overage"
- prior_fy_actuals: Look for "FY{fy_num - 1} Consumption Actuals", "FY{fy_num - 1} Actuals"
- prior_fy_minus_1_actuals: Look for "FY{fy_num - 2} Consumption Actuals", "FY{fy_num - 2} Actuals"

GUARDRAIL-RELATED FIELDS (for quota validation):
- is_consecutive_downsell: boolean - Look for "Is Consecutive Downsell?" (TRUE/FALSE)
- account_category: string - Look for "Acct Category" (e.g., "Customer", "Prospect")

CRITICAL INSTRUCTIONS FOR VALUE PARSING:

1. UNIT MULTIPLIERS: Column headers often specify units - apply them!
   - If column header contains "($K)" or "($K)": multiply value by 1,000
   - If column header contains "($M)": multiply value by 1,000,000
   - If column header contains "($B)": multiply value by 1,000,000,000
   - Example: Column "Prior Renewal Base ($K)" with value "460" → output 460000

2. CURRENCY PARSING: Remove formatting symbols
   - "$460" → 460
   - "2,652" → 2652
   - "$2.3M" → 2300000

3. DATE PARSING: Convert to YYYY-MM-DD format
   - "6/30/2027" → "2027-06-30"
   - "11/7/2026" → "2026-11-07"

4. TAB-DELIMITED FORMAT: When input has headers on line 1 and data on line 2+:
   - Parse headers to identify column types
   - Extract corresponding values from the data row
   - Apply unit multipliers based on column header indicators

5. EMPTY/MISSING VALUES: Skip fields with empty, blank, or "—" values

6. ACCOUNT NAME EXTRACTION: If the Account Name column contains a format like "ID | Name", extract just the Name part

OUTPUT: Return ONLY valid JSON with the extracted fields, no explanation or markdown.

INPUT TEXT:
{raw_text}

JSON OUTPUT:"""

    if IS_SNOWFLAKE:
        try:
            escaped_prompt = prompt.replace("'", "''")
            result = session.sql(f"""
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    '{MODEL_FALLBACK_PARSING}',
                    '{escaped_prompt}'
                ) AS response
            """).collect()
            
            response = result[0]['RESPONSE']
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                parsed = json.loads(json_match.group())
                
                # Validate and convert types using consolidated validation
                warnings = []
                validated = validate_extracted_fields(parsed)
                
                # Auto-populate guardrail context from extracted fields
                if 'is_consecutive_downsell' in validated:
                    if 'guardrail_context' not in st.session_state:
                        st.session_state.guardrail_context = {}
                    st.session_state.guardrail_context['is_declining_account'] = validated['is_consecutive_downsell']
                    warnings.append(f"Auto-detected declining account status: {'Yes' if validated['is_consecutive_downsell'] else 'No'}")
                
                # Infer account type from account_category
                if 'account_category' in validated:
                    if 'guardrail_context' not in st.session_state:
                        st.session_state.guardrail_context = {}
                    category = validated['account_category'].lower()
                    if 'prospect' in category:
                        st.session_state.guardrail_context['account_type'] = 'Acquisition'
                    elif 'customer' in category:
                        st.session_state.guardrail_context['account_type'] = 'Expansion'
                    warnings.append(f"Auto-detected account type: {st.session_state.guardrail_context['account_type']}")
                
                if validated:
                    warnings.append("Data extracted using AI - please verify values")
                    return validated, warnings
                else:
                    return {}, ["AI extraction returned no valid fields"]
            else:
                return {}, ["AI extraction failed: Could not parse JSON response"]
                
        except Exception as e:
            return {}, [f"AI extraction error: {str(e)}"]
    else:
        # Mock for local development
        return {
            'account_name': 'AI Extracted Account (Mock)',
            'contract_end_date': '2027-01-15',
            'capacity_remaining': 17600000.0,
            'l90d_burn_rate': 2260000.0,
            'prior_renewal_base': 15000000.0,
        }, []


def parse_uploaded_file(uploaded_file, planning_fy: str) -> Tuple[Dict[str, Any], List[str]]:
    """Parse an uploaded file (CSV, Excel, TSV)."""
    try:
        filename = uploaded_file.name.lower()
        
        if filename.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif filename.endswith('.tsv') or filename.endswith('.txt'):
            df = pd.read_csv(uploaded_file, sep='\t')
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            return {}, [f"Unsupported file format: {filename}"]
        
        if df.empty:
            return {}, ["Uploaded file is empty"]
        
        return parse_dataframe_to_fields(df, planning_fy)
        
    except Exception as e:
        return {}, [f"Error reading file: {str(e)}"]


def get_missing_required_fields(parsed_fields: Dict) -> List[str]:
    """Return list of missing required field labels."""
    required = set(TIER_1_FIELDS.keys())
    found = set(parsed_fields.keys())
    missing = required - found
    return [TIER_1_FIELDS[f]['label'] for f in missing if f in TIER_1_FIELDS]


# ============================================
# BULK PARSING HELPERS
# ============================================

def detect_bulk_format(df: pd.DataFrame) -> str:
    """Detect if the uploaded file is in Pigment format or simple template format."""
    from core.config import BULK_REQUIRED_COLUMNS, PIGMENT_INDICATOR_COLUMNS

    df_columns_lower = [col.lower().strip() for col in df.columns]

    pigment_matches = sum(1 for col in PIGMENT_INDICATOR_COLUMNS if col in df_columns_lower)
    if pigment_matches >= 2:
        return 'pigment'

    simple_matches = sum(1 for col in BULK_REQUIRED_COLUMNS if col.lower() in df_columns_lower)
    if simple_matches >= 3:
        return 'simple'

    return 'unknown'


def validate_bulk_upload(df: pd.DataFrame) -> Tuple[bool, List[str], str]:
    """
    Validate uploaded DataFrame has required columns.
    Returns: (is_valid, errors/warnings, detected_format)

    Note: DataFrame is preprocessed to handle Pigment export issues
    (empty first column headers, row indices, etc.)
    """
    from core.config import BULK_REQUIRED_COLUMNS

    errors: List[str] = []
    warnings: List[str] = []

    if len(df) == 0:
        errors.append("File contains no data rows")
        return False, errors, 'unknown'

    df, preprocess_notes = preprocess_dataframe(df)
    warnings.extend(preprocess_notes)

    detected_format = detect_bulk_format(df)
    df_columns_lower = [col.lower().strip() for col in df.columns]

    if detected_format == 'pigment':
        required_pigment = [
            ('account name', ['ult-parent name', 'acct name']),
            ('capacity', ['capacity usage remaining ($k)', 'capacity usage remaining']),
            ('burn rate', ['annualized run rate (l90d) ($k)', 'fy27 trailing 91d consumption_average ($k)']),
        ]
        for field_name, col_options in required_pigment:
            found = any(opt in df_columns_lower for opt in col_options)
            if not found:
                errors.append(f"Missing required field: {field_name} (expected one of: {', '.join(col_options)})")

        if 'contract end date' not in df_columns_lower:
            warnings.append("Warning: 'Contract End Date' not found - will default to end of planning FY")
        if not any(col in df_columns_lower for col in ['prior renewal base ($k)', 'prior renewal base']):
            warnings.append("Warning: 'Prior Renewal Base' not found - growth calculations may be limited")

        if errors:
            return False, errors + warnings, 'pigment'
        return True, warnings, 'pigment'

    elif detected_format == 'simple':
        for req_col in BULK_REQUIRED_COLUMNS:
            if req_col.lower() not in df_columns_lower:
                errors.append(f"Missing required column: {req_col}")
        if errors:
            return False, errors, 'simple'

        contract_col = None
        for col in df.columns:
            if col.lower().strip() == 'contract structure':
                contract_col = col
                break
        if contract_col:
            valid_structures = ['single-year', 'multi-year', '-- select --', '']
            invalid_rows = []
            for idx, val in df[contract_col].items():
                if pd.notna(val) and str(val).lower().strip() not in valid_structures:
                    invalid_rows.append(f"Row {idx + 2}: '{val}'")
            if invalid_rows:
                errors.append(f"Invalid Contract Structure values (must be 'Single-year' or 'Multi-year'): {', '.join(invalid_rows[:3])}")

        return len(errors) == 0, errors, 'simple'

    else:
        errors.append("Unrecognized file format. Please use either:")
        errors.append("  - Simple template: Download and fill out the CSV template")
        errors.append("  - Pigment export: Export directly from Pigment with standard columns")
        return False, errors, 'unknown'


def row_to_fields_legacy(row: pd.Series, planning_fy: str, detected_format: str = 'simple') -> Tuple[Dict[str, Any], bool]:
    """
    Convert a DataFrame row to the fields dict format used by analysis.
    Uses legacy regex-based parsing.

    Returns: (fields_dict, success_flag)
    """
    from core.config import PIGMENT_COLUMN_MAPPING

    fields: Dict[str, Any] = {}
    guardrail_context: Dict[str, Any] = {}

    simple_mapping = {
        'account name': ('account_name', 1),
        'contract end date': ('contract_end_date', 1),
        'capacity remaining': ('capacity_remaining', 1),
        'l90d burn rate': ('l90d_burn_rate', 1),
        'l30d burn rate': ('l30d_burn_rate', 1),
        'prior renewal base': ('prior_renewal_base', 1),
        'contract structure': ('contract_structure', 1),
        'fy prediction': ('planning_fy_prediction', 1),
        'account segment': ('account_segment', 1),
        'account owner': ('account_owner', 1),
        'qualitative context': ('qualitative_context', 1),
    }

    column_mapping = PIGMENT_COLUMN_MAPPING if detected_format == 'pigment' else simple_mapping

    for col in row.index:
        col_lower = col.lower().strip()
        mapping_entry = column_mapping.get(col_lower)

        if not mapping_entry and detected_format == 'pigment':
            for pattern, entry in PIGMENT_COLUMN_MAPPING.items():
                if pattern in col_lower or col_lower in pattern:
                    mapping_entry = entry
                    break

        if not mapping_entry:
            continue

        field_name, multiplier = mapping_entry
        value = row[col]

        if pd.isna(value) or value == '' or value == '—':
            continue

        if field_name == 'contract_end_date':
            parsed_date_val = parse_date(str(value))
            fields[field_name] = parsed_date_val if parsed_date_val else str(value)

        elif field_name in ['account_name', 'contract_structure', 'account_segment', 'account_owner',
                           'account_category', 'account_subtype', 'patch_name', 'theater', 'region',
                           'district', 'industry_category', 'industry', 'qualitative_context']:
            val_str = str(value).strip()
            if field_name == 'account_name' and '|' in val_str:
                val_str = val_str.split('|')[-1].strip()
            fields[field_name] = val_str

        elif field_name in ['is_consecutive_downsell', 'churn_risk_suggested', 'high_churn_risk']:
            if isinstance(value, bool):
                bool_val = value
            elif isinstance(value, str):
                bool_val = value.upper().strip() in ['TRUE', 'YES', '1']
            else:
                bool_val = bool(value)
            fields[field_name] = bool_val
            if field_name == 'is_consecutive_downsell':
                guardrail_context['is_declining_account'] = bool_val

        else:
            if isinstance(value, (int, float)):
                fields[field_name] = float(value) * multiplier
            else:
                parsed_val = parse_currency(str(value))
                if parsed_val is not None:
                    fields[field_name] = parsed_val * multiplier

    if 'account_category' in fields:
        category = fields['account_category'].lower()
        if 'prospect' in category:
            guardrail_context['account_type'] = 'Acquisition'
        elif 'customer' in category:
            guardrail_context['account_type'] = 'Expansion'

    if guardrail_context:
        fields['_guardrail_context'] = guardrail_context

    required_fields = ['account_name', 'capacity_remaining', 'l90d_burn_rate']
    has_required = all(field in fields for field in required_fields)

    return fields, has_required


def row_to_fields(row: pd.Series, planning_fy: str, detected_format: str = 'simple', use_ai_first: bool = True) -> Dict[str, Any]:
    """
    Convert a DataFrame row to the fields dict format used by analysis.

    AI-FIRST APPROACH (default): Uses Claude Haiku for semantic parsing.
    Falls back to legacy regex parsing if AI fails.
    """
    row_text_lines = []
    for col in row.index:
        value = row[col]
        if pd.notna(value) and value != '' and value != '—':
            row_text_lines.append(f"{col}: {value}")
    row_text = '\n'.join(row_text_lines)

    if use_ai_first and IS_SNOWFLAKE:
        try:
            ai_fields, _warnings = extract_data_with_haiku(row_text, planning_fy)
            if ai_fields:
                ai_fields['_parsed_with_ai'] = True
                return ai_fields
        except Exception:
            pass

    fields, success = row_to_fields_legacy(row, planning_fy, detected_format)
    if success:
        return fields

    if not use_ai_first or not IS_SNOWFLAKE:
        try:
            ai_fields, _warnings = extract_data_with_ai(row_text, planning_fy)
            if ai_fields:
                for key, value in ai_fields.items():
                    if key not in fields or fields[key] is None:
                        fields[key] = value
                fields['_parsed_with_ai'] = True
        except Exception:
            pass

    return fields


def row_to_fields_simple(row: pd.Series, planning_fy: str) -> Dict[str, Any]:
    """Legacy function for backwards compatibility — uses simple parsing only."""
    fields: Dict[str, Any] = {}

    column_mapping = {
        'account name': 'account_name',
        'contract end date': 'contract_end_date',
        'capacity remaining': 'capacity_remaining',
        'l90d burn rate': 'l90d_burn_rate',
        'l30d burn rate': 'l30d_burn_rate',
        'prior renewal base': 'prior_renewal_base',
        'contract structure': 'contract_structure',
        'fy prediction': 'planning_fy_prediction',
        'account segment': 'account_segment',
        'account owner': 'account_owner',
    }

    for col in row.index:
        col_lower = col.lower().strip()
        if col_lower in column_mapping:
            field_name = column_mapping[col_lower]
            value = row[col]

            if pd.isna(value) or value == '':
                continue

            if field_name == 'contract_end_date':
                parsed_date_val = parse_date(str(value))
                fields[field_name] = parsed_date_val if parsed_date_val else str(value)
            elif field_name in ['account_name', 'contract_structure', 'account_segment', 'account_owner']:
                fields[field_name] = str(value).strip()
            else:
                if isinstance(value, (int, float)):
                    fields[field_name] = float(value)
                else:
                    parsed_val = parse_currency(str(value))
                    if parsed_val is not None:
                        fields[field_name] = parsed_val

    return fields
