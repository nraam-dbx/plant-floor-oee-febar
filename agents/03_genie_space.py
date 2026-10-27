"""Stage 5 · Genie space "Plant OEE Analyst" defined as code (tables, instructions, example SQL, sample questions).
Creates the space on first run, updates it afterwards; the space id is kept in config.env as GENIE_SPACE_ID.
Run from the project root: python3 agents/03_genie_space.py"""
import hashlib, json, re, subprocess

PROFILE, WAREHOUSE = "fevm-nraameast1", "ba24ff79986686a9"
S = "nraameast1_catalog.plant_floor_oee_febar"
TITLE = "Plant OEE Analyst"
DESCRIPTION = ("Ask about plant-floor OEE (availability x performance x quality) per asset, shift and work center, "
               "unplanned downtime and its work orders, MTTR/MTBF, scrap, and the next-shift at-risk predictions. "
               "Built from integrated IT (ERP/MES/CMMS) and OT (historian/SCADA) data.")

TABLES = ["gold_oee_shift", "gold_downtime_events", "gold_asset_reliability", "gold_at_risk_queue",
          "gold_alert_response", "silver_assets", "silver_work_orders"]

INSTRUCTIONS = """\
Plant context: one turbine-component plant (PLT1), 12 assets in 5 work centers (WC_MACH blade machining CNC-01..04,
WC_GRND grinding GRD-01..02, WC_COAT thermal barrier coating CTG-01..02, WC_WELD welding WLD-01..02, WC_INSP CMM-01..02).
Data covers 2026-09-21 to 2026-10-18. Three 8-hour shifts per day: A 06-14, B 14-22, C 22-06; shift_id = <shift_date>-<A|B|C>.

OEE definitions (gold_oee_shift, one row per asset per shift):
- availability = run_min / planned_production_min; planned_production_min = 480 - planned_down_min (breaks, PM).
- performance = ideal_cycle_time_s * total_qty / (run_min * 60); minor stops (IDLE) are a performance loss.
- quality = good_qty / total_qty. oee = availability * performance * quality (0-1; show as a percentage).
- Plant OEE target is 75%. An asset-shift below 65% is "at risk".
- When aggregating OEE across shifts or assets, report the AVERAGE of oee (and of its three factors), never a sum.
- "Loss breakdown" = compare availability, performance and quality, plus unplanned_down_min, setup_min, minor_stop_count, scrap_qty.

Downtime and maintenance:
- gold_downtime_events holds unplanned stops; reason_code is the failure code; is_major_failure = the asset's primary failure mode.
- MTTR = average duration_min of unplanned stops; MTBF = run hours / stops (precomputed in gold_asset_reliability).
- wo_id links a stop to the CMMS work order raised for it (silver_work_orders has the problem and action text).

Predictions: gold_at_risk_queue has the latest next-shift risk per asset (risk_score 0-1, at_risk = risk_score >= 0.5),
model drivers, and the AI-drafted work order. gold_alert_response shows whether a supervisor acted on each at-risk alert.
Asset names, work centers and criticality are in silver_assets (criticality A = blade machining and coating).
"""

