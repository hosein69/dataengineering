from __future__ import annotations

"""Warehouse publication quality gate.

The gate is deliberately independent from Streamlit and business stages.
A failed gate keeps diagnostics but prevents the current pointer from moving.
"""

from dataclasses import dataclass
from typing import Iterable
import os
import sqlite3

from .reliability import Check, BLOCK, blocking


@dataclass(frozen=True)
class GateResult:
    passed: bool
    blocking_codes: tuple[str, ...]


def sqlite_foreign_key_check(conn: sqlite3.Connection) -> Check:
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    return Check(
        "sqlite", "FOREIGN_KEY_CHECK", BLOCK, len(fk) == 0,
        {"violations": fk[:50], "count": len(fk)},
    )


def _full_integrity_enabled() -> bool:
    return os.environ.get("GSI_SQLITE_FULL_INTEGRITY_CHECK", "").strip().lower() in (
        "1", "true", "yes", "on"
    )


def sqlite_integrity_check(conn: sqlite3.Connection, *, full: bool | None = None) -> Check:
    if full is None:
        full = _full_integrity_enabled()
    pragma = "integrity_check" if full else "quick_check"
    integrity = conn.execute(f"PRAGMA {pragma}").fetchone()
    integrity_value = integrity[0] if integrity else "unknown"
    return Check(
        "sqlite", "INTEGRITY_CHECK", BLOCK, integrity_value == "ok",
        {"result": integrity_value, "mode": "full" if full else "quick", "pragma": pragma},
    )


def sqlite_checks(conn: sqlite3.Connection) -> list[Check]:
    """Production-safe SQLite gate.

    Foreign keys are always checked. The normal refresh path uses SQLite's
    quick_check to avoid a full index/content validation on every DWH rebuild.
    Set GSI_SQLITE_FULL_INTEGRITY_CHECK=1 for release/forensic runs that need
    the complete integrity_check. The public check code stays INTEGRITY_CHECK
    so downstream quality-gate contracts remain stable.
    """
    return [sqlite_foreign_key_check(conn), sqlite_integrity_check(conn)]


def evaluate(checks: Iterable[Check]) -> GateResult:
    bad = blocking(checks)
    return GateResult(not bad, tuple(f"{x.contract}:{x.code}" for x in bad))
