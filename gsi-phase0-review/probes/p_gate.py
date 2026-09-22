# -*- coding: utf-8 -*-
"""OP-05: chatbot latest-PR ordering + blocked-run leakage; schema-drift blindness;
   self-disabling row-preservation gate; _SOURCE_FILE provenance."""
import sys, json, os, hashlib
import pandas as pd
sys.path.insert(0, os.environ["PKG"])
from gsi.warehouse.store import Warehouse
from gsi.warehouse.business_dwh import build as build_dwh
from gsi.adapters.a60_finance import SapAdapter
from gsi.knowledge_desk.operational import _pr_semantic, _published_run
from gsi.warehouse.reliability import schema_drift_checks
res = {}
wh = Warehouse()

def sap_export(items):
    return pd.DataFrame([{ "Purchase Requisition":"1000000001","Item of requisition":i,
        "Material":m,"Changed On":d,"Release Date":d,"Name of Supplier":s,
        "po.Purchasing Document":"","po.Item":"","po.Purchase Requisition":"",
        "po.Item of requisition":"","po.Material":"","po.Last Changed on":"",
        "WorkFlow ID":"","WorkFlow Status":""} for i,m,d,s in items])

# PR items 2 and 10: item 10 is the business-latest (Changed On 2026-06-01)
r1 = sap_export([("00002","MAT-2","2026-01-01","SUPPLIER-OLD"),
                 ("00010","MAT-10","2026-06-01","SUPPLIER-NEW")])
out1 = SapAdapter().transform({"Data": r1})
with wh.run({"p":"r1"}) as rid1:
    build_dwh(wh, {"sap": out1}, rid1)
with wh.db() as c:
    c.execute("INSERT INTO wh_current(slot,run_id) VALUES('dwh',?) ON CONFLICT(slot) DO UPDATE SET run_id=excluded.run_id",(rid1,))
with wh.read_db() as c:
    sem = _pr_semantic(c, "1000000001", _published_run(c))
res["published_run_is_r1"] = True
res["chatbot_supplier_reported"] = sem["supplier"]
res["chatbot_release_date_reported"] = sem["release_date"]
res["business_latest_supplier"] = "SUPPLIER-NEW"
res["pr_items_seen"] = sem["pr_items"]

# now a BLOCKED run adds a brand-new PR that must never be visible
r2 = pd.concat([r1, sap_export([("00010","MAT-X","2026-09-01","SUPPLIER-BLOCKED")]).assign(
    **{"Purchase Requisition":"1000000777"})], ignore_index=True)
out2 = SapAdapter().transform({"Data": r2})
with wh.run({"p":"blocked"}) as rid2:
    build_dwh(wh, {"sap": out2}, rid2)   # pointer intentionally NOT moved
with wh.read_db() as c:
    run_now = _published_run(c)
    leaked = _pr_semantic(c, "1000000777", run_now)
res["pointer_still_r1"] = (run_now == rid1)
res["blocked_pr_visible_to_chatbot"] = leaked["pr_items"] > 0
res["blocked_pr_asof_label"] = leaked["run_id"] == rid1

# --- schema drift: upstream header removed, standardized frame unchanged? ---
r3 = r1.drop(columns=["Name of Supplier"])
out3 = SapAdapter().transform({"Data": r3})
res["supplier_column_still_present"] = "SAP_SUPPLIER_NAME" in out3["pr_items"].columns
res["supplier_values_after_header_loss"] = sorted(set(out3["pr_items"]["SAP_SUPPLIER_NAME"].astype(str)))
with wh.run({"p":"drift0"}) as rid3:
    base = schema_drift_checks(wh, {"sap": {"pr_items": out1["pr_items"]}}, rid3)
with wh.run({"p":"drift1"}) as rid4:
    after = schema_drift_checks(wh, {"sap": {"pr_items": out3["pr_items"]}}, rid4)
res["schema_drift_baseline"] = [(c.code, c.passed) for c in base]
res["schema_drift_after_upstream_header_removed"] = [(c.code, c.passed, c.detail.get("added"), c.detail.get("removed")) for c in after]

# --- self-disabling row-preservation gate ---
from gsi.warehouse.reliability import Check, BLOCK
def gate_checks(extras):
    checks = []
    ps = extras.get('process_evidence_summary', {}) or {}
    if ps:
        checks.append(Check('process/evidence','PROCESS_ROW_PRESERVATION',BLOCK,
                            bool(ps.get('row_preservation_ok')), {}))
    return checks
res["gate_when_stage_ran"]   = [(c.code, c.passed) for c in gate_checks({"process_evidence_summary": {"row_preservation_ok": False}})]
res["gate_when_stage_raised"] = [(c.code, c.passed) for c in gate_checks({})]

# --- _SOURCE_FILE provenance after archive round-trip ---
import inspect
from gsi.dataio import reader as rdr
src = inspect.getsource(rdr.read_source)
res["temp_name_is_file_id"] = "fid + os.path.splitext(f)[1]" in src
res["source_file_is_basename_of_temp"] = '_SOURCE_FILE"] = os.path.basename(f)' in inspect.getsource(rdr._read_targets)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
