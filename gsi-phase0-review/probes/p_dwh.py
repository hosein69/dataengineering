# -*- coding: utf-8 -*-
"""OP-02: what dwh_relation actually records; evidence_count across runs;
   registration hub cross-product; blocked-run mutation of fact_source_row."""
import sys, json, os
import pandas as pd
sys.path.insert(0, os.environ["PKG"])
from gsi.warehouse.store import Warehouse
from gsi.warehouse.business_dwh import build as build_dwh

res = {}
wh = Warehouse()

# --- moghavemat frames exactly as the adapter emits them ---
main = pd.DataFrame([{ "KEY_ORDER": "O1", "MOGH_KEY_PR": "1000000001",
                       "MOGH_MATERIAL": "M-FIRST", "MOGH_MATERIALS_ALL": "M-FIRST، M-SECOND",
                       "MOGH_PI_VALUE_SUM": 100.0, "MOGH_CURRENCY": "EUR"}])
lines = pd.DataFrame([
    {"KEY_ORDER": "O1", "KEY_MATERIAL": "M-FIRST",  "KEY_PR": "1000000001", "MOGH_PR_ITEM": "10"},
    {"KEY_ORDER": "O1", "KEY_MATERIAL": "M-SECOND", "KEY_PR": "1000000002", "MOGH_PR_ITEM": "20"},
])
srcs = {"moghavemat": {"main": main, "lines": lines}}

with wh.run({"probe": "r1"}) as rid1:
    c1 = build_dwh(wh, srcs, rid1)
with wh.db() as c:
    rels = c.execute("SELECT left_type,left_key,right_type,right_key,frame,evidence_count FROM dwh_relation ORDER BY 1,2,3,4,5").fetchall()
res["relations_after_run1"] = [list(r) for r in rels]
res["cross_pair_PR1_to_M_SECOND"] = any(
    r[0:4] == ("PR", "1000000001", "MATERIAL", "M-SECOND") or r[0:4] == ("MATERIAL", "M-SECOND", "PR", "1000000001") for r in rels)
res["any_relation_from_main_frame"] = any(r[4] == "main" for r in rels)

# --- identical second run: does evidence_count inflate? ---
with wh.run({"probe": "r2"}) as rid2:
    build_dwh(wh, srcs, rid2)
with wh.db() as c:
    res["evidence_count_after_identical_rerun"] = dict(
        c.execute("SELECT left_type||'-'||left_key||'->'||right_type||'-'||right_key||'@'||frame, evidence_count FROM dwh_relation").fetchall())
    res["source_rows_table_count"] = c.execute("SELECT count(*) FROM dwh_fact_source_row").fetchone()[0]
res["counted_source_rows_per_run"] = c1["source_rows"]

# --- registration hub: 2 REG + 2 ORDER on one REG_FILE ---
il = pd.DataFrame([
    {"KEY_REG_FILE": "900000001", "KEY_REG": "88000001", "KEY_ORDER": ""},
    {"KEY_REG_FILE": "900000001", "KEY_REG": "88000002", "KEY_ORDER": ""},
    {"KEY_REG_FILE": "900000001", "KEY_REG": "",         "KEY_ORDER": "ORD-A"},
    {"KEY_REG_FILE": "900000001", "KEY_REG": "",         "KEY_ORDER": "ORD-B"},
])
with wh.run({"probe": "hub"}) as rid3:
    build_dwh(wh, {"ntsw": {"import_license": il}}, rid3)
with wh.db() as c:
    hub = c.execute("SELECT reg_file_key,reg_key,order_key FROM dwh_registration_hub ORDER BY 2,3").fetchall()
res["hub_rows_for_1_regfile_2reg_2order"] = [list(x) for x in hub]

# --- F002: does a later (unpublished) run move last_seen_run of unchanged rows? ---
fx1 = pd.DataFrame([{"KEY_REG": "88000001", "FX_AMOUNT": 100, "FX_CURRENCY": "EUR"}])
with wh.run({"probe": "pub"}) as pub_rid:
    build_dwh(wh, {"fx_transaction": {"main": fx1}}, pub_rid)
with wh.db() as c:
    c.execute("INSERT INTO wh_current(slot,run_id) VALUES('dwh',?) ON CONFLICT(slot) DO UPDATE SET run_id=excluded.run_id", (pub_rid,))
with wh.run({"probe": "blocked"}) as bad_rid:
    build_dwh(wh, {"fx_transaction": {"main": fx1}}, bad_rid)   # gate would block, but rows already written
with wh.db() as c:
    res["fx_rows_visible_to_published_run"] = c.execute(
        "SELECT count(*) FROM dwh_fact_source_row WHERE source='fx_transaction' AND last_seen_run=?", (pub_rid,)).fetchone()[0]
    res["fx_rows_now_owned_by_blocked_run"] = c.execute(
        "SELECT count(*) FROM dwh_fact_source_row WHERE source='fx_transaction' AND last_seen_run=?", (bad_rid,)).fetchone()[0]
print(json.dumps(res, ensure_ascii=False, indent=1))
