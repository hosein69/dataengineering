# -*- coding: utf-8 -*-
"""AIBL — توکن‌های طراحی، پالت وضعیت و قالب Plotly.

## چرا پالت عوض شد

پالت قبلی (`#F39C12` نارنجی و `#F1C40F` زرد) از اعتبارسنجی رد شد:

    worst adjacent #F1C40F↔#F39C12  ΔE 9.8 (normal vision) — below 15

یعنی «در حال بحرانی شدن» و «تحت نظر» — دو طبقه‌ای که اپراتور باید بینشان
تصمیم بگیرد — حتی با دید رنگی کامل به‌سختی تفکیک می‌شدند.

## پالت جدید

طبقه بحرانی یک **وضعیت** است، نه یک سری داده. پالت وضعیت ثابت است و هرگز
تم‌پذیر نمی‌شود، و همیشه با **آیکن + برچسب** می‌آید تا معنا هرگز فقط روی
رنگ سوار نباشد. «توقف خط» یک پله تیره‌تر از همان خانواده قرمزِ «بحرانی»
است (ترتیبی درون خانواده) و با آیکن متفاوت تفکیک می‌شود.
"""
from __future__ import annotations

import re
from typing import Dict, List

# ── سطوح و متن ────────────────────────────────────────────────────────────
from aibl.report import alborz as _AL
from aibl.report import aqua as _aqua

_L = _aqua.LIGHT

# سطح‌ها و مرکب از «نظام طراحی البرز» می‌آیند — منبع واحد.
# پیش از این از پالت آکوا می‌آمدند و زمینهٔ رابط سبز روشن بود؛ آکوا حالا
# فقط سربرگ و سطح‌های تیره را رنگ می‌کند، نه بدنه را.
SURFACE = _AL.PAGE
SURFACE_RAISED = _AL.CARD
SURFACE_SUNKEN = _AL.SUNKEN
BORDER = _AL.HAIRLINE
BORDER_STRONG = "#D2D2CE"
TEXT = _AL.INK
TEXT_SECONDARY = _AL.INK_2
TEXT_MUTED = _AL.INK_3

# ── هویت AIBL — از نظام آکوا ──────────────────────────────────────────────
BRAND = _AL.AQUA_700
BRAND_DEEP = _AL.AQUA_900
BRAND_SOFT = "#E4F1EC"
ACCENT = _AL.STRAW

# ── پالت وضعیت (ثابت — هرگز به‌عنوان رنگ سری استفاده نشود) ────────────────
#: «توقف خط» یک پله تیره‌تر از «بحرانی» است تا بدترین حالت، بدترین دیده شود.
STATUS: Dict[str, str] = dict(_AL.STATUS)

#: رنگ متن برچسب روی تراشه — تیره‌ترشدهٔ همان وضعیت، محاسبه‌شده در آکوا.
#: نقطهٔ رنگی تراشه رنگ خام را نگه می‌دارد؛ فقط متن تیره می‌شود.
STATUS_TEXT: Dict[str, str] = dict(_AL.STATUS_ON_TINT)

#: کد طبقه → (رنگ، آیکن، برچسب فارسی). آیکن و برچسب اجباری‌اند:
#: رنگ وضعیت هرگز به‌تنهایی حامل معنا نیست.
BANDS: Dict[str, tuple] = {
    "STOCKOUT":          (STATUS["stockout"], "⏹", "توقف خط"),
    "CRITICAL":          (STATUS["critical"], "⬤", "بحرانی"),
    "BECOMING_CRITICAL": (STATUS["serious"],  "◤", "در حال بحرانی شدن"),
    "WATCH":             (STATUS["warning"],  "◆", "تحت نظر"),
    "SAFE":              (STATUS["good"],     "✓", "ایمن"),
    "NO_CONSUMPTION":    (STATUS["neutral"],  "—", "بدون مصرف"),
    "UNKNOWN":           (STATUS["unknown"],  "?", "نامشخص"),
}

#: برچسب فارسی → همان سه‌تایی (خروجی خط لوله ستون فارسی هم دارد)
BANDS_FA: Dict[str, tuple] = {fa: (c, i, fa) for c, i, fa in BANDS.values()}

