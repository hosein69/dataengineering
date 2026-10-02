# -*- coding: utf-8 -*-
"""مرحله ۷۰ — موتور امتیاز ریسک و هشدارهای ترکیبی."""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from ..dataio.logging_setup import log
from ..engines.criticality import CriticalityEngine
from ..engines.risk import PENALTY_BASE, SAME_CURRENCY_CAP, RiskScoreEngine
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
        cb = pd.to_numeric(df["CB_VALUE"], errors="coerce")
        max_cb = float(cb.max() or 1.0)
        rse = RiskScoreEngine(max_cb, ctx.rb)
        caps = self._same_currency_caps(df, cb, ctx)
        bases = self._penalty_bases(df, cb, ctx)
        scored = []
        for i, r in enumerate(df.to_dict("records")):
            if caps is not None:
                r[SAME_CURRENCY_CAP] = caps[i]
            if bases is not None:
                r[PENALTY_BASE] = bases[i]
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

    @staticmethod
    def _same_currency_caps(df: pd.DataFrame, cb: pd.Series, ctx: PipelineContext):
        """بزرگ‌ترین CB_VALUE هم‌ارز برای هر ردیف؛ ارز نامعلوم ⇒ 0 (بی‌سهم). بی ستون
        CB_CURRENCY (مارت قدیمی) None برمی‌گردد و موتور همان سقف کلی را به کار می‌برد."""
        if "CB_CURRENCY" not in df.columns:
            return None
        from ..finance.registration import currency_coder
        ccy = df["CB_CURRENCY"].map(currency_coder(getattr(ctx, "rb", None)))
        caps = cb.groupby(ccy).transform("max")
        return [float(c) if k and pd.notna(c) and c > 0 else 0.0 for k, c in zip(ccy, caps)]

    @staticmethod
    def _penalty_bases(df: pd.DataFrame, cb: pd.Series, ctx: PipelineContext):
        """مبنای «مواجهه با جریمه» به ارز خود جریمه، برای هر ردیف.

        جریمه از مانده تعهد NTSW حساب می‌شود، پس به ارز تعهد (NTSW_CURRENCY) است. CB_VALUE
        فقط وقتی مبناست که ارزش همان ارز باشد؛ وگرنه تعهد اولیه NTSW که به همان ارز است؛
        وگرنه None. تا دور ۷ جریمه یوانی بر ارزش دلاری تقسیم می‌شد. بی ستون‌های ارز
        (مارت قدیمی) None برمی‌گردد و موتور همان فرمول قبلی را به کار می‌برد."""
        if "NTSW_CURRENCY" not in df.columns or "CB_CURRENCY" not in df.columns:
            return None
        from ..finance.registration import currency_coder
        code = currency_coder(getattr(ctx, "rb", None))
        pen = df["NTSW_CURRENCY"].map(code)
        cbc = df["CB_CURRENCY"].map(code)
        init = (pd.to_numeric(df["NTSW_INITIAL_COMMIT"], errors="coerce") if "NTSW_INITIAL_COMMIT" in df.columns
                else pd.Series(float("nan"), index=df.index))
        out = []
        for p, c, v, i in zip(pen, cbc, cb, init):
            if p and p == c and pd.notna(v):
                out.append(float(v))
            elif p and pd.notna(i):
                out.append(float(i))
            else:
                out.append(None)
        return out

    def columns(self) -> List[ColumnSpec]:
        return [
            # after the four part states and their totals (29.15.12), not between them
            ColumnSpec("هشدار ترکیبی بحرانی", "هشدار ترکیبی بحرانی", 46,
                       GROUP_MAIN, wrap=True, order=10, color_rule="flag_nonempty"),
            ColumnSpec("امتیاز ریسک", "امتیاز ریسک", 14, GROUP_ANALYTIC,
                       fmt="decimal", order=84, color_rule="scale_high_bad"),
            ColumnSpec("طبقه ریسک", "طبقه ریسک", 16, GROUP_ANALYTIC, order=85),
        ]

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict]:
        return {"موتور امتیاز ریسک": {
            "فرمول": "امتیاز = Σ (وزن مؤلفه × مقدار نرمال‌شده ۰ تا ۱۰۰)",
            "ارزش در معرض خطر": ("CB_VALUE ÷ بزرگ‌ترین CB_VALUE همان ارز (CB_CURRENCY)؛ "
                                 "ارزش‌های دو ارز مقایسه نمی‌شوند و ارز نامعلوم سهم ارزشی ندارد"),
            "مواجهه با جریمه": (f"جریمه برآوردی ÷ ({float(ctx.rb.get('alarms.risk_engine.penalty_exposure_base_ratio', 0.10)) * 100:.0f}٪ "
                                "ارزش به ارز تعهد)؛ ارزش CB_VALUE اگر به ارز تعهد باشد، "
                                "وگرنه تعهد اولیه NTSW. جریمه و ارزش دو ارز بر هم تقسیم نمی‌شوند."),
            "وزن‌ها": ctx.rb.risk_weights(),
            "طبقه‌بندی": [f"≥{b['min']} {b['fa']}"
                          for b in ctx.rb.get("alarms.risk_engine.bands", [])],
            "منبع": "rules/alarms.yaml",
        }}

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        s = pd.to_numeric(df.get("امتیاز ریسک"), errors="coerce")
        # R8: شمار پرونده (سفارش) یکتا، نه ردیف؛ ردیف اول سفارش به ازای هر بارنامه
        # و هر متریال تکرار می‌شود. ردیف بی‌سفارش پرونده مستقل است.
        from ..studio_core.grain import first_key, unique_count
        flag = (df["هشدار ترکیبی بحرانی"].fillna("").astype(str).str.strip().ne("")
                if "هشدار ترکیبی بحرانی" in df.columns else pd.Series(False, index=df.index))
        n = unique_count(df[flag], first_key(df, "CANONICAL_ORDER", "KEY_ORDER") or "CANONICAL_ORDER")
        return {
            "میانگین امتیاز ریسک": (round(float(s.mean() or 0), 1), "موتور ۸ مؤلفه‌ای"),
            "هشدار ترکیبی بحرانی + پرونده مشکل‌دار": (
                n, "قطعه بحرانی با پرونده بلوکه یا رسوب"),
        }
