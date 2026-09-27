# -*- coding: utf-8 -*-
"""Fail-closed HR hierarchy for personal publication.

Role is an HR fact, never a user-selected UI preference.  Names only join when
unique in the active roster; a fuzzy match cannot expand a person's access.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict

import pandas as pd

from ..core.text import clean_employee_code, normalize_persian_text

LEVELS = ("expert", "head", "manager", "vice")
LABELS = {"expert": "کارشناس", "head": "رئیس", "manager": "مدیر", "vice": "معاون"}


def _s(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return normalize_persian_text(str(value)).strip()


def _active(value) -> bool:
    value = _s(value).lower()
    return (value.startswith("فعال") and "غیرفعال" not in value) or value == "active"


def _name(row) -> str:
    return _s(row.get("HR_FULL_NAME")) or _s(
        f"{_s(row.get('HR_FIRST_NAME'))} {_s(row.get('HR_LAST_NAME'))}")


def _level(post: str) -> str:
    post = _s(post)
    if "معاون" in post:
        return "vice"
    if "مدیر" in post and "مدیریت" not in post:
        return "manager"
    if "رئیس" in post or "رييس" in post:
        return "head"
    return "expert"


@dataclass(frozen=True)
class Scope:
    employee_code: str
    name: str
    level: str
    organization: str
    member_codes: frozenset[str]


def build_scopes(hr: pd.DataFrame) -> Dict[str, Scope]:
    """Build exact-code scopes; empty/duplicate/inactive HR identities grant none."""
    if hr is None or hr.empty:
        raise ValueError("HR منتشرشده برای تعیین دامنه سازمانی موجود نیست.")
    rows = []
    for raw in hr.to_dict("records"):
        if not _active(raw.get("HR_STATUS")):
            continue
        emp = clean_employee_code(raw.get("KEY_EMP", ""))
        name = _name(raw)
        if emp and name:
            rows.append({"code": emp, "name": name,
                         "post": _s(raw.get("HR_POST")),
                         "head": _s(raw.get("HR_HEAD")),
                         "manager": _s(raw.get("HR_MANAGER")),
                         "vice": _s(raw.get("HR_VICE")),
                         "dept": _s(raw.get("HR_DEPT"))})
    code_counts = Counter(r["code"] for r in rows)
    rows = [r for r in rows if code_counts[r["code"]] == 1]
    name_counts = Counter(r["name"] for r in rows)
    vice_counts = Counter(r["vice"] for r in rows if _level(r["post"]) == "vice" and r["vice"])
    scopes = {}
    for person in rows:
        level = _level(person["post"])
        members = {person["code"]}
        if level in {"head", "manager"} and name_counts[person["name"]] == 1:
            field = level
            members.update(r["code"] for r in rows if r[field] == person["name"])
        elif (level == "vice" and name_counts[person["name"]] == 1
              and person["vice"] and vice_counts[person["vice"]] == 1):
            # A vice has no person-name field on subordinates; both must share
            # the exact HR vice unit, and the leader must have a vice post.
            members.update(r["code"] for r in rows if r["vice"] == person["vice"])
        org = person["vice"] if level == "vice" else person["dept"]
        scopes[person["code"]] = Scope(person["code"], person["name"], level,
                                        org, frozenset(members))
    return scopes


def restrict_rows(df: pd.DataFrame, scope: Scope) -> pd.DataFrame:
    if "KEY_EMP" not in df.columns:
        raise ValueError("KEY_EMP در Snapshot منتشرشده موجود نیست.")
    keys = df["KEY_EMP"].map(clean_employee_code)
    return df.loc[keys.isin(scope.member_codes)].copy()
