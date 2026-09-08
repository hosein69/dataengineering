# -*- coding: utf-8 -*-
"""پوشش سفارش در «Commercial Expert Data».

این ماژول فقط **پوشش سورس** را اندازه می‌گیرد و هیچ کارشناس خریدی را حدس
نمی‌زند.

## باگی که اینجا رفع شد

نسخه ۲۶٫۹ وقتی سورس اصلاً بارگذاری نشده بود (مسیر شبکه در دسترس نبود،
فایل قفل بود، الگوی نام عوض شده بود) مجموعه مرجع را **خالی** می‌گرفت و
نتیجه‌اش این بود که *همه* سفارش‌ها «خارج از Commercial Expert Data» علامت
می‌خوردند. روی داده واقعی همین اتفاق افتاد: ۶ سفارش از ۶ سفارش پرچم
گرفتند و KPI مدیریتی گفت هیچ قطعه‌ای مالک ندارد.

این بدترین نوع خطاست: یک قطعیِ زیرساختی به شکل یک فاجعه سازمانی گزارش
می‌شود. یک بار که چنین چیزی در گزارش روزانه بیاید، دفعه بعد کسی به پرچم
اعتماد نمی‌کند.

قاعده درست: **نبود سورس ≠ نبود سفارش در سورس.** اگر مرجع در دسترس نیست،
وضعیت «سنجش‌نشده» است، نه «مفقود».
"""
from __future__ import annotations

__contract__ = 2

from typing import Optional, Tuple

import pandas as pd

from ..core.text import clean_order_ref
from ..dataio.logging_setup import log

FLAG = "ORDER_MISSING_COMMERCIAL_EXPERT"
PRESENT = "COMMERCIAL_EXPERT_SOURCE_PRESENT"
REASON = "ORDER_MISSING_COMMERCIAL_REASON"
#: وضعیت سنجش: measured | source_unavailable
STATE = "COMMERCIAL_COVERAGE_STATE"

MEASURED, UNAVAILABLE = "measured", "source_unavailable"

_REASON_MISSING = ("این سفارش در Commercial Expert Data درج نشده است؛ "
                   "بنابراین کارشناس خرید از این سورس قابل انتساب نیست.")
_REASON_UNKNOWN = ("سورس Commercial Expert Data در این اجرا بارگذاری نشد؛ "
                   "پوشش سنجیده نشده است (این به معنای نبودِ سفارش نیست).")


def _reference(mogh_lines: Optional[pd.DataFrame]) -> set:
    """مجموعه شماره سفارش‌های موجود در سورس خرید."""
    out: set = set()
    if mogh_lines is None or mogh_lines.empty:
        return out
    for col in ("KEY_ORDER", "MOGH_ORDER_REF", "MOGH_ORDER_BASE"):
        if col not in mogh_lines.columns:
            continue
        vals = mogh_lines[col].map(clean_order_ref).astype(str).str.strip()
        out.update(x for x in vals if x)
        if out:
            break
    return out


def annotate(main: pd.DataFrame,
             mogh_lines: Optional[pd.DataFrame]) -> Tuple[pd.DataFrame, int]:
    """پرچم پوشش را اضافه می‌کند و تعداد سفارش‌های واقعاً مفقود را برمی‌گرداند."""
    out = main.copy()
    source = _reference(mogh_lines)

    orders = (out["CANONICAL_ORDER"].map(clean_order_ref).astype(str).str.strip()
              if "CANONICAL_ORDER" in out.columns
              else pd.Series("", index=out.index, dtype=object))

    if not source:
        # مرجع نداریم ⇒ چیزی سنجیده نشده. هیچ پرچمی روشن نمی‌شود.
        out[PRESENT] = False
        out[FLAG] = False
        out[STATE] = UNAVAILABLE
        out[REASON] = ""
        out.loc[orders.ne(""), REASON] = _REASON_UNKNOWN
        log.warning("⚠️ سورس «Commercial Expert Data» در دسترس نبود؛ پوشش سفارش "
                    "سنجیده نشد. هیچ سفارشی به‌غلط «بدون مالک» علامت نخورد.")
        return out, 0

    present = orders.map(lambda x: bool(x) and x in source)
    missing = orders.ne("") & ~present
    out[PRESENT] = present
    out[FLAG] = missing
    out[STATE] = MEASURED
    out[REASON] = ""
    out.loc[missing, REASON] = _REASON_MISSING
    count = int(orders[missing].nunique())
    log.info(f"🧾 پوشش Commercial Expert Data سنجیده شد — {count} سفارش یکتا "
             f"خارج از سورس، از {int(orders.ne('').sum())} ردیف دارای سفارش.")
    return out, count


def measured(df: pd.DataFrame) -> bool:
    """آیا پوشش در این اجرا واقعاً سنجیده شده است؟"""
    if STATE not in df.columns or df.empty:
        return False
    return bool((df[STATE] == MEASURED).any())


def kpi(df: pd.DataFrame, count: int) -> tuple:
    """KPI مدیریتی — «سنجیده نشد» را از «صفر» جدا نگه می‌دارد."""
    if measured(df):
        return (count, "سفارش موجود در جریان اصلی ولی درج‌نشده در سورس "
                       "کارشناسان خرید؛ بدون انتساب کارشناس خرید")
    return ("سنجیده نشد", "سورس Commercial Expert Data در این اجرا بارگذاری نشد")
