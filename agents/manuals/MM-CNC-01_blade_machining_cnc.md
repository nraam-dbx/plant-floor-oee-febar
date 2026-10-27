# MM-CNC-01 — 5-Axis Blade Machining Centers (CNC-01 … CNC-04): Maintenance Manual

Synthetic reference document for the plant-floor OEE demo. Applies to work center WC_MACH (Blade Machining).

## 1. Normal operating envelope
| Signal (historian tag) | Normal | Warning | Stop / escalate |
|---|---|---|---|
| Spindle vibration `…VIBRATION` (mm/s RMS, running) | 1.8 – 2.6 | > 4.8 (SCADA alarm VIB_HIGH) | > 7.0 sustained 30 min |
| Spindle temperature `…TEMPERATURE` (°C, running) | 48 – 56 | > 62 | > 70 |
| Spindle power `…POWER` (kW, running) | 32 – 36 | > 39 | — |
| Ideal cycle time | 240 s per blade | | |

## 2. Spindle bearing degradation (failure code SPINDLE_BEARING)
**Typical progression.** Vibration rises gradually over 3–6 days (often +0.3 to +0.5 mm/s per shift), spindle temperature
creeps up 5–15 °C, the controller reduces feed (Performance loss) and surface-finish scrap increases (Quality loss).
Run-to-failure ends in a 3–8 hour unplanned stop.

**Most common root cause:** lubrication starvation (blocked oil-air line, empty reservoir, failed auto-lube pump).

**Diagnostic procedure MM-CNC-01-D3 (30 min, during a planned stop):**
1. Check the oil-air lubrication reservoir level and the auto-lube pump fault history on the HMI.
2. Verify oil-air pressure at the spindle inlet: 3.5 – 4.5 bar. Below 3.0 bar = starvation.
3. Run spindle warm-up at 2,000 rpm for 10 min; record vibration at 6,000 and 12,000 rpm.
4. If vibration at 12,000 rpm > 4.8 mm/s, or a bearing-defect frequency is visible in the spectrum, plan replacement.

**Repair procedure MM-CNC-01-R7 — front spindle bearing set replacement (6 h, 2 technicians):**
1. Lock out / tag out per SOP-PLT-001.
2. Remove spindle cartridge; replace front angular-contact bearing set (part SP-BRG-7014-P4, matched pair).
3. Flush and refill oil-air lines; replace inline filter (part LUB-FLT-10).
4. Set bearing preload per cartridge label; run break-in cycle (procedure MM-CNC-01-R7.6, 45 min).
5. Balance check: vibration must be < 2.6 mm/s at 12,000 rpm before release.
6. Cut a first-article blade; CMM-verify before returning to production.

**Planning guidance:** if VIB_HIGH alarms appear on 2+ consecutive shifts, schedule MM-CNC-01-D3 at the next planned stop
and pre-stage SP-BRG-7014-P4. Replacing at a planned stop takes ~6 h; run-to-failure averages ~7 h of unplanned downtime
plus scrap and possible spindle-shaft damage.

## 3. Other recurring stops
| Failure code | Typical duration | First action |
|---|---|---|
| TOOL_BREAK | 15 – 45 min | Replace tool, re-touch offsets, check tool-life counter |
| COOLANT_LOW | 15 – 30 min | Top up coolant, clean chip filter |
| FIXTURE_JAM | 20 – 60 min | Clean/lubricate clamp cylinder; replace seal kit FX-SEAL-22 if leaking |
| CONTROLLER_FAULT | 15 – 60 min | Record alarm number, power-cycle drive, check axis cabling |
