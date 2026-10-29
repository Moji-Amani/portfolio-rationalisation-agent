"""Unit tests for step 3: overlap_groups and redundancy scoring.

Run with:  python -m unittest discover -s tests  (from the project root)
Standard library only.
"""
import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from portfolio_agent.overlap import overlap_groups  # noqa: E402
from portfolio_agent.validate import read_inventory  # noqa: E402

DATA = ROOT / "data"


@dataclass
class FakeTool:
    """Minimal stand-in for Tool so scoring can be tested in isolation."""
    tool_id: str
    name: str
    capability: str
    utilisation_pct: int | None
    active_users: int | None
    requirement_ids: list = field(default_factory=list)


class TestOverlapOnCleanInventory(unittest.TestCase):
    def setUp(self):
        self.groups = overlap_groups(read_inventory(DATA / "inventory.csv").rows)

    def test_single_overlap_group(self):
        # Only monitoring/network-performance has >1 tool in the clean estate.
        self.assertEqual(len(self.groups), 1)
        self.assertEqual(self.groups[0].capability, "monitoring/network-performance")

    def test_group_has_both_tools(self):
        ids = {t.tool_id for t in self.groups[0].tools}
        self.assertEqual(ids, {"T001", "T002"})

    def test_survivor_is_higher_utilised_tool(self):
        # T002 SignalScope (78% util, 210 users) should survive over
        # T001 PulseWatch (22% util, 70 users).
        self.assertEqual(self.groups[0].survivor.tool_id, "T002")

    def test_merge_candidate_is_pulsewatch(self):
        cands = self.groups[0].merge_candidates
        self.assertEqual([t.tool_id for t in cands], ["T001"])

    def test_merge_candidate_requirement_covered_elsewhere(self):
        # PulseWatch's only requirement R001 is also covered by SignalScope,
        # so merging loses no unique coverage.
        t001 = next(t for t in self.groups[0].tools if t.tool_id == "T001")
        self.assertEqual(t001.requirements_covered_elsewhere, ["R001"])
        self.assertEqual(t001.unique_requirements, [])

    def test_redundancy_score_in_range(self):
        for g in self.groups:
            for t in g.tools:
                self.assertGreaterEqual(t.redundancy_score, 0.0)
                self.assertLessEqual(t.redundancy_score, 1.0)

    def test_weaker_tool_scores_higher(self):
        t001 = next(t for t in self.groups[0].tools if t.tool_id == "T001")
        t002 = next(t for t in self.groups[0].tools if t.tool_id == "T002")
        self.assertGreater(t001.redundancy_score, t002.redundancy_score)


class TestOverlapScoringUnit(unittest.TestCase):
    def test_no_group_for_single_tool(self):
        tools = [FakeTool("A", "Solo", "cap/x", 50, 10, ["R1"])]
        self.assertEqual(overlap_groups(tools), [])

    def test_identical_tools_split_survivor_deterministically(self):
        # Two identical tools: both score the same; min() keeps the first.
        tools = [
            FakeTool("A", "Alpha", "cap/x", 50, 100, ["R1"]),
            FakeTool("B", "Beta", "cap/x", 50, 100, ["R1"]),
        ]
        g = overlap_groups(tools)[0]
        self.assertEqual(len(g.tools), 2)
        # Both cover R1 via the peer -> coverage component 1.0 for each.
        for t in g.tools:
            self.assertEqual(t.requirements_covered_elsewhere, ["R1"])

    def test_tool_with_no_requirements_has_full_coverage_component(self):
        # A tool mapping to no requirements loses nothing unique by merging.
        tools = [
            FakeTool("A", "Alpha", "cap/x", 90, 100, []),
            FakeTool("B", "Beta", "cap/x", 10, 5, ["R1"]),
        ]
        g = overlap_groups(tools)[0]
        a = next(t for t in g.tools if t.tool_id == "A")
        self.assertEqual(a.unique_requirements, [])

    def test_missing_signals_noted_and_safe(self):
        tools = [
            FakeTool("A", "Alpha", "cap/x", None, None, ["R1"]),
            FakeTool("B", "Beta", "cap/x", 80, 200, ["R1"]),
        ]
        g = overlap_groups(tools)[0]
        a = next(t for t in g.tools if t.tool_id == "A")
        self.assertIn("missing", a.note)
        # Score still valid and in range despite missing signals.
        self.assertGreaterEqual(a.redundancy_score, 0.0)
        self.assertLessEqual(a.redundancy_score, 1.0)

    def test_unique_requirement_not_counted_as_covered(self):
        tools = [
            FakeTool("A", "Alpha", "cap/x", 30, 10, ["R1", "R2"]),
            FakeTool("B", "Beta", "cap/x", 80, 200, ["R1"]),
        ]
        g = overlap_groups(tools)[0]
        a = next(t for t in g.tools if t.tool_id == "A")
        self.assertEqual(a.requirements_covered_elsewhere, ["R1"])
        self.assertEqual(a.unique_requirements, ["R2"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
