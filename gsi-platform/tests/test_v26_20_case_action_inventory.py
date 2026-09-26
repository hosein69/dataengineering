# -*- coding: utf-8 -*-
"""V26.20 — Supply Position, Allocation Queue, Case Actions, GSI identity."""
from __future__ import annotations
import os, sys, tempfile
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS, FAIL = [], []

# محیط synthetic پیش از اولین import از gsi تنظیم می‌شود؛ Settings در import cache می‌شود.
import importlib.util
_synth_path=os.path.join(ROOT,"tests","make_synthetic.py")
_spec=importlib.util.spec_from_file_location("v2620_synth_boot",_synth_path)
_mod=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_mod)
_SYNTH_ROOT=tempfile.mkdtemp(prefix="gsi_v2620_"); _D=_mod.build(_SYNTH_ROOT)
os.environ.update({
  "GSI_FOREIGN":_D["foreign"],"GSI_BLS":_D["bls"],"GSI_CLEARANCE":_D["clearance"],
  "GSI_HR":_D["hr"],"GSI_ESMAEILI":_D["esmaeili"],"GSI_GS_COMBINE":_D["gs_combine"],
  "GSI_MOHAMADI":_D["mohamadi"],"GSI_OUTPUT":_D["output"],"GSI_LOGS":_D["logs"],
  "GSI_TODAY":"2026-08-31"})
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


def test_unknown_not_zero():
    from gsi.engines.criticality import CriticalityEngine
    from gsi.rulebook import get_rulebook
    e = CriticalityEngine(get_rulebook(reload=True))
    r = e.evaluate({"STOCK_IKCO": 100, "STOCK_SAPCO": 50,
                    "SUPPLIER_QTY": "", "IN_TRANSIT_QTY": 20,
                    "IN_CUSTOMS_QTY": 10, "DAILY_NEED": 10})
    check("مقاومت انبار مستقل؛ مقاومت کل با فقدان موجودی سازنده نامشخص است",
          r.resistance_warehouse == 15.0 and r.resistance_total_supply is None and r.supplier_qty is None,
          f"band={r.band}, supplier={r.supplier_qty}, days={r.resistance_days}")
    check("با داده ناقص حداقل قابل اثبات حفظ می‌شود",
          abs((r.total_lower_bound or 0)-180) < 0.01 and r.coverage_pct == 80.0,
          f"lower={r.total_lower_bound}, coverage={r.coverage_pct}")

    r2 = e.evaluate({"STOCK_IKCO": 100, "STOCK_SAPCO": 50,
                     "SUPPLIER_QTY": 300, "IN_TRANSIT_QTY": 20,
                     "IN_CUSTOMS_QTY": 10, "DAILY_NEED": 10})
    check("فرمول پنج‌جزئی: Oracle + سه سبد کارشناسی",
          r2.total_confirmed == 480 and abs((r2.resistance_total_supply or 0)-48) < .01,
          f"total={r2.total_confirmed}, days={r2.resistance_days}")


