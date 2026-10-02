# -*- coding: utf-8 -*-
"""دامنه تاریخی خروجی‌ها، کنار «حداکثر ردیف».

مالک خواست دامنه گزارش به‌جای (یا کنار) حداکثر ردیف، با بازه تاریخ هم تعیین شود:
تاریخ درخواست، تاریخ ثبت سفارش، تاریخ PO و تاریخ IL. هر دامنه چند ستون نامزد دارد و
برای هر ردیف اولین تاریخ معتبر از همان ترتیب خوانده می‌شود؛ ستونی که در فریم نیست
نادیده گرفته می‌شود و اگر هیچ‌کدام نباشد دامنه «در دسترس نیست» اعلام می‌شود، نه اینکه
بی‌صدا همه ردیف‌ها حذف یا نگه داشته شوند.

ردیف بدون تاریخ به‌طور پیش‌فرض بیرون می‌ماند (بازه یعنی «تاریخش در این بازه است»)، ولی
با ``include_missing`` نگه داشته می‌شود. ورودی بازه متن است و شمسی («1405/01/01») و
میلادی («2026-03-21») هر دو پذیرفته می‌شوند.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from ..core.jalali import CalendarEngine, gregorian_to_jalali

#: کلید → (عنوان فارسی، عنوان انگلیسی، ستون‌های نامزد به ترتیب اولویت)
DATE_SCOPES: Dict[str, Tuple[str, str, Tuple[str, ...]]] = {
    "request": ("تاریخ درخواست (تخصیص ارز)", "Request date (FX allocation)",
                ("NTSW_REQ_DATE", "ALLOC_QUEUE_ENTER_DATE", "NTSW_QUEUE_ENTER_DATE")),
    "registration": ("تاریخ ثبت سفارش", "Order registration date",
                     ("NTSW_REG_DATE", "REG_DATE", "CRD_REG_DATE")),
    "po": ("تاریخ PO (ابلاغ سفارش)", "PO date",
           ("PO_SENT_DATE", "MOGH_PO_SENT_DATE", "PURCHASE_ORDER_DATE", "SAP_PO_DATE")),
    "il": ("تاریخ IL", "IL date", ("IL_REG_DATE", "IL_APPROVAL_DATE")),
}


@dataclass
class DateRange:
    start: Optional[date] = None
    end: Optional[date] = None
    include_missing: bool = False

    @property
    def active(self) -> bool:
        return self.start is not None or self.end is not None


@dataclass
class ScopeResult:
    df: pd.DataFrame
    rows_before: int
    rows_after: int
    notes: List[str] = field(default_factory=list)
    unavailable: List[str] = field(default_factory=list)


def parse_bound(text) -> Optional[date]:
    """متن مرز بازه → تاریخ؛ خالی یعنی بی‌مرز. متن نامعتبر ``ValueError`` می‌دهد."""
    if text is None or (isinstance(text, str) and not text.strip()):
        return None
    d = CalendarEngine.parse(text)
    if d is None:
        raise ValueError(f"تاریخ «{text}» خوانده نشد؛ مثل 1405/01/01 یا 2026-03-21 بنویسید.")
    return d


def jalali_text(d: Optional[date]) -> str:
    if d is None:
        return ""
    y, m, dd = gregorian_to_jalali(d)
    return f"{y:04d}/{m:02d}/{dd:02d}"


def available_columns(df: pd.DataFrame, key: str) -> List[str]:
    return [c for c in DATE_SCOPES[key][2] if c in df.columns]


def scope_dates(df: pd.DataFrame, key: str) -> pd.Series:
    """تاریخ هر ردیف برای یک دامنه: اولین مقدار معتبر از ستون‌های نامزد (یا None)."""
    cols = available_columns(df, key)
    out = pd.Series([None] * len(df), index=df.index, dtype=object)
    for c in cols:
        uniq = pd.unique(df[c].astype(object).to_numpy())
        parsed = {v: CalendarEngine.parse(v) for v in uniq}
        vals = df[c].astype(object).map(parsed)
        fill = out.isna() & vals.notna()
        out[fill] = vals[fill]
    return out


def apply_date_scope(df: pd.DataFrame, ranges: Mapping[str, DateRange]) -> ScopeResult:
    """همه بازه‌های فعال با «و» روی فریم اعمال می‌شوند."""
    before = len(df)
    res = ScopeResult(df=df, rows_before=before, rows_after=before)
    if df is None or df.empty:
        return res
    mask = pd.Series(True, index=df.index)
    for key, rng in ranges.items():
        if key not in DATE_SCOPES or rng is None or not rng.active:
            continue
        title = DATE_SCOPES[key][0]
        cols = available_columns(df, key)
        if not cols:
            res.unavailable.append(title)
            continue
        dates = scope_dates(df, key)
        missing = dates.isna()
        ok = pd.Series(True, index=df.index)
        if rng.start is not None:
            ok &= dates.map(lambda d: d is not None and d >= rng.start)
        if rng.end is not None:
            ok &= dates.map(lambda d: d is not None and d <= rng.end)
        if rng.include_missing:
            ok |= missing
        mask &= ok
        res.notes.append(
            f"{title}: {jalali_text(rng.start) or '…'} تا {jalali_text(rng.end) or '…'} "
            f"(مبنا: {'، '.join(cols)}؛ {int(missing.sum()):,} ردیف بی‌تاریخ "
            f"{'نگه داشته شد' if rng.include_missing else 'بیرون ماند'})")
    if res.notes:
        res.df = df.loc[mask]
        res.rows_after = int(mask.sum())
    return res


def describe(res: ScopeResult) -> str:
    if not res.notes and not res.unavailable:
        return ""
    parts = list(res.notes)
    parts += [f"{t}: ستون تاریخش در این داده نیست؛ اعمال نشد" for t in res.unavailable]
    return f"دامنه تاریخی: {res.rows_after:,} از {res.rows_before:,} ردیف · " + " · ".join(parts)
