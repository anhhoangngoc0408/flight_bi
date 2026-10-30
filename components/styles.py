"""Shared bright enterprise styling for AEROVISTA."""

import streamlit as st


def apply_global_styles() -> None:
    """Apply the shared light visual system to every page."""
    st.markdown(
        """
        <style>
        :root {
            --av-bg: #F6F8FC;
            --av-surface: #FFFFFF;
            --av-blue: #2878C8;
            --av-navy: #18324B;
            --av-muted: #718198;
            --av-cyan: #38BFD6;
            --av-mint: #36B58A;
            --av-amber: #F2AE4A;
            --av-red: #E66B6B;
            --av-border: #E7ECF3;
        }
        .stApp { background: var(--av-bg); color: var(--av-navy); }
        [data-testid="stSidebar"] {
            background: var(--av-surface);
            border-right: 1px solid var(--av-border);
        }
        [data-testid="stSidebar"] > div:first-child { padding-top: 1.1rem; }
        [data-testid="stSidebar"] [class*="st-key-av-nav-"] {
            border: 1px solid transparent;
            border-radius: 12px;
            min-height: 48px;
            margin: 0.12rem 0;
            padding: 0.18rem 0.25rem;
            transition: background-color 140ms ease, border-color 140ms ease;
        }

        .av-active-marker {
            color: var(--av-blue);
            font-size: 0.62rem;
            font-weight: 750;
            letter-spacing: 0.11em;
            margin: -0.15rem 0 0.55rem 3.2rem;
        }
        .block-container { max-width: 1540px; padding-top: 2rem; padding-bottom: 3rem; }
        h1, h2, h3, h4 { color: var(--av-navy); letter-spacing: -0.02em; }
        p, label, [data-testid="stCaptionContainer"] { color: var(--av-muted); }
        [data-testid="stMetric"] {
            background: var(--av-surface);
            border: 1px solid var(--av-border);
            border-radius: 13px;
            min-height: 102px;
            padding: 0.82rem 0.9rem;
            box-shadow: 0 4px 14px rgba(24, 50, 75, 0.045);
            transition: transform 140ms ease, box-shadow 140ms ease;
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 7px 18px rgba(24, 50, 75, 0.07);
        }
        [data-testid="stMetricLabel"] {
            color: var(--av-muted);
            font-size: 0.8rem;
            font-weight: 600;
            line-height: 1.25;
            white-space: normal;
        }
        [data-testid="stMetricValue"] {
            color: var(--av-navy);
            font-size: clamp(1.05rem, 1.35vw, 1.45rem);
            font-weight: 700;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }
        [data-testid="stMetricDelta"] { font-size: 0.76rem; }
        [data-testid="stButton"] button,
        [data-testid="stDownloadButton"] button {
            border-radius: 10px;
            font-weight: 650;
            transition: background-color 140ms ease, border-color 140ms ease, transform 140ms ease;
        }
        [data-testid="stButton"] button[kind="primary"] {
            background: var(--av-blue);
            border-color: var(--av-blue);
            color: white;
        }
        [data-testid="stButton"] button:hover,
        [data-testid="stDownloadButton"] button:hover { transform: translateY(-1px); }
        [data-testid="stButton"] button:disabled,
        [data-testid="stDownloadButton"] button:disabled { opacity: 0.48; cursor: not-allowed; }
        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div { border-radius: 10px; }
        [data-testid="stPlotlyChart"] {
            background: var(--av-surface);
            border: 1px solid var(--av-border);
            border-radius: 14px;
            padding: 0.4rem;
        }
        div[data-testid="stVerticalBlock"] > div[data-testid="stAlert"] { border-radius: 12px; }
        .av-brand { display: flex; align-items: center; gap: 0.65rem; margin: 0 0 0.2rem; }
        .av-brand-mark {
            display: grid; place-items: center; width: 38px; height: 38px;
            border-radius: 12px; background: #EAF4FD; color: var(--av-blue);
            font-size: 0.84rem; font-weight: 800; letter-spacing: 0.02em;
        }
        .av-brand-name { color: var(--av-navy); font-size: 1.06rem; font-weight: 800; letter-spacing: 0.09em; }
        .av-brand-sub { color: var(--av-muted); font-size: 0.72rem; margin-top: 0.08rem; }
        .av-page-kicker { color: var(--av-blue); font-size: 0.74rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }
        .av-page-title { color: var(--av-navy); font-size: clamp(1.7rem, 2.5vw, 2.2rem); font-weight: 750; margin: 0.25rem 0 0.35rem; }
        .av-page-subtitle { color: var(--av-muted); font-size: 0.97rem; margin-bottom: 1.45rem; }
        .av-sidebar-foot { border-top: 1px solid var(--av-border); margin-top: 1.5rem; padding-top: 0.8rem; color: var(--av-muted); font-size: 0.75rem; line-height: 1.6; }
        </style>
        """,
        unsafe_allow_html=True,
    )