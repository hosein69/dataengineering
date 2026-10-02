# -*- coding: utf-8 -*-
"""Global report evidence authority policy.

This module is the single policy used by the full GSI report whenever two
sources provide semantically interchangeable evidence for the same business
field.  It is deliberately separate from merge order: merge order is a
technical relation-building concern, while authority decides which observed
value wins a conflict.

Policy V29.7.3
--------------
Tier 1 (authoritative): Commercial Expert / ``moghavemat`` and ``ntsw``.
Tier 2 (secondary): ``abbasi`` and ``sata``.
Tier 3: all complementary operational/financial sources.

A lower tier may fill a blank, but must not overwrite a non-empty value from a
higher tier.  Within the same tier, caller-declared order is preserved because
field semantics (for example NTSW currency before expert PI currency) remain
important.
"""
from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple, TypeVar

import yaml

from .sources import _yaml_path

T = TypeVar("T")

def _load_policy() -> dict:
    try:
        with open(_yaml_path(), "r", encoding="utf-8") as f:
            root = yaml.safe_load(f) or {}
        return dict(root.get("authority") or {})
    except Exception:
        return {}


_POLICY = _load_policy()
_TIERS = dict(_POLICY.get("tiers") or {})
PRIMARY_SOURCES: Tuple[str, ...] = tuple(_TIERS.get("tier_1") or ("moghavemat", "ntsw"))
SECONDARY_SOURCES: Tuple[str, ...] = tuple(_TIERS.get("tier_2") or ("abbasi", "sata"))

# Prefixes are standardized adapter prefixes.  Longest-first matching is used
# only for domain-level candidate columns (DERIVED); canonical keys pass their
# source explicitly and do not depend on prefix inference.
_PREFIX_SOURCE: Tuple[Tuple[str, str], ...] = (
    ("MOGH_", "moghavemat"),
    ("NTSW_", "ntsw"),
    ("SATA_", "sata"),
    ("BL_", "abbasi"),
    ("CL_", "clearance"),
    ("COT_", "cotage"),
    ("ORC_", "oracle"),
    ("FX_", "fx_transaction"),
    ("CRD_", "credit"),
    ("IL_", "ilappend"),
    ("SAP_", "sap"),
    ("DOC_", "doccheck"),
    ("HR_", "hr"),
)


def source_tier(source: str) -> int:
    """Return 1 (primary), 2 (secondary), or 3 (complementary)."""
    s = str(source or "").strip().lower()
    if s in PRIMARY_SOURCES:
        return 1
    if s in SECONDARY_SOURCES:
        return 2
    return 3


def source_of_column(column: str) -> str:
    """Infer standardized adapter source from a prefixed column name."""
    c = str(column or "").strip().upper()
    for prefix, source in _PREFIX_SOURCE:
        if c.startswith(prefix):
            return source
    return ""


def sort_source_candidates(candidates: Sequence[Tuple[T, str]]) -> List[Tuple[T, str]]:
    """Stable authority sort for ``(payload, source)`` candidates.

    Stable sorting is intentional: equal-tier field semantics stay exactly as
    declared by the caller.
    """
    return sorted(list(candidates), key=lambda item: source_tier(item[1]))


def sort_columns(columns: Iterable[str]) -> List[str]:
    """Stable authority sort for standardized source-prefixed columns."""
    cols = list(columns)
    return sorted(cols, key=lambda c: source_tier(source_of_column(c)))


def policy_label() -> str:
    return "کارشناسان + NTSW درجه‌اول؛ عباسی + SATA درجه‌دوم؛ سایر منابع تکمیلی"


def policy_dict() -> dict:
    return {
        "tier_1": list(PRIMARY_SOURCES),
        "tier_2": list(SECONDARY_SOURCES),
        "fallback_rule": _POLICY.get("fallback_rule", "lower_tier_fills_blank_only"),
        "scope": _POLICY.get("scope", "full_report"),
    }
