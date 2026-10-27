# SOP-PLT-001 — Plant Safety, Lockout/Tagout and OEE Loss Escalation

Synthetic reference document for the plant-floor OEE demo. Applies to all work centers.

## 1. Lockout / tagout (LOTO)
Before any maintenance inside a guarded area: notify the shift supervisor, stop the machine at a safe position, isolate
electrical, pneumatic and hydraulic energy, apply personal locks and tags, verify zero energy (try-start), and record the
LOTO in the work order. Only the person who applied a lock may remove it.

## 2. OEE targets and escalation
* Plant OEE target: **75 %**. Shift floor: **65 %** — an asset below 65 % for a shift is "at risk".
* When the predictive at-risk score is ≥ 0.5 for an asset, the shift supervisor must **acknowledge** it in the plant-floor app
  within one hour of shift handover and either create a work order, defer with a reason, or dismiss with a reason.
* Criticality A assets (blade machining, coating) at risk: create a **P1** work order and plan the intervention at the next
  planned stop; do not run to failure.
* Work-order priorities: **P1** = act before or at the next planned stop; **P2** = within 48 h; **P3** = next scheduled PM.

## 3. Shift handover checklist
Review the at-risk queue, open P1/P2 work orders, minor-stop counters, and any quality holds (e.g. coating excursions).
