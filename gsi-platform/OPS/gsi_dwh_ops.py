# -*- coding: utf-8 -*-
"""Safe operational helper for the GSI DWH (version-independent).

This sidecar intentionally does not modify GSI business logic or schema.
- status / verify use SQLite read-only mode and never initialize a database.
- backup uses SQLite's online backup API and never copies a live DB byte-for-byte.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BLOCKING = ("BLOCK", "CRITICAL", "FATAL")
REQUIRED_CORE = {
    "wh_meta", "wh_run", "wh_current", "wh_quality_check",
    "wh_publish_event", "wh_frame", "wh_frame_row",
}


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
            if "wh_semantic_snapshot" in ts and rid:
                n = c.execute("SELECT count(*) FROM wh_semantic_snapshot WHERE run_id=?", (rid,)).fetchone()[0]
                _print_kv("immutable_semantic_snapshot", "YES" if n == 1 else "NO")
            dwh_tables = sorted(t for t in ts if t.startswith("dwh_") and not t.startswith("dwh_schema"))
            _print_kv("business_dwh_tables", len(dwh_tables))
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
            if version != 1:
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
            if "wh_semantic_snapshot" not in ts:
                problems.append("wh_semantic_snapshot missing")
            elif rid:
                n = c.execute("SELECT count(*) FROM wh_semantic_snapshot WHERE run_id=?", (rid,)).fetchone()[0]
                _print_kv("semantic_snapshot_rows", n)
                if n != 1:
                    problems.append("published run does not have exactly one immutable semantic snapshot")
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
        if str(integrity).lower() != "ok" or fk:
            print(f"FAIL: backup verification failed integrity={integrity}, fk={len(fk)}")
            try:
                out.unlink()
            except Exception:
                pass
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
