# -*- coding: utf-8 -*-
"""V29.6 — end-to-end money ledger and reconciliation."""
from datetime import date
import pandas as pd
from gsi.rulebook import get_rulebook
from gsi.stages.base import PipelineContext
from gsi.stages.s55_fx_traceability import FxTraceabilityStage
from gsi.stages.s56_money_flow_control import MoneyFlowControlStage


def _run(paid=True, balance=20):
    reg="12345678"
    fx={"KEY_REG":reg,"FX_AMOUNT":80,"FX_RIAL_VALUE":8000,"FX_RATE":100,"FX_EUR_VALUE":80,
        "FX_CURRENCY":"EUR","FX_BUY_DATE":"2026-08-01","FX_STATUS":"done",
        "FX_PAID_AMOUNT":80 if paid else None,"FX_PAID_CURRENCY":"EUR" if paid else "",
        "FX_RECEIPT_DATE":"2026-08-05" if paid else ""}
    sources={
      "fx_transaction":{"main":pd.DataFrame([fx])},
      "credit":{"main":pd.DataFrame([{"KEY_REG":reg,"CRD_REG_DATE":"2026-07-01",
        "CRD_PROFORMA_VALUE":100,"CRD_CURRENCY":"EUR","CRD_RIAL_AMOUNT":8000,
        "CRD_FUND_DATE":"2026-08-02","CRD_EUR_AMOUNT":80,"CRD_SWIFT_DATE":"2026-08-03",
        "CRD_PREPAYMENT":0,"CRD_REMAINING":0,"CRD_LAST_STATUS":"sent","CRD_LC_NO":"LC1"}])},
      "ntsw":{"allocation_rows":pd.DataFrame([
        {"KEY_REG":reg,"NTSW_REQUEST_KEY":"R1","NTSW_REQ_AMOUNT":100,"NTSW_REQ_CURRENCY":"EUR",
         "NTSW_REQ_DATE":"2026-07-10","NTSW_ALLOC_DATE":"2026-07-20","NTSW_REQUEST_STATE":"ALLOCATED","NTSW_ALLOC_STATUS":"تخصیص یافته"}]),
        "allocation":pd.DataFrame([{"KEY_REG":reg,"NTSW_REQ_AMOUNT":100,"NTSW_REQ_CURRENCY":"EUR",
         "NTSW_ALLOC_DATE":"2026-07-20","NTSW_ALLOCATED":True,"NTSW_ALLOCATED_AMOUNT":100,
         "NTSW_OPEN_REQUESTS":0,"NTSW_ALLOCATED_REQUESTS":1,"NTSW_ALLOC_REQUESTS":1}]),
        "commitment":pd.DataFrame([{"KEY_REG":reg,"NTSW_INITIAL_COMMIT":100,"NTSW_BALANCE":balance,
         "NTSW_COMMIT_DATE":"2026-08-10","NTSW_DEADLINE":"2026-10-01","NTSW_CURRENCY":"EUR",
         "NTSW_RELEASE_STATUS":"رفع تعهد نشده" if balance else "رفع تعهد شده"}])},
      "ilappend":{"main":pd.DataFrame([{"KEY_REG":reg,"IL_REG_DATE":"2026-07-01"}])},
    }
    df=pd.DataFrame([{"CANONICAL_REG":reg,"CANONICAL_ORDER":"O1","CANONICAL_BL":"B1",
        "BL_DATE":"2026-08-07","ARRIVAL_DATE":"2026-08-12","COT_DATE":"2026-08-15",
        "FULL_CLEAR_DATE":"2026-08-20","IS_FULL_CLEARED":True,"COTAGE_NO":"C1","SATA_NO":"S1"}])
    ctx=PipelineContext(rb=get_rulebook(reload=True,as_of=date(2026,9,21)),today=date(2026,9,21),sources=sources)
    out=MoneyFlowControlStage().run(FxTraceabilityStage().run(df,ctx),ctx)
    return out,ctx


def test_end_to_end_money_ledger_preserves_grain_and_unknown():
    _,ctx=_run(paid=False)
    led=ctx.extras["fx_money_ledger"]
    assert {"REGISTRATION_VALUE","ALLOCATION_REQUEST","ALLOCATION","FX_PURCHASE","BANK_FUNDING_IRR","SWIFT","COMMITMENT_INITIAL","COMMITMENT_RELEASED","COMMITMENT_BALANCE"}.issubset(set(led.EVENT_CODE))
    assert "SUPPLIER_PAYMENT" not in set(led.EVENT_CODE)
    rec=ctx.extras["fx_money_reconciliation"]
    eur=rec[rec.CURRENCY.eq("EUR")].iloc[0]
    assert eur.RECON_STATUS=="EVIDENCE_GAP"
    assert "SUPPLIER_PAID_AMOUNT" in eur.EVIDENCE_GAPS


def test_same_currency_reconciliation_and_obligation_equation():
    out,ctx=_run(paid=True,balance=20)
    eur=ctx.extras["fx_money_reconciliation"].query("CURRENCY == 'EUR'").iloc[0]
    assert eur.REQUESTED_AMOUNT==100
    assert eur.ALLOCATED_AMOUNT==100
    assert eur.PURCHASED_AMOUNT==80
    assert eur.SUPPLIER_PAID_AMOUNT==80
    assert eur.COMMITMENT_INITIAL==100 and eur.COMMITMENT_RELEASED==80 and eur.COMMITMENT_BALANCE==20
    assert abs(eur.OBLIGATION_INVARIANT_VARIANCE)<0.001
    assert eur.OBLIGATION_RECON_STATUS=="OK"
    assert eur.RECON_STATUS=="OPEN_AMOUNT_GAP"
    assert out.iloc[0].FX_MONEY_RECON_STATUS=="OPEN_AMOUNT_GAP"


def test_supplier_receipt_closes_swift_conversion_stage_evidence():
    _,ctx=_run(paid=True)
    t=ctx.extras["fx_stage_timeline"]
    x=t[t.STAGE_CODE.eq("SWIFT_CONVERSION")].iloc[0]
    assert x.STATUS=="DONE"
    assert "تایید وصول" in x.EVIDENCE
