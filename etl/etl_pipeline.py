# -*- coding: utf-8 -*-
"""
ETL PIPELINE – Đề tài 10 · Nhiệm vụ 2: Data Warehouse & ETL
================================================================
Nạp dữ liệu hàng không (BTS On-Time · T-100 · DB1B – hãng WN, năm 2024)
vào MySQL Data Warehouse `aviation_dw` (star schema).

Luồng: EXTRACT (CSV) -> TRANSFORM (sinh khóa, chuẩn kiểu) -> LOAD (dims -> facts)
      -> CHECK (verify_consistency.py: đối chiếu tổng measures & KPI mart)

Cách chạy (từ thư mục gốc dự án):
    python etl/etl_pipeline.py --init      # (re)tạo schema + nạp + kiểm tra
    python etl/etl_pipeline.py             # nạp lại (full refresh) + kiểm tra
    python etl/etl_pipeline.py --no-checks # chỉ nạp, bỏ bước kiểm tra

Toàn bộ pipeline là FULL REFRESH: truncate mọi bảng dim/fact rồi nạp lại
(kho dữ liệu nhỏ ~120k dòng, chạy lại mất < 1 phút).
"""
import argparse
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd
import pymysql
from sqlalchemy import create_engine, text

import flight_bi.config.config as cfg


# =========================================================================
# Tiện ích
# =========================================================================
def to_bool_int(s: pd.Series) -> pd.Series:
    """Chuỗi 'True'/'False'/bool -> 1/0."""
    if s.dtype == bool:
        return s.astype(int)
    return s.astype(str).str.strip().str.lower().isin(["true", "1"]).astype(int)


def read_source(name: str) -> pd.DataFrame:
    """Đọc CSV nguồn theo ánh xạ trong config.SOURCE_FILES."""
    path = cfg.SOURCE_DIR / cfg.SOURCE_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"Thiếu file nguồn: {path}")
    return pd.read_csv(path)


def truncate_all(engine):
    """Xoá trắng toàn bộ bảng dim/fact (tắt tạm FK check trong session)."""
    tables = [
        "fact_ontime_route_month",
        "fact_capacity_route_month",
        "fact_turnaround_airport_daypart_month",
        "fact_fare_segment_quarter",
        "fact_fare_market_quarter",
        "fact_fare_class_quarter",
        "dim_route",
        "dim_aircraft",
        "dim_daypart",
        "dim_delay_cause",
        "dim_cancel_reason",
        "dim_carrier",
        "dim_airport",
        "dim_month",
        "dim_quarter",
        "dim_date",
    ]
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in tables:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))


def bulk_insert(engine, df: pd.DataFrame, table: str) -> int:
    """Chèn DataFrame vào bảng đã tồn tại (INSERT INTO ... VALUES multi)."""
    if df.empty:
        return 0
    df.to_sql(table, con=engine, if_exists="append", index=False,
              method="multi", chunksize=2000)
    return len(df)


