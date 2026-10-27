# Evidence 02 — Lakeflow medallion pipeline (live query output)

Generated 2026-10-27 17:48 by `ops/stage1_evidence.py` against `nraameast1_catalog.plant_floor_oee_febar` on the SQL warehouse.

Pipeline `plant_oee_medallion` id `f14b8374-58e5-4d77-a962-8b291340d5b5` · update `9a58a44b-3a0e-4330-8d2c-d8079a741ea2` · state **COMPLETED** · cause JOB_TASK · full_refresh=True

## Tables produced (row counts)

```
layer  | t                                  | n      
-------+------------------------------------+--------
bronze | bronze_ot_historian                | 1939980
bronze | bronze_ot_machine_states           | 8730   
bronze | bronze_ot_alarms                   | 786    
bronze | bronze_it_production_orders        | 1367   
bronze | bronze_it_production_confirmations | 1367   
bronze | bronze_it_work_orders              | 147    
silver | silver_ot_historian                | 1933802
silver | silver_ot_tag_minute               | 483840 
silver | silver_ot_machine_states           | 8730   
silver | silver_production_confirmations    | 1364   
silver | silver_work_orders                 | 147    
gold   | gold_oee_shift                     | 1008   
gold   | gold_downtime_events               | 165    
gold   | gold_asset_reliability             | 12     
gold   | gold_shift_features                | 1008   
```

## Data-quality expectations (from the pipeline event log, latest update)

```
dataset                         | expectation          | passed  | failed
--------------------------------+----------------------+---------+-------
gold_oee_shift                  | oee_in_range         | 1008    | 0     
silver_assets                   | asset_id_present     | 12      | 0     
silver_assets                   | valid_ideal_cycle    | 12      | 0     
silver_ot_alarms                | equipment_mapped     | 786     | 0     
silver_ot_historian             | good_opc_quality     | 1937162 | 2818  
silver_ot_historian             | physically_plausible | 1936490 | 3490  
silver_ot_historian             | tag_mapped_to_asset  | 1937292 | 2688  
silver_ot_historian             | valid_timestamp      | 1939980 | 0     
silver_ot_machine_states        | equipment_mapped     | 8730    | 0     
silver_ot_machine_states        | known_state          | 8730    | 0     
silver_ot_machine_states        | valid_interval       | 8730    | 0     
silver_production_confirmations | equipment_mapped     | 1367    | 0     
silver_production_confirmations | non_negative_scrap   | 1364    | 3     
silver_production_confirmations | non_negative_yield   | 1367    | 0     
silver_production_orders        | equipment_mapped     | 1367    | 0     
silver_production_orders        | positive_plan        | 1367    | 0     
silver_work_orders              | closed_after_created | 147     | 0     
silver_work_orders              | equipment_mapped     | 147     | 0     
```

## IT/OT key resolution — every silver row carries one asset_id

```
asset_id | it_key   | ot_key             | ot_tag_rows | it_orders | it_work_orders
---------+----------+--------------------+-------------+-----------+---------------
CMM-01   | EQ-10011 | PLT1.WC_INSP.CMM01 | 161165      | 120       | 23            
CMM-02   | EQ-10012 | PLT1.WC_INSP.CMM02 | 161167      | 113       | 9             
CNC-01   | EQ-10001 | PLT1.WC_MACH.CNC01 | 161158      | 113       | 16            
CNC-02   | EQ-10002 | PLT1.WC_MACH.CNC02 | 161140      | 106       | 11            
CNC-03   | EQ-10003 | PLT1.WC_MACH.CNC03 | 161143      | 114       | 12            
CNC-04   | EQ-10004 | PLT1.WC_MACH.CNC04 | 161120      | 114       | 13            
CTG-01   | EQ-10007 | PLT1.WC_COAT.CTG01 | 161164      | 120       | 11            
CTG-02   | EQ-10008 | PLT1.WC_COAT.CTG02 | 161125      | 113       | 10            
GRD-01   | EQ-10005 | PLT1.WC_GRND.GRD01 | 161139      | 113       | 11            
GRD-02   | EQ-10006 | PLT1.WC_GRND.GRD02 | 161160      | 106       | 10            
WLD-01   | EQ-10009 | PLT1.WC_WELD.WLD01 | 161161      | 117       | 10            
WLD-02   | EQ-10010 | PLT1.WC_WELD.WLD02 | 161160      | 118       | 11            
```

