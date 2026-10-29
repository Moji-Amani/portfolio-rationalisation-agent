# Portfolio rationalisation agent

**Outcome:** turns a tooling estate into safe, evidence-backed keep / merge / retire decisions, with savings as ranges and a human sign-off before anything is final.

**Designed by Mojdeh Amani** (agent design, guardrails and evaluation). Built with Kiro.
*v1 is a deterministic, fully tested core; v2 adds a Gemini layer through Google ADK.*

An agent that analyses a software/tooling estate against business requirements
and recommends which tools to **keep, merge, or retire** — with guardrails that
stop it overclaiming or acting on its own. Every figure is a range with stated
assumptions, every recommendation cites its evidence, and nothing is finalised
without a human approval gate.

Reference date for the scenario: **2026-10-27**. Data is synthetic.

### What it produces

Output of `python3 demo.py`: the agent stops at the approval gate with these recommendations (excerpt).

```text
Summary: 1 merge, 1 do_not_renew, 1 procure, 1 needs_human_review, 32 keep

[MERGE] T001 PulseWatch Enterprise  (confidence: high; Two-Way Door)
    savings (low/base/high): £23,000 / £94,000 / £146,000
    cited tools: T001, T002
    - Overlaps with SignalScope (T002) on capability 'monitoring/network-performance'; redundancy score 0.82.
    - Its requirements are also covered by SignalScope, so merging loses no unique coverage.
    blast radius: Users of PulseWatch Enterprise migrate to SignalScope

[PROCURE] T028 Sentinel Vault PAM  (confidence: high; Two-Way Door)
    savings (low/base/high): £12,000 / £15,000 / £16,500
    - 260 active users exceed 200 licences (shortfall of 60).
    - Supports Must requirement(s) R008.

[NEEDS_HUMAN_REVIEW] T019 InsightBox  (confidence: low; Two-Way Door)
    - Zero active users.
    ! No owner recorded; identify an owner before any action.

approve / edit / reject >
```

After approval it writes a one-page decision memo (`memo.md`) and a step-by-step tool-call log (`tool_call_log.md`).

---

## 1. The problem

Large estates accumulate overlapping, under-used, or unsupported tools. Deciding
what to cut is risky: retire the wrong thing and you break a requirement a
business depends on; trust a vendor's claim and you over-report coverage; quote a
single savings number and you mislead. The goal here is an agent that reasons
about rationalisation **safely and auditably**, not one that maximises cuts.

The governing rules (see `.kiro/steering/rules.md`) are the real specification:

- Synthetic/public data only.
- Every number is a `(low, base, high)` range with stated assumptions; **all
  arithmetic is in code**, never done by the model.
- Every recommendation cites the inventory rows it used and carries a confidence.
- Each is tagged **Two-Way Door** (reversible) or **One-Way Door** (irreversible)
  with a blast radius.
- Never recommend retiring something a **Must** requirement depends on without
  flagging the dependency.
- `evidence_level = "claimed only"` never counts as covering a requirement.
- Below the confidence threshold → "needs human review", not decided.
- Nothing is finalised without the **human approval gate**.
- The agent never edits the inventory; it only reads inputs and writes a memo and
  a log.
- The agent and its code must never read `answer_key/`.

---

## 2. Design

The agent is a pipeline of small, independently tested functions. Each does one
job; later steps compose earlier ones.

| Module | Role |
|--------|------|
| `validate.py` | Read + validate inventory/requirements. Duplicate id is blocking; every other problem is reported, not dropped. |
| `classify.py` | Grade each capability against the taxonomy (`exact` / `domain_only` / `unknown`); flag low-confidence mappings. Never invents a capability. |
| `overlap.py` | Group tools by capability and score redundancy (dimensionless; no money). |
| `dependency.py` | Which requirements rely on a tool, with priority. `"claimed only"` never counts as coverage. Surfaces *blocking* Must dependencies. |
| `savings.py` | **The only place money is computed.** Every output a `(low, base, high)` range with assumptions. |
| `recommend.py` | Compose the above into a decision per tool with reasoning, cited rows, confidence, door type, blast radius. |
| `approval.py` | Print a summary, then stop and wait for approve / edit / reject. Never auto-approves. |
| `report.py` | Write the one-page memo and the step-by-step tool-call log. Writes nothing else. |

**Safety by design** runs through every step (full list in `DECISIONS.md`):
blocking a corrupt file but reporting (not hiding) lesser faults; trusting only
exact classifications; keeping all money in one audited place as ranges;
refusing to count unproven ("claimed only") coverage; a safety-first decision
order where a blocking Must dependency forces *keep*; a gate that treats
ambiguity as "ask again" and EOF as a safe reject; and an agent that only reads
inputs and writes a memo + log.

The decision order in `recommend.py` (first match wins) is deliberately
safety-first:

1. blocking Must dependency → **keep** + "do not retire" flag
2. orphan (no owner / 0 users) → **needs human review** + ask-for-owner
3. under-provisioned (users > licences) → **procure** + shortfall range
4. merge candidate (in an overlap group) → **merge** + retire-saving range
5. renewal (contract ≤ 90 days away and ≤ 40% utilised) → **do not renew**
6. otherwise → **keep**

---

## 3. Data

Deterministically generated by `data/generate.py`:

- `inventory.csv` — 36 tools across 7 domains, with cost, contract end, licences,
  active users, utilisation, owner, mapped requirements, and evidence level.
- `requirements.csv` — 14 requirements (Must / Should / Could) with thresholds.
- `taxonomy.csv` — 35 capabilities → 7 domains.
- `inventory_messy.csv` — the same estate with **7 planted faults** for the
  validation test.

