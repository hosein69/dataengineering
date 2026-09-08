# -*- coding: utf-8 -*-
"""قالب‌های گزارش عملکرد."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

SECTIONS: Dict[str, str] = {
    "summary": "خلاصه اجرایی",
    "leaderboard": "جدول عملکرد",
    "clusters": "نمای کلاستری",
    "contribution": "تحلیل سهم شاخص‌ها",
    "causal": "گراف علّی و اثرها",
    "peers": "گروه‌های همتا",
    "calibration": "کالیبراسیون و شواهد",
    "weights": "وزن‌های مدل",
}
VISUAL_SECTIONS = {"clusters", "causal", "contribution"}
TABLE_SECTIONS = {"leaderboard", "peers", "calibration", "weights"}


@dataclass(frozen=True)
class ReportTemplate:
    key: str
    icon: str
    title: str
    description: str
    sections: List[str] = field(default_factory=list)
    max_rows: int = 500

    def active_sections(self, visuals: bool = True, tables: bool = True) -> List[str]:
        out = []
        for s in self.sections:
            if s in VISUAL_SECTIONS and not visuals:
                continue
            if s in TABLE_SECTIONS and not tables:
                continue
            out.append(s)
        return out


TEMPLATES: Dict[str, ReportTemplate] = {
    "executive": ReportTemplate(
        "executive", "◈", "اجرایی",
        "برای مدیریت — خلاصه، رتبه‌بندی درون‌گروهی و نمای کلاستری.",
        ["summary", "clusters", "leaderboard", "weights"], 200),
    "manager": ReportTemplate(
        "manager", "👤", "مدیر واحد",
        "برای مدیر — تیم خودش، سهم شاخص‌ها و گروه همتا.",
        ["summary", "leaderboard", "contribution", "peers"], 500),
    "causal": ReportTemplate(
        "causal", "🕸", "تحلیل علّی",
        "اثر تعدیل‌شده در برابر همبستگی خام، و حساسیت به مخدوش‌کننده.",
        ["summary", "causal", "calibration"], 300),
    "audit": ReportTemplate(
        "audit", "◍", "ممیزی مدل",
        "کالیبراسیون، پوشش، شواهد، گروه‌های همتا و وزن‌ها.",
        ["calibration", "peers", "weights", "leaderboard"], 1000),
}
DEFAULT_TEMPLATE = "executive"


def get(key: str) -> ReportTemplate:
    return TEMPLATES.get(key, TEMPLATES[DEFAULT_TEMPLATE])
