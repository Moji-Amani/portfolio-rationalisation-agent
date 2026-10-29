# Portfolio Rationalisation Agent — Progress & Handover

_Last updated: 2026-10-27_

This document is a resume point. Read it top to bottom and you will know exactly
what exists, why, and what to do next.

---

## 1. What this project is

An agent that analyses a software/tooling estate (an "inventory") against a set
of business requirements and recommends which tools to **keep, merge, or
retire** — with strict guardrails so it never overclaims.

The guardrails (from `.kiro/steering/rules.md`) are the heart of the exercise:

- Synthetic / public data only.
- **Every number is a range** (low, base, high) with stated assumptions. All
  arithmetic lives in code (`savings_range`), never done by the model.
- Every recommendation **cites the inventory rows** it used and carries a
  **confidence level**.
- Each recommendation is tagged **Two-Way Door** (reversible: tier change,
  non-renewal, licence reduction) or **One-Way Door** (irreversible: hardware
  buy, multi-year commit, perpetual licence, decommissioning), with blast radius.
- Never recommend retiring something a **Must** requirement depends on without
  flagging the dependency.
- `evidence_level = "claimed only"` **never** counts as covering a requirement.
- Below the confidence threshold → "needs human review", not decided.
- Nothing is finalised without the **human approval gate** (step 7).
- The agent **never edits the inventory**; it only reads inputs and writes the
  memo and log.
- A requirement with no owner / no measurable threshold is **flagged, not guessed**.
- The agent must **never read `answer_key/`** (kept outside this folder).
- UK spelling, lean expert language.

---

## 2. Project layout

```
/home/moji/Portfolio Rationalisation Agent/portfolio-agent/
├── .kiro/
│   ├── specs/portfolio-agent/tasks.md     # the build plan (steps 1–8 + eval)
│   └── steering/rules.md                  # the standing rules above
├── data/
│   ├── inventory.csv                      # 36 tools (the clean estate)
│   ├── inventory_messy.csv                # same estate with 7 planted faults
│   ├── requirements.csv                   # 14 requirements
│   ├── taxonomy.csv                        # capability -> domain map
│   └── generate.py                        # deterministic data generator
├── src/portfolio_agent/
│   ├── __init__.py
│   ├── validate.py                        # STEP 1 (done)
│   ├── classify.py                        # STEP 2 (done)
│   ├── overlap.py                         # STEP 3 (done)
│   ├── dependency.py                      # STEP 4 (done)
│   ├── savings.py                         # STEP 5 (done)
│   └── recommend.py                       # STEP 6 (done)
│   └── approval.py                        # STEP 7 (done)
│   └── report.py                          # STEP 8 (done)
├── tests/
│   ├── test_validate.py                   # STEP 1 tests (10 passing)
│   ├── test_classify.py                   # STEP 2 tests (8 passing)
│   ├── test_overlap.py                    # STEP 3 tests (12 passing)
│   ├── test_dependency.py                 # STEP 4 tests (9 passing)
│   ├── test_savings.py                    # STEP 5 tests (14 passing)
│   ├── test_recommend.py                  # STEP 6 tests (14 passing)
│   ├── test_approval.py                   # STEP 7 tests (11 passing)
│   └── test_report.py                     # STEP 8 tests (10 passing)
│   └── test_eval.py                       # STEP 9 tests (2 passing)
├── eval/evaluate.py                       # STEP 9 evaluation harness (reads the answer key)
├── README.md                              # project README (problem/design/results/limits)
├── PROGRESS.md                            # this file (current state / handover)
├── DECISIONS.md                           # per-task "initial thought" + "outcome" log
└── challenges.md                          # problems hit per task and how they were fixed
```

> **Convention:** for each task, record the *initial thought* in `DECISIONS.md`
> **before** building, and the *outcome* **after** verifying. `PROGRESS.md` holds
> current state; `DECISIONS.md` holds the chronological reasoning.

> The `answer_key/` folder lives **outside** this project by design. The agent
> and its code must never read it. It is only used by the (separate) evaluation
> script in step 9. It is kept at the `generate.py` default location —
> `…/Portfolio Rationalisation Agent/answer_key/answer_key.json` — outside
> `portfolio-agent/`. `eval/evaluate.py` finds it with no flag; use
> `--answer-key` only if it moves.

