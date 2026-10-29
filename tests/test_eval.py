"""Tests for the evaluation harness (step 9).

These exercise the scorer. The planted-case scoring needs the answer key; if it
is not present, that test skips (the messy-file check needs no key and always
runs). Standard library only.

Run with:  python -m unittest discover -s tests  (from the project root)
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

import evaluate  # noqa: E402


class TestMessyEval(unittest.TestCase):
    def test_all_seven_faults_surface(self):
        all_found, findings = evaluate.run_messy_eval()
        self.assertTrue(all_found, msg="\n".join(findings))
        # One blocking + six reported findings recorded.
        self.assertGreaterEqual(len(findings), 7)


class TestCaseEval(unittest.TestCase):
    def setUp(self):
        try:
            self.key_path = evaluate.find_answer_key(None)
        except FileNotFoundError:
            self.skipTest("answer key not available in this environment")

    def test_all_six_cases_correct(self):
        key = json.loads(self.key_path.read_text())
        results = evaluate.run_case_eval(key)
        self.assertEqual(len(results), 6)
        grades = [grade for *_, grade, _ in results]
        self.assertTrue(all(g == evaluate.CORRECT for g in grades),
                        msg=str(results))


if __name__ == "__main__":
    unittest.main(verbosity=2)
