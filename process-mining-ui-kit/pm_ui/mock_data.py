# -*- coding: utf-8 -*-
"""دادهٔ آزمایشی (Mock) — فقط برای نمایش ظرفیت سامانهٔ طراحی؛ منبع واقعی جایگزینش می‌شود.

هیچ کدام از این مقادیر از رخدادی واقعی گرفته نشده‌اند. در استقرار واقعی،
این ماژول با یک آداپتور خواندن از فولدر شبکه/اکسل سازمانی جایگزین می‌شود؛
امضای تابع‌ها همان می‌ماند تا بقیهٔ سامانه بدون تغییر کار کند.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

from . import persian as fa


def process_graph() -> Dict[str, list]:
    """نمونهٔ گراف فرآیند «از ثبت سفارش تا ترخیص» با شدت جریان و یک گلوگاه."""
    nodes = [
        {"id": "reg", "label": "ثبت سفارش", "count": 1240, "status": "good"},
        {"id": "review", "label": "بررسی مدارک", "count": 1180, "status": "good"},
        {"id": "fx", "label": "تخصیص ارز", "count": 940, "status": "watch",
         "hint": "میانگین ۶٫۲ روز توقف"},
        {"id": "customs", "label": "ترخیص گمرکی", "count": 860, "status": "bottleneck",
         "hint": "بیشترین توقف کیس"},
        {"id": "delivery", "label": "تحویل انبار", "count": 820, "status": "good"},
        {"id": "rework", "label": "اصلاح مدارک", "count": 240, "status": "critical"},
    ]
    edges = [
        {"source": "reg", "target": "review", "count": 1180},
        {"source": "review", "target": "fx", "count": 940},
        {"source": "review", "target": "rework", "count": 240, "critical": True,
         "label": "انحراف"},
        {"source": "rework", "target": "review", "count": 210},
        {"source": "fx", "target": "customs", "count": 860, "critical": True,
         "label": "گلوگاه"},
        {"source": "customs", "target": "delivery", "count": 820},
    ]
    return {"nodes": nodes, "edges": edges}


def kpi_cards() -> List[dict]:
    return [
        {"label": "کیس‌های فعال", "value": fa.fa_number(1240), "delta": "‎+۴٪",
         "delta_good": True, "status": "good", "icon": "📦",
         "spark": [1020, 1080, 1110, 1150, 1190, 1240]},
        {"label": "میانگین زمان چرخه", "value": f"{fa.to_fa_digits('9.4')} روز", "delta": "‎-۸٪",
         "delta_good": True, "status": "good", "icon": "⏱",
         "spark": [11.2, 10.8, 10.1, 9.9, 9.6, 9.4]},
        {"label": "کیس‌های در گلوگاه", "value": fa.fa_number(86), "delta": "‎+۱۲٪",
         "delta_good": False, "status": "bottleneck", "icon": "⚠",
         "spark": [54, 61, 70, 75, 80, 86]},
        {"label": "ارزش ریالی در جریان", "value": fa.fa_compact(482_300_000_000),
         "delta": "‎+۲٪", "delta_good": True, "status": "good", "icon": "💰"},
    ]


def kanban_columns() -> List[dict]:
    return [
        {"title": "ثبت سفارش", "status": "good", "wip_limit": None, "cards": [
            {"title": "سفارش #۱۲۳۴۵", "tag": "واردات", "owner": "رضایی", "priority": "good", "age_days": 1},
            {"title": "سفارش #۱۲۳۵۰", "tag": "واردات", "owner": "احمدی", "priority": "good", "age_days": 2},
        ]},
        {"title": "تخصیص ارز", "status": "watch", "wip_limit": 6, "cards": [
            {"title": "سفارش #۱۲۳۰۱", "tag": "ارزی", "owner": "کریمی", "priority": "watch", "age_days": 5},
            {"title": "سفارش #۱۲۲۹۰", "tag": "ارزی", "owner": "رضایی", "priority": "watch", "age_days": 7},
            {"title": "سفارش #۱۲۲۸۸", "tag": "ارزی", "owner": "موسوی", "priority": "good", "age_days": 3},
        ]},
        {"title": "ترخیص گمرکی", "status": "bottleneck", "wip_limit": 5, "cards": [
            {"title": "سفارش #۱۲۲۵۰", "tag": "گمرک", "owner": "احمدی", "priority": "bottleneck", "age_days": 11},
            {"title": "سفارش #۱۲۲۴۰", "tag": "گمرک", "owner": "کریمی", "priority": "critical", "age_days": 14},
            {"title": "سفارش #۱۲۲۳۰", "tag": "گمرک", "owner": "موسوی", "priority": "bottleneck", "age_days": 9},
        ]},
        {"title": "تحویل انبار", "status": "good", "wip_limit": None, "cards": [
            {"title": "سفارش #۱۲۱۹۰", "tag": "تحویل", "owner": "رضایی", "priority": "good", "age_days": 1},
        ]},
    ]


def system_stages() -> List[dict]:
    return [
        {"label": "منابع داده سازمانی", "icon": "🗄", "sub": "SAP · اکسل · CSV", "status": "good"},
        {"label": "پالایش و اعتبارسنجی", "icon": "🧹", "sub": "قوانین کیفیت داده", "status": "good"},
        {"label": "انبار دادهٔ معنایی", "icon": "🏛", "sub": "Semantic DWH", "status": "good"},
        {"label": "موتور فرآیندکاوی", "icon": "🧭", "sub": "استخراج رویداد", "status": "watch"},
        {"label": "داشبورد و گزارش", "icon": "📊", "sub": "Streamlit / HTML / Excel", "status": "good"},
    ]


def intensity_series(days: int = 30) -> Dict[str, object]:
    today = date.today()
    labels = [fa.jalali_compact(today - timedelta(days=days - 1 - i)) for i in range(days)]
    base = 700
    values_a, values_b = [], []
    for i in range(days):
        values_a.append(base + i * 9 + (30 if i % 7 in (3, 4) else 0))
        values_b.append(int((base + i * 9) * 0.62))
    return {"labels": labels, "series": {"ثبت‌شده": values_a, "ترخیص‌شده": values_b}}


def heatmap_matrix() -> Dict[str, list]:
    weekdays = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
    hours = [fa.to_fa_digits(h) for h in (8, 10, 12, 14, 16, 18)]
    import random
    rnd = random.Random(7)
    z = [[rnd.randint(5, 120) for _ in hours] for _ in weekdays]
    return {"z": z, "x": hours, "y": weekdays}
