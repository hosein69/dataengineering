# -*- coding: utf-8 -*-
import re
import pandas as pd
from gsi.studio_core.html_export import build_dynamic_html


def _sample(n=1200):
    df = pd.DataFrame({
        "CASE_KEY": [f"C{i}" for i in range(n)],
        "KEY_MATERIAL": [f"M{i%300}" for i in range(n)],
        "CANONICAL_ORDER": [f"O{i%500}" for i in range(n)],
        "ORG_DEPT": ["خرید" if i % 2 else "گمرک" for i in range(n)],
        "CANONICAL_EXPERT": [f"E{i%20}" for i in range(n)],
        "بحرانی (کوتاه)": ["بحرانی" if i % 11 == 0 else "ایمن" for i in range(n)],
        "مقاومت (روز)": [float(i % 50) for i in range(n)],
        "روزهای رسوب": [float(i % 90) for i in range(n)],
    })
    return df


def test_main_payload_is_row_array_not_repeated_record_objects():
    df = _sample()
    h = build_dynamic_html(df, "2026-09-20", max_rows=len(df), selected_fields=list(df.columns),
                           tabs=[{"title": "داده", "fields": list(df.columns), "blocks": ["table"]}],
                           audience="expert")
    m = re.search(r"const DATA=(.*?);\s*const COL_INDEX=", h, re.S)
    assert m, "DATA payload missing"
    payload = m.group(1).lstrip()
    assert payload.startswith("[["), "row-array encoding must be used"
    assert '"payload_encoding": "row_array_v1"' in h
    # Column names must live in metadata/index, not repeat once per row.
    assert h.count('"KEY_MATERIAL"') < 20


def test_process_runtime_does_not_duplicate_eventlog_or_action_queue():
    df = _sample(100)
    eventlog = pd.DataFrame({
        "_CASE_KEY": [f"C{i%20}" for i in range(500)],
        "ACTIVITY_FA": ["PR", "سفارش", "ارز", "حمل", "گمرک"] * 100,
        "EVENTTIME": pd.date_range("2026-01-01", periods=500, freq="h"),
        "GIANT_UNUSED_EVENT_FIELD": ["EVENT_PAYLOAD_SENTINEL"] * 500,
    })
    actions = pd.DataFrame({
        "CASE_KEY": [f"C{i%20}" for i in range(300)],
        "TITLE": ["پیگیری"] * 300,
        "GIANT_UNUSED_ACTION_FIELD": ["ACTION_PAYLOAD_SENTINEL"] * 300,
    })
    extras = {"eventlog": eventlog, "case_actions": actions}
    h = build_dynamic_html(df, "2026-09-20", max_rows=100, selected_fields=list(df.columns),
                           tabs=[{"title": "فرآیند", "fields": list(df.columns),
                                  "blocks": ["process", "kanban"],
                                  "process_views": ["flow_map", "case_timeline"]}],
                           process_extras=extras, audience="manager")
    # Static process/kanban markup may contain selected visible values, but the
    # huge unused source columns must never be re-embedded in runtime PROC JSON.
    assert "GIANT_UNUSED_EVENT_FIELD" not in h
    assert "GIANT_UNUSED_ACTION_FIELD" not in h
    assert "EVENT_PAYLOAD_SENTINEL" not in h
    assert "ACTION_PAYLOAD_SENTINEL" not in h
