# Databricks notebook source
# MAGIC %md
# MAGIC # Stage 5 · Evaluate the Plant-Floor OEE Supervisor agent (MLflow LLM judges)
# MAGIC
# MAGIC Calls the live Agent Bricks Supervisor endpoint with plant questions whose answers are known from the governed data
# MAGIC and the manuals, then scores every answer with:
# MAGIC * **Correctness** — does the answer contain the expected facts (numbers/IDs taken from gold tables and manuals)?
# MAGIC * **RelevanceToQuery**, **Safety** — built-in judges.
# MAGIC * **Guidelines** — plant rules: cite procedure IDs, don't claim to have created a work order.
# MAGIC * **routed_to_expected_tool** — code scorer: did the supervisor call the tool the question needs (Genie, risk model,
# MAGIC   work-order draft, manuals)?

# COMMAND ----------

# MAGIC %pip install -q "mlflow[databricks]>=3.4"
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("endpoint", "mas-9960e05a-endpoint")
ENDPOINT = dbutils.widgets.get("endpoint")

import json, time
import mlflow
import pandas as pd
from databricks.sdk import WorkspaceClient
from mlflow.genai.scorers import Correctness, Guidelines, RelevanceToQuery, Safety, scorer

w = WorkspaceClient()
mlflow.set_experiment(f"/Users/{w.current_user.me().user_name}/plant_oee_agent_eval")

GENIE, RISK, DRAFT, MANUALS = "plant_oee_analyst", "get_asset_risk", "get_work_order_draft", "plant_maintenance_manuals"
EVAL = [
    ("Which work center had the lowest average OEE, and what was its biggest loss factor?",
     ["Root Form Grinding (WC_GRND) has the lowest average OEE, about 71%", "Its biggest loss factor is performance"], [GENIE]),
    ("What are the top three unplanned downtime reasons by hours lost?",
     ["CONTROLLER_FAULT is the top reason with about 23 hours", "SPINDLE_BEARING is second with about 22.8 hours",
      "FIXTURE_JAM is third with about 20 hours"], [GENIE]),
    ("Which work center has the worst MTTR?",
     ["Root Form Grinding (WC_GRND) has the worst MTTR, roughly 80 minutes (79.7)"], [GENIE]),
    ("Which assets are at risk next shift?",
     ["CNC-02 is the only asset at risk", "CNC-02's risk is about 0.998 (99.8%)"], [RISK]),
    ("Why is CNC-02 flagged as at risk?",
     ["Vibration is rising (about 6.0 mm/s, up about 1.8 mm/s versus the prior shifts)", "Performance is down / OEE is about 52%"], [RISK]),
    ("What is the likely root cause of CNC-02's problem?",
     ["Spindle bearing wear or degradation", "Lubrication starvation is the likely cause"], [DRAFT]),
    ("What is the spindle vibration warning threshold for the blade machining CNCs?",
     ["The warning is triggered above 4.8 mm/s (VIB_HIGH alarm)"], [MANUALS]),
    ("How long does a CNC front spindle bearing replacement take and which part is needed?",
     ["Procedure MM-CNC-01-R7", "About 6 hours with 2 technicians", "Part SP-BRG-7014-P4"], [MANUALS]),
    ("What must a shift supervisor do when an asset's risk score is at or above 0.5?",
     ["Acknowledge it in the plant-floor app within one hour of shift handover",
      "Then create a work order, defer with a reason, or dismiss with a reason"], [MANUALS]),
    ("What should I do about CNC-02 before next shift? Include the procedure and the parts to pre-stage.",
     ["CNC-02 is at very high risk and needs a P1 intervention", "Follow MM-CNC-01-R7 (front spindle bearing set replacement)",
      "Pre-stage bearing set SP-BRG-7014-P4", "Check the lubrication system (likely lubrication starvation)"], [RISK, DRAFT, MANUALS]),
]

def call_supervisor(question):
    t0 = time.time()
    resp = w.api_client.do("POST", f"/serving-endpoints/{ENDPOINT}/invocations",
                           body={"input": [{"role": "user", "content": question}]})
    tools, texts = [], []
    for item in resp.get("output", []):
        if item.get("type") == "function_call":
            name = item.get("name", "")
            tools.append(next((t for t in (GENIE, RISK, DRAFT, MANUALS) if name.endswith(t)), name))
        elif item.get("type") == "message":
            texts += [c.get("text", "") for c in item.get("content", []) if c.get("text")]
    return {"response": texts[-1] if texts else "", "tools_called": tools, "latency_s": round(time.time() - t0, 1)}

def predict_fn(question):
    return call_supervisor(question)

@scorer
def routed_to_expected_tool(inputs, outputs, expectations):
    called = set(outputs.get("tools_called", []))
    missing = [t for t in expectations["expected_tools"] if t not in called]
    return not missing

data = [{"inputs": {"question": q}, "expectations": {"expected_facts": facts, "expected_tools": tools}} for q, facts, tools in EVAL]
# Guidelines judges see only the question and the answer (not tool outputs), so every rule must be checkable from those.
# Whether numbers/IDs are real is covered by Correctness against expected facts taken from the data and manuals.
guidelines = Guidelines(name="plant_rules", guidelines=[
    "If the answer recommends repair or replacement steps for equipment, it cites at least one procedure ID "
    "in the form MM-XXX-NN-XN (for example MM-CNC-01-R7). Answers that recommend no repair satisfy this rule.",
    "The answer never states or implies that the assistant itself created, submitted or scheduled a work order. "
    "Telling the user to create or confirm the work order in the plant-floor app is correct behaviour."])

with mlflow.start_run(run_name="supervisor_eval") as run:
    results = mlflow.genai.evaluate(data=data, predict_fn=predict_fn,
                                    scorers=[Correctness(), RelevanceToQuery(), Safety(), guidelines, routed_to_expected_tool])
print("run_id:", run.info.run_id)
print(json.dumps({k: round(v, 3) for k, v in results.metrics.items() if k.endswith("/mean")}, indent=1))

# COMMAND ----------

# MAGIC %md ## Per-question results

# COMMAND ----------

tr = results.result_df
def val(row, name):
    for col in (f"{name}/value", name):
        if col in row and pd.notna(row[col]):
            return row[col]
    return None
rows = []
for _, r in tr.iterrows():
    req = r.get("request") or {}
    resp = r.get("response") or {}
    q = req.get("question") if isinstance(req, dict) else str(req)
    rationale = {s: str(r.get(f"{s}/rationale", ""))[:160] for s in ("correctness", "plant_rules")}
    rows.append({"question": (q or "")[:70],
                 "tools_called": ",".join(resp.get("tools_called", [])) if isinstance(resp, dict) else "",
                 "latency_s": resp.get("latency_s") if isinstance(resp, dict) else None,
                 **{s: val(r, s) for s in ("correctness", "relevance_to_query", "safety", "plant_rules", "routed_to_expected_tool")}})
summary = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(summary.to_string(index=False))
for _, r in tr.iterrows():
    for s in ("correctness", "plant_rules"):
        v = val(r, s)
        if v not in (None, "yes", True):
            req = r.get("request") or {}
            print(f"\n[{s}={v}] {req.get('question') if isinstance(req, dict) else req}\n  why: {r.get(f'{s}/rationale', '')}")
print("\nFULL ANSWER for the action question:\n")
print(call_supervisor(EVAL[-1][0])["response"])

# COMMAND ----------

dbutils.notebook.exit(json.dumps({k: round(v, 3) for k, v in results.metrics.items() if k.endswith("/mean")}))
