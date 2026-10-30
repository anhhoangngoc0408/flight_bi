"""Read-only analytical queries for dashboard pages."""

import pandas as pd

from services.database import query_df


def get_available_years() -> list[int]:
    """List years present in the carrier-level monthly mart."""
    frame = query_df(
        "SELECT DISTINCT year FROM mart_carrier_month ORDER BY year DESC"
    )
    return [int(year) for year in frame["year"].dropna().tolist()]


def get_executive_summary(year: int) -> pd.DataFrame:
    """Return additive annual totals used to calculate executive KPIs."""
    return query_df(
        """
        SELECT
            SUM(flights_scheduled) AS flights_scheduled,
            SUM(flights_completed) AS flights_completed,
            SUM(flights_cancelled) AS flights_cancelled,
            SUM(flights_diverted) AS flights_diverted,
            SUM(arr_del15_count) AS arr_del15_count,
            SUM(passengers) AS passengers,
            SUM(seats) AS seats,
            SUM(turn_actual_sum_min) AS turn_actual_sum_min,
            SUM(turn_n) AS turn_n
        FROM mart_carrier_month
        WHERE year = :year
        """,
        {"year": year},
    )


def get_monthly_performance(year: int) -> pd.DataFrame:
    """Return monthly totals; rates are recomputed from additive measures."""
    return query_df(
        """
        SELECT
            month,
            month_name,
            SUM(flights_scheduled) AS flights_scheduled,
            SUM(flights_completed) AS flights_completed,
            SUM(arr_del15_count) AS arr_del15_count,
            SUM(passengers) AS passengers,
            SUM(seats) AS seats
        FROM mart_carrier_month
        WHERE year = :year
        GROUP BY month, month_name
        ORDER BY month
        """,
        {"year": year},
    )


def get_delay_cause_totals(year: int) -> pd.DataFrame:
    """Return BTS delay-cause minutes grouped from the monthly cause mart."""
    return query_df(
        """
        SELECT
            cause_code,
            answer_label_vi,
            SUM(delay_min) AS delay_min
        FROM mart_delay_cause_month
        WHERE year = :year
        GROUP BY cause_code, answer_label_vi
        ORDER BY delay_min DESC
        """,
        {"year": year},
    )


def get_top_delayed_routes(year: int, limit: int = 10) -> pd.DataFrame:
    """Rank routes by total positive arrival-delay minutes, not average delay."""
    return query_df(
        """
        SELECT
            CONCAT(origin, '-', dest) AS route,
            SUM(arr_delay_pos_min) AS arr_delay_minutes,
            SUM(arr_del15_count) AS delayed_arrivals,
            SUM(flights_completed) AS flights_completed
        FROM mart_route_month
        WHERE year = :year
        GROUP BY origin, dest
        ORDER BY arr_delay_minutes DESC
        LIMIT :limit
        """,
        {"year": year, "limit": limit},
    )


def get_estimated_rask(year: int) -> pd.DataFrame:
    """Calculate annual RASK in cents using complete, covered quarter rows only."""
    return query_df(
        """
        SELECT
            SUM(revenue_est_usd) AS estimated_revenue_usd,
            SUM(asm) AS asm,
            SUM(revenue_est_usd) / NULLIF(SUM(asm), 0) * 100 AS rask_cents,
            COUNT(*) AS covered_complete_quarters
        FROM mart_carrier_quarter_rask
        WHERE year = :year
          AND source_presence = 't100+db1b'
          AND complete_quarter = 1
        """,
        {"year": year},
    )


def _route_filters(
    year: int,
    month: int | None = None,
    carrier: str | None = None,
    origin: str | None = None,
    dest: str | None = None,
) -> tuple[str, dict[str, object]]:
    """Build WHERE clauses only from fixed warehouse columns and bound values."""
    clauses = ["year = :year"]
    params: dict[str, object] = {"year": year}
    for column, value, key in (
        ("month", month, "month"),
        ("carrier", carrier, "carrier"),
        ("origin", origin, "origin"),
        ("dest", dest, "dest"),
    ):
        if value is not None:
            clauses.append(f"{column} = :{key}")
            params[key] = value
    return " AND ".join(clauses), params


