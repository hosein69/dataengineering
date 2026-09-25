# -*- coding: utf-8 -*-
"""پیش‌فرض‌های چیدمان — یک نسخه برای هر سطح مخاطب.

این‌ها فقط **دادهٔ اولیه** هستند. با :func:`pm_ui.layout.engine.save_layout`
می‌توان نسخهٔ ویرایش‌شده را روی فولدر شبکه ذخیره کرد تا مدیر محصول بدون
دست‌زدن به کد، چیدمان هر سطح را شخصی‌سازی کند.

سه سطح مخاطب:
    executive   مدیرعامل/هیئت‌مدیره — فقط KPI و جمع‌بندی، بدون جزئیات عملیاتی
    manager     مدیر فرآیند — KPI + نقشهٔ جریان + گلوگاه‌ها
    analyst     کارشناس/اپراتور — همهٔ بلوک‌ها + تخته کانبان عملیاتی
"""
from __future__ import annotations

from typing import List

from .engine import BlockSpec

DEFAULT_LAYOUT: List[BlockSpec] = [
    {"id": "kpi", "type": "kpi_row", "size": "full", "order": 0,
     "visible_for": [], "props": {}},
    {"id": "flow", "type": "process_flow", "title": "نقشهٔ جریان فرآیند", "size": "half",
     "order": 1, "visible_for": ["manager", "analyst"], "props": {}},
    {"id": "intensity", "type": "intensity_chart", "title": "روند حجم کیس",
     "size": "half", "order": 2, "visible_for": ["executive", "manager", "analyst"], "props": {}},
    {"id": "heatmap", "type": "heatmap", "title": "شدت فعالیت هفتگی", "size": "half",
     "order": 3, "visible_for": ["manager", "analyst"], "props": {}},
    {"id": "system", "type": "system_flow", "title": "خط لولهٔ سیستمی", "size": "half",
     "order": 4, "visible_for": ["manager", "analyst"], "props": {}},
    {"id": "kanban", "type": "kanban", "title": "وضعیت کیس‌ها در هر مرحله", "size": "full",
     "order": 5, "visible_for": ["analyst"], "props": {}},
]

AUDIENCES = ("executive", "manager", "analyst")
AUDIENCE_LABELS = {"executive": "مدیرعامل / هیئت‌مدیره", "manager": "مدیر فرآیند",
                    "analyst": "کارشناس / اپراتور"}
