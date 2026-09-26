from __future__ import annotations

"""Business-aware SQLite Core for GSI.

This module deliberately consumes adapter outputs at their native grains. It does
not reconstruct business relationships from the flattened dashboard mart.
Only co-observed keys in the same evidence row create a direct relationship.
"""

from dataclasses import dataclass
from typing import Mapping
import hashlib

import pandas as pd

from gsi.adapters.base import (
    KEY_BL, KEY_EMP, KEY_MATERIAL, KEY_ORDER, KEY_PR, KEY_PO, KEY_REG, KEY_REG_FILE,
)
from .store import Warehouse, RUN, dumps, now


ENTITY_COLS = {
    "ORDER": KEY_ORDER,
    "MATERIAL": KEY_MATERIAL,
    "BL": KEY_BL,
    "REG": KEY_REG,
    "REG_FILE": KEY_REG_FILE,
    "PR": KEY_PR,
    "PO": KEY_PO,
    "EMP": KEY_EMP,
}

# Only direct co-observation creates a bridge. Derived/transitive paths remain
# query-time paths so evidence is never confused with inference.
DIRECT_PAIRS = (
    ("ORDER", "MATERIAL"),
    ("ORDER", "PR"),
    ("PR", "MATERIAL"),
    ("PR", "PO"),
    ("PO", "MATERIAL"),
    ("PO", "BL"),  # roadmap profile 3: inbound reference document + BL
    ("PO", "REG_FILE"),  # roadmap profile 2: native PO registration-file evidence
    ("ORDER", "BL"),
    ("BL", "REG"),
    ("ORDER", "REG"),
    ("REG_FILE", "REG"),
    ("REG_FILE", "ORDER"),
    ("ORDER", "EMP"),
)

