# -*- coding: utf-8 -*-
"""Regression: two descriptions and incomplete expert rows stay in reporting."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
import pandas as pd

from gsi.adapters.moghavemat import MoghavematAdapter
from gsi.report.expert_material import build_expert_material_positions
from gsi.report.supply_views import build_material_view
from gsi.report.dashboard import ExcelDashboardBuilder, SHEET_LINES


class ExpertMaterialTests(unittest.TestCase):
    def test_missing_pi_amount_does_not_become_zero(self):
        raw = pd.DataFrame([
            {"Order No. (Our Reference)": "O1", "Material": "A1",
             "Material Description": "قطعه", "Currency": "EUR", "PI Line Value": None},
            {"Order No. (Our Reference)": "O1", "Material": "A1",
             "Material Description": "قطعه", "Currency": "EUR", "PI Line Value": 0},
        ])
        frames = MoghavematAdapter().transform({"Expert Data": raw})
        self.assertTrue(pd.isna(frames["lines"].iloc[0]["MOGH_PI_LINE_VALUE"]))
        self.assertEqual(frames["lines"].iloc[1]["MOGH_PI_LINE_VALUE"], 0)
        self.assertTrue(pd.isna(frames["main"].iloc[0]["MOGH_PI_VALUE_SUM"]))

    def test_same_code_across_orders_keeps_both_names_in_material_report(self):
        frame = pd.DataFrame([
            {"KEY_MATERIAL": "9654003280", "MOGH_MATERIAL": "9654003280",
             "MOGH_MATERIAL_DESC": "رينگ ضدقفل", "MOGH_MATERIAL_DESCS_ALL": "رينگ ضدقفل",
             "MOGH_KEY_MATERIAL_COUNT": 1, "CANONICAL_ORDER": "823107D"},
            {"KEY_MATERIAL": "9654003280", "MOGH_MATERIAL": "9654003280",
             "MOGH_MATERIAL_DESC": "هدف چرخشي ترمز", "MOGH_MATERIAL_DESCS_ALL": "هدف چرخشي ترمز",
             "MOGH_KEY_MATERIAL_COUNT": 1, "CANONICAL_ORDER": "843115"},
        ])
        view = build_material_view(frame)
        self.assertEqual(len(view), 2)
        for value in view["شرح‌های ثبت‌شده کارشناسان"]:
            self.assertIn("رينگ ضدقفل", value)
            self.assertIn("هدف چرخشي ترمز", value)
        self.assertTrue(view["اختلاف شرح متریال"].str.contains("چند شرح").all())

    def test_material_without_order_remains_unlinked_evidence(self):
        lines = pd.DataFrame([{"KEY_ORDER": "", "KEY_MATERIAL": "A1",
                               "MOGH_MATERIAL_DESC": "قطعه A"}])
        result = build_expert_material_positions(lines, None, None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["KEY_ORDER"], "")
        self.assertEqual(result.iloc[0]["SUPPLY_POSITION_STATUS"], "MISSING")

    def test_incomplete_same_code_two_descriptions_and_second_material(self):
        raw = pd.DataFrame([
            (57, "823107D", "9654003280", "رينگ ضدقفل مغناطيسي", 10, 2, 1),
            (58, "823107D", "9654003280", "هدف چرخشي ترمز ضدقفل", 10, 2, 1),
            (59, "823107D", "B-2", "قطعه دیگر", 4, 1, 0),
        ], columns=["Row No.", "Order No. (Our Reference)", "Material",
                    "Material Description", "Quantity In Order", "Quantity In Part",
                    "Customs Cleared Quantity"])
        transformed = MoghavematAdapter().transform({"Expert Data": raw})
        main, lines = transformed["main"], transformed["lines"]
        self.assertEqual(len(main), 1)
        self.assertEqual(len(lines), 3)
        self.assertEqual(main.iloc[0]["MOGH_MATERIAL_DESC_COUNT"], 3)
        self.assertIn("هدف چرخشي ترمز ضدقفل", main.iloc[0]["MOGH_MATERIAL_DESCS_ALL"])
        oracle = pd.DataFrame([
            {"KEY_MATERIAL": "9654003280", "ORC_STOCK_IKCO": 5,
             "ORC_STOCK_SAPCO": 0, "ORC_DAILY_NEED": 2},
            {"KEY_MATERIAL": "B2", "ORC_STOCK_IKCO": 7,
             "ORC_STOCK_SAPCO": 0, "ORC_DAILY_NEED": 1},
        ])
        positions = build_expert_material_positions(lines, transformed["inventory"], oracle)
        self.assertEqual(len(positions), 2)
        a = positions.set_index("KEY_MATERIAL").loc["9654003280"]
        b = positions.set_index("KEY_MATERIAL").loc["B2"]
        self.assertEqual(a["MOGH_MATERIAL_DESC_COUNT"], 2)
        self.assertEqual(a["EXPERT_SOURCE_ROWS"], 2)
        self.assertIn("شماره درخواست خرید", a["EXPERT_RECORD_GAPS"])
        self.assertIn("ارزش PI", a["EXPERT_RECORD_GAPS"])
        self.assertEqual(a["SUPPLY_POSITION_STATUS"], "PARTIAL")
        self.assertEqual(a["SUPPLY_TOTAL_LOWER_BOUND"], 13.0)
        self.assertTrue(pd.isna(a["SUPPLY_TOTAL_CONFIRMED"]))
        self.assertEqual(b["SUPPLY_TOTAL_LOWER_BOUND"], 10.0)
        self.assertNotIn("قطعه دیگر", a["MOGH_MATERIAL_DESCS_ALL"])

        display = main.copy()
        display["KEY_MATERIAL"] = "9654003280"
        view = build_material_view(display)
        # Multi-material order descriptions cannot be attributed to the first material.
        self.assertEqual(view.iloc[0]["شرح‌های ثبت‌شده کارشناسان"], "")
        single = main.copy()
        single["MOGH_KEY_MATERIAL_COUNT"] = 1
        single["MOGH_MATERIAL_DESCS_ALL"] = a["MOGH_MATERIAL_DESCS_ALL"]
        single["KEY_MATERIAL"] = "9654003280"
        view = build_material_view(single)
        self.assertIn("هدف چرخشي", view.iloc[0]["شرح‌های ثبت‌شده کارشناسان"])

        builder = ExcelDashboardBuilder(str(Path("/tmp") / "unused_expert_material.xlsx"))
        builder.build_order_lines(lines, positions)
        ws = builder.wb[SHEET_LINES]
        self.assertEqual(ws.max_row >= 4, True)
        self.assertIn("هدف چرخشي", str(ws.cell(2, 30).value))
        self.assertEqual(ws.cell(2, 34).value, 13.0)


if __name__ == "__main__":
    unittest.main()
