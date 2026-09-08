# -*- coding: utf-8 -*-
"""مرحله ۸۵ — بررسی انطباق فرآیند (Conformance Checking) و ریشه‌یابی علّی.

## چرا این مرحله وجود دارد

مرحله ۸۰ می‌گوید فرآیند **چگونه اجرا شده** (نقشه و گلوگاه).
این مرحله می‌گوید **کجا از مسیر درست منحرف شده و چرا** — یعنی از توصیف به
علت می‌رسد. سه سؤالی که پاسخ می‌دهد:

    ۱. کدام پرونده‌ها فعالیت لازم را جا انداخته‌اند؟        (Skipped)
    ۲. کدام پرونده‌ها فعالیت‌ها را خارج از ترتیب انجام داده‌اند؟ (Out-of-order)
    ۳. کدام ویژگی با انحراف همبستگی دارد؟                    (Root cause)

## مبنای نظری

مسیر مرجع (happy path) از ترتیب چرخه عمر در ``rules/fx_governance.yaml``
می‌آید — یعنی مدل مرجع، **داده** است نه کد، و با تغییر YAML عوض می‌شود.

نکته‌ای که در ادبیات فرآیندکاوی شیءمحور (OCEL 2.0) مطرح است و اینجا رعایت
شده: این فرآیند چند «مفهوم پرونده» هم‌زمان دارد — سفارش، بارنامه و متریال.
تخت‌کردن به یک کلید، تحلیل را تحریف می‌کند. بنابراین علاوه بر انطباق در سطح
پرونده، پوشش هر شیء جداگانه هم گزارش می‌شود.

## ⚠️ نکته معماری

این فایل تنها فایلی است که برای افزودن قابلیت «انطباق» ساخته شد.
هیچ فایل دیگری — نه pipeline، نه dashboard، نه config — لمس نشد.
"""
from __future__ import annotations

__contract__ = 1

from typing import Any, Dict, List, Tuple

import pandas as pd

from ..core.text import is_empty_val, num_safe
from ..dataio.logging_setup import log
from ..rulebook import get_rulebook
from .base import (ColumnSpec, FMT_DECIMAL, GROUP_ANALYTIC, PipelineContext,
                   Stage, register)

#: فعالیت‌هایی که نبودشان انحراف بحرانی است (نه صرفاً «هنوز نرسیده»)
MANDATORY_BEFORE = {
    # فعالیت: فعالیتی که اگر رخ داده باشد، این یکی حتماً باید قبلش بوده باشد
    "Currency Allocated": "Order Registered",
    "FX Supplied": "Currency Allocated",
    "Goods Shipped": "FX Supplied",
    "Customs Declaration": "Goods Shipped",
    "Cleared": "Customs Declaration",
}


