CREATE TABLE `CALENDAR` (
  `date_key` int PRIMARY KEY NOT NULL,
  `date` date UNIQUE NOT NULL,
  `year` smallint NOT NULL,
  `quarter` tinyint NOT NULL,
  `month` tinyint NOT NULL,
  `month_name` varchar(10) NOT NULL,
  `day_of_month` tinyint NOT NULL,
  `day_of_week` tinyint NOT NULL,
  `day_name` varchar(10) NOT NULL,
  `week_of_year` tinyint NOT NULL,
  `is_weekend` tinyint(1) NOT NULL,
  `is_us_federal_holiday` tinyint(1) NOT NULL,
  `season` varchar(10) NOT NULL
);

CREATE TABLE `MONTH` (
  `month_key` int PRIMARY KEY NOT NULL,
  `year` smallint NOT NULL,
  `quarter` tinyint NOT NULL,
  `month` tinyint NOT NULL,
  `month_name` varchar(10) NOT NULL,
  `month_label` char(7) NOT NULL
);

CREATE TABLE `QUARTER` (
  `quarter_key` int PRIMARY KEY NOT NULL,
  `year` smallint NOT NULL,
  `quarter` tinyint NOT NULL,
  `quarter_label` char(7) NOT NULL
);

CREATE TABLE `CARRIER` (
  `carrier_key` smallint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `carrier_code` char(2) UNIQUE NOT NULL,
  `carrier_name` varchar(64) NOT NULL,
  `business_model` varchar(30),
  `is_regional` tinyint(1) NOT NULL,
  `in_ontime` tinyint(1) NOT NULL,
  `in_t100` tinyint(1) NOT NULL,
  `in_db1b_operating` tinyint(1) NOT NULL,
  `in_db1b_ticketed` tinyint(1) NOT NULL
);

CREATE TABLE `AIRPORT` (
  `airport_key` smallint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `airport_code` char(3) UNIQUE NOT NULL,
  `city` varchar(64),
  `state` varchar(2),
  `city_market_id` int,
  `wac` smallint
);

CREATE TABLE `ROUTE` (
  `route_key` int PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `route` char(7) UNIQUE NOT NULL,
  `origin_key` smallint NOT NULL,
  `dest_key` smallint NOT NULL,
  `origin_code` char(3) NOT NULL,
  `dest_code` char(3) NOT NULL,
  `market` varchar(7) NOT NULL,
  `distance_mi` decimal(8,1),
  `distance_band` varchar(10)
);

CREATE TABLE `AIRCRAFT` (
  `aircraft_key` int PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `tail_number` varchar(10) NOT NULL,
  `carrier_code` char(2) NOT NULL,
  `first_flight_date` date,
  `last_flight_date` date,
  `n_flights` int NOT NULL,
  `n_completed` int NOT NULL,
  `avg_distance_mi` decimal(10,4),
  `flights_per_active_day` decimal(6,2)
);

CREATE TABLE `DAYPART` (
  `daypart_key` tinyint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `daypart_code` varchar(20) UNIQUE NOT NULL,
  `daypart_name` varchar(20) NOT NULL,
  `label_vi` varchar(30) NOT NULL,
  `hour_start` tinyint NOT NULL,
  `hour_end` tinyint NOT NULL,
  `sort_order` tinyint NOT NULL
);

CREATE TABLE `DELAY_CAUSE` (
  `delay_cause_key` tinyint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `cause_code` varchar(20) UNIQUE NOT NULL,
  `column_name` varchar(30) NOT NULL,
  `answer_label_vi` varchar(80) NOT NULL,
  `description_vi` varchar(255) NOT NULL,
  `sort_order` tinyint NOT NULL
);

CREATE TABLE `CANCEL_REASON` (
  `cancel_reason_key` tinyint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `cancellation_code` char(1) UNIQUE NOT NULL,
  `reason` varchar(20) NOT NULL
);

