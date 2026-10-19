# Execution evidence

Text-readable proof that each stage ran (notebook outputs, run logs, query results, model output).
Screenshots are not evidence on their own — every artifact here is committed as text/JSON/CSV/ipynb-with-outputs.

| File | Stage | What it proves | Regenerate |
|---|---|---|---|
| `01_generate_plant_data_run.ipynb` | 1 · Lakeflow (source) | Job-run export of the generator: row/file counts landed per IT/OT source, injected defects, ground-truth failure episodes | `python3 ops/export_run_evidence.py <task_run_id> evidence/01_generate_plant_data_run.ipynb` |
| `02_lakeflow_pipeline.md` | 1 · Lakeflow | Pipeline update state, row counts per layer, expectation pass/fail from the event log, IT↔OT key resolution, OEE by work center, MTTR/MTBF, CNC-03 degradation lead-up, MES-vs-OT reconciliation, ML label balance | `python3 ops/stage1_evidence.py` |
