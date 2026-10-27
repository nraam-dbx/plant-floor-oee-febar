# Demo script: plant-floor OEE (about 15 minutes)

**Audience:** VP Manufacturing Operations (exec sponsor), Plant Reliability & Maintenance Engineering Manager (domain
owner), IT/OT architect. **One sentence:** *we catch the OEE loss while the machine is still degrading, and give the
supervisor everything needed to act before the breakdown.*

Pre-flight (10 min before): `ops/manage.sh start && ops/healthcheck.sh`, then republish the alert so the KPI clock starts
now: `databricks bundle run plant_oee_build --only genai_root_cause,refresh_lakebase_sync`. Open the app and the deck.

| # | Time | Show | Say |
|---|---|---|---|
| 1 | 0:00 | Deck slide 2 (outcome) | "Per 12-asset line: about one OEE point, ~500 fewer unplanned hours, ≈ $2.75 M a year, base case. Here's how." |
| 2 | 1:00 | Deck slide 4 (where OEE is lost) | "The 4 days before a breakdown run at 58 % OEE instead of 76 %. That's 13 % of shifts and most of the scrap. Today nobody sees it until the machine stops." |
| 3 | 2:30 | App, top KPI tiles + OEE by asset | "Plant OEE against the 75 % target, from IT and OT data joined on one asset key and served from Lakebase." |
| 4 | 4:00 | App, at-risk queue: CNC-02 | "99.8 % risk that next shift drops below 65 %. Why: vibration 6.0 mm/s and climbing. The model's drivers are here, with the likely cause and a drafted work order grounded on four past repairs on sister machines." |
| 5 | 5:30 | Chat chip "What should I do about CNC-02" | Point at the tool trace: risk model → work-order draft → manuals. "It cites the real procedure MM-CNC-01-R7, the bearing part to pre-stage, and 6 hours. It does not invent part numbers; we test that." |
| 6 | 7:00 | Chat chip "Raise WO for CNC-02" → **Approve tool call** | "Agents don't act on their own here: the platform pauses the tool call for approval. Even then it only creates a *request*." |
| 7 | 8:00 | Work-order requests: **Approve**; queue: **Acknowledge** | "The supervisor approves the request. Every action records who did it and when." |
| 8 | 9:00 | Chat chip "Worst work center" | "Ask anything about OEE in plain English; Genie writes the SQL on the governed gold tables." |
| 9 | 10:00 | Workspace: Catalog Explorer → `gold_oee_shift` (lineage, tags), `silver_operators` (masked) | "Lineage from historian file to the OEE number. IT, OT and gold domains each have an owner. Operator names are masked unless you're in HR. The app's identity reaches only the 7 tables and 2 functions it needs." |
| 10 | 11:30 | SQL: `SELECT * FROM gold_alert_response` | "The supervisor's actions came back into the lakehouse from Postgres. Alert to first action is now a measured KPI." |
| 11 | 12:30 | Deck slides 7–8 (proof, value) | "Model vs today's rule; agent judged on 10 questions. Value math with every assumption labelled; we replace them with your numbers in the pilot." |
| 12 | 14:00 | Deck slide 10 (roadmap + ask) | "Ask: a 90-day pilot on one line, with a pilot shift team and historian / MES / CMMS access in week 1." |

**If something is slow:** the agent's long answers take up to ~100 s (cold start). Run step 5 first in pre-flight to
warm it. Lakebase resumes from suspend in a few seconds; refresh the page.