CREATE TABLE `FLIGHT_STATS` (
  `ontime_id` bigint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `month_key` int NOT NULL,
  `carrier_key` smallint NOT NULL,
  `route_key` int NOT NULL,
  `flights_scheduled` int NOT NULL,
  `flights_cancelled` int NOT NULL,
  `flights_diverted` int NOT NULL,
  `flights_completed` int NOT NULL,
  `dep_del15_count` int NOT NULL,
  `arr_del15_count` int NOT NULL,
  `arr_delay_pos_min` decimal(14,1) NOT NULL,
  `dep_delay_pos_min` decimal(14,1) NOT NULL,
  `delay_carrier_min` decimal(14,1) NOT NULL,
  `delay_weather_min` decimal(14,1) NOT NULL,
  `delay_nas_min` decimal(14,1) NOT NULL,
  `delay_security_min` decimal(14,1) NOT NULL,
  `delay_late_aircraft_min` decimal(14,1) NOT NULL,
  `cancel_carrier` int NOT NULL,
  `cancel_weather` int NOT NULL,
  `cancel_nas` int NOT NULL,
  `cancel_security` int NOT NULL,
  `taxi_out_sum_min` decimal(14,1) NOT NULL,
  `taxi_in_sum_min` decimal(14,1) NOT NULL,
  `crs_elapsed_sum_min` decimal(14,1) NOT NULL,
  `actual_elapsed_sum_min` decimal(14,1) NOT NULL,
  `turn_n` int NOT NULL,
  `turn_over_sched_n` int NOT NULL,
  `turn_sched_sum_min` decimal(14,1) NOT NULL,
  `turn_actual_sum_min` decimal(14,1) NOT NULL,
  `gate_return_n` int NOT NULL,
  `total_add_gtime_sum_min` decimal(14,1) NOT NULL
);

CREATE TABLE `CAPACITY_STATS` (
  `capacity_id` bigint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `month_key` int NOT NULL,
  `carrier_key` smallint NOT NULL,
  `route_key` int NOT NULL,
  `departures_scheduled` decimal(10,1) NOT NULL,
  `departures_performed` decimal(10,1) NOT NULL,
  `seats` decimal(12,1) NOT NULL,
  `passengers` decimal(12,1) NOT NULL,
  `freight_lbs` decimal(16,2) NOT NULL,
  `mail_lbs` decimal(16,2) NOT NULL,
  `asm` decimal(20,2) NOT NULL,
  `rpm` decimal(20,2) NOT NULL,
  `ramp_to_ramp_min` decimal(16,1) NOT NULL,
  `air_time_min` decimal(16,1) NOT NULL,
  `n_aircraft_types` int NOT NULL
);

CREATE TABLE `TURNAROUND_STATS` (
  `turnaround_id` bigint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `month_key` int NOT NULL,
  `carrier_key` smallint NOT NULL,
  `airport_key` smallint NOT NULL,
  `daypart_key` tinyint NOT NULL,
  `turn_n` int NOT NULL,
  `turn_sched_sum_min` decimal(14,1) NOT NULL,
  `turn_actual_sum_min` decimal(14,1) NOT NULL,
  `turn_excess_sum_min` decimal(14,1) NOT NULL,
  `turn_over_sched_n` int NOT NULL,
  `turn_after_late_inbound_n` int NOT NULL,
  `dep_delay_sum_min` decimal(14,1) NOT NULL
);

CREATE TABLE `FARE_SEGMENT` (
  `fare_segment_id` bigint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `quarter_key` int NOT NULL,
  `tk_carrier_key` smallint NOT NULL,
  `op_carrier_key` smallint NOT NULL,
  `origin_key` smallint NOT NULL,
  `dest_key` smallint NOT NULL,
  `pax_sample` int NOT NULL,
  `seg_revenue_sample` decimal(16,6) NOT NULL,
  `pax_miles_sample` decimal(16,6) NOT NULL,
  `pax_est` decimal(14,2) NOT NULL,
  `revenue_est_usd` decimal(18,2) NOT NULL
);

CREATE TABLE `FARE_MARKET` (
  `fare_market_id` bigint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `quarter_key` int NOT NULL,
  `carrier_key` smallint NOT NULL,
  `origin_key` smallint NOT NULL,
  `dest_key` smallint NOT NULL,
  `is_round_trip` tinyint(1) NOT NULL,
  `is_nonstop` tinyint(1) NOT NULL,
  `itineraries` int NOT NULL,
  `pax_sample` int NOT NULL,
  `rev_sample` decimal(16,6) NOT NULL,
  `pax_est` decimal(14,2) NOT NULL
);

