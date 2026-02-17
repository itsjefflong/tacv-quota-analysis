# Slide Generation Prompt

Use this prompt with Claude to generate a presentation slide introducing the TACV Quota Scenario Modeling App.

---

## Prompt

Create a single PowerPoint-style presentation slide (designed as a visual mockup using markdown/text) that introduces an internal Snowflake tool called **"TACV Quota Scenario Modeling App"**.

### About the App

**Purpose:** A Streamlit-based app that enables Field Operations teams to generate AI-powered TACV (Total Annual Contract Value) quota analysis for individual Snowflake customer accounts. It helps reps and managers model quota scenarios for renewals and growth opportunities.

**Target Audience:** Snowflake Field Operations, Account Executives, and Sales Leadership

### Key Features to Highlight

1. **Smart Data Input** — Paste account data from Google Sheets, CSV, or other formats. The app auto-detects and parses key fields like contract dates, capacity remaining, burn rates, and renewal base.

2. **AI-Powered Analysis** — Uses Snowflake Cortex (Claude) to generate comprehensive quota recommendations with full calculation transparency.

3. **Scenario Modeling** — Produces Conservative, Base, and Stretch TACV scenarios with confidence levels and clear rationale for each.

4. **Quota Classification** — Automatically classifies TACV into:
   - Renewal ACV vs Growth ACV
   - Contracted vs Non-Contracted
   - Quota-Bearing vs Non-Quota

5. **Data Quality Flags** — Surfaces potential issues with input data and highlights what needs validation.

6. **Guided 6-Step Workflow:**
   - Data Input → Confirm Fields → Add Context → Generate → Review → Export

### Slide Requirements

- Use Snowflake brand colors (primary: #29B5E8 Snowflake Blue, accent: #0C2340 Dark Navy)
- Include a clear headline/title
- Use icons or visual elements to represent features
- Keep text concise and scannable
- Include a tagline or value proposition statement
- Format as if it were the opening slide of a deck (sets the stage for what's to come)

### Suggested Tagline Options (pick one or suggest better)

- "From Data to Quota in Minutes"
- "AI-Powered Quota Modeling for Smarter Planning"
- "Turn Account Data into Actionable Quota Recommendations"

### Output Format

Please provide the slide content in a structured format that could easily be recreated in PowerPoint or Google Slides, including:
- Slide title
- Subtitle/tagline
- Main content (features as bullet points or icons with labels)
- Any footer text or call-to-action
- Color/styling notes

---

## Example Output Structure

```
SLIDE TITLE: [Title Here]
SUBTITLE: [Tagline]

HERO SECTION:
[Brief 1-2 sentence value prop]

FEATURES (with icons):
🔄 Feature 1 — Brief description
🤖 Feature 2 — Brief description
📊 Feature 3 — Brief description
✅ Feature 4 — Brief description

FOOTER/CTA:
[Any closing statement or next steps]

DESIGN NOTES:
- Color palette recommendations
- Layout suggestions
```








