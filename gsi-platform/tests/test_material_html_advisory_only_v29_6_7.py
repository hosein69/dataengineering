import pandas as pd

from gsi.report.supply_views import build_material_html_view
from gsi.studio_core.html_export import build_dynamic_html


def _frame(n=1):
    rows=[]
    for i in range(n):
        rows.append({
            "KEY_MATERIAL": f"96540032{i:02d}",
            "CANONICAL_ORDER": f"83{i:04d}A",
            "KEY_REG": "12345678",
            "CANONICAL_BL": "",
            # NTSW evidence exists but must not determine material dashboard status.
            "NTSW_ALLOC_DATE": "1405/06/20",
            "NTSW_ALLOC_STATUS": "رد شده" if i == 0 else "تخصیص یافته",
            "NTSW_BALANCE": 1000 if i == 0 else 0,
            "NTSW_RELEASE_STATUS": "رفع تعهد نشده" if i == 0 else "رفع تعهد شده",
            "NTSW_CURRENCY": "EUR",
            "NTSW_DEADLINE": "1405/07/01",
            # Expert source is commentary/advisory only.
            "MOGH_COMMERCIAL_NOTE": "پیگیری توسط کارشناس" if i == 0 else "",
            "MOGH_ALERTS": "نیازمند بررسی" if i == 0 else "",
            "PART_OWNER": "کارشناس نمونه",
            "PART_OWNER_DATA_GAP": "شماره درخواست خرید" if i == 0 else "",
        })
    return pd.DataFrame(rows)


def test_expert_and_ntsw_are_advisory_only_in_html_material_view():
    v=build_material_html_view(_frame())
    assert len(v) == 1
    # NTSW date cannot move operational position.
    assert v.loc[0, "موقعیت فعلی"] == "نامشخص"
    assert v.loc[0, "مرحله فعلی"] == "نامشخص"
    # Raw expert ownership is not a dashboard authority/column.
    assert "مالک قطعه (کارشناس خرید)" not in v.columns
    assert "کارشناس مسئول وضعیت" not in v.columns
    # Both sources remain visible only as warning/comment.
    assert "⚠" in v.loc[0, "هشدار کارشناسان"]
    assert "پیگیری توسط کارشناس" in v.loc[0, "کامنت کارشناسان"]
    assert "⚠" in v.loc[0, "هشدار NTSW"]
    assert "رد شده" in v.loc[0, "کامنت NTSW"]
    assert "پیگیری توسط کارشناس" not in v.loc[0, "چرایی / مبنای وضعیت"]


def test_material_html_payload_is_not_cut_before_search():
    df=_frame(19)
    view=build_material_html_view(df)
    h=build_dynamic_html(
        df, "2026-09-21", max_rows=5,
        selected_fields=["KEY_MATERIAL", "CANONICAL_ORDER"],
        material_supply_view=view,
    )
    # Late rows must be embedded; max_rows is only a post-filter presentation cap.
    assert '"material_supply_embedded_rows": 19' in h
    assert "9654003218" in h
    assert "هشدار کارشناسان" in h
    assert "هشدار NTSW" in h
    assert "فقط Advisory" in h
