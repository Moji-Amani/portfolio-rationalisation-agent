#!/usr/bin/env python3
"""Demo runner for the portfolio rationalisation agent.

A single, clean entry point for demos and blog posts. It runs the full agent
pipeline on the synthetic estate and writes the one-page memo + tool-call log.

Usage:
    python3 demo.py                 # interactive: the approval gate prompts you
    python3 demo.py --approve       # non-interactive: auto-approve (for recordings)
    python3 demo.py --reject        # non-interactive: auto-reject
    python3 demo.py --out DIR       # where to write memo.md + tool_call_log.md
                                    # (default: ./demo_out)

The agent only reads the inputs in data/ and writes the memo and log; it never
edits the inventory and never reads the answer key.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from portfolio_agent.report import run_agent, write_artifacts, write_memo  # noqa: E402

REF = _dt.date(2026, 10, 27)
DATA = ROOT / "data"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the portfolio rationalisation agent demo.")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--approve", action="store_true",
                       help="auto-approve the recommendations (non-interactive)")
    group.add_argument("--reject", action="store_true",
                       help="auto-reject the recommendations (non-interactive)")
    ap.add_argument("--out", default=str(ROOT / "demo_out"),
                    help="output directory for memo.md and tool_call_log.md")
    args = ap.parse_args()

    input_fn = None
    if args.approve:
        input_fn = lambda _prompt="": "approve"   # noqa: E731
    elif args.reject:
        input_fn = lambda _prompt="": "reject"     # noqa: E731

    run = run_agent(
        DATA / "inventory.csv",
        DATA / "requirements.csv",
        reference_date=REF,
        input_fn=input_fn,   # None -> the gate prompts interactively
    )

    paths = write_artifacts(run, args.out, REF)

    print()
    print("Artefacts written:")
    print(f"  memo: {paths['memo']}")
    print(f"  log : {paths['log']}")
    print()
    print("=" * 72)
    print(write_memo(run, REF))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
