# Challenges & fixes (Steps 1–9)

A record of the genuine problems that arose while building the agent, and how
each was resolved. These are the real issues hit during development — useful for
anyone picking the project up, and honest input for the "failures/limits"
section of the final README (step 9).

---

## Step 1 — input validation

### Challenge 1.1 — the "clean" inventory is not actually clean
**What happened:** my first test asserted that `inventory.csv` produced zero
validation issues. It failed: T019 (InsightBox) has an empty `owner` and 0 users.
**Root cause:** this is *by design* — T019 is the planted "orphan" case, not a
data error. My validator correctly flagged the missing owner (per the steering
rule "flag, don't guess"), but my test wrongly assumed a spotless file.
**Fix:** kept the validator behaviour (flag, don't suppress) and corrected the
test to expect exactly one by-design advisory (T019 missing owner). This also
clarified the design contract: a missing owner is a *reported* advisory, never a
blocking error.

### Challenge 1.2 — separating blocking from reported problems
**What happened:** needed a single read path that stops hard on some problems but
keeps going on others.
**Root cause:** a duplicate primary key makes the rest of the file untrustworthy,
whereas a bad date in one row does not.
**Fix:** duplicate `tool_id` / `requirement_id` raises `BlockingValidationError`;
every other problem is appended to a non-blocking `Issue` list while valid rows
are still returned. This matched the spec ("duplicate ID is blocking; others are
reported") and made the messy-file test easy to express.

### Challenge 1.3 — counting faults in the messy file
**What happened:** the messy-file test expected "6 remaining faults after the
blocking one" but got 7.
**Root cause:** the messy file inherits the same by-design T019 orphan advisory
as the clean file, on top of its 6 planted row-faults.
**Fix:** asserted the specific expected faults by field/row, and set the total to
7 (6 planted + 1 inherited orphan), with a comment explaining why.

---

## Step 2 — classification

### Challenge 2.1 — "classify" when the data already has a capability column
**What happened:** the inventory already carries a `capability`, so a naive
"classifier" would have nothing to do.
**Root cause:** the real task is confidence grading, not label invention — and
the steering rules forbid guessing a capability.
**Fix:** reframed classification as a confidence judgement with three levels —
`exact` (trusted), `domain_only` (domain prefix known, leaf unknown → flagged),
`unknown` (flagged). Only `exact` is trusted; everything else sets
`needs_review`. `security/firewall` (the messy-file capability) correctly lands
as `domain_only`.

---

## Step 3 — overlap & redundancy

### Challenge 3.1 — keeping money out of the scoring
**What happened:** it was tempting to express redundancy partly in pounds (e.g.
"you'd save £X by dropping this").
**Root cause:** the steering rules require *all* arithmetic to live in
`savings_range` (step 5), as ranges with assumptions.
**Fix:** made the redundancy score strictly dimensionless (mean of three [0,1]
signals) and deferred every monetary figure to step 5. The overlap module only
ranks tools and exposes the raw signals.

### Challenge 3.2 — missing signals skewing the score
**What happened:** a tool with a missing utilisation or user count could crash or
silently distort the mean.
**Fix:** missing signals (`None`) contribute 0 and are recorded in a `note`, so
the score stays in range and the gap is visible rather than hidden.

---

## Step 4 — dependency check

### Challenge 4.1 — "claimed only" must not count as coverage, twice over
**What happened:** the subtle part of the rule is that a claimed-only link must be
ignored both for the tool being checked *and* for any peer offered as a fallback.
**Root cause:** if a claimed-only peer were counted, the agent could wrongly
conclude "it's covered elsewhere, safe to retire".
**Fix:** a shared `_covers()` helper enforces `evidence != "claimed only"`
everywhere — for `covers` (this tool) and for `other_covering_tools` (peers).
Verified on FlowMesh/R007: FlowMesh `covers=False`, and R007's only genuine
coverage is ServiceWeave.

### Challenge 4.2 — distinguishing "a Must depends on it" from "blocking"
**What happened:** needed to tell apart a Must dependency that has a fallback
(safe) from one that does not (dangerous).
**Fix:** added `.blocking_dependencies` = Must + genuinely covered by this tool +
not covered elsewhere. The backup array (T033) depends on Must R003 but is *not*
blocking because StateKeeper (T015) also covers it.

---

## Step 5 — savings_range (money)

### Challenge 5.1 — conservative pairing of low/base/high
**What happened:** the first instinct was to compute the "low" saving from the
low value of every term — but that is wrong.
**Root cause:** a conservative (low) saving should combine the *smallest*
recoverable share with the *largest* migration and uplift costs. Mixing
"low of everything" understates cost and overstates the worst case incorrectly.
**Fix:** encoded the assumption tuples so recoverable is smallest-first but
migration and uplift are largest-first, so `low` pairs the pessimistic revenue
with the pessimistic costs. Verified exactly against the two reference results
(T001 → 23/94/146k; T028 → 12/15/16.5k).

### Challenge 5.2 — divide-by-zero on unit price
**What happened:** unit price = annual_cost / licence_qty blows up if licences
are 0.
**Fix:** return a zero range when there is no shortfall, and raise a clear
`ValueError` if `licence_qty <= 0` and no explicit unit-price override is given.

---

## Step 6 — recommendation engine

### Challenge 6.1 — "linked to" vs "genuinely covers" (contradiction bug)
**What happened:** the first version printed "Supports Must requirement R007" for
FlowMesh even though FlowMesh's evidence is claimed-only — directly contradicting
step 4.
**Root cause:** the keep branch used `must_dependencies` (which lists *linked*
Musts) without checking the `covers` flag.
**Fix:** split the keep reasoning — only claim "Supports Must Rxxx" where
`covers=True`; claimed-only Musts are reported as "linked to … but does not count
as covering them". Now consistent with the dependency check.

### Challenge 6.2 — door type for a kept hardware asset
**What happened:** a "keep" is status quo (Two-Way), but that hid the fact that
*decommissioning* a hardware/capex asset later would be irreversible — exactly
the point of the backup-array planted case.
**Fix:** keep recommendations still show Two-Way for the status quo, but
hardware/capex keeps carry an explicit flag: "If ever decommissioned, this is a
One-Way Door". The irreversibility is surfaced without mislabelling the current
decision.

### Challenge 6.3 — ordering the decision rules
**What happened:** several conditions can be true at once (e.g. a low-utilisation
tool that also has a blocking dependency).
**Root cause:** without a defined order, an unsafe decision could win.
**Fix:** a fixed first-match-wins order with safety first: blocking Must
dependency → orphan → under-provisioned → merge → renewal → keep. The blocking
check comes first so nothing a Must depends on (without fallback) can ever be
routed to retire/merge.

### Challenge 6.4 — relative imports require package import
**What happened:** `recommend.py` uses `from .dependency import …`, so importing
it directly by file path fails.
**Fix:** the test harness adds `src/` to `sys.path` and imports
`portfolio_agent.recommend` as a package member, which resolves the relative
imports cleanly.

---

## Step 7 — approval gate

### Challenge 7.1 — the gate must never read ambiguity as consent
**What happened:** the obvious loop ("read a line; if not 'reject', proceed")
would treat an empty line, a typo, or an accidental Enter as approval.
**Root cause:** approval is the single most safety-critical input in the system;
a permissive default here defeats the whole guardrail design.
**Fix:** only explicit affirmatives (approve/a/yes/y) approve. Empty strings and
unrecognised input re-prompt rather than guess, and EOF or too many invalid
attempts fail safe to *reject*. Verified by a dedicated "never auto-approves on
empty string" test.

### Challenge 7.2 — testing an interactive gate without real stdin
**What happened:** a gate built around the builtin `input()` and `print()` can't
be driven deterministically in unit tests, and would hang waiting for a human.
**Root cause:** hard dependency on real stdin/stdout.
**Fix:** injected the input source as a callable (`input_fn`, default `input`)
and the output as a stream (`output`, default stdout). Tests use a
`scripted_input([...])` helper and an `io.StringIO` buffer, so every branch is
covered with no real terminal. A `max_prompts` guard prevents an infinite
re-prompt loop.

### Challenge 7.3 — where should "edit" logic live?
**What happened:** "edit" implies changing the recommendation set, which could
pull business logic into the gate.
**Root cause:** mixing presentation/approval with editing rules would make the
gate harder to reason about and test.
**Fix:** modelled "edit" as a caller-supplied `edit_fn(current) -> amended`
callback. The gate stays free of business logic: it calls back, reprints the
amended set, and re-prompts for approval. If no callback is provided, edit is
cleanly reported as unavailable.

---

## Step 8 — memo + tool-call log

### Challenge 8.1 — keeping the memo to one page
**What happened:** a naive memo would list all 36 tools and run several pages.
**Root cause:** most tools are plain keeps that carry no action.
**Fix:** the memo lists only actionable items (merge / do-not-renew / procure /
needs-review) in full, and summarises keeps as a single count with a note about
the One-Way-Door caveat for hardware. One page, signal over noise.

### Challenge 8.2 — the log must be reproducible in tests
**What happened:** timestamps from `datetime.now()` make the rendered log
non-deterministic, so a test can't assert on its content.
**Root cause:** wall-clock time in the output.
**Fix:** the `Logger` accepts an optional injectable `_clock` callable; tests
pass a fixed clock and assert the exact timestamp, while production uses the real
clock by default.

### Challenge 8.3 — not recomputing money / not overstating certainty
**What happened:** it would be easy for the memo generator to re-derive a figure
or present a `needs_human_review`/unapproved item as if decided.
**Root cause:** the memo is the human-facing surface, so any drift here is the
most visible and most dangerous.
**Fix:** the memo only ever prints the `Range` objects already produced by
`savings_range` (never recomputes), summarises `needs_human_review` as exactly
that, and prints "NOT APPROVED" unless the approval gate returned APPROVED. A
footer states the agent only reads inputs and writes the memo + log.

---

## Step 9 — evaluation + README

### Challenge 9.1 — the answer key wasn't where the spec says
**What happened:** `generate.py` writes the key to the project-parent
`answer_key/`, but no key existed there; the only copy was in a leftover folder
(`~/New folder/answer_key/answer_key.json`) from the earlier data zip.
**Root cause:** the data and key zips were extracted/moved separately during
setup, so the key ended up detached from the project.
**Fix:** `find_answer_key()` takes an explicit `--answer-key` path and otherwise
tries the spec location then the known alternative. No path is hard-coded into
scoring; the harness just needs to *locate* the file, then reads it at run time.
**Resolved:** the key was subsequently moved to the canonical `generate.py`
location (`…/Portfolio Rationalisation Agent/answer_key/answer_key.json`, outside
`portfolio-agent/`), so `python3 eval/evaluate.py` now runs with no `--answer-key`
flag. The configurable path + fallbacks remain for portability.

### Challenge 9.2 — honouring "never read the answer key" without being unable to score
**What happened:** the agent (and I) must never read the key, yet the evaluation
has to compare against it.
**Root cause:** the rule applies to the agent and its code, not to an independent
evaluator.
**Fix:** put the harness in a top-level `eval/` directory, entirely outside the
`portfolio_agent` package, so no agent code can import it or reach the key.
Verified structurally with `grep`: `answer_key` appears only under `eval/`, never
under `src/`. The harness reads the key; the agent never does.

### Challenge 9.3 — scoring free-text expectations objectively
**What happened:** the key's `expected` fields are prose; grading on string match
would be brittle.
**Root cause:** prose expectations don't compare cleanly to structured output.
**Fix:** scored each case on concrete, structured facts instead — decision
family, door type, cited coverage, and the numeric savings range against the
key's `reference_*_gbp` values (compared as rounded low/base/high). The ranges
matched exactly, which also independently reconfirmed the step-5 maths.

---

## Cross-cutting

### Tooling: no pytest available
**What happened:** the environment has Python 3.14 but no pytest.
**Fix:** all tests use the standard-library `unittest` and run via
`python3 -m unittest discover -s tests`. No external dependencies, so the suite
runs anywhere.

### AST rewrite tool couldn't match a multi-statement block
**What happened:** an attempt to rewrite the keep branch with the structural
pattern tool failed ("multiple AST nodes").
**Fix:** used a plain string replacement for that multi-statement edit instead;
the AST tool is better suited to single-node patterns.