BUSINESS_SCHEMA = r'''
CREATE TABLE IF NOT EXISTS dwh_entity(
 entity_type TEXT NOT NULL,
 business_key TEXT NOT NULL,
 first_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 PRIMARY KEY(entity_type,business_key));

CREATE TABLE IF NOT EXISTS dwh_dim_order(
 order_key TEXT PRIMARY KEY,
 first_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));
CREATE TABLE IF NOT EXISTS dwh_dim_material(
 material_key TEXT PRIMARY KEY,
 first_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));
CREATE TABLE IF NOT EXISTS dwh_dim_bl(
 bl_key TEXT PRIMARY KEY,
 first_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));
CREATE TABLE IF NOT EXISTS dwh_dim_registration(
 reg_key TEXT PRIMARY KEY,
 first_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));
CREATE TABLE IF NOT EXISTS dwh_dim_registration_file(
 reg_file_key TEXT PRIMARY KEY,
 first_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));
CREATE TABLE IF NOT EXISTS dwh_dim_pr(
 pr_key TEXT PRIMARY KEY,
 first_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));
CREATE TABLE IF NOT EXISTS dwh_dim_po(
 po_key TEXT PRIMARY KEY,
 first_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));
CREATE TABLE IF NOT EXISTS dwh_dim_employee(
 emp_key TEXT PRIMARY KEY,
 first_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));

CREATE TABLE IF NOT EXISTS dwh_relation(
 left_type TEXT NOT NULL,
 left_key TEXT NOT NULL,
 right_type TEXT NOT NULL,
 right_key TEXT NOT NULL,
 source TEXT NOT NULL,
 frame TEXT NOT NULL,
 rule TEXT NOT NULL,
 first_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 evidence_count INTEGER NOT NULL DEFAULT 1,
 PRIMARY KEY(left_type,left_key,right_type,right_key,source,frame,rule),
 FOREIGN KEY(left_type,left_key) REFERENCES dwh_entity(entity_type,business_key),
 FOREIGN KEY(right_type,right_key) REFERENCES dwh_entity(entity_type,business_key));
CREATE INDEX IF NOT EXISTS dwh_relation_left ON dwh_relation(left_type,left_key);
CREATE INDEX IF NOT EXISTS dwh_relation_right ON dwh_relation(right_type,right_key);

CREATE TABLE IF NOT EXISTS dwh_fact_source_row(
 source TEXT NOT NULL,
 frame TEXT NOT NULL,
 row_hash TEXT NOT NULL,
 payload TEXT NOT NULL,
 first_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 PRIMARY KEY(source,frame,row_hash));

CREATE TABLE IF NOT EXISTS dwh_fact_supply_position(
 order_key TEXT NOT NULL REFERENCES dwh_dim_order(order_key),
 material_key TEXT NOT NULL REFERENCES dwh_dim_material(material_key),
 payload TEXT NOT NULL,
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 PRIMARY KEY(order_key,material_key));

CREATE TABLE IF NOT EXISTS dwh_bridge_order_material_pr_item(
 order_key TEXT NOT NULL REFERENCES dwh_dim_order(order_key),
 material_key TEXT NOT NULL REFERENCES dwh_dim_material(material_key),
 pr_key TEXT NOT NULL REFERENCES dwh_dim_pr(pr_key),
 pr_item TEXT NOT NULL DEFAULT '',
 evidence_count INTEGER NOT NULL DEFAULT 1,
 source_rows TEXT NOT NULL DEFAULT '',
 payload TEXT NOT NULL,
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 PRIMARY KEY(order_key,material_key,pr_key,pr_item));
CREATE INDEX IF NOT EXISTS dwh_ompi_order_material ON dwh_bridge_order_material_pr_item(order_key,material_key);
CREATE INDEX IF NOT EXISTS dwh_ompi_pr ON dwh_bridge_order_material_pr_item(pr_key);

CREATE TABLE IF NOT EXISTS dwh_fact_oracle_material(
 material_key TEXT PRIMARY KEY REFERENCES dwh_dim_material(material_key),
 payload TEXT NOT NULL,
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));


CREATE TABLE IF NOT EXISTS dwh_fact_sap_pr_item(
 pr_key TEXT NOT NULL REFERENCES dwh_dim_pr(pr_key),
 pr_item TEXT NOT NULL DEFAULT '',
 material_key TEXT,
 payload TEXT NOT NULL,
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 PRIMARY KEY(pr_key,pr_item));
CREATE INDEX IF NOT EXISTS dwh_sap_pr_material ON dwh_fact_sap_pr_item(material_key);

CREATE TABLE IF NOT EXISTS dwh_fact_sap_po_item(
 po_key TEXT NOT NULL REFERENCES dwh_dim_po(po_key),
 po_item TEXT NOT NULL DEFAULT '',
 pr_key TEXT,
 pr_item TEXT NOT NULL DEFAULT '',
 material_key TEXT,
 payload TEXT NOT NULL,
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id),
 PRIMARY KEY(po_key,po_item));
CREATE INDEX IF NOT EXISTS dwh_sap_po_pr ON dwh_fact_sap_po_item(pr_key,pr_item);

CREATE TABLE IF NOT EXISTS dwh_fact_sap_workflow(
 workflow_key TEXT PRIMARY KEY,
 pr_key TEXT NOT NULL REFERENCES dwh_dim_pr(pr_key),
 pr_item TEXT NOT NULL DEFAULT '',
 event_date TEXT,
 payload TEXT NOT NULL,
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));
CREATE INDEX IF NOT EXISTS dwh_sap_workflow_pr ON dwh_fact_sap_workflow(pr_key,event_date);

CREATE TABLE IF NOT EXISTS dwh_fact_ntsw_allocation_request(
 request_key TEXT PRIMARY KEY,
 reg_key TEXT NOT NULL REFERENCES dwh_dim_registration(reg_key),
 payload TEXT NOT NULL,
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));

CREATE TABLE IF NOT EXISTS dwh_fact_ntsw_commitment(
 reg_key TEXT PRIMARY KEY REFERENCES dwh_dim_registration(reg_key),
 payload TEXT NOT NULL,
 last_seen_run TEXT NOT NULL REFERENCES wh_run(id));

CREATE TABLE IF NOT EXISTS dwh_unresolved_relation(
 id INTEGER PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES wh_run(id),
 source TEXT NOT NULL,
 frame TEXT NOT NULL,
 row_hash TEXT NOT NULL,
 reason_code TEXT NOT NULL,
 payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS dwh_unresolved_run ON dwh_unresolved_relation(run_id,source,frame);

DROP VIEW IF EXISTS dwh_registration_hub;
CREATE VIEW dwh_registration_hub AS
WITH regs AS (SELECT DISTINCT left_key f,right_key r FROM dwh_relation WHERE left_type='REG_FILE' AND right_type='REG'),
ords AS (SELECT DISTINCT left_key f,right_key o FROM dwh_relation WHERE left_type='REG_FILE' AND right_type='ORDER'),
card AS (SELECT business_key f,(SELECT count(*) FROM regs WHERE f=business_key) nr,
(SELECT count(*) FROM ords WHERE f=business_key) no FROM dwh_entity WHERE entity_type='REG_FILE')
SELECT card.f reg_file_key,regs.r reg_key,ords.o order_key FROM card
LEFT JOIN regs ON regs.f=card.f LEFT JOIN ords ON ords.f=card.f WHERE nr<=1 AND no<=1
UNION ALL SELECT card.f,regs.r,NULL FROM card JOIN regs ON regs.f=card.f WHERE nr>1 OR no>1
UNION ALL SELECT card.f,NULL,ords.o FROM card JOIN ords ON ords.f=card.f WHERE nr>1 OR no>1;

'''


