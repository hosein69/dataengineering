# -*- coding: utf-8 -*-
"""OP-04: Persian status classifiers, NTSW aggregation, process case identity."""
import sys, json, os
import pandas as pd
sys.path.insert(0, os.environ["PKG"])
from gsi.resolve.process_evidence import _state_from_text, _observations, _components, build_process_inventory
from gsi.adapters.a50_ntsw import NtswAdapter

res = {}
# 1) process-evidence status classifier
res["state_from_text"] = {t: _state_from_text(t) for t in
    ["مورد تایید", "تایید نشده", "تأیید نشده", "رد شده", "در گردش", "تایید شده",
     "مورد بررسی", "لغو شده", "بازگشت داده شد"]}

# 2) NTSW allocation state classifier + multi-currency summary + commitment dedupe
ad = NtswAdapter.__new__(NtswAdapter); ad.key, ad.prefix = "ntsw", "NTSW"
alloc_raw = pd.DataFrame([
  {"کد ثبت سفارش":"88000001","ردیف درخواست":"1","وضعیت":"تایید نشده","فرآیند فعلی":"",
   "مبلغ درخواست":"100","ارز درخواست":"USD","تاریخ ایجاد درخواست":"1405/01/01",
   "تاریخ تخصیص":"","محل تامین ارز":"","نرخ ارز":"","نوع درخواست":"A","شعبه":"","تاریخ تایید":"","شرکت":""},
  {"کد ثبت سفارش":"88000001","ردیف درخواست":"2","وضعیت":"تخصیص یافته","فرآیند فعلی":"",
   "مبلغ درخواست":"100","ارز درخواست":"EUR","تاریخ ایجاد درخواست":"1405/01/02",
   "تاریخ تخصیص":"1405/02/02","محل تامین ارز":"","نرخ ارز":"","نوع درخواست":"A","شعبه":"","تاریخ تایید":"","شرکت":""},
])
a = ad.std(alloc_raw, ad.ALLOCATION_MAP, exclude=["توضیح"])
from gsi.warehouse.numeric import number
from gsi.rulebook import get_rulebook
a["KEY_REG"] = alloc_raw["کد ثبت سفارش"]
a["NTSW_KEY_REG"] = a["KEY_REG"]
a["NTSW_REQ_AMOUNT"] = a["NTSW_REQ_AMOUNT"].map(number)
a["NTSW_FX_RATE_NUMERIC"] = a["NTSW_FX_RATE_NUMERIC"].map(number)
a["NTSW_REQ_CURRENCY"] = a["NTSW_REQ_CURRENCY"].map(get_rulebook().normalize_currency)
ledger = ad._allocation_request_ledger(a)
res["allocation_states"] = dict(zip(ledger["NTSW_REQ_ROW"], ledger["NTSW_REQUEST_STATE"]))
summary = ad._agg_allocation(ledger)
res["allocation_summary"] = summary[["KEY_REG","NTSW_ALLOCATED_AMOUNT","NTSW_REQ_AMOUNT","NTSW_REQ_CURRENCY"]].to_dict("records")

# commitment: same COMMIT_ROW repeated (one obligation, two snapshots)
c = pd.DataFrame([
  {"KEY_REG":"88000001","NTSW_COMMIT_ROW":"7","NTSW_CURRENCY":"EUR","NTSW_INITIAL_COMMIT":100.0,
   "NTSW_BALANCE":50.0,"NTSW_COMMIT_DATE":"1405/01/01","NTSW_DEADLINE":"1405/06/01",
   "NTSW_RELEASE_STATUS":"رفع تعهد نشده","NTSW_BRANCH":"","NTSW_COMPANY":""},
  {"KEY_REG":"88000001","NTSW_COMMIT_ROW":"7","NTSW_CURRENCY":"EUR","NTSW_INITIAL_COMMIT":100.0,
   "NTSW_BALANCE":50.0,"NTSW_COMMIT_DATE":"1405/01/01","NTSW_DEADLINE":"1405/06/01",
   "NTSW_RELEASE_STATUS":"رفع تعهد نشده","NTSW_BRANCH":"","NTSW_COMPANY":""},
])
agg = ad._agg_commitment(c)
res["commitment_same_row_twice"] = agg[["KEY_REG","NTSW_COMMIT_ROWS","NTSW_INITIAL_COMMIT","NTSW_BALANCE"]].to_dict("records")

# 3) process case identity: two unrelated ORDERs sharing one MATERIAL
def mk(orders_materials):
    return pd.DataFrame([{ "KEY_ORDER": o, "KEY_MATERIAL": m, "MOGH_STATUS": "",
                           "MOGH_PO_SENT_DATE": "" } for o, m in orders_materials])
srcA = {"moghavemat": {"lines": mk([("ORD-A","M1"), ("ORD-B","M1")])}}
obs, cases, matrix = build_process_inventory(srcA)
res["shared_material_cases"] = len(cases)
res["shared_material_order_count"] = cases["ORDER_COUNT"].tolist() if not cases.empty else []
idA = cases["PROCESS_CASE_ID"].tolist() if not cases.empty else []

# same two orders, plus a third unrelated observation joining the component later
srcB = {"moghavemat": {"lines": mk([("ORD-A","M1"), ("ORD-B","M1"), ("ORD-C","M1")])}}
_, casesB, _ = build_process_inventory(srcB)
res["case_id_run_a"] = idA
res["case_id_run_b"] = casesB["PROCESS_CASE_ID"].tolist() if not casesB.empty else []
res["case_id_stable_when_member_added"] = bool(set(idA) & set(res["case_id_run_b"]))

# 4) duplicate native rows collapse -> row preservation gate
dup = pd.DataFrame([{"KEY_ORDER":"ORD-A","KEY_MATERIAL":"M1"},{"KEY_ORDER":"ORD-A","KEY_MATERIAL":"M1"}])
o2 = _observations({"moghavemat": {"lines": dup}})
res["duplicate_native_rows_in"] = 2
res["source_observations_out"] = int((o2["STAGE_CODE"]=="SOURCE_OBSERVATION").sum())
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
