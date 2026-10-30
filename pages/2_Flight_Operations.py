import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import date

from components.header import render_header
from services.analytics import (
    get_available_years,
    get_operations_causes,
    get_operations_dayparts,
    get_operations_monthly,
    get_operations_routes,
    get_operations_summary,
    get_performance_explorer,
    get_route_filter_values,
)
from services.database import DatabaseUnavailableError

render_header(
    "Flight Operations",
    "Explore punctuality, delay causes, cancellations, and route-level performance using verified monthly aggregates.",
)

CAUSE_LABELS = {
    "Carrier": "Carrier",
    "Weather": "Weather",
    "NAS": "National Airspace System",
    "Security": "Security",
    "LateAircraft": "Late aircraft",
}

try:
    years = get_available_years()
    route_choices = get_route_filter_values()
except DatabaseUnavailableError as exc:
    st.error("Could not read the operational marts from MySQL.")
    st.caption(str(exc))
    st.stop()

if not years or route_choices.empty:
    st.info("No operational data is available for filtering.")
    st.stop()

carrier_values = sorted(route_choices["carrier"].dropna().unique().tolist())
airport_values = sorted(set(route_choices["origin"].dropna()) | set(route_choices["dest"].dropna()))
filter_keys = (
    "ops_year", "ops_month", "ops_carrier", "ops_origin", "ops_dest", "ops_daypart",
    "ops_delay_causes", "ops_perf_dimension", "ops_perf_range", "ops_perf_carriers",
    "ops_perf_airports", "ops_perf_metric",
)
if st.button("Reset filters", icon=":material/refresh:", key="ops_reset_filters"):
    for key in filter_keys:
        st.session_state.pop(key, None)
    st.rerun()

filter_columns = st.columns(6)
selected_year = filter_columns[0].selectbox("Year", years, index=0, key="ops_year")
months = ["All"] + list(range(1, 13))
selected_month = filter_columns[1].selectbox("Month", months, key="ops_month")
selected_carrier = filter_columns[2].selectbox("Carrier", ["All", *carrier_values], key="ops_carrier")
selected_origin = filter_columns[3].selectbox("Origin airport", ["All", *airport_values], key="ops_origin")
selected_dest = filter_columns[4].selectbox("Destination airport", ["All", *airport_values], key="ops_dest")
daypart_values = ["All", "Morning", "Afternoon", "Evening", "Night"]
selected_daypart = filter_columns[5].selectbox("Daypart", daypart_values, key="ops_daypart")

month_filter = None if selected_month == "All" else int(selected_month)
carrier_filter = None if selected_carrier == "All" else str(selected_carrier)
origin_filter = None if selected_origin == "All" else str(selected_origin)
dest_filter = None if selected_dest == "All" else str(selected_dest)

try:
    summary_frame = get_operations_summary(
        selected_year, month_filter, carrier_filter, origin_filter, dest_filter
    )
    monthly = get_operations_monthly(
        selected_year, carrier_filter, origin_filter, dest_filter
    )
    causes = get_operations_causes(
        selected_year, month_filter, carrier_filter, origin_filter, dest_filter
    )
    routes = get_operations_routes(
        selected_year, month_filter, carrier_filter, origin_filter, dest_filter
    )
    dayparts = get_operations_dayparts(selected_year, month_filter, carrier_filter)
except DatabaseUnavailableError as exc:
    st.error("Could not query the operational marts.")
    st.caption(str(exc))
    st.stop()

if selected_daypart != "All":
    dayparts = dayparts.loc[dayparts["daypart_name"] == selected_daypart]

if summary_frame.empty or pd.isna(summary_frame.iloc[0]["flights_scheduled"]):
    st.info("No flights match the selected filters.")
    st.stop()

summary = summary_frame.iloc[0]
completed = float(summary["flights_completed"] or 0)
scheduled = float(summary["flights_scheduled"] or 0)
arr_delayed = float(summary["arr_del15_count"] or 0)
cancelled = float(summary["flights_cancelled"] or 0)
otp = 1 - arr_delayed / completed if completed else None
cancel_rate = cancelled / scheduled if scheduled else None
average_delay = float(summary["arr_delay_pos_min"]) / completed if completed else None

kpis = st.columns(4)
kpis[0].metric("Scheduled flights", f"{scheduled:,.0f}")
kpis[1].metric("On-time performance", "N/A" if otp is None else f"{otp:.1%}", help="OTP = 1 − arrivals delayed by 15 minutes or more / completed flights.")
kpis[2].metric("Avg. positive delay / completed flight", "N/A" if average_delay is None else f"{average_delay:.1f} min", help="Total positive arrival-delay minutes divided by completed flights; this is not the average among delayed flights only.")
kpis[3].metric("Cancellation rate", "N/A" if cancel_rate is None else f"{cancel_rate:.2%}", help="Cancelled flights divided by scheduled flights.")

