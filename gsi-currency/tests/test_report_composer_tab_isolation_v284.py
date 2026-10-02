# -*- coding: utf-8 -*-
import pandas as pd

from gsi.studio_core.composer import normalize_tabs
from gsi.studio_core.html_export import build_dynamic_html
from gsi.studio_core.report_builder import _filtered_process_extras


def _data():
    df = pd.DataFrame({
        "CASE_KEY": ["C1", "C2"],
        "KEY_REG": ["R1", "R2"],
        "KEY_MATERIAL": ["M1", "M2"],
        "CANONICAL_ORDER": ["O1", "O2"],
        "بحرانی (کوتاه)": ["بحرانی", "ایمن"],
        "مقاومت (روز)": [5.0, 55.0],
    })
    ev = pd.DataFrame({
        "_CASE_KEY": ["C1", "C1", "C2", "C2"],
        "ACTIVITY_FA": ["ثبت سفارش", "تخصیص ارز", "ثبت سفارش", "حمل"],
        "EVENTTIME": pd.to_datetime(["2026-09-01", "2026-09-05", "2026-09-02", "2026-09-07"]),
        "_SORTING": [1, 2, 1, 3],
    })
    cases = pd.DataFrame({
        "CASE_KEY": ["C1", "C2"],
        "CASE_STATE": ["OPEN", "OPEN"],
        "LAST_ACTIVITY": ["تخصیص ارز", "حمل"],
        "CURRENT_WAIT_DAYS": [12.0, 3.0],
        "VARIANT": ["ثبت سفارش ← تخصیص ارز", "ثبت سفارش ← حمل"],
        "THROUGHPUT_DAYS": [pd.NA, pd.NA],
    })
    actions = pd.DataFrame({
        "KEY_REG": ["R1", "R2"],
        "TITLE": ["پیگیری تخصیص", "پیگیری حمل"],
        "OWNER_ROLE": ["کارشناس الف", "کارشناس ب"],
        "PRIORITY": ["CRITICAL", "LOW"],
        "DAYS_REMAINING": [-1, 9],
    })
    return df, {"eventlog": ev, "case_table": cases, "case_actions": actions}


def test_legacy_global_charts_migrate_only_to_first_tab():
    tabs = normalize_tabs([
        {"title": "A", "fields": ["KEY_MATERIAL"]},
        {"title": "B", "fields": ["KEY_MATERIAL"]},
    ], ["KEY_MATERIAL"], "manager", ["criticality", "low_resistance"])
    assert tabs[0]["charts"] == ["criticality", "low_resistance"]
    assert tabs[1]["charts"] == []
    assert tabs[0]["id"] != tabs[1]["id"]


def test_html_tabs_are_structurally_isolated():
    df, extras = _data()
    scoped = _filtered_process_extras(extras, df)
    tabs = [
        {"id": "tab_proc", "title": "فقط فرآیند", "fields": ["KEY_MATERIAL"],
         "blocks": ["process"], "process_views": ["flow_map", "transition_heatmap"], "charts": []},
        {"id": "tab_kan", "title": "فقط کانبان", "fields": ["KEY_REG"],
         "blocks": ["kanban"], "kanban_mode": "due_window", "kanban_card_fields": ["title", "owner", "due"], "charts": []},
        {"id": "tab_chart", "title": "نمودار و جدول", "fields": ["KEY_MATERIAL", "مقاومت (روز)"],
         "blocks": ["charts", "table"], "charts": ["criticality"], "process_views": []},
    ]
    h = build_dynamic_html(df, "2026-09-20", selected_fields=list(df.columns), tabs=tabs,
                           process_extras=scoped, audience="manager", charts=["low_resistance"])
    assert ".pane[hidden]{display:none!important}" in h
    p1 = h[h.index('id="pane_tab_proc"'):h.index('id="pane_tab_kan"')]
    p2 = h[h.index('id="pane_tab_kan"'):h.index('id="pane_tab_chart"')]
    p3 = h[h.index('id="pane_tab_chart"'):h.index('</main>')]
    assert 'data-composer-block="process"' in p1
    assert 'PROCESS MINING STUDIO' in p1
    assert 'data-composer-block="kanban"' not in p1
    assert 'data-composer-block="table"' not in p1
    assert 'data-composer-block="kanban"' in p2
    assert 'پیگیری تخصیص' in p2
    assert 'data-composer-block="process"' not in p2
    assert 'data-composer-block="charts"' in p3 and 'data-composer-block="table"' in p3
    assert 'data-composer-block="kanban"' not in p3 and 'data-composer-block="process"' not in p3
    # Global fallback chart must not leak into a tab with explicit choices.
    assert '"criticality"' in h


def test_process_and_actions_follow_authorized_scope():
    df, extras = _data()
    scoped_df = df[df["KEY_REG"].eq("R1")].copy()
    out = _filtered_process_extras(extras, scoped_df)
    assert set(out["eventlog"]["_CASE_KEY"].astype(str)) == {"C1"}
    assert set(out["case_table"]["CASE_KEY"].astype(str)) == {"C1"}
    assert set(out["case_actions"]["KEY_REG"].astype(str)) == {"R1"}
    assert set(out["stage_queue"]["مرحله جاری"].astype(str)) == {"تخصیص ارز"}
    assert out["variants"]["تعداد پرونده"].sum() == 1
    assert set(out["bottlenecks"]["از فعالیت"].astype(str)) == {"ثبت سفارش"}


def test_timeline_has_local_escape_runtime():
    df, extras = _data()
    h = build_dynamic_html(df, "2026-09-20", selected_fields=list(df.columns),
                           tabs=[{"id":"tl","title":"Timeline","fields":["CASE_KEY"],
                                  "blocks":["process"],"process_views":["case_timeline"]}],
                           process_extras=extras, audience="analyst")
    assert "const E=s=>" in h
    assert "esc2(x.a)" not in h
