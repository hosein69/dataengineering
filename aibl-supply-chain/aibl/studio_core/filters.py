# -*- coding: utf-8 -*-
"""Pure filtering logic for AIBL Studio."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Mapping
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


def _str_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series("", index=df.index, dtype="string")
    return df[col].fillna("").astype(str)



# نام‌های عمومی UI → ستون فنی واقعی. برچسب فارسی فقط presentation است و
# نباید منطق فیلتر را بشکند.
ALIASES = {
    "transport": ("TRANSPORT_MODE", "روش حمل"),
    "criticality": ("بحرانی (کوتاه)", "طبقه بحرانی"),
    "management": ("ORG_DEPT", "مدیریت"),
    "expert": ("CANONICAL_EXPERT", "کارشناس مالک مرحله فعلی"),
    "expert_role": ("EXPERT_ROLE", "نقش کارشناس مالک"),
}


def resolve(df: pd.DataFrame, field: str) -> Optional[str]:
    """نام منطقی/فارسی/فنی را به ستون واقعی df resolve می‌کند."""
    if field in df.columns:
        return field
    candidates = ALIASES.get(field, (field,))
    for c in candidates:
        if c in df.columns:
            return c
    return None


def missing_columns(df: pd.DataFrame) -> List[str]:
    """فیلترهایی که در این اجرا ستون مبنایشان واقعاً وجود ندارد."""
    return [k for k in ALIASES if resolve(df, k) is None]

def apply_filters(df: pd.DataFrame, state: FilterState) -> pd.DataFrame:
    out = df.copy()
    c = resolve(out, "criticality")
    if state.criticality and c:
        out = out[_str_series(out, c).isin(state.criticality)]
    c = resolve(out, "management")
    if state.management and c:
        out = out[_str_series(out, c).isin(state.management)]
    c = resolve(out, "transport")
    if state.transport and c:
        wanted = set(state.transport)
        try:
            from ..rulebook import get_rulebook
            rb = get_rulebook()
            wanted_codes = {rb.transport_mode(x) or str(x).strip().upper() for x in wanted}
            wanted = wanted | wanted_codes
        except Exception:
            pass
        out = out[_str_series(out, c).map(lambda x: x if x in wanted else str(x).strip().upper()).isin(wanted)]
    c = resolve(out, "expert")
    if state.expert and c:
        out = out[_str_series(out, c).isin(state.expert)]
    c = resolve(out, "expert_role")
    if state.expert_role and c:
        out = out[_str_series(out, c).isin(state.expert_role)]
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
    def vals(col: str) -> List[str]:
        if col not in df.columns:
            return []
        return sorted([x for x in df[col].fillna("").astype(str).unique().tolist() if x])
    transport_col = resolve(df, "transport")
    transport_values = vals(transport_col or "")
    try:
        from ..rulebook import get_rulebook
        rb = get_rulebook()
        transport_values = [rb.transport_mode_fa(v) for v in transport_values]
        # نمایش یکتا و با ترتیب معنادار: دریایی، زمینی، هوایی، سپس سایر.
        order = ["دریایی", "زمینی (جاده‌ای)", "هوایی", "ریلی", "چندوجهی", "پست سریع / کوریر"]
        transport_values = sorted(set(transport_values),
                                  key=lambda x: (order.index(x) if x in order else 99, x))
    except Exception:
        pass
    return {
        "criticality": vals("بحرانی (کوتاه)"),
        "management": vals("ORG_DEPT"),
        "transport": transport_values,
        "expert": vals("CANONICAL_EXPERT"),
        "expert_role": vals("EXPERT_ROLE"),
    }
