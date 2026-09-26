"""python -m gsi.cashflow --input ledger.xlsx --out reports --as-of 2026-09-22"""
import argparse
from pathlib import Path
import pandas as pd
from .inputs import read_input, import_reference_rates, write_templates
from .engine import build_cashflow
from .report import excel_bytes, html_report


def main():
    p=argparse.ArgumentParser(description='GSI evidence-led financial cashflow')
    p.add_argument('--input');p.add_argument('--links');p.add_argument('--rates');p.add_argument('--rules')
    p.add_argument('--measurements')
    p.add_argument('--out',default='cashflow_output');p.add_argument('--as-of');p.add_argument('--currency',default='IRR')
    p.add_argument('--templates',action='store_true');a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    if a.templates:write_templates(out);return
    if a.input:
        bundle=read_input(a.input)
        bundle['origin']='UPLOADED_LEDGER'
    else:
        from .dwh import bundle_from_dwh
        bundle=bundle_from_dwh(a.as_of)
    for kind in ('links','rates','rules','measurements'):
        path=getattr(a,kind)
        if path:bundle[kind]=import_reference_rates(path) if kind=='rates' and path.lower().endswith('.xlsx') else pd.read_csv(path,dtype=str,keep_default_na=False)
    result=build_cashflow(bundle['events'],bundle.get('links'),bundle.get('rates'),as_of=a.as_of,reporting_currency=a.currency,rules=bundle.get('rules'),measurements=bundle.get('measurements'))
    result['meta'].update(input_origin=bundle.get('origin',''),warehouse_run_id=bundle.get('warehouse_run_id',''))
    if bundle.get('diagnostics') is not None:result['source_diagnostics']=bundle['diagnostics']
    if 'source_data' in bundle:result['source_data']=bundle['source_data']
    x=excel_bytes(result);(out/'GSI_Cashflow.xlsx').write_bytes(x)
    (out/'GSI_Cashflow.html').write_text(html_report(result,x),encoding='utf-8')
    result['issues'].to_csv(out/'issues.csv',index=False,encoding='utf-8-sig')
    print(f'Events={len(result["events"])}; observations={len(result["observations"])}; issues={len(result["issues"])}; output={out}')

if __name__=='__main__':main()
