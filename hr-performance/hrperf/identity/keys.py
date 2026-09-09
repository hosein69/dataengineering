# -*- coding: utf-8 -*-
"""کلید فرد — یک قطعه کد، همه‌جا یکسان.

## چرا این ماژول لازم شد

کد پرسنلی در سورس‌های واقعی یک شکل ندارد. همان فرد در سه فایل مختلف
این‌طور نوشته می‌شود:

    GS-1234        در فایل واحد الف
    1234           در فایل واحد ب
    1234.0         وقتی اکسل ستون را عددی خوانده باشد
    GS‑۱۲۳۴        با ارقام فارسی و نیم‌فاصله
    gs-01234       با حرف کوچک و صفر ابتدایی

پیش از این نسخه، خط لوله فقط ``str.strip()`` می‌زد. یعنی این پنج شکل،
**پنج نفر جدا** بودند: امتیاز هر کس بین چند رکورد نصفه پخش می‌شد، نقشه
سازمانی به هیچ‌کدام نمی‌چسبید، و همه در «گروه همتای عمومی» می‌افتادند.
در سیستمی که قرار است دربارهٔ آدم‌ها تصمیم بگیرد، این یک اشکال فنی
نیست؛ اجحاف است — کسی که کدش در یک فایل با پیشوند نوشته شده، نصف
کارنامه‌اش گم می‌شود.

## قاعده

کلید متعارف = **ارقام کد، صفرچین‌شده تا ۸ رقم**. همان قاعده‌ای که
``aibl/core/text.py::clean_employee_code`` در پکیج زنجیره تأمین به‌کار
می‌برد؛ عمداً یکسان، تا خروجی این دو پکیج روی یک کلید به هم بخورند.

    GS-1234 → 00001234        1234.0 → 00001234        GS‑۱۲۳۴ → 00001234

## دو محافظ که AIBL ندارد و اینجا لازم بود

**۱) هیچ‌کس حذف نمی‌شود.** اگر رشته اصلاً رقم نداشته باشد (کلید اسمی،
مثل ``AHMADI``)، همان شکل پاک‌شده به‌عنوان کلید می‌ماند. حذف کردن یک
نفر به‌خاطر شکل کدش، بدترین حالت ممکن است.

**۲) ادغام بی‌صدا ممنوع.** اگر دو کد با **پیشوندهای متفاوت** به یک عدد
برسند (``GS-1234`` و ``IK-1234``)، ممکن است واقعاً دو نفر باشند. اینجا
ادغام می‌شود ولی **اعلام** می‌شود تا منابع انسانی تصمیم بگیرد. عددی که
از ادغام دو نفر ساخته شده باشد و کسی نداند، از نبودنش بدتر است.
"""
from __future__ import annotations

__contract__ = 1

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

#: ارقام فارسی و عربی → لاتین
_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

#: فاصله‌های نامرئی که کپی‌پیست از اکسل با خود می‌آورد
_INVISIBLE = {"‌": "", "‏": "", "‎": "", "\xa0": " ", "\t": " "}

#: طول متعارف کد پرسنلی — همان ۸ رقمِ پکیج زنجیره تأمین
KEY_WIDTH = 8

_LEADING = re.compile(r"^([^0-9]*)(\d+)")
_NON_ALNUM = re.compile(r"[^A-Z0-9]")


def _is_nan(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float):
        return math.isnan(v)
    try:
        return v != v  # noqa: PLR0124
    except Exception:
        return False


def clean_text(v: Any) -> str:
    """ارقام لاتین، بدون فاصله نامرئی، بدون فاصله اضافی، بزرگ."""
    if _is_nan(v):
        return ""
    s = str(v).translate(_DIGIT_MAP)
    for src, dst in _INVISIBLE.items():
        s = s.replace(src, dst)
    return re.sub(r"\s+", " ", s).strip().upper()


def key_prefix(v: Any) -> str:
    """پیشوند حرفی پیش از ارقام — «GS» در ``GS-1234``؛ وگرنه رشته خالی."""
    m = _LEADING.match(clean_text(v))
    return _NON_ALNUM.sub("", m.group(1)) if m else ""


