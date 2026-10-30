-- =====================================================================
-- ĐỀ TÀI 10 – NHIỆM VỤ 2 · TRUY VẤN THỬ NGHIỆM TRÊN DATA WAREHOUSE
-- File: 02_test_queries.sql   |   DB: aviation_dw (MySQL 8.0)
-- Mỗi truy vấn là 1 use-case dashboard TV3 có thể dùng ngay.
-- Chạy: mysql -u root -p aviation_dw < sql/02_test_queries.sql
--   hoặc copy từng khối vào MySQL Workbench.
-- =====================================================================
USE aviation_dw;

-- ---------------------------------------------------------------------
-- Q0. Kiểm tra tổng thể: số dòng mỗi bảng fact/dim
-- ---------------------------------------------------------------------
SELECT 'dim_date'      AS bang, COUNT(*) AS so_dong FROM dim_date
UNION ALL SELECT 'dim_month',        COUNT(*) FROM dim_month
UNION ALL SELECT 'dim_quarter',      COUNT(*) FROM dim_quarter
UNION ALL SELECT 'dim_carrier',      COUNT(*) FROM dim_carrier
UNION ALL SELECT 'dim_airport',      COUNT(*) FROM dim_airport
UNION ALL SELECT 'dim_route',        COUNT(*) FROM dim_route
UNION ALL SELECT 'dim_aircraft',     COUNT(*) FROM dim_aircraft
UNION ALL SELECT 'dim_daypart',      COUNT(*) FROM dim_daypart
UNION ALL SELECT 'dim_delay_cause',  COUNT(*) FROM dim_delay_cause
UNION ALL SELECT 'dim_cancel_reason',COUNT(*) FROM dim_cancel_reason
UNION ALL SELECT 'fact_ontime_route_month',   COUNT(*) FROM fact_ontime_route_month
UNION ALL SELECT 'fact_capacity_route_month',  COUNT(*) FROM fact_capacity_route_month
UNION ALL SELECT 'fact_turnaround_airport_daypart_month', COUNT(*) FROM fact_turnaround_airport_daypart_month
UNION ALL SELECT 'fact_fare_segment_quarter',  COUNT(*) FROM fact_fare_segment_quarter
UNION ALL SELECT 'fact_fare_market_quarter',   COUNT(*) FROM fact_fare_market_quarter
UNION ALL SELECT 'fact_fare_class_quarter',    COUNT(*) FROM fact_fare_class_quarter;

-- ---------------------------------------------------------------------
-- Q1. Bảng điều khiển vận hành theo THÁNG: OTP, hủy, trễ
--     (OTP = 1 − arr_del15_count/flights_completed – chuẩn 15 phút DOT)
-- ---------------------------------------------------------------------
SELECT month                                        AS thang,
       month_name,
       flights_scheduled                            AS chuyến_lich,
       flights_cancelled                            AS chuyến_hủy,
       ROUND(1 - arr_del15_rate, 4)                 AS otp,
       ROUND(cancel_rate, 4)                        AS ty_le_huy,
       ROUND(avg_arr_delay_per_completed_min, 1)    AS tre_den_tb_phut,
       ROUND(load_factor, 4)                        AS he_so_tai
FROM mart_carrier_month
ORDER BY month;

-- ---------------------------------------------------------------------
-- Q2. Tỷ trọng nguyên nhân trễ theo QUÝ – câu hỏi quản trị #1
--     (dạng dòng – vẽ stacked bar %; khớp answer_delay_cause_share khi gộp cả năm)
-- ---------------------------------------------------------------------
SELECT ((month - 1) DIV 3) + 1                        AS quy,
       answer_label_vi                                AS nhom_nguyen_nhan,
       ROUND(SUM(delay_min))                          AS tong_phut,
       ROUND(SUM(delay_min)
             / NULLIF(SUM(SUM(delay_min)) OVER (PARTITION BY ((month - 1) DIV 3) + 1), 0)
             * 100, 1)                                AS ty_trong_pct
FROM mart_delay_cause_month
GROUP BY ((month - 1) DIV 3) + 1, answer_label_vi
ORDER BY quy, tong_phut DESC;

-- ---------------------------------------------------------------------
-- Q3. Quay đầu máy bay theo KHUNG GIỜ (cả năm 2024) – câu hỏi quản trị #2
--     Tổng hợp lại view tháng bằng trung bình có trọng số theo số lượt
-- ---------------------------------------------------------------------
SELECT daypart_name                                                   AS khung_gio,
       SUM(turn_n)                                                    AS so_luot,
       ROUND(SUM(avg_turn_sched_min  * turn_n) / SUM(turn_n), 1)      AS lich_tb_phut,
       ROUND(SUM(avg_turn_actual_min * turn_n) / SUM(turn_n), 1)      AS thuc_te_tb_phut,
       ROUND(SUM(avg_turn_actual_min * turn_n) / SUM(turn_n)
           - SUM(avg_turn_sched_min  * turn_n) / SUM(turn_n), 1)      AS vuot_lich_tb_phut,
       ROUND(SUM(turn_over_sched_rate * turn_n) / SUM(turn_n), 3)     AS ty_le_vuot_lich,
       ROUND(SUM(avg_dep_delay_min   * turn_n) / SUM(turn_n), 1)      AS tre_khoi_hanh_tb_phut
FROM mart_turnaround_daypart_month
GROUP BY daypart_code, daypart_name, sort_order
ORDER BY sort_order;

-- Xem drill-down 1 tháng cụ thể:
--   SELECT * FROM mart_turnaround_daypart_month WHERE month = 7 ORDER BY daypart_code;

