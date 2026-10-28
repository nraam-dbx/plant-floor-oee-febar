# Evidence 12 — Measured baseline behind the value model (live query output)

Generated 2026-10-28 15:08 by `ops/value_evidence.py` against `nraameast1_catalog.plant_floor_oee_febar`. These are the **measured** inputs of [`docs/deck/VALUE_MODEL.md`](../docs/deck/VALUE_MODEL.md); its assumptions A1–A6 are labelled there. Window = any shift overlapping the period from 4 days before a major failure until the machine is back.

## Plant OEE (all asset-shifts, 28 days)

```sql
SELECT count(*) asset_shifts, round(100*avg(oee),1) plant_oee_pct FROM nraameast1_catalog.plant_floor_oee_febar.gold_oee_shift
```

```
asset_shifts | plant_oee_pct
-------------+--------------
1008         | 74.1         
```

## Shifts inside a degrade → fail window vs all other shifts

```sql
WITH f AS (SELECT asset_id, start_ts, end_ts FROM nraameast1_catalog.plant_floor_oee_febar.gold_downtime_events WHERE is_major_failure),
w AS (SELECT s.*, EXISTS (SELECT 1 FROM f WHERE f.asset_id = s.asset_id
        AND s.shift_start + INTERVAL 8 HOURS > f.start_ts - INTERVAL 4 DAYS AND s.shift_start < f.end_ts) AS in_window
      FROM nraameast1_catalog.plant_floor_oee_febar.gold_oee_shift s)
SELECT in_window, count(*) shifts, round(100*count(*)/sum(count(*)) OVER (),1) pct_of_shifts,
  round(100*avg(oee),1) oee_pct, round(100*avg(availability),1) availability_pct, round(100*avg(performance),1) performance_pct,
  round(100*avg(quality),1) quality_pct, round(100*sum(scrap_qty)/sum(total_qty),1) scrap_pct, sum(scrap_qty) scrap_units,
  round(sum(unplanned_down_min)/60) unplanned_hours
FROM w GROUP BY 1 ORDER BY 1
```

```
in_window | shifts | pct_of_shifts | oee_pct | availability_pct | performance_pct | quality_pct | scrap_pct | scrap_units | unplanned_hours
----------+--------+---------------+---------+------------------+-----------------+-------------+-----------+-------------+----------------
false     | 875    | 86.8          | 76.5    | 90.6             | 86.2            | 97.9        | 1.9       | 1200        | 77             
true      | 133    | 13.2          | 58.4    | 86.2             | 73.0            | 92.6        | 6.9       | 622         | 63             
```

## Excess scrap in those windows (above the out-of-window scrap rate)

```sql
WITH f AS (SELECT asset_id, start_ts, end_ts FROM nraameast1_catalog.plant_floor_oee_febar.gold_downtime_events WHERE is_major_failure),
w AS (SELECT s.*, EXISTS (SELECT 1 FROM f WHERE f.asset_id = s.asset_id
        AND s.shift_start + INTERVAL 8 HOURS > f.start_ts - INTERVAL 4 DAYS AND s.shift_start < f.end_ts) AS in_window
      FROM nraameast1_catalog.plant_floor_oee_febar.gold_oee_shift s),
r AS (SELECT sum(scrap_qty) FILTER (WHERE NOT in_window) / sum(total_qty) FILTER (WHERE NOT in_window) base_rate FROM w)
SELECT sum(total_qty) window_units, sum(scrap_qty) window_scrap,
  round(sum(total_qty)*(SELECT base_rate FROM r)) expected_at_base_rate,
  round(sum(scrap_qty) - sum(total_qty)*(SELECT base_rate FROM r)) excess_parts
FROM w WHERE in_window
```

```
window_units | window_scrap | expected_at_base_rate | excess_parts
-------------+--------------+-----------------------+-------------
8990         | 622          | 170.0                 | 452.0       
```

## Major (run-to-failure) stops

```sql
SELECT count(*) major_failures, round(avg(duration_min)/60,1) avg_hours, round(sum(duration_min)/60,1) total_hours
FROM nraameast1_catalog.plant_floor_oee_febar.gold_downtime_events WHERE is_major_failure
```

```
major_failures | avg_hours | total_hours
---------------+-----------+------------
10             | 5.3       | 53.2       
```
