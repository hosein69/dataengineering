# -*- coding: utf-8 -*-
"""خروجی‌های سبک برای مصرف بیرون از Streamlit: ایمیل اوتلوک و اکسل.

## Streamlit در برابر HTML/اکسل — تفاوتی که باید همیشه رعایت شود

Streamlit **موتور ساخت** است: جایی که تیم محصول چیدمان و داده را می‌بیند و
تنظیم می‌کند. آن‌چه کاربر نهایی (مدیر، کارشناس) واقعاً می‌بیند HTML یا
اکسلی است که از همین ماژول بیرون می‌آید — سبک، آفلاین، بدون نیاز به سرور
یا مرورگر خاص. هرگز HTML داشبورد Streamlit را مستقیم به کاربر ایمیل نکنید؛
همیشه از ``build_report_html``/``build_excel_report`` استفاده کنید.
"""
from __future__ import annotations

from .excel_report import build_excel_report
from .html_report import build_report_html, kanban_summary_table_html, kpi_table_html, top_routes_table_html

__all__ = [
    "build_report_html", "kpi_table_html", "top_routes_table_html", "kanban_summary_table_html",
    "build_excel_report",
]
