# -*- coding: utf-8 -*-
"""Regression tests for the reviewed GSI Source Profiler.

Each test pins one defect from MAP_DEFECTS.md against the real GSI header
spellings. Run: python -m pytest -q test_profiler.py
"""
import json, subprocess, sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from gsi_source_profiler import (                                    # noqa: E402
    classify_column, semantic_columns, representative_key_columns, key_conflicts,
    relation_examples, infer_grain, status_profile, norm_key, load_config,
    build_global_key_index, column_side, MIN_GRAIN_COVERAGE,
)

SAP_ROWS = [
    {"Purchase Requisition": "6500029693", "Item of requisition": "00010",
     "Material": "9654003280", "Material Description": "واشر تخت", "Material Group": "MG-11",
     "Purchase order": "4500000001", "Quantity ordered": "60", "Name of Supplier": "ACME",
     "Changed On": "2026-01-10", "Processing status": "مورد تایید", "WorkFlow ID": "WF-1",
     "WorkFlow Status": "RELEASED", "po.Purchasing Document": "4500000001", "po.Item": "00010",
     "po.Purchase Requisition": "6500029693", "po.Item of requisition": "00010",
     "po.Material": "9654003280", "po.Net Order Value": "1200", "po.Currency": "EUR",
     "po.شماره پرونده": "664823825"},
    {"Purchase Requisition": "6500029693", "Item of requisition": "00010",
     "Material": "9654003280", "Material Description": "واشر تخت", "Material Group": "MG-11",
     "Purchase order": "4500000002", "Quantity ordered": "40", "Name of Supplier": "ACME",
     "Changed On": "2026-01-10", "Processing status": "تایید نشده", "WorkFlow ID": "WF-1",
     "WorkFlow Status": "RELEASED", "po.Purchasing Document": "4500000002", "po.Item": "00020",
     "po.Purchase Requisition": "6500029999", "po.Item of requisition": "00090",
     "po.Material": "9111111111", "po.Net Order Value": "800", "po.Currency": "EUR",
     "po.شماره پرونده": "664823825"},
]
IL_ROWS = [
    {"شماره پرونده ثبت سفارش": "664823825", "کد ثبت سفارش": "98404279",
     "شماره سفارش": "502805", "تاریخ صدور": "1405/01/01", "وضعیت": "فعال"},
    {"شماره پرونده ثبت سفارش": "664823826", "کد ثبت سفارش": "98404280",
     "شماره سفارش": "812211A", "تاریخ صدور": "1405/02/01", "وضعیت": "فعال"},
]


def sap_df():
    return pd.DataFrame(SAP_ROWS)


def il_df():
    return pd.DataFrame(IL_ROWS)


# ── M-02 : a measure is never a key, and role families resolve specific-first ──
@pytest.mark.parametrize("header,expected_key_role", [
    ("Purchase order", "PO"),                 # SAP purchasing document, not ORDER
    ("po.Net Order Value", None),             # money
    ("Quantity In Order", None),              # quantity
    ("Order No. (Our Reference)", "ORDER"),
    ("شماره پرونده ثبت سفارش", "REG_FILE"),    # 9-digit file, not the 8-digit code
    ("کد ثبت سفارش", "REG"),
    ("پرونده ترخیص", "CUSTOMS_FILE"),          # customs file is its own entity
    ("Material Description", None),
    ("Material Group", None),
    ("Material", "MATERIAL"),
    ("po.Item of requisition", "PR_ITEM"),     # a requisition item, not a PO item
    ("po.Item", "PO_ITEM"),
    ("تاریخ  دریافت شماره کوتاژ", None),        # a date, not a cotage key
    ("کوتاژ", "COTTAGE"),
    ("تاریخ تایید", None),                     # a date, not a status
    ("WorkFlow Status", None),                 # a status, not a workflow id
    ("WorkFlow ID", "WORKFLOW"),
    ("شماره ردیف تعهد", "NATIVE_ROW_ID"),
    ("po.Currency", None),
    ("مانده تعهد", None),
])
def test_key_role_assignment(header, expected_key_role):
    assert classify_column(header)["key_role"] == expected_key_role


