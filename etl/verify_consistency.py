# -*- coding: utf-8 -*-
"""
KIỂM TRA TÍNH NHẤT QUÁN – Đề tài 10 · Nhiệm vụ 2
================================================================
Đối chiếu Data Warehouse `aviation_dw` (đã nạp) với dữ liệu nguồn CSV:
  1. ROW COUNT  – số dòng mỗi bảng fact khớp file CSV nguồn
  2. MEASURE SUM– tổng mỗi cột measure khớp tổng CSV (sai số làm tròn nhỏ)
  3. FK ORPHAN  – 0 dòng mồ côi khóa ngoại (tham chiếu chiều)
  4. GRAIN DUP  – khóa grain là duy nhất (COUNT = COUNT DISTINCT)
  5. CROSS-SRC  – On-Time vs T-100: tỉ lệ chuyến/tháng ≥ 95% (khớp dq_cross_source)
  6. MART PARITY– các VIEW mart tái tạo đúng KPI của mart CSV Nhiệm vụ 1
  7. ANSWER     – tái tạo được đáp án quản trị (delay cause share, turnaround)

Kết quả ghi vào bảng dq_check + xuất output/dq_dwh_report.csv.

Chạy độc lập:  python etl/verify_consistency.py
"""
import sys
import time

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import flight_bi.config.config as cfg

# Cột measure cộng dồn được của từng fact (khớp DDL)
FACT_MEASURES = {
    "fact_ontime_route_month": {
        "file": "agg_ontime_carrier_route_month.csv",
        "cols": [
            "flights_scheduled", "flights_cancelled", "flights_diverted", "flights_completed",
            "dep_del15_count", "arr_del15_count", "arr_delay_pos_min", "dep_delay_pos_min",
            "delay_carrier_min", "delay_weather_min", "delay_nas_min", "delay_security_min",
            "delay_late_aircraft_min", "cancel_carrier", "cancel_weather", "cancel_nas",
            "cancel_security", "taxi_out_sum_min", "taxi_in_sum_min", "crs_elapsed_sum_min",
            "actual_elapsed_sum_min", "turn_n", "turn_over_sched_n", "turn_sched_sum_min",
            "turn_actual_sum_min", "gate_return_n", "total_add_gtime_sum_min"],
    },
    "fact_capacity_route_month": {
        "file": "agg_t100_carrier_route_month.csv",
        "cols": [
            "departures_scheduled", "departures_performed", "seats", "passengers",
            "freight_lbs", "mail_lbs", "asm", "rpm", "ramp_to_ramp_min", "air_time_min",
            "n_aircraft_types"],
    },
    "fact_turnaround_airport_daypart_month": {
        "file": "agg_turnaround_airport_daypart_month.csv",
        "cols": [
            "turn_n", "turn_sched_sum_min", "turn_actual_sum_min", "turn_excess_sum_min",
            "turn_over_sched_n", "turn_after_late_inbound_n", "dep_delay_sum_min"],
    },
    "fact_fare_segment_quarter": {
        "file": "agg_db1b_segment_quarter.csv",
        "cols": [
            "pax_sample", "seg_revenue_sample", "pax_miles_sample", "pax_est",
            "revenue_est_usd"],
    },
    "fact_fare_market_quarter": {
        "file": "agg_db1b_market_quarter.csv",
        "cols": [
            "itineraries", "pax_sample", "rev_sample", "pax_est"],
    },
    "fact_fare_class_quarter": {
        "file": "agg_db1b_fareclass_quarter.csv",
        "cols": ["pax_sample", "seg_revenue_sample"],
    },
}

# Cột KPI so sánh giữa VIEW mart và mart CSV của Nhiệm vụ 1
MART_KPI_COLS = [
    "cancel_rate", "divert_rate", "arr_del15_rate", "dep_del15_rate",
    "delay_cause_total_min", "delay_carrier_share", "delay_weather_share",
    "delay_nas_share", "delay_security_share", "delay_late_aircraft_share",
    "avg_arr_delay_per_completed_min", "load_factor", "avg_turn_sched_min",
    "avg_turn_actual_min", "turn_over_sched_rate", "gate_return_rate",
]
RASK_KPI_COLS = [
    "load_factor", "rask_cents", "yield_cents", "db1b_pax_to_t100_pax",
]

results = []  # các dòng kết quả (ghi dq_check + CSV)


def add(group, name, status, value="", detail=""):
    results.append(dict(check_group=group, check_name=name,
                        status="PASS" if status else "FAIL",
                        metric_value=str(value), detail=str(detail)[:480]))


