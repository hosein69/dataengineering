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

from typing import Dict

# ── سطوح و متن ────────────────────────────────────────────────────────────
SURFACE = "#fcfcfb"
SURFACE_RAISED = "#ffffff"
SURFACE_SUNKEN = "#f4f4f1"
BORDER = "#e3e3dd"
BORDER_STRONG = "#cfcfc6"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
TEXT_MUTED = "#7a7a73"

# ── هویت AIBL ─────────────────────────────────────────────────────────────
BRAND = "#0f6e6e"
BRAND_DEEP = "#0a4f4f"
BRAND_SOFT = "#e6f2f1"
ACCENT = "#2a78d6"

# ── پالت وضعیت (ثابت — هرگز به‌عنوان رنگ سری استفاده نشود) ────────────────
STATUS: Dict[str, str] = {
    "stockout": "#a32828",   # پله تیره‌تر خانواده critical
    "critical": "#d03b3b",
    "serious":  "#ec835a",
    "warning":  "#fab219",
    "good":     "#0ca30c",
    "neutral":  "#8a8a85",
    "unknown":  "#b5b5ae",
}

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
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

#: تک‌هیو ترتیبی برای بزرگی پیوسته (روشن → تیره)
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
              "#256abf", "#184f95", "#0d366b"]

FONT_STACK = "'IRANSans Light','IRANSans','Vazirmatn',Tahoma,Arial,sans-serif"


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
        showgrid=True, gridcolor=BORDER, gridwidth=1, zeroline=False,
        linecolor=BORDER_STRONG, ticks="outside", tickcolor=BORDER_STRONG,
        ticklen=4, tickfont=dict(size=11, color=TEXT_SECONDARY),
        title=dict(font=dict(size=12, color=TEXT_SECONDARY)),
        automargin=True,
    )
    return dict(
        layout=dict(
            font=dict(family=FONT_STACK, size=12, color=TEXT),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
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
