"""Regenerate evidence/05_ml_genai.md: UC model registry state, live risk table, and the GenAI prompt + answer."""
import datetime, json, subprocess
from sql import run, table

S = "nraameast1_catalog.plant_floor_oee_febar"
MODEL = f"{S}.oee_at_risk_model"

def api(path):
    return json.loads(subprocess.run(["databricks", "api", "get", path, "-p", "fevm-nraameast1"],
                                     capture_output=True, text=True, check=True).stdout)

m = api(f"/api/2.1/unity-catalog/models/{MODEL}?include_aliases=true")
versions = api(f"/api/2.1/unity-catalog/models/{MODEL}/versions").get("model_versions", [])
out = ["# Evidence 05 — ML model in Unity Catalog + GenAI root cause (live)", "",
       f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M} by `ops/stage3_evidence.py`. Training run output (metrics vs "
       "baseline, early-warning check, SHAP drivers) is in `04_train_oee_at_risk_run.ipynb`.", "",
       "## Registered model", "", "```",
       f"name:        {m['full_name']}", f"description: {m.get('comment', '')}",
       f"aliases:     {', '.join(a['alias_name'] + ' -> v' + str(a['version_num']) for a in m.get('aliases', []))}",
       "versions:    " + ", ".join(f"v{v['version']} ({v['status']}, run {v.get('run_id', '')[:8]})" for v in sorted(versions, key=lambda v: v['version'])),
       "```", "",
       "## gold_asset_risk — latest-shift risk per asset (scored with @champion)", "", "```",
       table(*run(f"SELECT asset_id, scored_shift_id, round(oee,3) oee, round(vib_mean_running,2) vib_mm_s, round(risk_score,4) risk, at_risk, model_version, top_drivers FROM {S}.gold_asset_risk ORDER BY risk_score DESC")),
       "```", ""]
cols, rows = run(f"SELECT asset_id, round(risk_score,4), llm_endpoint, generated_at, past_work_orders, insight_json, llm_error FROM {S}.gold_asset_risk_insights ORDER BY risk_score DESC")
for asset, risk, ep, ts, hist, ans, err in rows:
    out += [f"## GenAI root cause — {asset} (risk {risk}, `{ep}` via ai_query, {ts})", "",
            "Grounding passed to the LLM — past corrective work orders for the same failure mode:", "", "```", hist, "```", "",
            "LLM answer (parsed into `gold_asset_risk_insights.insight`):", "", "```json",
            json.dumps(json.loads(ans), indent=1) if ans else f"(no answer) {err}", "```", ""]
open("evidence/05_ml_genai.md", "w").write("\n".join(out))
print("wrote evidence/05_ml_genai.md")