CREATE TABLE `FARE_CLASS` (
  `fare_class_id` bigint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `quarter_key` int NOT NULL,
  `op_carrier_key` smallint NOT NULL,
  `fare_class` char(1) NOT NULL,
  `pax_sample` int NOT NULL,
  `seg_revenue_sample` decimal(16,6) NOT NULL
);

CREATE TABLE `ETL_RUN` (
  `run_id` int PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `started_at` datetime NOT NULL,
  `finished_at` datetime,
  `status` varchar(20) NOT NULL,
  `notes` varchar(255)
);

CREATE TABLE `ETL_LOAD_LOG` (
  `log_id` bigint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `run_id` int NOT NULL,
  `target_table` varchar(64) NOT NULL,
  `phase` varchar(20) NOT NULL,
  `rows_read` int NOT NULL,
  `rows_inserted` int NOT NULL,
  `rows_rejected` int NOT NULL,
  `duration_sec` decimal(10,2),
  `loaded_at` datetime NOT NULL
);

CREATE TABLE `DQ_CHECK` (
  `check_id` bigint PRIMARY KEY NOT NULL AUTO_INCREMENT,
  `run_id` int,
  `check_group` varchar(50) NOT NULL,
  `check_name` varchar(150) NOT NULL,
  `status` varchar(10) NOT NULL,
  `metric_value` varchar(100),
  `detail` varchar(500),
  `checked_at` datetime NOT NULL
);

ALTER TABLE `ROUTE` ADD FOREIGN KEY (`origin_key`) REFERENCES `AIRPORT` (`airport_key`) ON DELETE NO ACTION;

ALTER TABLE `ROUTE` ADD FOREIGN KEY (`dest_key`) REFERENCES `AIRPORT` (`airport_key`) ON DELETE NO ACTION;

ALTER TABLE `FLIGHT_STATS` ADD FOREIGN KEY (`month_key`) REFERENCES `MONTH` (`month_key`) ON DELETE NO ACTION;

ALTER TABLE `FLIGHT_STATS` ADD FOREIGN KEY (`carrier_key`) REFERENCES `CARRIER` (`carrier_key`) ON DELETE NO ACTION;

ALTER TABLE `FLIGHT_STATS` ADD FOREIGN KEY (`route_key`) REFERENCES `ROUTE` (`route_key`) ON DELETE NO ACTION;

ALTER TABLE `CAPACITY_STATS` ADD FOREIGN KEY (`month_key`) REFERENCES `MONTH` (`month_key`) ON DELETE NO ACTION;

ALTER TABLE `CAPACITY_STATS` ADD FOREIGN KEY (`carrier_key`) REFERENCES `CARRIER` (`carrier_key`) ON DELETE NO ACTION;

ALTER TABLE `CAPACITY_STATS` ADD FOREIGN KEY (`route_key`) REFERENCES `ROUTE` (`route_key`) ON DELETE NO ACTION;

ALTER TABLE `TURNAROUND_STATS` ADD FOREIGN KEY (`month_key`) REFERENCES `MONTH` (`month_key`) ON DELETE NO ACTION;

ALTER TABLE `TURNAROUND_STATS` ADD FOREIGN KEY (`carrier_key`) REFERENCES `CARRIER` (`carrier_key`) ON DELETE NO ACTION;

ALTER TABLE `TURNAROUND_STATS` ADD FOREIGN KEY (`airport_key`) REFERENCES `AIRPORT` (`airport_key`) ON DELETE NO ACTION;

ALTER TABLE `TURNAROUND_STATS` ADD FOREIGN KEY (`daypart_key`) REFERENCES `DAYPART` (`daypart_key`) ON DELETE NO ACTION;

ALTER TABLE `FARE_SEGMENT` ADD FOREIGN KEY (`quarter_key`) REFERENCES `QUARTER` (`quarter_key`) ON DELETE NO ACTION;

ALTER TABLE `FARE_SEGMENT` ADD FOREIGN KEY (`tk_carrier_key`) REFERENCES `CARRIER` (`carrier_key`) ON DELETE NO ACTION;

