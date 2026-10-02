# -*- coding: utf-8 -*-
"""مرحله ۱۰ — حل موجودیت کانونی."""
from __future__ import annotations

from typing import List

import pandas as pd

from ..adapters.base import KEY_BL, KEY_ORDER
from ..dataio.logging_setup import log
from ..resolve.expert_roles import (coverage as expert_coverage,
                                    current_owner, resolve_roles)
from .base import ColumnSpec, GROUP_DETAIL, GROUP_MAIN, PipelineContext, Stage, register


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
        # R9: بارنامه هر ردیف مال همان ردیف است (ردیف‌های جمعیت به ازای هر بارنامه عباسی باز
        # می‌شوند). قبلاً «اولین بارنامه کارشناس» سفارش روی همه ردیف‌های آن سفارش می‌نشست و سه
        # بارنامه یک بارنامه شمرده می‌شد. بارنامه کارشناس فقط ردیف بی‌بارنامه را پر می‌کند.
        "CANONICAL_BL": ("شماره بارنامه", True,
                         [(KEY_BL, "abbasi"), ("MOGH_BL_NO", "moghavemat")]),
        "CANONICAL_ORDER": ("شماره سفارش", True,
                            [("MOGH_ORDER_REF", "moghavemat"), (KEY_ORDER, "abbasi")]),
        "CANONICAL_PART_NO": ("شماره فنی", True,
                              [("MOGH_MATERIAL", "moghavemat"),
                               ("MOGH_MFR_PART_NO", "moghavemat"),
                               ("ORC_PART_NO", "oracle")]),
        "CANONICAL_GOODS_DESC": ("شرح کالا", False,
                                 [("MOGH_MATERIAL_DESC", "moghavemat"),
                                  ("ORC_MATERIAL_DESC", "oracle"),
                                  ("BL_GOODS_DESC", "abbasi"),
                                  ("CL_GOODS_DESC", "clearance"),
                                  ("SATA_GOODS_DESC", "sata")]),
        # ⚠️ «CANONICAL_EXPERT» دیگر اینجا ادغام نمی‌شود.
        # تا نسخه ۲۶٫۵ این ستون با «اولین مقدار غیرتهی» از پنج سورس پر
        # می‌شد و چون ORC_BUYER فقط ۱۷٪ پر است، نام **کارشناس ترخیص**
        # زیر عنوان «نام کارشناس» می‌نشست و عملکرد ترخیص به پای خرید
        # نوشته می‌شد. حالا هر نقش ستون مستقل دارد و مالکِ مرحله فعلی
        # همراه با نامِ نقشش گزارش می‌شود.
        # → gsi/resolve/expert_roles.py
        # ⚠️ کلید ثبت سفارش ۸ رقمی است و «شماره پرونده ثبت سفارش» (۹ رقمی)
        # نیست. از V29.7.3 شاهد NTSW در تعارض‌ها اولویت درجه‌اول دارد؛
        # SATA همچنان پل فنی مهم BL↔ORDER↔REG برای flat mart است.
        "CANONICAL_REG": ("ثبت سفارش", True,
                          [("NTSW_KEY_REG", "ntsw"),
                           ("SATA_KEY_REG", "sata"),
                           ("FX_KEY_REG", "fx_transaction"),
                           ("CRD_KEY_REG", "credit"),
                           ("IL_KEY_REG", "ilappend")]),
    }

    #: ستون‌هایی که مقدارشان مال خود ردیف است و ترتیب نامزدها (نه درجه اعتبار سورس) تعیین‌کننده است.
    ROW_OWNED = frozenset({"CANONICAL_BL"})

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        for target, (label, is_key, candidates) in self.MAP.items():
            df[target] = ctx.resolver.resolve(df, label, candidates, is_key=is_key,
                                              keep_order=(target in self.ROW_OWNED))

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
            # Order grain can legitimately contain several expert material lines.
            # Never let the compatibility/first material impersonate the whole order:
            # publish the preserved lineage next to it in every official matrix.
            ColumnSpec("MOGH_MATERIALS_ALL", "همه کدهای متریال ثبت‌شده کارشناسان در سفارش", 44,
                       GROUP_DETAIL, order=23, wrap=True),
            ColumnSpec("MOGH_KEY_MATERIAL_COUNT", "تعداد کدهای متریال کارشناسان در سفارش", 17,
                       GROUP_DETAIL, order=24),
            ColumnSpec("MOGH_MATERIAL_DESCS_ALL", "همه شرح‌های ثبت‌شده کارشناسان در سفارش", 48,
                       GROUP_DETAIL, order=25, wrap=True),
            ColumnSpec("MOGH_MATERIAL_DESC_COUNT", "تعداد شرح‌های کارشناسان در سفارش", 17,
                       GROUP_DETAIL, order=26),
        ]
