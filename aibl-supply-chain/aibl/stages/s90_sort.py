# -*- coding: utf-8 -*-
"""مرحله ۹۰ — مرتب‌سازی نهایی بر اساس بحرانی بودن."""
from __future__ import annotations

import pandas as pd

from ..dataio.logging_setup import log
from .base import PipelineContext, Stage, register


@register
class SortStage(Stage):
    name = "sort"
    title = "مرتب‌سازی: بحرانی‌ترین در بالا"
    order = 90
    requires = ["CRITICALITY_SORT", "امتیاز ریسک"]
    provides = []

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        cfg = ctx.rb.get("criticality.sorting", {}) or {}
        if not cfg.get("enabled", True) or df.empty:
            return df
        by, asc = [], []
        for rule in cfg.get("order", []) or []:
            col = rule.get("field")
            if col in df.columns:
                by.append(col)
                asc.append(bool(rule.get("ascending", True)))
        if not by:
            return df
        log.info(f"↕️ مرتب‌سازی بر اساس بحرانی بودن: {' → '.join(by)}")
        return df.sort_values(by=by, ascending=asc, na_position="last",
                              kind="mergesort").reset_index(drop=True)
