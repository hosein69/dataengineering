# -*- coding: utf-8 -*-
"""Evidence-preserving end-to-end process model.

V29.7.5 introduces a process ledger that is deliberately independent from the
flattened report population.  Every native source observation is preserved, and
process state is *projected* from evidence rather than replacing evidence.

Design rules:
- No fuzzy joins.  Cases are connected only by direct co-observed business keys.
- Later evidence never deletes an earlier/missing/bad state.  Missing predecessor
  stages become explicit EVIDENCE_GAP rows while later observations stay visible.
- SAP history is consumed at row grain when available (``workflow_rows``); a
  future richer SAP export therefore extends the graph without changing the
  contracts used by the existing report.
- Ambiguous links are not guessed.  Flat-report rows that match more than one
  process component are marked AMBIGUOUS_LINK while all components remain in the
  process inventory.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Any, Dict, Iterable, Mapping

import pandas as pd

from ..adapters.base import KEY_BL, KEY_EMP, KEY_MATERIAL, KEY_ORDER, KEY_PR, KEY_PO, KEY_REG, KEY_REG_FILE
from ..core.text import clean_key, clean_order_ref, clean_part_no, is_empty_val

ENTITY_COLS = {
    "PR": KEY_PR,
    "PO": KEY_PO,
    "ORDER": KEY_ORDER,
    "REG": KEY_REG,
    "REG_FILE": KEY_REG_FILE,
    "BL": KEY_BL,
    "MATERIAL": KEY_MATERIAL,
    "EMP": KEY_EMP,
}

# Explicit process sequence.  This is a control view, not a claim that every
# business case must use every stage.  A later observation with an absent earlier
# stage is therefore a visible evidence gap, never a reason to suppress the later fact.
STAGES = (
    ("PLANNING_PR", "ایجاد درخواست خرید / برنامه‌ریزی", "PLANNING"),
    ("EXPERT_INTAKE", "ورود به فایل کارشناسان", "COMMERCIAL"),
    ("ORDER_CREATED", "ایجاد سفارش", "COMMERCIAL"),
    ("REGISTRATION", "ثبت سفارش", "REGISTRATION"),
    ("ALLOCATION_REQUEST", "درخواست تخصیص", "FX_ALLOCATION"),
    ("ALLOCATION", "تخصیص ارز", "FX_ALLOCATION"),
    ("COMMITMENT", "تعهد ارزی", "FX_COMMITMENT"),
    ("FX_PURCHASE", "خرید ارز", "TREASURY"),
    ("FUNDING", "تأمین وجه", "TREASURY"),
    # SWIFT is an outgoing instruction, not proof that the beneficiary was paid.
    # It is a registered stage so the evidence stays visible in the matrix; emitting
    # it without registration silently dropped it from every case projection.
    ("SWIFT_SENT", "ارسال سوئیفت", "TREASURY"),
    ("PAYMENT", "پرداخت / وصول ذی‌نفع", "TREASURY"),
    ("SHIPMENT", "حمل", "LOGISTICS"),
    ("CUSTOMS", "اظهار / کوتاژ", "CUSTOMS"),
    ("CLEARANCE", "ترخیص", "CUSTOMS"),
    ("BANK_DOCS", "ارائه/تطبیق اسناد بانکی", "CREDIT"),
    ("SETTLEMENT", "رفع / برگشت تعهد", "FX_COMMITMENT"),
)
_STAGE_POS = {code: i for i, (code, _, _) in enumerate(STAGES)}
_STAGE_OWNER = {code: owner for code, _, owner in STAGES}
_STAGE_FA = {code: fa for code, fa, _ in STAGES}

SOURCE_REG_ALIAS = {
    "ntsw": "NTSW_KEY_REG",
    "sata": "SATA_KEY_REG",
    "fx_transaction": "FX_KEY_REG",
    "credit": "CRD_KEY_REG",
    "ilappend": "IL_KEY_REG",
}


def _s(v: Any) -> str:
    if is_empty_val(v):
        return ""
    return str(v).strip()


def _date_first(row: Mapping[str, Any], cols: Iterable[str]) -> str:
    for c in cols:
        v = _s(row.get(c))
        if v:
            return v
    return ""


def _keys(source: str, row: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for typ, col in ENTITY_COLS.items():
        v = row.get(col, "")
        if typ == "ORDER": v = clean_order_ref(v)
        elif typ == "MATERIAL": v = clean_part_no(v)
        else: v = clean_key(v)
        if v:
            out[typ] = v
    alias = SOURCE_REG_ALIAS.get(source)
    if alias and not out.get("REG"):
        v = clean_key(row.get(alias, ""))
        if v:
            out["REG"] = v
    return out


def _row_ref(source: str, frame: str, idx: int, row: Mapping[str, Any]) -> str:
    cached = row.get("__GSI_ROW_REF") if hasattr(row, "get") else None
    if cached:
        return str(cached)
    # Prefer immutable physical lineage over hashing every cell of a wide row.
    # SAP row numbers restart per sheet, hence sheet+row (plus file when present).
    file_id = (_s(row.get("_SOURCE_FILE_ID")) or _s(row.get("_SOURCE_FILE")) or
               _s(row.get("SAP_SOURCE_FILE_ID")) or _s(row.get("SAP_SOURCE_FILE")))
    sheet = _s(row.get("SAP_SOURCE_SHEET")) or _s(row.get("_SOURCE_SHEET"))
    row_no = _s(row.get("SAP_SOURCE_ROW")) or _s(row.get("_SOURCE_ROW"))
    if sheet and row_no:
        token = f"{file_id}|{sheet}|{row_no}"
        return f"{source}/physical:{sha1(token.encode('utf-8')).hexdigest()[:20]}"
    raw = "|".join(f"{k}={_s(v)}" for k, v in sorted(row.items()) if not str(k).startswith("__GSI_") and _s(v))
    return f"{source}/{frame}:{idx+1}:{sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _state_from_text(v: Any) -> str:
    """Conservative source-status classifier; the raw value is always retained."""
    s = _s(v).lower()
    if not s:
        return "OBSERVED"
    negative = ("cancel", "reject", "rework", "fail", "ابطال", "لغو", "رد", "ناموفق", "متوقف")
    positive = ("complete", "approved", "done", "closed", "success", "تایید", "تأیید", "تکمیل", "مختومه", "انجام")
    import re
    if any(x in s for x in ("نشده", "عدم", "not approved", "not completed", "بازگشت داده")):
        return "NEGATIVE_OBSERVED"
    if any(re.search(r"(?<!\w)" + re.escape(x) + r"(?!\w)", s) for x in negative):
        return "NEGATIVE_OBSERVED"
    if any(x in s for x in positive):
        return "POSITIVE_OBSERVED"
    return "OBSERVED"


def _emit(rows: list[dict], source: str, frame: str, idx: int, raw: Mapping[str, Any],
          stage: str, *, event_date: str = "", status: Any = "", detail: str = "") -> None:
    keys = _keys(source, raw)
    if not keys:
        return
    rows.append({
        "OBSERVATION_ID": _row_ref(source, frame, idx, raw) + f":{stage}",
        "SOURCE": source,
        "FRAME": frame,
        "SOURCE_ROW_REF": _row_ref(source, frame, idx, raw),
        "STAGE_CODE": stage,
        "STAGE_FA": _STAGE_FA.get(stage, stage),
        "OWNER_DOMAIN": _STAGE_OWNER.get(stage, ""),
        "EVENT_DATE": event_date,
        "OBSERVED_STATUS": _s(status),
        "EVIDENCE_STATE": _state_from_text(status),
        "DETAIL": detail,
        **{f"KEY_{k}": v for k, v in keys.items()},
    })


def source_observation_inventory(sources: Mapping[str, Mapping[str, pd.DataFrame]]) -> dict[str, Any]:
    """Inventory the *physical* source-row references expected in process evidence.

    Several adapters expose both native/history frames and semantic projections of
    the same physical rows.  Counting ``len(frame)`` across every projection makes
    row-preservation fail whenever a physical row legitimately appears in more than
    one semantic frame.  Process evidence itself deduplicates by ``SOURCE_ROW_REF``;
    the expectation must use that same physical identity contract.

    This function is intentionally independent from the produced observation table:
    it scans source frames and computes the expected unique physical references, so
    a missing SOURCE_OBSERVATION can still be detected.  Collisions are reported for
    diagnostics instead of silently treated as extra rows.
    """
    refs: set[str] = set()
    by_source: dict[str, set[str]] = {}
    by_frame_rows: dict[str, int] = {}
    duplicate_refs: dict[str, int] = {}
    candidates = 0
    for source, frames in (sources or {}).items():
        sap_raw = ((frames or {}).get("raw_rows") if source == "sap" else None)
        sap_has_raw = isinstance(sap_raw, pd.DataFrame) and not sap_raw.empty
        for frame, df in (frames or {}).items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            # Keep this eligibility contract in lock-step with _observations().
            if source == "sap" and sap_has_raw and frame not in {"raw_rows", "pr_items", "workflow_rows"}:
                continue
            if source == "sap" and frame == "main" and isinstance(frames.get("workflow_rows"), pd.DataFrame) and not frames["workflow_rows"].empty:
                continue
            generic = not (source == "sap" and sap_has_raw and frame != "raw_rows")
            if not generic:
                continue
            cols = list(df.columns)
            key = f"{source}/{frame}"
            by_frame_rows[key] = int(len(df))
            src_refs = by_source.setdefault(source, set())
            for idx, values in enumerate(df.itertuples(index=False, name=None)):
                raw = dict(zip(cols, values))
                ref = _row_ref(source, frame, idx, raw)
                candidates += 1
                if ref in refs:
                    duplicate_refs[ref] = duplicate_refs.get(ref, 1) + 1
                refs.add(ref)
                src_refs.add(ref)
    return {
        "unique_refs": refs,
        "expected_unique_rows": int(len(refs)),
        "candidate_frame_rows": int(candidates),
        "by_source_unique": {k: len(v) for k, v in sorted(by_source.items())},
        "by_frame_rows": by_frame_rows,
        "duplicate_ref_count": int(len(duplicate_refs)),
        "duplicate_ref_rows": int(sum(v - 1 for v in duplicate_refs.values())),
        "duplicate_ref_sample": sorted(duplicate_refs)[:12],
    }


def _observations(sources: Mapping[str, Mapping[str, pd.DataFrame]]) -> pd.DataFrame:
    rows: list[dict] = []
    for source, frames in sources.items():
        sap_raw = ((frames or {}).get("raw_rows") if source == "sap" else None)
        sap_has_raw = isinstance(sap_raw, pd.DataFrame) and not sap_raw.empty
        for frame, df in (frames or {}).items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            # raw_rows is the physical SAP archive. Semantic PR/PO/workflow/GR frames
            # are projections of those same physical rows and must not be counted a
            # second time as native SOURCE_OBSERVATION evidence. Only PR/workflow
            # projections still need a pass because they emit process-stage evidence.
            if source == "sap" and sap_has_raw and frame not in {"raw_rows", "pr_items", "workflow_rows"}:
                continue
            if source == "sap" and frame == "main" and isinstance(frames.get("workflow_rows"), pd.DataFrame) and not frames["workflow_rows"].empty:
                continue
            generic_source_observation = not (source == "sap" and sap_has_raw and frame != "raw_rows")
            cols = list(df.columns)
            for idx, values in enumerate(df.itertuples(index=False, name=None)):
                raw = dict(zip(cols, values))
                keys = _keys(source, raw)
                ref = _row_ref(source, frame, idx, raw)
                raw["__GSI_ROW_REF"] = ref
                if generic_source_observation:
                    # Generic trace row guarantees that every physical source row is
                    # visible. Keyless rows remain explicit orphans, never disappear.
                    rows.append({
                        "OBSERVATION_ID": ref + ":SOURCE_OBSERVATION",
                        "SOURCE": source, "FRAME": frame, "SOURCE_ROW_REF": ref,
                        "STAGE_CODE": "SOURCE_OBSERVATION", "STAGE_FA": "شاهد منبع", "OWNER_DOMAIN": "",
                        "EVENT_DATE": "", "OBSERVED_STATUS": "",
                        "EVIDENCE_STATE": "OBSERVED" if keys else "ORPHAN_NO_BUSINESS_KEY",
                        "DETAIL": "native source row preserved" if keys else "native row preserved but no attachable business key",
                        **{f"KEY_{k}": v for k, v in keys.items()},
                    })

                if source == "sap":
                    # SAP has several semantic frames. Only PR/workflow evidence
                    # should advance the planning stage; PO/raw semantic copies are
                    # still preserved by SOURCE_OBSERVATION but do not double-count
                    # the stage timeline.
                    if frame in {"pr_items", "workflow_rows"}:
                        _emit(rows, source, frame, idx, raw, "PLANNING_PR",
                              event_date=_date_first(raw, ["SAP_CHANGED_ON_ISO", "SAP_RELEASE_DATE_ISO",
                                                           "SAP_COMMISSION_DATE_ISO", "SAP_REQUISITION_DATE_ISO",
                                                           "SAP_CHANGED_ON", "SAP_COMMISSION_DATE"]),
                              status=(raw.get("SAP_PROCESSING_STATUS") or raw.get("SAP_OVERALL_RELEASE") or
                                      raw.get("SAP_PACK_PACKED")),
                              detail=("PR item=" + _s(raw.get("SAP_PR_ITEM")) +
                                      ("; workflow=" + _s(raw.get("SAP_WORKFLOW_ID")) if _s(raw.get("SAP_WORKFLOW_ID")) else "")))
                elif source == "moghavemat":
                    _emit(rows, source, frame, idx, raw, "EXPERT_INTAKE",
                          event_date=_date_first(raw, ["MOGH_PO_SENT_DATE", "MOGH_CREATE_DATE"]),
                          status=raw.get("MOGH_STATUS"), detail="Commercial Expert evidence")
                    if keys.get("ORDER"):
                        _emit(rows, source, frame, idx, raw, "ORDER_CREATED",
                              event_date=_date_first(raw, ["MOGH_PO_SENT_DATE", "MOGH_ORDER_DATE"]), status=raw.get("MOGH_STATUS"))
                elif source == "ntsw":
                    if frame == "import_license":
                        _emit(rows, source, frame, idx, raw, "REGISTRATION",
                              event_date=_date_first(raw, ["NTSW_REG_DATE", "NTSW_ISSUE_DATE"]), status=raw.get("NTSW_STATUS"))
                    elif frame in {"allocation_rows", "allocation"}:
                        _emit(rows, source, frame, idx, raw, "ALLOCATION_REQUEST",
                              event_date=_date_first(raw, ["NTSW_REQ_DATE", "NTSW_QUEUE_ENTER_DATE"]),
                              status=raw.get("NTSW_REQUEST_STATE") or raw.get("NTSW_ALLOC_STATUS"))
                        state = _s(raw.get("NTSW_REQUEST_STATE")).upper()
                        allocated_amount = 0.0
                        if not is_empty_val(raw.get("NTSW_ALLOCATED_AMOUNT")):
                            try:
                                allocated_amount = float(raw.get("NTSW_ALLOCATED_AMOUNT"))
                            except Exception:
                                allocated_amount = 0.0
                        allocated = (state == "ALLOCATED" or (not state and (bool(_s(raw.get("NTSW_ALLOC_DATE"))) or allocated_amount > 0)))
                        if allocated:
                            _emit(rows, source, frame, idx, raw, "ALLOCATION",
                                  event_date=_date_first(raw, ["NTSW_ALLOC_DATE"]), status=raw.get("NTSW_REQUEST_STATE") or raw.get("NTSW_ALLOC_STATUS"))
                    elif frame == "commitment":
                        _emit(rows, source, frame, idx, raw, "COMMITMENT",
                              event_date=_date_first(raw, ["NTSW_COMMIT_DATE"]), status=raw.get("NTSW_COMMIT_STATUS") or raw.get("NTSW_RELEASE_STATUS"))
                        # Settlement remains an observation only when source status
                        # explicitly says released/settled or balance is exactly zero.
                        rel = _s(raw.get("NTSW_RELEASE_STATUS"))
                        bal = raw.get("NTSW_BALANCE")
                        zero = False
                        try: zero = (not is_empty_val(bal) and float(bal) == 0)
                        except Exception: zero = False
                        if rel.strip().lower() in {"رفع تعهد شده", "رفع تعهد کامل", "settled", "released"}:
                            _emit(rows, source, frame, idx, raw, "SETTLEMENT",
                                  event_date=_date_first(raw, ["NTSW_RELEASE_DATE"]), status=rel,
                                  detail="NTSW settlement/balance observation; not a synthetic cash event")
                elif source == "fx_transaction":
                    if _s(raw.get("FX_PURCHASE_STATE")) != "PLANNED" and (_s(raw.get("FX_BUY_DATE")) or not is_empty_val(raw.get("FX_AMOUNT"))):
                        _emit(rows, source, frame, idx, raw, "FX_PURCHASE", event_date=_s(raw.get("FX_BUY_DATE")), status=raw.get("FX_STATUS"))
                    if _s(raw.get("FX_RECEIPT_DATE")) or not is_empty_val(raw.get("FX_PAID_AMOUNT")):
                        _emit(rows, source, frame, idx, raw, "PAYMENT", event_date=_date_first(raw, ["FX_RECEIPT_DATE"]), status=raw.get("FX_STATUS"))
                elif source == "credit":
                    if _s(raw.get("CRD_FUND_DATE")):
                        _emit(rows, source, frame, idx, raw, "FUNDING", event_date=_s(raw.get("CRD_FUND_DATE")), status=raw.get("CRD_LAST_STATUS") or raw.get("CRD_STATUS"))
                    if _s(raw.get("CRD_SWIFT_DATE")):
                        _emit(rows, source, frame, idx, raw, "SWIFT_SENT", event_date=_s(raw.get("CRD_SWIFT_DATE")), status=raw.get("CRD_LAST_STATUS") or raw.get("CRD_STATUS"), detail="SWIFT evidence")
                elif source in {"abbasi", "sata"}:
                    if keys.get("BL"):
                        _emit(rows, source, frame, idx, raw, "SHIPMENT",
                              event_date=_date_first(raw, ["BL_DISCHARGE_DATE", "SATA_TRACKING_DATE"]),
                              status=raw.get("BL_STATUS") or raw.get("SATA_CREDIT_STATUS"))
                elif source == "cotage":
                    if _s(raw.get("COT_NO")) or _s(raw.get("COT_COTAGE_DATE")):
                        _emit(rows, source, frame, idx, raw, "CUSTOMS", event_date=_s(raw.get("COT_COTAGE_DATE")), status=raw.get("COT_STATUS"))
                    if _s(raw.get("COT_FULL_CLEAR_DATE")):
                        _emit(rows, source, frame, idx, raw, "CLEARANCE", event_date=_s(raw.get("COT_FULL_CLEAR_DATE")), status=raw.get("COT_STATUS"))
                elif source == "clearance":
                    if _s(raw.get("CL_COTAGE_NO")) or _s(raw.get("CL_COTAGE_DATE")):
                        _emit(rows, source, frame, idx, raw, "CUSTOMS", event_date=_s(raw.get("CL_COTAGE_DATE")), status=raw.get("CL_NOTE"))
                    if bool(raw.get("CL_IS_FULL", False)) or _s(raw.get("CL_CLEAR_DATE")):
                        _emit(rows, source, frame, idx, raw, "CLEARANCE", event_date=_s(raw.get("CL_CLEAR_DATE")), status="FULL" if bool(raw.get("CL_IS_FULL", False)) else raw.get("CL_NOTE"), detail="done without date" if bool(raw.get("CL_CLEAR_DONE_NO_DATE", False)) else "")
                elif source == "doccheck":
                    _emit(rows, source, frame, idx, raw, "BANK_DOCS", event_date=_s(raw.get("DOC_SUBMIT_DATE")), status=raw.get("DOC_STATUS"), detail=_s(raw.get("DOC_DISCREPANCY")))
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    # Stable column presence for downstream persistence/reporting.
    for typ in ENTITY_COLS:
        c = f"KEY_{typ}"
        if c not in out: out[c] = ""
    return out.drop_duplicates(subset=["OBSERVATION_ID"], keep="first").reset_index(drop=True)


class _UF:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        if self.p[x] != x: self.p[x] = self.find(self.p[x])
        return self.p[x]
    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b: self.p[b] = a


def _components(obs: pd.DataFrame, unmeasured_stages: set[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if obs.empty:
        return pd.DataFrame(), pd.DataFrame()
    unmeasured_stages = set(unmeasured_stages or set())
    uf = _UF()
    key_cols = [f"KEY_{x}" for x in ENTITY_COLS if x not in {"MATERIAL", "EMP"}]
    row_nodes: list[list[str]] = []
    for _, r in obs.iterrows():
        nodes = [f"{c[4:]}:{_s(r.get(c))}" for c in key_cols if _s(r.get(c))]
        row_nodes.append(nodes)
        for n in nodes[1:]: uf.union(nodes[0], n)
        if nodes: uf.find(nodes[0])
    # Map roots to deterministic IDs based on all keys in component.
    groups: Dict[str, set[str]] = {}
    for node in list(uf.p): groups.setdefault(uf.find(node), set()).add(node)
    case_id = {root: "PC-" + sha1("|".join(sorted(nodes)).encode("utf-8")).hexdigest()[:14].upper() for root, nodes in groups.items()}
    case_for_node = {node: case_id[uf.find(node)] for node in uf.p}
    obs = obs.copy()
    obs["PROCESS_CASE_ID"] = [case_for_node.get(nodes[0], "") if nodes else "" for nodes in row_nodes]

    rows = []
    for cid, g in obs[obs["PROCESS_CASE_ID"].ne("")].groupby("PROCESS_CASE_ID", sort=False):
        stage_obs = g[g["STAGE_CODE"].isin(_STAGE_POS)]
        observed = set(stage_obs["STAGE_CODE"])
        furthest = max((_STAGE_POS[s] for s in observed), default=-1)
        missing_before = [STAGES[i][0] for i in range(furthest) if STAGES[i][0] not in observed]
        gaps = [x for x in missing_before if x not in unmeasured_stages]
        unmeasured = [x for x in missing_before if x in unmeasured_stages]
        if gaps:
            focus = gaps[0]
            status = "EVIDENCE_GAP"
        elif furthest + 1 < len(STAGES):
            focus = STAGES[furthest + 1][0]
            status = "SOURCE_COVERAGE_GAP" if focus in unmeasured_stages else ("IN_PROGRESS" if furthest >= 0 else "NO_STAGE_EVIDENCE")
        else:
            focus = STAGES[-1][0]
            status = "COMPLETE_EVIDENCE_CHAIN"
        # Negative source observations are never hidden by a later positive row.
        neg = stage_obs[stage_obs["EVIDENCE_STATE"].eq("NEGATIVE_OBSERVED")]
        if not neg.empty:
            status = "NEGATIVE_EVIDENCE_PRESENT" if not gaps else "EVIDENCE_GAP+NEGATIVE"
        ids = {}
        for typ in ENTITY_COLS:
            vals = sorted({_s(x) for x in g[f"KEY_{typ}"] if _s(x)})
            ids[f"{typ}_KEYS"] = " | ".join(vals)
            ids[f"{typ}_COUNT"] = len(vals)
        dates = [_s(x) for x in stage_obs["EVENT_DATE"] if _s(x)]
        rows.append({
            "PROCESS_CASE_ID": cid,
            "PROCESS_STATUS": status,
            "CURRENT_FOCUS_STAGE": focus,
            "CURRENT_FOCUS_STAGE_FA": _STAGE_FA.get(focus, focus),
            "CURRENT_OWNER": _STAGE_OWNER.get(focus, ""),
            "EVIDENCE_GAPS": " | ".join(gaps),
            "UNMEASURED_STAGES": " | ".join(unmeasured),
            "EVIDENCE_COUNT": int(len(g)),
            "STAGE_EVIDENCE_COUNT": int(len(stage_obs)),
            "NEGATIVE_EVIDENCE_COUNT": int(len(neg)),
            "LAST_EVIDENCE_DATE": max(dates) if dates else "",
            **ids,
        })
    return obs, pd.DataFrame(rows)


def _stage_matrix(obs: pd.DataFrame, cases: pd.DataFrame, unmeasured_stages: set[str] | None = None) -> pd.DataFrame:
    """Vectorized case × stage projection.

    The old implementation appended ~16 Python dicts per case. At ~79k cases
    that meant ~1.26M Python-loop iterations. This version builds the same grid
    with a cross join and merges the much smaller observed-stage aggregate.
    """
    if cases.empty:
        return pd.DataFrame()
    unmeasured_stages = set(unmeasured_stages or set())
    stage_catalog = pd.DataFrame([
        {"STAGE_ORDER": pos + 1, "STAGE_POS": pos, "STAGE_CODE": code,
         "STAGE_FA": fa, "OWNER_DOMAIN": owner}
        for pos, (code, fa, owner) in enumerate(STAGES)
    ])
    case_ids = cases[["PROCESS_CASE_ID"]].drop_duplicates().copy()
    case_ids["__K"] = 1; stage_catalog["__K"] = 1
    grid = case_ids.merge(stage_catalog, on="__K", how="inner").drop(columns="__K")

    stage_obs = obs[obs["STAGE_CODE"].isin(_STAGE_POS)].copy()
    if stage_obs.empty:
        agg = pd.DataFrame(columns=["PROCESS_CASE_ID", "STAGE_CODE", "OBSERVATION_COUNT"])
        furthest = pd.Series(dtype=float)
    else:
        stage_obs["__POS"] = stage_obs["STAGE_CODE"].map(_STAGE_POS)
        furthest = stage_obs.groupby("PROCESS_CASE_ID", sort=False)["__POS"].max()
        stage_obs["__NEG"] = stage_obs["EVIDENCE_STATE"].eq("NEGATIVE_OBSERVED")
        stage_obs["__POSITIVE"] = stage_obs["EVIDENCE_STATE"].eq("POSITIVE_OBSERVED")
        status_norm = stage_obs["OBSERVED_STATUS"].map(_s).str.lower()
        stage_obs["__COMPLETE"] = status_norm.isin({"completed", "done", "تکمیل شده"})
        stage_obs["__FAILED"] = status_norm.isin({"failed", "failure", "ناموفق"})
        def _join_unique(series):
            return " | ".join(sorted({_s(x) for x in series if _s(x)}))
        agg = (stage_obs.groupby(["PROCESS_CASE_ID", "STAGE_CODE"], sort=False, dropna=False)
               .agg(OBSERVATION_COUNT=("STAGE_CODE", "size"),
                    HAS_NEG=("__NEG", "any"), HAS_POS=("__POSITIVE", "any"),
                    HAS_COMPLETE=("__COMPLETE", "any"), HAS_FAILED=("__FAILED", "any"),
                    SOURCE_LIST=("SOURCE", _join_unique),
                    RAW_STATUS_LIST=("OBSERVED_STATUS", _join_unique),
                    EVENT_DATES=("EVENT_DATE", _join_unique))
               .reset_index())
    grid = grid.merge(agg, on=["PROCESS_CASE_ID", "STAGE_CODE"], how="left")
    grid["OBSERVATION_COUNT"] = pd.to_numeric(grid["OBSERVATION_COUNT"], errors="coerce").fillna(0).astype(int)
    for c in ("HAS_NEG", "HAS_POS", "HAS_COMPLETE", "HAS_FAILED"):
        if c not in grid.columns:
            grid[c] = False
        else:
            grid[c] = grid[c].eq(True)
    for c in ("SOURCE_LIST", "RAW_STATUS_LIST", "EVENT_DATES"):
        if c not in grid.columns:
            grid[c] = ""
        else:
            grid[c] = grid[c].fillna("")
    grid["FURTHEST"] = grid["PROCESS_CASE_ID"].map(furthest).fillna(-1).astype(int)
    grid["HAS_OBS"] = grid["OBSERVATION_COUNT"].gt(0)
    grid["UNMEASURED"] = grid["STAGE_CODE"].isin(unmeasured_stages)

    import numpy as np
    grid["STATUS"] = np.select(
        [grid["HAS_OBS"] & grid["HAS_NEG"],
         grid["HAS_OBS"] & ~grid["HAS_NEG"] & grid["HAS_POS"],
         grid["HAS_OBS"],
         ~grid["HAS_OBS"] & grid["UNMEASURED"],
         ~grid["HAS_OBS"] & ~grid["UNMEASURED"] & (grid["STAGE_POS"] < grid["FURTHEST"]),
         ~grid["HAS_OBS"] & ~grid["UNMEASURED"] & (grid["STAGE_POS"] == grid["FURTHEST"] + 1)],
        ["NEGATIVE_OBSERVED", "POSITIVE_OBSERVED", "OBSERVED", "NOT_MEASURED", "EVIDENCE_GAP", "CURRENT_FOCUS"],
        default="PENDING")
    grid["EVIDENCE_STATE"] = np.select(
        [grid["HAS_OBS"], grid["UNMEASURED"], grid["STAGE_POS"] < grid["FURTHEST"]],
        ["OBSERVED", "NOT_MEASURED", "EVIDENCE_GAP"], default="NOT_OBSERVED")
    grid["COVERAGE_STATE"] = np.where(grid["UNMEASURED"], "SOURCE_COVERAGE_GAP", "MEASURED")
    grid["COMPLETION_STATE"] = np.where(grid["HAS_OBS"] & grid["HAS_COMPLETE"], "COMPLETED", "NOT_OBSERVED")
    grid["EXECUTION_STATE"] = np.where(grid["HAS_OBS"] & grid["HAS_FAILED"], "FAILED", "NOT_OBSERVED")
    grid["RELATION_STATE"] = np.where(grid["HAS_OBS"] & grid["HAS_NEG"] & grid["HAS_POS"], "AMBIGUOUS", "NOT_OBSERVED")
    return grid[["PROCESS_CASE_ID", "STAGE_ORDER", "STAGE_CODE", "STAGE_FA", "OWNER_DOMAIN",
                 "STATUS", "EVIDENCE_STATE", "COVERAGE_STATE", "COMPLETION_STATE",
                 "EXECUTION_STATE", "RELATION_STATE", "OBSERVATION_COUNT", "SOURCE_LIST",
                 "RAW_STATUS_LIST", "EVENT_DATES"]].reset_index(drop=True)


def build_process_inventory(sources: Mapping[str, Mapping[str, pd.DataFrame]], unmeasured_stages: set[str] | None = None):
    obs = _observations(sources)
    obs, cases = _components(obs, unmeasured_stages=unmeasured_stages)
    matrix = _stage_matrix(obs, cases, unmeasured_stages=unmeasured_stages)
    return obs, cases, matrix


def attach_process_state(df: pd.DataFrame, observations: pd.DataFrame, cases: pd.DataFrame) -> pd.DataFrame:
    """Attach unambiguous process projection to flat rows without changing row count.

    The business rule is priority based: REG, then ORDER, PR, BL.  A stronger
    key that resolves to multiple process components must remain ambiguous; we
    never intersect it with a weaker key to manufacture a unique answer.  The
    previous implementation applied this rule row-by-row with thousands of
    scalar ``DataFrame.at`` writes.  This vectorized projection preserves the
    same rule while making large real snapshots practical.
    """
    out = df.copy()
    defaults = {
        "PROCESS_CASE_ID": "", "PROCESS_CASE_COUNT": 0, "PROCESS_STATUS": "",
        "PROCESS_CURRENT_STAGE": "", "PROCESS_CURRENT_OWNER": "", "PROCESS_GAPS": "",
        "PROCESS_LAST_EVIDENCE_DATE": "", "PROCESS_EVIDENCE_COUNT": 0,
    }
    for c, default in defaults.items():
        out[c] = default
    if observations.empty or cases.empty or out.empty:
        return out

    # value -> tuple(case ids), materialized once per entity type.  Tuples make
    # the mapping stable/hashable and avoid constructing a set for every report row.
    lookup: Dict[str, Dict[str, tuple[str, ...]]] = {}
    for typ in ENTITY_COLS:
        c = f"KEY_{typ}"
        if c not in observations.columns:
            continue
        z = observations.loc[observations[c].map(_s).ne(""), [c, "PROCESS_CASE_ID"]].copy()
        if z.empty:
            lookup[typ] = {}
            continue
        z[c] = z[c].map(_s)
        z["PROCESS_CASE_ID"] = z["PROCESS_CASE_ID"].map(_s)
        z = z[z["PROCESS_CASE_ID"].ne("")]
        lookup[typ] = {
            str(value): tuple(sorted(set(g["PROCESS_CASE_ID"])))
            for value, g in z.groupby(c, sort=False)
        }

    def _prefer(primary: str, fallback: str) -> pd.Series:
        a = out[primary].map(_s) if primary in out.columns else pd.Series("", index=out.index, dtype=object)
        if fallback in out.columns:
            b = out[fallback].map(_s)
            a = a.where(a.ne(""), b)
        return a

    probes = [
        ("REG", _prefer("CANONICAL_REG", KEY_REG)),
        ("ORDER", _prefer("CANONICAL_ORDER", KEY_ORDER)),
        ("PR", out[KEY_PR].map(_s) if KEY_PR in out.columns else pd.Series("", index=out.index, dtype=object)),
        ("BL", _prefer("CANONICAL_BL", KEY_BL)),
    ]

    chosen = pd.Series([()] * len(out), index=out.index, dtype=object)
    unresolved = pd.Series(True, index=out.index)
    for typ, values in probes:
        table = lookup.get(typ, {})
        if not table or not unresolved.any():
            continue
        mapped = values.map(table)
        has = unresolved & mapped.map(lambda x: isinstance(x, tuple) and len(x) > 0)
        if has.any():
            chosen.loc[has] = mapped.loc[has]
            unresolved.loc[has] = False

    counts = chosen.map(len).astype(int)
    out["PROCESS_CASE_COUNT"] = counts
    ambiguous = counts.gt(1)
    out.loc[ambiguous, "PROCESS_STATUS"] = "AMBIGUOUS_LINK"
    out.loc[ambiguous, "PROCESS_GAPS"] = "MULTIPLE_PROCESS_CASES"

    unique = counts.eq(1)
    if not unique.any():
        return out
    cids = chosen.loc[unique].map(lambda x: x[0])
    case_map = cases.drop_duplicates("PROCESS_CASE_ID").set_index("PROCESS_CASE_ID")
    projections = {
        "PROCESS_CASE_ID": None,
        "PROCESS_STATUS": "PROCESS_STATUS",
        "PROCESS_CURRENT_STAGE": "CURRENT_FOCUS_STAGE",
        "PROCESS_CURRENT_OWNER": "CURRENT_OWNER",
        "PROCESS_GAPS": "EVIDENCE_GAPS",
        "PROCESS_LAST_EVIDENCE_DATE": "LAST_EVIDENCE_DATE",
        "PROCESS_EVIDENCE_COUNT": "EVIDENCE_COUNT",
    }
    out.loc[unique, "PROCESS_CASE_ID"] = cids.values
    for target, source in projections.items():
        if source is None or source not in case_map.columns:
            continue
        mapped = cids.map(case_map[source])
        if target == "PROCESS_EVIDENCE_COUNT":
            mapped = pd.to_numeric(mapped, errors="coerce").fillna(0).astype(int)
        else:
            mapped = mapped.fillna("")
        out.loc[unique, target] = mapped.values
    return out
