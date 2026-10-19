# Databricks notebook source
# MAGIC %md
# MAGIC # Plant-floor OEE — synthetic IT + OT data generator
# MAGIC
# MAGIC Simulates one turbine-component plant (12 assets, 5 work centers) minute-by-minute and lands the
# MAGIC raw extracts each source system would produce into a UC volume. Lakeflow ingests them from there.
# MAGIC
# MAGIC | System | Domain | Keyed on | Files |
# MAGIC |---|---|---|---|
# MAGIC | Historian (1-min tags) | OT | `tag_name` e.g. `PLT1.WC_MACH.CNC03.VIBRATION` | `raw/ot/historian/*.csv` |
# MAGIC | SCADA machine states | OT | `equipment_path` e.g. `PLT1.WC_MACH.CNC03` | `raw/ot/machine_states/*.json` |
# MAGIC | SCADA alarms | OT | `equipment_path` | `raw/ot/alarms/*.json` |
# MAGIC | ERP equipment master | IT | `erp_equipment_id` e.g. `EQ-10003` (+ historian prefix = the IT↔OT key map) | `raw/it/assets/` |
# MAGIC | ERP/MES production orders + confirmations | IT | `erp_equipment_id`, `shift_id` | `raw/it/production_*` |
# MAGIC | CMMS work orders | IT | `erp_equipment_id` | `raw/it/work_orders/` |
# MAGIC | Shift calendar, operators (PII) | IT | `shift_id`, `operator_id` | `raw/it/shift_calendar/`, `raw/it/operators/` |
# MAGIC
# MAGIC Embedded stories (what the pipeline, model and agent should rediscover):
# MAGIC * **Degradation → failure** — vibration/temperature creep and speed loss for 3–6 days before a long
# MAGIC   unplanned stop (CNC-03 twice, plus random episodes elsewhere). This is the predictive signal.
# MAGIC * **Coating temperature excursions** — CTG-02 booth temperature spikes drive scrap (a Quality loss).
# MAGIC * **Minor stops** — GRD-01 loses Performance to frequent 2–5 min stops.
# MAGIC * **Data-quality defects** for the pipeline expectations: BAD OPC quality, out-of-range spikes,
# MAGIC   duplicate tag rows, an unmapped historian tag, impossible MES confirmations.

# COMMAND ----------

dbutils.widgets.text("catalog", "nraameast1_catalog")
dbutils.widgets.text("schema", "plant_floor_oee_febar")
dbutils.widgets.text("start_date", "2026-09-21")
dbutils.widgets.text("days", "28")
dbutils.widgets.text("seed", "42")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
START = dbutils.widgets.get("start_date")
DAYS = int(dbutils.widgets.get("days"))
SEED = int(dbutils.widgets.get("seed"))
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
print(f"Landing {DAYS} days from {START} into {RAW} (seed={SEED})")

# COMMAND ----------

import json, os, shutil
import numpy as np
import pandas as pd

SHIFT_MIN = 480
N = DAYS * 1440
T0 = pd.Timestamp(f"{START} 06:00:00")          # shift A starts 06:00
TS = T0 + pd.to_timedelta(np.arange(N), unit="min")
SHIFT_CODES = ["A", "B", "C"]                    # A 06-14, B 14-22, C 22-06

RUN, IDLE, SETUP, PLANNED, UNPLANNED = range(5)
STATE_NAMES = {RUN: "RUNNING", IDLE: "IDLE", SETUP: "SETUP", PLANNED: "PLANNED_DOWN", UNPLANNED: "UNPLANNED_DOWN"}

