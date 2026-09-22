import sys, json, os
import pandas as pd
sys.path.insert(0, os.environ["PKG"])
from gsi.warehouse.store import Warehouse
from gsi.adapters.a60_finance import SapAdapter
from gsi.warehouse.reliability import schema_drift_checks
wh = Warehouse(); res={}
def exp(extra=True):
    row={"Purchase Requisition":"1000000001","Item of requisition":"00010","Material":"M",
         "Changed On":"2026-01-01","Release Date":"2026-01-01",
         "po.Purchasing Document":"","po.Item":"","po.Purchase Requisition":"",
         "po.Item of requisition":"","po.Material":"","po.Last Changed on":"",
         "WorkFlow ID":"","WorkFlow Status":""}
    if extra: row["Name of Supplier"]="ACME"
    return pd.DataFrame([row, {**row, "Item of requisition":"00020"}])
a=SapAdapter().transform({"Data":exp(True)})["pr_items"]
b=SapAdapter().transform({"Data":exp(False)})["pr_items"]
res["cols_identical"] = list(a.columns)==list(b.columns)
res["supplier_before"]=sorted(set(a["SAP_SUPPLIER_NAME"].astype(str)))
res["supplier_after"]=sorted(set(b["SAP_SUPPLIER_NAME"].astype(str)))
res["dtypes_identical"]={str(c):(str(a[c].dtype),str(b[c].dtype)) for c in a.columns if str(a[c].dtype)!=str(b[c].dtype)}
with wh.run({"p":"d0"}) as r0: base=schema_drift_checks(wh,{"sap":{"pr_items":a}},r0)
with wh.run({"p":"d1"}) as r1: after=schema_drift_checks(wh,{"sap":{"pr_items":b}},r1)
res["baseline"]=[(c.code,c.passed) for c in base]
res["after"]=[(c.code,c.severity,c.passed,c.detail.get("added"),c.detail.get("removed"),c.detail.get("dtype_changed")) for c in after]
print(json.dumps(res,ensure_ascii=False,indent=1,default=str))