def close_enough(a, b, abs_tol=1e-4, rel_tol=1e-9):
    """So sánh 2 số thực: NaN-None coi là bằng nhau."""
    a, b = float(a), float(b)
    if np.isnan(a) and np.isnan(b):
        return True
    if np.isnan(a) or np.isnan(b):
        return False
    return abs(a - b) <= max(abs_tol, rel_tol * max(1.0, abs(a), abs(b)))


def compare_frames(db: pd.DataFrame, csv: pd.DataFrame, keys, cols,
                   group, label, abs_tol=1e-4, rel_tol=1e-9):
    """Gộp theo keys rồi so từng cột KPI; trả về số cột FAIL."""
    d = db[keys + cols].copy()
    s = csv[keys + cols].copy()
    # chuẩn hoá bool/NaN
    for df in (d, s):
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    m = d.merge(s, on=keys, how="outer", suffixes=("_db", "_csv"),
                indicator=True)
    n_mismatch_rows = int((m._merge != "both").sum())
    if n_mismatch_rows:
        add(group, f"{label}: trùng khớp khóa join",
            False, f"{n_mismatch_rows} dòng lệch",
            f"db={len(d)} csv={len(s)}")
    else:
        add(group, f"{label}: trùng khớp khóa join", True,
            f"{len(m)} dòng", f"db={len(d)} csv={len(s)}")
    n_fail = 0
    for c in cols:
        a, b = m[f"{c}_db"], m[f"{c}_csv"]
        bad = []
        for i, (x, y) in enumerate(zip(a, b)):
            xx = np.nan if pd.isna(x) else x
            yy = np.nan if pd.isna(y) else y
            if not close_enough(xx, yy, abs_tol, rel_tol):
                bad.append(i)
        if bad:
            n_fail += 1
            i = bad[0]
            add(group, f"{label}: KPI {c}", False, f"{len(bad)}/{len(m)} dòng lệch",
                f"vd dòng {i}: db={a.iloc[i]} vs csv={b.iloc[i]}")
        else:
            add(group, f"{label}: KPI {c}", True, f"max_diff≤tol",
                f"so trên {len(m)} dòng")
    return n_fail


