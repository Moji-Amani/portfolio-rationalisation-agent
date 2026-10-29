# Decision log — initial thoughts and outcomes

A chronological record of the *reasoning* behind each task: what I intended
**before** building it (design intent, assumptions, risks) and what actually
happened **after** (what was built, what changed, how it was verified).

`PROGRESS.md` is the "current state" handover. This file is the "why".

Format per task:
- **Initial thought (before):** the plan and reasoning going in.
- **Outcome (after):** what was built, surprises, and verification.

> Steps 1–5 were completed before this log existed; their "initial thought"
> entries are reconstructed faithfully from the design decisions recorded at the
> time (see PROGRESS.md and the task notes). From Step 6 onward, the "before"
> entry is written at the start of the task.

---

## Safety-by-design decisions (cross-step summary)

The whole point of this agent is that it will not overclaim or act unilaterally.
Every step made at least one deliberate safety choice; they are collected here
for audit, and each is repeated under its step below.

| Step | Safety-by-design decision | Why it is safe |
|------|---------------------------|----------------|
| 1 | Duplicate primary key is **blocking**; all other problems are *reported*, not silently dropped. Missing owner is **flagged, not rejected or guessed**. | A corrupt key makes the whole file untrustworthy, so stop; but one bad row shouldn't hide the rest. The human sees every issue. |
| 2 | Only an **exact** taxonomy match is trusted; anything weaker is `needs_review`. Capabilities are **never invented**. | Prevents a confident-looking but wrong classification from driving a decision. |
| 3 | Redundancy score is **dimensionless** — no money here. Missing signals contribute 0 and are **noted, not imputed**. | Keeps all money in one audited place (step 5); avoids inventing data to fill gaps. |
| 4 | `evidence_level = "claimed only"` **never counts as coverage** — for the tool *and* for any peer offered as a fallback. `blocking_dependencies` surfaces a Must with no genuine fallback. | Stops the agent concluding "covered elsewhere, safe to retire" on the strength of an unproven claim. |
| 5 | **All** arithmetic lives here; every figure is a **(low, base, high) range with stated assumptions**. Conservative pairing for the worst case; divide-by-zero raises rather than guesses. | The model never does sums; numbers are reproducible and auditable, and the worst case is honestly the worst case. |
| 6 | **Safety-first decision order:** a blocking Must dependency forces *keep* before any other rule can fire. Only genuine coverage is claimed ("linked" ≠ "covers"). Below-threshold/missing data → **needs human review**, not a decision. One-Way-Door irreversibility is flagged even on a *keep*. | Nothing a Must depends on (without fallback) can ever be routed to retire/merge; uncertainty is escalated, not resolved by guessing. |
| 7 | The gate **never auto-approves**: unrecognised/empty input re-prompts; EOF and too many invalid attempts **fail safe to reject**. The gate **actions nothing itself**. | Human approval is mandatory; ambiguity can never be read as consent. |
| 8 | The agent writes **only** the memo and log — **never edits the inventory**. Money in the memo is only the ranges from step 5 (never recomputed); unapproved/needs-review items are never shown as decided. | Read-only on source data; a tamper-proof, reproducible audit trail; the memo can't overstate certainty or approval. |
| 9 | The evaluation harness is **outside the agent package** and is the **only** code that reads the answer key (verified: `answer_key` appears only in `eval/`, never in `src/`). Scores are computed from the key, not hard-coded. | Enforces the "agent never reads the answer key" rule structurally, not just by convention. |

---

## Step 1 — read_inventory / read_requirements (validation)

**Initial thought (before):**
Before writing any validation I should read `data/generate.py` to learn the
exact schema, the controlled vocabularies, and precisely how the 7 messy-file
faults were planted — so the validators catch the real faults rather than ones I
imagine. Design intent: a duplicate primary key is *blocking* (can't trust the
rest of the file), but every other problem should be *reported* as a non-blocking
issue while still returning the valid rows, so downstream steps and the human can
see the whole picture. Risk to watch: don't over-validate and reject legitimate
by-design data.

**Outcome (after):**
Built `validate.py` with `read_inventory` / `read_requirements`, `Tool` /
`Requirement` dataclasses, a `ReadResult(rows, issues)` container, `Issue`, and
`BlockingValidationError`. Key surprise: the *clean* `inventory.csv` is not
issue-free — T019 (InsightBox) has no owner and 0 users *by design* (the planted
"orphan"). This validated the design choice to *report* missing owners rather
than reject them ("flag, don't guess"). Adjusted the tests to expect that one
advisory instead of suppressing it in code. Verified: 10 tests pass; the messy
file blocks on the duplicate id and reports the other 6 faults.

