# -*- coding: utf-8 -*-
"""کنترل دامنه داده پیش از ساخت artifact.

فیلتر داخل HTML امنیت نیست؛ بنابراین scope نقش/اداره/کارشناس باید قبل از embed
شدن داده اعمال شود. این ماژول عمداً مستقل از UI است تا CLI/Studio/Email همگی
یک قرارداد داشته باشند.
"""
from __future__ import annotations

__contract__ = 1
from dataclasses import dataclass, field
from typing import Iterable, List
import re
import pandas as pd

SENSITIVE_PATTERNS = [
    re.compile(r"EMAIL|MOBILE|PHONE|NATIONAL|کد ?ملی|موبایل|تلفن|ایمیل", re.I),
]

@dataclass(frozen=True)
class AccessScope:
    persona: str = "expert"  # executive | manager | supervisor | expert | auditor
    departments: List[str] = field(default_factory=list)
    experts: List[str] = field(default_factory=list)
    allowed_fields: List[str] = field(default_factory=list)
    deny_sensitive: bool = True


def apply_row_scope(df: pd.DataFrame, scope: AccessScope) -> pd.DataFrame:
    out = df
    if scope.departments and "ORG_DEPT" not in df.columns or scope.experts and "CANONICAL_EXPERT" not in df.columns:
        return df.iloc[0:0].copy()
    if scope.departments and "ORG_DEPT" in out.columns:
        wanted={str(x).strip() for x in scope.departments}
        out=out[out["ORG_DEPT"].astype(str).str.strip().isin(wanted)]
    if scope.experts and "CANONICAL_EXPERT" in out.columns:
        wanted={str(x).strip() for x in scope.experts}
        out=out[out["CANONICAL_EXPERT"].astype(str).str.strip().isin(wanted)]
    return out.copy()


def filter_fields(fields: Iterable[str], scope: AccessScope) -> List[str]:
    allowed=set(scope.allowed_fields or [])
    out=[]
    for c in fields:
        if allowed and c not in allowed:
            continue
        if scope.deny_sensitive and any(p.search(str(c)) for p in SENSITIVE_PATTERNS):
            continue
        out.append(c)
    return out
