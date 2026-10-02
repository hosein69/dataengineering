# -*- coding: utf-8 -*-
"""29.17 — زبان یک‌دست عنوان ستون‌ها (فارسی / English) و آیکن‌های مینیمال.

قفل‌ها:
  * هر ستونی که سیستم می‌شناسد (adapterها، stageها، کاتالوگ محاسباتی و
    عنوان‌های فارسی نماها) در حالت English عنوان بدون حرف فارسی دارد؛
  * در حالت فارسی، کلید فنی بدون برچسب هم عنوان فارسی می‌گیرد؛
  * هیچ جدولی عنوان تکراری نمی‌گیرد؛
  * data_editor ستون‌ها را به نام اصلی برمی‌گرداند تا کد نما نشکند؛
  * آیکن‌ها و گیج‌ها فقط رنگ توکن دارند و نامعلوم «—» است، نه صفر.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd

from gsi.design import icons as I
from gsi.design import tokens as T
from gsi.i18n import columns as C
from gsi.i18n.key_fa import fa_from_key

ROOT = Path(__file__).resolve().parents[1]
FA = re.compile(r"[؀-ۿ]")
HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")


def _known_columns():
    from gsi.studio_core.field_catalog import COMPUTED_LABELS, source_field_map
    from gsi.stages.base import collect_columns, discover
    cols = set(source_field_map()) | set(COMPUTED_LABELS)
    cols |= {c.key for c in collect_columns(discover())}
    return cols


def _view_headers():
    """عنوان‌های فارسی که نماها به‌عنوان نام ستون می‌سازند (rename و ردیف‌های dict)."""
    out = set()
    # نماهای چرخه ارز از نسخه 29.18 عنوان‌هایشان را از مدل مشترک گزارش می‌گیرند
    files = list((ROOT / "app").glob("*.py")) + [ROOT / "gsi/report" / f for f in (
        "critical_board.py", "fx_insight.py", "fx_html.py", "fx_excel.py")]
    for p in files:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "rename":
                for kw in n.keywords:
                    if kw.arg == "columns" and isinstance(kw.value, ast.Dict):
                        out |= {v.value for v in kw.value.values
                                if isinstance(v, ast.Constant) and isinstance(v.value, str)}
            if isinstance(n, ast.Dict) and n.keys and all(isinstance(k, ast.Constant) for k in n.keys):
                keys = [k.value for k in n.keys]
                const_vals = all(isinstance(v, ast.Constant) for v in n.values)   # نگاشت ثابت، نه ردیف داده
                if not const_vals and len(keys) >= 3 and all(isinstance(k, str) and FA.search(k) and len(k) < 60
                                                              for k in keys):
                    out |= set(keys)
    return {h for h in out if FA.search(h)}


def test_every_known_column_has_an_english_title():
    cols = _known_columns()
    assert len(cols) > 300
    bad = [c for c in cols if FA.search(C.label(c, C.EN))]
    assert not bad, bad[:20]


def test_every_persian_view_header_has_an_english_title():
    heads = _view_headers()
    assert len(heads) > 100
    bad = sorted(h for h in heads if FA.search(C.label(h, C.EN)))
    assert not bad, bad[:30]


def test_technical_keys_get_persian_titles_in_persian_mode():
    assert fa_from_key("BL_DISCHARGE_DATE") == "تاریخ تخلیه بارنامه"
    assert fa_from_key("IS_IN_CUSTOMS") == "در گمرک؟"
    assert fa_from_key("FX_EUR_VALUE_IS_UNKNOWN").endswith("نامعلوم")
    assert C.label("CURRENT_WAIT_DAYS", C.FA) == "انتظار جاری (روز)"
    latin_only = [c for c in _known_columns()
                  if re.fullmatch(r"_?[A-Z][A-Z0-9_]*", c) and not FA.search(C.label(c, C.FA))]
    assert not latin_only, latin_only[:20]


def test_english_titles_read_like_english():
    assert C.label("BLREG_REG_SHIPPED_PCT", C.EN).endswith("(%)")
    assert C.label("IS_IN_CUSTOMS", C.EN) == "In customs?"
    assert C.label("مقاومت (روز)", C.EN) == "Resistance (days)"
    # نیم‌فاصله و ی/ک عربی مانع ترجمه نمی‌شود
    assert C.label("بارنامه‌ها", C.EN) == C.label("بارنامه ها", C.EN) == "B/Ls"
    assert C.label("كد پرسنلي", C.EN) == "Employee ID"


def test_localized_frame_never_has_duplicate_titles_and_keeps_data():
    df = pd.DataFrame({"وضعیت": [1], "Status": [2], "STATUS": [3], "KEY_BL": ["x"]})
    out, mp = C.localize_frame(df, C.EN)
    assert out.columns.is_unique and len(out.columns) == 4
    assert out.iloc[0].tolist() == df.iloc[0].tolist()
    assert list(df.columns) == ["وضعیت", "Status", "STATUS", "KEY_BL"]   # اصل دست نخورد
    fa, _ = C.localize_frame(df, C.FA)
    assert fa.columns.is_unique


def test_data_editor_result_comes_back_with_original_names(monkeypatch):
    import streamlit as st
    from app import col_lang

    seen = {}

    def fake_editor(self, data=None, *a, **kw):
        seen["cols"] = list(data.columns)
        seen["cfg"] = kw.get("column_config")
        return data

    fake_editor.__name__ = "data_editor"
    wrapped = col_lang._wrap(fake_editor, editor=True)
    monkeypatch.setattr(col_lang, "current", lambda: C.EN)
    df = pd.DataFrame({"فیلد": ["a"], "انتخاب": [True]})
    res = wrapped(None, df, column_config={"انتخاب": {"label": "انتخاب", "type_config": {}}})
    assert seen["cols"] == ["Field", "Select"]
    assert "Select" in seen["cfg"] and seen["cfg"]["Select"]["label"] == "Select"
    assert list(res.columns) == ["فیلد", "انتخاب"]


def test_icons_are_stroke_only_and_every_stage_has_one():
    for n in I.NAMES:
        svg = I.icon(n)
        assert 'stroke="currentColor"' in svg and not HEX.search(svg), n
    assert I.icon("no-such-icon")          # ناشناخته ← نقطه، نه خطا
    for code in ("REG_FILE", "ORDER_REG", "ALLOCATION_QUEUE", "ALLOCATION", "FX_PURCHASE", "FUNDING",
                 "SWIFT_CONVERSION", "SHIPMENT", "CUSTOMS", "CLEARANCE", "BANK_DOCS", "SETTLEMENT", "CLOSED"):
        assert code in I.STAGE_ICON


def test_ring_shows_unknown_as_dash_not_zero_and_flags_overshoot():
    unknown = I.ring(None, label="x")
    assert "—" in unknown and "stroke-dasharray=\"3 5\"" in unknown and "url(#" not in unknown.split("</defs>")[1]
    zero = I.ring(0)
    assert "0٪" in zero
    over = I.ring(139)
    assert "139٪" in over and T.STATUS["critical"].ink in over


def test_minimal_css_uses_only_design_tokens():
    palette = {c.lower() for c in T.__dict__.values() if isinstance(c, str) and c.startswith("#")}
    palette |= {c.lower() for c in T.TEAL_PALETTE}
    palette |= {s.ink.lower() for s in T.STATUS_SCALE} | {s.fill.lower() for s in T.STATUS_SCALE}
    css = I.minimal_css() + I.stepper([("ORDER_REG", "a", "done"), ("SHIPMENT", "b", "current", 3)])
    stray = {h.lower() for h in HEX.findall(css)} - palette
    assert not stray, stray


def test_critical_board_english_mode_translates_headers():
    df = pd.DataFrame([{"CANONICAL_BL": "BL1", "KEY_MATERIAL": "M1", "کد طبقه بحرانی": "CRITICAL",
                        "BL_CRITICAL": True, "BL_CRITICAL_LEVEL": "CRITICAL", "مقاومت (روز)": 4.0,
                        "KEY_REG": "R1"}])
    en = __import__("gsi.report.critical_board", fromlist=["x"]).build_critical_html(df, "2026-09-28", lang="en")
    assert "Critical materials" in en and "Reference date" in en and "<th><bdi>B/L</bdi></th>" in en
