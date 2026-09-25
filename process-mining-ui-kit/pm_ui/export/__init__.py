# -*- coding: utf-8 -*-
"""خروجی‌های سبک برای مصرف بیرون از Streamlit: ایمیل اوتلوک و اکسل.

## Streamlit در برابر HTML/اکسل — تفاوتی که باید همیشه رعایت شود

Streamlit **موتور ساخت** است: جایی که تیم محصول چیدمان و داده را می‌بیند و
تنظیم می‌کند. آن‌چه کاربر نهایی (مدیر، کارشناس) واقعاً می‌بیند یکی از دو
خروجی این ماژول است، بسته به کانال توزیع:

    build_report_html      سبک‌ترین حالت — بدنه/پیوست ایمیل اوتلوک
                            (فقط جدول؛ بدون SVG/JS چون Word آن را نمی‌فهمد)
    build_standalone_html  کامل‌ترین حالت — فایلی برای فولدر شبکه/اشتراک
                            مستقیم (همهٔ نمودارها به‌صورت SVG، بدون JS)
    build_excel_report      برای بایگانی و پردازش بیشتر

هرگز HTML داشبورد Streamlit را مستقیم به کاربر ایمیل یا اشتراک نکنید؛
همیشه از یکی از این سه تابع استفاده کنید.
"""
from __future__ import annotations

from .excel_report import build_excel_report
from .html_report import build_report_html, kanban_summary_table_html, kpi_table_html, top_routes_table_html
from .standalone_html import build_standalone_html

__all__ = [
    "build_report_html", "kpi_table_html", "top_routes_table_html", "kanban_summary_table_html",
    "build_standalone_html",
    "build_excel_report",
]
