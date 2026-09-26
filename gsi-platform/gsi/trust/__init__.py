# -*- coding: utf-8 -*-
"""GSI data-trust layer — measure the data honestly, gate the decisions, route the fixes.

One call does the whole pass::

    from gsi.trust import assess
    report = assess(published_mart_df, ref_date=date(2026, 8, 31))
    print(report.headline_fa())
    report.frames()["decisions"]     # grade per decision
    report.frames()["next_fixes"]    # what to fix first, and what it unlocks

The layer never modifies the mart. It reads it, and produces a parallel set of
frames describing what can and cannot be trusted in it. Strategy and rationale:
``docs/DATA_STRATEGY_FA.md``.
"""
from __future__ import annotations

#: 2 — frames() adds owners_by_dept/owners_by_manager; scorecards_at().
__contract__ = 2

from dataclasses import dataclass, field as dc_field
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from . import codes, contracts as contract_defs, trend
from .fitness import (ADDITIVE, DECISION_GRADE, DIRECTIONAL, DISTRIBUTIONAL,
                      GRADE_FA, GRADE_LICENCE_FA, GRADE_RANK, GRADE_TONE,
                      NOT_USABLE, DecisionContract, FitnessVerdict,
                      evaluate_all, verdicts_frame)
from .impact import (FixOpportunity, OwnerScorecard, opportunities_frame,
                     owner_scorecards, owner_worklist, rank_opportunities,
                     scorecards_frame)
from .profiling import FieldRule, ProfileResult, profile_frame
from .verdict import Defect, DefectLedger, Evidence, Owner


@dataclass
class TrustReport:
    """Everything the trust layer knows about one published run."""
    ref_date: str = ""
    profiles: Dict[str, ProfileResult] = dc_field(default_factory=dict)
    verdicts: List[FitnessVerdict] = dc_field(default_factory=list)
    opportunities: List[FixOpportunity] = dc_field(default_factory=list)
    scorecards: List[OwnerScorecard] = dc_field(default_factory=list)

    # ── aggregates ──────────────────────────────────────────────────────────
    @property
    def ledger(self) -> DefectLedger:
        merged = DefectLedger()
        for p in self.profiles.values():
            merged.extend(p.ledger.items)
            for column in p.ledger.mapping_gaps():
                merged.note_mapping_gap(p.entity_type, column)
        return merged

    def grade_counts(self) -> Dict[str, int]:
        out = {DECISION_GRADE: 0, DIRECTIONAL: 0, NOT_USABLE: 0}
        for v in self.verdicts:
            out[v.grade] = out.get(v.grade, 0) + 1
        return out

    @property
    def actionable_defects(self) -> int:
        """Defects that block at least one decision today."""
        return sum(o.cells for o in self.opportunities)

    @property
    def unlockable_cases(self) -> int:
        return sum(o.entities_unlocked for o in self.opportunities)

    def headline_fa(self) -> str:
        """One honest sentence for the top of the page."""
        counts = self.grade_counts()
        total = sum(counts.values()) or 1
        green = counts.get(DECISION_GRADE, 0)
        head = (f"{green} از {total} تصمیم قابل استناد است"
                f" · {counts.get(DIRECTIONAL, 0)} جهت‌نما"
                f" · {counts.get(NOT_USABLE, 0)} غیرقابل استناد")
        if self.unlockable_cases:
            head += (f" — با تکمیل {self.actionable_defects:,} سلول، "
                     f"{self.unlockable_cases:,} پرونده آزاد می‌شود")
        return head

    def frames(self) -> Dict[str, pd.DataFrame]:
        fields = [p.fields_frame().assign(**{"موجودیت": contract_defs.ENTITY_FA.get(e, e)})
                  for e, p in self.profiles.items()]
        return {
            "decisions": verdicts_frame(self.verdicts),
            "fields": (pd.concat(fields, ignore_index=True) if fields else pd.DataFrame()),
            "defects": self.ledger.frame(),
            "next_fixes": opportunities_frame(self.opportunities),
            "owners": scorecards_frame(self.scorecards),
            # The same backlog by unit and by manager, so a department head can
            # plan their own queue instead of scanning a list of every person.
            "owners_by_dept": self.scorecards_at("dept"),
            "owners_by_manager": self.scorecards_at("manager"),
        }

    def scorecards_at(self, level: str) -> pd.DataFrame:
        """The backlog rolled up to one organizational level."""
        return scorecards_frame(
            owner_scorecards(self.opportunities, self.ledger, level=level),
            level=level)

    def summary(self) -> Dict[str, Any]:
        """Compact, JSON-safe state — this is what the trend line stores."""
        led = self.ledger.summary()
        return {
            "ref_date": self.ref_date,
            "grades": self.grade_counts(),
            "decisions": {v.contract.id: {
                "grade": v.grade,
                "coverage_pct": v.coverage_pct,
                "ready": v.ready,
                "entities": v.entities,
            } for v in self.verdicts},
            "entities": {e: p.entities for e, p in self.profiles.items()},
            "coverage_by_entity": {
                e: round(sum(f.coverage_pct for f in p.fields) / len(p.fields), 1)
                for e, p in self.profiles.items() if p.fields
            },
            "defects": led["defects"],
            "defects_by_state": led["by_state"],
            "defects_by_code": led["by_code"],
            "routable_pct": led["routable_pct"],
            "actionable_cells": self.actionable_defects,
            "unlockable_cases": self.unlockable_cases,
        }


