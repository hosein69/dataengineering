# -*- coding: utf-8 -*-
"""شاهد حرکت محموله — و مرزی که نباید از آن رد شد.

`BL_DATE` (تاریخ *صدور* بارنامه) از `BL_BL_DATE` مشتق می‌شد که هیچ adapterی
تولیدش نمی‌کند. نتیجه: همیشه خالی، و پنج مصرف‌کننده بی‌صدا از کار افتاده.

راه‌حل **remap نبود**، چون هیچ سورسی تاریخ صدور بارنامه را ندارد. کاری که شد:
شاهدهای واقعی و پرشده‌ای که adapter استخراج می‌کرد ولی خط لوله روی زمین
می‌گذاشت، نام دامنه‌ای گرفتند و در یک زنجیره‌ی مرتب به `SHIPPED_EVIDENCE_DATE`
رسیدند — با ستون دومی که می‌گوید کدام شاهد بوده.

مرز قرمز، که بیشتر این تست‌ها همان را نگه می‌دارند: **سررسید برات حق ندارد از
این زنجیره استفاده کند.** سررسید یوزانس از تاریخ صدور بارنامه شمرده می‌شود؛
تاریخ تخلیه هفته‌ها بعدتر و در مقصد است، پس جایگزینی سررسید را عقب می‌اندازد و
جریمه تأخیر را **کمتر از واقع** نشان می‌دهد. عددِ غلطِ خوش‌بینانه، بدترین
خروجی ممکن این سامانه است.
"""
from __future__ import annotations

import datetime as dt
import unittest

import pandas as pd

from gsi.stages.s20_derive import (DECLARED_UNMEASURED, DERIVED,
                                   SHIPMENT_EVIDENCE_CHAIN, DeriveStage)