WORK_CENTERS = {
    #           name                    ideal_s  kw  base_vib  parts                               failure mode
    "WC_MACH": ("Blade Machining",        240,  45,  2.2, ["BLD-S1-A", "BLD-S1-B", "BLD-S2-A"], "SPINDLE_BEARING"),
    "WC_GRND": ("Root Form Grinding",     180,  30,  1.8, ["BLD-ROOT-G1", "BLD-ROOT-G2"],       "WHEEL_SPINDLE"),
    "WC_COAT": ("Thermal Barrier Coating", 600, 80,  1.2, ["TBC-S1", "TBC-S2"],                 "PLASMA_GUN"),
    "WC_WELD": ("Vane Segment Welding",   420,  25,  0.9, ["VANE-SEG-W1"],                      "WIRE_FEED"),
    "WC_INSP": ("CMM Inspection",         300,   5,  0.3, ["INSP-S1", "INSP-S2"],               "PROBE_FAULT"),
}
#            asset    wc        degradation episodes   minor-stop p/min  scrap base  excursions/day
ASSETS = [("CNC-01", "WC_MACH", 1,    0.004, 0.020, 0.0),
          ("CNC-02", "WC_MACH", None, 0.004, 0.020, 0.0),
          ("CNC-03", "WC_MACH", "hero", 0.005, 0.025, 0.0),
          ("CNC-04", "WC_MACH", None, 0.004, 0.020, 0.0),
          ("GRD-01", "WC_GRND", None, 0.016, 0.015, 0.0),
          ("GRD-02", "WC_GRND", 1,    0.004, 0.015, 0.0),
          ("CTG-01", "WC_COAT", None, 0.003, 0.030, 0.2),
          ("CTG-02", "WC_COAT", None, 0.003, 0.030, 1.2),
          ("WLD-01", "WC_WELD", None, 0.004, 0.020, 0.0),
          ("WLD-02", "WC_WELD", 1,    0.004, 0.020, 0.0),
          ("CMM-01", "WC_INSP", None, 0.002, 0.005, 0.0),
          ("CMM-02", "WC_INSP", None, 0.002, 0.005, 0.0)]
RANDOM_STOP_REASONS = ["TOOL_BREAK", "COOLANT_LOW", "MATERIAL_SHORTAGE", "CONTROLLER_FAULT", "FIXTURE_JAM"]

def fmt(ts):
    return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

# COMMAND ----------

# MAGIC %md ## IT master data — equipment (with the IT↔OT key map), shift calendar, operators

# COMMAND ----------

assets_master = []
for i, (aid, wc, *_rest) in enumerate(ASSETS):
    wc_name, ideal_s, kw, _vib, parts, fmode = WORK_CENTERS[wc]
    assets_master.append(dict(
        erp_equipment_id=f"EQ-{10001 + i}", asset_id=aid,
        asset_name=f"{wc_name} {aid}", work_center=wc, work_center_name=wc_name,
        historian_prefix=f"PLT1.{wc}.{aid.replace('-', '')}",
        ideal_cycle_time_s=ideal_s, rated_power_kw=kw,
        criticality="A" if wc in ("WC_MACH", "WC_COAT") else "B",
        install_year=2012 + (i * 3) % 11, primary_failure_mode=fmode, plant="PLT1"))
assets_df = pd.DataFrame(assets_master)

FIRST = ["Alex", "Jordan", "Sam", "Taylor", "Casey", "Morgan", "Riley", "Jamie", "Avery",
         "Quinn", "Drew", "Reese", "Skyler", "Rowan", "Parker", "Emerson", "Hayden", "Kendall"]
LAST = ["Nguyen", "Patel", "Garcia", "Smith", "Okafor", "Kowalski", "Rossi", "Haddad", "Kim",
        "Silva", "Novak", "Ibrahim", "Larsen", "Mendez", "Chen", "Dubois", "Murphy", "Tanaka"]
operators_df = pd.DataFrame([dict(operator_id=f"OP-{201 + k}", full_name=f"{FIRST[k]} {LAST[(k * 7) % 18]}",
                                  badge_number=f"B{40000 + k * 37}", crew=SHIFT_CODES[k % 3],
                                  certification_level=["L1", "L2", "L3"][k % 3]) for k in range(18)])
crew_ops = {c: operators_df[operators_df.crew == c].operator_id.tolist() for c in SHIFT_CODES}

n_shifts = N // SHIFT_MIN
shifts = []
for s in range(n_shifts):
    start = T0 + pd.Timedelta(minutes=s * SHIFT_MIN)
    code = SHIFT_CODES[s % 3]
    prod_date = (start - pd.Timedelta(hours=6)).date()   # shift C (22-06) belongs to the day it starts
    shifts.append(dict(shift_id=f"{prod_date}-{code}", shift_date=str(prod_date), shift_code=code, crew=code,
                       shift_start=fmt(start), shift_end=fmt(start + pd.Timedelta(minutes=SHIFT_MIN)),
                       scheduled_minutes=SHIFT_MIN))
