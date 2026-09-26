import pandas as pd

from gsi.studio_core.html_export import build_dynamic_html


def _dashboard_frame():
    return pd.DataFrame([
        {
            "KEY_MATERIAL": "9654003280",
            "CANONICAL_ORDER": "843120",
            "KEY_REG": "12345678",
            "CANONICAL_BL": "",
            "PO_SENT_DATE": "1405/06/01",
            # NTSW may only contribute advisory warning/comment.
            "NTSW_ALLOC_DATE": "1405/06/20",
            "NTSW_ALLOC_STATUS": "رد شده",
            "NTSW_BALANCE": 1000,
            "NTSW_RELEASE_STATUS": "رفع تعهد نشده",
            "NTSW_CURRENCY": "EUR",
            # Commercial Expert prose may only contribute advisory warning/comment.
            "MOGH_COMMERCIAL_NOTE": "پیگیری توسط کارشناس",
            "MOGH_ALERTS": "نیازمند بررسی",
            "PART_OWNER": "کارشناس نمونه",
        }
    ])


def test_dashboard_style_call_auto_builds_material_advisory_tab():
    df = _dashboard_frame()
    # This mirrors app/dashboard.py: no material_supply_view argument is passed.
    h = build_dynamic_html(
        df,
        "2026-09-21",
        title="GSI Dashboard",
        selected_fields=["KEY_MATERIAL", "CANONICAL_ORDER", "KEY_REG"],
        max_rows=10000,
    )
    assert h.count("دید تأمین — متریال محور</button>") == 1
    assert '"material_supply_embedded_rows": 1' in h
    assert "هشدار کارشناسان" in h and "کامنت کارشناسان" in h
    assert "هشدار NTSW" in h and "کامنت NTSW" in h
    assert "پیگیری توسط کارشناس" in h
    assert "رد شده" in h
    # NTSW's later allocation date must not become the operational position.
    assert "ابلاغ سفارش به تأمین‌کننده" in h
    # Raw expert ownership columns are not part of the material dashboard view.
    material_payload = h.split("const MATERIAL_SUPPLY_DATA=", 1)[1].split(";", 1)[0]
    assert "مالک قطعه (کارشناس خرید)" not in material_payload
    assert "کارشناس مسئول وضعیت" not in material_payload