# =========================================================================
# 1-4. ROW COUNT / MEASURE SUM / FK ORPHAN / GRAIN DUP
# =========================================================================
def check_facts(engine):
    for table, spec in FACT_MEASURES.items():
        csv = pd.read_csv(cfg.SOURCE_DIR / spec["file"])

        # 1. Row count
        n_db = pd.read_sql(f"SELECT COUNT(*) n FROM {table}", engine).n.iloc[0]
        add("ROW_COUNT", f"{table} = {spec['file']}",
            n_db == len(csv), f"db={n_db} csv={len(csv)}")

        # 2. Measure sums
        sums_db = pd.read_sql(
            f"SELECT {', '.join('SUM(%s) AS %s' % (c, c) for c in spec['cols'])} FROM {table}",
            engine).iloc[0]
        for c in spec["cols"]:
            tol = 1.0 if c.endswith("_min") else 0.01
            ok = close_enough(sums_db[c], csv[c].sum(), abs_tol=tol, rel_tol=1e-9)
            add("MEASURE_SUM", f"{table}.{c}", ok,
                f"db={float(sums_db[c]):.2f} csv={csv[c].sum():.2f}")

        # 3. FK orphans – đếm orphan qua từng FK của bảng
        fk_queries = {
            "fact_ontime_route_month": [
                "SELECT COUNT(*) FROM fact_ontime_route_month f LEFT JOIN dim_month d ON d.month_key=f.month_key WHERE d.month_key IS NULL",
                "SELECT COUNT(*) FROM fact_ontime_route_month f LEFT JOIN dim_carrier d ON d.carrier_key=f.carrier_key WHERE d.carrier_key IS NULL",
                "SELECT COUNT(*) FROM fact_ontime_route_month f LEFT JOIN dim_route d ON d.route_key=f.route_key WHERE d.route_key IS NULL"],
            "fact_capacity_route_month": [
                "SELECT COUNT(*) FROM fact_capacity_route_month f LEFT JOIN dim_month d ON d.month_key=f.month_key WHERE d.month_key IS NULL",
                "SELECT COUNT(*) FROM fact_capacity_route_month f LEFT JOIN dim_carrier d ON d.carrier_key=f.carrier_key WHERE d.carrier_key IS NULL",
                "SELECT COUNT(*) FROM fact_capacity_route_month f LEFT JOIN dim_route d ON d.route_key=f.route_key WHERE d.route_key IS NULL"],
            "fact_turnaround_airport_daypart_month": [
                "SELECT COUNT(*) FROM fact_turnaround_airport_daypart_month f LEFT JOIN dim_month d ON d.month_key=f.month_key WHERE d.month_key IS NULL",
                "SELECT COUNT(*) FROM fact_turnaround_airport_daypart_month f LEFT JOIN dim_carrier d ON d.carrier_key=f.carrier_key WHERE d.carrier_key IS NULL",
                "SELECT COUNT(*) FROM fact_turnaround_airport_daypart_month f LEFT JOIN dim_airport d ON d.airport_key=f.airport_key WHERE d.airport_key IS NULL",
                "SELECT COUNT(*) FROM fact_turnaround_airport_daypart_month f LEFT JOIN dim_daypart d ON d.daypart_key=f.daypart_key WHERE d.daypart_key IS NULL"],
            "fact_fare_segment_quarter": [
                "SELECT COUNT(*) FROM fact_fare_segment_quarter f LEFT JOIN dim_quarter d ON d.quarter_key=f.quarter_key WHERE d.quarter_key IS NULL",
                "SELECT COUNT(*) FROM fact_fare_segment_quarter f LEFT JOIN dim_carrier d ON d.carrier_key=f.tk_carrier_key WHERE d.carrier_key IS NULL",
                "SELECT COUNT(*) FROM fact_fare_segment_quarter f LEFT JOIN dim_carrier d ON d.carrier_key=f.op_carrier_key WHERE d.carrier_key IS NULL",
                "SELECT COUNT(*) FROM fact_fare_segment_quarter f LEFT JOIN dim_airport d ON d.airport_key=f.origin_key WHERE d.airport_key IS NULL",
                "SELECT COUNT(*) FROM fact_fare_segment_quarter f LEFT JOIN dim_airport d ON d.airport_key=f.dest_key WHERE d.airport_key IS NULL"],
            "fact_fare_market_quarter": [
                "SELECT COUNT(*) FROM fact_fare_market_quarter f LEFT JOIN dim_quarter d ON d.quarter_key=f.quarter_key WHERE d.quarter_key IS NULL",
                "SELECT COUNT(*) FROM fact_fare_market_quarter f LEFT JOIN dim_carrier d ON d.carrier_key=f.carrier_key WHERE d.carrier_key IS NULL",
                "SELECT COUNT(*) FROM fact_fare_market_quarter f LEFT JOIN dim_airport d ON d.airport_key=f.origin_key WHERE d.airport_key IS NULL",
                "SELECT COUNT(*) FROM fact_fare_market_quarter f LEFT JOIN dim_airport d ON d.airport_key=f.dest_key WHERE d.airport_key IS NULL"],
            "fact_fare_class_quarter": [
                "SELECT COUNT(*) FROM fact_fare_class_quarter f LEFT JOIN dim_quarter d ON d.quarter_key=f.quarter_key WHERE d.quarter_key IS NULL",
                "SELECT COUNT(*) FROM fact_fare_class_quarter f LEFT JOIN dim_carrier d ON d.carrier_key=f.op_carrier_key WHERE d.carrier_key IS NULL"],
        }
        n_orphan = 0
        for q in fk_queries[table]:
            n_orphan += int(pd.read_sql(q, engine).iloc[0, 0])
        add("FK_ORPHAN", f"{table}: dòng mồ côi khóa ngoại", n_orphan == 0,
            f"{n_orphan} dòng mồ côi")

        # 4. Grain uniqueness
        n_dup = pd.read_sql(f"SELECT COUNT(*) - COUNT(DISTINCT "
                            f"{_grain_expr(table)}) FROM {table}", engine).iloc[0, 0]
        add("GRAIN_DUP", f"{table}: grain là duy nhất", int(n_dup) == 0,
            f"{int(n_dup)} dòng trùng grain")


def _grain_expr(table):
    return {
        "fact_ontime_route_month": "CONCAT(month_key,'-',carrier_key,'-',route_key)",
        "fact_capacity_route_month": "CONCAT(month_key,'-',carrier_key,'-',route_key)",
        "fact_turnaround_airport_daypart_month":
            "CONCAT(month_key,'-',carrier_key,'-',airport_key,'-',daypart_key)",
        "fact_fare_segment_quarter":
            "CONCAT(quarter_key,'-',tk_carrier_key,'-',op_carrier_key,'-',origin_key,'-',dest_key)",
        "fact_fare_market_quarter":
            "CONCAT(quarter_key,'-',carrier_key,'-',origin_key,'-',dest_key,'-',is_round_trip,'-',is_nonstop)",
        "fact_fare_class_quarter":
            "CONCAT(quarter_key,'-',op_carrier_key,'-',fare_class)",
    }[table]


