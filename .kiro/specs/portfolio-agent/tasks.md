# Tasks

Reference date for the scenario: 2026-10-27. Inputs: `data/inventory.csv`, `data/requirements.csv`, `data/taxonomy.csv`.

## Done
- [x] Synthetic estate (36 tools, 7 domains), requirements (14), taxonomy, messy variant (7 faults), answer key (stored outside the workspace)

## Next: steps 1–5
- [x] `read_inventory(path)` / `read_requirements(path)`: validate types, dates, ranges (0–100), allowed evidence levels, taxonomy membership, unique IDs. Duplicate ID is blocking; others are reported.
- [x] Classify: map to taxonomy; flag low-confidence mappings.
- [x] `overlap_groups(inventory)`: group by capability; redundancy score from utilisation, users, requirement coverage.
- [x] `dependency_check(tool_id, requirements)`: requirement IDs relying on a tool, with priority; ignore "claimed only" as coverage.
- [x] `savings_range(rows, assumptions)`: the only place numbers are computed. Low/base/high on recoverable share, migration cost, uplift on the surviving tool. Also licence shortfall cost (unit price × gap, with discount/list/premium).
- [x] Unit tests for each tool, including the messy file.

## Then: steps 6–8
- [x] Recommend keep / merge / retire with reasoning, cited rows, confidence, door type, blast radius.
- [x] Approval gate: print summary, stop, wait for approve / edit / reject.
- [x] Write one-page memo and a step-by-step log of every tool call.

## Evaluation
- [x] Run the six planted cases; score correct / partly / wrong against the answer key (run by a separate script, not the agent).
- [x] Run the messy file; expect all 7 faults reported.
- [x] README: problem, design, data, results table, honest failures, limits.
