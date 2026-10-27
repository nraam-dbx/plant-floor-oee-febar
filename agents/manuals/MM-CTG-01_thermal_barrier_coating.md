# MM-CTG-01 — Thermal Barrier Coating Cells (CTG-01, CTG-02): Maintenance & Process Manual

Synthetic reference document for the plant-floor OEE demo. Applies to work center WC_COAT (plasma-spray TBC).

## 1. Normal operating envelope
| Signal | Normal | Warning | Stop / escalate |
|---|---|---|---|
| Booth temperature `…TEMPERATURE` (°C) | 83 – 88 | > 93 (TEMP_HIGH) | > 96 for 30 min |
| Gun vibration (mm/s) | 0.9 – 1.5 | > 2.6 | — |
| Ideal cycle time | 600 s per part | | |

## 2. Booth temperature excursions (Quality loss, scrap code COATING_THICKNESS)
**Effect:** above ~93 °C the bond-coat/top-coat thickness and porosity drift out of specification; scrap typically rises
from ~3 % to 20 %+ during an excursion. **Common causes:** booth exhaust fan degradation, clogged exhaust filter, chiller
setpoint drift. **Response procedure MM-CTG-01-P2:** (1) hold parts in process, (2) check exhaust differential pressure
(replace filter EX-FLT-90 above 450 Pa), (3) verify chiller setpoint 18 °C, (4) resume only after booth temperature is
< 90 °C for 15 min, (5) quarantine parts sprayed during the excursion for thickness inspection.

## 3. Plasma gun electrode/nozzle wear (failure code PLASMA_GUN)
**Symptoms:** unstable arc voltage, coating-thickness variation flagged by inspection, rising gun vibration over days.
**Repair MM-CTG-01-R3 — electrode + nozzle change (2.5 h):** LOTO per SOP-PLT-001; replace electrode PG-ELC-3M and nozzle
PG-NOZ-6; recalibrate primary/secondary gas flow; spray a coupon and verify thickness before release.
Electrode service life is ~60 arc-hours; replace at a planned stop when approaching it.
