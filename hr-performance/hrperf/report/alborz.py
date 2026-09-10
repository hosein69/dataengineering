# -*- coding: utf-8 -*-
"""نظام طراحی «البرز» — یک منبع برای هر سطحی که کاربر می‌بیند.

    نام: البرز · Alborz Design System
    نسخه: ۱٫۰
    دامنه: پوستر، گزارش (اکسل/HTML/ایمیل)، و رابط هر دو پلتفرم
    سازمان: IKCO · Global Sourcing (GS) · Governance and Integration (GI)

نسخهٔ یکسانِ ``aibl/report/alborz.py``. عمداً کپی شده تا دو پکیج مستقل
بمانند؛ هر تغییر باید در **هر دو** اعمال شود و تست معماری این را می‌سنجد.

## این نظام از کجا آمد

از یک زنجیرهٔ نقد واقعی، نه از سلیقه. هر تصمیمش پاسخ به یک ایراد مشخص
است:

| ایراد | تصمیم |
|---|---|
| «سبز بی‌ربط، حس مدادرنگی» | سبز میانه فقط برای سربرگ، به‌صورت **طیف**؛ نه رنگ تخت |
| «خاکستری سرد، ارزان» | زمینهٔ طوسی با شست‌وشوی کاهی — فام دارد، خنثای مرده نیست |
| «کارت‌ها قالب آماده‌اند» | حاشیهٔ خاکستری حذف؛ عمق با **دو لایه سایه** و لبهٔ سفید داخلی |
| «وکتور بی‌ربط به ایران‌خودرو» | تصویرسازی دامنه‌ای: تارا، کشتی، بندر، انبار، کارخانه |
| «روایت شعاری» | محتوا از خود کد می‌آید: ۱۳ فعالیت، ۷ مرحله، ۱۲ سورس |

## قاعده‌های نشکستنی

* **رنگ وضعیت رزرو است.** good/warning/serious/critical هرگز «سری چهارم»
  نمی‌شوند و همیشه با آیکن و برچسب می‌آیند.
* **متن، توکن متن می‌پوشد** — نه رنگ سری، نه رنگ برند.
* **طیف آکوا فقط برای سربرگ و سطح‌های تیره.** بدنهٔ گزارش روی زمینهٔ
  روشن می‌نشیند.
* **کهربایی زیر ۵٪ سطح** و دو مقدار دارد: یکی برای خط، یکی برای متن.
  رنگی که به‌عنوان خط کار می‌کند، لزوماً به‌عنوان متن خوانا نیست.
* **هر متن باید ≥۴٫۵:۱ باشد** (۳:۱ برای متن بزرگ). این ادعا نیست —
  ``tests/test_packaging.py`` اندازه‌اش می‌گیرد.
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict, List, Tuple

NAME = "البرز"
NAME_EN = "Alborz Design System"
VERSION = "1.0"

# ═══════════════════ زمینه: طوسی سرد با شست‌وشوی کاهی ═══════════════════
#: پس‌زمینهٔ صفحه یک گرادیان سه‌توقفی است، نه رنگ تخت. خاکستری خالص
#: (فام صفر) با هیچ رنگی در سیستم نسبت ندارد؛ این سه، فام کاهی کم‌جان
#: دارند و کنار کهربایی می‌نشینند.
PAGE_STOPS: List[Tuple[float, str]] = [(0.0, "#F1F1F0"), (0.55, "#F3F1EE"), (1.0, "#EDEEEE")]
PAGE = "#F1F1F0"
CARD = "#FBFBFA"
CARD_EDGE = "#FFFFFF"
HAIRLINE = "#E4E4E1"
SUNKEN = "#E7E7E4"

# ═══════════════════ طیف آکوا — فقط سربرگ و سطح تیره ═══════════════════
AQUA_900 = "#005349"
AQUA_700 = "#007D6E"
AQUA_500 = "#00A693"
AQUA_GLOW = "#99E6D2"
HEADER_STOPS: List[Tuple[float, str]] = [(0.0, AQUA_900), (0.52, AQUA_700), (1.0, AQUA_500)]
ON_AQUA = "#FFFFFF"
ON_AQUA_2 = "#E8F8F3"
ON_AQUA_3 = "#EAF7F2"
FOOTER = "#00443C"
ON_FOOTER = "#8FC9BB"

# ═══════════════════ مرکب ═══════════════════
INK = "#22282B"
INK_2 = "#5A666B"
INK_3 = "#646D71"
STRAW = "#8A7434"
STRAW_INK = "#7E6A2F"
AMBER_BLIND = "#8A5A00"
BLIND_BG = "#F6EFDD"

# ═══════════════════ وضعیت (رزرو) ═══════════════════
STATUS: Dict[str, str] = {
    "stockout": "#8F1E17", "critical": "#B3261E", "serious": "#B3541E",
    "warning": "#8A6100", "good": "#2E7D32", "neutral": "#5F7A6E",
    "unknown": "#8FA79A",
}
#: رنگ **متن** روی ته‌رنگ ۱۰٪ همان وضعیت. محاسبه‌شده، نه انتخابی.
STATUS_ON_TINT: Dict[str, str] = {
    "stockout": "#8F1E17", "critical": "#B3261E", "serious": "#9E4A1A",
    "warning": "#825B00", "good": "#29702D", "neutral": "#51685E",
    "unknown": "#5A6961",
}

# ═══════════════════ عمق: دو لایه سایه، نه حاشیهٔ خاکستری ═══════════════
#: (offsetY, blur, spread, alpha) — لایهٔ نزدیک تیز، لایهٔ دور نرم
SHADOW_NEAR = (2, 8, -2, 0.07)
SHADOW_FAR = (14, 30, -8, 0.05)
SHADOW_RGB = (0.13, 0.16, 0.17)

RADIUS = {"card": 20, "patch": 18, "panel": 16, "chip": 999, "sm": 10, "xs": 6}
SPACE = [0, 6, 10, 16, 22, 28, 34, 44, 54]

# ═══════════════════ تایپوگرافی ═══════════════════
#: ایران‌سنس اول. Vazirmatn جایگزین آزادِ در دسترس در فیگما و لینوکس است.
FONT_STACK = "'IRANSans Light','IRANSans','Vazirmatn','SF Arabic','Segoe UI',Tahoma,'Geeza Pro',system-ui,sans-serif"
FONT_XLSX = "IRANSans Light"
TYPE_SCALE = {
    "display": 44, "title": 26, "section": 23, "lead": 19,
    "body": 13.5, "caption": 12, "micro": 11.5,
}

# ═══════════════════ نقش‌مایه‌ها ═══════════════════
#: «وصله و چسب»: هر تصویرسازی داخل قابی با گوشهٔ گرد، دو سایه و نوارهای
#: چسبِ نیمه‌شفافِ کج می‌نشیند. این همان چیزی است که کار را از «قالب
#: نرم‌افزاری» به «چیزِ ساخته‌شده» می‌برد.
TAPE_ALPHA = (0.50, 0.36, 0.50)
TAPE_TILT = (-8, 6)

#: تصویرسازی دامنه‌ای — نه آیکن عمومی
MOTIFS = ("تارا (نمای روبرو)", "کشتی کانتینری", "بندر و گمرک",
          "انبار", "کارخانهٔ تأمین‌کننده", "سیلوئت دماوند")

TAGLINE = "Inspiring Knowledge, Creating Opportunities"


def page_gradient_css(angle: str = "160deg") -> str:
    """گرادیان زمینه به‌صورت CSS."""
    body = ", ".join(f"{c} {int(p * 100)}%" for p, c in PAGE_STOPS)
    return f"linear-gradient({angle}, {body})"


def header_gradient_css(angle: str = "120deg") -> str:
    body = ", ".join(f"{c} {int(p * 100)}%" for p, c in HEADER_STOPS)
    return f"linear-gradient({angle}, {body})"


def shadow_css() -> str:
    """همان دو لایهٔ سایه، برای CSS."""
    r, g, b = (int(v * 255) for v in SHADOW_RGB)
    near = f"0 {SHADOW_NEAR[0]}px {SHADOW_NEAR[1]}px {SHADOW_NEAR[2]}px rgba({r},{g},{b},{SHADOW_NEAR[3]})"
    far = f"0 {SHADOW_FAR[0]}px {SHADOW_FAR[1]}px {SHADOW_FAR[2]}px rgba({r},{g},{b},{SHADOW_FAR[3]})"
    return f"{near}, {far}"


def tokens() -> Dict[str, str]:
    """نگاشت تخت برای مصرف‌کننده‌هایی که فقط رنگ می‌خواهند."""
    out = {
        "page": PAGE, "card": CARD, "card-edge": CARD_EDGE,
        "hairline": HAIRLINE, "sunken": SUNKEN,
        "aqua-900": AQUA_900, "aqua-700": AQUA_700, "aqua-500": AQUA_500,
        "on-aqua": ON_AQUA, "on-aqua-2": ON_AQUA_2, "footer": FOOTER,
        "ink": INK, "ink-2": INK_2, "ink-3": INK_3,
        "straw": STRAW, "straw-ink": STRAW_INK,
        "amber-blind": AMBER_BLIND, "blind-bg": BLIND_BG,
    }
    out.update({f"status-{k}": v for k, v in STATUS.items()})
    return out
