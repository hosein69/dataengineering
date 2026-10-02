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

    def test_only_the_declared_chain_can_serve_as_a_basis(self):
        """تاریخ‌های خارج از زنجیره حق ندارند سررسید بسازند.

        ترخیص و ورود، چه تقریبی چه دقیق، مبنا نیستند: خیلی دیرتر از بارنامه‌اند.
        """
        for outsider in ("DISCHARGE_DATE", "FULL_CLEAR_DATE", "ARRIVAL_DATE",
                         "DO_DATE", "RELEASE_DATE"):
            with self.subTest(outsider):
                self.assertIsNone(self._due(self._row(**{outsider: "1405/05/01"})))

    def test_an_explicit_barat_due_from_the_source_still_wins(self):
        """قاعده پیش‌فرض، مقدار صریح سورس را کنار نمی‌زند."""
        self.assertIsNotNone(self._due(self._row(BARAT_DUE="1405/12/01")))


class TheInterimBasisIsAllowedButNeverSilent(unittest.TestCase):
    """مالک (۱۴۰۵/۰۷/۰۴): «فعلاً نزدیک‌ترین تاریخ به تاریخ بارنامه، تا بررسی کنم».

    اجازه داده شد، ولی تقریب هرگز بی‌صدا نیست: مبنا نوشته می‌شود و پرونده
    علامت «تقریبی» می‌خورد. شاهد حرکت محموله همیشه **بعد از** تاریخ بارنامه
    است، پس سررسیدِ ساخته‌شده از آن دیرتر از واقع و جریمه کمتر از واقع است.
    """

    def test_the_chain_is_ordered_invoice_then_bill_of_lading_then_evidence(self):
        from gsi.engines.commitment import BARAT_BASIS_CHAIN
        self.assertEqual(["INVOICE_DATE", "BL_DATE", "SHIPPED_EVIDENCE_DATE"],
                         [c for c, _, _ in BARAT_BASIS_CHAIN])

    def test_only_the_last_link_is_approximate(self):
        from gsi.engines.commitment import BARAT_BASIS_CHAIN
        exact = {c: e for c, _, e in BARAT_BASIS_CHAIN}
        self.assertTrue(exact["INVOICE_DATE"])
        self.assertTrue(exact["BL_DATE"])
        self.assertFalse(exact["SHIPPED_EVIDENCE_DATE"])

    def test_a_bill_of_lading_date_is_used_and_is_not_approximate(self):
        from gsi.engines.commitment import barat_basis
        _, label, exact = barat_basis({"BL_DATE": "1405/05/01",
                                       "SHIPPED_EVIDENCE_DATE": "1405/06/20"})
        self.assertTrue(exact)
        self.assertNotIn("تقریبی", label)

    def test_the_evidence_date_is_used_but_marked_approximate(self):
        from gsi.engines.commitment import CommitmentEngine
        res = CommitmentEngine().evaluate(
            {"CANONICAL_REG": "1", "PAYMENT_METHOD": "برات", "SEGMENT": "production",
             "BARAT_DUE": "", "SHIPPED_EVIDENCE_DATE": "1405/05/01"},
            dt.date(2026, 8, 31))
        self.assertIsNotNone(res.deadline, "مالک اجازه استفاده موقت داده است")
        self.assertTrue(res.deadline_is_approximate)
        self.assertIn("تقریبی", res.barat_basis_fa)

    def test_the_basis_reaches_the_mart_so_a_reader_can_see_it(self):
        from gsi.engines.commitment import CommitmentEngine
        row = CommitmentEngine().evaluate(
            {"CANONICAL_REG": "1", "PAYMENT_METHOD": "برات", "SEGMENT": "production",
             "BARAT_DUE": "", "SHIPPED_EVIDENCE_DATE": "1405/05/01"},
            dt.date(2026, 8, 31)).as_dict()
        self.assertIn("تقریبی", row["مبنای سررسید برات"])
        self.assertTrue(row["DEADLINE_IS_APPROXIMATE"])

    def test_an_exact_basis_is_not_flagged(self):
        from gsi.engines.commitment import CommitmentEngine
        res = CommitmentEngine().evaluate(
            {"CANONICAL_REG": "1", "PAYMENT_METHOD": "برات", "SEGMENT": "production",
             "BARAT_DUE": "", "INVOICE_DATE": "1405/05/01"}, dt.date(2026, 8, 31))
        self.assertFalse(res.deadline_is_approximate)


