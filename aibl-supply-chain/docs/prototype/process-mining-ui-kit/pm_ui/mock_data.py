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
    """نمونهٔ گراف فرآیند «از ثبت سفارش تا ترخیص» با شدت جریان و یک گلوگاه.

    ``median_hours`` روی هر یال اضافه شده (پایهٔ حالت «عملکرد» نمودار —
    بررسی UX v2)؛ یال ``reg -> customs`` یک انحراف واقعی از انطباق را
    نمایش می‌دهد (پرش «بررسی مدارک»، نه فقط یک گلوگاه کند).
    """
    nodes = [
        {"id": "reg", "label": "ثبت سفارش", "count": 1240, "status": "good"},
        {"id": "review", "label": "بررسی مدارک", "count": 1180, "status": "good"},
        {"id": "fx", "label": "تخصیص ارز", "count": 940, "status": "warning",
         "hint": "میانگین ۶٫۲ روز توقف"},
        {"id": "customs", "label": "ترخیص گمرکی", "count": 860, "status": "stockout",
         "hint": "بیشترین توقف کیس"},
        {"id": "delivery", "label": "تحویل انبار", "count": 820, "status": "good"},
        {"id": "rework", "label": "اصلاح مدارک", "count": 240, "status": "critical"},
    ]
    edges = [
        {"source": "reg", "target": "review", "count": 1180, "median_hours": 3.0},
        {"source": "review", "target": "fx", "count": 940, "median_hours": 6.5},
        {"source": "review", "target": "rework", "count": 240, "critical": True,
         "label": "انحراف", "median_hours": 9.0},
        {"source": "rework", "target": "review", "count": 210, "median_hours": 4.0},
        {"source": "fx", "target": "customs", "count": 860, "critical": True,
         "label": "گلوگاه", "median_hours": 28.0},
        {"source": "customs", "target": "delivery", "count": 820, "median_hours": 5.0},
        {"source": "reg", "target": "customs", "count": 62, "deviating": True,
         "label": "پرش «بررسی مدارک»", "median_hours": 30.0},
    ]
    return {"nodes": nodes, "edges": edges}


def process_variants() -> List[dict]:
    """کاوشگر واریانت — همان توالی‌های گراف ``process_graph`` به‌صورت trace کامل.

    ``path_edges`` دقیقاً به (source, target) یال‌های همان گراف اشاره
    می‌کند تا انتخاب یک واریانت بتواند مسیرش را روی همان نقشه برجسته کند.
    """
    return [
        {"id": "v1", "label": "مسیر غالب", "pinned": True, "conformant": True,
         "route": "ثبت سفارش ← بررسی مدارک ← تخصیص ارز ← ترخیص گمرکی ← تحویل انبار",
         "share_pct": 62, "case_count": 769, "mean_cycle_days": 9.1,
         "path_edges": [("reg", "review"), ("review", "fx"), ("fx", "customs"), ("customs", "delivery")]},
        {"id": "v2", "label": "همان مسیر، با توقف طولانی‌تر گمرک", "conformant": True,
         "conformance_note": "توالی با مسیر مرجع یکی است؛ فقط مدت توقف در «ترخیص گمرکی» بیشتر است.",
         "route": "ثبت سفارش ← بررسی مدارک ← تخصیص ارز ← ترخیص گمرکی (میانه ۲۸ ساعت) ← تحویل انبار",
         "share_pct": 21, "case_count": 260, "mean_cycle_days": 13.4,
         "path_edges": [("reg", "review"), ("review", "fx"), ("fx", "customs"), ("customs", "delivery")]},
        {"id": "v3", "label": "با بازگشت اصلاح مدارک", "conformant": True,
         "conformance_note": "بازگشت به «بررسی مدارک» خودش خطا محسوب نمی‌شود.",
         "route": "ثبت سفارش ← بررسی مدارک ← اصلاح مدارک ← بررسی مدارک ← تخصیص ارز ← ترخیص گمرکی ← تحویل انبار",
         "share_pct": 11, "case_count": 136, "mean_cycle_days": 12.8,
         "path_edges": [("reg", "review"), ("review", "rework"), ("rework", "review"),
                        ("review", "fx"), ("fx", "customs"), ("customs", "delivery")]},
        {"id": "v4", "label": "پرش «بررسی مدارک»", "conformant": False,
         "conformance_note": "مرحلهٔ اجباری «بررسی مدارک» بین ثبت سفارش و ترخیص مشاهده نشده.",
         "route": "ثبت سفارش ← ترخیص گمرکی (بدون رویداد «بررسی مدارک») ← تحویل انبار",
         "share_pct": 6, "case_count": 62, "mean_cycle_days": 15.2,
         "path_edges": [("reg", "customs"), ("customs", "delivery")]},
    ]


def conformance_summary() -> dict:
    total = sum(v["case_count"] for v in process_variants())
    deviating = sum(v["case_count"] for v in process_variants() if not v.get("conformant", True))
    return {"fitness_pct": round(100 * (total - deviating) / total, 1),
           "total_cases": total, "deviating_cases": deviating}


