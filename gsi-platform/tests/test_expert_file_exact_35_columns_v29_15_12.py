# -*- coding: utf-8 -*-
"""The expert file, exactly as it is — GSI 29.15.12.

Owner (1405-07-05): the Commercial Expert Data file has exactly these 35
columns; «کد رو دقیقا بر اساس همین ستون‌ها بازنویسی کن که کثیف نشه … هدرهای
کارشناسان در گزارش‌ها بیشتر از آنچه هست می‌باشند و این گیج‌کننده است؛ فقط
هرآنچه هست بیار». «Quantity In Part» is in one of the states نزد سازنده /
آماده حمل / در راه / در گمرک, read from «Order Status».

Until 29.15.11 the adapter also mapped five columns the file never has
(supplier / in-transit / in-customs stock, inventory date and note); they
arrived empty on every run, reached the reports as extra headers, and the
supplier quantity was guessed as «Quantity In Order − Quantity In Part».
"""
from __future__ import annotations

import pandas as pd
import pytest

from gsi.adapters.moghavemat import EXPERT_HEADERS, PART_STATES, MoghavematAdapter
from gsi.report.dashboard import SHEET_LINES, ExcelDashboardBuilder
from gsi.report.expert_material import build_expert_material_positions
from gsi.report.supply_views import append_expert_materials, build_material_html_view

#: the owner's list, verbatim (␠ = a space in the real header)
OWNER_HEADERS = [
    "Row No.", "Order No.\n(Our Reference)", "PR No.", "PR Item", "Material",
    "Material Description", "Material Short Text", "Manufacturer Part Number", "PGR",
    "PR Total Quantity", "Unit Of Measure", "Reference Letter No.\n(شماره نامه اتوماسیونی)",
    "Data type ", "Quantity In Order", "Manufacturer Vendor Code ", "Manufacturer\nPI Number ",
    "Vendor Code ", "Vendor\nPI Number ", "PI Quantity ", "PI Unit Price", "Currency",
    "PI Line Value", "PI Additional Costs", " PO Sent Date\n( با فرمت میلادی PO تاریخ ابلاغ فرم)",
    "Part No.\n(شماره پارت در حمل پارشیالی)", "Quantity In Part", "Customs Cleared Quantity",
    "Order Status", "Mode of Transport", "Transport No.", "BL No.", "Carrier Name",
    "Scheduled Shipment Date", "Additional Data (Note , Brand etc.)", "Employee Code",
]
F = dict(zip(["ROW", "ORD", "PR", "PRI", "MAT", "DESC", "SHORT", "MFR", "PGR", "PRQ", "UOM",
              "REF", "DT", "QO", "MVC", "MPI", "VC", "VPI", "PIQ", "PUP", "CUR", "PIV", "PIA",
              "PO", "PART", "QP", "CLR", "OS", "MODE", "TNO", "BL", "CAR", "SCH", "ADD", "EMP"],
             OWNER_HEADERS))


def _row(**kw):
    r = {h: "" for h in OWNER_HEADERS}
    r.update({F[k]: v for k, v in kw.items()})
    return r


def _file(*rows):
    return MoghavematAdapter().transform({"Expert Data": pd.DataFrame(list(rows), columns=OWNER_HEADERS)})


def test_the_contract_is_exactly_the_owners_35_headers():
    assert [h for _, h in EXPERT_HEADERS] == OWNER_HEADERS
    assert len(MoghavematAdapter.COLUMN_MAP) == 35


def test_every_real_column_maps_once_and_nothing_else_is_read():
    t = _file(_row(ROW=1, ORD="O1", MAT="M1", QP=5, OS="در راه"))
    lines = t["lines"]
    assert list(lines.attrs["missing_mappings"]) == []
    assert list(lines.attrs["ignored_headers"]) == []
    for _, header in EXPERT_HEADERS:
        assert header in lines.attrs["source_headers"]
    phantoms = ("SUPPLIER_STOCK_QTY", "INVENTORY_ASOF", "INVENTORY_NOTE", "OPEN_SHIPPED",
                "SUPPLIER_STOCK_QTY_DERIVED", "MOGH_IN_TRANSIT_QTY", "MOGH_IN_CUSTOMS_QTY")
    for frame in ("lines", "main", "inventory"):
        assert not [c for c in t[frame].columns if any(p in c for p in phantoms)], frame


def test_extra_columns_are_ignored_and_part_no_never_takes_the_manufacturer_part_number():
    raw = pd.DataFrame([{"Order No. (Our Reference)": "O1", "Material": "M1",
                         "Manufacturer Part Number": "MFR-9", "Quantity In Part": 4,
                         "Order Status": "در گمرک", "موجودی نزد سازنده": 999}])
    lines = MoghavematAdapter().transform({"Expert Data": raw})["lines"]
    assert list(lines.attrs["ignored_headers"]) == ["موجودی نزد سازنده"]
    assert lines["MOGH_PART_NO_PARTIAL"].iloc[0] == ""           # missing, not «MFR-9»
    assert lines["MOGH_MFR_PART_NO"].iloc[0] == "MFR-9"          # the source value, as written
    assert lines["MOGH_QTY_IN_CUSTOMS"].iloc[0] == 4             # 999 is not read


