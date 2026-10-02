# -*- coding: utf-8 -*-
"""Critical and cash-flow fixes applied to the main package.

Pins the real-export SAP format, the gate that made a missing sheet invisible,
the goods-receipt reversal double-count, and the obligation totals scope.
"""
import pandas as pd
import pytest

from gsi.adapters.a60_finance import SapAdapter
from gsi.warehouse.store import Warehouse
from gsi.warehouse.reliability import source_runtime_checks, validate_frame, BLOCK
from gsi.warehouse.marts import stage
from gsi.warehouse.fx_obligation import totals_by_currency
from gsi import health


def pr_sheet():
    return pd.DataFrame([
        {"Purchase Requisition": "6500029693", "Item of requisition": "00010",
         "Material": "9654003280", "Purchase order": "4500000001",
         "Changed On": "2026-01-10", "Release Date": "2026-01-06",
         "Quantity requested": "100", "Processing status": "مورد تایید"}])


def po_sheet():
    return pd.DataFrame([
        {"Purchasing Document": "4500000001", "Item": "00010", "Document Item": "00010",
         "Material": "9111111111", "Purchase Requisition": "6500029999",
         "Item of requisition": "00090", "شماره پرونده": "664823825",
         "Our Reference": "502805", "Your Reference": "SUP-9",
         "Net Order Value": "1200", "Currency": "EUR", "Supplier": "V-900",
         "Document Date": "2026-02-01", "Last Changed on": "2026-02-05"}])


# ── the real export separates grains into sheets ──────────────────────────────
def test_native_multi_sheet_export_is_recognised():
    out = SapAdapter().transform({"pr": pr_sheet(), "po": po_sheet()})
    assert {"pr_items", "po_items", "raw_rows", "main"} <= set(out)
    assert len(out["pr_items"]) == 1 and len(out["po_items"]) == 1


def test_po_identity_comes_from_the_po_sheet_not_the_pr_sheet():
    """The PO sheet carries its own requisition; nothing may borrow the PR header."""
    out = SapAdapter().transform({"pr": pr_sheet(), "po": po_sheet()})
    row = out["po_items"].iloc[0]
    assert row["KEY_PO"] == "4500000001"
    assert row["KEY_PR"] == "6500029999"        # not 6500029693 from the pr sheet
    assert row["SAP_PR_ITEM"] == "90"
    assert row["KEY_MATERIAL"] == "9111111111"


def test_po_sheet_yields_the_native_registration_file_and_order_bridges():
    out = SapAdapter().transform({"pr": pr_sheet(), "po": po_sheet()})
    row = out["po_items"].iloc[0]
    assert row["KEY_REG_FILE"] == "664823825"   # شماره پرونده, observed not inferred
    assert row["KEY_ORDER"] == ""
    assert row["SAP_ORDER_REFERENCE_CANDIDATE"] == "502805"         # Our Reference is the buyer's order
    assert row["SAP_PO_YOUR_REFERENCE"] == "SUP-9"   # the supplier's ref stays separate


def test_inbound_sheet_gives_a_native_sap_to_bill_of_lading_link():
    inbound = pd.DataFrame([{"Delivery": "D1", "Item": "10", "Material": "9654003280",
                             "Delivery Quantity": "60", "Shipment Number": "SH-1",
                             "Supplier": "V-900", "شماره بارنامه": "BL-777"}])
    out = SapAdapter().transform({"inbound": inbound})
    assert out["inbound_deliveries"].iloc[0]["KEY_BL"] == "BL777"


def test_legacy_single_sheet_export_still_works():
    legacy = pd.DataFrame([{
        "Purchase Requisition": "6500029693", "Item of requisition": "00010",
        "Material": "PRMAT", "Changed On": "2026-01-10",
        "po.Purchasing Document": "4500000001", "po.Item": "00010",
        "po.Purchase Requisition": "6500029693", "po.Material": "POMAT"}])
    out = SapAdapter().transform({"Data": legacy})
    assert len(out["po_items"]) == 1
    assert out["po_items"].iloc[0]["KEY_PO"] == "4500000001"


# ── goods receipt: a reversal must not be counted as a second receipt ──────────
def gr_sheet():
    return pd.DataFrame([
        {"Posting Date": "2026-04-01", "Purchase order": "4500000001",
         "Material Document": "5000123", "Material Doc.Item": "1",
         "Material": "9654003280", "Quantity": "60", "Movement Type": "101"},
        {"Posting Date": "2026-04-05", "Purchase order": "4500000001",
         "Material Document": "5000124", "Material Doc.Item": "1",
         "Material": "9654003280", "Quantity": "60", "Movement Type": "102"},
        {"Posting Date": "2026-04-07", "Purchase order": "4500000001",
         "Material Document": "5000125", "Material Doc.Item": "1",
         "Material": "9654003280", "Quantity": "5", "Movement Type": "999"}])


