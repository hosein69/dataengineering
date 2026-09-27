"""Financial review candidates keep missing, currency and grain boundaries."""
from datetime import date

import pandas as pd

from gsi.rulebook import get_rulebook
from gsi.stages.base import PipelineContext
from gsi.stages.s55_fx_traceability import _credit_amounts
from gsi.stages.s56_money_flow_control import MoneyFlowControlStage


def test_unkeyed_credit_snapshots_are_not_summed_or_zeroed():
    assert _credit_amounts(None)["CRD_PREPAYMENT"] is None
    repeated = pd.DataFrame({"CRD_CURRENCY": ["EUR", "EUR"],
                             "CRD_LC_NO": ["", ""], "CRD_PREPAYMENT": [50, 50]})
    assert _credit_amounts(repeated)["CRD_PREPAYMENT"] is None
    explicit = pd.DataFrame({"CRD_CURRENCY": ["EUR"], "CRD_LC_NO": ["LC1"],
                             "CRD_PREPAYMENT": [0]})
    assert _credit_amounts(explicit)["CRD_PREPAYMENT"] == 0


def test_conversion_requires_explicit_fee_and_has_physical_lineage():
    stage = MoneyFlowControlStage()
    ctx = PipelineContext(rb=get_rulebook(reload=True, as_of=date(2026, 9, 17)),
                          today=date(2026, 9, 17), sources={"fx_transaction": {"main": pd.DataFrame([{
                              "KEY_REG": "1", "FX_AMOUNT": 100, "FX_RIAL_VALUE": 10000,
                              "FX_CURRENCY": "EUR", "FX_PAID_AMOUNT": 400,
                              "FX_PAID_CURRENCY": "CNY", "FX_PAID_RATE_RIAL": 30,
                              "FX_CONVERSION_RATE": 4, "FX_CONVERSION_FEE_RIAL": None,
                              "_SOURCE_FILE_ID": "F1", "_SOURCE_SHEET": "S1", "_SOURCE_ROW": 8,
                          }])}})
    gap = stage._build_rate_bridge(ctx).iloc[0]
    assert gap.STATUS == "CROSS_CURRENCY_EVIDENCE_GAP"
    assert pd.isna(gap.IMPACT_RIAL) and gap.SOURCE_ROW == "8"
    ctx.sources["fx_transaction"]["main"].loc[0, "FX_CONVERSION_FEE_RIAL"] = 0
    measured = stage._build_rate_bridge(ctx).iloc[0]
    assert measured.STATUS == "CROSS_CURRENCY_MEASURED"
    assert measured.IMPACT_RIAL == 2000


def test_decision_amount_is_non_additive_and_needs_both_stages():
    stage = MoneyFlowControlStage()
    ctx = PipelineContext(rb=get_rulebook(reload=True, as_of=date(2026, 9, 17)),
                          today=date(2026, 9, 17))
    money = pd.DataFrame([
        dict(KEY_REG="1", CURRENCY="EUR", EVENT_CODE="ALLOCATION", AMOUNT=100,
             SOURCE="ntsw/allocation", REFERENCE="request:1"),
        dict(KEY_REG="1", CURRENCY="EUR", EVENT_CODE="FX_PURCHASE", AMOUNT=40,
             SOURCE="fx_transaction", REFERENCE="fx:F1/S1/8"),
        dict(KEY_REG="1", CURRENCY="CNY", EVENT_CODE="SUPPLIER_PAYMENT", AMOUNT=400,
             SOURCE="fx_transaction", REFERENCE="fx:F1/S1/8"),
    ])
    recon = stage._build_money_reconciliation(money)
    assert recon.loc[recon.CURRENCY.eq("EUR"), "ALLOCATED_MINUS_PURCHASED"].iloc[0] == 60
    timeline = pd.DataFrame([dict(KEY_REG="1", STAGE_CODE="ALLOCATION", EVENT_DATE="2026-09-01")])
    decisions = stage._build_financial_decisions(money, recon, timeline, pd.DataFrame(), ctx)
    assert len(decisions) == 1
    row = decisions.iloc[0]
    assert row.OBSERVED_GAP_AMOUNT == 60 and row.WAIT_DAYS == 16
    assert row.ADDITIVITY == "NON_ADDITIVE" and row.DECISION_STATUS == "INVESTIGATE_ONLY"
    assert "request:1" in row.EVIDENCE and "fx:F1/S1/8" in row.EVIDENCE


def test_money_ledger_keeps_explicit_zero_and_source_row():
    stage = MoneyFlowControlStage()
    credit = pd.DataFrame([{"KEY_REG": "1", "CRD_PROFORMA_VALUE": 0,
                            "CRD_CURRENCY": "EUR", "_SOURCE_FILE_ID": "F2",
                            "_SOURCE_SHEET": "PURCREDIT", "_SOURCE_ROW": 7}])
    ctx = PipelineContext(rb=get_rulebook(reload=True, as_of=date(2026, 9, 17)),
                          today=date(2026, 9, 17), sources={"credit": {"main": credit}})
    money = stage._build_money_ledger(pd.DataFrame(), ctx)
    row = money.loc[money.EVENT_CODE.eq("REGISTRATION_VALUE")].iloc[0]
    assert row.AMOUNT == 0
    assert row.REFERENCE == "credit:F2/PURCREDIT/7"