Six scenarios are planted into the clean estate (overlap, renewal, dependency,
orphan, claimed-only, under-provisioned). The expected answers live in an
`answer_key/` kept **outside** this project; the agent never reads it.

---

## 4. How to run

```bash
# From the project root.
cd portfolio-rationalisation-agent

# Unit tests (standard library only; no pytest needed).
python3 -m unittest discover -s tests          # 90 tests

# Demo — full agent run; writes memo.md + tool_call_log.md to ./demo_out.
python3 demo.py                 # interactive: the approval gate prompts you
python3 demo.py --approve       # non-interactive: auto-approve (for recordings)
python3 demo.py --reject        # non-interactive: auto-reject

# Same demo, run as a package (needs src/ on the path):
PYTHONPATH=src python3 -m portfolio_agent --approve

# Evaluation (separate from the agent; it may read the answer key).
python3 eval/evaluate.py        # no flag needed; key is at the default location
```

> **Note on the answer key.** By design the key lives **outside** this project so
> the agent can never read it (steering rule). It is at the `generate.py` default
> location — `answer_key/answer_key.json` in the folder above the project — which is
> outside the project folder but discoverable by the evaluator. `eval/evaluate.py`
> finds it automatically, so `python3 eval/evaluate.py` runs with no flag; pass
> `--answer-key PATH` only if the key is elsewhere. The agent package never reads
> it; only `eval/evaluate.py` does.

---

## 5. Results

Evaluation output (`python3 eval/evaluate.py`), scored against the answer key:

| # | Case | Tool | Grade | Basis |
|---|------|------|-------|-------|
| 1 | Overlap | T001 | correct | merge into T002, survivor cited, saving £23k/£94k/£146k matches |
| 2 | Renewal | T026 | correct | do-not-renew, Two-Way, R004 still covered (T023 cited) |
| 3 | Dependency | T033 | correct | keep + One-Way-on-decommission flag + Must R003 cited |
| 4 | Orphan | T019 | correct | needs-review + ask-for-owner flag |
| 5 | Claimed only | T013 | correct | claimed-only flagged; R007 not counted as covered |
| 6 | Under-provisioned | T028 | correct | procure + shortfall £12k/£15k/£16.5k matches |

**Tally: 6 correct, 0 partly, 0 wrong.**

Messy file: all **7** planted faults surfaced — duplicate tool_id (blocking),
plus missing cost (T010), invalid date (T014), out-of-range utilisation (T017),
bad evidence level (T021), missing owner (T025), and capability not in taxonomy
(T031). **Result: PASS.**

Unit tests: **90 passing** (`validate` 10, `classify` 8, `overlap` 12,
`dependency` 9, `savings` 14, `recommend` 14, `approval` 11, `report` 10,
`eval` 2).

---

## 6. Honest failures and things that bit us

Recorded in full in `challenges.md`; the ones worth surfacing here:

- **The "clean" file was not clean.** T019 (the orphan) has no owner by design.
  A first test wrongly assumed zero issues. The validator was right to flag it;
  the test was fixed. Lesson: a by-design advisory is not a bug.
- **"Linked" vs "covers" contradiction.** The recommender initially said
  FlowMesh "supports Must R007" even though its evidence is claimed-only —
  contradicting the dependency check. Fixed by only claiming support where
  coverage is genuine.
- **Conservative range pairing.** The worst-case (low) saving has to pair the
  smallest recoverable share with the *largest* migration and uplift costs, not
  the smallest of everything. Getting this wrong understates risk.
- **Answer-key location.** The key was not where `generate.py` writes it; the
  eval script was given a configurable path with fallbacks rather than
  hard-coding one.

---

## 7. Limitations

- **Synthetic, small estate.** 36 tools, deterministic. Real estates are larger,
  messier, and have ambiguous capabilities; the `domain_only`/`unknown`
  classification tiers would see far more use.
- **Assumptions are defaults, not truths.** The recoverable-share, migration,
  uplift, discount and premium figures in `savings.py` are stated assumptions you
  should override per engagement. The ranges are only as good as those inputs.
- **Heuristic thresholds.** "Low utilisation ≤ 40%" and "renewal window ≤ 90
  days" are blunt; a real deployment would tune them per domain.
- **Overlap is capability-exact.** Two tools only count as overlapping if they
  share the exact capability string; near-duplicates under different capabilities
  are not detected.
- **No live action.** By design the agent proposes; it never executes. Carrying
  out an approved action (e.g. raising a change request) is out of scope.
- **Single-run evaluation.** The harness scores one deterministic run; it is not
  a statistical evaluation over many estates.

---

## 8. Project layout

```
portfolio-rationalisation-agent/
├── .kiro/                     # spec (tasks.md) and steering (rules.md)
├── data/                      # synthetic inventory, requirements, taxonomy, generator
├── src/portfolio_agent/       # the agent package (steps 1–8)
├── tests/                     # unit tests (stdlib unittest)
├── eval/evaluate.py           # evaluation harness (separate from the agent)
├── demo.py                    # one-command demo entry point
├── PROGRESS.md                # current state / handover
├── DECISIONS.md               # per-task reasoning + safety decisions
├── challenges.md              # problems hit and how they were fixed
├── LICENSE                    # MIT
└── README.md                  # this file
```

(The package is also runnable as `python3 -m portfolio_agent` via
`src/portfolio_agent/__main__.py`.)

---

## 9. Licence

MIT — see [`LICENSE`](LICENSE). 
