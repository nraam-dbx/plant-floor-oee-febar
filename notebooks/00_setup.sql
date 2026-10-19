-- One-time setup: schema + landing volume for raw IT/OT extracts. Run before the first bundle deploy.
CREATE SCHEMA IF NOT EXISTS nraameast1_catalog.plant_floor_oee_febar
  COMMENT 'Plant-floor OEE: IT (ERP/MES/CMMS) + OT (historian/SCADA) integration. Medallion by table prefix.';
CREATE VOLUME IF NOT EXISTS nraameast1_catalog.plant_floor_oee_febar.raw
  COMMENT 'Landing zone for raw source-system extracts (ot/*, it/*).';
