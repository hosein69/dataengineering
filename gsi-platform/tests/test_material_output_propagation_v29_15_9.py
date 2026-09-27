# -*- coding: utf-8 -*-
"""Regression: every expert material reaches DWH-facing, Excel and HTML outputs.

The order-level mart may keep one compatibility material, but it must publish the
full material-code lineage and the dedicated Order×Material ledger must be visible
without becoming operational shipment authority.
"""
from pathlib import Path
import pandas as pd

from gsi.adapters.moghavemat import MoghavematAdapter
from gsi.report.expert_material import build_expert_material_positions
from gsi.report.dashboard import ExcelDashboardBuilder
from gsi.report.supply_views import SHEETS, build_expert_material_evidence_view
from gsi.stages.s10_resolve import ResolveStage
from gsi.studio_core.html_export import build_dynamic_html


def _fixture():
    raw = pd.DataFrame([
        {"Row No.": 1, "Order No. (Our Reference)": "823107D", "Material": "9654003280",
         "Material Description": "رينگ ضدقفل مغناطيسي", "Quantity In Order": 10,
         "Quantity In Part": 2, "Customs Cleared Quantity": 1},
        {"Row No.": 2, "Order No. (Our Reference)": "823107D", "Material": "9654003280",
         "Material Description": "هدف چرخشي ترمز ضدقفل", "Quantity In Order": 10,
         "Quantity In Part": 2, "Customs Cleared Quantity": 1},
        {"Row No.": 3, "Order No. (Our Reference)": "823107D", "Material": "B-2",
         "Material Description": "قطعه دوم سفارش", "Quantity In Order": 4,
         "Quantity In Part": 1, "Customs Cleared Quantity": 0},
    ])
    transformed = MoghavematAdapter().transform({"Expert Data": raw})
    positions = build_expert_material_positions(
        transformed["lines"], transformed["inventory"], None)
    return transformed, positions


def test_order_matrix_declares_all_material_codes_and_descriptions():
    transformed, _ = _fixture()
    row = transformed["main"].iloc[0]
    assert "9654003280" in row["MOGH_MATERIALS_ALL"]
    assert "B-2" in row["MOGH_MATERIALS_ALL"]
    assert "هدف چرخشي ترمز ضدقفل" in row["MOGH_MATERIAL_DESCS_ALL"]
    published = {x.key for x in ResolveStage().columns()}
    assert {"MOGH_MATERIALS_ALL", "MOGH_KEY_MATERIAL_COUNT",
            "MOGH_MATERIAL_DESCS_ALL", "MOGH_MATERIAL_DESC_COUNT"} <= published


def test_excel_material_sheet_contains_complete_order_material_ledger(tmp_path):
    transformed, positions = _fixture()
    # The flat mart can only carry one representative material at order grain.
    main = transformed["main"].copy()
    main["KEY_MATERIAL"] = main["MOGH_MATERIAL"].astype(str)
    builder = ExcelDashboardBuilder(str(tmp_path / "material.xlsx"))
    builder.build_supply_views(main, positions)
    ws = builder.wb[SHEETS[0]]
    values = [str(c.value or "") for row in ws.iter_rows() for c in row]
    joined = " | ".join(values)
    assert "دفتر کامل شواهد کارشناسان" in joined
    assert "9654003280" in joined
    # clean_part_no normalises B-2 to B2 in KEY_MATERIAL
    assert "B2" in joined
    assert "هدف چرخشي ترمز ضدقفل" in joined
    assert any(t.displayName == "ExpertMaterialEvidence" for t in ws.tables.values())


def test_html_uses_expert_positions_only_as_visible_evidence():
    transformed, positions = _fixture()
    main = transformed["main"].copy()
    main["KEY_MATERIAL"] = main["MOGH_MATERIAL"].astype(str)
    html = build_dynamic_html(
        main, "2026-09-27", selected_fields=["KEY_MATERIAL", "CANONICAL_ORDER"],
        material_supply_view=positions)
    assert "دفتر کامل شواهد کارشناسان" in html
    assert "9654003280" in html and "B2" in html
    assert "هدف چرخشي ترمز ضدقفل" in html
    assert '"expert_material_evidence_rows": 2' in html
    # Evidence-only ledger must not be able to override operational status.
    bad = pd.DataFrame([{"KEY_MATERIAL": "X", "موقعیت فعلی": "BYPASS"}])
    html2 = build_dynamic_html(main, "2026-09-27", material_supply_view=bad)
    assert "BYPASS" not in html2


def test_evidence_view_preserves_one_row_per_order_material_without_sum():
    _, positions = _fixture()
    out = build_expert_material_evidence_view(positions)
    assert len(out) == 2
    assert set(out["متریال اعلامی کارشناسان"]) == {"9654003280", "B2"}
    a = out.set_index("متریال اعلامی کارشناسان").loc["9654003280"]
    assert int(a["تعداد ردیف منبع"]) == 2
    assert "هدف چرخشي" in a["شرح‌های ثبت‌شده کارشناسان"]
