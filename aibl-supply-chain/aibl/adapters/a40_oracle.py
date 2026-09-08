# -*- coding: utf-8 -*-
"""Oracle — متریال، موجودی و نیاز روزانه. مبنای محاسبه مقاومت قطعه.

هدرهای واقعی (۲۱ ستون، Total_Report):
شماره فني | کد جنس | شرح جنس | گروه تامين | گروه ساخت | گروه برنامه ريزي |
گروه قطعه | رده بندي قطعه | درصد سهم خريد خارجي | وضعيت | قطعه بحراني |
کد آلترناتيو | شماره نامه | تاريخ ثبت | توضيحات | شماره پرسنلي |
کارشناس خريد خارجي | موجودي انبار ايران خودرو | موجودي انبار ساپکو |
تعداد خودرو کف | نياز روزانه قطعات

⚠️ دو نکته که در HEADERS_MAP تأیید شد:
  • ستون «قطعه بحراني» **صفر درصد پر است** — پس بحرانی بودن باید محاسبه شود،
    نه خوانده. نسخه قبل دنبال ستون آماده «مقاومت» می‌گشت که اصلاً وجود ندارد.
  • این فایل بارنامه ندارد؛ نقش «وضعیت بارنامه» که قبلاً به Oracle نسبت داده
    شده بود، اشتباه بود و حذف شد.

Oracle همچنین «شماره پرسنلي» و «کارشناس خريد خارجي» دارد (۱۷٪ پر) که مسیر
دومی برای اتصال به HR است، در سطح قطعه به‌جای سطح سفارش.
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict

import pandas as pd

from ..core.text import clean_employee_code, num_safe
from ..dataio.logging_setup import log
from .base import KEY_MATERIAL, SourceAdapter, register


@register
class OracleAdapter(SourceAdapter):
    key, prefix = "oracle", "ORC"

    COLUMN_MAP = {
        "PART_NO":         ["شماره فني", "شماره فنی"],
        "MATERIAL_CODE":   ["کد جنس"],
        "MATERIAL_DESC":   ["شرح جنس"],
        "SUPPLY_GROUP":    ["گروه تامين", "گروه تامین"],
        "BUILD_GROUP":     ["گروه ساخت"],
        "PLANNING_GROUP":  ["گروه برنامه ريزي", "گروه برنامه ریزی"],
        "PART_GROUP":      ["گروه قطعه"],
        "PART_CLASS":      ["رده بندي قطعه", "رده بندی قطعه"],
        "FOREIGN_SHARE":   ["درصد سهم خريد خارجي", "درصد سهم خرید خارجی"],
        "STATUS":          ["وضعيت", "وضعیت"],
        "CRITICAL_FLAG":   ["قطعه بحراني", "قطعه بحرانی"],
        "ALTERNATIVE":     ["کد آلترناتيو", "کد آلترناتیو"],
        "REGISTER_DATE":   ["تاريخ ثبت", "تاریخ ثبت"],
        "EMP_CODE":        ["شماره پرسنلي", "شماره پرسنلی"],
        "BUYER":           ["کارشناس خريد خارجي", "کارشناس خرید خارجی"],
        "STOCK_IKCO":      ["موجودي انبار ايران خودرو", "موجودی انبار ایران خودرو"],
        "STOCK_SAPCO":     ["موجودي انبار ساپکو", "موجودی انبار ساپکو"],
        "CARS_ON_FLOOR":   ["تعداد خودرو کف"],
        "DAILY_NEED":      ["نياز روزانه قطعات", "نیاز روزانه قطعات", "نیاز روزانه"],
    }

    #: بدون این‌ها مقاومت قابل محاسبه نیست
    ESSENTIAL = ["STOCK_IKCO", "STOCK_SAPCO", "DAILY_NEED"]

    NUMERIC = ["STOCK_IKCO", "STOCK_SAPCO", "CARS_ON_FLOOR", "DAILY_NEED",
               "FOREIGN_SHARE"]

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None or df.empty:
            return {}
        p = self.p
        out = self.std(df, self.COLUMN_MAP, exclude=["توضیح"])
        for f in self.NUMERIC:
            out[p(f)] = out[p(f)].map(num_safe)
        out[p("EMP_CODE")] = out[p("EMP_CODE")].map(clean_employee_code)

        # کلید متریال از «شماره فني» — همان قالبی که ستون Material فایل مقاومت دارد
        self.add_material_key(out, df, ["شماره فني", "شماره فنی"])

        self._report(df, out)
        return {"main": self._aggregate(out)}

    # ── گزارش صریح پوشش ستون‌های حیاتی ──
    def _report(self, df: pd.DataFrame, out: pd.DataFrame) -> None:
        from ..core.columns import find_col
        p = self.p
        missing = []
        for f in self.ESSENTIAL:
            col = find_col(df, self.COLUMN_MAP[f], exclude=["توضیح"])
            (missing.append(f) if col is None
             else log.info(f"   ✅ [oracle] «{f}» ← «{col}»"))
        if missing:
            log.critical(
                "🚨 [oracle] ستون‌های " + " و ".join(missing) + " یافت نشد ⇒ "
                "مقاومت محاسبه نمی‌شود.\n"
                f"   ستون‌های موجود: {list(df.columns)[:25]}")
            return
        need = out[p("DAILY_NEED")].astype(float)
        log.info(f"   📦 [oracle] {len(out)} ردیف متریال | "
                 f"{int((need > 0).sum())} قطعه با نیاز روزانه > ۰ | "
                 f"جمع موجودی IKCO {out[p('STOCK_IKCO')].sum():,.0f} + "
                 f"ساپکو {out[p('STOCK_SAPCO')].sum():,.0f}")

    # ── یک ردیف به ازای هر متریال ──
    def _aggregate(self, out: pd.DataFrame) -> pd.DataFrame:
        p = self.p
        out = out[out[KEY_MATERIAL].astype(str).str.strip() != ""]
        if out.empty:
            log.warning("   ⚠️ [oracle] هیچ متریال با کلید معتبر نبود.")
            return out
        n0 = len(out)
        agg = {}
        for c in out.columns:
            if c == KEY_MATERIAL:
                continue
            if c in (p("STOCK_IKCO"), p("STOCK_SAPCO"), p("CARS_ON_FLOOR")):
                agg[c] = "sum"       # موجودی چند انبار جمع می‌شود
            elif c == p("DAILY_NEED"):
                agg[c] = "max"       # نیاز روزانه تکرار می‌شود، جمع نمی‌شود
            else:
                agg[c] = "first"
        res = out.groupby(KEY_MATERIAL, as_index=False).agg(agg)
        if len(res) != n0:
            log.info(f"   🧮 [oracle] {n0} ردیف → {len(res)} متریال یکتا (موجودی جمع شد)")
        return res
