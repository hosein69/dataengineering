# -*- coding: utf-8 -*-
"""Decision gates — fitness for purpose, graded per decision.

The whole strategy turns on one idea: **a grade belongs to the pair (decision,
record), not to the record.** A case whose clearance date is blank is perfectly
trustworthy for "where is this shipment?" and untrustworthy for "what penalty do
we owe?". Grading the record once, globally, forces a choice between deleting
usable evidence and letting a wrong number reach a decision. Grading per
decision avoids both.

Three grades, and what each one licenses:

``DECISION_GRADE``   act on the number — pay, block, commit, tell an outside party.
``DIRECTIONAL``      use the direction — prioritise, spot a bottleneck, watch a trend.
``NOT_USABLE``       look at it with its reason and owner; it enters no total.

Additive metrics (a sum) are held to a stricter rule than distributional ones (a
count, a ranking, a trend): a total with a missing part is simply wrong, while a
ranking built on 94% of the cases is usually still the right ranking. So an
additive metric is never green while any in-scope case is unknown — instead it
reports the known part and the unknown count side by side, which is the honest
answer and, not coincidentally, the one that makes the gap someone's problem.
"""
from __future__ import annotations

__contract__ = 1

from collections import defaultdict
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Sequence, Tuple

import pandas as pd

from ..core.numeric_parse import parse_decimal
from ..core.text import clean_key, is_empty_val
from . import codes as C
from .profiling import ProfileResult

# ── aggregation shape ───────────────────────────────────────────────────────
ADDITIVE = "ADDITIVE"              # a sum: one unknown part makes the total wrong
DISTRIBUTIONAL = "DISTRIBUTIONAL"  # a count / ranking / trend: partial is usable

# ── grades ──────────────────────────────────────────────────────────────────
DECISION_GRADE = "DECISION_GRADE"
DIRECTIONAL = "DIRECTIONAL"
NOT_USABLE = "NOT_USABLE"

GRADE_FA: Dict[str, str] = {
    DECISION_GRADE: "قابل تصمیم",
    DIRECTIONAL: "جهت‌نما",
    NOT_USABLE: "غیرقابل استناد",
}
GRADE_TONE: Dict[str, str] = {
    DECISION_GRADE: "good",
    DIRECTIONAL: "warning",
    NOT_USABLE: "critical",
}
GRADE_RANK: Dict[str, int] = {NOT_USABLE: 0, DIRECTIONAL: 1, DECISION_GRADE: 2}

#: What each grade licenses, shown to the user next to the number.
GRADE_LICENCE_FA: Dict[str, str] = {
    DECISION_GRADE: "مجاز برای اقدام رسمی: پرداخت، توقف، تعهد، مکاتبه بیرونی.",
    DIRECTIONAL: "فقط برای اولویت‌بندی و روند. برای رقم رسمی و مکاتبه بیرونی استناد نکنید.",
    NOT_USABLE: "در هیچ جمعی وارد نمی‌شود. ابتدا ایرادهای فهرست‌شده باید رفع شوند.",
}


@dataclass(frozen=True)
class DecisionContract:
    """What one decision needs from the data before it may be acted on."""
    id: str
    title_fa: str
    #: The question a manager actually asks. Shown as the panel heading.
    question_fa: str
    entity_type: str
    #: Fields that must be OK for a case to be decision-ready.
    required: Tuple[str, ...]
    aggregation: str = DISTRIBUTIONAL
    #: Optional: the money at stake, so the gap can be quantified.
    amount_field: str = ""
    currency_field: str = ""
    #: Coverage (% of in-scope cases that are ready) needed for each grade.
    #: The additive rule overrides ``decision_floor``: it demands zero unknowns.
    decision_floor: float = 100.0
    directional_floor: float = 80.0
    note_fa: str = ""

    @property
    def is_additive(self) -> bool:
        return self.aggregation == ADDITIVE


