# -*- coding: utf-8 -*-
"""منطقِ فیلترِ استودیو — خالص، بدون Streamlit.

## چرا اینجا نامِ ستون «کاندید» است، نه یک رشته

فیلترِ «روش حمل» یک بار در تولید **بی‌صدا** از کار افتاد: کد دنبال
ستونی به نامِ ``"روش حمل"`` می‌گشت، ولی نامِ واقعیِ ستون در فریمِ کاری
``TRANSPORT_MODE`` است — «روش حمل» فقط برچسبی است که هنگامِ **خروجی**
جایگزین می‌شود.

نتیجه‌اش این بود که شرطِ ``if "روش حمل" in out.columns`` همیشه نادرست
می‌شد: نه خطایی، نه هشداری — فقط فیلتر هیچ‌وقت اعمال نمی‌شد و فهرستِ
گزینه‌ها خالی می‌ماند. کاربر می‌دید که فیلتر «قفل» است.

پس دو قاعده اینجا قفل شد:

۱ هر فیلتر **فهرستی از نام‌های ممکن** دارد (فنی و برچسبی)، و اولین
  ستونِ موجود برنده است.
۲ ``missing_columns()`` می‌گوید کدام فیلتر در این داده ستونی ندارد، تا
  رابط بتواند صادقانه بگوید «این فیلتر روی این داده معنا ندارد» —
  به‌جای نمایشِ یک کنترلِ خالیِ گمراه‌کننده.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional
import pandas as pd

@dataclass
class FilterState:
    criticality: List[str] = field(default_factory=list)
    management: List[str] = field(default_factory=list)
    transport: List[str] = field(default_factory=list)
    expert: List[str] = field(default_factory=list)
    #: فیلتر بر اساس نقش کارشناسی — «کارشناس ترخیص» با «کارشناس خرید»
    #: یکی نیست و نباید در یک فهرست قاطی شوند.
    expert_role: List[str] = field(default_factory=list)
    search: str = ""
    critical_only: bool = False


#: نامِ ممکنِ ستونِ هر فیلتر — فنی اول، برچسبِ خروجی بعد.
#: ترتیب مهم است: فریمِ کاری نامِ فنی دارد و فریمِ خروجی برچسب.
COLUMNS: Dict[str, tuple] = {
    "criticality": ("بحرانی (کوتاه)", "CRITICAL_SHORT"),
    "management": ("ORG_DEPT", "مدیریت", "اداره"),
    "transport": ("TRANSPORT_MODE", "روش حمل"),
    "expert": ("CANONICAL_EXPERT", "کارشناس"),
    "expert_role": ("EXPERT_ROLE", "نقش کارشناسی"),
}


def resolve(df: pd.DataFrame, name: str) -> str:
    """نامِ واقعیِ ستونِ این فیلتر در این دیتافریم، یا رشتهٔ خالی."""
    for c in COLUMNS.get(name, ()):
        if c in df.columns:
            return c
    return ""


def missing_columns(df: pd.DataFrame) -> List[str]:
    """فیلترهایی که در این داده هیچ ستونی ندارند.

    رابط از این استفاده می‌کند تا به‌جای یک کنترلِ خالی، صادقانه بگوید
    این فیلتر روی این داده معنا ندارد.
    """
    return [k for k in COLUMNS if not resolve(df, k)]


def _str_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series("", index=df.index, dtype="string")
    return df[col].fillna("").astype(str)


def _pick(df: pd.DataFrame, out: pd.DataFrame, name: str,
          chosen: List[str]) -> pd.DataFrame:
    col = resolve(out, name)
    if not chosen or not col:
        return out
    return out[_str_series(out, col).isin(chosen)]


def apply_filters(df: pd.DataFrame, state: FilterState) -> pd.DataFrame:
    out = df.copy()
    out = _pick(df, out, "criticality", state.criticality)
    out = _pick(df, out, "management", state.management)
    out = _pick(df, out, "transport", state.transport)
    out = _pick(df, out, "expert", state.expert)
    out = _pick(df, out, "expert_role", state.expert_role)
    if state.critical_only:
        mask = pd.Series(False, index=out.index)
        for c in ("BL_CRITICAL", "ORDER_CRITICAL"):
            if c in out.columns:
                mask |= out[c].fillna(False).astype(bool)
        if "کد طبقه بحرانی" in out.columns:
            mask |= _str_series(out, "کد طبقه بحرانی").isin(["STOCKOUT", "CRITICAL"])
        out = out[mask]
    if state.search.strip():
        needle = state.search.strip().lower()
        cols = [c for c in ["KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_REG", "ORG_DEPT"] if c in out.columns]
        if cols:
            hay = out[cols].fillna("").astype(str).agg(" | ".join, axis=1).str.lower()
            out = out[hay.str.contains(needle, regex=False, na=False)]
    return out


def filter_options(df: pd.DataFrame) -> Dict[str, List[str]]:
    """گزینه‌های هر فیلتر، از همان ستونی که ``apply_filters`` می‌خواند.

    این دو تابع باید **همیشه** یک ستون را ببینند؛ وگرنه کاربر گزینه‌ای
    می‌بیند که انتخابش هیچ اثری ندارد — یا برعکس، فیلتری کار می‌کند که
    گزینه‌ای برایش نشان داده نشده. هر دو از ``resolve`` می‌خوانند.
    """
    def vals(name: str) -> List[str]:
        col = resolve(df, name)
        if not col:
            return []
        seen = df[col].fillna("").astype(str).unique().tolist()
        return sorted([x for x in seen if x.strip()])
    return {k: vals(k) for k in COLUMNS}
