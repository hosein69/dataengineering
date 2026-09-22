# -*- coding: utf-8 -*-
"""OP-03: SAP PR/PO grain. One PR item feeding two PO items; conflicting
   header-PR vs po.Purchase Requisition; workflow event identity; latest-PR pick."""
import sys, json, os
import pandas as pd
sys.path.insert(0, os.environ["PKG"])
from gsi.adapters.a60_finance import SapAdapter
from gsi.warehouse.store import Warehouse
from gsi.warehouse.business_dwh import build as build_dwh
from gsi.warehouse.reliability import validate_frame

res = {}
# One PR item (1000000001/10) split across two purchasing documents.
raw = pd.DataFrame([
 {"Purchase Requisition":"1000000001","Item of requisition":"00010","Material":"PRMAT",
  "Changed On":"2026-01-10","Release Date":"2026-01-05","Quantity requested":"100",
  "po.Purchasing Document":"4500000001","po.Item":"00010","po.Purchase Requisition":"1000000001",
  "po.Item of requisition":"00010","po.Material":"POMAT-A","po.Order Quantity":"60",
  "po.Last Changed on":"2026-02-01","WorkFlow ID":"WF-1","WorkFlow Status":"RELEASED"},
 {"Purchase Requisition":"1000000001","Item of requisition":"00010","Material":"PRMAT",
  "Changed On":"2026-01-10","Release Date":"2026-01-05","Quantity requested":"100",
  "po.Purchasing Document":"4500000002","po.Item":"00020","po.Purchase Requisition":"1000000009",
  "po.Item of requisition":"00090","po.Material":"POMAT-B","po.Order Quantity":"40",
  "po.Last Changed on":"2026-02-02","WorkFlow ID":"WF-1","WorkFlow Status":"RELEASED"},
 # second PR item, changed later than item 10 -> "latest per PR" must be item 20
 {"Purchase Requisition":"1000000001","Item of requisition":"00020","Material":"PRMAT2",
  "Changed On":"2026-03-15","Release Date":"2026-03-01","Quantity requested":"5",
  "po.Purchasing Document":"","po.Item":"","po.Purchase Requisition":"",
  "po.Item of requisition":"","po.Material":"","po.Order Quantity":"",
  "po.Last Changed on":"","WorkFlow ID":"WF-2","WorkFlow Status":"IN PROCESS"},
])
out = SapAdapter().transform({"Data": raw})
pr_items, po_items, wf, main = out["pr_items"], out["po_items"], out["workflow_rows"], out["main"]
res["counts"] = {k: len(v) for k, v in out.items()}
res["pr_item_10_row_count"] = int(((pr_items["KEY_PR"]=="1000000001") & (pr_items["SAP_PR_ITEM"]=="10")).sum())
res["pr_item_10_kept_po"] = pr_items.loc[pr_items["SAP_PR_ITEM"]=="10","SAP_PO_ITEM"].tolist()
res["main_latest_pr_item"] = main["SAP_PR_ITEM"].tolist()
res["po_items_header_pr_vs_po_pr"] = po_items[["KEY_PO","SAP_PO_ITEM","KEY_PR","SAP_PO_PR","KEY_MATERIAL","SAP_PO_MATERIAL","SAP_PO_PR_ITEM"]].to_dict("records")
res["workflow_rows_for_WF-1"] = int((wf["SAP_WORKFLOW_ID"]=="WF-1").sum())
res["workflow_seq"] = wf["SAP_WORKFLOW_SEQ"].tolist()

# what the DWH stores for PO items
wh = Warehouse()
with wh.run({"probe":"sap"}) as rid:
    build_dwh(wh, {"sap": out}, rid)
with wh.db() as c:
    res["dwh_fact_sap_po_item"] = [list(r) for r in c.execute(
        "SELECT po_key,po_item,pr_key,pr_item,material_key FROM dwh_fact_sap_po_item ORDER BY po_key").fetchall()]
    res["dwh_relation_PR_PO_and_PO_MATERIAL"] = [list(r) for r in c.execute(
        "SELECT left_type,left_key,right_type,right_key,frame FROM dwh_relation "
        "WHERE (left_type='PO' OR right_type='PO') ORDER BY 1,2,3,4").fetchall()]
    res["dwh_workflow_rows"] = c.execute("SELECT count(*) FROM dwh_fact_sap_workflow").fetchone()[0]

# re-ingest the SAME export with one extra row prepended -> SAP_SOURCE_ROW shifts
raw2 = pd.concat([raw.iloc[[2]], raw], ignore_index=True)
out2 = SapAdapter().transform({"Data": raw2})
with wh.run({"probe":"sap2"}) as rid2:
    build_dwh(wh, {"sap": out2}, rid2)
with wh.db() as c:
    res["dwh_workflow_rows_after_reorder"] = c.execute("SELECT count(*) FROM dwh_fact_sap_workflow").fetchone()[0]

# nullable-key loophole: duplicate (PR, blank item) must be caught by GRAIN_UNIQUENESS
dup = pd.DataFrame([{"KEY_PR":"1000000001","SAP_PR_ITEM":"","A":1},
                    {"KEY_PR":"1000000001","SAP_PR_ITEM":"","A":2}])
checks = {c.code: c.passed for c in validate_frame("sap/pr_items", dup)}
res["dup_blank_item_checks"] = checks

# ilappend contract: a frame where EVERY key is blank
il_blank = pd.DataFrame([{"KEY_REG_FILE":"","KEY_REG":"","KEY_ORDER":""} for _ in range(3)])
res["ilappend_all_blank_checks"] = {c.code: c.passed for c in validate_frame("ilappend/main", il_blank)}
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
