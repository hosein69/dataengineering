# -*- coding: utf-8 -*-
"""R10 — ردیف‌های فایل کارشناسان که متریالشان در Oracle نیست، و تحویل از شیت GR فایل SAP.

فقط داده مصنوعی. قاعده مالک: همه ردیف‌های فایل کارشناسان در همه گزارش‌ها می‌آیند؛ متریال
بیرون از Oracle «نامشخص، ممکن است بحرانی» است و نقص داده نام فایل را می‌گوید.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from gsi.adapters.a60_finance import SapAdapter
from gsi.report import critical_board as CB
from gsi.report import inventory_critical_report as R
from gsi.stages.base import PipelineContext
from gsi.stages.s41_sap_gr_delivery import SapGrDeliveryStage, gr_delivery


def _sap() -> dict:
    po = pd.DataFrame({"Purchasing Document": ["4500000001", "4500000002", "4500000003"],
                       "Item": ["00010", "00020", "00010"],
                       "Material": ["MX1", "MX2", "MX4"],
                       "Purchase Requisition": ["PR1", "PR2", "PR4"],
                       "Item of requisition": ["00010", "00010", "00010"]})
    gr = pd.DataFrame({"Posting Date": ["2026-07-01", "2026-07-03", "2026-07-05", "2026-07-06", "2026-08-01",
                                        "2026-08-02"],
                       "Purchase order": ["4500000001"] * 4 + ["4500000002", "4500000002"],
                       "Item": ["10", "10", "10", "10", "20", "20"],
                       "Material Document": ["M1", "M2", "M3", "M4", "M5", "M6"],
                       "Material Doc.Item": ["1"] * 6,
                       "Material": ["MX1"] * 4 + ["MX2", "MX2"],
                       "Quantity": ["200", "200", "150", "20", "100", "7"],
                       "Movement Type": ["103", "105", "103", "122", "101", "999"]})
    return SapAdapter().transform({"po": po, "GR": gr})


def _ompi() -> pd.DataFrame:
    return pd.DataFrame({"KEY_ORDER": ["O1", "O2", "O3", "O4", "O5", "O6"],
                         "KEY_MATERIAL": ["MX1", "MX2", "MX3", "MX4", "MX1", "MX6"],
                         "KEY_PR": ["PR1", "PR2", "PR3", "PR4", "PR1", "PR6"],
                         "MOGH_PR_ITEM": ["10", "", "", "10", "10", "10"]})


def _keys() -> pd.DataFrame:
    return pd.DataFrame({"KEY_ORDER": ["O1", "O2", "O3", "O4", "O5", "O6", "O7"],
                         "KEY_MATERIAL": ["MX1", "MX2", "MX3", "MX4", "MX1", "MX6", "MX7"]})


def test_gr_movements_link_states_and_shared_line():
    sap = _sap()
    info = gr_delivery(_keys(), _ompi(), sap["po_items"], sap["goods_receipts"])
    o1 = info[("O1", "MX1")]
    # 103 و 105 یک کالا هستند؛ 122 برگشت از انبار است
    assert o1["GR_DLV_LINK"] == "LINKED" and o1["GR_DLV_PO_LINES"] == "4500000001/10"
    assert o1["GR_DLV_DELIVERED_QTY"] == 180.0            # 200 (105) − 20 (122)؛ نه 550
    assert o1["GR_DLV_BLOCKED_QTY"] == 150.0              # 200 + 150 − 200
    assert o1["GR_DLV_RETURNED_QTY"] == 20.0 and o1["GR_DLV_LAST_DATE"] == "2026-07-06"
    assert o1["GR_DLV_SHARED"] == "O5"                    # همان قلم PO؛ قابل تقسیم نیست
    # قلم PR خالی: PR + متریال دقیق؛ نوع حرکت ناشناخته در جمع نمی‌آید و شمرده می‌شود
    o2 = info[("O2", "MX2")]
    assert o2["GR_DLV_DELIVERED_QTY"] == 100.0 and o2["GR_DLV_UNCLASSIFIED"] == 1
    assert info[("O3", "MX3")]["GR_DLV_LINK"] == "PR_NOT_IN_PO"
    assert info[("O4", "MX4")]["GR_DLV_LINK"] == "PO_NO_GR" and info[("O4", "MX4")]["GR_DLV_DELIVERED_QTY"] is None
    assert info[("O7", "MX7")]["GR_DLV_LINK"] == "NO_PR"
    # بی‌شیت GR: نامعلوم، نه صفر
    none = gr_delivery(_keys(), _ompi(), sap["po_items"], None)
    assert all(r["GR_DLV_LINK"] == "NO_SAP_GR" and r["GR_DLV_DELIVERED_QTY"] is None for r in none.values())


def test_stage_flags_non_oracle_rows_with_file_names():
    sap = _sap()
    df = pd.DataFrame({"KEY_ORDER": ["O1", "O7"], "KEY_MATERIAL": ["MX1", "MX7"],
                       "کد طبقه بحرانی": ["CRITICAL", "UNKNOWN"], "DAILY_NEED": [10.0, None],
                       "STOCK_IKCO": [5.0, None], "STOCK_SAPCO": [0.0, None]})
    oracle = pd.DataFrame({"KEY_MATERIAL": ["MX1"], "_SOURCE_FILE": ["Oracle.xlsx"]})
    ctx = PipelineContext(rb=None, today=date(2026, 8, 31),
                          sources={"sap": {**sap, "goods_receipts": sap["goods_receipts"].assign(
                              _SOURCE_FILE="GS_Full Chain 1405.xlsx")},
                                   "moghavemat": {"order_material_pr_item": _ompi()}, "oracle": {"main": oracle}})
    out = SapGrDeliveryStage().run(df.copy(), ctx)
    r1, r7 = out.iloc[0], out.iloc[1]
    assert bool(r1["ORACLE_HAS_MATERIAL"]) and r1["DATA_GAP_FILES"] == "" and r1["CRITICALITY_NOTE"] == ""
    assert not bool(r7["ORACLE_HAS_MATERIAL"])
    assert "Oracle.xlsx: متریال نیست" in r7["DATA_GAP_FILES"]
    assert "Commercial Expert Data.xlsx: PR خالی است" in r7["DATA_GAP_FILES"]
    assert "ممکن است بحرانی" in r7["CRITICALITY_NOTE"]
    assert ctx.extras["gr_delivery_files"]["sap"] == "GS_Full Chain 1405.xlsx"


def _row(order, mat, code, gap="", dlv=None, lines="", **kw):
    return {"KEY_ORDER": order, "CANONICAL_ORDER": order, "KEY_MATERIAL": mat, "CANONICAL_BL": "", "KEY_BL": "",
            "کد طبقه بحرانی": code, "مقاومت (روز)": 3.0 if code == "CRITICAL" else None,
            "STOCK_IKCO": 30.0 if code == "CRITICAL" else None, "STOCK_SAPCO": None,
            "DAILY_NEED": 10.0 if code == "CRITICAL" else None, "MATERIAL_DESC": "شرح " + mat,
            "CANONICAL_EXPERT": "کارشناس", "DATA_GAP_FILES": gap, "GR_DLV_DELIVERED_QTY": dlv,
            "GR_DLV_BLOCKED_QTY": 0.0 if dlv is not None else None, "GR_DLV_PO_LINES": lines,
            "GR_DLV_LINK_FA": "تحویل در GR ثبت شده" if lines else "", "GR_DLV_LAST_DATE": "", **kw}


def _frame() -> pd.DataFrame:
    gap = "Oracle.xlsx: متریال نیست (موجودی ایران‌خودرو/ساپکو و نیاز روزانه نامعلوم)"
    return pd.DataFrame([
        _row("O1", "MC", "CRITICAL"),
        _row("O2", "MU", "UNKNOWN", gap, 180.0, "4500000001/10"),
        _row("O3", "MU", "UNKNOWN", gap, 180.0, "4500000001/10"),     # همان قلم PO، سفارش دیگر
        _row("O4", "MV", "UNKNOWN", gap),
    ])


def test_inventory_report_keeps_unknown_rows_with_gap_and_gr():
    m = R.build_model(_frame(), None, "1405/06/10")
    assert set(m.materials["متریال"]) == {"MC", "MU", "MV"}
    fu = m.followup
    assert fu["متریال"].tolist()[0] == "MC"                      # بحرانی اول
    assert set(fu["متریال"].tolist()[1:]) == {"MU", "MV"} and len(fu) == 4
    assert fu.set_index("سفارش").loc["O2", R.GR_DLV] == 180.0
    assert "Oracle.xlsx" in fu.set_index("سفارش").loc["O4", R.GAP]
    mu = m.materials.set_index("متریال").loc["MU"]
    assert mu[R.GR_DLV] == 180.0                                 # قلم مشترک یک بار، نه 360
    assert mu["اقدام پیشنهادی"] == R.MAYBE_CRIT and "Oracle.xlsx" in mu[R.GAP]
    assert m.kpis[R.KPI_MAYBE] == 2 and m.kpis["متریال بحرانی"] == 1
    assert set(m.checks.loc[m.checks["بررسی"].eq(R.CHK_MAYBE_CRIT), "متریال"]) == {"MU", "MV"}
    page = R.build_html(m, lang="en", embed_fonts=False)
    assert "material not present" in page and "Data gap (which file)" in page


def test_critical_board_lists_unknown_materials():
    df = _frame()
    w = CB.watch_materials(df)
    assert w["متریال"].tolist() == ["MU", "MV"]
    assert w.set_index("متریال").loc["MU", "تحویل‌شده به انبار (GR)"] == 180.0
    page = CB.build_critical_html(df, "1405/06/10")
    assert CB.WATCH_TITLE in page and "MV" in page and "Oracle.xlsx" in page
    only_known = CB.build_critical_html(df[df["کد طبقه بحرانی"].ne("UNKNOWN")], "1405/06/10")
    assert CB.WATCH_TITLE not in only_known
