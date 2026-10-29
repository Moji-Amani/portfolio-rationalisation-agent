#!/usr/bin/env python3
"""Evaluation harness — SEPARATE from the agent.

Standing rule: the agent and its code never read ``answer_key/``. This harness is
NOT the agent; it is an independent scorer that may read the key and grade the
agent's output against it. It lives outside the ``portfolio_agent`` package so no
agent code can import it or the key.

What it does:
  1. Runs the agent's recommendations on the clean inventory.
  2. For each of the six planted cases, scores correct / partly / wrong on the
     salient facts (decision family, door type, cited coverage, and the savings
     range where the key provides one).
  3. Runs the messy file and confirms all seven planted faults are surfaced.
  4. Prints a results table and a final tally.

Usage:
    python3 eval/evaluate.py [--answer-key PATH]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT / "src"))

from portfolio_agent.recommend import recommend  # noqa: E402
from portfolio_agent.validate import (  # noqa: E402
    BlockingValidationError,
    read_inventory,
    read_requirements,
)

DATA = PROJECT / "data"
REF = _dt.date(2026, 10, 27)

CORRECT, PARTLY, WRONG = "correct", "partly", "wrong"

# Candidate locations for the answer key (spec location first, then fallbacks).
_KEY_CANDIDATES = [
    PROJECT.parent / "answer_key" / "answer_key.json",          # generate.py KEY_DIR (canonical)
    Path.home() / "New folder" / "answer_key" / "answer_key.json",  # legacy/alternative location
]


def find_answer_key(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p
        raise FileNotFoundError(f"answer key not found at {p}")
    for cand in _KEY_CANDIDATES:
        if cand.is_file():
            return cand
    raise FileNotFoundError(
        "answer key not found; pass --answer-key PATH. Tried:\n  " +
        "\n  ".join(str(c) for c in _KEY_CANDIDATES))


def _range_matches(rec, key_range) -> bool:
    if rec.savings is None or key_range is None:
        return False
    return (round(rec.savings.low) == round(key_range["low"])
            and round(rec.savings.base) == round(key_range["base"])
            and round(rec.savings.high) == round(key_range["high"]))


def score_case(case, recs_by_id) -> tuple[str, str]:
    """Return (grade, note) for one planted case."""
    name = case.get("name", "")
    tool_ids = case.get("tools", [])
    primary = tool_ids[0] if tool_ids else None
    rec = recs_by_id.get(primary)
    if rec is None:
        return WRONG, f"no recommendation for {primary}"

    d = rec.decision
    flags = " ".join(rec.flags).lower()
    reasons = " ".join(rec.reasoning).lower()

    if name == "Overlap":
        ok_decision = d in ("merge", "retire")
        ok_money = _range_matches(rec, case.get("reference_saving_gbp"))
        ok_cite = any(t in rec.cited_tool_ids for t in tool_ids[1:])  # survivor cited
        if ok_decision and ok_money and ok_cite:
            return CORRECT, "merge, survivor cited, saving range matches"
        if ok_decision:
            return PARTLY, f"decision ok; money={ok_money}, cite={ok_cite}"
        return WRONG, f"decision {d!r}"

    if name == "Renewal":
        ok_decision = d == "do_not_renew"
        ok_door = rec.door_type == "Two-Way Door"
        ok_cover = any(x != primary for x in rec.cited_tool_ids)  # covered elsewhere
        if ok_decision and ok_door and ok_cover:
            return CORRECT, "do-not-renew, Two-Way, coverage cited elsewhere"
        if ok_decision:
            return PARTLY, f"decision ok; door={ok_door}, cover_cited={ok_cover}"
        return WRONG, f"decision {d!r}"

    if name == "Dependency":
        # Keep, and the Must dependency / One-Way-on-decommission must be visible.
        ok_decision = d == "keep"
        ok_flag = "one-way" in flags
        ok_must = any(r in rec.cited_requirement_ids for r in ("R003",))
        if ok_decision and ok_flag and ok_must:
            return CORRECT, "keep + One-Way-on-decommission flag + Must cited"
        if ok_decision and (ok_flag or ok_must):
            return PARTLY, f"keep; flag={ok_flag}, must_cited={ok_must}"
        return WRONG, f"decision {d!r}"

    if name == "Orphan":
        ok_decision = d in ("needs_human_review", "retire")
        ok_owner = "owner" in flags
        if ok_decision and ok_owner:
            return CORRECT, "needs-review + ask-for-owner flag"
        if ok_decision:
            return PARTLY, "decision ok; no owner flag"
        return WRONG, f"decision {d!r}"

    if name == "Claimed only":
        # Must not count claimed-only as covering; flag it.
        ok_flag = "claimed only" in flags
        ok_not_covered = "does not count" in reasons or "not count as covering" in flags
        if ok_flag and ok_not_covered:
            return CORRECT, "claimed-only flagged; R007 not counted as covered"
        if ok_flag:
            return PARTLY, "flagged but coverage wording weak"
        return WRONG, "claimed-only not flagged"

    if name == "Under-provisioned":
        ok_decision = d == "procure"
        ok_money = _range_matches(rec, case.get("reference_cost_gbp"))
        if ok_decision and ok_money:
            return CORRECT, "procure + shortfall cost range matches"
        if ok_decision:
            return PARTLY, f"procure; money={ok_money}"
        return WRONG, f"decision {d!r}"

    return WRONG, f"unknown case {name!r}"


def run_case_eval(key) -> list[tuple]:
    inv = read_inventory(DATA / "inventory.csv").rows
    reqs = read_requirements(DATA / "requirements.csv").rows
    recs_by_id = {r.tool_id: r for r in recommend(inv, reqs, reference_date=REF)}

    results = []
    for case in key["cases"]:
        grade, note = score_case(case, recs_by_id)
        results.append((case["case"], case["name"], case["tools"][0], grade, note))
    return results


def run_messy_eval() -> tuple[bool, list[str]]:
    """Confirm the messy file surfaces all seven planted faults."""
    findings: list[str] = []
    # The duplicate tool_id is the blocking fault.
    try:
        read_inventory(DATA / "inventory_messy.csv")
        blocking_ok = False
    except BlockingValidationError as e:
        blocking_ok = "duplicate" in str(e).lower()
        findings.append(f"blocking: {e}")

    # De-duplicate in-place to surface the remaining six reported faults.
    import csv
    import tempfile
    with open(DATA / "inventory_messy.csv", newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    seen = set()
    for r in body:
        if r[0] in seen:
            r[0] = r[0] + "R"
        seen.add(r[0])
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as tmp:
        w = csv.writer(tmp)
        w.writerow(header)
        w.writerows(body)
        tmp_path = tmp.name
    try:
        result = read_inventory(tmp_path, taxonomy_path=DATA / "taxonomy.csv")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    wanted = {
        "annual_cost_gbp": "missing cost (T010)",
        "contract_end": "invalid date (T014)",
        "utilisation_pct": "utilisation out of range (T017)",
        "evidence_level": "bad evidence level (T021)",
        "capability": "capability not in taxonomy (T031)",
    }
    fields = {i.field for i in result.issues}
    for field, desc in wanted.items():
        if field in fields:
            findings.append(f"reported: {desc}")
    # The planted missing-owner fault is T025 specifically (T019 orphan is by design).
    owner_faults = {i.row_id for i in result.issues if i.field == "owner"}
    if "T025" in owner_faults:
        findings.append("reported: missing owner (T025)")

    all_found = (blocking_ok
                 and all(f in fields for f in wanted)
                 and "T025" in owner_faults)
    return all_found, findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate the portfolio agent.")
    ap.add_argument("--answer-key", default=None, help="path to answer_key.json")
    args = ap.parse_args()

    key_path = find_answer_key(args.answer_key)
    key = json.loads(key_path.read_text())

    print("=" * 72)
    print("PORTFOLIO AGENT — EVALUATION")
    print(f"answer key: {key_path}")
    print(f"reference date: {key.get('reference_date')}")
    print("=" * 72)

    # Part 1: planted cases.
    print("\nPlanted cases (scored against the answer key):\n")
    print(f"{'#':<3}{'case':<20}{'tool':<7}{'grade':<9}note")
    print("-" * 72)
    results = run_case_eval(key)
    tally = {CORRECT: 0, PARTLY: 0, WRONG: 0}
    for num, name, tool, grade, note in results:
        tally[grade] += 1
        print(f"{num:<3}{name:<20}{tool:<7}{grade:<9}{note}")
    print("-" * 72)
    print(f"Tally: {tally[CORRECT]} correct, {tally[PARTLY]} partly, "
          f"{tally[WRONG]} wrong (of {len(results)})")

    # Part 2: messy file.
    print("\nMessy file (expect all 7 planted faults):\n")
    all_found, findings = run_messy_eval()
    for f in findings:
        print(f"  - {f}")
    print(f"\nAll 7 faults surfaced: {'YES' if all_found else 'NO'}")

    ok = (tally[WRONG] == 0 and all_found)
    print("\nRESULT:", "PASS" if ok else "REVIEW")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
