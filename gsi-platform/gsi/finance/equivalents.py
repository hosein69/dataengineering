# -*- coding: utf-8 -*-
"""Source-authority preserving FX equivalents.

The corporate sources already carry reported FX rates and EUR/IRR equivalents.
This module makes that evidence usable without silently mixing currencies.

Authority order
---------------
* Purchase totals: source-reported ``FX_EUR_VALUE`` / ``FX_RIAL_VALUE``.
* Commitment native amount: NTSW Release Commitment.
* Commitment EUR/IRR *reference equivalent*: only evidence observed for the
  same REG and same currency is eligible.  No global/cross-case rate is used.
* For IRR only, NTSW Allocation rate is a fallback if no same-case purchase
  equivalent/rate is available.

A commitment equivalent produced here is explicitly a reference valuation,
not a claim that NTSW itself reported an equivalent balance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import math

import pandas as pd

from ..adapters.base import KEY_REG
from ..core.jalali import CalendarEngine
from ..core.text import clean_key, is_empty_val

EPS = 1e-12


def _text(v: Any) -> str:
    return "" if is_empty_val(v, treat_zero_as_empty=False) else str(v).strip()


def _num(v: Any) -> Optional[float]:
    try:
        x = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]
        if pd.isna(x):
            return None
        value = float(x)
        return value if math.isfinite(value) else None
    except Exception:
        return None


def _positive(v: Any) -> Optional[float]:
    x = _num(v)
    return x if x is not None and x > EPS else None


def _currency(v: Any) -> str:
    return _text(v).upper()


def _fmt(v: float) -> str:
    return f"{v:,.2f}"


def _native_display(frame: pd.DataFrame, amount_col: str, currency_col: str) -> str:
    if frame is None or frame.empty or amount_col not in frame.columns or currency_col not in frame.columns:
        return "—"
    z = frame[[amount_col, currency_col]].copy()
    z[amount_col] = pd.to_numeric(z[amount_col], errors="coerce")
    z[currency_col] = z[currency_col].map(_currency)
    z = z[z[amount_col].notna() & z[currency_col].ne("")]
    if z.empty:
        return "—"
    totals = z.groupby(currency_col, sort=True)[amount_col].sum()
    return " | ".join(f"{_fmt(float(v))} {cur}" for cur, v in totals.items())


@dataclass(frozen=True)
class EquivalentResult:
    native_display: str
    single_currency: str
    single_native_amount: Optional[float]
    source_eur_total: Optional[float]
    source_rial_total: Optional[float]
    eur_coverage_pct: float
    rial_coverage_pct: float


@dataclass(frozen=True)
class CreditEquivalentResult:
    source_eur_total: Optional[float]
    source_rial_total: Optional[float]
    status: str
    logical_credit_count: int
    eur_coverage_pct: float = 0.0
    rial_coverage_pct: float = 0.0


def summarize_credit_equivalents(frame: Optional[pd.DataFrame]) -> CreditEquivalentResult:
    """Safely aggregate direct Credit-source EUR/IRR equivalents.

    ``CRD_EUR_AMOUNT`` and ``CRD_RIAL_AMOUNT`` are already common-unit source
    facts.  Repeated snapshots of the same LC must not be double counted, so
    rows are collapsed by ``CRD_LC_NO`` when available.  If one LC carries
    conflicting reported values, the conflicted unit is withheld rather than
    guessed.  Multiple unidentified (blank-LC) non-identical rows are also
    treated as ambiguous.
    """
    if frame is None or frame.empty:
        return CreditEquivalentResult(None, None, "NO_CREDIT_SOURCE", 0, 0.0, 0.0)
    z = frame.copy()
    for c in ("CRD_EUR_AMOUNT", "CRD_RIAL_AMOUNT"):
        if c not in z.columns:
            z[c] = pd.NA
        z[c] = pd.to_numeric(z[c], errors="coerce")
    if "CRD_LC_NO" not in z.columns:
        z["CRD_LC_NO"] = ""
    z["__lc"] = z["CRD_LC_NO"].map(_text)

    groups: list[pd.DataFrame] = []
    identified = z[z["__lc"].ne("")]
    if not identified.empty:
        groups.extend(g.copy() for _, g in identified.groupby("__lc", sort=False))

    unknown = z[z["__lc"].eq("")].copy()
    ambiguous_unknown = False
    if not unknown.empty:
        # Exact duplicate unidentified rows are one observation; distinct rows
        # cannot be proven to be distinct credits, so do not sum them.
        sig_cols = [c for c in ("CRD_EUR_AMOUNT", "CRD_RIAL_AMOUNT", "CRD_CURRENCY",
                                "CRD_PROFORMA_VALUE") if c in unknown.columns]
        u = unknown.drop_duplicates(subset=sig_cols or None)
        if len(u) == 1:
            groups.append(u)
        else:
            ambiguous_unknown = True

    eur_values: list[float] = []
    rial_values: list[float] = []
    eur_conflict = False
    rial_conflict = False
    for g in groups:
        for col, target, conflict_name in (
            ("CRD_EUR_AMOUNT", eur_values, "eur"),
            ("CRD_RIAL_AMOUNT", rial_values, "rial"),
        ):
            vals = pd.to_numeric(g[col], errors="coerce").dropna().unique().tolist()
            if len(vals) == 1:
                target.append(float(vals[0]))
            elif len(vals) > 1:
                if conflict_name == "eur":
                    eur_conflict = True
                else:
                    rial_conflict = True

    eur_total = None if eur_conflict or ambiguous_unknown or not eur_values else float(sum(eur_values))
    rial_total = None if rial_conflict or ambiguous_unknown or not rial_values else float(sum(rial_values))
    logical_count = len(groups)
    eur_cov = round(100.0 * len(eur_values) / logical_count, 1) if logical_count and not eur_conflict and not ambiguous_unknown else 0.0
    rial_cov = round(100.0 * len(rial_values) / logical_count, 1) if logical_count and not rial_conflict and not ambiguous_unknown else 0.0
    partial = logical_count > 0 and ((0 < len(eur_values) < logical_count) or (0 < len(rial_values) < logical_count))
    if ambiguous_unknown:
        status = "AMBIGUOUS_UNIDENTIFIED_CREDIT_ROWS"
    elif eur_conflict or rial_conflict:
        status = "CONFLICTING_SOURCE_EQUIVALENTS"
    elif partial:
        status = "PARTIAL_SOURCE_EQUIVALENTS"
    elif eur_total is not None and rial_total is not None:
        status = "EUR_AND_IRR_REPORTED"
    elif eur_total is not None:
        status = "EUR_REPORTED"
    elif rial_total is not None:
        status = "IRR_REPORTED"
    else:
        status = "NO_REPORTED_EQUIVALENT"
    return CreditEquivalentResult(eur_total, rial_total, status, logical_count, eur_cov, rial_cov)


def _actual_purchase_rows(frame: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Return rows eligible as observed/actual FX purchases.

    Explicit planning/forecast states are not transaction evidence. Missing state
    remains eligible for backward-compatible source snapshots that predate the
    state field.
    """
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    planned = pd.Series(False, index=out.index)
    blocked = {"PLANNED", "PLAN", "FORECAST", "DRAFT", "در برنامه خرید", "برنامه خرید"}
    for c in ("FX_PURCHASE_STATE", "FX_STATUS"):
        if c in out.columns:
            values = out[c].map(lambda v: _text(v).upper())
            planned = planned | values.isin({x.upper() for x in blocked})
    return out.loc[~planned].copy()


