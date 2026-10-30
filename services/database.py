"""Environment-based, read-only MySQL access for dashboard queries."""

import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import URL, Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


class DatabaseUnavailableError(RuntimeError):
    """Raised when safe dashboard database access cannot be established."""


def _database_url() -> URL:
    """Build a URL without embedding credentials in source code."""
    username = os.getenv("MYSQL_USER", "").strip()
    password = os.getenv("MYSQL_PASSWORD", "")
    if not username or not password:
        raise DatabaseUnavailableError(
            "Set MYSQL_USER and MYSQL_PASSWORD in the environment or local .env. "
            "Use a dedicated MySQL account with SELECT-only privileges."
        )

    try:
        port = int(os.getenv("MYSQL_PORT", "3306"))
    except ValueError as exc:
        raise DatabaseUnavailableError("MYSQL_PORT must be an integer.") from exc

    return URL.create(
        "mysql+pymysql",
        username=username,
        password=password,
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=port,
        database=os.getenv("MYSQL_DB", "aviation_dw"),
        query={"charset": "utf8mb4"},
    )


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    """Create a pooled engine whose MySQL sessions default to read-only."""
    try:
        return create_engine(
            _database_url(),
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=5,
            max_overflow=5,
            connect_args={
                "connect_timeout": 5,
                "init_command": "SET SESSION TRANSACTION READ ONLY",
            },
        )
    except (SQLAlchemyError, DatabaseUnavailableError) as exc:
        raise DatabaseUnavailableError(str(exc)) from exc


def _require_select(statement: str) -> str:
    """Allow only one non-locking SELECT query from the dashboard."""
    query = statement.strip()
    if query.endswith(";"):
        query = query[:-1].rstrip()
    if not query or re.match(r"(?i)^SELECT\b", query) is None:
        raise ValueError("Dashboard queries must be a single SELECT statement.")
    if ";" in query or any(token in query for token in ("--", "#", "/*", "*/")):
        raise ValueError("Multiple SQL statements are not allowed.")
    unsafe_clauses = re.compile(
        r"(?i)\bINTO\s+(?:OUTFILE|DUMPFILE)\b"
        r"|\bFOR\s+(?:UPDATE|SHARE)\b"
        r"|\bLOCK\s+IN\s+SHARE\s+MODE\b"
    )
    if unsafe_clauses.search(query):
        raise ValueError("Dashboard SELECT queries cannot write or lock database data.")
    return query


@st.cache_data(ttl=300, show_spinner=False)
def query_df(statement: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Execute a parameterized SELECT and return its result as a DataFrame."""
    query = _require_select(statement)
    try:
        with get_engine().connect() as connection:
            return pd.read_sql_query(text(query), connection, params=params or {})
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError(
            "The dashboard could not read the requested data from MySQL. "
            "Check connectivity, permissions, and the configured schema."
        ) from exc


@st.cache_data(ttl=60, show_spinner=False)
def check_connection() -> tuple[str, str]:
    """Return the active database and server version using a read-only query."""
    try:
        with get_engine().connect() as connection:
            row = connection.execute(
                text("SELECT DATABASE() AS database_name, VERSION() AS server_version")
            ).mappings().one()
            return str(row["database_name"]), str(row["server_version"])
    except (SQLAlchemyError, DatabaseUnavailableError) as exc:
        raise DatabaseUnavailableError(str(exc)) from exc