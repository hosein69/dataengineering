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
from .s80_eventlog import ACTIVITIES
from .base import (ColumnSpec, FMT_DECIMAL, GROUP_ANALYTIC, PipelineContext,
                   Stage, register)

#: فعالیت‌هایی که نبودشان انحراف بحرانی است (نه صرفاً «هنوز نرسیده»)
#: حداقل اندازه نمونه برای اینکه یک گروه در جدول «عوامل همراه» بیاید.
#:
#: چرا ۵: با ۲ پرونده، یک انحراف یعنی نرخ ۵۰٪ و دو انحراف یعنی ۱۰۰٪ — عددی
#: که بالای هر فهرستی می‌نشیند و هیچ چیز را ثابت نمی‌کند. ۵ کف عملی است که
#: نویز تصادفی را کم می‌کند بدون آنکه گروه‌های واقعی را حذف کند.
MIN_GROUP_SIZE = 5

MANDATORY_BEFORE = {
    # نام‌ها دقیقاً با s80_eventlog.ACTIVITIES یکسان‌اند.
    # «خرید ارز قبل از حمل» عمداً قاعده عمومی نیست: برات/یوزانس و برخی
    # اعتبارات می‌توانند توالی متفاوت داشته باشند.
    "FX Allocated": "FX Commitment Created",
    "FX Purchased": "FX Allocated",
    "Customs Declaration Filed": "Goods Shipped",
    "Fully Cleared": "Customs Declaration Filed",
}


