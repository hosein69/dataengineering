# -*- coding: utf-8 -*-
"""RC: publication isolation through the REAL reader path, plus gate/stage checks."""
import sys, json, os
import pandas as pd
sys.path.insert(0, os.environ["PKG"])
from gsi.warehouse.store import Warehouse
from gsi.warehouse.business_dwh import build as build_dwh
from gsi.knowledge_desk.operational import _pr_semantic, _published_run, operational_search
from gsi.adapters.a60_finance import SapAdapter
from gsi.warehouse.reliability import validate_frame
res = {}
wh = Warehouse()

def sap(rows):
    return pd.DataFrame([{ "Purchase Requisition":pr,"Item of requisition":it,"Material":m,
        "Changed On":d,"Release Date":d,"Name of Supplier":s,
        "po.Purchasing Document":"","po.Item":"","po.Purchase Requisition":"",
        "po.Item of requisition":"","po.Material":"","po.Last Changed on":"",
        "WorkFlow ID":"","WorkFlow Status":""} for pr,it,m,d,s in rows])

r1 = sap([("1000000001","00002","M2","2026-01-01","SUPPLIER-OLD"),
          ("1000000001","00010","M10","2026-06-01","SUPPLIER-NEW")])
out1 = SapAdapter().transform({"Data": r1})
with wh.run({"p":"r1"}) as rid1:
    build_dwh(wh, {"sap": out1}, rid1)
with wh.db() as c:
    c.execute("INSERT INTO wh_current(slot,run_id) VALUES('dwh',?) ON CONFLICT(slot) DO UPDATE SET run_id=excluded.run_id",(rid1,))
with wh.read_db() as c:
    sem = _pr_semantic(c, "1000000001", _published_run(c))
res["published_supplier"] = sem["supplier"]          # expect SUPPLIER-NEW (date-based latest)
res["published_pr_items"] = sem["pr_items"]

# blocked run adds a brand new PR and REMOVES nothing
r2 = pd.concat([r1, sap([("1000000777","00010","MX","2026-09-01","SUPPLIER-BLOCKED")])], ignore_index=True)
out2 = SapAdapter().transform({"Data": r2})
with wh.run({"p":"blocked"}) as rid2:
    build_dwh(wh, {"sap": out2}, rid2)        # pointer deliberately NOT moved
with wh.read_db() as c:
    run_now = _published_run(c)
    leaked = _pr_semantic(c, "1000000777", run_now)
    still  = _pr_semantic(c, "1000000001", run_now)
res["pointer_still_r1"] = (run_now == rid1)
res["blocked_pr_visible"] = leaked["pr_items"] > 0
res["published_pr_survived_blocked_run"] = still["pr_items"]

# omission: a later published run drops PR 1000000001 entirely; does R1 history survive?
r3 = sap([("1000000002","00010","MZ","2026-07-01","S3")])
out3 = SapAdapter().transform({"Data": r3})
with wh.run({"p":"r3"}) as rid3:
    build_dwh(wh, {"sap": out3}, rid3)
with wh.db() as c:
    c.execute("UPDATE wh_current SET run_id=? WHERE slot='dwh'",(rid3,))
with wh.read_db() as c:
    gone = _pr_semantic(c, "1000000001", _published_run(c))
res["omitted_pr_after_new_publish"] = gone["pr_items"]
with wh.db() as c:
    res["snapshot_runs_retained"] = c.execute("SELECT count(*) FROM wh_semantic_snapshot").fetchone()[0]
    res["r1_snapshot_rows_intact"] = c.execute("SELECT count(*) FROM snap_dwh_fact_sap_pr_item WHERE snapshot_run=?",(rid1,)).fetchone()[0]
    try:
        c.execute("DELETE FROM snap_dwh_fact_sap_pr_item WHERE snapshot_run=?",(rid1,))
        res["snapshot_immutable"] = False
    except Exception as ex:
        res["snapshot_immutable"] = "Immutable" in str(ex)

# F025 gate re-check
il_blank = pd.DataFrame([{"KEY_REG_FILE":"","KEY_REG":"","KEY_ORDER":""} for _ in range(3)])
res["ilappend_all_blank_checks"] = {ch.code: (ch.severity, ch.passed) for ch in validate_frame("ilappend/main", il_blank)}
dup = pd.DataFrame([{"KEY_PR":"1000000001","SAP_PR_ITEM":"","A":1},{"KEY_PR":"1000000001","SAP_PR_ITEM":"","A":2}])
res["dup_blank_item_checks"] = {ch.code: (ch.severity, ch.passed) for ch in validate_frame("sap/pr_items", dup)}
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
