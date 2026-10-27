# Evidence 05 — ML model in Unity Catalog + GenAI root cause (live)

Generated 2026-10-27 17:48 by `ops/stage3_evidence.py`. Training run output (metrics vs baseline, early-warning check, SHAP drivers) is in `04_train_oee_at_risk_run.ipynb`.

## Registered model

```
name:        nraameast1_catalog.plant_floor_oee_febar.oee_at_risk_model
description: Probability that an asset's NEXT-shift OEE falls below 0.65, from this shift's OT condition signals and IT outcomes. Trained on gold_shift_features. Input: 23 float features (see signature). Output: risk probability.
aliases:     champion -> v4
versions:    v1 (READY, run 54b96ff6), v2 (READY, run df482dc2), v3 (READY, run a34abfbc), v4 (READY, run 3e8d59b1)
```

## gold_asset_risk — latest-shift risk per asset (scored with @champion)

```
asset_id | scored_shift_id | oee   | vib_mm_s | risk   | at_risk | model_version | top_drivers                                                                             
---------+-----------------+-------+----------+--------+---------+---------------+-----------------------------------------------------------------------------------------
CNC-02   | 2026-10-18-C    | 0.516 | 6.04     | 0.9981 | true    | 4             | ["vib_trend_vs_prev6=1.77 (+3.70)","performance=0.65 (+2.56)","temp_mean=56.38 (+0.81)"]
CNC-04   | 2026-10-18-C    | 0.827 | 2.2      | 0.0682 | false   | 4             | ["performance=0.90 (+0.86)","vib_p95=2.63 (+0.65)","temp_mean=48.53 (+0.59)"]           
CMM-01   | 2026-10-18-C    | 0.833 | 0.3      | 0.037  | false   | 4             | ["minor_stop_count=0.00 (+0.47)","vib_max=0.40 (+0.28)","oee_prev3_avg=0.75 (+0.27)"]   
GRD-02   | 2026-10-18-C    | 0.807 | 1.83     | 0.0291 | false   | 4             | ["availability=0.93 (+0.47)","scrap_rate=0.01 (+0.24)","temp_mean=48.19 (+0.22)"]       
WLD-01   | 2026-10-18-C    | 0.762 | 0.9      | 0.0179 | false   | 4             | ["minor_stop_count=0.00 (+0.46)","vib_max=1.26 (+0.45)","oee_prev3_avg=0.70 (+0.32)"]   
CMM-02   | 2026-10-18-C    | 0.844 | 0.3      | 0.0169 | false   | 4             | ["temp_mean=49.16 (+0.32)","power_mean=3.40 (+0.26)","scrap_rate=0.00 (+0.18)"]         
WLD-02   | 2026-10-18-C    | 0.747 | 0.9      | 0.0146 | false   | 4             | ["performance=0.84 (+0.59)","oee=0.75 (+0.18)","temp_mean=48.47 (+0.13)"]               
CTG-02   | 2026-10-18-C    | 0.8   | 1.2      | 0.0144 | false   | 4             | ["availability=0.94 (+0.42)","temp_max=86.32 (+0.26)","performance=0.88 (+0.24)"]       
CTG-01   | 2026-10-18-C    | 0.756 | 1.2      | 0.0061 | false   | 4             | ["oee=0.76 (+0.28)","scrap_rate=0.00 (+0.23)","quality=1.00 (+0.12)"]                   
CNC-03   | 2026-10-18-C    | 0.818 | 2.19     | 0.004  | false   | 4             | ["vib_p95=2.62 (+0.68)","temp_mean=48.40 (+0.44)","scrap_rate=0.00 (+0.19)"]            
GRD-01   | 2026-10-18-C    | 0.667 | 1.8      | 0.0034 | false   | 4             | ["oee=0.67 (+0.46)","unplanned_down_min=62.00 (+0.35)","power_mean=16.83 (+0.24)"]      
CNC-01   | 2026-10-18-C    | 0.738 | 2.18     | 0.0026 | false   | 4             | ["oee=0.74 (+0.25)","vib_p95=2.58 (+0.14)","performance=0.87 (+0.04)"]                  
```

## GenAI root cause — CNC-02 (risk 0.9981, `databricks-claude-sonnet-4-6` via ai_query, 2026-10-27T21:42:28.498Z)

Grounding passed to the LLM — past corrective work orders for the same failure mode:

```
CNC-03 2026-10-14 [SPINDLE_BEARING, 4.8h]: Spindle vibration high and audible noise from spindle housing; part surface finish out of tolerance. FIX: Replaced front spindle bearing set, re-greased, ran balance check. Root cause: bearing wear from lubrication starvation.
CNC-01 2026-10-07 [SPINDLE_BEARING, 7.4h]: Spindle vibration high and audible noise from spindle housing; part surface finish out of tolerance. FIX: Replaced front spindle bearing set, re-greased, ran balance check. Root cause: bearing wear from lubrication starvation.
CNC-01 2026-10-02 [SPINDLE_BEARING, 5.7h]: Spindle vibration high and audible noise from spindle housing; part surface finish out of tolerance. FIX: Replaced front spindle bearing set, re-greased, ran balance check. Root cause: bearing wear from lubrication starvation.
CNC-03 2026-10-01 [SPINDLE_BEARING, 6.0h]: Spindle vibration high and audible noise from spindle housing; part surface finish out of tolerance. FIX: Replaced front spindle bearing set, re-greased, ran balance check. Root cause: bearing wear from lubrication starvation.
```

LLM answer (parsed into `gold_asset_risk_insights.insight`):

```json
{
 "probable_cause": "Spindle bearing wear, most likely driven by lubrication starvation, consistent with the dominant failure mode for this asset class and the vibration signature observed this shift.",
 "evidence": [
  "Running vibration 6.04 mm/s this shift, up 1.77 mm/s vs. prior 6-shift average \u2014 the single largest model driver at +3.70 SHAP units",
  "8 vibration alarms fired this shift, indicating the elevated vibration is sustained, not transient",
  "Current shift OEE 0.516, well below the 0.65 threshold; performance sub-score 0.65 is the second-largest model driver (+2.56)",
  "Max spindle temperature 65.8 \u00b0C this shift vs. 6-shift mean of 56.38 \u00b0C (+9.4 \u00b0C delta), consistent with increased bearing friction",
  "Model assigns 0.998 probability of OEE < 0.65 on next shift, indicating near-certain continued degradation",
  "Four recent corrective WOs on sister machines CNC-01 and CNC-03 (2026-10-01 through 2026-10-14) all share identical symptom pattern \u2014 high spindle vibration, surface finish out of tolerance \u2014 and identical root cause: bearing wear from lubrication starvation",
  "Typical documented failure mode for CNC-02 is SPINDLE_BEARING, aligning with all available historical evidence"
 ],
 "recommended_action": "Remove CNC-02 from production at the next available planned stop (or immediately if vibration exceeds safe operating limits or part quality is confirmed out of tolerance). Inspect and replace the front spindle bearing set, check and restore spindle lubrication system, re-grease per maintenance standard, and perform a spindle balance check before return to service. Investigate root cause of lubrication starvation to prevent recurrence across the CNC fleet.",
 "urgency": "IMMEDIATE",
 "confidence": "high",
 "work_order": {
  "priority": "P1",
  "problem_description": "CNC-02 Blade Machining: Spindle vibration elevated to 6.04 mm/s (+1.77 mm/s vs. 6-shift baseline) with 8 vibration alarms this shift and spindle temperature reaching 65.8 \u00b0C (vs. 56.38 \u00b0C mean). Current OEE 0.516; predictive model scores 0.998 probability of OEE < 0.65 next shift. Symptom pattern matches four recent SPINDLE_BEARING failures on CNC-01 and CNC-03 (2026-10-01 to 2026-10-14), all caused by bearing wear from lubrication starvation. Asset criticality: A.",
  "planned_tasks": [
   "Take CNC-02 out of service and lock out / tag out before beginning work",
   "Inspect spindle housing for audible noise and visible signs of bearing distress",
   "Check spindle lubrication system for blockages, low lubricant level, or delivery failure \u2014 address any deficiency found before reassembly",
   "Remove and inspect front spindle bearing set; document condition and wear pattern",
   "Replace front spindle bearing set (reference sister-machine WOs CNC-03 2026-10-14 and CNC-01 2026-10-07 for repair scope)",
   "Re-grease spindle per lubrication specification",
   "Run spindle balance check and verify vibration returns to baseline before releasing machine",
   "Verify part surface finish on first-off parts meets tolerance before resuming production",
   "Document findings and root cause; flag lubrication starvation pattern to maintenance supervisor for fleet-wide review of CNC-01, CNC-02, and CNC-03 lubrication intervals"
  ],
  "estimated_hours": 6.0
 }
}
```
