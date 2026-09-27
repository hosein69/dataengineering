# -*- coding: utf-8 -*-
"""The expert file is the primary material criterion — GSI 29.15.10.

Owner's words (1405-07-05): «هنوز متریال که در فایل کارشناسان هست اگه ناقص
پرکرده باشند نشونش نمی‌ده … یک کد متریال دو شرح داره ولی فقط یکیش نشون داده
میشه … این نباید از گزارش اصلی حذف بشه … معیار اصلی فایل کارشناسان هست حتی
اگه ناقص باشه میشه گزارش داد ناقصه».

Until 29.15.9 the main, searchable material view held only the operational
material of each order (the first one, and only with an Oracle match); the
second material of an order, a row without an order number, and the second
description of a multi-material order were visible only in a side evidence
table. Each test below failed on 29.15.9.

The safety line of the older contract stays: expert data never sets position,
owner or BL, and nothing here enters the mart, a KPI or a sum.
"""
from __future__ import annotations

import pandas as pd

from gsi.adapters.moghavemat import MoghavematAdapter
from gsi.report.dashboard import ExcelDashboardBuilder
from gsi.report.expert_material import build_expert_material_positions
from gsi.report.supply_views import (SHEETS, SOURCE_COL, SOURCE_EXPERT_ONLY, GAPS_COL,
                                     append_expert_materials, build_material_html_view,
                                     build_material_view)
from gsi.studio_core.html_export import build_dynamic_html


def _owner_case():
    """Order 823107D from the owner's note: 9654003280 with two descriptions,
    a second material B-2 in the same order, nothing but the order and the
    material filled — plus one row with no order number at all."""
    raw = pd.DataFrame([
        {"Row No.": 1, "Order No. (Our Reference)": "823107D", "Material": "9654003280",
         "Material Description": "رينگ ضدقفل مغناطيسي", "Quantity In Order": 10},
        {"Row No.": 2, "Order No. (Our Reference)": "823107D", "Material": "9654003280",
         "Material Description": "هدف چرخشي ترمز ضدقفل", "Quantity In Order": 10},
        {"Row No.": 3, "Order No. (Our Reference)": "823107D", "Material": "B-2",
         "Material Description": "قطعه دوم سفارش", "Quantity In Order": 4},
        {"Row No.": 4, "Order No. (Our Reference)": "", "Material": "IK88888888",
         "Material Description": "بست لوله"},
    ])
    t = MoghavematAdapter().transform({"Expert Data": raw})
    oracle = pd.DataFrame([{"KEY_MATERIAL": "9654003280", "ORC_STOCK_IKCO": 40,
                            "ORC_STOCK_SAPCO": 10, "ORC_DAILY_NEED": 10,
                            "ORC_MATERIAL_DESC": "رینگ ABS"}])
    positions = build_expert_material_positions(t["lines"], t["inventory"], oracle)
    # The flat mart: one row for the order, its first material, known to Oracle.
    main = t["main"].copy()
    main["KEY_MATERIAL"] = main["MOGH_MATERIAL"].astype(str)
    main["CANONICAL_ORDER"] = main["KEY_ORDER"]
    main["ORC_PART_NO"] = "9654003280"
    main["ORC_MATERIAL_DESC"] = "رینگ ABS"
    return main, positions


def _html_view(main, positions):
    import json
    h = build_dynamic_html(main, "2026-09-27", selected_fields=["KEY_MATERIAL"],
                           material_supply_view=positions)
    return pd.DataFrame(json.JSONDecoder().raw_decode(
        h.split("const MATERIAL_SUPPLY_DATA=", 1)[1])[0])


def test_second_material_and_orderless_row_are_rows_of_the_main_html_view():
    main, positions = _owner_case()
    view = _html_view(main, positions)
    assert {"9654003280", "B2", "IK88888888"} <= set(view["متریال"])
    b2 = view[view["متریال"] == "B2"].iloc[0]
    assert b2[SOURCE_COL] == SOURCE_EXPERT_ONLY
    assert b2["سفارش"] == "823107D"
    orphan = view[view["متریال"] == "IK88888888"].iloc[0]
    assert "شماره سفارش" in orphan[GAPS_COL]
    assert orphan["سفارش"] == "—"