**Safety-by-design:** a duplicate primary key is blocking (stop on an
untrustworthy file), but every other problem is *reported* while valid rows are
still returned — nothing is silently dropped. A missing owner is *flagged, not
guessed or rejected*.

---

## Step 2 — classify to taxonomy, flag low-confidence

**Initial thought (before):**
The inventory already carries a `capability` string, so "classification" here is
really about *confidence*: how well does each stated capability map to the
controlled taxonomy? Intent: never invent a capability; instead grade each
mapping and surface weak ones for human review. A two-level taxonomy
(`domain/leaf`) suggests a natural confidence ladder: exact match (trust),
domain-prefix match only (low confidence), or nothing recognised (lowest).
`security/firewall` from the messy file should land as "domain known, leaf not".

**Outcome (after):**
Built `classify.py` with `load_taxonomy`, `classify_capability`,
`classify_tools`, `low_confidence`, and a `Classification` record. Only `exact`
is trusted; everything else sets `needs_review=True`. On the clean estate all 36
tools are exact (zero flags), and `security/firewall` correctly classifies as
`domain_only`. Verified: 8 tests pass (full suite 18).

**Safety-by-design:** only an exact taxonomy match is trusted; a capability is
never invented. Weak or unknown mappings are forced to `needs_review` so a
plausible-but-wrong label cannot silently drive a decision.

---

## Step 3 — overlap_groups + redundancy score

**Initial thought (before):**
Tools sharing a `capability` are overlap candidates. Intent: produce a
*dimensionless* redundancy score only — no money here (money belongs solely in
`savings_range`, step 5). A tool is a stronger retire candidate when it has low
utilisation, few users, and its requirements are also covered by a peer. I'll
average three equal-weight signals and expose the raw signals so the score is
explainable. Risk: missing values (None) must not crash or silently distort the
score.

**Outcome (after):**
Built `overlap.py` with `overlap_groups`, `OverlapGroup` (with `.survivor` /
`.merge_candidates`), and `ToolScore`. Missing signals contribute 0 and are
noted. On the clean estate there is exactly one overlap group
(`monitoring/network-performance`): T001 PulseWatch scores 0.816 (merge),
T002 SignalScope 0.407 (survivor) — both cover R001, so merging loses no unique
coverage. Matches the planted Overlap case. Verified: 12 tests pass (full suite 30).

**Safety-by-design:** the redundancy score is strictly dimensionless — no money
is computed here, keeping every financial figure in the single audited place
(step 5). Missing signals are noted and contribute 0 rather than being imputed.

---

## Step 4 — dependency_check

**Initial thought (before):**
This answers "if we touch this tool, what breaks?" Intent: for a tool, list the
requirements relying on it, each with priority, and — critically — enforce that
`evidence_level = "claimed only"` never counts as coverage, both for the tool
itself and for any peer offered as a fallback. The important derived fact is a
*blocking* dependency: a Must requirement this tool genuinely covers with no
other real coverage, which must be flagged before any retire. Report facts only;
no decision, no money.

**Outcome (after):**
Built `dependency.py` with `dependency_check`, `DependencyReport` (with
`.must_dependencies` / `.blocking_dependencies`) and `RequirementDependency`.
Verified on real data: T033 → Must R003 covered but also by T015 (not blocking);
T013 FlowMesh → R007 `covers=False` because claimed-only, real coverage T012
only; T028 → Must R008 covered, also T032. Unknown tool ids handled gracefully.
Verified: 9 tests pass (full suite 39).

**Safety-by-design:** "claimed only" evidence never counts as coverage — for the
tool itself *or* for any peer offered as a fallback — so the agent can't conclude
"covered elsewhere, safe to retire" on an unproven claim. `blocking_dependencies`
explicitly surfaces a Must with no genuine fallback.

---

## Step 5 — savings_range (the only place money is computed)

**Initial thought (before):**
This is the most rules-sensitive step: every figure must be a (low, base, high)
range with explicit assumptions, and the model must never do arithmetic. Two
shapes: a retire/merge net saving (recoverable share of cost − migration −
uplift) and a licence-shortfall cost (gap × unit price with discount/list/
premium). The subtle part is *conservative pairing*: the low/worst-case saving
must combine the smallest recoverable share with the largest migration and
uplift. I'll encode assumptions as dataclasses with the known defaults and
sanity-check against the two reference results (T001 → 23/94/146k; T028 →
12/15/16.5k) without reading the answer key.

