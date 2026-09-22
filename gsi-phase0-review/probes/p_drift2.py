import sys, json, os
import pandas as pd
sys.path.insert(0, os.environ["PKG"])
from gsi.warehouse.store import Warehouse
from gsi.adapters.a60_finance import SapAdapter
from gsi.warehouse.reliability import schema_drift_checks, schema_fingerprint
wh=Warehouse(); res={}
def exp(name):
    row={"Purchase Requisition":"1000000001","Item of requisition":"00010","Material":"M",
         "Changed On":"2026-01-01","Release Date":"2026-01-01",
         "po.Purchasing Document":"","po.Item":"","po.Purchase Requisition":"",
         "po.Item of requisition":"","po.Material":"","po.Last Changed on":"",
         "WorkFlow ID":"","WorkFlow Status":"", name:"ACME"}
    return pd.DataFrame([row])
# upstream renames "Name of Supplier" -> "Supplier Name (new)"
a=SapAdapter().transform({"Data":exp("Name of Supplier")})["pr_items"].astype(object)
b=SapAdapter().transform({"Data":exp("Supplier Name (new)")})["pr_items"].astype(object)
res["cols_identical"]=list(a.columns)==list(b.columns)
res["fingerprint_identical"]=schema_fingerprint(a)==schema_fingerprint(b)
res["supplier"]= [a["SAP_SUPPLIER_NAME"].iloc[0], b["SAP_SUPPLIER_NAME"].iloc[0]]
with wh.run({"p":"x0"}) as r0: schema_drift_checks(wh,{"sap":{"pr_items":a}},r0)
with wh.run({"p":"x1"}) as r1: after=schema_drift_checks(wh,{"sap":{"pr_items":b}},r1)
res["drift_after_rename"]=[(c.code,c.severity,c.passed,c.detail.get("added"),c.detail.get("removed"),c.detail.get("dtype_changed")) for c in after]
print(json.dumps(res,ensure_ascii=False,indent=1,default=str))
