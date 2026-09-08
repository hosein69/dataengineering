# -*- coding: utf-8 -*-
"""قالب‌های گزارش — چیدمان از پیش تعریف‌شده برای خروجی Excel / HTML / PDF.

هر قالب فقط می‌گوید **کدام بخش‌ها** و **کدام فیلدهای پیش‌فرض** در سند
باشند. انتخاب نهایی فیلدها همیشه با کاربر است و قالب آن را بازنویسی
نمی‌کند؛ قالب فقط نقطه شروع و ترتیب بخش‌هاست.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from typing import Dict, List

#: بخش‌های قابل درج در گزارش
SECTIONS: Dict[str, str] = {
    "kpi":          "کارت‌های شاخص",
    "criticality":  "ترکیب طبقه بحرانی",
    "resistance":   "کم‌مقاومت‌ترین قطعات",
    "org":          "بار سازمانی",
    "table":        "جدول تفصیلی",
    "bottlenecks":  "گلوگاه گذارها",
    "variants":     "مسیرهای فرآیند",
    "conformance":  "انطباق و ریشه‌یابی",
    "eventlog":     "لاگ رویداد",
    "quality":      "کیفیت داده",
    "integrity":    "صحت محاسبات (دانه‌بندی)",
}

#: بخش‌هایی که ماهیتاً نمودارند (با خاموش کردن «ویژوال» حذف می‌شوند)
VISUAL_SECTIONS = {"criticality", "resistance", "org", "bottlenecks"}
#: بخش‌هایی که ماهیتاً جدول‌اند
TABLE_SECTIONS = {"table", "variants", "conformance", "eventlog", "quality", "integrity"}


@dataclass(frozen=True)
class ReportTemplate:
    key: str
    title: str
    description: str
    icon: str
    sections: List[str]
    default_fields: List[str] = field(default_factory=list)
    max_rows: int = 5000
    #: در PDF/چاپ، جدول تفصیلی به این تعداد ستون محدود می‌شود تا خوانا بماند
    print_max_cols: int = 12

    def active_sections(self, visuals: bool = True, tables: bool = True) -> List[str]:
        out = []
        for s in self.sections:
            if s in VISUAL_SECTIONS and not visuals:
                continue
            if s in TABLE_SECTIONS and not tables:
                continue
            out.append(s)
        return out


_EXEC_FIELDS = ["CANONICAL_BL", "CANONICAL_ORDER", "KEY_MATERIAL", "ORG_DEPT",
                "بحرانی (کوتاه)", "مقاومت (روز)", "مانده تعهد"]
_OPS_FIELDS = ["KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_REG",
               "CANONICAL_EXPERT", "ORG_DEPT", "روش حمل", "بحرانی (کوتاه)",
               "مقاومت (روز)", "BL_CRITICAL_REASON", "ORDER_CRITICAL_REASON"]
_PROC_FIELDS = ["CANONICAL_ORDER", "CANONICAL_BL", "ORG_DEPT", "CANONICAL_EXPERT",
                "بحرانی (کوتاه)"]
_AUDIT_FIELDS = ["KEY_BL", "KEY_ORDER", "KEY_REG", "KEY_MATERIAL",
                 "مانده تعهد", "مقاومت (روز)"]


TEMPLATES: Dict[str, ReportTemplate] = {
    "executive": ReportTemplate(
        key="executive", icon="◈", title="اجرایی",
        description="برای مدیریت — شاخص‌ها، ترکیب بحرانی و فهرست کوتاه موارد بحرانی.",
        sections=["kpi", "criticality", "resistance", "org", "table", "integrity"],
        default_fields=_EXEC_FIELDS, max_rows=500, print_max_cols=8),

    "operational": ReportTemplate(
        key="operational", icon="▦", title="عملیاتی",
        description="برای کارشناس — جدول تفصیلی کامل با همه فیلدهای انتخابی و فیلتر زنده.",
        sections=["kpi", "table", "quality", "integrity"],
        default_fields=_OPS_FIELDS, max_rows=20000, print_max_cols=14),

    "process": ReportTemplate(
        key="process", icon="⛓", title="فرآیندی",
        description="برای تحلیل فرآیند — گلوگاه، مسیرها، انطباق و لاگ رویداد.",
        sections=["kpi", "bottlenecks", "variants", "conformance", "eventlog", "integrity"],
        default_fields=_PROC_FIELDS, max_rows=5000, print_max_cols=10),

    "audit": ReportTemplate(
        key="audit", icon="◍", title="ممیزی داده",
        description="برای کنترل صحت — دانه‌بندی، دوباره‌شماری، پرشدگی و رابطه‌ها.",
        sections=["integrity", "quality", "table"],
        default_fields=_AUDIT_FIELDS, max_rows=5000, print_max_cols=10),
}

DEFAULT_TEMPLATE = "executive"


def get(key: str) -> ReportTemplate:
    return TEMPLATES.get(key, TEMPLATES[DEFAULT_TEMPLATE])
