# Evidence 05 — ML model in Unity Catalog + GenAI root cause (live)

Generated 2026-10-19 15:00 by `ops/stage3_evidence.py`. Training run output (metrics vs baseline, early-warning check, SHAP drivers) is in `04_train_oee_at_risk_run.ipynb`.

## Registered model

```
name:        nraameast1_catalog.plant_floor_oee_febar.oee_at_risk_model
description: Probability that an asset's NEXT-shift OEE falls below 0.65, from this shift's OT condition signals and IT outcomes. Trained on gold_shift_features. Input: 23 float features (see signature). Output: risk probability.
aliases:     champion -> v3
versions:    v1 (READY, run 54b96ff6), v2 (READY, run df482dc2), v3 (READY, run a34abfbc)
```

## gold_asset_risk — latest-shift risk per asset (scored with @champion)

```
asset_id | scored_shift_id | oee   | vib_mm_s | risk   | at_risk | model_version | top_drivers                                                                             
---------+-----------------+-------+----------+--------+---------+---------------+-----------------------------------------------------------------------------------------
CNC-02   | 2026-10-18-C    | 0.516 | 6.04     | 0.9981 | true    | 3             | ["vib_trend_vs_prev6=1.77 (+3.70)","performance=0.65 (+2.56)","temp_mean=56.38 (+0.81)"]
CNC-04   | 2026-10-18-C    | 0.827 | 2.2      | 0.0682 | false   | 3             | ["performance=0.90 (+0.86)","vib_p95=2.63 (+0.65)","temp_mean=48.53 (+0.59)"]           
CMM-01   | 2026-10-18-C    | 0.833 | 0.3      | 0.037  | false   | 3             | ["minor_stop_count=0.00 (+0.47)","vib_max=0.40 (+0.28)","oee_prev3_avg=0.75 (+0.27)"]   
GRD-02   | 2026-10-18-C    | 0.807 | 1.83     | 0.0291 | false   | 3             | ["availability=0.93 (+0.47)","scrap_rate=0.01 (+0.24)","temp_mean=48.19 (+0.22)"]       
WLD-01   | 2026-10-18-C    | 0.762 | 0.9      | 0.0179 | false   | 3             | ["minor_stop_count=0.00 (+0.46)","vib_max=1.26 (+0.45)","oee_prev3_avg=0.70 (+0.32)"]   
CMM-02   | 2026-10-18-C    | 0.844 | 0.3      | 0.0169 | false   | 3             | ["temp_mean=49.16 (+0.32)","power_mean=3.40 (+0.26)","scrap_rate=0.00 (+0.18)"]         
WLD-02   | 2026-10-18-C    | 0.747 | 0.9      | 0.0146 | false   | 3             | ["performance=0.84 (+0.59)","oee=0.75 (+0.18)","temp_mean=48.47 (+0.13)"]               
CTG-02   | 2026-10-18-C    | 0.8   | 1.2      | 0.0144 | false   | 3             | ["availability=0.94 (+0.42)","temp_max=86.32 (+0.26)","performance=0.88 (+0.24)"]       
CTG-01   | 2026-10-18-C    | 0.756 | 1.2      | 0.0061 | false   | 3             | ["oee=0.76 (+0.28)","scrap_rate=0.00 (+0.23)","quality=1.00 (+0.12)"]                   
CNC-03   | 2026-10-18-C    | 0.818 | 2.19     | 0.004  | false   | 3             | ["vib_p95=2.62 (+0.68)","temp_mean=48.40 (+0.44)","scrap_rate=0.00 (+0.19)"]            
GRD-01   | 2026-10-18-C    | 0.667 | 1.8      | 0.0034 | false   | 3             | ["oee=0.67 (+0.46)","unplanned_down_min=62.00 (+0.35)","power_mean=16.83 (+0.24)"]      
CNC-01   | 2026-10-18-C    | 0.738 | 2.18     | 0.0026 | false   | 3             | ["oee=0.74 (+0.25)","vib_p95=2.58 (+0.14)","performance=0.87 (+0.04)"]                  
```

## GenAI root cause — CNC-02 (risk 0.9981, `databricks-claude-sonnet-4-6` via ai_query, 2026-10-19T19:00:06.474Z)

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
 "probable_cause": "Spindle bearing wear on CNC-02, most likely driven by lubrication starvation, consistent with the dominant failure mode for this asset class and the pattern seen in four recent corrective work orders on sister machines CNC-01 and CNC-03.",
 "evidence": [
  "Running vibration 6.04 mm/s this shift, up 1.77 mm/s vs prior 6-shift average \u2014 the single largest model driver at +3.70 SHAP weight",
  "8 vibration alarms triggered this shift, indicating the elevated vibration is not a transient spike",
  "Current OEE 0.516 is already well below the 0.65 threshold; next-shift OEE < 0.65 risk is 0.998",
  "Performance sub-score of 0.65 is the second-largest model driver (+2.56), consistent with spindle speed/feed-rate degradation typical of bearing wear",
  "Max spindle temperature 65.8 \u00b0C (6-shift mean 56.38 \u00b0C, +9.4 \u00b0C rise) \u2014 elevated temperature is consistent with increased bearing friction from lubrication starvation",
  "Asset criticality A and typical failure mode explicitly listed as SPINDLE_BEARING",
  "Four recent corrective WOs on CNC-01 and CNC-03 (2026-10-01 through 2026-10-14) all share identical root cause: bearing wear from lubrication starvation, same symptoms (high vibration, surface finish out of tolerance), same fix (front spindle bearing replacement, re-grease, balance check), with repair durations 4.8\u20137.4 h",
  "No conflicting data source points to an alternative failure mode in the supplied dataset"
 ],
 "recommended_action": "Remove CNC-02 from production at the next available planned stop (or immediately if vibration or temperature continues to rise this shift). Inspect front spindle bearing set for wear; inspect and restore lubrication system to address likely starvation root cause. Replace front spindle bearing set if wear is confirmed, re-grease, and run balance check before return to service. Verify lubrication delivery before restart to prevent recurrence.",
 "urgency": "IMMEDIATE",
 "confidence": "medium",
 "work_order": {
  "priority": "P1",
  "problem_description": "CNC-02 Blade Machining CNC \u2014 Suspected spindle bearing wear (lubrication starvation). This shift OEE 0.516; running vibration 6.04 mm/s (+1.77 mm/s vs 6-shift baseline); 8 vibration alarms; max spindle temperature 65.8 \u00b0C vs 6-shift mean 56.38 \u00b0C. Model predicts 99.8% probability of OEE < 0.65 on next shift. Pattern matches four recent SPINDLE_BEARING corrective WOs on CNC-01 and CNC-03 with root cause of lubrication starvation. Asset criticality A.",
  "planned_tasks": [
   "Lock out / tag out CNC-02 per site safety requirements before any inspection",
   "Inspect spindle lubrication system: check lubricant level, delivery lines, pump output, and filter condition for evidence of starvation",
   "Remove spindle housing access covers and visually inspect front spindle bearing set for wear, discoloration, pitting, or cage damage",
   "Replace front spindle bearing set if wear is confirmed (reference sister-machine repairs on CNC-01 and CNC-03 for scope)",
   "Re-grease spindle assembly with correct lubricant type and quantity per machine specification",
   "Restore and verify lubrication system operation before reassembly to address root cause",
   "Reassemble spindle housing and run dynamic balance check",
   "Perform trial run and record vibration level and temperature; confirm both are within acceptable baseline before releasing to production",
   "Document findings, actual root cause confirmation, and any additional defects found in CMMS"
  ],
  "estimated_hours": 6.5
 }
}
```