**Outcome (after):**
Built `savings.py` with a frozen `Range`, `RetireAssumptions`,
`ShortfallAssumptions`, `retire_saving`, `licence_shortfall_cost`, and the
`savings_range` dispatcher (preserves `inputs` for audit; unknown kind raises).
Both reference results reproduced exactly. Edge cases handled: no shortfall →
zero range; `licence_qty ≤ 0` without a unit-price override → `ValueError`.
Verified: 14 tests pass (full suite 53).

**Safety-by-design:** this is the single place money is computed; every figure is
a (low, base, high) range carrying its assumptions, so the model never does
arithmetic and results are reproducible. The worst-case (low) figure is paired
conservatively, and an undefined unit price raises rather than guessing.

---

## Step 6 — recommend keep / merge / retire

**Initial thought (before):**
This step composes steps 2–5 into a per-tool recommendation; it decides nothing
on its own that the guardrails don't support. Intent and plan:

- **Decision** ∈ {keep, merge, retire, do-not-renew, procure}, plus a
  **needs-human-review** escape when confidence is low or inputs are missing.
- Every recommendation must carry: **reasoning**, **cited inventory rows**
  (tool ids / requirement ids it relied on), a **confidence** level, a **door
  type**, and a **blast radius**.
- **Door type** (from steering): Two-Way = reversible (tier change, non-renewal,
  licence reduction at renewal); One-Way = irreversible (hardware buy, multi-year
  commit, perpetual licence, decommissioning with no rollback). So retiring a
  `hardware` asset is One-Way; non-renewing a software opex licence is Two-Way.
- **Safety rule:** never recommend retiring a tool with a *blocking* Must
  dependency (from step 4). If one exists, downgrade to keep/flag.
- **Money** only ever comes from `savings_range` (step 5) — the recommender
  passes request rows to it and quotes the returned ranges, never doing sums.
- **Confidence** should be driven by evidence quality, data completeness, and
  (for merges) the overlap redundancy score; anything below a threshold becomes
  "needs human review", not a decision.

Risk to watch: this is where the six planted cases are actually adjudicated, so
I'll sanity-check each case's expected shape (merge PulseWatch; don't-renew
QueueDesk; keep EdgeStore + flag; orphan InsightBox → ask for owner; FlowMesh →
R007 not covered; PAM → procure shortfall) without reading the answer key.

**Outcome (after):**
Built `recommend.py` composing steps 2–5 (relative imports, so it imports as
`portfolio_agent.recommend`). `recommend(inventory, requirements, reference_date)`
returns a `Recommendation` per tool with decision, confidence, door type, blast
radius, reasoning, cited tool/requirement ids, optional `savings` Range, and
flags. Decision order (first match wins): blocking Must dependency → keep + "do
not retire" flag; orphan → needs-review + ask-for-owner; under-provisioned →
procure (+ shortfall range); merge candidate → merge (+ retire saving); renewal
(ending ≤90 days and util ≤40%) → do-not-renew; else keep.

Surprise caught during build: my first cut said "Supports Must R007" for FlowMesh
even though its evidence is claimed-only — a contradiction with step 4. Fixed by
distinguishing *linked-to* from *genuinely covers*: the keep branch only claims
support where `covers=True`, and claimed-only Musts are explicitly reported as
"linked but not covering". Also added a One-Way-Door-on-decommission flag to keep
recommendations for hardware/capex assets (e.g. the EdgeStore backup array), so
the irreversibility is visible even though the status-quo door is Two-Way.

All six planted cases reproduce the expected shapes (T001 merge→T002 w/
23/94/146k; T026 do-not-renew citing T023; T033 keep + One-Way flag + R003;
T019 needs-review orphan; T013 keep + R007-not-covered flag; T028 procure
12/15/16.5k). Verified: 14 tests pass (full suite 67).

**Safety-by-design:** the decision order is safety-first — a blocking Must
dependency forces *keep* before any other rule can fire, so nothing a Must
depends on (without fallback) can be routed to retire/merge. Only genuine
coverage is claimed ("linked" ≠ "covers"); low confidence or missing data →
needs-human-review, not a decision; and One-Way-Door irreversibility is flagged
even on a keep. Money comes solely from `savings_range`.

---

## Step 7 — approval gate

**Initial thought (before):**
Nothing the agent proposes may be finalised without a human decision — this is
the control point the whole design hinges on. Plan:

- A `print_summary(recommendations)` that renders a concise, scannable table:
  tool, decision, confidence, door type, savings range, and any flags. Grouped
  so the human sees retire/merge/do-not-renew/procure/needs-review first (the
  actionable ones) and plain keeps last.
- An `approval_gate(recommendations, ...)` that prints the summary, then **stops
  and waits** for one of three responses: **approve**, **edit**, **reject**.