# =========================================================================
# LOAD DIMENSIONS
# =========================================================================
def load_dimensions(engine, run_id: int, log: list) -> dict:
    """Nạp các bảng chiều, trả về dict ánh xạ khóa tự nhiên -> surrogate key."""
    maps = {}

    def log_row(table, phase, read_n, ins_n, rej_n, secs):
        log.append(dict(run_id=run_id, target_table=table, phase=phase,
                        rows_read=read_n, rows_inserted=ins_n,
                        rows_rejected=rej_n, duration_sec=round(secs, 2)))

    # ---- dim_date (khóa thông minh date_key) --------------------------
    t0 = time.time()
    df = read_source("dim_date")
    df = df[["date_key", "date", "year", "quarter", "month", "month_name",
             "day_of_month", "day_of_week", "day_name", "week_of_year",
             "is_weekend", "is_us_federal_holiday", "season"]].copy()
    for c in ["is_weekend", "is_us_federal_holiday"]:
        df[c] = to_bool_int(df[c])
    n = bulk_insert(engine, df, "dim_date")
    log_row("dim_date", "DIM", len(df), n, 0, time.time() - t0)

    # ---- dim_month & dim_quarter (suy ra từ dim_date) ------------------
    t0 = time.time()
    md = (df.drop_duplicates(subset=["year", "month"])
            .assign(month_key=lambda d: d["year"] * 100 + d["month"],
                    month_label=lambda d: d["year"].astype(str) + "-" +
                                         d["month"].astype(str).str.zfill(2))
            [["month_key", "year", "quarter", "month", "month_name", "month_label"]])
    n = bulk_insert(engine, md, "dim_month")
    qd = (df.drop_duplicates(subset=["year", "quarter"])
             .assign(quarter_key=lambda d: d["year"] * 10 + d["quarter"],
                     quarter_label=lambda d: d["year"].astype(str) + "-Q" +
                                              d["quarter"].astype(str))
             [["quarter_key", "year", "quarter", "quarter_label"]])
    n += bulk_insert(engine, qd, "dim_quarter")
    log_row("dim_month+dim_quarter", "DIM", len(md) + len(qd), n, 0, time.time() - t0)

    # ---- dim_carrier ----------------------------------------------------
    t0 = time.time()
    df = read_source("dim_carrier")
    df = df[["carrier_code", "carrier_name", "business_model", "is_regional",
             "in_ontime", "in_t100", "in_db1b_operating", "in_db1b_ticketed"]].copy()
    for c in ["is_regional", "in_ontime", "in_t100",
              "in_db1b_operating", "in_db1b_ticketed"]:
        df[c] = to_bool_int(df[c])
    bulk_insert(engine, df, "dim_carrier")
    m = pd.read_sql("SELECT carrier_key, carrier_code FROM dim_carrier", engine)
    maps["carrier"] = dict(zip(m.carrier_code, m.carrier_key))
    log_row("dim_carrier", "DIM", len(df), len(m), 0, time.time() - t0)

    # ---- dim_airport -----------------------------------------------------
    t0 = time.time()
    df = read_source("dim_airport")
    df = df[["airport_code", "city", "state", "city_market_id", "wac"]].copy()
    bulk_insert(engine, df, "dim_airport")
    m = pd.read_sql("SELECT airport_key, airport_code FROM dim_airport", engine)
    maps["airport"] = dict(zip(m.airport_code, m.airport_key))
    log_row("dim_airport", "DIM", len(df), len(m), 0, time.time() - t0)

    # ---- dim_route (FK về dim_airport) -----------------------------------
    t0 = time.time()
    df = read_source("dim_route")
    df["origin_key"] = df["origin"].map(maps["airport"])
    df["dest_key"] = df["dest"].map(maps["airport"])
    rejected = int(df["origin_key"].isna().sum() + df["dest_key"].isna().sum())
    df = df.dropna(subset=["origin_key", "dest_key"])
    out = df[["route", "origin_key", "dest_key", "origin", "dest",
              "market", "distance_mi", "distance_band"]].rename(
        columns={"origin": "origin_code", "dest": "dest_code"})
    bulk_insert(engine, out, "dim_route")
    m = pd.read_sql(
        "SELECT route_key, origin_code, dest_code FROM dim_route", engine)
    maps["route"] = {(r.origin_code, r.dest_code): r.route_key for r in m.itertuples()}
    log_row("dim_route", "DIM", len(df) + rejected, len(m), rejected, time.time() - t0)

    # ---- dim_aircraft -----------------------------------------------------
    t0 = time.time()
    df = read_source("dim_aircraft")
    out = df[["tail_number", "carrier", "first_flight_date", "last_flight_date",
              "n_flights", "n_completed", "avg_distance_mi",
              "flights_per_active_day"]].rename(columns={"carrier": "carrier_code"})
    bulk_insert(engine, out, "dim_aircraft")
    log_row("dim_aircraft", "DIM", len(out), len(out), 0, time.time() - t0)

    # ---- dim_daypart (tĩnh) ------------------------------------------------
    t0 = time.time()
    df = pd.DataFrame(cfg.DAYPART_ROWS, columns=[
        "daypart_code", "daypart_name", "label_vi", "hour_start", "hour_end", "sort_order"])
    bulk_insert(engine, df, "dim_daypart")
    m = pd.read_sql("SELECT daypart_key, daypart_code FROM dim_daypart", engine)
    maps["daypart"] = dict(zip(m.daypart_code, m.daypart_key))
    log_row("dim_daypart", "DIM", len(df), len(df), 0, time.time() - t0)

    # ---- dim_delay_cause (+ nhãn quản trị tiếng Việt) ------------------------
    t0 = time.time()
    df = read_source("dim_delay_cause")
    df["answer_label_vi"] = df["cause_code"].map(cfg.DELAY_CAUSE_LABEL_VI)
    df["sort_order"] = df["cause_code"].map(cfg.DELAY_CAUSE_SORT)
    out = df[["cause_code", "column_name", "answer_label_vi",
              "description_vi", "sort_order"]]
    bulk_insert(engine, out, "dim_delay_cause")
    log_row("dim_delay_cause", "DIM", len(out), len(out), 0, time.time() - t0)

    # ---- dim_cancel_reason ----------------------------------------------------
    t0 = time.time()
    df = read_source("dim_cancel_reason")
    bulk_insert(engine, df[["cancellation_code", "reason"]], "dim_cancel_reason")
    log_row("dim_cancel_reason", "DIM", len(df), len(df), 0, time.time() - t0)

    return maps