def test_quantity_in_part_goes_to_the_state_in_order_status():
    t = _file(
        _row(ROW=1, ORD="823107D", MAT="9654003280", QO=100, PART="1", QP=30, OS="در راه"),
        _row(ROW=2, ORD="823107D", MAT="9654003280", QO=100, PART="2", QP=40, CLR=10, OS="در گمرک"),
        _row(ROW=3, ORD="823107D", MAT="9654003280", QO=100, PART="3", QP=20, OS="آماده حمل"),
        _row(ROW=4, ORD="823107D", MAT="9654003280", QO=100, PART="4", QP=10, OS="نزد سازنده"),
        _row(ROW=5, ORD="823107D", MAT="B-2", QO=4, QP=4, OS="In Transit"),
    )
    m = t["main"].set_index("MOGH_MATERIAL")
    a = m.loc["9654003280"]
    assert (a["MOGH_QTY_AT_SUPPLIER"], a["MOGH_QTY_READY"],
            a["MOGH_QTY_IN_TRANSIT"], a["MOGH_QTY_IN_CUSTOMS"]) == (10, 20, 30, 30)  # 40 − 10 cleared
    assert a["MOGH_QTY_STATE_UNKNOWN"] == 0
    b = m.loc["B-2"]
    assert b["MOGH_QTY_IN_TRANSIT"] == 4 and b["MOGH_QTY_AT_SUPPLIER"] == 0      # known zero


def test_status_spelling_variants_match_as_whole_words():
    t = _file(_row(ROW=1, ORD="O1", MAT="M1", QP=1, OS="درراه"),
              _row(ROW=2, ORD="O1", MAT="M2", QP=1, OS="Ready for shipment"),
              _row(ROW=3, ORD="O1", MAT="M3", QP=1, OS="گمرک و ترخیص"))
    states = dict(zip(t["lines"]["MOGH_MATERIAL"], t["lines"]["MOGH_PART_STATE"]))
    assert states == {"M1": "IN_TRANSIT", "M2": "READY", "M3": "UNRECOGNIZED"}


def test_an_unknown_status_is_reported_not_guessed():
    t = _file(_row(ROW=1, ORD="O1", MAT="M1", QO=10, PART="1", QP=6, OS="در راه"),
              _row(ROW=2, ORD="O1", MAT="M1", QO=10, PART="2", QP=4, OS=""))
    r = t["main"].iloc[0]
    assert r["MOGH_QTY_STATE_UNKNOWN"] == 4
    assert r["MOGH_QTY_IN_TRANSIT"] == 6
    # part 2 may be anywhere: a zero elsewhere is not provable
    assert pd.isna(r["MOGH_QTY_AT_SUPPLIER"]) and pd.isna(r["MOGH_QTY_IN_CUSTOMS"])


def test_a_part_repeated_on_two_pr_items_is_counted_once_and_state_conflicts_are_recorded():
    t = _file(_row(ROW=1, ORD="O1", PR="P1", PRI=10, MAT="M1", PART="1", QP=8, OS="در راه"),
              _row(ROW=2, ORD="O1", PR="P1", PRI=20, MAT="M1", PART="1", QP=8, OS="در گمرک"))
    inv = t["inventory"].iloc[0]
    assert inv["MOGH_QTY_IN_TRANSIT"] + inv["MOGH_QTY_IN_CUSTOMS"] == 8
    assert "Part 1" in inv["MOGH_INVENTORY_CONFLICT"]


def test_an_orderless_line_keeps_its_part_states_in_the_mart():
    t = _file(_row(ROW=1, MAT="IK88888888", DESC="بست لوله", QP=7, OS="نزد سازنده"))
    r = t["main"].iloc[0]
    assert r["MOGH_ITEM_ROLE"] == "NO_ORDER" and r["MOGH_QTY_AT_SUPPLIER"] == 7
    inv = t["inventory"].iloc[0]
    assert inv["KEY_ORDER"] == "" and inv["MOGH_QTY_AT_SUPPLIER"] == 7