shift_df = pd.DataFrame(shifts)
display(assets_df)

# COMMAND ----------

# MAGIC %md ## Minute-level simulation per asset

# COMMAND ----------

hist_frames, state_rows, alarm_rows, order_rows, conf_rows, wo_rows = [], [], [], [], [], []
truth_rows = []   # ground-truth failure episodes, printed for the evidence log (not landed)
order_seq, wo_seq = 2600001, 7100001

WO_TEXT = {
    "SPINDLE_BEARING": ("Spindle vibration high and audible noise from spindle housing; part surface finish out of tolerance.",
                        "Replaced front spindle bearing set, re-greased, ran balance check. Root cause: bearing wear from lubrication starvation."),
    "WHEEL_SPINDLE": ("Grinding wheel spindle chatter, burn marks on blade root form.",
                      "Replaced wheel spindle bearings and dressed wheel. Root cause: bearing fatigue."),
    "PLASMA_GUN": ("Plasma gun arc unstable, coating thickness variation flagged by inspection.",
                   "Replaced electrode and nozzle, recalibrated gas flow. Root cause: electrode erosion past service life."),
    "WIRE_FEED": ("Wire feed slipping, porosity in weld bead.",
                  "Replaced drive rolls and liner, re-tensioned feeder. Root cause: worn drive rolls."),
    "PROBE_FAULT": ("CMM probe collision alarm, measurement repeatability failed.",
                    "Replaced stylus, re-qualified probe. Root cause: probe module wear."),
    "TOOL_BREAK": ("Cutting tool broke mid-cycle.", "Replaced tool and re-touched offsets."),
    "COOLANT_LOW": ("Coolant low-level alarm, machine stopped.", "Topped up coolant, cleaned chip filter."),
    "MATERIAL_SHORTAGE": ("No blanks staged at machine.", "Material staged from warehouse; no equipment fault."),
    "CONTROLLER_FAULT": ("Controller fault, axis drive alarm.", "Power-cycled drive, cleared fault, checked cabling."),
    "FIXTURE_JAM": ("Fixture clamp failed to release.", "Cleaned and lubricated clamp cylinder, replaced seal."),
}

