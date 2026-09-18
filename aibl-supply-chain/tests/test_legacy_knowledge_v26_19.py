# -*- coding: utf-8 -*-
"""V26.19 — انتقال دانش نسل قدیم به مدل versioned و fail-closed."""
from __future__ import annotations
from datetime import date
import os, sys
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gsi.knowledge.legacy import can_auto_enforce, load_legacy_catalog
from gsi.rulebook import get_rulebook
from gsi.stages.base import PipelineContext, discover
from gsi.stages.s55_fx_traceability import FxTraceabilityStage
from gsi.stages.s56_money_flow_control import MoneyFlowControlStage
from gsi.stages.s57_legacy_knowledge import LegacyKnowledgeTransferStage

PASS=[]; FAIL=[]
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f" → {detail}" if detail else ""))


def _ctx_and_df(with_bl=False, note=""):
    reg="L-100"
    sources={
      "fx_transaction":{"main":pd.DataFrame([{
        "KEY_REG":reg,"KEY_ORDER":"","KEY_BL":"",
        "FX_AMOUNT":100,"FX_RIAL_VALUE":10000,"FX_RATE":100,
        "FX_EUR_VALUE":100,"FX_CURRENCY":"EUR","FX_BUY_DATE":"2026-08-01",
        "FX_BENEFICIARY":"SUP","FX_BANK":"BANK","FX_EXCHANGE":"EX","FX_STATUS":"done",
        # مقصد متفاوت است ولی شواهد conversion عمداً ناقص است
        "FX_PAID_AMOUNT":400,"FX_PAID_CURRENCY":"CNY","FX_PAID_RATE_RIAL":0,
        "FX_CONVERSION_RATE":0,"FX_CONVERSION_FEE_RIAL":0,
        "FX_AUTH_REF":"","FX_REALLOC_REASON":""}])},
      "ntsw":{
        "commitment":pd.DataFrame([{"KEY_REG":reg,"NTSW_INITIAL_COMMIT":100,"NTSW_BALANCE":100,
          "NTSW_COMMIT_DATE":"2026-07-05","NTSW_DEADLINE":"2026-12-30",
          "NTSW_CURRENCY":"EUR","NTSW_RELEASE_STATUS":"رفع تعهد نشده"}]),
        "allocation":pd.DataFrame([{"KEY_REG":reg,"NTSW_REQ_AMOUNT":100,"NTSW_REQ_CURRENCY":"EUR",
          "NTSW_ALLOC_DATE":"2026-07-20","NTSW_ALLOCATED":True,"NTSW_ALLOC_STATUS":"تخصیص یافته",
          "NTSW_REQ_TYPE":"DIRECT","NTSW_ALLOC_PROCESS":"تخصیص","NTSW_FX_SOURCE":"مرکز مبادله"}])},
    }
    df=pd.DataFrame([{
      "CANONICAL_REG":reg,"CANONICAL_ORDER":"O1","CANONICAL_BL":"B1" if with_bl else "",
      "BL_DATE":"2026-08-10" if with_bl else "","ARRIVAL_DATE":"","DISCHARGE_DATE":"",
      "COT_DATE":"","FULL_CLEAR_DATE":"","IS_FULL_CLEARED":False,"COTAGE_NO":"","SATA_NO":"",
      "INVOICE_VALUE":100,"CURRENCY":"EUR","SEGMENT":"تولیدی","STATUS_NOTE":note,
    }])
    ctx=PipelineContext(rb=get_rulebook(reload=True,as_of=date(2026,9,17)),today=date(2026,9,17),sources=sources)
    out=FxTraceabilityStage().run(df,ctx)
    out=MoneyFlowControlStage().run(out,ctx)
    out=LegacyKnowledgeTransferStage().run(out,ctx)
    return out,ctx


