# -*- coding: utf-8 -*-
"""رگرسیون V28.1 — اوراکل نباید شیت‌ها را دور بریزد.

دو شیت تولیدی اوراکل، دو بخش مجزا از دنیای قطعه‌اند نه دو روایت از یک داده:
روی فایل واقعی «هیچ» شماره فنی مشترکی ندارند. سیاست قبلی «یک شیت را انتخاب کن»
هر قطعه‌ای را که فقط در شیت بازنده بود حذف می‌کرد — روی ورودی واقعی ۳ قطعه از ۴.
"""
from __future__ import annotations
import os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from gsi.adapters.base import KEY_MATERIAL
from gsi.adapters.a40_oracle import OracleAdapter


def sheet(rows, **extra):
    df = pd.DataFrame(rows)
    for k, v in extra.items():
        df[k] = v
    df["_SOURCE_ROW"] = range(2, 2 + len(df))
    df["_SOURCE_FILE_ID"] = "fid"
    return df


class OracleUnionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.keep = os.environ.get("GSI_DWH_PATH")
        os.environ["GSI_DWH_PATH"] = str(Path(self.tmp.name) / "wh.sqlite")

    def tearDown(self):
        if self.keep is None:
            os.environ.pop("GSI_DWH_PATH", None)
        else:
            os.environ["GSI_DWH_PATH"] = self.keep
        self.tmp.cleanup()

    def disjoint(self):
        a = sheet([{"شماره فني": "IK60018480", "شرح جنس": "ميل بادامك",
                    "موجودي انبار ايران خودرو": 5882, "موجودي انبار ساپکو": 0,
                    "نياز روزانه قطعات": 230}])
        b = sheet([{"شماره فني": "YG20237585", "شرح قطعه": "تراشه ايموبيلايزر",
                    "میانگین نیاز روزانه (عدد)": 3440},
                   {"شماره فني": "K914564038A", "شرح قطعه": "سوپاپ دود",
                    "میانگین نیاز روزانه (عدد)": 2160}])
        return {"1": a, "SAPCO_IK": b}

    def test_no_part_is_dropped_when_sheets_are_disjoint(self):
        out = OracleAdapter().transform(self.disjoint())["main"]
        self.assertEqual(len(out), 3, "هر سه قطعه باید بمانند")
        self.assertEqual(set(out[KEY_MATERIAL]),
                         {"IK60018480", "YG20237585", "K914564038A"})

    def test_source_sheet_is_recorded_for_every_row(self):
        out = OracleAdapter().transform(self.disjoint())["main"]
        self.assertEqual(set(out["ORC_SOURCE_SHEET"]), {"1", "SAPCO_IK"})

    def test_excluded_headers_never_reach_the_output(self):
        s = self.disjoint()
        s["1"]["وضعيت"] = "فعال"
        s["1"]["قطعه بحراني"] = "بله"
        s["1"]["شماره پرسنلي"] = "12345"
        s["SAPCO_IK"]["ریسک پذیری"] = "بالا"
        s["SAPCO_IK"]["Column18"] = "x"
        out = OracleAdapter().transform(s)["main"]
        banned = {"وضعیت", "قطعه بحرانی", "شماره پرسنلی", "ریسک پذیری", "column18"}
        leaked = [c for c in out.columns if str(c).strip().lower() in banned]
        self.assertFalse(leaked, f"ستون ممنوعه نشت کرد: {leaked}")
        flat = out.astype(str).values.ravel().tolist()
        self.assertNotIn("فعال", flat)
        self.assertNotIn("بالا", flat)

    def test_missing_quantity_stays_missing_not_zero(self):
        out = OracleAdapter().transform(self.disjoint())["main"]
        sapco = out[out[KEY_MATERIAL] == "YG20237585"].iloc[0]
        for field in ("ORC_STOCK_IKCO", "ORC_STOCK_SAPCO"):
            self.assertTrue(pd.isna(sapco[field]),
                            f"{field} باید نامعلوم بماند، نه صفر")
        real_zero = out[out[KEY_MATERIAL] == "IK60018480"].iloc[0]
        self.assertEqual(real_zero["ORC_STOCK_SAPCO"], 0.0,
                         "صفر واقعی باید صفر بماند")

    def test_overlapping_part_uses_one_sheet_only_no_hybrid(self):
        a = sheet([{"شماره فني": "P1", "شرح جنس": "شرح از شیت یک",
                    "موجودي انبار ايران خودرو": 10, "موجودي انبار ساپکو": 2,
                    "نياز روزانه قطعات": 5}])
        b = sheet([{"شماره فني": "P1", "شرح قطعه": None,
                    "گروه تامين": "گروه از شیت دو",
                    "میانگین نیاز روزانه (عدد)": 5}])
        out = OracleAdapter().transform({"1": a, "SAPCO_IK": b})["main"]
        self.assertEqual(len(out), 1, "قطعه مشترک نباید تکثیر شود")
        row = out.iloc[0]
        self.assertEqual(row["ORC_SOURCE_SHEET"], "1")
        self.assertEqual(row["ORC_MATERIAL_DESC"], "شرح از شیت یک")
        self.assertTrue(pd.isna(row["ORC_SUPPLY_GROUP"]),
                        "نباید فیلد خالی از شیت دیگر پر شود و رکورد هیبرید ساخته شود")
        self.assertEqual(row["ORC_STOCK_IKCO"], 10.0)

    def test_duplicate_inside_one_sheet_resolves_at_material_grain(self):
        a = sheet([{'شماره فني': 'D1', 'موجودي انبار ايران خودرو': 1,
                    'موجودي انبار ساپکو': 1, 'نياز روزانه قطعات': 2},
                   {'شماره فني': 'D1', 'موجودي انبار ايران خودرو': 2,
                    'موجودي انبار ساپکو': 3, 'نياز روزانه قطعات': 2}])
        out = OracleAdapter().transform({'1': a})['main']
        self.assertEqual(len(out), 1)
        row = out.iloc[0]
        self.assertEqual(row['ORC_STOCK_IKCO'], 3.0, 'موجودی چند bucket باید جمع شود')
        self.assertEqual(row['ORC_STOCK_SAPCO'], 4.0)
        self.assertEqual(row['ORC_DAILY_NEED'], 2.0, 'نیاز روزانه نباید جمع شود')

    def test_exact_duplicate_business_row_is_not_double_counted(self):
        a = sheet([{'شماره فني': 'D2', 'موجودي انبار ايران خودرو': 7,
                    'موجودي انبار ساپکو': 1, 'نياز روزانه قطعات': 3},
                   {'شماره فني': 'D2', 'موجودي انبار ايران خودرو': 7,
                    'موجودي انبار ساپکو': 1, 'نياز روزانه قطعات': 3}])
        out = OracleAdapter().transform({'1': a})['main']
        row = out.iloc[0]
        self.assertEqual(row['ORC_STOCK_IKCO'], 7.0, 'duplicate کامل نباید موجودی را دوبرابر کند')
        self.assertEqual(row['ORC_DAILY_NEED'], 3.0)



def main() -> int:
    r = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(OracleUnionTests))
    ok = r.testsRun - len(r.failures) - len(r.errors)
    fail = len(r.failures) + len(r.errors)
    print(f"نتیجه: {ok} موفق | {fail} ناموفق")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
