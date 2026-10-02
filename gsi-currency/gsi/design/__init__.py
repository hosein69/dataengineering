# -*- coding: utf-8 -*-
"""GSI Design System — یک منبع برای رنگ، فاصله، تایپ، حرکت و کامپوننت.

    tokens.py      UI Basics — رنگ، فاصله، تایپ، شعاع، ارتفاع، حرکت، نقاط شکست
    css.py         Auto Layout، Responsive، دسترس‌پذیری، چاپ
    components.py  کامپوننت‌ها و واریانت‌ها
    charts_js.py   نشانه‌های SVG داخل مرورگر
    excel.py       پل Excel — همان توکن‌ها، سبک‌های openpyxl
    handoff.py     Dev Handoff — جدول توکن، فهرست کامپوننت، ممیزی دسترس‌پذیری

هر چهار خروجی GSI (HTML، Excel، ایمیل، Streamlit) از همین توکن‌ها می‌خوانند،
تا مدیری که Excel را باز می‌کند و مدیری که HTML را باز می‌کند، **یک** گزارش
ببینند نه دو گزارش.
"""
from __future__ import annotations

__contract__ = 1

from . import charts_js, components, css, excel, tokens

__all__ = ["tokens", "css", "components", "charts_js", "excel"]
