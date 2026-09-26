# -*- coding: utf-8 -*-
"""Defect instances and the ledger that holds them.

Two rules shape this module:

**Nothing is deleted.** A defect is a *pointer* to a cell, never a replacement
for it. The row stays in the mart exactly as it was; the ledger records that one
of its cells cannot be trusted, and for which reason.

**No defect without evidence.** Every instance carries the physical lineage of
the cell it accuses — source, file, sheet, row, column, and the raw value as it
appears. A defect an owner cannot verify is a defect they will not fix, and an
accusation the system cannot back up costs it the trust the whole layer is for.
"""
from __future__ import annotations

#: 2 — Owner carries the escalation path (manager/vice), the ledger remembers
#: mapping gaps, and role_fa() lives here so the ledger itself translates.
__contract__ = 2

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import pandas as pd

from . import codes as C

#: Lineage column names GSI adapters and the merge layer produce, best first.
#: The prefixed forms appear after ``safe_merge`` namespaces a right-hand side.
_FILE_COLS = ("_SOURCE_FILE", "_SOURCE_FILE_ID", "SAP_SOURCE_FILE", "SAP_SOURCE_FILE_ID")
_SHEET_COLS = ("_SOURCE_SHEET", "SAP_SOURCE_SHEET")
_ROW_COLS = ("_SOURCE_ROW", "SAP_SOURCE_ROW")

#: Owner columns, most specific first. ``CURRENT_OWNER`` is the person the case
#: sits with right now, which is who should act; the role-specific columns are
#: the fallback when the stage that resolves the current owner did not run.
_OWNER_NAME_COLS = ("CANONICAL_EXPERT", "PART_OWNER", "CURRENT_OWNER", "NEXT_ACTION_OWNER")
#: ``PROCESS_CURRENT_OWNER`` holds a *stage code* (``TREASURY``), not a person —
#: it describes the role a case sits with, so it belongs here, not in the name.
_OWNER_ROLE_COLS = ("EXPERT_ROLE", "PROCESS_CURRENT_OWNER")
_OWNER_DEPT_COLS = ("ORG_DEPT", "ORG_UNIT")
#: The escalation path above the expert. A worklist item that stalls has to be
#: escalatable without anyone opening the HR chart, and a manager has to be able
#: to see their own unit's backlog rather than only their own name.
_OWNER_MANAGER_COLS = ("ORG_MANAGER", "ORG_HEAD")
_OWNER_VICE_COLS = ("ORG_VICE",)

UNKNOWN_OWNER = "نامشخص"

#: Owner of a source-contract defect. A field the pipeline never reads cannot
#: be fixed by any business expert, so routing it to one is worse than not
#: routing it at all: the expert opens the source, sees the cell already
#: filled, and stops believing the rest of the list.
PLATFORM_OWNER = "تیم داده — نگاشت سورس"
PLATFORM_ROLE = "مالک قرارداد سورس"


def _text(value: Any) -> str:
    """Display text for evidence; never raises, never invents."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _first_present(row: Mapping[str, Any], names: Sequence[str]) -> str:
    for n in names:
        v = _text(row.get(n))
        if v:
            return v
    return ""


@dataclass(frozen=True)
class Evidence:
    """Where the accused cell physically lives."""
    source: str = ""
    file: str = ""
    sheet: str = ""
    row: str = ""
    column: str = ""
    raw_value: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, Any], *, column: str, source: str = "") -> "Evidence":
        return cls(
            source=source,
            file=_first_present(row, _FILE_COLS),
            sheet=_first_present(row, _SHEET_COLS),
            row=_first_present(row, _ROW_COLS),
            column=column,
            raw_value=_text(row.get(column)),
        )

    @property
    def locator_fa(self) -> str:
        """One line an owner can follow to the cell with their own eyes."""
        parts = [p for p in (self.file, self.sheet) if p]
        if self.row:
            parts.append(f"ردیف {self.row}")
        if self.column:
            parts.append(f"ستون «{self.column}»")
        return " · ".join(parts) or (self.source or "—")


#: Stage-unit codes that ``PROCESS_CURRENT_OWNER`` carries, in Persian.
#: Source of truth for the codes: ``gsi/resolve/process_evidence.STAGES``.
UNIT_FA: Dict[str, str] = {
    "PLANNING": "برنامه‌ریزی",
    "COMMERCIAL": "بازرگانی",
    "REGISTRATION": "ثبت سفارش",
    "FX_ALLOCATION": "تخصیص ارز",
    "FX_COMMITMENT": "تعهد ارزی",
    "TREASURY": "خزانه‌داری",
    "LOGISTICS": "لجستیک",
    "CUSTOMS": "گمرک و ترخیص",
    "CREDIT": "اعتبارات",
}


def role_fa(role: str) -> str:
    """Persian label for a role, whether it arrives as a label or a stage code."""
    return UNIT_FA.get(str(role).strip().upper(), role)


@dataclass(frozen=True)
class Owner:
    """Who can close the defect."""
    name: str = UNKNOWN_OWNER
    role: str = ""
    dept: str = ""
    manager: str = ""
    vice: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, Any], *, prefer: str = "",
                 role_label: str = "") -> "Owner":
        """Resolve who should fix a cell.

        ``prefer`` is the role-specific expert column for the field in question
        (``EXPERT_SETTLEMENT`` for a commitment balance, ``EXPERT_CLEARANCE``
        for a customs date). Routing a settlement defect to the clearance expert
        because they happen to be the case's generic expert wastes both their
        time, so the field's own role wins when the source supplies it.
        """
        name = _text(row.get(prefer)) if prefer else ""
        return cls(
            name=name or _first_present(row, _OWNER_NAME_COLS) or UNKNOWN_OWNER,
            role=role_label or _first_present(row, _OWNER_ROLE_COLS),
            dept=_first_present(row, _OWNER_DEPT_COLS),
            manager=_first_present(row, _OWNER_MANAGER_COLS),
            vice=_first_present(row, _OWNER_VICE_COLS),
        )

    @property
    def known(self) -> bool:
        return self.name != UNKNOWN_OWNER and bool(self.name)


@dataclass(frozen=True)
class Defect:
    """One untrustworthy cell, with its reason, evidence and owner."""
    code: str
    entity_type: str
    entity_key: str
    evidence: Evidence
    owner: Owner = field(default_factory=Owner)
    note: str = ""

    def __post_init__(self) -> None:
        C.get(self.code)          # fail loudly on an unknown code

    @property
    def spec(self) -> C.DefectCode:
        return C.get(self.code)

    @property
    def state(self) -> str:
        return self.spec.state

    @property
    def field_name(self) -> str:
        return self.evidence.column

    def row(self) -> Dict[str, Any]:
        """Flat record for the ledger frame and for the owner's worklist."""
        spec = self.spec
        return {
            "کد ایراد": self.code,
            "عنوان": spec.title_fa,
            "وضعیت": spec.state_fa,
            "بُعد کیفیت": spec.dimension_fa,
            "نوع اقدام": spec.fix_type_fa,
            "اقدام لازم": spec.action_fa,
            "نوع موجودیت": self.entity_type,
            "کلید": self.entity_key,
            "فیلد": self.evidence.column,
            "مقدار فعلی": self.evidence.raw_value,
            "مالک": self.owner.name,
            "نقش": role_fa(self.owner.role),
            "اداره": self.owner.dept,
            "مدیر": self.owner.manager,
            "معاونت": self.owner.vice,
            "شاهد": self.evidence.locator_fa,
            "توضیح": self.note,
            # machine-readable duplicates for grouping and trend
            "_state": spec.state,
            "_dimension": spec.dimension,
            "_fix_type": spec.fix_type,
            "_source": self.evidence.source,
        }