def summarize_fx_purchases(frame: Optional[pd.DataFrame]) -> EquivalentResult:
    """Summarize FX purchase rows without adding unlike native currencies.

    EUR/IRR equivalents are additive because they already share a unit.  A
    reported-equivalent total is returned only for observed values.  Coverage
    is deliberately row-based because native amounts from unlike currencies
    cannot form a valid common denominator without another conversion step.
    This makes partial source coverage visible without inventing a rate.
    """
    if frame is None or frame.empty:
        return EquivalentResult("—", "", None, None, None, 0.0, 0.0)

    f = _actual_purchase_rows(frame)
    if f.empty:
        return EquivalentResult("—", "", None, None, None, 0.0, 0.0)
    for c in ("FX_AMOUNT", "FX_EUR_VALUE", "FX_RIAL_VALUE"):
        if c not in f.columns:
            f[c] = pd.NA
        f[c] = pd.to_numeric(f[c], errors="coerce")
        f.loc[~f[c].map(lambda x: bool(pd.notna(x) and math.isfinite(float(x)))), c] = pd.NA
    if "FX_CURRENCY" not in f.columns:
        f["FX_CURRENCY"] = ""
    f["FX_CURRENCY"] = f["FX_CURRENCY"].map(_currency)
    valid = f["FX_AMOUNT"].notna() & f["FX_CURRENCY"].ne("")
    f = f.loc[valid].copy()
    if f.empty:
        return EquivalentResult("—", "", None, None, None, 0.0, 0.0)

    native_display = _native_display(f, "FX_AMOUNT", "FX_CURRENCY")
    currencies = sorted(set(f["FX_CURRENCY"]))
    single_currency = currencies[0] if len(currencies) == 1 else ""
    single_native_amount = float(f["FX_AMOUNT"].sum()) if single_currency else None

    # Coverage is row-based.  Cross-currency native amounts are never added to
    # form a denominator because that would itself require an FX conversion.
    row_count = len(f)
    eur_mask = f["FX_EUR_VALUE"].notna()
    rial_mask = f["FX_RIAL_VALUE"].notna()
    eur_total = float(f.loc[eur_mask, "FX_EUR_VALUE"].sum()) if eur_mask.any() else None
    rial_total = float(f.loc[rial_mask, "FX_RIAL_VALUE"].sum()) if rial_mask.any() else None
    eur_cov = round(100.0 * int(eur_mask.sum()) / row_count, 1) if row_count else 0.0
    rial_cov = round(100.0 * int(rial_mask.sum()) / row_count, 1) if row_count else 0.0
    return EquivalentResult(native_display, single_currency, single_native_amount,
                            eur_total, rial_total, eur_cov, rial_cov)


