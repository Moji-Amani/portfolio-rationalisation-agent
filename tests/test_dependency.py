"""Unit tests for step 4: dependency_check.

Run with:  python -m unittest discover -s tests  (from the project root)
Standard library only.
"""
import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from portfolio_agent.dependency import dependency_check  # noqa: E402
from portfolio_agent.validate import read_inventory, read_requirements  # noqa: E402

DATA = ROOT / "data"


@dataclass
class FakeTool:
    tool_id: str
    name: str
    evidence_level: str
    requirement_ids: list = field(default_factory=list)


@dataclass
class FakeReq:
    requirement_id: str
    priority: str


class TestDependencyCheckRealData(unittest.TestCase):
    def setUp(self):
        self.inv = read_inventory(DATA / "inventory.csv").rows
        self.reqs = read_requirements(DATA / "requirements.csv").rows

    def test_unknown_tool_not_found(self):
        r = dependency_check("T999", self.inv, self.reqs)
        self.assertFalse(r.found)
        self.assertEqual(r.dependencies, [])

    def test_backup_array_must_dependency_covered_elsewhere(self):
        # T033 EdgeStore Array covers Must R003; StateKeeper (T015) also covers it.
        r = dependency_check("T033", self.inv, self.reqs)
        self.assertTrue(r.found)
        dep = next(d for d in r.dependencies if d.requirement_id == "R003")
        self.assertEqual(dep.priority, "Must")
        self.assertTrue(dep.covers)
        self.assertTrue(dep.covered_elsewhere)
        self.assertIn("T015", dep.other_covering_tools)
        # It is a Must dependency, but not a *blocking* one (fallback exists).
        self.assertTrue(r.must_dependencies)
        self.assertEqual(r.blocking_dependencies, [])

    def test_claimed_only_does_not_cover(self):
        # T013 FlowMesh links R007 but evidence is 'claimed only' -> no coverage.
        r = dependency_check("T013", self.inv, self.reqs)
        dep = next(d for d in r.dependencies if d.requirement_id == "R007")
        self.assertEqual(dep.priority, "Must")
        self.assertFalse(dep.covers)
        self.assertIn("claimed only", dep.note)
        # R007's genuine coverage is ServiceWeave (T012) only.
        self.assertEqual(dep.other_covering_tools, ["T012"])

    def test_priority_attached_from_requirements(self):
        r = dependency_check("T028", self.inv, self.reqs)  # Sentinel Vault PAM
        dep = next(d for d in r.dependencies if d.requirement_id == "R008")
        self.assertEqual(dep.priority, "Must")

    def test_priority_none_when_requirements_omitted(self):
        r = dependency_check("T033", self.inv)  # no requirements passed
        dep = next(d for d in r.dependencies if d.requirement_id == "R003")
        self.assertIsNone(dep.priority)


class TestDependencyCheckUnit(unittest.TestCase):
    def test_blocking_when_must_only_covered_by_this_tool(self):
        inv = [
            FakeTool("A", "Alpha", "tested", ["R1"]),
            FakeTool("B", "Beta", "tested", ["R2"]),
        ]
        reqs = [FakeReq("R1", "Must"), FakeReq("R2", "Should")]
        r = dependency_check("A", inv, reqs)
        dep = r.dependencies[0]
        self.assertTrue(dep.covers)
        self.assertFalse(dep.covered_elsewhere)
        self.assertEqual([d.requirement_id for d in r.blocking_dependencies], ["R1"])

    def test_claimed_only_peer_does_not_provide_coverage(self):
        # A genuinely covers R1; B links R1 but only 'claimed only'.
        inv = [
            FakeTool("A", "Alpha", "tested", ["R1"]),
            FakeTool("B", "Beta", "claimed only", ["R1"]),
        ]
        reqs = [FakeReq("R1", "Must")]
        # Retiring A: is R1 covered elsewhere? B is claimed-only, so NO.
        r = dependency_check("A", inv, reqs)
        dep = r.dependencies[0]
        self.assertTrue(dep.covers)
        self.assertFalse(dep.covered_elsewhere)  # B's claimed-only link ignored
        self.assertEqual(dep.other_covering_tools, [])
        self.assertEqual([d.requirement_id for d in r.blocking_dependencies], ["R1"])

    def test_claimed_only_tool_itself_covers_nothing(self):
        inv = [
            FakeTool("A", "Alpha", "claimed only", ["R1"]),
            FakeTool("B", "Beta", "tested", ["R1"]),
        ]
        reqs = [FakeReq("R1", "Must")]
        r = dependency_check("A", inv, reqs)
        dep = r.dependencies[0]
        self.assertFalse(dep.covers)
        self.assertTrue(dep.covered_elsewhere)
        self.assertEqual(dep.other_covering_tools, ["B"])
        # Not blocking: A does not actually cover R1.
        self.assertEqual(r.blocking_dependencies, [])

    def test_tool_with_no_requirements(self):
        inv = [FakeTool("A", "Alpha", "tested", [])]
        r = dependency_check("A", inv, [])
        self.assertTrue(r.found)
        self.assertEqual(r.dependencies, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
