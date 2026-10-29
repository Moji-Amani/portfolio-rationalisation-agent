"""Unit tests for step 7: the approval gate.

Run with:  python -m unittest discover -s tests  (from the project root)
Standard library only. Input/output are injected so no real stdin is used.
"""
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from portfolio_agent.approval import (  # noqa: E402
    APPROVED,
    REJECTED,
    approval_gate,
    format_summary,
)
from portfolio_agent.recommend import Recommendation  # noqa: E402
from portfolio_agent.savings import Range  # noqa: E402


def make_recs():
    return [
        Recommendation(
            tool_id="T001", name="PulseWatch", decision="merge",
            confidence="high", door_type="Two-Way Door",
            blast_radius="users migrate", reasoning=["overlaps with T002"],
            cited_tool_ids=["T001", "T002"], cited_requirement_ids=["R001"],
            savings=Range(23000, 94000, 146000, "assumptions"), flags=[]),
        Recommendation(
            tool_id="T002", name="SignalScope", decision="keep",
            confidence="high", door_type="Two-Way Door",
            blast_radius="None", reasoning=["78% util"],
            cited_tool_ids=["T002"], cited_requirement_ids=["R001"]),
    ]


def scripted_input(responses):
    """Return an input_fn that yields each response in turn."""
    it = iter(responses)

    def _fn(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    return _fn


class TestFormatSummary(unittest.TestCase):
    def test_summary_contains_decisions_and_money(self):
        text = format_summary(make_recs())
        self.assertIn("MERGE", text)
        self.assertIn("KEEP", text)
        self.assertIn("£23,000", text)
        self.assertIn("approve / edit / reject", text)

    def test_actionable_items_sorted_before_keep(self):
        text = format_summary(make_recs())
        self.assertLess(text.index("MERGE"), text.index("KEEP"))


class TestApprovalGate(unittest.TestCase):
    def test_approve(self):
        out = io.StringIO()
        res = approval_gate(make_recs(), input_fn=scripted_input(["approve"]), output=out)
        self.assertEqual(res.outcome, APPROVED)
        self.assertEqual(len(res.approved_recommendations), 2)

    def test_reject_actions_nothing(self):
        out = io.StringIO()
        res = approval_gate(make_recs(), input_fn=scripted_input(["reject"]), output=out)
        self.assertEqual(res.outcome, REJECTED)
        self.assertEqual(res.approved_recommendations, [])

    def test_shortcut_letters(self):
        out = io.StringIO()
        self.assertEqual(
            approval_gate(make_recs(), input_fn=scripted_input(["y"]), output=out).outcome,
            APPROVED)
        self.assertEqual(
            approval_gate(make_recs(), input_fn=scripted_input(["n"]), output=out).outcome,
            REJECTED)

    def test_unrecognised_then_approve_reprompts(self):
        out = io.StringIO()
        res = approval_gate(
            make_recs(), input_fn=scripted_input(["maybe", "approve"]), output=out)
        self.assertEqual(res.outcome, APPROVED)
        self.assertIn("Unrecognised", out.getvalue())

    def test_eof_fails_safe_to_reject(self):
        out = io.StringIO()
        res = approval_gate(make_recs(), input_fn=scripted_input([]), output=out)
        self.assertEqual(res.outcome, REJECTED)
        self.assertIn("EOF", res.note)

    def test_edit_then_approve_uses_amended_set(self):
        out = io.StringIO()

        def drop_merges(recs):
            return [r for r in recs if r.decision != "merge"]

        res = approval_gate(
            make_recs(),
            input_fn=scripted_input(["edit", "approve"]),
            output=out,
            edit_fn=drop_merges,
        )
        self.assertEqual(res.outcome, APPROVED)
        # The merge was dropped during edit -> only the keep remains.
        self.assertEqual(len(res.approved_recommendations), 1)
        self.assertEqual(res.approved_recommendations[0].tool_id, "T002")

    def test_edit_unavailable_without_callback(self):
        out = io.StringIO()
        res = approval_gate(
            make_recs(),
            input_fn=scripted_input(["edit", "reject"]),
            output=out,
        )
        self.assertEqual(res.outcome, REJECTED)
        self.assertIn("not available", out.getvalue())

    def test_too_many_invalid_fails_safe(self):
        out = io.StringIO()
        res = approval_gate(
            make_recs(),
            input_fn=scripted_input(["?"] * 20),
            output=out,
            max_prompts=5,
        )
        self.assertEqual(res.outcome, REJECTED)

    def test_never_auto_approves(self):
        # An empty string must never be read as approval.
        out = io.StringIO()
        res = approval_gate(
            make_recs(), input_fn=scripted_input(["", "reject"]), output=out)
        self.assertEqual(res.outcome, REJECTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