for i, (aid, wc, degr, p_minor, scrap_base, exc_per_day) in enumerate(ASSETS):
    rng = np.random.default_rng(SEED + i)
    wc_name, ideal_s, kw, base_vib, parts, fmode = WORK_CENTERS[wc]
    m = assets_master[i]
    prefix, eq = m["historian_prefix"], m["erp_equipment_id"]
    state = np.full(N, RUN, dtype=np.int8)
    reason = np.full(N, "", dtype=object)
    d = np.zeros(N)                              # degradation level 0..1

    # 1) planned: mid-shift meal break + a 4h preventive maintenance every 14 days
    for s in range(n_shifts):
        b = s * SHIFT_MIN + 225
        state[b:b + 30], reason[b:b + 30] = PLANNED, "MEAL_BREAK"
    pm_windows = []
    for day in range(i % 7, DAYS, 14):
        b = day * 1440 + 60
        state[b:b + 240], reason[b:b + 240] = PLANNED, "PREVENTIVE_MAINT"
        pm_windows.append((b, b + 240))

    # 2) production orders: 1-2 per shift, changeover (SETUP) at the start of each
    orders = []
    for s in range(n_shifts):
        s0 = s * SHIFT_MIN
        starts = [s0, s0 + 255] if rng.random() < 0.35 else [s0]
        for k, o0 in enumerate(starts):
            o1 = starts[k + 1] if k + 1 < len(starts) else s0 + SHIFT_MIN
            setup = int(rng.integers(15, 40))
            sl = slice(o0, o0 + setup)
            free = state[sl] == RUN
            state[sl][free] = SETUP
            reason[sl][free] = "CHANGEOVER"
            orders.append((s, o0, o1))

    # 3) degradation episodes ending in a long unplanned failure
    if degr == "hero":
        fail_mins = [int(10.4 * 1440), int(23.6 * 1440)]
    else:
        k = rng.poisson(degr) if degr else (1 if rng.random() < 0.25 else 0)
        fail_mins = sorted(int(x) for x in rng.uniform(6 * 1440, (DAYS - 0.5) * 1440, size=k))
    for f in fail_mins:
        ramp = int(rng.uniform(3, 6) * 1440)
        a = max(0, f - ramp)
        d[a:f] = np.maximum(d[a:f], np.linspace(0, 1, f - a) ** 1.5)
        dur = int(rng.integers(180, 480))
        state[f:f + dur], reason[f:f + dur] = UNPLANNED, fmode
        truth_rows.append(dict(asset_id=aid, failure_start=fmt(TS[f]), duration_min=dur, ramp_days=round(ramp / 1440, 1), failure_mode=fmode))

    # 4) random short unplanned stops with no precursor (noise the model can't predict)
    for _ in range(rng.poisson(0.5 * DAYS)):
        f = int(rng.integers(0, N - 90))
        if state[f] != RUN:
            continue
        dur = int(rng.integers(15, 75))
        sl = slice(f, f + dur)
        free = np.isin(state[sl], (RUN, IDLE))
        state[sl][free] = UNPLANNED
        reason[sl][free] = rng.choice(RANDOM_STOP_REASONS)

    # 5) minor stops (IDLE) — performance loss, more frequent while degrading
    p = p_minor + 0.01 * d
    for f in np.flatnonzero((rng.random(N) < p) & (state == RUN)):
        dur = int(rng.integers(2, 6))
        sl = slice(f, f + dur)
        free = state[sl] == RUN
        state[sl][free] = IDLE
        reason[sl][free] = "MINOR_STOP"

    # 6) coating booth temperature excursions (quality loss)
    exc = np.zeros(N, dtype=bool)
    for _ in range(rng.poisson(exc_per_day * DAYS)):
        f = int(rng.integers(0, N - 200))
        exc[f:f + int(rng.integers(60, 180))] = True

    # production: fractional cycles while RUNNING, slower when degraded
    running = state == RUN
    speed = np.clip(0.88 - 0.28 * d + rng.normal(0, 0.02, N), 0.3, 1.0)
    cum = np.cumsum(running * speed * 60.0 / ideal_s)
    cycle_count = np.floor(cum)
    completions = np.diff(np.concatenate([[0], cycle_count])).astype(int)
    p_scrap = np.clip(scrap_base + 0.12 * d + 0.20 * exc, 0, 0.9)
    scrap = rng.binomial(completions, p_scrap)

    # historian tags
    vib = np.where(running, base_vib * (1 + 2.8 * d ** 1.2), np.where(np.isin(state, (IDLE, SETUP)), 0.25 * base_vib, 0.02))
    vib = np.abs(vib + rng.normal(0, 0.12 * base_vib, N))
    if wc == "WC_COAT":
        temp_target = np.where(running | (state == IDLE), 85 + 12 * exc, 30.0)
    else:
        temp_target = np.where(running, 52 + 18 * d, 24.0)
    temp = pd.Series(temp_target).ewm(alpha=0.08).mean().to_numpy() + rng.normal(0, 0.6, N)
    power = np.where(running, kw * (0.75 + 0.1 * d), np.where(np.isin(state, (IDLE, SETUP)), kw * 0.15, kw * 0.02))
    power = np.abs(power + rng.normal(0, 0.03 * kw, N))

    h = pd.DataFrame({"ts": np.tile(TS, 4),
                      "tag_name": np.repeat([f"{prefix}.VIBRATION", f"{prefix}.TEMPERATURE", f"{prefix}.POWER", f"{prefix}.CYCLE_COUNT"], N),
                      "value": np.concatenate([vib.round(3), temp.round(2), power.round(2), cycle_count])})
    h["quality"] = "GOOD"
    bad = rng.random(len(h)) < 0.0015                      # BAD OPC quality, value lost
    h.loc[bad, "quality"], h.loc[bad, "value"] = "BAD", np.nan
    spike = (rng.random(len(h)) < 0.0005) & ~h.tag_name.str.endswith("CYCLE_COUNT").to_numpy()
    h.loc[spike, "value"] = 9999.0                          # sensor spike, GOOD quality but impossible
    dup = h.sample(frac=0.001, random_state=SEED + i)       # store-and-forward duplicates
    hist_frames.append(pd.concat([h, dup]))

    # SCADA machine-state intervals (run-length encoded)
    key = state.astype(str).astype(object) + "|" + reason
    edges = np.flatnonzero(np.concatenate([[True], key[1:] != key[:-1]]))
    ends = np.concatenate([edges[1:], [N]])
    for a, b in zip(edges, ends):
        state_rows.append(dict(equipment_path=prefix, state=STATE_NAMES[int(state[a])], reason_code=reason[a] or None,
                               start_ts=fmt(TS[a]), end_ts=fmt(T0 + pd.Timedelta(minutes=int(b))), source="SCADA"))

    # SCADA alarms: debounced vibration / booth temperature highs, and a fault alarm at each unplanned stop
    last = -10**9
    for f in np.flatnonzero(vib > base_vib * 2.2):
        if f - last >= 60:
            alarm_rows.append(dict(equipment_path=prefix, alarm_code="VIB_HIGH", severity="WARNING",
                                   alarm_ts=fmt(TS[f]), value=round(float(vib[f]), 2), message="Vibration above warning limit"))
            last = f
    if wc == "WC_COAT":
        last = -10**9
        for f in np.flatnonzero(temp > 93):
            if f - last >= 60:
                alarm_rows.append(dict(equipment_path=prefix, alarm_code="TEMP_HIGH", severity="WARNING",
                                       alarm_ts=fmt(TS[f]), value=round(float(temp[f]), 1), message="Booth temperature above limit"))
                last = f
    unp = state == UNPLANNED
    for a in np.flatnonzero(unp & ~np.concatenate([[False], unp[:-1]])):
        alarm_rows.append(dict(equipment_path=prefix, alarm_code=f"FAULT_{reason[a]}", severity="CRITICAL",
                               alarm_ts=fmt(TS[a]), value=None, message=f"Machine stopped: {reason[a]}"))

    # ERP/MES production orders + confirmations (keyed by ERP equipment id, not the historian tag)
    for s, o0, o1 in orders:
        sh = shifts[s]
        total = int(completions[o0:o1].sum())
        scr = int(scrap[o0:o1].sum())
        oid = f"PO-{order_seq}"
        order_seq += 1
        order_rows.append(dict(order_id=oid, erp_equipment_id=eq, shift_id=sh["shift_id"],
                               part_number=parts[int(rng.integers(len(parts)))],
                               planned_qty=int((o1 - o0 - 30) * 60 / ideal_s * 0.85),
                               scheduled_start=fmt(TS[o0]), scheduled_end=fmt(T0 + pd.Timedelta(minutes=o1)),
                               operator_id=rng.choice(crew_ops[sh["crew"]])))
        reported = total + (int(rng.integers(-3, 4)) if rng.random() < 0.04 else 0)   # manual-entry variance
        yld, scr_rep = max(reported - scr, 0), scr
        if rng.random() < 0.005:
            scr_rep = -scr_rep - 1                          # impossible confirmation for the expectations
        conf_rows.append(dict(confirmation_id=f"CF-{oid[3:]}", order_id=oid, erp_equipment_id=eq,
                              confirmed_ts=fmt(T0 + pd.Timedelta(minutes=o1 + int(rng.integers(5, 30)))),
                              yield_qty=yld, scrap_qty=scr_rep,
                              scrap_reason=("COATING_THICKNESS" if wc == "WC_COAT" else "DIMENSIONAL") if scr_rep > 0 else None))

    # CMMS work orders: corrective for every unplanned stop >= 20 min, preventive for each PM window
    for a in np.flatnonzero(unp & ~np.concatenate([[False], unp[:-1]])):
        b = a
        while b < N and state[b] == UNPLANNED:
            b += 1
        if b - a < 20:
            continue
        code = reason[a]
        problem, action = WO_TEXT[code]
        created = TS[a] + pd.Timedelta(minutes=int(rng.integers(2, 10)))
        wo_rows.append(dict(wo_id=f"WO-{wo_seq}", erp_equipment_id=eq, wo_type="CORRECTIVE",
                            priority="P1" if code == fmode else "P2", failure_code=code,
                            problem_description=problem, action_taken=action,
                            created_ts=fmt(created), actual_start_ts=fmt(created + pd.Timedelta(minutes=int(rng.integers(5, 20)))),
                            closed_ts=fmt(T0 + pd.Timedelta(minutes=int(b + rng.integers(0, 45)))),
                            technician_id=f"TECH-{int(rng.integers(11, 19))}",
                            labor_hours=round((b - a) / 60 * rng.uniform(0.8, 1.3), 1)))
        wo_seq += 1
    for a, b in pm_windows:
        wo_rows.append(dict(wo_id=f"WO-{wo_seq}", erp_equipment_id=eq, wo_type="PREVENTIVE", priority="P3",
                            failure_code=None, problem_description="Scheduled 14-day preventive maintenance.",
                            action_taken="Lubrication, inspection, filter change per PM checklist.",
                            created_ts=fmt(TS[a] - pd.Timedelta(days=2)), actual_start_ts=fmt(TS[a]),
                            closed_ts=fmt(T0 + pd.Timedelta(minutes=b)), technician_id=f"TECH-{int(rng.integers(11, 19))}",
                            labor_hours=4.0))
        wo_seq += 1

