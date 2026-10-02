"""Shipping evidence is BL-grained, conservative and source preserving."""
import unittest

import pandas as pd

from gsi.report.shipping_insights import build_shipping_insights
from gsi.rulebook.loader import get_rulebook


class ShippingInsightTests(unittest.TestCase):
    def test_deduplicates_material_rows_without_hiding_expert_bl(self):
        a = {"CANONICAL_BL": "HDMU123456", "CANONICAL_ORDER": "823107D",
             "KEY_MATERIAL": "A", "کد طبقه بحرانی": "CRITICAL",
             "TRANSPORT_MODE": "SEA", "DISCHARGE_DATE": "1405/06/01",
             "DO_DATE": "1405/06/04", "COT_DATE": "1405/06/08"}
        b = {**a, "KEY_MATERIAL": "B", "کد طبقه بحرانی": "GOOD"}
        c = {"CANONICAL_BL": "HDMU777777", "CANONICAL_ORDER": "823122A",
             "KEY_MATERIAL": "C", "BL_SHIP_STATUS": "در راه"}
        dossiers, coverage = build_shipping_insights(pd.DataFrame([a, b, c,
                                      {"CANONICAL_BL": "", "CANONICAL_ORDER": "NO_BL"}]), "1405/06/10")
        self.assertEqual(len(dossiers), 2)
        first = dossiers.loc[dossiers["بارنامه"].eq("HDMU123456")].iloc[0]
        self.assertEqual(first["شمار ردیف منبع"], 2)
        self.assertEqual(first["اقلام بحرانی یکتا"], 1)
        self.assertEqual(first["تخلیه تا دریافت ترخیصیه (روز)"], 3)
        self.assertEqual(first["تخلیه تا کوتاژ (روز)"], 7)
        self.assertEqual(coverage.loc[coverage["شاهد"].eq("دریافت ترخیصیه"), "دارای شاهد"].iloc[0], 1)
        self.assertIn("دریافت شاهد ورود/تخلیه", dossiers.iloc[1]["اقدام پیشنهادی"])

    def test_conflicting_dates_do_not_pick_one(self):
        rows = pd.DataFrame([{"CANONICAL_BL": "HDMU123456", "DISCHARGE_DATE": d,
                              "DO_DATE": "2026-09-03", "TRANSPORT_MODE": "SEA"}
                             for d in ("2026-09-01", "2026-09-02")])
        dossiers, coverage = build_shipping_insights(rows, "2026-09-10")
        self.assertEqual(dossiers.iloc[0]["تخلیه"], "")
        self.assertTrue(pd.isna(dossiers.iloc[0]["تخلیه تا دریافت ترخیصیه (روز)"]))
        self.assertIn("تخلیه", dossiers.iloc[0]["مغایرت شواهد"])
        row = coverage.loc[coverage["شاهد"].eq("تخلیه")].iloc[0]
        self.assertEqual((row["دارای شاهد"], row["متعارض"]), (0, 1))

    def test_clearance_done_without_date_is_not_open_age(self):
        f = pd.DataFrame([{"CANONICAL_BL": "HDMU123456", "DISCHARGE_DATE": "2026-09-01",
                           "CL_CLEAR_DONE_NO_DATE": True}])
        d, _ = build_shipping_insights(f, "2026-09-20")
        self.assertTrue(pd.isna(d.iloc[0]["روز سپری‌شده پس از تخلیه (بدون ترخیص کامل)"]))
        self.assertIn("بدون تاریخ", d.iloc[0]["دادهٔ لازم"])

    def test_no_free_time_or_global_score_is_invented(self):
        d, _ = build_shipping_insights(pd.DataFrame([{"CANONICAL_BL": "HDMU123456",
                                  "DISCHARGE_DATE": "2026-09-01"}]), "2026-09-20")
        self.assertEqual(d.iloc[0]["روز سپری‌شده پس از تخلیه (بدون ترخیص کامل)"], 19)
        self.assertFalse(any("دموراژ" in c or "نمره" in c or "مقصر" in c for c in d.columns))
        self.assertIn("فری‌تایم قراردادی", d.iloc[0]["اقدام پیشنهادی"])
        rule = get_rulebook(reload=True).get("transport.operational_analysis")
        self.assertEqual(rule["evidence_grain"], "CANONICAL_BL")
        self.assertEqual(rule["iran_local_rule_status"], "needs_verification")


if __name__ == "__main__":
    unittest.main()
