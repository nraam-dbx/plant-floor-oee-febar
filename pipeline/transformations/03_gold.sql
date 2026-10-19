-- Gold: business-ready OEE built from BOTH domains.
--   Availability = run time / planned production time            (OT: SCADA machine states)
--   Performance  = ideal cycle time x total count / run time      (IT: ERP ideal cycle + MES counts; OT run time)
--   Quality      = good count / total count                       (IT: MES confirmations)
--   OEE          = Availability x Performance x Quality

CREATE OR REFRESH MATERIALIZED VIEW gold_asset_shift_time
COMMENT 'Minutes per asset, shift and machine state (SCADA intervals clipped to shift boundaries).'
AS SELECT ms.asset_id, s.shift_id, s.shift_date, s.shift_code, s.shift_start, ms.state, ms.reason_code,
  sum(timestampdiff(SECOND, greatest(ms.start_ts, s.shift_start), least(ms.end_ts, s.shift_end))) / 60.0 AS minutes,
  count(*) AS intervals
FROM silver_ot_machine_states ms
JOIN silver_shift_calendar s ON ms.start_ts < s.shift_end AND ms.end_ts > s.shift_start
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW gold_ot_cycles_shift
COMMENT 'OT cycle counter increments per asset per shift, to reconcile against MES-reported quantities.'
AS WITH d AS (
  SELECT asset_id, ts, cycle_count - lag(cycle_count) OVER (PARTITION BY asset_id ORDER BY ts) AS delta
  FROM silver_ot_tag_minute WHERE cycle_count IS NOT NULL)
SELECT d.asset_id, s.shift_id, sum(greatest(coalesce(d.delta, 0), 0)) AS ot_cycle_count
FROM d JOIN silver_shift_calendar s ON d.ts >= s.shift_start AND d.ts < s.shift_end
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW gold_oee_shift (
  CONSTRAINT oee_in_range EXPECT (oee BETWEEN 0 AND 1)
)
COMMENT 'OEE per asset per shift = Availability x Performance x Quality, joining OT run time with IT counts.'
AS WITH t AS (
  SELECT asset_id, shift_id, shift_date, shift_code, shift_start,
    sum(CASE WHEN state = 'PLANNED_DOWN'   THEN minutes ELSE 0 END) AS planned_down_min,
    sum(CASE WHEN state = 'UNPLANNED_DOWN' THEN minutes ELSE 0 END) AS unplanned_down_min,
    sum(CASE WHEN state = 'SETUP'          THEN minutes ELSE 0 END) AS setup_min,
    sum(CASE WHEN state = 'IDLE'           THEN minutes ELSE 0 END) AS minor_stop_min,
    sum(CASE WHEN state = 'IDLE'           THEN intervals ELSE 0 END) AS minor_stop_count,
    sum(CASE WHEN state = 'RUNNING'        THEN minutes ELSE 0 END) AS running_min
  FROM gold_asset_shift_time GROUP BY ALL),
q AS (
  SELECT o.asset_id, o.shift_id, sum(c.total_qty) AS total_qty, sum(c.yield_qty) AS good_qty,
         sum(c.scrap_qty) AS scrap_qty, sum(o.planned_qty) AS planned_qty
  FROM silver_production_orders o JOIN silver_production_confirmations c ON c.order_id = o.order_id
  GROUP BY ALL),
b AS (
  SELECT t.*, a.work_center, a.work_center_name, a.ideal_cycle_time_s, a.criticality,
    480 - t.planned_down_min                                        AS planned_production_min,
    480 - t.planned_down_min - t.unplanned_down_min - t.setup_min   AS run_min,   -- minor stops stay in run time (performance loss)
    coalesce(q.total_qty, 0) AS total_qty, coalesce(q.good_qty, 0) AS good_qty,
    coalesce(q.scrap_qty, 0) AS scrap_qty, q.planned_qty, c.ot_cycle_count
  FROM t
  JOIN silver_assets a USING (asset_id)
  LEFT JOIN q USING (asset_id, shift_id)
  LEFT JOIN gold_ot_cycles_shift c USING (asset_id, shift_id))
SELECT *,
  round(availability * performance * quality, 4) AS oee,
  total_qty - ot_cycle_count AS mes_vs_ot_count_variance
FROM (
  SELECT *,
    round(CASE WHEN planned_production_min > 0 THEN greatest(run_min, 0) / planned_production_min ELSE 0 END, 4) AS availability,
    round(CASE WHEN run_min > 0 THEN least(1.0, ideal_cycle_time_s * total_qty / (run_min * 60.0)) ELSE 0 END, 4) AS performance,
    round(CASE WHEN total_qty > 0 THEN good_qty / total_qty ELSE 1.0 END, 4) AS quality
  FROM b);

CREATE OR REFRESH MATERIALIZED VIEW gold_downtime_events
COMMENT 'Unplanned stops (OT) linked to the CMMS work order raised for them (IT); duration and response times.'
AS SELECT ms.asset_id, a.work_center, ms.reason_code, ms.start_ts, ms.end_ts, ms.duration_min,
  s.shift_id, w.wo_id, w.priority, w.problem_description, w.action_taken, w.technician_id,
  timestampdiff(MINUTE, ms.start_ts, w.created_ts)  AS minutes_to_work_order,
  timestampdiff(MINUTE, ms.start_ts, w.closed_ts)   AS minutes_to_close,
  ms.reason_code = a.primary_failure_mode           AS is_major_failure
