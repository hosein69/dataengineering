# -*- coding: utf-8 -*-
"""موتور تقویم شمسی/میلادی.

بهبود نسبت به نسخه ۲۰.۱: وابستگی سخت به jdatetime حذف شد. اگر کتابخانه نصب
باشد از آن استفاده می‌شود، در غیر این صورت مبدل داخلی (الگوریتم Behrooz Parhami)
به کار می‌رود تا سیستم روی سرورهای بدون اینترنت هم کار کند.
"""
from __future__ import annotations

import re

#: نسخه قرارداد این ماژول — gsi/version.py آن را می‌سنجد.
#: با هر تغییر در رابط عمومی، این عدد یکی زیاد می‌شود.
__contract__ = 2


from datetime import date, datetime
from typing import Any, Optional

from .text import to_latin_digits, _is_nan

try:  # pragma: no cover
    import jdatetime  # type: ignore
    HAS_JDATETIME = True
except ImportError:  # pragma: no cover
    HAS_JDATETIME = False

def jalali_month_length(jy: int, jm: int) -> int:
    """طول ماه شمسی؛ اسفند سال کبیسه ۳۰ روز است."""
    if not 1 <= jm <= 12:
        raise ValueError(f"ماه شمسی نامعتبر: {jm}")
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if is_jalali_leap(jy) else 29


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    """تبدیل تاریخ شمسی به میلادی (الگوریتم استاندارد، بدون نیاز به jdatetime).

    V29.9: تاریخ نامعتبر (ماه ۱۳، روز ۳۱ مهر، ۳۰ اسفند سال غیرکبیسه، ماه/روز
    صفر) ``ValueError`` می‌دهد. مبدل داخلی قبلاً این مقادیر را بی‌صدا به یک
    تاریخ واقعی دیگر «سرریز» می‌کرد (مثلاً ``1403/13/05 → 2025-03-25``)؛ یعنی
    نتیجه به نصب بودن یا نبودن jdatetime بستگی داشت.
    """
    if not 1 <= jd <= jalali_month_length(jy, jm):
        raise ValueError(f"تاریخ شمسی نامعتبر: {jy}/{jm}/{jd}")
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
    """سال کبیسه شمسی — سازگار با همان حساب ۳۳ ساله‌ای که مبدل استفاده می‌کند.

    نسخه قبلی فرمول چرخه ۲۸۲۰ ساله را داشت که ۱۴۰۳ را عادی و ۱۴۰۴ را کبیسه
    می‌دانست؛ در حالی که ۱۴۰۳/۱۲/۳۰ (= 2025-03-20) تاریخ واقعی است.
    کبیسه یعنی نوروز سال بعد یک روز دیرتر از ۳۶۵ روز می‌رسد.
    """
    return _jalali_day_number(jy + 1, 1, 1) - _jalali_day_number(jy, 1, 1) == 366


def _jalali_day_number(jy: int, jm: int, jd: int) -> int:
    """شماره روز خطی همان الگوریتم مبدل (بدون اعتبارسنجی)."""
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    days += (jm - 1) * 31 if jm < 7 else ((jm - 7) * 30 + 186)
    return days


