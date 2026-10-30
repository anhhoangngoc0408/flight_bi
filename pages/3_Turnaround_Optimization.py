import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

from components.header import render_header
from services.analytics import (
    get_available_years,
    get_turnaround_airports,
    get_turnaround_dayparts,
    get_turnaround_monthly,
    get_turnaround_summary,
)
from services.database import DatabaseUnavailableError

render_header(
    "Turnaround Optimization",
    "Investigate observed turnaround performance and an explicitly hypothetical improvement scenario.",
)

try:
    years = get_available_years()
except DatabaseUnavailableError as exc:
    st.error("Could not query the warehouse.")
    st.caption(str(exc))
    st.stop()

if not years:
    st.info("No years are available for analysis.")
    st.stop()

filters = st.columns(2)
year = filters[0].selectbox("Year", years, key="turn_year")
months = ["All"] + list(range(1, 13))
month_choice = filters[1].selectbox("Month", months, key="turn_month")
month = None if month_choice == "All" else int(month_choice)

try:
    summary_frame = get_turnaround_summary(year, month)
    monthly = get_turnaround_monthly(year)
    airports = get_turnaround_airports(year, month)
    dayparts = get_turnaround_dayparts(year, month)
except DatabaseUnavailableError as exc:
    st.error("Could not read the turnaround marts.")
    st.caption(str(exc))
    st.stop()

if summary_frame.empty or pd.isna(summary_frame.iloc[0]["turn_n"]) or not float(summary_frame.iloc[0]["turn_n"]):
    st.info("No valid turnaround events match this selection.")
    st.stop()

summary = summary_frame.iloc[0]
turn_n = float(summary["turn_n"])
actual_sum = float(summary["turn_actual_sum_min"] or 0)
scheduled_sum = float(summary["turn_sched_sum_min"] or 0)
excess_sum = float(summary["turn_excess_sum_min"] or 0)
actual_avg = actual_sum / turn_n
scheduled_avg = scheduled_sum / turn_n
over_schedule_rate = float(summary["turn_over_sched_n"] or 0) / turn_n
late_inbound_n = float(summary["turn_after_late_inbound_n"] or 0)
dep_delay_sum = float(summary["dep_delay_sum_min"] or 0)
late_inbound_share = late_inbound_n / turn_n

kpis = st.columns(4)
kpis[0].metric("Avg scheduled turnaround", f"{scheduled_avg:.1f} min")
kpis[1].metric("Avg actual turnaround", f"{actual_avg:.1f} min")
kpis[2].metric("Over-schedule rate", f"{over_schedule_rate:.1%}")
kpis[3].metric("Valid turnaround events", f"{turn_n:,.0f}")

st.markdown("### Observed performance")
left, right = st.columns(2)
with left:
    if monthly.empty:
        st.info("No monthly turnaround data is available.")
    else:
        monthly["month_label"] = monthly["month"].map(lambda value: pd.Timestamp(year, int(value), 1).strftime("%b"))
        chart = px.line(
            monthly, x="month_label", y=["avg_turn_sched_min", "avg_turn_actual_min"],
            markers=True, title="Scheduled vs actual turnaround by month",
            labels={"month_label": "Month", "value": "Minutes", "variable": "Measure"},
            color_discrete_map={"avg_turn_sched_min": "#38BFD6", "avg_turn_actual_min": "#2878C8"},
        )
        chart.for_each_trace(lambda trace: trace.update(name={
            "avg_turn_sched_min": "Scheduled average", "avg_turn_actual_min": "Actual average"
        }.get(trace.name, trace.name)))
        chart.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
        st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})

with right:
    if airports.empty:
        st.info("No airport turnaround data is available.")
    else:
        airport_chart = px.bar(
            airports.head(15).sort_values("turn_excess_sum_min"),
            x="turn_excess_sum_min", y="airport_code", orientation="h",
            title="Airports by total turnaround excess",
            labels={"turn_excess_sum_min": "Total excess minutes", "airport_code": "Airport"},
            color_discrete_sequence=["#2878C8"],
            hover_data={"avg_turn_sched_min": ":.1f", "avg_turn_actual_min": ":.1f", "turn_over_sched_rate": ":.1%"},
        )
        airport_chart.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
        st.plotly_chart(airport_chart, width="stretch", config={"displayModeBar": False})

if not dayparts.empty:
    daypart_chart = px.bar(
        dayparts, x="daypart_name", y=["avg_turn_sched_min", "avg_turn_actual_min"],
        barmode="group", title="Scheduled vs actual turnaround by daypart",
        labels={"daypart_name": "Daypart", "value": "Minutes", "variable": "Measure"},
        color_discrete_map={"avg_turn_sched_min": "#38BFD6", "avg_turn_actual_min": "#2878C8"},
    )
    daypart_chart.for_each_trace(lambda trace: trace.update(name={
        "avg_turn_sched_min": "Scheduled average", "avg_turn_actual_min": "Actual average"
    }.get(trace.name, trace.name)))
    daypart_chart.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
    st.plotly_chart(daypart_chart, width="stretch", config={"displayModeBar": False})

