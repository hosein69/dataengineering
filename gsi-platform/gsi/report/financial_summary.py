"""Currency-aware, grain-safe financial summaries for decision-facing outputs.

Financial amounts such as commitment balance and penalty live at registration
(REG) grain while the main fact table can be BL × material.  This module is the
single place where those values are collapsed for presentation so reports do
not silently double-count fan-out rows or add unlike currencies.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Iterable, Sequence

import pandas as pd

_REGISTRATION_CANDIDATES = ("KEY_REG", "CANONICAL_REG")
_CURRENCY_CANDIDATES = ("NTSW_CURRENCY", "CURRENCY", "ارز")
_BALANCE_CANDIDATES = ("NTSW_BALANCE", "مانده تعهد")


def _pick(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    return next((c for c in candidates if c in df.columns), None)


def _truthy(value: object) -> bool:
    if value is True:
        return True
    if value is False or value is None or pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "بله"}


def _decimal(value: object) -> Decimal | None:
    try:
        out = Decimal(str(value))
        return out if out.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def currency_amount_display(
    df: pd.DataFrame,
    amount_candidates: Sequence[str],
    *,
    unknown_flag: str | None = None,
    unknown_message: str = "مبلغ نامشخص؛ جمع قابل اتکا نیست",
) -> str:
    """Return a REG-grain total split by currency.

    The function deliberately returns text rather than a naked number.  A
    currency-less total is not decision-safe for the multi-currency sourcing
    population.  Duplicate fan-out rows are collapsed by registration and
    currency; conflicting values are surfaced instead of being guessed.
    """
    if df.empty:
        return "—"

    amount = _pick(df, amount_candidates)
    currency = _pick(df, _CURRENCY_CANDIDATES)
    registration = _pick(df, _REGISTRATION_CANDIDATES)
    if not all((amount, currency, registration)):
        return "نیازمند کلید ثبت سفارش و ارز"

    cols = [registration, currency, amount]
    if unknown_flag and unknown_flag in df.columns:
        cols.append(unknown_flag)

    groups: dict[tuple[str, str], set[Decimal]] = {}
    for row in df[cols].itertuples(index=False, name=None):
        reg, cur, value = row[:3]
        is_unknown = _truthy(row[3]) if len(row) > 3 else False

        if pd.isna(reg) or pd.isna(cur) or not str(reg).strip() or not str(cur).strip():
            return "کلید یا ارز ناقص؛ جمع قابل اتکا نیست"
        if is_unknown:
            return unknown_message

        dec = _decimal(value)
        if dec is None:
            return unknown_message
        groups.setdefault((str(reg).strip(), str(cur).strip()), set()).add(dec)

    totals: dict[str, Decimal] = {}
    for (_, cur), values in groups.items():
        if len(values) != 1:
            return "مغایرت مبلغ برای ثبت سفارش؛ نیازمند بررسی"
        totals[cur] = totals.get(cur, Decimal(0)) + next(iter(values))

    return " | ".join(f"{value:,.2f} {cur}" for cur, value in sorted(totals.items()))


def commitment_display(df: pd.DataFrame) -> str:
    """Decision-safe commitment balance, split by currency and REG grain."""
    msg = currency_amount_display(
        df,
        _BALANCE_CANDIDATES,
        unknown_flag="BALANCE_IS_UNKNOWN",
        unknown_message="مانده نامشخص؛ جمع قابل اتکا نیست",
    )
    # Preserve the established, more specific wording for balance conflicts.
    if msg == "مغایرت مبلغ برای ثبت سفارش؛ نیازمند بررسی":
        return "مغایرت مانده برای ثبت سفارش؛ نیازمند بررسی"
    return msg


def penalty_display(df: pd.DataFrame) -> str:
    """Decision-safe estimated penalty, split by currency and REG grain.

    Penalty is calculated from commitment balance; an unknown source balance
    therefore makes its total non-authoritative too.
    """
    return currency_amount_display(
        df,
        ("جریمه برآوردی",),
        unknown_flag="BALANCE_IS_UNKNOWN",
        unknown_message="مبنای جریمه نامشخص؛ جمع قابل اتکا نیست",
    )


def commitment_status_summary(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Build chart-safe commitment totals by currency and deadline status.

    One amount is accepted per (registration, currency).  Unknown balances,
    missing keys/currencies, or conflicting duplicates are *not* converted to
    zero and are counted in diagnostics instead.  Consequently an unknown
    balance can never be mislabeled as settled.
    """
    columns = ["currency", "status", "amount", "count"]
    diag = {"unknown": 0, "conflict": 0, "missing_key_or_currency": 0}
    if df.empty:
        return pd.DataFrame(columns=columns), diag

    amount = _pick(df, _BALANCE_CANDIDATES)
    currency = _pick(df, _CURRENCY_CANDIDATES)
    registration = _pick(df, _REGISTRATION_CANDIDATES)
    overdue = _pick(df, ("روزهای تأخیر",))
    if not all((amount, currency, registration)):
        diag["missing_key_or_currency"] = int(len(df))
        return pd.DataFrame(columns=columns), diag

    selected = [registration, currency, amount]
    if overdue:
        selected.append(overdue)
    if "BALANCE_IS_UNKNOWN" in df.columns:
        selected.append("BALANCE_IS_UNKNOWN")

    # Operate on registration/currency groups so BL/material fan-out cannot
    # multiply the same commitment amount.
    accepted: list[tuple[str, str, Decimal]] = []
    tmp = df[selected].copy()
    tmp["__reg"] = tmp[registration].astype(str).str.strip()
    tmp["__cur"] = tmp[currency].astype(str).str.strip()

    missing = tmp["__reg"].eq("") | tmp["__cur"].eq("") | tmp[registration].isna() | tmp[currency].isna()
    diag["missing_key_or_currency"] += int(missing.sum())
    tmp = tmp.loc[~missing]

    for (_, _), g in tmp.groupby(["__reg", "__cur"], sort=False, dropna=False):
        cur = str(g["__cur"].iloc[0])
        if "BALANCE_IS_UNKNOWN" in g.columns and g["BALANCE_IS_UNKNOWN"].map(_truthy).any():
            diag["unknown"] += 1
            continue

        amounts = {_decimal(v) for v in g[amount].tolist()}
        if None in amounts:
            diag["unknown"] += 1
            continue
        if len(amounts) != 1:
            diag["conflict"] += 1
            continue
        value = next(iter(amounts))

        if value <= 0:
            status = "تسویه‌شده"
        elif overdue:
            delays = pd.to_numeric(g[overdue], errors="coerce").dropna().unique().tolist()
            if len(delays) == 0:
                status = "مهلت نامشخص"
            elif len(delays) > 1:
                diag["conflict"] += 1
                continue
            else:
                status = "معوق" if float(delays[0]) > 0 else "در مهلت"
        else:
            status = "مهلت نامشخص"
        accepted.append((cur, status, value))

    if not accepted:
        return pd.DataFrame(columns=columns), diag

    rows = pd.DataFrame(accepted, columns=["currency", "status", "amount"])
    out = (rows.groupby(["currency", "status"], sort=True, as_index=False)
               .agg(amount=("amount", lambda s: float(sum(s, Decimal(0)))),
                    count=("amount", "size")))
    return out[columns], diag