BAND_ORDER = ["STOCKOUT", "CRITICAL", "BECOMING_CRITICAL", "WATCH",
              "SAFE", "NO_CONSUMPTION", "UNKNOWN"]
BAND_ORDER_FA = [BANDS[k][2] for k in BAND_ORDER]

# ── پالت دسته‌ای (ترتیب ثابت، هرگز چرخشی) ─────────────────────────────────
# ترتیب مرجع اعتبارسنجی‌شده؛ سه اسلات اول برای نمودارهای all-pairs امن‌اند.
SERIES: List[str] = list(_aqua.CATEGORICAL_LIGHT)

#: تک‌هیو ترتیبی برای بزرگی پیوسته (روشن → تیره)
SEQUENTIAL: List[str] = ["#D7F0E7", "#A9DFD1", "#7CCDBB",
                         "#4DBEA8", "#00A693", "#007D6E", "#005349"]

#: از «نظام طراحی البرز» — رابط و گزارش نباید دو پشتهٔ فونت داشته باشند.
#: نسخهٔ محلیِ قبلی 'SF Arabic' و 'Geeza Pro' را نداشت و روی مکِ بدون
#: ایران‌سنس، فارسیِ رابط با قلمِ جانشینِ سیستم رندر می‌شد.
FONT_STACK = _AL.FONT_STACK


# ── تم Streamlit — یک منبع، دو مصرف‌کننده ─────────────────────────────────
#: تم داخلی Streamlit (ویجت‌ها، جدول، نوار کناری) از CSS ما خوانده نمی‌شود؛
#: Streamlit آن را از پیکربندی خودش می‌گیرد. اگر آن پیکربندی نباشد،
#: Streamlit از حالت روشن/تاریکِ **مرورگر** پیروی می‌کند و روی ویندوزِ
#: تاریک متن را سفید می‌کند — سفید روی پس‌زمینه سبز روشن ما یعنی متن
#: نامرئی. این یک بار در تولید اتفاق افتاد و کل رابط را از کار انداخت.
#:
#: پس مقدارها اینجا تعریف می‌شوند و دو جا مصرف: ``.streamlit/config.toml``
#: (که ``make_package.py`` می‌سازد و می‌بندد) و متغیرهای محیطی راه‌انداز.
#: داشتن هر دو عمدی است: اگر یکی نبود، آن دیگری تم را نگه می‌دارد.
STREAMLIT_THEME: Dict[str, str] = {
    "base": "light",
    "font": "sans serif",
    "primaryColor": BRAND,
    "backgroundColor": SURFACE,
    "secondaryBackgroundColor": SURFACE_RAISED,
    "textColor": TEXT,
}


def theme_env() -> Dict[str, str]:
    """همان تم، به شکل متغیر محیطی — اولویتش از فایل پیکربندی بالاتر است."""
    out = {}
    for key, val in STREAMLIT_THEME.items():
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", key).upper()
        out[f"STREAMLIT_THEME_{snake}"] = val
    return out


def config_toml() -> str:
    """متن ``.streamlit/config.toml`` از روی همین تم."""
    lines = ["# ساخته‌شده از app/theme.py — دستی ویرایش نکنید.",
             "# نبودِ این فایل یعنی تم از مرورگر می‌آید و متن نامرئی می‌شود.",
             "[theme]"]
    for key, val in STREAMLIT_THEME.items():
        lines.append(f'{key} = "{val}"')
    lines += ["", "[server]", "headless = true",
              "", "[browser]", "gatherUsageStats = false", ""]
    return "\n".join(lines)


def band_of(value) -> tuple:
    """(رنگ، آیکن، برچسب) برای یک کد یا برچسب طبقه بحرانی."""
    s = str(value).strip()
    if s in BANDS:
        return BANDS[s]
    if s in BANDS_FA:
        return BANDS_FA[s]
    return (STATUS["unknown"], "?", s or "نامشخص")


