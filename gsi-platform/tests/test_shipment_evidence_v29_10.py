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


class TheUsanceDueDateRefusesASubstitute(unittest.TestCase):
    """مرز قرمز: جایگزینی اینجا، جریمه تأخیر را کمتر از واقع نشان می‌دهد."""

    def _due(self, row):
        from gsi.engines.commitment import CommitmentEngine
        return CommitmentEngine().evaluate(row, dt.date(2026, 8, 31)).deadline

    def test_a_discharge_date_does_not_become_a_usance_due_date(self):
        base = {
            "CANONICAL_REG": "10000001", "PAYMENT_METHOD": "برات",
            "SEGMENT": "production", "BL_DATE": "",
            "SHIPPED_EVIDENCE_DATE": "1405/05/01",
            "SHIPPED_EVIDENCE_BASIS": "تاریخ تخلیه",
            "BARAT_DUE": "", "CB_DATE": "", "BUY_DATE": "",
        }
        with_evidence = self._due(dict(base))
        without = self._due(dict(base, SHIPPED_EVIDENCE_DATE="", SHIPPED_EVIDENCE_BASIS=""))
        self.assertEqual(
            without, with_evidence,
            "سررسید برات نباید از شاهد حرکت محموله ساخته شود؛ عدد خوش‌بینانه غلط، "
            "بدتر از عدد نامعلوم است.")

    def test_a_real_bill_of_lading_date_does_drive_it(self):
        """قاعده باید هنوز کار کند — این تست «کلاً خاموشش کردیم» را رد می‌کند."""
        row = {
            "CANONICAL_REG": "10000001", "PAYMENT_METHOD": "برات",
            "SEGMENT": "production", "BL_DATE": "1405/05/01",
            "BARAT_DUE": "", "CB_DATE": "", "BUY_DATE": "",
        }
        blank = dict(row, BL_DATE="")
        self.assertNotEqual(self._due(blank), self._due(row),
                            "تاریخ واقعی بارنامه باید سررسید بسازد")


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