def _weighted_ratio(frame: pd.DataFrame, numerator: str) -> tuple[Optional[float], int, int]:
    frame = _actual_purchase_rows(frame)
    if frame is None or frame.empty or "FX_AMOUNT" not in frame.columns or numerator not in frame.columns:
        return None, 0, 0
    amount = pd.to_numeric(frame["FX_AMOUNT"], errors="coerce")
    num = pd.to_numeric(frame[numerator], errors="coerce")
    amount_finite = amount.map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
    num_finite = num.map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
    eligible = amount_finite & amount.gt(EPS)
    usable = eligible & num_finite & num.gt(EPS)
    if not usable.any():
        return None, int(eligible.sum()), 0
    den = float(amount.loc[usable].sum())
    if den <= EPS:
        return None, int(eligible.sum()), int(usable.sum())
    return float(num.loc[usable].sum()) / den, int(eligible.sum()), int(usable.sum())


def _weighted_rate(frame: pd.DataFrame) -> tuple[Optional[float], int, int]:
    frame = _actual_purchase_rows(frame)
    if frame is None or frame.empty or "FX_AMOUNT" not in frame.columns or "FX_RATE" not in frame.columns:
        return None, 0, 0
    amount = pd.to_numeric(frame["FX_AMOUNT"], errors="coerce")
    rate = pd.to_numeric(frame["FX_RATE"], errors="coerce")
    amount_finite = amount.map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
    rate_finite = rate.map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
    eligible = amount_finite & amount.gt(EPS)
    usable = eligible & rate_finite & rate.gt(EPS)
    if not usable.any():
        return None, int(eligible.sum()), 0
    den = float(amount.loc[usable].sum())
    if den <= EPS:
        return None, int(eligible.sum()), int(usable.sum())
    return float((amount.loc[usable] * rate.loc[usable]).sum()) / den, int(eligible.sum()), int(usable.sum())


