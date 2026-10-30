# How I built this

An account of the build process: which AI tools I used, where they changed my workflow, where I had to step in, and
the trade-offs of working this way. What was built and why: [`README.md`](README.md),
[`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md); proof it ran: [`EVIDENCE.md`](EVIDENCE.md).

## Tools
| Tool | What I used it for |
|---|---|
| **Claude Code** (Databricks' internal setup, *Isaac*; every commit carries its co-author trailer) | Main coding agent in my terminal: scaffolding, pipeline SQL, notebooks, app, bundle config, evidence scripts, debugging against the live workspace through the Databricks CLI |
| Field Engineering Claude Code plugins | Demo scaffold (standard repo layout + `config.env`), Google Slides builder for the deck, Glean search for internal guidance |
| **Agent Bricks** | Knowledge Assistant over the maintenance manuals and the Supervisor agent: configured, not hand-coded |
| **Genie** | Natural-language analytics over the gold tables; space defined as code (`agents/03_genie_space.py`) |
| **MLflow GenAI evaluation** | LLM judges plus a custom routing scorer, used as the test suite for the agent instructions |
| `CLAUDE.md` in the repo | Project memory for the coding agent: workspace facts, conventions, and every gotcha we hit, so later sessions didn't repeat mistakes |

## How the work went
| When | What | Time |
|---|---|---|
| Oct 19 | Problem framing, design, scaffold; stages 1–4 (data, Lakeflow, UC, ML + GenAI, Lakebase) | ~4.5 h |
| Oct 27 | Stages 5–6 (Genie, agents, eval, app), deck, clean rebuild + all evidence regenerated | ~1.5 h |
| Oct 28–30 | Read the FE Bar FAQ, fit evidence to the scorer's limits, fixed the value baseline and the deck, tightened the design notes | a few short sessions |

My loop for each stage: I set the goal and the constraints (which stage, what "done" looks like, what evidence must
exist), the agent wrote the code and ran it on the workspace, and I reviewed the output before committing. Each stage
ends with a script that regenerates its evidence from live queries (`ops/stage*_evidence.py`), so "it ran" is a
command, not a screenshot.

## Decisions I made (not the AI)
- **The problem.** A real customer ask, IT/OT integration to raise plant-floor OEE, kept anonymous in this repo.
- **Scope and shape.** One `asset_id` through all six stages; next-shift risk as the prediction, because that's the
  decision a supervisor makes at handover; adding the Genie + Supervisor agent layer on top of plain Genie.
- **Built fresh.** I chose not to reuse an earlier Lakebase build, so every stage here is new work.
- **Governance within real limits.** No account-admin access on the demo workspace, so I kept human-role grants as
  design only and gave real grants only to service principals, instead of granting broad access to make it "work".
- **Human approval for agent actions.** The agent may propose a work order but never create one silently.
- **Outward actions stayed with me:** making the repo public, rebuilding the deck, deleting old versions.

## Where AI was a force multiplier
1. **Speed through unfamiliar ground.** Stages 1–4 went from empty repo to running, governed, evidenced pipeline +
   model + Lakebase in one afternoon. Lakebase synced tables and reverse CDF sync are new features with few examples;
   the agent worked from CLI help and API error messages and iterated on the live workspace far faster than reading docs.
2. **Debugging on the real platform.** It found causes I'd have spent hours on: psycopg on serverless aborting during a
   GSSAPI probe (fix `gssencmode=disable`), reverse sync silently skipping tables without `REPLICA IDENTITY FULL`, a
   synced table breaking because `CREATE OR REPLACE` gave its source a new Delta id (fix: publish with `MERGE`), and
   the Supervisor's call to the app's MCP tool getting 401 until the app's service principal had `CAN_USE` on itself.
3. **Evaluation as the test suite.** Instead of eyeballing agent answers, we wrote 10 questions with expected facts and
   scored them with MLflow judges. The first run (correctness 0.7, plant rules 0.6) told us which instructions to fix.
   Later runs got correctness 0.8, plant rules 1.0, and the remaining misses traced to the judge, not the agent.
4. **Reading the rules, then reshaping the submission.** Glean found the FE Bar FAQ, which says the scorer reads at most
   30 files and 9,000 characters per file. The agent measured the repo against that, found the notebook outputs sat past
   the cut-off, and wrote `ops/nb_to_md.py` to render runs output-first.

## Where I had to step in
- **The LLM invented references.** The first `ai_query` root-cause prompt cited SOP numbers that don't exist. We changed
  the prompt to allow only references it is given, and checked the answer against the grounding (`evidence/05`).
- **A number without a source.** The deck's baseline (58.2 % vs 76.5 % OEE) came from a query nobody committed, and
  mixed two window definitions. We picked one, committed the query (`ops/value_evidence.py` → `evidence/12`) and I
  had the deck rebuilt from it (now 58.4 % vs 76.5 %). Rule since then: no number in the deck without a query in the repo.
- **A duplicated evidence file.** One file claiming to show the app's grants was a byte copy of another. Removed.
- **Overclaiming in drafts.** The first draft of the design notes said boosted trees "beat" a deep model (never tested)
  and justified Lakebase with a lookup on a 12-row table. On review we rewrote both to the real reasons.

## Trade-offs of building this way
- **Speed vs verification.** Code arrives fast; checking it doesn't. Every claim in the README and deck links to
  committed output so I, or a reviewer, can verify it.
- **Project memory matters.** Without `CLAUDE.md` the agent would have re-hit the same serverless and Lakebase issues
  every session. Writing down the gotchas cost minutes and saved hours.
- **Keep the human on the irreversible steps.** The agent proposes; I approve anything public or destructive.
