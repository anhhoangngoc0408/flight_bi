"""Consistent page title treatment."""

import streamlit as st


def render_header(title: str, subtitle: str, *, section: str = "AEROVISTA ANALYTICS") -> None:
    """Render a compact page heading with shared typography."""
    st.markdown(
      
        f'<div class="av-page-title">{title}</div>'
        f'<div class="av-page-subtitle">{subtitle}</div>',
        unsafe_allow_html=True,
    )