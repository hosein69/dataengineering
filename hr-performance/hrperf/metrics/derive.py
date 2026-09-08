# -*- coding: utf-8 -*-
"""شاخص‌های محاسبه‌شده — ورود «غیرمستقیم» به کلاستر.

بعضی آیتم‌ها مستقیم از سورس می‌آیند و بعضی از ترکیب چند شاخص ساخته
می‌شوند. فرمول هر شاخص محاسبه‌شده در ``model.yaml`` اعلام می‌شود
(``formula:``) و اینجا پیاده‌سازی دارد، پس افزودن شاخص جدید نیازی به
تغییر موتور ندارد.
"""
from __future__ import annotations

__contract__ = 1

from typing import Callable, Dict

import numpy as np
import pandas as pd

from ..config.model import PerformanceModel


def _wide(long: pd.DataFrame, col: str = "value") -> pd.DataFrame:
    if long.empty:
        return pd.DataFrame()
    return long.pivot_table(index="person_key", columns="metric_key",
                            values=col, aggfunc="mean")


def actual_over_expected(long: pd.DataFrame, model: PerformanceModel) -> pd.Series:
    """A/E — خطای واقعی نسبت به خطای مورد انتظارِ ترکیب پرونده‌ها.

    انتظار از میانگین گروه ساخته می‌شود؛ عدد کمتر از ۱ یعنی بهتر از
    انتظار. اگر مخرج صفر باشد نتیجه NA است، نه صفر — تفاوتی که پکیج
    قبلی هم رویش تأکید داشت و اینجا حفظ شده.
    """
    w = _wide(long)
    if "major_error_rate" not in w.columns:
        return pd.Series(dtype=float)
    actual = pd.to_numeric(w["major_error_rate"], errors="coerce")
    expected = float(actual.mean(skipna=True))
    if not np.isfinite(expected) or expected <= 0:
        return pd.Series(np.nan, index=w.index, dtype=float)
    return actual / expected


def case_mix_difficulty(long: pd.DataFrame, model: PerformanceModel) -> pd.Series:
    """سختی مورد انتظار از ترکیب حجم و تنوع کار."""
    w = _wide(long)
    cases = pd.to_numeric(w.get("unique_cases"), errors="coerce") \
        if "unique_cases" in w.columns else None
    orders = pd.to_numeric(w.get("unique_orders"), errors="coerce") \
        if "unique_orders" in w.columns else None
    parts = [x for x in (cases, orders) if x is not None and x.notna().any()]
    if not parts:
        return pd.Series(dtype=float)
    z = sum((p - p.mean()) / (p.std(ddof=0) or 1.0) for p in parts) / len(parts)
    return z


FORMULAS: Dict[str, Callable[[pd.DataFrame, PerformanceModel], pd.Series]] = {
    "actual_over_expected": actual_over_expected,
    "case_mix_difficulty": case_mix_difficulty,
}


def apply_derived(long: pd.DataFrame, model: PerformanceModel) -> pd.DataFrame:
    """شاخص‌های محاسبه‌شده را به جدول بلند اضافه می‌کند."""
    if long.empty:
        return long
    add = []
    for m in model.metrics.values():
        if m.entry != "derived" or not m.formula:
            continue
        fn = FORMULAS.get(m.formula)
        if fn is None:
            continue
        try:
            s = fn(long, model)
        except Exception:
            continue
        if s is None or s.empty:
            continue
        add.append(pd.DataFrame({
            "person_key": s.index.astype(str),
            "metric_key": m.key,
            "value": s.values,
            "sample_n": np.nan,
            "source": "derived",
        }))
    if not add:
        return long
    keep = long[~long["metric_key"].isin([m.key for m in model.metrics.values()
                                          if m.entry == "derived"])]
    return pd.concat([keep, *add], ignore_index=True)
