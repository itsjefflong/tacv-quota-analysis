# Snowflake Streamlit Application Development Guide

A comprehensive guide for creating branded, theme-adaptive Streamlit applications in Snowflake's UI (Streamlit in Snowflake / SiS).

---

## Table of Contents
1. [Creating a Streamlit App in Snowflake](#creating-a-streamlit-app-in-snowflake)
2. [Snowflake Brand Colors](#snowflake-brand-colors)
3. [Dark & Light Mode Support](#dark--light-mode-support)
4. [CSS Styling Patterns](#css-styling-patterns)
5. [Component Styling Reference](#component-styling-reference)
6. [Plotly Chart Styling](#plotly-chart-styling)
7. [SiS Limitations & Restrictions](#sis-limitations--restrictions)
8. [Warehouse & Performance](#warehouse--performance)
9. [External Access & Integrations](#external-access--integrations)
10. [Version Management & Dependencies](#version-management--dependencies)
11. [Security Considerations](#security-considerations)
12. [Best Practices](#best-practices)
13. [Complete Code Templates](#complete-code-templates)
14. [Troubleshooting](#troubleshooting)

---

## Creating a Streamlit App in Snowflake

### Prerequisites
- Snowflake account with appropriate permissions
- Access to Snowsight (Snowflake's web interface)
- A warehouse for running the app
- A database and schema for storing the app

### Steps to Create

1. **Sign In to Snowsight**
   - Navigate to [app.snowflake.com](https://app.snowflake.com)
   - Log in with your Snowflake credentials

2. **Navigate to Streamlit Projects**
   - In the left-hand navigation, select **Projects** → **Streamlit**

3. **Create a New Streamlit App**
   - Click the **+ Streamlit** button
   - Configure the app:
     - **Name**: Your application name
     - **Warehouse**: Select the compute warehouse
     - **App Location**: Choose database and schema
   - Click **Create**

4. **Development Environment**
   - The Streamlit editor opens with a sample app
   - Use `get_active_session()` to access Snowflake data
   - Auto-save is enabled; changes reflect immediately

### Basic App Structure

```python
import streamlit as st
from snowflake.snowpark.context import get_active_session
import pandas as pd

# Initialize Snowflake session
session = get_active_session()

# Page configuration (must be first Streamlit command)
st.set_page_config(
    page_title="My App",
    layout="wide",
    page_icon="❄️"
)

# Your app code here
st.title("My Snowflake App")
```

---

## Snowflake Brand Colors

### Primary Color Palette

| Color Name | Hex Code | Usage |
|------------|----------|-------|
| **Snowflake Blue** | `#29B5E8` | Primary brand color, buttons, accents, highlights |
| **Snowflake Dark** | `#0C2340` | Dark backgrounds, text on light backgrounds |
| **Snowflake Light** | `#E8F4F8` | Light backgrounds, subtle highlights |
| **Snowflake Blue Darker** | `#1a9dcc` | Hover states, gradients |
| **Snowflake Blue Lighter** | `#5DADE2` | Secondary accents, gradients |

### Extended Palette for Data Visualization

```python
# Snowflake-branded color sequence for charts
SNOWFLAKE_COLORS = [
    '#29B5E8',  # Primary Blue
    '#1a9dcc',  # Darker Blue
    '#5DADE2',  # Lighter Blue
    '#0C2340',  # Navy/Dark
    '#FF9F40',  # Orange (accent for contrast)
    '#4CAF50',  # Green (success/positive)
    '#E91E63',  # Pink (accent)
    '#9C27B0',  # Purple (accent)
]

# For gradients
SNOWFLAKE_GRADIENT = "linear-gradient(135deg, #29B5E8 0%, #1a9dcc 100%)"
```

### CSS Variables Definition

```css
:root {
    --snowflake-blue: #29B5E8;
    --snowflake-dark: #0C2340;
    --snowflake-light: #E8F4F8;
    --snowflake-blue-darker: #1a9dcc;
    --snowflake-blue-lighter: #5DADE2;
}
```

---

## Dark & Light Mode Support

### Key Principle
Streamlit in Snowflake automatically inherits the user's theme preference. Your CSS must work in **both modes** without requiring theme detection.

### Best Practices for Theme Compatibility

1. **Use Transparent Backgrounds**
   ```css
   paper_bgcolor='rgba(0,0,0,0)'
   plot_bgcolor='rgba(0,0,0,0)'
   ```

2. **Use RGBA for Semi-Transparent Colors**
   ```css
   /* Works in both light and dark mode */
   background-color: rgba(41, 181, 232, 0.08);  /* Subtle Snowflake blue */
   border: 2px solid rgba(41, 181, 232, 0.3);   /* Semi-transparent border */
   ```

3. **Avoid Hard-Coded Background Colors**
   ```css
   /* ❌ BAD - Will clash in dark mode */
   background-color: white;
   
   /* ✅ GOOD - Transparent, inherits theme */
   background-color: rgba(0, 0, 0, 0);
   ```

4. **Use High-Contrast Accent Colors**
   ```css
   /* Snowflake Blue (#29B5E8) has good contrast in both modes */
   color: #29B5E8;
   ```

5. **Avoid Pure Black/White Text in Custom Elements**
   ```css
   /* For custom HTML elements, use colors that work in both modes */
   /* Or use Snowflake Blue for consistency */
   color: #29B5E8;
   ```

---

## CSS Styling Patterns

### Complete Base CSS Template

```python
st.markdown("""
    <style>
    /* ============================================
       SNOWFLAKE BRAND VARIABLES
       ============================================ */
    :root {
        --snowflake-blue: #29B5E8;
        --snowflake-dark: #0C2340;
        --snowflake-light: #E8F4F8;
    }
    
    /* ============================================
       MAIN HEADER - Hero Section
       ============================================ */
    .main-header {
        background: linear-gradient(135deg, #29B5E8 0%, #1a9dcc 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    
    .main-header h1 {
        color: white;
        font-size: 2.5rem;
        margin: 0;
        font-weight: 600;
    }
    
    .main-header p {
        color: #0C2340;
        font-size: 1.1rem;
        margin: 0.5rem 0 0 0;
        font-weight: 500;
    }
    
    /* ============================================
       METRIC CARDS
       ============================================ */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #29B5E8;
        font-weight: 600;
    }
    
    [data-testid="stMetricLabel"] {
        font-weight: 500;
        font-size: 0.9rem;
    }
    
    /* ============================================
       SECTION HEADERS
       ============================================ */
    .section-header {
        color: #29B5E8;
        font-size: 1.5rem;
        font-weight: 600;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #29B5E8;
    }
    
    /* ============================================
       SIDEBAR
       ============================================ */
    .sidebar-header {
        color: #29B5E8;
        font-size: 1.2rem;
        font-weight: 600;
        padding: 1rem 0;
    }
    
    /* ============================================
       BUTTONS
       ============================================ */
    .stDownloadButton button {
        background-color: #29B5E8 !important;
        color: white !important;
        border: none !important;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    
    .stDownloadButton button:hover {
        background-color: #1a9dcc !important;
    }
    
    /* ============================================
       SUBHEADERS
       ============================================ */
    h3 {
        color: #29B5E8 !important;
        font-weight: 500 !important;
    }
    
    /* ============================================
       TABS - Theme Adaptive
       ============================================ */
    .stTabs {
        background-color: rgba(41, 181, 232, 0.08);
        padding: 1rem;
        border-radius: 10px;
        margin: 2rem 0;
        border: 2px solid rgba(41, 181, 232, 0.3);
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(41, 181, 232, 0.05);
        padding: 0.5rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 0 24px;
        background-color: rgba(128, 128, 128, 0.15);
        border-radius: 6px;
        font-weight: 500;
        font-size: 1rem;
        border: 2px solid transparent;
        transition: all 0.3s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #29B5E8 0%, #1a9dcc 100%) !important;
        color: white !important;
        border: 2px solid #29B5E8 !important;
        box-shadow: 0 4px 8px rgba(41, 181, 232, 0.4) !important;
        font-weight: 600 !important;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: rgba(41, 181, 232, 0.2);
        border: 2px solid #29B5E8;
        color: #29B5E8 !important;
    }
    
    .stTabs [aria-selected="true"]:hover {
        background: linear-gradient(135deg, #1a9dcc 0%, #29B5E8 100%) !important;
        box-shadow: 0 6px 10px rgba(41, 181, 232, 0.5) !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)
```

---

## Component Styling Reference

### Header with Logo

```python
st.markdown("""
    <div class="main-header">
        <h1>
            <img src="https://companieslogo.com/img/orig/SNOW-35164165.png" 
                 style="height: 45px; vertical-align: middle; margin-right: 15px; filter: brightness(0) invert(1);">
            Your Dashboard Title
        </h1>
        <p>Your subtitle or description here</p>
    </div>
""", unsafe_allow_html=True)
```

### Section Headers

```python
st.markdown('<p class="section-header">📈 Your Section Title</p>', unsafe_allow_html=True)
```

### Sidebar Headers

```python
st.sidebar.markdown('<p class="sidebar-header">🔍 Filters</p>', unsafe_allow_html=True)
st.sidebar.markdown("**Filters apply to all tabs and charts below**")
st.sidebar.markdown("---")
```

### Info/Success/Warning Messages

```python
# Contextual messages that adapt to theme
st.info("ℹ️ **Note**: Your informational message here.")
st.success("✓ **Success**: Your success message here.")
st.warning("⚠️ **Warning**: Your warning message here.")
```

### Expander with Guide Content

```python
with st.expander("📖 Dashboard Guide - Click to Learn More", expanded=False):
    st.markdown("""
    ### Welcome! 👋
    
    #### 🎯 Quick Start
    1. **Step one** - Description
    2. **Step two** - Description
    
    #### 🔍 Pro Tips
    - Tip one
    - Tip two
    """)
```

---

## Plotly Chart Styling

### Theme-Adaptive Chart Template

```python
import plotly.graph_objects as go

def create_snowflake_chart(fig):
    """Apply Snowflake branding to any Plotly figure."""
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',  # Transparent background
        plot_bgcolor='rgba(0,0,0,0)',   # Transparent plot area
        font=dict(size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified'
    )
    return fig
```

### Bar Chart Example

```python
fig = go.Figure()
fig.add_trace(go.Bar(
    name='Metric A',
    x=data['Category'],
    y=data['Value A'],
    marker_color='#29B5E8',  # Snowflake Blue
    text=data['Value A'],
    texttemplate='%{text:.1f}%',
    textposition='outside'
))
fig.add_trace(go.Bar(
    name='Metric B',
    x=data['Category'],
    y=data['Value B'],
    marker_color='#1a9dcc',  # Darker Blue
    text=data['Value B'],
    texttemplate='%{text:.1f}%',
    textposition='outside'
))

fig.update_layout(
    barmode='group',
    height=450,
    xaxis_tickangle=-45,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(size=12),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis_title="Value (%)"
)

st.plotly_chart(fig, use_container_width=True, key="unique_chart_key")
```

### Line Chart Example

```python
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=data['Date'],
    y=data['Value'],
    mode='lines+markers',
    name='Trend',
    line=dict(color='#29B5E8', width=3),
    marker=dict(size=8, color='#29B5E8')
))

fig.update_layout(
    height=400,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(size=12),
    yaxis_title="Value",
    showlegend=False,
    hovermode='x unified'
)

st.plotly_chart(fig, use_container_width=True, key="line_chart")
```

### Funnel Chart Example

```python
fig = go.Figure(go.Funnel(
    y=funnel_data['Stage'],
    x=funnel_data['Count'],
    textinfo="value",
    marker=dict(color=[
        '#5DADE2',  # Light Blue
        '#29B5E8',  # Snowflake Blue
        '#1a9dcc',  # Darker Blue
        '#0C2340',  # Navy
        '#FF9F40',  # Orange
        '#4CAF50'   # Green
    ]),
    hoverinfo="text"
))

fig.update_layout(
    height=400,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(size=14)
)

st.plotly_chart(fig, use_container_width=True, key="funnel")
```

### Pie/Donut Chart Example

```python
fig = go.Figure(go.Pie(
    labels=data['Category'],
    values=data['Value'],
    hole=0.4,  # Makes it a donut chart
    marker=dict(colors=['#29B5E8', '#1a9dcc', '#0C2340', '#FF9F40'])
))

fig.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    font=dict(size=12)
)

st.plotly_chart(fig, use_container_width=True)
```

---

## SiS Limitations & Restrictions

### Unsupported Streamlit Features

The following Streamlit features are **NOT supported** in Snowflake:

| Feature | Status | Workaround |
|---------|--------|------------|
| `st.bokeh_chart` | ❌ Not supported | Use `plotly` or `altair` instead |
| `st.set_page_config` properties | ⚠️ Partial | `page_title`, `page_icon`, `menu_items` not supported |
| `st.toast` | ❌ Not supported | Use `st.info`, `st.success`, `st.warning` |
| `st.balloons` | ❌ Not supported | - |
| `st.snow` | ❌ Not supported | - |
| `st.camera_input` | ❌ Not supported | - |
| Anchor links | ❌ Not supported | Use tabs or expanders for navigation |

### Content Security Policy (CSP) Restrictions

Streamlit in Snowflake operates under a **strict CSP** that blocks:

| Resource Type | Status | Notes |
|---------------|--------|-------|
| External scripts | ❌ Blocked | Cannot load JS from external CDNs |
| External stylesheets | ❌ Blocked | Must use inline CSS |
| External fonts | ❌ Blocked | Use system fonts or inline fonts |
| iFrame embedding | ❌ Blocked | Cannot embed external content |
| Mapbox/Carto | ✅ Allowed | Exception for map rendering |
| External images/media | ✅ Allowed | Images from external URLs work |

> ⚠️ **Important**: External images work in SiS but **NOT** in the Snowflake Native App Framework.

### Data Display Limitations

| Limitation | Value | Notes |
|------------|-------|-------|
| Message size limit | **32 MB** | Max data per single `st.dataframe` call |
| Query size | No limit | You can run large queries |
| In-memory data | No limit | But avoid exceeding message limit |

```python
# ❌ BAD - May cause MessageSizeError
st.dataframe(huge_df)  # If > 32MB

# ✅ GOOD - Paginate or filter large data
st.dataframe(df.head(10000))  # Show limited rows
```

### Caching Behavior ⚠️

**Critical difference from standard Streamlit:**

| Aspect | Standard Streamlit | SiS Behavior |
|--------|-------------------|--------------|
| `st.cache_data` | Persists across sessions | **Session-only** |
| `st.cache_resource` | Shared between users | **Session-only** |
| Cache sharing | Cross-session/user | **NOT supported** |

```python
# Caching still helps within a session, but resets between sessions
@st.cache_data(ttl="1h")  # TTL still works within session
def load_data():
    return session.sql("SELECT * FROM table").to_pandas()
```

### File Upload Constraints

| Constraint | Value |
|------------|-------|
| Max file size | **200 MB** |
| Configurable? | No |

```python
# For larger files, use Snowflake stages instead
uploaded_file = st.file_uploader("Upload CSV", type="csv")
if uploaded_file:
    if uploaded_file.size > 200 * 1024 * 1024:
        st.error("File too large! Max 200MB. Use Snowflake stages for larger files.")
```

### Custom Components

| Type | Support |
|------|---------|
| Components without external calls | ✅ Supported |
| Components requiring external services | ❌ Not supported |
| Third-party components | ⚠️ Use at your own risk |

> Snowflake does not maintain third-party components. They are subject to their own licenses.

### Query Parameters Behavior

In SiS, URL query parameters have a special prefix:

```python
# URL: ...?streamlit-my_param=value

# Accessing in code (prefix is stripped automatically)
value = st.query_params.get("my_param")  # NOT "streamlit-my_param"
```

---

## Warehouse & Performance

### Warehouse Selection Guidelines

| Recommendation | Reason |
|----------------|--------|
| Start with X-Small | Minimize costs; scale up if needed |
| Use dedicated warehouse | Isolate costs and improve load times |
| Separate warehouse for queries | Use larger warehouse for complex queries |

```python
# Use a larger warehouse for heavy queries
session.sql("USE WAREHOUSE LARGE_WH").collect()
result = session.sql("SELECT * FROM huge_table").to_pandas()
session.sql("USE WAREHOUSE SMALL_WH").collect()  # Switch back
```

### Warehouse Auto-Suspend Behavior

- WebSocket connection stays open while app is in use
- Connection expires **~15 minutes** after last interaction
- Warehouse auto-suspends after connection closes

### Custom Sleep Timer

You can configure auto-suspend time via `.streamlit/config.toml`:

```toml
# .streamlit/config.toml (uploaded to your app's stage)
[server]
# Time in seconds before app auto-suspends (default: 15 minutes = 900)
runOnSave = true

[browser]
serverAddress = "localhost"
```

### Performance Optimization Tips

1. **Push computation to Snowflake**
   ```python
   # ❌ BAD - Pulls all data then filters in Python
   df = session.sql("SELECT * FROM large_table").to_pandas()
   filtered = df[df['status'] == 'active']
   
   # ✅ GOOD - Filter in SQL
   df = session.sql("SELECT * FROM large_table WHERE status = 'active'").to_pandas()
   ```

2. **Aggregate in SQL**
   ```python
   # ✅ GOOD - Aggregate in Snowflake
   query = """
       SELECT category, COUNT(*) as count, AVG(value) as avg_value
       FROM large_table
       GROUP BY category
   """
   summary_df = session.sql(query).to_pandas()
   ```

3. **Use caching wisely**
   ```python
   @st.cache_data(ttl="30m", show_spinner="Loading...")
   def get_data():
       return session.sql(query).to_pandas()
   ```

---

## External Access & Integrations

### Enabling External Network Access

To call external APIs, you need to set up External Access Integration:

```sql
-- Step 1: Create a network rule
CREATE OR REPLACE NETWORK RULE my_api_rule
    MODE = EGRESS
    TYPE = HOST_PORT
    VALUE_LIST = ('api.example.com:443');

-- Step 2: Create a secret for API credentials (optional)
CREATE OR REPLACE SECRET my_api_secret
    TYPE = GENERIC_STRING
    SECRET_STRING = 'your-api-key';

-- Step 3: Create external access integration
CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION my_api_integration
    ALLOWED_NETWORK_RULES = (my_api_rule)
    ALLOWED_AUTHENTICATION_SECRETS = (my_api_secret)
    ENABLED = TRUE;

-- Step 4: Alter the Streamlit app to use the integration
ALTER STREAMLIT my_app
    SET EXTERNAL_ACCESS_INTEGRATIONS = (my_api_integration);
```

### Using External Access in Code

```python
import requests
from snowflake.snowpark.context import get_active_session

session = get_active_session()

# Access the secret
secret = session.sql("SELECT GET_SECRET('my_api_secret')").collect()[0][0]

# Make external API call
response = requests.get(
    "https://api.example.com/data",
    headers={"Authorization": f"Bearer {secret}"}
)
```

### Context Functions & Row Access Policies

To use context functions like `CURRENT_USER()` with row access policies:

```sql
-- ACCOUNTADMIN must grant this privilege to the app owner role
GRANT READ SESSION ON ACCOUNT TO ROLE my_app_owner_role;
```

```python
# Now you can use context functions
current_user = session.sql("SELECT CURRENT_USER()").collect()[0][0]
```

---

## Version Management & Dependencies

### Pinning Streamlit Version

Create an `environment.yml` file to pin specific versions:

```yaml
# environment.yml
name: streamlit_app
channels:
  - snowflake
dependencies:
  - streamlit=1.26.0
  - pandas=2.0.3
  - plotly=5.18.0
  - snowflake-snowpark-python
```

### Checking Available Packages

```sql
-- List available packages in Snowflake's Anaconda channel
SELECT * FROM INFORMATION_SCHEMA.PACKAGES 
WHERE PACKAGE_NAME LIKE '%streamlit%';
```

### Supported Core Packages

| Package | Notes |
|---------|-------|
| `streamlit` | Core framework |
| `pandas` | Data manipulation |
| `numpy` | Numerical computing |
| `plotly` | Interactive charts |
| `altair` | Declarative visualization |
| `snowflake-snowpark-python` | Snowflake integration |
| `scikit-learn` | Machine learning |
| `scipy` | Scientific computing |

> Check [Snowflake's Anaconda channel](https://docs.snowflake.com/en/developer-guide/udf/python/udf-python-packages) for the complete list.

---

## Security Considerations

### Shared Responsibility Model

| Snowflake Responsibility | Developer Responsibility |
|--------------------------|-------------------------|
| Infrastructure security | App code security |
| CSP enforcement | Input validation |
| Network isolation | SQL injection prevention |
| Authentication | Authorization logic |

### Security Best Practices

1. **Validate user inputs**
   ```python
   # ❌ BAD - SQL injection risk
   query = f"SELECT * FROM table WHERE name = '{user_input}'"
   
   # ✅ GOOD - Use parameterized queries
   query = "SELECT * FROM table WHERE name = ?"
   df = session.sql(query, params=[user_input]).to_pandas()
   ```

2. **Use role-based access**
   ```python
   # Check user's role before showing sensitive data
   current_role = session.sql("SELECT CURRENT_ROLE()").collect()[0][0]
   if current_role in ['ADMIN', 'ANALYST']:
       st.dataframe(sensitive_data)
   else:
       st.warning("You don't have access to this data.")
   ```

3. **Don't expose secrets in UI**
   ```python
   # ❌ BAD
   st.write(f"API Key: {api_key}")
   
   # ✅ GOOD - Keep secrets server-side
   # Use secrets only in backend operations
   ```

---

## Best Practices

### 1. Data Caching

```python
@st.cache_data(ttl="1h", show_spinner="Fetching data...")
def load_data():
    session = get_active_session()
    query = "SELECT * FROM my_table"
    return session.sql(query).to_pandas()
```

### 2. Use Unique Chart Keys

```python
# Always provide unique keys to avoid rendering conflicts
st.plotly_chart(fig, use_container_width=True, key="unique_chart_name")
st.dataframe(df, use_container_width=True, key="unique_table_name")
```

### 3. Handle Empty Data Gracefully

```python
if df.empty:
    st.warning("No data available for the selected filters.")
else:
    # Render your visualizations
    st.plotly_chart(fig)
```

### 4. Optimize Queries

```python
# Push computation to Snowflake
@st.cache_data(ttl="30m")
def get_aggregated_data():
    query = """
        SELECT 
            category,
            COUNT(*) as count,
            SUM(value) as total
        FROM large_table
        GROUP BY category
    """
    return session.sql(query).to_pandas()
```

### 5. Use Sidebar for Filters

```python
# Keep main area clean, filters in sidebar
with st.sidebar:
    st.markdown("### Filters")
    date_range = st.date_input("Date Range", value=(start, end))
    category = st.selectbox("Category", options=['All'] + categories)
```

### 6. Chunk Large Data Displays

```python
# For large datasets, use pagination
page_size = 1000
page = st.number_input("Page", min_value=1, value=1)
start_idx = (page - 1) * page_size
st.dataframe(df.iloc[start_idx:start_idx + page_size])
```

---

## Complete Code Templates

### Minimal Branded App Template

```python
import streamlit as st
from snowflake.snowpark.context import get_active_session
import pandas as pd
import plotly.graph_objects as go

# Initialize session
session = get_active_session()

# Page configuration
st.set_page_config(page_title="My App", layout="wide", page_icon="❄️")

# Snowflake branding CSS
st.markdown("""
    <style>
    :root {
        --snowflake-blue: #29B5E8;
        --snowflake-dark: #0C2340;
    }
    
    .main-header {
        background: linear-gradient(135deg, #29B5E8 0%, #1a9dcc 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    
    .main-header h1 { color: white; margin: 0; }
    .main-header p { color: #0C2340; margin: 0.5rem 0 0 0; }
    
    [data-testid="stMetricValue"] { color: #29B5E8; font-weight: 600; }
    
    .section-header {
        color: #29B5E8;
        font-size: 1.5rem;
        font-weight: 600;
        border-bottom: 3px solid #29B5E8;
        padding-bottom: 0.5rem;
        margin: 2rem 0 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="main-header">
        <h1>❄️ My Snowflake App</h1>
        <p>Subtitle description here</p>
    </div>
""", unsafe_allow_html=True)

# Load data
@st.cache_data(ttl="1h")
def load_data():
    return session.sql("SELECT * FROM my_table LIMIT 1000").to_pandas()

df = load_data()

# Metrics
st.markdown('<p class="section-header">📈 Key Metrics</p>', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Records", len(df))
with col2:
    st.metric("Unique Items", df['column'].nunique())
with col3:
    st.metric("Average", f"{df['value'].mean():.2f}")

# Chart
st.markdown('<p class="section-header">📊 Visualization</p>', unsafe_allow_html=True)
fig = go.Figure(go.Bar(
    x=df['category'],
    y=df['value'],
    marker_color='#29B5E8'
))
fig.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)'
)
st.plotly_chart(fig, use_container_width=True, key="main_chart")

# Data table
st.markdown('<p class="section-header">📋 Data Table</p>', unsafe_allow_html=True)
st.dataframe(df, use_container_width=True, hide_index=True)
```

---

## Quick Reference Card

### 🎨 Colors
| Name | Hex | Use |
|------|-----|-----|
| Primary | `#29B5E8` | Main brand color |
| Dark | `#0C2340` | Text, dark backgrounds |
| Hover | `#1a9dcc` | Hover states |
| Light | `#5DADE2` | Secondary accents |

### 🔲 Transparency Pattern
```css
rgba(41, 181, 232, 0.08)  /* Subtle background */
rgba(41, 181, 232, 0.3)   /* Border */
rgba(0, 0, 0, 0)          /* Fully transparent */
```

### 📊 Chart Backgrounds
```python
paper_bgcolor='rgba(0,0,0,0)'
plot_bgcolor='rgba(0,0,0,0)'
```

### 🎯 Key CSS Selectors
- Metrics: `[data-testid="stMetricValue"]`, `[data-testid="stMetricLabel"]`
- Tabs: `.stTabs`, `[data-baseweb="tab"]`, `[aria-selected="true"]`
- Buttons: `.stDownloadButton button`
- Sidebar: Can target with `.css-1d391kg` (check browser inspector)

### ⚠️ Critical Limits
| Limit | Value |
|-------|-------|
| Max display data | 32 MB |
| Max file upload | 200 MB |
| Session timeout | ~15 min |
| Cache scope | Session-only |

### ❌ Not Supported
`st.bokeh_chart` · `st.toast` · `st.balloons` · `st.snow` · Anchor links · External scripts/fonts

---

## Troubleshooting

### Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `MessageSizeError` | Data > 32MB in single display | Paginate or filter data before displaying |
| `ModuleNotFoundError` | Package not in Snowflake channel | Check available packages; use alternatives |
| External request blocked | CSP restriction | Set up External Access Integration |
| Session timeout | App idle > 15 min | Warehouse auto-suspended; refresh page |
| `st.set_page_config` error | Unsupported properties | Remove `page_title`, `page_icon`, `menu_items` |
| Cache not persisting | SiS caching limitation | Cache is session-only; this is expected |

### Debugging Tips

1. **Check console for errors**
   ```python
   import traceback
   try:
       # Your code
   except Exception as e:
       st.error(f"Error: {e}")
       st.code(traceback.format_exc())
   ```

2. **Verify data size before display**
   ```python
   import sys
   data_size_mb = sys.getsizeof(df) / (1024 * 1024)
   if data_size_mb > 30:
       st.warning(f"Data size: {data_size_mb:.1f}MB - Consider filtering")
   ```

3. **Test queries separately**
   ```python
   # Test your SQL in Snowsight worksheets first
   # Then copy to Streamlit app
   ```

4. **Check warehouse status**
   ```python
   wh_status = session.sql("SHOW WAREHOUSES LIKE 'MY_WH'").to_pandas()
   st.write(wh_status[['name', 'state', 'size']])
   ```

### Native App Framework Differences

If building for Snowflake Marketplace (Native Apps), note these **additional restrictions**:

| Feature | SiS | Native App Framework |
|---------|-----|---------------------|
| External images | ✅ Allowed | ❌ Blocked |
| External media | ✅ Allowed | ❌ Blocked |
| Sharing | Direct URL | Marketplace listing |

---

## Resources

- [Snowflake Streamlit Documentation](https://docs.snowflake.com/en/developer-guide/streamlit/about-streamlit)
- [SiS Limitations & Library Changes](https://docs.snowflake.com/en/developer-guide/streamlit/limitations)
- [Additional SiS Features](https://docs.snowflake.com/en/developer-guide/streamlit/additional-features)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Plotly Python Documentation](https://plotly.com/python/)
- [Snowflake Snowpark Python](https://docs.snowflake.com/en/developer-guide/snowpark/python/index)
- [Snowflake Anaconda Packages](https://docs.snowflake.com/en/developer-guide/udf/python/udf-python-packages)

---

*Last updated: November 2024*

