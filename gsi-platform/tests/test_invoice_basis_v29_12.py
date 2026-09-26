# -*- coding: utf-8 -*-
"""فاکتور تجاری به‌عنوان مبنای تعهد — و سنجش سازگاری سورس‌ها.

مالک کسب‌وکار (۱۴۰۵/۰۷/۰۴) تعیین کرد که مبنای سررسید برات، **فاکتور تجاری**
است نه بارنامه. دو چیز از این تصمیم نتیجه شد:

۱. `INVOICE_DATE` اعلام شد و `default_barat_due()` به آن وصل شد. امروز هیچ
   فایلی این ستون را ندارد، پس سررسید نامعلوم می‌ماند — و این از یک عدد
   خوش‌بینانهٔ غلط بهتر است.

۲. «ارزش فاکتور» سه سورس دارد که در داده واقعی تا ۵۷ برابر اختلاف داشتند.
   ادغام، یکی را با ترتیب authority برمی‌داشت و بقیه را بی‌صدا دور می‌ریخت.
   حالا اختلاف، خودش یک ایراد ثبت‌شده با مالک است.
"""
from __future__ import annotations

import datetime as dt
import unittest

import pandas as pd

from gsi.stages.s20_derive import DECLARED_UNMEASURED, DERIVED
from gsi.trust.profiling import CURRENCY, CrossSourceRule, profile_frame


class TheUsanceDueDateCountsFromTheCommercialInvoice(unittest.TestCase):

    def _due(self, row):
        from gsi.engines.commitment import CommitmentEngine
        return CommitmentEngine().evaluate(row, dt.date(2026, 8, 31)).deadline

    def _row(self, **over):
        row = {"CANONICAL_REG": "10000001", "PAYMENT_METHOD": "برات",
               "SEGMENT": "production", "BARAT_DUE": "", "CB_DATE": "", "BUY_DATE": ""}
        row.update(over)
        return row

    def test_an_invoice_date_produces_a_due_date(self):
        self.assertIsNotNone(self._due(self._row(INVOICE_DATE="1405/05/01")))

    def test_the_tenor_is_counted_from_the_invoice_date(self):
        from gsi.engines.commitment import default_barat_due
        from gsi.rulebook import get_rulebook
        rb = get_rulebook()
        days = int(rb.deadline_days("default_barat_tenor") or 180)
        basis = dt.date(2026, 1, 1)
        self.assertEqual(basis + dt.timedelta(days=days), default_barat_due(basis, rb))

    def test_no_shipment_date_can_stand_in_for_it(self):
        """مرز قرمز: تخلیه/ترخیص هفته‌ها بعدترند و جریمه را کمتر از واقع نشان می‌دهند."""
        for substitute in ("SHIPPED_EVIDENCE_DATE", "BL_DATE", "DISCHARGE_DATE",
                           "FULL_CLEAR_DATE", "ARRIVAL_DATE"):
            with self.subTest(substitute):
                self.assertIsNone(
                    self._due(self._row(**{substitute: "1405/05/01"})),
                    f"«{substitute}» نباید سررسید برات بسازد")

    def test_an_explicit_barat_due_from_the_source_still_wins(self):
        """قاعده پیش‌فرض، مقدار صریح سورس را کنار نمی‌زند."""
        self.assertIsNotNone(self._due(self._row(BARAT_DUE="1405/12/01")))


class TheInvoiceDateIsDeclaredEvenThoughNoSourceCarriesItYet(unittest.TestCase):

    def test_it_is_a_domain_field_with_candidates_ready(self):
        self.assertIn("INVOICE_DATE", DERIVED)
        self.assertTrue(DERIVED["INVOICE_DATE"][0],
                        "کاندیدها باید از قبل اعلام شوند تا افزودن ستون، تغییر کد نخواهد")

    def test_decided_is_not_confused_with_forgotten(self):
        self.assertIn("INVOICE_DATE", DECLARED_UNMEASURED)

    def test_the_bill_of_lading_is_no_longer_the_basis_for_anything(self):
        self.assertIn("BL_DATE", DECLARED_UNMEASURED)


def _frame(rows):
    return pd.DataFrame(rows)


_VALUE_RULE = CrossSourceRule(
    column="INVOICE_VALUE",
    sources=("CL_INVOICE_VALUE", "SATA_INVOICE_VALUE", "COT_INVOICE_VALUE"),
    title_fa="ارزش فاکتور")
_CURRENCY_RULE = CrossSourceRule(
    column="CURRENCY", sources=("CL_CURRENCY", "SATA_CURRENCY"),
    title_fa="ارز فاکتور", kind=CURRENCY)


