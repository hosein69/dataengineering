# -*- coding: utf-8 -*-
from pathlib import Path
import os, sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
import tempfile
import pandas as pd
from aibl.studio_core.filters import FilterState, apply_filters
from aibl.studio_core.html_export import build_dynamic_html
from aibl.studio_core.excel_export import build_custom_excel
PASS=[]; FAIL=[]
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("✅" if cond else "❌"), name, detail if not cond else "")
def sample():
    return pd.DataFrame({
        'KEY_MATERIAL':['M1','M2','M3'], 'CANONICAL_ORDER':['O1','O1','O2'], 'CANONICAL_BL':['B1','B1','B2'],
        'بحرانی (کوتاه)':['بحرانی','ایمن','تحت نظر'], 'کد طبقه بحرانی':['CRITICAL','SAFE','WATCH'],
        'مقاومت (روز)':[5,30,15], 'BL_CRITICAL':[True,True,False], 'ORDER_CRITICAL':[True,True,False],
        'ORG_DEPT':['A','A','B'], 'CANONICAL_EXPERT':['علی','علی','مریم'], 'روش حمل':['Sea','Air','Land']
    })
def run():
    d=sample(); out=apply_filters(d,FilterState(criticality=['بحرانی'])); check('فیلتر برخط',len(out)==1 and out.iloc[0]['KEY_MATERIAL']=='M1')
    out=apply_filters(d,FilterState(expert=['مریم'])); check('فیلتر کارشناس',len(out)==1 and out.iloc[0]['CANONICAL_EXPERT']=='مریم')
    h=build_dynamic_html(d,'2026-09-07',selected_fields=['KEY_MATERIAL','CANONICAL_EXPERT','CANONICAL_ORDER']); check('HTML شامل CSS و JavaScript پویا است','<script>' in h and 'addEventListener' in h and 'CANONICAL_EXPERT' in h)
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'custom.xlsx'; out=build_custom_excel(d,p,['kpi','criticality','expert','table'],'2026-09-07',selected_fields=['KEY_MATERIAL','CANONICAL_EXPERT','CANONICAL_ORDER']); import openpyxl; wb=openpyxl.load_workbook(p); check('Excel سفارشی ساخته می‌شود',p.exists() and 'Executive' in wb.sheetnames and 'Criticality' in wb.sheetnames and 'Expert Workload' in wb.sheetnames and 'Live Data' in wb.sheetnames)
    launcher=Path(ROOT)/'app'/'run_platform.py'; text=launcher.read_text(encoding='utf-8'); check('لانچر Studio به فایل صحیح اشاره می‌کند', (Path(ROOT)/'app'/'studio.py').exists() and "os.path.join(HERE,'studio.py')" in text and 'platform.py' not in text)
    print(f'نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق'); return 1 if FAIL else 0
if __name__=='__main__': raise SystemExit(run())
