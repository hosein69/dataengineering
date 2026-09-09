# -*- coding: utf-8 -*-
"""مرحله ۴۰ — مقاومت قطعه و بحرانی بودن.

نمونه کامل «یک قابلیت = یک فایل»: موتور، ستون‌های گزارش و KPIهای این قابلیت
همه اینجا اعلام می‌شوند. حذف این فایل، قابلیت را بدون خطا از سیستم برمی‌دارد.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .. import health
from ..dataio.logging_setup import log
from ..engines.criticality import CriticalityEngine
from .base import (ColumnSpec, GROUP_MAIN, PipelineContext, Stage, register)


@register
class CriticalityStage(Stage):
    name = "criticality"
    title = "محاسبه مقاومت قطعه (موجودی ÷ مصرف روزانه)"
    order = 40
    requires = ["STOCK_IKCO", "STOCK_SAPCO", "DAILY_NEED"]
    provides = ["مقاومت (روز)", "مقاومت انبار (روز)", "طبقه بحرانی",
                "بحرانی (کوتاه)", "کد طبقه بحرانی", "CRITICALITY_SORT",
                "اقدام پیشنهادی مقاومت", "موجودی ایران خودرو", "موجودی ساپکو",
                "موجودی کل قابل احتساب", "نیاز روزانه", "موجودی در راه",
                "موجودی در گمرک", "مقاومت انبار (روز)",
                "PART_CRITICALITY_SCORE",
                "BL_CRITICAL", "BL_CRITICAL_LEVEL", "BL_CRITICAL_MATERIALS",
                "BL_CRITICAL_REASON", "ORDER_CRITICAL", "ORDER_CRITICAL_LEVEL",
                "ORDER_CRITICAL_MATERIALS", "ORDER_CRITICAL_REASON"]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        eng = CriticalityEngine(ctx.rb)
        results = [eng.evaluate(r) for r in df.to_dict("records")]
        # سلول موجودی که عدد نیست ⇒ ردیف به «نامشخص» رفت، نه به توقف خط.
        # این تفاوت باید دیده شود، وگرنه کاهش ناگهانی «توقف خط» بی‌توضیح می‌ماند.
        bad = getattr(eng, "unreadable_cells", {})
        if bad:
            detail = "، ".join(f"{k}: {v}" for k, v in sorted(bad.items()))
            log.warning(f"⚠️ سلول‌های غیرعددی در ستون‌های موجودی/نیاز — {detail}. "
                        f"این ردیف‌ها «نامشخص» شدند، نه «توقف خط».")
            health.current().find(
                "کیفیت عدد", health.WARN,
                f"{sum(bad.values())} سلول غیرعددی در ستون‌های موجودی/نیاز",
                f"{detail} — این ردیف‌ها به طبقه «نامشخص» رفتند تا هشدار "
                f"توقف خط از روی داده ناخوانا ساخته نشود.")
        if results:
            for k in results[0].as_dict():
                df[k] = [r.as_dict()[k] for r in results]
        df["PART_CRITICALITY_SCORE"] = [r.risk_score for r in results]

        known = int(df["کد طبقه بحرانی"].ne("UNKNOWN").sum())
        if known == 0:
            log.critical(
                "🚨 مقاومت هیچ قطعه‌ای محاسبه نشد — سورس Oracle موجودی/مصرف نداد.\n"
                "   ⇒ نام ستون واقعی را به OracleAdapter.COLUMN_MAP اضافه کنید.")
        else:
            log.info(f"🔧 مقاومت محاسبه شد برای {known} از {len(df)} ردیف — "
                     f"{df['بحرانی (کوتاه)'].value_counts().to_dict()}")
        # ── بحرانی بودن در سطح بارنامه/سفارش ──
        # قاعده کسب‌وکار: وجود حتی یک متریال STOCKOUT/CRITICAL، کل
        # بارنامه/سفارش را بحرانی می‌کند؛ اما علت باید تا سطح همان متریال
        # قابل drill-down باقی بماند. BECOMING فقط «در حال بحرانی شدن» است.
        critical_codes = {"STOCKOUT", "CRITICAL"}
        severity = {"UNKNOWN": 0, "SAFE": 0, "WATCH": 1,
                    "BECOMING_CRITICAL": 2, "CRITICAL": 3, "STOCKOUT": 4}

        def group_info(g: pd.DataFrame):
            actionable = g[g["کد طبقه بحرانی"].isin(critical_codes)].copy()
            if actionable.empty:
                # سطح هشدار گروه برای نمایش روندی، بدون تبدیل «در حال بحرانی» به بحران
                codes = [str(x) for x in g["کد طبقه بحرانی"].dropna().tolist()]
                level = max(codes, key=lambda x: severity.get(x, 0), default="UNKNOWN")
                return False, level, "", ""
            actionable["_sev"] = actionable["کد طبقه بحرانی"].map(severity).fillna(0)
            actionable = actionable.sort_values(["_sev", "مقاومت (روز)"], ascending=[False, True])
            mats=[]; reasons=[]
            for _, r in actionable.drop_duplicates(subset=["KEY_MATERIAL"]).head(5).iterrows():
                mat=str(r.get("KEY_MATERIAL", "")).strip() or "متریال نامشخص"
                band=str(r.get("بحرانی (کوتاه)", r.get("کد طبقه بحرانی", "")))
                days=r.get("مقاومت (روز)")
                d="نامشخص" if pd.isna(days) else f"{float(days):.1f} روز"
                mats.append(mat); reasons.append(f"{mat}: {band} ({d})")
            level=str(actionable.iloc[0]["کد طبقه بحرانی"])
            return True, level, "، ".join(mats), " | ".join(reasons)

        def attach(prefix: str, key: str):
            flags={}; levels={}; mats={}; reasons={}
            if key not in df.columns:
                return
            for value, g in df.groupby(key, dropna=False, sort=False):
                k="" if pd.isna(value) else str(value).strip()
                if not k:
                    continue
                flags[k], levels[k], mats[k], reasons[k]=group_info(g)
            df[f"{prefix}_CRITICAL"] = df[key].map(flags).astype("boolean").fillna(False).astype(bool)
            df[f"{prefix}_CRITICAL_LEVEL"] = df[key].map(levels).fillna("UNKNOWN")
            df[f"{prefix}_CRITICAL_MATERIALS"] = df[key].map(mats).fillna("")
            df[f"{prefix}_CRITICAL_REASON"] = df[key].map(reasons).fillna("")

        attach("BL", "CANONICAL_BL")
        attach("ORDER", "CANONICAL_ORDER")
        ctx.extras["criticality_known"] = known
        ctx.extras["critical_group_rule"] = "هر بارنامه/سفارش با حداقل یک متریال STOCKOUT یا CRITICAL بحرانی است؛ علت تا سطح متریال ثبت می‌شود."
        return df

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("طبقه بحرانی", "طبقه بحرانی", 22, GROUP_MAIN, order=1),
            ColumnSpec("مقاومت (روز)", "مقاومت (روز)", 14, GROUP_MAIN,
                       fmt="decimal", order=2, color_rule="scale_low_bad"),
            ColumnSpec("موجودی ایران خودرو", "موجودی ایران‌خودرو", 13, GROUP_MAIN, fmt="decimal", order=3),
            ColumnSpec("موجودی ساپکو", "موجودی ساپکو", 12, GROUP_MAIN, fmt="decimal", order=4),
            ColumnSpec("موجودی کل قابل احتساب", "موجودی کل", 12, GROUP_MAIN, fmt="decimal", order=5),
            ColumnSpec("نیاز روزانه", "نیاز روزانه", 14, GROUP_MAIN,
                       fmt="decimal", order=4),
            ColumnSpec("BL_CRITICAL", "بحرانی بودن بارنامه", 16, GROUP_MAIN, order=28),
            ColumnSpec("BL_CRITICAL_MATERIALS", "متریال بحرانی بارنامه", 34, GROUP_MAIN, wrap=True, order=29),
            ColumnSpec("BL_CRITICAL_REASON", "علت بحرانی بودن بارنامه", 58, GROUP_MAIN, wrap=True, order=30),
            ColumnSpec("ORDER_CRITICAL", "بحرانی بودن سفارش", 16, GROUP_MAIN, order=31),
            ColumnSpec("ORDER_CRITICAL_MATERIALS", "متریال بحرانی سفارش", 34, GROUP_MAIN, wrap=True, order=32),
            ColumnSpec("ORDER_CRITICAL_REASON", "علت بحرانی بودن سفارش", 58, GROUP_MAIN, wrap=True, order=33),
        ]

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict]:
        bands = ctx.rb.get("criticality.bands", []) or []
        return {"مقاومت قطعه": {
            "فرمول": "مقاومت (روز) = (ایران‌خودرو + ساپکو + در راه + در گمرک) ÷ نیاز روزانه",
            "طبقه‌بندی": [f"{b.get('fa')}" for b in bands],
            "کالای در راه": ("لحاظ نمی‌شود" if not ctx.rb.get(
                "criticality.formula.include_in_transit", False) else "لحاظ می‌شود"),
            "منبع": "rules/criticality.yaml",
        }}

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        def n(code: str) -> int:
            if "کد طبقه بحرانی" not in df or "KEY_MATERIAL" not in df:
                return 0
            return int(df.loc[df["کد طبقه بحرانی"] == code, "KEY_MATERIAL"]
                       .replace("", np.nan).nunique())

        low = pd.to_numeric(df.get("مقاومت (روز)"), errors="coerce").min()
        return {
            "🔴 قطعات با توقف خط (موجودی صفر)": (n("STOCKOUT"), "مقاومت صفر"),
            "🔴 قطعات بحرانی (مقاومت زیر ۱۰ روز)": (n("CRITICAL"), "نیازمند اقدام فوری"),
            "🟠 در حال بحرانی شدن (۱۰ تا ۲۰ روز)": (n("BECOMING_CRITICAL"), "پیگیری هفتگی"),
            "کمترین مقاومت (روز)": (round(float(low or 0), 1), "بحرانی‌ترین قطعه"),
        }