def _clean(v) -> str:
    if v is None or v is pd.NA:
        return ""
    t = str(v).strip()
    if t.lower() in {"nan", "none", "<na>"}:
        return ""
    return t


def _source_business_keys(source: str, row: pd.Series, columns) -> dict[str, str]:
    """Extract native business keys, including source-prefixed copies.

    The flat mart may need SATA to seed KEY_REG, but the business DWH must retain
    source-native REG evidence independently.  This keeps NTSW/source relations
    usable even when the dashboard merge path is incomplete.
    """
    keys = {typ: _clean(row.get(col, "")) for typ, col in ENTITY_COLS.items() if col in columns}
    aliases = {
        "ntsw": {"REG": "NTSW_KEY_REG"},
        "sata": {"REG": "SATA_KEY_REG"},
        "fx_transaction": {"REG": "FX_KEY_REG"},
        "credit": {"REG": "CRD_KEY_REG"},
        "ilappend": {"REG": "IL_KEY_REG"},
    }.get(source, {})
    for typ, col in aliases.items():
        if not keys.get(typ) and col in columns:
            keys[typ] = _clean(row.get(col, ""))
    return keys


def _row_payload(row: pd.Series) -> str:
    return dumps({str(k): (None if pd.isna(v) else v) for k, v in row.items()})


def _row_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dim_table(entity_type: str) -> tuple[str, str]:
    return {
        "ORDER": ("dwh_dim_order", "order_key"),
        "MATERIAL": ("dwh_dim_material", "material_key"),
        "BL": ("dwh_dim_bl", "bl_key"),
        "REG": ("dwh_dim_registration", "reg_key"),
        "REG_FILE": ("dwh_dim_registration_file", "reg_file_key"),
        "PR": ("dwh_dim_pr", "pr_key"),
        "PO": ("dwh_dim_po", "po_key"),
        "EMP": ("dwh_dim_employee", "emp_key"),
    }[entity_type]


def _upsert_entity(conn, entity_type: str, key: str, run_id: str) -> None:
    if not key:
        return
    conn.execute(
        "INSERT INTO dwh_entity(entity_type,business_key,first_seen_run,last_seen_run) VALUES(?,?,?,?) "
        "ON CONFLICT(entity_type,business_key) DO UPDATE SET last_seen_run=excluded.last_seen_run",
        (entity_type, key, run_id, run_id),
    )
    table, col = _dim_table(entity_type)
    conn.execute(
        f"INSERT INTO {table}({col},first_seen_run,last_seen_run) VALUES(?,?,?) "
        f"ON CONFLICT({col}) DO UPDATE SET last_seen_run=excluded.last_seen_run",
        (key, run_id, run_id),
    )


def _relation_allowed(source: str, left_type: str, right_type: str) -> bool:
    # Commercial Expert's BL field is explicitly quarantined as non-shipping BL.
    if source == "moghavemat" and "BL" in (left_type, right_type):
        return False
    return True


def _upsert_relation(conn, run_id: str, source: str, frame: str,
                     lt: str, lk: str, rt: str, rk: str) -> None:
    if not (lk and rk) or not _relation_allowed(source, lt, rt):
        return
    rule = f"DIRECT_COOBSERVED:{source}/{frame}:{lt}+{rt}"
    conn.execute(
        "INSERT INTO dwh_relation(left_type,left_key,right_type,right_key,source,frame,rule,first_seen_run,last_seen_run,evidence_count) "
        "VALUES(?,?,?,?,?,?,?,?,?,1) "
        "ON CONFLICT(left_type,left_key,right_type,right_key,source,frame,rule) DO UPDATE SET "
        "last_seen_run=excluded.last_seen_run,evidence_count=dwh_relation.evidence_count+1",
        (lt, lk, rt, rk, source, frame, rule, run_id, run_id),
    )


