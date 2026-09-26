from __future__ import annotations

"""Data reliability contracts for the GSI SQLite warehouse.

Design goals:
- fail closed on structural/grain violations;
- never silently drop rows;
- keep diagnostics for every blocked run;
- separate evidence (direct keys) from inferred relationships;
- keep business rules out of the orchestration layer.
"""

from dataclasses import dataclass, field, asdict
from typing import Iterable, Sequence, Mapping, Any
import hashlib
import json

import pandas as pd


BLOCK = "BLOCK"  # publication-blocking compatibility severity
CRITICAL = "CRITICAL"
FATAL = "FATAL"
DEGRADED = "DEGRADED"
WARN = "WARN"
INFO = "INFO"

PUBLISH_BLOCKING = {BLOCK, CRITICAL, FATAL}


@dataclass(frozen=True)
class GrainContract:
    name: str
    grain: str
    natural_key: tuple[str, ...]
    required_columns: tuple[str, ...] = ()
    nullable_key: bool = False
    key_completeness_policy: str = "strict"  # strict | partial_evidence
    duplicate_policy: str = "forbid"  # forbid | warn | allow
    description: str = ""
    additive_measures: tuple[str, ...] = ()
    non_additive_measures: tuple[str, ...] = ()


@dataclass
class Check:
    contract: str
    code: str
    severity: str
    passed: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def row(self) -> dict[str, Any]:
        d = asdict(self)
        d["detail"] = json.dumps(d["detail"], ensure_ascii=False, default=str)
        return d


