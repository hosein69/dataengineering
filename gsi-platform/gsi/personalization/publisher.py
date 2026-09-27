# -*- coding: utf-8 -*-
"""Publish per-employee encrypted snapshots to the shared profile folder.

The central GSI run writes only rows scoped to each employee. Personal clients
read these encrypted snapshots directly from the shared folder; they do not
connect back to the central process by IP/API.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, Optional, Sequence

import math
import numpy as np
import pandas as pd

from ..core.text import clean_employee_code
from .store import EncryptedUserStore
from .hr_scope import build_scopes, restrict_rows


DEFAULT_FIELDS = (
    "KEY_EMP", "KEY_REG", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_MATERIAL",
    "CANONICAL_EXPERT", "EXPERT_ROLE", "ORG_VICE", "ORG_DEPT",
    "ORG_MANAGER", "ORG_HEAD", "مرحله جاری", "انتظار جاری (روز)",
    "بحرانی (کوتاه)", "مقاومت (روز)", "مانع فعلی", "مانده تعهد", "روزهای تأخیر",
    "FX_CURRENT_STAGE", "FX_TIME_DAYS_LEFT", "FX_EVIDENCE_COVERAGE",
    "SUPPLIER_OPEN_QTY", "IN_TRANSIT_QTY", "IN_CUSTOMS_QTY",
    "ORACLE_IKCO_QTY", "ORACLE_SAPCO_QTY", "SUPPLY_POSITION_COVERAGE",
    "NEXT_ACTION_TITLE", "NEXT_ACTION_PRIORITY", "NEXT_ACTION_DUE_DATE", "NEXT_ACTION_OWNER", "NEXT_ACTION_ID", "کد طبقه بحرانی",
    "FX_ACTION_TITLE", "FX_ACTION_PRIORITY", "FX_ACTION_DUE_DATE",
)


def _jsonable(v: Any) -> Any:
    if v is None or v is pd.NaT or v is pd.NA:
        return None
    # numpy booleans subclass neither bool nor int, so they must be caught first;
    # otherwise they fall through to str() and a False becomes the truthy "False".
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (str, int)):
        return v
    if isinstance(v, (float, np.floating)):
        return None if not math.isfinite(float(v)) else float(v)
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
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1:
        raise ValueError("max_rows must be a positive integer")
    if fields is not None and (not fields or isinstance(fields, str)):
        raise ValueError("fields must be a nonempty sequence")
    selected = [c for c in (DEFAULT_FIELDS if fields is None else fields) if c in df.columns]
    if "KEY_EMP" in df.columns and "KEY_EMP" not in selected:
        selected.insert(0, "KEY_EMP")
    view = df[selected].head(max_rows).copy()
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
                               ref_date: Optional[str] = None,
                               hr_frame: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    if "KEY_EMP" not in df.columns:
        raise ValueError("KEY_EMP برای ساخت Snapshot شخصی لازم است.")

    work = df.copy()
    work["KEY_EMP"] = work["KEY_EMP"].map(clean_employee_code)
    work = work[work["KEY_EMP"].astype(str).str.strip().ne("")]
    wanted = None
    if employee_codes is not None:
        if isinstance(employee_codes, str):
            raise ValueError("employee_codes must be a sequence, not a string")
        wanted = {clean_employee_code(x) for x in employee_codes if clean_employee_code(x)}
        if hr_frame is None:
            work = work[work["KEY_EMP"].isin(wanted)]

    scopes = build_scopes(hr_frame) if hr_frame is not None else None
    if scopes is not None:
        target_codes = sorted(wanted if wanted is not None else scopes)
        invalid = set(target_codes) - set(scopes)
        if invalid:
            raise ValueError("هویت فعال و یکتای HR برای این کدها پیدا نشد: " + ", ".join(sorted(invalid)))
        groups = [(emp, restrict_rows(work, scopes[emp])) for emp in target_codes]
    else:
        groups = list(work.groupby("KEY_EMP", sort=True))
    published: Dict[str, int] = {}
    for emp, group in groups:
        store = EncryptedUserStore.from_master_env(emp)
        payload = frame_payload(group, fields=fields, max_rows=max_rows, ref_date=ref_date)
        if scopes is not None:
            s = scopes[emp]
            payload["hr_scope"] = {"level": s.level, "label": {"expert": "کارشناس", "head": "رئیس", "manager": "مدیر", "vice": "معاون"}[s.level],
                                   "name": s.name, "organization": s.organization,
                                   "member_count": len(s.member_codes)}
        store.replace_snapshot(payload, source_run_id=source_run_id)
        published[emp] = int(len(group))

    missing = sorted(wanted - set(published)) if wanted is not None else []
    for emp in missing:
        store = EncryptedUserStore.from_master_env(emp)
        store.replace_snapshot(frame_payload(work.iloc[:0], fields=fields, max_rows=max_rows, ref_date=ref_date), source_run_id=source_run_id)
        published[emp] = 0
    return {"published": published, "missing": missing, "users": len(published), "rows": sum(published.values())}


def load_personal_frame(employee_code: str) -> pd.DataFrame:
    store = EncryptedUserStore.from_env(employee_code)
    snap = store.current_snapshot()
    records = snap.get("records", []) if isinstance(snap, dict) else []
    return pd.DataFrame(records)
