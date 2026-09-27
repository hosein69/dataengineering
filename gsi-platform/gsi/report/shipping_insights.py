# -*- coding: utf-8 -*-
"""Evidence-led shipment view at BL grain; no inferred owner or SLA verdict."""
from __future__ import annotations

from datetime import date

import pandas as pd

from ..core.jalali import CalendarEngine

DATE_FIELDS = {
    "ARRIVAL_DATE": "ورود", "DISCHARGE_DATE": "تخلیه",
    "DO_DATE": "دریافت ترخیصیه", "COT_DATE": "کوتاژ",
    "FULL_CLEAR_DATE": "ترخیص کامل",
}
CONFLICT_FIELDS = (*DATE_FIELDS, "TRANSPORT_MODE", "BL_VESSEL", "BL_VOYAGE_NO")
OUTPUT_COLUMNS = [
    "بارنامه", "سفارش‌ها", "روش حمل", "کشتی", "شماره سفر", "مبنای شاهد حرکت",
    "ورود", "تخلیه", "دریافت ترخیصیه", "کوتاژ", "ترخیص کامل",
    "ورود تا دریافت ترخیصیه (روز)", "تخلیه تا دریافت ترخیصیه (روز)",
    "تخلیه تا کوتاژ (روز)", "روز سپری‌شده پس از تخلیه (بدون ترخیص کامل)",
    "اقلام بحرانی یکتا", "شمار ردیف منبع", "مغایرت شواهد", "دادهٔ لازم", "اقدام پیشنهادی",
]


def _present(value) -> bool:
    if value is None:
        return False
    try:
        if bool(pd.isna(value)):
            return False
    except (TypeError, ValueError):
        pass
    return str(value).strip() not in {"", "nan", "None", "NaT", "—"}


def _values(part: pd.DataFrame, column: str, *, dates: bool = False) -> tuple[list, bool]:
    if column not in part:
        return [], False
    raw = [v for v in part[column] if _present(v)]
    if dates:
        parsed = []
        for v in raw:
            try:
                parsed.append(CalendarEngine.parse(v))
            except (TypeError, ValueError):
                parsed.append(None)
        values = sorted(set(v for v in parsed if v is not None))
        return values, len(values) > 1 or len(values) < len(raw) and any(v is None for v in parsed)
    values = sorted(set(str(v).strip() for v in raw))
    return values, len(values) > 1


def _one(part: pd.DataFrame, column: str, *, dates: bool = False):
    values, conflict = _values(part, column, dates=dates)
    return (values[0] if len(values) == 1 and not conflict else None), conflict


def _gap(start: date | None, end: date | None) -> int | None:
    # Negative durations may be valid (DO before arrival); label them for review.
    return (end - start).days if start and end else None


