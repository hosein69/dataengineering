from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd


def test_sap_raw_rows_grain_is_sheet_plus_row_and_allows_row_number_restart():
    from gsi.warehouse.reliability import CONTRACTS, validate_frame, blocking

    contract = CONTRACTS["sap/raw_rows"]
    assert contract.natural_key == ("SAP_SOURCE_SHEET", "SAP_SOURCE_ROW")

    ok = pd.DataFrame([
        {"SAP_SOURCE_SHEET": "pr", "SAP_SOURCE_ROW": 1, "KEY_PR": "P1"},
        {"SAP_SOURCE_SHEET": "po", "SAP_SOURCE_ROW": 1, "KEY_PO": "O1"},
        {"SAP_SOURCE_SHEET": "GR", "SAP_SOURCE_ROW": 1, "SAP_GR_MATERIAL_DOC": "M1"},
    ])
    checks = validate_frame("sap/raw_rows", ok)
    uq = next(c for c in checks if c.code == "GRAIN_UNIQUENESS")
    assert uq.passed and uq.detail["duplicate_rows"] == 0
    assert not blocking(checks)

    bad = pd.concat([ok, ok.iloc[[0]]], ignore_index=True)
    checks = validate_frame("sap/raw_rows", bad)
    uq = next(c for c in checks if c.code == "GRAIN_UNIQUENESS")
    assert not uq.passed and uq.detail["duplicate_rows"] == 2
    assert blocking(checks)


def test_f031_unknown_financial_values_remain_missing_while_real_zero_remains_zero():
    from gsi.stages.base import PipelineContext
    from gsi.stages.s20_derive import DeriveStage

    ctx = PipelineContext(rb=None, today=date(2026, 9, 24))
    out = DeriveStage().run(pd.DataFrame({
        "NTSW_BALANCE": [float("nan"), 0, "bad", float("inf"), "12.5"],
    }), ctx)

    assert out["BALANCE_IS_UNKNOWN"].tolist() == [True, False, True, True, False]
    assert pd.isna(out.loc[0, "BALANCE"])
    assert out.loc[1, "BALANCE"] == 0
    assert pd.isna(out.loc[2, "BALANCE"])
    assert pd.isna(out.loc[3, "BALANCE"])
    assert float(out.loc[4, "BALANCE"]) == 12.5
    cov = ctx.extras["derive_coverage"]
    assert cov["unknown_defaulted_to_zero"] == {}
    assert cov["unknown_preserved_as_missing"]["BALANCE"] == 3


def test_safe_merge_namespaces_rhs_physical_lineage_instead_of_dropping_it():
    from gsi.dataio.merge import safe_merge

    left = pd.DataFrame({
        "KEY_REG": ["R1"], "_SOURCE_ROW": [7], "_SOURCE_FILE_ID": ["LEFT"],
    })
    right = pd.DataFrame({
        "KEY_REG": ["R1"], "_SOURCE_ROW": [41], "_SOURCE_FILE_ID": ["RIGHT"],
        "_SOURCE_SHEET": ["SheetA"], "VALUE": [10],
    })
    out = safe_merge(left, right, "KEY_REG", "fx_transaction")

    assert out.loc[0, "_SOURCE_ROW"] == 7
    assert out.loc[0, "_SOURCE_FILE_ID"] == "LEFT"
    assert out.loc[0, "FX_TRANSACTION_SOURCE_ROW"] == 41
    assert out.loc[0, "FX_TRANSACTION_SOURCE_FILE_ID"] == "RIGHT"
    assert out.loc[0, "_SOURCE_SHEET"] == "SheetA"  # no clash: original name is retained
    assert out.loc[0, "VALUE"] == 10


def test_process_evidence_counts_sap_physical_rows_once_but_keeps_pr_stage_evidence():
    from gsi.resolve.process_evidence import build_process_inventory

    raw = pd.DataFrame([
        {"SAP_SOURCE_SHEET": "pr", "SAP_SOURCE_ROW": 1, "KEY_PR": "P1"},
        {"SAP_SOURCE_SHEET": "po", "SAP_SOURCE_ROW": 1, "KEY_PR": "P1", "KEY_PO": "O1"},
    ])
    pr = pd.DataFrame([
        {"SAP_SOURCE_SHEET": "pr", "SAP_SOURCE_ROW": 1, "KEY_PR": "P1", "SAP_PR_ITEM": "10"},
    ])
    po = pd.DataFrame([
        {"SAP_SOURCE_SHEET": "po", "SAP_SOURCE_ROW": 1, "KEY_PR": "P1", "KEY_PO": "O1", "SAP_PO_ITEM": "10"},
    ])
    obs, cases, matrix = build_process_inventory({"sap": {"raw_rows": raw, "pr_items": pr, "po_items": po}})

    generic = obs[obs["STAGE_CODE"].eq("SOURCE_OBSERVATION")]
    assert len(generic) == len(raw)
    assert generic["SOURCE_ROW_REF"].nunique() == 2
    assert (obs["STAGE_CODE"] == "PLANNING_PR").sum() == 1
    assert not cases.empty and not matrix.empty


