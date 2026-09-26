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
    title = "مهلت کنترلی، سناریوی جریمه و هشدارهای رفع تعهد ارزی"
    order = 50
    requires = ["SEGMENT", "CB_DATE", "BALANCE"]
    provides = ["نوع پرونده", "کد سگمنت", "روش پرداخت", "نوع ترخیص", "برات/یوزانس",
                "مهلت قانونی رفع تعهد", "روزهای تأخیر", "مانده تعهد",
                "جریمه برآوردی", "وضعیت کلی هشدار", "شرح هشدارها",
                "مبنای مهلت تعهد", "مبنای جریمه", "LEGAL_DEADLINE_DAYS"]

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
            ColumnSpec("جریمه برآوردی", "جریمه سناریویی", 18, GROUP_ANALYTIC,
                       fmt="currency", order=87),
            ColumnSpec("وضعیت کلی هشدار", "وضعیت هشدار تعهد", 16, GROUP_ANALYTIC,
                       order=88),
            ColumnSpec("مبنای مهلت تعهد", "اعتبار مبنای مهلت", 38, GROUP_ANALYTIC,
                       wrap=True, order=88),
            ColumnSpec("مبنای جریمه", "اعتبار مبنای جریمه", 38, GROUP_ANALYTIC,
                       wrap=True, order=88),
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
        # سنجه‌های تعهد در سطح REG هستند و پس از join ممکن است fan-out شوند.
        from ..studio_core.grain import safe_agg
        red = ctx.rb.status_label("red")
        has_fin_contract = (
            any(c in df.columns for c in ("KEY_REG", "CANONICAL_REG"))
            and any(c in df.columns for c in ("NTSW_CURRENCY", "CURRENCY", "ارز"))
        )
        if has_fin_contract:
            from ..report.financial_summary import commitment_display, penalty_display
            balance_value = commitment_display(df)
            penalty_value = penalty_display(df)
            balance_note = "سورس NTSW — دانه REG و تفکیک ارز؛ جمع بین ارزهای متفاوت ممنوع"
            penalty_note = "سناریوی داخلی طبق fx_governance.yaml — دانه REG و تفکیک ارز"
        else:
            # قرارداد backward-compatible برای تست/داده تاریخی فاقد ستون ارز.
            balance_value = round(safe_agg(df, "مانده تعهد", "sum"), 2)
            penalty_value = round(safe_agg(df, "جریمه برآوردی", "sum"), 2)
            balance_note = "سورس NTSW — تجمیع دانه‌ای REG؛ ستون ارز در داده موجود نیست"
            penalty_note = "سناریوی داخلی — تجمیع دانه‌ای REG؛ ستون ارز در داده موجود نیست"
        return {
            "تعهدات با هشدار قرمز": (int((df.get("وضعیت کلی هشدار") == red).sum()),
                                      "عبور از آستانه کنترلی RuleBook؛ مبنای حقوقی در ستون مجزا"),
            "جمع مانده تعهد": (balance_value, balance_note),
            "جمع جریمه برآوردی": (penalty_value, penalty_note),
        }
