# Technical Architecture Slide Generation Prompt

Use this prompt with Claude to generate a technical presentation slide explaining how the TACV Quota Scenario Modeling App works under the hood. This is intended for a data science / engineering audience.

---

## Prompt

Create a single PowerPoint-style presentation slide (designed as a visual mockup using markdown/text) that explains the **technical architecture and data flow** of an internal Snowflake application called **"TACV Quota Scenario Modeling App"**.

The audience is the **Data Science team** - they are technical and want to understand how the application works, what models/APIs are used, and how the analysis is generated.

### Technical Overview

**Application Stack:**
- **Frontend:** Streamlit (Python-based web framework)
- **Deployment:** Snowflake Native App / Streamlit in Snowflake
- **AI/LLM:** Snowflake Cortex using Claude Sonnet 4.5
- **Data Processing:** Pandas for parsing and transformation

### Data Flow (Step by Step)

```
1. DATA INPUT
   User pastes/uploads account data (from Google Sheets, CSV, Excel)
   ↓
2. SMART PARSING
   - Auto-detect format (tab-delimited, CSV, pipe, key-value)
   - Normalize column names to standard fields
   - Parse currency values, dates
   - Validate required fields present
   ↓
3. FIELD CONFIRMATION
   User reviews and can manually adjust parsed values
   ↓
4. CONTEXT ENRICHMENT
   User adds qualitative context (business signals, account notes)
   ↓
5. PROMPT CONSTRUCTION
   Build structured prompt with:
   - Fiscal year context (FY dates, 1H/2H splits)
   - TACV definitions and classification rules
   - Scenario selection criteria
   - Account data (all parsed fields)
   - Qualitative context
   - Structured output format specification
   ↓
6. LLM INFERENCE
   Call Snowflake Cortex COMPLETE() with Claude Sonnet 4.5
   - Prompt: ~1,500 tokens (instructions + data)
   - Response: ~2,000-3,000 tokens (structured analysis)
   - Latency: ~10-15 seconds per account
   ↓
7. RESPONSE PARSING
   Parse structured response into sections:
   - [SUMMARY] - Key metrics, confidence level
   - [DATA_FLAGS] - Quality issues detected
   - [SCENARIOS] - Conservative/Base/Stretch with breakdowns
   - [RECOMMENDATION] - Selected scenario + rationale
   - [CALCULATIONS] - Transparency into derivation
   - [RISKS] - Identified risks and mitigations
   ↓
8. DISPLAY & EXPORT
   Render in tabbed UI, allow export to MD/JSON/CSV
```

### Key Technical Components

**Prompt Engineering:**
- Detailed TACV definitions (Renewal vs Growth, Contracted vs Non-Contracted)
- Explicit scenario selection criteria with consumption pattern triggers
- Structured output format with delimiters for reliable parsing
- Confidence calibration instructions ("Be honest if data is weak")

**Structured Output Parsing:**
- Response uses custom delimiters: `[SECTION]...[/SECTION]`, `---SCENARIO---...---END_SCENARIO---`
- Regex-based extraction into Python dicts
- Graceful fallback if parsing fails (show raw output)

**Analysis Logic (in prompt):**
- Calculates capacity runway (months at current burn)
- Detects acceleration/deceleration (L30D vs L90D comparison)
- Evaluates early renewal scenarios (if overage > 2x annual)
- Splits TACV into Quota-Bearing vs Non-Quota based on contract structure

**Bulk Processing:**
- Iterates through uploaded DataFrame
- Calls same analysis pipeline per row
- 0.5s delay between calls (rate limit protection)
- Error handling: log failures, continue processing

### Slide Requirements

- Use a technical diagram or flowchart style
- Show the data flow from input → LLM → output
- Highlight the Snowflake Cortex / Claude integration
- Call out prompt engineering as a key component
- Keep it readable for a 5-minute explanation
- Use Snowflake brand colors where appropriate (#29B5E8, #0C2340)

### Output Format

Please provide the slide content in a structured format:

```
SLIDE TITLE: [Title Here]
SUBTITLE: [Technical context]

ARCHITECTURE DIAGRAM:
[Visual representation of the data flow]

KEY COMPONENTS:
1. Component Name - Brief technical description
2. Component Name - Brief technical description
3. Component Name - Brief technical description

TECH STACK CALLOUTS:
- Bullet points on specific technologies/models

METRICS/STATS (if applicable):
- Latency, token counts, etc.

DESIGN NOTES:
- Diagram style suggestions
- Color coding recommendations
```

### Suggested Titles

- "Under the Hood: How TACV Analysis Works"
- "Technical Architecture: From Data to Quota Recommendation"
- "The AI Pipeline: Cortex + Claude Powering Quota Modeling"




