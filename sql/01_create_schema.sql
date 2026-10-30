-- =====================================================================
-- ĐỀ TÀI 10 – DSS Quản trị Khai thác Chuyến bay & Doanh thu Hãng hàng không
-- NHIỆM VỤ 2 – DATA WAREHOUSE & ETL
-- File   : 01_create_schema.sql
-- Server : MySQL 8.0+   (InnoDB, utf8mb4)
-- Lược đồ: aviation_dw  (star schema / data-mart constellation)
--
-- NGUỒN NẠP: các CSV tổng hợp của Nhiệm vụ 1 (thư mục data/aggregated_WN_2024)
--   · BTS On-Time  -> agg_ontime_carrier_route_month, agg_turnaround_airport_daypart_month
--   · BTS T-100    -> agg_t100_carrier_route_month
--   · BTS DB1B     -> agg_db1b_segment_quarter, agg_db1b_market_quarter, agg_db1b_fareclass_quarter
--   · Dimensions   -> dim_date, dim_carrier, dim_airport, dim_route, dim_aircraft,
--                     dim_delay_cause, dim_cancel_reason
--
-- QUY ƯỚC ĐẶT TÊN (đã chốt – TV3 dashboard dựa vào đây):
--   · dim_*  : bảng chiều; khóa surrogate *_key (AI) trừ dim_date/dim_month/dim_quarter dùng khóa thông minh
--   · fact_* : bảng sự kiện; khóa grain là UNIQUE constraint, measures là cột cộng dồn được
--   · mart_* : VIEW serving layer cho dashboard (không phải bảng vật lý)
--   · _min = phút, _mi = dặm, _lbs = pound, _usd = USD, _n = số lượng, _sum = tổng cộng dồn
-- =====================================================================

DROP DATABASE IF EXISTS aviation_dw;
CREATE DATABASE aviation_dw
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE aviation_dw;

-- =====================================================================
-- PHẦN A · BẢNG CHIỀU (DIMENSIONS)
-- =====================================================================

-- ---------------------------------------------------------------------
-- A1. dim_date – grain: 1 NGÀY (năm 2024, 366 dòng)
--     Khóa thông minh date_key = yyyymmdd (không dùng surrogate AI)
-- ---------------------------------------------------------------------
CREATE TABLE dim_date (
    date_key              INT          NOT NULL COMMENT 'Khóa chính yyyymmdd (20240101)',
    date                  DATE         NOT NULL COMMENT 'Ngày',
    year                  SMALLINT     NOT NULL COMMENT 'Năm',
    quarter               TINYINT      NOT NULL COMMENT 'Quý 1-4',
    month                 TINYINT      NOT NULL COMMENT 'Tháng 1-12',
    month_name            VARCHAR(10)  NOT NULL COMMENT 'Tên tháng tiếng Anh',
    day_of_month          TINYINT      NOT NULL COMMENT 'Ngày trong tháng 1-31',
    day_of_week           TINYINT      NOT NULL COMMENT 'Thứ trong tuần (1=Thứ Hai … 7=Chủ Nhật)',
    day_name              VARCHAR(10)  NOT NULL COMMENT 'Tên thứ tiếng Anh',
    week_of_year          TINYINT      NOT NULL COMMENT 'Tuần trong năm 1-53',
    is_weekend            TINYINT(1)   NOT NULL COMMENT '1 = Thứ Bảy/Chủ Nhật',
    is_us_federal_holiday TINYINT(1)   NOT NULL COMMENT '1 = ngày lễ liên bang Mỹ',
    season                VARCHAR(10)  NOT NULL COMMENT 'Winter/Spring/Summer/Fall',
    PRIMARY KEY (date_key),
    UNIQUE KEY uq_dim_date_date (date)
) ENGINE=InnoDB COMMENT='Chiều thời gian – hạt ngày';

-- ---------------------------------------------------------------------
-- A2. dim_month – grain: 1 THÁNG (12 dòng, suy ra từ dim_date)
--     Dùng cho các fact hạt tháng (thay vì FK về ngày đầu tháng)
-- ---------------------------------------------------------------------
CREATE TABLE dim_month (
    month_key   INT         NOT NULL COMMENT 'Khóa chính yyyymm (202401)',
    year        SMALLINT    NOT NULL,
    quarter     TINYINT     NOT NULL,
    month       TINYINT     NOT NULL,
    month_name  VARCHAR(10) NOT NULL,
    month_label CHAR(7)     NOT NULL COMMENT 'Nhãn 2024-01',
    PRIMARY KEY (month_key)
) ENGINE=InnoDB COMMENT='Chiều thời gian – hạt tháng (rollup của dim_date)';

-- ---------------------------------------------------------------------
-- A3. dim_quarter – grain: 1 QUÝ (4 dòng, suy ra từ dim_date)
--     Dùng cho các fact DB1B hạt quý
-- ---------------------------------------------------------------------
CREATE TABLE dim_quarter (
    quarter_key   INT       NOT NULL COMMENT 'Khóa chính yyyyq (20241)',
    year          SMALLINT  NOT NULL,
    quarter       TINYINT   NOT NULL,
    quarter_label CHAR(7)   NOT NULL COMMENT 'Nhãn 2024-Q1',
    PRIMARY KEY (quarter_key)
) ENGINE=InnoDB COMMENT='Chiều thời gian – hạt quý (rollup của dim_date)';

-- ---------------------------------------------------------------------
-- A4. dim_carrier – grain: 1 HÃNG BAY (hiện chỉ có WN – hãng được chọn)
-- ---------------------------------------------------------------------
CREATE TABLE dim_carrier (
    carrier_key       SMALLINT     NOT NULL AUTO_INCREMENT,
    carrier_code      CHAR(2)      NOT NULL COMMENT 'Mã IATA 2 ký tự (WN)',
    carrier_name      VARCHAR(64)  NOT NULL,
    business_model    VARCHAR(30)  NULL COMMENT 'Low-cost / Full-service / Regional',
    is_regional       TINYINT(1)   NOT NULL DEFAULT 0,
    in_ontime         TINYINT(1)   NOT NULL DEFAULT 0 COMMENT 'Có mặt trong nguồn On-Time',
    in_t100           TINYINT(1)   NOT NULL DEFAULT 0 COMMENT 'Có mặt trong nguồn T-100',
    in_db1b_operating TINYINT(1)   NOT NULL DEFAULT 0 COMMENT 'Có chặng khai thác trong DB1B',
    in_db1b_ticketed  TINYINT(1)   NOT NULL DEFAULT 0 COMMENT 'Có hành trình xuất vé trong DB1B',
    PRIMARY KEY (carrier_key),
    UNIQUE KEY uq_dim_carrier_code (carrier_code)
) ENGINE=InnoDB COMMENT='Chiều hãng bay';

-- ---------------------------------------------------------------------
-- A5. dim_airport – grain: 1 SÂN BAY
-- ---------------------------------------------------------------------
CREATE TABLE dim_airport (
    airport_key    SMALLINT     NOT NULL AUTO_INCREMENT,
    airport_code   CHAR(3)      NOT NULL COMMENT 'Mã IATA 3 ký tự (ABQ)',
    city           VARCHAR(64)  NULL COMMENT 'Thành phố, tiểu bang',
    state          VARCHAR(2)   NULL COMMENT 'Mã tiểu bang',
    city_market_id INT          NULL COMMENT 'Mã thị trường sân bay DOT',
    wac            SMALLINT     NULL COMMENT 'World Area Code',
    PRIMARY KEY (airport_key),
    UNIQUE KEY uq_dim_airport_code (airport_code)
) ENGINE=InnoDB COMMENT='Chiều sân bay (hợp nhất On-Time + T-100)';