def test_both_descriptions_of_one_code_are_shown_in_the_main_view():
    main, positions = _owner_case()
    row = _html_view(main, positions).set_index("متریال").loc["9654003280"]
    shown = row["شرح‌های ثبت‌شده کارشناسان"]
    assert "رينگ ضدقفل مغناطيسي" in shown and "هدف چرخشي ترمز ضدقفل" in shown
    assert row["اختلاف شرح متریال"] == "⚠ چند شرح برای یک متریال"
    assert row[SOURCE_COL] == "عملیاتی"


def test_incompleteness_is_reported_not_hidden():
    main, positions = _owner_case()
    view = _html_view(main, positions).set_index("متریال")
    for code in ("9654003280", "B2"):
        gaps = view.loc[code, GAPS_COL]
        assert "823107D" in gaps and "شماره درخواست خرید" in gaps and "ارزش PI" in gaps


def test_expert_only_rows_never_carry_operational_state():
    main, positions = _owner_case()
    view = _html_view(main, positions).set_index("متریال")
    for code in ("B2", "IK88888888"):
        assert view.loc[code, "موقعیت فعلی"] == "نامشخص"
        assert view.loc[code, "مرحله فعلی"] == "نامشخص"
    # a forged ledger column cannot become a status either
    bad = positions.assign(**{"موقعیت فعلی": "BYPASS"})
    import json
    h = build_dynamic_html(main, "2026-09-27", material_supply_view=bad)
    payload = json.JSONDecoder().raw_decode(h.split("const MATERIAL_SUPPLY_DATA=", 1)[1])[0]
    assert "BYPASS" not in json.dumps(payload, ensure_ascii=False)


def test_the_operational_view_itself_is_unchanged():
    """Calculations and the boundary contract: the operational view is exactly
    what it was; expert rows are appended after it, never merged into it."""
    main, positions = _owner_case()
    before = build_material_html_view(main)
    after = append_expert_materials(before, positions, df=main)
    ops = after[after[SOURCE_COL] == "عملیاتی"].drop(
        columns=[SOURCE_COL, GAPS_COL, "شرح‌های ثبت‌شده کارشناسان", "اختلاف شرح متریال"])
    pd.testing.assert_frame_equal(
        ops.reset_index(drop=True),
        before.drop(columns=["شرح‌های ثبت‌شده کارشناسان", "اختلاف شرح متریال"]).reset_index(drop=True))


def test_excel_sheet_14_main_table_lists_every_expert_material(tmp_path):
    main, positions = _owner_case()
    builder = ExcelDashboardBuilder(str(tmp_path / "m.xlsx"))
    builder.build_supply_views(main, positions)
    ws = builder.wb[SHEETS[0]]
    rows = [[str(c.value or "") for c in r] for r in ws.iter_rows()]
    header = rows[0]
    first_table = rows[1:rows.index([])] if [] in rows else rows[1:]
    mat = header.index("متریال")
    main_codes = {r[mat] for r in first_table if len(r) > mat}
    assert {"9654003280", "B2", "IK88888888"} <= main_codes


def test_a_filtered_report_does_not_grow_other_slices():
    main, positions = _owner_case()
    other = main.assign(CANONICAL_ORDER="999999", KEY_ORDER="999999")
    out = append_expert_materials(build_material_view(other), positions, df=other)
    # order 823107D is outside this slice; the order-less row belongs to none and stays
    assert "B2" not in set(out["متریال"])
    assert "IK88888888" in set(out["متریال"])


def test_no_ledger_no_change():
    main, _ = _owner_case()
    view = build_material_html_view(main)
    pd.testing.assert_frame_equal(append_expert_materials(view, None, df=main), view)
