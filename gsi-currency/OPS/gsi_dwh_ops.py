# -*- coding: utf-8 -*-
"""Safe operational helper for the GSI DWH (warehouse format 2).

This sidecar intentionally does not modify GSI business logic or schema.
- status / verify use SQLite read-only mode and never initialize a database.
- backup uses SQLite's online backup API and never copies a live DB byte-for-byte;
  the content-addressed archive folder (``<db>.objects``: source files and Parquet
  frames) is hard-linked or copied next to the backup, because format 2 keeps those
  bytes outside SQLite.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BLOCKING = ("BLOCK", "CRITICAL", "FATAL")
SCHEMA_VERSION = 2
REQUIRED_CORE = {
    "wh_meta", "wh_run", "wh_current", "wh_quality_check", "wh_publish_event", "wh_frame",
    "wh_object", "wh_source_load", "src_record", "src_change", "src_zdict", "dwh_entity",
}
#: history tables whose rows may only be appended (and, for versioned rows, closed once)
GUARDED = ("src_record", "src_change", "src_zdict", "wh_run")


def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _path() -> Path:
    raw = os.environ.get("GSI_DWH_PATH", "").strip()
    if not raw:
        # Same default as gsi.warehouse.store.default_data_root(): the documented
        # D:\GSI_DATA on Windows; ~/GSI_DATA elsewhere (never a relative "D:\..." dir).
        default = r"D:\GSI_DATA" if os.name == "nt" else str(Path.home() / "GSI_DATA")
        root = os.environ.get("GSI_DATA_ROOT", default).strip() or default
        raw = str(Path(root) / "warehouse.sqlite")
    if raw.startswith(("\\\\", "//")):
        raise SystemExit("ERROR: operational SQLite DWH must be on a local disk, not UNC/network storage")
    return Path(raw).expanduser().resolve()


def _ro(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(path)
    c = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=8)
    c.execute("PRAGMA query_only=ON")
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=8000")
    return c


def _tables(c: sqlite3.Connection) -> set[str]:
    return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _current(c: sqlite3.Connection) -> dict[str, str]:
    if "wh_current" not in _tables(c):
        return {}
    return {str(slot): str(rid) for slot, rid in c.execute("SELECT slot,run_id FROM wh_current ORDER BY slot")}


def _run(c: sqlite3.Connection, rid: str | None):
    if not rid:
        return None
    row = c.execute("SELECT id,started,finished,status,context,error FROM wh_run WHERE id=?", (rid,)).fetchone()
    if row is None:
        return None
    return {
        "id": row[0], "started": row[1], "finished": row[2], "status": row[3],
        "context": row[4], "error": row[5],
    }


def _failed_blocking(c: sqlite3.Connection, rid: str | None) -> list[dict]:
    if not rid:
        return []
    q = """SELECT contract,code,severity,detail
           FROM wh_quality_check
           WHERE run_id=? AND passed=0 AND severity IN ('BLOCK','CRITICAL','FATAL')
           ORDER BY seq"""
    return [
        {"contract": a, "code": b, "severity": s, "detail": d}
        for a, b, s, d in c.execute(q, (rid,)).fetchall()
    ]


def _print_kv(k, v):
    print(f"{k:<28}: {v}")


def _objects_root(path: Path) -> Path:
    return path.with_name(path.name + ".objects")


def _object_path(root: Path, sha: str, ext: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", str(sha)):
        raise ValueError(f"invalid object id: {sha!r}")
    return root / sha[:2] / f"{sha}.{ext}"


def _versioned_tables(c: sqlite3.Connection, ts: set[str]) -> list[str]:
    out = []
    for t in sorted(ts):
        if t.startswith("dwh_"):
            cols = {r[1] for r in c.execute(f'PRAGMA table_info("{t}")')}
            if {"from_seq", "to_seq", "vhash"} <= cols:
                out.append(t)
    return out


def _version_keys(c: sqlite3.Connection, table: str) -> list[str]:
    """Natural key columns of a versioned table = its UNIQUE(... ,from_seq) index minus from_seq."""
    for _seq, name, unique, *_ in c.execute(f'PRAGMA index_list("{table}")'):
        if not unique:
            continue
        cols = [r[2] for r in c.execute(f'PRAGMA index_info("{name}")')]
        if cols and cols[-1] == "from_seq":
            return cols[:-1]
    return []


def status(_args) -> int:
    p = _path()
    print("=== GSI DWH STATUS (READ-ONLY) ===")
    _print_kv("resolved_path", p)
    _print_kv("exists", p.exists())
    if not p.exists():
        print("NO_PUBLISHED_DWH: run REFRESH_GSI_DATA.cmd after source preflight.")
        return 2
    _print_kv("bytes", p.stat().st_size)
    try:
        with _ro(p) as c:
            version = c.execute("PRAGMA user_version").fetchone()[0]
            _print_kv("schema_user_version", version)
            ts = _tables(c)
            _print_kv("tables", len(ts))
            current = _current(c)
            _print_kv("current_slots", json.dumps(current, ensure_ascii=False))
            rid = current.get("dwh") or current.get("report")
            info = _run(c, rid)
            if info:
                _print_kv("published_run", info["id"])
                _print_kv("published_status", info["status"])
                _print_kv("published_started", info["started"])
                _print_kv("published_finished", info["finished"])
            else:
                _print_kv("published_run", "NONE")
            if "wh_publish_event" in ts:
                evt = c.execute("SELECT at,run_id,slots FROM wh_publish_event ORDER BY id DESC LIMIT 1").fetchone()
                _print_kv("last_publish_event", evt or "NONE")
            if rid:
                bad = _failed_blocking(c, rid)
                _print_kv("published_blocking_failures", len(bad))
            if version != SCHEMA_VERSION:
                _print_kv("warehouse_format", f"LEGACY v{version}: the next refresh archives it untouched and builds format 2")
            dwh_tables = _versioned_tables(c, ts)
            _print_kv("business_dwh_tables", len(dwh_tables))
            if "src_record" in ts:
                _print_kv("source_versions", c.execute("SELECT count(*) FROM src_record").fetchone()[0])
                _print_kv("source_open_rows", c.execute("SELECT count(*) FROM src_record WHERE to_seq IS NULL").fetchone()[0])
            if "src_change" in ts:
                _print_kv("change_log_rows", c.execute("SELECT count(*) FROM src_change").fetchone()[0])
            if "wh_object" in ts:
                n, size = c.execute("SELECT count(*),COALESCE(sum(size),0) FROM wh_object").fetchone()
                _print_kv("archived_objects", f"{n} ({size:,} bytes in {_objects_root(p).name})")
            recent = c.execute("SELECT id,started,finished,status,error FROM wh_run ORDER BY started DESC LIMIT 5").fetchall()
            print("recent_runs:")
            for row in recent:
                print("  -", row)
    except sqlite3.OperationalError as ex:
        print(f"DWH_READ_BUSY_OR_SQLITE_ERROR: {ex}")
        return 3
    return 0


def verify(_args) -> int:
    p = _path()
    print("=== GSI DWH VERIFY (READ-ONLY) ===")
    _print_kv("resolved_path", p)
    problems: list[str] = []
    if not p.exists():
        print("FAIL: warehouse does not exist")
        return 2
    try:
        with _ro(p) as c:
            version = c.execute("PRAGMA user_version").fetchone()[0]
            if version in (0, 1):
                problems.append(f"legacy warehouse format v{version}: run one refresh; it is archived untouched "
                                "and a format-2 warehouse is built")
            elif version != SCHEMA_VERSION:
                problems.append(f"unsupported/unexpected user_version={version}")
            ts = _tables(c)
            missing = sorted(REQUIRED_CORE - ts)
            if missing:
                problems.append("missing core tables: " + ", ".join(missing))
            integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
            _print_kv("integrity_check", integrity)
            if str(integrity).lower() != "ok":
                problems.append("PRAGMA integrity_check != ok")
            fk = c.execute("PRAGMA foreign_key_check").fetchall()
            _print_kv("foreign_key_errors", len(fk))
            if fk:
                problems.append(f"foreign key errors={len(fk)}")
            current = _current(c)
            _print_kv("current_slots", json.dumps(current, ensure_ascii=False))
            report = current.get("report")
            dwh = current.get("dwh")
            if not report or not dwh:
                problems.append("report/dwh published slots are not both present")
            elif report != dwh:
                problems.append(f"atomic publish mismatch: report={report}, dwh={dwh}")
            rid = dwh or report
            info = _run(c, rid)
            if not info:
                problems.append("published run row is missing")
            elif info["status"] != "completed":
                problems.append(f"published run status={info['status']}")
            bad = _failed_blocking(c, rid)
            _print_kv("blocking_failures_on_published", len(bad))
            if bad:
                problems.append("published run has blocking quality failures")
                for item in bad[:12]:
                    print("  BLOCK:", item["contract"], item["code"], item["severity"])
            # History guards: append-only / close-once triggers must be present.
            triggers = {r[0] for r in c.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")}
            dwh_tables = _versioned_tables(c, ts)
            unguarded = [t for t in (*GUARDED, *dwh_tables) if t in ts and t not in triggers]
            _print_kv("history_guards_missing", len(unguarded))
            if unguarded:
                problems.append("history tables without append-only/close-once guards: " + ", ".join(unguarded))
            # At most one open version per key, and no version closed before it opened.
            broken = []
            for t in dwh_tables:
                keys = _version_keys(c, t)
                if keys:
                    cols = ",".join(f'"{k}"' for k in keys)
                    dup = c.execute(f'SELECT count(*) FROM (SELECT 1 FROM "{t}" WHERE to_seq IS NULL '
                                    f'GROUP BY {cols} HAVING count(*)>1)').fetchone()[0]
                    if dup:
                        broken.append(f"{t}: {dup} keys with several open versions")
                bad = c.execute(f'SELECT count(*) FROM "{t}" WHERE to_seq IS NOT NULL AND to_seq<=from_seq').fetchone()[0]
                if bad:
                    broken.append(f"{t}: {bad} versions closed before they opened")
            if "src_record" in ts:
                dup = c.execute("SELECT count(*) FROM (SELECT 1 FROM src_record WHERE to_seq IS NULL "
                                "GROUP BY source,frame,rkey,occ HAVING count(*)>1)").fetchone()[0]
                if dup:
                    broken.append(f"src_record: {dup} records with several open versions")
            _print_kv("version_errors", len(broken))
            problems.extend(broken)
            # Format 2 keeps frame bytes outside SQLite: every object of the published run must be
            # present and must still hash to its name.
            if rid and "wh_object" in ts:
                root = _objects_root(p)
                objs = c.execute("SELECT DISTINCT o.sha,o.ext,o.size FROM wh_frame f JOIN wh_object o ON o.sha=f.object_sha "
                                 "WHERE f.run_id=?", (rid,)).fetchall()
                missing_objects = []
                for sha, ext, size in objs:
                    target = _object_path(root, sha, ext)
                    if not target.exists() or target.stat().st_size != int(size):
                        missing_objects.append(target.name)
                    elif hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                        missing_objects.append(target.name + " (content does not match its fingerprint)")
                _print_kv("published_frame_objects", f"{len(objs)} checked, {len(missing_objects)} missing/damaged")
                if missing_objects:
                    problems.append("published frames missing or damaged in the archive folder: "
                                    + ", ".join(missing_objects[:8]))
            if "wh_publish_event" in ts and rid:
                n = c.execute("SELECT count(*) FROM wh_publish_event WHERE run_id=?", (rid,)).fetchone()[0]
                _print_kv("publish_events_for_current", n)
                if n < 1:
                    problems.append("no publish event for current run")
    except sqlite3.OperationalError as ex:
        problems.append(f"SQLite operational error: {ex}")
    if problems:
        print("\nVERIFY_RESULT=FAIL")
        for x in problems:
            print(" -", x)
        return 2
    print("\nVERIFY_RESULT=PASS")
    return 0


def backup(args) -> int:
    src_path = _path()
    if not src_path.exists():
        print(f"FAIL: source DWH not found: {src_path}")
        return 2
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.output).expanduser().resolve() if args.output else (src_path.parent / "backups" / f"warehouse_{stamp}.sqlite")
    if str(out).startswith(("\\\\", "//")):
        print("FAIL: backup destination must be local")
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        print(f"FAIL: destination already exists: {out}")
        return 2
    try:
        with _ro(src_path) as src:
            ts = _tables(src)
            if "wh_meta" not in ts:
                print("FAIL: selected source is not a GSI warehouse")
                return 2
            dst = sqlite3.connect(out)
            try:
                src.backup(dst)
                dst.commit()
            finally:
                dst.close()
        with _ro(out) as check:
            integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
            fk = check.execute("PRAGMA foreign_key_check").fetchall()
            objects = (check.execute("SELECT sha,ext,size FROM wh_object").fetchall()
                       if "wh_object" in _tables(check) else [])
        if str(integrity).lower() != "ok" or fk:
            print(f"FAIL: backup verification failed integrity={integrity}, fk={len(fk)}")
            try:
                out.unlink()
            except Exception:
                pass
            return 2
        # Archived source files and frames: immutable, so a hard link is a safe copy.
        src_root, dst_root = _objects_root(src_path), _objects_root(out)
        missing = 0
        for sha, ext, size in objects:
            src = _object_path(src_root, sha, ext)
            dst = _object_path(dst_root, sha, ext)
            if not src.exists():
                missing += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
            if dst.stat().st_size != int(size):
                print(f"FAIL: archived object copy has the wrong size: {dst}")
                return 2
        print(f"objects: {len(objects) - missing} copied/linked to {dst_root}" + (f", {missing} missing in source" if missing else ""))
        if missing:
            print("BACKUP_RESULT=FAIL: the source archive folder is missing objects; run verify")
            return 2
        print(f"BACKUP_RESULT=PASS\n{out}")
        return 0
    except Exception as ex:
        print(f"BACKUP_RESULT=FAIL: {type(ex).__name__}: {ex}")
        return 3


def main(argv=None) -> int:
    _utf8()
    ap = argparse.ArgumentParser(description="Safe GSI DWH operations sidecar")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status", help="read-only DWH/publish/run status").set_defaults(fn=status)
    sp.add_parser("verify", help="read-only integrity/FK/publish/snapshot checks").set_defaults(fn=verify)
    b = sp.add_parser("backup", help="consistent local SQLite backup + verification")
    b.add_argument("--output", help="new local .sqlite path; defaults to <DWH>/backups/timestamp")
    b.set_defaults(fn=backup)
    ns = ap.parse_args(argv)
    return int(ns.fn(ns))


if __name__ == "__main__":
    raise SystemExit(main())
