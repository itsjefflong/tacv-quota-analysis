# TACV Quota Scenario Modeling App - Future Features

A running list of planned and potential features for the TACV app.

---

## 🚧 In Development

### Bulk Account Analysis
**Status:** In Development / Testing  
**Priority:** P0  
**Target:** Current Planning Cycle

- Upload spreadsheet with multiple accounts (CSV/Excel)
- Process all accounts with full AI-powered analysis
- View results in interactive table with drill-down
- Export complete analysis to CSV/Excel
- Progress tracking during processing (~10 sec/account)
- Error handling for failed accounts

---

## 📋 Planned

### Direct Data Table Integration
**Status:** Planned  
**Priority:** P1  
**Target:** Post-Planning Cycle (pending data access provisioning)

- Connect directly to Snowflake consumption/contract/capacity tables
- Eliminate manual copy-paste from Google Sheets
- Auto-refresh with latest data
- Account lookup by name or ID

**Blockers:**
- [ ] Identify and document required data sources
- [ ] Request table access provisioning
- [ ] Define data refresh cadence

---

## 💡 Future Considerations

### Scheduled Batch Processing
**Priority:** P2

- Run bulk analysis on a schedule (nightly, weekly)
- Define account lists to monitor automatically
- Automated reports delivered to stakeholders
- Integration with email or Slack notifications

### Portfolio & Territory Roll-ups
**Priority:** P2

- Aggregate quota views by segment, rep, or region
- Manager dashboards showing team-level quota coverage
- Identify gaps and opportunities across territories
- Summary statistics (total quota, coverage %, etc.)

### Historical Analysis Tracking
**Priority:** P3

- Store past analyses in a persistent table
- Compare how recommendations evolve over time
- Audit trail showing who ran what analysis when
- Version comparison view

### Proactive Alerts & Notifications
**Priority:** P3

- Alert when accounts hit risk thresholds
- Examples: "<3 months capacity", "overage imminent", "renewal in 60 days"
- Configurable thresholds per segment
- Delivery via email, Slack, or in-app

### What-If Scenario Modeling
**Priority:** P3

- Interactive sliders to adjust assumptions
- "What if consumption grows 30%?"
- "What if contract extends 6 months?"
- Real-time TACV recalculation

### CRM/Salesforce Integration
**Priority:** P4

- Push quota recommendations to Salesforce opportunity records
- Sync account data from CRM
- Link analysis to specific opportunities

### Custom Prompt Templates
**Priority:** P4

- Allow teams to customize analysis prompts
- Segment-specific guidance (Enterprise vs Commercial)
- Save and share templates across team

### API Access
**Priority:** P4

- REST API for programmatic analysis requests
- Enable integration with other internal tools
- Batch processing via API calls

---

## ✅ Completed

### Single Account Analysis (v1.0)
- Paste account data from Google Sheets
- AI-powered TACV analysis with Claude via Cortex
- Conservative/Base/Stretch scenario modeling
- Quota classification (Renewal vs Growth, Contracted vs Non-Contracted)
- Data quality flags and validation
- Export to Markdown/Text/JSON

---

## Notes

- Features are prioritized based on user feedback and business impact
- Timelines are estimates and subject to change
- P0 = Critical, P1 = High, P2 = Medium, P3 = Low, P4 = Backlog

---

*Last updated: December 2024*