def root_cause_rows() -> List[dict]:
    """نرخ انحراف هر بُعد نسبت به میانگین کل — فقط تفاضل مشاهده‌شده، نه ادعای علّیت."""
    return [
        {"dimension": "منبع سفارش — کانال دریایی", "delta_pct": 18, "status": "critical"},
        {"dimension": "شعبهٔ ثبت — دفتر مرکزی", "delta_pct": 9, "status": "warning"},
        {"dimension": "فصل تابستان", "delta_pct": -4, "status": "good"},
    ]


def kpi_cards() -> List[dict]:
    return [
        {"label": "کیس‌های فعال", "value": fa.fa_number(1240), "delta": "‎+۴٪",
         "delta_good": True, "status": "good", "icon": "📦",
         "spark": [1020, 1080, 1110, 1150, 1190, 1240]},
        {"label": "میانگین زمان چرخه", "value": f"{fa.to_fa_digits('9.4')} روز", "delta": "‎-۸٪",
         "delta_good": True, "status": "good", "icon": "⏱",
         "spark": [11.2, 10.8, 10.1, 9.9, 9.6, 9.4]},
        {"label": "کیس‌های در گلوگاه", "value": fa.fa_number(86), "delta": "‎+۱۲٪",
         "delta_good": False, "status": "stockout", "icon": "⚠",
         "spark": [54, 61, 70, 75, 80, 86]},
        {"label": "ارزش ریالی در جریان", "value": fa.fa_compact(482_300_000_000),
         "delta": "‎+۲٪", "delta_good": True, "status": "good", "icon": "💰"},
    ]


def insight_cards() -> List[dict]:
    """الگوی «Stats Card» صفحهٔ فیگمای Cash Flow — ادعای شواهدمحور، نه یک عدد تنها."""
    return [
        {"icon": "🔎", "headline": "شواهد رویداد فرآیند، با منشأ روشن",
         "body": "کد کیس ≠ کد ثبت سفارش / Case ID ≠ شناسهٔ سیستم مبدأ"},
    ]


def evidence_table() -> dict:
    """الگوی «Settlement / Evidence comparison» — همان پنل، ترجمه‌شده به دامنهٔ فرآیندکاوی."""
    return {
        "title": "شواهد رویداد در مرحلهٔ گلوگاه",
        "subtitle": "دانه: کد کیس × مرحله  |  زمان‌ها این صفحه نمونهٔ طراحی هستند",
        "columns": [
            {"key": "case", "label": "کد کیس"},
            {"key": "stage", "label": "مرحله"},
            {"key": "expected", "label": "زمان مورد انتظار"},
            {"key": "observed", "label": "زمان مشاهده‌شده"},
            {"key": "deviation", "label": "انحراف (روز)"},
        ],
        "rows": [
            {"case": fa.to_fa_digits("CASE-88213"), "stage": "ترخیص گمرکی",
             "expected": fa.to_fa_digits("3"), "observed": fa.to_fa_digits("11"),
             "deviation": fa.to_fa_digits("+8")},
        ],
        "source_meta": "منبع: ثبت رویداد سیستمی · نوع شاهد: Timestamp Log · زمان مشاهده: در شناسنامهٔ رویداد",
        "gap_warning": "شکاف شواهد: انحراف مشاهده‌شده لزوماً به‌معنای خطای عملیاتی نیست.",
        "gap_note": "بدون مقایسه با SLA قراردادی، از این انحراف نمی‌توان تخلف قطعی نتیجه گرفت.",
        "actions": ["دریافت Excel با شناسنامهٔ شواهد", "دریافت HTML مستقل"],
    }


def kanban_columns() -> List[dict]:
    return [
        {"title": "ثبت سفارش", "status": "good", "wip_limit": None, "cards": [
            {"title": "سفارش #۱۲۳۴۵", "tag": "واردات", "owner": "رضایی", "priority": "good", "age_days": 1},
            {"title": "سفارش #۱۲۳۵۰", "tag": "واردات", "owner": "احمدی", "priority": "good", "age_days": 2},
        ]},
        {"title": "تخصیص ارز", "status": "warning", "wip_limit": 6, "cards": [
            {"title": "سفارش #۱۲۳۰۱", "tag": "ارزی", "owner": "کریمی", "priority": "warning", "age_days": 5},
            {"title": "سفارش #۱۲۲۹۰", "tag": "ارزی", "owner": "رضایی", "priority": "warning", "age_days": 7},
            {"title": "سفارش #۱۲۲۸۸", "tag": "ارزی", "owner": "موسوی", "priority": "good", "age_days": 3},
        ]},
        {"title": "ترخیص گمرکی", "status": "stockout", "wip_limit": 5, "cards": [
            {"title": "سفارش #۱۲۲۵۰", "tag": "گمرک", "owner": "احمدی", "priority": "stockout", "age_days": 11},
            {"title": "سفارش #۱۲۲۴۰", "tag": "گمرک", "owner": "کریمی", "priority": "critical", "age_days": 14},
            {"title": "سفارش #۱۲۲۳۰", "tag": "گمرک", "owner": "موسوی", "priority": "stockout", "age_days": 9},
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
        {"label": "موتور فرآیندکاوی", "icon": "🧭", "sub": "استخراج رویداد", "status": "warning"},
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
