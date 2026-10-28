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

## MES vs OT count reconciliation

```
shifts | shifts_with_variance | abs_unit_variance | mes_total_units | ot_cycle_units
-------+----------------------+-------------------+-----------------+---------------
1008   | 46                   | 257.0             | 72296           | 72457.0       
```

More output: [`02b_lakeflow_gold_reliability.md`](02b_lakeflow_gold_reliability.md).
