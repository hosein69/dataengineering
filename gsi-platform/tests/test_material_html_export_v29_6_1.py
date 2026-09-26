# -*- coding: utf-8 -*-
"""Compatibility regression after V29.6.2.

V29.6.1 injected a detached, non-filterable material table. V29.6.2 keeps the
business identity fix but requires material to live in the normal tab runtime.
"""
import pandas as pd
from gsi.studio_core.html_export import build_dynamic_html


def _df():
    return pd.DataFrame({
        "KEY_MATERIAL": ["MAT-1001", "MAT-1002"],
        "CANONICAL_ORDER": ["PO-1", "PO-2"],
        "KEY_REG": ["REG-1", "REG-2"],
        "بحرانی (کوتاه)": ["بحرانی", "تحت نظر"],
        "مقاومت (روز)": [4.0, 18.0],
    })


def test_material_identity_is_kept_in_main_tab_table_even_if_saved_tab_omits_it():
    html = build_dynamic_html(
        _df(), "2026-09-21", selected_fields=["CANONICAL_ORDER"],
        tabs=[{"title": "نمای اصلی", "fields": ["CANONICAL_ORDER"], "blocks": ["table"]}],
        show_visuals=False, show_tables=True,
    )
    assert "KEY_MATERIAL" in html
    assert "MAT-1001" in html
    assert html.count("دید تأمین — متریال محور</button>") == 1
