# -*- coding: utf-8 -*-
"""سورس‌های گمرکی: ترخیص و کوتاژ."""
from __future__ import annotations

__contract__ = 1

from typing import Dict

import pandas as pd

from ..core.text import is_empty_val, normalize_persian_text, num_safe
from ..dataio.logging_setup import log
from ..rulebook import get_rulebook
from .base import SourceAdapter, register

#: در فایل‌های ترخیص، «ترخیص کامل» و «ترخیص درصدی» تاریخ نیستند بلکه علامت‌اند
_FLAG_MARKS = {"*", "✓", "√", "x", "X", "بله", "yes", "دارد"}


def _is_flagged(v) -> bool:
    s = normalize_persian_text(v).strip()
    return bool(s) and (s in _FLAG_MARKS or s.startswith("*"))


@register
class ClearanceAdapter(SourceAdapter):
    """ترخیص گمرکی — چهار فایل با شیت‌های هم‌نام خودشان.

    ⚠️ سه اصلاح نسبت به نسخه قبل:
      ۱ شیت «Clearance Report» اصلاً وجود ندارد؛ هر فایل شیت خودش را دارد
        (Sea/Air/Land/chabaharClearance) → استراتژی all_data_sheets.
      ۲ «ترخیص کامل» و «ترخیص درصدی» ستون علامت‌اند («*») نه تاریخ.
        تاریخ واقعی در «تاریخ بارگیری» است.
      ۳ ستون «تعرفه» کد تعرفه گمرکی واقعی است (87085032) و جایگزین
        حدس‌زدن HS از شرح کالا می‌شود.
    """
    key, prefix = "clearance", "CL"

    COLUMN_MAP = {
        "FILE_NO":        ["پرونده ترخیص"],
        "GOODS_DESC":     ["شرح کالا"],
        "TRANSPORT_MODE": ["نوع حمل"],
        "REF_DATE":       ["تاریخ ارجاع"],
        "EXPERT":         ["کارشناس ترخیص"],
        "COTAGE_DATE":    ["تاریخ  دریافت شماره کوتاژ", "تاریخ دریافت شماره کوتاژ"],
        "COTAGE_NO":      ["کوتاژ"],
        "LICENSE_DATE":   ["تاریخ صدور پروانه"],
        "CURRENCY":       ["نوع ارز"],
        "INVOICE_VALUE":  ["ارزش فاکتور"],
        "EUR_VALUE":      ["ارزش یورویی"],
        "RIAL_VALUE":     ["ارزش ریالی"],
        "HS_CODE":        ["تعرفه"],
        "DUTY_RATE":      ["ماخذ"],
        "DUTY_AMOUNT":    ["مبلغ حقوق و عوارض گمرکی"],
        "DUTY_DATE":      ["تاریخ حقوق و عوارض گمرکی"],
        "PARTIAL_FLAG":   ["ترخیص درصدی"],
        "FULL_FLAG":      ["ترخیص کامل"],
        "LOAD_DATE_1":    ["تاریخ بارگیری 1", "_تاریخ بارگیری1_", "_تاریخ بارگیری_"],
        # چهار فایل ترخیص، چهار نام متفاوت برای همین یک مفهوم:
        #   Sea            → «تاریخ بارگیری 6 (کامل)»
        #   Air            → «تاریخ بارگیری»
        #   Land/chabahar  → «_ تاریخ بارگیری نهایی_»
        # نرمال‌سازی نام ستون زیرخط و فاصله اضافی را حذف می‌کند تا هر چهار
        # شکل به یک کلید برسند.  «تاریخ بارگیری 1» عمداً اینجا نیست:
        # بارگیری مرحله ۱ ترخیص کامل نیست و اگر جایگزینش شود، لیدتایم
        # بی‌صدا اشتباه می‌شود.
        "LOAD_DATE_FINAL": ["تاریخ بارگیری 6 (کامل)", "تاریخ بارگیری نهایی",
                            "تاریخ بارگیری"],
        "DAMAGE_PCT":     ["درصد آسیب دیده"],
        "NOTE":           ["توضیحات"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None or df.empty:
            return {}
        p = self.p
        out = self.std(df, self.COLUMN_MAP)
        self.add_bl_key(out, df, ["بارنامه", "شماره بارنامه"])
        self.add_order_key(out, df, ["شماره سفارش", "سفارش"])

        for f in ("INVOICE_VALUE", "EUR_VALUE", "RIAL_VALUE", "DUTY_AMOUNT", "DUTY_RATE"):
            out[p(f)] = out[p(f)].map(num_safe)

        # ── پرچم‌های ترخیص ──
        out[p("IS_FULL")] = out[p("FULL_FLAG")].map(_is_flagged)
        out[p("IS_PARTIAL")] = out[p("PARTIAL_FLAG")].map(_is_flagged)
        # تاریخ مؤثر ترخیص = آخرین تاریخ بارگیری موجود
        # توکن «*» یعنی «انجام شده ولی تاریخ ثبت نشده» — نه تهی، نه تاریخ.
        # اگر تاریخ واقعی نبود، ستون خالی می‌ماند و پرچم جدا ثبت می‌شود تا
        # عدد جعلی وارد محاسبه لیدتایم نشود.
        def _real_date(v: Any) -> str:
            s_ = str(v).strip()
            return "" if (is_empty_val(v) or s_.startswith("*")) else s_

        fin = out[p("LOAD_DATE_FINAL")].map(_real_date)
        out[p("CLEAR_DATE")] = fin
        out[p("CLEAR_DONE_NO_DATE")] = [
            bool(full) and not d
            for full, d in zip(out[p("IS_FULL")], fin)]
        n_nodate = int(sum(out[p("CLEAR_DONE_NO_DATE")]))
        if n_nodate:
            log.info(f"   🕗 [clearance] {n_nodate} ردیف «ترخیص کامل بدون تاریخ» "
                     f"— ستون تاریخ خالی ماند تا لیدتایم جعلی نشود.")

        # ── کد تعرفه واقعی (به‌جای استنتاج از شرح کالا) ──
        out[p("HS_CODE")] = out[p("HS_CODE")].map(
            lambda v: "" if is_empty_val(v) else str(int(num_safe(v))) if num_safe(v) > 0 else "")

        # ── روش حمل از rulebook ──
        rb = get_rulebook()
        out[p("TRANSPORT_MODE_CODE")] = out[p("TRANSPORT_MODE")].map(rb.transport_mode)

        if "_SOURCE_SHEET" in df.columns:
            out[p("SOURCE_SHEET")] = df["_SOURCE_SHEET"]

        n_full = int(out[p("IS_FULL")].sum())
        n_part = int(out[p("IS_PARTIAL")].sum())
        log.info(f"   🛃 [clearance] {len(out)} ردیف — {n_full} ترخیص کامل، "
                 f"{n_part} ترخیص درصدی، "
                 f"{int(out[p('HS_CODE')].ne('').sum())} کد تعرفه")
        return {"main": out}


@register
class CotageAdapter(SourceAdapter):
    """کوتاژ گمرکی — شامل درصد ترخیص، مرز ورودی و وضعیت ترانزیت."""
    key, prefix = "cotage", "COT"

    COLUMN_MAP = {
        "STATUS":          ["وضعیت"],
        "INVOICE_VALUE":   ["ارزش فاکتور"],
        "EUR_VALUE":       ["معادل یورویی"],
        "PACK_COUNT":      ["تعداد بسته بندی"],
        "PACK_TYPE":       ["نوع بسته بندی"],
        "TRANSIT_STATUS":  ["وضعیت ترانزیت"],
        "EXPERT":          ["کارشناس ترخیص", "کارشناس"],
        "ENTRY_BORDER":    ["مرز ورودی"],
        "DEST_CUSTOMS":    ["گمرک مقصد"],
        "DOC_DATE":        ["تاریخ دریافت اسناد جهت اظهار گمرکی از اعتبارات"],
        "COTAGE_DATE":     ["تاریخ دریافت شماره کوتاژ"],
        "NO":              ["کوتاژ"],
        "PARTIAL_PCT_1":   ["درصد ترخیص 1"],
        "PARTIAL_DATE_1":  ["تاریخ درصد ترخیص 1"],
        "PARTIAL_PCT_2":   ["درصد ترخیص 2"],
        "PARTIAL_DATE_2":  ["تاریخ درصد ترخیص 2"],
        "ABANDONED_DATE":  ["تاریخ متروکه"],
        "FULL_CLEAR_DATE": ["تاریخ ترخیص کامل"],
        "NOTE":            ["توضیحات"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None:
            return {}
        p = self.p
        out = self.std(df, self.COLUMN_MAP)
        self.add_bl_key(out, df, ["بارنامه", "شماره بارنامه"])
        for f in ("INVOICE_VALUE", "EUR_VALUE"):
            out[p(f)] = out[p(f)].map(num_safe)
        out[p("IS_ABANDONED")] = ~out[p("ABANDONED_DATE")].map(is_empty_val)
        return {"main": out}
