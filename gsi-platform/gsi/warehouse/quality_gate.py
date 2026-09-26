from __future__ import annotations

"""Warehouse publication quality gate.

The gate is deliberately independent from Streamlit and business stages.
A failed gate keeps diagnostics but prevents the current pointer from moving.
"""

from dataclasses import dataclass
from typing import Iterable
import sqlite3

from .reliability import Check, BLOCK, blocking


@dataclass(frozen=True)
class GateResult:
    passed: bool
    blocking_codes: tuple[str, ...]


def sqlite_checks(conn: sqlite3.Connection) -> list[Check]:
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    integrity = conn.execute("PRAGMA integrity_check").fetchone()
    integrity_value = integrity[0] if integrity else "unknown"
    return [
        Check("sqlite", "FOREIGN_KEY_CHECK", BLOCK, len(fk) == 0, {"violations": fk[:50], "count": len(fk)}),
        Check("sqlite", "INTEGRITY_CHECK", BLOCK, integrity_value == "ok", {"result": integrity_value}),
    ]


def evaluate(checks: Iterable[Check]) -> GateResult:
    bad = blocking(checks)
    return GateResult(not bad, tuple(f"{x.contract}:{x.code}" for x in bad))