ALTER TABLE `FARE_SEGMENT` ADD FOREIGN KEY (`op_carrier_key`) REFERENCES `CARRIER` (`carrier_key`) ON DELETE NO ACTION;

ALTER TABLE `FARE_SEGMENT` ADD FOREIGN KEY (`origin_key`) REFERENCES `AIRPORT` (`airport_key`) ON DELETE NO ACTION;

ALTER TABLE `FARE_SEGMENT` ADD FOREIGN KEY (`dest_key`) REFERENCES `AIRPORT` (`airport_key`) ON DELETE NO ACTION;

ALTER TABLE `FARE_MARKET` ADD FOREIGN KEY (`quarter_key`) REFERENCES `QUARTER` (`quarter_key`) ON DELETE NO ACTION;

ALTER TABLE `FARE_MARKET` ADD FOREIGN KEY (`carrier_key`) REFERENCES `CARRIER` (`carrier_key`) ON DELETE NO ACTION;

ALTER TABLE `FARE_MARKET` ADD FOREIGN KEY (`origin_key`) REFERENCES `AIRPORT` (`airport_key`) ON DELETE NO ACTION;

ALTER TABLE `FARE_MARKET` ADD FOREIGN KEY (`dest_key`) REFERENCES `AIRPORT` (`airport_key`) ON DELETE NO ACTION;

ALTER TABLE `FARE_CLASS` ADD FOREIGN KEY (`quarter_key`) REFERENCES `QUARTER` (`quarter_key`) ON DELETE NO ACTION;

ALTER TABLE `FARE_CLASS` ADD FOREIGN KEY (`op_carrier_key`) REFERENCES `CARRIER` (`carrier_key`) ON DELETE NO ACTION;

ALTER TABLE `MONTH` ADD UNIQUE KEY `uq_month_ym` (`year`, `month`);

ALTER TABLE `CALENDAR` ADD FOREIGN KEY (`year`, `month`) REFERENCES `MONTH` (`year`, `month`) ON DELETE NO ACTION;

ALTER TABLE `AIRCRAFT` ADD FOREIGN KEY (`carrier_code`) REFERENCES `CARRIER` (`carrier_code`) ON DELETE NO ACTION;

ALTER TABLE `ETL_LOAD_LOG` ADD FOREIGN KEY (`run_id`) REFERENCES `ETL_RUN` (`run_id`) ON DELETE NO ACTION;

ALTER TABLE `DQ_CHECK` ADD FOREIGN KEY (`run_id`) REFERENCES `ETL_RUN` (`run_id`) ON DELETE NO ACTION;

CREATE TABLE `FLIGHT_STATS_DELAY_CAUSE` (
  `FLIGHT_STATS_ontime_id` bigint,
  `DELAY_CAUSE_delay_cause_key` tinyint,
  PRIMARY KEY (`FLIGHT_STATS_ontime_id`, `DELAY_CAUSE_delay_cause_key`)
);

ALTER TABLE `FLIGHT_STATS_DELAY_CAUSE` ADD FOREIGN KEY (`FLIGHT_STATS_ontime_id`) REFERENCES `FLIGHT_STATS` (`ontime_id`);

ALTER TABLE `FLIGHT_STATS_DELAY_CAUSE` ADD FOREIGN KEY (`DELAY_CAUSE_delay_cause_key`) REFERENCES `DELAY_CAUSE` (`delay_cause_key`);


CREATE TABLE `FLIGHT_STATS_CANCEL_REASON` (
  `FLIGHT_STATS_ontime_id` bigint,
  `CANCEL_REASON_cancel_reason_key` tinyint,
  PRIMARY KEY (`FLIGHT_STATS_ontime_id`, `CANCEL_REASON_cancel_reason_key`)
);

ALTER TABLE `FLIGHT_STATS_CANCEL_REASON` ADD FOREIGN KEY (`FLIGHT_STATS_ontime_id`) REFERENCES `FLIGHT_STATS` (`ontime_id`);

ALTER TABLE `FLIGHT_STATS_CANCEL_REASON` ADD FOREIGN KEY (`CANCEL_REASON_cancel_reason_key`) REFERENCES `CANCEL_REASON` (`cancel_reason_key`);