def gregorian_to_jalali(value: date) -> tuple:
    """تبدیل میلادی به شمسی ``(jy, jm, jd)`` — معکوس دقیق ``jalali_to_gregorian``."""
    if HAS_JDATETIME:
        j = jdatetime.date.fromgregorian(date=value)
        return j.year, j.month, j.day
    jy = value.year - 621
    if value < jalali_to_gregorian(jy, 1, 1):
        jy -= 1
    start = jalali_to_gregorian(jy, 1, 1)
    offset = (value - start).days
    jm = 1
    while True:
        length = jalali_month_length(jy, jm)
        if offset < length:
            return jy, jm, offset + 1
        offset -= length
        jm += 1


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

        from .numeric_parse import strip_invisible
        s = strip_invisible(to_latin_digits(x)).strip()
        if not s:
            return None
        s = s.split(" ")[0]  # حذف بخش ساعت
        # ISO 8601 با ساعت: 2026-07-26T10:00:00 — بخش ساعت حذف می‌شود.
        if len(s) > 10 and s[10:11] in ("T", "t") and s[4:5] == "-":
            s = s[:10]

        sep = next((c for c in cls._SEPARATORS if c in s), None)
        if sep is None or (sep == "." and cls._EXCEL_SERIAL.fullmatch(s)):
            # فرمت فشرده 14040315 یا 20260726
            if s.isdigit() and len(s) == 8:
                return cls._build(int(s[:4]), int(s[4:6]), int(s[6:]))
            return cls._excel_serial(s)

        parts = [p.strip() for p in s.split(sep) if p.strip()]
        if len(parts) < 3 or not all(p.isdigit() for p in parts[:3]):
            return None
        a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
        # فرمت معکوس روز/ماه/سال
        if a <= 31 and c >= 1300:
            a, b, c = c, b, a
        return cls._build(a, b, c)

    #: سلول تاریخ واقعی Excel در مسیر OOXML خام (Oracle/FX/NTSW) به‌صورت
    #: شماره سریال (مثلاً «45371» یا «45371.5») می‌رسد، نه متن تاریخ. بازه
    #: 20000..80000 یعنی 1954-10-03 تا 2119-01-10؛ عدد خارج از آن تاریخ نیست.
    _EXCEL_SERIAL = re.compile(r"\d{5}(?:\.\d+)?")
    _EXCEL_EPOCH = date(1899, 12, 30)

    @classmethod
    def _excel_serial(cls, s: str) -> Optional[date]:
        if not cls._EXCEL_SERIAL.fullmatch(s):
            return None
        serial = float(s)
        if not 20000 <= serial <= 80000:
            return None
        from datetime import timedelta
        return cls._EXCEL_EPOCH + timedelta(days=int(serial))

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


# ═══════════ نمایش تاریخ برای کاربر ═══════════
#: جداکننده‌های ایزوله جهت (Unicode LRI/PDI). تاریخ «2026-08-31» داخل متن
#: راست‌به‌چپ بدون ایزوله به‌شکل «31-08-2026» دیده می‌شد (bidi reordering).
_LRI, _PDI = "⁦", "⁩"


def to_iso(value: Any) -> Optional[str]:
    """هر تاریخ پشتیبانی‌شده (شمسی/میلادی/سریال Excel) → ``YYYY-MM-DD`` یا None."""
    d = CalendarEngine.parse(value)
    return d.isoformat() if d else None


def format_jalali(value: Any) -> str:
    """``2026-08-31`` → ``1405/06/09``؛ مقدار نامعتبر بدون تغییر برمی‌گردد."""
    d = CalendarEngine.parse(value)
    if d is None:
        return "" if _is_nan(value) else str(value)
    jy, jm, jd = gregorian_to_jalali(d)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def date_label(value: Any, *, gregorian: bool = True) -> str:
    """برچسب تاریخ برای متن فارسی: شمسی، و میلادی داخل پرانتز؛ هر دو ایزوله.

    خروجی متن ساده است (بدون HTML) تا در Streamlit، HTML، Excel و ایمیل
    یکسان کار کند. ``date_label("2026-08-31")`` → «1405/06/09 (2026-08-31)».
    """
    d = CalendarEngine.parse(value)
    if d is None:
        return "" if _is_nan(value) else str(value)
    text = f"{_LRI}{format_jalali(d)}{_PDI}"
    if not gregorian:
        return text
    # WORD JOINER کنار خط‌تیره‌ها: در ستون باریک (سایدبار) تاریخ از وسط
    # «2026-08-31» به دو خط شکسته نشود؛ پرانتز داخل ایزوله تا آینه نشود.
    iso = d.isoformat().replace("-", "\u2060-\u2060")
    return f"{text} {_LRI}({iso}){_PDI}"
