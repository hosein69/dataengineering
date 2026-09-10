# -*- coding: utf-8 -*-
"""توکن‌های طراحی — همه از نظام «آکوا» (`report/aqua.py`) می‌آیند.

این فایل دیگر رنگی تعریف نمی‌کند؛ فقط نام‌های قدیمی را به توکن‌های
آکوا وصل می‌کند تا مصرف‌کننده‌های موجود (اکسل، HTML، داشبورد) بدون
تغییر کار کنند. **یک** منبع رنگ وجود دارد، نه چهار تا.

پالت وضعیت رزرو است و همیشه با **آیکن + برچسب** می‌آید؛ رنگ به‌تنهایی
هرگز حامل معنا نیست.
"""
from __future__ import annotations

from . import aqua

_L = aqua.tokens(False)

SURFACE, RAISED, BORDER = _L["surface"], _L["raised"], _L["border"]
TEXT, TEXT2, TEXT3 = _L["text"], _L["text-2"], _L["text-3"]
BRAND, BRAND_DEEP = _L["brand-strong"], _L["header"]
CARD, HIGHLIGHT, ACCENT, CTA = _L["card"], _L["highlight"], _L["accent"], _L["cta"]

_S = aqua.status(False)
STATUS = {
    "critical": _S["critical"], "poor": _S["critical"], "watch": _S["serious"],
    "fair": _S["warning"], "good": _S["good"], "neutral": aqua.OTHER_LIGHT,
}

#: رده عملکرد: (کف امتیاز، رنگ، آیکن، برچسب) — مرزها همان
#: ``aqua.SCORE_BANDS`` است تا جدول و نمودار یک داستان بگویند.
BANDS = [
    (75.0, _S["good"], "▲", "برجسته"),
    (60.0, _S["warning"], "△", "مطلوب"),
    (45.0, _S["serious"], "◆", "قابل بهبود"),
    (0.0, _S["critical"], "▼", "نیازمند اقدام"),
]

SERIES = aqua.categorical(False)
#: طیف پیوسته — یک هیو، روشن به تیره (قاعدهٔ طیف ترتیبی)
SEQUENTIAL = ["#D7F0E7", "#A9DFD1", "#7CCDBB", "#4DBEA8",
              "#00A693", "#007D6E", "#005349"]

FONT_STACK = aqua.FONT_STACK


def band_of(score) -> tuple:
    """(رنگ، آیکن، برچسب) برای یک امتیاز عملکرد."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return (STATUS["neutral"], "?", "نامشخص")
    for floor, color, icon, label in BANDS:
        if s >= floor:
            return (color, icon, label)
    return (STATUS["neutral"], "?", "نامشخص")


def plotly_template() -> dict:
    axis = dict(showgrid=True, gridcolor=BORDER, zeroline=False,
                linecolor="#cfcfc6", ticks="outside", tickcolor="#cfcfc6",
                ticklen=4, tickfont=dict(size=11, color=TEXT2),
                title=dict(font=dict(size=12, color=TEXT2)), automargin=True)
    return dict(layout=dict(
        font=dict(family=FONT_STACK, size=12, color=TEXT),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=SERIES, xaxis=axis, yaxis=axis,
        margin=dict(t=48, r=24, b=44, l=24),
        hoverlabel=dict(bgcolor=RAISED, bordercolor="#cfcfc6",
                        font=dict(family=FONT_STACK, size=12, color=TEXT),
                        align="right"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1,
                    font=dict(size=11, color=TEXT2), bgcolor="rgba(0,0,0,0)"),
        title=dict(font=dict(size=14, color=TEXT), x=1, xanchor="right"),
        separators="٫٬"))
