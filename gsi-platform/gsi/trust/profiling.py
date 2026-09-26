# -*- coding: utf-8 -*-
"""The point-zero mirror: measure what the data actually is, without judging it.

This module answers one question honestly — *for every field that matters, how
many cases have a usable value, and where exactly are the ones that do not?*

Two design decisions carry most of the weight:

**Defects are counted at entity grain, never row grain.** The published mart has
one row per bill-of-lading × material, but a commitment balance lives at
registration grain and is repeated across every one of those rows. Counting per
row would report one missing cell as forty, flooding the owner's worklist with
the same cell and making the "point zero" number meaningless. The profiler emits
at most one defect per (entity, field, code) and measures coverage over distinct
entities.

**The three most common bad values in a column are reported.** In real source
files the overwhelming majority of defects in a column are two or three repeated
patterns — ``"در حال بررسی"``, ``"-"``, ``"0"``. Showing them turns "1,840
defects in this column" into a five-minute fix the owner can see the shape of.
"""
from __future__ import annotations

__contract__ = 1

from collections import Counter, defaultdict
from dataclasses import dataclass, field as dc_field
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from ..core.jalali import CalendarEngine
from ..core.numeric_parse import parse_decimal
from ..core.text import clean_key, normalize_persian_text
from . import codes as C
from .verdict import (Defect, DefectLedger, Evidence, Owner,
                      PLATFORM_OWNER, PLATFORM_ROLE)

# ── field kinds ─────────────────────────────────────────────────────────────
TEXT = "TEXT"
NUMBER = "NUMBER"
DATE = "DATE"
CURRENCY = "CURRENCY"
KEY = "KEY"

#: Below this many cases, "nothing is filled in" is not evidence of a broken
#: mapping — it is just a small sample.
NEVER_POPULATED_MIN_ENTITIES = 3

#: Text that occupies a cell without saying anything. Distinguished from a blank
#: cell because it is evidence that somebody *looked* at the cell and had nothing
#: to put in it — which is a different conversation than "nobody got to it yet".
_PLACEHOLDERS = frozenset({
    "-", "--", "---", "نامشخص", "ندارد", "نا مشخص", "نامعلوم", "فاقد", "خالی",
    "na", "n/a", "#n/a", "null", "none", "؟", "?", "در حال بررسی", "در دست بررسی",
    "بررسی شود", "tbd", "xxx", "...", "*",
})


@dataclass(frozen=True)
class FieldRule:
    """What a field must satisfy to count as usable."""
    column: str
    kind: str = TEXT
    title_fa: str = ""
    #: A blank value in a required field is a defect; in an optional field it is
    #: simply absence and is recorded as coverage, not as a defect to route.
    required: bool = True
    allow_negative: bool = False
    #: Emit VALUE_CONFLICT when one entity carries two different values.
    check_conflict: bool = False
    source: str = ""
    #: Column holding the expert who owns *this field* (e.g. EXPERT_SETTLEMENT).
    #: Falls back to the case's generic expert when the source does not supply it.
    owner_column: str = ""
    #: Human label for that role, shown in the worklist.
    owner_role_fa: str = ""

    @property
    def label(self) -> str:
        return self.title_fa or self.column


@dataclass
class FieldProfile:
    """What the mirror shows for one field."""
    column: str
    label: str
    kind: str
    entities: int = 0
    ok: int = 0
    missing: int = 0
    suspect: int = 0
    conflict: int = 0
    top_bad_values: List[Tuple[str, int]] = dc_field(default_factory=list)

    @property
    def usable(self) -> int:
        return self.ok

    @property
    def coverage_pct(self) -> float:
        return round(100.0 * self.ok / self.entities, 1) if self.entities else 0.0

    def row(self) -> Dict[str, Any]:
        return {
            "فیلد": self.label,
            "ستون": self.column,
            "نوع": self.kind,
            "پرونده": self.entities,
            "سالم": self.ok,
            "خالی": self.missing,
            "مشکوک": self.suspect,
            "متعارض": self.conflict,
            "پوشش (٪)": self.coverage_pct,
            "شایع‌ترین مقدار نامعتبر": " · ".join(
                f"«{v}»×{n}" for v, n in self.top_bad_values[:3]) or "—",
        }