# Contracts are intentionally conservative: only grains already proven by source
# code/business semantics are blocking. Ambiguous sources remain observable but
# are not forced into a false key.
CONTRACTS: dict[str, GrainContract] = {
    "ntsw/import_license": GrainContract(
        name="ntsw/import_license",
        grain="import licence evidence row (registration-file hub)",
        natural_key=("KEY_REG_FILE", "KEY_REG"),
        required_columns=("KEY_REG_FILE", "KEY_REG"),
        key_completeness_policy="partial_evidence",
        duplicate_policy="warn",
        description="Direct evidence connecting registration file to registration code; duplicates may be historical observations and are audited, not dropped.",
    ),
    "ilappend/main": GrainContract(
        name="ilappend/main",
        grain="IL append evidence row",
        natural_key=("KEY_REG_FILE", "KEY_REG", "KEY_ORDER"),
        required_columns=("KEY_REG_FILE", "KEY_REG"),
        key_completeness_policy="partial_evidence",
        duplicate_policy="warn",
        description="IL is the bridge from registration file to registration/order. Blank order is allowed at row level.",
        nullable_key=True,
    ),
    "oracle/main": GrainContract(
        name="oracle/main",
        grain="one row per material after two-sheet reconciliation",
        natural_key=("KEY_MATERIAL",),
        required_columns=("KEY_MATERIAL",),
        description="Oracle material stock/need snapshot; duplicate material must be resolved before Core.",
    ),
    "moghavemat/inventory": GrainContract(
        name="moghavemat/inventory",
        grain="order × material supply position",
        natural_key=("KEY_ORDER", "KEY_MATERIAL"),
        required_columns=("KEY_ORDER", "KEY_MATERIAL"),
        description="Commercial supply position. Snapshot quantities are non-additive across duplicate lines.",
    ),
    "moghavemat/order_material_pr_item": GrainContract(
        name="moghavemat/order_material_pr_item",
        grain="order × material × PR × PR item procurement relation",
        natural_key=("MOGH_OMPI_KEY",),
        required_columns=("KEY_ORDER", "KEY_MATERIAL", "KEY_PR", "MOGH_OMPI_KEY"),
        description="Direct procurement lineage. PR Item may be blank; MOGH_OMPI_KEY preserves blank as an explicit grain component and repeated raw evidence is counted, not duplicated.",
    ),
    "sap/main": GrainContract(
        name="sap/main",
        grain="latest compatibility projection per PR",
        natural_key=("KEY_PR",),
        required_columns=("KEY_PR",),
        description="Legacy/UI projection only. Analytical SAP facts live in pr_items, po_items and workflow_rows.",
    ),
    "sap/raw_rows": GrainContract(
        name="sap/raw_rows",
        grain="one standardized row per SAP source sheet × physical row",
        natural_key=("SAP_SOURCE_SHEET", "SAP_SOURCE_ROW"),
        required_columns=("SAP_SOURCE_SHEET", "SAP_SOURCE_ROW"),
        description="Replay/lineage frame; row numbers restart in each SAP sheet, so sheet+row is the physical grain.",
    ),
    "sap/pr_items": GrainContract(
        name="sap/pr_items",
        grain="current PR item (PR-level fallback when legacy export lacks item)",
        natural_key=("KEY_PR", "SAP_PR_ITEM"),
        required_columns=("KEY_PR", "SAP_PR_ITEM"),
        nullable_key=True,
        description="Current PR-item snapshot. Legacy SAP may have blank item; PR remains usable without fabricating an item number.",
    ),
    "sap/po_items": GrainContract(
        name="sap/po_items",
        grain="current purchasing document item",
        natural_key=("KEY_PO", "SAP_PO_ITEM"),
        required_columns=("KEY_PO", "SAP_PO_ITEM"),
        description="PO-item fact preserving direct PR/material lineage where co-observed.",
    ),
    "sap/workflow_rows": GrainContract(
        name="sap/workflow_rows",
        grain="workflow/package observation at source-row grain",
        natural_key=("SAP_SOURCE_ROW",),
        required_columns=("KEY_PR", "SAP_SOURCE_ROW"),
        nullable_key=False,
        description="History-preserving workflow evidence; repeated PRs are expected and must not be deduplicated globally.",
    ),
    "sap/inbound_deliveries": GrainContract(
        name="sap/inbound_deliveries",
        grain="inbound delivery item",
        natural_key=("SAP_IB_DELIVERY", "SAP_IB_ITEM"),
        required_columns=("SAP_IB_DELIVERY",),
        nullable_key=True,
        duplicate_policy="warn",
        description="Direct SAP↔bill-of-lading evidence co-observed on one native row; "
                    "the shipping link is observed here, not inferred downstream.",
    ),
    "sap/goods_receipts": GrainContract(
        name="sap/goods_receipts",
        grain="goods movement line (material document × item)",
        natural_key=("SAP_GR_MATERIAL_DOC", "SAP_GR_DOC_ITEM"),
        required_columns=("SAP_GR_MATERIAL_DOC", "SAP_GR_MOVEMENT_TYPE"),
        nullable_key=True,
        duplicate_policy="forbid",
        additive_measures=(),
        non_additive_measures=("SAP_GR_QTY", "SAP_GR_SIGNED_QTY"),
        description="A reversal repeats the quantity with the opposite meaning. Only "
                    "Neither quantity is a global stock total. Resolve movement phase, material, "
                    "base unit, plant and document identity before any aggregation.",
    ),
    "hr/main": GrainContract(
        name="hr/main",
        grain="one active HR mapping row per employee code",
        natural_key=("KEY_EMP",),
        required_columns=("KEY_EMP",),
        description="Employee/org mapping.",
    ),
    "ntsw/allocation_rows": GrainContract(
        name="ntsw/allocation_rows",
        grain="latest observation per allocation request",
        natural_key=("NTSW_REQUEST_KEY",),
        required_columns=("KEY_REG", "NTSW_REQUEST_KEY"),
        description="Operational allocation request ledger; raw observations are preserved separately when available.",
    ),
    "ntsw/allocation": GrainContract(
        name="ntsw/allocation",
        grain="allocation summary per registration",
        natural_key=("KEY_REG",),
        required_columns=("KEY_REG",),
        description="Derived summary from the request ledger; do not sum retry history.",
    ),
    "ntsw/commitment": GrainContract(
        name="ntsw/commitment",
        grain="commitment summary per registration",
        natural_key=("KEY_REG",),
        required_columns=("KEY_REG",),
        description="Aggregated release-commitment position per registration.",
    ),
}


def schema_fingerprint(df: pd.DataFrame) -> str:
    payload = [(str(c), str(df[c].dtype)) for c in df.columns]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _blank(s: pd.Series) -> pd.Series:
    return s.isna() | s.astype(str).str.strip().eq("")


