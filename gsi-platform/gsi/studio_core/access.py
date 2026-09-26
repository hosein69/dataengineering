# -*- coding: utf-8 -*-
"""کنترل دامنه خروجی گزارش‌های قابل اشتراک.

HTML خودبسنده است؛ بنابراین هر داده‌ای که داخل فایل embed شود قابل استخراج است.
این ماژول scope را *قبل از تولید فایل* اعمال می‌کند. فیلتر JavaScript امنیت نیست.
"""
from __future__ import annotations

__contract__ = 1

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence

import pandas as pd

SENSITIVE_RX = re.compile(
    r"(EMAIL|E_MAIL|MAIL_ADDRESS|MOBILE|PHONE|TEL|NATIONAL_ID|NATIONAL_CODE|"
    r"SSN|PASSWORD|TOKEN|SECRET|KEY_EMP|EMP_CODE|PERSONNEL|آدرس ایمیل|ایمیل|موبایل|تلفن|کد ملی)", re.I)

AUDIENCES = {
    "internal": "داخلی بدون محدودیت نقش",
    "executive": "مدیر ارشد / رئیس",
    "manager": "مدیر / رئیس اداره",
    "supervisor": "سرپرست",
    "expert": "کارشناس",
    "auditor": "ممیزی / کنترل داده",
}


def is_sensitive_field(name: str) -> bool:
    """True if a column name is treated as share-sensitive by default."""
    return bool(SENSITIVE_RX.search(str(name or "")))


def sanitize_fields(columns: Iterable[str], *, include_sensitive: bool = False) -> List[str]:
    """Remove share-sensitive field names while preserving input order."""
    out: List[str] = []
    for c in columns:
        if c in out:
            continue
        if not include_sensitive and is_sensitive_field(c):
            continue
        out.append(c)
    return out


@dataclass(frozen=True)
class AccessResult:
    df: pd.DataFrame
    fields: List[str]
    removed_fields: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)


def _scope_values(df: pd.DataFrame, column: str, values: Sequence[str]) -> pd.DataFrame:
    if not values:
        return df
    if column not in df.columns:
        return df.iloc[0:0].copy()
    wanted = {str(x).strip() for x in values if str(x).strip()}
    if not wanted:
        return df
    return df[df[column].fillna("").astype(str).str.strip().isin(wanted)].copy()


def apply_access_scope(df: pd.DataFrame, fields: Iterable[str], *, audience: str = "internal",
                       allowed_departments: Sequence[str] = (),
                       allowed_experts: Sequence[str] = (),
                       include_sensitive: bool = False) -> AccessResult:
    """Row/column scope را قبل از serialize شدن داده اعمال می‌کند."""
    out = df.copy()
    messages: List[str] = []
    before = len(out)
    out = _scope_values(out, "ORG_DEPT", allowed_departments)
    out = _scope_values(out, "CANONICAL_EXPERT", allowed_experts)
    if len(out) != before:
        messages.append(f"دامنه دسترسی: {len(out):,} از {before:,} ردیف مجاز باقی ماند.")

    selected = [c for c in fields if c in out.columns]
    removed: List[str] = []
    if not include_sensitive:
        for c in list(selected):
            if is_sensitive_field(c):
                selected.remove(c)
                removed.append(c)
        if removed:
            messages.append(f"{len(removed)} فیلد حساس از خروجی اشتراکی حذف شد.")

    # برای auditor محدودیت ستونی خودکار نداریم؛ برای سایر نقش‌ها هم انتخاب کاربر
    # معتبر است، اما داده فقط پس از row-scope و حذف PII وارد فایل می‌شود.
    return AccessResult(out, selected, removed, messages)