---

## 3. Data schema (from `data/generate.py`)

**inventory.csv** columns:
`tool_id, name, capability, vendor, type, cost_type, annual_cost_gbp,
contract_end, licence_qty, active_users, utilisation_pct, owner,
requirement_ids, evidence_level`

- `requirement_ids` is `;`-separated (may be empty).
- Controlled vocabularies:
  - `evidence_level` ∈ {tested, demonstrated, documented, **claimed only**}
  - `type` ∈ {software, hardware}
  - `cost_type` ∈ {opex, capex}

**requirements.csv** columns:
`requirement_id, text, priority, threshold, owner`
- `priority` ∈ {Must, Should, Could}

**taxonomy.csv** columns: `capability, domain`

Reference date for the scenario: **2026-10-27**.

---

## 4. Environment

- Python **3.14.4**.
- **No pytest installed** → tests use the standard-library `unittest`. No
  external dependencies at all.

Run the tests (from the project root):

```bash
cd "/home/moji/Portfolio Rationalisation Agent/portfolio-agent"
python3 -m unittest discover -s tests -v
```

Expected: **90 tests, all OK** (10 Step 1, 8 Step 2, 12 Step 3, 9 Step 4, 14 Step 5, 14 Step 6, 11 Step 7, 10 Step 8, 2 Step 9).

---

## 4b. What I built (running summary)

A short "what I built + how it was verified" note per finished step, in order.
The detailed per-step sections follow further down; this is the quick narrative.

- **Step 1 — input validation.** `validate.py`: `read_inventory` /
  `read_requirements` with full type/date/range/vocabulary/taxonomy/unique-id
  checks; duplicate id is blocking, everything else reported. Verified: 10 tests;
  messy file blocks on the duplicate and reports the other 6 faults; clean file
  raises exactly the one by-design T019 orphan advisory.

- **Step 2 — classification.** `classify.py`: grades each capability against the
  taxonomy as `exact` / `domain_only` / `unknown`; only exact is trusted, the
  rest are flagged for review (never invents a capability). Verified: 8 tests;
  all 36 clean tools are exact; `security/firewall` → `domain_only`.

- **Step 3 — overlap & redundancy.** `overlap.py`: groups tools by capability and
  scores redundancy from a dimensionless mean of utilisation, users, and
  requirement-coverage overlap (no money here). Verified: 12 tests; the one clean
  overlap group ranks PulseWatch (merge) below SignalScope (survivor).

- **Step 4 — dependency check.** `dependency.py`: lists requirements relying on a
  tool with priority; "claimed only" never counts as coverage (for the tool or a
  peer); `blocking_dependencies` flags a Must with no fallback. Verified: 9 tests;
  FlowMesh does not cover R007, backup array's R003 is covered by a fallback.

- **Step 5 — savings_range (money).** `savings.py`: the single place money is
  computed; every figure a (low, base, high) range with assumptions; conservative
  worst-case pairing. Verified: 14 tests; reproduces the two reference results
  exactly (23/94/146k; 12/15/16.5k).

- **Step 6 — recommendation engine.** `recommend.py`: composes steps 2–5 into a
  per-tool decision (keep/merge/retire/do-not-renew/procure/needs-review) with
  reasoning, cited rows, confidence, door type and blast radius; safety-first
  ordering; "linked" ≠ "covers". Verified: 14 tests; all six planted cases match.

- **Step 7 — approval gate.** `approval.py`: prints a scannable summary, then
  stops and waits for approve/edit/reject; never auto-approves; EOF and invalid
  input fail safe to reject; input/output injected for testing. Verified: 11
  tests; real summary reads "1 merge, 1 do_not_renew, 1 procure, 1
  needs_human_review, 32 keep".

- **Step 8 — memo + tool-call log.** `report.py`: a `Logger`, a `run_agent`
  orchestrator that drives steps 1→7 through the log, a one-page `write_memo`,
  and `write_artifacts` (memo.md + tool_call_log.md). The agent writes only the
  memo and log — never the inventory; money is only the ranges from step 5.
  Verified: 10 tests; end-to-end run logs 6 calls and the memo shows the four
  actions + 32 keeps + APPROVED (and NOT APPROVED on the reject path).

