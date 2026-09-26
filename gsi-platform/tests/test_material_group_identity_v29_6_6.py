import pandas as pd

from gsi.report.supply_views import build_material_view
from gsi.studio_core.html_export import build_dynamic_html


def _frame():
    keys = ["MAT-A"] * 5 + ["MAT-B"] * 4 + ["MAT-C"] * 4
    return pd.DataFrame({
        "KEY_MATERIAL": keys,
        # Deliberately wrong/repeated row-level description reproduces the real bug:
        # it must never become material identity / group title.
        "MATERIAL_DESC": ["OLD-DELETED-TITLE"] * 13,
        "CANONICAL_ORDER": [f"O{i%5}" for i in range(13)],
        "CANONICAL_BL": [f"B{i%4}" for i in range(13)],
    })


def test_material_identity_is_key_not_description():
    out = build_material_view(_frame())
    assert len(out) == 13  # detail grain is intentionally preserved
    assert set(out["عنوان گروه"]) == {"MAT-A", "MAT-B", "MAT-C"}
    assert set(out["متریال"]) == {"MAT-A", "MAT-B", "MAT-C"}
    assert "OLD-DELETED-TITLE" not in set(out["عنوان گروه"])
    counts = out.groupby("متریال")["تعداد ردیف تفصیلی گروه"].first().to_dict()
    assert counts == {"MAT-A": 5, "MAT-B": 4, "MAT-C": 4}


def test_material_description_is_separate_filterable_attribute():
    out = build_material_view(_frame())
    html = build_dynamic_html(
        _frame(), "2026-09-21", selected_fields=["KEY_MATERIAL", "CANONICAL_ORDER"],
        tabs=[{"title": "تفصیلی", "fields": ["KEY_MATERIAL", "CANONICAL_ORDER"], "blocks": ["table"]}],
        material_supply_view=out,
    )
    assert 'data-f="متریال"' in html
    assert 'data-f="شرح متریال"' in html
    assert "MAT-A" in html and "MAT-B" in html and "MAT-C" in html
