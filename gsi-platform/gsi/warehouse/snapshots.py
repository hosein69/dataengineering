"""Run-scoped semantic snapshots; omission is not a business deletion event."""
from __future__ import annotations
import re

def tables(conn):
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'dwh_*' ORDER BY name")]

def capture(conn, run_id: str) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS wh_semantic_snapshot(run_id TEXT PRIMARY KEY REFERENCES wh_run(id))")
    if conn.execute("SELECT 1 FROM wh_semantic_snapshot WHERE run_id=?", (run_id,)).fetchone():
        raise ValueError("Semantic snapshot is immutable: " + run_id)
    for name in tables(conn):
        assert re.fullmatch(r"dwh_[a-z0-9_]+", name)
        target = "snap_" + name
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{target}" AS SELECT CAST(NULL AS TEXT) AS snapshot_run, * FROM "{name}" WHERE 0')
        conn.execute(f'CREATE INDEX IF NOT EXISTS "idx_{target}_run" ON "{target}"(snapshot_run)')
        for operation in ('UPDATE', 'DELETE'):
            conn.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{target}_{operation} BEFORE {operation} ON \"{target}\" BEGIN SELECT RAISE(ABORT, 'Immutable semantic snapshot'); END")
        columns = [r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')]
        for key in ('pr_key','po_key','reg_key','business_key','left_key','right_key','source'):
            if key in columns:
                conn.execute(f'CREATE INDEX IF NOT EXISTS "idx_{target}_{key}" ON "{target}"(snapshot_run,"{key}")')
        conn.execute(f'INSERT INTO "{target}" SELECT ?, * FROM "{name}"', (run_id,))
    conn.execute("INSERT INTO wh_semantic_snapshot VALUES(?)", (run_id,))

def bind_published(conn) -> None:
    """Connection-local views pin all business reads to one published run."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='wh_semantic_snapshot'").fetchone():
        # Legacy mutable rows cannot prove their published as-of state.
        for name in tables(conn):
            conn.execute(f'CREATE TEMP VIEW "{name}" AS SELECT * FROM main."{name}" WHERE 0')
        return
    row = conn.execute("SELECT run_id FROM wh_current WHERE slot IN ('dwh','report') ORDER BY CASE slot WHEN 'dwh' THEN 0 ELSE 1 END LIMIT 1").fetchone()
    rid = row[0] if row else ''
    literal = "'" + rid.replace("'", "''") + "'"
    for name in tables(conn):
        target = "snap_" + name
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (target,)).fetchone():
            continue
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')]
        projection = ','.join('"' + c + '"' for c in cols)
        conn.execute(f'CREATE TEMP VIEW "{name}" AS SELECT {projection} FROM main."{target}" WHERE snapshot_run={literal}')
    # Rebind dependent views so they resolve the connection-local base tables.
    for name, sql in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='view' AND name GLOB 'dwh_*'").fetchall():
        definition = sql[sql.upper().index(' AS') + 3:]
        conn.execute(f'CREATE TEMP VIEW "{name}" AS ' + definition)