@register
class ConformanceStage(Stage):
    name = "conformance"
    title = "بررسی انطباق فرآیند و ریشه‌یابی انحراف"
    order = 85                      # بعد از eventlog(۸۰)، قبل از sort(۹۰)
    requires = ["CANONICAL_ORDER"]
    tolerant = True                 # اگر لاگ رویداد نبود، فقط رد می‌شود
    provides = ["انحراف فرآیند", "فعالیت‌های جاافتاده", "نقض ترتیب",
                "امتیاز انطباق (٪)", "عوامل همراه با انحراف"]

    # ═══════════ اجرا ═══════════
    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        events = ctx.extras.get("eventlog")
        if events is None or len(events) == 0:
            log.warning("⚠️ [conformance] لاگ رویداد موجود نیست؛ بررسی انطباق رد شد.")
            for c in self.provides:
                df[c] = ""
            return df

        per_case = self._analyse_cases(events, self._precedence(ctx.rb))

        key_col = "_CASE_KEY" if "_CASE_KEY" in df.columns else "CANONICAL_ORDER"
        keys = df[key_col].astype(str) if key_col in df.columns else pd.Series([""] * len(df))

        # پرونده‌ای که هیچ رویدادی ندارد، «منطبق» نیست — **ناشناخته** است.
        #
        # نسخه قبلی به آن امتیاز ۱۰۰ و برچسب «بدون انحراف» می‌داد. یعنی
        # نبودِ شاهد، به‌صورت سلامت گزارش می‌شد: هرچه داده یک پرونده
        # ناقص‌تر، نمرهٔ انطباقش بهتر. این دقیقاً وارونهٔ چیزی است که باید
        # اتفاق بیفتد، و همان قاعده‌ای را می‌شکند که این پکیج جای دیگر
        # رعایت می‌کند: Unknown با Zero یکی نیست.
        blank = {"skipped": "", "out_of_order": "", "score": None,
                 "deviation": "شاهد کافی نداریم"}
        rows = [per_case.get(k, blank) for k in keys]

        df["فعالیت‌های جاافتاده"] = [r["skipped"] for r in rows]
        df["نقض ترتیب"] = [r["out_of_order"] for r in rows]
        df["امتیاز انطباق (٪)"] = [r["score"] for r in rows]
        df["انحراف فرآیند"] = [r["deviation"] for r in rows]
        df["پایه انطباق"] = [r.get("checks", "") for r in rows]

        ctx.extras["conformance_cases"] = pd.DataFrame(
            [{"_CASE_KEY": k, **v} for k, v in per_case.items()])
        roots = self._root_causes(df)
        ctx.extras["conformance_root_causes"] = roots
        df["عوامل همراه با انحراف"] = self._explain(df, roots)

        judged = df["انحراف فرآیند"] != "شاهد کافی نداریم"
        n_dev = int((judged & (df["انحراف فرآیند"] != "بدون انحراف")).sum())
        n_unknown = int((~judged).sum())
        mean_score = pd.to_numeric(df["امتیاز انطباق (٪)"], errors="coerce").mean()
        log.info(f"🔍 [conformance] {n_dev} از {int(judged.sum())} پرونده قابل‌ارزیابی "
                 f"انحراف دارند · {n_unknown} پرونده شاهد کافی ندارند · "
                 f"میانگین انطباق {mean_score:.1f}٪ (فقط قابل‌ارزیابی‌ها)")
        return df

    # ═══════════ مسیر مرجع از YAML ═══════════
    @staticmethod
    def _happy_path() -> List[str]:
        rb = get_rulebook()
        stages = sorted(rb.get("fx_governance.lifecycle.stages", []) or [],
                        key=lambda s: s.get("order", 999))
        return [s["code"] for s in stages]

    # ═══════════ تحلیل هر پرونده ═══════════
    @staticmethod
    def _precedence(rb) -> Dict[str, str]:
        """قواعد پیش‌نیازی، ساخته‌شده از ترتیب چرخه عمر در YAML.

        نسخه قبلی ``_happy_path()`` را محاسبه می‌کرد، به این تابع **پاس
        می‌داد و هرگز استفاده نمی‌کرد** — یک پارامتر مرده. قواعد واقعی چهار
        سطر hardcode بودند، در حالی که YAML دوازده مرحله تعریف می‌کند و
        مستندات ادعا می‌کرد مسیر مرجع از آنجا می‌آید.

        حالا واقعاً از YAML ساخته می‌شود: هر فعالیت، فعالیتِ مرحلهٔ **قبلیِ
        مشاهده‌شدنی** را به‌عنوان پیش‌نیاز می‌گیرد. ``MANDATORY_BEFORE``
        به‌عنوان قواعد دستیِ دامنه‌ای روی آن سوار می‌شود، چون چند رابطه
        (مثل «کوتاژ پس از حمل») از ترتیب مرحله‌ها استنتاج نمی‌شود.
        """
        stages = sorted(rb.get("fx_governance.lifecycle.stages", []) or [],
                        key=lambda x: x.get("order", 999))
        order = {s["code"]: i for i, s in enumerate(stages)}
        # فعالیت‌های هر مرحله، به ترتیب چرخه عمر
        by_stage: Dict[str, List[str]] = {}
        for col, en, fa, sort, stage in ACTIVITIES:
            by_stage.setdefault(stage, []).append(en)
        seq = [en for stage in sorted(by_stage, key=lambda s: order.get(s, 999))
               for en in by_stage[stage]]
        rules = {later: seq[i - 1] for i, later in enumerate(seq) if i > 0}
        rules.update(MANDATORY_BEFORE)      # قواعد دامنه‌ای، اولویت دارند
        return rules

    def _analyse_cases(self, events: pd.DataFrame,
                       precedence: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
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
            # جایگاه واقعی در توالی مرتب‌شده؛ _SORTING فقط tie-breaker است.
            # نسخه قبلی خودِ _SORTING ثابت فعالیت را مقایسه می‌کرد و بنابراین
            # نقض زمانی واقعی را عملاً پنهان می‌کرد.
            order_map = {name: pos for pos, name in enumerate(g[act_col].astype(str))}

            # ── ۱) فعالیت‌های جاافتاده: پیش‌نیازی که نیامده ولی پیامدش آمده ──
            skipped: List[str] = []
            for later, required in precedence.items():
                if later in seq and required not in seq:
                    skipped.append(required)

            # ── ۲) نقض ترتیب: پیش‌نیاز بعد از پیامد ثبت شده ──
            violations: List[str] = []
            for later, required in precedence.items():
                if later in order_map and required in order_map:
                    if num_safe(order_map[required]) > num_safe(order_map[later]):
                        violations.append(f"{required} پس از {later}")

            # فقط قواعدی که برای این پرونده **قابل اعمال**‌اند در مخرج
            # می‌آیند. شمردن قاعده‌ای که فعالیتش اصلاً رخ نداده،
            # پرونده کوتاه را بی‌دلیل خوش‌نمره می‌کرد.
            applicable = [l for l in precedence if l in seq]
            total_checks = len(applicable) * 2 or 1
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
                "checks": f"{len(applicable)} قاعده قابل اعمال از {len(precedence)}",
            }
        return out

    # ═══════════ ریشه‌یابی: کدام ویژگی با انحراف همبسته است ═══════════
    @staticmethod
    def _root_causes(df: pd.DataFrame) -> pd.DataFrame:
        """نرخ انحراف هر گروه را با نرخ کل مقایسه می‌کند — **همبستگی، نه علت**.

        نسخه قبلی خروجی این تابع را «علت ریشه‌ای» می‌نامید. این نام‌گذاری
        یک خطای استنتاجی است که می‌تواند به آدم‌ها آسیب بزند: کارشناسی که
        عمداً پرونده‌های دشوارتر به او سپرده شده، در این جدول بالا می‌آید و
        «علت مشکل» معرفی می‌شود. گروهی با دو پرونده هم می‌تواند نرخ ۱۰۰٪
        بگیرد و بالای فهرست بنشیند.

        پس دو تغییر: نام خروجی «عوامل همراه با انحراف» شد، و حداقل اندازه
        نمونه از ۲ به :data:`MIN_GROUP_SIZE` رفت تا گروه‌های ریز، صدرنشین
        نشوند. ستون «تعداد پرونده» عمداً کنار نرخ می‌ماند تا خواننده خودش
        وزن شاهد را ببیند.
        """
        if "انحراف فرآیند" not in df.columns or df.empty:
            return pd.DataFrame()
        judged_all = df[df["انحراف فرآیند"] != "شاهد کافی نداریم"]
        if judged_all.empty:
            return pd.DataFrame()
        base_rate = float((judged_all["انحراف فرآیند"] != "بدون انحراف").mean())
        dims = [("نوع پرونده", "سگمنت"), ("CANONICAL_EXPERT", "کارشناس"),
                ("بحرانی (کوتاه)", "طبقه بحرانی"), ("ORDER_STAGE_FA", "مرحله سفارش"),
                ("ORG_DEPT", "مدیریت"), ("روش پرداخت", "روش پرداخت")]
        rows = []
        for col, label in dims:
            if col not in df.columns:
                continue
            for value, g in df.groupby(df[col].astype(str), sort=False):
                if len(g) < MIN_GROUP_SIZE or is_empty_val(value):
                    continue
                judged = g[g["انحراف فرآیند"] != "شاهد کافی نداریم"]
                if len(judged) < MIN_GROUP_SIZE:
                    continue
                rate = float((judged["انحراف فرآیند"] != "بدون انحراف").mean())
                rows.append({
                    "بُعد": label, "مقدار": value, "تعداد پرونده": int(len(judged)),
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
        """عواملی که با انحراف این ردیف **همراه**‌اند — نه علت آن.

        تفاوت لحن اینجا عمدی است. «علت این است که کارشناس فلانی» یک اتهام
        است؛ «این پرونده در گروهی است که نرخ انحرافش ۱۲ واحد بالاتر است» یک
        مشاهده است که می‌شود دربارهٔ آن گفت‌وگو کرد.
        """
        if roots.empty:
            return ["" for _ in range(len(df))]
        top = roots[roots["اثر تفاضلی (واحد درصد)"] > 0].head(6)
        lookup = {("نوع پرونده", "سگمنت"), ("CANONICAL_EXPERT", "کارشناس"),
                  ("بحرانی (کوتاه)", "طبقه بحرانی"), ("ORDER_STAGE_FA", "مرحله سفارش"),
                  ("ORG_DEPT", "مدیریت"), ("روش پرداخت", "روش پرداخت")}
        label_to_col = {lab: col for col, lab in lookup}

        out: List[str] = []
        for _, row in df.iterrows():
            if row.get("انحراف فرآیند") in ("بدون انحراف", "شاهد کافی نداریم"):
                out.append("")
                continue
            causes = []
            for _, r in top.iterrows():
                col = label_to_col.get(r["بُعد"])
                if col and str(row.get(col, "")) == str(r["مقدار"]):
                    causes.append(
                        f"{r['بُعد']} «{r['مقدار']}» — نرخ انحراف این گروه "
                        f"{r['اثر تفاضلی (واحد درصد)']:+.0f} واحد درصد بالاتر از پایه "
                        f"(بر پایه {int(r['تعداد پرونده'])} پرونده)")
            out.append(" ؛ ".join(causes[:2]) if causes else "عامل گروهی شاخصی دیده نشد")
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
            ColumnSpec("عوامل همراه با انحراف", "عوامل همراه (نه علت)", width=52,
                       group=GROUP_ANALYTIC, wrap=True),
            ColumnSpec("پایه انطباق", "قواعد قابل اعمال", width=24,
                       group=GROUP_ANALYTIC),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        if "انحراف فرآیند" not in df.columns or df.empty:
            return {}
        judged = df["انحراف فرآیند"] != "شاهد کافی نداریم"
        dev = int((judged & (df["انحراف فرآیند"] != "بدون انحراف")).sum())
        unknown = int((~judged).sum())
        roots = ctx.extras.get("conformance_root_causes")
        worst = "—"
        if roots is not None and not roots.empty:
            r = roots.iloc[0]
            worst = f"{r['بُعد']}: {r['مقدار']} ({r['اثر تفاضلی (واحد درصد)']:+.0f})"
        score = pd.to_numeric(df["امتیاز انطباق (٪)"], errors="coerce")
        out = {
            "پرونده‌های منحرف از مسیر استاندارد": (
                dev, f"از {int(judged.sum())} پرونده قابل‌ارزیابی"),
            "میانگین انطباق پرونده‌های قابل‌ارزیابی (٪)": (
                round(float(score.mean()), 1) if score.notna().any() else "—",
                "پرونده بدون شاهد در این میانگین نیست"),
        }
        if unknown:
            out["پرونده بدون شاهد کافی"] = (
                unknown, "نه منطبق، نه منحرف — قابل ارزیابی نیست")
        if worst != "—":
            out["قوی‌ترین عامل همراه با انحراف"] = (
                worst, "همبستگی است، نه علت — پیش از اقدام بررسی شود")
        return out

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict[str, Any]]:
        return {
            "بررسی انطباق و ریشه‌یابی علّی": {
                "مسیر مرجع": " → ".join(self._happy_path()),
                "منبع قواعد": "ترتیب چرخه عمر در rules/fx_governance.yaml + قواعد دامنه‌ای",
                "قواعد دامنه‌ای": " ؛ ".join(
                    f"{v} باید پیش از {k}" for k, v in MANDATORY_BEFORE.items()),
                "مخرج امتیاز": "فقط قواعد قابل اعمال بر همان پرونده",
                "پرونده بدون رویداد": "«شاهد کافی نداریم» — نه ۱۰۰، نه صفر",
                "جدول عوامل": f"همبستگی است نه علت؛ حداقل اندازه گروه {MIN_GROUP_SIZE}",
                "امتیاز انطباق": "۱۰۰ × (۱ − تعداد تخلف ÷ تعداد بررسی)",
                "اثر تفاضلی": "نرخ انحراف گروه − نرخ انحراف کل جمعیت",
                "منبع مسیر مرجع": "rules/fx_governance.yaml → lifecycle.stages",
            }
        }
