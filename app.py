"""AEROVISTA Streamlit application entry point."""

import streamlit as st

from components.sidebar import render_sidebar
from components.styles import apply_global_styles

st.set_page_config(
    page_title="AEROVISTA | Aviation Intelligence",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()

pages = [
    st.Page(
        "pages/1_Executive_Overview.py",
        title="Overview",
        default=True,
    ),
    st.Page("pages/2_Flight_Operations.py", title="Flight Operations"),
    st.Page(
        "pages/3_Turnaround_Optimization.py",
        title="Turnaround Optimization",
    ),
    st.Page("pages/4_Revenue_Capacity.py", title="Revenue & Capacity"),
    st.Page("pages/5_OLAP_Explorer.py", title="OLAP Explorer"),
    st.Page("pages/6_Data_Quality.py", title="Reports & Data Quality"),
]

page = st.navigation(pages, position="hidden")
render_sidebar(pages, page)
page.run()