- **Step 9 — evaluation + README.** `eval/evaluate.py` (separate from the agent;
  the only code that reads the answer key): scores the six planted cases against
  the key and checks the messy file. Plus `README.md`. Verified: **6 correct / 0
  partly / 0 wrong**, all 7 messy faults surfaced, **PASS**; savings ranges match
  the key exactly. 2 eval tests (suite now 90).

---

## 5. What is DONE — Step 1: input validation

**File:** `src/portfolio_agent/validate.py`

Public API:

- `read_inventory(path, taxonomy_path=None) -> ReadResult`
- `read_requirements(path) -> ReadResult`

Supporting types: `Tool`, `Requirement`, `ReadResult` (has `.rows` and
`.issues`, plus `.ok`), `Issue` (row_id, field, message), and
`BlockingValidationError`.

Validation performed:

| Check | Behaviour |
|-------|-----------|
| Duplicate `tool_id` / `requirement_id` | **Blocking** — raises `BlockingValidationError` |
| Missing / non-numeric `annual_cost_gbp`, `licence_qty`, `active_users` | Reported issue |
| `utilisation_pct` outside 0–100 | Reported issue |
| `contract_end` not a real ISO date | Reported issue |
| `evidence_level` / `type` / `cost_type` / `priority` not in allowed set | Reported issue |
| `capability` not in taxonomy | Reported issue |
| Missing `owner` (inventory and requirements) | Reported issue |
| Missing `threshold` (requirements) | Reported issue |

Design rule applied: **duplicate ID blocks the whole read; everything else is
reported** as a non-blocking issue while valid rows are still returned.

### Important nuance discovered
The **clean** `inventory.csv` is not completely issue-free: **T019 (InsightBox)**
has no owner and 0 active users *by design* — it is the planted "orphan" case.
A missing owner is therefore correctly **flagged as one advisory** (per the
"flag, don't guess" rule), not silently accepted. The tests expect exactly this
one advisory on the clean file.

---

## 6. Tests — Step 1 (all passing)

**File:** `tests/test_validate.py` — 10 tests:

- Clean inventory: 36 rows load; types coerced (ints + `datetime.date`);
  `requirement_ids` split on `;`; empty req ids handled; **exactly one** expected
  advisory (T019 missing owner).
- Clean requirements: 14 rows; no issues; priorities parsed.
- **Messy file (7 planted faults):**
  - Duplicate `tool_id` (T004) → **blocking** (`BlockingValidationError`).
  - After de-duplicating in-test, the other six faults are all **reported**:
    T010 missing cost, T014 invalid date `31/04/2027`, T017 utilisation 140,
    T021 bad evidence level, T025 missing owner, T031 capability not in taxonomy.
  - Total reported issues on the messy file = **7** = 6 planted row-faults +
    the inherited by-design T019 orphan advisory.

Last run result: **Ran 10 tests … OK**.

---

## 6b. What is DONE — Step 2: classification

**File:** `src/portfolio_agent/classify.py`

Public API:

- `load_taxonomy(path) -> dict[capability, domain]` (35 capabilities, 7 domains)
- `classify_capability(capability, taxonomy) -> (domain, confidence, note)`
- `classify_tools(tools, taxonomy) -> list[Classification]`
- `low_confidence(classifications) -> list[Classification]` (needs-review only)

`Classification` fields: `tool_id, capability, domain, confidence,
needs_review, note`.

Confidence levels (only `exact` is trusted; the rest set `needs_review=True`):

| Level | Meaning |
|-------|---------|
| `exact` | capability is a taxonomy member; domain taken from taxonomy |
| `domain_only` | full capability unknown but its domain prefix (before `/`) is known — flagged |
| `unknown` | neither capability nor domain prefix recognised — flagged |

This enacts the steering rule "flag low-confidence mappings, never guess".
`security/firewall` (the messy-file capability fault) classifies as
`domain_only` (domain `security` is known, leaf `firewall` is not).

