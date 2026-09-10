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

# ── تم Streamlit — یک منبع، دو مصرف‌کننده ─────────────────────────────────
#: تم داخلی Streamlit (ویجت، جدول، نوار کناری) از CSS ما خوانده نمی‌شود؛
#: Streamlit آن را از پیکربندی خودش می‌گیرد. اگر آن پیکربندی همراه بسته
#: نباشد، Streamlit از حالت روشن/تاریکِ **مرورگر** پیروی می‌کند و روی
#: ویندوزِ تاریک متن را سفید می‌کند — سفید روی پس‌زمینهٔ روشن ما یعنی متن
#: نامرئی. این دقیقاً در AIBL نسخهٔ ۲۶٫۱۵٫۰ رخ داد.
STREAMLIT_THEME = {
    "base": "light",
    "font": "sans serif",
    "primaryColor": BRAND,
    "backgroundColor": SURFACE,
    "secondaryBackgroundColor": RAISED,
    "textColor": TEXT,
}


def theme_env() -> dict:
    """همان تم، به شکل متغیر محیطی — اولویتش از فایل پیکربندی بالاتر است."""
    import re as _re
    return {f"STREAMLIT_THEME_{_re.sub(r'(?<!^)(?=[A-Z])', '_', k).upper()}": v
            for k, v in STREAMLIT_THEME.items()}


def config_toml() -> str:
    """متن ``.streamlit/config.toml`` از روی همین تم."""
    lines = ["# ساخته‌شده از hrperf/report/theme.py — دستی ویرایش نکنید.",
             "# نبودِ این فایل یعنی تم از مرورگر می‌آید و متن نامرئی می‌شود.",
             "[theme]"]
    lines += [f'{k} = "{v}"' for k, v in STREAMLIT_THEME.items()]
    lines += ["", "[server]", "headless = true",
              "", "[browser]", "gatherUsageStats = false", ""]
    return "\n".join(lines)


#: رنگ **متن** برچسب روی تراشه. پس‌زمینهٔ تراشه همان رنگ رده با ۱۰٪
#: شفافیت است و رنگ خام روی آن ته‌رنگ، برای متن ۱۲ پیکسلی زیر حد
#: خوانایی می‌افتد. مقدارها در آکوا محاسبه شده‌اند، نه انتخاب سلیقه‌ای.
_ON_TINT = {
    _S["good"]: aqua.STATUS_ON_TINT_LIGHT["good"],
    _S["warning"]: aqua.STATUS_ON_TINT_LIGHT["warning"],
    _S["serious"]: aqua.STATUS_ON_TINT_LIGHT["serious"],
    _S["critical"]: aqua.STATUS_ON_TINT_LIGHT["critical"],
    aqua.OTHER_LIGHT: aqua.STATUS_ON_TINT_LIGHT["neutral"],
}


def band_text_color(score) -> str:
    """رنگ متن برچسب رده — نه رنگ خود رده."""
    return _ON_TINT.get(band_of(score)[0], TEXT)


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


def finalize(fig):
    """رنگ‌های نمودار را روی خودِ ``layout`` می‌نشاند، نه روی قالب.

    ``go.Figure`` قالب پیش‌فرض را هنگام ساخت نمی‌گیرد؛ وقتی Streamlit شکل
    را برای مرورگر سریال می‌کند هیچ قالبی همراهش نیست و سمت مرورگر تم
    Streamlit روی آن می‌نشیند — در حالت تاریک، بومِ مشکی داخل کارت سفید.
    مقدار صریح روی ``layout`` از هر قالبی بالاتر است.
    """
    fig.update_layout(
        paper_bgcolor=RAISED, plot_bgcolor=RAISED,
        font=dict(family=FONT_STACK, size=12, color=TEXT),
        colorway=SERIES,
        hoverlabel=dict(bgcolor=RAISED, bordercolor=BORDER,
                        font=dict(family=FONT_STACK, size=12, color=TEXT)))
    ax = dict(gridcolor=BORDER, tickfont=dict(color=TEXT2),
              title=dict(font=dict(color=TEXT2)), automargin=True)
    fig.update_xaxes(**ax)
    fig.update_yaxes(**ax)
    return fig


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