## OEE by work center (28 days)

```
work_center_name        | availability | performance | quality | oee   | unplanned_hrs | scrap_units | good_units
------------------------+--------------+-------------+---------+-------+---------------+-------------+-----------
Root Form Grinding      | 0.899        | 0.815       | 0.971   | 0.714 | 29.2          | 484         | 17789     
Thermal Barrier Coating | 0.903        | 0.852       | 0.954   | 0.734 | 17.9          | 261         | 5492      
Blade Machining         | 0.899        | 0.843       | 0.97    | 0.737 | 52.0          | 803         | 27565     
Vane Segment Welding    | 0.901        | 0.844       | 0.974   | 0.742 | 21.4          | 208         | 7922      
CMM Inspection          | 0.903        | 0.871       | 0.994   | 0.783 | 19.4          | 66          | 11706     
```

## Asset reliability (MTTR / MTBF)

```
asset_id | work_center | avg_oee | avg_availability | avg_performance | avg_quality | scrap_rate | unplanned_stops | major_failures | unplanned_hours | mttr_min | mtbf_hours
---------+-------------+---------+------------------+-----------------+-------------+------------+-----------------+----------------+-----------------+----------+-----------
CNC-03   | WC_MACH     | 0.7063  | 0.8951           | 0.8191          | 0.9588      | 0.0386     | 13              | 2              | 14.8            | 68.4     | 42.9      
GRD-02   | WC_GRND     | 0.7083  | 0.8959           | 0.8131          | 0.9654      | 0.031      | 10              | 2              | 18.2            | 108.9    | 55.9      
CNC-01   | WC_MACH     | 0.7108  | 0.8834           | 0.8285          | 0.9654      | 0.0312     | 21              | 2              | 22.2            | 63.3     | 26.2      
WLD-02   | WC_WELD     | 0.7115  | 0.8953           | 0.8221          | 0.9643      | 0.0341     | 11              | 2              | 14.9            | 81.1     | 50.8      
CTG-01   | WC_COAT     | 0.716   | 0.8971           | 0.8333          | 0.9571      | 0.0422     | 15              | 1              | 10.6            | 42.4     | 37.3      
GRD-01   | WC_GRND     | 0.7199  | 0.9022           | 0.8163          | 0.9766      | 0.022      | 12              | 1              | 11.1            | 55.3     | 46.8      
CTG-02   | WC_COAT     | 0.7526  | 0.9081           | 0.8711          | 0.9509      | 0.0483     | 12              | 0              | 7.3             | 36.3     | 47.2      
CNC-02   | WC_MACH     | 0.7604  | 0.9137           | 0.8538          | 0.9741      | 0.0255     | 10              | 0              | 6.4             | 38.5     | 57.0      
CNC-04   | WC_MACH     | 0.7705  | 0.9033           | 0.8692          | 0.9811      | 0.0188     | 13              | 0              | 8.6             | 39.7     | 43.4      
CMM-01   | WC_INSP     | 0.7718  | 0.8923           | 0.8686          | 0.995       | 0.0052     | 29              | 0              | 15.2            | 31.3     | 19.2      
WLD-01   | WC_WELD     | 0.7723  | 0.9068           | 0.8667          | 0.9828      | 0.0176     | 10              | 0              | 6.5             | 39.1     | 56.5      
CMM-02   | WC_INSP     | 0.7934  | 0.9139           | 0.8736          | 0.9939      | 0.006      | 9               | 0              | 4.3             | 28.6     | 63.3      
```

## CNC-03 around its first spindle-bearing failure — OT signal leads the IT outcome

