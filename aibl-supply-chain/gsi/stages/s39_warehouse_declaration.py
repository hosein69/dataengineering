# -*- coding: utf-8 -*-
"""مرحله ۳۹ — اظهار انبار (سامانه جامع انبارها).

## شکافی که این مرحله می‌بندد

زنجیره شاهد یک محموله وارداتی با «ترخیص کامل» تمام نمی‌شود. کالا پس از
ترخیص باید در **سامانه جامع انبارها و مراکز نگهداری کالا** اظهار شود و قبض
انبار الکترونیکی بگیرد. تا V26.20، گزارش GSI درست همان‌جا ساکت می‌شد:
ستون ``WAREHOUSE_RECEIPT`` در فریم مبدأ (BLs Tracking) وجود داشت ولی هرگز
به فریم اصلی نمی‌رسید، پس آخرین حلقه زنجیره — «کالا الان کجاست» — در هیچ
خروجی دیده نمی‌شد.

## کاری که این مرحله **نمی‌کند**

حکم تخلف صادر نمی‌کند. مهلت قانونی اظهار بسته به نوع انبار، نوع کالا و
بخشنامه جاری فرق می‌کند و متن رسمی قابل استناد در اختیار این پکیج نبوده
است. پس ``warehouse.deadlines.*`` با ``status: needs_verification`` و
``automatic_apply: false`` ثبت شده و این مرحله فقط دو چیز می‌گوید:

    «قبض انبار هست یا نیست» — که واقعیتِ داده است
    «چند روز از ترخیص گذشته»  — که حساب است، نه قضاوت

آستانه‌ای که وضعیت را رنگ می‌کند (``warehouse.monitoring.*``) صریحاً
**آستانه پایش سازمانی** برچسب خورده، نه قاعده قانونی. اگر روزی متن رسمی
آرشیو شود، همان عدد در YAML ``verified`` می‌شود و این کد تغییر نمی‌کند.

## Unknown با Zero یکی نیست

ردیفی که تاریخ ترخیصش را نمی‌دانیم ``UNKNOWN`` می‌گیرد، نه «شکاف شاهد».
نبودِ داده اتهام نیست.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..core.jalali import CalendarEngine
from ..core.text import is_empty_val
from ..dataio.logging_setup import log
from .base import (ColumnSpec, FMT_DECIMAL, GROUP_ANALYTIC, GROUP_DETAIL,
                   PipelineContext, Stage, register)

#: ستون‌هایی که «تاریخ ترخیص» از آنها خوانده می‌شود، به ترتیب اولویت.
#:
#: ترخیص کامل قوی‌ترین شاهد است؛ اگر نبود ترخیص جزئی، و در نهایت تخلیه —
#: چون کالای تخلیه‌شده هم بالاخره باید سر از انبار دربیاورد.
#:
#: دو ستون آخر عمداً **پیشونددار** (مستقیم از سورس) هستند: در بسیاری از
#: پرونده‌ها ستون دامنه‌ای خالی است و تاریخ فقط در فریم مبدأ وجود دارد.
#: این‌ها به ``DERIVED`` اضافه نشدند چون ``DISCHARGE_DATE`` را مرحله ۲۰ برای
#: تشخیص «در راه بودن» می‌خواند و پر کردنش از منبع دیگر، طبقه‌بندی حمل را
#: بی‌صدا جابه‌جا می‌کرد. اینجا دامنه اثر محدود است و ``WH_CLEAR_BASIS``
#: می‌گوید تاریخ از کدام ستون آمده — پس هیچ‌چیز پنهان نمی‌ماند.
CLEAR_DATE_FIELDS = ("FULL_CLEAR_DATE", "COT_FULL_CLEAR_DATE",
                     "PARTIAL_CLEAR_DATE", "DISCHARGE_DATE", "BL_DISCHARGE_DATE")


def _dates(s: pd.Series) -> pd.Series:
    """ستون تاریخ (شمسی یا میلادی) → ``datetime64``، با یکتاسازی.

    همان الگوی مرحله ۳۸: ``CalendarEngine.parse`` روی مقادیر **یکتا** اجرا
    می‌شود، نه روی تک‌تک ردیف‌ها. ستون تاریخ در عمل چند صد مقدار متمایز
    دارد و نه چند صد هزار.
    """
    codes, uniq = pd.factorize(s, use_na_sentinel=False)
    lut = np.array([np.datetime64(d, "D") if (d := CalendarEngine.parse(u)) else
                    np.datetime64("NaT", "D") for u in uniq], dtype="datetime64[D]")
    return pd.Series(lut[codes], index=s.index).astype("datetime64[ns]")


@register
class WarehouseDeclarationStage(Stage):
    name = "warehouse_declaration"
    title = "اظهار انبار — قبض انبار الکترونیکی و شکاف شاهد پس از ترخیص"
    order = 39
    requires = ["WAREHOUSE_RECEIPT"]
    provides = [
        "WH_RECEIPT_DATE", "WH_DECLARED", "WH_CLEAR_DATE", "WH_CLEAR_BASIS",
        "WH_LAG_DAYS", "WH_AGE_DAYS", "WH_STATUS", "WH_STATUS_FA",
        "WH_GAP_REASON", "WH_RULE_BASIS",
    ]

    #: وضعیت → (برچسب فارسی، آهنگ رنگی در سیستم طراحی)
    STATE_TONE = {
        "DECLARED": "good", "LATE": "warning", "OVERDUE": "serious",
        "CRITICAL_GAP": "critical", "SEQUENCE_CONFLICT": "warning",
        "PENDING": "neutral", "NOT_CLEARED": "neutral", "UNKNOWN": "unknown",
    }

    def _labels(self, ctx: PipelineContext) -> Dict[str, str]:
        return {s["code"]: s.get("fa", s["code"])
                for s in (ctx.rb.get("warehouse.states", []) or [])}

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        rb = ctx.rb
        overdue = int(rb.get("warehouse.monitoring.receipt_overdue_days.value", 7))
        stale = int(rb.get("warehouse.monitoring.receipt_stale_days.value", 30))
        today = pd.Timestamp(ctx.today)

        receipt = _dates(df["WAREHOUSE_RECEIPT"]) if "WAREHOUSE_RECEIPT" in df.columns \
            else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")

        # ── مبنای ترخیص: اولین ستونی که مقدار دارد، با ثبت اینکه کدام بود ──
        clear = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
        basis = pd.Series("", index=df.index, dtype=object)
        for f in CLEAR_DATE_FIELDS:
            if f not in df.columns:
                continue
            d = _dates(df[f])
            take = clear.isna() & d.notna()
            clear = clear.where(~take, d)
            basis = basis.where(~take, f)

        declared = receipt.notna()
        lag = (receipt - clear).dt.days.where(declared & clear.notna())
        age = (today - clear).dt.days.where(~declared & clear.notna())

        status = pd.Series("UNKNOWN", index=df.index, dtype=object)
        status = status.mask(clear.isna() & ~declared, "NOT_CLEARED")
        status = status.mask(declared & (lag.isna() | (lag <= overdue)), "DECLARED")
        status = status.mask(declared & (lag > overdue), "LATE")
        status = status.mask(~declared & clear.notna() & (age <= overdue), "PENDING")
        status = status.mask(~declared & clear.notna() & (age > overdue), "OVERDUE")
        status = status.mask(~declared & clear.notna() & (age > stale), "CRITICAL_GAP")
        # قبض انبار پیش از ترخیص: یکی از دو تاریخ غلط است. اگر این را
        # «اظهار شده» بشماریم، مغایرت برای همیشه پنهان می‌ماند — و بدتر،
        # فاصله منفی وارد میانه‌ها می‌شود و آمار را مسموم می‌کند.
        status = status.mask(declared & lag.notna() & (lag < 0), "SEQUENCE_CONFLICT")

        labels = self._labels(ctx)
        reason = pd.Series("", index=df.index, dtype=object)
        reason = reason.mask(status.isin(["OVERDUE", "CRITICAL_GAP"]),
                             "ترخیص ثبت شده ولی قبض انبار در سامانه نیست")
        reason = reason.mask(status == "LATE",
                             "قبض انبار دیرتر از آستانه پایش ثبت شده است")
        reason = reason.mask(status == "UNKNOWN",
                             "تاریخ ترخیص در دسترس نیست؛ وضعیت اظهار قابل محاسبه نیست")
        reason = reason.mask(status == "SEQUENCE_CONFLICT",
                             "قبض انبار پیش از تاریخ ترخیص ثبت شده — دو تاریخ با هم نمی‌خوانند")

        # فاصله منفی هیچ‌جا به‌عنوان «مدت» گزارش نمی‌شود؛ خودش وضعیت دارد.
        lag = lag.where(status != "SEQUENCE_CONFLICT")

        df["WH_RECEIPT_DATE"] = receipt.dt.strftime("%Y-%m-%d").fillna("")
        df["WH_DECLARED"] = declared
        df["WH_CLEAR_DATE"] = clear.dt.strftime("%Y-%m-%d").fillna("")
        df["WH_CLEAR_BASIS"] = basis
        df["WH_LAG_DAYS"] = lag
        df["WH_AGE_DAYS"] = age
        df["WH_STATUS"] = status
        df["WH_STATUS_FA"] = status.map(labels).fillna(status)
        df["WH_GAP_REASON"] = reason
        df["WH_RULE_BASIS"] = (
            f"آستانه پایش سازمانی: شکاف پس از {overdue} روز، بحرانی پس از {stale} روز. "
            "مهلت قانونی اظهار needs_verification است و خودکار اعمال نمی‌شود."
        )

        ctx.extras["warehouse_declaration"] = self._ledger(df)

        counts = status.value_counts().to_dict()
        gaps = int(counts.get("OVERDUE", 0) + counts.get("CRITICAL_GAP", 0))
        log.info(
            f"🏭 [warehouse] اظهارشده {counts.get('DECLARED', 0)} | "
            f"با تأخیر {counts.get('LATE', 0)} | شکاف شاهد {gaps} | "
            f"تناقض تاریخ {counts.get('SEQUENCE_CONFLICT', 0)} | "
            f"در مهلت {counts.get('PENDING', 0)} | نامشخص {counts.get('UNKNOWN', 0)}"
            "؛ مهلت قانونی اعمال نشد (needs_verification)."
        )
        return df

    @staticmethod
    def _ledger(df: pd.DataFrame) -> pd.DataFrame:
        cols = [c for c in [
            "KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_REG",
            "WH_CLEAR_DATE", "WH_CLEAR_BASIS", "WH_RECEIPT_DATE", "WH_LAG_DAYS",
            "WH_AGE_DAYS", "WH_STATUS", "WH_STATUS_FA", "WH_GAP_REASON",
        ] if c in df.columns]
        if not cols:
            return pd.DataFrame()
        return df[cols].drop_duplicates().reset_index(drop=True)

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("WH_STATUS_FA", "وضعیت اظهار انبار", 18, GROUP_DETAIL, order=70),
            ColumnSpec("WH_RECEIPT_DATE", "تاریخ قبض انبار", 15, GROUP_DETAIL, order=71),
            ColumnSpec("WH_LAG_DAYS", "فاصله ترخیص تا قبض انبار (روز)", 18,
                       GROUP_ANALYTIC, fmt=FMT_DECIMAL, order=95),
            ColumnSpec("WH_AGE_DAYS", "عمر شکاف انبار (روز)", 16,
                       GROUP_ANALYTIC, fmt=FMT_DECIMAL, color_rule="scale_high_bad",
                       order=96),
            ColumnSpec("WH_GAP_REASON", "علت شکاف اظهار انبار", 40,
                       GROUP_ANALYTIC, wrap=True, order=97),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        if "WH_STATUS" not in df.columns:
            return {}
        st = df["WH_STATUS"]
        gap = int(st.isin(["OVERDUE", "CRITICAL_GAP"]).sum())
        out = {
            "شکاف شاهد انبار": (
                gap, "ترخیص ثبت شده، قبض انبار نه"),
            "اظهار انبار با تأخیر": (
                int((st == "LATE").sum()), "از آستانه پایش گذشته بود"),
        }
        conflict = int((st == "SEQUENCE_CONFLICT").sum())
        if conflict:
            out["تناقض تاریخ انبار"] = (
                conflict, "قبض انبار پیش از ترخیص ثبت شده")
        return out

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict[str, Any]]:
        overdue = ctx.rb.get("warehouse.monitoring.receipt_overdue_days.value", 7)
        stale = ctx.rb.get("warehouse.monitoring.receipt_stale_days.value", 30)
        return {"اظهار انبار (سامانه جامع انبارها)": {
            "مبنای ترخیص": "اولین مقدار موجود از FULL_CLEAR → PARTIAL_CLEAR → DISCHARGE",
            "فاصله اظهار": "تاریخ قبض انبار − تاریخ ترخیص",
            "عمر شکاف": "تاریخ مرجع − تاریخ ترخیص (فقط وقتی قبض انبار نیست)",
            "آستانه شکاف": f"{overdue} روز (پایش سازمانی، نه قاعده قانونی)",
            "آستانه بحرانی": f"{stale} روز",
            "مهلت قانونی": "needs_verification — خودکار اعمال نمی‌شود",
            "قاعده Unknown": "بدون تاریخ ترخیص → UNKNOWN، نه شکاف",
        }}
