# -*- coding: utf-8 -*-
"""مرحله ۶۰ — راوی شناختی فارسی."""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from ..core.text import is_empty_val
from ..narrate.narrator import DynamicGranularNarrator
from .base import (ColumnSpec, GROUP_ANALYTIC, GROUP_MAIN, PipelineContext,
                   Stage, register)


@register
class NarrateStage(Stage):
    name = "narrate"
    title = "تولید روایت و پیشنهاد عملیاتی"
    order = 60
    # این requires همان گاردی است که باگ B1 را برای همیشه می‌بندد:
    # راوی نمی‌تواند پیش از ساخت ستون‌های شاهد اجرا شود.
    requires = ["CANONICAL_BL", "COTAGE_NO", "SATA_NO", "DISCHARGE_DATE",
                "وضعیت کلی هشدار"]
    provides = ["روایت اختصاصی بارنامه", "پیشنهاد عملیاتی هوش مصنوعی",
                "درصد قطعیت", "روزهای رسوب", "وضعیت هوشمند",
                "احتمال بقای ویبول (٪)", "احتمال حضور در گمرک (٪)",
                "وضعیت سیستمی دوگانه"]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        records = df.to_dict("records")
        out = [DynamicGranularNarrator.generate(
            r, ctx.today, ctx.resolver.conflict_for_bl(r.get("CANONICAL_BL", "")),
            validate=False).as_dict() for r in records]
        if out:
            for k in out[0]:
                df[k] = [o[k] for o in out]

        customs = np.where(df["FULL_CLEAR_DATE"].map(is_empty_val),
                           "در جریان ترخیص", "ترخیص شده")
        banking = np.where(df["وضعیت کلی هشدار"].eq(ctx.rb.status_label("red")),
                           "تعهد معوق", "تعهد در مهلت")
        df["وضعیت سیستمی دوگانه"] = [f"{c} | {b}" for c, b in zip(customs, banking)]
        return df

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("وضعیت هوشمند", "وضعیت هوشمند", 20, GROUP_MAIN, order=24),
            ColumnSpec("وضعیت سیستمی دوگانه", "وضعیت سیستمی دوگانه", 28,
                       GROUP_MAIN, order=25),
            ColumnSpec("روایت اختصاصی بارنامه", "روایت شناختی اختصاصی", 60,
                       GROUP_MAIN, wrap=True, order=26),
            ColumnSpec("پیشنهاد عملیاتی هوش مصنوعی", "پیشنهاد عملیاتی", 50,
                       GROUP_MAIN, wrap=True, order=27),
            ColumnSpec("روزهای رسوب", "روزهای رسوب", 14, GROUP_ANALYTIC,
                       fmt="decimal", order=80),
            ColumnSpec("درصد قطعیت", "قطعیت (٪)", 12, GROUP_ANALYTIC,
                       fmt="decimal", order=81),
            ColumnSpec("احتمال بقای ویبول (٪)", "بقای ویبول (٪)", 14,
                       GROUP_ANALYTIC, fmt="decimal", order=82),
            ColumnSpec("احتمال حضور در گمرک (٪)", "احتمال گمرک (٪)", 14,
                       GROUP_ANALYTIC, fmt="decimal", order=83),
        ]

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict]:
        rb = ctx.rb
        return {
            "تحلیل بقای ویبول": {
                "فرمول": "S(t) = exp(-(t/η)^β) × ۱۰۰",
                "β (پارامتر شکل)": rb.get("customs.survival_model.beta"),
                "η (پارامتر مقیاس، روز)": rb.get("customs.survival_model.eta_days"),
                "منبع پارامترها": "rules/customs.yaml",
            },
            "احتمال بیزین حضور در گمرک": {
                "فرمول": "P(H|E) = P(E|H)·P(H) / [P(E|H)·P(H) + P(E|¬H)·P(¬H)]",
                "پیشین P(H)": rb.get("customs.customs_presence_model.prior"),
                "نرخ شاهد کاذب P(E|¬H)": rb.get(
                    "customs.customs_presence_model.false_positive_rate"),
                "وزن شواهد": rb.get("customs.customs_presence_model.evidence_weights"),
            },
        }

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        num = lambda c: pd.to_numeric(df.get(c), errors="coerce")  # noqa: E731
        return {
            "میانگین روزهای رسوب": (round(float(num("روزهای رسوب").mean() or 0), 1),
                                     "از تاریخ تخلیه"),
            "میانگین قطعیت داده (٪)": (round(float(num("درصد قطعیت").mean() or 0), 1),
                                        "شاخص کیفیت داده"),
        }