def test_ntsw_request_ledger():
    from gsi.adapters.a50_ntsw import NtswAdapter
    a = pd.DataFrame({
        "کد ثبت سفارش": ["12345678","12345678","12345678"],
        "ردیف درخواست": ["1","1","2"],
        "وضعیت": ["آماده برای تخصیص","تخصیص یافته","در صف تخصیص"],
        "فرآیند فعلی": ["صف","تخصیص","صف"],
        "مبلغ درخواست": [100,100,50],
        "ارز درخواست": ["EUR","EUR","EUR"],
        "تاریخ ایجاد درخواست": ["1405/01/01","1405/01/01","1405/02/01"],
        "تاریخ تخصیص": ["","1405/01/20",""],
        "محل تامین ارز": ["مرکز مبادله"]*3,
        "نرخ ارز": [0,0,0], "نوع درخواست": ["عادی"]*3,
        "شعبه": ["الف"]*3, "تاریخ تایید": ["1405/01/02","1405/01/20","1405/02/02"],
        "شرکت": ["IKCO"]*3, "رتبه در صف": ["","",4],
    })
    out = NtswAdapter().transform({"Allocation": a})
    rows = out["allocation_rows"]; agg = out["allocation"].iloc[0]
    check("تاریخچه status یک درخواست دوباره‌شماری نمی‌شود", len(rows) == 2,
          f"request ledger rows={len(rows)}")
    check("مبلغ تخصیص و مبلغ باز صف جدا هستند",
          float(agg["NTSW_ALLOCATED_AMOUNT"]) == 100 and float(agg["NTSW_OPEN_QUEUE_AMOUNT"]) == 50,
          f"alloc={agg['NTSW_ALLOCATED_AMOUNT']} open={agg['NTSW_OPEN_QUEUE_AMOUNT']}")
    check("پرونده هم‌زمان تخصیص جزئی و صف باز را حفظ می‌کند",
          agg["NTSW_QUEUE_STATE"] == "PARTIAL_ALLOCATED" and int(agg["NTSW_QUEUE_RANK"]) == 4,
          f"{agg['NTSW_QUEUE_STATE']} rank={agg['NTSW_QUEUE_RANK']}")


def test_pipeline_actions_identity():
    from gsi.pipeline import Pipeline
    res=Pipeline().run(build_report=False)
    sp=res.extras.get("supply_position", pd.DataFrame())
    acts=res.extras.get("case_actions", pd.DataFrame())
    tl=res.extras.get("fx_stage_timeline", pd.DataFrame())
    check("Supply Position Ledger در Grain سفارش×متریال ساخته می‌شود", not sp.empty and "SUPPLY_POSITION_STATUS" in sp.columns, f"rows={len(sp)}")
    check("سه سبد کارشناسی و دو موجودی Oracle در lineage مستقل‌اند",
          all(c in res.df.columns for c in ["موجودی نزد سازنده","موجودی در راه","موجودی در گمرک","موجودی ایران خودرو","موجودی ساپکو"]),
          "five inventory components")
    check("Case Action Queue واقعی تولید می‌شود", not acts.empty and acts["HUMAN_REVIEW_REQUIRED"].all(), f"actions={len(acts)}")
    check("Timeline صف تخصیص را مرحله مستقل دارد", "ALLOCATION_QUEUE" in set(tl.get("STAGE_CODE",[])))
    check("ترخیص و ارائه سند بانکی دو Stage مستقل‌اند",
          {"CLEARANCE","BANK_DOCS","SETTLEMENT"}.issubset(set(tl.get("STAGE_CODE",[]))))

    from gsi.integrations.daily_email import build_case_action_html
    html=build_case_action_html(acts.iloc[0].to_dict())
    check("Draft Email با هویت GSI و هشدار بازبینی انسانی ساخته می‌شود",
          "GSI" in html and ("بازبینی" in html or "انسان" in html), "HTML draft")

    import gsi
    from gsi.factsheet import VERSION
    check("هویت فنی پکیج GSI و نسخه از 26.20 عقب نرفته",
          gsi.__version__ == VERSION and tuple(map(int, VERSION.split("."))) >= (26, 20, 0), VERSION)
    check("نام پکیج قدیمی aibl در import فعال وجود ندارد", not os.path.isdir(os.path.join(ROOT,"aibl")))


def test_contracts():
    from gsi.version import check_contracts
    issues=check_contracts()
    check("قراردادهای ماژولی V26.20+ سازگارند", not issues, " | ".join(x.message for x in issues))


if __name__ == "__main__":
    print("="*78); print("GSI V26.20 — Case Action / Allocation Queue / Supply Position"); print("="*78)
    test_unknown_not_zero(); test_ntsw_request_ledger(); test_pipeline_actions_identity(); test_contracts()
    print("\n"+"="*78); print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL: print("ناموفق: " + " ، ".join(FAIL))
    print("="*78); sys.exit(1 if FAIL else 0)
