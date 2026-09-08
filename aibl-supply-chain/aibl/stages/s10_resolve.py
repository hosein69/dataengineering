# -*- coding: utf-8 -*-
"""مرحله ۱۰ — حل موجودیت کانونی."""
from __future__ import annotations

from typing import List

import pandas as pd

from ..adapters.base import KEY_BL, KEY_ORDER
from ..dataio.logging_setup import log
from ..resolve.expert_roles import (coverage as expert_coverage,
                                    current_owner, resolve_roles)
from .base import ColumnSpec, GROUP_MAIN, PipelineContext, Stage, register


@register
class ResolveStage(Stage):
    name = "resolve"
    title = "حل تعارض و ساخت کلیدهای کانونی"
    order = 10
    requires = [KEY_BL, KEY_ORDER]
    provides = ["CANONICAL_BL", "CANONICAL_ORDER", "CANONICAL_PART_NO",
                "CANONICAL_GOODS_DESC", "CANONICAL_EXPERT", "EXPERT_ROLE",
                "CANONICAL_REG"]

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
        # ⚠️ «CANONICAL_EXPERT» دیگر اینجا ادغام نمی‌شود.
        # تا نسخه ۲۶٫۵ این ستون با «اولین مقدار غیرتهی» از پنج سورس پر
        # می‌شد و چون ORC_BUYER فقط ۱۷٪ پر است، نام **کارشناس ترخیص**
        # زیر عنوان «نام کارشناس» می‌نشست و عملکرد ترخیص به پای خرید
        # نوشته می‌شد. حالا هر نقش ستون مستقل دارد و مالکِ مرحله فعلی
        # همراه با نامِ نقشش گزارش می‌شود.
        # → aibl/resolve/expert_roles.py
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

        # ── نقش‌های کارشناسی: هر نقش ستون مستقل، بدون سرریز بین نقش‌ها ──
        df = resolve_roles(df)
        df["CANONICAL_EXPERT"], df["EXPERT_ROLE"] = current_owner(df)

        cov = expert_coverage(df)
        filled = cov[cov["پرشدگی (٪)"] > 0]
        if not filled.empty:
            log.info("👤 نقش‌های کارشناسی: "
                     + " | ".join(f"{r['نقش']} {r['پرشدگی (٪)']:.0f}٪"
                                  f" ({r['افراد یکتا']} نفر)"
                                  for _i, r in filled.iterrows()))
        empty = cov[cov["پرشدگی (٪)"] == 0]["نقش"].tolist()
        if empty:
            log.warning("⚠️ این نقش‌ها در این اجرا هیچ داده‌ای ندارند: "
                        + "، ".join(empty)
                        + " — امتیاز و بینششان ساخته نمی‌شود.")
        ctx.extras["expert_coverage"] = cov
        return df

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("CANONICAL_ORDER", "شماره سفارش (کانونی)", 18, GROUP_MAIN, order=20),
            ColumnSpec("CANONICAL_BL", "شماره بارنامه (کانونی)", 20, GROUP_MAIN, order=21),
            ColumnSpec("CANONICAL_PART_NO", "شماره فنی / متریال", 18, GROUP_MAIN, order=22),
        ]