- Testability: the gate must not hard-depend on real stdin. I'll inject the
  input source as a callable (defaulting to `input`) and the output as a
  writable stream (defaulting to stdout), so tests can drive it deterministically.
- Return a structured `GateResult(outcome, approved_recommendations, note)` so
  step 8 can log exactly what the human decided and which items were approved.
- "edit" means the human amends the set (e.g. drops or changes an item) before
  approving; I'll model it as approve-with-a-modified-list supplied by the
  caller/edit-callback, keeping the gate itself free of business logic.
- The gate actions nothing itself; it only decides whether downstream steps may
  proceed. Unrecognised input re-prompts rather than guessing.

Risk to watch: don't let the gate silently default to "approve" on empty or
unexpected input — ambiguity must re-prompt, and EOF should be treated as a
safe reject.

**Outcome (after):**
Built `approval.py` with a pure `format_summary(recommendations)` (no I/O,
returns a string) and `approval_gate(recommendations, input_fn=input,
output=None, edit_fn=None, max_prompts=10)` returning
`GateResult(outcome, approved_recommendations, note)`. Input and output are
injected, so the whole gate is tested without touching real stdin. Behaviour:
approve/a/yes/y → APPROVED with the current set; reject/r/no/n → REJECTED with an
empty set; edit/e → call `edit_fn` to get an amended set, reprint, and re-prompt
(or report "not available" if no callback). Unrecognised input re-prompts;
empty string never approves; EOF and exceeding `max_prompts` both fail safe to
REJECTED. The summary lists actionable items (retire/merge/do-not-renew/procure/
needs-review) before keeps, each with savings range, cited rows, reasoning,
flags, and blast radius. Verified: 11 tests pass (full suite 78); the real
summary renders "1 merge, 1 do_not_renew, 1 procure, 1 needs_human_review,
32 keep".

**Summary note (as reported at step close):**
Step 7 complete and verified.

- `src/portfolio_agent/approval.py`:
  - `format_summary(recommendations)` — a pure function (no I/O) that renders a
    scannable summary: a counts line, then actionable items (retire / merge /
    do-not-renew / procure / needs-review) first and plain keeps last, each
    showing confidence, door type, savings range, cited rows, reasoning, flags,
    and blast radius.
  - `approval_gate(...)` — prints the summary, then stops and waits for approve /
    edit / reject, returning a structured `GateResult`.
- Safety-by-design: it never auto-approves. Unrecognised input and empty strings
  re-prompt rather than guess; EOF and too many invalid attempts both fail safe
  to reject. Input and output are injectable, so the gate is fully testable with
  no real stdin. The gate actions nothing itself — it only decides whether
  downstream may proceed.
- `tests/test_approval.py` — 11 tests covering approve, reject, shortcut letters,
  re-prompting, EOF, edit-then-approve with an amended set, edit-unavailable, the
  max-prompts guard, and the never-auto-approve rule.
- Verification: full suite 78/78 passing. The real summary on the clean inventory
  renders "1 merge, 1 do_not_renew, 1 procure, 1 needs_human_review, 32 keep".
- Docs updated: DECISIONS.md (before + after for Step 7), PROGRESS.md (layout,
  count, new section, table), and the task list.
- This completes the agent's decision pipeline (steps 1–7). Next is Step 8: the
  agent writes a one-page memo and a step-by-step log of every tool call (and
  never edits the inventory — only reads inputs, writes memo + log).

---


## Step 8 — one-page memo + step-by-step tool-call log

**Initial thought (before):**
The agent must produce two artefacts and — per the steering rules — it writes
*only* the memo and log; it never edits the inventory. Plan:

- A lightweight `Logger` that records every agent tool call as a structured
  entry: sequence number, timestamp, the tool name, a short summary of inputs,
  and a short summary of the result. The log is the audit trail: a reader can
  see exactly what the agent did, in order, and reproduce it.
- An orchestration function `run_agent(...)` that drives steps 1→7 *through* the
  logger: read → classify → overlap → dependency/savings (as composed by
  recommend) → format summary → approval gate. Each call appends a log entry.
- A one-page memo generator: concise, human-readable, UK spelling, lean expert
  language. It should state the estate at a glance (counts), the actionable
  recommendations (merge/retire/do-not-renew/procure/needs-review) with their
  low/base/high ranges, door types and cited rows, the key flags/risks, and the
  approval outcome. Keeps are summarised as a count, not listed line by line, so
  it stays to roughly one page.
- Both artefacts are returned as strings and can be written to disk by the caller
  (so the functions stay pure and testable); a thin writer helper can persist
  them under an `out/` directory.