st.markdown("### Interactive operational explorers")
delay_tab, performance_tab = st.tabs(["Flight delay analysis", "Flight performance explorer"])
with delay_tab:
    st.caption("Use the carrier and month filters above, then choose which of BTS's five reported delay causes to compare.")
    cause_codes = causes["cause_code"].tolist() if not causes.empty else list(CAUSE_LABELS)
    selected_causes = st.multiselect(
        "Delay categories",
        options=cause_codes,
        default=cause_codes,
        format_func=lambda code: CAUSE_LABELS.get(code, code),
        key="ops_delay_causes",
        help="BTS reports Carrier, Weather, NAS, Security, and Late aircraft; categories are not further inferred.",
    )
    delay_metric = st.selectbox(
        "Compare by",
        ["Delay minutes", "Contribution to reported delay (%)"],
        key="ops_delay_metric",
    )
    if causes.empty or causes["delay_min"].fillna(0).sum() <= 0:
        st.info("No reported delay-cause minutes are available for this selection.")
    elif not selected_causes:
        st.info("Select at least one delay category to display the chart.")
    else:
        delay_data = causes.loc[causes["cause_code"].isin(selected_causes)].copy()
        total_cause_minutes = float(causes["delay_min"].fillna(0).sum())
        delay_data["Cause"] = delay_data["cause_code"].map(CAUSE_LABELS)
        delay_data["Contribution to reported delay (%)"] = delay_data["delay_min"] / total_cause_minutes * 100
        delay_data = delay_data.sort_values("delay_min", ascending=False)
        largest_cause = delay_data.iloc[0]
        st.metric(
            "Largest selected contributor",
            f"{largest_cause['Cause']} · {float(largest_cause['Contribution to reported delay (%)']):.1f}%",
            help="Share is calculated against total minutes across all five reported BTS causes, not only selected categories.",
        )
        chart_column = "delay_min" if delay_metric == "Delay minutes" else "Contribution to reported delay (%)"
        st.bar_chart(
            delay_data,
            x="Cause",
            y=chart_column,
            horizontal=True,
            sort=False,
            y_label=delay_metric,
            height=330,
        )
        st.dataframe(
            delay_data[["Cause", "delay_min", "Contribution to reported delay (%)"]].rename(
                columns={"delay_min": "Delay minutes"},
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "Delay minutes": st.column_config.NumberColumn(format="%,.0f min"),
                "Contribution to reported delay (%)": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

with performance_tab:
    st.caption("The warehouse is monthly-grain. Date-range selections include every represented month intersecting the selected dates.")
    date_column, dimension_column, metric_column = st.columns([1.5, 1, 1])
    with date_column:
        date_range = st.date_input(
            "Date range",
            value=(date(selected_year, 1, 1), date(selected_year, 12, 31)),
            min_value=date(selected_year, 1, 1),
            max_value=date(selected_year, 12, 31),
            key="ops_perf_range",
            help="Daily records are not available; the analysis uses the full month for each month touched by this range.",
        )
    with dimension_column:
        dimension = st.selectbox(
            "Analyze by", ["Route", "Origin airport", "Destination airport", "Carrier"],
            key="ops_perf_dimension",
        )
    with metric_column:
        performance_metric = st.selectbox(
            "Chart metric", ["OTP (%)", "Avg. positive delay / completed flight (min)"],
            key="ops_perf_metric",
        )
    scope_columns = st.columns(2)
    with scope_columns[0]:
        performance_carriers = st.multiselect(
            "Carrier filter (optional)", carrier_values, default=carrier_values,
            key="ops_perf_carriers", help="No selection means all available carriers.",
        )
    with scope_columns[1]:
        performance_airports = st.multiselect(
            "Airport filter (optional)", airport_values, default=[],
            key="ops_perf_airports", help="When selected, include routes touching any selected airport.",
        )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        range_start, range_end = date_range
    else:
        range_start = range_end = date_range
    if range_start > range_end:
        st.warning("Start date must be on or before end date.")
    else:
        try:
            performance = get_performance_explorer(
                range_start.year, range_start.month, range_end.year, range_end.month,
                dimension, performance_carriers, performance_airports,
            )
        except DatabaseUnavailableError as exc:
            st.error("Could not load performance data for this selection.")
            st.caption(str(exc))
            performance = pd.DataFrame()
        if performance.empty:
            st.info("No performance records match this date range and filter selection.")
        else:
            performance["OTP (%)"] = (
                1 - performance["arr_del15_count"] / performance["flights_completed"].replace(0, pd.NA)
            ) * 100
            performance["Avg. positive delay / completed flight (min)"] = (
                performance["arr_delay_pos_min"] / performance["flights_completed"].replace(0, pd.NA)
            )
            chart_data = performance.dropna(subset=[performance_metric]).nlargest(30, performance_metric)
            st.bar_chart(
                chart_data,
                x="dimension",
                y=performance_metric,
                horizontal=True,
                sort=False,
                y_label=performance_metric,
                height=420,
            )
            st.dataframe(
                performance[["dimension", "flights_scheduled", "flights_completed", "OTP (%)", "Avg. positive delay / completed flight (min)"]]
                .rename(columns={
                    "dimension": dimension, "flights_scheduled": "Scheduled flights",
                    "flights_completed": "Completed flights",
                }),
                width="stretch", hide_index=True,
                column_config={
                    "OTP (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Avg. positive delay / completed flight (min)": st.column_config.NumberColumn(format="%.1f min"),
                },
            )

monthly = monthly.sort_values("month")
monthly["otp"] = 1 - monthly["arr_del15_count"] / monthly["flights_completed"].replace(0, pd.NA)
monthly["cancel_rate"] = monthly["flights_cancelled"] / monthly["flights_scheduled"].replace(0, pd.NA)
monthly["month_label"] = monthly["month"].map(lambda value: pd.Timestamp(selected_year, int(value), 1).strftime("%b"))

st.markdown("### Operational trends")
left, right = st.columns(2)
with left:
    if monthly.empty:
        st.info("No monthly OTP data is available.")
    else:
        figure = px.line(
            monthly, x="month_label", y="otp", markers=True,
            title="Monthly on-time performance",
            labels={"month_label": "Month", "otp": "OTP"},
            color_discrete_sequence=["#2878C8"],
        )
        figure.update_yaxes(tickformat=".0%")
        figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
        st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

with right:
    if causes.empty or causes["delay_min"].fillna(0).sum() == 0:
        st.info("No reported delay-cause minutes are available for this selection.")
    else:
        causes["cause_label"] = causes["cause_code"].map(CAUSE_LABELS).fillna(causes["cause_code"])
        figure = px.bar(
            causes, x="delay_min", y="cause_label", orientation="h",
            title="Delay minutes by BTS cause",
            labels={"delay_min": "Positive delay minutes", "cause_label": "BTS cause"},
            color_discrete_sequence=["#38BFD6"],
        )
        figure.update_yaxes(autorange="reversed")
        figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
        st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

left, right = st.columns(2)
with left:
    if monthly.empty:
        st.info("No cancellation data is available.")
    else:
        figure = px.line(
            monthly, x="month_label", y="cancel_rate", markers=True,
            title="Monthly cancellation rate",
            labels={"month_label": "Month", "cancel_rate": "Cancellation rate"},
            color_discrete_sequence=["#E66B6B"],
        )
        figure.update_yaxes(tickformat=".1%")
        figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
        st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

with right:
    if dayparts.empty:
        st.info("No turnaround-associated daypart data is available.")
    else:
        figure = px.bar(
            dayparts, x="daypart_name", y="avg_dep_delay_min",
            title="Average departure delay by turnaround daypart",
            labels={"daypart_name": "Daypart", "avg_dep_delay_min": "Minutes per valid turnaround"},
            color_discrete_sequence=["#F2AE4A"],
            hover_data={"turn_after_late_inbound_rate": ":.1%", "turn_n": ":,.0f"},
        )
        figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
        st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

st.markdown("### Route performance")
if routes.empty:
    st.info("No routes match the selected filters.")
else:
    routes["route"] = routes["origin"] + "–" + routes["dest"]
    routes["otp"] = 1 - routes["arr_del15_count"] / routes["flights_completed"].replace(0, pd.NA)
    routes["avg_delay_min"] = routes["arr_delay_pos_min"] / routes["flights_completed"].replace(0, pd.NA)
    routes["cancel_rate"] = routes["flights_cancelled"] / routes["flights_scheduled"].replace(0, pd.NA)
    top_routes = routes.head(10)
    figure = px.bar(
        top_routes.sort_values("arr_delay_pos_min"),
        x="arr_delay_pos_min", y="route", orientation="h",
        title="Top 10 routes by total positive arrival-delay minutes",
        labels={"arr_delay_pos_min": "Delay minutes", "route": "Route"},
        color_discrete_sequence=["#2878C8"],
    )
    figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
    st.dataframe(
        routes[["origin", "dest", "flights_scheduled", "flights_completed", "otp", "avg_delay_min", "cancel_rate"]]
        .rename(columns={
            "origin": "Origin", "dest": "Destination", "flights_scheduled": "Scheduled flights",
            "flights_completed": "Completed flights", "otp": "OTP",
            "avg_delay_min": "Avg arrival delay (min)", "cancel_rate": "Cancellation rate",
        }),
        width="stretch", hide_index=True,
        column_config={
            "OTP": st.column_config.NumberColumn(format="%.1f%%"),
            "Cancellation rate": st.column_config.NumberColumn(format="%.2f%%"),
            "Avg arrival delay (min)": st.column_config.NumberColumn(format="%.1f"),
        },
    )

st.warning(
    "The daypart selector filters turnaround-associated daypart analysis only. "
    "Route-level monthly OTP and delay marts do not include daypart. "
    "A weekday-by-daypart heatmap is unavailable because weekday detail is not retained."
)
st.caption(
    "OTP = 1 − arrivals delayed by 15 minutes or more / completed flights. Cancellation rate uses scheduled flights. "
    "Daypart measures describe turnaround-associated observations, not causal estimates."
)