def assess(
    df: pd.DataFrame,
    *,
    ref_date: Optional[date] = None,
    entity_types: Optional[Sequence[str]] = None,
    contracts: Optional[Sequence[DecisionContract]] = None,
    rules: Optional[Dict[str, Sequence[FieldRule]]] = None,
    top_fixes: int = 0,
) -> TrustReport:
    """Profile, grade and route in one pass over a published mart."""
    entity_types = list(entity_types or contract_defs.entity_types())
    contracts = list(contracts if contracts is not None else contract_defs.CONTRACTS)
    rules = dict(rules or contract_defs.RULES)

    report = TrustReport(ref_date=ref_date.isoformat() if ref_date else "")

    for entity in entity_types:
        key_column = contract_defs.KEY_COLUMN.get(entity)
        entity_rules = rules.get(entity)
        if not key_column or not entity_rules:
            continue
        profile = profile_frame(
            df, list(entity_rules), entity_type=entity,
            key_column=key_column, ref_date=ref_date, source=entity,
            cross_source=contract_defs.cross_source_for(entity),
        )
        report.profiles[entity] = profile

        entity_contracts = [c for c in contracts if c.entity_type == entity]
        report.verdicts.extend(evaluate_all(entity_contracts, profile, df, key_column))
        report.opportunities.extend(
            rank_opportunities(entity_contracts, profile, df, key_column)
        )

    report.opportunities.sort(
        key=lambda o: (-o.entities_unlocked, -o.efficiency, o.cells, o.field))
    if top_fixes:
        report.opportunities = report.opportunities[:top_fixes]
    report.verdicts.sort(key=lambda v: (GRADE_RANK[v.grade], v.contract.id))
    report.scorecards = owner_scorecards(report.opportunities, report.ledger)
    return report


__all__ = [
    "assess", "TrustReport",
    "codes", "contract_defs", "trend",
    "DecisionContract", "FitnessVerdict", "FieldRule", "ProfileResult",
    "Defect", "DefectLedger", "Evidence", "Owner",
    "FixOpportunity", "OwnerScorecard", "owner_worklist",
    "ADDITIVE", "DISTRIBUTIONAL",
    "DECISION_GRADE", "DIRECTIONAL", "NOT_USABLE",
    "GRADE_FA", "GRADE_TONE", "GRADE_RANK", "GRADE_LICENCE_FA",
]