def validate_frame(name: str, df: pd.DataFrame, contract: GrainContract | None = None) -> list[Check]:
    c = contract or CONTRACTS.get(name)
    if c is None:
        return [Check(name, "NO_EXPLICIT_GRAIN_CONTRACT", INFO, True, {"columns": list(df.columns), "rows": len(df)})]

    checks: list[Check] = []
    missing = [x for x in c.required_columns if x not in df.columns]
    checks.append(Check(c.name, "REQUIRED_COLUMNS", BLOCK, not missing, {"missing": missing}))
    if missing:
        return checks

    key_cols = list(c.natural_key)
    missing_key_cols = [x for x in key_cols if x not in df.columns]
    checks.append(Check(c.name, "KEY_COLUMNS_PRESENT", BLOCK, not missing_key_cols, {"missing": missing_key_cols, "key": key_cols}))
    if missing_key_cols:
        return checks

    complete_mask = pd.Series(True, index=df.index)
    for k in key_cols:
        complete_mask &= ~_blank(df[k])

    if c.nullable_key and key_cols:
        usable = ~_blank(df[key_cols[0]])
        checks.append(Check(c.name, "USABLE_KEY_EVIDENCE", BLOCK, bool(usable.any()) or df.empty,
                            {"usable_rows": int(usable.sum()), "total": len(df)}))
    if not c.nullable_key:
        bad = int((~complete_mask).sum())
        complete = int(complete_mask.sum())
        if c.key_completeness_policy == "partial_evidence":
            # Evidence tables may legitimately contain incomplete observations.
            # Preserve and audit them; block only when the frame has no usable
            # complete key-pair at all. This avoids one blank row taking down
            # the whole warehouse while still failing closed on a broken hub.
            checks.append(Check(c.name, "PARTIAL_KEY_EVIDENCE", WARN, bad == 0, {
                "incomplete_rows": bad, "complete_rows": complete,
                "total": len(df), "key": key_cols,
                "action": "incomplete rows are retained for forensic audit and excluded from direct bridge evidence",
            }))
            checks.append(Check(c.name, "USABLE_KEY_EVIDENCE", BLOCK, complete > 0, {
                "complete_rows": complete, "total": len(df), "key": key_cols,
            }))
        else:
            checks.append(Check(c.name, "NULL_OR_BLANK_KEY", BLOCK, bad == 0, {"rows": bad, "total": len(df), "key": key_cols}))

    # Grain uniqueness is meaningful only for rows whose natural key is complete.
    # Blank evidence rows must not collapse into a fake duplicate key.
    dup_base = (df.loc[~_blank(df[key_cols[0]])] if c.nullable_key else df.loc[complete_mask]) if len(df) else df
    dup_mask_local = dup_base.duplicated(subset=key_cols, keep=False) if len(dup_base) else pd.Series([], dtype=bool)
    dup_mask = pd.Series(False, index=df.index)
    if len(dup_base):
        dup_mask.loc[dup_base.index] = dup_mask_local
    dup_rows = int(dup_mask.sum()) if len(df) else 0
    dup_keys = int(df.loc[dup_mask, key_cols].drop_duplicates().shape[0]) if dup_rows else 0
    sev = BLOCK if c.duplicate_policy == "forbid" else WARN if c.duplicate_policy == "warn" else INFO
    passed = dup_rows == 0 or c.duplicate_policy == "allow"
    sample = df.loc[dup_mask, key_cols].drop_duplicates().head(10).to_dict("records") if dup_rows else []
    checks.append(Check(c.name, "GRAIN_UNIQUENESS", sev, passed, {
        "duplicate_rows": dup_rows,
        "duplicate_keys": dup_keys,
        "key": key_cols,
        "sample": sample,
    }))

    checks.append(Check(c.name, "SCHEMA_FINGERPRINT", INFO, True, {
        "fingerprint": schema_fingerprint(df),
        "columns": list(df.columns),
        "rows": len(df),
    }))
    return checks


def validate_sources(sources: Mapping[str, Mapping[str, pd.DataFrame]]) -> list[Check]:
    out: list[Check] = []
    for source, frames in sources.items():
        for frame, df in frames.items():
            if not isinstance(df, pd.DataFrame):
                continue
            out.extend(validate_frame(f"{source}/{frame}", df))
    return out


def reconcile_partition(total: int, buckets: Mapping[str, int], name: str) -> Check:
    accounted = sum(int(v) for v in buckets.values())
    return Check(name, "ROW_PRESERVATION", BLOCK, accounted == int(total), {
        "source_rows": int(total), "accounted_rows": accounted, "buckets": dict(buckets), "delta": int(total) - accounted,
    })


def blocking(checks: Iterable[Check]) -> list[Check]:
    """Checks that are unsafe to publish.

    WARN/DEGRADED are intentionally non-blocking so one damaged optional branch
    does not stop the entire run. BLOCK/CRITICAL/FATAL preserve the last good
    published snapshot while retaining the failed run for forensic review.
    """
    return [c for c in checks if c.severity in PUBLISH_BLOCKING and not c.passed]


