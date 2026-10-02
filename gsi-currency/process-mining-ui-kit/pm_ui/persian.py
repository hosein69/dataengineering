# -*- coding: utf-8 -*-
"""بومی‌سازی فارسی — ارقام، تقویم شمسی، و قالب پول تومان/ریال.

خالص پایتون و بدون وابستگی بیرونی (نه ``jdatetime``، نه هیچ بستهٔ دیگر) چون
محیط اجرا کاملاً آفلاین است (فقط فولدر شبکه + ایمیل اوتلوک سازمانی، بدون
دسترسی به سرور یا اینترنت). اگر ``jdatetime`` در محیطی نصب باشد استفاده
می‌شود، وگرنه مبدل داخلی (الگوریتم استاندارد تقویم جلالی) جایگزین می‌شود.
"""
from __future__ import annotations

__contract__ = 1

from datetime import date, datetime
from typing import Optional, Union

try:  # pragma: no cover - محیط ممکن است این بسته را نداشته باشد
    import jdatetime  # type: ignore
    _HAS_JDATETIME = True
except ImportError:  # pragma: no cover
    _HAS_JDATETIME = False

_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_EN_DIGITS = "0123456789"
_TO_FA = str.maketrans(_EN_DIGITS, _FA_DIGITS)
_TO_EN = str.maketrans(_FA_DIGITS, _EN_DIGITS)

FA_MONTHS = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)
FA_WEEKDAYS = ("دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه")


def to_fa_digits(value: object) -> str:
    """اعداد لاتین درون یک رشته را به ارقام فارسی برمی‌گرداند."""
    return str(value).translate(_TO_FA)


def to_en_digits(value: object) -> str:
    """ارقام فارسی/عربی را به لاتین برمی‌گرداند (برای پردازش عددی)."""
    return str(value).translate(_TO_EN).replace("٫", ".")


def fa_number(value: Union[int, float], *, decimals: int = 0) -> str:
    """عدد را با جداکنندهٔ هزارگان فارسی («،») و ارقام فارسی قالب‌بندی می‌کند.

    طبق درخواست سازمانی، جداکنندهٔ هزارگان کاماى فارسی (U+060C) است، نه
    ممیز انگلیسی — خروجی مستقیماً برای برچسب و کارت KPI آماده است.
    """
    try:
        n = float(value)
    except (TypeError, ValueError):
        return to_fa_digits(value)
    grouped = f"{n:,.{decimals}f}"
    grouped = grouped.replace(",", "،").replace(".", "٫")
    return to_fa_digits(grouped)


def fa_money(value: Union[int, float], *, unit: str = "تومان", decimals: int = 0) -> str:
    """قالب پولی سازمانی: عدد فارسی + جداکنندهٔ «،» + واحد (تومان/ریال)."""
    return f"{fa_number(value, decimals=decimals)} {unit}"


def fa_compact(value: Union[int, float], *, unit: str = "تومان") -> str:
    """قالب فشرده برای کارت KPI: ۱۲،۳۰۰،۰۰۰،۰۰۰ → «۱۲٫۳ میلیارد تومان»."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return f"{value} {unit}"
    sign = "-" if n < 0 else ""
    a = abs(n)
    if a >= 1_000_000_000_000:
        return f"{sign}{fa_number(a / 1_000_000_000_000, decimals=1)} همت {unit}".replace("همت", "هزار میلیارد")
    if a >= 1_000_000_000:
        return f"{sign}{fa_number(a / 1_000_000_000, decimals=1)} میلیارد {unit}"
    if a >= 1_000_000:
        return f"{sign}{fa_number(a / 1_000_000, decimals=1)} میلیون {unit}"
    return f"{sign}{fa_number(a, decimals=0)} {unit}"


def gregorian_to_jalali(g: date) -> tuple:
    """میلادی → (سال، ماه، روز) شمسی؛ بدون نیاز به کتابخانهٔ بیرونی.

    الگوریتم استاندارد تقویم جلالی (مرجع: کتابخانهٔ متن‌باز jdf/jalaali)،
    مبتنی بر شمارش روزهای سپری‌شده از یک مبدأ ثابت — دقیق برای بازهٔ
    کاربردی تقویم (سال‌های ۱۱۷۸ تا ۱۶۳۳ شمسی).
    """
    if _HAS_JDATETIME:  # pragma: no cover
        j = jdatetime.date.fromgregorian(date=g)
        return j.year, j.month, j.day

    gy, gm, gd = g.year, g.month, g.day
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    gy_ = gy - 1600
    gm_ = gm - 1
    gd_ = gd - 1

    g_day_no = 365 * gy_ + (gy_ + 3) // 4 - (gy_ + 99) // 100 + (gy_ + 399) // 400
    for i in range(gm_):
        g_day_no += g_days_in_month[i]
    if gm_ > 1 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        g_day_no += 1
    g_day_no += gd_

    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    jm = 0
    for i in range(11):
        if j_day_no >= j_days_in_month[i]:
            j_day_no -= j_days_in_month[i]
            jm += 1
        else:
            break
    jd = j_day_no + 1
    return jy, jm + 1, jd


def today_jalali_str(*, with_weekday: bool = True) -> str:
    """امروز به‌صورت «شنبه، ۴ مهر ۱۴۰۴» — برای سربرگ گزارش‌ها."""
    return jalali_str(datetime.now(), with_weekday=with_weekday)


def jalali_str(dt: Optional[Union[date, datetime]] = None, *, with_weekday: bool = True) -> str:
    """تاریخ میلادی → رشتهٔ نمایشی شمسی با نام ماه و (اختیاری) روز هفته."""
    d = dt or datetime.now()
    if isinstance(d, datetime):
        d = d.date()
    jy, jm, jd = gregorian_to_jalali(d)
    month_name = FA_MONTHS[max(0, min(11, jm - 1))]
    base = f"{to_fa_digits(jd)} {month_name} {to_fa_digits(jy)}"
    if with_weekday:
        weekday = FA_WEEKDAYS[d.weekday()]
        return f"{weekday}، {base}"
    return base


def jalali_compact(dt: Optional[Union[date, datetime]] = None) -> str:
    """قالب فشردهٔ عددی شمسی: «۱۴۰۴/۰۷/۰۴» — برای جدول و محور نمودار."""
    d = dt or datetime.now()
    if isinstance(d, datetime):
        d = d.date()
    jy, jm, jd = gregorian_to_jalali(d)
    return to_fa_digits(f"{jy:04d}/{jm:02d}/{jd:02d}")
