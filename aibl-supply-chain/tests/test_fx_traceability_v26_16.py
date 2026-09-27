# -*- coding: utf-8 -*-
"""Regression tests for V26.16 FX traceability."""
from datetime import date
import os, sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pandas as pd

from gsi.rulebook import get_rulebook
from gsi.stages.base import PipelineContext
from gsi.stages.s55_fx_traceability import FxTraceabilityStage
from gsi.stages.s85_conformance import ConformanceStage, MANDATORY_BEFORE


def _ctx():
    reg = "12345678"
    sources = {
        "fx_transaction": {"main": pd.DataFrame([{
            "KEY_REG": reg, "FX_AMOUNT": 100, "FX_RIAL_VALUE": 9_000_000,
            "FX_EUR_VALUE": 100, "FX_CURRENCY": "EUR", "FX_BUY_DATE": "2026-05-01",
            "FX_BENEFICIARY": "SUP", "FX_BANK": "BANK", "FX_EXCHANGE": "EX",
            "FX_STATUS": "done"}])},
        "credit": {"main": pd.DataFrame([{
            "KEY_REG": reg, "CRD_FUND_DATE": "2026-05-02", "CRD_SWIFT_DATE": "2026-05-03",
            "CRD_RIAL_AMOUNT": 9_000_000, "CRD_EUR_AMOUNT": 100,
            "CRD_LAST_STATUS": "sent", "CRD_LC_NO": "LC1", "CRD_PROFORMA_VALUE": 100,
            "CRD_PREPAYMENT": 20, "CRD_REMAINING": 0}])},
        "ntsw": {
            "commitment": pd.DataFrame([{
                "KEY_REG": reg, "NTSW_INITIAL_COMMIT": 100, "NTSW_BALANCE": 0,
                "NTSW_COMMIT_DATE": "2026-04-20", "NTSW_CURRENCY": "EUR",
                "NTSW_RELEASE_STATUS": "رفع تعهد شده"}]),
            "allocation": pd.DataFrame([{
                "KEY_REG": reg, "NTSW_REQ_AMOUNT": 100, "NTSW_REQ_CURRENCY": "EUR",
                "NTSW_ALLOC_DATE": "2026-04-25", "NTSW_ALLOCATED": True,
                "NTSW_ALLOC_STATUS": "تخصیص یافته", "NTSW_REQ_TYPE": "معامله مستقیم",
                "NTSW_ALLOC_PROCESS": "تخصیص", "NTSW_FX_SOURCE": "مرکز مبادله"}]),
        },
    }
    return PipelineContext(rb=get_rulebook(reload=True, as_of=date(2026, 9, 17)),
                           today=date(2026, 9, 17), sources=sources)


def test_fx_ledger_is_reg_grain_and_no_fanout():
    reg = "12345678"
    df = pd.DataFrame([
        {"CANONICAL_REG": reg, "CANONICAL_BL": "BL001", "BL_DATE": "2026-05-10",
         "COT_DATE": "2026-06-20", "FULL_CLEAR_DATE": "2026-06-25",
         "IS_FULL_CLEARED": True, "COTAGE_NO": "COT1", "SATA_NO": "SAT1",
         "SATA_DATE": "2026-06-24", "INVOICE_VALUE": 60, "CURRENCY": "EUR"},
        {"CANONICAL_REG": reg, "CANONICAL_BL": "BL002", "BL_DATE": "2026-05-11",
         "COT_DATE": "2026-06-21", "FULL_CLEAR_DATE": "2026-06-26",
         "IS_FULL_CLEARED": True, "COTAGE_NO": "COT2", "SATA_NO": "SAT2",
         "SATA_DATE": "2026-06-25", "INVOICE_VALUE": 40, "CURRENCY": "EUR"},
    ])
    ctx = _ctx()
    out = FxTraceabilityStage().run(df, ctx)
    ledger = ctx.extras["fx_ledger"]
    assert len(ledger) == 1
    assert ledger.iloc[0]["BL_COUNT"] == 2
    assert ledger.iloc[0]["FX_PURCHASED_AMOUNT"] == 100  # not 200 through BL fan-out
    assert ledger.iloc[0]["FX_NTSW_RELEASED"] == 100
    assert ledger.iloc[0]["FX_TRACE_SCORE"] == 100
    assert out["FX_PURCHASED_AMOUNT"].tolist() == [100, 100]


