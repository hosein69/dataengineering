# -*- coding: utf-8 -*-
"""نظام طراحی «آکوا» — یک منبع رنگ برای هر دو پکیج و همهٔ خروجی‌ها.

این فایل نسخهٔ یکسانِ ``hrperf/report/aqua.py`` است. عمداً کپی شده و
وابستگی متقابل بین دو پکیج ساخته نشده: هر پکیج باید مستقل نصب و اجرا
شود. هر تغییر رنگ باید در **هر دو** اعمال شود؛ تست معماری این را
می‌سنجد.

## چرا این فایل وجود دارد

تا امروز هر خروجی پالت خودش را داشت: اکسل یک سبز، HTML یک سبز دیگر،
داشبورد یک سوم. کاربری که سه فایل را کنار هم می‌گذارد، فکر می‌کند سه
سیستم متفاوت است. اینجا **یک** تعریف هست و بقیه از آن می‌خوانند.

## پالت پایه از کجا آمد

پالت آکوای سازمانی (سبز فیروزه‌ای / سبز ایرانی / کهربایی-مفرغی) مبنا
است. سه اصلاح روی آن انجام شد، هر سه **محاسبه‌شده** نه سلیقه‌ای:

| مشکل | اندازه‌گیری | اصلاح |
|---|---|---|
| بردر `#73A88B` روی پس‌زمینه | ۲٫۳۵:۱ — تقریباً نامرئی | `#5F9077` (۳٫۱۵:۱) |
| سفید روی دکمهٔ برند `#00A693` | ۳٫۰۵:۱ — زیر حد متن | دکمه `#007D6E` (۵٫۰۵:۱)؛ `#00A693` می‌ماند برای سطح و آیکون |
| متن ثانویه روی کارت | ۴٫۱۳:۱ | `#3E6350` (۴٫۹۷:۱) |

و دو افزوده که پالت اصلی نداشت و بدون آن‌ها کار نمی‌کرد:

* **طیف دسته‌ای برای نمودار.** پالت اصلی یک خانوادهٔ رنگی است؛ سه سبزش
  در نمودار از هم قابل تشخیص نیستند (ΔE نرمال ۸٫۱ — زیر کف ۱۵). یک طیف
  هشت‌تایی ساخته شد که لنگرش همان آکوای برند است ولی هیوها پخش‌اند.
* **حالت تاریک.** همهٔ خروجی‌های HTML این پکیج تم‌آگاهند؛ پالت اصلی فقط
  روشن بود.

هر دو طیف با `validate_palette.js` سنجیده شده‌اند و **هر شش بررسی** را
روی سطح واقعیِ خودشان (نه سفید فرضی) رد می‌کنند:

```
روشن  (سطح #E1F2E9): بدترین جفت مجاور — CVD ΔE ۱۲٫۰ · دید عادی ΔE ۲۱٫۷
تاریک (سطح #0C1F1A): بدترین جفت مجاور — CVD ΔE ۱۰٫۹ · دید عادی ΔE ۲۲٫۰
```

## قاعده‌ها

* ترتیب طیف دسته‌ای **ثابت** است و هرگز چرخانده نمی‌شود؛ فیلترکردن یک
  سری، رنگ بقیه را عوض نمی‌کند.
* رنگ‌های وضعیت (خوب/هشدار/جدی/بحرانی) **رزرو**اند و هرگز به‌عنوان
  «سری چهارم» به‌کار نمی‌روند.
* متن هرگز رنگ سری نمی‌گیرد؛ متن، توکن متن می‌پوشد.
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict, List

# ═══════════════════ پالت پایهٔ سازمانی (آکوا) ═══════════════════
#: سبز فیروزه‌ای — از بسیار روشن تا بسیار تیره
TEAL = {
    "50": "#E1F2E9",   # پس‌زمینه اصلی صفحه
    "100": "#C2E5D3",  # کارت / باکس
    "300": "#A0D6B4",  # سطح وکتور / تصویرسازی
    "500": "#5F9077",  # حاشیه / بردر  ← اصلاح‌شده از #73A88B (۲٫۳۵:۱)
    "600": "#47705B",  # متن ثانویه روی پس‌زمینه
    "700": "#3E6350",  # متن ثانویه روی کارت ← اصلاح‌شده
}

#: سبز ایرانی — خانوادهٔ برند
IRANIAN = {
    "200": "#99D9CC",  # پس‌زمینه بخش‌ها
    "400": "#4DBEA8",  # آیکون / هایلایت
    "500": "#00A693",  # رنگ برند (سطح، آیکون، خط)
    "600": "#007D6E",  # دکمه ← متن سفید روی آن ۵٫۰۵:۱
    "700": "#006B5E",  # هاور دکمه
    "900": "#005349",  # پس‌زمینه هدر و فوتر
}

#: کهربایی-مفرغی — تأکید و عنوان روی تیره
AMBER = {
    "50": "#FDF6EC",   # پس‌زمینه هایلایت
    "200": "#F5D3A3",  # عنوان روی سبز تیره (۶٫۳۱:۱)
    "400": "#F0B463",  # عنوان و لینک روی تیره (۴٫۸۹:۱)
    "600": "#C4761A",  # تأکید / سطح CTA
    "700": "#A85F12",  # دکمهٔ CTA با متن سفید (۴٫۸۷:۱)
    "800": "#7A430E",  # عنوان روی سبز روشن (۴٫۸۴:۱)
    "900": "#3D1F06",  # جزئیات ریز / متن روی کهربایی روشن
}

#: خنثی
INK = "#14332C"        # متن بدنه — ۱۱٫۷:۱ روی پس‌زمینه اصلی
WHITE = "#FFFFFF"

# ═══════════════════ توکن‌های حالت روشن ═══════════════════
LIGHT: Dict[str, str] = {
    "surface": TEAL["50"],
    "raised": WHITE,
    "sunken": IRANIAN["200"],
    "card": TEAL["100"],
    "border": TEAL["500"],
    "border-soft": TEAL["300"],
    "text": INK,
    "text-2": TEAL["600"],
    "text-3": TEAL["700"],
    "brand": IRANIAN["500"],
    "brand-strong": IRANIAN["600"],
    "brand-hover": IRANIAN["700"],
    "header": IRANIAN["900"],
    "on-header": WHITE,
    "on-header-title": AMBER["200"],
    "on-header-link": AMBER["400"],
    "accent": AMBER["600"],
    "cta": AMBER["700"],
    "on-cta": WHITE,
    "highlight": AMBER["50"],
    "on-brand": WHITE,
}

# ═══════════════════ توکن‌های حالت تاریک ═══════════════════
#: سطوح تاریک از همان خانوادهٔ آکوا مشتق شده‌اند، نه خاکستری خنثی —
#: تا تم تاریک، «همان سیستم در نور کم» باشد نه سیستمی دیگر.
DARK: Dict[str, str] = {
    "surface": "#0C1F1A",
    "raised": "#12291F",
    "sunken": "#0A1A16",
    "card": "#12291F",
    "border": "#4E7666",      # ۳٫۳۵:۱ — بردر باید دیده شود
    "border-soft": "#2C4A3E",
    "text": "#EAF6EF",        # ۱۵٫۴:۱
    "text-2": "#A9C6B7",      # ۹٫۳:۱
    "text-3": "#8FB0A0",
    "brand": IRANIAN["400"],  # ۷٫۵:۱ روی سطح تاریک
    "brand-strong": IRANIAN["500"],
    "brand-hover": "#5FD0BA",
    "header": "#0A2620",
    "on-header": "#EAF6EF",
    "on-header-title": AMBER["200"],
    "on-header-link": AMBER["400"],
    "accent": AMBER["400"],
    "cta": AMBER["600"],
    "on-cta": "#FFFFFF",
    "highlight": "#1A2C22",
    "on-brand": "#06231E",
}

# ═══════════════════ طیف دسته‌ای نمودار ═══════════════════
#: ترتیب ثابت. لنگر اول، آکوای برند است تا نمودار با هویت بخواند.
#: هر شش بررسی روی سطح واقعی رد شده (نه سطح سفید فرضی).
CATEGORICAL_LIGHT: List[str] = [
    "#008E82",  # آکوا (برند)
    "#C4761A",  # کهربایی
    "#2F74D0",  # آبی
    "#B0357A",  # سرخابی
    "#5E8C1B",  # سبز زیتونی
    "#7A5AD6",  # بنفش
    "#B03A2E",  # آجری
    "#1478A0",  # فیروزه‌ای تیره
]
CATEGORICAL_DARK: List[str] = [
    "#22A797", "#C87424", "#4A86D6", "#CE5A92",
    "#6FA32C", "#8F7DE0", "#D65F58", "#2F8DB0",
]
OTHER_LIGHT, OTHER_DARK = "#5F7A6E", "#8FB0A0"

# ═══════════════════ رنگ وضعیت (رزرو) ═══════════════════
STATUS_LIGHT: Dict[str, str] = {
    "good": "#2E7D32", "warning": "#8A6100",
    "serious": "#B3541E", "critical": "#B3261E",
}
STATUS_DARK: Dict[str, str] = {
    "good": "#5FBF62", "warning": "#D6A62E",
    "serious": "#E08A54", "critical": "#E86B62",
}

#: طبقه‌های امتیاز — (کف، سقف، کلید وضعیت، برچسب)
SCORE_BANDS = [
    (0, 45, "critical", "نیازمند اقدام"),
    (45, 60, "serious", "قابل بهبود"),
    (60, 75, "warning", "مطلوب"),
    (75, 101, "good", "برجسته"),
]

#: تایپوگرافی — یک نردبان، همه‌جا
TYPE_SCALE = {
    "display": 24, "title": 19, "section": 15,
    "body": 13.5, "caption": 12, "micro": 11,
}
FONT_STACK = '"Vazirmatn","IRANSans","Segoe UI",Tahoma,system-ui,sans-serif'
#: خانوادهٔ فونت اکسل و نمودارها — همان فونت سازمانی موجود.
#: عمداً عوض نشد: انتخاب فونت، تصمیم رنگ نیست و تغییرش هر خروجی
#: چاپ‌شدهٔ قبلی را با نسخهٔ تازه ناهم‌خوان می‌کرد.
FONT_XLSX = "IRANSans Light"

#: شعاع گوشه و فاصله — نردبان ۴ پیکسلی
RADIUS = {"sm": 6, "md": 9, "lg": 13, "pill": 999}
SPACE = [0, 4, 8, 12, 16, 24, 32, 48]


def tokens(dark: bool = False) -> Dict[str, str]:
    return dict(DARK if dark else LIGHT)


def categorical(dark: bool = False) -> List[str]:
    return list(CATEGORICAL_DARK if dark else CATEGORICAL_LIGHT)


def status(dark: bool = False) -> Dict[str, str]:
    return dict(STATUS_DARK if dark else STATUS_LIGHT)


def band_of(score: float, dark: bool = False) -> tuple:
    """(رنگ، برچسب) برای یک امتیاز ۰..۱۰۰."""
    pal = status(dark)
    for lo, hi, key, label in SCORE_BANDS:
        if lo <= score < hi:
            return pal[key], label
    return pal["good"], SCORE_BANDS[-1][3]


def css_vars(dark: bool = False, prefix: str = "--") -> str:
    """توکن‌ها به‌صورت متغیر CSS — همان نام‌ها در هر خروجی HTML."""
    t = tokens(dark)
    lines = [f"  {prefix}{k}:{v};" for k, v in t.items()]
    for i, c in enumerate(categorical(dark), start=1):
        lines.append(f"  {prefix}series-{i}:{c};")
    for k, v in status(dark).items():
        lines.append(f"  {prefix}{k}:{v};")
    lines.append(f"  {prefix}other:{OTHER_DARK if dark else OTHER_LIGHT};")
    return "\n".join(lines)


def stylesheet(selector: str = ":root") -> str:
    """بلوک کامل CSS با هر دو تم — پایهٔ همهٔ صفحه‌های این پکیج.

    ترتیب عمدی است: تم روشن روی ``:root`` خالی، تم تاریک هم زیر
    ``prefers-color-scheme`` (با محافظِ انتخاب صریح روشن) و هم زیر
    ``[data-theme="dark"]`` — تا دکمهٔ تم در هر دو جهت کار کند.
    """
    return f"""{selector}{{
  color-scheme: light;
{css_vars(False)}
  --font: {FONT_STACK};
  --radius-sm:{RADIUS['sm']}px; --radius-md:{RADIUS['md']}px;
  --radius-lg:{RADIUS['lg']}px;
}}
@media (prefers-color-scheme: dark){{
  {selector}:not([data-theme="light"]){{
    color-scheme: dark;
{css_vars(True)}
  }}
}}
{selector}[data-theme="dark"]{{
  color-scheme: dark;
{css_vars(True)}
}}"""


def xlsx_theme(dark: bool = False) -> Dict[str, str]:
    """رنگ‌ها بدون ``#`` — قالب رنگ در openpyxl همین را می‌خواهد."""
    out = {k: v.lstrip("#") for k, v in tokens(dark).items()}
    out.update({f"series{i}": c.lstrip("#")
                for i, c in enumerate(categorical(dark), start=1)})
    out.update({k: v.lstrip("#") for k, v in status(dark).items()})
    return out
