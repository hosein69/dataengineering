# -*- coding: utf-8 -*-
"""Financial decisions must use a published version and witnessed amounts."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from gsi.stages.base import PipelineContext
from gsi.stages.s20_derive import DeriveStage
from gsi.warehouse.fx_obligation import chain, coverage, totals_by_currency
from gsi.warehouse.marts import stage
from gsi.warehouse.store import Warehouse


class FinancialSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("GSI_DWH_PATH")
        os.environ["GSI_DWH_PATH"] = str(Path(self.tmp.name) / "warehouse.sqlite")
        self.wh = Warehouse()

    def tearDown(self):
        if self.old is None:
            os.environ.pop("GSI_DWH_PATH", None)
        else:
            os.environ["GSI_DWH_PATH"] = self.old
        self.tmp.cleanup()

    def ingest(self, amount, registration, tag):
        with self.wh.run({"tag": tag}) as rid:
            fid = self.wh.blob(tag.encode(), tag + ".xlsx", "ntsw", "/" + tag)
            stage(pd.DataFrame([{
                "_SOURCE_ROW": 2, "کد ثبت سفارش": registration,
                "تاریخ ایجاد تعهد": "1405/06/24", "وضعیت رفع تعهد": "رفع تعهد نشده",
                "مانده تعهد": amount, "ارز": "یورو",
            }]), "ntsw", "Release Commitment", fid)
        return rid

    def test_chain_and_coverage_use_only_published_run(self):
        old = self.ingest("500", "OLD", "old")
        self.wh.publish(old)
        new = self.ingest("50", "NEW", "new")
        # An unapproved refresh must not appear in the current decision.
        self.assertEqual([r["ثبت سفارش"] for r in chain(self.wh)], ["OLD"])
        self.assertEqual(coverage(self.wh)["registrations_total"], 1)
        self.wh.publish(new)
        self.assertEqual([r["ثبت سفارش"] for r in chain(self.wh)], ["NEW"])
        self.assertEqual(chain(self.wh)[0]["مانده تعهد"], "50")
        self.assertEqual(coverage(self.wh)["registrations_total"], 1)
        self.assertEqual(chain(self.wh, run_id=old)[0]["مانده تعهد"], "500")
        self.assertEqual(totals_by_currency(self.wh)[0]["جمع معلوم"], "50")

    def test_no_publication_never_reads_archived_records(self):
        self.ingest("500", "OLD", "old")
        self.assertEqual(chain(self.wh), [])
        self.assertEqual(coverage(self.wh)["registrations_total"], 0)

    def test_missing_financial_values_are_not_zero(self):
        targets = ("EUR_VALUE", "DUTY_AMOUNT", "FX_EUR_VALUE",
                   "CREDIT_PROFORMA", "CREDIT_RIAL_AMOUNT", "CREDIT_EUR_AMOUNT",
                   "CREDIT_PREPAYMENT", "CREDIT_REMAINING")
        sources = {
            "CL_EUR_VALUE": "EUR_VALUE", "CL_DUTY_AMOUNT": "DUTY_AMOUNT",
            "FX_EUR_VALUE": "FX_EUR_VALUE", "CRD_PROFORMA_VALUE": "CREDIT_PROFORMA",
            "CRD_RIAL_AMOUNT": "CREDIT_RIAL_AMOUNT", "CRD_EUR_AMOUNT": "CREDIT_EUR_AMOUNT",
            "CRD_PREPAYMENT": "CREDIT_PREPAYMENT", "CRD_REMAINING": "CREDIT_REMAINING",
        }
        df = pd.DataFrame({source: [None, "0", "12.5"] for source in sources})
        out = DeriveStage().run(df, PipelineContext(rb=None, today=date(2026, 9, 27)))
        for target in targets:
            self.assertTrue(pd.isna(out.loc[0, target]), target)
            self.assertEqual(out.loc[1, target], 0, target)
            self.assertEqual(out.loc[2, target], 12.5, target)
            self.assertEqual(out[target + "_IS_UNKNOWN"].tolist(), [True, False, False])


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(FinancialSnapshotTests))
    print(f"نتیجه: {result.testsRun - len(result.failures) - len(result.errors)} موفق | "
          f"{len(result.failures) + len(result.errors)} ناموفق")
    raise SystemExit(0 if result.wasSuccessful() else 1)
