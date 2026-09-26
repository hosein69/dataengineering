"""Synthetic, fully documented sample. Never treat these amounts as company data."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from gsi.cashflow.engine import EVENT_COLUMNS,LINK_COLUMNS,RATE_COLUMNS,MEASUREMENT_COLUMNS
from gsi.cashflow.inputs import write_templates

def create(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);write_templates(root/'templates')
    ev=[]
    def add(i,k,amount='',cur='EUR',**kw):
        row=dict(event_id=i,case_id='DEMO-REG-1',order_id='999999999999999999',bl_id='',kind=k,date='2026-09-01',amount=amount,currency=cur,from_account='EXTERNAL:funding',to_account='OWN:bank',document='DEMO-DOC-'+i,source='SYNTHETIC ONLY',status='POSTED',note='داده کاملاً مصنوعی')
        row.update(kw);ev.append(row)
    add('file','FILE');add('reg','REGISTRATION','1200');add('queue','QUEUE','1200')
    add('quota','QUOTA','1200');add('allocation','ALLOCATION','1100');add('allocuse','ALLOCATION_USE','1000');add('quotause','QUOTA_USE','1000')
    add('openingIRR','OPENING','0','IRR',to_account='OWN:IRR');add('openingEUR','OPENING','0')
    add('fund','FUNDING','100000000','IRR',to_account='OWN:IRR')
    add('sell','FX_SELL','100000000','IRR',from_account='OWN:IRR',to_account='EXTERNAL:exchange',group_id='FX-1')
    add('buy','FX_BUY','1000',from_account='EXTERNAL:exchange',group_id='FX-1')
    add('payment','PAYMENT','800',from_account='OWN:bank',to_account='EXTERNAL:supplier')
    add('commit','COMMITMENT','1000',due_date='2026-12-01')
    add('BL1','SHIPMENT','400',bl_id='DEMO-BL-1');add('BL2','SHIPMENT','300',bl_id='DEMO-BL-2')
    add('customs','CUSTOMS','450','USD',bl_id='DEMO-BL-1')
    add('clear','CLEARANCE',bl_id='DEMO-BL-1');add('warehouse','WAREHOUSE',bl_id='DEMO-BL-1')
    add('bankdoc','BANK_DOCS',bl_id='DEMO-BL-1');add('settle','SETTLEMENT','350',bl_id='DEMO-BL-1')
    links=[]
    def link(i,a,b,x,y,**kw):
        row=dict(link_id=i,from_event=a,to_event=b,from_amount=x,to_amount=y,document='DEMO-LINK-'+i)
        row.update(kw);links.append(row)
    link('L1','fund','sell','100000000','100000000');link('L2','sell','buy','100000000','1000')
    link('L3','buy','payment','800','800');link('L4','payment','BL1','400','400');link('L5','payment','BL2','300','300')
    link('L6','payment','customs','400','450');link('L7','commit','settle','350','350',relation_type='OBLIGATION_SETTLEMENT')
    rates=[]
    for dt in ['2026-09-01','2026-09-22']:
        for cur,rate,purpose in [('EUR','100000','accounting'),('USD','90000','customs'),('EUR','100000','settlement')]:
            rates.append(dict(rate_id=f'DEMO-{dt}-{cur}-{purpose}',date=dt,value_date=dt,base=cur,quote='IRR',rate=rate,purpose=purpose,
                              source='SYNTHETIC RATE ONLY',source_document='DEMO-RATE-DOC',source_hash='0'*64,
                              approved='true',approved_by='DEMO',approved_at=dt,max_age_days='0'))
    measurements=[dict(measurement_id='DEMO-M1',case_id='DEMO-REG-1',metric='COMMITMENT_BALANCE',observed_at='2026-09-22',
                       amount='650',currency='EUR',source='SYNTHETIC NTSW',source_record_id='DEMO-NTSW-1',document='DEMO-SNAPSHOT',status='OBSERVED')]
    pd.DataFrame(ev,columns=EVENT_COLUMNS).to_csv(root/'Events.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(links,columns=LINK_COLUMNS).to_csv(root/'Links.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(rates,columns=RATE_COLUMNS).to_csv(root/'Rates.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(measurements,columns=MEASUREMENT_COLUMNS).to_csv(root/'Measurements.csv',index=False,encoding='utf-8-sig')
if __name__=='__main__':create(sys.argv[1])