def build_shipping_insights(frame: pd.DataFrame, as_of: date | str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return BL dossiers and field coverage from the *scoped* published mart.

    Multiple order/material rows per BL contribute one dossier. Conflicting
    evidence is retained as a gap, never silently reduced to the first row.
    Unknown free time, route and cause are not inferred from elapsed days.
    """
    empty = pd.DataFrame(columns=OUTPUT_COLUMNS)
    if frame is None or frame.empty or "CANONICAL_BL" not in frame:
        return empty, pd.DataFrame(columns=["شاهد", "بارنامه واجدشرایط", "دارای شاهد", "متعارض", "پوشش (%)"])
    today = CalendarEngine.parse(as_of)
    if today is None:
        raise ValueError("تاریخ مرجع معتبر برای تحلیل حمل لازم است")
    work = frame.loc[frame["CANONICAL_BL"].map(_present)].copy()
    if work.empty:
        return empty, pd.DataFrame(columns=["شاهد", "بارنامه واجدشرایط", "دارای شاهد", "متعارض", "پوشش (%)"])
    work["_BL_KEY"] = work["CANONICAL_BL"].astype(str).str.strip()
    records = []
    for bl, part in work.groupby("_BL_KEY", sort=True):
        dates, conflicts = {}, []
        for field, label in DATE_FIELDS.items():
            value, conflict = _one(part, field, dates=True)
            dates[field] = value
            if conflict:
                conflicts.append(label)
        mode, conflict = _one(part, "TRANSPORT_MODE")
        if conflict:
            conflicts.append("روش حمل")
        vessel, conflict = _one(part, "BL_VESSEL")
        if conflict:
            conflicts.append("کشتی")
        voyage, conflict = _one(part, "BL_VOYAGE_NO")
        if conflict:
            conflicts.append("شماره سفر")
        movement_basis, movement_conflict = _one(part, "SHIPPED_EVIDENCE_BASIS")
        if movement_conflict:
            conflicts.append("مبنای شاهد حرکت")
        orders, _ = _values(part, "CANONICAL_ORDER")
        done_without_date = ("CL_CLEAR_DONE_NO_DATE" in part and
                             part["CL_CLEAR_DONE_NO_DATE"].eq(True).fillna(False).any())
        critical = 0
        if "KEY_MATERIAL" in part and "کد طبقه بحرانی" in part:
            critical = int(part.loc[part["کد طبقه بحرانی"].isin(("STOCKOUT", "CRITICAL")), "KEY_MATERIAL"]
                           .dropna().astype(str).replace("", pd.NA).dropna().nunique())
        arrival, discharge, do, cot, clear = (dates[c] for c in DATE_FIELDS)
        missing = [label for c, label in DATE_FIELDS.items() if dates[c] is None and label not in conflicts]
        if not mode:
            missing.append("روش حمل")
        if done_without_date and not clear:
            missing.append("شاهد ترخیص کامل بدون تاریخ")
        actions = []
        if conflicts:
            actions.append("تطبیق شاهدهای متعارض با اصل سند")
        if not discharge and not arrival:
            actions.append("دریافت شاهد ورود/تخلیه از منبع حمل")
        elif not do:
            actions.append("استعلام وضعیت دریافت ترخیصیه و تاریخ درخواست/پرداخت")
        if discharge and not clear and not done_without_date:
            actions.append("استعلام وضعیت ترخیص و فری‌تایم قراردادی؛ هزینه قابل استنتاج نیست")
        if not actions:
            actions.append("بررسی خط زمانی؛ علت و مسئولیت از زمان خام استنتاج نمی‌شود")
        age = ((today - discharge).days if discharge and not clear and not done_without_date
               and today >= discharge else None)
        records.append({
            "بارنامه": bl, "سفارش‌ها": " | ".join(orders), "روش حمل": mode or "نامشخص",
            "کشتی": vessel or "", "شماره سفر": voyage or "",
            "مبنای شاهد حرکت": movement_basis or "",
            **{label: dates[c].isoformat() if dates[c] else "" for c, label in DATE_FIELDS.items()},
            "ورود تا دریافت ترخیصیه (روز)": _gap(arrival, do),
            "تخلیه تا دریافت ترخیصیه (روز)": _gap(discharge, do),
            "تخلیه تا کوتاژ (روز)": _gap(discharge, cot),
            "روز سپری‌شده پس از تخلیه (بدون ترخیص کامل)": age,
            "اقلام بحرانی یکتا": critical, "شمار ردیف منبع": len(part),
            "مغایرت شواهد": "، ".join(conflicts), "دادهٔ لازم": "، ".join(missing),
            "اقدام پیشنهادی": "؛ ".join(actions),
        })
    dossiers = pd.DataFrame(records, columns=OUTPUT_COLUMNS)
    coverage = []
    n = len(dossiers)
    for label in (*DATE_FIELDS.values(), "روش حمل"):
        observed = int(dossiers[label].map(_present).sum()) if label in dossiers else 0
        conflict = int(dossiers["مغایرت شواهد"].str.split("، ").map(lambda a: label in a).sum())
        if label == "روش حمل":
            observed = int(dossiers[label].ne("نامشخص").sum())
        coverage.append({"شاهد": label, "بارنامه واجدشرایط": n, "دارای شاهد": observed,
                         "متعارض": conflict, "پوشش (%)": round(100 * observed / n, 1)})
    return dossiers, pd.DataFrame(coverage)