EXAMPLES = [
    ("Which assets had the lowest average OEE over the last 7 days?",
     f"""SELECT asset_id, work_center_name, round(avg(oee) * 100, 1) AS avg_oee_pct,
  round(avg(availability) * 100, 1) AS availability_pct, round(avg(performance) * 100, 1) AS performance_pct,
  round(avg(quality) * 100, 1) AS quality_pct
FROM {S}.gold_oee_shift
WHERE shift_date > (SELECT max(shift_date) - INTERVAL 7 DAYS FROM {S}.gold_oee_shift)
GROUP BY ALL ORDER BY avg_oee_pct ASC"""),
    ("Why did OEE drop on CNC-03 between September 27 and October 1?",
     f"""SELECT shift_id, round(oee * 100, 1) AS oee_pct, round(availability * 100, 1) AS availability_pct,
  round(performance * 100, 1) AS performance_pct, round(quality * 100, 1) AS quality_pct,
  unplanned_down_min, minor_stop_count, scrap_qty
FROM {S}.gold_oee_shift
WHERE asset_id = 'CNC-03' AND shift_date BETWEEN '2026-09-27' AND '2026-10-01'
ORDER BY shift_start"""),
    ("What are MTTR and unplanned downtime hours by work center?",
     f"""SELECT work_center, count(*) AS unplanned_stops, round(avg(duration_min), 1) AS mttr_min,
  round(sum(duration_min) / 60, 1) AS unplanned_hours
FROM {S}.gold_downtime_events GROUP BY work_center ORDER BY unplanned_hours DESC"""),
    ("What are the top unplanned downtime reasons?",
     f"""SELECT reason_code, count(*) AS stops, round(sum(duration_min) / 60, 1) AS hours, round(avg(duration_min), 1) AS avg_min
FROM {S}.gold_downtime_events GROUP BY reason_code ORDER BY hours DESC"""),
    ("Which assets are at risk next shift and has anyone acted on them?",
     f"""SELECT q.asset_id, q.asset_name, round(q.risk_score, 3) AS risk_score, q.top_drivers, q.wo_priority,
  r.first_action, r.minutes_to_first_action
FROM {S}.gold_at_risk_queue q LEFT JOIN {S}.gold_alert_response r USING (asset_id)
WHERE q.at_risk ORDER BY q.risk_score DESC"""),
]

SAMPLE_QUESTIONS = [
    "What was plant OEE by work center last week?",
    "Which assets are at risk next shift?",
    "Show the OEE loss breakdown for CNC-03 around its spindle failure",
    "Which work center has the worst MTTR?",
    "How much scrap did the coating cells produce, and on which shifts?",
]


def hid(text):                       # deterministic 32-hex ids so re-runs update in place
    return hashlib.md5(text.encode()).hexdigest()


def cli(*args):
    out = subprocess.run(["databricks", *args, "-p", PROFILE, "-o", "json"], capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(out.stderr or out.stdout)
    return json.loads(out.stdout) if out.stdout.strip() else {}


space = {
    "version": 2,
    "config": {"sample_questions": sorted(({"id": hid(q), "question": [q]} for q in SAMPLE_QUESTIONS), key=lambda x: x["id"])},
    "data_sources": {"tables": [{"identifier": f"{S}.{t}"} for t in sorted(TABLES)]},
    "instructions": {
        "text_instructions": [{"id": hid("instructions"), "content": [INSTRUCTIONS]}],
        "example_question_sqls": sorted(({"id": hid(q), "question": [q], "sql": [sql]} for q, sql in EXAMPLES), key=lambda x: x["id"]),
    },
}
serialized = json.dumps(space)

env = open("config.env").read()
m = re.search(r'^GENIE_SPACE_ID="([0-9a-f]*)"', env, re.M)
space_id = m.group(1) if m else ""
if space_id:
    cli("genie", "update-space", space_id, "--json", json.dumps(
        {"serialized_space": serialized, "title": TITLE, "description": DESCRIPTION, "warehouse_id": WAREHOUSE}))
    print(f"updated Genie space {space_id}")
else:
    res = cli("genie", "create-space", "--json", json.dumps(
        {"warehouse_id": WAREHOUSE, "serialized_space": serialized, "title": TITLE, "description": DESCRIPTION}))
    space_id = res["space_id"]
    line = f'GENIE_SPACE_ID="{space_id}"                    # Genie space "Plant OEE Analyst" (agents/03_genie_space.py)\n'
    env = re.sub(r'^GENIE_SPACE_ID=.*\n', line, env, flags=re.M) if "GENIE_SPACE_ID=" in env else env + line
    open("config.env", "w").write(env)
    print(f"created Genie space {space_id}")
