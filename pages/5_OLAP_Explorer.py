import pandas as pd
import streamlit as st

from components.header import render_header
from services.analytics import get_available_years, get_olap_carrier_routes
from services.database import DatabaseUnavailableError

render_header(
    "OLAP Explorer",
    "Self-service drill-down from carrier summary to route aggregates supported by the warehouse grain.",
)

try:
    years = get_available_years()
except DatabaseUnavailableError as exc:
    st.error("Could not query the warehouse.")
    st.caption(str(exc))
    st.stop()

if not years:
    st.info("No carrier-year data is available.")
    st.stop()

year = st.selectbox("Analysis year", years, key="olap_year")
try:
    routes = get_olap_carrier_routes(year)
except DatabaseUnavailableError as exc:
    st.error("Could not read the route mart.")
    st.caption(str(exc))
    st.stop()

if routes.empty:
    st.info("No route aggregates are available for this selection.")
    st.stop()

routes["otp"] = 1 - routes["arr_del15_count"] / routes["flights_completed"].replace(0, pd.NA)
routes["plf"] = routes["passengers"] / routes["seats"].replace(0, pd.NA)
routes["avg_turnaround"] = routes["turn_actual_sum_min"] / routes["turn_n"].replace(0, pd.NA)
routes["route"] = routes["origin"] + "–" + routes["dest"]

carrier_flights = routes["flights_scheduled"].sum()
carrier_completed = routes["flights_completed"].sum()
carrier_delayed = routes["arr_del15_count"].sum()
carrier_seats = routes["seats"].sum()
carrier_passengers = routes["passengers"].sum()
carrier_turn_n = routes["turn_n"].sum()
carrier_turn_minutes = routes["turn_actual_sum_min"].sum()
carrier_otp = 1 - carrier_delayed / carrier_completed if carrier_completed else None
carrier_plf = carrier_passengers / carrier_seats if carrier_seats else None
carrier_turn = carrier_turn_minutes / carrier_turn_n if carrier_turn_n else None

st.markdown("**Breadcrumb:** Carrier")
kpis = st.columns(4)
kpis[0].metric("Carrier", "WN")
kpis[1].metric("Scheduled flights", f"{carrier_flights:,.0f}")
kpis[2].metric("OTP", "N/A" if carrier_otp is None else f"{carrier_otp:.1%}")
kpis[3].metric("PLF", "N/A" if carrier_plf is None else f"{carrier_plf:.1%}")
st.caption(f"Carrier turnaround: {'N/A' if carrier_turn is None else f'{carrier_turn:.1f} min'} · {len(routes):,} route rows aggregated for {year}.")

if "olap_selected_route" not in st.session_state:
    st.session_state.olap_selected_route = None

if st.session_state.olap_selected_route is None:
    st.markdown("### Route level")
    search = st.text_input("Search route or airport", placeholder="For example: LAS or LAS–SAN")
    visible = routes.copy()
    if search.strip():
        query = search.strip().upper()
        visible = visible.loc[
            visible["route"].str.contains(query, regex=False)
            | visible["origin"].str.contains(query, regex=False)
            | visible["dest"].str.contains(query, regex=False)
        ]
    st.dataframe(
        visible[["route", "flights_scheduled", "flights_completed", "otp", "arr_delay_pos_min", "plf", "avg_turnaround"]]
        .rename(columns={
            "route": "Route", "flights_scheduled": "Scheduled flights", "flights_completed": "Completed flights",
            "otp": "OTP", "arr_delay_pos_min": "Positive arrival-delay minutes", "plf": "PLF",
            "avg_turnaround": "Avg turnaround (min)",
        }),
        width="stretch", hide_index=True,
        column_config={
            "OTP": st.column_config.NumberColumn(format="%.1f%%"),
            "PLF": st.column_config.NumberColumn(format="%.1f%%"),
            "Avg turnaround (min)": st.column_config.NumberColumn(format="%.1f"),
            "Positive arrival-delay minutes": st.column_config.NumberColumn(format="%,.0f"),
        },
    )
    options = visible["route"].tolist()
    if options:
        selection = st.selectbox("Select route to drill down", options, key="olap_route_select")
        if st.button("Open route details", type="primary"):
            st.session_state.olap_selected_route = selection
            st.rerun()
else:
    selected = routes.loc[routes["route"] == st.session_state.olap_selected_route]
    if selected.empty:
        st.session_state.olap_selected_route = None
        st.rerun()
    route = selected.iloc[0]
    st.markdown(f"**Breadcrumb:** Carrier › Route · {route['route']}")
    if st.button("← Back to carrier routes"):
        st.session_state.olap_selected_route = None
        st.rerun()
    details = st.columns(4)
    details[0].metric("Route", str(route["route"]))
    details[1].metric("Scheduled flights", f"{float(route['flights_scheduled']):,.0f}")
    details[2].metric("OTP", "N/A" if pd.isna(route["otp"]) else f"{float(route['otp']):.1%}")
    details[3].metric("Average positive arrival delay", "N/A" if not float(route["flights_completed"] or 0) else f"{float(route['arr_delay_pos_min']) / float(route['flights_completed']):.1f} min")
    st.dataframe(
        selected[["origin", "dest", "flights_scheduled", "flights_completed", "arr_del15_count", "arr_delay_pos_min", "passengers", "seats", "turn_actual_sum_min", "turn_n"]]
        .rename(columns={"origin": "Origin", "dest": "Destination", "flights_scheduled": "Scheduled flights", "flights_completed": "Completed flights", "arr_del15_count": "Arrivals delayed 15+", "arr_delay_pos_min": "Positive arrival-delay minutes", "passengers": "Passengers", "seats": "Seats", "turn_actual_sum_min": "Turnaround total minutes", "turn_n": "Valid turnaround events"}),
        width="stretch", hide_index=True,
    )
    st.info(
        "The warehouse contains monthly route aggregates, not individual flights. "
        "Flight date, flight number, scheduled/actual timestamps, and tail number are unavailable at this level."
    )

st.caption("PLF and OTP are calculated from summed measures at the displayed grain. RASK and yield are intentionally not shown here because they are only valid at quarter-route grain with explicit source coverage.")