# =========================================================================
# LOAD FACTS
# =========================================================================
ONTIME_MEASURES = [
    "flights_scheduled", "flights_cancelled", "flights_diverted", "flights_completed",
    "dep_del15_count", "arr_del15_count", "arr_delay_pos_min", "dep_delay_pos_min",
    "delay_carrier_min", "delay_weather_min", "delay_nas_min", "delay_security_min",
    "delay_late_aircraft_min", "cancel_carrier", "cancel_weather", "cancel_nas",
    "cancel_security", "taxi_out_sum_min", "taxi_in_sum_min", "crs_elapsed_sum_min",
    "actual_elapsed_sum_min", "turn_n", "turn_over_sched_n", "turn_sched_sum_min",
    "turn_actual_sum_min", "gate_return_n", "total_add_gtime_sum_min",
]

CAPACITY_MEASURES = [
    "departures_scheduled", "departures_performed", "seats", "passengers",
    "freight_lbs", "mail_lbs", "asm", "rpm", "ramp_to_ramp_min", "air_time_min",
    "n_aircraft_types",
]

TURN_MEASURES = [
    "turn_n", "turn_sched_sum_min", "turn_actual_sum_min", "turn_excess_sum_min",
    "turn_over_sched_n", "turn_after_late_inbound_n", "dep_delay_sum_min",
]


