# -*- coding: utf-8 -*-
"""SQLite data warehouse and process log store.

Design goals
------------
* stdlib-only persistence (sqlite3) so deployment remains simple;
* WAL + short transactions for Studio/read concurrency;
* wide case snapshots for fast interactive filtering;
* immutable event catalogue + run/event bridge to avoid duplicating event history;
* transition snapshots for exact process-mining at every run;
* KPI + state-change + audit logs for longitudinal analysis.

SQLite is deliberately the first warehouse tier.  The public API does not expose
SQLite-specific SQL to the rest of AIBL, so the same contract can later be backed
by PostgreSQL/DuckDB/SQL Server if concurrency or scale outgrows one file.
"""
from __future__ import annotations

__contract__ = 2

import hashlib
import json
import os
import sqlite3
import threading
import shutil
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..config.settings import SETTINGS
from ..dataio.logging_setup import log
from ..version import PACKAGE_VERSION

SCHEMA_VERSION = 2
_LOCK = threading.RLock()


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _q(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _run_id(ref_date: str) -> str:
    # UUID مانع collision اجرای مجدد همان تاریخ در یک ثانیه/Process می‌شود.
    # تاریخ در prefix می‌ماند تا run_id برای اپراتور قابل خواندن باشد.
    return f"{ref_date.replace('-', '')}_{uuid.uuid4().hex[:16]}"


def _stable_hash(*parts: Any) -> str:
    s = "\x1f".join("" if x is None else str(x) for x in parts)
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def _sqlite_type(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s) or pd.api.types.is_integer_dtype(s):
        return "INTEGER"
    if pd.api.types.is_float_dtype(s):
        return "REAL"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "TEXT"
    return "TEXT"


def _scalar(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (np.bool_, bool)):
        return int(bool(v))
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if pd.isna(v) else float(v)
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(v).isoformat()
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, (dict, list, tuple, set)):
        try:
            return json.dumps(v, ensure_ascii=False, default=str)
        except Exception:
            return str(v)
    return str(v) if not isinstance(v, (str, int, float, bytes)) else v


def _normalise_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].map(lambda x: None if pd.isna(x) else pd.Timestamp(x).isoformat())
        elif pd.api.types.is_bool_dtype(out[c]):
            out[c] = out[c].astype("Int64")
        elif out[c].dtype == "object":
            out[c] = out[c].map(_scalar)
    return out.where(pd.notna(out), None)


@dataclass
class WarehouseSnapshot:
    run_id: str
    ref_date: str
    df: pd.DataFrame
    main: pd.DataFrame
    extras: Dict[str, pd.DataFrame]
    metadata: Dict[str, Any]


