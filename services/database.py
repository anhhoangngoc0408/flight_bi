"""Environment-based, read-only MySQL access for dashboard queries."""

import os
import re
import atexit
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import URL, Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from streamlit.errors import StreamlitSecretNotFoundError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
_temporary_ca_paths: list[Path] = []


def _secrets() -> dict[str, Any]:
    """Return Streamlit secrets when configured; local runs may have none."""
    try:
        return dict(st.secrets)
    except StreamlitSecretNotFoundError:
        return {}


def _database_profile() -> str:
    """Select local or Aiven settings from environment or Streamlit secrets."""
    environment_profile = os.getenv("MYSQL_PROFILE", "").strip().lower()
    secrets = _secrets()
    database_secrets = secrets.get("database", {})
    secret_profile = str(database_secrets.get("profile", "local")).strip().lower()
    profile = environment_profile or secret_profile
    if profile not in {"local", "aiven"}:
        raise DatabaseUnavailableError("MYSQL_PROFILE must be either 'local' or 'aiven'.")
    return profile


def _profile_value(profile: str, key: str, default: str = "") -> str:
    """Read profile-specific environment/secrets without sharing passwords across profiles."""
    environment_key = f"MYSQL_{profile.upper()}_{key.upper()}"
    environment_aliases = {
        "user": f"MYSQL_{profile.upper()}_USERNAME",
    }
    if environment_key in os.environ:
        return os.environ[environment_key].strip()
    alias_environment_key = environment_aliases.get(key)
    if alias_environment_key and alias_environment_key in os.environ:
        return os.environ[alias_environment_key].strip()

    secrets = _secrets()
    mysql_secrets = secrets.get("mysql", {})
    profile_secrets = mysql_secrets.get(profile, {})
    secret_value = profile_secrets.get(key)
    if secret_value is None and key == "user":
        secret_value = profile_secrets.get("username")
    if secret_value is not None:
        return str(secret_value).strip()

    if profile == "local":
        legacy_names = {
            "host": "MYSQL_HOST",
            "port": "MYSQL_PORT",
            "database": "MYSQL_DB",
            "user": "MYSQL_USER",
            "password": "MYSQL_PASSWORD",
            "ssl_ca": "MYSQL_SSL_CA",
            "ssl_ca_pem": "MYSQL_SSL_CA_PEM",
        }
        legacy_name = legacy_names.get(key)
        if legacy_name and legacy_name in os.environ:
            return os.environ[legacy_name].strip()
        local_secrets = mysql_secrets.get("local", {})
        local_value = local_secrets.get(key)
        if local_value is not None:
            return str(local_value).strip()
    return default


def _aiven_ca_path() -> str:
    """Resolve an Aiven CA file or materialize a PEM certificate from secrets."""
    ca_path = _profile_value("aiven", "ssl_ca")
    if ca_path:
        if not Path(ca_path).is_file():
            raise DatabaseUnavailableError("The configured Aiven SSL CA file does not exist.")
        return ca_path

    ca_pem = _profile_value("aiven", "ssl_ca_pem")
    if ca_pem:
        if "-----BEGIN CERTIFICATE-----" not in ca_pem:
            raise DatabaseUnavailableError("MYSQL_AIVEN_SSL_CA_PEM must contain a PEM CA certificate.")
        return _materialize_ca_certificate(ca_pem)

    raise DatabaseUnavailableError(
        "Aiven connections require the provider CA certificate for verified TLS. "
        "Set MYSQL_AIVEN_SSL_CA to its local path or add ssl_ca_pem under [mysql.aiven] in Streamlit secrets."
    )


@st.cache_resource(show_spinner=False)
def _materialize_ca_certificate(certificate_pem: str) -> str:
    """Write a CA certificate once per process so pooled engines reuse its path."""
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".pem", prefix="aerovista-aiven-ca-", delete=False
    ) as certificate_file:
        certificate_file.write(certificate_pem)
        path = Path(certificate_file.name)
    _temporary_ca_paths.append(path)
    return str(path)


@atexit.register
def _remove_temporary_ca_files() -> None:
    """Remove temporary public CA files created from Streamlit secrets on shutdown."""
    for path in _temporary_ca_paths:
        path.unlink(missing_ok=True)


class DatabaseUnavailableError(RuntimeError):
    """Raised when safe dashboard database access cannot be established."""


def _database_url(profile: str | None = None) -> URL:
    """Build a URL from the selected local or cloud profile."""
    selected_profile = profile or _database_profile()
    defaults = {
        "local": {"host": "127.0.0.1", "port": "3306", "database": "aviation_dw", "user": ""},
        "aiven": {
            "host": "mysql-nanh-flight.e.aivencloud.com",
            "port": "26015",
            "database": "defaultdb",
            "user": "avnadmin",
        },
    }[selected_profile]
    username = _profile_value(selected_profile, "user", defaults["user"])
    password = _profile_value(selected_profile, "password")
    if not username or not password:
        raise DatabaseUnavailableError(
            f"Database profile '{selected_profile}' is selected, but its username or password is missing. "
            "Configure the selected profile in local .env or Streamlit Cloud secrets."
        )

    try:
        port = int(_profile_value(selected_profile, "port", defaults["port"]))
    except ValueError as exc:
        raise DatabaseUnavailableError(f"The {selected_profile} MySQL port must be an integer.") from exc

    return URL.create(
        "mysql+pymysql",
        username=username,
        password=password,
        host=_profile_value(selected_profile, "host", defaults["host"]),
        port=port,
        database=_profile_value(selected_profile, "database", defaults["database"]),
        query={"charset": "utf8mb4"},
    )