def test_supply_position_uses_the_four_states():
    t = _file(_row(ROW=1, ORD="O1", MAT="M1", PART="1", QP=6, OS="در راه"),
              _row(ROW=2, ORD="O1", MAT="M1", PART="2", QP=4, OS="آماده حمل"),
              _row(ROW=3, ORD="O1", MAT="M2", PART="1", QP=5, OS=""))
    oracle = pd.DataFrame([{"KEY_MATERIAL": "M1", "ORC_STOCK_IKCO": 3, "ORC_STOCK_SAPCO": 1,
                            "ORC_DAILY_NEED": 2},
                           {"KEY_MATERIAL": "M2", "ORC_STOCK_IKCO": 2, "ORC_STOCK_SAPCO": 0,
                            "ORC_DAILY_NEED": 1}])
    pos = build_expert_material_positions(t["lines"], t["inventory"], oracle).set_index("KEY_MATERIAL")
    assert pos.loc["M1", "SUPPLY_POSITION_STATUS"] == "COMPLETE"
    assert pos.loc["M1", "SUPPLY_TOTAL_CONFIRMED"] == 3 + 1 + 6 + 4
    assert pos.loc["M2", "SUPPLY_POSITION_STATUS"] == "PARTIAL"
    assert "وضعیت نامشخص" in pos.loc["M2", "SUPPLY_POSITION_GAPS"]
    assert pos.loc["M2", "SUPPLY_TOTAL_LOWER_BOUND"] == 2


def test_the_lines_sheet_shows_the_35_headers_and_the_states_only(tmp_path):
    t = _file(_row(ROW=1, ORD="O1", MAT="M1", DESC="قطعه", QP=5, OS="در گمرک", EMP="10201069_GS"))
    b = ExcelDashboardBuilder(str(tmp_path / "l.xlsx"))
    b.build_order_lines(t["lines"])
    ws = b.wb[SHEET_LINES]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    assert headers == [h.strip() for h in OWNER_HEADERS] + \
        [f"{fa} (Quantity In Part)" for _, fa, _ in PART_STATES]
    row = dict(zip(headers, [ws.cell(2, c).value for c in range(1, ws.max_column + 1)]))
    assert row["Employee Code"] == "10201069_GS"            # as written in the file
    assert row["در گمرک (Quantity In Part)"] == 5


def test_reports_carry_no_duplicate_or_phantom_inventory_headers():
    from gsi.stages import discover
    from gsi.stages.base import REGISTRY
    discover()
    labels = [spec.title for cls in REGISTRY.values() for spec in cls().columns()]
    for name in ("نزد سازنده", "آماده حمل", "در راه", "در گمرک"):
        assert labels.count(name) == 1, name
    assert not [x for x in labels if "(کارشناس)" in x]
    assert "موجودی کل قطعی" not in labels and "SUPPLY_POSITION_ASOF" not in labels


def test_catalog_keeps_the_expert_group_to_the_35_headers():
    from gsi.studio_core.field_catalog import build_catalog
    t = _file(_row(ROW=1, ORD="O1", MAT="M1", QP=5, OS="در راه"))
    specs = build_catalog(t["main"].join(t["lines"].drop(columns=t["main"].columns, errors="ignore")))
    groups = {}
    for sp in specs:
        groups.setdefault(sp.group, []).append(sp)
    expert = [g for g in groups if g.startswith("مرجع درجه‌اول") and "محاسبه‌شده" not in g]
    assert len(expert) == 1
    assert {sp.label for sp in groups[expert[0]]} <= {" ".join(h.split()) for h in OWNER_HEADERS} | \
        {h.strip() for h in OWNER_HEADERS}


def test_first_material_attributes_are_never_borrowed_from_a_sibling():
    """Targeted debug of 29.15.11: the first material's blank description must
    stay blank, not become the second material's."""
    t = _file(_row(ROW=1, ORD="O1", MAT="M1", DESC="", QP=1, OS="در راه"),
              _row(ROW=2, ORD="O1", MAT="M2", DESC="شرح M2", MFR="P-2", QP=1, OS="در راه"))
    m = t["main"].set_index("MOGH_MATERIAL")
    assert m.loc["M1", "MOGH_MATERIAL_DESC"] == ""
    assert m.loc["M1", "MOGH_MFR_PART_NO"] == ""


def test_an_empty_filtered_report_stays_empty():
    """Targeted debug of 29.15.11: an empty slice must not refill from the ledger."""
    t = _file(_row(ROW=1, ORD="O1", MAT="M1", QP=1, OS="در راه"))
    ledger = build_expert_material_positions(t["lines"], t["inventory"], None)
    empty = pd.DataFrame(columns=["KEY_MATERIAL", "CANONICAL_ORDER"])
    view = build_material_html_view(empty)
    assert len(append_expert_materials(view, ledger, df=empty)) == len(view)


@pytest.mark.parametrize("header", ["Order No.", "Our Reference", "Order No. (Our Reference)"])
def test_order_header_spellings_are_the_same_column(header):
    raw = pd.DataFrame([{header: "603128A", "Material": "M1"}])
    lines = MoghavematAdapter().transform({"Expert Data": raw})["lines"]
    assert lines["KEY_ORDER"].iloc[0] == "603128A"
