# -*- coding: utf-8 -*-
"""Smallest next fix — what to do, who does it, and what it unlocks.

A defect list is not a plan. Handing an expert four thousand defects produces
nothing; handing them *"fill these twelve cells and twelve cases worth 4.2M EUR
become decision-grade"* produces twelve filled cells. This module does that
translation.

The ranking is deliberately built on **cases unlocked alone** — cases whose only
remaining blocker is this one group of cells. A fix that leaves the case blocked
by something else unlocks nothing today and must not be advertised as if it did;
promising value that does not arrive is how a data programme loses its audience
after the first sprint.
"""
from __future__ import annotations

__contract__ = 1

from collections import defaultdict
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Sequence, Tuple

import pandas as pd

from ..core.numeric_parse import parse_decimal
from . import codes as C
from .fitness import DecisionContract, _entity_first
from .profiling import ProfileResult
from .verdict import Defect, DefectLedger, UNKNOWN_OWNER


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


@dataclass
class FixOpportunity:
    """One group of cells one person can fix, and what it buys."""
    owner: str
    role: str
    dept: str
    field: str
    code: str
    decisions: List[str] = dc_field(default_factory=list)
    #: Cases touched / unlocked, as *sets of keys*. A case blocked in two
    #: decisions is still one case and one cell to type; counting per
    #: (decision, case) pair would inflate both the promise and the workload.
    _touched: set = dc_field(default_factory=set)
    _unlocked: set = dc_field(default_factory=set)
    _valued: Dict[str, Dict[str, float]] = dc_field(default_factory=dict)

    @property
    def cells(self) -> int:
        """One source cell per case — that is the real typing effort."""
        return len(self._touched)

    @property
    def entities_unlocked(self) -> int:
        return len(self._unlocked)

    @property
    def entities_touched(self) -> int:
        return len(self._touched)

    @property
    def sample_keys(self) -> List[str]:
        return sorted(self._unlocked or self._touched)

    @property
    def value_unlocked(self) -> Dict[str, float]:
        """currency -> value that becomes decision-grade, each case counted once."""
        out: Dict[str, float] = {}
        for per_currency in self._valued.values():
            for cur, val in per_currency.items():
                out[cur] = out.get(cur, 0.0) + val
        return out

    @property
    def spec(self) -> C.DefectCode:
        return C.get(self.code)

    @property
    def efficiency(self) -> float:
        """Cases unlocked per cell typed — the cheapest wins go first."""
        return self.entities_unlocked / self.cells if self.cells else 0.0

    @property
    def role_fa(self) -> str:
        return role_fa(self.role)

    @property
    def value_fa(self) -> str:
        # A zero balance is a real fact but adds nothing to "what this unlocks";
        # printing "0 AED" next to a million EUR only dilutes the message.
        return " | ".join(f"{v:,.0f} {cur}" for cur, v in sorted(self.value_unlocked.items())
                          if cur and cur != "—" and abs(v) >= 0.005)

    def headline_fa(self) -> str:
        """The single sentence that goes to the owner."""
        what = self.spec.action_fa
        head = f"{self.cells:,} سلول «{self.field}» — {what}"
        if self.entities_unlocked:
            tail = f"با این کار {self.entities_unlocked:,} پرونده قابل تصمیم می‌شود"
            value = self.value_fa
            if value:
                tail += f" ({value})"
            return f"{head} ← {tail}."
        if self.entities_touched:
            return (f"{head} ← {self.entities_touched:,} پرونده را جلو می‌برد، "
                    "ولی برای قابل‌تصمیم‌شدن، ایراد دیگری هم باید رفع شود.")
        return head + "."

    def row(self) -> Dict[str, Any]:
        return {
            "مالک": self.owner,
            "نقش": self.role_fa,
            "اداره": self.dept,
            "فیلد": self.field,
            "ایراد": self.spec.title_fa,
            "نوع اقدام": self.spec.fix_type_fa,
            "تعداد سلول": self.cells,
            "پرونده آزادشده": self.entities_unlocked,
            "پرونده متأثر": self.entities_touched,
            "ارزش آزادشده": self.value_fa or "—",
            "تصمیم‌های متأثر": " · ".join(self.decisions) or "—",
            "نمونه کلید": " · ".join(self.sample_keys[:3]) or "—",
            "اقدام پیشنهادی": self.headline_fa(),
        }


def _blockers(contract: DecisionContract, profile: ProfileResult) -> Dict[str, List[str]]:
    """entity key -> required fields that are not OK for this decision."""
    out: Dict[str, List[str]] = {}
    for key, states in profile.states.items():
        bad = [f for f in contract.required if states.get(f, C.MISSING) != C.OK]
        if bad:
            out[key] = bad
    return out


def _defect_index(ledger: DefectLedger) -> Dict[Tuple[str, str], Defect]:
    """(entity key, field) -> defect, for owner and reason lookup."""
    return {(d.entity_key, d.field_name): d for d in ledger if d.entity_key}


