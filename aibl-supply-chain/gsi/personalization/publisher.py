# -*- coding: utf-8 -*-
"""Publish per-employee encrypted snapshots to the shared profile folder.

The central GSI run writes only rows scoped to each employee. Personal clients
read these encrypted snapshots directly from the shared folder; they do not
connect back to the central process by IP/API.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from ..core.text import clean_employee_code
from .store import EncryptedUserStore


DEFAULT_FIELDS = (
    "KEY_EMP", "KEY_REG", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_MATERIAL",
    "CANONICAL_EXPERT", "ORG_DEPT", "مرحله جاری", "انتظار جاری (روز)",
    "بحرانی (کوتاه)", "مقاومت (روز)", "مانع فعلی", "مانده تعهد", "روزهای تأخیر",
    "FX_CURRENT_STAGE", "FX_TIME_DAYS_LEFT", "FX_EVIDENCE_COVERAGE",
    "SUPPLIER_OPEN_QTY", "IN_TRANSIT_QTY", "IN_CUSTOMS_QTY",
    "ORACLE_IKCO_QTY", "ORACLE_SAPCO_QTY", "SUPPLY_POSITION_COVERAGE",
    "FX_ACTION_TITLE", "FX_ACTION_PRIORITY", "FX_ACTION_DUE_DATE",
)


def _jsonable(v: Any) -> Any:
    if v is None:
        return None
    # numpy booleans subclass neither bool nor int, so they must be caught first;
    # otherwise they fall through to str() and a False becomes the truthy "False".
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (str, int)):
        return v
    if isinstance(v, (float, np.floating)):
        return None if pd.isna(v) else float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (date, datetime, pd.Timestamp)):
        return v.isoformat()
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    return str(v)


def frame_payload(df: pd.DataFrame, *, fields: Optional[Sequence[str]] = None,
                  max_rows: int = 3000, ref_date: Optional[str] = None) -> Dict[str, Any]:
    selected = [c for c in (fields or DEFAULT_FIELDS) if c in df.columns]
    if "KEY_EMP" in df.columns and "KEY_EMP" not in selected:
        selected.insert(0, "KEY_EMP")
    view = df[selected].head(max_rows).copy() if selected else df.head(max_rows).copy()
    records = [
        {str(k): _jsonable(v) for k, v in row.items()}
        for row in view.to_dict(orient="records")
    ]
    return {
        "ref_date": ref_date or date.today().isoformat(),
        "row_count": int(len(df)),
        "published_rows": int(len(records)),
        "truncated": bool(len(df) > len(records)),
        "columns": selected,
        "records": records,
    }


def publish_employee_snapshots(df: pd.DataFrame, *, employee_codes: Optional[Iterable[str]] = None,
                               fields: Optional[Sequence[str]] = None,
                               max_rows: int = 3000, source_run_id: str = "",
                               ref_date: Optional[str] = None) -> Dict[str, Any]:
    if "KEY_EMP" not in df.columns:
        raise ValueError("KEY_EMP برای ساخت Snapshot شخصی لازم است.")

    work = df.copy()
    work["KEY_EMP"] = work["KEY_EMP"].map(clean_employee_code)
    work = work[work["KEY_EMP"].astype(str).str.strip().ne("")]
    wanted = None
    if employee_codes is not None:
        wanted = {clean_employee_code(x) for x in employee_codes if clean_employee_code(x)}
        work = work[work["KEY_EMP"].isin(wanted)]

    published: Dict[str, int] = {}
    for emp, group in work.groupby("KEY_EMP", sort=True):
        store = EncryptedUserStore.from_master_env(emp)
        payload = frame_payload(group, fields=fields, max_rows=max_rows, ref_date=ref_date)
        store.replace_snapshot(payload, source_run_id=source_run_id)
        published[emp] = int(len(group))

    missing = sorted(wanted - set(published)) if wanted is not None else []
    return {"published": published, "missing": missing, "users": len(published), "rows": sum(published.values())}


def load_personal_frame(employee_code: str) -> pd.DataFrame:
    store = EncryptedUserStore.from_env(employee_code)
    snap = store.current_snapshot()
    records = snap.get("records", []) if isinstance(snap, dict) else []
    return pd.DataFrame(records)
