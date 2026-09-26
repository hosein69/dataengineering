# -*- coding: utf-8 -*-
import os
from pathlib import Path
import pandas as pd

from gsi.studio_core.composer import normalize_blocks, normalize_tabs
from gsi.studio_core.designs import ReportDesign, save_design, load_design
from gsi.studio_core.html_export import build_dynamic_html


def _sample():
    df = pd.DataFrame({
        "KEY_MATERIAL": ["M1", "M2"],
        "CANONICAL_ORDER": ["O1", "O2"],
        "KEY_REG": ["R1", "R2"],
        "CASE_KEY": ["R1", "R2"],
        "کد طبقه بحرانی": ["CRITICAL", "SAFE"],
        "بحرانی (کوتاه)": ["بحرانی", "ایمن"],
        "مقاومت (روز)": [5.0, 60.0],
    })
    extras = {
        "eventlog": pd.DataFrame({"_CASE_KEY": ["R1", "R1"], "ACTIVITY_FA": ["ثبت سفارش", "تخصیص ارز"], "EVENTTIME": ["2026-09-01", "2026-09-05"]}),
        "bottlenecks": pd.DataFrame({"از فعالیت": ["ثبت سفارش"], "به فعالیت": ["تخصیص ارز"], "میانه روز": [4.0]}),
        "variants": pd.DataFrame({"مسیر": ["ثبت سفارش > تخصیص ارز"], "تعداد پرونده": [1]}),
        "case_actions": pd.DataFrame({"CASE_KEY": ["R1", "R2"], "STATUS": ["مسدود", "نیازمند اقدام"], "NEXT_ACTION": ["پیگیری ارز", "تماس با کارشناس"], "OWNER": ["حسین", "علی"]}),
    }
    return df, extras


def test_tab_blocks_keep_author_order():
    t = normalize_tabs([{"title": "X", "fields": ["A"], "blocks": ["table", "charts", "kpi"]}], ["A"], "manager")
    assert t[0]["blocks"] == ["table", "charts", "kpi"]


def test_html_composer_process_kanban_order_and_header():
    df, extras = _sample()
    blocks = ["charts", "process", "kanban", "table", "kpi"]
    h = build_dynamic_html(
        df, "2026-09-20", selected_fields=["KEY_MATERIAL", "مقاومت (روز)"],
        tabs=[{"title": "مدیریتی", "fields": ["KEY_MATERIAL", "مقاومت (روز)"], "blocks": blocks}],
        charts=["criticality"], process_extras=extras, audience="manager",
        header_title="هدر اختصاصی مدیر", header_subtitle="زیرعنوان اختصاصی")
    assert "هدر اختصاصی مدیر" in h and "زیرعنوان اختصاصی" in h
    assert "کانبان / Scrum Action Board" in h
    assert "فرآیند و گلوگاه‌ها" in h
    positions = [h.index(f'data-composer-block="{x}"') for x in blocks]
    assert positions == sorted(positions)
    assert "پیگیری ارز" in h


def test_saved_design_persists_layout_persona_headers(tmp_path, monkeypatch):
    monkeypatch.setenv("GSI_DESIGNS", str(tmp_path))
    d = ReportDesign(
        name="manager-only-charts", persona="manager",
        tabs=[{"title": "فقط نمودار", "fields": ["KEY_MATERIAL"], "blocks": ["charts", "process"]}],
        html_header="گزارش مدیر", html_subtitle="فقط موارد تصمیم",
        html_header_preset="executive_navy", email_header="ایمیل مدیر",
        email_subtitle="خلاصه روزانه")
    save_design(d)
    r = load_design(d.name)
    assert r.persona == "manager"
    assert r.tabs[0]["blocks"] == ["charts", "process"]
    assert r.html_header == "گزارش مدیر"
    assert r.email_header == "ایمیل مدیر"
    assert r.email_subtitle == "خلاصه روزانه"
