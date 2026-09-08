# -*- coding: utf-8 -*-
"""مرحله ۵۰ — موتور رفع تعهد ارزی."""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from ..engines.commitment import CommitmentEngine
from .base import (ColumnSpec, GROUP_ANALYTIC, GROUP_DETAIL, GROUP_MAIN,
                   PipelineContext, Stage, register)


@register
class CommitmentStage(Stage):
    name = "commitment"
    title = "مهلت قانونی، جریمه و هشدارهای رفع تعهد ارزی"
    order = 50
    requires = ["SEGMENT", "CB_DATE", "BALANCE"]
    provides = ["نوع پرونده", "کد سگمنت", "روش پرداخت", "نوع ترخیص", "برات/یوزانس",
                "مهلت قانونی رفع تعهد", "روزهای تأخیر", "مانده تعهد",
                "جریمه برآوردی", "وضعیت کلی هشدار", "شرح هشدارها",
                "LEGAL_DEADLINE_DAYS"]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        eng = CommitmentEngine(ctx.rb)
        results = [eng.evaluate(r, ctx.today).as_dict() for r in df.to_dict("records")]
        if results:
            for k in results[0]:
                df[k] = [r[k] for r in results]
        df["LEGAL_DEADLINE_DAYS"] = df["کد سگمنت"].map(ctx.rb.release_deadline_days)
        return df

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("نوع ترخیص", "نوع ترخیص", 16, GROUP_DETAIL, order=68),
            ColumnSpec("روش پرداخت", "روش پرداخت", 16, GROUP_DETAIL, order=69),
            ColumnSpec("مانده تعهد", "مانده تعهد", 18, GROUP_ANALYTIC,
                       fmt="currency", order=86),
            ColumnSpec("جریمه برآوردی", "جریمه برآوردی", 18, GROUP_ANALYTIC,
                       fmt="currency", order=87),
            ColumnSpec("وضعیت کلی هشدار", "وضعیت هشدار تعهد", 16, GROUP_ANALYTIC,
                       order=88),
        ]

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict]:
        rb = ctx.rb
        return {"مهلت و جریمه رفع تعهد": {
            "مهلت تولیدی (روز)": rb.release_deadline_days("production"),
            "مهلت بازرگانی (روز)": rb.release_deadline_days("commercial"),
            "جریمه": "؛ ".join(
                f"{t.get('fa')}" for t in
                rb.get("fx_governance.penalties.delay_tiers", []) or []),
            "منبع": "rules/fx_governance.yaml",
        }}

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        red = ctx.rb.status_label("red")
        num = lambda c: pd.to_numeric(df.get(c), errors="coerce")  # noqa: E731
        return {
            "تعهدات با هشدار قرمز": (int((df.get("وضعیت کلی هشدار") == red).sum()),
                                      "عبور از مهلت قانونی"),
            "جمع مانده تعهد": (round(float(num("مانده تعهد").sum() or 0), 2), "سورس NTSW"),
            "جمع جریمه برآوردی": (round(float(num("جریمه برآوردی").sum() or 0), 2),
                                   "پلکانی طبق fx_governance.yaml"),
        }