def get_route_filter_values() -> pd.DataFrame:
    """Return carrier and airport choices present in the operational mart."""
    return query_df(
        """
        SELECT DISTINCT carrier, origin, dest
        FROM mart_route_month
        ORDER BY carrier, origin, dest
        """
    )


def get_operations_summary(
    year: int,
    month: int | None = None,
    carrier: str | None = None,
    origin: str | None = None,
    dest: str | None = None,
) -> pd.DataFrame:
    """Aggregate operational measures at the user's selected route scope."""
    where, params = _route_filters(year, month, carrier, origin, dest)
    return query_df(
        f"""
        SELECT
            SUM(flights_scheduled) AS flights_scheduled,
            SUM(flights_completed) AS flights_completed,
            SUM(flights_cancelled) AS flights_cancelled,
            SUM(flights_diverted) AS flights_diverted,
            SUM(arr_del15_count) AS arr_del15_count,
            SUM(arr_delay_pos_min) AS arr_delay_pos_min,
            SUM(passengers) AS passengers,
            SUM(seats) AS seats
        FROM mart_route_month WHERE {where}
        """,
        params,
    )


def get_operations_monthly(
    year: int,
    carrier: str | None = None,
    origin: str | None = None,
    dest: str | None = None,
) -> pd.DataFrame:
    """Return additive monthly measures for trend calculations."""
    where, params = _route_filters(year, carrier=carrier, origin=origin, dest=dest)
    return query_df(
        f"""
        SELECT month, SUM(flights_completed) AS flights_completed,
               SUM(arr_del15_count) AS arr_del15_count,
               SUM(flights_scheduled) AS flights_scheduled,
               SUM(flights_cancelled) AS flights_cancelled,
               SUM(passengers) AS passengers, SUM(seats) AS seats
        FROM mart_route_month WHERE {where}
        GROUP BY month ORDER BY month
        """,
        params,
    )


def get_operations_causes(
    year: int,
    month: int | None = None,
    carrier: str | None = None,
    origin: str | None = None,
    dest: str | None = None,
) -> pd.DataFrame:
    """Unpivot BTS's five delay-cause minute measures at the selected route grain."""
    where, params = _route_filters(year, month, carrier, origin, dest)
    return query_df(
        f"""
        SELECT cause_code, delay_min
        FROM (
            SELECT 'Carrier' AS cause_code, SUM(delay_carrier_min) AS delay_min
            FROM mart_route_month WHERE {where}
            UNION ALL
            SELECT 'Weather', SUM(delay_weather_min)
            FROM mart_route_month WHERE {where}
            UNION ALL
            SELECT 'NAS', SUM(delay_nas_min)
            FROM mart_route_month WHERE {where}
            UNION ALL
            SELECT 'Security', SUM(delay_security_min)
            FROM mart_route_month WHERE {where}
            UNION ALL
            SELECT 'LateAircraft', SUM(delay_late_aircraft_min)
            FROM mart_route_month WHERE {where}
        ) causes
        ORDER BY delay_min DESC
        """,
        params,
    )


def get_operations_routes(
    year: int,
    month: int | None = None,
    carrier: str | None = None,
    origin: str | None = None,
    dest: str | None = None,
    limit: int = 1000,
) -> pd.DataFrame:
    """Aggregate route KPI measures; ratios are returned as additive inputs."""
    where, params = _route_filters(year, month, carrier, origin, dest)
    params["limit"] = limit
    return query_df(
        f"""
        SELECT origin, dest, SUM(flights_scheduled) AS flights_scheduled,
               SUM(flights_completed) AS flights_completed,
               SUM(flights_cancelled) AS flights_cancelled,
               SUM(arr_del15_count) AS arr_del15_count,
               SUM(arr_delay_pos_min) AS arr_delay_pos_min
        FROM mart_route_month WHERE {where}
        GROUP BY origin, dest
        ORDER BY arr_delay_pos_min DESC
        LIMIT :limit
        """,
        params,
    )


