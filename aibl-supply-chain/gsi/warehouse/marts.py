"""Source-grain business records and exact decimal facts; never sum across file versions.
Keys are evidence for linking, not authorization or proof of uniqueness.
"""
from collections import defaultdict
from decimal import Decimal
from .store import Warehouse,dumps
from .numeric import decimal_text

DDL='''
CREATE TABLE IF NOT EXISTS wh_business_record(file_id TEXT NOT NULL REFERENCES wh_file(id),source TEXT NOT NULL,sheet TEXT NOT NULL,row_no INTEGER NOT NULL,registration_id TEXT,order_id TEXT,material_id TEXT,request_id TEXT,payload TEXT NOT NULL,PRIMARY KEY(file_id,sheet,row_no));
CREATE INDEX IF NOT EXISTS wh_business_reg ON wh_business_record(registration_id,source,file_id);
CREATE INDEX IF NOT EXISTS wh_business_material ON wh_business_record(material_id,source,file_id);
CREATE TABLE IF NOT EXISTS wh_measure(file_id TEXT NOT NULL,sheet TEXT NOT NULL,row_no INTEGER NOT NULL,measure TEXT NOT NULL,amount_decimal TEXT,amount_raw TEXT,currency TEXT NOT NULL,status TEXT NOT NULL,PRIMARY KEY(file_id,sheet,row_no,measure),FOREIGN KEY(file_id,sheet,row_no) REFERENCES wh_business_record(file_id,sheet,row_no));
CREATE INDEX IF NOT EXISTS wh_measure_currency ON wh_measure(file_id,measure,currency);
'''

def stage(df,source,sheet,fid):
    wh=Warehouse()
    def first(row,names):return next((str(row[n]).strip() for n in names if n in row and row[n] is not None and str(row[n]).strip()),'')
    measures={
      'fx_transaction': [('ارز خریداری شده','نوع ارز خریداری شده'),('مبلغ ارز پروفرم','نوع ارز'),('ارز سوئیفت','نوع ارز__2'),('مبلغ ریالی','IRR')],
      'ntsw': [('مبلغ درخواست','ارز درخواست'),('تعهد اولیه','ارز'),('مانده تعهد','ارز'),('مبلغ کل پیش فاکتور','نوع ارز'),('ارزش کل','نوع ارز')]
    }.get(source,[])
    with wh.db() as c:
        c.executescript(DDL)
        for r in df.to_dict('records'):
            rn=int(r['_SOURCE_ROW']);reg=first(r,['کد ثبت سفارش','شماره ثبت سفارش','ثبت سفارش']);order=first(r,['شماره سفارش','سفارش'])
            c.execute('INSERT OR IGNORE INTO wh_business_record VALUES(?,?,?,?,?,?,?,?,?)',(fid,source,sheet,rn,reg,order,first(r,['شماره فنی']),first(r,['ردیف درخواست','شماره ردیف تعهد']),dumps(r)))
            for label,unit in measures:
                if label not in r:continue
                raw=r[label];amount=decimal_text(raw);currency=unit if unit=='IRR' else first(r,[unit])
                status='valid' if amount is not None and currency and (reg or order) else 'unresolved'
                c.execute('INSERT OR IGNORE INTO wh_measure VALUES(?,?,?,?,?,?,?,?)',(fid,sheet,rn,label,amount,None if raw is None else str(raw),currency,status))

def totals(fid):
    wh=Warehouse(); sums=defaultdict(Decimal);unknown=defaultdict(int)
    with wh.db() as c:
        c.executescript(DDL)
        rows=c.execute('SELECT sheet,measure,currency,amount_decimal,status FROM wh_measure WHERE file_id=?',(fid,)).fetchall()
    for sheet,measure,currency,amount,status in rows:
        key=(sheet,measure,currency)
        if status=='valid':sums[key]+=Decimal(amount)
        else:unknown[key]+=1
    return [{'sheet':k[0],'measure':k[1],'currency':k[2] or 'نامشخص','known_total':format(sums[k],'f'),'unresolved_rows':unknown[k]} for k in sorted(set(sums)|set(unknown))]