def _rows(**overrides):
    row = {
        "CANONICAL_BL": "BL1",
        "BL_BL_DATE": "",
        "BL_BL_DELIVERY_DATE": "",
        "BL_DISCHARGE_DATE": "",
        "BL_DO_DATE": "",
        "BL_RELEASE_DATE": "",
        "BL_WAREHOUSE_RECEIPT": "",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def _evidence(df):
    date, basis = DeriveStage._shipment_evidence(df)
    return str(date.iat[0]), str(basis.iat[0])


class TheEvidenceChainPicksTheEarliestProof(unittest.TestCase):

    def test_the_bill_of_lading_date_wins_when_it_exists(self):
        """اگر روزی سورسی تاریخ بارنامه بدهد، همان مبنا می‌شود."""
        date, basis = _evidence(_rows(BL_BL_DATE="1405/05/01",
                                      BL_DISCHARGE_DATE="1405/06/20"))
        self.assertEqual("1405/05/01", date)
        self.assertEqual("تاریخ بارنامه", basis)

    def test_it_falls_back_through_the_lifecycle_in_order(self):
        date, basis = _evidence(_rows(BL_DISCHARGE_DATE="1405/06/20",
                                      BL_RELEASE_DATE="1405/07/02"))
        self.assertEqual("1405/06/20", date, "تخلیه زودتر از آزادسازی است")
        self.assertEqual("تاریخ تخلیه", basis)

    def test_the_last_link_still_counts_as_proof(self):
        date, basis = _evidence(_rows(BL_WAREHOUSE_RECEIPT="1405/07/10"))
        self.assertEqual("1405/07/10", date)
        self.assertEqual("تاریخ قبض انبار", basis)

    def test_no_evidence_stays_empty_and_is_never_invented(self):
        date, basis = _evidence(_rows())
        self.assertEqual("", date)
        self.assertEqual("", basis)

    def test_the_basis_column_is_never_silently_dropped(self):
        """تاریخِ بدون منشأ، روی صفحه «تاریخ بارنامه» خوانده می‌شود."""
        date, basis = _evidence(_rows(BL_DO_DATE="1405/06/01"))
        self.assertTrue(date)
        self.assertTrue(basis, "تاریخ بدون ذکر منشأ منتشر نمی‌شود")

    def test_a_missing_source_column_does_not_break_the_chain(self):
        thin = pd.DataFrame([{"CANONICAL_BL": "BL1", "BL_RELEASE_DATE": "1405/07/02"}])
        date, basis = _evidence(thin)
        self.assertEqual("1405/07/02", date)
        self.assertEqual("تاریخ آزادسازی", basis)


class TheRealShipmentDatesAreNoLongerDroppedOnTheFloor(unittest.TestCase):
    """adapter این سه را استخراج می‌کرد و مرحله ترجمه نادیده می‌گرفت."""

    def test_recovered_fields_have_a_domain_name(self):
        for target, source in (("BL_DELIVERY_DATE", "BL_BL_DELIVERY_DATE"),
                               ("RELEASE_DATE", "BL_RELEASE_DATE"),
                               ("DO_DATE", "BL_DO_DATE")):
            self.assertIn(target, DERIVED)
            self.assertIn(source, DERIVED[target][0])


class TheBillOfLadingDateStaysUnknownOnPurpose(unittest.TestCase):

    def test_it_is_declared_unmeasured_not_quietly_broken(self):
        """«تصمیم‌گرفته‌شده» باید از «مرده و فراموش‌شده» جدا بماند."""
        self.assertIn("BL_DATE", DECLARED_UNMEASURED)

    def test_it_is_not_secretly_sourced_from_a_lookalike(self):
        candidates = DERIVED["BL_DATE"][0]
        self.assertEqual(["BL_BL_DATE"], list(candidates))
        for lookalike in ("BL_BL_DELIVERY_DATE", "BL_DISCHARGE_DATE",
                          "BL_DO_DATE", "BL_RELEASE_DATE", "BL_WAREHOUSE_RECEIPT"):
            self.assertNotIn(lookalike, candidates,
                             "تاریخ صدور بارنامه با هیچ تاریخ مشابهی جایگزین نمی‌شود")


class TheUsanceDueDateUsesTheEvidenceOnlyAsAFlaggedInterim(unittest.TestCase):
    """سیاست در ۱۴۰۵/۰۷/۰۴ با تصمیم مالک عوض شد.

    نسخه قبلی این کلاس، ساختن سررسید از شاهد حرکت را **ممنوع** می‌کرد، چون
    شاهد همیشه بعد از تاریخ بارنامه است و سررسید را دیرتر از واقع می‌سازد.
    مالک این ریسک را شنید و تصمیم گرفت: «فعلاً نزدیک‌ترین تاریخ به تاریخ
    بارنامه، تا بررسی کنم».

    پس ممنوعیت برداشته شد، ولی خودِ ریسک نه: تقریب هرگز بی‌صدا نیست. هر
    پرونده‌ای که این‌طور حساب شده، علامت می‌خورد و تصمیم‌های وابسته حداکثر
    «جهت‌نما» می‌شوند. جزئیات و تست کامل در ``test_invoice_basis_v29_12``.
    """

    def _result(self, **row):
        from gsi.engines.commitment import CommitmentEngine
        base = {"CANONICAL_REG": "10000001", "PAYMENT_METHOD": "برات",
                "SEGMENT": "production", "BARAT_DUE": "", "CB_DATE": "", "BUY_DATE": ""}
        base.update(row)
        return CommitmentEngine().evaluate(base, dt.date(2026, 8, 31))

    def test_the_evidence_date_now_produces_a_due_date(self):
        self.assertIsNotNone(self._result(SHIPPED_EVIDENCE_DATE="1405/05/01").deadline)

    def test_and_that_due_date_is_always_marked_approximate(self):
        res = self._result(SHIPPED_EVIDENCE_DATE="1405/05/01")
        self.assertTrue(res.deadline_is_approximate,
                        "تقریب باید دیده شود، وگرنه به عدد قطعی تبدیل می‌شود")
        self.assertIn("تقریبی", res.barat_basis_fa)

    def test_a_bill_of_lading_date_outranks_the_evidence_and_is_exact(self):
        res = self._result(BL_DATE="1405/05/01", SHIPPED_EVIDENCE_DATE="1405/06/20")
        self.assertFalse(res.deadline_is_approximate)

    def test_the_invoice_date_outranks_both(self):
        res = self._result(INVOICE_DATE="1405/04/01", BL_DATE="1405/05/01",
                           SHIPPED_EVIDENCE_DATE="1405/06/20")
        self.assertFalse(res.deadline_is_approximate)
        self.assertIn("فاکتور", res.barat_basis_fa)


class TheConsumersPointAtEvidenceThatExists(unittest.TestCase):

    def test_the_shipment_event_no_longer_depends_on_a_phantom_column(self):
        from gsi.stages.s80_eventlog import EventLogStage
        self.assertIn("SHIPPED_EVIDENCE_DATE", EventLogStage.requires)
        self.assertNotIn("BL_DATE", EventLogStage.requires)

    def test_the_shipment_decision_grades_on_real_evidence(self):
        from gsi.trust.contracts import BY_ID
        required = BY_ID["SHIPMENT_TRACKING"].required
        self.assertIn("SHIPPED_EVIDENCE_DATE", required)
        self.assertNotIn("BL_DATE", required)

    def test_no_expert_is_sent_looking_for_a_cell_that_cannot_exist(self):
        """BL_DATE نباید در فهرست کار کارشناس باشد — قابل پرکردن نیست."""
        from gsi.trust.contracts import RULES, BL
        self.assertNotIn("BL_DATE", [r.column for r in RULES[BL]])


class TheChainIsOrderedByLifecycle(unittest.TestCase):

    def test_the_bill_of_lading_is_first_and_the_warehouse_receipt_is_last(self):
        columns = [c for c, _ in SHIPMENT_EVIDENCE_CHAIN]
        self.assertEqual("BL_BL_DATE", columns[0])
        self.assertEqual("BL_WAREHOUSE_RECEIPT", columns[-1])

    def test_every_link_has_a_persian_label_for_the_basis_column(self):
        for column, label in SHIPMENT_EVIDENCE_CHAIN:
            self.assertTrue(label.strip(), column)


if __name__ == "__main__":
    unittest.main()
