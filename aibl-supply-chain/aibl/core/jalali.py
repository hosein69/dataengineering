# -*- coding: utf-8 -*-
"""موتور تقویم شمسی/میلادی.

بهبود نسبت به نسخه ۲۰.۱: وابستگی سخت به jdatetime حذف شد. اگر کتابخانه نصب
باشد از آن استفاده می‌شود، در غیر این صورت مبدل داخلی (الگوریتم Behrooz Parhami)
به کار می‌رود تا سیستم روی سرورهای بدون اینترنت هم کار کند.
"""
from __future__ import annotations

import re

#: نسخه قرارداد این ماژول — aibl/version.py آن را می‌سنجد.
#: با هر تغییر در رابط عمومی، این عدد یکی زیاد می‌شود.
__contract__ = 1


from datetime import date, datetime
from typing import Any, Optional

from .text import to_latin_digits, _is_nan

try:  # pragma: no cover
    import jdatetime  # type: ignore
    HAS_JDATETIME = True
except ImportError:  # pragma: no cover
    HAS_JDATETIME = False

def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    """تبدیل تاریخ شمسی به میلادی (الگوریتم استاندارد، بدون نیاز به jdatetime)."""
    if HAS_JDATETIME:
        return jdatetime.date(jy, jm, jd).togregorian()

    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    days += (jm - 1) * 31 if jm < 7 else ((jm - 7) * 30 + 186)

    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1

    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    months = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    for length in months:
        if gd <= length:
            break
        gd -= length
        gm += 1
    return date(gy, gm, gd)


def is_jalali_leap(jy: int) -> bool:
    """سال کبیسه شمسی بر پایه چرخه ۳۳ ساله."""
    return ((jy + 2346) % 2820) % 128 % 33 % 4 == 1


class CalendarEngine:
    """تشخیص خودکار تقویم و تبدیل به ``datetime.date``."""

    JALALI_MIN, JALALI_MAX = 1300, 1500
    GREGORIAN_MIN, GREGORIAN_MAX = 1900, 2100
    _SEPARATORS = ("/", "-", ".", "،")

    @classmethod
    def parse(cls, x: Any) -> Optional[date]:
        if _is_nan(x):
            return None
        if isinstance(x, datetime):
            return x.date()
        if isinstance(x, date):
            return x
        # pandas.Timestamp
        if hasattr(x, "to_pydatetime"):
            try:
                return x.to_pydatetime().date()
            except Exception:
                pass

        s = to_latin_digits(x).strip()
        if not s:
            return None
        s = s.split(" ")[0]  # حذف بخش ساعت

        sep = next((c for c in cls._SEPARATORS if c in s), None)
        if sep is None:
            # فرمت فشرده 14040315 یا 20260726
            if s.isdigit() and len(s) == 8:
                return cls._build(int(s[:4]), int(s[4:6]), int(s[6:]))
            return None

        parts = [p.strip() for p in s.split(sep) if p.strip()]
        if len(parts) < 3 or not all(p.isdigit() for p in parts[:3]):
            return None
        a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
        # فرمت معکوس روز/ماه/سال
        if a <= 31 and c >= 1300:
            a, b, c = c, b, a
        return cls._build(a, b, c)

    @classmethod
    def _build(cls, y: int, m: int, d: int) -> Optional[date]:
        try:
            if cls.JALALI_MIN <= y <= cls.JALALI_MAX:
                return jalali_to_gregorian(y, m, d)
            if cls.GREGORIAN_MIN <= y <= cls.GREGORIAN_MAX:
                return date(y, m, d)
        except Exception:
            return None
        return None

    @classmethod
    def days_between(cls, start: Any, end: Any) -> Optional[int]:
        d1, d2 = cls.parse(start), cls.parse(end)
        if d1 is None or d2 is None:
            return None
        return (d2 - d1).days


_DATE_TOKENS = re.compile(r"(\d{1,4})\D+(\d{1,2})\D+(\d{1,2})")


def jalali_sort_key(value: Any) -> str:
    """کلید مرتب‌سازی یکدست ``YYYY-MM-DD`` میلادی برای هر تاریخ ورودی.

    چرا لازم است — یک باگ فساد خاموش داده
    ────────────────────────────────────────
    در فایل‌های ترخیص، Sea تاریخ را «1403/12/13» می‌نویسد ولی Land «98/12/27».
    مرتب‌سازی رشته‌ای می‌گوید ``"98/…" > "1403/…"`` چون «۹» از «۱» بزرگ‌تر
    است. نتیجه: در هر برخورد بارنامه، رکورد پنج سال قدیمی‌تر **بی‌صدا**
    برندهٔ dedupe می‌شد و داده سالم را می‌خورد.

    قواعد:
      • سال دو رقمی: ``>= 50`` → قرن ۱۳ ، ``< 50`` → قرن ۱۴  (۹۸ → ۱۳۹۸)
      • همه‌چیز به میلادی تبدیل می‌شود تا شمسی و میلادی قابل مقایسه شوند
      • هر مقدار غیرقابل‌تفسیر ``"0000-00-00"`` می‌گیرد — یعنی **همیشه بازنده**.
        این عمدی است: مقدار خراب نباید داده سالم را کنار بزند.

    >>> jalali_sort_key("98/12/27") < jalali_sort_key("1403/01/01")
    True
    >>> jalali_sort_key("1403/1/5") == jalali_sort_key("1403/01/05")
    True
    >>> jalali_sort_key("*")
    '0000-00-00'
    """
    FAIL = "0000-00-00"
    if _is_nan(value):
        return FAIL
    s = to_latin_digits(str(value)).strip()
    if not s or s in ("*", "-", "—", "0"):
        return FAIL

    d = CalendarEngine.parse(s)
    if d:
        return d.isoformat()

    # سال دو رقمی که parse نشناخت: به چهار رقم بسط و دوباره تلاش
    m = _DATE_TOKENS.search(s)
    if not m:
        return FAIL
    y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y = 1300 + y if y >= 50 else 1400 + y
    if not (1200 <= y <= 1499 and 1 <= mo <= 12 and 1 <= dd <= 31):
        return FAIL
    d = CalendarEngine.parse(f"{y:04d}/{mo:02d}/{dd:02d}")
    return d.isoformat() if d else FAIL
