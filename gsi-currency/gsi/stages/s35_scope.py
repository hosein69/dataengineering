# -*- coding: utf-8 -*-
"""مرحله ۳۵ — حوزه مسئولیت، مالک قطعه و وضعیت «کجا/کی/چه کسی».

بعد از مرحله ۳۰ اجرا می‌شود، چون تبدیل «کد پرسنلی → نام» به HR نیاز دارد
و آن نگاشت همان‌جا ساخته می‌شود.

این مرحله هیچ ردیفی را حذف یا فیلتر نمی‌کند. تنها کاری که می‌کند افزودن
ستون است — از جمله ستونی که می‌گوید مالک چه داده‌ای را پر نکرده.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from ..dataio.logging_setup import log
from ..resolve import part_status as ps
from ..resolve.expert_scope import (MISSING_SOURCE, OWNER_GAP, OWNER_NAME,
                                    OWNER_SOURCE, SCOPES, coverage,
                                    resolve_owner, resolve_scopes)
from ..resolve.org_mapper import DynamicOrgMapper
from .base import (ColumnSpec, FMT_INT, GROUP_ANALYTIC, GROUP_DETAIL,
                   GROUP_MAIN, PipelineContext, Stage, register)


@register
class ScopeStage(Stage):
    name = "scope"
    title = "حوزه مسئولیت، مالک قطعه و وضعیت کجا/کی/چه کسی"
    order = 35
    requires = ["CANONICAL_EXPERT"]
    provides = ([s.key for s in SCOPES]
                + [OWNER_NAME, OWNER_SOURCE, OWNER_GAP, MISSING_SOURCE]
                + ps.OUTPUT_COLUMNS)

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        mapper = DynamicOrgMapper(ctx.sheet("hr"))
        df = resolve_scopes(df, mapper)
        df = resolve_owner(df, mapper)
        df = ps.resolve(df)

        cov = coverage(df)
        ctx.extras["scope_coverage"] = cov
        parts = [f"{r['حوزه']} {r['پوشش']:.0%} ({r['نفرات یکتا']} نفر)"
                 for _, r in cov.iterrows()]
        log.info("🎯 حوزه‌های مسئولیت: " + " | ".join(parts))

        owned = int(df[OWNER_NAME].astype(str).str.strip().ne("").sum())
        if owned == 0:
            log.warning("⚠️ مالک هیچ قطعه‌ای شناسایی نشد — سورس "
                        "«Commercial Expert Data» یا ستون Employee Code را بررسی کنید.")
        else:
            log.info(f"👤 مالک قطعه برای {owned} از {len(df)} ردیف شناسایی شد "
                     f"({owned / max(len(df), 1):.0%}).")
        gap = int(df[OWNER_GAP].astype(str).str.strip().ne("").sum())
        if gap:
            log.info(f"🧩 {gap} ردیف شکاف داده مالک دارد — ردیف‌ها حذف نشدند؛ "
                     f"علت در ستون «{OWNER_GAP}» ثبت شد.")
        absent = str(df[MISSING_SOURCE].iloc[0]) if len(df) else ""
        if absent:
            log.warning(f"⚠️ این فیلدهای مالک اصلاً در داده نیستند: {absent} — "
                        f"شکاف سورس است، نه کوتاهی ردیف‌ها.")
        ctx.extras["owner_rows"] = owned
        ctx.extras["owner_gap_rows"] = gap

        wait = df[ps.WAITING_SCOPE].astype(str).str.strip()
        top = wait[wait.ne("")].value_counts().head(1)
        if not top.empty:
            log.info(f"⏳ بیشترین انتظار روی «{top.index[0]}» است — {int(top.iloc[0])} ردیف.")
        return df

    def columns(self) -> List[ColumnSpec]:
        cols = [
            ColumnSpec(OWNER_NAME, "مالک قطعه (کارشناس خرید)", 24, GROUP_MAIN, order=24),
            ColumnSpec(ps.WHERE, "موقعیت فعلی", 18, GROUP_MAIN, order=25),
            ColumnSpec(ps.WHEN, "تاریخ آخرین رویداد", 16, GROUP_MAIN, order=26),
            ColumnSpec(ps.AGE, "سن وضعیت (روز)", 12, GROUP_MAIN, fmt=FMT_INT,
                       order=27, color_rule="scale_high_bad"),
            ColumnSpec(ps.WHO, "کارشناس مسئول وضعیت", 22, GROUP_MAIN, order=28),
            ColumnSpec(ps.WAITING_SCOPE, "معطل حوزه", 18, GROUP_MAIN, order=29),
        ]
        cols += [ColumnSpec(s.key, s.fa, 22, GROUP_DETAIL) for s in SCOPES]
        cols += [
            ColumnSpec(ps.ACTIVITY, "آخرین فعالیت", 24, GROUP_DETAIL),
            ColumnSpec(ps.WHO_SCOPE, "حوزه مسئول وضعیت", 18, GROUP_DETAIL),
            ColumnSpec(ps.NEXT_ACT, "فعالیت بعدی مورد انتظار", 24, GROUP_DETAIL),
            ColumnSpec(ps.WAITING_WHO, "کارشناس معطل‌شده", 22, GROUP_DETAIL),
            ColumnSpec(OWNER_SOURCE, "منبع شناسایی مالک", 22, GROUP_ANALYTIC),
            ColumnSpec(OWNER_GAP, "شکاف داده مالک", 34, GROUP_ANALYTIC, wrap=True),
            ColumnSpec(ps.BASIS, "مبنای تعیین وضعیت", 30, GROUP_ANALYTIC, wrap=True),
            ColumnSpec(ps.MISSING, "تاریخ‌های ثبت‌نشده", 34, GROUP_ANALYTIC, wrap=True),
        ]
        return cols

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        out: Dict[str, tuple] = {}
        owned = int(df.get(OWNER_NAME, pd.Series(dtype=str)).astype(str).str.strip().ne("").sum())
        out["ردیف دارای مالک قطعه"] = (
            owned, "کارشناس خرید، از Commercial Expert Data یا کد پرسنلی")
        gap = int(df.get(OWNER_GAP, pd.Series(dtype=str)).astype(str).str.strip().ne("").sum())
        out["ردیف با شکاف داده مالک"] = (
            gap, "داده ناقصِ مالک — ردیف حذف نشده، علت ثبت شده است")
        if ps.AGE in df.columns:
            age = pd.to_numeric(df[ps.AGE], errors="coerce")
            if age.notna().any():
                out["کهنه‌ترین وضعیت (روز)"] = (
                    int(age.max()), "روزهای سپری‌شده از آخرین رویداد تاریخ‌دار")
        return out