Design rule to honour: money in the memo is only ever the ranges already
computed by `savings_range` — the memo never recomputes anything. The memo also
must not present a `needs_human_review`/unapproved item as decided.

Risk to watch: keep the memo genuinely one page (don't dump all 36 tools), and
make sure the log captures inputs/results faithfully without leaking large
objects.

**Outcome (after):**
Built `report.py` with a `Logger` (ordered, timestamped entries; an optional
injectable `_clock` for deterministic tests), a `run_agent(...)` orchestrator
that drives steps 1→7 through the logger (6 entries: read_inventory,
read_requirements, classify_tools, overlap_groups, recommend, approval_gate),
`write_memo(run, reference_date)`, and `write_artifacts(run, out_dir)` which
persists `memo.md` + `tool_call_log.md`. The memo gives the estate at a glance,
the actionable recommendations with their low/base/high ranges, door types,
cited rows and flags, summarises keeps as a count, and states the approval
outcome. Verified end-to-end on the clean inventory: 6 calls logged in order; the
memo shows 1 merge / 1 do-not-renew / 1 procure / 1 needs-review / 32 keep with
the correct ranges (23/94/146k, 12/15/16.5k) and APPROVED; the reject path shows
NOT APPROVED. 10 tests pass (full suite 88).

**Safety-by-design:** the agent writes *only* the memo and log — it never edits
the inventory (the orchestrator calls read-only readers). Money in the memo is
only the ranges already computed by `savings_range`; nothing is recomputed. A
`needs_human_review` item is never presented as decided, and the memo's approval
section explicitly says NOT APPROVED unless the human approved. The tool-call log
makes the entire run auditable and reproducible.

---


## Step 9 — evaluation + README

**Initial thought (before):**
The final step proves the agent works and documents it honestly. Two artefacts
plus a doc:

- An **evaluation script** that is *separate from the agent*. The standing rule
  is that the agent and its code never read `answer_key/`; the eval harness is
  not the agent, so it alone may read the key and score the agent's output
  against it. It runs the agent's recommendations on the clean inventory and, for
  each of the six planted cases, scores correct / partly / wrong on the salient
  facts (decision, door type, cited coverage, and the savings range where the key
  gives one). It prints a results table.
- A **messy-file check**: run `read_inventory` on `inventory_messy.csv` and
  confirm all seven planted faults are surfaced (one blocking + six reported).
- A **README**: problem, design, data, results table, honest failures, limits —
  drawing on `challenges.md` and the safety section of `DECISIONS.md`.

Answer-key location problem (discovered up front): `generate.py` writes the key
to `ROOT.parent.parent/answer_key` (the project parent), but at first there was
no key there — the only copy was in a leftover folder from the earlier data zip.
Plan: make the eval script's answer-key path a parameter with a sensible default
(the spec location), so it finds the key without me opening it. I will
**not** read the key's contents myself; the script reads it at run time and the
score is computed in code.

Risk to watch: keep the eval harness strictly outside the agent package (e.g. a
top-level `eval/` dir) so there is no path by which agent code could import or
read the key. Scores must be computed from the key, not hard-coded.

**Outcome (after):**
Built `eval/evaluate.py` as a standalone harness outside the `portfolio_agent`
package. `find_answer_key(explicit)` uses an explicit `--answer-key` path if
given, otherwise the `generate.py` spec location (project-parent `answer_key/`),
where the key is now kept — so `python3 eval/evaluate.py` runs with no flag.
`score_case` grades each
planted case correct/partly/wrong on decision, door type, cited coverage and the
savings range (compared to the key's `reference_*_gbp`); `run_messy_eval`
confirms the blocking duplicate plus the six reported faults (checking T025's
owner fault specifically, not the by-design T019 orphan). Result: **6 correct /
0 partly / 0 wrong**, all **7** messy faults surfaced, **PASS** — and the savings
ranges matched the real key exactly (23/94/146k; 12/15/16.5k), independently
confirming the step-5 maths. Added `tests/test_eval.py` (2 tests; the case test
skips if no key but found it via fallback). Wrote `README.md` (problem, design,
data, how-to-run, results table, honest failures, limitations, layout). Cleaned
temp artefacts.

**Safety-by-design:** the harness is strictly outside the agent package, so no
agent code can import it or reach the key — verified by `grep`: `answer_key`
appears only in `eval/`, never in `src/`. Scores are computed from the key at
run time, not hard-coded. This is the one place the key is read, exactly as the
rules require.

This completes all nine tasks. Full suite: **90 tests passing**; evaluation:
**PASS**.

---
