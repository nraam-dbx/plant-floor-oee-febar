"""Regenerate evidence/12_value_baseline.md: the measured baseline behind docs/deck/VALUE_MODEL.md (run from project root)."""
import datetime, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from sql import run, table

S = "nraameast1_catalog.plant_floor_oee_febar"
# Degrade -> fail window: any shift overlapping [4 days before a major (run-to-failure) stop, end of that stop].
WINDOW = f"""
WITH f AS (SELECT asset_id, start_ts, end_ts FROM {S}.gold_downtime_events WHERE is_major_failure),
w AS (SELECT s.*, EXISTS (SELECT 1 FROM f WHERE f.asset_id = s.asset_id
        AND s.shift_start + INTERVAL 8 HOURS > f.start_ts - INTERVAL 4 DAYS AND s.shift_start < f.end_ts) AS in_window
      FROM {S}.gold_oee_shift s)"""

SECTIONS = [
    ("Plant OEE (all asset-shifts, 28 days)",
     f"SELECT count(*) asset_shifts, round(100*avg(oee),1) plant_oee_pct FROM {S}.gold_oee_shift"),
    ("Shifts inside a degrade → fail window vs all other shifts", WINDOW + """
SELECT in_window, count(*) shifts, round(100*count(*)/sum(count(*)) OVER (),1) pct_of_shifts,
  round(100*avg(oee),1) oee_pct, round(100*avg(availability),1) availability_pct, round(100*avg(performance),1) performance_pct,
  round(100*avg(quality),1) quality_pct, round(100*sum(scrap_qty)/sum(total_qty),1) scrap_pct, sum(scrap_qty) scrap_units,
  round(sum(unplanned_down_min)/60) unplanned_hours
FROM w GROUP BY 1 ORDER BY 1"""),
    ("Excess scrap in those windows (above the out-of-window scrap rate)", WINDOW + """,
r AS (SELECT sum(scrap_qty) FILTER (WHERE NOT in_window) / sum(total_qty) FILTER (WHERE NOT in_window) base_rate FROM w)
SELECT sum(total_qty) window_units, sum(scrap_qty) window_scrap,
  round(sum(total_qty)*(SELECT base_rate FROM r)) expected_at_base_rate,
  round(sum(scrap_qty) - sum(total_qty)*(SELECT base_rate FROM r)) excess_parts
FROM w WHERE in_window"""),
    ("Major (run-to-failure) stops", f"""
SELECT count(*) major_failures, round(avg(duration_min)/60,1) avg_hours, round(sum(duration_min)/60,1) total_hours
FROM {S}.gold_downtime_events WHERE is_major_failure"""),
]

out = ["# Evidence 12 — Measured baseline behind the value model (live query output)", "",
       f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M} by `ops/value_evidence.py` against `{S}`. These are the "
       "**measured** inputs of [`docs/deck/VALUE_MODEL.md`](../docs/deck/VALUE_MODEL.md); its assumptions A1–A6 are "
       "labelled there. Window = any shift overlapping the period from 4 days before a major failure until the machine is back.", ""]
for title, sql in SECTIONS:
    out += [f"## {title}", "", "```sql", sql.strip(), "```", "", "```", table(*run(sql)), "```", ""]
open("evidence/12_value_baseline.md", "w").write("\n".join(out))
print("wrote evidence/12_value_baseline.md")
