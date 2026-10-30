# AEROVISTA — Aviation Intelligence

Streamlit BI dashboard for the aviation warehouse. The site reads the existing `aviation_dw` MySQL database and local ETL-generated answer/metadata CSVs. It does not run ETL or write to the warehouse.

## Requirements

- Python 3.14 (or another version supported by the installed Streamlit / Pandas dependencies)
- MySQL 8 with the existing `aviation_dw` schema and marts
- A MySQL account with `SELECT` privileges on the required marts, dimensions, facts, and DQ metadata tables

## Setup

1. From the repository directory, create and activate a virtual environment if desired:

	```powershell
	py -3.14 -m venv .venv
	.\.venv\Scripts\Activate.ps1
	```

2. Install dependencies and create your local configuration:

	```powershell
	pip install -r requirements.txt
	Copy-Item .env.example .env
	```

3. Edit `.env` with local connection values. Do not commit `.env`.
4. Ensure the MySQL account used by the dashboard is read-only. The app also starts sessions read-only and restricts application SQL to a single non-locking `SELECT` statement.
5. Start with `streamlit run app.py` and open the local URL printed by Streamlit.

Example environment variables:

- `MYSQL_HOST` (default `127.0.0.1`)
- `MYSQL_PORT` (default `3306`)
- `MYSQL_DB` (default `aviation_dw`)
- `MYSQL_USER`
- `MYSQL_PASSWORD`

The application intentionally refuses to use credentials embedded in source files or a default database password. If connection configuration is missing, pages show a database-unavailable message rather than substitute sample data.

## Pages

1. **Executive Overview** — annual schedule, OTP, PLF, turnaround, coverage-qualified estimated RASK, trends, delay-cause totals, delayed-route ranking, and generated insights.
2. **Flight Operations** — year/month/carrier/origin/destination filters, OTP and cancellation trends, BTS delay causes, turnaround-associated daypart context, route table and delay ranking.
3. **Turnaround Optimization** — scheduled/actual weighted averages, over-schedule rates, airport/daypart comparisons, late-inbound association, ETL reference scenario CSV, and a separate adjustable hypothetical scenario.
4. **Revenue & Capacity** — quarterly T-100/DB1B coverage, PLF, ASM, RPM, estimated revenue, RASK/yield, route ranking, and fare-class sample mix.
5. **OLAP Explorer** — carrier-to-route drill-down at the available aggregate grain. It does not fabricate flight records.
6. **Data Quality & Reports** — allowlisted warehouse row counts, source coverage, ETL runs/load logs, DQ results, metadata, and CSV downloads.

## Data and KPI limitations

- Warehouse facts are monthly or quarterly aggregates; the current schema has no individual flight timestamps/flight numbers. Flight-level browsing, weekday-by-daypart heatmaps, and raw turnaround histograms/box plots are therefore unavailable and are called out in the UI.
- OTP uses completed flights as denominator. Cancellation rate uses scheduled flights. PLF is passengers/seats. Turnaround averages use summed minutes divided by valid events.
- Delay causes are BTS's five groups only. No additional cause categories are inferred.
- DB1B is a 10% ticket sample. Revenue is an ETL estimate; RASK/yield are displayed in cents with their respective warehouse measures and only when source coverage permits.
- Monthly T-100 and DB1B coverage is surfaced before annual/route revenue KPIs are interpreted.
- The turnaround slider is a hypothetical assumption and must not be interpreted as an equal reduction in total flight delays. The separate ETL scenario is loaded from the existing answer CSV when present.

## Security and operations

- Do not use the ETL owner/root account for the dashboard. Create/use an account restricted to `SELECT` on the required objects.
- Do not run `etl/etl_pipeline.py` from the web app. Existing ETL/schema scripts include destructive refresh/DDL behavior and remain separate operator workflows.
- `.env` and Streamlit secrets are ignored by Git. `.env.example` contains placeholders only.
- Analytics queries use bound values and aggregate in MySQL; fact-level data is not loaded wholesale into Pandas.
