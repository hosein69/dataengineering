"""Explicit input contracts and conservative bridges from legacy report snapshots."""
from hashlib import sha256
from pathlib import Path
import pandas as pd
from .engine import EVENT_COLUMNS, LINK_COLUMNS, RATE_COLUMNS, MEASUREMENT_COLUMNS, RULE_COLUMNS, text, day


def read_input(path):
    """Canonical workbook sheets: Events, Measurements, Links, Rates, Rules. CSV means Events only."""
    if str(getattr(path,'name',path)).lower().endswith('.csv'):
        return {'events':pd.read_csv(path,dtype=str,keep_default_na=False)}
    sheets=pd.read_excel(path,sheet_name=None,dtype=str,keep_default_na=False)
    if 'Events' in sheets:
        return {k.lower():v for k,v in sheets.items() if k in {'Events','Measurements','Links','Rates','Rules'}}
    first=next(iter(sheets.values()))
    if 'CB No.' in first:
        return {'events':legacy_of(first),'source_data':first}
    raise ValueError('شیت Events یا ساختار شناخته‌شده OF موجود نیست')


#: نگاشت ستون‌های OF به رویدادهای دارای مبلغ.
#: (kind, ستون مبلغ, ستون ارز, ستون تاریخ, ستون سند, دانه)
#: دانه از روی خود فایل واقعی اندازه‌گیری شده است، نه از روی حدس:
#:   CB Value / CB Date / Fx / Punishment* در هر CB ثابت‌اند و در همهٔ ردیف‌های
#:   همان CB تکرار می‌شوند؛ BL / BL Value / تاریخ ارسال اسناد در سطح ردیف‌اند.
OF_VALUED = [('PAYMENT','Payment','Fx Payment','Date of Buying Currency','Payment Number','case'),
             ('SHIPMENT','BL Value','Fx','Date of Sending Documents','BL','bl'),
             ('REGISTRATION','CB Value','Fx','CB Date','CB No.','case'),
             ('FEE','Punishment Value','Punishment Fx','Punishment Date to Bank','CB No.','case')]
#: مراحلی که OF فقط تاریخ‌شان را ثبت می‌کند. موتور برای این نوع‌ها مبلغ لازم ندارد،
#: پس ثبت‌شان «اختراع مبلغ» نیست و پیوستگی فرایند را از همان منبع می‌سازد.
OF_DATED = [('BANK_DOCS','Date of Finance Receipt','دریافت اسناد مالی','bl'),
            ('CLEARANCE','Date of Clearance','ترخیص','bl')]

_OF_NOTE = ('گزارش مشتق تخصیص است، نه دفتر بانکی: حساب بانکی و سند اصلی در آن نیست. '
            'به همین دلیل SOURCE_FACT ثبت می‌شود و گردش حساب نمی‌سازد. '
            'ارز بارنامه نیازمند تأیید مستقل است.')


