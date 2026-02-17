# Roadmap Slide Generation Prompt

Use this prompt with Claude to generate a presentation slide highlighting upcoming features for the TACV Quota Scenario Modeling App.

---

## Prompt

Create a single PowerPoint-style presentation slide (designed as a visual mockup using markdown/text) that showcases the **upcoming features and roadmap** for an internal Snowflake tool called **"TACV Quota Scenario Modeling App"**.

This slide should follow an introductory slide that already covered current features. The goal is to build excitement about what's coming next.

### Context

The TACV Quota Scenario Modeling App currently allows Field Operations to:
- Paste account data and get AI-powered quota analysis
- View Conservative/Base/Stretch TACV scenarios
- See quota classification (Renewal vs Growth, Contracted vs Non-Contracted)
- Export analysis to markdown/text/JSON

### Upcoming Features to Highlight

**NOW IN DEVELOPMENT (Priority #1):**

**Bulk Account Analysis**
- Upload a spreadsheet with hundreds of accounts
- Process all accounts automatically with full AI analysis
- View results in an interactive table with drill-down capability
- Export complete analysis to CSV/Excel for team distribution
- Estimated processing: ~10 seconds per account with progress tracking

---

**FUTURE STATE (Planned):**

**Direct Data Integration**
- Connect directly to Snowflake data tables (consumption, contracts, capacity)
- No more manual copy-paste from Google Sheets
- Always up-to-date data, refreshed automatically
- *Timeline: Post-planning cycle, pending data source access provisioning*

---

**ON THE HORIZON (Under Consideration):**

**Scheduled Batch Processing**
- Run bulk analysis on a defined schedule (nightly, weekly)
- Automated reports delivered to stakeholders
- Proactive monitoring without manual intervention

**Portfolio & Territory Roll-ups**
- Aggregate quota views by segment, rep, or region
- Manager dashboards showing team-level quota coverage
- Identify gaps and opportunities across territories

**Historical Analysis Tracking**
- Store and compare past analyses for the same accounts
- Track how recommendations evolve over planning cycles
- Audit trail for compliance and review

**Proactive Alerts**
- Notifications when accounts hit risk thresholds
- "5 accounts have <3 months capacity remaining"
- Early warning system for overage risk

### Slide Requirements

- Use Snowflake brand colors (primary: #29B5E8 Snowflake Blue, accent: #0C2340 Dark Navy)
- Organize features into clear tiers/phases (Now, Next, Later or similar)
- Use visual indicators to show development status (e.g., In Progress, Planned, Exploring)
- Keep text concise - this is a roadmap, not documentation
- Include a "timeline" or "phases" visual if appropriate
- Make it clear this is iterative - feedback welcome

### Suggested Tagline Options (pick one or suggest better)

- "Building for Scale: What's Next"
- "From Single Account to Full Portfolio"
- "The Roadmap to Smarter Quota Planning"

### Output Format

Please provide the slide content in a structured format that could easily be recreated in PowerPoint or Google Slides, including:

```
SLIDE TITLE: [Title Here]
SUBTITLE: [Tagline]

PHASE SECTIONS:

[NOW - In Development]
- Feature 1: Brief description
- Feature 2: Brief description

[NEXT - Planned]
- Feature 1: Brief description

[FUTURE - Exploring]
- Feature 1: Brief description
- Feature 2: Brief description

FOOTER/CTA:
[Feedback callout or timeline note]

DESIGN NOTES:
- Layout suggestions
- Visual hierarchy recommendations
- Color usage
```








