# Power BI (Service refresh) — L&C Emailing dataset

## 1) Export the dataset (CSV)

From the project root:

```bash
. .venv/bin/activate
python -m src.lnc_agent.cli export-powerbi --out powerbi_dataset
```

This produces:

- `powerbi_dataset/dim_prospects.csv`
- `powerbi_dataset/fact_recommendations.csv`
- `powerbi_dataset/fact_agent_tracking.csv`
- `powerbi_dataset/fact_sendgrid_events.csv`
- `powerbi_dataset/kpi_daily.csv`

## 2) Put the folder in OneDrive / SharePoint (for automatic refresh)

To enable scheduled refresh in Power BI Service without running your laptop:

- Move `powerbi_dataset/` into a OneDrive/SharePoint synced location (recommended)
  - Example: `OneDrive/lead_and_connect/powerbi_dataset/`

## 3) Build your report in Power BI Desktop

Use **Get Data → Folder** (or **Get Data → Text/CSV** for each file).

Recommended model:

- `dim_prospects[id]` 1→* `fact_recommendations[prospect_id]`
- `dim_prospects[id]` 1→* `fact_agent_tracking[prospect_id]`
- `dim_prospects[email]` 1→* `fact_sendgrid_events[email]`
- Create a Date table and relate `Date[Date]` to `fact_sendgrid_events[date]` and `kpi_daily[date]`

## 4) Publish + refresh in Power BI Service (Option B)

- Publish your `.pbix`
- In the dataset settings, configure the OneDrive/SharePoint connection
- Set up **Scheduled refresh**

Notes:
- If you used **Folder** connector pointed at OneDrive/SharePoint, refresh is usually straightforward.
- If you used a local disk path, refresh will not work in the Service until you move it to OneDrive/SharePoint or use an on-premises data gateway.