class Warehouse:
    """Durable AIBL analytical store."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._backup_before_upgrade()
        self.ensure_schema()

    def _existing_schema_version(self) -> int:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return 0
        try:
            con = sqlite3.connect(str(self.path), timeout=10.0)
            try:
                row = con.execute("SELECT value FROM dw_meta WHERE key='schema_version'").fetchone()
                return int(row[0]) if row else 0
            finally:
                con.close()
        except Exception:
            return 0

    def _existing_package_version(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return ""
        try:
            con = sqlite3.connect(str(self.path), timeout=10.0)
            try:
                try:
                    row = con.execute("SELECT value FROM dw_meta WHERE key='package_version'").fetchone()
                    if row and str(row[0]).strip():
                        return str(row[0]).strip()
                except sqlite3.DatabaseError:
                    pass
                try:
                    row = con.execute("SELECT package_version FROM dw_run ORDER BY started_at DESC LIMIT 1").fetchone()
                    return str(row[0]).strip() if row and row[0] else ""
                except sqlite3.DatabaseError:
                    return ""
            finally:
                con.close()
        except Exception:
            return ""

    def _backup_before_upgrade(self) -> None:
        """Take a consistent backup before schema *or package* upgrade.

        The first open by a new AIBL release creates exactly one safety backup,
        even when the SQLite schema itself did not change. This makes replacing
        the release folder safe for historical snapshots/events/audit data.
        """
        old_schema = self._existing_schema_version()
        old_package = self._existing_package_version()
        schema_upgrade = bool(old_schema and old_schema < SCHEMA_VERSION)
        package_upgrade = bool(old_package and old_package != PACKAGE_VERSION)
        if not (schema_upgrade or package_upgrade):
            return
        backup_dir = self.path.parent / "warehouse_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        reason = (f"schema{old_schema}_to_{SCHEMA_VERSION}" if schema_upgrade
                  else f"pkg{old_package.replace('.', '_')}_to_{PACKAGE_VERSION.replace('.', '_')}")
        target = backup_dir / f"{self.path.stem}_{reason}_{stamp}.sqlite3"
        src = sqlite3.connect(str(self.path), timeout=30.0)
        dst = sqlite3.connect(str(target), timeout=30.0)
        try:
            src.backup(dst)
        finally:
            dst.close(); src.close()
        log.info("🛡️ Warehouse backup before upgrade (%s): %s", reason, target)

    # ── connection / schema ──────────────────────────────────────────────
    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=30.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=30000")
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError:
            pass
        return con

    def ensure_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS dw_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS dw_run (
            run_id TEXT PRIMARY KEY,
            ref_date TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            package_version TEXT NOT NULL,
            row_count INTEGER DEFAULT 0,
            main_count INTEGER DEFAULT 0,
            event_count INTEGER DEFAULT 0,
            case_count INTEGER DEFAULT 0,
            transition_count INTEGER DEFAULT 0,
            note TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_dw_run_ref_date ON dw_run(ref_date DESC, started_at DESC);

        CREATE TABLE IF NOT EXISTS source_run_log (
            run_id TEXT NOT NULL REFERENCES dw_run(run_id) ON DELETE CASCADE,
            source_key TEXT NOT NULL,
            frame_name TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            column_count INTEGER NOT NULL,
            columns_json TEXT NOT NULL,
            fingerprint TEXT,
            PRIMARY KEY(run_id, source_key, frame_name)
        );
        CREATE INDEX IF NOT EXISTS ix_source_run_source ON source_run_log(source_key, frame_name, run_id);

        CREATE TABLE IF NOT EXISTS fact_case_snapshot (
            run_id TEXT NOT NULL REFERENCES dw_run(run_id) ON DELETE CASCADE,
            snapshot_date TEXT NOT NULL,
            partition_name TEXT NOT NULL,
            row_ordinal INTEGER NOT NULL,
            row_identity TEXT NOT NULL,
            PRIMARY KEY(run_id, row_ordinal)
        );
        CREATE INDEX IF NOT EXISTS ix_fact_case_run_part ON fact_case_snapshot(run_id, partition_name);
        CREATE INDEX IF NOT EXISTS ix_fact_case_identity ON fact_case_snapshot(row_identity, run_id);

        CREATE TABLE IF NOT EXISTS fact_event (
            event_id TEXT PRIMARY KEY,
            case_key TEXT NOT NULL,
            activity_en TEXT,
            activity_fa TEXT,
            event_time TEXT NOT NULL,
            sorting INTEGER DEFAULT 0,
            lifecycle_stage TEXT,
            bl_no TEXT,
            part_no TEXT,
            resource TEXT,
            org_unit TEXT,
            currency TEXT,
            case_value REAL,
            criticality TEXT,
            segment TEXT,
            transport_mode TEXT,
            first_seen_run_id TEXT,
            last_seen_run_id TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT,
            payload_json TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_fact_event_case_time ON fact_event(case_key, event_time, sorting);
        CREATE INDEX IF NOT EXISTS ix_fact_event_activity ON fact_event(activity_fa, event_time);

        CREATE TABLE IF NOT EXISTS bridge_run_event (
            run_id TEXT NOT NULL REFERENCES dw_run(run_id) ON DELETE CASCADE,
            event_id TEXT NOT NULL REFERENCES fact_event(event_id) ON DELETE CASCADE,
            PRIMARY KEY(run_id, event_id)
        );
        CREATE INDEX IF NOT EXISTS ix_bridge_event_run ON bridge_run_event(run_id);

        CREATE TABLE IF NOT EXISTS fact_case_process_snapshot (
            run_id TEXT NOT NULL REFERENCES dw_run(run_id) ON DELETE CASCADE,
            case_key TEXT NOT NULL,
            first_event TEXT,
            last_event TEXT,
            event_count INTEGER,
            throughput_days REAL,
            rework_count INTEGER,
            first_activity TEXT,
            last_activity TEXT,
            variant TEXT,
            process_completeness REAL,
            PRIMARY KEY(run_id, case_key)
        );
        CREATE INDEX IF NOT EXISTS ix_case_proc_case ON fact_case_process_snapshot(case_key, run_id);

        CREATE TABLE IF NOT EXISTS fact_transition_snapshot (
            run_id TEXT NOT NULL REFERENCES dw_run(run_id) ON DELETE CASCADE,
            case_key TEXT NOT NULL,
            seq_no INTEGER NOT NULL,
            from_activity TEXT NOT NULL,
            to_activity TEXT NOT NULL,
            from_time TEXT NOT NULL,
            to_time TEXT NOT NULL,
            wait_days REAL NOT NULL,
            from_stage TEXT,
            to_stage TEXT,
            org_unit TEXT,
            resource TEXT,
            PRIMARY KEY(run_id, case_key, seq_no)
        );
        CREATE INDEX IF NOT EXISTS ix_transition_run_pair ON fact_transition_snapshot(run_id, from_activity, to_activity);
        CREATE INDEX IF NOT EXISTS ix_transition_case ON fact_transition_snapshot(case_key, run_id, seq_no);

        CREATE TABLE IF NOT EXISTS fact_conformance_snapshot (
            run_id TEXT NOT NULL REFERENCES dw_run(run_id) ON DELETE CASCADE,
            case_key TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY(run_id, case_key)
        );

        CREATE TABLE IF NOT EXISTS fact_kpi_snapshot (
            run_id TEXT NOT NULL REFERENCES dw_run(run_id) ON DELETE CASCADE,
            ref_date TEXT NOT NULL,
            metric_key TEXT NOT NULL,
            metric_label TEXT NOT NULL,
            numeric_value REAL,
            text_value TEXT,
            unit TEXT,
            PRIMARY KEY(run_id, metric_key)
        );
        CREATE INDEX IF NOT EXISTS ix_kpi_metric_date ON fact_kpi_snapshot(metric_key, ref_date);

        CREATE TABLE IF NOT EXISTS case_state_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL REFERENCES dw_run(run_id) ON DELETE CASCADE,
            ref_date TEXT NOT NULL,
            case_key TEXT NOT NULL,
            previous_run_id TEXT,
            state_hash TEXT NOT NULL,
            changed_fields_json TEXT NOT NULL,
            previous_json TEXT,
            current_json TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_case_state_case_date ON case_state_log(case_key, ref_date, id);

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            run_id TEXT,
            actor TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            level TEXT NOT NULL DEFAULT 'INFO',
            message TEXT,
            payload_json TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_audit_created ON audit_log(created_at DESC);
        CREATE INDEX IF NOT EXISTS ix_audit_run ON audit_log(run_id, created_at);

        CREATE TABLE IF NOT EXISTS app_profile (
            profile_type TEXT NOT NULL,
            name TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(profile_type, name)
        );
        CREATE INDEX IF NOT EXISTS ix_app_profile_type ON app_profile(profile_type, updated_at DESC);

        CREATE VIEW IF NOT EXISTS vw_latest_run AS
        SELECT * FROM dw_run
        WHERE status='SUCCESS'
        ORDER BY ref_date DESC, finished_at DESC
        LIMIT 1;

        CREATE VIEW IF NOT EXISTS vw_kpi_trend AS
        SELECT k.ref_date, k.metric_key, k.metric_label, k.numeric_value, k.text_value, k.unit, k.run_id
        FROM fact_kpi_snapshot k
        JOIN dw_run r ON r.run_id=k.run_id
        WHERE r.status='SUCCESS';
        """
        with _LOCK, self.connect() as con:
            con.executescript(ddl)
            con.execute("INSERT OR REPLACE INTO dw_meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
            con.execute("INSERT OR REPLACE INTO dw_meta(key,value) VALUES('package_version',?)", (PACKAGE_VERSION,))
            con.commit()

    # ── generic helpers ─────────────────────────────────────────────────
    def _columns(self, con: sqlite3.Connection, table: str) -> set[str]:
        return {r["name"] for r in con.execute(f"PRAGMA table_info({_q(table)})")}

    def _ensure_wide_columns(self, con: sqlite3.Connection, table: str, df: pd.DataFrame) -> None:
        existing = self._columns(con, table)
        for c in df.columns:
            if c in existing:
                continue
            con.execute(f"ALTER TABLE {_q(table)} ADD COLUMN {_q(c)} {_sqlite_type(df[c])}")
            existing.add(c)

    def audit(self, action: str, *, run_id: str | None = None, actor: str = "system",
              entity_type: str = "", entity_id: str = "", level: str = "INFO",
              message: str = "", payload: Any = None) -> None:
        raw = None if payload is None else json.dumps(payload, ensure_ascii=False, default=str)
        try:
            with _LOCK, self.connect() as con:
                con.execute(
                    "INSERT INTO audit_log(created_at,run_id,actor,action,entity_type,entity_id,level,message,payload_json) VALUES(?,?,?,?,?,?,?,?,?)",
                    (_utcnow(), run_id, actor, action, entity_type, entity_id, level, message, raw),
                )
                con.commit()
        except Exception as ex:
            log.warning("⚠️ ثبت audit در SQLite ناموفق بود: %s", ex)

    # ── persistent Studio / email profiles ─────────────────────────────
    def save_profile(self, profile_type: str, name: str, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload or {}, ensure_ascii=False, default=str)
        with _LOCK, self.connect() as con:
            con.execute("""INSERT INTO app_profile(profile_type,name,payload_json,updated_at) VALUES(?,?,?,?)
                           ON CONFLICT(profile_type,name) DO UPDATE SET payload_json=excluded.payload_json,updated_at=excluded.updated_at""",
                        (str(profile_type), str(name), raw, _utcnow()))
            con.commit()

    def load_profile(self, profile_type: str, name: str) -> Dict[str, Any]:
        with self.connect() as con:
            r = con.execute("SELECT payload_json FROM app_profile WHERE profile_type=? AND name=?",
                            (str(profile_type), str(name))).fetchone()
        if not r:
            return {}
        try:
            return json.loads(r[0]) or {}
        except Exception:
            return {}

    def list_profiles(self, profile_type: str) -> List[str]:
        with self.connect() as con:
            rows = con.execute("SELECT name FROM app_profile WHERE profile_type=? ORDER BY updated_at DESC,name",
                               (str(profile_type),)).fetchall()
        return [str(r[0]) for r in rows]

    # ── persistence ─────────────────────────────────────────────────────
    def begin_run(self, ref_date: date | str, *, package_version: str = PACKAGE_VERSION,
                  run_id: str | None = None) -> str:
        """Register a pipeline execution before source IO begins.

        This gives runtime/audit logs a durable ``run_id`` even if the pipeline
        fails before a snapshot can be committed.
        """
        ref = str(ref_date)[:10]
        rid = run_id or _run_id(ref)
        with _LOCK, self.connect() as con:
            con.execute(
                """INSERT INTO dw_run(run_id,ref_date,started_at,status,package_version)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(run_id) DO UPDATE SET
                     ref_date=excluded.ref_date, status='RUNNING',
                     package_version=excluded.package_version, finished_at=NULL, note=NULL""",
                (rid, ref, _utcnow(), "RUNNING", package_version),
            )
            con.commit()
        return rid

    def fail_run(self, run_id: str, ref_date: date | str, note: str,
                 *, package_version: str = PACKAGE_VERSION) -> None:
        """Mark a registered execution failed without losing its audit trail."""
        ref = str(ref_date)[:10]
        with _LOCK, self.connect() as con:
            con.execute(
                """INSERT INTO dw_run(run_id,ref_date,started_at,finished_at,status,package_version,note)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(run_id) DO UPDATE SET
                     finished_at=excluded.finished_at,status='FAILED',
                     package_version=excluded.package_version,note=excluded.note""",
                (run_id, ref, _utcnow(), _utcnow(), "FAILED", package_version, str(note)[:2000]),
            )
            con.execute(
                "INSERT INTO audit_log(created_at,run_id,actor,action,entity_type,entity_id,level,message,payload_json) VALUES(?,?,?,?,?,?,?,?,?)",
                (_utcnow(), run_id, "pipeline", "PIPELINE_FAILED", "run", run_id, "ERROR", str(note)[:2000], None),
            )
            con.commit()

    def persist_pipeline(self, result: Any, ref_date: date | str,
                         *, package_version: str = PACKAGE_VERSION,
                         sources: Optional[Dict[str, Dict[str, pd.DataFrame]]] = None,
                         run_id: str | None = None) -> str:
        """Persist one successful pipeline execution atomically.

        ``result`` is intentionally duck-typed to avoid a pipeline→warehouse→pipeline
        import cycle. Expected attributes: df, main, to_resolve, excluded, extras.
        """
        ref = str(ref_date)[:10]
        rid = run_id or _run_id(ref)
        started = _utcnow()
        with _LOCK, self.connect() as con:
            try:
                con.execute("BEGIN IMMEDIATE")
                con.execute(
                    """INSERT INTO dw_run(run_id,ref_date,started_at,status,package_version) VALUES(?,?,?,?,?)
                       ON CONFLICT(run_id) DO UPDATE SET
                         ref_date=excluded.ref_date,status='RUNNING',package_version=excluded.package_version,
                         finished_at=NULL,note=NULL""",
                    (rid, ref, started, "RUNNING", package_version),
                )
                self._persist_source_lineage(con, rid, sources or {})
                snap = self._prepare_case_snapshot(result, rid, ref)
                self._ensure_wide_columns(con, "fact_case_snapshot", snap)
                _normalise_frame(snap).to_sql("fact_case_snapshot", con, if_exists="append", index=False)

                extras = dict(getattr(result, "extras", {}) or {})
                events = extras.get("eventlog")
                if not isinstance(events, pd.DataFrame):
                    events = pd.DataFrame()
                event_n = self._persist_events(con, rid, events)
                transitions = self._build_transitions(events)
                if not transitions.empty:
                    transitions.insert(0, "run_id", rid)
                    _normalise_frame(transitions).to_sql("fact_transition_snapshot", con, if_exists="append", index=False)

                cases = extras.get("case_table")
                if not isinstance(cases, pd.DataFrame):
                    cases = pd.DataFrame()
                case_n = self._persist_case_process(con, rid, cases, getattr(result, "df", pd.DataFrame()))
                self._persist_conformance(con, rid, extras.get("conformance_cases"))
                self._persist_kpis(con, rid, ref, getattr(result, "main", pd.DataFrame()), cases)
                self._persist_case_state_changes(con, rid, ref, cases, getattr(result, "main", pd.DataFrame()))

                con.execute(
                    "UPDATE dw_run SET finished_at=?, status='SUCCESS', row_count=?, main_count=?, event_count=?, case_count=?, transition_count=? WHERE run_id=?",
                    (_utcnow(), len(getattr(result, "df", [])), len(getattr(result, "main", [])), event_n, case_n, len(transitions), rid),
                )
                con.execute(
                    "INSERT INTO audit_log(created_at,run_id,actor,action,entity_type,entity_id,level,message,payload_json) VALUES(?,?,?,?,?,?,?,?,?)",
                    (_utcnow(), rid, "pipeline", "WAREHOUSE_COMMIT", "run", rid, "INFO",
                     f"snapshot={len(snap)} events={event_n} cases={case_n} transitions={len(transitions)}", None),
                )
                con.commit()
                log.info("🗄 SQLite Warehouse: run=%s | %s snapshot rows | %s events | %s transitions", rid, len(snap), event_n, len(transitions))
                return rid
            except Exception as ex:
                con.rollback()
                try:
                    con.execute(
                        """INSERT INTO dw_run(run_id,ref_date,started_at,finished_at,status,package_version,note) VALUES(?,?,?,?,?,?,?)
                           ON CONFLICT(run_id) DO UPDATE SET finished_at=excluded.finished_at,status='FAILED',
                           package_version=excluded.package_version,note=excluded.note""",
                        (rid, ref, started, _utcnow(), "FAILED", package_version, str(ex)[:1000]),
                    )
                    con.commit()
                except Exception:
                    pass
                raise

    def _persist_source_lineage(self, con: sqlite3.Connection, rid: str,
                                sources: Dict[str, Dict[str, pd.DataFrame]]) -> None:
        rows=[]
        for source_key, frames in (sources or {}).items():
            for frame_name, frame in (frames or {}).items():
                if not isinstance(frame,pd.DataFrame):
                    continue
                cols=[str(c) for c in frame.columns]
                try:
                    hv=pd.util.hash_pandas_object(frame, index=False).values.tobytes()
                    fp=hashlib.sha256(hv).hexdigest()[:24]
                except Exception:
                    fp=_stable_hash(source_key,frame_name,len(frame),json.dumps(cols,ensure_ascii=False))[:24]
                rows.append((rid,str(source_key),str(frame_name),len(frame),len(cols),
                             json.dumps(cols,ensure_ascii=False),fp))
        if rows:
            con.executemany("INSERT OR REPLACE INTO source_run_log(run_id,source_key,frame_name,row_count,column_count,columns_json,fingerprint) VALUES(?,?,?,?,?,?,?)",rows)

    def _prepare_case_snapshot(self, result: Any, rid: str, ref: str) -> pd.DataFrame:
        df = getattr(result, "df", pd.DataFrame()).copy()
        main_idx = set(getattr(result, "main", pd.DataFrame()).index.tolist())
        resolve_idx = set(getattr(result, "to_resolve", pd.DataFrame()).index.tolist())
        excluded_idx = set(getattr(result, "excluded", pd.DataFrame()).index.tolist())
        part = []
        for idx in df.index:
            if idx in main_idx:
                part.append("main")
            elif idx in resolve_idx:
                part.append("to_resolve")
            elif idx in excluded_idx:
                part.append("excluded")
            else:
                part.append("other")
        identity_cols = [c for c in ("CASE_KEY", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_MATERIAL", "KEY_REG") if c in df.columns]
        ids = []
        for pos, (_, row) in enumerate(df.iterrows()):
            vals = [row.get(c, "") for c in identity_cols]
            ids.append(_stable_hash(*vals, pos))
        meta = pd.DataFrame({
            "run_id": rid,
            "snapshot_date": ref,
            "partition_name": part,
            "row_ordinal": np.arange(len(df), dtype=int),
            "row_identity": ids,
        }, index=df.index)
        return pd.concat([meta.reset_index(drop=True), df.reset_index(drop=True)], axis=1)

    def _persist_events(self, con: sqlite3.Connection, rid: str, events: pd.DataFrame) -> int:
        if events.empty:
            return 0
        now = _utcnow()
        known = {
            "_CASE_KEY": "case_key", "ACTIVITY_EN": "activity_en", "ACTIVITY_FA": "activity_fa",
            "EVENTTIME": "event_time", "_SORTING": "sorting", "LIFECYCLE_STAGE": "lifecycle_stage",
            "BL_NO": "bl_no", "PART_NO": "part_no", "RESOURCE": "resource", "ORG_UNIT": "org_unit",
            "CURRENCY": "currency", "CASE_VALUE": "case_value", "CRITICALITY": "criticality",
            "SEGMENT": "segment", "TRANSPORT_MODE": "transport_mode",
        }
        sql = """INSERT INTO fact_event(
            event_id,case_key,activity_en,activity_fa,event_time,sorting,lifecycle_stage,bl_no,part_no,resource,org_unit,currency,case_value,criticality,segment,transport_mode,
            first_seen_run_id,last_seen_run_id,first_seen_at,last_seen_at,payload_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_id) DO UPDATE SET
                last_seen_run_id=excluded.last_seen_run_id,
                last_seen_at=excluded.last_seen_at,
                payload_json=excluded.payload_json
        """
        rows = []
        bridges = []
        for rec in events.to_dict("records"):
            case = str(rec.get("_CASE_KEY") or rec.get("CASE_KEY") or "").strip()
            et = rec.get("EVENTTIME")
            if not case or pd.isna(et):
                continue
            et_iso = pd.Timestamp(et).isoformat()
            eid = _stable_hash(case, rec.get("ACTIVITY_EN"), rec.get("ACTIVITY_FA"), et_iso, rec.get("_SORTING", 0))
            payload = {k: _scalar(v) for k, v in rec.items() if k not in known}
            value = pd.to_numeric(pd.Series([rec.get("CASE_VALUE")]), errors="coerce").iloc[0]
            rows.append((
                eid, case, _scalar(rec.get("ACTIVITY_EN")), _scalar(rec.get("ACTIVITY_FA")), et_iso,
                int(pd.to_numeric(pd.Series([rec.get("_SORTING", 0)]), errors="coerce").fillna(0).iloc[0]),
                _scalar(rec.get("LIFECYCLE_STAGE")), _scalar(rec.get("BL_NO")), _scalar(rec.get("PART_NO")),
                _scalar(rec.get("RESOURCE")), _scalar(rec.get("ORG_UNIT")), _scalar(rec.get("CURRENCY")),
                None if pd.isna(value) else float(value), _scalar(rec.get("CRITICALITY")), _scalar(rec.get("SEGMENT")),
                _scalar(rec.get("TRANSPORT_MODE")), rid, rid, now, now,
                json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
            ))
            bridges.append((rid, eid))
        con.executemany(sql, rows)
        # Eventlog ممکن است به‌علت ادغام چند سورس یک occurrence یکسان را دوبار
        # تحویل دهد. bridge و شمار اجرای ثبت‌شده باید occurrence یکتا را نشان دهند.
        bridges = list(dict.fromkeys(bridges))
        con.executemany("INSERT OR IGNORE INTO bridge_run_event(run_id,event_id) VALUES(?,?)", bridges)
        return len(bridges)

    @staticmethod
    def _build_transitions(events: pd.DataFrame) -> pd.DataFrame:
        cols = ["case_key","seq_no","from_activity","to_activity","from_time","to_time","wait_days","from_stage","to_stage","org_unit","resource"]
        if events is None or events.empty or "EVENTTIME" not in events.columns:
            return pd.DataFrame(columns=cols)
        ev = events.copy()
        key = "_CASE_KEY" if "_CASE_KEY" in ev.columns else "CASE_KEY"
        if key not in ev.columns:
            return pd.DataFrame(columns=cols)
        ev["EVENTTIME"] = pd.to_datetime(ev["EVENTTIME"], errors="coerce")
        sort_cols = [key, "EVENTTIME"] + (["_SORTING"] if "_SORTING" in ev.columns else [])
        ev = ev.dropna(subset=["EVENTTIME"]).sort_values(sort_cols, kind="mergesort")
        rows: List[Dict[str, Any]] = []
        for case, g in ev.groupby(key, sort=False):
            recs = g.to_dict("records")
            for i in range(len(recs) - 1):
                a, b = recs[i], recs[i + 1]
                wait = (pd.Timestamp(b["EVENTTIME"]) - pd.Timestamp(a["EVENTTIME"])).total_seconds() / 86400.0
                rows.append({
                    "case_key": str(case), "seq_no": i + 1,
                    "from_activity": a.get("ACTIVITY_FA") or a.get("ACTIVITY_EN") or "",
                    "to_activity": b.get("ACTIVITY_FA") or b.get("ACTIVITY_EN") or "",
                    "from_time": pd.Timestamp(a["EVENTTIME"]).isoformat(),
                    "to_time": pd.Timestamp(b["EVENTTIME"]).isoformat(),
                    "wait_days": round(float(wait), 6),
                    "from_stage": a.get("LIFECYCLE_STAGE", ""), "to_stage": b.get("LIFECYCLE_STAGE", ""),
                    "org_unit": a.get("ORG_UNIT", ""), "resource": a.get("RESOURCE", ""),
                })
        return pd.DataFrame(rows, columns=cols)

    def _persist_case_process(self, con: sqlite3.Connection, rid: str, cases: pd.DataFrame,
                              df: pd.DataFrame) -> int:
        if cases.empty:
            return 0
        comp_by_case: Dict[str, float] = {}
        if isinstance(df, pd.DataFrame) and {"CASE_KEY", "PROCESS_COMPLETENESS"} <= set(df.columns):
            tmp = df[["CASE_KEY", "PROCESS_COMPLETENESS"]].dropna().drop_duplicates("CASE_KEY")
            comp_by_case = dict(zip(tmp["CASE_KEY"].astype(str), pd.to_numeric(tmp["PROCESS_COMPLETENESS"], errors="coerce")))
        rows = []
        for rec in cases.to_dict("records"):
            case = str(rec.get("CASE_KEY") or rec.get("_CASE_KEY") or "").strip()
            if not case:
                continue
            rows.append((
                rid, case, _scalar(rec.get("FIRST_EVENT")), _scalar(rec.get("LAST_EVENT")),
                int(pd.to_numeric(pd.Series([rec.get("EVENT_COUNT", 0)]), errors="coerce").fillna(0).iloc[0]),
                float(pd.to_numeric(pd.Series([rec.get("THROUGHPUT_DAYS", 0)]), errors="coerce").fillna(0).iloc[0]),
                int(pd.to_numeric(pd.Series([rec.get("REWORK_COUNT", 0)]), errors="coerce").fillna(0).iloc[0]),
                _scalar(rec.get("FIRST_ACTIVITY")), _scalar(rec.get("LAST_ACTIVITY")), _scalar(rec.get("VARIANT")),
                None if pd.isna(comp_by_case.get(case, np.nan)) else float(comp_by_case[case]),
            ))
        con.executemany("""INSERT OR REPLACE INTO fact_case_process_snapshot(
            run_id,case_key,first_event,last_event,event_count,throughput_days,rework_count,first_activity,last_activity,variant,process_completeness)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", rows)
        return len(rows)

    def _persist_conformance(self, con: sqlite3.Connection, rid: str, frame: Any) -> None:
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            return
        key = "CASE_KEY" if "CASE_KEY" in frame.columns else ("_CASE_KEY" if "_CASE_KEY" in frame.columns else None)
        if not key:
            return
        rows = []
        for rec in frame.to_dict("records"):
            case = str(rec.get(key) or "").strip()
            if case:
                rows.append((rid, case, json.dumps({k:_scalar(v) for k,v in rec.items()}, ensure_ascii=False, default=str)))
        con.executemany("INSERT OR REPLACE INTO fact_conformance_snapshot(run_id,case_key,payload_json) VALUES(?,?,?)", rows)

    def _persist_kpis(self, con: sqlite3.Connection, rid: str, ref: str,
                      df: pd.DataFrame, cases: pd.DataFrame) -> None:
        if df is None:
            df = pd.DataFrame()
        def uniq(c: str) -> int:
            return int(df[c].replace("", pd.NA).nunique()) if c in df.columns else 0
        band = df.get("کد طبقه بحرانی", df.get("بحرانی (کوتاه)", pd.Series("", index=df.index))).astype(str)
        crit = band.isin(["STOCKOUT","CRITICAL","توقف خط","بحرانی"])
        stop = band.isin(["STOCKOUT","توقف خط"])
        metrics: List[tuple[str,str,Optional[float],Optional[str],str]] = [
            ("rows","ردیف‌های جریان اصلی",float(len(df)),None,"row"),
            ("orders","سفارش یکتا",float(uniq("CANONICAL_ORDER")),None,"case"),
            ("bls","بارنامه یکتا",float(uniq("CANONICAL_BL")),None,"case"),
            ("materials","متریال یکتا",float(uniq("KEY_MATERIAL")),None,"material"),
            ("critical_rows","ردیف بحرانی/توقف",float(crit.sum()),None,"row"),
            ("stockout_rows","ردیف توقف خط",float(stop.sum()),None,"row"),
        ]
        # KPIهای تاریخی Warehouse هم باید دقیقاً همان Grain Registry را استفاده
        # کنند که Pipeline و HTML استفاده می‌کنند؛ در غیر این صورت trend تاریخی
        # با KPI صفحه اختلاف پیدا می‌کند.
        try:
            from ..studio_core.grain import safe_agg
        except Exception:
            safe_agg = None
        if "مقاومت (روز)" in df.columns:
            v = pd.to_numeric(df["مقاومت (روز)"], errors="coerce")
            val = (safe_agg(df,"مقاومت (روز)","mean") if safe_agg is not None
                   else (float(v.mean()) if v.notna().any() else None))
            metrics.append(("avg_resistance","میانگین مقاومت",None if val is None else float(val),None,"day"))
        if "مانده تعهد" in df.columns and safe_agg is not None:
            metrics.append(("commitment_balance","مانده تعهد",float(safe_agg(df,"مانده تعهد","sum")),None,"amount"))
        if isinstance(cases, pd.DataFrame) and not cases.empty and "THROUGHPUT_DAYS" in cases.columns:
            v = pd.to_numeric(cases["THROUGHPUT_DAYS"], errors="coerce")
            metrics.append(("avg_throughput","میانگین طول چرخه",float(v.mean()) if v.notna().any() else None,None,"day"))
            metrics.append(("variant_count","تعداد واریانت فرآیند",float(cases.get("VARIANT",pd.Series(dtype=str)).nunique()),None,"variant"))
        con.executemany(
            "INSERT OR REPLACE INTO fact_kpi_snapshot(run_id,ref_date,metric_key,metric_label,numeric_value,text_value,unit) VALUES(?,?,?,?,?,?,?)",
            [(rid,ref,*x) for x in metrics],
        )

    def _persist_case_state_changes(self, con: sqlite3.Connection, rid: str, ref: str,
                                    cases: pd.DataFrame, main: pd.DataFrame) -> None:
        if not isinstance(cases, pd.DataFrame) or cases.empty:
            return
        # Enrich case-level process state with a small set of operational attributes.
        attrs = [c for c in ("CASE_KEY","ORG_DEPT","CANONICAL_EXPERT","کد طبقه بحرانی","بحرانی (کوتاه)","STAGE_FA","CURRENT_STAGE","TRANSPORT_MODE") if c in main.columns]
        op: Dict[str, Dict[str, Any]] = {}
        if "CASE_KEY" in attrs:
            for rec in main[attrs].drop_duplicates("CASE_KEY").to_dict("records"):
                op[str(rec.get("CASE_KEY") or "")] = rec
        prev = con.execute("SELECT run_id,ref_date FROM dw_run WHERE status='SUCCESS' AND ref_date<=? AND run_id<>? ORDER BY ref_date DESC, finished_at DESC LIMIT 1", (ref,rid)).fetchone()
        prev_id = prev["run_id"] if prev else None
        prev_states: Dict[str, Dict[str, Any]] = {}
        if prev_id:
            # آخرین state معتبر تا snapshot قبلی را می‌خوانیم، نه آخرین state کل
            # دیتابیس. بنابراین backfill یک تاریخ قدیمی هرگز با آینده مقایسه نمی‌شود.
            q = """SELECT s.case_key,s.current_json FROM case_state_log s
                   JOIN (SELECT case_key,MAX(id) AS max_id FROM case_state_log
                         WHERE ref_date<=? AND run_id<>? GROUP BY case_key) x
                     ON x.case_key=s.case_key AND x.max_id=s.id"""
            for row in con.execute(q,(prev["ref_date"],rid)):
                try: prev_states[row["case_key"]] = json.loads(row["current_json"] or "{}")
                except Exception: prev_states[row["case_key"]] = {}
        rows = []
        for rec in cases.to_dict("records"):
            case = str(rec.get("CASE_KEY") or "").strip()
            if not case:
                continue
            cur = {
                "first_activity": _scalar(rec.get("FIRST_ACTIVITY")),
                "last_activity": _scalar(rec.get("LAST_ACTIVITY")),
                "event_count": _scalar(rec.get("EVENT_COUNT")),
                "throughput_days": _scalar(rec.get("THROUGHPUT_DAYS")),
                "rework_count": _scalar(rec.get("REWORK_COUNT")),
                "variant": _scalar(rec.get("VARIANT")),
            }
            cur.update({k:_scalar(v) for k,v in op.get(case,{}).items() if k != "CASE_KEY"})
            old = prev_states.get(case, {})
            changed = sorted(k for k,v in cur.items() if str(old.get(k,"")) != str(v if v is not None else ""))
            if not changed and prev_id:
                continue
            rows.append((rid,ref,case,prev_id,_stable_hash(json.dumps(cur,ensure_ascii=False,sort_keys=True,default=str)),
                         json.dumps(changed,ensure_ascii=False),json.dumps(old,ensure_ascii=False,default=str) if old else None,
                         json.dumps(cur,ensure_ascii=False,default=str),_utcnow()))
        con.executemany("""INSERT INTO case_state_log(run_id,ref_date,case_key,previous_run_id,state_hash,changed_fields_json,previous_json,current_json,created_at)
                           VALUES(?,?,?,?,?,?,?,?,?)""", rows)

    # ── reads ───────────────────────────────────────────────────────────
    def latest_run(self, ref_date: str | None = None) -> Optional[Dict[str, Any]]:
        with self.connect() as con:
            if ref_date:
                row = con.execute("SELECT * FROM dw_run WHERE status='SUCCESS' AND ref_date<=? ORDER BY ref_date DESC, finished_at DESC LIMIT 1", (str(ref_date)[:10],)).fetchone()
            else:
                row = con.execute("SELECT * FROM dw_run WHERE status='SUCCESS' ORDER BY ref_date DESC, finished_at DESC LIMIT 1").fetchone()
            return dict(row) if row else None

    def list_runs(self, limit: int = 60) -> pd.DataFrame:
        with self.connect() as con:
            return pd.read_sql_query("SELECT run_id,ref_date,started_at,finished_at,status,package_version,row_count,main_count,event_count,case_count,transition_count,note FROM dw_run ORDER BY ref_date DESC, started_at DESC LIMIT ?", con, params=(int(limit),))

    def load_snapshot(self, run_id: str | None = None, ref_date: str | None = None) -> Optional[WarehouseSnapshot]:
        meta = None
        with self.connect() as con:
            if run_id:
                r = con.execute("SELECT * FROM dw_run WHERE run_id=? AND status='SUCCESS'", (run_id,)).fetchone()
                meta = dict(r) if r else None
            else:
                meta = self.latest_run(ref_date)
            if not meta:
                return None
            rid = meta["run_id"]
            all_df = pd.read_sql_query("SELECT * FROM fact_case_snapshot WHERE run_id=? ORDER BY row_ordinal", con, params=(rid,))
            syscols = ["run_id","snapshot_date","partition_name","row_ordinal","row_identity"]
            main = all_df[all_df["partition_name"] == "main"].copy() if not all_df.empty else all_df.copy()
            df = all_df.drop(columns=syscols, errors="ignore")
            main = main.drop(columns=syscols, errors="ignore")
            extras = self._load_process_extras(con, rid)
            return WarehouseSnapshot(rid, meta["ref_date"], df.reset_index(drop=True), main.reset_index(drop=True), extras, meta)

    def _load_process_extras(self, con: sqlite3.Connection, rid: str) -> Dict[str, pd.DataFrame]:
        ev = pd.read_sql_query("""SELECT e.case_key AS _CASE_KEY,e.activity_en AS ACTIVITY_EN,e.activity_fa AS ACTIVITY_FA,e.event_time AS EVENTTIME,
            e.sorting AS _SORTING,e.lifecycle_stage AS LIFECYCLE_STAGE,e.bl_no AS BL_NO,e.part_no AS PART_NO,e.resource AS RESOURCE,
            e.org_unit AS ORG_UNIT,e.currency AS CURRENCY,e.case_value AS CASE_VALUE,e.criticality AS CRITICALITY,e.segment AS SEGMENT,e.transport_mode AS TRANSPORT_MODE
            FROM bridge_run_event b JOIN fact_event e ON e.event_id=b.event_id WHERE b.run_id=? ORDER BY e.case_key,e.event_time,e.sorting""", con, params=(rid,))
        if not ev.empty:
            ev["EVENTTIME"] = pd.to_datetime(ev["EVENTTIME"], errors="coerce")
        cases = pd.read_sql_query("""SELECT case_key AS CASE_KEY, first_event AS FIRST_EVENT,last_event AS LAST_EVENT,event_count AS EVENT_COUNT,
            variant AS VARIANT,first_activity AS FIRST_ACTIVITY,last_activity AS LAST_ACTIVITY,throughput_days AS THROUGHPUT_DAYS,rework_count AS REWORK_COUNT,
            process_completeness AS PROCESS_COMPLETENESS FROM fact_case_process_snapshot WHERE run_id=? ORDER BY case_key""", con, params=(rid,))
        bn = pd.read_sql_query("""SELECT from_activity AS 'از فعالیت',to_activity AS 'به فعالیت',ROUND(AVG(wait_days),1) AS 'میانگین روز',
            ROUND(MAX(wait_days),1) AS 'بیشینه روز',COUNT(*) AS 'تعداد',COUNT(DISTINCT case_key) AS 'تعداد پرونده'
            FROM fact_transition_snapshot WHERE run_id=? GROUP BY from_activity,to_activity ORDER BY AVG(wait_days) DESC""", con, params=(rid,))
        var = pd.read_sql_query("""SELECT variant AS VARIANT,COUNT(*) AS 'تعداد پرونده',ROUND(AVG(throughput_days),1) AS 'میانگین throughput'
            FROM fact_case_process_snapshot WHERE run_id=? GROUP BY variant ORDER BY COUNT(*) DESC""", con, params=(rid,))
        if not var.empty:
            total = max(int(var["تعداد پرونده"].sum()),1)
            var["سهم (٪)"] = (var["تعداد پرونده"] / total * 100).round(1)
        conf_rows = con.execute("SELECT payload_json FROM fact_conformance_snapshot WHERE run_id=?", (rid,)).fetchall()
        conf = pd.DataFrame([json.loads(r[0]) for r in conf_rows]) if conf_rows else pd.DataFrame()
        return {"eventlog":ev,"case_table":cases,"bottlenecks":bn,"variants":var,"conformance_cases":conf,
                "transitions":pd.read_sql_query("SELECT * FROM fact_transition_snapshot WHERE run_id=? ORDER BY case_key,seq_no",con,params=(rid,))}

    def case_timeline(self, case_key: str, run_id: str | None = None) -> pd.DataFrame:
        meta = self.latest_run() if not run_id else {"run_id":run_id}
        if not meta:
            return pd.DataFrame()
        rid = meta["run_id"]
        with self.connect() as con:
            return pd.read_sql_query("""SELECT e.activity_fa AS activity,e.activity_en,event_time,sorting,lifecycle_stage,org_unit,resource,bl_no,part_no,criticality
                FROM bridge_run_event b JOIN fact_event e ON e.event_id=b.event_id
                WHERE b.run_id=? AND e.case_key=? ORDER BY e.event_time,e.sorting""", con, params=(rid,str(case_key)))

    def case_transitions(self, case_key: str, run_id: str | None = None) -> pd.DataFrame:
        """Return exact adjacent activity transitions for one case/snapshot."""
        meta = self.latest_run() if not run_id else {"run_id": run_id}
        if not meta:
            return pd.DataFrame()
        with self.connect() as con:
            return pd.read_sql_query(
                """SELECT seq_no,from_activity,to_activity,from_time,to_time,
                          ROUND(wait_days,4) AS wait_days,from_stage,to_stage,org_unit,resource
                   FROM fact_transition_snapshot WHERE run_id=? AND case_key=? ORDER BY seq_no""",
                con, params=(meta["run_id"], str(case_key)))

    def case_changes(self, case_key: str, limit: int = 100) -> pd.DataFrame:
        with self.connect() as con:
            return pd.read_sql_query("SELECT ref_date,run_id,previous_run_id,changed_fields_json,previous_json,current_json,created_at FROM case_state_log WHERE case_key=? ORDER BY id DESC LIMIT ?", con, params=(str(case_key),int(limit)))

    def kpi_trend(self, metric_key: str | None = None, limit: int = 366) -> pd.DataFrame:
        with self.connect() as con:
            if metric_key:
                return pd.read_sql_query("SELECT * FROM vw_kpi_trend WHERE metric_key=? ORDER BY ref_date DESC LIMIT ?", con, params=(metric_key,int(limit)))
            return pd.read_sql_query("SELECT * FROM vw_kpi_trend ORDER BY ref_date DESC,metric_key LIMIT ?", con, params=(int(limit)*20,))

    def process_bottlenecks(self, run_id: str | None = None, *, org_unit: str | None = None,
                            resource: str | None = None, limit: int = 50) -> pd.DataFrame:
        meta = self.latest_run() if not run_id else {"run_id":run_id}
        if not meta:
            return pd.DataFrame()
        clauses=["run_id=?"]; params: List[Any]=[meta["run_id"]]
        if org_unit:
            clauses.append("org_unit=?"); params.append(org_unit)
        if resource:
            clauses.append("resource=?"); params.append(resource)
        params.append(int(limit))
        sql=f"""SELECT from_activity AS 'از فعالیت',to_activity AS 'به فعالیت',ROUND(AVG(wait_days),2) AS 'میانگین روز',
                 ROUND(MAX(wait_days),2) AS 'بیشینه روز',COUNT(DISTINCT case_key) AS 'پرونده',COUNT(*) AS 'transition'
                 FROM fact_transition_snapshot WHERE {' AND '.join(clauses)} GROUP BY from_activity,to_activity
                 ORDER BY AVG(wait_days) DESC LIMIT ?"""
        with self.connect() as con:
            return pd.read_sql_query(sql,con,params=params)

    def source_lineage(self, run_id: str | None = None) -> pd.DataFrame:
        meta=self.latest_run() if not run_id else {"run_id":run_id}
        if not meta: return pd.DataFrame()
        with self.connect() as con:
            return pd.read_sql_query("SELECT source_key,frame_name,row_count,column_count,fingerprint,columns_json FROM source_run_log WHERE run_id=? ORDER BY source_key,frame_name",con,params=(meta["run_id"],))

    def audit_entries(self, limit: int = 200, run_id: str | None = None) -> pd.DataFrame:
        with self.connect() as con:
            if run_id:
                return pd.read_sql_query("SELECT * FROM audit_log WHERE run_id=? ORDER BY id DESC LIMIT ?", con, params=(run_id,int(limit)))
            return pd.read_sql_query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", con, params=(int(limit),))

    def stats(self) -> Dict[str, Any]:
        with self.connect() as con:
            q = lambda sql: con.execute(sql).fetchone()[0]
            files = [self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")]
            size = sum(x.stat().st_size for x in files if x.exists())
            return {
                "path": str(self.path),
                "schema_version": SCHEMA_VERSION,
                "size_mb": round(size / 1024 / 1024, 2),
                "runs": q("SELECT COUNT(*) FROM dw_run WHERE status='SUCCESS'"),
                "failed_runs": q("SELECT COUNT(*) FROM dw_run WHERE status='FAILED'"),
                "events": q("SELECT COUNT(*) FROM fact_event"),
                "transitions": q("SELECT COUNT(*) FROM fact_transition_snapshot"),
                "state_changes": q("SELECT COUNT(*) FROM case_state_log"),
                "audit_entries": q("SELECT COUNT(*) FROM audit_log"),
            }

    def prune(self, keep_runs: int = 365) -> Dict[str, int]:
        """Keep the newest N successful runs and remove orphaned event records.

        Failed run/audit records are retained because they are operational evidence.
        Use ``vacuum`` afterwards when physical file compaction is required.
        """
        keep = max(1, int(keep_runs))
        with _LOCK, self.connect() as con:
            rows = con.execute(
                "SELECT run_id FROM dw_run WHERE status='SUCCESS' ORDER BY ref_date DESC, finished_at DESC"
            ).fetchall()
            doomed = [r[0] for r in rows[keep:]]
            if doomed:
                con.executemany("DELETE FROM dw_run WHERE run_id=?", [(x,) for x in doomed])
            before = con.execute("SELECT COUNT(*) FROM fact_event").fetchone()[0]
            con.execute("DELETE FROM fact_event WHERE event_id NOT IN (SELECT event_id FROM bridge_run_event)")
            after = con.execute("SELECT COUNT(*) FROM fact_event").fetchone()[0]
            con.commit()
        self.audit("WAREHOUSE_PRUNE", actor="maintenance", message=f"deleted_runs={len(doomed)} orphan_events={before-after}")
        return {"deleted_runs": len(doomed), "deleted_orphan_events": before - after}

    def vacuum(self) -> None:
        with _LOCK, self.connect() as con:
            con.execute("VACUUM")


def _warehouse_pointer_file() -> Path:
    home = Path(os.environ.get("AIBL_HOME") or (Path.home() / ".aibl")).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    return home / "warehouse.path"

def warehouse_from_settings() -> Warehouse:
    """Resolve one durable warehouse path across package upgrades.

    Priority: explicit env > persisted pointer > configured/legacy path.  The
    pointer is deliberately outside the release directory, so replacing the ZIP
    never creates a fresh warehouse by accident.
    """
    explicit = os.environ.get("AIBL_WAREHOUSE_PATH", "").strip()
    pointer = _warehouse_pointer_file()
    chosen: Path | None = Path(explicit).expanduser() if explicit else None
    if chosen is None and pointer.exists():
        try:
            raw = pointer.read_text(encoding="utf-8").strip()
            if raw:
                chosen = Path(raw).expanduser()
        except Exception:
            chosen = None
    if chosen is None:
        configured = getattr(SETTINGS, "WAREHOUSE_PATH", "") or os.path.join(SETTINGS.OUTPUT_DIR, "AIBL_warehouse.sqlite3")
        chosen = Path(configured).expanduser()
    chosen = chosen.resolve()
    chosen.parent.mkdir(parents=True, exist_ok=True)
    try:
        pointer.write_text(str(chosen), encoding="utf-8")
    except Exception as ex:
        log.warning("⚠️ ذخیره pointer دیتاورهاوس ناموفق بود: %s", ex)
    return Warehouse(chosen)
