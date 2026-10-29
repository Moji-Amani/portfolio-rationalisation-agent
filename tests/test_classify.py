"""Unit tests for step 2: classification against the taxonomy.

Run with:  python -m unittest discover -s tests  (from the project root)
Standard library only.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from portfolio_agent.classify import (  # noqa: E402
    CONFIDENCE_DOMAIN_ONLY,
    CONFIDENCE_EXACT,
    CONFIDENCE_UNKNOWN,
    classify_capability,
    classify_tools,
    load_taxonomy,
    low_confidence,
)
from portfolio_agent.validate import read_inventory  # noqa: E402

DATA = ROOT / "data"


class TestClassifyCapability(unittest.TestCase):
    def setUp(self):
        self.tax = load_taxonomy(DATA / "taxonomy.csv")

    def test_taxonomy_loaded(self):
        # 35 capabilities across 7 domains in the generated taxonomy.
        self.assertEqual(len(self.tax), 35)
        self.assertEqual(self.tax["monitoring/network-performance"], "monitoring")

    def test_exact_match(self):
        domain, conf, note = classify_capability("security/privileged-access", self.tax)
        self.assertEqual(domain, "security")
        self.assertEqual(conf, CONFIDENCE_EXACT)
        self.assertEqual(note, "")

    def test_domain_only_match(self):
        # 'security/firewall' is the messy-file fault: known domain, unknown leaf.
        domain, conf, note = classify_capability("security/firewall", self.tax)
        self.assertEqual(domain, "security")
        self.assertEqual(conf, CONFIDENCE_DOMAIN_ONLY)
        self.assertIn("firewall", note)

    def test_unknown_match(self):
        domain, conf, note = classify_capability("spaceships/warp-core", self.tax)
        self.assertIsNone(domain)
        self.assertEqual(conf, CONFIDENCE_UNKNOWN)

    def test_empty_capability_is_unknown(self):
        domain, conf, _ = classify_capability("", self.tax)
        self.assertIsNone(domain)
        self.assertEqual(conf, CONFIDENCE_UNKNOWN)


class TestClassifyTools(unittest.TestCase):
    def setUp(self):
        self.tax = load_taxonomy(DATA / "taxonomy.csv")
        self.tools = read_inventory(DATA / "inventory.csv").rows

    def test_clean_inventory_all_exact(self):
        classifications = classify_tools(self.tools, self.tax)
        self.assertEqual(len(classifications), 36)
        # Every capability in the clean file is a taxonomy member -> all exact.
        self.assertEqual(low_confidence(classifications), [])
        self.assertTrue(all(c.confidence == CONFIDENCE_EXACT for c in classifications))
        self.assertFalse(any(c.needs_review for c in classifications))

    def test_domain_matches_taxonomy(self):
        classifications = {c.tool_id: c for c in classify_tools(self.tools, self.tax)}
        # T001 PulseWatch -> monitoring/network-performance -> monitoring domain.
        self.assertEqual(classifications["T001"].domain, "monitoring")
        # T033 EdgeStore Array -> backup/storage-array -> backup domain.
        self.assertEqual(classifications["T033"].domain, "backup")

    def test_flags_low_confidence_mapping(self):
        # Simulate a tool whose capability is not an exact taxonomy member.
        from dataclasses import replace
        tools = list(self.tools)
        tools[0] = replace(tools[0], capability="security/firewall")
        classifications = classify_tools(tools, self.tax)
        flagged = low_confidence(classifications)
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0].tool_id, "T001")
        self.assertEqual(flagged[0].confidence, CONFIDENCE_DOMAIN_ONLY)
        self.assertTrue(flagged[0].needs_review)


if __name__ == "__main__":
    unittest.main(verbosity=2)
