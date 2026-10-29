"""Unit tests for step 8: tool-call log + one-page memo.

Run with:  python -m unittest discover -s tests  (from the project root)
Standard library only.
"""
import datetime as _dt
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from portfolio_agent.report import (  # noqa: E402
    Logger,
    run_agent,
    write_artifacts,
    write_memo,
)

DATA = ROOT / "data"
REF = _dt.date(2026, 10, 27)


def _approve(_prompt=""):
    return "approve"


def _reject(_prompt=""):
    return "reject"


class TestLogger(unittest.TestCase):
    def test_entries_are_ordered_and_timestamped(self):
        clock = lambda: _dt.datetime(2026, 10, 27, 9, 0, 0)  # noqa: E731
        log = Logger(_clock=clock)
        log.log("read_inventory", "path=x", "36 tools")
        log.log("recommend", "36 tools", "36 recs")
        self.assertEqual([e.seq for e in log.entries], [1, 2])
        self.assertEqual(log.entries[0].tool, "read_inventory")
        self.assertIn("2026-10-27T09:00:00", log.render())

    def test_render_contains_in_and_out(self):
        log = Logger()
        log.log("classify_tools", "36 tools", "0 low-confidence")
        text = log.render()
        self.assertIn("in :", text)
        self.assertIn("out:", text)
        self.assertIn("classify_tools", text)


class TestRunAgent(unittest.TestCase):
    def setUp(self):
        self.run = run_agent(
            DATA / "inventory.csv", DATA / "requirements.csv",
            reference_date=REF, input_fn=_approve, output=io.StringIO())

    def test_logs_every_pipeline_step(self):
        tools = [e.tool for e in self.run.log.entries]
        for expected in ("read_inventory", "read_requirements", "classify_tools",
                         "overlap_groups", "recommend", "approval_gate"):
            self.assertIn(expected, tools)

    def test_produces_one_rec_per_tool(self):
        self.assertEqual(len(self.run.recommendations), 36)

    def test_gate_recorded_in_log(self):
        last = self.run.log.entries[-1]
        self.assertEqual(last.tool, "approval_gate")
        self.assertIn("approved", last.result)

    def test_validation_advisory_surfaced(self):
        # T019 orphan missing owner is the one by-design advisory.
        self.assertEqual(len(self.run.issues), 1)


class TestMemo(unittest.TestCase):
    def test_memo_lists_actionable_with_ranges(self):
        run = run_agent(DATA / "inventory.csv", DATA / "requirements.csv",
                        reference_date=REF, input_fn=_approve, output=io.StringIO())
        memo = write_memo(run, REF)
        self.assertIn("MERGE", memo)
        self.assertIn("£23,000 / £94,000 / £146,000", memo)       # overlap saving
        self.assertIn("£12,000 / £15,000 / £16,500", memo)        # shortfall cost
        self.assertIn("APPROVED", memo)
        self.assertIn("only reads inputs and writes this memo", memo)

    def test_memo_shows_not_approved_when_rejected(self):
        run = run_agent(DATA / "inventory.csv", DATA / "requirements.csv",
                        reference_date=REF, input_fn=_reject, output=io.StringIO())
        memo = write_memo(run, REF)
        self.assertIn("NOT APPROVED", memo)

    def test_memo_summarises_keeps_as_count_not_list(self):
        run = run_agent(DATA / "inventory.csv", DATA / "requirements.csv",
                        reference_date=REF, input_fn=_approve, output=io.StringIO())
        memo = write_memo(run, REF)
        self.assertIn("32 tool(s) recommended to keep", memo)


class TestArtifacts(unittest.TestCase):
    def test_write_artifacts_creates_files(self):
        run = run_agent(DATA / "inventory.csv", DATA / "requirements.csv",
                        reference_date=REF, input_fn=_approve, output=io.StringIO())
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_artifacts(run, tmp, REF)
            self.assertTrue(paths["memo"].exists())
            self.assertTrue(paths["log"].exists())
            self.assertIn("decision memo", paths["memo"].read_text())
            self.assertIn("Tool-call log", paths["log"].read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
