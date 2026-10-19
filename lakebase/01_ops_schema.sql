-- Stage 4 · Writable operational tables in Lakebase Postgres (database databricks_postgres).
-- The app and the agent's create_work_order tool write here; a change-data-feed config replicates schema ops
-- back to Unity Catalog Delta tables, so supervisor actions join the analytics (alert -> action latency).
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.supervisor_actions (
  action_id        BIGSERIAL PRIMARY KEY,
  asset_id         TEXT        NOT NULL,
  scored_shift_id  TEXT        NOT NULL,          -- the shift whose risk score triggered the action
  risk_score       NUMERIC(6,4),
  action           TEXT        NOT NULL CHECK (action IN ('ACKNOWLEDGE', 'CREATE_WORK_ORDER', 'DEFER', 'DISMISS')),
  note             TEXT,
  work_order_request_id BIGINT,
  acted_by         TEXT        NOT NULL,
  acted_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.work_order_requests (
  request_id          BIGSERIAL PRIMARY KEY,
  asset_id            TEXT        NOT NULL,
  priority            TEXT        NOT NULL CHECK (priority IN ('P1', 'P2', 'P3')),
  problem_description TEXT        NOT NULL,
  planned_tasks       TEXT,
  estimated_hours     NUMERIC(5,1),
  source              TEXT        NOT NULL CHECK (source IN ('APP', 'AGENT')),   -- who drafted it
  status              TEXT        NOT NULL DEFAULT 'REQUESTED' CHECK (status IN ('REQUESTED', 'APPROVED', 'SENT_TO_CMMS', 'REJECTED')),
  requested_by        TEXT        NOT NULL,
  requested_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS supervisor_actions_asset_idx ON ops.supervisor_actions (asset_id, acted_at DESC);
CREATE INDEX IF NOT EXISTS work_order_requests_asset_idx ON ops.work_order_requests (asset_id, requested_at DESC);

-- Reverse sync (change data feed -> UC Delta) needs the full old row image on UPDATE/DELETE.
ALTER TABLE ops.supervisor_actions  REPLICA IDENTITY FULL;
ALTER TABLE ops.work_order_requests REPLICA IDENTITY FULL;
