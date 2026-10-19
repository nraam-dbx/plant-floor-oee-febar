"""Regenerate evidence/03_unity_catalog.md (governance: masking, tags, lineage) from live UC metadata."""
import datetime
from sql import run, table

C, SC = "nraameast1_catalog", "plant_floor_oee_febar"
S = f"{C}.{SC}"
SECTIONS = [
    ("PII masking — what a non-HR user sees (query as the build user, not in plant_hr_admins)",
     f"SELECT operator_id, full_name, badge_number, crew, certification_level FROM {S}.silver_operators ORDER BY operator_id LIMIT 6"),
    ("Column masks registered in Unity Catalog",
     f"SELECT table_name, column_name, mask_name FROM {C}.information_schema.column_masks WHERE table_schema = '{SC}' ORDER BY 1, 2"),
    ("Mask function definition",
     f"SELECT routine_name, routine_definition, comment FROM {C}.information_schema.routines WHERE routine_schema = '{SC}' AND routine_name = 'mask_pii'"),
    ("Domain / ownership tags per table (IT vs OT vs integrated gold)", f"""
SELECT table_name,
  max(CASE WHEN tag_name = 'oee_domain' THEN tag_value END) domain,
  max(CASE WHEN tag_name = 'oee_layer' THEN tag_value END) layer,
  max(CASE WHEN tag_name = 'oee_source_system' THEN tag_value END) source_system,
  max(CASE WHEN tag_name = 'oee_data_owner' THEN tag_value END) owner,
  max(CASE WHEN tag_name = 'oee_data_steward' THEN tag_value END) steward,
  max(CASE WHEN tag_name = 'system.certification_status' THEN tag_value END) certification,
  max(CASE WHEN tag_name = 'oee_pii' THEN tag_value END) pii
FROM {C}.information_schema.table_tags WHERE schema_name = '{SC}' GROUP BY 1 ORDER BY layer, domain, 1"""),
    ("Lineage captured by Unity Catalog (system.access.table_lineage) — raw volume to gold", f"""
SELECT DISTINCT coalesce(source_table_name, source_path) AS source, target_table_name AS target
FROM system.access.table_lineage
WHERE target_table_catalog = '{C}' AND target_table_schema = '{SC}' AND event_date >= '2026-10-19'
  AND (source_table_schema = '{SC}' OR source_path LIKE '/Volumes/{C}/{SC}/raw%')
ORDER BY target, source"""),
]
out = ["# Evidence 03 — Unity Catalog governance (live metadata)", "",
       f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M} by `ops/stage2_evidence.py`. Governance is applied by "
       "`agents/01_governance.sql` (function + tags) and by column `MASK` clauses in the pipeline SQL.", ""]
for title, sql in SECTIONS:
    out += [f"## {title}", "", "```", table(*run(sql)), "```", ""]
open("evidence/03_unity_catalog.md", "w").write("\n".join(out))
print("wrote evidence/03_unity_catalog.md")