@st.cache_resource(show_spinner=False)
def _create_engine(database_url: URL, profile: str, ca_path: str | None) -> Engine:
    """Create a pooled engine with read-only sessions and verified Aiven TLS."""
    connect_args: dict[str, Any] = {
        "connect_timeout": 5,
        "init_command": "SET SESSION TRANSACTION READ ONLY",
    }
    if profile == "aiven":
        # Aiven's SSL mode is REQUIRED; the CA and hostname are also verified.
        connect_args.update(
            ssl_ca=ca_path,
            ssl_verify_cert=True,
            ssl_verify_identity=True,
        )
    try:
        return create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=5,
            max_overflow=5,
            connect_args=connect_args,
        )
    except (SQLAlchemyError, DatabaseUnavailableError) as exc:
        raise DatabaseUnavailableError(str(exc)) from exc


def get_engine() -> Engine:
    """Return the cached engine for the currently selected connection profile."""
    profile = _database_profile()
    ca_path = _aiven_ca_path() if profile == "aiven" else None
    return _create_engine(_database_url(profile), profile, ca_path)


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


@st.cache_data(ttl=60, show_spinner=False)
def _read_mart_view_definitions(
    database_url: URL,
    profile: str,
    ca_path: str | None,
) -> dict[str, str]:
    """Read view definitions so placeholder SELECT-1 marts cannot masquerade as real data."""
    try:
        with _create_engine(database_url, profile, ca_path).connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT TABLE_NAME AS table_name, VIEW_DEFINITION AS definition "
                    "FROM information_schema.VIEWS WHERE TABLE_SCHEMA = DATABASE()"
                )
            ).mappings()
            return {
                str(row["table_name"]).lower(): str(row["definition"] or "")
                for row in rows
                if str(row["table_name"]).lower().startswith("mart_")
            }
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError(
            "Could not verify the warehouse mart definitions before querying them."
        ) from exc


def _validate_referenced_marts(
    query: str,
    database_url: URL,
    profile: str,
    ca_path: str | None,
) -> None:
    """Fail closed if a queried mart is missing or is only a SELECT-1 placeholder."""
    referenced_marts = {
        name.lower() for name in re.findall(r"\bmart_[A-Za-z0-9_]+\b", query, flags=re.IGNORECASE)
    }
    if not referenced_marts:
        return

    view_definitions = _read_mart_view_definitions(database_url, profile, ca_path)
    missing = sorted(name for name in referenced_marts if name not in view_definitions)
    placeholders = sorted(
        name for name in referenced_marts
        if name in view_definitions and re.search(r"\bFROM\b", view_definitions[name], re.IGNORECASE) is None
    )
    if missing or placeholders:
        details = []
        if missing:
            details.append(f"missing mart views: {', '.join(missing)}")
        if placeholders:
            details.append(f"placeholder mart views (no source tables): {', '.join(placeholders)}")
        raise DatabaseUnavailableError(
            "The selected MySQL database is reachable, but its analytics marts are not ready "
            f"({'; '.join(details)}). Dashboard metrics are withheld to avoid showing invalid data. "
            "Provision the correct warehouse views using an approved database administration process."
        )


@st.cache_data(ttl=300, show_spinner=False)
def _query_df_cached(
    statement: str,
    params: dict[str, Any],
    profile: str,
    database_url: URL,
    ca_path: str | None,
) -> pd.DataFrame:
    """Run a SELECT with profile included in the cache key."""
    query = _require_select(statement)
    _validate_referenced_marts(query, database_url, profile, ca_path)
    try:
        with _create_engine(database_url, profile, ca_path).connect() as connection:
            return pd.read_sql_query(text(query), connection, params=params)
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError(
            "The dashboard could not read the requested data from MySQL. "
            "Check connectivity, permissions, and the configured schema."
        ) from exc


def query_df(statement: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Execute a parameterized SELECT and return its result as a DataFrame."""
    _require_select(statement)
    profile = _database_profile()
    ca_path = _aiven_ca_path() if profile == "aiven" else None
    return _query_df_cached(statement, params or {}, profile, _database_url(profile), ca_path)


@st.cache_data(ttl=60, show_spinner=False)
def _check_connection_cached(profile: str, database_url: URL, ca_path: str | None) -> tuple[str, str]:
    """Return the active database and server version using a read-only query."""
    try:
        with _create_engine(database_url, profile, ca_path).connect() as connection:
            row = connection.execute(
                text("SELECT DATABASE() AS database_name, VERSION() AS server_version")
            ).mappings().one()
            return str(row["database_name"]), str(row["server_version"])
    except (SQLAlchemyError, DatabaseUnavailableError) as exc:
        raise DatabaseUnavailableError(str(exc)) from exc


def check_connection() -> tuple[str, str]:
    """Check the active profile using a read-only query."""
    profile = _database_profile()
    ca_path = _aiven_ca_path() if profile == "aiven" else None
    return _check_connection_cached(profile, _database_url(profile), ca_path)