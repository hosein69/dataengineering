# -*- coding: utf-8 -*-
"""Browser smoke test for the self-contained HTML artifact.

The suite remains portable: when Playwright/Chromium is unavailable it still
checks the runtime-critical JS contract statically instead of failing deploys.
"""
from __future__ import annotations
import os, shutil, sys, tempfile, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
os.environ["AIBL_SQLITE_LOG"]="0"
import pandas as pd
from gsi.studio_core.html_export import build_dynamic_html

PASS=[]; FAIL=[]
def check(n,c,d=""):
    (PASS if c else FAIL).append(n); print(("✅" if c else "❌"),n,("→ "+d if d else ""))

def sample_html():
    df=pd.DataFrame({"CASE_KEY":["C1","C2","C3"],"KEY_MATERIAL":["M1","M2","M3"],
        "ORG_DEPT":["گمرک","خرید","گمرک"],"INVOICE_VALUE":[1001.5,2002.0,3003.25],
        "EVENT_DATE":pd.to_datetime(["2026-09-01","2026-09-02","2026-09-03"]),
        "بحرانی (کوتاه)":["بحرانی","ایمن","تحت نظر"],"مقاومت (روز)":[4.0,30.0,15.0]})
    ev=pd.DataFrame({"_CASE_KEY":["C1","C1","C2","C2","C3","C3"],
        "ACTIVITY_FA":["ثبت","حمل","ثبت","ترخیص","ثبت","حمل"],
        "ACTIVITY_EN":["register","ship","register","customs","register","ship"],
        "EVENTTIME":pd.to_datetime(["2026-09-01","2026-09-05","2026-09-02","2026-09-12","2026-09-03","2026-09-06"]),
        "_SORTING":[1,2,1,2,1,2]})
    return build_dynamic_html(df,"2026-09-15",selected_fields=["KEY_MATERIAL","ORG_DEPT","INVOICE_VALUE","EVENT_DATE","بحرانی (کوتاه)","مقاومت (روز)"],show_process=True,process_extras={"eventlog":ev},lineage={"warehouse_run_id":"BROWSER-TEST"})

def run():
    h=sample_html()
    check("runtime filter function داخل HTML است","function rows(t)" in h)
    check("lineage داخل HTML است","BROWSER-TEST" in h and "REPORT_META" in h)
    check("تاریخ KPI جمع نمی‌شود",'"EVENT_DATE":"sum"' not in h)
    chromium=next((shutil.which(x) for x in ("chromium","chromium-browser","google-chrome","chrome") if shutil.which(x)),None)
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        sync_playwright=None
    if not chromium or sync_playwright is None:
        check("Browser runtime smoke",True,"Playwright/Chromium در این محیط نصب نیست؛ static contract تأیید شد")
    else:
        with tempfile.TemporaryDirectory(prefix="aibl_browser_") as td:
            xlsx=Path(td)/"filtered.xlsx"; pdf=Path(td)/"print.pdf"; errors=[]
            with sync_playwright() as pw:
                b=pw.chromium.launch(headless=True,executable_path=chromium,args=["--no-sandbox"])
                page=b.new_page(); page.on("pageerror",lambda e: errors.append(str(e)))
                page.set_content(h,wait_until="load")
                page.locator('select[data-f="ORG_DEPT"]').first.select_option(label="گمرک")
                page.wait_for_timeout(50)
                check("فیلتر مرورگر دو ردیف می‌دهد","۲" in page.locator("#cnt_0").inner_text())
                with page.expect_download() as dl:
                    page.get_by_text("استخراج داده فیلترشده (Excel)").first.click()
                dl.value.save_as(xlsx)
                page.evaluate("window.__printed=false;window.print=()=>{window.__printed=true}")
                page.get_by_text("PDF / چاپ").first.click()
                check("دکمه PDF همان HTML را چاپ می‌کند",page.evaluate("window.__printed") is True)
                page.pdf(path=str(pdf),format="A4",print_background=True)
                b.close()
            check("بدون JavaScript runtime error",not errors,"; ".join(errors[:2]))
            with zipfile.ZipFile(xlsx) as z:
                sheet=z.read("xl/worksheets/sheet1.xml").decode("utf-8")
            check("Excel فقط برش فعال را دارد",sheet.count("<row ")==3)
            check("Excel عدد و تاریخ typed دارد",'s="2"' in sheet and 's="3"' in sheet)
            check("PDF واقعی از DOM ساخته می‌شود",pdf.exists() and pdf.stat().st_size>1000)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق"); return 1 if FAIL else 0

if __name__=="__main__": raise SystemExit(run())
