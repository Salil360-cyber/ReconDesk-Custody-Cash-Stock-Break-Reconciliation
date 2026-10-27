"""
Ground-truth tests.

generate_data.py records every break it injects in injected_breaks.json.
These tests regenerate the data in a temp folder and check that the engine
finds every injected break, with the right break type and probable cause,
and raises nothing extra.

Run:  python -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import generate_data  # noqa: E402
import reconcile  # noqa: E402
from recon_engine import reconcile_cash  # noqa: E402


class GroundTruthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        data = os.path.join(cls.tmp.name, "data")
        out = os.path.join(cls.tmp.name, "reports")
        with redirect_stdout(StringIO()):
            generate_data.main(data)
            cls.cash, cls.stock, cls.breaks, cls.summary = reconcile.run(
                data, out, use_ai=False, quiet=True)
        with open(os.path.join(data, "injected_breaks.json")) as f:
            cls.truth = json.load(f)["expected"]
        cls.out = out

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_injected_break_is_found(self):
        found = {b["key"]: b for b in self.breaks}
        for t in self.truth:
            if t["status"] == "MATCHED_WITHIN_TOLERANCE":
                continue
            with self.subTest(key=t["key"]):
                self.assertIn(t["key"], found, "injected break was missed")
                self.assertEqual(found[t["key"]]["status"], t["status"])
                self.assertEqual(found[t["key"]]["probable_cause"], t["cause"])

    def test_no_false_breaks(self):
        expected = {t["key"] for t in self.truth if t["status"] != "MATCHED_WITHIN_TOLERANCE"}
        extra = {b["key"] for b in self.breaks} - expected
        self.assertEqual(extra, set(), "engine raised breaks that were never injected")

    def test_rounding_is_not_a_break(self):
        rounding = {t["key"] for t in self.truth if t["status"] == "MATCHED_WITHIN_TOLERANCE"}
        statuses = {r["key"]: r["status"] for r in self.cash}
        for k in rounding:
            self.assertEqual(statuses[k], "MATCHED_WITHIN_TOLERANCE")

    def test_reports_written(self):
        files = os.listdir(self.out)
        self.assertTrue(any(f.endswith(".xlsx") for f in files))
        self.assertTrue(any(f.endswith(".csv") for f in files))


class RuleTests(unittest.TestCase):
    """Small hand-made cases for individual rules."""

    def row(self, ref, amt, d="2026-10-20", t="TRADE_SETTLEMENT"):
        return {"ref_id": ref, "account_id": "ACC-1", "value_date": d,
                "txn_type": t, "currency": "INR", "amount": str(amt)}

    def test_v1_bug_small_fee_is_now_a_break(self):
        # v1 used a 3% tolerance, so a 1% shortfall was reported as matched.
        res = reconcile_cash([self.row("A", 100000)], [self.row("A", 99000)])
        self.assertEqual(res[0]["status"], "AMOUNT_DIFF")

    def test_v1_bug_one_day_delay_is_now_a_break(self):
        res = reconcile_cash([self.row("A", 500)], [self.row("A", 500, d="2026-10-21")])
        self.assertEqual(res[0]["status"], "TIMING_DIFF")

    def test_duplicate_on_custodian_side(self):
        res = reconcile_cash([self.row("A", 500)], [self.row("A", 500), self.row("A", 500)])
        self.assertEqual(res[0]["status"], "DUPLICATE_AT_CUSTODIAN")

    def test_withholding_tax_detected(self):
        res = reconcile_cash([self.row("D", 10000, t="DIVIDEND")], [self.row("D", 9000, t="DIVIDEND")])
        self.assertEqual(res[0]["probable_cause"], "WITHHOLDING_TAX")


if __name__ == "__main__":
    unittest.main()