LEDGER_COLUMNS = list(
    Defect(
        code="VALUE_MISSING", entity_type="", entity_key="",
        evidence=Evidence(),
    ).row().keys()
)


class DefectLedger:
    """Append-only collection of defects.

    Deliberately append-only: a defect is removed by *fixing the data and
    re-running*, never by editing the ledger. That is what makes the trend line
    meaningful.
    """

    __slots__ = ("_items", "_mapping_gaps")

    def __init__(self, items: Optional[Iterable[Defect]] = None) -> None:
        self._items: List[Defect] = list(items or ())
        #: (entity type, column) pairs proven to be source-contract gaps.
        self._mapping_gaps: set = set()

    def add(self, defect: Defect) -> None:
        self._items.append(defect)

    def extend(self, defects: Iterable[Defect]) -> None:
        self._items.extend(defects)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    @property
    def items(self) -> List[Defect]:
        return list(self._items)

    def frame(self) -> pd.DataFrame:
        """The ledger as a frame, with stable columns even when empty."""
        if not self._items:
            return pd.DataFrame(columns=LEDGER_COLUMNS)
        return pd.DataFrame([d.row() for d in self._items], columns=LEDGER_COLUMNS)

    def drop_field(self, entity_type: str, column: str) -> int:
        """Remove per-case defects for one field, once it is known to be a
        mapping gap rather than thousands of individual omissions.

        The only removal this ledger permits, and it replaces noise with a
        single truthful finding rather than hiding anything.
        """
        before = len(self._items)
        self._items = [d for d in self._items
                       if not (d.entity_type == entity_type and d.field_name == column)]
        # Remembered, because every other surface rebuilds its view from the
        # field states rather than from this ledger. Without the memory the
        # dropped cells reappear downstream as ordinary data entry — the exact
        # mis-routing this removal exists to prevent.
        self._mapping_gaps.add((entity_type, column))
        return before - len(self._items)

    def note_mapping_gap(self, entity_type: str, column: str) -> None:
        """Carry a known gap into a merged ledger without re-running detection."""
        self._mapping_gaps.add((entity_type, column))

    def mapping_gaps(self, entity_type: str = "") -> set:
        """Fields known to be unread by the pipeline, not unfilled by people."""
        return {c for e, c in self._mapping_gaps
                if not entity_type or e == entity_type}

    def is_mapping_gap(self, entity_type: str, column: str) -> bool:
        return (entity_type, column) in self._mapping_gaps

    def keys_with_defects(self, entity_type: str = "") -> set:
        return {
            d.entity_key for d in self._items
            if d.entity_key and (not entity_type or d.entity_type == entity_type)
        }

    def by_state(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for d in self._items:
            out[d.state] = out.get(d.state, 0) + 1
        return out

    def summary(self) -> Dict[str, Any]:
        by_code: Dict[str, int] = {}
        owners: set = set()
        unowned = 0
        for d in self._items:
            by_code[d.code] = by_code.get(d.code, 0) + 1
            if d.owner.known:
                owners.add(d.owner.name)
            else:
                unowned += 1
        return {
            "defects": len(self._items),
            "by_state": self.by_state(),
            "by_code": dict(sorted(by_code.items(), key=lambda kv: -kv[1])),
            "owners": len(owners),
            "unowned_defects": unowned,
            # Share of defects nobody can be asked to fix. A high number here
            # means the routing is broken, not that the data is fine.
            "routable_pct": round(100.0 * (len(self._items) - unowned) / len(self._items), 1)
            if self._items else 100.0,
        }


__all__ = ["Evidence", "Owner", "Defect", "DefectLedger", "LEDGER_COLUMNS",
           "UNKNOWN_OWNER", "PLATFORM_OWNER", "PLATFORM_ROLE",
           "UNIT_FA", "role_fa"]
