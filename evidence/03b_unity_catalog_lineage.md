# Evidence 03b — Unity Catalog lineage, raw volume → bronze → silver → gold → Lakebase (live metadata)

Generated 2026-10-27 17:48 by `ops/stage2_evidence.py`. Governance is applied by `agents/01_governance.sql` (function + tags) and by column `MASK` clauses in the pipeline SQL.

Companion to [`03_unity_catalog.md`](03_unity_catalog.md).

## Lineage captured by Unity Catalog (system.access.table_lineage) — raw volume to gold

```
source                                                                   | target                         
-------------------------------------------------------------------------+--------------------------------
/Volumes/nraameast1_catalog/plant_floor_oee_febar/raw/it/assets/         | bronze_it_assets               
/Volumes/nraameast1_catalog/plant_floor_oee_febar/raw/it/operators/      | bronze_it_operators            
/Volumes/nraameast1_catalog/plant_floor_oee_febar/raw/it/shift_calendar/ | bronze_it_shift_calendar       
gold_at_risk_queue                                                       | gold_alert_response            
gold_supervisor_actions                                                  | gold_alert_response            
silver_shift_calendar                                                    | gold_alert_response            
gold_downtime_events                                                     | gold_asset_reliability         
gold_oee_shift                                                           | gold_asset_reliability         
silver_assets                                                            | gold_asset_reliability         
gold_asset_risk                                                          | gold_asset_risk_insights       
silver_assets                                                            | gold_asset_risk_insights       
silver_work_orders                                                       | gold_asset_risk_insights       
silver_ot_machine_states                                                 | gold_asset_shift_time          
silver_shift_calendar                                                    | gold_asset_shift_time          
gold_asset_risk                                                          | gold_at_risk_queue             
gold_asset_risk_insights                                                 | gold_at_risk_queue             
silver_assets                                                            | gold_at_risk_queue             
silver_assets                                                            | gold_downtime_events           
silver_ot_machine_states                                                 | gold_downtime_events           
silver_shift_calendar                                                    | gold_downtime_events           
silver_work_orders                                                       | gold_downtime_events           
gold_asset_shift_time                                                    | gold_oee_shift                 
gold_ot_cycles_shift                                                     | gold_oee_shift                 
silver_assets                                                            | gold_oee_shift                 
silver_production_confirmations                                          | gold_oee_shift                 
silver_production_orders                                                 | gold_oee_shift                 
silver_ot_tag_minute                                                     | gold_ot_cycles_shift           
silver_shift_calendar                                                    | gold_ot_cycles_shift           
gold_oee_shift                                                           | gold_shift_features            
silver_assets                                                            | gold_shift_features            
silver_ot_alarms                                                         | gold_shift_features            
silver_ot_tag_minute                                                     | gold_shift_features            
silver_shift_calendar                                                    | gold_shift_features            
lb_supervisor_actions_history                                            | gold_supervisor_actions        
lb_work_order_requests_history                                           | gold_work_order_requests       
gold_at_risk_queue                                                       | lb_at_risk_queue               
gold_oee_shift                                                           | lb_oee_shift                   
bronze_it_assets                                                         | silver_assets                  
bronze_it_operators                                                      | silver_operators               
bronze_ot_alarms                                                         | silver_ot_alarms               
silver_assets                                                            | silver_ot_alarms               
bronze_ot_historian                                                      | silver_ot_historian            
silver_assets                                                            | silver_ot_historian            
bronze_ot_machine_states                                                 | silver_ot_machine_states       
silver_assets                                                            | silver_ot_machine_states       
silver_ot_historian                                                      | silver_ot_tag_minute           
bronze_it_production_confirmations                                       | silver_production_confirmations
silver_assets                                                            | silver_production_confirmations
bronze_it_production_orders                                              | silver_production_orders       
silver_assets                                                            | silver_production_orders       
bronze_it_shift_calendar                                                 | silver_shift_calendar          
bronze_it_work_orders                                                    | silver_work_orders             
silver_assets                                                            | silver_work_orders             
```
