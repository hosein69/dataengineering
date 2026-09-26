# -*- coding: utf-8 -*-
import pandas as pd
from gsi.studio_core.html_export import build_dynamic_html


def _df(n=60):
    return pd.DataFrame({
        "KEY_MATERIAL": [f"MAT-{i:04d}" for i in range(n)],
        "CANONICAL_ORDER": [f"PO-{i%7}" for i in range(n)],
        "KEY_REG": [f"REG-{i%5}" for i in range(n)],
        "بحرانی (کوتاه)": ["بحرانی" if i % 3 == 0 else "عادی" for i in range(n)],
        "مقاومت (روز)": [float(i) for i in range(n)],
    })


def test_no_global_static_material_supply_table_is_injected_above_tabs():
    html = build_dynamic_html(
        _df(), "2026-09-21", selected_fields=["CANONICAL_ORDER"],
        tabs=[
            {"title": "تب اول", "fields": ["CANONICAL_ORDER"], "blocks": ["table"]},
            {"title": "تب دوم", "fields": ["KEY_REG"], "blocks": ["table"]},
        ], show_visuals=False, show_tables=True,
    )
    assert html.count("دید تأمین — متریال محور</button>") == 1
    # Material identity remains in the actual first tab table, not a detached table.
    assert 'data-f="KEY_MATERIAL"' in html
    assert 'data-filter-mode="contains"' in html
    assert "KEY_MATERIAL" in html


def test_high_cardinality_material_gets_tab_scoped_text_filter():
    html = build_dynamic_html(
        _df(75), "2026-09-21", selected_fields=["KEY_MATERIAL", "CANONICAL_ORDER"],
        tabs=[{"title": "مواد", "fields": ["KEY_MATERIAL", "CANONICAL_ORDER"], "blocks": ["table"]}],
        show_visuals=False, show_tables=True,
    )
    assert 'data-f="KEY_MATERIAL"' in html
    assert 'data-filter-mode="contains"' in html
    assert 'placeholder="جستجو در KEY_MATERIAL"' in html
    assert "querySelectorAll('[data-f][data-pane=\"'+t.id+'\"]')" in html


def test_material_filter_is_part_of_same_runtime_slice_as_table():
    html = build_dynamic_html(
        _df(75), "2026-09-21",
        tabs=[{"title": "مواد", "fields": ["KEY_MATERIAL", "CANONICAL_ORDER"], "blocks": ["kpi", "table"]}],
        show_visuals=False, show_tables=True,
    )
    assert "dataset.filterMode==='contains'" in html
    assert "render(active)" in html
    assert 'id="tb_0"' in html