**Tests:** `tests/test_classify.py` — 8 tests. Taxonomy loads 35 capabilities;
exact / domain_only / unknown / empty cases; clean inventory → all 36 `exact`
with zero low-confidence; domain resolution (T001→monitoring, T033→backup);
low-confidence flagging via `dataclasses.replace`. **Ran 8 tests … OK**.

---

## 6c. What is DONE — Step 3: overlap groups & redundancy scoring

**File:** `src/portfolio_agent/overlap.py`

Public API:

- `overlap_groups(inventory) -> list[OverlapGroup]` — groups tools by
  `capability`; only capabilities with **2+ tools** are returned; ordered by
  capability name.

`OverlapGroup(capability, tools)` with properties:
- `.survivor` — the tool to keep (lowest redundancy score)
- `.merge_candidates` — the rest, highest redundancy first

`ToolScore` fields: `tool_id, name, redundancy_score (0–1), utilisation_pct,
active_users, requirement_ids, requirements_covered_elsewhere,
unique_requirements, note`.

**Redundancy score** (higher = stronger retire/merge candidate) is the mean of
three equal-weight signals; it is **dimensionless — no money is computed here**
(money lives only in `savings_range`, step 5):
1. low utilisation: `1 − utilisation_pct/100`
2. few users vs busiest peer: `1 − active_users / max_users_in_group`
3. coverage overlap: `covered_elsewhere / total_requirements` (1.0 if the tool
   maps to no requirements, i.e. nothing unique is lost by merging)

Missing signals (`None`) contribute 0 and are recorded in `note`.

On the clean estate there is exactly **one** overlap group,
`monitoring/network-performance`: T001 PulseWatch (22% util, 70 users, R001) vs
T002 SignalScope (78%, 210, R001). Scores: T001 ≈ 0.816 (merge candidate),
T002 ≈ 0.407 (survivor). Both cover R001, so merging PulseWatch into SignalScope
loses no unique coverage — matching the planted "Overlap" case.

**Tests:** `tests/test_overlap.py` — 12 tests. Uses a `FakeTool` stand-in for
isolated scoring tests plus real clean-inventory assertions: single group; both
tools present; survivor = T002; merge candidate = T001; R001 covered elsewhere;
score within [0,1]; weaker tool scores higher; no group for a lone tool;
identical tools; no-requirement tool gets full coverage component; missing
signals safe; a unique requirement is not counted as covered. **Ran 12 tests … OK**.

---

## 6d. What is DONE — Step 4: dependency check

**File:** `src/portfolio_agent/dependency.py`

Public API:

- `dependency_check(tool_id, inventory, requirements=None) -> DependencyReport`

`DependencyReport(tool_id, found, dependencies)` with properties:
- `.must_dependencies` — dependencies whose priority is Must
- `.blocking_dependencies` — Must requirements this tool **genuinely covers**
  with **no other coverage**; retiring would leave them uncovered (must be
  flagged before any retire/decommission).

`RequirementDependency` fields: `requirement_id, priority, covers,
covered_elsewhere, other_covering_tools, note`.

**Critical rule enacted:** `evidence_level = "claimed only"` never counts as
coverage. A claimed-only link sets `covers=False`, and claimed-only peers are
excluded from `other_covering_tools` / `covered_elsewhere`.

Reports facts only — no keep/retire decision (step 6), no money (step 5).
`found=False` if the tool id is absent; `priority` is `None` if `requirements`
is not supplied.

Verified on real data:
- **T033 EdgeStore Array** → R003 (Must), covers=True, also covered by T015 →
  a Must dependency but **not blocking** (fallback exists).
- **T013 FlowMesh** → R007 (Must), covers=**False** (claimed only); R007's real
  coverage is T012 ServiceWeave only.
- **T028 Sentinel Vault PAM** → R008 (Must), covers=True, also covered by T032.

**Tests:** `tests/test_dependency.py` — 9 tests (FakeTool/FakeReq stand-ins +
real data): unknown tool not found; backup-array Must dep covered elsewhere (not
blocking); claimed-only does not cover + note; priority attached; priority None
when requirements omitted; blocking when a Must is only covered by this tool; a
claimed-only peer provides no coverage (so still blocking); a claimed-only tool
itself covers nothing; tool with no requirements. **Ran 9 tests … OK**.