FROM silver_ot_machine_states ms
JOIN silver_assets a USING (asset_id)
JOIN silver_shift_calendar s ON ms.start_ts >= s.shift_start AND ms.start_ts < s.shift_end
LEFT JOIN silver_work_orders w
  ON w.asset_id = ms.asset_id AND w.failure_code = ms.reason_code
 AND w.created_ts BETWEEN ms.start_ts AND ms.start_ts + INTERVAL 30 MINUTES
WHERE ms.state = 'UNPLANNED_DOWN';

CREATE OR REFRESH MATERIALIZED VIEW gold_asset_reliability
COMMENT 'Per-asset reliability over the window: failures, MTTR, MTBF, unplanned hours, average OEE.'
AS WITH f AS (
  SELECT asset_id, count(*) AS stops, sum(duration_min) AS unplanned_min,
         count_if(is_major_failure) AS major_failures, avg(duration_min) AS mttr_min
  FROM gold_downtime_events GROUP BY asset_id),
o AS (
  SELECT asset_id, sum(running_min + minor_stop_min) AS run_min, avg(oee) AS avg_oee,
         avg(availability) AS avg_availability, avg(performance) AS avg_performance, avg(quality) AS avg_quality,
         sum(scrap_qty) / nullif(sum(total_qty), 0) AS scrap_rate, sum(good_qty) AS good_qty
  FROM gold_oee_shift GROUP BY asset_id)
SELECT a.asset_id, a.asset_name, a.work_center, a.criticality,
  round(o.avg_oee, 4) AS avg_oee, round(o.avg_availability, 4) AS avg_availability,
  round(o.avg_performance, 4) AS avg_performance, round(o.avg_quality, 4) AS avg_quality,
  round(o.scrap_rate, 4) AS scrap_rate, o.good_qty,
  coalesce(f.stops, 0) AS unplanned_stops, coalesce(f.major_failures, 0) AS major_failures,
  round(coalesce(f.unplanned_min, 0) / 60.0, 1) AS unplanned_hours,
  round(f.mttr_min, 1) AS mttr_min,
  round(o.run_min / 60.0 / nullif(f.stops, 0), 1) AS mtbf_hours
FROM silver_assets a JOIN o USING (asset_id) LEFT JOIN f USING (asset_id);

CREATE OR REFRESH MATERIALIZED VIEW gold_shift_features
COMMENT 'ML feature table: per asset per shift OT condition signals + OEE, labelled with NEXT-shift outcome.'
AS WITH sig AS (
  SELECT m.asset_id, s.shift_id,
    avg(m.vibration_mm_s) FILTER (WHERE m.power_kw > 0.5 * a.rated_power_kw)  AS vib_mean_running,
    max(m.vibration_mm_s)                                                      AS vib_max,
    percentile_approx(m.vibration_mm_s, 0.95)                                  AS vib_p95,
    avg(m.temperature_c)                                                       AS temp_mean,
    max(m.temperature_c)                                                       AS temp_max,
    avg(m.power_kw)                                                            AS power_mean
  FROM silver_ot_tag_minute m
  JOIN silver_assets a USING (asset_id)
  JOIN silver_shift_calendar s ON m.ts >= s.shift_start AND m.ts < s.shift_end
  GROUP BY ALL),
alm AS (
  SELECT l.asset_id, s.shift_id,
    count_if(l.alarm_code = 'VIB_HIGH')  AS vib_alarms,
    count_if(l.alarm_code = 'TEMP_HIGH') AS temp_alarms,
    count_if(l.severity = 'CRITICAL')    AS fault_alarms
  FROM silver_ot_alarms l JOIN silver_shift_calendar s ON l.alarm_ts >= s.shift_start AND l.alarm_ts < s.shift_end
  GROUP BY ALL),
j AS (
  SELECT o.asset_id, o.work_center, o.shift_id, o.shift_start, o.shift_code,
    o.oee, o.availability, o.performance, o.quality, o.unplanned_down_min, o.minor_stop_count,
    o.scrap_qty / nullif(o.total_qty, 0) AS scrap_rate,
    sig.vib_mean_running, sig.vib_max, sig.vib_p95, sig.temp_mean, sig.temp_max, sig.power_mean,
    coalesce(alm.vib_alarms, 0) AS vib_alarms, coalesce(alm.temp_alarms, 0) AS temp_alarms,
    coalesce(alm.fault_alarms, 0) AS fault_alarms
  FROM gold_oee_shift o
  LEFT JOIN sig USING (asset_id, shift_id)
  LEFT JOIN alm USING (asset_id, shift_id))
SELECT *,
  vib_mean_running - avg(vib_mean_running) OVER w6         AS vib_trend_vs_prev6,
  avg(oee) OVER w3                                          AS oee_prev3_avg,
  lead(oee) OVER w                                          AS next_shift_oee,
  lead(unplanned_down_min) OVER w                           AS next_shift_unplanned_min
FROM j
WINDOW w  AS (PARTITION BY asset_id ORDER BY shift_start),
       w6 AS (PARTITION BY asset_id ORDER BY shift_start ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING),
       w3 AS (PARTITION BY asset_id ORDER BY shift_start ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING);
