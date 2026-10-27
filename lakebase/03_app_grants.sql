-- Stage 6 · Least-privilege Postgres grants for the app's service principal role (substituted as {app_role}).
-- Read: the synced tables. Write: insert actions / work-order requests; update only work-order status.
GRANT USAGE ON SCHEMA plant_floor_oee_febar, ops TO "{app_role}";
GRANT SELECT ON ALL TABLES IN SCHEMA plant_floor_oee_febar TO "{app_role}";
GRANT SELECT, INSERT ON ops.supervisor_actions, ops.work_order_requests TO "{app_role}";
GRANT UPDATE (status, updated_at) ON ops.work_order_requests TO "{app_role}";
GRANT USAGE ON ALL SEQUENCES IN SCHEMA ops TO "{app_role}";
