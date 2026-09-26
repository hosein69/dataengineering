# -*- coding: utf-8 -*-
"""پاک‌کردن و ساخت دوبارهٔ انبار داده.

تا پیش از این هیچ مسیر پشتیبانی‌شده‌ای برای «از اول ساختن» نبود و تنها راه،
پاک‌کردن دستی فایل بود؛ کارِ دستی کش فریم و قفل نویسنده را جا می‌گذاشت.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from gsi.warehouse.store import Warehouse

ROOT = Path(__file__).resolve().parents[1]


def _seeded(tmp_path: Path) -> Warehouse:
    wh = Warehouse(tmp_path / "wh.sqlite")
    with wh.run({"kind": "test"}):
        wh.frame(pd.DataFrame({"a": [1, 2, 3]}), "standardized", "demo")
    return wh


def test_reset_refuses_without_explicit_confirmation(tmp_path):
    wh = _seeded(tmp_path)
    with pytest.raises(ValueError):
        wh.reset()
    with wh.db() as c:
        assert c.execute("SELECT count(*) FROM wh_run").fetchone()[0] == 1


def test_reset_refuses_a_database_that_is_not_a_gsi_warehouse(tmp_path):
    alien = tmp_path / "alien.sqlite"
    with sqlite3.connect(alien) as c:
        c.execute("CREATE TABLE payroll(id INTEGER)")
        c.execute("INSERT INTO payroll VALUES (1)")
    wh = Warehouse(alien, initialize=False)
    with pytest.raises(ValueError):
        wh.reset(confirm=True)
    with sqlite3.connect(alien) as c:
        assert c.execute("SELECT count(*) FROM payroll").fetchone()[0] == 1


def test_reset_backs_up_before_deleting(tmp_path):
    wh = _seeded(tmp_path)
    report = wh.reset(confirm=True)
    backup = Path(report["backup"])
    assert backup.exists()
    with sqlite3.connect(backup) as c:
        assert c.execute("SELECT count(*) FROM wh_run").fetchone()[0] == 1


def test_reset_clears_runs_frames_cache_and_lock(tmp_path):
    wh = _seeded(tmp_path)
    cache = wh.path.with_suffix(wh.path.suffix + ".frame_cache")
    lock = wh.path.with_suffix(".writer.lock")
    assert cache.is_dir() and lock.exists()
    wh.reset(confirm=True, keep_backup=False)
    assert not cache.exists(), "کش فریم باید پاک شود"
    assert lock.exists(), "Stable lock inode must survive reset"
    from gsi.warehouse.writer_lock import WriterLock
    with WriterLock(lock, timeout=0.1):
        pass  # A retained file is not a held OS lock.
    with wh.db() as c:
        assert c.execute("SELECT count(*) FROM wh_run").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM wh_frame").fetchone()[0] == 0
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_warehouse_is_usable_again_right_after_reset(tmp_path):
    wh = _seeded(tmp_path)
    wh.reset(confirm=True, keep_backup=False)
    with wh.run({"kind": "rebuild"}):
        wh.frame(pd.DataFrame({"b": [9]}), "standardized", "rebuilt")
    with wh.db() as c:
        assert c.execute("SELECT count(*) FROM wh_run").fetchone()[0] == 1
        assert c.execute("SELECT name FROM wh_frame").fetchone()[0] == "rebuilt"


def test_reset_on_a_missing_file_creates_an_empty_warehouse(tmp_path):
    wh = Warehouse(tmp_path / "absent.sqlite", initialize=False)
    report = wh.reset(confirm=True)
    assert report["existed"] is False and report["backup"] is None
    with wh.db() as c:
        assert c.execute("SELECT count(*) FROM wh_run").fetchone()[0] == 0


def test_cli_requires_yes_and_reports_what_it_removed(tmp_path):
    wh = _seeded(tmp_path)
    env = {"GSI_DWH_PATH": str(wh.path), "PYTHONPATH": str(ROOT), "PYTHONUTF8": "1"}
    import os
    env = {**os.environ, **env}
    dry = subprocess.run([sys.executable, "-m", "gsi.warehouse", "reset"],
                         capture_output=True, text=True, cwd=ROOT, env=env)
    assert dry.returncode == 2 and "--yes" in dry.stdout
    with wh.db() as c:
        assert c.execute("SELECT count(*) FROM wh_run").fetchone()[0] == 1
    done = subprocess.run([sys.executable, "-m", "gsi.warehouse", "reset", "--yes"],
                          capture_output=True, text=True, cwd=ROOT, env=env)
    assert done.returncode == 0 and '"recreated": true' in done.stdout
    with wh.db() as c:
        assert c.execute("SELECT count(*) FROM wh_run").fetchone()[0] == 0


def test_reset_still_empties_the_warehouse_when_the_file_cannot_be_deleted(tmp_path, monkeypatch):
    """Windows refuses to delete a file another handle still holds.

    A real Windows run reported `PermissionError: [WinError 32]` from this
    method. The contract of reset is that the warehouse is empty, not that the
    inode is gone, so an undeletable file must be emptied in place instead of
    failing the reset.
    """
    from pathlib import Path
    wh = _seeded(tmp_path)
    real_unlink = Path.unlink

    def stubborn(self, *a, **kw):
        if self.suffix == ".sqlite":
            raise PermissionError(32, "The process cannot access the file")
        return real_unlink(self, *a, **kw)

    monkeypatch.setattr(Path, "unlink", stubborn)
    report = wh.reset(confirm=True, keep_backup=False)
    monkeypatch.undo()

    assert report["emptied_in_place"] is True
    assert wh.path.name in report.get("undeleted", [])
    assert wh.path.exists(), "the file stays; only its contents go"
    with wh.db() as c:
        assert c.execute("SELECT count(*) FROM wh_run").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM wh_frame").fetchone()[0] == 0
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with wh.run({"kind": "rebuild"}):
        wh.frame(pd.DataFrame({"b": [9]}), "standardized", "rebuilt")
    with wh.db() as c:
        assert c.execute("SELECT name FROM wh_frame").fetchone()[0] == "rebuilt"
