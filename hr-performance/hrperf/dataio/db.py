# -*- coding: utf-8 -*-
"""پایگاه داده SQLite — تاریخچه اجرا، امتیاز، وزن و اثر.

چرا SQLite: بدون سرور، تک‌فایل، قابل کپی روی شبکه، و برای این حجم
(چند صد نفر × چند ده شاخص × چند اجرا) کاملاً کافی. هر اجرا یک ``run``
است، پس روند زمانی و مقایسه دوره‌ای بدون بازنویسی داده قبلی ممکن می‌شود.
"""
from __future__ import annotations

__contract__ = 1

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd

from ..config.settings import SETTINGS

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS runs (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_date      TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    model_version TEXT,
    package_version TEXT,
    n_people      INTEGER,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS people (
    run_id      INTEGER NOT NULL,
    person_key  TEXT NOT NULL,
    full_name   TEXT,
    personnel_id TEXT,
    vice        TEXT,
    management  TEXT,
    department  TEXT,
    job_family  TEXT,
    role        TEXT,
    manager     TEXT,
    head        TEXT,
    active      INTEGER,
    peer_group  TEXT,
    peer_level  TEXT,
    peer_size   INTEGER,
    peer_is_fallback INTEGER,
    PRIMARY KEY (run_id, person_key),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS metric_values (
    run_id     INTEGER NOT NULL,
    person_key TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    raw_value  REAL,
    sample_n   REAL,
    shrunk     REAL,
    score      REAL,
    percentile REAL,
    evidence   REAL,
    PRIMARY KEY (run_id, person_key, metric_key),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cluster_scores (
    run_id      INTEGER NOT NULL,
    person_key  TEXT NOT NULL,
    cluster_key TEXT NOT NULL,
    score       REAL,
    coverage    REAL,
    PRIMARY KEY (run_id, person_key, cluster_key),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS performance (
    run_id      INTEGER NOT NULL,
    person_key  TEXT NOT NULL,
    score       REAL,
    fair_score  REAL,
    expected    REAL,
    coverage    REAL,
    evidence    REAL,
    confidence  REAL,
    peer_rank   INTEGER,
    peer_n      INTEGER,
    PRIMARY KEY (run_id, person_key),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS weights (
    run_id      INTEGER NOT NULL,
    level       TEXT NOT NULL,      -- 'cluster' | 'metric'
    key         TEXT NOT NULL,
    cluster_key TEXT,
    weight      REAL,
    effective   REAL,
    PRIMARY KEY (run_id, level, key),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS causal_effects (
    run_id     INTEGER NOT NULL,
    treatment  TEXT NOT NULL,
    outcome    TEXT NOT NULL,
    raw        REAL,
    adjusted   REAL,
    adjust_set TEXT,
    e_value    REAL,
    n          INTEGER,
    misleading INTEGER,
    PRIMARY KEY (run_id, treatment, outcome),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit (
    run_id  INTEGER NOT NULL,
    kind    TEXT NOT NULL,
    payload TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_perf_run   ON performance(run_id);
CREATE INDEX IF NOT EXISTS ix_metric_run ON metric_values(run_id, metric_key);
CREATE INDEX IF NOT EXISTS ix_people_mg  ON people(run_id, management, department);
"""


@contextmanager
def connect(path: Optional[str | Path] = None):
    p = Path(path or SETTINGS.DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init(path: Optional[str | Path] = None) -> Path:
    with connect(path) as c:
        c.executescript(SCHEMA)
    return Path(path or SETTINGS.DB_PATH)


def start_run(ref_date: str, model_version: str, package_version: str,
              n_people: int, notes: str = "",
              path: Optional[str | Path] = None) -> int:
    with connect(path) as c:
        cur = c.execute(
            "INSERT INTO runs (ref_date, created_at, model_version,"
            " package_version, n_people, notes) VALUES (?,?,?,?,?,?)",
            (ref_date, datetime.now().isoformat(timespec="seconds"),
             model_version, package_version, int(n_people), notes))
        return int(cur.lastrowid)


def write_frame(df: pd.DataFrame, table: str, run_id: int,
                path: Optional[str | Path] = None) -> int:
    """درج یک دیتافریم در جدول، با ستون run_id."""
    if df is None or df.empty:
        return 0
    out = df.copy()
    out.insert(0, "run_id", run_id)
    with connect(path) as c:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
        keep = [x for x in out.columns if x in cols]
        out = out[keep]
        out.to_sql(table, c, if_exists="append", index=False)
    return len(out)


def write_audit(kind: str, payload, run_id: int,
                path: Optional[str | Path] = None) -> None:
    with connect(path) as c:
        c.execute("INSERT INTO audit (run_id, kind, payload) VALUES (?,?,?)",
                  (run_id, kind, json.dumps(payload, ensure_ascii=False,
                                            default=str)))


def read(sql: str, params: Iterable = (), path: Optional[str | Path] = None
         ) -> pd.DataFrame:
    with connect(path) as c:
        return pd.read_sql_query(sql, c, params=list(params))


def latest_run(path: Optional[str | Path] = None) -> Optional[int]:
    df = read("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1", path=path)
    return int(df.iloc[0, 0]) if not df.empty else None


def runs(path: Optional[str | Path] = None) -> pd.DataFrame:
    return read("SELECT * FROM runs ORDER BY run_id DESC", path=path)
