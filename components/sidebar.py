"""Custom image-based product navigation and database status."""

from collections.abc import Sequence
from pathlib import Path

import streamlit as st

from services.database import DatabaseUnavailableError, check_connection

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NAV_ASSETS = {
    "Overview": "overview.png",
    "Flight Operations": "flight.png",
    "Turnaround Optimization": "turn-down.png",
    "Revenue & Capacity": "revenue.png",
    "OLAP Explorer": "explorer.png",
    "Reports & Data Quality": "report.png",
}


def render_sidebar(pages: Sequence[object], current_page: object) -> None:
    """Render the brand, multipage navigation links, and connection status."""
    with st.sidebar:
        st.markdown(
            '<div class="av-brand"><div class="av-brand-mark">AV</div>'
            '<div><div class="av-brand-name">AEROVISTA</div>'
            '<div class="av-brand-sub">Aviation Intelligence</div></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(" ")
        st.caption("DECISION SUPPORT SYSTEM")
        for page in pages:
            slug = page.title.lower().replace(" & ", "-").replace(" ", "-")
            active = page.title == current_page.title
            active = page.title == current_page.title
            nav_key = f"av-nav-{slug}-active" if active else f"av-nav-{slug}"
            with st.container(key=nav_key):
                icon_column, link_column = st.columns([0.24, 0.76], vertical_alignment="center")
                with icon_column:
                    icon_file = NAV_ASSETS.get(page.title)
                    if icon_file:
                        st.image(PROJECT_ROOT / "assets" / icon_file, width=34)
                with link_column:
                    st.page_link(page, label=page.title, width="stretch")
            # if active:
            #     st.markdown('<div class="av-active-marker">CURRENT PAGE</div>', unsafe_allow_html=True)

        try:
            database, version = check_connection()
            st.success(f"Connected · {database}", icon="🟢")
            st.caption(f"MySQL {version}")
        except DatabaseUnavailableError as exc:
            st.warning("Database unavailable", icon="⚠️")
            st.caption(str(exc))
        st.caption("Data scope · WN · 2024")