def clean_person_key(v: Any) -> str:
    """کلید متعارف فرد. رشتهٔ خالی یعنی «کلیدی نبود»، نه «فرد بی‌ارزش»."""
    s = clean_text(v)
    if not s:
        return ""
    if s.endswith(".0"):          # اکسل ستون را عددی خوانده
        s = s[:-2]
    m = _LEADING.match(s)
    if not m:                     # کلید بدون رقم — دست‌نخورده می‌ماند
        return _NON_ALNUM.sub("", s)
    digits = m.group(2).lstrip("0") or "0"
    return digits.zfill(KEY_WIDTH) if len(digits) <= KEY_WIDTH else digits


def normalize_series(s: pd.Series) -> pd.Series:
    """ستون کلید را متعارف می‌کند (بدون تغییر شکل نمایشی)."""
    return s.map(clean_person_key).astype(str)


def display_code(values: pd.Series) -> str:
    """خواناترین شکلِ خامِ یک کلید — آنچه در گزارش دیده می‌شود.

    ترجیح با شکلی است که پیشوند دارد: کاربر «GS-1234» را می‌شناسد، نه
    «00001234» را. کلیدِ متعارف برای **اتصال** است، نه برای خواندن.
    """
    raw = [clean_text(v) for v in values if clean_text(v)]
    if not raw:
        return ""
    with_prefix = [r for r in raw if key_prefix(r)]
    pool = with_prefix or raw
    return sorted(pool, key=lambda x: (-len(x), x))[0]


def attach(df: pd.DataFrame, col: str = "person_key",
           raw_col: str = "person_code") -> pd.DataFrame:
    """کلید متعارف را می‌نشاند و شکل خام را برای نمایش نگه می‌دارد."""
    if col not in df.columns:
        return df
    out = df.copy()
    raw = out[col].map(clean_text)
    out[col] = normalize_series(out[col])
    if raw_col not in out.columns:
        out[raw_col] = raw
    else:
        keep = out[raw_col].map(clean_text)
        out[raw_col] = keep.where(keep.ne(""), raw)
    return out


def collisions(values) -> Dict[str, Set[str]]:
    """کلیدهایی که از چند شکل خامِ **با پیشوند متفاوت** ساخته شده‌اند.

    اختلاف صفر ابتدایی، ``.0`` اکسل، یا **نبودِ** پیشوند، همان فرد است و
    گزارش نمی‌شود: «GS-1234» و «1234» یعنی یک نفر که در یک فایل پیشوندش
    نوشته نشده. آنچه ابهام است، دو پیشوند **متفاوت** روی یک شماره است —
    ``GS-1234`` و ``IK-1234`` ممکن است دو نفر باشند.
    """
    seen: Dict[str, Set[str]] = {}
    prefixes: Dict[str, Set[str]] = {}
    for v in values:
        k = clean_person_key(v)
        if not k:
            continue
        seen.setdefault(k, set()).add(clean_text(v))
        pre = key_prefix(v)
        if pre:
            prefixes.setdefault(k, set()).add(pre)
    return {k: seen[k] for k, p in prefixes.items() if len(p) > 1}


def notes(values) -> List[str]:
    """هشدارهای خواندنی دربارهٔ کلیدها — برای نمایش در خروجی اجرا."""
    out: List[str] = []
    raw = [clean_text(v) for v in values]
    raw = [r for r in raw if r]
    if not raw:
        return out
    merged = len(set(raw)) - len({clean_person_key(r) for r in raw})
    if merged > 0:
        out.append(f"{merged:,} کد پرسنلی با شکل متفاوت (پیشوند، صفر ابتدایی "
                   "یا اعشار اکسل) به یک نفر نسبت داده شد — پیش‌تر هر شکل، "
                   "یک نفر جدا شمرده می‌شد.")
    col = collisions(raw)
    if col:
        sample = "، ".join(sorted(next(iter(col.values())))[:3])
        out.append(f"⚑ {len(col):,} شماره با **دو پیشوند متفاوت** دیده شد "
                   f"(مثل: {sample}) و یکی شمرده شد. اگر دو نفر جدا هستند، "
                   "این امتیاز اشتباه است — پیشوند را در سورس‌ها یکسان کنید.")
    return out
