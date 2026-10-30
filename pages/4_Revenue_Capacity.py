import pandas as pd
import plotly.express as px
import streamlit as st

from components.header import render_header
from services.analytics import (
    get_available_years,
    get_fare_class_mix,
    get_revenue_quarters,
    get_revenue_routes,
)
from services.database import DatabaseUnavailableError

render_header(
    "Revenue & Capacity",
    "Review T-100 capacity and DB1B-derived revenue estimates with quarter and route coverage visible.",
)

try:
    years = get_available_years()
except DatabaseUnavailableError as exc:
    st.error("Could not query the warehouse.")
    st.caption(str(exc))
    st.stop()

if not years:
    st.info("No data years are available.")
    st.stop()

year = st.selectbox("Year", years, key="revenue_year")
try:
    quarters = get_revenue_quarters(year)
    routes = get_revenue_routes(year)
    fare_classes = get_fare_class_mix(year)
except DatabaseUnavailableError as exc:
    st.error("Could not read the revenue and capacity marts.")
    st.caption(str(exc))
    st.stop()

if quarters.empty:
    st.info("No quarterly carrier data is available for this year.")
    st.stop()

covered = quarters.loc[
    (quarters["source_presence"] == "t100+db1b")
    & (quarters["complete_quarter"] == 1)
].copy()
if covered.empty:
    st.warning("No quarter has complete T-100 and DB1B coverage. RASK and estimated revenue are shown as N/A.")
    total_revenue = total_asm = total_rpm = None
    rask = yield_value = None
else:
    total_revenue = covered["revenue_est_usd"].sum(min_count=1)
    total_asm = covered["asm"].sum(min_count=1)
    total_rpm = covered["rpm"].sum(min_count=1)
    rask = total_revenue / total_asm * 100 if total_revenue is not None and total_asm else None
    sample_miles = covered["pax_miles_sample"].sum(min_count=1)
    sample_revenue = covered["seg_revenue_sample"].sum(min_count=1)
    yield_value = (
        sample_revenue / sample_miles * 100
        if pd.notna(sample_revenue) and pd.notna(sample_miles) and sample_miles
        else None
    )
    if len(covered) < 4:
        st.warning(f"Only {len(covered)} of 4 quarters have complete T-100 (3 months) and DB1B coverage. Annual KPIs include only these quarters.")

annual_passengers = covered["passengers"].sum(min_count=1) if not covered.empty else None
annual_seats = covered["seats"].sum(min_count=1) if not covered.empty else None
plf = annual_passengers / annual_seats if annual_passengers is not None and annual_seats else None
annual_values = [
    ("Passenger load factor", plf, "{:.1%}"),
    ("ASM", total_asm, "{:,.0f}"),
    ("RPM", total_rpm, "{:,.0f}"),
    ("Estimated passenger revenue", total_revenue, "${:,.0f}"),
    ("RASK", rask, "{:.2f} ¢/ASM"),
    ("Yield", yield_value, "{:.2f} ¢/RPM"),
]
kpis = st.columns(3)
for index, (label, value, fmt) in enumerate(annual_values):
    text = "N/A" if value is None or pd.isna(value) else fmt.format(float(value))
    kpis[index % 3].metric(label, text)

st.caption("RASK uses estimated DB1B segment revenue divided by T-100 ASM. Yield uses DB1B sample segment revenue divided by passenger-miles; both are shown in cents.")

st.markdown("### Quarterly performance")
plot_quarters = quarters.copy()
plot_quarters["quarter_label"] = plot_quarters["quarter"].map(lambda value: f"Q{int(value)}")
revenue_chart_data = plot_quarters.loc[
    (plot_quarters["source_presence"] == "t100+db1b")
    & (plot_quarters["complete_quarter"] == 1)
].dropna(subset=["revenue_est_usd"])
if revenue_chart_data.empty:
    st.info("Quarterly estimated revenue is unavailable without complete T-100 and DB1B coverage.")
else:
    revenue_figure = px.bar(
        revenue_chart_data,
        x="quarter_label",
        y="revenue_est_usd",
        title="Estimated passenger revenue by quarter",
        labels={"quarter_label": "Quarter", "revenue_est_usd": "Estimated revenue (USD)"},
        color_discrete_sequence=["#2878C8"],
    )
    revenue_figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
    st.plotly_chart(revenue_figure, width="stretch", config={"displayModeBar": False})

left, right = st.columns(2)
with left:
    chart_data = plot_quarters.dropna(subset=["load_factor"])
    if chart_data.empty:
        st.info("PLF is unavailable because T-100 data is missing.")
    else:
        figure = px.line(
            chart_data, x="quarter_label", y="load_factor", markers=True,
            title="Quarterly passenger load factor",
            labels={"quarter_label": "Quarter", "load_factor": "Passengers / seats"},
            color_discrete_sequence=["#36B58A"],
        )
        figure.update_yaxes(tickformat=".0%")
        figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
        st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
