# -*- coding: utf-8 -*-
"""هویت سازمانی — یک منبع برای هر سطحی که کاربر می‌بیند.

«AIBL» نام داخلی پکیج پایتون است و همان می‌ماند (تغییرش یعنی بازنویسی
هر import). ولی **برند دیده‌شده** نام سازمان است، نه نام ماژول: عنوان
پنجره، سربرگ داشبورد، موضوع و بدنهٔ ایمیل، نام فایل خروجی و پوستر
آموزشی همه از اینجا می‌خوانند.

سلسله‌مراتب:

    IKCO
      └── Governance and Integration  (GI)
            └── Global Sourcing       (GS)
                  └── Data Analytics and KPI

پالت هم اینجاست و **پالت استاندارد سازمان** است، نه یک انتخاب تازه:
از پوسترهای موجود تیم استخراج شده تا خروجی این پلتفرم کنار بقیهٔ
اقلام ارتباطی، غریبه به نظر نرسد.
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict

# ═══════════════════ نام‌ها ═══════════════════
COMPANY = "IKCO"
COMPANY_FA = "ایران‌خودرو"

DIVISION = "Governance and Integration"
DIVISION_SHORT = "GI"
DIVISION_FA = "راهبری و یکپارچه‌سازی"

UNIT = "Global Sourcing"
UNIT_SHORT = "GS"
UNIT_FA = "خرید خارجی"

TEAM = "Data Analytics and KPI"
TEAM_FA = "تحلیل داده و شاخص‌های عملکرد"

#: خطِ هویت که روی سربرگ می‌نشیند
LOCKUP = f"{COMPANY} · {UNIT_SHORT} · {DIVISION_SHORT}"
LOCKUP_FULL = f"{COMPANY} — {UNIT} ({UNIT_SHORT}) · {DIVISION} ({DIVISION_SHORT})"

#: عنوان محصول — دیگر «AIBL» نیست
PRODUCT = "سامانهٔ یکپارچهٔ زنجیرهٔ تأمین"
PRODUCT_SHORT = "زنجیرهٔ تأمین"
TAGLINE = f"{TEAM_FA} · {DIVISION_FA}"

#: پیشوند نام پروندهٔ خروجی
FILE_PREFIX = f"{COMPANY}_{UNIT_SHORT}"


def subject(ref_date: str) -> str:
    """موضوع ایمیل — سازمان اول، تاریخ آخر."""
    return f"{COMPANY} {UNIT_SHORT} — گزارش زنجیرهٔ تأمین {ref_date}"


def title(page: str = "") -> str:
    return f"{PRODUCT} · {LOCKUP}" + (f" — {page}" if page else "")


# ═══════════════════ پالت استاندارد سازمان ═══════════════════
#: از اقلام ارتباطی موجود تیم استخراج شده (نمونه‌برداری مستقیم از پوستر
#: تأییدشده)، نه انتخاب سلیقه‌ای. سبز، شناسهٔ اصلی است؛ سرمه‌ای برای
#: عنوان‌های سطح دو؛ کهربایی فقط برای تأکید.
GREEN       = "#00784B"   # شناسهٔ اصلی — عنوان، شماره، خط
GREEN_DEEP  = "#005C39"   # هاور و سطح تیره
GREEN_SOFT  = "#E6F3EC"   # ته‌رنگ سبز برای سطح
NAVY        = "#0A3A69"   # عنوان سطح دو
NAVY_SOFT   = "#E8EEF5"
ORANGE      = "#E88400"   # تأکید و آیکن
ORANGE_SOFT = "#FDF1DF"
PAGE        = "#F8F8F8"   # پس‌زمینهٔ صفحه
CARD        = "#FFFFFF"
BORDER      = "#E3E6E8"
BORDER_STRONG = "#C9CFD4"
INK         = "#1A1A1A"   # متن بدنه
INK_2       = "#4A5560"   # متن ثانویه
INK_3       = "#6B7780"
WHITE       = "#FFFFFF"

PALETTE: Dict[str, str] = {
    "green": GREEN, "green-deep": GREEN_DEEP, "green-soft": GREEN_SOFT,
    "navy": NAVY, "navy-soft": NAVY_SOFT,
    "orange": ORANGE, "orange-soft": ORANGE_SOFT,
    "page": PAGE, "card": CARD, "border": BORDER, "border-strong": BORDER_STRONG,
    "ink": INK, "ink-2": INK_2, "ink-3": INK_3, "white": WHITE,
}