# =========================================================================
# 5. CROSS-SOURCE: On-Time vs T-100
# =========================================================================
def check_cross_source(engine):
    q = """
        SELECT m.year, m.month,
               SUM(o.flights_scheduled)  AS flights_scheduled,
               SUM(o.flights_cancelled)  AS flights_cancelled,
               SUM(o.flights_scheduled - o.flights_cancelled) AS flights_operated_ontime,
               SUM(t.departures_performed) AS departures_performed
        FROM fact_ontime_route_month o
        JOIN dim_month m ON m.month_key = o.month_key
        LEFT JOIN fact_capacity_route_month t
               ON t.month_key = o.month_key AND t.carrier_key = o.carrier_key
              AND t.route_key = o.route_key
        GROUP BY m.year, m.month ORDER BY m.year, m.month
    """
    db = pd.read_sql(q, engine)
    db["ratio_ontime_vs_t100"] = db.flights_operated_ontime / db.departures_performed
    csv = pd.read_csv(cfg.SOURCE_DIR / "dq_cross_source.csv")
    m = db.merge(csv[["year", "month", "ratio_ontime_vs_t100"]],
                 on=["year", "month"], suffixes=("_db", "_csv"))
    ok_ratio = all(close_enough(a, b, abs_tol=1e-6)
                   for a, b in zip(m.ratio_ontime_vs_t100_db, m.ratio_ontime_vs_t100_csv))
    add("CROSS_SOURCE", "12 tháng: tỉ lệ On-Time/T-100 khớp dq_cross_source.csv",
        ok_ratio and len(m) == 12, f"min={db.ratio_ontime_vs_t100.min():.4f}")
    ok_min = db.ratio_ontime_vs_t100.min() >= cfg.CROSS_SOURCE_RATIO_MIN
    add("CROSS_SOURCE", f"mọi tháng tỉ lệ ≥ {cfg.CROSS_SOURCE_RATIO_MIN}",
        bool(ok_min), f"min={db.ratio_ontime_vs_t100.min():.4f}",
        "T-100.departures_performed ≈ On-Time chuyến đã cất cánh")


# =========================================================================
# 6. MART PARITY: VIEW tái tạo đúng mart CSV của Nhiệm vụ 1
# =========================================================================
def check_marts(engine):
    # mart_carrier_month / mart_route_month
    for view, file, keys in [
        ("mart_carrier_month", "mart_carrier_month.csv", ["year", "month", "carrier"]),
        ("mart_route_month", "mart_route_month.csv",
         ["year", "month", "carrier", "origin", "dest"]),
    ]:
        db = pd.read_sql(f"SELECT * FROM {view}", engine)
        csv = pd.read_csv(cfg.SOURCE_DIR / file)
        n_ok = len(db) == len(csv)
        add("MART_PARITY", f"{view}: số dòng", n_ok, f"db={len(db)} csv={len(csv)}")
        compare_frames(db, csv, keys, MART_KPI_COLS, "MART_PARITY", view)

    # mart rask (quý)
    for view, file, keys in [
        ("mart_carrier_quarter_rask", "mart_carrier_quarter_rask.csv",
         ["year", "quarter", "carrier"]),
        ("mart_route_quarter_rask", "mart_route_quarter_rask.csv",
         ["year", "quarter", "carrier", "origin", "dest"]),
    ]:
        db = pd.read_sql(f"SELECT * FROM {view}", engine)
        csv = pd.read_csv(cfg.SOURCE_DIR / file)
        add("MART_PARITY", f"{view}: số dòng", len(db) == len(csv),
            f"db={len(db)} csv={len(csv)}")
        # complete_quarter: CSV True/False -> 1/0
        csv["complete_quarter"] = csv["complete_quarter"].astype(str).str.lower().eq("true").astype(int)
        compare_frames(db, csv, keys, RASK_KPI_COLS + ["complete_quarter"],
                       "MART_PARITY", view, abs_tol=1e-3)