def _defects(rows, rules):
    result = profile_frame(_frame(rows), (), entity_type="REG",
                           key_column="CANONICAL_REG", cross_source=rules)
    return list(result.ledger)


class SourcesThatDisagreeAboutMoneyAreReported(unittest.TestCase):

    def test_a_real_disagreement_is_caught(self):
        found = _defects([{"CANONICAL_REG": "1", "CL_INVOICE_VALUE": 413056.67,
                           "SATA_INVOICE_VALUE": 16284521.76}], [_VALUE_RULE])
        self.assertEqual(1, len(found))
        self.assertEqual("SOURCE_DISAGREEMENT", found[0].code)

    def test_the_note_names_every_source_and_its_number(self):
        found = _defects([{"CANONICAL_REG": "1", "CL_INVOICE_VALUE": 413056.67,
                           "SATA_INVOICE_VALUE": 16284521.76}], [_VALUE_RULE])
        note = found[0].note
        self.assertIn("CL_INVOICE_VALUE", note)
        self.assertIn("SATA_INVOICE_VALUE", note)
        self.assertIn("413,056.67", note)

    def test_agreeing_sources_produce_nothing(self):
        self.assertEqual([], _defects(
            [{"CANONICAL_REG": "1", "CL_INVOICE_VALUE": 100.0,
              "SATA_INVOICE_VALUE": 100.0}], [_VALUE_RULE]))

    def test_rounding_noise_is_not_a_disagreement(self):
        """هشدار کاذب، کنترل را خاموش می‌کند."""
        self.assertEqual([], _defects(
            [{"CANONICAL_REG": "1", "CL_INVOICE_VALUE": 1000.00,
              "SATA_INVOICE_VALUE": 1000.05}], [_VALUE_RULE]))

    def test_one_source_alone_is_not_a_disagreement(self):
        self.assertEqual([], _defects(
            [{"CANONICAL_REG": "1", "CL_INVOICE_VALUE": 100.0}], [_VALUE_RULE]))

    def test_a_blank_source_is_silence_not_a_zero(self):
        self.assertEqual([], _defects(
            [{"CANONICAL_REG": "1", "CL_INVOICE_VALUE": 100.0,
              "SATA_INVOICE_VALUE": ""}], [_VALUE_RULE]))

    def test_one_case_across_many_rows_is_one_defect(self):
        """دانه موجودیت، مثل بقیه لایه — نه یک ایراد به‌ازای هر ردیف."""
        rows = [{"CANONICAL_REG": "1", "CL_INVOICE_VALUE": 100.0,
                 "SATA_INVOICE_VALUE": 900.0} for _ in range(40)]
        self.assertEqual(1, len(_defects(rows, [_VALUE_RULE])))

    def test_the_defect_carries_evidence_and_an_owner_slot(self):
        found = _defects([{"CANONICAL_REG": "1", "CL_INVOICE_VALUE": 1.0,
                           "SATA_INVOICE_VALUE": 99.0,
                           "_SOURCE_FILE": "sata.xlsx", "_SOURCE_ROW": 12}],
                         [_VALUE_RULE])
        self.assertTrue(found[0].evidence.locator_fa)
        self.assertEqual("INVOICE_VALUE", found[0].field_name)


class SourcesThatDisagreeAboutCurrencyAreReported(unittest.TestCase):

    def test_two_different_currencies_for_one_case_are_caught(self):
        found = _defects([{"CANONICAL_REG": "1", "CL_CURRENCY": "یوان",
                           "SATA_CURRENCY": "EUR"}], [_CURRENCY_RULE])
        self.assertEqual(1, len(found))
        self.assertEqual("CURRENCY_DISAGREEMENT", found[0].code)

    def test_the_same_currency_written_two_ways_is_not_a_conflict(self):
        """«یوان» و «CNY» یک ارزند؛ مقایسه خام هشدار کاذب می‌سازد."""
        self.assertEqual([], _defects(
            [{"CANONICAL_REG": "1", "CL_CURRENCY": "یوان",
              "SATA_CURRENCY": "CNY"}], [_CURRENCY_RULE]))


class TheCheckIsRegisteredForTheRealMart(unittest.TestCase):

    def test_invoice_value_and_currency_are_both_watched(self):
        from gsi.trust.contracts import REG, cross_source_for
        watched = {r.column for r in cross_source_for(REG)}
        self.assertIn("INVOICE_VALUE", watched)
        self.assertIn("CURRENCY", watched)


if __name__ == "__main__":
    unittest.main()