@register
class ConformanceStage(Stage):
    name = "conformance"
    title = "بررسی انطباق فرآیند و ریشه‌یابی انحراف"
    order = 85                      # بعد از eventlog(۸۰)، قبل از sort(۹۰)
    requires = ["CANONICAL_ORDER"]
    tolerant = True                 # اگر لاگ رویداد نبود، فقط رد می‌شود
    provides = ["انحراف فرآیند", "فعالیت‌های جاافتاده", "نقض ترتیب",
                "امتیاز انطباق (٪)", "علت ریشه‌ای پیشنهادی"]

    # ═══════════ اجرا ═══════════
    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        events = ctx.extras.get("eventlog")
        if events is None or len(events) == 0:
            log.warning("⚠️ [conformance] لاگ رویداد موجود نیست؛ بررسی انطباق رد شد.")
            for c in self.provides:
                df[c] = ""
            return df

        happy = self._happy_path()
        per_case = self._analyse_cases(events, happy)

        key_col = "_CASE_KEY" if "_CASE_KEY" in df.columns else "CANONICAL_ORDER"
        keys = df[key_col].astype(str) if key_col in df.columns else pd.Series([""] * len(df))

        blank = {"skipped": "", "out_of_order": "", "score": 100.0, "deviation": "بدون انحراف"}
        rows = [per_case.get(k, blank) for k in keys]

        df["فعالیت‌های جاافتاده"] = [r["skipped"] for r in rows]
        df["نقض ترتیب"] = [r["out_of_order"] for r in rows]
        df["امتیاز انطباق (٪)"] = [r["score"] for r in rows]
        df["انحراف فرآیند"] = [r["deviation"] for r in rows]

        ctx.extras["conformance_cases"] = pd.DataFrame(
            [{"_CASE_KEY": k, **v} for k, v in per_case.items()])
        roots = self._root_causes(df)
        ctx.extras["conformance_root_causes"] = roots
        df["علت ریشه‌ای پیشنهادی"] = self._explain(df, roots)

        n_dev = int((df["انحراف فرآیند"] != "بدون انحراف").sum())
        log.info(f"🔍 [conformance] {n_dev} از {len(df)} پرونده انحراف دارند — "
                 f"میانگین انطباق {df['امتیاز انطباق (٪)'].mean():.1f}٪")
        return df

    # ═══════════ مسیر مرجع از YAML ═══════════
    @staticmethod
    def _happy_path() -> List[str]:
        rb = get_rulebook()
        stages = sorted(rb.get("fx_governance.lifecycle.stages", []) or [],
                        key=lambda s: s.get("order", 999))
        return [s["code"] for s in stages]

    # ═══════════ تحلیل هر پرونده ═══════════
    def _analyse_cases(self, events: pd.DataFrame,
                       happy: List[str]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        act_col = "ACTIVITY_EN" if "ACTIVITY_EN" in events.columns else "ACTIVITY"
        sort_col = "_SORTING" if "_SORTING" in events.columns else None
        time_col = "EVENTTIME" if "EVENTTIME" in events.columns else None

        for case, g in events.groupby("_CASE_KEY", sort=False):
            if sort_col:
                g = g.sort_values([time_col, sort_col] if time_col else [sort_col])
            elif time_col:
                g = g.sort_values(time_col)
            seq = list(g[act_col].astype(str))
            order_map = dict(zip(g[act_col].astype(str),
                                 g[sort_col] if sort_col else range(len(g))))

            # ── ۱) فعالیت‌های جاافتاده: پیش‌نیازی که نیامده ولی پیامدش آمده ──
            skipped: List[str] = []
            for later, required in MANDATORY_BEFORE.items():
                if later in seq and required not in seq:
                    skipped.append(required)

            # ── ۲) نقض ترتیب: پیش‌نیاز بعد از پیامد ثبت شده ──
            violations: List[str] = []
            for later, required in MANDATORY_BEFORE.items():
                if later in order_map and required in order_map:
                    if num_safe(order_map[required]) > num_safe(order_map[later]):
                        violations.append(f"{required} پس از {later}")

            total_checks = len(MANDATORY_BEFORE) * 2 or 1
            faults = len(skipped) + len(violations)
            score = round(max(0.0, (1 - faults / total_checks)) * 100, 1)

            if skipped and violations:
                dev = "جاافتادگی و نقض ترتیب"
            elif skipped:
                dev = "فعالیت جاافتاده"
            elif violations:
                dev = "نقض ترتیب"
            else:
                dev = "بدون انحراف"

            out[str(case)] = {
                "skipped": " ؛ ".join(dict.fromkeys(skipped)),
                "out_of_order": " ؛ ".join(dict.fromkeys(violations)),
                "score": score,
                "deviation": dev,
            }
        return out

    # ═══════════ ریشه‌یابی: کدام ویژگی با انحراف همبسته است ═══════════
    @staticmethod
    def _root_causes(df: pd.DataFrame) -> pd.DataFrame:
        """نرخ انحراف را در هر گروه با نرخ کل مقایسه می‌کند (اثر تفاضلی).

        این همان منطق «تحلیل ریشه‌ای» ابزارهای فرآیندکاوی است: گروهی که نرخ
        انحرافش به‌طور معنادار بالاتر از میانگین است، مظنون اصلی است.
        """
        if "انحراف فرآیند" not in df.columns or df.empty:
            return pd.DataFrame()
        base_rate = float((df["انحراف فرآیند"] != "بدون انحراف").mean())
        dims = [("نوع پرونده", "سگمنت"), ("CANONICAL_EXPERT", "کارشناس"),
                ("بحرانی (کوتاه)", "طبقه بحرانی"), ("ORDER_STAGE_FA", "مرحله سفارش"),
                ("ORG_DEPT", "مدیریت"), ("روش پرداخت", "روش پرداخت")]
        rows = []
        for col, label in dims:
            if col not in df.columns:
                continue
            for value, g in df.groupby(df[col].astype(str), sort=False):
                if len(g) < 2 or is_empty_val(value):
                    continue
                rate = float((g["انحراف فرآیند"] != "بدون انحراف").mean())
                rows.append({
                    "بُعد": label, "مقدار": value, "تعداد پرونده": int(len(g)),
                    "نرخ انحراف (٪)": round(rate * 100, 1),
                    "نرخ پایه (٪)": round(base_rate * 100, 1),
                    "اثر تفاضلی (واحد درصد)": round((rate - base_rate) * 100, 1),
                })
        if not rows:
            return pd.DataFrame()
        out = pd.DataFrame(rows).sort_values(
            "اثر تفاضلی (واحد درصد)", ascending=False).reset_index(drop=True)
        return out

    @staticmethod
    def _explain(df: pd.DataFrame, roots: pd.DataFrame) -> List[str]:
        """برای هر ردیف منحرف، محتمل‌ترین علت ریشه‌ای را نسبت می‌دهد."""
        if roots.empty:
            return ["" for _ in range(len(df))]
        top = roots[roots["اثر تفاضلی (واحد درصد)"] > 0].head(6)
        lookup = {("نوع پرونده", "سگمنت"), ("CANONICAL_EXPERT", "کارشناس"),
                  ("بحرانی (کوتاه)", "طبقه بحرانی"), ("ORDER_STAGE_FA", "مرحله سفارش"),
                  ("ORG_DEPT", "مدیریت"), ("روش پرداخت", "روش پرداخت")}
        label_to_col = {lab: col for col, lab in lookup}

        out: List[str] = []
        for _, row in df.iterrows():
            if row.get("انحراف فرآیند") == "بدون انحراف":
                out.append("")
                continue
            causes = []
            for _, r in top.iterrows():
                col = label_to_col.get(r["بُعد"])
                if col and str(row.get(col, "")) == str(r["مقدار"]):
                    causes.append(f"{r['بُعد']} «{r['مقدار']}» "
                                  f"({r['اثر تفاضلی (واحد درصد)']:+.0f} واحد درصد بالاتر از میانگین)")
            out.append(" ؛ ".join(causes[:2]) if causes else "علت گروهی شناسایی نشد")
        return out

    # ═══════════ مستندسازی ═══════════
    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("امتیاز انطباق (٪)", "انطباق (٪)", width=14,
                       group=GROUP_ANALYTIC, fmt=FMT_DECIMAL,
                       color_rule="scale_low_bad"),
            ColumnSpec("فعالیت‌های جاافتاده", "فعالیت جاافتاده", width=34, group=GROUP_ANALYTIC),
            ColumnSpec("نقض ترتیب", "نقض ترتیب", width=34, group=GROUP_ANALYTIC,
                       wrap=True),
            ColumnSpec("انحراف فرآیند", "انحراف فرآیند", width=22,
                       group=GROUP_ANALYTIC, color_rule="flag_nonempty"),
            ColumnSpec("علت ریشه‌ای پیشنهادی", "علت ریشه‌ای", width=52,
                       group=GROUP_ANALYTIC, wrap=True),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        if "انحراف فرآیند" not in df.columns or df.empty:
            return {}
        dev = int((df["انحراف فرآیند"] != "بدون انحراف").sum())
        roots = ctx.extras.get("conformance_root_causes")
        worst = "—"
        if roots is not None and not roots.empty:
            r = roots.iloc[0]
            worst = f"{r['بُعد']}: {r['مقدار']} ({r['اثر تفاضلی (واحد درصد)']:+.0f})"
        return {
            "پرونده‌های منحرف از مسیر استاندارد": (dev, "جاافتادگی یا نقض ترتیب فعالیت‌ها"),
            "میانگین امتیاز انطباق (٪)": (
                round(float(df["امتیاز انطباق (٪)"].mean()), 1),
                "۱۰۰ یعنی اجرای کامل مطابق چرخه عمر تعریف‌شده"),
            "قوی‌ترین علت ریشه‌ای انحراف": (worst, "بیشترین اثر تفاضلی نسبت به نرخ پایه"),
        }

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict[str, Any]]:
        return {
            "بررسی انطباق و ریشه‌یابی علّی": {
                "مسیر مرجع": " → ".join(self._happy_path()),
                "قواعد پیش‌نیاز": " ؛ ".join(
                    f"{v} باید پیش از {k}" for k, v in MANDATORY_BEFORE.items()),
                "امتیاز انطباق": "۱۰۰ × (۱ − تعداد تخلف ÷ تعداد بررسی)",
                "اثر تفاضلی": "نرخ انحراف گروه − نرخ انحراف کل جمعیت",
                "منبع مسیر مرجع": "rules/fx_governance.yaml → lifecycle.stages",
            }
        }