def test_reversed_receipt_cancels_instead_of_double_counting():
    gr = SapAdapter().transform({"GR": gr_sheet()})["goods_receipts"]
    assert gr["SAP_GR_QTY"].sum() == 125          # what a naive sum would report
    assert gr["SAP_GR_SIGNED_QTY"].sum() == 0.0   # receipt 60 cancelled by reversal 60


def test_unknown_movement_type_is_never_given_a_sign():
    gr = SapAdapter().transform({"GR": gr_sheet()})["goods_receipts"]
    row = gr[gr["SAP_GR_MOVEMENT_TYPE"].eq("999")].iloc[0]
    assert row["SAP_GR_DIRECTION"] == "UNCLASSIFIED"
    assert pd.isna(row["SAP_GR_SIGNED_QTY"])


def test_goods_receipt_contract_marks_only_the_signed_quantity_additive():
    gr = SapAdapter().transform({"GR": gr_sheet()})["goods_receipts"]
    checks = {c.code: c for c in validate_frame("sap/goods_receipts", gr)}
    assert checks["REQUIRED_COLUMNS"].passed
    from gsi.warehouse.reliability import CONTRACTS
    c = CONTRACTS["sap/goods_receipts"]
    assert c.additive_measures == ()
    assert "SAP_GR_SIGNED_QTY" in c.non_additive_measures
    assert "SAP_GR_QTY" in c.non_additive_measures


# ── a workbook found but with no expected sheet must block, not degrade ───────
class _Pipeline:
    def __init__(self, sources):
        self.sources = sources
        self.source_failures = {}
        self.source_fallbacks = {}
        self.merge_failures = []


def test_missing_expected_sheet_blocks_publication():
    health.reset()
    rec = health.current().source("sap", title="SAP", required=False)
    health.current().schema_gap("sap", "شیت «Data» در SAP.xlsx نیست (شیت‌های موجود: ['pr','po'])")
    checks = source_runtime_checks(_Pipeline({"sap": {}}))
    broken = [c for c in checks if c.code == "SOURCE_SCHEMA_CONTRACT_BROKEN"]
    assert broken and broken[0].severity == BLOCK and not broken[0].passed
    assert rec is not None


def test_source_simply_absent_still_only_degrades():
    health.reset()
    health.current().source("doccheck", title="DocCheck", required=False)
    checks = source_runtime_checks(_Pipeline({"doccheck": {}}))
    codes = {c.code for c in checks}
    assert "SOURCE_COVERAGE_GAP" in codes
    assert "SOURCE_SCHEMA_CONTRACT_BROKEN" not in codes


# ── cash flow: obligation totals must not sum every archived file version ─────
def _stage_commitment(wh, balance, tag):
    df = pd.DataFrame([{"_SOURCE_ROW": 2, "کد ثبت سفارش": "R1",
                        "تاریخ ایجاد تعهد": "1405/06/24",
                        "وضعیت رفع تعهد": "رفع تعهد نشده", "تعهد اولیه": balance,
                        "مانده تعهد": balance, "ارز": "یورو"}])
    fid = wh.blob(tag.encode(), f"ntsw_{tag}.xlsx", "ntsw", f"/tmp/ntsw_{tag}.xlsx")
    stage(df, "ntsw", "Release Commitment", fid)
    return fid


def test_totals_use_the_published_run_not_every_archived_version(tmp_path, monkeypatch):
    monkeypatch.setenv("GSI_DWH_PATH", str(tmp_path / "w.sqlite"))
    wh = Warehouse(tmp_path / "w.sqlite")
    with wh.run({"t": 1}):
        _stage_commitment(wh, "50", "v1")
    with wh.run({"t": 2}) as rid2:
        _stage_commitment(wh, "50", "v2")
    with wh.db() as c:
        c.execute("INSERT INTO wh_current(slot,run_id) VALUES('dwh',?) "
                  "ON CONFLICT(slot) DO UPDATE SET run_id=excluded.run_id", (rid2,))
    scoped = {(t["سنجه"], t["ارز"]): t for t in totals_by_currency(wh)}
    assert scoped[("مانده تعهد", "یورو")]["جمع معلوم"] == "50"
    assert scoped[("مانده تعهد", "یورو")]["دامنه"].startswith("run:")
    archive = {(t["سنجه"], t["ارز"]): t for t in totals_by_currency(wh, all_versions=True)}
    assert archive[("مانده تعهد", "یورو")]["جمع معلوم"] == "100"      # the old behaviour
    assert archive[("مانده تعهد", "یورو")]["دامنه"] == "all_archived_versions"


def test_totals_without_a_publication_stay_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("GSI_DWH_PATH", str(tmp_path / "w2.sqlite"))
    wh = Warehouse(tmp_path / "w2.sqlite")
    with wh.run({"t": 1}):
        _stage_commitment(wh, "50", "a")
    with wh.run({"t": 2}):
        _stage_commitment(wh, "50", "b")
    assert totals_by_currency(wh) == []  # no unpublished fallback