```
shift_id     | vib_mm_s | vib_trend | vib_alarms | oee   | perf  | quality | unplanned_min | next_oee
-------------+----------+-----------+------------+-------+-------+---------+---------------+---------
2026-09-26-A | 2.21     | 0.01      | 0          | 0.782 | 0.866 | 0.989   | 0             | 0.773   
2026-09-26-B | 2.2      | 0.0       | 0          | 0.773 | 0.839 | 0.967   | 0             | 0.773   
2026-09-26-C | 2.2      | 0.0       | 0          | 0.773 | 0.850 | 0.978   | 0             | 0.747   
2026-09-27-A | 2.26     | 0.06      | 0          | 0.747 | 0.861 | 0.966   | 0             | 0.738   
2026-09-27-B | 2.36     | 0.15      | 0          | 0.738 | 0.856 | 0.933   | 0             | 0.738   
2026-09-27-C | 2.55     | 0.32      | 0          | 0.738 | 0.837 | 0.965   | 0             | 0.747   
2026-09-28-A | 2.84     | 0.55      | 0          | 0.747 | 0.815 | 0.977   | 0             | 0.684   
2026-09-28-B | 3.15     | 0.75      | 0          | 0.684 | 0.745 | 0.987   | 0             | 0.64    
2026-09-28-C | 3.52     | 0.96      | 0          | 0.64  | 0.767 | 0.96    | 0             | 0.604   
2026-09-29-A | 3.98     | 1.2       | 0          | 0.604 | 0.771 | 0.971   | 24            | 0.649   
2026-09-29-B | 4.47     | 1.4       | 6          | 0.649 | 0.737 | 0.924   | 0             | 0.605   
2026-09-29-C | 5.05     | 1.63      | 8          | 0.605 | 0.716 | 0.883   | 0             | 0.578   
2026-09-30-A | 5.68     | 1.85      | 8          | 0.578 | 0.692 | 0.89    | 0             | 0.569   
2026-09-30-B | 6.34     | 2.03      | 8          | 0.569 | 0.656 | 0.928   | 0             | 0.516   
2026-09-30-C | 7.03     | 2.19      | 8          | 0.516 | 0.632 | 0.921   | 0             | 0.462   
2026-10-01-A | 7.84     | 2.41      | 7          | 0.462 | 0.594 | 0.853   | 0             | 0.167   
2026-10-01-B | 5.61     | -0.46     | 2          | 0.167 | 0.708 | 0.87    | 327           | 0.764   
2026-10-01-C | 2.22     | -4.04     | 0          | 0.764 | 0.860 | 0.966   | 0             | 0.773   
2026-10-02-A | 2.17     | -3.62     | 0          | 0.773 | 0.871 | 0.956   | 0             | 0.702   
```

## Downtime linked to CMMS work orders (largest 10)

```
asset_id | reason_code     | start_ts                 | min | wo_id      | priority | minutes_to_work_order | minutes_to_close
---------+-----------------+--------------------------+-----+------------+----------+-----------------------+-----------------
GRD-02   | WHEEL_SPINDLE   | 2026-10-09T08:56:00.000Z | 441 | WO-7100068 | P1       | 4                     | 459             
CNC-01   | SPINDLE_BEARING | 2026-10-07T10:19:00.000Z | 434 | WO-7100010 | P1       | 6                     | 463             
GRD-02   | WHEEL_SPINDLE   | 2026-10-15T14:57:00.000Z | 332 | WO-7100070 | P1       | 4                     | 355             
CNC-03   | SPINDLE_BEARING | 2026-10-01T15:36:00.000Z | 327 | WO-7100031 | P1       | 8                     | 370             
CNC-01   | SPINDLE_BEARING | 2026-10-02T23:45:00.000Z | 325 | WO-7100005 | P1       | 7                     | 365             
WLD-02   | WIRE_FEED       | 2026-10-05T15:12:00.000Z | 299 | WO-7100110 | P1       | 8                     | 313             
CNC-03   | SPINDLE_BEARING | 2026-10-14T20:24:00.000Z | 283 | WO-7100036 | P1       | 3                     | 308             
CTG-01   | PLASMA_GUN      | 2026-10-09T15:38:00.000Z | 262 | WO-7100077 | P1       | 6                     | 285             
WLD-02   | WIRE_FEED       | 2026-10-14T06:57:00.000Z | 261 | WO-7100111 | P1       | 9                     | 280             
GRD-01   | WHEEL_SPINDLE   | 2026-10-01T22:06:00.000Z | 227 | WO-7100057 | P1       | 6                     | 266             
```

## MES vs OT count reconciliation

```
shifts | shifts_with_variance | abs_unit_variance | mes_total_units | ot_cycle_units
-------+----------------------+-------------------+-----------------+---------------
1008   | 46                   | 257.0             | 72296           | 72457.0       
```

## ML label balance + signal strength (gold_shift_features)

```
rows | next_shift_at_risk | at_risk_rate | corr_vib_next_oee | corr_vib_trend_next_oee | corr_temp_max_quality
-----+--------------------+--------------+-------------------+-------------------------+----------------------
1008 | 125                | 0.124        | -0.61             | -0.442                  | -0.42                
```
