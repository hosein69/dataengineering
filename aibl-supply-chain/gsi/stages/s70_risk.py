# -*- coding: utf-8 -*-
"""مرحله ۷۰ — موتور امتیاز ریسک و هشدارهای ترکیبی."""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from ..dataio.logging_setup import log
from ..engines.criticality import CriticalityEngine
from ..engines.risk import RiskScoreEngine
from .base import (ColumnSpec, GROUP_ANALYTIC, GROUP_MAIN, PipelineContext,
                   Stage, register)


@register
class RiskStage(Stage):
    name = "risk"
    title = "امتیاز ریسک ۰–۱۰۰ و هشدار ترکیبی بحرانی"
    order = 70
    requires = ["روزهای رسوب", "جریمه برآوردی", "CB_VALUE",
                "PART_CRITICALITY_SCORE", "LEGAL_DEADLINE_DAYS"]
    provides = ["امتیاز ریسک", "طبقه ریسک",
                "هشدار ترکیبی بحرانی", "اقدام هشدار ترکیبی"]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        max_cb = float(pd.to_numeric(df["CB_VALUE"], errors="coerce").max() or 1.0)
        rse = RiskScoreEngine(max_cb, ctx.rb)
        scored = []
        for r in df.to_dict("records"):
            r["ELAPSED_DAYS"] = r.get("روزهای رسوب", 0)
            r["STUCK_DAYS"] = r.get("روزهای رسوب", 0)
            r["PENALTY"] = r.get("جریمه برآوردی", 0)
            scored.append(rse.score(r))
        df["امتیاز ریسک"] = [s.score for s in scored]
        df["طبقه ریسک"] = [s.band for s in scored]

        eng = CriticalityEngine(ctx.rb)
        alerts = [eng.combined_alerts(r) for r in df.to_dict("records")]
        df["هشدار ترکیبی بحرانی"] = [" ؛ ".join(a["fa"] for a in lst) for lst in alerts]
        df["اقدام هشدار ترکیبی"] = [" ؛ ".join(a["action"] for a in lst) for lst in alerts]
        n = sum(1 for lst in alerts if lst)
        if n:
            log.warning(f"🚨 {n} ردیف هشدار ترکیبی «قطعه بحرانی + پرونده مشکل‌دار» دارند.")
        return df

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("هشدار ترکیبی بحرانی", "هشدار ترکیبی بحرانی", 46,
                       GROUP_MAIN, wrap=True, order=5, color_rule="flag_nonempty"),
            ColumnSpec("امتیاز ریسک", "امتیاز ریسک", 14, GROUP_ANALYTIC,
                       fmt="decimal", order=84, color_rule="scale_high_bad"),
            ColumnSpec("طبقه ریسک", "طبقه ریسک", 16, GROUP_ANALYTIC, order=85),
        ]

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict]:
        return {"موتور امتیاز ریسک": {
            "فرمول": "امتیاز = Σ (وزن مؤلفه × مقدار نرمال‌شده ۰ تا ۱۰۰)",
            "وزن‌ها": ctx.rb.risk_weights(),
            "طبقه‌بندی": [f"≥{b['min']} {b['fa']}"
                          for b in ctx.rb.get("alarms.risk_engine.bands", [])],
            "منبع": "rules/alarms.yaml",
        }}

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        s = pd.to_numeric(df.get("امتیاز ریسک"), errors="coerce")
        n = int(df.get("هشدار ترکیبی بحرانی", pd.Series(dtype=str))
                .astype(str).str.strip().ne("").sum())
        return {
            "میانگین امتیاز ریسک": (round(float(s.mean() or 0), 1), "موتور ۸ مؤلفه‌ای"),
            "هشدار ترکیبی بحرانی + پرونده مشکل‌دار": (
                n, "قطعه بحرانی با پرونده بلوکه یا رسوب"),
        }
