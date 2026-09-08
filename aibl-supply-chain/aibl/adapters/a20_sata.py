# -*- coding: utf-8 -*-
"""ساتا — مهم‌ترین پل سیستم.

تنها سورسی که «بارنامه» + «سفارش» + «ثبت سفارش ۸ رقمی» را کنار هم دارد.
کلید KEY_REG که کل لایه رفع تعهد ارزی (NTSW) و خرید ارز به آن وابسته است،
از همین‌جا ساخته می‌شود.

⚠️ اشتباه نسخه قبل: KEY_REG از «شماره پرونده ثبت سفارش» فایل IL گرفته می‌شد
که عددی ۹ رقمی و مفهوم دیگری است. نتیجه: NTSW با ۴۷۱۸ ردیف تعهد، صفر ردیف
منطبق داشت و «جمع مانده تعهد» صفر گزارش می‌شد.

هدرهای واقعی: بارنامه | ارزش فاکتور | سفارش | ثبت سفارش | دریافت اسناد |
عودت اسناد | تاریخ اخذ کد رهگیری | کد رهگیری | کد ابزار پرداخت |
وضعیت اعتبارات | بانک | _شرح کالا_ | _نوع ارز_ | محل تامین ارز |
روش پرداخت | کارشناس اعتبارات
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict

import pandas as pd

from ..core.text import clean_key, num_safe
from ..dataio.logging_setup import log
from .base import SourceAdapter, register


@register
class SataAdapter(SourceAdapter):
    key, prefix = "sata", "SATA"

    COLUMN_MAP = {
        "INVOICE_VALUE":   ["ارزش فاکتور"],
        "DOC_RECEIVED":    ["دریافت اسناد"],
        "DOC_RETURNED":    ["عودت اسناد"],
        "TRACKING_DATE":   ["تاریخ اخذ کد رهگیری"],
        "NO":              ["کد رهگیری"],
        "PAY_INSTRUMENT":  ["کد ابزار پرداخت"],
        "CREDIT_STATUS":   ["وضعیت اعتبارات"],
        "BANK":            ["بانک"],
        "GOODS_DESC":      ["_شرح کالا_", "شرح کالا"],
        "CURRENCY":        ["_نوع ارز_", "نوع ارز"],
        "FX_SOURCE":       ["محل تامین ارز"],
        "PAYMENT_METHOD":  ["روش پرداخت"],
        "CREDIT_EXPERT":   ["کارشناس اعتبارات"],
        "SENT_TO_BANK":    ["ارسال به بانک"],
        "CLOSED_DATE":     ["مختومه شدن"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None:
            return {}
        out = self.std(df, self.COLUMN_MAP, exclude=["توضیح"])
        out[self.p("INVOICE_VALUE")] = out[self.p("INVOICE_VALUE")].map(num_safe)
        self.add_bl_key(out, df, ["بارنامه", "شماره بارنامه"])
        self.add_order_key(out, df, ["سفارش", "شماره سفارش"])

        # ── کلید ثبت سفارش: ستون صریح «ثبت سفارش»، نه «شماره پرونده» ──
        from ..core.columns import find_col
        col = find_col(df, ["ثبت سفارش", "کد ثبت سفارش", "شماره ثبت سفارش"],
                       exclude=["پرونده", "تاریخ", "ارزش", "حالت", "کارمزد"])
        # ⚠️ با پیشوند، نه KEY_REG خام: این سورس روی «بارنامه» ادغام می‌شود و
        # موتور ادغام سایر کلیدها را حذف می‌کند تا تصادم نکنند. اگر کلید بدون
        # پیشوند نوشته شود، همین‌جا دور ریخته می‌شود و NTSW هرگز وصل نمی‌ماند.
        out[self.p("KEY_REG")] = df[col].map(clean_key) if col is not None else ""
        n = int(out[self.p("KEY_REG")].astype(str).str.strip().ne("").sum())
        log.info(f"   🔑 [sata] کلید ثبت سفارش از ستون «{col}» ساخته شد — "
                 f"{n} از {len(out)} ردیف "
                 f"({out[self.p('KEY_REG')].nunique()} کد یکتا)")
        return {"main": out}
