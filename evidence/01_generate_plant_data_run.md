# Evidence 01 — Synthetic IT + OT source data landed in UC (job run)

Job task run `431970301759147` exported with outputs. Full run (all code + outputs): [`raw/01_generate_plant_data_run.ipynb`](raw/01_generate_plant_data_run.ipynb) · source: `data_generation/generate_plant_data.py`.

# Plant-floor OEE — synthetic IT + OT data generator

Simulates one turbine-component plant (12 assets, 5 work centers) minute-by-minute and lands the
raw extracts each source system would produce into a UC volume. Lakeflow ingests them from there.

| System | Domain | Keyed on | Files |
|---|---|---|---|
| Historian (1-min tags) | OT | `tag_name` e.g. `PLT1.WC_MACH.CNC03.VIBRATION` | `raw/ot/historian/*.csv` |
| SCADA machine states | OT | `equipment_path` e.g. `PLT1.WC_MACH.CNC03` | `raw/ot/machine_states/*.json` |
| SCADA alarms | OT | `equipment_path` | `raw/ot/alarms/*.json` |
| ERP equipment master | IT | `erp_equipment_id` e.g. `EQ-10003` (+ historian prefix = the IT↔OT key map) | `raw/it/assets/` |
| ERP/MES production orders + confirmations | IT | `erp_equipment_id`, `shift_id` | `raw/it/production_*` |
| CMMS work orders | IT | `erp_equipment_id` | `raw/it/work_orders/` |
| Shift calendar, operators (PII) | IT | `shift_id`, `operator_id` | `raw/it/shift_calendar/`, `raw/it/operators/` |

Embedded stories (what the pipeline, model and agent should rediscover):
* **Degradation → failure** — vibration/temperature creep and speed loss for 3–6 days before a long
  unplanned stop (CNC-03 twice, plus random episodes elsewhere). This is the predictive signal.
* **In-flight degradation** — CNC-02 starts degrading ~4 days before the window ends; its failure falls after
  the window, so the latest-shift risk score should flag it (the "act now" case for the app and agent).
* **Coating temperature excursions** — CTG-02 booth temperature spikes drive scrap (a Quality loss).
* **Minor stops** — GRD-01 loses Performance to frequent 2–5 min stops.
* **Data-quality defects** for the pipeline expectations: BAD OPC quality, out-of-range spikes,
  duplicate tag rows, an unmapped historian tag, impossible MES confirmations.

```python
dbutils.widgets.text("catalog", "nraameast1_catalog")
dbutils.widgets.text("schema", "plant_floor_oee_febar")
dbutils.widgets.text("start_date", "2026-09-21")
dbutils.widgets.text("days", "28")
dbutils.widgets.text("seed", "42")

# … 7 more lines (see data_generation/generate_plant_data.py)
```

Output:
```
Landing 28 days from 2026-09-21 into /Volumes/nraameast1_catalog/plant_floor_oee_febar/raw (seed=42)
```

```python
import json, os, shutil
import numpy as np
import pandas as pd

SHIFT_MIN = 480
N = DAYS * 1440
# … 32 more lines (see data_generation/generate_plant_data.py)
```

## IT master data — equipment (with the IT↔OT key map), shift calendar, operators

```python
assets_master = []
for i, (aid, wc, *_rest) in enumerate(ASSETS):
    wc_name, ideal_s, kw, _vib, parts, fmode = WORK_CENTERS[wc]
    assets_master.append(dict(
        erp_equipment_id=f"EQ-{10001 + i}", asset_id=aid,
        asset_name=f"{wc_name} {aid}", work_center=wc, work_center_name=wc_name,
# … 26 more lines (see data_generation/generate_plant_data.py)
```