def test_catalog_and_guard():
    print("\n── کاتالوگ و گارد حاکمیتی ──")
    rb=get_rulebook(reload=True,as_of=date(2026,9,17))
    cat=load_legacy_catalog(rb)
    check("بسته legacy_knowledge بارگذاری شده", "legacy_knowledge" in rb.packs)
    check("کاتالوگ حداقل 15 دانش دارد", len(cat.items)>=15, str(len(cat.items)))
    hist=cat.get("HIST_ABC_CLOCK_MODEL")
    check("مدل A/B/C تاریخی است نه binding", hist is not None and hist.binding is False)
    check("Legacy حتی با دانش تاریخی auto enforce نمی‌شود", hist is not None and can_auto_enforce(hist) is False)
    check("Payment without BL به Unallocated Balance ترجمه شده",
          cat.get("LEGACY_PAYMENT_WITHOUT_BL") is not None and "Unallocated" in cat.get("LEGACY_PAYMENT_WITHOUT_BL").description)


def test_runtime_signals():
    print("\n── Signal پرونده و Evidence ──")
    out,ctx=_ctx_and_df(with_bl=False,note="کسر تخلیه در اظهارنامه بررسی شود")
    row=out.iloc[0]
    check("Payment بدون BL سیگنال می‌شود", row["FX_PAYMENT_WITHOUT_BL_SIGNAL"]=="UNALLOCATED_PAYMENT_CANDIDATE", str(row["FX_PAYMENT_WITHOUT_BL_SIGNAL"]))
    check("کسر تخلیه به عنوان Root-cause candidate ظاهر می‌شود", "کسر تخلیه" in str(row["FX_ROOT_CAUSE_HINTS"]), str(row["FX_ROOT_CAUSE_HINTS"]))
    check("شواهد کسر تخلیه پیشنهاد می‌شود", "قبض انبار" in str(row["FX_EVIDENCE_REQUIREMENTS"]), str(row["FX_EVIDENCE_REQUIREMENTS"]))
    check("شکاف نرخ Cross-Currency جعل P&L نمی‌کند", "Cross Rate" in str(row["FX_RATE_SEMANTIC_GAPS"]) or "تبدیل" in str(row["FX_RATE_SEMANTIC_GAPS"]), str(row["FX_RATE_SEMANTIC_GAPS"]))
    check("گارد legacy روی پرونده فعال است", row["FX_LEGACY_RULE_GUARD"]=="NO_AUTO_ENFORCEMENT")
    sig=ctx.extras["legacy_case_signals"]
    check("Signal table provenance دارد", not sig.empty and {"SOURCE_ID","SOURCE_LOCATION","AUTO_ENFORCE"} <= set(sig.columns))
    check("هیچ Signal legacy قابل enforce خودکار نیست", not sig.empty and not sig["AUTO_ENFORCE"].astype(bool).any())


def test_stage_and_rate_semantics():
    print("\n── معماری و semantics نرخ ──")
    names=[s.name for s in discover()]
    check("Stage انتقال دانش کشف می‌شود", "legacy_knowledge_transfer" in names)
    check("Stage بعد از Money Flow و قبل از Narrate است",
          names.index("money_flow_control") < names.index("legacy_knowledge_transfer") < names.index("narrate"), str(names))
    _,ctx=_ctx_and_df(with_bl=True)
    rates=ctx.extras["legacy_rate_semantics"]
    check("نرخ خرید، نرخ پرداخت و Cross Rate مستقل‌اند",
          {"FX_PURCHASE_RATE","SUPPLIER_SETTLEMENT_RATE","CROSS_RATE"} <= set(rates.get("code",[])))
    legacy=rates[rates["code"]=="LEGACY_REFERENCE_NORMALIZATION_RATE"].iloc[0]
    check("نرخ ثابت قدیمی برای P&L ممنوع است", "P&L" in str(legacy.get("forbidden_use")))


if __name__=="__main__":
    print("="*78); print("GSI V26.19 — Legacy Knowledge Transfer"); print("="*78)
    test_catalog_and_guard(); test_runtime_signals(); test_stage_and_rate_semantics()
    print("\n"+"="*78); print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL: print("ناموفق: "+" ، ".join(FAIL))
    print("="*78); sys.exit(1 if FAIL else 0)