class AProvisionalAnswerIsNeverDecisionGrade(unittest.TestCase):
    """تقریبِ اعلام‌شده نباید چند صفحه بعد به عدد قطعی تبدیل شود."""

    def _verdict(self, approximate):
        from gsi.trust.fitness import DecisionContract, evaluate
        from gsi.trust.profiling import FieldRule, profile_frame
        rows = [{"CANONICAL_REG": "1", "مهلت قانونی رفع تعهد": "1405/09/01",
                 "DEADLINE_IS_APPROXIMATE": approximate}]
        frame = pd.DataFrame(rows)
        profile = profile_frame(frame, (FieldRule("مهلت قانونی رفع تعهد", title_fa="مهلت"),),
                                entity_type="REG", key_column="CANONICAL_REG")
        contract = DecisionContract(
            id="X", title_fa="x", question_fa="x?", entity_type="REG",
            required=("مهلت قانونی رفع تعهد",),
            provisional_flag="DEADLINE_IS_APPROXIMATE")
        return evaluate(contract, profile, frame, "CANONICAL_REG")

    def test_full_coverage_is_still_only_directional_when_provisional(self):
        from gsi.trust.fitness import DECISION_GRADE, DIRECTIONAL
        v = self._verdict(True)
        self.assertEqual(100.0, v.coverage_pct)
        self.assertEqual(1, v.provisional_cases)
        self.assertEqual(DIRECTIONAL, v.grade)
        self.assertNotEqual(DECISION_GRADE, v.grade)

    def test_the_same_data_without_the_flag_is_decision_grade(self):
        from gsi.trust.fitness import DECISION_GRADE
        v = self._verdict(False)
        self.assertEqual(0, v.provisional_cases)
        self.assertEqual(DECISION_GRADE, v.grade)

    def test_the_reason_says_the_number_understates_the_penalty(self):
        reasons = " ".join(self._verdict(True).reasons_fa())
        self.assertIn("تقریبی", reasons)
        self.assertIn("کمتر از واقع", reasons)

    def test_the_deadline_decisions_carry_the_flag(self):
        from gsi.trust.contracts import BY_ID
        for cid in ("FX_DEADLINE_RISK", "PENALTY_EXPOSURE"):
            self.assertEqual("DEADLINE_IS_APPROXIMATE", BY_ID[cid].provisional_flag, cid)


class TheInvoiceValueComesFromTheNamedSourcesOnly(unittest.TestCase):
    """مرجع: ساتا و NTSW (تصمیم مالک). ترخیص و کوتاژ پرکننده جای خالی نیستند."""

    def test_clearance_and_cotage_cannot_supply_the_value(self):
        candidates = DERIVED["INVOICE_VALUE"][0]
        self.assertIn("SATA_INVOICE_VALUE", candidates)
        self.assertNotIn("CL_INVOICE_VALUE", candidates)
        self.assertNotIn("COT_INVOICE_VALUE", candidates)

    def test_but_they_are_still_compared_so_the_disagreement_stays_visible(self):
        from gsi.trust.contracts import REG, cross_source_for
        rule = [r for r in cross_source_for(REG) if r.column == "INVOICE_VALUE"][0]
        self.assertIn("CL_INVOICE_VALUE", rule.sources)
        self.assertIn("COT_INVOICE_VALUE", rule.sources)


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
