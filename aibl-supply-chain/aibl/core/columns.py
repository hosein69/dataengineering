# -*- coding: utf-8 -*-
"""تشخیص هوشمند ستون‌ها.

اصلاح نسبت به نسخه ۲۰.۱:
  * ``exclude`` اکنون در فاز تطبیق دقیق هم اعمال می‌شود (قبلاً فقط در فاز جزئی).
  * تطبیق جزئی امتیازدهی می‌شود؛ به جای «اولین ستونی که شامل کاندید است»،
    بهترین ستون انتخاب می‌گردد. این باگ باعث می‌شد کاندید 'نام' ستون
    «نام معاونت» را برگرداند.
  * تابع ``require_col`` برای مواردی که نبود ستون باید خطای صریح بدهد.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, List, Optional, Sequence

import pandas as pd

from .text import normalize_persian_text


def _norm(s: Any) -> str:
    """نام ستون را برای تطبیق یکدست می‌کند.

    هدرهای واقعی IKCO این ناهنجاری‌ها را دارند و بدون حذفشان تطبیق شکست
    می‌خورد:  «_شرح کالا_» ، «_ تاریخ بارگیری نهایی_» ، «تاریخ  دریافت
    شماره کوتاژ» (دو فاصله) ، «Order No.\n(Our Reference)» (شکست خط).
    """
    t = normalize_persian_text(s).lower()
    t = t.replace("\u200c", " ").replace("\u0640", "")   # نیم‌فاصله، تطویل
    t = re.sub(r"[_()\[\]{}«»\"']", " ", t)
    return re.sub(r"\s+", "", t)


def _is_excluded(col_norm: str, exclude: Sequence[str]) -> bool:
    return any(_norm(ex) and _norm(ex) in col_norm for ex in exclude)


def find_col(
    df: pd.DataFrame,
    candidates: Iterable[str],
    exclude: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """بهترین ستون منطبق با فهرست کاندیدها را برمی‌گرداند (یا None)."""
    exclude = list(exclude or [])
    norm_map = {}
    for col in df.columns:
        n = _norm(col)
        if n and n not in norm_map:
            norm_map[n] = col

    cands = [c for c in candidates]

    # فاز ۱: تطبیق دقیق (با اعمال exclude)
    for cand in cands:
        nc = _norm(cand)
        if nc and nc in norm_map and not _is_excluded(nc, exclude):
            return norm_map[nc]

    # فاز ۲: تطبیق جزئی امتیازدهی‌شده — کوتاه‌ترین ستون منطبق برنده است
    best: Optional[tuple[float, str]] = None
    for rank, cand in enumerate(cands):
        nc = _norm(cand)
        if not nc:
            continue
        for col_norm, col_orig in norm_map.items():
            if _is_excluded(col_norm, exclude):
                continue
            if nc in col_norm or col_norm in nc:
                # امتیاز: اولویت کاندید (کمتر بهتر) + نسبت طول اضافی
                extra = abs(len(col_norm) - len(nc)) / max(len(nc), 1)
                score = rank * 10 + extra
                if best is None or score < best[0]:
                    best = (score, col_orig)
    return best[1] if best else None


def require_col(df: pd.DataFrame, candidates: Iterable[str], label: str,
                exclude: Optional[Sequence[str]] = None) -> str:
    """مثل find_col ولی در صورت نیافتن، خطای صریح می‌دهد (fail-fast)."""
    col = find_col(df, candidates, exclude)
    if col is None:
        raise KeyError(f"ستون الزامی «{label}» یافت نشد. ستون‌های موجود: {list(df.columns)[:25]}")
    return col


def get_safe_col(
    df: pd.DataFrame,
    candidates: Iterable[str],
    default_val: Any = "",
    exclude: Optional[Sequence[str]] = None,
) -> pd.Series:
    """سری ستون منطبق یا سری پیش‌فرض هم‌طول با دیتافریم."""
    col = find_col(df, candidates, exclude)
    if col is not None and col in df.columns:
        return df[col]
    return pd.Series([default_val] * len(df), index=df.index, dtype="object")


def first_present(df: pd.DataFrame, names: List[str], default_val: Any = "") -> pd.Series:
    """اولین ستون موجود از فهرست نام‌های *دقیق* (نه فازی) را برمی‌گرداند.

    برای ستون‌های استانداردشده توسط adapterها استفاده می‌شود، جایی که نام‌ها
    قطعی هستند و نباید تطبیق فازی انجام شود.
    """
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series([default_val] * len(df), index=df.index, dtype="object")