-- Q4. TOP 10 sân bay có tổng phút quay đầu VƯỢT LỊCH lớn nhất (cả năm)
--     → nơi ưu tiên triển khai "pit-stop" song song để giảm 15% quay đầu
-- ---------------------------------------------------------------------
SELECT airport_code,
       city,
       SUM(turn_n)                        AS so_luot,
       ROUND(SUM(turn_excess_sum_min))    AS tong_phut_vuot_lich,
       ROUND(AVG(avg_turn_actual_min - avg_turn_sched_min), 1) AS vuot_lich_tb_phut,
       ROUND(SUM(turn_over_sched_n) / NULLIF(SUM(turn_n), 0), 3) AS ty_le_vuot
FROM mart_turnaround_airport_month
GROUP BY airport_code, city
ORDER BY tong_phut_vuot_lich DESC
LIMIT 10;

-- ---------------------------------------------------------------------
-- Q5. TOP 10 đường bay theo hành khách tháng 12 + hệ số tải
-- ---------------------------------------------------------------------
SELECT month, origin, dest, distance_mi,
       passengers                                   AS hanh_khach,
       ROUND(load_factor, 3)                        AS he_so_tai,
       ROUND(arr_del15_rate, 3)                     AS ty_le_tre_15p
FROM mart_route_month
WHERE month = 12
ORDER BY passengers DESC
LIMIT 10;

-- ---------------------------------------------------------------------
-- Q6. RASK · Yield · PLF theo QUÝ (T-100 + DB1B) – hiệu quả doanh thu
-- ---------------------------------------------------------------------
SELECT year, quarter,
       ROUND(departures_performed)       AS chuyến_thuc_hien,
       months_in_t100                    AS thang_t100,
       complete_quarter                  AS quy_du_du_lieu,
       ROUND(load_factor, 4)             AS plf,
       ROUND(rask_cents, 2)              AS rask_xu,
       ROUND(yield_cents, 2)             AS yield_xu,
       ROUND(revenue_est_usd / 1e6, 1)   AS doanh_thu_trieu_usd
FROM mart_carrier_quarter_rask
ORDER BY year, quarter;

-- ---------------------------------------------------------------------
-- Q7. TOP 10 thị trường O&D giá vé bình quân một chiều cao nhất (quý 4,
--     vé một chiều, bay thẳng, tối thiểu 100 khách mẫu)
-- ---------------------------------------------------------------------
SELECT year, quarter, market,
       pax_sample                                    AS khach_mau,
       ROUND(avg_one_way_fare_usd, 2)                AS gia_ve_tb_usd
FROM mart_fare_market_quarter
WHERE quarter = 4 AND is_round_trip = 0 AND is_nonstop = 1 AND pax_sample >= 100
ORDER BY gia_ve_tb_usd DESC
LIMIT 10;

-- ---------------------------------------------------------------------
-- Q8. Drill-down đa tầng: Hãng → Sân bay → Khung giờ (tháng 7)
--     top 5 tổ hợp có trung bình vượt lịch cao nhất
-- ---------------------------------------------------------------------
SELECT m.month           AS thang,
       a.airport_code    AS san_bay,
       dp.daypart_name   AS khung_gio,
       f.turn_n          AS so_luot,
       ROUND(f.turn_actual_sum_min / f.turn_n, 1) AS thuc_te_tb_phut,
       ROUND(f.turn_sched_sum_min  / f.turn_n, 1) AS lich_tb_phut,
       ROUND(f.turn_excess_sum_min / f.turn_n, 1) AS vuot_tb_phut
FROM fact_turnaround_airport_daypart_month f
JOIN dim_month   m  ON m.month_key   = f.month_key
JOIN dim_airport a  ON a.airport_key = f.airport_key
JOIN dim_daypart dp ON dp.daypart_key = f.daypart_key
WHERE m.month = 7
ORDER BY vuot_tb_phut DESC
LIMIT 5;

-- ---------------------------------------------------------------------
-- Q9. Hệ số tải & quãng đường: nhóm khoảng cách đường bay (dùng dim_route)
-- ---------------------------------------------------------------------
SELECT rt.distance_band                                 AS nhom_khoang_cach,
       COUNT(*)                                         AS so_duong_bay,
       ROUND(AVG(t.passengers / NULLIF(t.seats, 0)), 3) AS he_so_tai_tb
FROM mart_route_month m
JOIN dim_route rt ON rt.route = m.route
JOIN fact_capacity_route_month t
     ON t.month_key = m.year * 100 + m.month
    AND rt.origin_code = m.origin AND rt.dest_code = m.dest
GROUP BY rt.distance_band
ORDER BY MIN(rt.distance_mi);

-- ---------------------------------------------------------------------
-- Q10. Kiểm tra ETL: lịch sử chạy + nhật ký nạp + kết quả DQ cuối cùng
-- ---------------------------------------------------------------------
SELECT run_id, started_at, finished_at, status, notes FROM etl_run;

SELECT target_table, phase, rows_read, rows_inserted, rows_rejected, duration_sec
FROM etl_load_log
WHERE run_id = (SELECT MAX(run_id) FROM etl_run)
ORDER BY phase, target_table;

SELECT check_group,
       COUNT(*)                                            AS so_kiem_tra,
       SUM(status = 'PASS')                                AS pass,
       SUM(status = 'FAIL')                                AS fail
FROM dq_check
WHERE run_id = (SELECT MAX(run_id) FROM dq_check)
GROUP BY check_group;