# an OT tag the ERP master doesn't know (compressor on the utility skid) -> exercises the mapping expectation
util = pd.DataFrame({"ts": TS[::15], "tag_name": "PLT1.WC_UTIL.COMP01.PRESSURE", "value": 7.0, "quality": "GOOD"})
hist_frames.append(util)
print(f"Simulated {len(ASSETS)} assets x {N:,} minutes")

# COMMAND ----------

# MAGIC %md ## Land raw extracts in the UC volume

# COMMAND ----------

def reset(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

def land_daily(df, ts_col, sub, kind):
    """Write one file per production day — the way the source systems drop extracts."""
    path = f"{RAW}/{sub}"
    reset(path)
    day = pd.to_datetime(df[ts_col]).dt.strftime("%Y-%m-%d")
    for dval, part in df.groupby(day):
        f = f"{path}/{sub.split('/')[-1]}_{dval}.{kind}"
        if kind == "csv":
            part.to_csv(f, index=False)
        else:
            part.to_json(f, orient="records", lines=True)
    return day.nunique()

def land_snapshot(df, sub):
    path = f"{RAW}/{sub}"
    reset(path)
    df.to_csv(f"{path}/{sub.split('/')[-1]}_snapshot.csv", index=False)

hist = pd.concat(hist_frames, ignore_index=True)
hist["ts"] = hist["ts"].dt.strftime("%Y-%m-%d %H:%M:%S")
hist = hist[["tag_name", "ts", "value", "quality"]]

summary = {
    "ot/historian": (len(hist), land_daily(hist, "ts", "ot/historian", "csv")),
    "ot/machine_states": (len(state_rows), land_daily(pd.DataFrame(state_rows), "start_ts", "ot/machine_states", "json")),
    "ot/alarms": (len(alarm_rows), land_daily(pd.DataFrame(alarm_rows), "alarm_ts", "ot/alarms", "json")),
    "it/production_orders": (len(order_rows), land_daily(pd.DataFrame(order_rows), "scheduled_start", "it/production_orders", "csv")),
    "it/production_confirmations": (len(conf_rows), land_daily(pd.DataFrame(conf_rows), "confirmed_ts", "it/production_confirmations", "csv")),
    "it/work_orders": (len(wo_rows), land_daily(pd.DataFrame(wo_rows), "created_ts", "it/work_orders", "csv")),
}
land_snapshot(assets_df, "it/assets"); summary["it/assets"] = (len(assets_df), 1)
land_snapshot(shift_df, "it/shift_calendar"); summary["it/shift_calendar"] = (len(shift_df), 1)
land_snapshot(operators_df, "it/operators"); summary["it/operators"] = (len(operators_df), 1)

print(f"{'source':32s} {'rows':>10s} {'files':>6s}")
for k, (rows, files) in summary.items():
    print(f"{k:32s} {rows:>10,} {files:>6}")

# COMMAND ----------

# MAGIC %md ## Ground truth (for validating the model later — not landed for the pipeline)

# COMMAND ----------

truth = pd.DataFrame(truth_rows).sort_values("failure_start")
print(truth.to_string(index=False))
print("\nInjected defects: BAD-quality rows =", int((hist.quality == "BAD").sum()),
      "| 9999 spikes =", int((hist.value == 9999.0).sum()),
      "| negative-scrap confirmations =", int((pd.DataFrame(conf_rows).scrap_qty < 0).sum()),
      "| unmapped tag rows =", len(util))
