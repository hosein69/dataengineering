# -*- coding: utf-8 -*-
"""موتور تقویم شمسی/میلادی — پورت مستقیم از ``aibl/core/jalali.py``.

تاریخ‌های سورس‌های زنجیره تأمین شمسی‌اند. اگر «۱۴۰۵/۰۱/۲۹» را با
``pd.to_datetime`` بخوانید، سال ۱۴۰۵ **میلادی** تفسیر می‌شود و اختلاف
تاریخ‌ها به صدها هزار روز می‌رسد — این باگ یک‌بار در AIBL دیده و رفع شد
و برای اینکه دوباره از راه دیگری وارد نشود، همان موتور اینجا هم به‌کار
می‌رود، نه یک پیاده‌سازی موازی.

الگوریتم تبدیل: Behrooz Parhami. اگر ``jdatetime`` نصب باشد از آن
استفاده می‌شود، وگرنه مبدل داخلی — تا روی سرور بدون اینترنت هم کار کند.
"""
from __future__ import annotations

__contract__ = 1

import math
from datetime import date, datetime
from typing import Any, Optional

try:  # pragma: no cover
    import jdatetime  # type: ignore
    HAS_JDATETIME = True
except ImportError:  # pragma: no cover
    HAS_JDATETIME = False

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _is_nan(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float):
        return math.isnan(v)
    try:
        return v != v  # noqa: PLR0124
    except Exception:
        return False


def to_latin_digits(s: Any) -> str:
    return "" if _is_nan(s) else str(s).translate(_DIGIT_MAP)



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