def test_obligations_are_separate_not_one_boolean():
    ctx = _ctx()
    df = pd.DataFrame([{
        "CANONICAL_REG": "12345678", "CANONICAL_BL": "BL001", "BL_DATE": "2026-05-10",
        "FULL_CLEAR_DATE": "2026-06-25", "IS_FULL_CLEARED": True,
        "COTAGE_NO": "COT1", "SATA_NO": "SAT1", "INVOICE_VALUE": 100, "CURRENCY": "EUR"}])
    FxTraceabilityStage().run(df, ctx)
    r = ctx.extras["fx_ledger"].iloc[0]
    assert "تطبیق بانکی" in r["FX_CUSTOMS_DOC_OBLIGATION"]
    assert "مابه" in r["FX_DIFFERENTIAL_OBLIGATION"]
    assert "وثیقه" in r["FX_COLLATERAL_STATUS"]


def test_conformance_names_match_eventlog_and_order_uses_position():
    assert MANDATORY_BEFORE["FX Purchased"] == "FX Allocated"
    assert "Goods Shipped" not in MANDATORY_BEFORE  # no universal purchase-before-shipment rule
    events = pd.DataFrame([
        {"_CASE_KEY":"C1", "ACTIVITY_EN":"FX Purchased", "EVENTTIME":pd.Timestamp("2026-05-01"), "_SORTING":60},
        {"_CASE_KEY":"C1", "ACTIVITY_EN":"FX Allocated", "EVENTTIME":pd.Timestamp("2026-05-02"), "_SORTING":50},
        {"_CASE_KEY":"C1", "ACTIVITY_EN":"FX Commitment Created", "EVENTTIME":pd.Timestamp("2026-04-20"), "_SORTING":40},
    ])
    # قواعد پیش‌نیازی حالا از YAML ساخته می‌شوند، نه چهار سطر hardcode.
    # همین تست را قوی‌تر می‌کند: مسیر واقعی سنجیده می‌شود، نه یک زیرمجموعه.
    rules = ConformanceStage._precedence(get_rulebook(reload=True))
    assert rules["FX Purchased"] == "FX Allocated"
    result = ConformanceStage()._analyse_cases(events, rules)
    assert "FX Allocated پس از FX Purchased" in result["C1"]["out_of_order"]


def test_current_rule_snapshot_present():
    rb = get_rulebook(reload=True, as_of=date(2026, 9, 17))
    assert rb.get("fx_governance.regulatory_snapshot.obligation_separation_1405_03_04.status") == "verified"
    assert rb.get("fx_governance.regulatory_snapshot.temporary_extension_1405_05_07.extension_days_max") == 120
    assert rb.get("customs.legal_storage_period.article") == 24
    assert rb.get("fx_governance.regulatory_snapshot.emergency_deadline_overlay_1405_05_14.circular_no") == "65882/48174"
    assert rb.get("fx_governance.regulatory_snapshot.emergency_deadline_overlay_1405_05_14.automatic_apply") is False
    assert rb.get("customs.emergency_sata_waiver_1405.automatic_apply") is False
    assert rb.get("fx_governance.penalties.legal_claim") is False


def test_html_process_explorer_embeds_fx_traceability():
    from gsi.studio_core.html_export import build_dynamic_html
    df = pd.DataFrame({
        "KEY_MATERIAL": ["M1"], "CANONICAL_ORDER": ["O1"],
        "بحرانی (کوتاه)": ["ایمن"], "مقاومت (روز)": [20],
    })
    extras = {
        "fx_ledger": pd.DataFrame([{
            "KEY_REG": "12345678", "FX_MONEY_STAGE": "شاهد سوئیفت موجود",
            "FX_NTSW_BALANCE": 0, "FX_TRACE_SCORE": 100, "FX_ANOMALY_COUNT": 0,
        }]),
        "fx_anomalies": pd.DataFrame([{
            "KEY_REG": "12345678", "SEVERITY": "LOW", "ANOMALY": "demo"
        }]),
    }
    h = build_dynamic_html(df, "2026-09-17", selected_fields=list(df.columns),
                           process_extras=extras, max_rows=20)
    assert "رهگیری مالی-ارزی / FX Traceability" in h
    assert "12345678" in h
    assert "PROC.fx_ledger" in h

def _run_direct():
    ok = fail = 0
    for fn in [test_fx_ledger_is_reg_grain_and_no_fanout, test_obligations_are_separate_not_one_boolean, test_conformance_names_match_eventlog_and_order_uses_position, test_current_rule_snapshot_present, test_html_process_explorer_embeds_fx_traceability]:
        try:
            fn()
            ok += 1
            print(f"✅ {fn.__name__}")
        except Exception as ex:
            fail += 1
            print(f"❌ {fn.__name__} → {type(ex).__name__}: {ex}")
    print(f"نتیجه: {ok} موفق | {fail} ناموفق")
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(_run_direct())
