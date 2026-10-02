# -*- coding: utf-8 -*-
"""مرحله ۴۰ — مقاومت قطعه و بحرانی بودن.

نمونه کامل «یک قابلیت = یک فایل»: موتور، ستون‌های گزارش و KPIهای این قابلیت
همه اینجا اعلام می‌شوند. حذف این فایل، قابلیت را بدون خطا از سیستم برمی‌دارد.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from ..dataio.logging_setup import log
from ..engines.criticality import CriticalityEngine
from .base import (ColumnSpec, GROUP_MAIN, PipelineContext, Stage, register)


@register
class CriticalityStage(Stage):
    name = "criticality"
    title = "محاسبه مقاومت قطعه (IKCO + SAPCO ÷ نیاز روزانه) + مقاومت‌های زنجیره"
    order = 40
    requires = ["STOCK_IKCO", "STOCK_SAPCO", "SUPPLIER_QTY", "READY_QTY", "IN_TRANSIT_QTY",
                "IN_CUSTOMS_QTY", "DAILY_NEED"]
    provides = ["مقاومت (روز)", "مقاومت انبار (روز)", "طبقه بحرانی",
                "بحرانی (کوتاه)", "کد طبقه بحرانی", "CRITICALITY_SORT",
                "اقدام پیشنهادی مقاومت", "موجودی ایران خودرو", "موجودی ساپکو",
                "موجودی نزد سازنده", "موجودی آماده حمل", "موجودی کل قابل احتساب",
                "حداقل موجودی قابل اثبات", "پوشش اجزای موجودی (٪)",
                "شکاف اجزای موجودی", "نیاز روزانه", "موجودی در راه",
                "موجودی در گمرک", "مقاومت انبار (روز)",
                "مقاومت ایران خودرو (روز)", "مقاومت ساپکو (روز)",
                "مقاومت نزد سازنده (روز)", "مقاومت آماده حمل (روز)", "مقاومت در راه (روز)",
                "مقاومت در گمرک (روز)",
                "PART_CRITICALITY_SCORE",
                "BL_CRITICAL", "BL_CRITICAL_LEVEL", "BL_CRITICAL_MATERIALS",
                "BL_CRITICAL_REASON", "ORDER_CRITICAL", "ORDER_CRITICAL_LEVEL",
                "ORDER_CRITICAL_MATERIALS", "ORDER_CRITICAL_REASON"]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        eng = CriticalityEngine(ctx.rb)
        results = [eng.evaluate(r) for r in df.to_dict("records")]
        if results:
            for k in results[0].as_dict():
                df[k] = [r.as_dict()[k] for r in results]
        df["PART_CRITICALITY_SCORE"] = [r.risk_score for r in results]

        # مقاومت جزءبه‌جزء — همان مخرج مشترک DAILY_NEED. این ستون‌ها
        # مستقل از مقاومت کل هستند و برای Studio/گزارش قابل انتخاب‌اند.
        need = pd.to_numeric(df.get("DAILY_NEED"), errors="coerce")
        component_res = {
            "مقاومت ایران خودرو (روز)": "STOCK_IKCO",
            "مقاومت ساپکو (روز)": "STOCK_SAPCO",
            "مقاومت نزد سازنده (روز)": "SUPPLIER_QTY",
            "مقاومت آماده حمل (روز)": "READY_QTY",
            "مقاومت در راه (روز)": "IN_TRANSIT_QTY",
            "مقاومت در گمرک (روز)": "IN_CUSTOMS_QTY",
        }
        for out_col, src_col in component_res.items():
            x = pd.to_numeric(df.get(src_col), errors="coerce")
            df[out_col] = (x / need.where(need > 0)).round(1)

        known = int(df["کد طبقه بحرانی"].ne("UNKNOWN").sum())
        unknown = int(df["کد طبقه بحرانی"].eq("UNKNOWN").sum())
        partial = int(pd.to_numeric(df.get("پوشش اجزای موجودی (٪)"), errors="coerce").lt(100).fillna(True).sum())
        if known == 0:
            log.critical(
                "🚨 مقاومت انبار هیچ قطعه‌ای محاسبه نشد — موجودی IKCO/SAPCO یا نیاز روزانه ناقص است.\n"
                "   ⇒ چهار وضعیت پارت کارشناسی شرط محاسبه طبقه بحرانی نیستند؛ Oracle/KEY_MATERIAL را بررسی کنید.")
        else:
            log.info(f"🔧 مقاومت قطعی برای {known} از {len(df)} ردیف — "
                     f"UNKNOWN={unknown}, پوشش ناقص={partial}, "
                     f"طبقات={df['بحرانی (کوتاه)'].value_counts().to_dict()}")
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

        # R8: بحرانی بودن سفارش روی همه ردیف‌های سفارش (FIRST و ADDITIONAL)
        # حساب می‌شود. بارنامه‌های سفارش فقط روی ردیف متریال اول نشسته‌اند و هیچ
        # منبعی نمی‌گوید کدام بارنامه کدام متریال را حمل می‌کند؛ پس بحرانی بودن
        # بارنامه = «دست‌کم یک سفارشِ این بارنامه بحرانی است»، محاسبه‌شده روی همه
        # متریال‌های آن سفارش‌ها — نه «متریالی که بارنامه حمل می‌کند».
        def _keys(*names: str) -> pd.Series:
            out = pd.Series("", index=range(len(df)), dtype=object)
            for name in names:
                if name in df.columns:
                    v = pd.Series(df[name].to_numpy(), index=out.index).map(
                        lambda x: "" if pd.isna(x) else str(x).strip())
                    out = out.where(out.ne(""), v)
            return out

        order_key = _keys("CANONICAL_ORDER", "KEY_ORDER")
        bl_key = _keys("CANONICAL_BL") if "CANONICAL_BL" in df.columns else None
        narrow = df[[c for c in dict.fromkeys(("کد طبقه بحرانی", "مقاومت (روز)",
                                              "KEY_MATERIAL", "بحرانی (کوتاه)"))
                     if c in df.columns]].reset_index(drop=True)   # ایندکس یکتا برای union ردیف‌ها

        def write(prefix: str, key: pd.Series, info: Dict[str, tuple]) -> None:
            k = key.fillna("").astype(str)
            blank = (False, "UNKNOWN", "", "")
            df[f"{prefix}_CRITICAL"] = k.map(lambda x: bool(info.get(x, blank)[0])).to_numpy(dtype=bool)
            df[f"{prefix}_CRITICAL_LEVEL"] = k.map(lambda x: info.get(x, blank)[1]).to_numpy()
            df[f"{prefix}_CRITICAL_MATERIALS"] = k.map(lambda x: info.get(x, blank)[2]).to_numpy()
            df[f"{prefix}_CRITICAL_REASON"] = k.map(lambda x: info.get(x, blank)[3]).to_numpy()

        # ── سفارش: همه ردیف‌های سفارش ──
        order_rows: Dict[str, pd.Index] = {}
        order_info: Dict[str, tuple] = {}
        if "CANONICAL_ORDER" in df.columns or "KEY_ORDER" in df.columns:
            for value, g in narrow.groupby(order_key, sort=False):
                if not value:
                    continue
                order_rows[value] = g.index
                order_info[value] = group_info(g)
            write("ORDER", order_key, order_info)

        # ── بارنامه: سفارش‌های روی این بارنامه (شاهد: ردیف بارنامه ↔ سفارش) ──
        if bl_key is not None:
            pairs = pd.DataFrame({"bl": bl_key, "order": order_key})
            pairs = pairs[pairs["bl"].ne("")]
            bl_info: Dict[str, tuple] = {}
            for b, pg in pairs.groupby("bl", sort=False):
                orders = [o for o in dict.fromkeys(pg["order"]) if o]
                idx = pg.index[pg["order"].eq("")]      # ردیف بارنامه‌ی بدون سفارش: فقط خودش
                if len(orders) == 1 and idx.empty and orders[0] in order_info:
                    flag, level, mats, own = order_info[orders[0]]
                else:
                    for o in orders:
                        idx = idx.union(order_rows.get(o, pd.Index([])))
                    flag, level, mats, own = group_info(narrow.loc[idx])
                reasons = []
                for o in orders:
                    of, _ol, _om, orr = order_info.get(o, (False, "", "", ""))
                    if of and orr:
                        reasons.append(f"سفارش {o}: {orr}")
                if not reasons and flag and own:
                    reasons.append(own)
                bl_info[b] = (flag, level, mats, " || ".join(reasons))
            write("BL", bl_key, bl_info)
        ctx.extras["criticality_known"] = known
        # R8: قاعده بارنامه از سفارش می‌آید، نه از متریال روی ردیف بارنامه
        ctx.extras["critical_group_rule"] = ("هر سفارش با حداقل یک متریال STOCKOUT یا CRITICAL (در همه ردیف‌های سفارش) بحرانی است؛ "
                                             "بارنامه‌ای که دست‌کم یک سفارش بحرانی دارد «بارنامه دارای سفارش بحرانی» است. "
                                             "منبعی نمی‌گوید کدام بارنامه کدام متریال را حمل می‌کند؛ علت تا سطح متریال سفارش ثبت می‌شود.")
        return df

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("طبقه بحرانی", "طبقه بحرانی", 22, GROUP_MAIN, order=1),
            ColumnSpec("مقاومت (روز)", "مقاومت قطعی (روز)", 16, GROUP_MAIN,
                       fmt="decimal", order=2, color_rule="scale_low_bad"),
            ColumnSpec("موجودی ایران خودرو", "موجودی ایران‌خودرو (Oracle)", 18, GROUP_MAIN, fmt="decimal", order=3),
            ColumnSpec("موجودی ساپکو", "موجودی ساپکو (Oracle)", 17, GROUP_MAIN, fmt="decimal", order=4),
            # چهار وضعیت پارت، جمع‌ها، پوشش و شکاف موجودی را مرحله ۳۸ (supply_position)
            # یک بار نشان می‌دهد؛ تکرارشان اینجا ستون‌های هم‌معنای دوم می‌ساخت (29.15.12).
            ColumnSpec("نیاز روزانه", "نیاز روزانه (Oracle)", 16, GROUP_MAIN, fmt="decimal", order=12),
            # R8: بارنامه متریال را «حمل نمی‌کند» (شاهدی نیست)؛ برچسب‌ها سطح سفارش را می‌گویند
            ColumnSpec("BL_CRITICAL", "بارنامه دارای سفارش بحرانی", 16, GROUP_MAIN, order=28),
            ColumnSpec("BL_CRITICAL_MATERIALS", "متریال بحرانی سفارش‌های این بارنامه", 34, GROUP_MAIN, wrap=True, order=29),
            ColumnSpec("BL_CRITICAL_REASON", "علت بحرانی بودن سفارش‌های این بارنامه", 58, GROUP_MAIN, wrap=True, order=30),
            ColumnSpec("ORDER_CRITICAL", "بحرانی بودن سفارش", 16, GROUP_MAIN, order=31),
            ColumnSpec("ORDER_CRITICAL_MATERIALS", "متریال بحرانی سفارش", 34, GROUP_MAIN, wrap=True, order=32),
            ColumnSpec("ORDER_CRITICAL_REASON", "علت بحرانی بودن سفارش", 58, GROUP_MAIN, wrap=True, order=33),
        ]

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict]:
        bands = ctx.rb.get("criticality.bands", []) or []
        return {"مقاومت قطعه": {
            "فرمول": "مقاومت اصلی/بحرانی (روز) = (ایران‌خودرو Oracle + ساپکو Oracle) ÷ نیاز روزانه. مقاومت نزد سازنده، در راه و گمرک جداگانه با همان مخرج محاسبه می‌شوند؛ مقاومت کل تامین فقط وقتی همه اجزا معلوم باشند ساخته می‌شود.",
            "طبقه‌بندی": [f"{b.get('fa')}" for b in bands],
            "کالای در راه": ("لحاظ نمی‌شود" if not ctx.rb.get(
                "criticality.formula.include_in_transit", False) else "لحاظ می‌شود"),
            "قاعده داده": "طبقه بحرانی فقط به IKCO/SAPCO و نیاز روزانه وابسته است. سه مؤلفه نزد سازنده/در راه/گمرک از Commercial Expert Data و شواهد حمل مشتق/خوانده می‌شوند و نبودشان مقاومت اصلی را UNKNOWN نمی‌کند. Unknown ≠ Zero.",
            "منبع": "rules/criticality.yaml + stage supply_position",
        }}

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        def n(code: str) -> int:
            if "کد طبقه بحرانی" not in df or "KEY_MATERIAL" not in df:
                return 0
            return int(df.loc[df["کد طبقه بحرانی"] == code, "KEY_MATERIAL"]
                       .replace("", np.nan).nunique())

        low = pd.to_numeric(df.get("مقاومت (روز)"), errors="coerce").min()
        low_value = "—" if pd.isna(low) else round(float(low), 1)
        coverage = pd.to_numeric(df.get("پوشش اجزای موجودی (٪)"), errors="coerce")
        cov_value = "—" if coverage.dropna().empty else round(float(coverage.mean()), 1)
        return {
            "🔴 قطعات با توقف خط (موجودی صفر)": (n("STOCKOUT"), "مقاومت صفر"),
            "🔴 قطعات بحرانی (مقاومت زیر ۱۰ روز)": (n("CRITICAL"), "نیازمند اقدام فوری"),
            "🟠 در حال بحرانی شدن (۱۰ تا ۲۰ روز)": (n("BECOMING_CRITICAL"), "پیگیری هفتگی"),
            "کمترین مقاومت قطعی (روز)": (low_value, "بحرانی‌ترین قطعه با داده کامل"),
            "پوشش متوسط اجزای موجودی (٪)": (cov_value, "Oracle + چهار وضعیت پارت کارشناسی"),
        }