def _latest_allocation_rate(frame: Optional[pd.DataFrame], currency: str) -> tuple[Optional[float], str]:
    if (frame is None or frame.empty or "NTSW_FX_RATE_NUMERIC" not in frame.columns
            or "NTSW_REQ_CURRENCY" not in frame.columns):
        return None, "NONE"
    z = frame.copy()
    z = z[z["NTSW_REQ_CURRENCY"].map(_currency).eq(currency)]
    if z.empty:
        return None, "NONE"
    # When a request state is explicitly supplied, only an allocated request is
    # authoritative rate evidence. Legacy rows without the field remain usable.
    if "NTSW_REQUEST_STATE" in z.columns:
        states = z["NTSW_REQUEST_STATE"].map(lambda v: _text(v).upper())
        explicit = states.ne("")
        z = z[(~explicit) | states.eq("ALLOCATED")]
    if z.empty:
        return None, "NONE"
    z["__rate"] = pd.to_numeric(z["NTSW_FX_RATE_NUMERIC"], errors="coerce")
    finite = z["__rate"].map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
    z = z[finite & z["__rate"].gt(EPS)]
    if z.empty:
        return None, "NONE"

    def dt_key(row: pd.Series) -> str:
        for c in ("NTSW_ALLOC_DATE", "NTSW_APPROVE_DATE", "NTSW_REQ_DATE"):
            d = CalendarEngine.parse(row.get(c))
            if d:
                return d.isoformat()
        return ""

    z["__date"] = z.apply(dt_key, axis=1)
    latest = z["__date"].max()
    top = z[z["__date"].eq(latest)]
    rates = sorted({float(x) for x in top["__rate"]})
    if len(rates) != 1:
        return None, "CONFLICT"
    return rates[0], "OK"


