"""Unit tests for step 6: recommend keep / merge / retire.

Run with:  python -m unittest discover -s tests  (from the project root)
Standard library only.
"""
import datetime as _dt
import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from portfolio_agent.recommend import (  # noqa: E402
    DO_NOT_RENEW,
    KEEP,
    MERGE,
    NEEDS_REVIEW,
    ONE_WAY,
    PROCURE,
    TWO_WAY,
    recommend,
)
from portfolio_agent.validate import read_inventory, read_requirements  # noqa: E402

DATA = ROOT / "data"
REF = _dt.date(2026, 10, 27)


@dataclass
class FakeTool:
    tool_id: str
    name: str
    capability: str = "cap/x"
    type: str = "software"
    cost_type: str = "opex"
    annual_cost_gbp: int | None = 50000
    contract_end: _dt.date | None = _dt.date(2028, 1, 1)
    licence_qty: int | None = 100
    active_users: int | None = 50
    utilisation_pct: int | None = 70
    owner: str = "Some Lead"
    requirement_ids: list = field(default_factory=list)
    evidence_level: str = "tested"


@dataclass
class FakeReq:
    requirement_id: str
    priority: str


class TestPlantedCases(unittest.TestCase):
    """The six planted cases on the clean inventory."""

    @classmethod
    def setUpClass(cls):
        inv = read_inventory(DATA / "inventory.csv").rows
        reqs = read_requirements(DATA / "requirements.csv").rows
        cls.recs = {r.tool_id: r for r in recommend(inv, reqs, reference_date=REF)}

    def test_case1_overlap_merge(self):
        r = self.recs["T001"]
        self.assertEqual(r.decision, MERGE)
        self.assertEqual(r.door_type, TWO_WAY)
        self.assertIn("T002", r.cited_tool_ids)
        self.assertEqual((r.savings.low, r.savings.base, r.savings.high),
                         (23000, 94000, 146000))

    def test_case1_survivor_kept(self):
        self.assertEqual(self.recs["T002"].decision, KEEP)

    def test_case2_renewal_do_not_renew(self):
        r = self.recs["T026"]
        self.assertEqual(r.decision, DO_NOT_RENEW)
        self.assertEqual(r.door_type, TWO_WAY)
        self.assertIn("T023", r.cited_tool_ids)  # ResolveDesk still covers R004

    def test_case3_dependency_keep_and_flag_oneway(self):
        r = self.recs["T033"]
        self.assertEqual(r.decision, KEEP)
        self.assertIn("R003", r.cited_requirement_ids)
        self.assertTrue(any("One-Way" in f for f in r.flags))

    def test_case4_orphan_needs_review(self):
        r = self.recs["T019"]
        self.assertEqual(r.decision, NEEDS_REVIEW)
        self.assertTrue(any("owner" in f.lower() for f in r.flags))

    def test_case5_claimed_only_not_counted(self):
        r = self.recs["T013"]
        self.assertTrue(any("claimed only" in f.lower() for f in r.flags))
        self.assertTrue(any("R007" in f for f in r.flags))
        # Must not assert genuine support for R007.
        self.assertFalse(any("Supports Must requirement(s) R007" in s
                             for s in r.reasoning))

    def test_case6_under_provisioned_procure(self):
        r = self.recs["T028"]
        self.assertEqual(r.decision, PROCURE)
        self.assertEqual((r.savings.low, r.savings.base, r.savings.high),
                         (12000, 15000, 16500))
        self.assertIn("R008", r.cited_requirement_ids)

    def test_every_rec_cites_rows_and_has_confidence(self):
        for r in self.recs.values():
            self.assertTrue(r.cited_tool_ids)          # always cites itself at least
            self.assertIn(r.confidence, ("high", "medium", "low"))
            self.assertIn(r.door_type, (TWO_WAY, ONE_WAY))
            self.assertTrue(r.reasoning or r.flags)


class TestGuardrails(unittest.TestCase):
    def test_blocking_must_dependency_forces_keep(self):
        # A sole tool covering a Must requirement must never be retired, even at
        # low utilisation.
        tools = [FakeTool("A", "Alpha", utilisation_pct=5, requirement_ids=["R1"])]
        reqs = [FakeReq("R1", "Must")]
        r = recommend(tools, reqs, reference_date=REF)[0]
        self.assertEqual(r.decision, KEEP)
        self.assertTrue(any("do not retire" in f.lower() for f in r.flags))

    def test_hardware_removal_is_one_way_flag(self):
        tools = [FakeTool("H", "Hardbox", type="hardware", cost_type="capex",
                          utilisation_pct=50, requirement_ids=[])]
        r = recommend(tools, [], reference_date=REF)[0]
        self.assertTrue(any("One-Way" in f for f in r.flags))

    def test_orphan_no_owner(self):
        tools = [FakeTool("O", "Orphan", owner="", active_users=0, utilisation_pct=0)]
        r = recommend(tools, [], reference_date=REF)[0]
        self.assertEqual(r.decision, NEEDS_REVIEW)

    def test_renewal_only_when_low_util_and_soon(self):
        # Contract ends soon but utilisation is high -> not a non-renewal.
        soon = REF + _dt.timedelta(days=30)
        tools = [FakeTool("K", "Keeper", contract_end=soon, utilisation_pct=85,
                          requirement_ids=[])]
        r = recommend(tools, [], reference_date=REF)[0]
        self.assertEqual(r.decision, KEEP)

    def test_procure_when_users_exceed_licences(self):
        tools = [FakeTool("P", "Provision", licence_qty=100, active_users=130,
                          annual_cost_gbp=100000, utilisation_pct=95)]
        r = recommend(tools, [], reference_date=REF)[0]
        self.assertEqual(r.decision, PROCURE)
        self.assertIsNotNone(r.savings)

    def test_missing_utilisation_lowers_confidence(self):
        tools = [FakeTool("U", "Unknown", utilisation_pct=None, requirement_ids=[])]
        r = recommend(tools, [], reference_date=REF)[0]
        self.assertEqual(r.decision, KEEP)
        self.assertEqual(r.confidence, "low")


if __name__ == "__main__":
    unittest.main(verbosity=2)