@dataclass
class ProfileResult:
    entity_type: str
    entities: int
    fields: List[FieldProfile]
    ledger: DefectLedger
    #: entity key -> field -> worst state, for the fitness layer.
    states: Dict[str, Dict[str, str]]

    def fields_frame(self) -> pd.DataFrame:
        cols = list(FieldProfile("", "", "").row().keys())
        if not self.fields:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame([f.row() for f in self.fields], columns=cols)

    def state_of(self, key: str, column: str) -> str:
        return self.states.get(key, {}).get(column, C.MISSING)

    def summary(self) -> Dict[str, Any]:
        worst = sorted(self.fields, key=lambda f: f.coverage_pct)
        return {
            "entity_type": self.entity_type,
            "entities": self.entities,
            "fields": len(self.fields),
            "mean_coverage_pct": round(
                sum(f.coverage_pct for f in self.fields) / len(self.fields), 1
            ) if self.fields else 0.0,
            "weakest_fields": [(f.label, f.coverage_pct) for f in worst[:5]],
            **self.ledger.summary(),
        }


def _is_placeholder(raw: str) -> bool:
    return normalize_persian_text(raw).casefold() in _PLACEHOLDERS


def _blank(value: Any) -> bool:
    """Physically empty only — None, NaN, or whitespace.

    Deliberately *not* ``core.text.is_empty_val``: that helper is semantic and
    treats ``"نامشخص"`` and ``"-"`` as empty, which is right for business logic
    and wrong here. The trust layer must see those strings to tell the owner
    "somebody typed «نامشخص» into 1,840 cells" — the single most actionable
    thing a field profile can say.
    """
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return not str(value).strip()


def _known_currencies() -> frozenset:
    from ..rulebook import get_rulebook
    rb = get_rulebook()
    out = {str(c["code"]).upper() for c in (rb.get("currencies.currencies", []) or [])}
    out |= {str(d["code"]).upper() for d in (rb.get("currencies.derived_units", []) or [])}
    return frozenset(out)


def _classify(raw: str, rule: FieldRule, *, ref_date: Optional[date],
              currencies: frozenset) -> Tuple[str, str]:
    """(state, defect_code) for one non-normalised raw value.

    Returns ``("OK", "")`` when the value is usable. Pure and value-only: the
    caller attaches entity, evidence and owner.
    """
    if _blank(raw):
        return C.MISSING, "VALUE_MISSING"
    text = str(raw).strip()
    if _is_placeholder(text):
        return C.MISSING, "VALUE_PLACEHOLDER"

    if rule.kind == NUMBER:
        value = parse_decimal(text, strict=True)
        if value is None:
            return C.SUSPECT, "VALUE_UNPARSEABLE"
        if value < 0 and not rule.allow_negative:
            return C.SUSPECT, "VALUE_NEGATIVE"
        return C.OK, ""

    if rule.kind == DATE:
        parsed = CalendarEngine.parse(text)
        if parsed is None:
            return C.SUSPECT, "DATE_INVALID"
        if ref_date is not None and parsed > ref_date:
            return C.SUSPECT, "DATE_FUTURE"
        return C.OK, ""

    if rule.kind == CURRENCY:
        from ..rulebook import get_rulebook
        code = get_rulebook().normalize_currency(text)
        if not code:
            return C.SUSPECT, "CURRENCY_AMBIGUOUS"
        if code.upper() not in currencies:
            return C.SUSPECT, "CURRENCY_UNKNOWN"
        return C.OK, ""

    if rule.kind == KEY:
        key = clean_key(text)
        if not key:
            return C.MISSING, "KEY_MISSING"
        if not key.strip("0") or key in {"-", "0"}:
            return C.SUSPECT, "KEY_PLACEHOLDER"
        return C.OK, ""

    return C.OK, ""