def commitment_numeric_if_single_currency(df: pd.DataFrame) -> tuple[float | None, str | None, str]:
    """Return a numeric balance only when a single authoritative currency exists.

    Historical stores/charts sometimes require a numeric value.  In a mixed-
    currency population returning a single float would destroy the unit, so the
    numeric part is ``None`` and callers should persist/use the display text.
    """
    display = commitment_display(df)
    summary, diag = commitment_status_summary(df)
    if sum(diag.values()) or summary.empty:
        return None, None, display
    currencies = summary["currency"].dropna().astype(str).unique().tolist()
    if len(currencies) != 1:
        return None, None, display
    return float(summary["amount"].sum()), currencies[0], display


def commitment_equivalent_summary(df: pd.DataFrame) -> dict[str, object]:
    """Aggregate source-backed commitment equivalents at proven REG grain.

    Missing identities, unknown native balances, non-finite equivalents and
    multi-native-currency fan-out are never promoted into portfolio totals.
    Conflicted/unknown REGs remain in the coverage denominator so uncertainty
    cannot disappear from decision-facing KPIs.
    """
    result: dict[str, object] = {
        "eur": None, "irr": None, "covered": 0, "total": 0,
        "eur_covered": 0, "irr_covered": 0, "status": "UNAVAILABLE",
        "conflicted": 0, "unknown": 0, "missing_key_rows": 0,
    }
    if df is None or df.empty:
        return result
    reg = _pick(df, _REGISTRATION_CANDIDATES)
    if reg is None:
        result["missing_key_rows"] = len(df)
        return result

    cols = [reg]
    for c in ("FX_NTSW_BALANCE_EUR_EQ", "FX_NTSW_BALANCE_RIAL_EQ",
              "FX_NTSW_EQ_STATUS", "FX_NTSW_CURRENCY", "NTSW_CURRENCY",
              "BALANCE_IS_UNKNOWN", "FX_NTSW_BALANCE_UNKNOWN", "FX_NTSW_BALANCE"):
        if c in df.columns and c not in cols:
            cols.append(c)
    if len(cols) == 1:
        return result
    z = df[cols].copy()

    def clean_reg(v: object) -> str:
        try:
            if v is None or pd.isna(v):
                return ""
        except Exception:
            pass
        t = str(v).strip()
        return "" if t.lower() in {"nan", "none", "<na>"} else t

    z["__reg"] = z[reg].map(clean_reg)
    missing = z["__reg"].eq("")
    result["missing_key_rows"] = int(missing.sum())
    z = z.loc[~missing].copy()
    if z.empty:
        return result

    rows: list[dict[str, object]] = []
    conflicts = 0
    unknowns = 0
    for key, g in z.groupby("__reg", sort=False):
        native_col = "FX_NTSW_CURRENCY" if "FX_NTSW_CURRENCY" in g.columns else ("NTSW_CURRENCY" if "NTSW_CURRENCY" in g.columns else None)
        currencies = set()
        if native_col:
            for v in g[native_col]:
                try:
                    missing_v = v is None or pd.isna(v)
                except Exception:
                    missing_v = False
                if not missing_v and str(v).strip():
                    currencies.add(str(v).strip().upper())
        if len(currencies) > 1:
            conflicts += 1
            continue

        unknown = False
        for flag in ("BALANCE_IS_UNKNOWN", "FX_NTSW_BALANCE_UNKNOWN"):
            if flag in g.columns and any(_truthy(v) for v in g[flag]):
                unknown = True
        if unknown:
            unknowns += 1
            rows.append({"reg": key, "FX_NTSW_BALANCE_EUR_EQ": None,
                         "FX_NTSW_BALANCE_RIAL_EQ": None, "unknown": True})
            continue

        row: dict[str, object] = {"reg": key, "unknown": False}
        conflict = False
        for c in ("FX_NTSW_BALANCE_EUR_EQ", "FX_NTSW_BALANCE_RIAL_EQ"):
            if c not in g.columns:
                row[c] = None
                continue
            vals: list[float] = []
            for v in g[c]:
                dec = _decimal(v)
                if dec is not None:
                    vals.append(float(dec))
            uniq = sorted(set(vals))
            if len(uniq) > 1:
                conflict = True
                break
            row[c] = uniq[0] if uniq else None
        if conflict:
            conflicts += 1
        else:
            rows.append(row)

    result["total"] = len(rows) + conflicts
    result["conflicted"] = conflicts
    result["unknown"] = unknowns
    if not rows:
        if conflicts:
            result["status"] = "CONFLICTED"
        return result

    eur_rows = [r for r in rows if r.get("FX_NTSW_BALANCE_EUR_EQ") is not None]
    irr_rows = [r for r in rows if r.get("FX_NTSW_BALANCE_RIAL_EQ") is not None]
    joint_rows = [r for r in rows if r.get("FX_NTSW_BALANCE_EUR_EQ") is not None
                  and r.get("FX_NTSW_BALANCE_RIAL_EQ") is not None]
    result["eur_covered"] = len(eur_rows)
    result["irr_covered"] = len(irr_rows)
    result["covered"] = len(joint_rows)
    result["eur"] = float(sum(float(r["FX_NTSW_BALANCE_EUR_EQ"]) for r in eur_rows)) if eur_rows else None
    result["irr"] = float(sum(float(r["FX_NTSW_BALANCE_RIAL_EQ"]) for r in irr_rows)) if irr_rows else None
    population = int(result["total"] or 0)
    if not conflicts and not unknowns and population and len(joint_rows) == population:
        result["status"] = "COMPLETE"
    elif eur_rows or irr_rows or conflicts or unknowns:
        result["status"] = "PARTIAL"
    return result


def commitment_equivalent_display(df: pd.DataFrame) -> str:
    """Human-readable EUR/IRR commitment equivalent with explicit coverage."""
    s = commitment_equivalent_summary(df)
    total = int(s["total"] or 0)
    if not total:
        return "معادل منبع‌محور در دسترس نیست"
    parts: list[str] = []
    if s["eur"] is not None:
        parts.append(f"€ {float(s['eur']):,.2f} ({int(s['eur_covered'])}/{total} پرونده)")
    if s["irr"] is not None:
        parts.append(f"IRR {float(s['irr']):,.0f} ({int(s['irr_covered'])}/{total} پرونده)")
    return " | ".join(parts) if parts else "معادل منبع‌محور در دسترس نیست"
