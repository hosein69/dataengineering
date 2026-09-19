# -*- coding: utf-8 -*-
"""SQLite warehouse + HTML-only delivery regression tests for V26.17."""
from __future__ import annotations
import os, sys, tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
os.environ["AIBL_SQLITE_LOG"]="0"
import pandas as pd
from aibl.warehouse.sqlite_store import Warehouse
from aibl.studio_core.html_export import build_dynamic_html

PASS=[]; FAIL=[]
def check(n,c,d=""):
    (PASS if c else FAIL).append(n); print(("✅" if c else "❌"),n,("→ "+d if d else ""))

def frames(owner="E1"):
    main=pd.DataFrame({
        "CASE_KEY":["C1","C2"],"CANONICAL_ORDER":["O1","O2"],"CANONICAL_BL":["B1","B2"],
        "KEY_MATERIAL":["M1","M2"],"ORG_DEPT":["D1","D2"],"CANONICAL_EXPERT":[owner,"E2"],
        "بحرانی (کوتاه)":["بحرانی","ایمن"],"مقاومت (روز)":[4.0,30.0],"INVOICE_VALUE":[1001,2002]
    })
    ev=pd.DataFrame({
        "_CASE_KEY":["C1","C1","C2","C2"],"ACTIVITY_EN":["register","ship","register","customs"],
        "ACTIVITY_FA":["ثبت","حمل","ثبت","ترخیص"],
        "EVENTTIME":pd.to_datetime(["2026-09-01","2026-09-05","2026-09-02","2026-09-12"]),
        "_SORTING":[1,2,1,2],"ORG_UNIT":["D1","D1","D2","D2"],"RESOURCE":[owner,owner,"E2","E2"]
    })
    cases=pd.DataFrame({
        "CASE_KEY":["C1","C2"],"FIRST_EVENT":["2026-09-01","2026-09-02"],"LAST_EVENT":["2026-09-05","2026-09-12"],
        "EVENT_COUNT":[2,2],"THROUGHPUT_DAYS":[4.0,10.0],"REWORK_COUNT":[0,0],
        "FIRST_ACTIVITY":["ثبت","ثبت"],"LAST_ACTIVITY":["حمل","ترخیص"],"VARIANT":["ثبت ← حمل","ثبت ← ترخیص"]
    })
    res=SimpleNamespace(df=main.copy(),main=main.copy(),to_resolve=main.iloc[0:0],excluded=main.iloc[0:0],extras={"eventlog":ev,"case_table":cases})
    return res

def run():
    tmp=Path(tempfile.mkdtemp(prefix="aibl_wh_")); wh=Warehouse(tmp/"aibl.sqlite3")
    rid0=wh.begin_run("2026-09-15",package_version="26.17.0")
    check("run از ابتدا ثبت می‌شود",wh.list_runs(5).iloc[0]["status"]=="RUNNING")
    r1=frames(); rid1=wh.persist_pipeline(r1,"2026-09-15",package_version="26.17.0",run_id=rid0,sources={"src":{"main":r1.main}})
    st=wh.stats(); check("snapshot موفق",st["runs"]==1); check("event log پایدار",st["events"]==4); check("transition دقیق",st["transitions"]==2)
    snap=wh.load_snapshot(rid1); check("snapshot از SQLite بازخوانی می‌شود",snap is not None and len(snap.main)==2 and "INVOICE_VALUE" in snap.main.columns)
    check("lineage سورس ذخیره می‌شود",len(wh.source_lineage(rid1))==1)
    bn=wh.process_bottlenecks(rid1,org_unit="D1"); check("گلوگاه با scope اداره",len(bn)==1 and bn.iloc[0]["از فعالیت"]=="ثبت")
    tl=wh.case_timeline("C1",rid1); check("timeline پرونده",list(tl["activity"])==["ثبت","حمل"])
    changes1=len(wh.case_changes("C1"))
    r2=frames(); rid2=wh.persist_pipeline(r2,"2026-09-16",package_version="26.17.0")
    check("eventهای تکراری duplicate نمی‌شوند",wh.stats()["events"]==4)
    check("snapshot بدون تغییر، state log اضافه نمی‌کند",len(wh.case_changes("C1"))==changes1)
    r3=frames("E9"); rid3=wh.persist_pipeline(r3,"2026-09-17",package_version="26.17.0")
    ch=wh.case_changes("C1"); check("تغییر مالک ثبت می‌شود",len(ch)==changes1+1 and "CANONICAL_EXPERT" in ch.iloc[0]["changed_fields_json"])
    changed_after_future=len(ch)
    # backfill تاریخ قدیمی نباید با state آینده مقایسه شود.
    wh.persist_pipeline(frames(),"2026-09-16",package_version="26.17.0")
    check("backfill با آینده مقایسه نمی‌شود",len(wh.case_changes("C1"))==changed_after_future)
    # KPI تاریخی مقاومت باید بر دانه متریال باشد، نه میانگین ردیف‌های fan-out.
    r4=frames(); r4.main=pd.concat([r4.main,r4.main.iloc[[0]]],ignore_index=True); r4.df=r4.main.copy()
    rid4=wh.persist_pipeline(r4,"2026-09-18",package_version="26.17.0")
    kt=wh.kpi_trend("avg_resistance"); kval=float(kt.loc[kt["run_id"]==rid4,"numeric_value"].iloc[0])
    check("KPI تاریخی مقاومت grain-safe است",abs(kval-17.0)<1e-9,str(kval))
    failed=wh.begin_run("2026-09-19",package_version="26.17.0"); wh.fail_run(failed,"2026-09-19","synthetic failure",package_version="26.17.0")
    check("اجرای ناموفق قابل ممیزی است",wh.stats()["failed_runs"]==1 and not wh.audit_entries(run_id=failed).empty)
    html=build_dynamic_html(r3.main,"2026-09-17",selected_fields=["KEY_MATERIAL","INVOICE_VALUE"],show_process=True,process_extras=r3.extras,lineage={"warehouse_run_id":rid3})
    check("HTML دارای lineage snapshot است",rid3 in html and "REPORT_META" in html)
    check("HTML تنها artifact و Excel داخل مرورگر", "downloadFilteredXlsx" in html and "styles.xml" in html)
    check("PDF از همان HTML", "function exportPdf(){window.print()}" in html)
    check("CASE_KEY برای process filter در payload می‌ماند", '"CASE_KEY"' in html)
    pr=wh.prune(keep_runs=1); check("retention snapshot",pr["deleted_runs"]==4 and wh.stats()["runs"]==1)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق"); return 1 if FAIL else 0

if __name__=="__main__": raise SystemExit(run())