def profile_frame(
    df: pd.DataFrame,
    rules: Sequence[FieldRule],
    *,
    entity_type: str,
    key_column: str,
    ref_date: Optional[date] = None,
    source: str = "",
) -> ProfileResult:
    """Profile ``df`` at the grain of ``key_column``.

    Rows whose key is blank are not silently dropped: they are reported once as
    ``KEY_MISSING`` under the sentinel key ``""`` so the count of unkeyed rows
    stays visible instead of vanishing from the denominator.
    """
    present = [r for r in rules if r.column in df.columns]
    ledger = DefectLedger()
    states: Dict[str, Dict[str, str]] = defaultdict(dict)

    if df.empty or key_column not in df.columns:
        return ProfileResult(entity_type, 0, [
            FieldProfile(r.column, r.label, r.kind) for r in present
        ], ledger, {})

    currencies = _known_currencies()
    keys = df[key_column].map(lambda v: "" if _blank(v) else clean_key(v))

    # Unkeyed rows are a defect in their own right, reported once.
    unkeyed = int((keys == "").sum())
    if unkeyed:
        first = df.loc[keys == ""].iloc[0]
        ledger.add(Defect(
            code="KEY_MISSING", entity_type=entity_type, entity_key="",
            evidence=Evidence.from_row(first, column=key_column, source=source),
            owner=Owner.from_row(first),
            note=f"{unkeyed:,} ردیف بدون کلید کسب‌وکار؛ به هیچ پرونده‌ای متصل نمی‌شوند.",
        ))

    keyed = df.loc[keys != ""].copy()
    keyed["__key"] = keys[keys != ""]
    entities = int(keyed["__key"].nunique())

    profiles: List[FieldProfile] = []
    for rule in present:
        prof = FieldProfile(rule.column, rule.label, rule.kind, entities=entities)
        bad_values: Counter = Counter()

        # One verdict per entity, not per row: parse each distinct raw value once.
        cache: Dict[str, Tuple[str, str]] = {}

        for key, group in keyed.groupby("__key", sort=False):
            raws = [x for x in group[rule.column].tolist()]
            distinct = {str(x).strip() for x in raws if not _blank(x)}

            # Conflict beats every other verdict: two different answers for one
            # key means the value cannot be used even though it is present.
            if rule.check_conflict and len(distinct) > 1:
                row = group.iloc[0]
                ledger.add(Defect(
                    code="VALUE_CONFLICT", entity_type=entity_type, entity_key=key,
                    evidence=Evidence.from_row(row, column=rule.column, source=source),
                    owner=Owner.from_row(row, prefer=rule.owner_column,
                                         role_label=rule.owner_role_fa),
                    note="مقادیر متفاوت: " + " | ".join(sorted(distinct)[:5]),
                ))
                states[key][rule.column] = C.CONFLICT
                prof.conflict += 1
                continue

            raw = next(iter(distinct)) if distinct else ""
            if raw not in cache:
                cache[raw] = _classify(raw, rule, ref_date=ref_date, currencies=currencies)
            state, code = cache[raw]

            states[key][rule.column] = state
            if state == C.OK:
                prof.ok += 1
                continue
            if state == C.MISSING:
                prof.missing += 1
            else:
                prof.suspect += 1
            if raw:
                bad_values[raw] += 1

            # An optional field that is simply blank is absence, not a defect to
            # route to a person; it still counts against coverage above.
            if not rule.required and state == C.MISSING:
                continue

            row = group.iloc[0]
            ledger.add(Defect(
                code=code, entity_type=entity_type, entity_key=key,
                evidence=Evidence.from_row(row, column=rule.column, source=source),
                owner=Owner.from_row(row, prefer=rule.owner_column,
                                     role_label=rule.owner_role_fa),
            ))

        prof.top_bad_values = bad_values.most_common(5)

        # A field that is empty for *every* case is almost never a thousand
        # people forgetting the same cell — it is a field the pipeline does not
        # read. Routing it as data entry would send experts to fill cells that
        # are already filled at source, and the first person who checks will
        # stop trusting every other item on the list. Report it once, against
        # the source contract, and drop the per-case noise.
        if (rule.required and prof.entities >= NEVER_POPULATED_MIN_ENTITIES
                and prof.ok == 0 and prof.conflict == 0 and prof.suspect == 0):
            ledger.drop_field(entity_type, rule.column)
            ledger.add(Defect(
                code="FIELD_NEVER_POPULATED", entity_type=entity_type, entity_key="",
                evidence=Evidence(source=source, column=rule.column),
                owner=Owner(name=PLATFORM_OWNER, role=PLATFORM_ROLE),
                note=(f"هیچ‌کدام از {prof.entities:,} {entity_type} مقدار ندارند. "
                      "قبل از ارجاع به کارشناس، نگاشت سورس بررسی شود."),
            ))

        profiles.append(prof)

    return ProfileResult(entity_type, entities, profiles, ledger, dict(states))


__all__ = [
    "TEXT", "NUMBER", "DATE", "CURRENCY", "KEY",
    "FieldRule", "FieldProfile", "ProfileResult", "profile_frame",
]
