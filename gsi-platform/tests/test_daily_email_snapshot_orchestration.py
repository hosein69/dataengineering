# -*- coding: utf-8 -*-
"""Coverage for the daily-email orchestration fix.

Before this fix, ``create_daily_email`` unconditionally called
``Pipeline(today=d).run(build_report=True)`` -- a full pipeline re-run --
every time it was invoked, independent of whatever ``python -m gsi refresh``
had already published. RUNBOOK_FINAL_20260925_FA.md states Refresh must only
happen via an explicit action; a scheduled daily-email task silently
triggered one anyway, and could collide with a concurrent publisher (see
NETWORK_OUTLOOK_RELEASE_FA.md's "همزمان دو انتشار پشتیبانی نمی‌شود").

These tests mock the two collaborators at their lazy-import source
(``gsi.warehouse.service.last_report`` and ``gsi.pipeline.Pipeline``) so no
real warehouse or source files are needed, and assert the new contract:
  1. A published snapshot for the requested day is used as-is -- Pipeline
     is never constructed.
  2. No snapshot at all + refresh=False -> NoPublishedSnapshot, still no
     Pipeline call.
  3. No snapshot at all + refresh=True -> Pipeline runs exactly once.
  4. refresh=True but a concurrent publisher holds the writer lock
     (WarehouseBusyError) -> falls back to the last published snapshot
     instead of raising or retrying, and marks the result stale.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import gsi.warehouse.service as warehouse_service
import gsi.pipeline as pipeline_module
from gsi.integrations import daily_email
from gsi.warehouse.writer_lock import WarehouseBusyError


def _fake_main_df() -> pd.DataFrame:
    return pd.DataFrame({"KEY_MATERIAL": ["M1"], "CANONICAL_BL": ["B1"]})


@pytest.fixture(autouse=True)
def isolated_output(tmp_path, monkeypatch):
    monkeypatch.setenv("GSI_OUTPUT", str(tmp_path))
    monkeypatch.setenv("GSI_DAILY_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("GSI_TODAY", "2026-08-31")
    yield


def _write_excel_stub(tmp_path: Path) -> Path:
    p = tmp_path / "published.xlsx"
    p.write_bytes(b"stub")
    return p


class _CallCounter:
    def __init__(self):
        self.calls = 0


def test_uses_published_snapshot_without_running_pipeline(tmp_path, monkeypatch):
    excel_path = _write_excel_stub(tmp_path)
    counter = _CallCounter()

    def fake_last_report(ref_date=None):
        return (_fake_main_df(), _fake_main_df(), {}, str(excel_path))

    def fake_pipeline(*a, **k):
        counter.calls += 1
        raise AssertionError("Pipeline must not be constructed when a snapshot is published")

    monkeypatch.setattr(warehouse_service, "last_report", fake_last_report)
    monkeypatch.setattr(pipeline_module, "Pipeline", fake_pipeline)

    main_df, extras, dashboard_path, stale = daily_email._load_snapshot_or_run(
        date(2026, 8, 31), refresh=False
    )
    assert dashboard_path == str(excel_path)
    assert stale is False
    assert counter.calls == 0


def test_no_snapshot_no_refresh_raises_without_running_pipeline(monkeypatch):
    counter = _CallCounter()

    def fake_last_report(ref_date=None):
        return None

    def fake_pipeline(*a, **k):
        counter.calls += 1
        raise AssertionError("Pipeline must not run when refresh=False")

    monkeypatch.setattr(warehouse_service, "last_report", fake_last_report)
    monkeypatch.setattr(pipeline_module, "Pipeline", fake_pipeline)

    with pytest.raises(daily_email.NoPublishedSnapshot):
        daily_email._load_snapshot_or_run(date(2026, 8, 31), refresh=False)
    assert counter.calls == 0


def test_no_snapshot_with_refresh_runs_pipeline_exactly_once(tmp_path, monkeypatch):
    excel_path = _write_excel_stub(tmp_path)
    counter = _CallCounter()

    def fake_last_report(ref_date=None):
        return None

    class FakeResult:
        main = _fake_main_df()
        extras = {"runtime_status": "FRESH_RUN"}
        dashboard_path = str(excel_path)

    class FakePipeline:
        def __init__(self, today=None):
            counter.calls += 1
            self.today = today

        def run(self, build_report=True):
            return FakeResult()

    monkeypatch.setattr(warehouse_service, "last_report", fake_last_report)
    monkeypatch.setattr(pipeline_module, "Pipeline", FakePipeline)

    main_df, extras, dashboard_path, stale = daily_email._load_snapshot_or_run(
        date(2026, 8, 31), refresh=True
    )
    assert dashboard_path == str(excel_path)
    assert stale is False
    assert counter.calls == 1


def test_concurrent_publisher_falls_back_to_last_snapshot_instead_of_stacking_a_run(
    tmp_path, monkeypatch
):
    excel_path = _write_excel_stub(tmp_path)
    calls = {"last_report": 0}

    def fake_last_report(ref_date=None):
        calls["last_report"] += 1
        # Call 1: last_report(ref) for the requested day -> miss.
        # Call 2: last_report(None) stale-fallback lookup -> also miss
        #         (nothing has ever been published yet).
        # Call 3: the WarehouseBusyError recovery lookup, after Pipeline.run()
        #         collided with a concurrent publisher -> a snapshot exists now.
        if calls["last_report"] <= 2:
            return None
        return (_fake_main_df(), _fake_main_df(), {}, str(excel_path))

    pipeline_calls = {"n": 0}

    class FakePipeline:
        def __init__(self, today=None):
            pipeline_calls["n"] += 1

        def run(self, build_report=True):
            raise WarehouseBusyError(tmp_path / "warehouse.sqlite", {"host": "other-host", "pid": 999})

    monkeypatch.setattr(warehouse_service, "last_report", fake_last_report)
    monkeypatch.setattr(pipeline_module, "Pipeline", FakePipeline)

    main_df, extras, dashboard_path, stale = daily_email._load_snapshot_or_run(
        date(2026, 8, 31), refresh=True
    )
    assert dashboard_path == str(excel_path)
    assert stale is True
    assert extras["runtime_status"] == "UPDATE_IN_PROGRESS"
    # last_report was consulted three times: requested day (miss), stale
    # fallback (miss), then the busy-writer recovery (hit). Pipeline itself
    # was constructed and run exactly once -- no retry loop.
    assert calls["last_report"] == 3
    assert pipeline_calls["n"] == 1


def test_cli_refresh_flag_is_wired_through(monkeypatch):
    seen = {}

    def fake_create_daily_email(*, send, display, refresh):
        seen["refresh"] = refresh
        return {"excel": "x", "html": "y", "charts": [], "recipients": [], "sent": False,
                "stale_snapshot": False}

    monkeypatch.setattr(daily_email, "create_daily_email", fake_create_daily_email)
    rc = daily_email.main(["--refresh"])
    assert rc == 0
    assert seen["refresh"] is True


def test_cli_no_snapshot_exits_nonzero_with_explicit_message(monkeypatch, capsys):
    def fake_create_daily_email(*, send, display, refresh):
        raise daily_email.NoPublishedSnapshot("no snapshot for 2026-08-31")

    monkeypatch.setattr(daily_email, "create_daily_email", fake_create_daily_email)
    rc = daily_email.main([])
    assert rc == 3
    assert "no snapshot" in capsys.readouterr().out
