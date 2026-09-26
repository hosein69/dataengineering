import sys
from pathlib import Path
sys.path.insert(0,str(Path('final_src').resolve()))
import pandas as pd
from gsi.cashflow.engine import build_cashflow
from gsi.cashflow.report import excel_bytes,html_report
rows=[]
for i,(reg,amount,cur) in enumerate([('88000001',125000,'EUR'),('88000002',86000,'USD'),('88000003',47000,'EUR')]):
 for j,kind in enumerate(['REGISTRATION','QUEUE','ALLOCATION','COMMITMENT','FX_BUY','PAYMENT']):
  if i==2 and kind in ['FX_BUY','PAYMENT']:continue
  rows.append({'event_id':f'{i}-{j}','case_id':reg,'order_id':f'60216{i}B','kind':kind,'date':f'2026-09-{j+1:02}', 'amount':str(amount if j<4 else amount//2),'currency':cur,'document':f'DEMO-{i}-{j}','source':'SYNTHETIC QA','status':'SOURCE_FACT'})
ms=pd.DataFrame([{'measurement_id':'m1','case_id':'88000001','metric':'COMMITMENT_BALANCE','observed_at':'2026-09-22','amount':'75000','currency':'EUR','source':'SYNTHETIC NTSW','source_record_id':'1','document':'DEMO-SNAPSHOT','status':'OBSERVED'}])
r=build_cashflow(pd.DataFrame(rows),measurements=ms,as_of='2026-09-22')
r['meta'].update(input_origin='نمونه نمایشی؛ داده واقعی سازمان نیست',warehouse_run_id='DEMO-20260922')
out=Path('final_evidence/ui');out.mkdir(exist_ok=True)
x=excel_bytes(r);(out/'GSI_FINANCE_PREVIEW.html').write_text(html_report(r,x));(out/'GSI_FINANCE_PREVIEW.xlsx').write_bytes(x)
print('preview created')
