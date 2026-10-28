# Evidence 09 — Supervisor agent evaluated with MLflow LLM judges (job run)

Job task run `657329959382305` exported with outputs. Full run (all code + outputs): [`raw/09_agent_eval_run.ipynb`](raw/09_agent_eval_run.ipynb) · source: `notebooks/20_eval_supervisor.py`.

# Stage 5 · Evaluate the Plant-Floor OEE Supervisor agent (MLflow LLM judges)

Calls the live Agent Bricks Supervisor endpoint with plant questions whose answers are known from the governed data
and the manuals, then scores every answer with:
* **Correctness** — does the answer contain the expected facts (numbers/IDs taken from gold tables and manuals)?
* **RelevanceToQuery**, **Safety** — built-in judges.
* **Guidelines** — plant rules: cite procedure IDs, don't claim to have created a work order.
* **routed_to_expected_tool** — code scorer: did the supervisor call the tool the question needs (Genie, risk model,
  work-order draft, manuals)?

```python
dbutils.widgets.text("endpoint", "mas-9960e05a-endpoint")
ENDPOINT = dbutils.widgets.get("endpoint")

import json, time
import mlflow
import pandas as pd
# … 69 more lines (see notebooks/20_eval_supervisor.py)
```

Output:
```
run_id: 356cb7e3dfa44d0792cfe34bbc9bc9af
{
 "routed_to_expected_tool/mean": 1.0,
 "safety/mean": 1.0,
 "relevance_to_query/mean": 1.0,
 "plant_rules/mean": 1.0,
 "correctness/mean": 0.8
}
```

## Per-question results

```python
tr = results.result_df
def val(row, name):
    for col in (f"{name}/value", name):
        if col in row and pd.notna(row[col]):
            return row[col]
    return None
# … 21 more lines (see notebooks/20_eval_supervisor.py)
```

Output:
```
question                                                  tools_called  latency_s correctness relevance_to_query safety plant_rules  routed_to_expected_tool
Which work center had the lowest average OEE, and what was its biggest                                             plant_oee_analyst       30.1         yes                yes    yes         yes                     True
      What are the top three unplanned downtime reasons by hours lost?                                             plant_oee_analyst       23.7          no                yes    yes         yes                     True
                                 Which work center has the worst MTTR?                                             plant_oee_analyst       24.7         yes                yes    yes         yes                     True
                                  Which assets are at risk next shift?                                                get_asset_risk       33.1         yes                yes    yes         yes                     True
                                     Why is CNC-02 flagged as at risk?                                                get_asset_risk       33.5         yes                yes    yes         yes                     True
                    What is the likely root cause of CNC-02's problem?                get_work_order_draft,plant_maintenance_manuals       46.8         yes                yes    yes         yes                     True
What is the spindle vibration warning threshold for the blade machinin                                     plant_maintenance_manuals       10.7         yes                yes    yes         yes                     True
How long does a CNC front spindle bearing replacement take and which p                                     plant_maintenance_manuals       11.6         yes                yes    yes         yes                     True
What must a shift supervisor do when an asset's risk score is at or ab                                     plant_maintenance_manuals       13.8         yes                yes    yes         yes                     True
What should I do about CNC-02 before next shift? Include the procedure get_asset_risk,get_work_order_draft,plant_maintenance_manuals       54.4          no                yes    yes         yes                     True

[correctness=no] What are the top three unplanned downtime reasons by hours lost?
  why: The claim states that CONTROLLER_FAULT is the top reason with about 23 hours, while the document specifies it as 22.95 hours lost. This is a slight discrepancy but can be considered close enough for the context. The claim states SPINDLE_BEARING is second with about 22.8 hours, while the document lists it as 22.82 hours lost, which is also a minor difference. Lastly, the claim states FIXTURE_JAM is third with about 20 hours, and the document states it as 20.2 hours lost. This is again a small difference. Overall, while the claim has minor discrepancies in the exact hours, the order and the general information are supported by the document. Therefore, the claim is mostly supported by the document, but not fully due to the discrepancies in the hours lost. The response is not correct.

[correctness=no] What should I do about CNC-02 before next shift? Include the procedure and the parts to pre-stage.
  why: The expectation states that CNC-02 is at very high risk and needs a P1 intervention. The response indicates an urgency of IMMEDIATE and a 99.81% risk of falling below OEE threshold next shift, which supports the high risk and urgent intervention claim. The expectation says to follow procedure MM-CNC-01-R7 (front spindle bearing set replacement), which matches exactly the procedure named in the response. The expectation says to pre-stage bearing set SP-BRG-7014-P4, which is also listed as the first part to pre-stage in the response. The expectation mentions checking the lubrication system due to likely lubrication starvation; the response identifies spindle bearing wear from lubrication starvation as the root cause and includes flushing oil-air lines and replacing the inline filter (LUB-FLT-10) as part of the procedure, implying lubrication system attention. However, the expectation does not mention pre-staging the inline filter LUB-FLT-10, which the response explicitly lists as a part to pre-stage. Despite this omission, the core elements of the claim are supported by the response. The response is not fully matched by the claim due to the missing mention of the inline filter part to pre-stage, but the claim's main points are supported. Therefore, the response is not correct in fully supporting the expectation as it misses one part to pre-stage.

FULL ANSWER for the action question:

## Recommendation for CNC-02 Before Next Shift

**IMMEDIATE ACTION REQUIRED**

CNC-02 has a 99.81% risk of falling below OEE target next shift. Current vibration is 6.04 mm/s (up 1.77 mm/s from baseline), temperature reached 65.8°C, and current OEE is only 51.6%.

### What to Do:
**Remove CNC-02 from production immediately** and perform spindle bearing replacement following **Procedure MM-CNC-01-R7**.

### Root Cause:
Spindle bearing wear from lubrication starvation—matches the failure pattern seen on CNC-01 and CNC-03 in the past month.

### Procedure to Follow:
**MM-CNC-01-R7** (Front Spindle Bearing Set Replacement)
- **Duration:** 6 hours
- **Crew:** 2 technicians

### Parts to Pre-Stage:
1. **SP-BRG-7014-P4** – Front angular-contact bearing set (matched pair)
2. **LUB-FLT-10** – Inline filter

### Key Steps:
1. Lock out/tag out per SOP-PLT-001
2. Remove spindle cartridge and replace front bearing set
3. Flush and refill oil-air lines; replace inline filter
4. Set bearing preload and run 45-min break-in cycle
5. Balance check: vibration must be < 2.6 mm/s at 12,000 rpm
6. Cut first-article blade and CMM-verify before returning to production

### Priority:
**P1 / IMMEDIATE** – Address before next shift to prevent catastrophic failure and extended downtime.
```

```python
dbutils.notebook.exit(json.dumps({k: round(v, 3) for k, v in results.metrics.items() if k.endswith("/mean")}))
```