@dataclass
class FitnessVerdict:
    """The grade of one decision on one published run."""
    contract: DecisionContract
    entities: int = 0
    ready: int = 0
    missing_required: int = 0
    conflicted: int = 0
    #: currency -> total over decision-ready cases only.
    known_total: Dict[str, float] = dc_field(default_factory=dict)
    #: currency -> value sitting in cases that are *not* ready.
    at_risk: Dict[str, float] = dc_field(default_factory=dict)
    #: Cases whose amount itself is unknown — cannot be placed in either bucket.
    unquantified: int = 0
    #: (field, cases blocked) worst first.
    blocking_fields: List[Tuple[str, int]] = dc_field(default_factory=list)

    @property
    def coverage_pct(self) -> float:
        return round(100.0 * self.ready / self.entities, 1) if self.entities else 0.0

    @property
    def grade(self) -> str:
        c = self.contract
        if not self.entities:
            return NOT_USABLE
        # Fail-closed on contradiction: a conflicting value is a *wrong* number,
        # not merely an absent one, so it can never be decision-grade.
        if self.conflicted:
            return DIRECTIONAL if self.coverage_pct >= c.directional_floor else NOT_USABLE
        if c.is_additive:
            if self.ready == self.entities:
                return DECISION_GRADE
            return DIRECTIONAL if self.coverage_pct >= c.directional_floor else NOT_USABLE
        if self.coverage_pct >= c.decision_floor:
            return DECISION_GRADE
        if self.coverage_pct >= c.directional_floor:
            return DIRECTIONAL
        return NOT_USABLE

    @property
    def grade_fa(self) -> str:
        return GRADE_FA[self.grade]

    @property
    def may_act(self) -> bool:
        return self.grade == DECISION_GRADE

    def total_display(self) -> str:
        """The known total, per currency, with the unknown part stated aloud.

        Never a bare number: a total that hides its unknown part is the exact
        failure this layer exists to prevent.
        """
        if not self.known_total:
            base = "—"
        else:
            base = " | ".join(f"{v:,.2f} {cur}" for cur, v in sorted(self.known_total.items()))
        gap = self.entities - self.ready
        if gap:
            base += f" · {gap:,} پرونده نامعلوم خارج از جمع"
        return base

    def reasons_fa(self) -> List[str]:
        out: List[str] = []
        if self.conflicted:
            out.append(f"{self.conflicted:,} پرونده مقدار متعارض دارد (دو منبع دو عدد می‌گویند).")
        if self.missing_required:
            out.append(f"{self.missing_required:,} پرونده شاهد کلیدی ناقص دارد.")
        for fld, n in self.blocking_fields[:3]:
            out.append(f"«{fld}» در {n:,} پرونده قابل استفاده نیست.")
        if self.unquantified:
            out.append(f"{self.unquantified:,} پرونده مبلغ نامعلوم دارد و در هیچ جمعی نیامده.")
        return out

    def row(self) -> Dict[str, Any]:
        return {
            "شناسه": self.contract.id,
            "تصمیم": self.contract.title_fa,
            "پرسش": self.contract.question_fa,
            "درجه": self.grade_fa,
            "پوشش (٪)": self.coverage_pct,
            "پرونده آماده": self.ready,
            "کل پرونده": self.entities,
            "عدد قابل استناد": self.total_display(),
            "ارزش در معرض": " | ".join(
                f"{v:,.2f} {cur}" for cur, v in sorted(self.at_risk.items())) or "—",
            "علت": " ؛ ".join(self.reasons_fa()) or "—",
            "مجاز برای اقدام": "بله" if self.may_act else "خیر",
            "_grade": self.grade,
            "_tone": GRADE_TONE[self.grade],
        }


def _entity_first(df: pd.DataFrame, key_column: str, column: str) -> Dict[str, Any]:
    """First non-empty value of ``column`` per entity key.

    Fan-out repeats a registration-grain value across every bill-of-lading row;
    taking the first non-empty one per key is the de-fan-out that keeps a single
    missing cell from being counted forty times.
    """
    if column not in df.columns:
        return {}
    out: Dict[str, Any] = {}
    for key, value in zip(df[key_column], df[column]):
        k = clean_key(key) if not is_empty_val(key) else ""
        if not k or k in out:
            continue
        if not is_empty_val(value, treat_zero_as_empty=False):
            out[k] = value
    return out


def evaluate(contract: DecisionContract, profile: ProfileResult,
             df: pd.DataFrame, key_column: str) -> FitnessVerdict:
    """Grade one decision against a profiled frame."""
    verdict = FitnessVerdict(contract=contract)
    if df.empty or key_column not in df.columns or not profile.states:
        return verdict

    amounts = _entity_first(df, key_column, contract.amount_field) if contract.amount_field else {}
    currencies = _entity_first(df, key_column, contract.currency_field) if contract.currency_field else {}

    blocking: Dict[str, int] = defaultdict(int)
    known: Dict[str, float] = defaultdict(float)
    at_risk: Dict[str, float] = defaultdict(float)

    for key, field_states in profile.states.items():
        verdict.entities += 1
        states = [field_states.get(f, C.MISSING) for f in contract.required]
        worst = C.worst_state(states)

        for fld, st in zip(contract.required, states):
            if st != C.OK:
                blocking[fld] += 1

        amount = parse_decimal(amounts.get(key), strict=True) if contract.amount_field else None
        cur = str(currencies.get(key, "")).strip().upper() or "—"

        if worst == C.OK:
            verdict.ready += 1
            if contract.amount_field:
                if amount is None:
                    verdict.unquantified += 1
                else:
                    known[cur] += float(amount)
            continue

        if worst == C.CONFLICT:
            verdict.conflicted += 1
        else:
            verdict.missing_required += 1
        if contract.amount_field:
            if amount is None:
                verdict.unquantified += 1
            else:
                at_risk[cur] += float(amount)

    verdict.known_total = dict(known)
    verdict.at_risk = dict(at_risk)
    verdict.blocking_fields = sorted(blocking.items(), key=lambda kv: -kv[1])
    return verdict


def evaluate_all(contracts: Sequence[DecisionContract], profile: ProfileResult,
                 df: pd.DataFrame, key_column: str) -> List[FitnessVerdict]:
    return [evaluate(c, profile, df, key_column) for c in contracts
            if c.entity_type == profile.entity_type]


def verdicts_frame(verdicts: Sequence[FitnessVerdict]) -> pd.DataFrame:
    cols = list(FitnessVerdict(
        contract=DecisionContract("", "", "", "", ())).row().keys())
    if not verdicts:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame([v.row() for v in verdicts], columns=cols)


__all__ = [
    "ADDITIVE", "DISTRIBUTIONAL",
    "DECISION_GRADE", "DIRECTIONAL", "NOT_USABLE",
    "GRADE_FA", "GRADE_TONE", "GRADE_RANK", "GRADE_LICENCE_FA",
    "DecisionContract", "FitnessVerdict", "evaluate", "evaluate_all", "verdicts_frame",
]