-- ---------------------------------------------------------------------
-- A6. dim_route – grain: 1 ĐƯỜNG BAY CÓ HƯỚNG (origin → dest)
--     Nguồn: On-Time + T-100 (đủ khoảng cách distance_mi)
--     Ghi chú: DB1B có nhiều cặp O&D không nằm ở đây (không có chuyến khai thác
--     trực tiếp) nên các fact DB1B FK về dim_airport (origin_key/dest_key)
--     thay vì FK về dim_route.
-- ---------------------------------------------------------------------
CREATE TABLE dim_route (
    route_key     INT           NOT NULL AUTO_INCREMENT,
    route         CHAR(7)       NOT NULL COMMENT 'Khóa tự nhiên ABQ-AUS',
    origin_key    SMALLINT      NOT NULL COMMENT 'FK dim_airport (điểm đi)',
    dest_key      SMALLINT      NOT NULL COMMENT 'FK dim_airport (điểm đến)',
    origin_code   CHAR(3)       NOT NULL COMMENT 'Mã sân bay đi (denormalized cho BI)',
    dest_code     CHAR(3)       NOT NULL COMMENT 'Mã sân bay đến (denormalized cho BI)',
    market        VARCHAR(7)    NOT NULL COMMENT 'Thị trường O&D của đường bay thẳng',
    distance_mi   DECIMAL(8,1)  NULL COMMENT 'Khoảng cách (dặm)',
    distance_band VARCHAR(10)   NULL COMMENT 'Nhóm khoảng cách (≤100/101-500/501-1000/1001-1500/1501-2500/2501+)',
    PRIMARY KEY (route_key),
    UNIQUE KEY uq_dim_route (route),
    UNIQUE KEY uq_dim_route_od (origin_key, dest_key),
    CONSTRAINT fk_route_origin FOREIGN KEY (origin_key) REFERENCES dim_airport (airport_key),
    CONSTRAINT fk_route_dest   FOREIGN KEY (dest_key)   REFERENCES dim_airport (airport_key)
) ENGINE=InnoDB COMMENT='Chiều đường bay có hướng';

-- ---------------------------------------------------------------------
-- A7. dim_aircraft – grain: 1 SỐ ĐUÔI MÁY BAY (Tail_Number, của hãng WN)
-- ---------------------------------------------------------------------
CREATE TABLE dim_aircraft (
    aircraft_key            INT           NOT NULL AUTO_INCREMENT,
    tail_number             VARCHAR(10)   NOT NULL COMMENT 'Số đuôi máy bay (N1801U)',
    carrier_code            CHAR(2)       NOT NULL,
    first_flight_date       DATE          NULL COMMENT 'Chuyến đầu tiên trong năm dữ liệu',
    last_flight_date        DATE          NULL COMMENT 'Chuyến cuối cùng trong năm dữ liệu',
    n_flights               INT           NOT NULL DEFAULT 0 COMMENT 'Số chuyến theo lịch',
    n_completed             INT           NOT NULL DEFAULT 0 COMMENT 'Số chuyến hoàn thành',
    avg_distance_mi         DECIMAL(10,4) NULL COMMENT 'Quãng đường bình quân/chuyến',
    flights_per_active_day  DECIMAL(6,2)  NULL COMMENT 'Số chuyến/ngày hoạt động',
    PRIMARY KEY (aircraft_key),
    UNIQUE KEY uq_dim_aircraft_tail (tail_number, carrier_code)
) ENGINE=InnoDB COMMENT='Chiều máy bay (từ Tail_Number On-Time)';

-- ---------------------------------------------------------------------
-- A8. dim_daypart – grain: 1 KHUNG GIỜ TRONG NGÀY (4 dòng, tạo tĩnh)
-- ---------------------------------------------------------------------
CREATE TABLE dim_daypart (
    daypart_key   TINYINT      NOT NULL AUTO_INCREMENT,
    daypart_code  VARCHAR(20)  NOT NULL COMMENT 'Khóa tự nhiên morning_06_11/afternoon_12_17/evening_18_23/night_00_05',
    daypart_name  VARCHAR(20)  NOT NULL COMMENT 'Morning/Afternoon/Evening/Night',
    label_vi      VARCHAR(30)  NOT NULL COMMENT 'Nhãn tiếng Anh+giờ: Morning 06-11',
    hour_start    TINYINT      NOT NULL COMMENT 'Giờ bắt đầu (0-23)',
    hour_end      TINYINT      NOT NULL COMMENT 'Giờ kết thúc (độc quyền)',
    sort_order    TINYINT      NOT NULL COMMENT 'Thứ tự hiển thị theo ngày',
    PRIMARY KEY (daypart_key),
    UNIQUE KEY uq_dim_daypart_code (daypart_code)
) ENGINE=InnoDB COMMENT='Chiều khung giờ trong ngày (turnaround)';

-- ---------------------------------------------------------------------
-- A9. dim_delay_cause – grain: 1 NHÓM NGUYÊN NHÂN TRỄ (5 nhóm BTS)
--     Không FK từ fact (fact lưu 5 cột phút trễ) – bảng này là lookup
--     khi UNPIVOT sang dạng dòng (xem mart_delay_cause_month)
-- ---------------------------------------------------------------------
CREATE TABLE dim_delay_cause (
    delay_cause_key TINYINT       NOT NULL AUTO_INCREMENT,
    cause_code      VARCHAR(20)   NOT NULL COMMENT 'Carrier/Weather/NAS/Security/LateAircraft',
    column_name     VARCHAR(30)   NOT NULL COMMENT 'Cột phút trễ tương ứng trong fact_ontime_route_month',
    answer_label_vi NVARCHAR(80)  NOT NULL COMMENT 'Nhãn quản trị tiếng Việt (khớp answer_delay_cause_share)',
    description_vi  NVARCHAR(255) NOT NULL,
    sort_order      TINYINT       NOT NULL,
    PRIMARY KEY (delay_cause_key),
    UNIQUE KEY uq_dim_delay_cause (cause_code)
) ENGINE=InnoDB COMMENT='Chiều nhóm nguyên nhân trễ (5 nhóm BTS)';

-- ---------------------------------------------------------------------
-- A10. dim_cancel_reason – grain: 1 LÝ DO HỦY CHUYẾN (mã A/B/C/D)
-- ---------------------------------------------------------------------
CREATE TABLE dim_cancel_reason (
    cancel_reason_key TINYINT      NOT NULL AUTO_INCREMENT,
    cancellation_code CHAR(1)      NOT NULL COMMENT 'A=Carrier, B=Weather, C=NAS, D=Security',
    reason            VARCHAR(20)  NOT NULL,
    PRIMARY KEY (cancel_reason_key),
    UNIQUE KEY uq_dim_cancel_reason (cancellation_code)
) ENGINE=InnoDB COMMENT='Chiều lý do hủy chuyến';

-- =====================================================================
-- PHẦN B · BẢNG SỰ KIỆN (FACT TABLES)
-- =====================================================================

