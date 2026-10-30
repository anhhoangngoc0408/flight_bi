import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from components.header import render_header
from services.analytics import (
    get_data_quality_checks,
    get_data_quality_runs,
    get_etl_load_log,
    get_warehouse_row_counts,
)
from services.database import DatabaseUnavailableError, query_df

render_header(
    "Reports & Data Quality",
    "Review warehouse coverage, ETL health, and consistency checks. This page is read-only.",
)

try:
    row_counts = get_warehouse_row_counts()
    runs = get_data_quality_runs()
    checks = get_data_quality_checks()
    load_log = get_etl_load_log()
    monthly_coverage = query_df(
        """
        SELECT m.year, m.month,
               COUNT(DISTINCT o.route_key) AS ontime_routes,
               COUNT(DISTINCT t.route_key) AS t100_routes,
               SUM(CASE WHEN t.route_key IS NOT NULL THEN 1 ELSE 0 END) AS matched_route_months
        FROM dim_month m
        LEFT JOIN fact_ontime_route_month o ON o.month_key = m.month_key
        LEFT JOIN fact_capacity_route_month t
               ON t.month_key = o.month_key AND t.carrier_key = o.carrier_key AND t.route_key = o.route_key
        GROUP BY m.year, m.month ORDER BY m.year, m.month
        """
    )
    quarterly_coverage = query_df(
        """
        SELECT year, quarter, source_presence, complete_quarter,
               months_in_t100, revenue_est_usd
        FROM mart_carrier_quarter_rask ORDER BY year, quarter
        """
    )
except DatabaseUnavailableError as exc:
    st.error("Could not query the warehouse reporting and data-quality tables.")
    st.caption(str(exc))
    st.stop()

latest_run = runs.iloc[0] if not runs.empty else None
latest_run_id = int(latest_run["run_id"]) if latest_run is not None else None
latest_checks = checks.loc[checks["run_id"] == latest_run_id] if latest_run_id is not None and not checks.empty else pd.DataFrame()

if latest_run is None:
    st.warning("No ETL run record was found in etl_run.")
else:
    run_status = str(latest_run["status"])
    if run_status.upper() == "SUCCESS":
        st.success(f"Latest ETL run #{latest_run_id}: {run_status}")
    else:
        st.warning(f"Latest ETL run #{latest_run_id}: {run_status}")
    st.caption(f"Started: {latest_run['started_at']} · Finished: {latest_run['finished_at']}")

kpis = st.columns(4)
kpis[0].metric("Warehouse objects counted", f"{len(row_counts):,}")
kpis[1].metric("Latest run checks", f"{len(latest_checks):,}")
kpis[2].metric("DQ checks passed", f"{int((latest_checks['status'].str.upper() == 'PASS').sum()):,}" if not latest_checks.empty else "N/A")
kpis[3].metric("DQ checks failed", f"{int((latest_checks['status'].str.upper() == 'FAIL').sum()):,}" if not latest_checks.empty else "N/A")

st.markdown("### Source coverage")
if not monthly_coverage.empty:
    monthly_coverage["period"] = monthly_coverage.apply(lambda row: f"{int(row['year'])}-{int(row['month']):02d}", axis=1)
    chart_data = monthly_coverage.melt(
        id_vars="period", value_vars=["ontime_routes", "t100_routes"],
        var_name="Source", value_name="Route-month rows",
    )
    chart_data["Source"] = chart_data["Source"].map({"ontime_routes": "On-Time", "t100_routes": "T-100"})
    figure = px.bar(
        chart_data, x="period", y="Route-month rows", color="Source", barmode="group",
        title="Monthly route coverage by source",
        color_discrete_map={"On-Time": "#2878C8", "T-100": "#38BFD6"},
    )
    figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
    st.dataframe(monthly_coverage, width="stretch", hide_index=True)