def rank_opportunities(
    contracts: Sequence[DecisionContract],
    profile: ProfileResult,
    df: pd.DataFrame,
    key_column: str,
    *,
    limit: int = 0,
) -> List[FixOpportunity]:
    """Rank fixes by what they actually unlock, cheapest first."""
    index = _defect_index(profile.ledger)
    groups: Dict[Tuple[str, str, str], FixOpportunity] = {}

    for contract in contracts:
        if contract.entity_type != profile.entity_type:
            continue
        amounts = (_entity_first(df, key_column, contract.amount_field)
                   if contract.amount_field else {})
        currencies = (_entity_first(df, key_column, contract.currency_field)
                      if contract.currency_field else {})

        for key, bad_fields in _blockers(contract, profile).items():
            alone = len(bad_fields) == 1
            for fld in bad_fields:
                defect = index.get((key, fld))
                owner = defect.owner if defect else None
                code = defect.code if defect else "VALUE_MISSING"
                gkey = (owner.name if owner else UNKNOWN_OWNER, fld, code)

                opp = groups.get(gkey)
                if opp is None:
                    opp = FixOpportunity(
                        owner=owner.name if owner else UNKNOWN_OWNER,
                        role=owner.role if owner else "",
                        dept=owner.dept if owner else "",
                        field=fld, code=code,
                    )
                    groups[gkey] = opp

                if contract.title_fa not in opp.decisions:
                    opp.decisions.append(contract.title_fa)
                opp._touched.add(key)
                if alone:
                    opp._unlocked.add(key)
                    # Value is recorded per case, so a case unlocked for two
                    # decisions contributes its amount once, not twice.
                    if key not in opp._valued and amounts:
                        amount = parse_decimal(amounts.get(key), strict=True)
                        if amount is not None:
                            cur = str(currencies.get(key, "")).strip().upper() or "—"
                            opp._valued[key] = {cur: float(amount)}

    ranked = sorted(
        groups.values(),
        key=lambda o: (-o.entities_unlocked, -o.efficiency, o.cells, o.field),
    )
    return ranked[:limit] if limit else ranked


def opportunities_frame(opportunities: Sequence[FixOpportunity]) -> pd.DataFrame:
    cols = list(FixOpportunity("", "", "", "", "VALUE_MISSING").row().keys())
    if not opportunities:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame([o.row() for o in opportunities], columns=cols)


@dataclass
class OwnerScorecard:
    """What one owner is carrying, framed as work rather than blame."""
    owner: str
    role: str = ""
    dept: str = ""
    defects: int = 0
    cases: int = 0
    entities_unlocked: int = 0
    data_entry_cells: int = 0
    investigation_cells: int = 0
    top_actions: List[str] = dc_field(default_factory=list)

    def row(self) -> Dict[str, Any]:
        return {
            "مالک": self.owner,
            "نقش": self.role,
            "اداره": self.dept,
            "ایراد": self.defects,
            "پرونده درگیر": self.cases,
            "پرونده قابل آزادسازی": self.entities_unlocked,
            "سلول برای تکمیل": self.data_entry_cells,
            "مورد برای بررسی": self.investigation_cells,
            "مهم‌ترین اقدام": self.top_actions[0] if self.top_actions else "—",
        }


def owner_scorecards(opportunities: Sequence[FixOpportunity],
                     ledger: DefectLedger) -> List[OwnerScorecard]:
    """Per-owner view, ordered by what they can unlock — not by who is worst.

    Ordering by unlockable value rather than by defect count is deliberate: the
    list reads as an opportunity queue, not a naughty step. Owners who see
    themselves at the top of a blame table stop reporting problems.
    """
    cards: Dict[str, OwnerScorecard] = {}
    cases: Dict[str, set] = defaultdict(set)
    roles: Dict[str, set] = defaultdict(set)

    for d in ledger:
        card = cards.setdefault(d.owner.name, OwnerScorecard(
            owner=d.owner.name, role=d.owner.role, dept=d.owner.dept))
        card.defects += 1
        if d.owner.role:
            roles[d.owner.name].add(role_fa(d.owner.role))
        if d.entity_key:
            cases[d.owner.name].add(d.entity_key)
        if d.spec.fix_type == C.DATA_ENTRY:
            card.data_entry_cells += 1
        elif d.spec.fix_type == C.INVESTIGATION:
            card.investigation_cells += 1

    for opp in opportunities:
        card = cards.setdefault(opp.owner, OwnerScorecard(
            owner=opp.owner, role=opp.role, dept=opp.dept))
        card.entities_unlocked += opp.entities_unlocked
        if opp.entities_unlocked and len(card.top_actions) < 3:
            card.top_actions.append(opp.headline_fa())

    for name, keys in cases.items():
        if name in cards:
            cards[name].cases = len(keys)
    # One person can wear several hats; showing only the last one seen is a lie
    # the owner will notice immediately and stop trusting the page for.
    for name, seen in roles.items():
        if name in cards:
            cards[name].role = " · ".join(sorted(seen))

    return sorted(cards.values(), key=lambda c: (-c.entities_unlocked, -c.defects, c.owner))


def scorecards_frame(cards: Sequence[OwnerScorecard]) -> pd.DataFrame:
    cols = list(OwnerScorecard("").row().keys())
    if not cards:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame([c.row() for c in cards], columns=cols)


def owner_worklist(ledger: DefectLedger, owner: str) -> pd.DataFrame:
    """Every cell one owner must touch, with the evidence to find it."""
    frame = ledger.frame()
    if frame.empty:
        return frame
    return frame.loc[frame["مالک"] == owner].reset_index(drop=True)


__all__ = [
    "FixOpportunity", "rank_opportunities", "opportunities_frame",
    "OwnerScorecard", "owner_scorecards", "scorecards_frame", "owner_worklist",
]
