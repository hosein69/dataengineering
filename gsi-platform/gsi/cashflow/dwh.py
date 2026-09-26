"""Cash-flow evidence bridge from the published SQLite business DWH.

The dashboard cash-flow panel must not depend on the flattened BL mart to discover
financial cases.  This module reads the native-grain evidence kept in
``dwh_fact_source_row`` and resolves only direct, documented business keys.

Source precedence is a business policy, not a merge-order side effect:
  1. Commercial Expert (moghavemat) + NTSW
  2. Abbasi + SATA
  3. other financial feeds (FX transaction / credit / IL) as complementary facts

No fuzzy relation is created.  If equal-priority evidence disagrees, the mapping is
left unresolved and a diagnostic row is returned instead of choosing silently.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import sqlite3
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

import pandas as pd

from ..adapters.base import KEY_BL, KEY_ORDER, KEY_REG, KEY_REG_FILE
from ..core.jalali import CalendarEngine
from ..warehouse.store import Warehouse, loads
from .engine import EVENT_COLUMNS, LINK_COLUMNS, MEASUREMENT_COLUMNS, number, text

SOURCE_PRIORITY = {
    "moghavemat": 400,
    "ntsw": 400,
    "abbasi": 300,
    "sata": 300,
    "fx_transaction": 200,
    "credit": 180,
    "ilappend": 160,
}

class FinancialSourceUnavailable(RuntimeError):
    """Published financial evidence could not be read or decoded."""


def _clean(v: Any) -> str:
    return text(v)


def _truthy(v: Any) -> bool:
    """NA-safe boolean decoder for source flags."""
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except (TypeError, ValueError):
        pass
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "y", "allocated", "تخصیص یافته"}
    try:
        return bool(v)
    except (TypeError, ValueError):
        return False


def _first(*values: Any) -> Any:
    """First non-empty value without evaluating pandas.NA as boolean."""
    for value in values:
        if _clean(value):
            return value
    return ""


def _stable(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(x) for x in parts)
    return f"{prefix}:{sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _frame(rows, columns):
    return pd.DataFrame(rows, columns=columns)


def _source_reg(source: str, row: Mapping[str, Any]) -> str:
    """Return a source-native REG key without borrowing from the flat mart."""
    for col in (
        KEY_REG,
        "NTSW_KEY_REG" if source == "ntsw" else "",
        "SATA_KEY_REG" if source == "sata" else "",
        "FX_KEY_REG" if source == "fx_transaction" else "",
        "CRD_KEY_REG" if source == "credit" else "",
        "IL_KEY_REG" if source == "ilappend" else "",
    ):
        if col and _clean(row.get(col)):
            return _clean(row.get(col))
    return ""


def _published_source_frames(warehouse: Optional[Warehouse] = None):
    wh = warehouse or Warehouse(initialize=False)
    if not wh.path.exists():
        return {}, None
    try:
        with wh.read_db() as conn:
            current = conn.execute("SELECT run_id FROM wh_current WHERE slot='dwh'").fetchone()
            if not current:
                current = conn.execute("SELECT run_id FROM wh_current WHERE slot='report'").fetchone()
            if not current:
                return {}, None
            rid = current[0]
            rows = conn.execute(
                "SELECT source,frame,payload FROM dwh_fact_source_row "
                "WHERE last_seen_run=? ORDER BY source,frame,row_hash",
                (rid,),
            ).fetchall()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        raise FinancialSourceUnavailable("FINANCIAL_SOURCE_UNAVAILABLE") from exc
    grouped: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for source, frame, payload in rows:
        try:
            grouped[str(source)][str(frame)].append(loads(payload))
        except Exception as exc:
            raise FinancialSourceUnavailable("INVALID_PUBLISHED_FINANCIAL_PAYLOAD") from exc
    out = {
        source: {frame: pd.DataFrame(items) for frame, items in frames.items()}
        for source, frames in grouped.items()
    }
    return out, rid


def _candidate_maps(sources: Mapping[str, Mapping[str, pd.DataFrame]]):
    """Build documented ORDER/BL→REG candidates from native source rows.

    Besides direct co-observation, the sanctioned registration-file hub is used:
    NTSW Import Licence REG_FILE→REG plus IL/NTSW REG_FILE→ORDER.  This is a
    documented DWH path, not a fuzzy join, and lets Commercial Expert orders reach
    NTSW without requiring SATA to be the starting population.
    """
    order_candidates = defaultdict(list)
    bl_candidates = defaultdict(list)
    regfile_reg_candidates = defaultdict(list)
    regfile_order_candidates = defaultdict(list)
    diagnostics = []

    for source, frames in sources.items():
        priority = SOURCE_PRIORITY.get(source, 100)
        for frame, df in frames.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            for idx, row in df.iterrows():
                reg = _source_reg(source, row)
                order = _clean(row.get(KEY_ORDER))
                bl = _clean(row.get(KEY_BL))
                reg_file = _clean(row.get(KEY_REG_FILE))
                ref = f"{source}/{frame}#{idx+1}"
                if reg and order:
                    order_candidates[order].append((priority, reg, source, ref))
                if reg and bl:
                    bl_candidates[bl].append((priority, reg, source, ref))
                if reg_file and reg:
                    regfile_reg_candidates[reg_file].append((priority, reg, source, ref))
                if reg_file and order:
                    regfile_order_candidates[reg_file].append((priority, order, source, ref))

    def resolve(candidates, entity_type, value_name='REG'):
        resolved = {}
        for key, vals in candidates.items():
            top = max(v[0] for v in vals)
            winners = [v for v in vals if v[0] == top]
            values = sorted({v[1] for v in winners})
            if len(values) == 1:
                resolved[key] = values[0]
            else:
                diagnostics.append({
                    "code": "DWH_EQUAL_PRIORITY_KEY_CONFLICT",
                    "entity_type": entity_type,
                    "entity_key": key,
                    "detail": f"{value_name}: " + " | ".join(f"{v[2]}:{v[1]}" for v in winners),
                })
        return resolved

    regfile_to_reg = resolve(regfile_reg_candidates, "REG_FILE", "REG")
    regfile_to_order = resolve(regfile_order_candidates, "REG_FILE", "ORDER")
    for reg_file in sorted(set(regfile_to_reg) & set(regfile_to_order)):
        order = regfile_to_order[reg_file]
        reg = regfile_to_reg[reg_file]
        # NTSW registration-file hub is deliberately above SATA direct bridging,
        # but below a direct NTSW ORDER+REG co-observation.
        order_candidates[order].append((390, reg, "ntsw/reg_file_hub", reg_file))

    return resolve(order_candidates, "ORDER"), resolve(bl_candidates, "BL"), diagnostics


def _date(v: Any) -> str:
    d = CalendarEngine.parse(v) if _clean(v) else None
    return d.isoformat() if d else ""


def _row_doc(source: str, frame: str, idx: int, native_ref: Any = "") -> str:
    return _clean(native_ref) or f"DWH:{source}/{frame}#{idx+1}"


def _event(rows: list, *, source: str, frame: str, idx: int, case_id: str,
           kind: str, date: Any, amount: Any = "", currency: Any = "",
           order_id: Any = "", bl_id: Any = "", native_ref: Any = "",
           note: str = "", due_date: Any = "") -> str:
    if not case_id:
        return ""
    doc = _row_doc(source, frame, idx, native_ref)
    eid = _stable("DWH", source, frame, native_ref or idx + 1, kind, case_id)
    rows.append({
        "event_id": eid,
        "source_event_id": ((_clean(native_ref) + ":" + kind) if _clean(native_ref) else ""),
        "case_id": case_id,
        "order_id": _clean(order_id),
        "bl_id": _clean(bl_id),
        "kind": kind,
        "date": _date(date),
        "amount": _clean(amount),
        "currency": _clean(currency).upper(),
        "document": doc,
        "source": f"DWH/{source}/{frame}",
        "status": "SOURCE_FACT",
        "due_date": _date(due_date),
        "note": note,
    })
    return eid


def bundle_from_dwh(as_of=None, warehouse: Optional[Warehouse] = None, *, scope=None):
    """Return engine-ready events/measurements plus DWH provenance diagnostics."""
    sources, run_id = _published_source_frames(warehouse)
    if not sources:
        return {
            "events": _frame([], EVENT_COLUMNS),
            "measurements": _frame([], MEASUREMENT_COLUMNS),
            "links": _frame([], LINK_COLUMNS),
            "diagnostics": pd.DataFrame(columns=["code","entity_type","entity_key","detail"]),
            "origin": "DWH_EMPTY",
            "warehouse_run_id": run_id,
        }

    order_to_reg, bl_to_reg, diagnostics = _candidate_maps(sources)
    for source, frames in sources.items():
        for name in ("commitment_quarantine", "allocation_quarantine"):
            q = frames.get(name)
            if isinstance(q, pd.DataFrame) and not q.empty:
                for _, row in q.iterrows():
                    diagnostics.append({"code":"QUARANTINED_FINANCIAL_EVIDENCE", "entity_type":source,
                                        "entity_key":_source_reg(source,row),
                                        "detail":name+": "+_clean(row.get("DQ_REASON"))})
    events, measurements, links = [], [], []
    asof = CalendarEngine.parse(as_of) if as_of else None
    asof_s = asof.isoformat() if asof else ""

    # 1) Commercial Expert: primary commercial value evidence at ORDER grain.
    # Use order-level aggregate to avoid multiplying line rows.
    mogh = sources.get("moghavemat", {}).get("main")
    if isinstance(mogh, pd.DataFrame) and not mogh.empty:
        for i, r in mogh.reset_index(drop=True).iterrows():
            order = _clean(r.get(KEY_ORDER))
            reg = order_to_reg.get(order, "")
            amount = r.get("MOGH_PI_VALUE_SUM")
            currency = r.get("MOGH_CURRENCY")
            # PI/PO evidence is commercial registration/proforma evidence, not bank cash.
            if reg and _clean(amount) and _clean(currency):
                _event(events, source="moghavemat", frame="main", idx=i, case_id=reg,
                       kind="REGISTRATION", date=r.get("MOGH_PO_SENT_DATE"), amount=amount,
                       currency=currency, order_id=order, native_ref=order,
                       note="شاهد مبلغ PI از فایل کارشناسان؛ منبع درجه‌اول تجاری، نه سند بانکی")

    # 2) NTSW: authoritative allocation/commitment evidence.
    alloc = sources.get("ntsw", {}).get("allocation_rows")
    if alloc is None or alloc.empty:
        alloc = sources.get("ntsw", {}).get("allocation")
    if isinstance(alloc, pd.DataFrame) and not alloc.empty:
        for i, r in alloc.reset_index(drop=True).iterrows():
            reg = _source_reg("ntsw", r)
            state = _clean(r.get("NTSW_REQUEST_STATE"))
            if state == "AMBIGUOUS":
                diagnostics.append({"code":"AMBIGUOUS_ALLOCATION_STATUS", "entity_type":"REG",
                                    "entity_key":reg, "detail":"Equal-date request states conflict; excluded from sums"})
                continue
            ref = _first(r.get("NTSW_REQUEST_KEY"), r.get("NTSW_REQ_ROW"), f"allocation#{i+1}")
            _event(events, source="ntsw", frame="allocation_rows", idx=i, case_id=reg,
                   kind="QUEUE", date=r.get("NTSW_REQ_DATE"), amount=r.get("NTSW_REQ_AMOUNT"),
                   currency=r.get("NTSW_REQ_CURRENCY"), native_ref=ref,
                   note=f"درخواست تخصیص NTSW؛ state={state or _clean(r.get('NTSW_ALLOC_STATUS'))}")
            if state == "ALLOCATED" or _truthy(r.get("NTSW_ALLOCATED")):
                amt = r.get("NTSW_REQ_AMOUNT")
                if not _clean(amt):
                    amt = r.get("NTSW_ALLOCATED_AMOUNT")
                _event(events, source="ntsw", frame="allocation_rows", idx=i, case_id=reg,
                       kind="ALLOCATION", date=r.get("NTSW_ALLOC_DATE"), amount=amt,
                       currency=r.get("NTSW_REQ_CURRENCY"), native_ref=ref,
                       note="تخصیص ثبت‌شده در NTSW")

    com = sources.get("ntsw", {}).get("commitment")
    if isinstance(com, pd.DataFrame) and not com.empty:
        for i, r in com.reset_index(drop=True).iterrows():
            reg = _source_reg("ntsw", r)
            ref = f"{reg}:commitment-summary"
            _event(events, source="ntsw", frame="commitment", idx=i, case_id=reg,
                   kind="COMMITMENT", date=r.get("NTSW_COMMIT_DATE"),
                   amount=r.get("NTSW_INITIAL_COMMIT"), currency=r.get("NTSW_CURRENCY"),
                   native_ref=ref, due_date=r.get("NTSW_DEADLINE"),
                   note="تعهد اولیه تجمیع‌شده NTSW؛ مانده به‌صورت Snapshot جدا نگهداری می‌شود")
            if reg and _clean(r.get("NTSW_BALANCE")) and _clean(r.get("NTSW_CURRENCY")) and asof_s:
                measurements.append({
                    "measurement_id": _stable("DWHM", "ntsw", "commitment", ref, reg, asof_s),
                    "case_id": reg,
                    "metric": "COMMITMENT_BALANCE",
                    "observed_at": asof_s,
                    "amount": _clean(r.get("NTSW_BALANCE")),
                    "currency": _clean(r.get("NTSW_CURRENCY")).upper(),
                    "source": "DWH/ntsw/commitment",
                    "source_record_id": _clean(ref),
                    "document": _row_doc("ntsw", "commitment", i, ref),
                    "status": "OBSERVED",
                    "note": "Snapshot مانده NTSW در تاریخ گزارش؛ مهلت رفع تعهد تاریخ مشاهده نیست",
                })

    # 3) Complementary financial systems. These facts are usable for amount flow,
    # but remain SOURCE_FACT and therefore never fabricate OWN bank accounts.
    fx = sources.get("fx_transaction", {}).get("main")
    if isinstance(fx, pd.DataFrame) and not fx.empty:
        for i, r in fx.reset_index(drop=True).iterrows():
            reg = _source_reg("fx_transaction", r)
            if not reg:
                order = _clean(r.get(KEY_ORDER)); bl = _clean(r.get(KEY_BL))
                candidates = {x for x in (order_to_reg.get(order), bl_to_reg.get(bl)) if x}
                if len(candidates) == 1:
                    reg = next(iter(candidates))
                else:
                    diagnostics.append({"code":"UNRESOLVED_FINANCIAL_EVIDENCE", "entity_type":"fx_transaction", "entity_key":order or bl,
                                        "detail":f"row={i+1}; candidates={sorted(candidates)}; native source row retained"})
            ref = f"fx#{i+1}"
            buy_id = ""
            if _clean(r.get("FX_PURCHASE_STATE")) == "PLANNED":
                diagnostics.append({"code": "PLANNED_PURCHASE_NOT_EXECUTED", "entity_type": "fx_transaction",
                                    "entity_key": reg or ref, "detail": "Source status is a purchase plan; excluded from executed FX cash events"})
            else:
                buy_id = _event(events, source="fx_transaction", frame="main", idx=i, case_id=reg,
                                kind="FX_BUY", date=r.get("FX_BUY_DATE"), amount=r.get("FX_AMOUNT"),
                                currency=r.get("FX_CURRENCY"), native_ref=ref,
                                note="شاهد خرید ارز از DWH؛ جزئیات حساب بانکی در این سورس موجود نیست")
            if _clean(r.get("FX_PAID_AMOUNT")) and _clean(r.get("FX_PAID_CURRENCY")):
                pay_id = _event(events, source="fx_transaction", frame="main", idx=i, case_id=reg,
                                kind="PAYMENT", date=r.get("FX_RECEIPT_DATE"),
                                amount=r.get("FX_PAID_AMOUNT"), currency=r.get("FX_PAID_CURRENCY"), native_ref=ref+":payment",
                                note="شاهد پرداخت ذی‌نفع از DWH؛ بدون ساخت حساب بانکی فرضی")
                # Same native source row is direct provenance that the supplier payment
                # belongs to this FX purchase. Link only the explicitly observed paid
                # amount, never infer a remainder or cross-currency conversion.
                bought, paid = number(r.get("FX_AMOUNT")), number(r.get("FX_PAID_AMOUNT"))
                buy_cur = _clean(r.get("FX_CURRENCY")).upper()
                paid_cur = _clean(r.get("FX_PAID_CURRENCY")).upper()
                if buy_id and pay_id and bought is not None and paid is not None and paid > 0 and bought >= paid and buy_cur == paid_cur:
                    links.append({
                        "link_id": _stable("DWHL", "fx_transaction", ref, "FX_BUY_PAYMENT", reg),
                        "relation_type": "SOURCE_RECORD_FLOW",
                        "from_event": buy_id, "to_event": pay_id,
                        "from_amount": str(paid), "to_amount": str(paid),
                        "document": _row_doc("fx_transaction", "main", i, ref),
                        "authorization": "", "rate_id": "", "conversion_basis": "",
                    })

    credit = sources.get("credit", {}).get("main")
    if isinstance(credit, pd.DataFrame) and not credit.empty:
        for i, r in credit.reset_index(drop=True).iterrows():
            reg = _source_reg("credit", r)
            if not reg:
                order = _clean(r.get(KEY_ORDER)); bl = _clean(r.get(KEY_BL))
                candidates = {x for x in (order_to_reg.get(order), bl_to_reg.get(bl)) if x}
                if len(candidates) == 1:
                    reg = next(iter(candidates))
                else:
                    diagnostics.append({"code":"UNRESOLVED_FINANCIAL_EVIDENCE", "entity_type":"credit", "entity_key":order or bl,
                                        "detail":f"row={i+1}; candidates={sorted(candidates)}; native source row retained"})
            ref = f"credit#{i+1}"
            if _clean(r.get("CRD_FUND_DATE")):
                diagnostics.append({"code": "FUNDING_AMOUNT_UNMEASURED", "entity_type": "credit",
                                    "entity_key": reg or ref,
                                    "detail": "Funding date observed; مبلغ به ریال is proforma equivalent, not an observed funded amount; no cash event inferred"})

    ev = _frame(events, EVENT_COLUMNS)
    ms = _frame(measurements, MEASUREMENT_COLUMNS)
    lk = _frame(links, LINK_COLUMNS)
    scope_status = "ALL_PUBLISHED"
    if scope is not None:
        keys = _scope_keys(scope, order_to_reg, bl_to_reg)
        scope_status = "RESOLVED" if keys else "EMPTY_OR_UNRESOLVED"
        ev = ev.loc[ev["case_id"].isin(keys)].copy()
        ms = ms.loc[ms["case_id"].isin(keys)].copy()
        event_ids = set(ev["event_id"])
        lk = lk.loc[lk["from_event"].isin(event_ids) & lk["to_event"].isin(event_ids)].copy()
    return {
        "events": ev,
        "measurements": ms,
        "links": lk,
        "diagnostics": pd.DataFrame(diagnostics, columns=["code","entity_type","entity_key","detail"]),
        "origin": "SQLITE_BUSINESS_DWH",
        "warehouse_run_id": run_id,
        "scope_status": scope_status,
        "source_priority": "moghavemat=ntsw > abbasi=sata > complementary finance",
    }


def scope_regs_from_dwh(df: pd.DataFrame, warehouse: Optional[Warehouse] = None) -> set[str]:
    """Expand dashboard scope through source-native DWH keys instead of flat-only REG."""
    sources, _ = _published_source_frames(warehouse)
    order_to_reg, bl_to_reg, _ = _candidate_maps(sources)
    return _scope_keys(df, order_to_reg, bl_to_reg)


def _scope_keys(df, order_to_reg, bl_to_reg):
    regs = set()
    for c in (KEY_REG, "CANONICAL_REG"):
        if c in df.columns:
            regs.update(_clean(v) for v in df[c] if _clean(v))
    for c in (KEY_ORDER, "CANONICAL_ORDER"):
        if c in df.columns:
            regs.update(order_to_reg.get(_clean(v), "") for v in df[c] if _clean(v))
    for c in (KEY_BL, "CANONICAL_BL"):
        if c in df.columns:
            regs.update(bl_to_reg.get(_clean(v), "") for v in df[c] if _clean(v))
    return {r for r in regs if r}
