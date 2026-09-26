# -*- coding: utf-8 -*-
"""Shared chart catalog for Studio HTML, email and Excel.

The catalog is presentation-only: chart selection never changes source data.
Each key has a Persian title, a business question and graceful fallbacks so an
empty process log does not leave a blank dashboard on day one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class ChartSpec:
    key: str
    title: str
    group: str
    kind: str
    question: str
    requires_any: Tuple[str, ...] = ()


_SPECS = [
    ChartSpec("criticality", "ترکیب وضعیت بحرانی قطعات", "ریسک تولید", "donut", "چند قطعه در آستانه توقف خط است؟", ("کد طبقه بحرانی","بحرانی (کوتاه)")),
    ChartSpec("low_resistance", "۱۰ قطعه با کمترین مقاومت", "ریسک تولید", "bar", "کدام قطعات باید امروز پیگیری شوند؟", ("مقاومت (روز)",)),
    ChartSpec("stock_vs_total", "مقاومت انبار در برابر مقاومت کل", "ریسک تولید", "grouped", "چه میزان از پوشش به کالای در راه/گمرک وابسته است؟", ("مقاومت انبار (روز)","مقاومت (روز)")),
    ChartSpec("sediment_vs_resistance", "مقاومت در برابر روزهای رسوب", "ریسک تولید", "scatter", "کدام پرونده هم رسوب بالا و هم مقاومت پایین دارد؟", ("روزهای رسوب","مقاومت (روز)")),
    ChartSpec("risk_mix", "ترکیب سبد ریسک", "ریسک و تعهد", "donut", "ترکیب ریسک پرونده‌ها چگونه است؟", ("طبقه ریسک",)),
    ChartSpec("commitment", "مانده تعهد بر حسب وضعیت مهلت", "ریسک و تعهد", "bar", "چه مبلغی در معرض جریمه/تأخیر است؟", ("مانده تعهد",)),
    ChartSpec("overdue_bucket", "توزیع پرونده‌ها بر حسب روزهای تأخیر", "ریسک و تعهد", "bar", "انباشت تأخیر در چه بازه‌ای است؟", ("روزهای تأخیر",)),
    ChartSpec("delay_vs_commitment", "مانده تعهد در برابر روزهای تأخیر", "ریسک و تعهد", "scatter", "جریمه کجا انباشته می‌شود: پرونده بزرگ یا کهنه؟", ("مانده تعهد","روزهای تأخیر")),
    ChartSpec("pareto_delay", "تمرکز تأخیر — قاعده ۸۰/۲۰", "ریسک و تعهد", "bar", "چند درصد از کل تأخیر روی چند پرونده متمرکز است؟", ("روزهای تأخیر",)),
    ChartSpec("org_workload", "بار کاری واحدهای سازمانی", "سازمان", "bar", "پرونده‌ها روی کدام واحدها متمرکز شده‌اند؟", ("ORG_DEPT","ORG_VICE")),
    ChartSpec("expert_workload", "بار کاری کارشناسان", "سازمان", "bar", "بار عملیاتی روی کدام کارشناسان است؟", ("CANONICAL_EXPERT",)),
    ChartSpec("transport_mix", "ترکیب شیوه حمل", "حمل و لجستیک", "donut", "سبد حمل چگونه توزیع شده است؟", ("TRANSPORT_MODE",)),
    ChartSpec("stage_distribution", "توزیع مرحله فعلی پرونده‌ها", "فرآیند", "bar", "پرونده‌ها اکنون در کدام مرحله متوقف‌اند؟", ("STAGE_FA","ORDER_STAGE_FA","LIFECYCLE_STAGE")),
    ChartSpec("bottlenecks", "گلوگاه فرآیند / وضعیت جایگزین", "فرآیند", "bar", "کدام گذار بیشترین انتظار را دارد؟", ("STAGE_FA","ORDER_STAGE_FA")),
    ChartSpec("top_orders", "سفارش‌های دارای بیشترین اقلام/پرونده", "تأمین", "bar", "تمرکز عملیات روی کدام سفارش‌هاست؟", ("CANONICAL_ORDER",)),
    ChartSpec("top_bl", "بارنامه‌های دارای بیشترین اقلام/پرونده", "حمل و لجستیک", "bar", "کدام بارنامه‌ها بیشترین درگیری عملیاتی دارند؟", ("CANONICAL_BL",)),
    ChartSpec("supplier_mix", "تمرکز تأمین‌کنندگان", "تأمین", "bar", "ریسک تمرکز تأمین روی کدام Vendor/Supplier است؟", ("SUPPLIER","VENDOR_CODE","MFR_VENDOR_CODE")),
]

CHART_SPECS: Dict[str, ChartSpec] = {s.key: s for s in _SPECS}
CHART_TITLES: Dict[str, str] = {s.key: s.title for s in _SPECS}
CHART_GROUPS = tuple(dict.fromkeys(s.group for s in _SPECS))
DEFAULT_HTML_CHARTS = ["criticality","low_resistance","stage_distribution","org_workload","transport_mix","commitment"]
DEFAULT_EMAIL_CHARTS = ["criticality","low_resistance","stage_distribution","commitment"]


def grouped_catalog() -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for s in _SPECS:
        out.setdefault(s.group, {})[s.key] = s.title
    return out

# V28 is the presentation source of truth for titles/questions. Keep the richer
# catalog metadata/kinds from V26.18 while aligning user-visible labels with V28.
try:
    from .designs import EMAIL_CHARTS as _V28_TITLES, CHART_QUESTIONS as _V28_QUESTIONS
    CHART_TITLES.update(_V28_TITLES)
    for _k, _q in _V28_QUESTIONS.items():
        if _k in CHART_SPECS:
            pass
except Exception:
    pass
