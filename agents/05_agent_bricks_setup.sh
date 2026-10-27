#!/usr/bin/env bash
# Stage 5 · Agent Bricks as code: Knowledge Assistant over the manuals volume + Supervisor agent with 4 tools.
# Idempotent: reuses KNOWLEDGE_ASSISTANT / SUPERVISOR_AGENT from config.env when set; otherwise creates and records them.
# Prereqs: manuals uploaded (databricks fs cp -r agents/manuals dbfs:/Volumes/<cat>/<schema>/manuals),
#          agents/02_uc_functions.sql applied, Genie space created (python3 agents/03_genie_space.py).
set -euo pipefail
cd "$(dirname "$0")/.." && source config.env
F="${CATALOG}.${SCHEMA}"
j() { jq -c -n "$@"; }

if [ -z "${KNOWLEDGE_ASSISTANT:-}" ]; then
  KNOWLEDGE_ASSISTANT=$(databricks knowledge-assistants create-knowledge-assistant "Plant Maintenance Manuals" \
    "Answers how to diagnose and repair plant-floor equipment (blade machining CNCs, grinders, coating cells, welding cells, CMMs) and plant safety / OEE escalation rules, citing the maintenance manual or SOP." \
    --instructions "Answer only from the manuals and SOPs. Always cite the document ID and procedure ID (e.g. MM-CNC-01-R7, SOP-PLT-001). Include thresholds, part numbers and estimated hours when the manual gives them. If the manuals do not cover the question, say so." \
    -p "$PROFILE" -o json | jq -r .name)
  databricks knowledge-assistants create-knowledge-source "$KNOWLEDGE_ASSISTANT" -p "$PROFILE" -o json --json "$(j \
    --arg p "/Volumes/${CATALOG}/${SCHEMA}/manuals" '{display_name:"Maintenance manuals and SOPs", source_type:"files",
     description:"Synthetic maintenance manuals (MM-CNC-01, MM-GRD-01, MM-CTG-01, MM-WLD-01, MM-CMM-01) and plant SOP-PLT-001.", files:{path:$p}}')" >/dev/null
  echo "KNOWLEDGE_ASSISTANT=\"$KNOWLEDGE_ASSISTANT\"" >> config.env
else
  databricks knowledge-assistants sync-knowledge-sources "$KNOWLEDGE_ASSISTANT" -p "$PROFILE" >/dev/null   # pick up manual edits
fi
KA_ID=${KNOWLEDGE_ASSISTANT##*/}

if [ -z "${SUPERVISOR_AGENT:-}" ]; then
  SUPERVISOR_AGENT=$(databricks supervisor-agents create-supervisor-agent "Plant-Floor OEE Agent" \
    --description "Answers plant-floor OEE questions and recommends actions for at-risk assets by combining OEE analytics (Genie), next-shift risk predictions and AI work-order drafts (UC functions) and maintenance manuals (Knowledge Assistant)." \
    --instructions "$(cat agents/04_supervisor_instructions.md)" -p "$PROFILE" -o json | jq -r .name)
  echo "SUPERVISOR_AGENT=\"$SUPERVISOR_AGENT\"" >> config.env
else
  databricks supervisor-agents update-supervisor-agent "$SUPERVISOR_AGENT" instructions "Plant-Floor OEE Agent" \
    --instructions "$(cat agents/04_supervisor_instructions.md)" -p "$PROFILE" -o json >/dev/null
fi

existing=$(databricks supervisor-agents list-tools "$SUPERVISOR_AGENT" -p "$PROFILE" -o json | jq -r '.[].tool_id')
tool() {  # tool_id json
  grep -qx "$1" <<<"$existing" && { echo "tool $1 exists"; return; }
  databricks supervisor-agents create-tool "$SUPERVISOR_AGENT" "$1" --json "$2" -p "$PROFILE" -o json >/dev/null && echo "tool $1 created"
}
tool plant_oee_analyst "$(j --arg id "$GENIE_SPACE_ID" '{tool_type:"genie_space", genie_space:{id:$id},
  description:"Historical plant OEE analytics: OEE and its availability/performance/quality factors by asset, shift and work center; unplanned downtime, reasons, MTTR/MTBF, scrap; whether supervisors acted on alerts."}')"
tool get_asset_risk "$(j --arg f "$F.get_asset_risk" '{tool_type:"uc_function", uc_function:{name:$f},
  description:"Next-shift OEE risk per asset (ML model) with top drivers; which assets are at risk."}')"
tool get_work_order_draft "$(j --arg f "$F.get_work_order_draft" '{tool_type:"uc_function", uc_function:{name:$f},
  description:"AI-drafted probable cause and work order for an at-risk asset; the draft must be confirmed by a person in the app."}')"
tool request_work_order "$(j '{tool_type:"app", app:{name:"plant-floor-oee-febar"}, description:"Plant-floor app actions over MCP: request_work_order(asset_id, reason) raises a work-order REQUEST from an at-risk asset AI draft; a supervisor must approve it in the app. Use only when the user explicitly asks to raise or request a work order."}')"
tool plant_maintenance_manuals "$(j --arg id "$KA_ID" '{tool_type:"knowledge_assistant", knowledge_assistant:{knowledge_assistant_id:$id},
  description:"How to diagnose and repair plant equipment (CNC spindles, grinders, coating cells, welders, CMMs): thresholds, procedure IDs, part numbers, repair hours; plant LOTO safety and OEE escalation rules (SOP-PLT-001)."}')"
databricks supervisor-agents get-supervisor-agent "$SUPERVISOR_AGENT" -p "$PROFILE" -o json | jq -r '"supervisor endpoint: " + .endpoint_name'