def legacy_of(df):
    """OF is a derived allocation report, not a bank journal. Never invent payment IDs.

    ## دو نقصِ اندازه‌گیری‌شده که اینجا بسته می‌شود

    **۱) گزارش کاملاً خالی.** موتور فقط ``POSTED`` و ``SOURCE_FACT`` را قابل
    احتساب می‌داند و ``document`` خالی را رد می‌کند. نسخهٔ قبلی این تابع
    ``status='OBSERVED'`` با ``document=''`` می‌ساخت، بنابراین **۱۰۰٪** ردیف‌های
    فایل واقعی OF با کد ``UNVERIFIED_EVIDENCE`` بیرون می‌افتادند و شیت
    «رویدادهای پذیرفته‌شده» صفر ردیف داشت. ردیف OF یک شاهد منبع مستند است
    (نه یک ثبت بانکی)، پس جای درستش ``SOURCE_FACT`` با ارجاع سندی است که خود
    فایل دارد: شماره پرداخت، بارنامه یا شماره ثبت سفارش. هیچ شناسه‌ای ساخته
    نمی‌شود؛ اگر ستون سند خالی باشد، مرجع ردیف فایل ثبت می‌شود و در یادداشت
    صریحاً گفته می‌شود کدام ستون خالی بوده است.

    **۲) دوبار‌شماری ناشی از دانهٔ مخلوط (fan-out).** OF یک گزارش تخت است که
    ستون‌های سطح CB را در کنار ستون‌های سطح بارنامه می‌گذارد. اندازه‌گیری روی
    فایل واقعی: ``CB1`` پنج ردیف دارد و ``CB Value`` در هر پنج ردیف تکرار شده
    است. ساخت یک رویداد به‌ازای هر ردیف یعنی ارزش ثبت سفارش ۵ برابر شود
    (۶۰٬۷۳۷ → ۳۰۳٬۶۸۶). بنابراین شناسهٔ رویداد از **محتوا** ساخته می‌شود نه از
    شمارهٔ ردیف: تکرارِ یک واقعیتِ واحد در چند ردیف، یک رویداد است. شماره‌های
    ردیفِ مشارکت‌کننده در یادداشت حفظ می‌شوند تا ردیابی از بین نرود.
    """
    events={}
    for i,r in df.iterrows():
        case=text(r.get('CB No.'));bl=text(r.get('BL'));row_no=i+2
        deadline=text(r.get('OF Deadline'))

        def add(kind,scope,amount,currency,when,doc_col,note_extra=''):
            ref=text(r.get(doc_col)) if doc_col else ''
            scoped_bl=bl if scope=='bl' else ''
            # مهلت در فایل واقعی در سطح ردیف/بارنامه تغییر می‌کند، پس فقط روی
            # رویداد بارنامه‌ای می‌نشیند؛ روی رویداد سطح CB باعث تکثیر می‌شد.
            due=deadline if scope=='bl' and kind=='SHIPMENT' else ''
            key='|'.join([case,scoped_bl,kind,text(amount),text(currency),text(when),ref,due])
            eid='OF:'+sha256(key.encode('utf-8')).hexdigest()[:24]
            prev=events.get(eid)
            if prev is not None:
                prev['_rows'].append(row_no);return
            missing=('' if ref or not doc_col
                     else f' ستون «{doc_col}» در این ردیف خالی است؛ شناسه‌ای ساخته نشد.')
            events[eid]=dict(event_id=eid,source_event_id=key,case_id=case,bl_id=scoped_bl,
                kind=kind,date=text(when),amount=text(amount),currency=text(currency),
                source='OF',document=ref,status='SOURCE_FACT',due_date=due,
                note=(_OF_NOTE+missing+note_extra).strip(),_rows=[row_no])

        for kind,amt,cur,dt,doc,scope in OF_VALUED:
            add(kind,scope,r.get(amt),r.get(cur),r.get(dt),doc)
        for kind,dt,label,scope in OF_DATED:
            if not text(r.get(dt)):continue
            add(kind,scope,'','',r.get(dt),'CB No.',
                f' {label}: OF فقط تاریخ این مرحله را دارد؛ مبلغی برای آن در منبع نیست.')

    rows=[]
    for e in events.values():
        refs=sorted(set(e.pop('_rows')))
        shown=', '.join(str(n) for n in refs[:12])+('، …' if len(refs)>12 else '')
        e['source']=f'OF / {len(refs)} ردیف'
        e['note']=f"{e['note']} ردیف‌های منبع: {shown}."
        if not e['document']:e['document']=f'OF:rows:{refs[0]}'
        rows.append(e)
    return pd.DataFrame(rows,columns=EVENT_COLUMNS)