def test_measure_columns_never_hold_a_key_role():
    for c in ("po.Net Order Value", "Quantity ordered", "Changed On", "تاریخ صدور",
              "مبلغ درخواست", "نوع ارز"):
        cls = classify_column(c)
        assert cls["key_role"] is None, c
        assert cls["measure_roles"], c


def test_sap_purchase_order_is_not_a_commercial_order():
    sem = semantic_columns(sap_df())
    assert "Purchase order" in sem.get("PO", [])
    assert "ORDER" not in sem, f"SAP must not publish an ORDER key: {sem.get('ORDER')}"


def test_side_marks_the_grain_a_column_belongs_to():
    assert column_side("po.Purchase Requisition") == "po"
    assert column_side("Purchase Requisition") == "header"
    assert column_side("pack.Pack Number") == "pack"


# ── M-01 : the Import Licence hub must profile, not crash ─────────────────────
def test_import_licence_hub_profiles_without_crashing():
    df = il_df()
    sem = semantic_columns(df)
    keys = representative_key_columns(df, sem)
    rels = relation_examples(df, sem, keys)          # upstream raised AttributeError here
    pair = [r for r in rels if {r["from_role"], r["to_role"]} == {"REG", "REG_FILE"}]
    assert pair, "REG_FILE↔REG co-observation must be reported"
    assert pair[0]["from_column"] != pair[0]["to_column"]


def test_reg_role_takes_the_code_not_the_file_number():
    df = il_df()
    keys = representative_key_columns(df, semantic_columns(df))
    assert keys["REG"] == "کد ثبت سفارش"
    assert keys["REG_FILE"] == "شماره پرونده ثبت سفارش"


# ── M-03 : representative key chosen by evidence, not column order ─────────────
def test_representative_key_prefers_coverage_over_position():
    df = pd.DataFrame({"کد ثبت سفارش": ["", "", "98404279"],
                       "شماره ثبت سفارش": ["98404279", "98404280", "98404281"]})
    keys = representative_key_columns(df, semantic_columns(df))
    assert keys["REG"] == "شماره ثبت سفارش"


# ── M-09 : same-role conflicts are surfaced, not merged ───────────────────────
def test_header_pr_and_po_pr_conflict_is_reported():
    df = sap_df()
    conflicts = key_conflicts(df, semantic_columns(df))
    pr = [c for c in conflicts if c["role"] == "PR"]
    assert pr, "header PR vs po.Purchase Requisition must be reported"
    assert pr[0]["rows_disagreeing"] == 1
    assert {pr[0]["side_a"], pr[0]["side_b"]} == {"header", "po"}


def test_no_conflict_reported_when_columns_agree():
    df = sap_df().copy()
    df.loc[1, "po.Purchase Requisition"] = "6500029693"
    assert not [c for c in key_conflicts(df, semantic_columns(df)) if c["role"] == "PR"]


# ── M-04 : Persian/Arabic folding for comparison only ─────────────────────────
def test_arabic_and_persian_spellings_fold_together():
    assert norm_key("تخصيص يافته") == norm_key("تخصیص یافته")
    assert norm_key("۹۸۴۰۴۲۷۹") == norm_key("98404279")
    assert norm_key("كالا") == norm_key("کالا")


def test_status_counts_fold_but_keep_raw_variants():
    df = pd.DataFrame({"وضعیت": ["تخصيص يافته", "تخصیص یافته", "تایید نشده"]})
    rows = status_profile(df, ["وضعیت"])["وضعیت"]
    allocated = [r for r in rows if "تخص" in r["normalised"]]
    assert len(allocated) == 1 and allocated[0]["count"] == 2
    assert len(allocated[0]["raw_variants"]) == 2      # both spellings stay visible


def test_persian_digits_do_not_inflate_distinct_keys():
    df = pd.DataFrame({"کد ثبت سفارش": ["98404279", "۹۸۴۰۴۲۷۹"]})
    grain = infer_grain(df, representative_key_columns(df, semantic_columns(df)))
    reg = [c for c in grain["candidates"] if c["label"] == "REG"][0]
    assert reg["distinct_keys"] == 1


# ── M-06 : grain needs coverage, not just a high ratio on a few rows ──────────
def test_grain_candidate_below_coverage_is_never_named_best():
    df = pd.DataFrame({"کد ثبت سفارش": ["98404279"] + [""] * 19,
                       "شماره سفارش": ["502805"] + [""] * 19})
    grain = infer_grain(df, representative_key_columns(df, semantic_columns(df)))
    assert grain["best_candidate"] is None
    assert any(c["coverage_of_frame"] < MIN_GRAIN_COVERAGE for c in grain["candidates"])