---

## 6e. What is DONE — Step 5: savings_range (the only place money is computed)

**File:** `src/portfolio_agent/savings.py`

Per the steering rules, **all** arithmetic lives here and **every** figure is a
`(low, base, high)` range carrying its assumptions string. The agent never does
sums — it calls these and quotes the ranges.

Public API:

- `Range(low, base, high, assumptions)` — frozen; `.rounded()` → whole pounds.
- `retire_saving(annual_cost, assumptions=None) -> Range`
- `licence_shortfall_cost(annual_cost, licence_qty, active_users, assumptions=None) -> Range`
- `savings_range(rows, assumptions=None) -> list[SavingsResult]` — dispatches
  request rows by `kind` (`retire_saving` | `licence_shortfall`); unknown kind
  raises `ValueError`; preserves `inputs` for audit.

**retire_saving** = `recoverable_share*cost − migration − surviving_uplift`.
Defaults: recoverable `60/80/95%` (smallest-first); migration `£50k/30k/15k`
and uplift `£35k/20k/10k` (largest-first), so the pessimistic **low** saving is
paired with the costliest migration+uplift. Verified: £180k → **23,000 / 94,000
/ 146,000** (matches the Overlap reference).

**licence_shortfall_cost**: `gap = active − owned`; zero range if no gap;
`unit = annual_cost/licence_qty` (or override); `base = gap*unit`,
`low = base*(1−0.20)`, `high = base*(1+0.10)`. Raises `ValueError` if
`licence_qty ≤ 0` with no unit-price override. Verified: 50k / 200 / 260 →
**12,000 / 15,000 / 16,500** (matches the Under-provisioned reference).

**Tests:** `tests/test_savings.py` — 14 tests: T001 reference; low<base<high;
worst-case pairing; custom assumptions; assumptions string present; T028
reference; no-shortfall zero; exact-fit zero; unit-price override; zero-licence
`ValueError`; discount/premium applied; mixed-row dispatch; unknown kind raises;
inputs preserved. **Ran 14 tests … OK**.

---

## 6f. What is DONE — Step 6: recommendation engine

**File:** `src/portfolio_agent/recommend.py` (composes steps 2–5; uses relative
imports, so import it as `portfolio_agent.recommend`).

Public API:

- `recommend(inventory, requirements=None, reference_date=date(2026,10,27)) ->
  list[Recommendation]`

`Recommendation` fields: `tool_id, name, decision, confidence, door_type,
blast_radius, reasoning[], cited_tool_ids[], cited_requirement_ids[],
savings (Range|None), flags[]`.

Decisions: `keep, merge, retire, do_not_renew, procure, needs_human_review`.
Doors: `Two-Way Door` / `One-Way Door`. Confidence: `high/medium/low`.

**Decision order (first match wins):**
1. **Blocking Must dependency** → keep + "do not retire" flag (safety first).
2. **Orphan** (no owner or 0 users) → needs-review, low confidence,
   ask-for-owner flag.
3. **Under-provisioned** (active users > licences) → procure + licence-shortfall
   range from `savings_range`.