def load_facts(engine, maps: dict, run_id: int, log: list):
    def log_row(table, read_n, ins_n, rej_n, secs):
        log.append(dict(run_id=run_id, target_table=table, phase="FACT",
                        rows_read=read_n, rows_inserted=ins_n,
                        rows_rejected=rej_n, duration_sec=round(secs, 2)))

    # ---- fact_ontime_route_month -------------------------------------------
    t0 = time.time()
    df = read_source("fact_ontime_route_month")
    df["month_key"] = df["year"] * 100 + df["month"]
    df["carrier_key"] = df["carrier"].map(maps["carrier"])
    df["route_key"] = list(map(maps["route"].get, zip(df["origin"], df["dest"])))
    bad = df["carrier_key"].isna() | df["route_key"].isna()
    rejected = int(bad.sum())
    df = df[~bad]
    out = df[["month_key", "carrier_key", "route_key"] + ONTIME_MEASURES].copy()
    out[ONTIME_MEASURES] = out[ONTIME_MEASURES].fillna(0)
    bulk_insert(engine, out, "fact_ontime_route_month")
    log_row("fact_ontime_route_month", len(df) + rejected, len(out), rejected,
            time.time() - t0)

    # ---- fact_capacity_route_month -------------------------------------------
    t0 = time.time()
    df = read_source("fact_capacity_route_month")
    df["month_key"] = df["year"] * 100 + df["month"]
    df["carrier_key"] = df["carrier"].map(maps["carrier"])
    df["route_key"] = list(map(maps["route"].get, zip(df["origin"], df["dest"])))
    bad = df["carrier_key"].isna() | df["route_key"].isna()
    rejected = int(bad.sum())
    df = df[~bad]
    out = df[["month_key", "carrier_key", "route_key"] + CAPACITY_MEASURES].copy()
    out[CAPACITY_MEASURES] = out[CAPACITY_MEASURES].fillna(0)
    bulk_insert(engine, out, "fact_capacity_route_month")
    log_row("fact_capacity_route_month", len(df) + rejected, len(out), rejected,
            time.time() - t0)

    # ---- fact_turnaround_airport_daypart_month --------------------------------
    t0 = time.time()
    df = read_source("fact_turnaround_airport_daypart_month")
    df["month_key"] = df["year"] * 100 + df["month"]
    df["carrier_key"] = df["carrier"].map(maps["carrier"])
    df["airport_key"] = df["airport"].map(maps["airport"])
    df["daypart_key"] = df["dep_daypart"].map(maps["daypart"])
    bad = df[["carrier_key", "airport_key", "daypart_key"]].isna().any(axis=1)
    rejected = int(bad.sum())
    df = df[~bad]
    out = df[["month_key", "carrier_key", "airport_key", "daypart_key"]
             + TURN_MEASURES].copy()
    out[TURN_MEASURES] = out[TURN_MEASURES].fillna(0)
    bulk_insert(engine, out, "fact_turnaround_airport_daypart_month")
    log_row("fact_turnaround_airport_daypart_month", len(df) + rejected, len(out),
            rejected, time.time() - t0)

    # ---- fact_fare_segment_quarter (DB1B) --------------------------------------
    t0 = time.time()
    df = read_source("fact_fare_segment_quarter")
    df["quarter_key"] = df["yyyy"] * 10 + df["quarter"]
    df["tk_carrier_key"] = df["tk_carrier"].map(maps["carrier"])
    df["op_carrier_key"] = df["op_carrier"].map(maps["carrier"])
    df["origin_key"] = df["origin"].map(maps["airport"])
    df["dest_key"] = df["dest"].map(maps["airport"])
    bad = df[["tk_carrier_key", "op_carrier_key",
              "origin_key", "dest_key"]].isna().any(axis=1)
    rejected = int(bad.sum())
    df = df[~bad]
    out = df[["quarter_key", "tk_carrier_key", "op_carrier_key",
              "origin_key", "dest_key", "pax_sample", "seg_revenue_sample",
              "pax_miles_sample", "pax_est", "revenue_est_usd"]].copy()
    bulk_insert(engine, out, "fact_fare_segment_quarter")
    log_row("fact_fare_segment_quarter", len(df) + rejected, len(out), rejected,
            time.time() - t0)

    # ---- fact_fare_market_quarter (DB1B) ----------------------------------------
    t0 = time.time()
    df = read_source("fact_fare_market_quarter")
    df["quarter_key"] = df["yyyy"] * 10 + df["quarter"]
    df["carrier_key"] = df["first_tk_carrier"].map(maps["carrier"])
    df["origin_key"] = df["market_origin"].map(maps["airport"])
    df["dest_key"] = df["market_dest"].map(maps["airport"])
    df["is_round_trip_i"] = to_bool_int(df["is_round_trip"])
    df["is_nonstop_i"] = to_bool_int(df["is_nonstop"])
    bad = df[["carrier_key", "origin_key", "dest_key"]].isna().any(axis=1)
    rejected = int(bad.sum())
    df = df[~bad]
    out = df[["quarter_key", "carrier_key", "origin_key", "dest_key",
              "is_round_trip_i", "is_nonstop_i", "itineraries", "pax_sample",
              "rev_sample", "pax_est"]].rename(
        columns={"is_round_trip_i": "is_round_trip", "is_nonstop_i": "is_nonstop"})
    bulk_insert(engine, out, "fact_fare_market_quarter")
    log_row("fact_fare_market_quarter", len(df) + rejected, len(out), rejected,
            time.time() - t0)

    # ---- fact_fare_class_quarter (DB1B) ------------------------------------------
    t0 = time.time()
    df = read_source("fact_fare_class_quarter")
    df["quarter_key"] = df["yyyy"] * 10 + df["quarter"]
    df["op_carrier_key"] = df["op_carrier"].map(maps["carrier"])
    bad = df["op_carrier_key"].isna()
    rejected = int(bad.sum())
    df = df[~bad]
    out = df[["quarter_key", "op_carrier_key", "fare_class",
              "pax_sample", "seg_revenue_sample"]]
    bulk_insert(engine, out, "fact_fare_class_quarter")
    log_row("fact_fare_class_quarter", len(df) + rejected, len(out), rejected,
            time.time() - t0)


