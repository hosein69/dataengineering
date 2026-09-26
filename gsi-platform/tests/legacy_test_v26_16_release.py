# -*- coding: utf-8 -*-
"""رگرسیون انتشار 26.16 — سنجه معنایی، امنیت، HTML و روند مدیریتی."""
from __future__ import annotations
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
import pandas as pd

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,ROOT)
PASS=[]; FAIL=[]
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name); print(("✅" if cond else "❌"),name,("→ "+detail if detail else ""))

def main():
    from gsi.factsheet import VERSION, DASHBOARD_SHEETS
    from gsi.studio_core.grain import measure_kind, safe_agg, KIND_ADDITIVE
    from gsi.studio_core.access import apply_access_scope
    from gsi.studio_core.templates import TEMPLATES
    from gsi.studio_core.html_export import build_dynamic_html
    from gsi.report.history import snapshot
    check("نسخه انتشار حداقل 26.16 است", tuple(map(int,VERSION.split("."))) >= (26,16,0), VERSION)
    check("گزارش رسمی ۱۷ شیت دارد", DASHBOARD_SHEETS==17, str(DASHBOARD_SHEETS))
    s=pd.Series([1001,2002,3003,4004,5005,6006])
    check("مبلغ یکتای صحیح شناسه تشخیص داده نمی‌شود", all(measure_kind(c,s)==KIND_ADDITIVE for c in ["INVOICE_VALUE","DUTY_AMOUNT","NTSW_BALANCE","CB_VALUE"]))
    fan=pd.DataFrame({"KEY_REG":["R1","R1","R1","R2"],"مانده تعهد":[1000,1000,1000,500]})
    check("جمع تعهد دانه‌ای است", safe_agg(fan,"مانده تعهد","sum")==1500)
    sec=pd.DataFrame({"ORG_DEPT":["A","B"],"EMP_EMAIL":["a@example.invalid","b@example.invalid"],"KEY_ORDER":["1","2"]})
    ar=apply_access_scope(sec,list(sec.columns),allowed_departments=["A"])
    check("scope ردیفی قبل از خروجی اعمال می‌شود", len(ar.df)==1)
    check("فیلد حساس پیش‌فرض حذف می‌شود", "EMP_EMAIL" not in ar.fields)
    check("چهار قالب نقش‌محور اصلی موجود است", {"executive","operational","process","audit"}.issubset(TEMPLATES))
    df=pd.DataFrame({"_CASE_KEY":["C1","C2"],"KEY_MATERIAL":["M1","M2"],"بحرانی (کوتاه)":["بحرانی","ایمن"],"مقاومت (روز)":[4,50],"مانده تعهد":[1000,0],"روزهای تأخیر":[10,0]})
    ev=pd.DataFrame({"_CASE_KEY":["C1","C1","C2","C2"],"ACTIVITY_FA":["ثبت سفارش","تخصیص ارز","ثبت سفارش","حمل"],"EVENTTIME":pd.to_datetime(["2026-09-01","2026-09-11","2026-09-01","2026-09-03"])})
    h=build_dynamic_html(df,"2026-09-15",selected_fields=list(df.columns),process_extras={"eventlog":ev},show_process=True,lineage={"warehouse_run_id":"R-TEST"})
    check("HTML lifecycle تکراری ندارد", h.count("addEventListener('click'") == 1)
    check("Process از Event Log فیلترشده محاسبه می‌شود", "processStats(a)" in h and "PROC.eventlog" in h)
    check("Excel مرورگری به‌عنوان استخراج داده نام‌گذاری شده", "استخراج داده فیلترشده (Excel)" in h)
    check("lineage در HTML وجود دارد", "R-TEST" in h and "REPORT_META" in h)
    node=shutil.which("node")
    if node:
        js="\n".join(re.findall(r"<script>(.*?)</script>",h,re.S))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"a.js"; p.write_text(js,encoding="utf-8")
            r=subprocess.run([node,"--check",str(p)],capture_output=True,text=True)
        check("JavaScript از نظر syntax معتبر است", r.returncode==0, r.stderr[-120:])
    else: check("JavaScript از نظر syntax معتبر است", True, "node در محیط نیست؛ تست اختیاری")
    snap=snapshot(pd.DataFrame({"KEY_REG":["R1","R1","R2"],"مانده تعهد":[1000,1000,500],"روزهای تأخیر":[5,5,0]}),"2026-09-15")
    check("Snapshot روند نیز دانه‌ای است", snap["مانده تعهد"]==1500 and snap["مانده تعهد معوق"]==1000)
    print("\n"+"="*78); print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق"); print("="*78)
    return 1 if FAIL else 0
if __name__=="__main__": sys.exit(main())