Output:
```
erp_equipment_id	asset_id	asset_name	work_center	work_center_name	historian_prefix	ideal_cycle_time_s	rated_power_kw	criticality	install_year	primary_failure_mode	plant
EQ-10001	CNC-01	Blade Machining CNC-01	WC_MACH	Blade Machining	PLT1.WC_MACH.CNC01	240	45	A	2012	SPINDLE_BEARING	PLT1
EQ-10002	CNC-02	Blade Machining CNC-02	WC_MACH	Blade Machining	PLT1.WC_MACH.CNC02	240	45	A	2015	SPINDLE_BEARING	PLT1
EQ-10003	CNC-03	Blade Machining CNC-03	WC_MACH	Blade Machining	PLT1.WC_MACH.CNC03	240	45	A	2018	SPINDLE_BEARING	PLT1
EQ-10004	CNC-04	Blade Machining CNC-04	WC_MACH	Blade Machining	PLT1.WC_MACH.CNC04	240	45	A	2021	SPINDLE_BEARING	PLT1
EQ-10005	GRD-01	Root Form Grinding GRD-01	WC_GRND	Root Form Grinding	PLT1.WC_GRND.GRD01	180	30	B	2013	WHEEL_SPINDLE	PLT1
EQ-10006	GRD-02	Root Form Grinding GRD-02	WC_GRND	Root Form Grinding	PLT1.WC_GRND.GRD02	180	30	B	2016	WHEEL_SPINDLE	PLT1
EQ-10007	CTG-01	Thermal Barrier Coating CTG-01	WC_COAT	Thermal Barrier Coating	PLT1.WC_COAT.CTG01	600	80	A	2019	PLASMA_GUN	PLT1
EQ-10008	CTG-02	Thermal Barrier Coating CTG-02	WC_COAT	Thermal Barrier Coating	PLT1.WC_COAT.CTG02	600	80	A	2022	PLASMA_GUN	PLT1
EQ-10009	WLD-01	Vane Segment Welding WLD-01	WC_WELD	Vane Segment Welding	PLT1.WC_WELD.WLD01	420	25	B	2014	WIRE_FEED	PLT1
EQ-10010	WLD-02	Vane Segment Welding WLD-02	WC_WELD	Vane Segment Welding	PLT1.WC_WELD.WLD02	420	25	B	2017	WIRE_FEED	PLT1
EQ-10011	CMM-01	CMM Inspection CMM-01	WC_INSP	CMM Inspection	PLT1.WC_INSP.CMM01	300	5	B	2020	PROBE_FAULT	PLT1
EQ-10012	CMM-02	CMM Inspection CMM-02	WC_INSP	CMM Inspection	PLT1.WC_INSP.CMM02	300	5	B	2012	PROBE_FAULT	PLT1
```

## Minute-level simulation per asset

```python
hist_frames, state_rows, alarm_rows, order_rows, conf_rows, wo_rows = [], [], [], [], [], []
truth_rows = []   # ground-truth failure episodes, printed for the evidence log (not landed)
order_seq, wo_seq = 2600001, 7100001

WO_TEXT = {
    "SPINDLE_BEARING": ("Spindle vibration high and audible noise from spindle housing; part surface finish out of tolerance.",
# … 205 more lines (see data_generation/generate_plant_data.py)
```

Output:
```
Simulated 12 assets x 40,320 minutes
```

## Land raw extracts in the UC volume

```python
def reset(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

def land_daily(df, ts_col, sub, kind):
# … 36 more lines (see data_generation/generate_plant_data.py)
```

Output:
```
source                                 rows  files
ot/historian                      1,939,980     29
ot/machine_states                     8,730     29
ot/alarms                               786     29
it/production_orders                  1,367     29
it/production_confirmations           1,367     29
it/work_orders                          147     30
it/assets                                12      1
it/shift_calendar                        84      1
it/operators                             18      1
```

## Ground truth (for validating the model later — not landed for the pipeline)

```python
truth = pd.DataFrame(truth_rows).sort_values("failure_start")
print(truth.to_string(index=False))
print("\nInjected defects: BAD-quality rows =", int((hist.quality == "BAD").sum()),
      "| 9999 spikes =", int((hist.value == 9999.0).sum()),
      "| negative-scrap confirmations =", int((pd.DataFrame(conf_rows).scrap_qty < 0).sum()),
      "| unmapped tag rows =", len(util))
```

Output:
```
asset_id       failure_start  duration_min  ramp_days    failure_mode                       note
  CNC-03 2026-10-01 15:36:00           327        4.5 SPINDLE_BEARING                           
  GRD-01 2026-10-01 22:06:00           227        4.1   WHEEL_SPINDLE                           
  CNC-01 2026-10-02 23:45:00           325        4.0 SPINDLE_BEARING                           
  WLD-02 2026-10-05 15:12:00           299        5.5       WIRE_FEED                           
  CNC-01 2026-10-07 10:19:00           434        4.6 SPINDLE_BEARING                           
  GRD-02 2026-10-09 08:56:00           441        4.2   WHEEL_SPINDLE                           
  CTG-01 2026-10-09 15:38:00           262        5.8      PLASMA_GUN                           
  WLD-02 2026-10-14 06:57:00           261        4.5       WIRE_FEED                           
  CNC-03 2026-10-14 20:24:00           283        5.8 SPINDLE_BEARING                           
  GRD-02 2026-10-15 14:57:00           332        5.6   WHEEL_SPINDLE                           
  CNC-02 2026-10-20 06:00:00           191        5.0 SPINDLE_BEARING after window (in progress)

Injected defects: BAD-quality rows = 2818 | 9999 spikes = 673 | negative-scrap confirmations = 3 | unmapped tag rows = 2688
```