def test_grain_candidate_with_full_coverage_is_selected():
    df = pd.DataFrame({"کد ثبت سفارش": [f"9840427{i}" for i in range(10)],
                       "شماره سفارش": [f"50280{i}" for i in range(10)]})
    grain = infer_grain(df, representative_key_columns(df, semantic_columns(df)))
    assert grain["best_candidate"]["coverage_of_frame"] == 1.0


# ── M-08 : composite repeated keys are profiled ───────────────────────────────
def test_repeated_composite_key_is_reported():
    from gsi_source_profiler import duplicate_profile
    df = pd.DataFrame({"کد ثبت سفارش": ["98404279"] * 4,
                       "شماره ردیف تعهد": ["7", "7", "8", "9"]})
    keys = representative_key_columns(df, semantic_columns(df))
    grain = infer_grain(df, keys)
    dp = duplicate_profile(df, keys, grain)
    comp = [d for d in dp["composite_grain"] if d["grain_label"] == "REG_NATIVE_ROW"]
    assert comp and comp[0]["duplicate_rows"] == 2


# ── M-11/M-12 : config validation ─────────────────────────────────────────────
def test_duplicate_source_name_is_rejected(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("sources:\n  - {name: A, path: x}\n  - {name: a, path: y}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate source name"):
        load_config(p)


def test_unknown_config_key_names_the_offender(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("sources:\n  - {name: A, path: x, shets: all}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown key"):
        load_config(p)


def test_shipped_registry_covers_the_real_sources():
    cfg = load_config(Path(__file__).parent / "gsi_sources.yaml")
    names = {s.name.casefold() for s in cfg}
    for required in ("oracle", "credit", "il_append", "doccheck", "hr", "cotage"):
        assert required in names, f"{required} missing from the registry"


# ── M-05 : incomplete coverage is loud and exits non-zero ─────────────────────
def _run(tmp_path, cfg_text, *extra):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(cfg_text, encoding="utf-8")
    out = tmp_path / "pack"
    r = subprocess.run([sys.executable, str(Path(__file__).parent / "gsi_source_profiler.py"),
                        "--config", str(cfg), "--output", str(out), *extra],
                       capture_output=True, text=True)
    return r, out


def test_missing_source_is_loud_and_fails(tmp_path):
    r, out = _run(tmp_path, "sources:\n  - {name: Ghost, path: /nonexistent/x.xlsx}\n")
    assert r.returncode == 2
    summary = (out / "executive_summary.md").read_text(encoding="utf-8")
    assert "INCOMPLETE" in summary and "Ghost" in summary
    pack = (out / "model_context_pack.md").read_text(encoding="utf-8")
    assert "INCOMPLETE EVIDENCE PACK" in pack
    cov = json.loads((out / "coverage_report.json").read_text(encoding="utf-8"))
    assert cov["coverage"][0]["status"] == "MISSING_FILE"


def test_allow_missing_flag_downgrades_exit_code(tmp_path):
    r, _ = _run(tmp_path, "sources:\n  - {name: Ghost, path: /nonexistent/x.xlsx}\n",
                "--allow-missing")
    assert r.returncode == 0


def test_configured_sheet_absent_from_workbook_is_reported(tmp_path):
    wb = tmp_path / "w.xlsx"
    pd.DataFrame(IL_ROWS).to_excel(wb, sheet_name="Import Licence", index=False)
    r, out = _run(tmp_path, f"sources:\n  - name: NTSW\n    path: {wb}\n    sheets: ['Allocation']\n")
    assert r.returncode == 2
    cov = json.loads((out / "coverage_report.json").read_text(encoding="utf-8"))
    assert any("Allocation" in e for e in cov["errors"])


# ── M-07 : sample rows carry workbook provenance ──────────────────────────────
def test_sample_rows_carry_excel_row_and_file(tmp_path):
    wb = tmp_path / "ntsw.xlsx"
    pd.DataFrame(IL_ROWS).to_excel(wb, sheet_name="Import Licence", index=False)
    r, out = _run(tmp_path, f"sources:\n  - name: NTSW\n    path: {wb}\n    sheets: all\n")
    assert r.returncode == 0
    s = pd.read_csv(next((out / "samples").glob("*.csv")), dtype=object)
    for col in ("__excel_row__", "__source_file__", "__sheet__", "__frame_row_index__"):
        assert col in s.columns
    assert sorted(int(x) for x in s["__excel_row__"]) == [2, 3]   # header on row 1
    assert set(s["__sheet__"]) == {"Import Licence"}


# ── M-02 downstream : the cross-source join map stays clean ───────────────────
def test_join_map_is_built_from_representative_keys_only(tmp_path):
    wb1, wb2 = tmp_path / "sap.xlsx", tmp_path / "experts.xlsx"
    pd.DataFrame(SAP_ROWS).to_excel(wb1, sheet_name="Data", index=False)
    pd.DataFrame([{"Order No. (Our Reference)": "502805", "Material": "9654003280",
                   "Quantity In Order": "100"}]).to_excel(wb2, sheet_name="Expert Data",
                                                          index=False)
    r, out = _run(tmp_path, f"sources:\n  - name: SAP\n    path: {wb1}\n"
                            f"  - name: Commercial_Expert\n    path: {wb2}\n")
    assert r.returncode == 0
    idx = json.loads((out / "process_key_index.json").read_text(encoding="utf-8"))
    order_cols = [x["column"] for x in idx["roles"].get("ORDER", [])]
    assert "Purchase order" not in order_cols
    assert "po.Net Order Value" not in order_cols
    assert "Quantity In Order" not in order_cols
    assert order_cols == ["Order No. (Our Reference)"]
    assert "ORDER" not in idx["candidate_cross_source_join_roles"]


# ── export sequence number is not a business identifier ───────────────────────
@pytest.mark.parametrize("header,expected", [
    ("ردیف", "EXPORT_ROW_NO"),
    ("شماره ردیف تعهد", "NATIVE_ROW_ID"),
    ("ردیف درخواست", "NATIVE_ROW_ID"),
    ("Comparision ID", "COMPARISON"),
    ("WorkFlow ID", "WORKFLOW"),
    ("Name of Supplier", None),          # a name is not a key
    ("po.Supplier", "SUPPLIER"),
])
def test_row_counter_and_identifier_roles(header, expected):
    assert classify_column(header)["key_role"] == expected


def test_repeated_commitment_line_is_not_hidden_by_the_row_counter():
    """A repeated obligation line must stay visible as a repeated composite key.

    Picking the export sequence number as the native id would make every row
    unique and silently answer the snapshot-versus-new-obligation question.
    """
    from gsi_source_profiler import duplicate_profile
    df = pd.DataFrame({
        "ردیف": ["1", "2", "3"],
        "کد ثبت سفارش": ["98404279"] * 3,
        "شماره ردیف تعهد": ["7", "7", "8"],
        "مانده تعهد": ["50", "50", "20"],
    })
    sem = semantic_columns(df)
    keys = representative_key_columns(df, sem)
    assert keys["NATIVE_ROW_ID"] == "شماره ردیف تعهد"
    assert keys.get("EXPORT_ROW_NO") == "ردیف"
    grain = infer_grain(df, keys)
    comp = [d for d in duplicate_profile(df, keys, grain)["composite_grain"]
            if d["grain_label"] == "REG_NATIVE_ROW"]
    assert comp and comp[0]["duplicate_rows"] == 2


def test_export_row_number_never_reaches_the_join_map():
    profiles = [{"source": "NTSW", "sheet": "Release Commitment", "authority": "", "domain": "",
                 "representative_keys": {"REG": "کد ثبت سفارش", "EXPORT_ROW_NO": "ردیف"},
                 "semantic_columns": {}},
                {"source": "FX", "sheet": "Sheet1", "authority": "", "domain": "",
                 "representative_keys": {"REG": "ثبت سفارش", "EXPORT_ROW_NO": "ردیف"},
                 "semantic_columns": {}}]
    idx = build_global_key_index(profiles)
    assert "EXPORT_ROW_NO" not in idx["roles"]
    assert "EXPORT_ROW_NO" not in idx["candidate_cross_source_join_roles"]
    assert "REG" in idx["candidate_cross_source_join_roles"]