-- ---------------------------------------------------------------------
-- B1. fact_ontime_route_month
--   GRAIN : 1 dòng = THÁNG × HÃNG × ĐƯỜNG BAY (On-Time, có hướng)
--   Nguồn: agg_ontime_carrier_route_month.csv (19.538 dòng)
--   Tất cả measures là số cộng dồn được (additive) trên grain này
-- ---------------------------------------------------------------------
CREATE TABLE fact_ontime_route_month (
    ontime_id                BIGINT       NOT NULL AUTO_INCREMENT,
    month_key                INT          NOT NULL COMMENT 'FK dim_month (yyyymm)',
    carrier_key              SMALLINT     NOT NULL COMMENT 'FK dim_carrier',
    route_key                INT          NOT NULL COMMENT 'FK dim_route',
    -- Số chuyến
    flights_scheduled        INT          NOT NULL DEFAULT 0,
    flights_cancelled        INT          NOT NULL DEFAULT 0,
    flights_diverted         INT          NOT NULL DEFAULT 0,
    flights_completed        INT          NOT NULL DEFAULT 0,
    -- Trễ >=15 phút (chuẩn DOT)
    dep_del15_count          INT          NOT NULL DEFAULT 0,
    arr_del15_count          INT          NOT NULL DEFAULT 0,
    -- Phút trễ (chỉ tính phần dương)
    arr_delay_pos_min        DECIMAL(14,1) NOT NULL DEFAULT 0,
    dep_delay_pos_min        DECIMAL(14,1) NOT NULL DEFAULT 0,
    -- Phút trễ theo 5 nhóm nguyên nhân BTS
    delay_carrier_min        DECIMAL(14,1) NOT NULL DEFAULT 0,
    delay_weather_min        DECIMAL(14,1) NOT NULL DEFAULT 0,
    delay_nas_min            DECIMAL(14,1) NOT NULL DEFAULT 0,
    delay_security_min       DECIMAL(14,1) NOT NULL DEFAULT 0,
    delay_late_aircraft_min  DECIMAL(14,1) NOT NULL DEFAULT 0,
    -- Số chuyến hủy theo lý do
    cancel_carrier           INT          NOT NULL DEFAULT 0,
    cancel_weather           INT          NOT NULL DEFAULT 0,
    cancel_nas               INT          NOT NULL DEFAULT 0,
    cancel_security          INT          NOT NULL DEFAULT 0,
    -- Taxi / thời gian bay (tổng phút)
    taxi_out_sum_min         DECIMAL(14,1) NOT NULL DEFAULT 0,
    taxi_in_sum_min          DECIMAL(14,1) NOT NULL DEFAULT 0,
    crs_elapsed_sum_min      DECIMAL(14,1) NOT NULL DEFAULT 0,
    actual_elapsed_sum_min   DECIMAL(14,1) NOT NULL DEFAULT 0,
    -- Quay đầu máy bay (turnaround) trên đường bay
    turn_n                   INT          NOT NULL DEFAULT 0 COMMENT 'Số lượt quay đầu hợp lệ',
    turn_over_sched_n        INT          NOT NULL DEFAULT 0 COMMENT 'Số lượt vượt lịch quay đầu',
    turn_sched_sum_min       DECIMAL(14,1) NOT NULL DEFAULT 0,
    turn_actual_sum_min      DECIMAL(14,1) NOT NULL DEFAULT 0,
    gate_return_n            INT          NOT NULL DEFAULT 0 COMMENT 'Số chuyến quay lại cổng',
    total_add_gtime_sum_min  DECIMAL(14,1) NOT NULL DEFAULT 0,
    PRIMARY KEY (ontime_id),
    UNIQUE KEY uq_fact_ontime_grain (month_key, carrier_key, route_key),
    CONSTRAINT fk_ontime_month   FOREIGN KEY (month_key)   REFERENCES dim_month (month_key),
    CONSTRAINT fk_ontime_carrier FOREIGN KEY (carrier_key) REFERENCES dim_carrier (carrier_key),
    CONSTRAINT fk_ontime_route   FOREIGN KEY (route_key)   REFERENCES dim_route (route_key)
) ENGINE=InnoDB COMMENT='Fact vận hành On-Time – grain tháng × hãng × đường bay';

-- ---------------------------------------------------------------------
-- B2. fact_capacity_route_month
--   GRAIN : 1 dòng = THÁNG × HÃNG × ĐƯỜNG BAY (T-100, service class F)
--   Nguồn: agg_t100_carrier_route_month.csv (19.538 dòng)
--   load_factor KHÔNG lưu (tính lại = rpm/asm trong mart, tránh phóng đại khi cộng dồn)
-- ---------------------------------------------------------------------
CREATE TABLE fact_capacity_route_month (
    capacity_id           BIGINT        NOT NULL AUTO_INCREMENT,
    month_key             INT           NOT NULL,
    carrier_key           SMALLINT      NOT NULL,
    route_key             INT           NOT NULL,
    departures_scheduled  DECIMAL(10,1) NOT NULL DEFAULT 0,
    departures_performed  DECIMAL(10,1) NOT NULL DEFAULT 0 COMMENT 'Số chuyến cất cánh thực tế',
    seats                 DECIMAL(12,1) NOT NULL DEFAULT 0 COMMENT 'Số ghế cung ứng',
    passengers            DECIMAL(12,1) NOT NULL DEFAULT 0,
    freight_lbs           DECIMAL(16,2) NOT NULL DEFAULT 0,
    mail_lbs              DECIMAL(16,2) NOT NULL DEFAULT 0,
    asm                   DECIMAL(20,2) NOT NULL DEFAULT 0 COMMENT 'Available Seat Miles = ghế × dặm',
    rpm                   DECIMAL(20,2) NOT NULL DEFAULT 0 COMMENT 'Revenue Passenger Miles = khách × dặm',
    ramp_to_ramp_min      DECIMAL(16,1) NOT NULL DEFAULT 0,
    air_time_min          DECIMAL(16,1) NOT NULL DEFAULT 0,
    n_aircraft_types      INT           NOT NULL DEFAULT 0,
    PRIMARY KEY (capacity_id),
    UNIQUE KEY uq_fact_capacity_grain (month_key, carrier_key, route_key),
    CONSTRAINT fk_cap_month   FOREIGN KEY (month_key)   REFERENCES dim_month (month_key),
    CONSTRAINT fk_cap_carrier FOREIGN KEY (carrier_key) REFERENCES dim_carrier (carrier_key),
    CONSTRAINT fk_cap_route   FOREIGN KEY (route_key)   REFERENCES dim_route (route_key)
) ENGINE=InnoDB COMMENT='Fact năng lực & tải ghế T-100 – grain tháng × hãng × đường bay';

