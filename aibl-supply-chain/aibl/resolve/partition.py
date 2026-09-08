# -*- coding: utf-8 -*-
"""افراز داده — طبق تصمیم شما: **دو محور مستقل**.

محور A (کامل بودن کلید — مشخصات §۷):
    P1 = نه بارنامه دارد نه سفارش   (نامشخص)
    P2 = فقط بارنامه دارد
    P3 = هم بارنامه هم سفارش       (کامل)

محور B (پوشش عملیاتی — منطق کد فعلی):
    M1 = در فایل مقاومت هست                       → گزارش اصلی
    M2 = در مقاومت نیست ولی ساتا یا کوتاژ دارد    → کنارگذاشته (ولی گزارش می‌شود)
    M3 = نه مقاومت، نه ساتا، نه کوتاژ             → تعیین تکلیف

FIX-9: بررسی COTAGE_NO و SATA_NO با ``is_empty_val`` انجام می‌شود، نه truthiness.
B6 (FIX): اگر فایل مقاومت غایب باشد، به‌جای خالی شدن بی‌صدای گزارش اصلی،
هشدار بحرانی صادر و کل داده به محور A سپرده می‌شود.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd

from ..core.text import is_empty_val
from ..dataio.logging_setup import log

AXIS_A = "PARTITION_KEY"
AXIS_B = "PARTITION_COVERAGE"

P1_NEITHER = "P1 — فاقد بارنامه و سفارش"
P2_BL_ONLY = "P2 — فقط بارنامه"
P3_COMPLETE = "P3 — بارنامه و سفارش"

M1_MAIN = "M1 — موجود در مقاومت"
M2_EXCLUDED = "M2 — فاقد مقاومت، دارای ساتا/کوتاژ"
M3_TO_RESOLVE = "M3 — تعیین تکلیف"


@dataclass
class PartitionResult:
    df: pd.DataFrame
    main: pd.DataFrame
    excluded: pd.DataFrame
    to_resolve: pd.DataFrame
    counts: Dict[str, int]


def _nonempty(s: pd.Series) -> pd.Series:
    return ~s.map(is_empty_val)


def partition(df: pd.DataFrame, moghavemat_available: bool = True) -> PartitionResult:
    has_bl = _nonempty(df.get("CANONICAL_BL", pd.Series([""] * len(df), index=df.index)))
    has_order = _nonempty(df.get("CANONICAL_ORDER", pd.Series([""] * len(df), index=df.index)))

    axis_a = pd.Series(P1_NEITHER, index=df.index, dtype="object")
    axis_a[has_bl & ~has_order] = P2_BL_ONLY
    axis_a[has_bl & has_order] = P3_COMPLETE
    df = df.copy()
    df[AXIS_A] = axis_a

    in_mogh = df.get("IS_IN_MOGHAVEMAT", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    has_sata = _nonempty(df.get("SATA_NO", pd.Series([""] * len(df), index=df.index)))
    has_cotage = _nonempty(df.get("COTAGE_NO", pd.Series([""] * len(df), index=df.index)))
    has_evidence = has_sata | has_cotage

    axis_b = pd.Series(M3_TO_RESOLVE, index=df.index, dtype="object")
    axis_b[~in_mogh & has_evidence] = M2_EXCLUDED
    axis_b[in_mogh] = M1_MAIN
    df[AXIS_B] = axis_b

    if not moghavemat_available:
        log.critical("🚨 فایل مقاومت در دسترس نیست! محور B بی‌اعتبار است؛ "
                     "گزارش اصلی به کل رکوردهای دارای شواهد گمرکی تغییر یافت.")
        axis_b = pd.Series(M3_TO_RESOLVE, index=df.index, dtype="object")
        axis_b[has_evidence] = M1_MAIN
        df[AXIS_B] = axis_b

    main = df[df[AXIS_B] == M1_MAIN].copy()
    excluded = df[df[AXIS_B] == M2_EXCLUDED].copy()
    to_resolve = df[df[AXIS_B] == M3_TO_RESOLVE].copy()

    counts = {
        "کل ردیف": len(df),
        "بارنامه یکتا": int(df.loc[has_bl, "CANONICAL_BL"].nunique()) if "CANONICAL_BL" in df else 0,
        P1_NEITHER: int((df[AXIS_A] == P1_NEITHER).sum()),
        P2_BL_ONLY: int((df[AXIS_A] == P2_BL_ONLY).sum()),
        P3_COMPLETE: int((df[AXIS_A] == P3_COMPLETE).sum()),
        M1_MAIN: len(main),
        M2_EXCLUDED: len(excluded),
        M3_TO_RESOLVE: len(to_resolve),
    }
    log.info("📊 افراز دو محوری:")
    for k, v in counts.items():
        log.info(f"   • {k}: {v}")

    return PartitionResult(df, main, excluded, to_resolve, counts)