with right:
    chart_data = plot_quarters.dropna(subset=["rask_cents", "yield_cents"])
    if chart_data.empty:
        st.info("RASK and yield are unavailable without qualifying source coverage.")
    else:
        figure = px.line(
            chart_data, x="quarter_label", y=["rask_cents", "yield_cents"], markers=True,
            title="RASK vs yield (cents)",
            labels={"quarter_label": "Quarter", "value": "Cents", "variable": "Metric"},
            color_discrete_map={"rask_cents": "#2878C8", "yield_cents": "#38BFD6"},
        )
        figure.for_each_trace(lambda trace: trace.update(name={"rask_cents": "RASK (¢/ASM)", "yield_cents": "Yield (¢/RPM)"}.get(trace.name, trace.name)))
        figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
        st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

with st.expander("Quarter-level data and coverage", expanded=False):
    st.dataframe(
        plot_quarters[["quarter_label", "source_presence", "months_in_t100", "complete_quarter", "passengers", "seats", "asm", "rpm", "revenue_est_usd", "load_factor", "rask_cents", "yield_cents"]],
        width="stretch", hide_index=True,
    )

st.markdown("### Route performance")
if routes.empty:
    st.info("No route-quarter records are available.")
else:
    quarter_options = ["All"] + sorted(routes["quarter"].dropna().astype(int).unique().tolist())
    quarter_choice = st.selectbox("Route quarter", quarter_options, key="revenue_quarter")
    if quarter_choice != "All":
        routes = routes.loc[routes["quarter"] == int(quarter_choice)]
    routes["route"] = routes["origin"] + "–" + routes["dest"]
    complete_routes = routes.loc[
        (routes["source_presence"] == "t100+db1b")
        & (routes["complete_quarter"] == 1)
    ].dropna(subset=["rask_cents", "revenue_est_usd"])
    if complete_routes.empty:
        st.warning("No route has both three months of T-100 data and DB1B coverage in the selected quarter.")
    else:
        route_tabs = st.tabs(["Revenue contribution", "Top / bottom RASK", "PLF by route"])
        with route_tabs[0]:
            top_revenue = complete_routes.nlargest(15, "revenue_est_usd").sort_values("revenue_est_usd")
            figure = px.bar(
                top_revenue, x="revenue_est_usd", y="route", orientation="h",
                title="Top routes by estimated passenger revenue",
                labels={"revenue_est_usd": "Estimated revenue (USD)", "route": "Route"},
                color_discrete_sequence=["#2878C8"],
            )
            figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
            st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
        with route_tabs[1]:
            best = complete_routes.nlargest(10, "rask_cents").copy()
            best["performance"] = "Top RASK"
            worst = complete_routes.nsmallest(10, "rask_cents").copy()
            worst["performance"] = "Bottom RASK"
            comparison = pd.concat([best, worst]).drop_duplicates(subset=["route"])
            figure = px.bar(
                comparison.sort_values("rask_cents"), x="rask_cents", y="route", color="performance",
                orientation="h", title="Highest and lowest route RASK",
                labels={"rask_cents": "RASK (¢/ASM)", "route": "Route"},
                color_discrete_map={"Top RASK": "#36B58A", "Bottom RASK": "#E66B6B"},
            )
            figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
            st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
        with route_tabs[2]:
            load_data = complete_routes.dropna(subset=["load_factor"])
            figure = px.bar(
                load_data.nlargest(20, "passengers").sort_values("load_factor"),
                x="load_factor", y="route", orientation="h",
                title="PLF for top passenger-volume routes",
                labels={"load_factor": "Passengers / seats", "route": "Route"},
                color_discrete_sequence=["#36B58A"],
            )
            figure.update_xaxes(tickformat=".0%")
            figure.update_layout(template="plotly_white", margin=dict(l=12, r=12, t=55, b=12))
            st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
        st.dataframe(
            complete_routes[["route", "quarter", "passengers", "seats", "revenue_est_usd", "load_factor", "rask_cents", "yield_cents"]]
            .rename(columns={"route": "Route", "quarter": "Quarter", "passengers": "Passengers", "seats": "Seats", "revenue_est_usd": "Estimated revenue (USD)", "load_factor": "PLF", "rask_cents": "RASK (¢/ASM)", "yield_cents": "Yield (¢/RPM)"}),
            width="stretch", hide_index=True,
        )

st.markdown("### DB1B fare-class distribution")
if fare_classes.empty:
    st.info("DB1B fare-class data is unavailable for the selected year.")
else:
    fare_classes["quarter_label"] = fare_classes["quarter"].map(lambda value: f"Q{int(value)}")
    figure = px.bar(
        fare_classes, x="quarter_label", y="pax_sample", color="fare_class",
        title="DB1B sampled passengers by quarter and fare class",
        labels={"quarter_label": "Quarter", "pax_sample": "Passengers in sample", "fare_class": "Fare class"},
        color_discrete_sequence=["#2878C8", "#38BFD6", "#36B58A", "#F2AE4A"],
    )
    figure.update_layout(template="plotly_white", barmode="stack", margin=dict(l=12, r=12, t=55, b=12))
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

st.warning(
    "DB1B is a 10% ticket sample and reported revenue is an ETL estimate, not the carrier's actual total revenue. "
    "Only matching quarter/route coverage is used for RASK. DB1B does not contain ticket purchase dates, so no advance-purchase analysis is shown."
)