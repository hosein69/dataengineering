# -*- coding: utf-8 -*-
"""جدول پایه — BLs Tracking (۲۳ ستون واقعی).

هدرهای واقعی: بارنامه | وضعیت | _شرح کالا_ | شماره سفارش | نوع سفر |
کانتینر20 | کانتینر40 | شماره سفر | نام کشتی | تاریخ تخلیه |
تاریخ تحویل بارنامه | تاریخ آزاد سازی | تاریخ دریافت ترخیصیه |
تاریخ دریافت قبض انبار | وضعیت حمل
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict

import pandas as pd

from ..core.text import clean_part_no, is_empty_val
from ..rulebook import get_rulebook
from .base import SourceAdapter, register


@register
class AbbasiAdapter(SourceAdapter):
    key, prefix = "abbasi", "BL"

    COLUMN_MAP = {
        "STATUS":            ["وضعیت"],
        "GOODS_DESC":        ["_شرح کالا_", "شرح کالا"],
        "TRIP_MODE":         ["نوع سفر"],
        "CONTAINER_20":      ["کانتینر20", "کانتینر 20"],
        "CONTAINER_40":      ["کانتینر40", "کانتینر 40"],
        "VOYAGE_NO":         ["شماره سفر"],
        "VESSEL":            ["نام کشتی"],
        "DISCHARGE_DATE":    ["تاریخ تخلیه"],
        "BL_DELIVERY_DATE":  ["تاریخ تحویل بارنامه"],
        "RELEASE_DATE":      ["تاریخ آزاد سازی"],
        "DO_DATE":           ["تاریخ دریافت ترخیصیه"],
        "WAREHOUSE_RECEIPT": ["تاریخ دریافت قبض انبار"],
        "SHIP_STATUS":       ["وضعیت حمل"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None:
            return {}
        out = self.std(df, self.COLUMN_MAP, exclude=["توضیح"])
        self.add_bl_key(out, df, ["بارنامه", "شماره بارنامه"])
        self.add_order_key(out, df, ["شماره سفارش", "سفارش"])

        # روش حمل در BLs Tracking با «نوع سفر» ثبت می‌شود؛ اگر این مقدار
        # خالی باشد، از «وضعیت حمل» و در صورت امکان از نام شیت/فایل به‌عنوان
        # سرنخ استفاده می‌کنیم. این ستون باید پیش از merge به یک کد پایدار
        # تبدیل شود تا فیلتر Studio وابسته به نام خام سورس نباشد.
        rb = get_rulebook()
        mode = out[self.p("TRIP_MODE")].map(rb.transport_mode)
        ship = out[self.p("SHIP_STATUS")].map(rb.transport_mode)
        mode = mode.where(mode.astype(str).str.strip() != "", ship)
        if "_SOURCE_SHEET" in df.columns:
            sheet_mode = df["_SOURCE_SHEET"].map(
                lambda x: rb.transport_mode(x) if not is_empty_val(x) else "")
            mode = mode.where(mode.astype(str).str.strip() != "", sheet_mode)
        if "_SOURCE_FILE" in df.columns:
            file_mode = df["_SOURCE_FILE"].map(
                lambda x: rb.transport_mode(x) if not is_empty_val(x) else "")
            mode = mode.where(mode.astype(str).str.strip() != "", file_mode)
        out[self.p("TRIP_MODE_CODE")] = mode
        return {"main": out}
