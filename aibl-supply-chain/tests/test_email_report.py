# -*- coding: utf-8 -*-
from __future__ import annotations
import os,sys,tempfile
from datetime import date
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,ROOT)
TMP=tempfile.mkdtemp(prefix="aibl_email_"); os.environ["AIBL_OUTPUT"]=TMP; os.environ["AIBL_DAILY_REPORT_ROOT"]=TMP; os.environ["AIBL_TODAY"]="2026-08-31"
import pandas as pd
from aibl.integrations.daily_email import daily_paths, executive_kpis, build_email_html
PASS=[]; FAIL=[]
def check(n,c): (PASS if c else FAIL).append(n); print(("✅" if c else "❌"),n)
def run():
 d=date(2026,8,31); p=daily_paths(d); check("پوشه تاریخ‌دار",p["folder"].name=="2026-08-31"); check("نام ثابت تاریخ‌دار",p["excel"].name=="2026-08-31_Systemmatic Material.xlsx")
 df=pd.DataFrame({"KEY_MATERIAL":["M1","M2","M3"],"CANONICAL_BL":["B1","B1","B2"],"CANONICAL_ORDER":["O1","O1","O2"],"کد طبقه بحرانی":["CRITICAL","SAFE","SAFE"],"مقاومت (روز)":[4,50,80],"BL_CRITICAL":[True,True,False],"ORDER_CRITICAL":[True,True,False],"BL_CRITICAL_MATERIALS":["M1","M1",""] ,"BL_CRITICAL_REASON":["M1: بحرانی (4.0 روز)","M1: بحرانی (4.0 روز)",""]})
 by={x["label"]:x for x in executive_kpis(df)}; check("KPI بارنامه یکتا",by["بارنامه بحرانی"]["value"]==1); check("KPI متریال",by["متریال بحرانی"]["value"]==1)
 from aibl.integrations.daily_email import make_email_charts
 import pathlib
 h=build_email_html(d,df,[],p["excel"]); check("نام Excel در ایمیل", "Systemmatic Material.xlsx" in h); check("علت متریال در ایمیل", "M1: بحرانی" in h); check("دعوت به Excel", "چرا فایل Excel را باز کنیم؟" in h); check("فونت ایمیل IRANSans Light است", "IRANSans Light" in h); check("بدون CSS خارجی", "fonts.googleapis.com" not in h)
 assets=pathlib.Path(p["assets"]); charts=make_email_charts(df,assets); check("سه نمودار ایمیل ساخته می‌شود", len(charts)==3 and all(x.exists() for x in charts)); check("رسم نمودارها با عناوین انگلیسی انجام می‌شود", "Material Criticality Mix" in open("aibl/integrations/daily_email.py",encoding="utf-8").read() and "Critical Cases" in open("aibl/integrations/daily_email.py",encoding="utf-8").read())
 print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق"); return 1 if FAIL else 0
if __name__=="__main__": raise SystemExit(run())