def pipeline_observations(extras):
    """Bridge the persisted money-control ledger into cash-flow source facts.

    These rows are source evidence, not bank-journal postings.  ``SOURCE_FACT``
    lets the cash-flow engine include documented amounts in lifecycle summaries
    without inventing OWN accounts.  Derived balances remain measurements.
    """
    ledger=extras.get('fx_money_ledger')
    if ledger is None or ledger.empty:return pd.DataFrame(columns=EVENT_COLUMNS)
    from hashlib import sha256
    rows=[]
    mapping={'BANK_FUNDING_IRR':'FUNDING','SUPPLIER_PAYMENT':'PAYMENT','FX_PURCHASE':'FX_BUY',
             'REGISTRATION_VALUE':'REGISTRATION','ALLOCATION_REQUEST':'QUEUE','ALLOCATION':'ALLOCATION',
             'COMMITMENT_INITIAL':'COMMITMENT','CUSTOMS_VALUE':'CUSTOMS','SWIFT':'BANK_DOCS'}
    skip={'COMMITMENT_BALANCE','ALLOCATION_BALANCE','QUOTA_BALANCE','COMMITMENT_RELEASED'}
    for _,r in ledger.iterrows():
        code=text(r.get('EVENT_CODE'))
        if code in skip or code not in mapping:continue
        source=text(r.get('SOURCE'))
        ref=text(r.get('REFERENCE'))
        case=text(r.get('KEY_REG'))
        raw='|'.join([source,ref,code,case,text(r.get('EVENT_DATE')),text(r.get('AMOUNT')),text(r.get('CURRENCY'))])
        eid='GSI:source:'+sha256(raw.encode('utf-8')).hexdigest()[:24]
        rows.append(dict(event_id=eid,source_event_id=(ref+':'+code if ref else ''),case_id=case,
            kind=mapping[code],amount=text(r.get('AMOUNT')),currency=text(r.get('CURRENCY')),date=text(r.get('EVENT_DATE')),
            source=source or 'GSI/DWH money ledger',document=ref or eid,status='SOURCE_FACT',
            note=('شاهد بومی منبع از دفتر DWH؛ جزئیات حساب بانکی استنباط نشده است. '+text(r.get('NOTE'))).strip()))
    return pd.DataFrame(rows,columns=EVENT_COLUMNS)


def pipeline_measurements(extras, observed_at=None):
    """Cumulative source balances stay measurements and can never inflate events.

    ``EVENT_DATE`` of some operational rows is a deadline (not snapshot time), so
    the report reference date is the observation date whenever it is supplied.
    """
    ledger=extras.get('fx_money_ledger')
    if ledger is None or ledger.empty:return pd.DataFrame(columns=MEASUREMENT_COLUMNS)
    from hashlib import sha256
    rows=[]
    supported={'COMMITMENT_BALANCE','ALLOCATION_BALANCE','QUOTA_BALANCE'}
    observed=text(observed_at)
    for _,r in ledger.iterrows():
        code=text(r.get('EVENT_CODE'))
        if code not in supported:continue
        source=text(r.get('SOURCE')) or 'GSI/DWH money ledger'
        ref=text(r.get('REFERENCE'))
        case=text(r.get('KEY_REG'))
        at=observed or text(r.get('EVENT_DATE'))
        raw='|'.join([source,ref,code,case,at,text(r.get('AMOUNT')),text(r.get('CURRENCY'))])
        mid='GSI:snapshot:'+sha256(raw.encode('utf-8')).hexdigest()[:24]
        rows.append(dict(measurement_id=mid,case_id=case,metric=code,
                         observed_at=at,amount=text(r.get('AMOUNT')),
                         currency=text(r.get('CURRENCY')),source=source,
                         source_record_id=ref,document=ref or mid,
                         status='OBSERVED',note='مانده تجمیعی منبع؛ Snapshot است و رویداد مالی نیست'))
    return pd.DataFrame(rows,columns=MEASUREMENT_COLUMNS)

def import_reference_rates(path):
    """Notebook identifies units of CCY per USD. Imported rates remain unapproved."""
    raw=pd.read_excel(path,sheet_name='Data');rows=[]
    for _,r in raw.iterrows():
        dt=day(r.get('Miladi_Date'))
        for cur in raw.columns:
            if cur in {'Miladi_Date','Shamsi_Date'}:continue
            from .engine import number
            v=number(r.get(cur))
            if dt and v and v>0:
                rows.append(dict(date=dt.isoformat(),value_date=dt.isoformat(),base=cur,quote='USD',rate=str(1/v),
                    purpose='accounting',source='Exchange Rates.xlsx; جهت نرخ از notebook استنباط شده؛ نیازمند تأیید',
                    approved='false',max_age_days='0'))
    return pd.DataFrame(rows,columns=RATE_COLUMNS)


def write_templates(directory):
    p=Path(directory);p.mkdir(parents=True,exist_ok=True)
    for name,cols in [('Events',EVENT_COLUMNS),('Measurements',MEASUREMENT_COLUMNS),('Links',LINK_COLUMNS),('Rates',RATE_COLUMNS),
                      ('Rules',RULE_COLUMNS)]:
        pd.DataFrame(columns=cols).to_csv(p/(name+'.csv'),index=False,encoding='utf-8-sig')