def get_operations_dayparts(
    year: int, month: int | None = None, carrier: str | None = None
) -> pd.DataFrame:
    """Return weighted daypart turnaround/departure-delay measures."""
    clauses = ["year = :year"]
    params: dict[str, object] = {"year": year}
    if month is not None:
        clauses.append("month = :month")
        params["month"] = month
    if carrier is not None:
        clauses.append("carrier = :carrier")
        params["carrier"] = carrier
    return query_df(
        f"""
        SELECT daypart_name, SUM(turn_n) AS turn_n,
               SUM(avg_dep_delay_min * turn_n) / NULLIF(SUM(turn_n), 0) AS avg_dep_delay_min,
               SUM(turn_after_late_inbound_rate * turn_n) / NULLIF(SUM(turn_n), 0)
                   AS turn_after_late_inbound_rate
        FROM mart_turnaround_daypart_month
        WHERE {' AND '.join(clauses)}
        GROUP BY daypart_name, sort_order ORDER BY sort_order
        """,
        params,
    )


def get_turnaround_summary(year: int, month: int | None = None) -> pd.DataFrame:
    """Return additive turnaround sums at airport × daypart × month grain."""
    clauses = ["m.year = :year"]
    params: dict[str, object] = {"year": year}
    if month is not None:
        clauses.append("m.month = :month")
        params["month"] = month
    return query_df(
        f"""
        SELECT SUM(f.turn_n) AS turn_n,
               SUM(f.turn_sched_sum_min) AS turn_sched_sum_min,
               SUM(f.turn_actual_sum_min) AS turn_actual_sum_min,
               SUM(f.turn_excess_sum_min) AS turn_excess_sum_min,
               SUM(f.turn_over_sched_n) AS turn_over_sched_n,
               SUM(f.turn_after_late_inbound_n) AS turn_after_late_inbound_n,
               SUM(f.dep_delay_sum_min) AS dep_delay_sum_min
        FROM fact_turnaround_airport_daypart_month f
        JOIN dim_month m ON m.month_key = f.month_key
        WHERE {' AND '.join(clauses)}
        """,
        params,
    )


def get_turnaround_monthly(year: int) -> pd.DataFrame:
    """Return weighted monthly turnaround averages and counts."""
    return query_df(
        """
        SELECT m.month,
               SUM(f.turn_sched_sum_min) / NULLIF(SUM(f.turn_n), 0) AS avg_turn_sched_min,
               SUM(f.turn_actual_sum_min) / NULLIF(SUM(f.turn_n), 0) AS avg_turn_actual_min,
               SUM(f.turn_n) AS turn_n,
               SUM(f.turn_excess_sum_min) AS turn_excess_sum_min
        FROM fact_turnaround_airport_daypart_month f
        JOIN dim_month m ON m.month_key = f.month_key
        WHERE m.year = :year
        GROUP BY m.month ORDER BY m.month
        """,
        {"year": year},
    )


def get_turnaround_airports(year: int, month: int | None = None, limit: int = 30) -> pd.DataFrame:
    """Return airport-level turnaround aggregate metrics."""
    clauses = ["year = :year"]
    params: dict[str, object] = {"year": year, "limit": limit}
    if month is not None:
        clauses.append("month = :month")
        params["month"] = month
    return query_df(
        f"""
        SELECT airport_code, city, SUM(turn_n) AS turn_n,
               SUM(avg_turn_sched_min * turn_n) / NULLIF(SUM(turn_n), 0) AS avg_turn_sched_min,
               SUM(avg_turn_actual_min * turn_n) / NULLIF(SUM(turn_n), 0) AS avg_turn_actual_min,
               SUM(turn_excess_sum_min) AS turn_excess_sum_min,
               SUM(turn_over_sched_rate * turn_n) / NULLIF(SUM(turn_n), 0) AS turn_over_sched_rate,
               SUM(turn_after_late_inbound_n) AS turn_after_late_inbound_n
        FROM mart_turnaround_airport_month
        WHERE {' AND '.join(clauses)}
        GROUP BY airport_code, city
        ORDER BY turn_excess_sum_min DESC LIMIT :limit
        """,
        params,
    )