if not quarterly_coverage.empty:
    quarterly_coverage["quarter_label"] = quarterly_coverage.apply(
        lambda row: f"{int(row['year'])}-Q{int(row['quarter'])}", axis=1
    )
    quarterly_coverage["Coverage"] = quarterly_coverage["source_presence"].map({
        "t100+db1b": "T-100 + DB1B", "t100_only": "T-100 only", "db1b_only": "DB1B only"
    }).fillna(quarterly_coverage["source_presence"])
    coverage_chart = px.bar(
        quarterly_coverage, x="quarter_label", y="months_in_t100", color="Coverage",
        title="T-100 month coverage and DB1B matching by quarter",
        labels={"quarter_label": "Quarter", "months_in_t100": "T-100 months (of 3)"},
        color_discrete_map={"T-100 + DB1B": "#36B58A", "T-100 only": "#F2AE4A", "DB1B only": "#E66B6B"},
    )
    coverage_chart.update_layout(template="plotly_white", barmode="group", margin=dict(l=12, r=12, t=55, b=12))
    st.plotly_chart(coverage_chart, width="stretch", config={"displayModeBar": False})
    st.dataframe(quarterly_coverage, width="stretch", hide_index=True)

st.markdown("### Warehouse row counts")
if row_counts.empty:
    st.info("No allowlisted warehouse objects are available.")
else:
    st.dataframe(row_counts, width="stretch", hide_index=True)
    st.download_button(
        "Download warehouse row counts CSV", row_counts.to_csv(index=False).encode("utf-8-sig"),
        file_name="aerovista_warehouse_row_counts.csv", mime="text/csv",
        icon=":material/download:",
    )

st.markdown("### ETL load log")
if load_log.empty:
    st.info("No etl_load_log records are available.")
else:
    st.dataframe(load_log, width="stretch", hide_index=True)
    st.download_button(
        "Download ETL load log CSV", load_log.to_csv(index=False).encode("utf-8-sig"),
        file_name="aerovista_etl_load_log.csv", mime="text/csv",
        icon=":material/download:",
    )

st.markdown("### Consistency checks")
if latest_checks.empty:
    st.info("No data-quality checks are available for the latest ETL run.")
else:
    status_summary = latest_checks.groupby(["check_group", "status"], dropna=False).size().reset_index(name="check_count")
    figure = px.bar(
        status_summary, x="check_group", y="check_count", color="status", barmode="group",
        title="DQ check results by group",
        color_discrete_map={"PASS": "#36B58A", "FAIL": "#E66B6B"},
    )
    figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
    st.dataframe(
        latest_checks[["check_id", "run_id", "check_group", "status", "metric_value", "checked_at"]],
        width="stretch", hide_index=True,
    )
    st.download_button(
        "Download latest DQ checks CSV", latest_checks.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"aerovista_dq_run_{latest_run_id}.csv", mime="text/csv",
        icon=":material/download:",
    )

carrier_file = Path(__file__).resolve().parents[1] / "data" / "aggregated_WN_2024" / "selected_carrier.json"
if carrier_file.exists():
    try:
        carrier_info = json.loads(carrier_file.read_text(encoding="utf-8"))
        with st.expander("Dataset selection metadata"):
            metadata_columns = st.columns(3)
            metadata_columns[0].metric("Selected carrier", str(carrier_info.get("carrier", "N/A")))
            metadata_columns[1].metric("Selected year", str(carrier_info.get("year", "N/A")))
            rows = carrier_info.get("ontime_rows_raw")
            metadata_columns[2].metric("Raw On-Time rows", "N/A" if rows is None else f"{int(rows):,}")
    except (OSError, json.JSONDecodeError) as exc:
        st.warning(f"Could not read selected_carrier.json: {exc}")

st.caption(
    "Counts are computed at request time against a fixed allowlist. The UI does not execute ETL, "
    "write to warehouse tables, or infer missing-value/duplicate tests when no DQ rule exists."
)