4. **Merge candidate** (in an overlap group's merge list) → merge + retire-saving
   range; confidence high if util ≤ 40% else medium.
5. **Renewal** (contract ends in 0–90 days and util ≤ 40%) → do-not-renew (high
   if covered elsewhere with no Must; medium if Musts covered elsewhere;
   needs-review if not covered).
6. **Default** → keep.

**Door on removal:** hardware or capex → One-Way; otherwise Two-Way. A keep
recommendation shows Two-Way (status quo) but hardware/capex keeps carry a flag:
"If ever decommissioned, One-Way Door".

**Money** comes only from `savings_range`. **Coverage integrity:** a keep only
claims "Supports Must Rxxx" where the dependency genuinely `covers`; claimed-only
Musts are reported as "linked but does not count as covering".

All six planted cases verified on the clean inventory:
T001 merge→T002 (Two-Way, 23k/94k/146k) · T002 keep · T026 do-not-renew (45
days, 18%, cites T023) · T033 keep + One-Way-on-decommission flag + R003 · T019
needs-review orphan · T013 keep + claimed-only flag naming R007 · T028 procure
(12k/15k/16.5k) + R008.

**Tests:** `tests/test_recommend.py` — 14 tests (6 planted cases + "every rec
cites rows / has confidence / has door" + 7 guardrail tests using
FakeTool/FakeReq). **Ran 14 tests … OK**.

---

## 6g. What is DONE — Step 7: approval gate

**File:** `src/portfolio_agent/approval.py`

Public API:

- `format_summary(recommendations) -> str` — pure (no I/O); actionable items
  (retire/merge/do-not-renew/procure/needs-review) listed before keeps, each with
  savings range, cited rows, reasoning, flags, and blast radius, plus a counts
  line.
- `approval_gate(recommendations, input_fn=input, output=None, edit_fn=None,
  max_prompts=10) -> GateResult` — prints the summary, then **stops and waits**.

`GateResult(outcome, approved_recommendations, note)`; `outcome` is `approved`
or `rejected`.

Behaviour: approve/a/yes/y → APPROVED with the current set; reject/r/no/n →
REJECTED, empty set; edit/e → calls `edit_fn` for an amended set, reprints,
re-prompts (or says "not available" if no callback). **Never auto-approves**:
unrecognised input and empty string re-prompt; EOF and exceeding `max_prompts`
both fail safe to REJECTED. Input/output are injected so tests drive it with no
real stdin. The gate actions nothing itself.

**Tests:** `tests/test_approval.py` — 11 tests: summary content/order; approve;
reject actions nothing; shortcut letters; unrecognised-then-approve re-prompts;
EOF → reject; edit-then-approve uses the amended set; edit unavailable without a
callback; too many invalid → reject; never auto-approves on empty string.
**Ran 11 tests … OK**.

---

## 6h. What is DONE — Step 8: memo + tool-call log

**File:** `src/portfolio_agent/report.py` (agent writes ONLY the memo and log; it
never edits the inventory).

Public API:

- `Logger` — ordered, timestamped tool-call entries; `.render()` → markdown
  audit trail; optional injectable `_clock` for deterministic tests.
- `run_agent(inventory_path, requirements_path, taxonomy_path=None,
  reference_date=None, input_fn=None, output=None, logger=None) -> AgentRun` —
  drives steps 1→7 through the logger (6 entries: read_inventory,
  read_requirements, classify_tools, overlap_groups, recommend, approval_gate).
- `write_memo(run, reference_date=None) -> str` — the one-page memo.
- `write_artifacts(run, out_dir, reference_date=None) -> {memo, log}` — persists
  `memo.md` + `tool_call_log.md`.

The memo: estate at a glance (counts + advisories + low-confidence maps);
actionable recommendations with low/base/high ranges, door type, confidence,
cited rows and flags; keeps summarised as a count; and the approval outcome
(APPROVED vs NOT APPROVED). Money is only the ranges already computed by
`savings_range`.

Verified end-to-end (clean inventory, approve): 6 calls logged in order; memo
shows 1 merge / 1 do-not-renew / 1 procure / 1 needs-review / 32 keep with
ranges 23/94/146k and 12/15/16.5k and APPROVED; the reject path shows NOT
APPROVED.

**Tests:** `tests/test_report.py` — 10 tests. **Ran 10 tests … OK**.

---

## 6i. What is DONE — Step 9: evaluation harness + README

**Files:** `eval/evaluate.py` (standalone harness, **outside** the
`portfolio_agent` package) and `README.md`.

The harness is the **only** code permitted to read the answer key — it is not
the agent. Verified structurally: `answer_key` appears only under `eval/`, never
under `src/`.

Public API (in `eval/evaluate.py`):

- `find_answer_key(explicit)` — uses an explicit `--answer-key` path if given,
  else tries the `generate.py` spec location (project-parent `answer_key/`) then
  the known alternative (`~/New folder/answer_key/answer_key.json`). It only
  *locates* the file; scoring is never hard-coded.
- `score_case(case, recs_by_id) -> (grade, note)` — grades a planted case
  `correct` / `partly` / `wrong` on structured facts: decision family, door type,
  cited coverage, and the savings range vs the key's `reference_*_gbp`
  (rounded low/base/high).
- `run_case_eval(key)` — runs `recommend()` on the clean inventory and scores all
  six cases.
- `run_messy_eval() -> (all_found, findings)` — confirms the blocking duplicate
  plus the six reported faults (checking T025's owner fault specifically, not the
  by-design T019 orphan).
- `main()` — prints the results table, tally, messy-file check, and a final
  PASS / REVIEW; `--answer-key PATH` optional.

**Result:** 6 correct / 0 partly / 0 wrong; all 7 messy-file faults surfaced;
**PASS**. The savings ranges matched the real key exactly (£23k/£94k/£146k;
£12k/£15k/£16.5k), independently reconfirming the step-5 arithmetic.

**README.md** covers: problem, design (module table + safety-by-design +
decision order), data, how-to-run, the results table, honest failures (drawn
from `challenges.md`), limitations, and the project layout.

**Tests:** `tests/test_eval.py` — 2 tests: the messy-file all-7-faults check
(needs no key) and the all-six-cases-correct check (skips if no key, but the
fallback located it so it ran and passed). **Ran 2 tests … OK**.

---

## 7. The six planted evaluation cases (for later context)

These are the scenarios the finished agent must handle. (Expected answers live
in the external answer key, used only by the step 9 eval script — not by the
agent.)

1. **Overlap** — two near-duplicate network-performance monitors; recommend
   merging the low-utilised one into the other; saving as a range; Two-Way Door.
2. **Renewal** — a low-utilised ticketing tool whose contract ends soon;
   recommend non-renewal; confirm another tool still covers the requirement;
   Two-Way Door.
3. **Dependency** — a low-utilised backup array that a **Must** requirement
   depends on; recommend **keep** and flag the dependency; decommissioning would
   be One-Way Door.
4. **Orphan** — a tool with no owner and 0 users; retire candidate, but **ask for
   an owner first**; no requirement dependency.
5. **Claimed only** — an orchestration tool whose key capability is
   `evidence_level = "claimed only"`; do **not** count it as covering its Must
   requirement.
6. **Under-provisioned** — a security tool with more active users than licences;
   flag a licence shortfall and cost it as a range.

---

## 8. Remaining work (the plan)

| Step | Description | Status |
|------|-------------|--------|
| 1 | `read_inventory` / `read_requirements` + validation + tests | ✅ done |
| 2 | Classify tools to taxonomy; flag low-confidence mappings; tests | ✅ done |
| 3 | `overlap_groups(inventory)` — group by capability; redundancy score from utilisation, users, requirement coverage; tests | ✅ done |
| 4 | `dependency_check(tool_id, requirements)` — requirement IDs relying on a tool with priority; ignore "claimed only"; tests | ✅ done |
| 5 | `savings_range(rows, assumptions)` — the ONLY place numbers are computed (low/base/high recoverable share, migration cost, uplift; plus licence-shortfall cost); tests | ✅ done |
| 6 | Recommend keep/merge/retire with reasoning, cited rows, confidence, door type, blast radius | ✅ done |
| 7 | Approval gate — print summary, stop, wait for approve/edit/reject | ✅ done |
| 8 | One-page memo + step-by-step log of every tool call | ✅ done |
| 9 | Evaluation script (scores 6 cases vs answer key), run messy file (expect 7 faults), write README | ✅ done |

---

## 9. How to resume

1. Reopen the CLI. If you exported this chat, run from the directory you saved
   it in:
   ```
   /chat load "/home/moji/Portfolio Rationalisation Agent/portfolio-agent-session.json"
   ```
   or resume the auto-saved session with `kiro-cli chat --resume` from the same
   directory you were in.
2. Re-run the tests to confirm the state (should be 10 passing):
   ```bash
   cd "/home/moji/Portfolio Rationalisation Agent/portfolio-agent"
   python3 -m unittest discover -s tests -v
   ```
3. Say: **"continue with Step 2"** (classification). Everything needed is in
   this file.
