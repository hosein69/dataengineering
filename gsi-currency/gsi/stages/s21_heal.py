# -*- coding: utf-8 -*-
"""مرحله ۲۱ — اعمال ترمیم‌هایی که یک انسان تأیید کرده است؛ نه بیشتر.

«خودترمیمی» در GSI یعنی این و فقط این: وقتی کسی یک ناهنجاری را دید، علتش را
فهمید و یک اصلاح مشخص را **با نام خودش و یک جمله دلیل** تأیید کرد، سامانه آن
اصلاح را از آن به بعد در هر اجرا خودش دوباره اعمال می‌کند. سامانه هیچ‌وقت
خودش تصمیم نمی‌گیرد که عددی غلط است.

چرا ترتیب ۲۱: بعد از مشتق‌سازی (۲۰) تا ستون‌های ورودی مثل ``DAILY_NEED`` و
``INVOICE_VALUE`` ساخته شده باشند، و **قبل از هر موتور محاسبه** (سازمان ۳۰،
موجودی ۳۸، مقاومت ۴۰، تعهد ۵۰) تا عدد اصلاح‌شده در همه محاسبات یکسان دیده
شود — نه اینکه یک گزارش عدد اصلاح‌شده و گزارش دیگر عدد خام را بگوید.

چرا tolerant: اگر خواندن دفتر پاسخ‌ها شکست بخورد، امن‌ترین رفتار «هیچ ترمیمی
اعمال نکن» است — داده خام، با همان علامت‌های اعتماد، نه داده حدسی.

بدون هیچ تأییدی، خروجی این مرحله دقیقاً همان ورودی است به‌اضافه ستون خالی
``HEALED_FIELDS``.
"""
from __future__ import annotations

from typing import List

import pandas as pd

from ..dataio.logging_setup import log
from ..trust.inquiry import (APPLIED_COLUMNS, STALE_COLUMNS, InquiryRegister,
                             apply_repairs)
from .base import ColumnSpec, GROUP_ANALYTIC, PipelineContext, Stage, register


def register_for(ctx: PipelineContext) -> InquiryRegister:
    """The answers to use for this run.

    ``ctx.extras['inquiry_decisions']`` (a list of plain dicts) overrides the
    warehouse — used by tests and by what-if runs, and JSON-safe so it survives
    ``report_metadata``.
    """
    injected = ctx.extras.get("inquiry_decisions")
    if injected is not None:
        return InquiryRegister.from_dicts(injected)
    return InquiryRegister.load()


@register
class ApprovedHealingStage(Stage):
    name = "approved_healing"
    title = "اعمال ترمیم‌های تأییدشده (فقط با تأیید انسانی)"
    order = 21
    tolerant = True
    requires: List[str] = []
    provides = ["HEALED_FIELDS"]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        approved = register_for(ctx).approved()
        df, applied, stale = apply_repairs(df, approved)
        ctx.extras["heal_applied"] = pd.DataFrame(applied, columns=APPLIED_COLUMNS)
        ctx.extras["heal_stale"] = pd.DataFrame(stale, columns=STALE_COLUMNS)
        if applied or stale:
            log.info(f"🩹 [healing] {len(applied)} ترمیم تأییدشده اعمال شد"
                     f" | {len(stale)} ترمیم دیگر با داده نمی‌خواند و اعمال نشد")
        return df

    def columns(self) -> List[ColumnSpec]:
        return [ColumnSpec("HEALED_FIELDS", "ترمیم تأییدشده (مقدار اصلی ← جدید)", 40,
                           GROUP_ANALYTIC, wrap=True, color_rule="flag_nonempty", order=123)]

    def math_docs(self, ctx: PipelineContext):
        return {"ترمیم با تأیید انسانی": {
            "قاعده": "هیچ مقداری بدون تأیید یک نفر با نام و یک جمله دلیل تغییر نمی‌کند.",
            "انقیاد": "ترمیم فقط تا وقتی اعمال می‌شود که سورس همان مقدار تأییدشده را دارد؛ "
                      "اگر مقدار عوض شود، ترمیم کنار می‌رود و سؤال دوباره پرسیده می‌شود.",
            "ردپا": "مقدار اصلی، مقدار جدید، تأییدکننده و تاریخ روی همان ردیف در HEALED_FIELDS می‌ماند.",
            "ممنوع": "کلیدها و اعداد محاسبه‌شده هرگز ترمیم نمی‌شوند.",
            "مرجع": "docs/DATA_STRATEGY_FA.md — بخش ناهنجاری‌ها",
        }}
