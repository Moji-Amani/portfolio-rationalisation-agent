"""Entry point so the package can be run as ``python3 -m portfolio_agent``.

Runs the full agent pipeline on the synthetic estate and writes the one-page
memo + tool-call log. Mirrors ``demo.py`` at the project root.

Usage (from the project root, with ``src`` on the path):
    python3 -m portfolio_agent               # interactive approval gate
    python3 -m portfolio_agent --approve     # auto-approve (non-interactive)
    python3 -m portfolio_agent --reject      # auto-reject
    python3 -m portfolio_agent --out DIR     # output directory
"""
from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path

from .report import run_agent, write_artifacts, write_memo

REF = _dt.date(2026, 10, 27)


def _find_data_dir() -> Path:
    """Locate the data/ directory relative to the project root."""
    # package is src/portfolio_agent -> project root is two parents up.
    root = Path(__file__).resolve().parent.parent.parent
    return root / "data"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m portfolio_agent",
                                 description="Portfolio rationalisation agent demo.")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--approve", action="store_true", help="auto-approve (non-interactive)")
    group.add_argument("--reject", action="store_true", help="auto-reject (non-interactive)")
    ap.add_argument("--out", default="demo_out", help="output directory")
    args = ap.parse_args(argv)

    data = _find_data_dir()
    input_fn = None
    if args.approve:
        input_fn = lambda _p="": "approve"   # noqa: E731
    elif args.reject:
        input_fn = lambda _p="": "reject"     # noqa: E731

    run = run_agent(data / "inventory.csv", data / "requirements.csv",
                    reference_date=REF, input_fn=input_fn)
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
