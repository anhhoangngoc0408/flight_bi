import pandas as pd
import plotly.express as px
import streamlit as st

from components.header import render_header
from services.analytics import (
    get_available_years,
    get_delay_cause_totals,
    get_estimated_rask,
    get_executive_summary,
    get_monthly_performance,
    get_top_delayed_routes,
)
from services.database import DatabaseUnavailableError

CAUSE_LABELS = {
    "Carrier": "Carrier",
    "Weather": "Weather",
    "NAS": "National Airspace System",
    "Security": "Security",
    "LateAircraft": "Late aircraft",
}

render_header(
    "Overview",
    "A live, warehouse-backed snapshot of punctuality, capacity, and delays.",
)


def _number(value: object) -> float | None:
    """Convert a database aggregate to a finite float or unavailable value."""
    if value is None or pd.isna(value):
        return None
    result = float(value)
    return result if pd.notna(result) else None


def _ratio(numerator: object, denominator: object) -> float | None:
    top = _number(numerator)
    bottom = _number(denominator)
    if top is None or bottom is None or bottom == 0:
        return None
    return top / bottom


def _display(value: float | None, format_string: str) -> str:
    return "N/A" if value is None else format_string.format(value)


try:
    years = get_available_years()
except DatabaseUnavailableError as exc:
    st.error("Could not connect to the warehouse. This dashboard reads MySQL data only.")
    st.caption(str(exc))
    st.stop()

if not years:
    st.info("No years are available in the serving mart.")
    st.stop()

selected_year = st.selectbox("Analysis year", years, index=0)

try:
    summary_frame = get_executive_summary(selected_year)
    monthly = get_monthly_performance(selected_year)
    causes = get_delay_cause_totals(selected_year)
    routes = get_top_delayed_routes(selected_year)
    rask_frame = get_estimated_rask(selected_year)
except DatabaseUnavailableError as exc:
    st.error("Could not read one or more required marts.")
    st.caption(str(exc))
    st.stop()

if summary_frame.empty or monthly.empty:
    st.info(f"No data is available for {selected_year}.")
    st.stop()

summary = summary_frame.iloc[0]
scheduled = _number(summary["flights_scheduled"])
completed = _number(summary["flights_completed"])
arr_delayed = _number(summary["arr_del15_count"])
otp = None if completed in (None, 0) or arr_delayed is None else 1 - arr_delayed / completed
plf = _ratio(summary["passengers"], summary["seats"])
turnaround = _ratio(summary["turn_actual_sum_min"], summary["turn_n"])
rask = _number(rask_frame.iloc[0]["rask_cents"]) if not rask_frame.empty else None
covered_quarters = (
    int(_number(rask_frame.iloc[0]["covered_complete_quarters"]) or 0)
    if not rask_frame.empty
    else 0
)

flight_kpis = st.columns(3)
flight_kpis[0].metric("Scheduled flights", _display(scheduled, "{:,.0f}"))
flight_kpis[1].metric("On-time %", _display(otp, "{:.1%}"))
flight_kpis[2].metric("Load factor", _display(plf, "{:.1%}"))

efficiency_kpis = st.columns(2)
efficiency_kpis[0].metric(
    "Avg actual turnaround",
    _display(turnaround, "{:,.1f} min"),
    help="Total observed turnaround minutes divided by valid turnaround events.",
)
efficiency_kpis[1].metric(
    "Estimated RASK",
    _display(rask, "{:.2f} ¢/ASM"),
    help=(
        f"Only complete quarters with both T-100 and DB1B coverage are included "
        f"({covered_quarters}/4 quarters). DB1B revenue is an estimate from a 10% ticket sample."
    ),
)

monthly["otp"] = 1 - monthly["arr_del15_count"] / monthly["flights_completed"].replace(0, pd.NA)
monthly["plf"] = monthly["passengers"] / monthly["seats"].replace(0, pd.NA)
monthly["month_name"] = monthly["month_name"].astype(str).str[:3]

st.markdown("### Operational performance")
left, right = st.columns(2)
with left:
    otp_chart = px.line(
        monthly,
        x="month_name",
        y="otp",
        markers=True,
        labels={"month_name": "Month", "otp": "On-time performance"},
        title="Monthly on-time performance",
        color_discrete_sequence=["#2878C8"],
    )
    otp_chart.update_yaxes(tickformat=".0%", title="OTP")
    otp_chart.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
    st.plotly_chart(otp_chart, width="stretch", config={"displayModeBar": False})

