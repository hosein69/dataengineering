# -*- coding: utf-8 -*-
"""V26.18 — Money Flow Control Tower regression tests."""
from __future__ import annotations
from datetime import date
import os, sys
import pandas as pd

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gsi.rulebook import get_rulebook
from gsi.stages.base import PipelineContext
from gsi.stages.s55_fx_traceability import FxTraceabilityStage
from gsi.stages.s56_money_flow_control import MoneyFlowControlStage

PASS=[]; FAIL=[]
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


def _run(auth_ref=""):
    reg="11111111"; other="22222222"
    sources={
      "fx_transaction":{"main":pd.DataFrame([{
        "KEY_REG":reg,"KEY_ORDER":"O2","KEY_BL":"",
        "FX_AMOUNT":100,"FX_RIAL_VALUE":10000,"FX_RATE":100,
        "FX_EUR_VALUE":100,"FX_CURRENCY":"EUR","FX_BUY_DATE":"2026-08-01",
        "FX_BENEFICIARY":"SUP","FX_BANK":"BANK","FX_EXCHANGE":"EX","FX_STATUS":"done",
        "FX_PAID_AMOUNT":400,"FX_PAID_CURRENCY":"CNY","FX_PAID_RATE_RIAL":30,
        "FX_CONVERSION_RATE":4,"FX_CONVERSION_FEE_RIAL":100,
        "FX_AUTH_REF":auth_ref,"FX_REALLOC_REASON":"شرایط بحرانی"}])},
      "credit":{"main":pd.DataFrame([{
        "KEY_REG":reg,"CRD_FUND_DATE":"2026-08-02","CRD_SWIFT_DATE":"2026-08-03",
        "CRD_RIAL_AMOUNT":10000,"CRD_EUR_AMOUNT":100,"CRD_LAST_STATUS":"sent",
        "CRD_LC_NO":"LC1","CRD_PROFORMA_VALUE":100,"CRD_PREPAYMENT":0,"CRD_REMAINING":0,
        "CRD_REG_DATE":"2026-07-01","CRD_CURRENCY":"CNY"}])},
      "ntsw":{
        "commitment":pd.DataFrame([{"KEY_REG":reg,"NTSW_INITIAL_COMMIT":100,"NTSW_BALANCE":100,
          "NTSW_COMMIT_DATE":"2026-07-05","NTSW_DEADLINE":"2026-09-10",
          "NTSW_CURRENCY":"EUR","NTSW_RELEASE_STATUS":"رفع تعهد نشده"}]),
        "allocation":pd.DataFrame([{"KEY_REG":reg,"NTSW_REQ_AMOUNT":100,"NTSW_REQ_CURRENCY":"EUR",
          "NTSW_ALLOC_DATE":"2026-07-20","NTSW_ALLOCATED":True,"NTSW_ALLOC_STATUS":"تخصیص یافته",
          "NTSW_REQ_TYPE":"DIRECT","NTSW_ALLOC_PROCESS":"تخصیص","NTSW_FX_SOURCE":"مرکز مبادله"}])},
      "ilappend":{"main":pd.DataFrame([{"KEY_REG":reg,"IL_REG_DATE":"2026-07-01"}])},
    }
    df=pd.DataFrame([
      {"CANONICAL_REG":reg,"CANONICAL_ORDER":"O1","CANONICAL_BL":"B1","BL_DATE":"2026-08-10",
       "ARRIVAL_DATE":"2026-08-25","DISCHARGE_DATE":"2026-08-26","COT_DATE":"2026-09-01",
       "FULL_CLEAR_DATE":"","IS_FULL_CLEARED":False,"COTAGE_NO":"C1","SATA_NO":"S1","SATA_DATE":"2026-09-02",
       "INVOICE_VALUE":100,"CURRENCY":"CNY","SEGMENT":"تولیدی"},
      {"CANONICAL_REG":other,"CANONICAL_ORDER":"O2","CANONICAL_BL":"B2","BL_DATE":"2026-08-11",
       "ARRIVAL_DATE":"","DISCHARGE_DATE":"","COT_DATE":"","FULL_CLEAR_DATE":"",
       "IS_FULL_CLEARED":False,"COTAGE_NO":"","SATA_NO":"","INVOICE_VALUE":50,"CURRENCY":"EUR","SEGMENT":"تولیدی"},
    ])
    ctx=PipelineContext(rb=get_rulebook(reload=True, as_of=date(2026,9,17)), today=date(2026,9,17), sources=sources)
    df=FxTraceabilityStage().run(df,ctx)
    out=MoneyFlowControlStage().run(df,ctx)
    return out,ctx


