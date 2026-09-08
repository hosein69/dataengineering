# -*- coding: utf-8 -*-
"""Pure filtering logic for AIBL Studio."""
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


def _str_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series("", index=df.index, dtype="string")
    return df[col].fillna("").astype(str)


def apply_filters(df: pd.DataFrame, state: FilterState) -> pd.DataFrame:
    out = df.copy()
    if state.criticality and "بحرانی (کوتاه)" in out.columns:
        out = out[_str_series(out, "بحرانی (کوتاه)").isin(state.criticality)]
    if state.management and "ORG_DEPT" in out.columns:
        out = out[_str_series(out, "ORG_DEPT").isin(state.management)]
    if state.transport and "روش حمل" in out.columns:
        out = out[_str_series(out, "روش حمل").isin(state.transport)]
    if state.expert and "CANONICAL_EXPERT" in out.columns:
        out = out[_str_series(out, "CANONICAL_EXPERT").isin(state.expert)]
    if state.expert_role and "EXPERT_ROLE" in out.columns:
        out = out[_str_series(out, "EXPERT_ROLE").isin(state.expert_role)]
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
    return {
        "criticality": vals("بحرانی (کوتاه)"),
        "management": vals("ORG_DEPT"),
        "transport": vals("روش حمل"),
        "expert": vals("CANONICAL_EXPERT"),
        "expert_role": vals("EXPERT_ROLE"),
    }