with right:
    status_rows = [
        ("Completed", completed),
        ("Cancelled", _number(summary["flights_cancelled"])),
        ("Diverted", _number(summary["flights_diverted"])),
    ]
    status_data = pd.DataFrame(
        [(label, value) for label, value in status_rows if value is not None and value > 0],
        columns=["Status", "Flights"],
    )
    if status_data.empty:
        st.info("No flight-status data is available.")
    else:
        status_chart = px.pie(
            status_data,
            names="Status",
            values="Flights",
            hole=0.66,
            title="Flight status distribution",
            color="Status",
            color_discrete_map={
                "Completed": "#2878C8",
                "Cancelled": "#E66B6B",
                "Diverted": "#F2AE4A",
            },
        )
        status_chart.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
        st.plotly_chart(status_chart, width="stretch", config={"displayModeBar": False})

st.markdown("### Delay and capacity")
left, right = st.columns(2)
with left:
    if causes.empty:
        st.info("No delay-cause minutes are available for this selection.")
    else:
        causes["cause_label"] = causes["cause_code"].map(CAUSE_LABELS).fillna(causes["cause_code"])
        cause_chart = px.bar(
            causes,
            x="delay_min",
            y="cause_label",
            orientation="h",
            labels={"delay_min": "Delay minutes", "cause_label": "BTS delay cause"},
            title="Delay minutes by BTS cause",
            color_discrete_sequence=["#38BFD6"],
        )
        cause_chart.update_yaxes(autorange="reversed")
        cause_chart.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
        st.plotly_chart(cause_chart, width="stretch", config={"displayModeBar": False})

with right:
    if routes.empty:
        st.info("No delayed-route data is available for this selection.")
    else:
        route_chart = px.bar(
            routes,
            x="arr_delay_minutes",
            y="route",
            orientation="h",
            labels={"arr_delay_minutes": "Positive arrival-delay minutes", "route": "Route"},
            title="Top 10 routes by arrival-delay minutes",
            color_discrete_sequence=["#2878C8"],
            hover_data={"delayed_arrivals": True, "flights_completed": True},
        )
        route_chart.update_yaxes(autorange="reversed")
        route_chart.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
        st.plotly_chart(route_chart, width="stretch", config={"displayModeBar": False})

plf_chart = px.line(
    monthly,
    x="month_name",
    y="plf",
    markers=True,
    labels={"month_name": "Month", "plf": "Passenger load factor"},
    title="Monthly passenger load factor",
    color_discrete_sequence=["#36B58A"],
)
plf_chart.update_yaxes(tickformat=".0%", title="Passengers / seats")
plf_chart.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
st.plotly_chart(plf_chart, width="stretch", config={"displayModeBar": False})

st.markdown("### Executive insights")
insights: list[str] = []
valid_otp = monthly.dropna(subset=["otp"])
if not valid_otp.empty:
    best_month = valid_otp.loc[valid_otp["otp"].idxmax()]
    insights.append(
        f"Highest monthly OTP was {best_month['month_name']} "
        f"({best_month['otp']:.1%}) based on completed flights."
    )
if not causes.empty:
    top_cause = causes.iloc[0]
    insights.append(
        f"{CAUSE_LABELS.get(top_cause['cause_code'], top_cause['cause_code'])} contributed "
        f"{float(top_cause['delay_min']):,.0f} positive delay minutes, the largest cause total."
    )
if not routes.empty:
    top_route = routes.iloc[0]
    insights.append(
        f"{top_route['route']} had the highest total positive arrival-delay minutes "
        f"({float(top_route['arr_delay_minutes']):,.0f})."
    )
if insights:
    for insight in insights:
        st.markdown(f"- {insight}")
else:
    st.info("There is not enough data to generate insights for this selection.")

st.caption(
    "OTP uses completed flights as its denominator. Delay causes are BTS's five reported groups. "
    "DB1B-derived revenue is an estimate based on a 10% ticket sample; RASK is shown in cents per ASM."
)