def test_rate_bridge():
    print("\n── پل نرخ و تبدیل ──")
    _,ctx=_run()
    b=ctx.extras["fx_rate_bridge"]
    r=b.iloc[0]
    check("تبدیل EUR→CNY اندازه‌گیری شده", r["STATUS"]=="CROSS_CURRENCY_MEASURED", str(r["STATUS"]))
    check("اثر ریالی تبدیل ۲۱۰۰ است", abs(float(r["IMPACT_RIAL"])-2100)<0.001, str(r["IMPACT_RIAL"]))
    c=ctx.extras["fx_control_summary"]
    x=c[c["KEY_REG"]=="11111111"].iloc[0]
    check("اثر تبدیل به پرونده تجمیع شده", abs(float(x["FX_CONVERSION_IMPACT_RIAL"])-2100)<0.001)


def test_reallocation():
    print("\n── جابه‌جایی پرونده ──")
    _,ctx=_run()
    r=ctx.extras["fx_reallocations"]
    check("مغایرت REG مالی با مالک O2 کشف شد", ((r["FROM_REG"]=="11111111")&(r["TO_REG"]=="22222222")).any())
    check("بدون شاهد مجوز UNEXPLAINED است", (r["STATUS"]=="UNEXPLAINED").any())
    _,ctx2=_run("AUTH-77")
    r2=ctx2.extras["fx_reallocations"]
    check("با شماره مجوز AUTHORIZED است", len(r2)>0 and (r2["STATUS"]=="AUTHORIZED").all())


def test_stage_timeline_and_deadline():
    print("\n── مراحل و Deadline ──")
    _,ctx=_run()
    t=ctx.extras["fx_stage_timeline"]
    t=t[t["KEY_REG"]=="11111111"]
    check("یازده مرحله پرونده ساخته شده", len(t)==11, str(len(t)))
    check("مرحله رفع تعهد OVERDUE است", t.loc[t["STAGE_CODE"]=="SETTLEMENT","STATUS"].iloc[0]=="OVERDUE")
    check("روز باقی‌مانده NTSW منفی ۷ است", int(t.loc[t["STAGE_CODE"]=="SETTLEMENT","DAYS_REMAINING"].iloc[0])==-7)
    c=ctx.extras["fx_control_summary"]
    x=c[c["KEY_REG"]=="11111111"].iloc[0]
    check("مبنای مهلت NTSW شفاف است", "NTSW" in str(x["FX_DEADLINE_BASIS"]), str(x["FX_DEADLINE_BASIS"]))
    check("ریسک به دلیل جابه‌جایی+Deadline بالا است", x["FX_CONTROL_RISK_BAND"] in {"HIGH","CRITICAL"}, str(x["FX_CONTROL_RISK_SCORE"]))


def test_intelligence_registry():
    print("\n── منابع Field Intelligence ──")
    rb=get_rulebook(reload=True, as_of=date(2026,9,17))
    src=rb.get("intelligence_sources.telegram_sources",[]) or []
    check("پنج منبع تلگرامی ثبت شده", len(src)==5, str(len(src)))
    check("Field Signal اجازه enforce خودکار ندارد",
          rb.get("intelligence_sources.trust_model.binding_levels",[])[-1]["can_auto_enforce"] is False)


if __name__=="__main__":
    print("="*78); print("GSI V26.18 — Money Flow Control Tower"); print("="*78)
    test_rate_bridge(); test_reallocation(); test_stage_timeline_and_deadline(); test_intelligence_registry()
    print("\n"+"="*78); print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL: print("ناموفق: "+" ، ".join(FAIL))
    print("="*78); sys.exit(1 if FAIL else 0)
