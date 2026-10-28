# Evidence 03 — Unity Catalog governance (live metadata)

Generated 2026-10-27 17:48 by `ops/stage2_evidence.py`. Governance is applied by `agents/01_governance.sql` (function + tags) and by column `MASK` clauses in the pipeline SQL.

## PII masking — what a non-HR user sees (query as the build user, not in plant_hr_admins)

```
operator_id | full_name | badge_number | crew | certification_level
------------+-----------+--------------+------+--------------------
OP-201      | A***      | B***         | A    | L1                 
OP-202      | J***      | B***         | B    | L2                 
OP-203      | S***      | B***         | C    | L3                 
OP-204      | T***      | B***         | A    | L1                 
OP-205      | C***      | B***         | B    | L2                 
OP-206      | M***      | B***         | C    | L3                 
```

## Column masks registered in Unity Catalog

```
table_name          | column_name  | mask_name                                        
--------------------+--------------+--------------------------------------------------
bronze_it_operators | badge_number | nraameast1_catalog.plant_floor_oee_febar.mask_pii
bronze_it_operators | full_name    | nraameast1_catalog.plant_floor_oee_febar.mask_pii
silver_operators    | badge_number | nraameast1_catalog.plant_floor_oee_febar.mask_pii
silver_operators    | full_name    | nraameast1_catalog.plant_floor_oee_febar.mask_pii
```

## Mask function definition

```
routine_name | routine_definition                                                                                                                                                                                   | comment                                                                                          
-------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------
mask_pii     | CASE WHEN is_member('plant_hr_admins') THEN value   -- workspace group (FEVM: no account-console access)
            WHEN value IS NULL THEN NULL
            ELSE concat(left(value, 1), '***') END | Column mask for operator PII: plant_hr_admins see the value, everyone else sees an initial + ***.
```

## Domain / ownership tags per table (IT vs OT vs integrated gold)

```
table_name                         | domain | layer       | source_system | owner                 | steward                 | certification | pii 
-----------------------------------+--------+-------------+---------------+-----------------------+-------------------------+---------------+-----
bronze_it_assets                   | IT     | bronze      | erp           | manufacturing_it      | production_planning     | None          | None
bronze_it_operators                | IT     | bronze      | mes           | manufacturing_it      | plant_hr                | None          | true
bronze_it_production_confirmations | IT     | bronze      | mes           | manufacturing_it      | production_planning     | None          | None
bronze_it_production_orders        | IT     | bronze      | erp           | manufacturing_it      | production_planning     | None          | None
bronze_it_shift_calendar           | IT     | bronze      | mes           | manufacturing_it      | production_planning     | None          | None
bronze_it_work_orders              | IT     | bronze      | cmms          | manufacturing_it      | maintenance_planning    | None          | None
bronze_ot_alarms                   | OT     | bronze      | scada         | controls_engineering  | reliability_engineering | None          | None
bronze_ot_historian                | OT     | bronze      | historian     | controls_engineering  | reliability_engineering | None          | None
bronze_ot_machine_states           | OT     | bronze      | scada         | controls_engineering  | reliability_engineering | None          | None
gold_asset_reliability             | IT_OT  | gold        | None          | operations_excellence | reliability_engineering | certified     | None
gold_asset_risk                    | IT_OT  | gold        | None          | operations_excellence | data_science            | None          | None
gold_asset_risk_insights           | IT_OT  | gold        | None          | operations_excellence | reliability_engineering | None          | None
gold_asset_shift_time              | IT_OT  | gold        | None          | operations_excellence | plant_performance       | certified     | None
gold_at_risk_queue                 | IT_OT  | gold        | None          | operations_excellence | plant_performance       | None          | None
gold_downtime_events               | IT_OT  | gold        | None          | operations_excellence | reliability_engineering | certified     | None
gold_oee_shift                     | IT_OT  | gold        | None          | operations_excellence | plant_performance       | certified     | None
gold_ot_cycles_shift               | IT_OT  | gold        | None          | operations_excellence | plant_performance       | None          | None
gold_shift_features                | IT_OT  | gold        | None          | operations_excellence | data_science            | None          | None
lb_supervisor_actions_history      | IT_OT  | operational | lakebase_app  | operations_excellence | None                    | None          | None
lb_work_order_requests_history     | IT_OT  | operational | lakebase_app  | operations_excellence | None                    | None          | None
silver_assets                      | IT     | silver      | None          | manufacturing_it      | production_planning     | None          | None
silver_operators                   | IT     | silver      | None          | manufacturing_it      | plant_hr                | None          | true
silver_production_confirmations    | IT     | silver      | None          | manufacturing_it      | production_planning     | None          | None
silver_production_orders           | IT     | silver      | None          | manufacturing_it      | production_planning     | None          | None
silver_shift_calendar              | IT     | silver      | None          | manufacturing_it      | production_planning     | None          | None
silver_work_orders                 | IT     | silver      | None          | manufacturing_it      | maintenance_planning    | None          | None
silver_ot_alarms                   | OT     | silver      | None          | controls_engineering  | reliability_engineering | None          | None
silver_ot_historian                | OT     | silver      | None          | controls_engineering  | reliability_engineering | None          | None
silver_ot_machine_states           | OT     | silver      | None          | controls_engineering  | reliability_engineering | None          | None
silver_ot_tag_minute               | OT     | silver      | None          | controls_engineering  | reliability_engineering | None          | None
```

More output: [`03b_unity_catalog_lineage.md`](03b_unity_catalog_lineage.md).
