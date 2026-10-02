# -*- coding: utf-8 -*-
"""مرحله ۹۵ — سنجش اعتماد داده و درجه‌بندی تصمیم‌ها.

این مرحله **هیچ مقدار کسب‌وکاری را تغییر نمی‌دهد**. فقط روی خروجی نهایی
خط لوله نگاه می‌کند و می‌گوید هر عدد چقدر قابل استناد است، ایراد هر سلول
کجاست و مالکش کیست.

چرا آخرین مرحله است: درجه اعتماد باید روی همان چیزی محاسبه شود که کاربر
می‌بیند — بعد از همه مشتق‌ها، ادغام‌ها و اصلاح‌ها، نه روی داده خام.

چرا `tolerant = True` است: خطای این مرحله هرگز نباید انتشار یک اجرای سالم
را متوقف کند. اگر سنجش اعتماد شکست بخورد، سامانه بدون درجه کار می‌کند —
کُند ولی درست — و خود این شکست در «سلامت سیستم» ثبت می‌شود.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from ..dataio.logging_setup import log
from ..trust import assess
from ..trust.contracts import KEY_COLUMN
from ..trust.fitness import DECISION_GRADE, NOT_USABLE
from ..trust import codes as C
from .base import (ColumnSpec, GROUP_ANALYTIC, PipelineContext, Stage, register)


@register
class DataTrustStage(Stage):
    name = "data_trust"
    title = "سنجش اعتماد داده و درجه‌بندی تصمیم‌ها"
    order = 95
    tolerant = True
    requires: List[str] = []
    provides = ["TRUST_STATE", "TRUST_BLOCKERS", "TRUST_NOT_READY_FOR"]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        report = assess(df, ref_date=ctx.today)

        frames = report.frames()
        ctx.extras["trust_decisions"] = frames["decisions"]
        ctx.extras["trust_fields"] = frames["fields"]
        ctx.extras["trust_defects"] = frames["defects"]
        ctx.extras["trust_next_fixes"] = frames["next_fixes"]
        ctx.extras["trust_owners"] = frames["owners"]
        ctx.extras["trust_owners_by_dept"] = frames["owners_by_dept"]
        ctx.extras["trust_owners_by_manager"] = frames["owners_by_manager"]
        ctx.extras["trust_summary"] = report.summary()
        ctx.extras["trust_headline"] = report.headline_fa()

        self._attach_row_columns(df, report)

        counts = report.grade_counts()
        log.info(
            f"🔎 [data-trust] {counts.get(DECISION_GRADE, 0)} تصمیم قابل استناد | "
            f"{counts.get(NOT_USABLE, 0)} غیرقابل استناد | "
            f"{len(report.ledger):,} ایراد | "
            f"{report.unlockable_cases:,} پرونده با {report.actionable_defects:,} سلول آزاد می‌شود"
        )
        return df

    # ── per-row columns so the UI can filter on trust ───────────────────────
    def _attach_row_columns(self, df: pd.DataFrame, report) -> None:
        """سه ستون سبک روی هر ردیف، برای فیلترکردن در Studio و HTML.

        عمداً سه ستون و نه بیشتر: هدف، فیلترپذیری است نه انتقال کل دفتر ایراد
        به جدول اصلی. جزئیات کامل در فریم‌های `trust_*` است.
        """
        for column in self.provides:
            df[column] = ""
        if df.empty:
            return

        # worst state + blocking fields, per entity key, per entity type
        blockers: Dict[str, Dict[str, List[str]]] = {}
        states: Dict[str, Dict[str, str]] = {}
        for entity, profile in report.profiles.items():
            blockers[entity] = {}
            states[entity] = {}
            for key, field_states in profile.states.items():
                bad = [f for f, s in field_states.items() if s != C.OK]
                states[entity][key] = C.worst_state(field_states.values())
                if bad:
                    blockers[entity][key] = bad

        # decisions each entity is not ready for
        not_ready: Dict[str, Dict[str, List[str]]] = {e: {} for e in report.profiles}
        for verdict in report.verdicts:
            entity = verdict.contract.entity_type
            profile = report.profiles.get(entity)
            if profile is None:
                continue
            for key, field_states in profile.states.items():
                if any(field_states.get(f, C.MISSING) != C.OK for f in verdict.contract.required):
                    not_ready[entity].setdefault(key, []).append(verdict.contract.title_fa)

        from ..core.text import clean_key

        state_col: List[str] = []
        blocker_col: List[str] = []
        not_ready_col: List[str] = []
        key_series = {e: (df[KEY_COLUMN[e]] if KEY_COLUMN.get(e) in df.columns else None)
                      for e in report.profiles}

        for i in range(len(df)):
            row_states: List[str] = []
            row_blockers: List[str] = []
            row_not_ready: List[str] = []
            for entity, series in key_series.items():
                if series is None:
                    continue
                key = clean_key(series.iat[i])
                if not key:
                    continue
                row_states.append(states.get(entity, {}).get(key, C.OK))
                row_blockers.extend(blockers.get(entity, {}).get(key, ()))
                row_not_ready.extend(not_ready.get(entity, {}).get(key, ()))
            worst = C.worst_state(row_states)
            state_col.append(C.STATE_FA.get(worst, worst))
            blocker_col.append(" · ".join(dict.fromkeys(row_blockers)))
            not_ready_col.append(" · ".join(dict.fromkeys(row_not_ready)))

        df["TRUST_STATE"] = state_col
        df["TRUST_BLOCKERS"] = blocker_col
        df["TRUST_NOT_READY_FOR"] = not_ready_col

    # ── report surfaces ─────────────────────────────────────────────────────
    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("TRUST_STATE", "وضعیت اعتماد داده", 16, GROUP_ANALYTIC, order=120),
            ColumnSpec("TRUST_BLOCKERS", "فیلدهای ناقص", 40, GROUP_ANALYTIC,
                       wrap=True, color_rule="flag_nonempty", order=121),
            ColumnSpec("TRUST_NOT_READY_FOR", "تصمیم‌های غیرقابل استناد", 46,
                       GROUP_ANALYTIC, wrap=True, color_rule="flag_nonempty", order=122),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        summary = ctx.extras.get("trust_summary") or {}
        grades = summary.get("grades") or {}
        total = sum(grades.values())
        if not total:
            return {}
        return {
            "تصمیم‌های قابل استناد": (
                f"{grades.get(DECISION_GRADE, 0)} از {total}",
                "بقیه یا جهت‌نما هستند یا شاهد کلیدی ندارند"),
            "پرونده قابل آزادسازی": (
                int(summary.get("unlockable_cases", 0)),
                f"با تکمیل {summary.get('actionable_cells', 0):,} سلول مشخص"),
        }

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict[str, Any]]:
        return {"درجه اعتماد تصمیم": {
            "قاعده": "درجه به جفت (تصمیم، پرونده) تعلق دارد، نه به خود پرونده. "
                     "یک پرونده می‌تواند برای «کجاست؟» قابل استناد و برای «چقدر بدهکاریم؟» نباشد.",
            "جمع مبلغ": "اگر حتی یک پرونده نامعلوم باشد، جمع «قابل تصمیم» نیست؛ "
                        "بخش معلوم و تعداد نامعلوم جدا گزارش می‌شوند.",
            "تعارض": "دو مقدار متفاوت برای یک کلید، fail-closed است: عدد غلط بدتر از عدد ناقص است.",
            "حذف": "هیچ ردیفی به‌خاطر کیفیت حذف نمی‌شود؛ فقط از جمع کنار گذاشته و علتش ثبت می‌شود.",
            "مرجع": "docs/DATA_STRATEGY_FA.md",
        }}