st.markdown("### Late inbound association")
association = pd.DataFrame({
    "Inbound group": ["Not flagged late", "Following a late inbound"],
    "Turnaround events": [turn_n - late_inbound_n, late_inbound_n],
    "Share of events": [1 - late_inbound_share, late_inbound_share],
})
left, right = st.columns(2)
with left:
    chart = px.bar(
        association, x="Inbound group", y="Share of events", title="Turnarounds following late inbound flights",
        labels={"Share of events": "Share of valid turnaround events"},
        color="Inbound group", color_discrete_map={"Not flagged late": "#38BFD6", "Following a late inbound": "#F2AE4A"},
    )
    chart.update_yaxes(tickformat=".0%")
    chart.update_layout(template="plotly_white", showlegend=False, margin=dict(l=12, r=12, t=55, b=12))
    st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
with right:
    st.metric("Mean departure delay per valid turnaround", f"{dep_delay_sum / turn_n:.1f} min")
    st.caption("The aggregate data shows association only; it does not establish that late inbound arrival caused the departure delay.")

st.markdown("### Turnaround optimization simulator")
scenario_left, scenario_right = st.columns([1, 2])
with scenario_left:
    reduction = st.slider(
        "Assumed turnaround reduction",
        min_value=0,
        max_value=30,
        value=15,
        step=1,
        format="%d%%",
        help="This is a user-selected scenario assumption, not a measured operational result.",
    ) / 100

target_avg = actual_avg * (1 - reduction)
minutes_saved_per_turn = actual_avg - target_avg
total_turnaround_minutes_saved = minutes_saved_per_turn * turn_n
with scenario_right:
    metrics = st.columns(4)
    metrics[0].metric("Measured current average", f"{actual_avg:.1f} min")
    metrics[1].metric("Scenario reduction", f"{reduction:.0%}")
    metrics[2].metric("Scenario target average", f"{target_avg:.1f} min")
    metrics[3].metric("Observed events in scope", f"{turn_n:,.0f}")
    st.metric("Assumed turnaround time saved across observed events", f"{total_turnaround_minutes_saved:,.0f} min")

scenario_chart = pd.DataFrame(
    {"Average turnaround (min)": [actual_avg, target_avg]},
    index=["Measured current", "Scenario target"],
)
st.bar_chart(scenario_chart, y="Average turnaround (min)", y_label="Minutes", height=260)

st.info(
    "Simulation only: the selected reduction is applied to the measured average turnaround, and the per-event saving is multiplied by the observed event count. "
    "This is not a forecast of departure-delay recovery and must not be interpreted as the same percentage reduction in total flight delays."
)
st.caption(
    f"Observed actual turnaround excess over scheduled: {excess_sum:,.0f} minutes. "
    "Turnaround is inferred by the ETL from aircraft tail and adjacent flight times, not directly reported by BTS."
)
st.warning(
    "The warehouse contains monthly aggregate measures, not individual turnaround-duration records. "
    "A flight-level turnaround histogram or box plot cannot be computed without raw-event data."
)

st.markdown("### ETL reference scenario")
scenario_path = Path(__file__).resolve().parents[1] / "data" / "aggregated_WN_2024" / "answer_turnaround_15pct_scenario.csv"
if scenario_path.exists():
    try:
        scenario_frame = pd.read_csv(scenario_path, index_col=0)
        scenario_values = pd.to_numeric(scenario_frame.iloc[:, 0], errors="coerce")
        # This existing ETL answer file has a fixed, inspected row order.
        if len(scenario_values) < 5:
            raise ValueError("The ETL scenario file has fewer rows than expected.")
        etl_actual = None if pd.isna(scenario_values.iloc[0]) else float(scenario_values.iloc[0])
        etl_target = None if pd.isna(scenario_values.iloc[1]) else float(scenario_values.iloc[1])
        etl_events = None if pd.isna(scenario_values.iloc[3]) else float(scenario_values.iloc[3])
        etl_saved = None if pd.isna(scenario_values.iloc[4]) else float(scenario_values.iloc[4])
        etl_metrics = st.columns(4)
        etl_metrics[0].metric("ETL current average", "N/A" if etl_actual is None else f"{etl_actual:.1f} min")
        etl_metrics[1].metric("ETL 15% target average", "N/A" if etl_target is None else f"{etl_target:.1f} min")
        etl_metrics[2].metric("ETL scenario delay-recovery estimate", "N/A" if etl_saved is None else f"{etl_saved:,.0f} min", help="Existing ETL scenario estimate; this is not observed delay recovery.")
        etl_metrics[3].metric("ETL affected events", "N/A" if etl_events is None else f"{etl_events:,.0f}")
        st.caption("These reference values come from the existing ETL answer CSV. The adjustable simulator above is a separate user-defined assumption.")
    except (OSError, ValueError, IndexError) as exc:
        st.warning(f"Could not read the ETL scenario file: {exc}")
else:
    st.info("The ETL answer_turnaround_15pct_scenario.csv file is not present; only the adjustable hypothetical scenario is shown.")