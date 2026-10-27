# MM-GRD-01 — Root Form Grinders (GRD-01, GRD-02): Maintenance Manual

Synthetic reference document for the plant-floor OEE demo. Applies to work center WC_GRND (Root Form Grinding).

## 1. Normal operating envelope
| Signal | Normal | Warning | Stop / escalate |
|---|---|---|---|
| Wheel-spindle vibration (mm/s RMS, running) | 1.4 – 2.2 | > 4.0 (VIB_HIGH) | > 6.0 |
| Spindle temperature (°C) | 48 – 56 | > 62 | > 70 |
| Ideal cycle time | 180 s per blade root | | |

## 2. Wheel-spindle bearing fatigue (failure code WHEEL_SPINDLE)
**Symptoms:** chatter marks and grinding burn on the fir-tree root form, rising vibration over several days, more
dressing cycles needed. **Root cause:** bearing fatigue, often accelerated by coolant ingress past the spindle labyrinth seal.

**Diagnostic MM-GRD-01-D2 (20 min):** inspect labyrinth seal for coolant ingress; measure vibration at operating speed;
check wheel balance after dressing.

**Repair MM-GRD-01-R4 — wheel-spindle bearing replacement (5 h):** LOTO per SOP-PLT-001; replace bearings (part
GS-BRG-6212-HS) and labyrinth seal (GS-SEAL-40); re-balance wheel; dress wheel; first-article check on CMM.

## 3. Minor stops (Performance loss)
Frequent 2–5 minute stops on grinders are usually **coolant nozzle clogging** or **part-presence sensor misreads** at load.
Procedure MM-GRD-01-M1: clean coolant nozzles each shift, check the part-presence sensor gap (1.5 ± 0.3 mm), and review
the minor-stop counter at shift handover. More than ~15 minor stops per shift warrants a sensor replacement (part PS-IND-08).