# =========================================================================
# ĐIỀU PHỐI
# =========================================================================
def run_ddl(engine):
    """Chạy file DDL (drop & recreate schema) rồi tái tạo engine tới DB mới."""
    statements, buf = [], []
    for line in cfg.DDL_FILE.read_text(encoding="utf-8").splitlines():
        buf.append(line)
        # Kết thúc 1 statement: dòng lệnh (không phải comment '--') kết thúc bằng ';'
        if line.rstrip().endswith(";") and not line.strip().startswith("--"):
            stmt = "\n".join(buf).strip()
            if stmt.strip("; \n"):
                statements.append(stmt)
            buf = []
    server_url = cfg.SQLALCHEMY_URL.rsplit("/", 1)[0]
    tmp_engine = create_engine(server_url)
    with tmp_engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    tmp_engine.dispose()


def persist_log(engine, run_id: int, log: list, status: str, notes: str):
    if log:
        pd.DataFrame(log).to_sql("etl_load_log", con=engine, if_exists="append",
                                 index=False, method="multi", chunksize=1000)
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE etl_run SET finished_at = :f, status = :s, notes = :n "
            "WHERE run_id = :r"),
            dict(f=datetime.now(), s=status, n=notes, r=run_id))


def main():
    ap = argparse.ArgumentParser(description="ETL vào MySQL Data Warehouse aviation_dw")
    ap.add_argument("--init", action="store_true",
                    help="chạy lại file DDL (drop & recreate schema) trước khi nạp")
    ap.add_argument("--no-checks", action="store_true",
                    help="bỏ bước kiểm tra tính nhất quán sau khi nạp")
    args = ap.parse_args()

    print("=" * 70)
    print("ETL PIPELINE – Data Warehouse hàng không (aviation_dw)")
    print(f"Server: {cfg.MYSQL_HOST}:{cfg.MYSQL_PORT} | DB: {cfg.MYSQL_DB}")
    print("=" * 70)

    if args.init:
        print("[0] Tạo lại schema từ sql/01_create_schema.sql ...")
        run_ddl(create_engine(cfg.SQLALCHEMY_URL))

    engine = create_engine(cfg.SQLALCHEMY_URL)
    conn = pymysql.connect(host=cfg.MYSQL_HOST, port=cfg.MYSQL_PORT,
                           user=cfg.MYSQL_USER, password=cfg.MYSQL_PASSWORD,
                           database=cfg.MYSQL_DB, charset="utf8mb4")
    with conn.cursor() as cur:
        cur.execute("INSERT INTO etl_run (started_at, status) VALUES (NOW(), 'RUNNING')")
        run_id = cur.lastrowid
    conn.commit()
    conn.close()
    print(f"[•] run_id = {run_id}")

    log = []
    try:
        print("[1] TRUNCATE bảng dim/fact (full refresh) ...")
        truncate_all(engine)

        print("[2] Nạp DIMENSIONS ...")
        maps = load_dimensions(engine, run_id, log)
        for k, v in maps.items():
            print(f"    map {k}: {len(v)} khóa")

        print("[3] Nạp FACTS ...")
        load_facts(engine, maps, run_id, log)
        for row in log:
            print(f"    {row['target_table']:<45} đọc={row['rows_read']:>6} "
                  f"nạp={row['rows_inserted']:>6} loại={row['rows_rejected']:>3} "
                  f"({row['duration_sec']}s)")

        if args.no_checks:
            persist_log(engine, run_id, log, "SUCCESS", "nạp không kèm kiểm tra")
            print("[4] Bỏ bước kiểm tra (--no-checks). Hoàn tất.")
        else:
            print("[4] KIỂM TRA TÍNH NHẤT QUÁN ...")
            import flight_bi.etl.verify_consistency as vc
            all_pass = vc.run_checks(engine, run_id=run_id)
            persist_log(engine, run_id, log,
                        "SUCCESS" if all_pass else "WARNING",
                        "tất cả kiểm tra PASS" if all_pass else "có kiểm tra FAIL – xem dq_check")
            if not all_pass:
                print("!! Có kiểm tra FAIL – xem chi tiết output/dq_dwh_report.csv")
        print("HOÀN TẤT ETL.")
    except Exception as e:
        persist_log(engine, run_id, log, "FAILED", str(e)[:250])
        engine.dispose()
        raise
    engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
