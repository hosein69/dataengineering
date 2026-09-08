# -*- coding: utf-8 -*-
"""مرحله ۱۰ — حل موجودیت کانونی."""
from __future__ import annotations

from typing import List

import pandas as pd

from ..adapters.base import KEY_BL, KEY_ORDER
from .base import ColumnSpec, GROUP_MAIN, PipelineContext, Stage, register


@register
class ResolveStage(Stage):
    name = "resolve"
    title = "حل تعارض و ساخت کلیدهای کانونی"
    order = 10
    requires = [KEY_BL, KEY_ORDER]
    provides = ["CANONICAL_BL", "CANONICAL_ORDER", "CANONICAL_PART_NO",
                "CANONICAL_GOODS_DESC", "CANONICAL_EXPERT", "CANONICAL_REG"]

    #: نگاشت موجودیت → کاندیدها. افزودن سورس جدید = یک تاپل اینجا.
    MAP = {
        "CANONICAL_BL": ("شماره بارنامه", True,
                         [(KEY_BL, "abbasi"), ("MOGH_BL_NO", "moghavemat")]),
        "CANONICAL_ORDER": ("شماره سفارش", True,
                            [(KEY_ORDER, "abbasi"), ("MOGH_ORDER_REF", "moghavemat")]),
        "CANONICAL_PART_NO": ("شماره فنی", True,
                              [("ORC_PART_NO", "oracle"),
                               ("MOGH_MATERIAL", "moghavemat"),
                               ("MOGH_MFR_PART_NO", "moghavemat")]),
        "CANONICAL_GOODS_DESC": ("شرح کالا", False,
                                 [("ORC_MATERIAL_DESC", "oracle"),
                                  ("MOGH_MATERIAL_DESC", "moghavemat"),
                                  ("BL_GOODS_DESC", "abbasi"),
                                  ("CL_GOODS_DESC", "clearance"),
                                  ("SATA_GOODS_DESC", "sata")]),
        # کارشناس: هر مرحله مالک خودش را دارد. کارشناس خرید خارجی (Oracle)
        # مالک قطعه است و بالاترین اولویت را دارد؛ بقیه مالک مرحله‌اند.
        "CANONICAL_EXPERT": ("نام کارشناس", False,
                             [("ORC_BUYER", "oracle"),
                              ("CL_EXPERT", "clearance"),
                              ("SATA_CREDIT_EXPERT", "sata"),
                              ("CRD_EXPERT", "credit"),
                              ("DOC_EXPERT", "doccheck")]),
        # ⚠️ کلید ثبت سفارش ۸ رقمی است و «شماره پرونده ثبت سفارش» (۹ رقمی)
        # نیست. ساتا تنها سورسی است که این ستون را ۱۰۰٪ پر دارد.
        "CANONICAL_REG": ("ثبت سفارش", True,
                          [("SATA_KEY_REG", "sata"),
                           ("FX_KEY_REG", "fx_transaction"),
                           ("CRD_KEY_REG", "credit"),
                           ("IL_KEY_REG", "ilappend")]),
    }

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        for target, (label, is_key, candidates) in self.MAP.items():
            df[target] = ctx.resolver.resolve(df, label, candidates, is_key=is_key)
        return df

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("CANONICAL_ORDER", "شماره سفارش (کانونی)", 18, GROUP_MAIN, order=20),
            ColumnSpec("CANONICAL_BL", "شماره بارنامه (کانونی)", 20, GROUP_MAIN, order=21),
            ColumnSpec("CANONICAL_PART_NO", "شماره فنی / متریال", 18, GROUP_MAIN, order=22),
        ]