def commitment_equivalents(
    *,
    reg: Any,
    currency: Any,
    balance: Any,
    initial: Any = None,
    fx_rows: Optional[pd.DataFrame] = None,
    allocation_rows: Optional[pd.DataFrame] = None,
) -> dict[str, Any]:
    """Return EUR/IRR reference equivalents for an NTSW commitment.

    Only source evidence belonging to the same registration and currency is
    eligible.  The basis fields make the exact authority visible to reports.
    """
    reg_s = clean_key(reg)
    cur = _currency(currency)
    bal = _num(balance)
    ini = _num(initial)
    result: dict[str, Any] = {
        "FX_NTSW_CURRENCY": cur,
        "FX_NTSW_BALANCE_EUR_EQ": None,
        "FX_NTSW_BALANCE_RIAL_EQ": None,
        "FX_NTSW_INITIAL_EUR_EQ": None,
        "FX_NTSW_INITIAL_RIAL_EQ": None,
        "FX_NTSW_EUR_RATE_PER_UNIT": None,
        "FX_NTSW_RIAL_RATE_PER_UNIT": None,
        "FX_NTSW_EUR_EQ_BASIS": "NO_SAME_CASE_SOURCE_RATE",
        "FX_NTSW_RIAL_EQ_BASIS": "NO_SAME_CASE_SOURCE_RATE",
        "FX_NTSW_EQ_STATUS": "UNAVAILABLE",
    }
    if not reg_s or not cur or bal is None:
        return result

    # Without both identity fields a transaction cannot supply a case rate.
    f = (fx_rows.copy() if fx_rows is not None and
         {KEY_REG, "FX_CURRENCY"}.issubset(fx_rows.columns) else pd.DataFrame())
    if not f.empty:
        f = f[f[KEY_REG].map(clean_key).eq(reg_s) & f["FX_CURRENCY"].map(_currency).eq(cur)]
        f = _actual_purchase_rows(f)

    # EUR authority: identity for EUR, otherwise source-reported EUR equivalent
    # on same-case purchase rows.
    eur_rate: Optional[float] = None
    if cur == "EUR":
        eur_rate = 1.0
        result["FX_NTSW_EUR_EQ_BASIS"] = "NTSW_NATIVE_EUR"
    else:
        eur_rate, eligible, usable = _weighted_ratio(f, "FX_EUR_VALUE")
        if eur_rate is not None:
            coverage = "COMPLETE" if eligible and usable == eligible else "PARTIAL"
            result["FX_NTSW_EUR_EQ_BASIS"] = f"FX_SOURCE_REPORTED_EUR_{coverage}_SAME_REG_CURRENCY"

    # IRR authority: identity for IRR; source-reported rial equivalent; source
    # purchase rate; finally NTSW allocation rate from same REG+currency.
    rial_rate: Optional[float] = None
    if cur == "IRR":
        rial_rate = 1.0
        result["FX_NTSW_RIAL_EQ_BASIS"] = "NTSW_NATIVE_IRR"
    else:
        rial_rate, eligible, usable = _weighted_ratio(f, "FX_RIAL_VALUE")
        if rial_rate is not None:
            coverage = "COMPLETE" if eligible and usable == eligible else "PARTIAL"
            result["FX_NTSW_RIAL_EQ_BASIS"] = f"FX_SOURCE_REPORTED_RIAL_{coverage}_SAME_REG_CURRENCY"
        else:
            rial_rate, eligible, usable = _weighted_rate(f)
            if rial_rate is not None:
                coverage = "COMPLETE" if eligible and usable == eligible else "PARTIAL"
                result["FX_NTSW_RIAL_EQ_BASIS"] = f"FX_SOURCE_RATE_{coverage}_SAME_REG_CURRENCY"
            else:
                alloc = (allocation_rows if allocation_rows is not None and
                         {KEY_REG, "NTSW_REQ_CURRENCY"}.issubset(allocation_rows.columns)
                         else None)
                if alloc is not None and not alloc.empty:
                    alloc = alloc[alloc[KEY_REG].map(clean_key).eq(reg_s)]
                rial_rate, allocation_status = _latest_allocation_rate(alloc, cur)
                if allocation_status == "CONFLICT":
                    result["FX_NTSW_RIAL_EQ_BASIS"] = "NTSW_ALLOCATION_RATE_CONFLICT_SAME_REG_CURRENCY"
                elif rial_rate is not None:
                    result["FX_NTSW_RIAL_EQ_BASIS"] = "NTSW_ALLOCATION_LATEST_RATE_SAME_REG_CURRENCY"

    if eur_rate is not None:
        result["FX_NTSW_EUR_RATE_PER_UNIT"] = eur_rate
        result["FX_NTSW_BALANCE_EUR_EQ"] = bal * eur_rate
        if ini is not None:
            result["FX_NTSW_INITIAL_EUR_EQ"] = ini * eur_rate
    if rial_rate is not None:
        result["FX_NTSW_RIAL_RATE_PER_UNIT"] = rial_rate
        result["FX_NTSW_BALANCE_RIAL_EQ"] = bal * rial_rate
        if ini is not None:
            result["FX_NTSW_INITIAL_RIAL_EQ"] = ini * rial_rate

    if eur_rate is not None and rial_rate is not None:
        result["FX_NTSW_EQ_STATUS"] = "EUR_AND_IRR_AVAILABLE"
    elif eur_rate is not None:
        result["FX_NTSW_EQ_STATUS"] = "EUR_AVAILABLE"
    elif rial_rate is not None:
        result["FX_NTSW_EQ_STATUS"] = "IRR_AVAILABLE"
    return result