# =========================================================================
# 7. ANSWER PARITY: tái tạo đáp án quản trị của Nhiệm vụ 1
# =========================================================================
def check_answers(engine):
    # 7a. Tỷ trọng nguyên nhân trễ (answer_delay_cause_share.csv)
    db = pd.read_sql("""
        SELECT cause_code, answer_label_vi, SUM(delay_min) AS delay_min
        FROM mart_delay_cause_month GROUP BY cause_code, answer_label_vi
    """, engine)
    total = db.delay_min.sum()
    db["share_pct"] = db.delay_min / total * 100
    csv = pd.read_csv(cfg.SOURCE_DIR / "answer_delay_cause_share.csv")
    csv = csv.rename(columns={csv.columns[0]: "answer_label_vi",
                              csv.columns[1]: "tong_phut_tre",
                              csv.columns[2]: "ty_trong_pct"})
    m = db.merge(csv, on="answer_label_vi")
    ok = len(m) == 5 and all(
        close_enough(a, b, abs_tol=1e6, rel_tol=1e-3)  # tổng phút: sai số tương đối 0.1%
        for a, b in zip(m.delay_min, m.tong_phut_tre))
    add("ANSWER", "answer_delay_cause_share: tổng phút trễ theo nhóm",
        ok and len(m) == 5, f"{len(m)}/5 nhóm khớp")
    ok_share = all(abs(a - b) <= 0.05
                   for a, b in zip(m.share_pct, m.ty_trong_pct))
    add("ANSWER", "answer_delay_cause_share: tỷ trọng % (làm tròn 1 số thập phân)",
        ok_share, "chênh lệch ≤ 0.05 điểm %",
        "; ".join(f"{r.cause_code}:{r.share_pct:.1f}%" for r in m.itertuples()))

    # 7b. Turnaround theo khung giờ (answer_turnaround_by_daypart.csv)
    db = pd.read_sql("""
        SELECT daypart_code,
               SUM(turn_n)                                              AS luot,
               SUM(avg_turn_sched_min  * turn_n) / SUM(turn_n)         AS lich_tb,
               SUM(avg_turn_actual_min * turn_n) / SUM(turn_n)         AS thuc_te_tb,
               SUM(turn_over_sched_rate * turn_n) / SUM(turn_n)        AS ty_le_vuot,
               SUM(avg_dep_delay_min   * turn_n) / SUM(turn_n)         AS tre_di_tb
        FROM mart_turnaround_daypart_month GROUP BY daypart_code
    """, engine)
    csv = pd.read_csv(cfg.SOURCE_DIR / "answer_turnaround_by_daypart.csv")
    csv = csv.rename(columns={"dep_daypart": "daypart_code"})
    m = db.merge(csv, on="daypart_code", suffixes=("_db", "_csv"))
    ok = len(m) == 4
    detail = []
    for c in ["luot", "lich_tb", "thuc_te_tb", "ty_le_vuot", "tre_di_tb"]:
        a_col, b_col = f"{c}_db", f"{c}_csv"
        for a, b in zip(m[a_col], m[b_col]):
            if not close_enough(a, b, abs_tol=0.05, rel_tol=1e-3):
                ok = False
                detail.append(f"{c}: db={a:.2f} vs csv={b:.2f}")
    add("ANSWER", "answer_turnaround_by_daypart: 4 khung giờ khớp",
        ok, "chênh lệch ≤ 0.05", "; ".join(detail) if detail else "tất cả khớp")


# =========================================================================
# ĐIỀU PHỐI
# =========================================================================
def run_checks(engine=None, run_id=None) -> bool:
    if engine is None:
        engine = create_engine(cfg.SQLALCHEMY_URL)
    results.clear()
    t0 = time.time()
    check_facts(engine)
    check_cross_source(engine)
    check_marts(engine)
    check_answers(engine)

    df = pd.DataFrame(results)
    cfg.OUTPUT_DIR.mkdir(exist_ok=True)
    out = cfg.OUTPUT_DIR / "dq_dwh_report.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")

    if run_id is not None:
        df2 = df.copy()
        df2.insert(0, "run_id", run_id)
        df2.to_sql("dq_check", con=engine, if_exists="append", index=False,
                   method="multi", chunksize=1000)

    # In tóm tắt
    print("-" * 78)
    print(f"KIỂM TRA TÍNH NHẤT QUÁN – {len(df)} kiểm tra trong {time.time()-t0:.1f}s")
    print("-" * 78)
    summary = df.groupby("check_group").agg(
        total=("status", "size"),
        fail=("status", lambda s: int((s == "FAIL").sum())))
    print(summary.to_string())
    fails = df[df.status == "FAIL"]
    if len(fails):
        print("\nCác kiểm tra FAIL:")
        for _, r in fails.iterrows():
            print(f"  [{r.check_group}] {r.check_name} | {r.metric_value} | {r.detail}")
    else:
        print(f"\nTẤT CẢ {len(df)} KIỂM TRA ĐẠI: PASS ✔")
    print(f"Báo cáo đầy đủ: {out}")
    return len(fails) == 0


if __name__ == "__main__":
    ok = run_checks()
    sys.exit(0 if ok else 1)
