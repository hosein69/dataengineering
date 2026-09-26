# -*- coding: utf-8 -*-
"""زنجیره تعهد ارزی: از درخواست تخصیص تا رفع تعهد."""
from __future__ import annotations
import os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from gsi.warehouse.store import Warehouse
from gsi.warehouse import marts
from gsi.warehouse.fx_obligation import chain, coverage, totals_by_currency


def frame(rows, start=2):
    df = pd.DataFrame(rows)
    df["_SOURCE_ROW"] = range(start, start + len(df))
    return df


class FxObligationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.keep = os.environ.get("GSI_DWH_PATH")
        os.environ["GSI_DWH_PATH"] = str(Path(self.tmp.name) / "wh.sqlite")
        self.wh = Warehouse()

    def tearDown(self):
        if self.keep is None:
            os.environ.pop("GSI_DWH_PATH", None)
        else:
            os.environ["GSI_DWH_PATH"] = self.keep
        self.tmp.cleanup()

    def stage_all(self, alloc=None, commit=None):
        # wh_business_record.file_id has a real foreign key into wh_file, so the
        # fixture registers a file the same way ingestion does.
        with self.wh.run({"reference_date": "1405-06-25"}) as rid:
            self.fixture_run = rid
            fid = self.wh.blob(b"fixture", "fixture.xlsx", "ntsw", "/fixture.xlsx")
            if alloc is not None:
                marts.stage(frame(alloc), "ntsw", "Allocation", fid)
            if commit is not None:
                marts.stage(frame(commit), "ntsw", "Release Commitment", fid)
        return fid

    def test_matched_registration_closes_the_chain(self):
        self.stage_all(
            alloc=[{"کد ثبت سفارش": "R1", "تاریخ ایجاد درخواست": "1405/06/22",
                    "تاریخ تخصیص": "1405/06/24", "مبلغ درخواست": "1000", "ارز درخواست": "یورو"}],
            commit=[{"کد ثبت سفارش": "R1", "تاریخ ایجاد تعهد": "1405/06/24",
                     "مهلت رفع تعهد": "1406/03/22", "وضعیت رفع تعهد": "رفع تعهد نشده",
                     "تعهد اولیه": "1000", "مانده تعهد": "400", "ارز": "یورو"}])
        rows = {r["ثبت سفارش"]: r for r in chain()}
        self.assertIn("R1", rows)
        r = rows["R1"]
        self.assertEqual(r["درخواست تخصیص"], "✔")
        self.assertEqual(r["تخصیص ارز"], "✔")
        self.assertEqual(r["ایجاد تعهد"], "✔")
        self.assertEqual(r["مانده تعهد"], "400")
        self.assertEqual(r["ارز تعهد"], "یورو")
        cov = coverage()
        self.assertEqual(cov["allocation_to_commitment_matched"], 1)
        self.assertEqual(cov["match_rate"], 1.0)

    def test_unmatched_chain_is_reported_not_hidden(self):
        self.stage_all(
            alloc=[{"کد ثبت سفارش": "A1", "تاریخ ایجاد درخواست": "1405/06/22",
                    "مبلغ درخواست": "5", "ارز درخواست": "یورو"}],
            commit=[{"کد ثبت سفارش": "C1", "تاریخ ایجاد تعهد": "1405/06/24",
                     "وضعیت رفع تعهد": "رفع تعهد نشده", "تعهد اولیه": "5",
                     "مانده تعهد": "5", "ارز": "یورو"}])
        cov = coverage()
        self.assertEqual(cov["allocation_to_commitment_matched"], 0)
        self.assertEqual(cov["match_rate"], 0.0)
        self.assertEqual(cov["in_more_than_one_stage"], 0)

    def test_missing_amount_is_unknown_never_zero(self):
        self.stage_all(alloc=[{"کد ثبت سفارش": "R2", "تاریخ ایجاد درخواست": "1405/06/22"}])
        r = {x["ثبت سفارش"]: x for x in chain()}["R2"]
        self.assertEqual(r["مانده تعهد"], "نامعلوم")
        self.assertNotEqual(r["مانده تعهد"], 0)
        self.assertEqual(r["ارز تعهد"], "نامعلوم")

    def test_a_real_zero_balance_stays_zero(self):
        self.stage_all(commit=[{"کد ثبت سفارش": "R3", "تاریخ ایجاد تعهد": "1405/06/24",
                                "وضعیت رفع تعهد": "رفع تعهد شده", "تعهد اولیه": "100",
                                "مانده تعهد": "0", "ارز": "یورو"}])
        r = {x["ثبت سفارش"]: x for x in chain()}["R3"]
        self.assertEqual(r["مانده تعهد"], "0")
        self.assertEqual(r["رفع تعهد"], "✔")

    def test_currencies_are_never_summed_together(self):
        self.stage_all(commit=[
            {"کد ثبت سفارش": "R4", "تاریخ ایجاد تعهد": "1405/06/24", "وضعیت رفع تعهد": "رفع تعهد نشده",
             "تعهد اولیه": "100.25", "مانده تعهد": "100.25", "ارز": "یورو"},
            {"کد ثبت سفارش": "R5", "تاریخ ایجاد تعهد": "1405/06/24", "وضعیت رفع تعهد": "رفع تعهد نشده",
             "تعهد اولیه": "200.50", "مانده تعهد": "200.50", "ارز": "یوان چین"}])
        tot = {(t["سنجه"], t["ارز"]): t["جمع معلوم"] for t in totals_by_currency(self.wh, run_id=self.fixture_run)}
        self.assertEqual(tot[("مانده تعهد", "یورو")], "100.25")
        self.assertEqual(tot[("مانده تعهد", "یوان چین")], "200.50")
        self.assertNotIn(("مانده تعهد", "نامشخص"), tot)

    def test_decimal_precision_survives(self):
        self.stage_all(commit=[{"کد ثبت سفارش": "R6", "تاریخ ایجاد تعهد": "1405/06/24",
                                "وضعیت رفع تعهد": "رفع تعهد نشده", "تعهد اولیه": "715550.4",
                                "مانده تعهد": "715550.4", "ارز": "یوان چین"}])
        tot = {(t["سنجه"], t["ارز"]): t["جمع معلوم"] for t in totals_by_currency(self.wh, run_id=self.fixture_run)}
        self.assertEqual(tot[("مانده تعهد", "یوان چین")], "715550.4")

    def test_blank_source_row_is_not_a_case(self):
        self.stage_all(alloc=[{"کد ثبت سفارش": None, "تاریخ ایجاد درخواست": None},
                              {"کد ثبت سفارش": "R7", "تاریخ ایجاد درخواست": "1405/06/22"}])
        regs = [r["ثبت سفارش"] for r in chain()]
        self.assertEqual(regs, ["R7"])
        self.assertNotIn("nan", [str(x).lower() for x in regs])

    def test_stage_without_evidence_is_unknown_not_done(self):
        self.stage_all(alloc=[{"کد ثبت سفارش": "R8", "تاریخ ایجاد درخواست": "1405/06/22"}])
        r = {x["ثبت سفارش"]: x for x in chain()}["R8"]
        self.assertEqual(r["اظهارنامه گمرکی"], "نامعلوم")
        self.assertEqual(r["تخصیص ارز"], "—", "تاریخ تخصیص خالی یعنی هنوز تخصیص نیافته")
        self.assertIn("اظهارنامه گمرکی", r["گام بدون شاهد"])


def main() -> int:
    r = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(FxObligationTests))
    ok = r.testsRun - len(r.failures) - len(r.errors)
    fail = len(r.failures) + len(r.errors)
    print(f"نتیجه: {ok} موفق | {fail} ناموفق")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
