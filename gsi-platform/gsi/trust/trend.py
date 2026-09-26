# -*- coding: utf-8 -*-
"""Improvement over time — the part that turns a scorecard into a culture.

A single quality score tells an owner they are bad at their job. The same score
next to last week's tells them whether they are winning, which is the only
version anyone acts on twice.

The measure of record here is deliberately the **delta**, not the level. At
point zero the level is poor and that is nobody's personal failing; ranking
people by it produces concealment, not clean data. Ranking by improvement
rewards exactly the behaviour the programme needs and is achievable from any
starting point.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

from .fitness import DECISION_GRADE, DIRECTIONAL, NOT_USABLE

#: Metrics tracked across runs: key -> (Persian label, better direction).
TRACKED: Dict[str, tuple] = {
    "decision_grade": ("تصمیم قابل استناد", +1),
    "defects": ("ایراد باز", -1),
    "unlockable_cases": ("پرونده قابل آزادسازی", -1),
    "routable_pct": ("ایراد دارای مالک (٪)", +1),
    "mean_coverage_pct": ("میانگین پوشش فیلدها (٪)", +1),
}


def _flatten(summary: Dict[str, Any]) -> Dict[str, Any]:
    """One trend row from one stored snapshot."""
    grades = summary.get("grades") or {}
    coverage = summary.get("coverage_by_entity") or {}
    return {
        "ref_date": summary.get("ref_date", ""),
        "decision_grade": int(grades.get(DECISION_GRADE, 0)),
        "directional": int(grades.get(DIRECTIONAL, 0)),
        "not_usable": int(grades.get(NOT_USABLE, 0)),
        "defects": int(summary.get("defects", 0)),
        "unlockable_cases": int(summary.get("unlockable_cases", 0)),
        "actionable_cells": int(summary.get("actionable_cells", 0)),
        "routable_pct": float(summary.get("routable_pct", 0.0)),
        "mean_coverage_pct": round(
            sum(coverage.values()) / len(coverage), 1) if coverage else 0.0,
    }


def load_snapshots(warehouse=None, *, limit: int = 60) -> pd.DataFrame:
    """Trust snapshots across runs, oldest first.

    Returns an empty frame — never raises — when the warehouse has no history
    yet, because "no trend yet" is the normal state on day one and must not
    look like a failure.
    """
    from ..warehouse.store import Warehouse, loads

    wh = warehouse or Warehouse(initialize=False)
    if not wh.path.exists():
        return pd.DataFrame()
    try:
        with wh.read_db() as c:
            rows = c.execute(
                "SELECT at, run_id, payload FROM wh_audit "
                "WHERE kind='trust_snapshot' ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
    except Exception:
        return pd.DataFrame()

    records: List[Dict[str, Any]] = []
    for at, run_id, payload in reversed(rows):
        try:
            summary = loads(payload)
        except Exception:
            continue
        record = {"at": str(at)[:19].replace("T", " "), "run_id": str(run_id or "")[:12]}
        record.update(_flatten(summary))
        records.append(record)
    return pd.DataFrame(records)


@dataclass
class Delta:
    """Change in one metric between two runs."""
    key: str
    label: str
    previous: float
    current: float
    better_direction: int

    @property
    def change(self) -> float:
        return round(self.current - self.previous, 1)

    @property
    def improved(self) -> Optional[bool]:
        if self.change == 0:
            return None
        return (self.change > 0) == (self.better_direction > 0)

    def sentence_fa(self) -> str:
        if self.change == 0:
            return f"{self.label}: بدون تغییر ({self.current:,.0f})"
        arrow = "↑" if self.change > 0 else "↓"
        verdict = "بهبود" if self.improved else "افت"
        return (f"{self.label}: {arrow} {abs(self.change):,.0f} "
                f"({self.previous:,.0f} ← {self.current:,.0f}) — {verdict}")


def compare(history: pd.DataFrame) -> List[Delta]:
    """Deltas between the last two runs; empty when there is no comparison yet."""
    if history is None or len(history) < 2:
        return []
    previous, current = history.iloc[-2], history.iloc[-1]
    out: List[Delta] = []
    for key, (label, direction) in TRACKED.items():
        if key not in history.columns:
            continue
        out.append(Delta(key, label, float(previous[key]), float(current[key]), direction))
    return out


def headline_fa(history: pd.DataFrame) -> str:
    """One sentence about the direction of travel."""
    if history is None or history.empty:
        return "هنوز سابقه‌ای ثبت نشده است؛ این اجرا، نقطه صفر می‌شود."
    if len(history) < 2:
        return ("اولین عکس کیفیت ثبت شد. از اجرای بعدی، بهبود قابل اندازه‌گیری است "
                "— معیار ما «نرخ بهبود» است، نه مقدار مطلق.")
    deltas = compare(history)
    gained = [d for d in deltas if d.improved is True]
    lost = [d for d in deltas if d.improved is False]
    if not gained and not lost:
        return "نسبت به اجرای قبل تغییری ثبت نشد."
    parts = []
    if gained:
        parts.append("بهبود در " + "، ".join(d.label for d in gained))
    if lost:
        parts.append("افت در " + "، ".join(d.label for d in lost))
    return "نسبت به اجرای قبل: " + " · ".join(parts) + "."


def trend_frame(history: pd.DataFrame) -> pd.DataFrame:
    """Persian-labelled history for display."""
    if history is None or history.empty:
        return pd.DataFrame(columns=["اجرا", "تاریخ مرجع", "تصمیم قابل استناد",
                                     "ایراد باز", "پرونده قابل آزادسازی",
                                     "ایراد دارای مالک (٪)", "میانگین پوشش (٪)"])
    return pd.DataFrame({
        "اجرا": history["at"],
        "تاریخ مرجع": history["ref_date"],
        "تصمیم قابل استناد": history["decision_grade"],
        "ایراد باز": history["defects"],
        "پرونده قابل آزادسازی": history["unlockable_cases"],
        "ایراد دارای مالک (٪)": history["routable_pct"],
        "میانگین پوشش (٪)": history["mean_coverage_pct"],
    })


__all__ = ["TRACKED", "Delta", "load_snapshots", "compare", "headline_fa", "trend_frame"]