-- ---------------------------------------------------------------------
-- B3. fact_turnaround_airport_daypart_month
--   GRAIN : 1 dòng = THÁNG × HÃNG × SÂN BAY (nơi xuất phát) × KHUNG GIỜ
--   Nguồn: agg_turnaround_airport_daypart_month.csv (3.863 dòng)
--   Phục vụ drill-down Hãng → Sân bay → Khung giờ (câu hỏi quản trị #2)
-- ---------------------------------------------------------------------
CREATE TABLE fact_turnaround_airport_daypart_month (
    turnaround_id             BIGINT        NOT NULL AUTO_INCREMENT,
    month_key                 INT           NOT NULL,
    carrier_key               SMALLINT      NOT NULL,
    airport_key               SMALLINT      NOT NULL COMMENT 'Sân bay của chuyến xuất phát (lượt quay đầu)',
    daypart_key               TINYINT       NOT NULL,
    turn_n                    INT           NOT NULL DEFAULT 0,
    turn_sched_sum_min        DECIMAL(14,1) NOT NULL DEFAULT 0,
    turn_actual_sum_min       DECIMAL(14,1) NOT NULL DEFAULT 0,
    turn_excess_sum_min       DECIMAL(14,1) NOT NULL DEFAULT 0 COMMENT 'Tổng phút vượt lịch quay đầu',
    turn_over_sched_n         INT           NOT NULL DEFAULT 0,
    turn_after_late_inbound_n INT           NOT NULL DEFAULT 0 COMMENT 'Lượt quay đầu ngay sau chuyến đến muộn (hiệu ứng dây chuyền)',
    dep_delay_sum_min         DECIMAL(14,1) NOT NULL DEFAULT 0,
    PRIMARY KEY (turnaround_id),
    UNIQUE KEY uq_fact_turnaround_grain (month_key, carrier_key, airport_key, daypart_key),
    CONSTRAINT fk_ta_month   FOREIGN KEY (month_key)   REFERENCES dim_month (month_key),
    CONSTRAINT fk_ta_carrier FOREIGN KEY (carrier_key) REFERENCES dim_carrier (carrier_key),
    CONSTRAINT fk_ta_airport FOREIGN KEY (airport_key) REFERENCES dim_airport (airport_key),
    CONSTRAINT fk_ta_daypart FOREIGN KEY (daypart_key) REFERENCES dim_daypart (daypart_key)
) ENGINE=InnoDB COMMENT='Fact quay đầu máy bay – grain tháng × hãng × sân bay × khung giờ';

-- ---------------------------------------------------------------------
-- B4. fact_fare_segment_quarter
--   GRAIN : 1 dòng = QUÝ × HÃNG XUẤT VÉ × HÃNG KHAI THÁC × CẶP SÂN BAY (chặng)
--   Nguồn: agg_db1b_segment_quarter.csv (12.335 dòng)
--   Doanh thu hành trình đã phân bổ về chặng theo tỷ lệ dặm; mẫu 10% vé
--   → pax_est = pax_sample × 10; revenue_est_usd = doanh thu mẫu × 10
-- ---------------------------------------------------------------------
CREATE TABLE fact_fare_segment_quarter (
    fare_segment_id     BIGINT        NOT NULL AUTO_INCREMENT,
    quarter_key         INT           NOT NULL COMMENT 'FK dim_quarter (yyyyq)',
    tk_carrier_key      SMALLINT      NOT NULL COMMENT 'FK dim_carrier – hãng xuất vé',
    op_carrier_key      SMALLINT      NOT NULL COMMENT 'FK dim_carrier – hãng khai thác chặng',
    origin_key          SMALLINT      NOT NULL COMMENT 'FK dim_airport – sân bay đi của chặng',
    dest_key            SMALLINT      NOT NULL COMMENT 'FK dim_airport – sân bay đến của chặng',
    pax_sample          INT           NOT NULL DEFAULT 0 COMMENT 'Khách trong mẫu 10%',
    seg_revenue_sample  DECIMAL(16,6) NOT NULL DEFAULT 0 COMMENT 'Doanh thu mẫu phân bổ về chặng (USD)',
    pax_miles_sample    DECIMAL(16,6) NOT NULL DEFAULT 0 COMMENT 'Khách-dặm mẫu của chặng',
    pax_est             DECIMAL(14,2) NOT NULL DEFAULT 0 COMMENT 'Khách ước tính = pax_sample × 10',
    revenue_est_usd     DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT 'Doanh thu ước tính (USD)',
    PRIMARY KEY (fare_segment_id),
    UNIQUE KEY uq_fact_fare_segment_grain (quarter_key, tk_carrier_key, op_carrier_key, origin_key, dest_key),
    CONSTRAINT fk_fs_quarter FOREIGN KEY (quarter_key)    REFERENCES dim_quarter (quarter_key),
    CONSTRAINT fk_fs_tk      FOREIGN KEY (tk_carrier_key) REFERENCES dim_carrier (carrier_key),
    CONSTRAINT fk_fs_op      FOREIGN KEY (op_carrier_key) REFERENCES dim_carrier (carrier_key),
    CONSTRAINT fk_fs_origin  FOREIGN KEY (origin_key)     REFERENCES dim_airport (airport_key),
    CONSTRAINT fk_fs_dest    FOREIGN KEY (dest_key)       REFERENCES dim_airport (airport_key)
) ENGINE=InnoDB COMMENT='Fact doanh thu vé theo chặng (DB1B) – grain quý × cặp hãng × chặng';

-- ---------------------------------------------------------------------
-- B5. fact_fare_market_quarter
--   GRAIN : 1 dòng = QUÝ × HÃNG XUẤT VÉ ĐẦU × THỊ TRƯỜNG O&D × KHỨ HỒI × THẲNG
--   Nguồn: agg_db1b_market_quarter.csv (63.087 dòng)
--   Phục vụ phân tích giá vé bình quân một chiều theo thị trường
-- ---------------------------------------------------------------------
CREATE TABLE fact_fare_market_quarter (
    fare_market_id    BIGINT        NOT NULL AUTO_INCREMENT,
    quarter_key       INT           NOT NULL,
    carrier_key       SMALLINT      NOT NULL COMMENT 'FK dim_carrier – hãng xuất vé đầu tiên',
    origin_key        SMALLINT      NOT NULL COMMENT 'FK dim_airport – điểm đầu hành trình',
    dest_key          SMALLINT      NOT NULL COMMENT 'FK dim_airport – điểm cuối hành trình',
    is_round_trip     TINYINT(1)    NOT NULL COMMENT '1 = vé khứ hồi (dimension thu gọn)',
    is_nonstop        TINYINT(1)    NOT NULL COMMENT '1 = hành trình bay thẳng (dimension thu gọn)',
    itineraries       INT           NOT NULL DEFAULT 0 COMMENT 'Số hành trình trong mẫu',
    pax_sample        INT           NOT NULL DEFAULT 0,
    rev_sample        DECIMAL(16,6) NOT NULL DEFAULT 0 COMMENT 'Doanh thu một chiều trong mẫu (USD)',
    pax_est           DECIMAL(14,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (fare_market_id),
    UNIQUE KEY uq_fact_fare_market_grain (quarter_key, carrier_key, origin_key, dest_key, is_round_trip, is_nonstop),
    CONSTRAINT fk_fm_quarter FOREIGN KEY (quarter_key)   REFERENCES dim_quarter (quarter_key),
    CONSTRAINT fk_fm_carrier FOREIGN KEY (carrier_key)   REFERENCES dim_carrier (carrier_key),
    CONSTRAINT fk_fm_origin  FOREIGN KEY (origin_key)    REFERENCES dim_airport (airport_key),
    CONSTRAINT fk_fm_dest    FOREIGN KEY (dest_key)      REFERENCES dim_airport (airport_key)
) ENGINE=InnoDB COMMENT='Fact giá vé thị trường O&D (DB1B) – grain quý × thị trường × loại vé';

-- ---------------------------------------------------------------------
-- B6. fact_fare_class_quarter
--   GRAIN : 1 dòng = QUÝ × HÃNG KHAI THÁC × HẠNG VÉ
--   Nguồn: agg_db1b_fareclass_quarter.csv (8 dòng)
-- ---------------------------------------------------------------------
CREATE TABLE fact_fare_class_quarter (
    fare_class_id       BIGINT        NOT NULL AUTO_INCREMENT,
    quarter_key         INT           NOT NULL,
    op_carrier_key      SMALLINT      NOT NULL,
    fare_class          CHAR(1)       NOT NULL COMMENT 'Hạng vé (dimension thu gọn: X, Y, …)',
    pax_sample          INT           NOT NULL DEFAULT 0,
    seg_revenue_sample  DECIMAL(16,6) NOT NULL DEFAULT 0,
    PRIMARY KEY (fare_class_id),
    UNIQUE KEY uq_fact_fare_class_grain (quarter_key, op_carrier_key, fare_class),
    CONSTRAINT fk_fc_quarter FOREIGN KEY (quarter_key)    REFERENCES dim_quarter (quarter_key),
    CONSTRAINT fk_fc_carrier FOREIGN KEY (op_carrier_key) REFERENCES dim_carrier (carrier_key)
) ENGINE=InnoDB COMMENT='Fact cơ cấu hạng vé (DB1B) – grain quý × hãng × hạng vé';

-- =====================================================================
-- PHẦN C · DATA MART (VIEWS) – lớp serving cho dashboard TV3
--   Tất cả KPI tính từ fact + dim, KHÔNG lưu cột tỉ lệ trong fact
--   (công thức khớp data dictionary Nhiệm vụ 1 – sheet KPI_cong_thuc)
-- =====================================================================

-- ---------------------------------------------------------------------
-- C1. mart_carrier_month – GRAIN: THÁNG × HÃNG (12 dòng)
--   Vận hành (On-Time) + năng lực/tải ghế (T-100) + toàn bộ KPI
-- ---------------------------------------------------------------------
CREATE VIEW mart_carrier_month AS
SELECT
    m.year,
    m.quarter,
    m.month,
    m.month_name,
    c.carrier_code                                     AS carrier,
    SUM(o.flights_scheduled)                           AS flights_scheduled,
    SUM(o.flights_cancelled)                           AS flights_cancelled,
    SUM(o.flights_diverted)                            AS flights_diverted,
    SUM(o.flights_completed)                           AS flights_completed,
    SUM(o.dep_del15_count)                             AS dep_del15_count,
    SUM(o.arr_del15_count)                             AS arr_del15_count,
    SUM(o.arr_delay_pos_min)                           AS arr_delay_pos_min,
    SUM(o.dep_delay_pos_min)                           AS dep_delay_pos_min,
    SUM(o.delay_carrier_min)                           AS delay_carrier_min,
    SUM(o.delay_weather_min)                           AS delay_weather_min,
    SUM(o.delay_nas_min)                               AS delay_nas_min,
    SUM(o.delay_security_min)                          AS delay_security_min,
    SUM(o.delay_late_aircraft_min)                     AS delay_late_aircraft_min,
    SUM(o.cancel_carrier)                              AS cancel_carrier,
    SUM(o.cancel_weather)                              AS cancel_weather,
    SUM(o.cancel_nas)                                  AS cancel_nas,
    SUM(o.cancel_security)                             AS cancel_security,
    SUM(o.taxi_out_sum_min)                            AS taxi_out_sum_min,
    SUM(o.taxi_in_sum_min)                             AS taxi_in_sum_min,
    SUM(o.crs_elapsed_sum_min)                         AS crs_elapsed_sum_min,
    SUM(o.actual_elapsed_sum_min)                      AS actual_elapsed_sum_min,
    SUM(o.turn_n)                                      AS turn_n,
    SUM(o.turn_over_sched_n)                           AS turn_over_sched_n,
    SUM(o.turn_sched_sum_min)                          AS turn_sched_sum_min,
    SUM(o.turn_actual_sum_min)                         AS turn_actual_sum_min,
    SUM(o.gate_return_n)                               AS gate_return_n,
    SUM(o.total_add_gtime_sum_min)                     AS total_add_gtime_sum_min,
    SUM(t.departures_scheduled)                        AS departures_scheduled,
    SUM(t.departures_performed)                        AS departures_performed,
    SUM(t.seats)                                       AS seats,
    SUM(t.passengers)                                  AS passengers,
    SUM(t.asm)                                         AS asm,
    SUM(t.rpm)                                         AS rpm,
    SUM(t.ramp_to_ramp_min)                            AS ramp_to_ramp_min,
    SUM(t.air_time_min)                                AS air_time_min,
    CASE WHEN SUM(o.flights_scheduled) IS NOT NULL AND SUM(t.departures_performed) IS NOT NULL
         THEN 'ontime+t100' END                        AS source_presence,
    -- KPI (mẫu số theo data dictionary: chuyến hoàn thành / chuyến theo lịch / lượt quay đầu)
    SUM(o.flights_cancelled)  / NULLIF(SUM(o.flights_scheduled), 0) AS cancel_rate,
    SUM(o.flights_diverted)   / NULLIF(SUM(o.flights_scheduled), 0) AS divert_rate,
    SUM(o.arr_del15_count)    / NULLIF(SUM(o.flights_completed), 0) AS arr_del15_rate,
    SUM(o.dep_del15_count)    / NULLIF(SUM(o.flights_completed), 0) AS dep_del15_rate,
    (SUM(o.delay_carrier_min) + SUM(o.delay_weather_min) + SUM(o.delay_nas_min)
     + SUM(o.delay_security_min) + SUM(o.delay_late_aircraft_min))  AS delay_cause_total_min,
    SUM(o.delay_carrier_min)       / NULLIF(SUM(o.delay_carrier_min) + SUM(o.delay_weather_min) + SUM(o.delay_nas_min)
                                           + SUM(o.delay_security_min) + SUM(o.delay_late_aircraft_min), 0) AS delay_carrier_share,
    SUM(o.delay_weather_min)       / NULLIF(SUM(o.delay_carrier_min) + SUM(o.delay_weather_min) + SUM(o.delay_nas_min)
                                           + SUM(o.delay_security_min) + SUM(o.delay_late_aircraft_min), 0) AS delay_weather_share,
    SUM(o.delay_nas_min)           / NULLIF(SUM(o.delay_carrier_min) + SUM(o.delay_weather_min) + SUM(o.delay_nas_min)
                                           + SUM(o.delay_security_min) + SUM(o.delay_late_aircraft_min), 0) AS delay_nas_share,
    SUM(o.delay_security_min)      / NULLIF(SUM(o.delay_carrier_min) + SUM(o.delay_weather_min) + SUM(o.delay_nas_min)
                                           + SUM(o.delay_security_min) + SUM(o.delay_late_aircraft_min), 0) AS delay_security_share,
    SUM(o.delay_late_aircraft_min) / NULLIF(SUM(o.delay_carrier_min) + SUM(o.delay_weather_min) + SUM(o.delay_nas_min)
                                           + SUM(o.delay_security_min) + SUM(o.delay_late_aircraft_min), 0) AS delay_late_aircraft_share,
    SUM(o.arr_delay_pos_min)   / NULLIF(SUM(o.flights_completed), 0) AS avg_arr_delay_per_completed_min,
    SUM(t.passengers)          / NULLIF(SUM(t.seats), 0)            AS load_factor,
    SUM(o.turn_sched_sum_min)  / NULLIF(SUM(o.turn_n), 0)            AS avg_turn_sched_min,
    SUM(o.turn_actual_sum_min) / NULLIF(SUM(o.turn_n), 0)            AS avg_turn_actual_min,
    SUM(o.turn_over_sched_n)   / NULLIF(SUM(o.turn_n), 0)            AS turn_over_sched_rate,
    SUM(o.gate_return_n)       / NULLIF(SUM(o.flights_scheduled), 0) AS gate_return_rate
FROM fact_ontime_route_month o
JOIN dim_month   m ON m.month_key   = o.month_key
JOIN dim_carrier c ON c.carrier_key = o.carrier_key
LEFT JOIN fact_capacity_route_month t
       ON t.month_key = o.month_key AND t.carrier_key = o.carrier_key AND t.route_key = o.route_key
GROUP BY m.year, m.quarter, m.month, m.month_name, c.carrier_code;

-- ---------------------------------------------------------------------
-- C2. mart_route_month – GRAIN: THÁNG × HÃNG × ĐƯỜNG BAY (19.538 dòng)
-- ---------------------------------------------------------------------
CREATE VIEW mart_route_month AS
SELECT
    m.year,
    m.quarter,
    m.month,
    c.carrier_code   AS carrier,
    rt.origin_code   AS origin,
    rt.dest_code     AS dest,
    rt.route,
    rt.distance_mi,
    o.flights_scheduled, o.flights_cancelled, o.flights_diverted, o.flights_completed,
    o.dep_del15_count, o.arr_del15_count,
    o.arr_delay_pos_min, o.dep_delay_pos_min,
    o.delay_carrier_min, o.delay_weather_min, o.delay_nas_min, o.delay_security_min, o.delay_late_aircraft_min,
    o.cancel_carrier, o.cancel_weather, o.cancel_nas, o.cancel_security,
    o.taxi_out_sum_min, o.taxi_in_sum_min, o.crs_elapsed_sum_min, o.actual_elapsed_sum_min,
    o.turn_n, o.turn_over_sched_n, o.turn_sched_sum_min, o.turn_actual_sum_min,
    o.gate_return_n, o.total_add_gtime_sum_min,
    t.departures_scheduled, t.departures_performed, t.seats, t.passengers,
    t.asm, t.rpm, t.ramp_to_ramp_min, t.air_time_min,
    CASE WHEN t.capacity_id IS NOT NULL THEN 'ontime+t100' ELSE 'ontime_only' END AS source_presence,
    o.flights_cancelled  / NULLIF(o.flights_scheduled, 0) AS cancel_rate,
    o.flights_diverted   / NULLIF(o.flights_scheduled, 0) AS divert_rate,
    o.arr_del15_count    / NULLIF(o.flights_completed, 0) AS arr_del15_rate,
    o.dep_del15_count    / NULLIF(o.flights_completed, 0) AS dep_del15_rate,
    (o.delay_carrier_min + o.delay_weather_min + o.delay_nas_min
     + o.delay_security_min + o.delay_late_aircraft_min)  AS delay_cause_total_min,
    o.delay_carrier_min       / NULLIF(o.delay_carrier_min + o.delay_weather_min + o.delay_nas_min
                                     + o.delay_security_min + o.delay_late_aircraft_min, 0) AS delay_carrier_share,
    o.delay_weather_min       / NULLIF(o.delay_carrier_min + o.delay_weather_min + o.delay_nas_min
                                     + o.delay_security_min + o.delay_late_aircraft_min, 0) AS delay_weather_share,
    o.delay_nas_min           / NULLIF(o.delay_carrier_min + o.delay_weather_min + o.delay_nas_min
                                     + o.delay_security_min + o.delay_late_aircraft_min, 0) AS delay_nas_share,
    o.delay_security_min      / NULLIF(o.delay_carrier_min + o.delay_weather_min + o.delay_nas_min
                                     + o.delay_security_min + o.delay_late_aircraft_min, 0) AS delay_security_share,
    o.delay_late_aircraft_min / NULLIF(o.delay_carrier_min + o.delay_weather_min + o.delay_nas_min
                                     + o.delay_security_min + o.delay_late_aircraft_min, 0) AS delay_late_aircraft_share,
    o.arr_delay_pos_min   / NULLIF(o.flights_completed, 0) AS avg_arr_delay_per_completed_min,
    t.passengers          / NULLIF(t.seats, 0)            AS load_factor,
    o.turn_sched_sum_min  / NULLIF(o.turn_n, 0)            AS avg_turn_sched_min,
    o.turn_actual_sum_min / NULLIF(o.turn_n, 0)            AS avg_turn_actual_min,
    o.turn_over_sched_n   / NULLIF(o.turn_n, 0)            AS turn_over_sched_rate,
    o.gate_return_n       / NULLIF(o.flights_scheduled, 0) AS gate_return_rate
FROM fact_ontime_route_month o
JOIN dim_month   m  ON m.month_key   = o.month_key
JOIN dim_carrier c  ON c.carrier_key = o.carrier_key
JOIN dim_route   rt ON rt.route_key  = o.route_key
LEFT JOIN fact_capacity_route_month t
       ON t.month_key = o.month_key AND t.carrier_key = o.carrier_key AND t.route_key = o.route_key;

-- ---------------------------------------------------------------------
-- C3. mart_carrier_quarter_rask – GRAIN: QUÝ × HÃNG (4 dòng)
--   T-100 (năng lực) + DB1B (doanh thu ước tính) → RASK, Yield, PLF
--   RASK chỉ có ý nghĩa khi complete_quarter = 1 (T-100 đủ 3 tháng của quý)
-- ---------------------------------------------------------------------
CREATE VIEW mart_carrier_quarter_rask AS
WITH t100_q AS (
    SELECT q.year, q.quarter, c.carrier_code,
           SUM(t.seats) AS seats, SUM(t.passengers) AS passengers,
           SUM(t.asm) AS asm, SUM(t.rpm) AS rpm,
           SUM(t.departures_performed) AS departures_performed,
           COUNT(DISTINCT t.month_key) AS months_in_t100
    FROM fact_capacity_route_month t
    JOIN dim_month   m ON m.month_key   = t.month_key
    JOIN dim_quarter q ON q.year = m.year AND q.quarter = m.quarter
    JOIN dim_carrier c ON c.carrier_key = t.carrier_key
    GROUP BY q.year, q.quarter, c.carrier_code
),
db1b_q AS (
    SELECT q.year, q.quarter, c.carrier_code,
           SUM(f.pax_est) AS pax_est, SUM(f.revenue_est_usd) AS revenue_est_usd,
           SUM(f.seg_revenue_sample) AS seg_revenue_sample, SUM(f.pax_miles_sample) AS pax_miles_sample
    FROM fact_fare_segment_quarter f
    JOIN dim_quarter q ON q.quarter_key = f.quarter_key
    JOIN dim_carrier c ON c.carrier_key = f.op_carrier_key
    GROUP BY q.year, q.quarter, c.carrier_code
)
SELECT
    COALESCE(a.year, b.year)                                  AS year,
    COALESCE(a.quarter, b.quarter)                            AS quarter,
    COALESCE(a.carrier_code, b.carrier_code)                  AS carrier,
    a.seats, a.passengers, a.asm, a.rpm, a.departures_performed, a.months_in_t100,
    b.pax_est, b.revenue_est_usd, b.seg_revenue_sample, b.pax_miles_sample,
    CASE WHEN a.year IS NOT NULL AND b.year IS NOT NULL THEN 't100+db1b'
         WHEN a.year IS NOT NULL THEN 't100_only'
         ELSE 'db1b_only' END                                 AS source_presence,
    CASE WHEN a.months_in_t100 = 3 THEN 1 ELSE 0 END          AS complete_quarter,
    a.passengers / NULLIF(a.seats, 0)                                  AS load_factor,
    CASE WHEN a.months_in_t100 = 3
         THEN b.revenue_est_usd / NULLIF(a.asm, 0) * 100 END  AS rask_cents,
    b.seg_revenue_sample / NULLIF(b.pax_miles_sample, 0) * 100 AS yield_cents,
    b.pax_est / NULLIF(a.passengers, 0)                       AS db1b_pax_to_t100_pax
FROM t100_q a
LEFT JOIN db1b_q b ON b.year = a.year AND b.quarter = a.quarter AND b.carrier_code = a.carrier_code
UNION ALL
SELECT
    b.year, b.quarter, b.carrier_code,
    NULL, NULL, NULL, NULL, NULL, NULL,
    b.pax_est, b.revenue_est_usd, b.seg_revenue_sample, b.pax_miles_sample,
    'db1b_only', 0, NULL, NULL,
    b.seg_revenue_sample / NULLIF(b.pax_miles_sample, 0) * 100 AS yield_cents,
    NULL
FROM db1b_q b
LEFT JOIN t100_q a ON b.year = a.year AND b.quarter = a.quarter AND b.carrier_code = a.carrier_code
WHERE a.year IS NULL;

-- ---------------------------------------------------------------------
-- C4. mart_route_quarter_rask – GRAIN: QUÝ × HÃNG × ĐƯỜNG BAY (12.336 dòng)
--   FULL OUTER JOIN (emulate bằng UNION ALL) T-100 ↔ DB1B theo cặp sân bay
-- ---------------------------------------------------------------------
CREATE VIEW mart_route_quarter_rask AS
WITH t100_q AS (
    SELECT q.year, q.quarter, c.carrier_code, rt.origin_code, rt.dest_code,
           SUM(t.seats) AS seats, SUM(t.passengers) AS passengers,
           SUM(t.asm) AS asm, SUM(t.rpm) AS rpm,
           SUM(t.departures_performed) AS departures_performed,
           COUNT(DISTINCT t.month_key) AS months_in_t100
    FROM fact_capacity_route_month t
    JOIN dim_month   m  ON m.month_key   = t.month_key
    JOIN dim_quarter q  ON q.year = m.year AND q.quarter = m.quarter
    JOIN dim_carrier c  ON c.carrier_key = t.carrier_key
    JOIN dim_route   rt ON rt.route_key  = t.route_key
    GROUP BY q.year, q.quarter, c.carrier_code, rt.origin_code, rt.dest_code
),
db1b_q AS (
    SELECT q.year, q.quarter, c.carrier_code, ao.airport_code AS origin_code, ad.airport_code AS dest_code,
           SUM(f.pax_est) AS pax_est, SUM(f.revenue_est_usd) AS revenue_est_usd,
           SUM(f.seg_revenue_sample) AS seg_revenue_sample, SUM(f.pax_miles_sample) AS pax_miles_sample
    FROM fact_fare_segment_quarter f
    JOIN dim_quarter q  ON q.quarter_key  = f.quarter_key
    JOIN dim_carrier c  ON c.carrier_key  = f.op_carrier_key
    JOIN dim_airport ao ON ao.airport_key = f.origin_key
    JOIN dim_airport ad ON ad.airport_key = f.dest_key
    GROUP BY q.year, q.quarter, c.carrier_code, ao.airport_code, ad.airport_code
)
SELECT
    a.year, a.quarter, a.carrier_code AS carrier, a.origin_code AS origin, a.dest_code AS dest,
    a.seats, a.passengers, a.asm, a.rpm, a.departures_performed, a.months_in_t100,
    b.pax_est, b.revenue_est_usd, b.seg_revenue_sample, b.pax_miles_sample,
    CASE WHEN b.year IS NOT NULL THEN 't100+db1b' ELSE 't100_only' END AS source_presence,
    CASE WHEN a.months_in_t100 = 3 THEN 1 ELSE 0 END                   AS complete_quarter,
    a.passengers / NULLIF(a.seats, 0)                                  AS load_factor,
    CASE WHEN a.months_in_t100 = 3
         THEN b.revenue_est_usd / NULLIF(a.asm, 0) * 100 END           AS rask_cents,
    b.seg_revenue_sample / NULLIF(b.pax_miles_sample, 0) * 100         AS yield_cents,
    b.pax_est / NULLIF(a.passengers, 0)                                AS db1b_pax_to_t100_pax
FROM t100_q a
LEFT JOIN db1b_q b
       ON b.year = a.year AND b.quarter = a.quarter AND b.carrier_code = a.carrier_code
      AND b.origin_code = a.origin_code AND b.dest_code = a.dest_code
UNION ALL
SELECT
    b.year, b.quarter, b.carrier_code, b.origin_code, b.dest_code,
    NULL, NULL, NULL, NULL, NULL, NULL,
    b.pax_est, b.revenue_est_usd, b.seg_revenue_sample, b.pax_miles_sample,
    'db1b_only', 0, NULL, NULL,
    b.seg_revenue_sample / NULLIF(b.pax_miles_sample, 0) * 100,
    NULL
FROM db1b_q b
LEFT JOIN t100_q a
       ON b.year = a.year AND b.quarter = a.quarter AND b.carrier_code = a.carrier_code
      AND b.origin_code = a.origin_code AND b.dest_code = a.dest_code
WHERE a.year IS NULL;

-- ---------------------------------------------------------------------
-- C5. mart_delay_cause_month – GRAIN: THÁNG × NHÓM NGUYÊN NHÂN (60 dòng)
--   Dạng "tidy" cho biểu đồ stacked/100%; khớp answer_delay_cause_share
-- ---------------------------------------------------------------------
CREATE VIEW mart_delay_cause_month AS
SELECT
    m.year,
    m.month,
    c.carrier_code AS carrier,
    dc.cause_code,
    dc.answer_label_vi,
    SUM(d.delay_min) AS delay_min,
    SUM(d.delay_min) / NULLIF(SUM(SUM(d.delay_min)) OVER (PARTITION BY m.year, m.month, c.carrier_code), 0) AS share_of_month
FROM (
    SELECT month_key, carrier_key, delay_carrier_min       AS delay_min, 'delay_carrier_min'       AS column_name FROM fact_ontime_route_month
    UNION ALL
    SELECT month_key, carrier_key, delay_weather_min,      'delay_weather_min'      FROM fact_ontime_route_month
    UNION ALL
    SELECT month_key, carrier_key, delay_nas_min,          'delay_nas_min'          FROM fact_ontime_route_month
    UNION ALL
    SELECT month_key, carrier_key, delay_security_min,     'delay_security_min'     FROM fact_ontime_route_month
    UNION ALL
    SELECT month_key, carrier_key, delay_late_aircraft_min,'delay_late_aircraft_min' FROM fact_ontime_route_month
) d
JOIN dim_month   m  ON m.month_key   = d.month_key
JOIN dim_carrier c  ON c.carrier_key = d.carrier_key
JOIN dim_delay_cause dc ON dc.column_name = d.column_name
GROUP BY m.year, m.month, c.carrier_code, dc.cause_code, dc.answer_label_vi, dc.sort_order
ORDER BY m.year, m.month, dc.sort_order;

-- ---------------------------------------------------------------------
-- C6. mart_turnaround_daypart_month – GRAIN: THÁNG × KHUNG GIỜ (48 dòng)
--   KPI quay đầu theo khung giờ (khớp answer_turnaround_by_daypart khi
--   cộng dồn cả năm)
-- ---------------------------------------------------------------------
CREATE VIEW mart_turnaround_daypart_month AS
SELECT
    m.year,
    m.month,
    c.carrier_code AS carrier,
    dp.daypart_code,
    dp.daypart_name,
    dp.sort_order,
    SUM(f.turn_n)                    AS turn_n,
    SUM(f.turn_sched_sum_min)        / NULLIF(SUM(f.turn_n), 0) AS avg_turn_sched_min,
    SUM(f.turn_actual_sum_min)       / NULLIF(SUM(f.turn_n), 0) AS avg_turn_actual_min,
    SUM(f.turn_excess_sum_min)       / NULLIF(SUM(f.turn_n), 0) AS avg_turn_excess_min,
    SUM(f.turn_over_sched_n)         / NULLIF(SUM(f.turn_n), 0) AS turn_over_sched_rate,
    SUM(f.turn_after_late_inbound_n) / NULLIF(SUM(f.turn_n), 0) AS turn_after_late_inbound_rate,
    SUM(f.dep_delay_sum_min)         / NULLIF(SUM(f.turn_n), 0) AS avg_dep_delay_min
FROM fact_turnaround_airport_daypart_month f
JOIN dim_month   m  ON m.month_key   = f.month_key
JOIN dim_carrier c  ON c.carrier_key = f.carrier_key
JOIN dim_daypart dp ON dp.daypart_key = f.daypart_key
GROUP BY m.year, m.month, c.carrier_code, dp.daypart_code, dp.daypart_name, dp.sort_order
ORDER BY m.year, m.month, dp.sort_order;

-- ---------------------------------------------------------------------
-- C7. mart_turnaround_airport_month – GRAIN: THÁNG × SÂN BAY (1.284+ dòng)
--   Drill-down sân bay cho mục tiêu giảm 15% thời gian quay đầu
-- ---------------------------------------------------------------------
CREATE VIEW mart_turnaround_airport_month AS
SELECT
    m.year,
    m.month,
    c.carrier_code AS carrier,
    a.airport_code,
    a.city,
    SUM(f.turn_n)              AS turn_n,
    SUM(f.turn_sched_sum_min)  / NULLIF(SUM(f.turn_n), 0) AS avg_turn_sched_min,
    SUM(f.turn_actual_sum_min) / NULLIF(SUM(f.turn_n), 0) AS avg_turn_actual_min,
    SUM(f.turn_excess_sum_min) AS turn_excess_sum_min,
    SUM(f.turn_excess_sum_min) / NULLIF(SUM(f.turn_n), 0) AS avg_turn_excess_min,
    SUM(f.turn_over_sched_n)   / NULLIF(SUM(f.turn_n), 0) AS turn_over_sched_rate,
    SUM(f.turn_after_late_inbound_n) AS turn_after_late_inbound_n,
    SUM(f.dep_delay_sum_min)   / NULLIF(SUM(f.turn_n), 0) AS avg_dep_delay_min
FROM fact_turnaround_airport_daypart_month f
JOIN dim_month   m ON m.month_key   = f.month_key
JOIN dim_carrier c ON c.carrier_key = f.carrier_key
JOIN dim_airport a ON a.airport_key = f.airport_key
GROUP BY m.year, m.month, c.carrier_code, a.airport_code, a.city
ORDER BY m.year, m.month, SUM(f.turn_excess_sum_min) DESC;

-- ---------------------------------------------------------------------
-- C8. mart_fare_market_quarter – GRAIN: QUÝ × THỊ TRƯỜNG O&D × LOẠI VÉ
--   Giá vé bình quân một chiều = rev_sample / pax_sample
-- ---------------------------------------------------------------------
CREATE VIEW mart_fare_market_quarter AS
SELECT
    q.year,
    q.quarter,
    c.carrier_code AS carrier,
    ao.airport_code AS origin,
    ad.airport_code AS dest,
    CONCAT(ao.airport_code, '-', ad.airport_code) AS market,
    f.is_round_trip,
    f.is_nonstop,
    SUM(f.itineraries) AS itineraries,
    SUM(f.pax_sample)  AS pax_sample,
    SUM(f.rev_sample)  AS rev_sample_usd,
    SUM(f.pax_est)     AS pax_est,
    SUM(f.rev_sample) / NULLIF(SUM(f.pax_sample), 0) AS avg_one_way_fare_usd
FROM fact_fare_market_quarter f
JOIN dim_quarter q  ON q.quarter_key  = f.quarter_key
JOIN dim_carrier c  ON c.carrier_key  = f.carrier_key
JOIN dim_airport ao ON ao.airport_key = f.origin_key
JOIN dim_airport ad ON ad.airport_key = f.dest_key
GROUP BY q.year, q.quarter, c.carrier_code, ao.airport_code, ad.airport_code, f.is_round_trip, f.is_nonstop;

-- =====================================================================
-- PHẦN D · BẢNG ĐIỀU KHIỂN ETL & NHẬT KÝ KIỂM TRA (metadata)
-- =====================================================================

CREATE TABLE etl_run (
    run_id      INT          NOT NULL AUTO_INCREMENT,
    started_at  DATETIME     NOT NULL,
    finished_at DATETIME     NULL,
    status      VARCHAR(20)  NOT NULL COMMENT 'RUNNING/SUCCESS/FAILED',
    notes       VARCHAR(255) NULL,
    PRIMARY KEY (run_id)
) ENGINE=InnoDB COMMENT='Lịch sử các lần chạy ETL';

CREATE TABLE etl_load_log (
    log_id        BIGINT       NOT NULL AUTO_INCREMENT,
    run_id        INT          NOT NULL,
    target_table  VARCHAR(64)  NOT NULL,
    phase         VARCHAR(20)  NOT NULL COMMENT 'DIM/FACT',
    rows_read     INT          NOT NULL DEFAULT 0,
    rows_inserted INT          NOT NULL DEFAULT 0,
    rows_rejected INT          NOT NULL DEFAULT 0,
    duration_sec  DECIMAL(10,2) NULL,
    loaded_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (log_id),
    CONSTRAINT fk_log_run FOREIGN KEY (run_id) REFERENCES etl_run (run_id)
) ENGINE=InnoDB COMMENT='Nhật ký nạp từng bảng';

CREATE TABLE dq_check (
    check_id     BIGINT       NOT NULL AUTO_INCREMENT,
    run_id       INT          NULL,
    check_group  VARCHAR(50)  NOT NULL,
    check_name   VARCHAR(150) NOT NULL,
    status       VARCHAR(10)  NOT NULL COMMENT 'PASS/FAIL',
    metric_value VARCHAR(100) NULL,
    detail       VARCHAR(500) NULL,
    checked_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (check_id)
) ENGINE=InnoDB COMMENT='Kết quả kiểm tra tính nhất quán sau nạp';