def get_turnaround_dayparts(year: int, month: int | None = None) -> pd.DataFrame:
    """Return weighted daypart turnaround averages."""
    clauses = ["year = :year"]
    params: dict[str, object] = {"year": year}
    if month is not None:
        clauses.append("month = :month")
        params["month"] = month
    return query_df(
        f"""
        SELECT daypart_name, sort_order, SUM(turn_n) AS turn_n,
               SUM(avg_turn_sched_min * turn_n) / NULLIF(SUM(turn_n), 0) AS avg_turn_sched_min,
               SUM(avg_turn_actual_min * turn_n) / NULLIF(SUM(turn_n), 0) AS avg_turn_actual_min,
               SUM(turn_after_late_inbound_rate * turn_n) / NULLIF(SUM(turn_n), 0)
                   AS turn_after_late_inbound_rate,
               SUM(avg_dep_delay_min * turn_n) / NULLIF(SUM(turn_n), 0) AS avg_dep_delay_min
        FROM mart_turnaround_daypart_month
        WHERE {' AND '.join(clauses)}
        GROUP BY daypart_name, sort_order ORDER BY sort_order
        """,
        params,
    )


def get_revenue_quarters(year: int) -> pd.DataFrame:
    """Return quarterly carrier metrics and include coverage fields from the mart."""
    return query_df(
        """
         SELECT year, quarter, seats, passengers, asm, rpm, revenue_est_usd,
             seg_revenue_sample, pax_miles_sample, source_presence,
             complete_quarter, load_factor, rask_cents, yield_cents,
             months_in_t100, pax_est
        FROM mart_carrier_quarter_rask
        WHERE year = :year ORDER BY quarter
        """,
        {"year": year},
    )


def get_revenue_routes(year: int, quarter: int | None = None, limit: int = 2000) -> pd.DataFrame:
    """Return route-quarter revenue and capacity at their shared route-quarter grain."""
    clauses = ["year = :year"]
    params: dict[str, object] = {"year": year, "limit": limit}
    if quarter is not None:
        clauses.append("quarter = :quarter")
        params["quarter"] = quarter
    return query_df(
        f"""
         SELECT origin, dest, quarter, seats, passengers, asm, rpm, revenue_est_usd,
             seg_revenue_sample, pax_miles_sample, source_presence,
             complete_quarter, load_factor, rask_cents, yield_cents
        FROM mart_route_quarter_rask
        WHERE {' AND '.join(clauses)}
        ORDER BY revenue_est_usd DESC LIMIT :limit
        """,
        params,
    )


def get_fare_class_mix(year: int) -> pd.DataFrame:
    """Aggregate DB1B sampled records and sampled revenue by fare class."""
    return query_df(
        """
        SELECT q.year, q.quarter, f.fare_class,
               SUM(f.pax_sample) AS pax_sample,
               SUM(f.seg_revenue_sample) AS revenue_sample_usd
        FROM fact_fare_class_quarter f
        JOIN dim_quarter q ON q.quarter_key = f.quarter_key
        WHERE q.year = :year
        GROUP BY q.year, q.quarter, f.fare_class
        ORDER BY q.quarter, f.fare_class
        """,
        {"year": year},
    )


def get_olap_carrier_routes(year: int) -> pd.DataFrame:
    """Return route drill-down rows at month × carrier × route grain."""
    return query_df(
        """
        SELECT origin, dest, SUM(flights_scheduled) AS flights_scheduled,
               SUM(flights_completed) AS flights_completed,
               SUM(arr_del15_count) AS arr_del15_count,
               SUM(arr_delay_pos_min) AS arr_delay_pos_min,
               SUM(passengers) AS passengers, SUM(seats) AS seats,
               SUM(turn_actual_sum_min) AS turn_actual_sum_min, SUM(turn_n) AS turn_n
        FROM mart_route_month WHERE year = :year
        GROUP BY origin, dest ORDER BY flights_scheduled DESC
        """,
        {"year": year},
    )