def source_runtime_checks(pipeline) -> list[Check]:
    """Convert adapter/merge runtime failures into explicit quality evidence.

    The pipeline is allowed to continue loading independent branches. Critical
    business-spine failures block publication; optional-source failures degrade
    the run but do not erase unrelated fresh data.
    """
    out: list[Check] = []
    failures = getattr(pipeline, "source_failures", {}) or {}
    fallbacks = getattr(pipeline, "source_fallbacks", {}) or {}
    merge_failures = getattr(pipeline, "merge_failures", []) or []
    critical_sources = {"ntsw", "ilappend"}
    # A workbook that was found but whose expected sheets are absent is a broken
    # contract, not an availability gap: the file is there and the pipeline still
    # gets nothing. Left at DEGRADED this publishes a fresh report with a whole
    # source silently missing, which is how an SAP export that renamed its sheets
    # could contribute zero rows and still pass the gate.
    from .. import health as _health
    try:
        health_sources = dict(_health.current().sources)
    except Exception:
        health_sources = {}
    for source, frames in (getattr(pipeline, 'sources', {}) or {}).items():
        if not any(isinstance(df, pd.DataFrame) and not df.empty for df in frames.values()):
            rec = health_sources.get(source)
            gaps = list(getattr(rec, "schema_gaps", []) or [])
            if gaps:
                out.append(Check(f"source/{source}", "SOURCE_SCHEMA_CONTRACT_BROKEN", BLOCK, False, {
                    "state": "FILE_PRESENT_EXPECTED_SHEET_MISSING", "schema_gaps": gaps[:10],
                    "action": "the workbook was located but no configured sheet was found; fix the "
                              "sheet list in config/sources.yaml or the export, then re-run"}))
            else:
                out.append(Check(f"source/{source}", "SOURCE_COVERAGE_GAP", DEGRADED, False,
                                 {"state": "NOT_OBSERVED"}))
        for name, df in frames.items():
            if 'quarantine' in name and isinstance(df, pd.DataFrame) and not df.empty:
                out.append(Check(f"{source}/{name}", "QUARANTINED_SOURCE_ROWS", DEGRADED, False, {"rows":len(df)}))
    for source, detail in failures.items():
        sev = BLOCK if source in critical_sources else DEGRADED
        out.append(Check(f"source/{source}", "SOURCE_LOAD_FAILED", sev, False, dict(detail)))
    for source, detail in fallbacks.items():
        sev = BLOCK if source in critical_sources else DEGRADED
        out.append(Check(f"source/{source}", "STALE_FALLBACK_USED", sev, False, dict(detail)))
    for item in merge_failures:
        out.append(Check(str(item.get("contract", "merge")), "JOIN_CARDINALITY_VIOLATION", BLOCK, False, dict(item)))
    return out


def checks_frame(checks: Sequence[Check]) -> pd.DataFrame:
    return pd.DataFrame([c.row() for c in checks], columns=["contract", "code", "severity", "passed", "detail"])


def schema_drift_checks(wh, sources: Mapping[str, Mapping[str, pd.DataFrame]], run_id: str) -> list[Check]:
    """Compare native adapter schemas with the first accepted baseline.

    Baselines are intentionally not auto-rewritten after a change. This makes
    upstream Excel/header changes visible until explicitly reviewed.
    """
    out: list[Check] = []
    with wh.db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS wh_schema_candidate(run_id TEXT,contract TEXT,fingerprint TEXT,columns_json TEXT,updated TEXT,PRIMARY KEY(run_id,contract))")
        for source, frames in sources.items():
            for frame, df in frames.items():
                if not isinstance(df, pd.DataFrame):
                    continue
                name = f"{source}/{frame}"
                missing_maps = df.attrs.get('missing_mappings', [])
                if missing_maps:
                    out.append(Check(name, 'SOURCE_MAPPING_COVERAGE', WARN, False, {'missing':missing_maps, 'source_headers':df.attrs.get('source_headers', [])}))
                cols = [str(c) for c in df.columns]
                dtypes = {str(c): str(df[c].dtype) for c in df.columns}
                fp = schema_fingerprint(df)
                row = conn.execute(
                    "SELECT fingerprint,columns_json FROM wh_schema_baseline WHERE contract=?",
                    (name,),
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT OR REPLACE INTO wh_schema_candidate(run_id,contract,fingerprint,columns_json,updated) VALUES(?,?,?,?,?)",
                        (run_id, name, fp, json.dumps({"columns": cols, "dtypes": dtypes}, ensure_ascii=False), pd.Timestamp.utcnow().isoformat()),
                    )
                    out.append(Check(name, "SCHEMA_BASELINE_CANDIDATE", INFO, True, {"columns": cols}))
                    continue
                old = json.loads(row[1])
                old_cols = list(old.get("columns", []))
                old_types = dict(old.get("dtypes", {}))
                added = [c for c in cols if c not in old_cols]
                removed = [c for c in old_cols if c not in cols]
                changed_type = {c: {"before": old_types.get(c), "after": dtypes.get(c)}
                                for c in cols if c in old_types and old_types.get(c) != dtypes.get(c)}
                changed = bool(added or removed or changed_type)
                out.append(Check(name, "SCHEMA_DRIFT", WARN, not changed, {
                    "added": added, "removed": removed, "dtype_changed": changed_type,
                    "baseline_fingerprint": row[0], "observed_fingerprint": fp,
                }))
    return out