def ensure_schema(wh: Warehouse) -> None:
    with wh.db() as conn:
        conn.executescript(BUSINESS_SCHEMA)


def build(wh: Warehouse, sources: Mapping[str, Mapping[str, pd.DataFrame]], run_id: str | None = None) -> dict[str, int]:
    run_id = run_id or RUN.get()
    if not run_id:
        raise RuntimeError("Business DWH build requires an active warehouse run")
    counts = {"source_rows": 0, "entities": 0, "relations": 0, "unresolved": 0}
    with wh.db() as conn:
        conn.executescript(BUSINESS_SCHEMA)
        from .snapshots import capture, tables
        # Preserve a legacy publication before replacing mutable working tables.
        has_snap = conn.execute("SELECT 1 FROM sqlite_master WHERE name='wh_semantic_snapshot'").fetchone()
        previous = conn.execute("SELECT run_id FROM wh_current WHERE slot='dwh'").fetchone()
        if previous and not has_snap:
            conn.execute("INSERT INTO wh_issue(run_id,code,detail) VALUES(?,?,?)", (run_id, "LEGACY_SNAPSHOT_NOT_RECONSTRUCTABLE", dumps({"previous_run":previous[0],"action":"rebuild from archived run frames before historical use"})))
        # Child tables first to retain FK enforcement. Raw archive is untouched.
        names = tables(conn)
        for name in sorted(names, key=lambda n: (n.startswith('dwh_dim_') or n == 'dwh_entity', n)):
            conn.execute(f'DELETE FROM "{name}"')
        # Diagnostics are per-run; current dimensions/relations are upserted.
        conn.execute("DELETE FROM dwh_unresolved_relation WHERE run_id=?", (run_id,))
        # Archive physical source rows once and pre-aggregate entity/relation writes.
        # SAP semantic frames are projections of raw_rows; archiving both doubled
        # >500k physical rows and caused millions of scalar SQLite calls.
        entity_keys: set[tuple[str, str]] = set()
        relation_counts: dict[tuple[str, str, str, str, str, str, str], int] = {}
        unresolved_rows = []
        source_batch = []

        def flush_source_batch():
            nonlocal source_batch
            if source_batch:
                conn.executemany(
                    "INSERT INTO dwh_fact_source_row(source,frame,row_hash,payload,first_seen_run,last_seen_run) VALUES(?,?,?,?,?,?) "
                    "ON CONFLICT(source,frame,row_hash) DO UPDATE SET last_seen_run=excluded.last_seen_run",
                    source_batch)
                source_batch = []

        for source, frames in sources.items():
            sap_has_raw = (source == "sap" and isinstance((frames or {}).get("raw_rows"), pd.DataFrame)
                           and not frames["raw_rows"].empty)
            for frame, df in frames.items():
                if not isinstance(df, pd.DataFrame) or df.empty:
                    continue
                # raw_rows is the physical archive for native multi-sheet SAP.
                # pr_items/po_items/workflow/inbound/GR are still consumed below by
                # dedicated fact tables, but are not duplicated in source-row archive.
                if sap_has_raw and frame != "raw_rows":
                    continue
                columns = list(df.columns)
                for ordinal, values in enumerate(df.itertuples(index=False, name=None)):
                    row = dict(zip(columns, values))
                    payload = _row_payload(row)
                    rh = _row_hash(payload + ":" + str(ordinal))
                    counts["source_rows"] += 1
                    source_batch.append((source, frame, rh, payload, run_id, run_id))
                    if len(source_batch) >= 2000:
                        flush_source_batch()
                    keys = _source_business_keys(source, row, columns)
                    if source == "sap" and frame == "raw_rows":
                        po_pr = _clean(row.get("SAP_PO_PR", ""))
                        if po_pr and keys.get("PR") and po_pr != keys["PR"]:
                            unresolved_rows.append((run_id, source, frame, rh, "SAP_HEADER_PO_PR_CONFLICT", payload))
                            counts["unresolved"] += 1
                    for typ, key in keys.items():
                        if key:
                            entity_keys.add((typ, key))
                    for lt, rt in DIRECT_PAIRS:
                        lk, rk = keys.get(lt, ""), keys.get(rt, "")
                        if source == "sap" and (lt, rt) == ("PR", "PO"):
                            lk = _clean(row.get("SAP_PO_PR", "")) or lk
                        if source == "sap" and (lt, rt) == ("PO", "MATERIAL"):
                            rk = _clean(row.get("SAP_PO_MATERIAL", "")) or rk
                        if lk: entity_keys.add((lt, lk))
                        if rk: entity_keys.add((rt, rk))
                        if lk and rk and _relation_allowed(source, lt, rt):
                            rule = f"DIRECT_COOBSERVED:{source}/{frame}:{lt}+{rt}"
                            k = (lt, lk, rt, rk, source, frame, rule)
                            relation_counts[k] = relation_counts.get(k, 0) + 1
                    if source == "ntsw" and frame == "import_license":
                        reg_file, reg = keys.get("REG_FILE"), keys.get("REG")
                        reason = None
                        if reg_file and not reg: reason = "REG_FILE_WITHOUT_REG_IN_IMPORT_LICENCE"
                        elif reg and not reg_file: reason = "REG_WITHOUT_REG_FILE_IN_IMPORT_LICENCE"
                        elif not reg_file and not reg: reason = "IMPORT_LICENCE_ROW_WITHOUT_REG_KEYS"
                        if reason:
                            unresolved_rows.append((run_id, source, frame, rh, reason, payload)); counts["unresolved"] += 1
                    if source == "ilappend" and keys.get("REG_FILE") and not (keys.get("REG") or keys.get("ORDER")):
                        unresolved_rows.append((run_id, source, frame, rh, "IL_REG_FILE_WITHOUT_REG_OR_ORDER", payload)); counts["unresolved"] += 1
        flush_source_batch()

        # Batch unique dimensions. This preserves exactly the same current-run state
        # while replacing millions of scalar INSERT/UPDATE calls with bounded batches.
        by_type: dict[str, list[str]] = {}
        for typ, key in entity_keys:
            by_type.setdefault(typ, []).append(key)
        for typ, keys in by_type.items():
            uniq = sorted(set(keys))
            conn.executemany(
                "INSERT INTO dwh_entity(entity_type,business_key,first_seen_run,last_seen_run) VALUES(?,?,?,?) "
                "ON CONFLICT(entity_type,business_key) DO UPDATE SET last_seen_run=excluded.last_seen_run",
                [(typ, key, run_id, run_id) for key in uniq])
            table, col = _dim_table(typ)
            conn.executemany(
                f"INSERT INTO {table}({col},first_seen_run,last_seen_run) VALUES(?,?,?) "
                f"ON CONFLICT({col}) DO UPDATE SET last_seen_run=excluded.last_seen_run",
                [(key, run_id, run_id) for key in uniq])
        if relation_counts:
            conn.executemany(
                "INSERT INTO dwh_relation(left_type,left_key,right_type,right_key,source,frame,rule,first_seen_run,last_seen_run,evidence_count) "
                "VALUES(?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(left_type,left_key,right_type,right_key,source,frame,rule) DO UPDATE SET "
                "last_seen_run=excluded.last_seen_run,evidence_count=dwh_relation.evidence_count+excluded.evidence_count",
                [(*k, run_id, run_id, n) for k, n in relation_counts.items()])
        if unresolved_rows:
            conn.executemany(
                "INSERT INTO dwh_unresolved_relation(run_id,source,frame,row_hash,reason_code,payload) VALUES(?,?,?,?,?,?)",
                unresolved_rows)

        # Business-current facts: source history remains immutable in fact_source_row.
        inv = sources.get("moghavemat", {}).get("inventory")
        if isinstance(inv, pd.DataFrame) and not inv.empty:
            for _, row in inv.iterrows():
                o, m = _clean(row.get(KEY_ORDER, "")), _clean(row.get(KEY_MATERIAL, ""))
                if not (o and m):
                    continue
                _upsert_entity(conn, "ORDER", o, run_id); _upsert_entity(conn, "MATERIAL", m, run_id)
                conn.execute(
                    "INSERT INTO dwh_fact_supply_position(order_key,material_key,payload,last_seen_run) VALUES(?,?,?,?) "
                    "ON CONFLICT(order_key,material_key) DO UPDATE SET payload=excluded.payload,last_seen_run=excluded.last_seen_run",
                    (o, m, _row_payload(row), run_id),
                )
        ompi = sources.get("moghavemat", {}).get("order_material_pr_item")
        if isinstance(ompi, pd.DataFrame) and not ompi.empty:
            pr_item_col = "MOGH_PR_ITEM"
            ev_col = "MOGH_EVIDENCE_COUNT"
            rows_col = "MOGH_SOURCE_ROWS"
            for _, row in ompi.iterrows():
                o = _clean(row.get(KEY_ORDER, ""))
                m = _clean(row.get(KEY_MATERIAL, ""))
                pr = _clean(row.get(KEY_PR, ""))
                item = _clean(row.get(pr_item_col, ""))
                if not (o and m and pr):
                    continue
                _upsert_entity(conn, "ORDER", o, run_id)
                _upsert_entity(conn, "MATERIAL", m, run_id)
                _upsert_entity(conn, "PR", pr, run_id)
                try:
                    evidence_count = max(1, int(float(row.get(ev_col, 1) or 1)))
                except Exception:
                    evidence_count = 1
                conn.execute(
                    "INSERT INTO dwh_bridge_order_material_pr_item(order_key,material_key,pr_key,pr_item,evidence_count,source_rows,payload,last_seen_run) "
                    "VALUES(?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(order_key,material_key,pr_key,pr_item) DO UPDATE SET "
                    "evidence_count=excluded.evidence_count,source_rows=excluded.source_rows,payload=excluded.payload,last_seen_run=excluded.last_seen_run",
                    (o, m, pr, item, evidence_count, _clean(row.get(rows_col, "")), _row_payload(row), run_id),
                )

        # SAP procurement marts: native grains, not the flattened compatibility projection.
        sap_pr = sources.get("sap", {}).get("pr_items")
        if isinstance(sap_pr, pd.DataFrame) and not sap_pr.empty:
            for _, row in sap_pr.iterrows():
                pr = _clean(row.get(KEY_PR, "")); item = _clean(row.get("SAP_PR_ITEM", ""))
                mat = _clean(row.get(KEY_MATERIAL, ""))
                if not pr: continue
                _upsert_entity(conn, "PR", pr, run_id)
                if mat: _upsert_entity(conn, "MATERIAL", mat, run_id)
                conn.execute(
                    "INSERT INTO dwh_fact_sap_pr_item(pr_key,pr_item,material_key,payload,last_seen_run) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(pr_key,pr_item) DO UPDATE SET material_key=excluded.material_key,payload=excluded.payload,last_seen_run=excluded.last_seen_run",
                    (pr, item, mat or None, _row_payload(row), run_id),
                )
        sap_po = sources.get("sap", {}).get("po_items")
        if isinstance(sap_po, pd.DataFrame) and not sap_po.empty:
            for _, row in sap_po.iterrows():
                po = _clean(row.get(KEY_PO, "")); item = _clean(row.get("SAP_PO_ITEM", ""))
                explicit_pr = _clean(row.get("SAP_PO_PR", ""))
                pr = explicit_pr or _clean(row.get(KEY_PR, ""))
                pri = _clean(row.get("SAP_PO_PR_ITEM", "")) if explicit_pr else _clean(row.get("SAP_PR_ITEM", ""))
                mat = _clean(row.get("SAP_PO_MATERIAL", "")) or _clean(row.get(KEY_MATERIAL, ""))
                if not po: continue
                _upsert_entity(conn, "PO", po, run_id)
                if pr: _upsert_entity(conn, "PR", pr, run_id)
                if mat: _upsert_entity(conn, "MATERIAL", mat, run_id)
                conn.execute(
                    "INSERT INTO dwh_fact_sap_po_item(po_key,po_item,pr_key,pr_item,material_key,payload,last_seen_run) VALUES(?,?,?,?,?,?,?) "
                    "ON CONFLICT(po_key,po_item) DO UPDATE SET pr_key=excluded.pr_key,pr_item=excluded.pr_item,material_key=excluded.material_key,payload=excluded.payload,last_seen_run=excluded.last_seen_run",
                    (po, item, pr or None, pri, mat or None, _row_payload(row), run_id),
                )
        sap_wf = sources.get("sap", {}).get("workflow_rows")
        if isinstance(sap_wf, pd.DataFrame) and not sap_wf.empty:
            for ix, row in sap_wf.iterrows():
                pr = _clean(row.get(KEY_PR, "")); item = _clean(row.get("SAP_PR_ITEM", ""))
                if not pr: continue
                _upsert_entity(conn, "PR", pr, run_id)
                payload = _row_payload(row)
                wf = _clean(row.get("SAP_WORKFLOW_ID", "")) or _clean(row.get("SAP_COMPARISON_ID", ""))
                key_seed = f"{pr}|{item}|{wf}|{_clean(row.get('SAP_SOURCE_ROW',''))}|{payload}"
                wkey = hashlib.sha256(key_seed.encode("utf-8")).hexdigest()
                event_date = (_clean(row.get("SAP_CHANGED_ON_ISO", "")) or _clean(row.get("SAP_RELEASE_DATE_ISO", "")) or
                              _clean(row.get("SAP_COMMISSION_DATE_ISO", "")) or _clean(row.get("SAP_REQUISITION_DATE_ISO", "")))
                conn.execute(
                    "INSERT INTO dwh_fact_sap_workflow(workflow_key,pr_key,pr_item,event_date,payload,last_seen_run) VALUES(?,?,?,?,?,?) "
                    "ON CONFLICT(workflow_key) DO UPDATE SET event_date=excluded.event_date,payload=excluded.payload,last_seen_run=excluded.last_seen_run",
                    (wkey, pr, item, event_date or None, payload, run_id),
                )

        oracle = sources.get("oracle", {}).get("main")
        if isinstance(oracle, pd.DataFrame) and not oracle.empty:
            for _, row in oracle.iterrows():
                m = _clean(row.get(KEY_MATERIAL, ""))
                if not m: continue
                _upsert_entity(conn, "MATERIAL", m, run_id)
                conn.execute(
                    "INSERT INTO dwh_fact_oracle_material(material_key,payload,last_seen_run) VALUES(?,?,?) "
                    "ON CONFLICT(material_key) DO UPDATE SET payload=excluded.payload,last_seen_run=excluded.last_seen_run",
                    (m, _row_payload(row), run_id),
                )
        alloc = sources.get("ntsw", {}).get("allocation_rows")
        if isinstance(alloc, pd.DataFrame) and not alloc.empty and "NTSW_REQUEST_KEY" in alloc.columns:
            for _, row in alloc.iterrows():
                r, q = _clean(row.get(KEY_REG, "")), _clean(row.get("NTSW_REQUEST_KEY", ""))
                if not (r and q): continue
                _upsert_entity(conn, "REG", r, run_id)
                conn.execute(
                    "INSERT INTO dwh_fact_ntsw_allocation_request(request_key,reg_key,payload,last_seen_run) VALUES(?,?,?,?) "
                    "ON CONFLICT(request_key) DO UPDATE SET reg_key=excluded.reg_key,payload=excluded.payload,last_seen_run=excluded.last_seen_run",
                    (q, r, _row_payload(row), run_id),
                )
        com = sources.get("ntsw", {}).get("commitment")
        if isinstance(com, pd.DataFrame) and not com.empty:
            for _, row in com.iterrows():
                r = _clean(row.get(KEY_REG, ""))
                if not r: continue
                _upsert_entity(conn, "REG", r, run_id)
                conn.execute(
                    "INSERT INTO dwh_fact_ntsw_commitment(reg_key,payload,last_seen_run) VALUES(?,?,?) "
                    "ON CONFLICT(reg_key) DO UPDATE SET payload=excluded.payload,last_seen_run=excluded.last_seen_run",
                    (r, _row_payload(row), run_id),
                )
        counts["entities"] = conn.execute("SELECT count(*) FROM dwh_entity").fetchone()[0]
        counts["relations"] = conn.execute("SELECT count(*) FROM dwh_relation").fetchone()[0]
        counts["order_material_pr_item"] = conn.execute("SELECT count(*) FROM dwh_bridge_order_material_pr_item").fetchone()[0]
        counts["sap_pr_items"] = conn.execute("SELECT count(*) FROM dwh_fact_sap_pr_item").fetchone()[0]
        counts["sap_po_items"] = conn.execute("SELECT count(*) FROM dwh_fact_sap_po_item").fetchone()[0]
        counts["sap_workflow"] = conn.execute("SELECT count(*) FROM dwh_fact_sap_workflow").fetchone()[0]
        capture(conn, run_id)
    return counts
