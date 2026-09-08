# -*- coding: utf-8 -*-
"""توکن‌های طراحی و پالت — همان پالت اعتبارسنجی‌شده پلتفرم AIBL.

پالت وضعیت ثابت است و همیشه با **آیکن + برچسب** می‌آید؛ رنگ به‌تنهایی
هرگز حامل معنا نیست. رده‌های عملکرد پنج‌تایی‌اند و روی همان چهار نقش
وضعیت به‌علاوه یک پله تیره‌تر ساخته شده‌اند.
"""
from __future__ import annotations

SURFACE, RAISED, BORDER = "#fcfcfb", "#ffffff", "#e3e3dd"
TEXT, TEXT2, TEXT3 = "#0b0b0b", "#52514e", "#6e6e66"
BRAND, BRAND_DEEP = "#1c5cab", "#0d366b"      # آبی — هویت منابع انسانی

STATUS = {
    "critical": "#a32828", "poor": "#d03b3b", "watch": "#ec835a",
    "fair": "#fab219", "good": "#0ca30c", "neutral": "#8a8a85",
}

#: رده عملکرد: (کف امتیاز، رنگ، آیکن، برچسب)
BANDS = [
    (75.0, STATUS["good"], "▲", "بسیار خوب"),
    (60.0, "#5fa832", "△", "خوب"),
    (45.0, STATUS["fair"], "◆", "مورد انتظار"),
    (32.0, STATUS["watch"], "▽", "نیازمند بهبود"),
    (0.0, STATUS["poor"], "▼", "بحرانی"),
]

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
              "#256abf", "#184f95", "#0d366b"]

FONT_STACK = "'IRANSans Light','IRANSans','Vazirmatn',Tahoma,Arial,sans-serif"


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
