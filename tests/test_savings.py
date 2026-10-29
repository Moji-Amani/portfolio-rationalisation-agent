"""Unit tests for step 5: savings_range (the only place numbers are computed).

Run with:  python -m unittest discover -s tests  (from the project root)
Standard library only.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from portfolio_agent.savings import (  # noqa: E402
    Range,
    RetireAssumptions,
    ShortfallAssumptions,
    licence_shortfall_cost,
    retire_saving,
    savings_range,
)


class TestRetireSaving(unittest.TestCase):
    def test_reference_case_t001(self):
        # PulseWatch £180k with default assumptions -> 23k / 94k / 146k.
        r = retire_saving(180000)
        self.assertEqual((r.low, r.base, r.high), (23000, 94000, 146000))

    def test_low_is_most_conservative(self):
        r = retire_saving(180000)
        self.assertLess(r.low, r.base)
        self.assertLess(r.base, r.high)

    def test_assumptions_pairing_low_uses_worst_case(self):
        # Manually: low = 0.60*cost - 50000 - 35000.
        cost = 100000
        r = retire_saving(cost)
        self.assertEqual(r.low, round(0.60 * cost - 50000 - 35000))
        self.assertEqual(r.high, round(0.95 * cost - 15000 - 10000))

    def test_custom_assumptions(self):
        a = RetireAssumptions(
            recoverable_share=(0.5, 0.7, 0.9),
            migration_cost=(10000, 5000, 1000),
            surviving_uplift=(0, 0, 0),
        )
        r = retire_saving(100000, a)
        self.assertEqual(r.low, round(0.5 * 100000 - 10000 - 0))
        self.assertEqual(r.base, round(0.7 * 100000 - 5000 - 0))
        self.assertEqual(r.high, round(0.9 * 100000 - 1000 - 0))

    def test_assumptions_string_present(self):
        r = retire_saving(180000)
        self.assertIn("recoverable", r.assumptions)
        self.assertIn("migration", r.assumptions)


class TestLicenceShortfall(unittest.TestCase):
    def test_reference_case_t028(self):
        # PAM: 50k cost, 200 owned, 260 active -> 12k / 15k / 16.5k.
        r = licence_shortfall_cost(50000, 200, 260)
        self.assertEqual((r.low, r.base, r.high), (12000, 15000, 16500))

    def test_no_shortfall_returns_zero(self):
        r = licence_shortfall_cost(50000, 300, 260)
        self.assertEqual((r.low, r.base, r.high), (0, 0, 0))
        self.assertIn("no shortfall", r.assumptions)

    def test_exact_fit_returns_zero(self):
        r = licence_shortfall_cost(50000, 260, 260)
        self.assertEqual((r.low, r.base, r.high), (0, 0, 0))

    def test_unit_price_override(self):
        # gap 10, unit price forced to 100 -> base 1000.
        a = ShortfallAssumptions(unit_price=100, volume_discount=0.0, mid_term_premium=0.0)
        r = licence_shortfall_cost(99999, 100, 110, a)
        self.assertEqual(r.base, 1000)
        self.assertEqual(r.low, 1000)
        self.assertEqual(r.high, 1000)

    def test_zero_licences_without_unit_price_raises(self):
        with self.assertRaises(ValueError):
            licence_shortfall_cost(50000, 0, 10)

    def test_discount_and_premium_applied(self):
        r = licence_shortfall_cost(50000, 200, 260)  # base 15000
        self.assertEqual(r.low, round(15000 * 0.80))
        self.assertEqual(r.high, round(15000 * 1.10))


class TestSavingsRangeDispatch(unittest.TestCase):
    def test_dispatch_mixed_rows(self):
        rows = [
            {"kind": "retire_saving", "tool_id": "T001", "annual_cost": 180000},
            {"kind": "licence_shortfall", "tool_id": "T028",
             "annual_cost": 50000, "licence_qty": 200, "active_users": 260},
        ]
        results = savings_range(rows)
        self.assertEqual(len(results), 2)
        by_id = {r.tool_id: r for r in results}
        self.assertEqual(
            (by_id["T001"].amount.low, by_id["T001"].amount.base, by_id["T001"].amount.high),
            (23000, 94000, 146000))
        self.assertEqual(
            (by_id["T028"].amount.low, by_id["T028"].amount.base, by_id["T028"].amount.high),
            (12000, 15000, 16500))

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            savings_range([{"kind": "wishful_thinking", "tool_id": "X"}])

    def test_inputs_preserved_for_audit(self):
        rows = [{"kind": "retire_saving", "tool_id": "T001", "annual_cost": 180000}]
        result = savings_range(rows)[0]
        self.assertEqual(result.inputs["annual_cost"], 180000)
        self.assertEqual(result.kind, "retire_saving")


if __name__ == "__main__":
    unittest.main(verbosity=2)
