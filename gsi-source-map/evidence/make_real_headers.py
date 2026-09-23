# -*- coding: utf-8 -*-
"""Build workbooks whose headers are the REAL GSI source headers, taken from the
RC adapters' COLUMN_MAPs, so the profiler is exercised against the true layout."""
import sys, os, json
import pandas as pd
sys.path.insert(0, os.environ["RC"])
out = os.environ["OUT"]; os.makedirs(out, exist_ok=True)

# --- SAP: header PR/PO plus the po.* family, exactly as V29.7.6 documents ---
sap = pd.DataFrame([
 {"Purchase Requisition":"6500029693","Item of requisition":"00010","Material":"9654003280",
  "Material Description":"واشر تخت","Material Group":"MG-11","Purchase order":"4500000001",
  "Purchasing Group":"P01","Requisition date":"2026-01-05","Changed On":"2026-01-10",
  "Release Date":"2026-01-06","Processing status":"مورد تایید","Deletion Indicator":"",
  "Quantity requested":"100","Quantity ordered":"60","Name of Supplier":"ACME",
  "WorkFlow ID":"WF-1","WorkFlow Status":"RELEASED","Comparision ID":"C-1",
  "po.Purchasing Document":"4500000001","po.Item":"00010","po.Purchase Requisition":"6500029693",
  "po.Item of requisition":"00010","po.Material":"9654003280","po.Supplier":"V-900",
  "po.Net Order Value":"1200","po.Currency":"EUR","po.Document Date":"2026-02-01",
  "po.شماره پرونده":"664823825"},
 {"Purchase Requisition":"6500029693","Item of requisition":"00010","Material":"9654003280",
  "Material Description":"واشر تخت","Material Group":"MG-11","Purchase order":"4500000002",
  "Purchasing Group":"P01","Requisition date":"2026-01-05","Changed On":"2026-01-10",
  "Release Date":"2026-01-06","Processing status":"تایید نشده","Deletion Indicator":"",
  "Quantity requested":"100","Quantity ordered":"40","Name of Supplier":"ACME",
  "WorkFlow ID":"WF-1","WorkFlow Status":"RELEASED","Comparision ID":"C-1",
  "po.Purchasing Document":"4500000002","po.Item":"00020","po.Purchase Requisition":"6500029999",
  "po.Item of requisition":"00090","po.Material":"9111111111","po.Supplier":"V-901",
  "po.Net Order Value":"800","po.Currency":"EUR","po.Document Date":"2026-02-02",
  "po.شماره پرونده":"664823825"},
 {"Purchase Requisition":"6500029700","Item of requisition":"00020","Material":"9654003281",
  "Material Description":"پيچ","Material Group":"MG-12","Purchase order":"",
  "Purchasing Group":"P02","Requisition date":"2026-03-01","Changed On":"2026-03-15",
  "Release Date":"2026-03-02","Processing status":"در گردش","Deletion Indicator":"X",
  "Quantity requested":"5","Quantity ordered":"","Name of Supplier":"",
  "WorkFlow ID":"WF-2","WorkFlow Status":"IN PROCESS","Comparision ID":"",
  "po.Purchasing Document":"","po.Item":"","po.Purchase Requisition":"",
  "po.Item of requisition":"","po.Material":"","po.Supplier":"",
  "po.Net Order Value":"","po.Currency":"","po.Document Date":"","po.شماره پرونده":""},
])

