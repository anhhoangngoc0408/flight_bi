# -*- coding: utf-8 -*-
"""
Cấu hình ETL – Đề tài 10 (Nhiệm vụ 2: Data Warehouse & ETL)

Ưu tiên đọc biến môi trường, nếu không có thì dùng giá trị mặc định (máy local):
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB
"""
import os
from pathlib import Path
from urllib.parse import quote_plus

# ----------------------------------------------------------------数据库--
# Kết nối MySQL: credentials chỉ lấy từ biến môi trường.
MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DB = os.environ.get("MYSQL_DB", "aviation_dw")

# Chuỗi kết nối cho SQLAlchemy (mật khẩu được URL-encode vì có thể chứa '@')
SQLALCHEMY_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
)

# ------------------------------------------------------------------path--
# Thư mục gốc dự án = cha của thư mục etl/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Thư mục CSV nguồn do Nhiệm vụ 1 xuất ra (đã giải nén)
SOURCE_DIR = PROJECT_ROOT / "data" / "aggregated_WN_2024"

# File DDL tạo schema (dùng cho tuỳ chọn --init)
DDL_FILE = PROJECT_ROOT / "sql" / "01_create_schema.sql"

# Thư mục xuất báo cáo kiểm tra
OUTPUT_DIR = PROJECT_ROOT / "output"

# -----------------------------------------------------------------files--
# Ánh xạ bảng đích -> file CSV nguồn
SOURCE_FILES = {
    "dim_date":        "dim_date.csv",
    "dim_carrier":     "dim_carrier.csv",
    "dim_airport":     "dim_airport.csv",
    "dim_route":       "dim_route.csv",
    "dim_aircraft":    "dim_aircraft.csv",
    "dim_delay_cause": "dim_delay_cause.csv",
    "dim_cancel_reason": "dim_cancel_reason.csv",
    "fact_ontime_route_month":  "agg_ontime_carrier_route_month.csv",
    "fact_capacity_route_month": "agg_t100_carrier_route_month.csv",
    "fact_turnaround_airport_daypart_month": "agg_turnaround_airport_daypart_month.csv",
    "fact_fare_segment_quarter": "agg_db1b_segment_quarter.csv",
    "fact_fare_market_quarter":  "agg_db1b_market_quarter.csv",
    "fact_fare_class_quarter":   "agg_db1b_fareclass_quarter.csv",
}

# File mart CSV của Nhiệm vụ 1 – dùng làm "chuẩn đối chiếu" khi kiểm tra nhất quán
MART_BENCHMARK_FILES = {
    "mart_carrier_month":       "mart_carrier_month.csv",
    "mart_route_month":         "mart_route_month.csv",
    "mart_carrier_quarter_rask": "mart_carrier_quarter_rask.csv",
    "mart_route_quarter_rask":  "mart_route_quarter_rask.csv",
}

# File answer của Nhiệm vụ 1 – đối chiếu lại câu trả lời quản trị
ANSWER_FILES = {
    "answer_delay_cause_share":     "answer_delay_cause_share.csv",
    "answer_turnaround_by_daypart": "answer_turnaround_by_daypart.csv",
}

# dim_daypart không có file nguồn – tạo tĩnh (khớp giá trị dep_daypart của On-Time)
DAYPART_ROWS = [
    # code,              name,        label_vi,                 start, end, sort
    ("morning_06_11",   "Morning",   "Sáng (06:00-11:59)",      6,  12, 1),
    ("afternoon_12_17", "Afternoon", "Chiều (12:00-17:59)",    12,  18, 2),
    ("evening_18_23",   "Evening",   "Tối (18:00-23:59)",      18,  24, 3),
    ("night_00_05",     "Night",     "Đêm (00:00-05:59)",       0,   6, 4),
]

# Nhãn quản trị tiếng Việt cho 5 nhóm nguyên nhân trễ
# (khớp cột "nhóm quản trị" trong answer_delay_cause_share.csv)
DELAY_CAUSE_LABEL_VI = {
    "LateAircraft": "Late Aircraft (Cascading Delay)",
    "Carrier":      "Carrier (Maintenance · Fueling · Crew · Loading)",
    "NAS":          "National Airspace System (NAS)",
    "Weather":      "Weather",
    "Security":     "Security",
}
DELAY_CAUSE_SORT = {"LateAircraft": 1, "Carrier": 2, "NAS": 3, "Weather": 4, "Security": 5}

# Ngưỡng khi so sánh số thực (sai số làm tròn giữa CSV và DECIMAL trong MySQL)
FLOAT_TOL = 1e-6
# Ngưỡng tỉ lệ On-Time/T-100 được coi là nhất quán (khớp dq_cross_source)
CROSS_SOURCE_RATIO_MIN = 0.95