def test_business_dwh_archives_sap_raw_once_and_still_builds_semantic_facts(tmp_path):
    from gsi.warehouse.business_dwh import build
    from gsi.warehouse.store import Warehouse

    wh = Warehouse(tmp_path / "w.sqlite")
    raw = pd.DataFrame([
        {"SAP_SOURCE_SHEET": "pr", "SAP_SOURCE_ROW": 1, "KEY_PR": "P1"},
        {"SAP_SOURCE_SHEET": "po", "SAP_SOURCE_ROW": 1, "KEY_PR": "P1", "KEY_PO": "PO1"},
    ])
    pr = pd.DataFrame([{"KEY_PR": "P1", "SAP_PR_ITEM": "10", "KEY_MATERIAL": "M1"}])
    po = pd.DataFrame([{
        "KEY_PO": "PO1", "SAP_PO_ITEM": "20", "SAP_PO_PR": "P1",
        "SAP_PO_PR_ITEM": "10", "SAP_PO_MATERIAL": "M1",
    }])
    with wh.run({"test": "sap_archive_once"}) as rid:
        counts = build(wh, {"sap": {"raw_rows": raw, "pr_items": pr, "po_items": po}}, rid)

    assert counts["source_rows"] == 2
    assert counts["sap_pr_items"] == 1
    assert counts["sap_po_items"] == 1
    with wh.db() as conn:
        assert conn.execute("SELECT count(*) FROM dwh_fact_source_row WHERE source='sap'").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM dwh_fact_sap_pr_item").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM dwh_fact_sap_po_item").fetchone()[0] == 1


def test_sap_native_reader_uses_one_excel_handle_per_workbook(tmp_path, monkeypatch):
    from gsi.config.sources import get_source
    from gsi.dataio import reader

    path = tmp_path / "sap.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        pd.DataFrame({"Purchase Requisition": ["P1"]}).to_excel(xw, sheet_name="pr", index=False)
        pd.DataFrame({"Pack Number": ["K1"]}).to_excel(xw, sheet_name="pack", index=False)
        pd.DataFrame({"Purchasing Document": ["PO1"]}).to_excel(xw, sheet_name="po", index=False)
        pd.DataFrame({"Inbound Delivery": ["I1"]}).to_excel(xw, sheet_name="inbound", index=False)
        pd.DataFrame({"Material Document": ["G1"]}).to_excel(xw, sheet_name="GR", index=False)

    real_excel_file = reader.pd.ExcelFile
    calls = []

    def counted_excel_file(*args, **kwargs):
        calls.append(str(args[0]))
        return real_excel_file(*args, **kwargs)

    monkeypatch.setattr(reader.pd, "ExcelFile", counted_excel_file)
    out = reader._read_targets(get_source("sap"), [str(path)])
    assert set(out) == {"pr", "pack", "po", "inbound", "GR"}
    assert len(calls) == 1


def test_dashboard_default_path_is_snapshot_only_not_automatic_etl():
    root = Path(__file__).resolve().parents[1]
    text = (root / "app" / "dashboard.py").read_text(encoding="utf-8")
    assert "data = None if _rerun else load_published(ref_date)" in text
    assert "if _rerun:\n        data = load_pipeline(ref_date)" in text
    assert "elif data is None:" in text


def test_snapshot_excel_export_module_never_imports_or_runs_pipeline():
    import ast
    root = Path(__file__).resolve().parents[1]
    text = (root / "gsi" / "warehouse" / "export_snapshot.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any(name.endswith("pipeline") or name == "gsi.pipeline" for name in imported)
    assert "last_report" in text and "build_custom_excel" in text


def test_early_quality_gate_skips_business_dwh_for_known_blocking_source_error(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from gsi.warehouse import bridge
    from gsi.warehouse.store import QualityGateBlockedError, Warehouse
    import pytest

    monkeypatch.setenv("GSI_DWH_PATH", str(tmp_path / "w.sqlite"))
    # Same physical sheet+row twice: a real raw-grain violation, known before DWH.
    bad_raw = pd.DataFrame([
        {"SAP_SOURCE_SHEET": "pr", "SAP_SOURCE_ROW": 1, "KEY_PR": "P1"},
        {"SAP_SOURCE_SHEET": "pr", "SAP_SOURCE_ROW": 1, "KEY_PR": "P1"},
    ])
    result = SimpleNamespace(
        df=pd.DataFrame({"x": [1]}), main=pd.DataFrame({"x": [1]}),
        to_resolve=pd.DataFrame(), excluded=pd.DataFrame(), audit=pd.DataFrame(),
        mogh_lines=pd.DataFrame(), extras={
            "process_evidence_summary": {
                "row_preservation_ok": True,
                "expected_native_rows": 2,
                "preserved_source_observations": 2,
                "orphan_no_business_key": 0,
            },
            "derive_coverage": {},
        },
        dashboard_path=None, extract_paths=[], counts={},
    )

    class FakePipeline:
        today = date(2026, 9, 24)
        sources = {"sap": {"raw_rows": bad_raw}}
        source_failures = {}
        source_fallbacks = {}
        merge_failures = []
        def _run_warehouse(self, _build_report):
            return result

    called = {"dwh": 0}
    def forbidden_dwh(*args, **kwargs):
        called["dwh"] += 1
        raise AssertionError("Business DWH must be skipped after an early blocking gate")
    monkeypatch.setattr(bridge, "build_business_dwh", forbidden_dwh)

    with pytest.raises(QualityGateBlockedError) as ex:
        bridge.run_pipeline(FakePipeline(), build_report=False, version="test")
    assert "sap/raw_rows:GRAIN_UNIQUENESS" in ex.value.as_dict()["blocking_checks"]
    assert called["dwh"] == 0
    wh = Warehouse(tmp_path / "w.sqlite")
    assert wh.current_run("report") is None