# --- NTSW: three sheets; REG is 8-digit, REG_FILE is 9-digit (documented trap) ---
il = pd.DataFrame([
 {"شماره پرونده ثبت سفارش":"664823825","کد ثبت سفارش":"98404279","شماره سفارش":"502805",
  "تاریخ صدور":"1405/01/01","وضعیت":"فعال"},
 {"شماره پرونده ثبت سفارش":"664823826","کد ثبت سفارش":"98404280","شماره سفارش":"812211A",
  "تاریخ صدور":"1405/02/01","وضعیت":"فعال"},
])
commit = pd.DataFrame([
 {"ردیف":"1","کد ثبت سفارش":"98404279","شماره ردیف تعهد":"7","شعبه":"B1","ارز":"EUR",
  "تعهد اولیه":"100","مانده تعهد":"50","تاریخ ایجاد تعهد":"1405/01/01",
  "مهلت رفع تعهد":"1405/06/01","وضعیت رفع تعهد":"رفع تعهد نشده","شرکت":"X"},
 {"ردیف":"2","کد ثبت سفارش":"98404279","شماره ردیف تعهد":"7","شعبه":"B1","ارز":"EUR",
  "تعهد اولیه":"100","مانده تعهد":"50","تاریخ ایجاد تعهد":"1405/01/01",
  "مهلت رفع تعهد":"1405/06/01","وضعیت رفع تعهد":"رفع تعهد نشده","شرکت":"X"},
])
alloc = pd.DataFrame([
 {"ردیف":"1","کد ثبت سفارش":"98404279","ردیف درخواست":"1","وضعیت":"تایید نشده","فرآیند فعلی":"",
  "مبلغ درخواست":"100","ارز درخواست":"USD","تاریخ ایجاد درخواست":"1405/01/01","تاریخ تخصیص":"",
  "محل تامین ارز":"","نرخ ارز":"","نوع درخواست":"A","شعبه":"B1","تاریخ تایید":"","شرکت":"X"},
 {"ردیف":"2","کد ثبت سفارش":"98404279","ردیف درخواست":"2","وضعیت":"تخصيص يافته","فرآیند فعلی":"",
  "مبلغ درخواست":"100","ارز درخواست":"EUR","تاریخ ایجاد درخواست":"1405/01/02",
  "تاریخ تخصیص":"1405/02/02","محل تامین ارز":"","نرخ ارز":"","نوع درخواست":"A","شعبه":"B1",
  "تاریخ تایید":"","شرکت":"X"},
])
# --- Commercial Expert ---
expert = pd.DataFrame([
 {"Order No. (Our Reference)":"502805","Data type":"Purchase Approval Data","Material":"9654003280",
  "Material Description":"واشر تخت","Purchase Requisition":"6500029693","Item of requisition":"00010",
  "BL No.":"TECHREF1","نوع ارز":"EUR","PI Line Value":"1200","Quantity In Order":"100",
  "وضعیت سفارش":"مورد تایید","نزد سازنده":"10","در راه":"5","گمرک":"0"},
 {"Order No. (Our Reference)":"502805","Data type":"Pre Purchase Approval Data","Material":"9654003281",
  "Material Description":"پيچ","Purchase Requisition":"6500029700","Item of requisition":"00020",
  "BL No.":"TECHREF2","نوع ارز":"USD","PI Line Value":"800","Quantity In Order":"5",
  "وضعیت سفارش":"تایید نشده","نزد سازنده":"","در راه":"","گمرک":""},
])
# --- Oracle (missing from the map config entirely) ---
oracle = pd.DataFrame([
 {"شماره فنی":"9654003280","کد جنس":"K1","شرح جنس":"واشر تخت","گروه تامین":"G1",
  "موجودی انبار ایران خودرو":"12","موجودی انبار ساپکو":"3","نیاز روزانه قطعات":"4",
  "تعداد خودرو کف":"100","وضعیت":"","کارشناس خرید خارجی":""},
])
# --- FX: the duplicate "نوع ارز" header the RC binds positionally ---
fx = pd.DataFrame([
 {"تاریخ خرید":"1405/02/10","ثبت سفارش":"98404279","شماره سفارش":"502805","نام ذینفع":"ACME",
  "ارز خریداری شده":"1000","نوع ارز خریداری شده":"EUR","نرخ ارز خریداری شده":"60000",
  "مبلغ ارز پروفرم":"1200","نوع ارز":"EUR","ارز سوئیفت":"1000","تاریخ سوئیفت":"1405/02/11",
  "تاریخ تایید وصول":"","وضعیت":"تایید شده","شماره بارنامه":"BL-777"},
])
# --- Customs / Clearance ---
clearance = pd.DataFrame([
 {"پرونده ترخیص":"CF-1","شماره بارنامه":"BL-777","شماره سفارش":"502805","نوع حمل":"دریایی",
  "کوتاژ":"34138249","تاریخ  دریافت شماره کوتاژ":"1405/03/01","ترخیص کامل":"*",
  "ترخیص درصدی":"","تاریخ بارگیری 6 (کامل)":"1405/03/05","تعرفه":"87085032","ارزش فاکتور":"1200",
  "نوع ارز":"EUR"},
])
with pd.ExcelWriter(os.path.join(out,"SAP.xlsx")) as w: sap.to_excel(w, sheet_name="Data", index=False)
with pd.ExcelWriter(os.path.join(out,"ntsw.xlsx")) as w:
    il.to_excel(w, sheet_name="Import Licence", index=False)
    commit.to_excel(w, sheet_name="Release Commitment", index=False)
    alloc.to_excel(w, sheet_name="Allocation", index=False)
with pd.ExcelWriter(os.path.join(out,"experts.xlsx")) as w: expert.to_excel(w, sheet_name="Expert Data", index=False)
with pd.ExcelWriter(os.path.join(out,"oracle.xlsx")) as w: oracle.to_excel(w, sheet_name="Total_Report 14050610", index=False)
with pd.ExcelWriter(os.path.join(out,"fx_transactions.xlsx")) as w: fx.to_excel(w, sheet_name="Sheet1", index=False)
with pd.ExcelWriter(os.path.join(out,"customs.xlsx")) as w: clearance.to_excel(w, sheet_name="SeaClearance", index=False)
print("fixtures written to", out)
