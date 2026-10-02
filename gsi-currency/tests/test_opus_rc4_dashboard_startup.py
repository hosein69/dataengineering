# -*- coding: utf-8 -*-
"""سرعت بالا آمدن داشبورد.

اندازه‌گیری روی همین بسته (۶ ردیف): اجرای کامل خط لوله با ساخت گزارش ۳٫۵۴
ثانیه، بدون ساخت گزارش ۱٫۷۳ ثانیه، و خواندن Snapshot منتشرشده ۰٫۰۰۵ ثانیه.
روی دادهٔ واقعی نسبت این سه بسیار بزرگ‌تر است. ``app/studio.py`` از ابتدا
Snapshot را اول می‌خواند؛ ``app/dashboard.py`` این کار را نمی‌کرد.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = (ROOT / "app" / "dashboard.py").read_text(encoding="utf-8")


def test_dashboard_reads_the_published_snapshot_before_running_the_pipeline():
    assert "def load_published(" in DASHBOARD
    order = DASHBOARD.index("data = None if _rerun else load_published(ref_date)")
    assert DASHBOARD.index("data = load_pipeline(ref_date)", order) > order, (
        "خط لوله فقط باید وقتی اجرا شود که Snapshot منتشرشده‌ای نباشد")


def test_explicit_button_still_forces_a_fresh_pipeline_run():
    assert '_rerun = st.sidebar.button("اجرای مجدد خط لوله"' in DASHBOARD
    assert "if _rerun:\n    st.cache_data.clear()" in DASHBOARD


def test_dashboard_caches_are_bounded():
    """کش بدون سقف و بدون انقضا، حافظه را در یک نشست طولانی پر می‌کند."""
    decorators = re.findall(r"@st\.cache_data\(([^)]*)\)", DASHBOARD)
    assert decorators, "داشبورد باید کش داشته باشد"
    for d in decorators:
        assert "max_entries" in d and "ttl" in d, f"کش بی‌سقف: {d}"


def test_dashboard_never_materializes_lazy_extras_eagerly():
    tree = ast.parse(DASHBOARD)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "dict" and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "extras"):
            pytest.fail("dict(extras) نگاشت تنبل را کامل باز می‌کند و همان کندی برمی‌گردد")


# ═════════ محدودکردن دامنه باید تنبل بماند و همچنان اعمال شود ═════════

def test_scoping_stays_lazy_but_is_still_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("GSI_DWH_PATH", str(tmp_path / "wh.sqlite"))
    from gsi.warehouse.service import LazyFrameExtras
    from gsi.warehouse.store import Warehouse
    from gsi.studio_core.report_builder import _filtered_process_extras

    wh = Warehouse()
    wide = pd.DataFrame({"KEY_REG": ["R1", "R2", "R3"], "V": [1, 2, 3]})
    with wh.run({"reference_date": "2026-09-21"}):
        fid = wh.frame(wide, "mart", "extras/process_evidence")
    extras = LazyFrameExtras(wh.path, {"flag": True}, {"process_evidence": fid})
    assert "process_evidence" not in extras.materialized_keys()

    scoped = _filtered_process_extras(extras, pd.DataFrame({"KEY_REG": ["R1"]}))
    assert isinstance(scoped, LazyFrameExtras)
    assert "process_evidence" not in scoped.materialized_keys(), (
        "فریمی که هیچ نمایی نخواسته نباید همان لحظه از SQLite ساخته شود")

    got = scoped["process_evidence"]
    assert list(got["KEY_REG"]) == ["R1"], "دامنه باید هنگام دسترسی تنبل هم اعمال شود"


def test_already_materialized_frames_are_scoped_too(tmp_path, monkeypatch):
    monkeypatch.setenv("GSI_DWH_PATH", str(tmp_path / "wh.sqlite"))
    from gsi.warehouse.service import LazyFrameExtras
    from gsi.studio_core.report_builder import _filtered_process_extras
    eager = pd.DataFrame({"KEY_REG": ["R1", "R9"], "V": [1, 9]})
    extras = LazyFrameExtras(tmp_path / "wh.sqlite", {"eventlog": eager})
    scoped = _filtered_process_extras(extras, pd.DataFrame({"KEY_REG": ["R1"]}))
    assert list(scoped["eventlog"]["KEY_REG"]) == ["R1"]


def test_plain_dict_extras_still_work_unchanged():
    from gsi.studio_core.report_builder import _filtered_process_extras
    extras = {"eventlog": pd.DataFrame({"KEY_REG": ["R1", "R9"]}), "scalar": 3}
    out = _filtered_process_extras(extras, pd.DataFrame({"KEY_REG": ["R1"]}))
    assert isinstance(out, dict)
    assert list(out["eventlog"]["KEY_REG"]) == ["R1"] and out["scalar"] == 3
