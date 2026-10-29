"""Unit tests for step 1: read_inventory / read_requirements validation.

Run with:  python -m unittest discover -s tests  (from the project root)
These tests use only the standard library (no pytest needed).
"""
import datetime as _dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from portfolio_agent.validate import (  # noqa: E402
    BlockingValidationError,
    read_inventory,
    read_requirements,
)

DATA = ROOT / "data"


class TestReadInventoryClean(unittest.TestCase):
    def setUp(self):
        self.result = read_inventory(DATA / "inventory.csv")

    def test_only_expected_advisory_on_clean_file(self):
        # The clean file is valid except for one by-design advisory: InsightBox
        # (T019) is the planted "orphan" with no owner and 0 users. A missing
        # owner is correctly *flagged* (steering rule: flag, do not guess), so
        # exactly one issue is expected and it must be that one.
        self.assertEqual(len(self.result.issues), 1,
                         msg=str([str(i) for i in self.result.issues]))
        only = self.result.issues[0]
        self.assertEqual(only.row_id, "T019")
        self.assertEqual(only.field, "owner")

    def test_all_36_rows_loaded(self):
        self.assertEqual(len(self.result.rows), 36)

    def test_types_coerced(self):
        t1 = self.result.rows[0]
        self.assertEqual(t1.tool_id, "T001")
        self.assertEqual(t1.annual_cost_gbp, 180000)
        self.assertEqual(t1.utilisation_pct, 22)
        self.assertEqual(t1.contract_end, _dt.date(2027, 2, 26))
        self.assertIsInstance(t1.annual_cost_gbp, int)

    def test_requirement_ids_split(self):
        # StateKeeper maps to "R003;R012"
        state = next(t for t in self.result.rows if t.name == "StateKeeper")
        self.assertEqual(state.requirement_ids, ["R003", "R012"])

    def test_empty_requirement_ids(self):
        spare = next(t for t in self.result.rows if t.name == "SpareTrack")
        self.assertEqual(spare.requirement_ids, [])


class TestReadRequirementsClean(unittest.TestCase):
    def setUp(self):
        self.result = read_requirements(DATA / "requirements.csv")

    def test_no_issues(self):
        self.assertEqual(self.result.issues, [], msg=str([str(i) for i in self.result.issues]))

    def test_14_requirements(self):
        self.assertEqual(len(self.result.rows), 14)

    def test_priorities(self):
        r001 = next(r for r in self.result.rows if r.requirement_id == "R001")
        self.assertEqual(r001.priority, "Must")


class TestMessyFile(unittest.TestCase):
    """The messy file has 7 planted faults. One (duplicate tool_id) is blocking.

    We verify the blocking behaviour, then verify the other six are all reported
    once the blocking row is removed.
    """

    def test_duplicate_id_is_blocking(self):
        with self.assertRaises(BlockingValidationError) as ctx:
            read_inventory(DATA / "inventory_messy.csv")
        self.assertIn("duplicate tool_id", str(ctx.exception).lower())

    def test_remaining_six_faults_reported(self):
        # Build a copy of the messy file with the duplicate row de-duplicated so
        # the read proceeds and surfaces the other six faults as issues.
        import csv
        import tempfile

        src = DATA / "inventory_messy.csv"
        with open(src, newline="") as f:
            rows = list(csv.reader(f))
        header, body = rows[0], rows[1:]

        # The planted duplicate is T005's id set to T004. Restore T005's id so
        # the primary-key check passes and the row-level faults are reported.
        seen = set()
        for r in body:
            tid = r[0]
            if tid in seen:
                r[0] = "T005R"  # make unique without touching other fields
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

        fields = {(i.field, i.message) for i in result.issues}
        joined = "\n".join(str(i) for i in result.issues)

        # Fault 2: T010 missing annual_cost_gbp
        self.assertTrue(any(i.field == "annual_cost_gbp" and "missing" in i.message
                            for i in result.issues), joined)
        # Fault 3: T014 invalid contract_end '31/04/2027'
        self.assertTrue(any(i.field == "contract_end" and "invalid" in i.message
                            for i in result.issues), joined)
        # Fault 4: T017 utilisation 140 out of range
        self.assertTrue(any(i.field == "utilisation_pct" and "out of range" in i.message
                            for i in result.issues), joined)
        # Fault 5: T021 evidence_level not allowed
        self.assertTrue(any(i.field == "evidence_level" and "not allowed" in i.message
                            for i in result.issues), joined)
        # Fault 6: T025 missing owner (distinct from the by-design T019 orphan)
        self.assertTrue(any(i.row_id == "T025" and i.field == "owner"
                            for i in result.issues), joined)
        # Fault 7: T031 capability not in taxonomy
        self.assertTrue(any(i.field == "capability" and "not in taxonomy" in i.message
                            for i in result.issues), joined)

        # The messy file carries the 6 remaining planted row-faults (the 7th,
        # the duplicate tool_id, is blocking and tested separately) PLUS the
        # by-design T019 orphan missing-owner advisory inherited from the base
        # estate = 7 reported issues in total.
        self.assertEqual(len(result.issues), 7,
                         msg=f"expected 7 reported issues, got {len(result.issues)}:\n{joined}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