def get_data_quality_runs(limit: int = 20) -> pd.DataFrame:
    """Return recent ETL runs when the warehouse has its run-control tables."""
    return query_df(
        "SELECT run_id, started_at, finished_at, status, notes "
        "FROM etl_run ORDER BY started_at DESC LIMIT :limit",
        {"limit": limit},
    )


def get_data_quality_checks(limit: int = 500) -> pd.DataFrame:
    """Return recent DQ results for read-only inspection and CSV export."""
    return query_df(
        """
        SELECT check_id, run_id, check_group, check_name, status, metric_value,
               detail, checked_at
        FROM dq_check ORDER BY checked_at DESC, check_id DESC LIMIT :limit
        """,
        {"limit": limit},
    )


def get_etl_load_log(limit: int = 500) -> pd.DataFrame:
    """Return recent ETL table-load records."""
    return query_df(
        """
        SELECT log_id, run_id, target_table, phase, rows_read, rows_inserted,
               rows_rejected, duration_sec, loaded_at
        FROM etl_load_log ORDER BY loaded_at DESC, log_id DESC LIMIT :limit
        """,
        {"limit": limit},
    )


def get_warehouse_row_counts() -> pd.DataFrame:
    """Count rows from a fixed allowlist of dimensions, facts, and marts."""
    objects = (
        "dim_date", "dim_month", "dim_quarter", "dim_carrier", "dim_airport",
        "dim_route", "dim_aircraft", "dim_delay_cause", "dim_cancel_reason",
        "fact_ontime_route_month", "fact_capacity_route_month",
        "fact_turnaround_airport_daypart_month", "fact_fare_segment_quarter",
        "fact_fare_market_quarter", "fact_fare_class_quarter", "mart_carrier_month",
        "mart_route_month", "mart_carrier_quarter_rask", "mart_route_quarter_rask",
        "mart_delay_cause_month", "mart_turnaround_airport_month",
        "mart_turnaround_daypart_month", "mart_fare_market_quarter",
    )
    union = " UNION ALL ".join(
        f"SELECT '{name}' AS object_name, COUNT(*) AS row_count FROM `{name}`"
        for name in objects
    )
    return query_df(f"SELECT object_name, row_count FROM ({union}) counts ORDER BY object_name")


def get_performance_explorer(
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
    dimension: str,
    carriers: list[str],
    airports: list[str],
) -> pd.DataFrame:
    """Aggregate actual warehouse measures for the interactive performance explorer."""
    dimension_columns = {
        "Route": "CONCAT(origin, '-', dest)",
        "Origin airport": "origin",
        "Destination airport": "dest",
        "Carrier": "carrier",
    }
    if dimension not in dimension_columns:
        raise ValueError("Unsupported performance dimension.")

    start_period = start_year * 100 + start_month
    end_period = end_year * 100 + end_month
    clauses = ["year * 100 + month BETWEEN :start_period AND :end_period"]
    params: dict[str, object] = {
        "start_period": start_period,
        "end_period": end_period,
    }
    if carriers:
        placeholders = []
        for index, value in enumerate(carriers):
            key = f"carrier_{index}"
            placeholders.append(f":{key}")
            params[key] = value
        clauses.append(f"carrier IN ({', '.join(placeholders)})")
    if airports:
        placeholders = []
        for index, value in enumerate(airports):
            key = f"airport_{index}"
            placeholders.append(f":{key}")
            params[key] = value
        airport_list = ", ".join(placeholders)
        clauses.append(f"(origin IN ({airport_list}) OR dest IN ({airport_list}))")

    dimension_expression = dimension_columns[dimension]
    return query_df(
        f"""
        SELECT {dimension_expression} AS dimension,
               SUM(flights_scheduled) AS flights_scheduled,
               SUM(flights_completed) AS flights_completed,
               SUM(arr_del15_count) AS arr_del15_count,
               SUM(arr_delay_pos_min) AS arr_delay_pos_min
        FROM mart_route_month
        WHERE {' AND '.join(clauses)}
        GROUP BY dimension
        ORDER BY arr_delay_pos_min DESC
        LIMIT 500
        """,
        params,
    )