def band_text_color(value) -> str:
    """رنگ **متن** برچسب طبقه — نه رنگ خود طبقه.

    رنگ وضعیت روی ته‌رنگ ۱۰٪ خودش، برای متن ۱۲ پیکسلی کنتراست کافی
    نمی‌دهد (اندازه‌گیری: ۲٫۰۶ تا ۴٫۴۱). این نسخهٔ تیره‌شده ≥۴٫۶:۱ است.
    """
    color = band_of(value)[0]
    for key, raw in STATUS.items():
        if raw == color:
            return STATUS_TEXT.get(key, TEXT)
    return TEXT


def band_color(value) -> str:
    return band_of(value)[0]


def finalize(fig):
    """رنگ‌های نمودار را روی خودِ ``layout`` می‌نشاند، نه روی قالب.

    ``go.Figure`` — برخلاف ``plotly.express`` — قالب پیش‌فرض را هنگام
    ساخت نمی‌گیرد. وقتی Streamlit شکل را برای مرورگر سریال می‌کند، هیچ
    قالبی همراهش نیست و سمت مرورگر تم Streamlit روی آن می‌نشیند: بوم
    ``#0E1117`` و ناحیهٔ رسم ``#262730`` — نمودار مشکی داخل کارت سفید،
    با برچسب‌های تیرهٔ نادیدنی.

    مقدارِ صریح روی ``layout`` از هر قالبی بالاتر است، پس این تابع
    مستقل از نسخهٔ Streamlit و مستقل از آرگومان ``theme`` کار می‌کند.
    """
    fig.update_layout(
        paper_bgcolor=SURFACE_RAISED, plot_bgcolor=SURFACE_RAISED,
        font=dict(family=FONT_STACK, size=12, color=TEXT),
        colorway=SERIES, separators="\u066b\u066c",
        hoverlabel=dict(bgcolor=SURFACE_RAISED, bordercolor=BORDER_STRONG,
                        font=dict(family=FONT_STACK, size=12, color=TEXT)),
    )
    ax = dict(gridcolor=BORDER, linecolor=BORDER_STRONG, tickcolor=BORDER_STRONG,
              tickfont=dict(color=TEXT_SECONDARY),
              title=dict(font=dict(color=TEXT_SECONDARY)), automargin=True)
    fig.update_xaxes(**ax)
    fig.update_yaxes(**ax)
    if fig.layout.title is not None:
        fig.update_layout(title=dict(font=dict(color=TEXT)))
    if fig.layout.legend is not None:
        fig.update_layout(legend=dict(font=dict(color=TEXT_SECONDARY)))
    return fig


def plotly_template() -> dict:
    """قالب Plotly: شبکه پس‌رونده، متن با توکن متن (نه رنگ سری)، هاور یکپارچه."""
    # automargin ضروری است: برچسب‌های فارسی بلندند و بدون آن روی نمودار
    # میله‌ای افقی بریده می‌شوند — میله بدون برچسب بی‌معناست.
    axis = dict(
        showgrid=True, gridcolor=BORDER, gridwidth=1, zeroline=False,
        linecolor=BORDER_STRONG, ticks="outside", tickcolor=BORDER_STRONG,
        ticklen=4, tickfont=dict(size=11, color=TEXT_SECONDARY),
        title=dict(font=dict(size=12, color=TEXT_SECONDARY)),
        automargin=True,
    )
    return dict(
        layout=dict(
            font=dict(family=FONT_STACK, size=12, color=TEXT),
            # صریح، نه شفاف: با شفاف، بومِ نمودار رنگ تم Streamlit را
            # می‌گرفت و در حالت تاریکِ مرورگر، مشکی می‌شد — نمودار مشکی
            # داخل کارت سفید، با برچسب‌های مشکیِ نادیدنی.
            paper_bgcolor=SURFACE_RAISED,
            plot_bgcolor=SURFACE_RAISED,
            colorway=SERIES,
            xaxis=axis, yaxis=axis,
            margin=dict(t=52, r=24, b=44, l=24),
            hoverlabel=dict(
                bgcolor=SURFACE_RAISED, bordercolor=BORDER_STRONG,
                font=dict(family=FONT_STACK, size=12, color=TEXT),
                align="right",
            ),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(size=11, color=TEXT_SECONDARY),
                bgcolor="rgba(0,0,0,0)",
            ),
            title=dict(font=dict(size=14, color=TEXT), x=1, xanchor="right"),
            separators="٫٬",
        )
    )
