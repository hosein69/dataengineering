# -*- coding: utf-8 -*-
"""GSI — توکن‌های طراحی، پالت وضعیت و قالب Plotly.

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

## منبع رنگ

این ماژول دیگر مقدار خودش را نمی‌سازد. هر رنگ از :mod:`gsi.design.tokens`
می‌آید — همان جایی که HTML، Excel و ایمیل هم از آن می‌خوانند. تا پیش از
این، اپ Streamlit یک پالت هشتم بود: «تحت نظر» اینجا ``#fab219`` بود و در
Excel ``F1C40F`` و در ایمیل ``F39C12``. سه زرد برای یک معنا.

نام‌ها دست‌نخورده مانده‌اند تا ``app/ui_kit.py`` و ``app/dashboard.py`` بدون
تغییر کار کنند؛ فقط مقداری که می‌گیرند، مقدار سنجیده‌شده است.
"""
from __future__ import annotations

import os
import sys
from typing import Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gsi.design import tokens as _T   # noqa: E402

# ── سطوح و متن ────────────────────────────────────────────────────────────
SURFACE = _T.SURFACE_PAGE
SURFACE_RAISED = _T.SURFACE_RAISED
SURFACE_SUNKEN = _T.SURFACE_SUNKEN
BORDER = _T.BORDER
BORDER_STRONG = _T.BORDER_STRONG
TEXT = _T.TEXT
TEXT_SECONDARY = _T.TEXT_SECONDARY
TEXT_MUTED = _T.TEXT_MUTED

# ── هویت GSI | Global Sourcing Intelligence ─────────────────────────────
# Data • Process • Decision: Navy=اعتماد/داده، Teal=جریان/فرآیند، Gold=تصمیم.
BRAND_NAVY = _T.BRAND_NAVY
BRAND_TEAL = _T.BRAND_TEAL
BRAND_GOLD = _T.BRAND_GOLD
BRAND = BRAND_TEAL
BRAND_DEEP = BRAND_NAVY
BRAND_SOFT = _T.TEAL_WASH
TEAL_WASH_ = _T.TEAL_WASH   # نام صریح برای مصرف‌کننده‌های ui_kit
ACCENT = BRAND_GOLD

# ── پالت وضعیت (ثابت — هرگز به‌عنوان رنگ سری استفاده نشود) ────────────────
#: رنگ *نشانه* هر وضعیت (``fill``). برای متن، :data:`STATUS_INK` را بردارید؛
#: ``fill`` روشن است و زیر متن نمی‌نشیند.
STATUS: Dict[str, str] = {s.key: s.fill for s in _T.STATUS_SCALE}

#: رنگ *متن* هر وضعیت — کنتراست هر کدام روی سفید بین ۶٫۰۹ و ۸٫۸۱ است.
STATUS_INK: Dict[str, str] = {s.key: s.ink for s in _T.STATUS_SCALE}

#: زمینه ملایم هر وضعیت؛ متن ``STATUS_INK`` روی آن می‌نشیند.
STATUS_WASH: Dict[str, str] = {s.key: s.wash for s in _T.STATUS_SCALE}

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
SERIES = list(_T.CATEGORICAL)

#: تک‌هیو ترتیبی برای بزرگی پیوسته (روشن → تیره)
SEQUENTIAL = list(_T.SEQUENTIAL)

FONT_STACK = _T.FONT_STACK


def band_of(value) -> tuple:
    """(رنگ، آیکن، برچسب) برای یک کد یا برچسب طبقه بحرانی."""
    s = str(value).strip()
    if s in BANDS:
        return BANDS[s]
    if s in BANDS_FA:
        return BANDS_FA[s]
    return (STATUS["unknown"], "?", s or "نامشخص")


def band_color(value) -> str:
    return band_of(value)[0]


def plotly_template() -> dict:
    """قالب Plotly: شبکه پس‌رونده، متن با توکن متن (نه رنگ سری)، هاور یکپارچه."""
    # automargin ضروری است: برچسب‌های فارسی بلندند و بدون آن روی نمودار
    # میله‌ای افقی بریده می‌شوند — میله بدون برچسب بی‌معناست.
    axis = dict(
        showgrid=True, gridcolor=_T.PAPER_RULE, gridwidth=1, griddash="dot", zeroline=False,
        linecolor=BORDER_STRONG, ticks="outside", tickcolor=BORDER_STRONG,
        ticklen=4, tickfont=dict(size=11, color=TEXT_SECONDARY),
        title=dict(font=dict(size=12, color=TEXT_SECONDARY)),
        automargin=True,
    )
    return dict(
        layout=dict(
            font=dict(family=FONT_STACK, size=12, color=TEXT),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor=_T.SURFACE_PAPER_SOFT,
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
