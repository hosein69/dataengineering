from __future__ import annotations

import copy
import hashlib
import html
import io
import json
import os
import re
import string
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from gsi.design import tokens as T
from gsi.core.text import clean_employee_code
from .locking import FileLock as _FileLock

LEVELS = {'expert': 'کارشناس', 'manager': 'مدیر میانی', 'executive': 'مدیر ارشد'}
KINDS = {'daily': 'روزانه', 'comprehensive': 'جامع دوره‌ای', 'custom': 'سفارشی'}
SOURCE_KINDS = {'contacts': 'فهرست ایمیل و افراد', 'clusters': 'تعریف کلاستر', 'memberships': 'عضویت در کلاستر'}
REQUIRED = {'contacts': ('employee_code', 'email'), 'clusters': ('cluster_id', 'name'),
            'memberships': ('employee_code', 'cluster_id')}
OPTIONAL = {'contacts': ('name','first_name','last_name','management','department','position','level','cluster_id','active'), 'clusters': ('active',), 'memberships': ('level','active')}
WIDGETS = {'actions': 'اقدام‌های قابل پیگیری', 'cases': 'پرونده‌ها', 'stages': 'توزیع مرحله‌ها', 'blockers': 'موانع ثبت‌شده', 'commitments':'تعهدهای نزدیک و عقب‌افتاده', 'workboard':'تابلوی اقدام', 'decisions':'تصمیم‌های موردنیاز مدیر', 'learning':'راهنمای کوتاه پیگیری'}
FIELDS = ['KEY_REG', 'CANONICAL_ORDER', 'CANONICAL_BL', 'KEY_MATERIAL', 'مرحله جاری',
          'NEXT_ACTION_TITLE', 'NEXT_ACTION_DUE_DATE', 'NEXT_ACTION_OWNER', 'مانع فعلی',
          'FX_CURRENT_STAGE', 'FX_ACTION_TITLE', 'FX_ACTION_DUE_DATE', 'بحرانی (کوتاه)', 'recipient_name','recipient_management','recipient_department','recipient_position']


def now():
    return datetime.now(timezone.utc).isoformat()


def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', value):
        raise ValueError('شناسه باید ۱ تا ۶۴ حرف لاتین، عدد، خط تیره یا زیرخط باشد.')
    return value


def emp(value):
    raw = str(value).strip()
    if not raw or any(c in raw for c in '/\\\r\n'):
        raise ValueError('کد پرسنلی نامعتبر است.')
    result = clean_employee_code(raw)
    if not re.fullmatch(r'\d{8}', result):
        raise ValueError('کد پرسنلی معتبر هشت‌رقمی لازم است.')
    return result


def active(value):
    if isinstance(value, bool):
        return value
    v = str(value).strip().lower()
    if v in ('true', '1', 'فعال', 'yes'): return True
    if v in ('false', '0', 'غیرفعال', 'no'): return False
    raise ValueError('وضعیت باید true/false یا فعال/غیرفعال باشد.')


def template(value, context):
    if not isinstance(value, str): raise ValueError('قالب متن باید رشته باشد.')
    for _, field, spec, conversion in string.Formatter().parse(value):
        if field is not None and (field not in context or spec or conversion):
            raise ValueError('متغیر قالب ناشناخته است؛ از نام، مدیریت، اداره، جایگاه، سطح و مشخصات گزارش استفاده کنید.')
    return value.format(**context)


def default_cluster(cid, name, color=T.CLUSTER_ACCENTS['purchase_1']):
    return {'id': cid, 'name': name, 'active': True, 'header': name, 'color': color,
            'subject': '{report_type} | {cluster} | {date}',
            'body': '{name} گرامی\nگزارش {cluster} برای بررسی و پیگیری خدمت شما ارائه می‌شود.',
            'signature': 'واحد پایش زنجیره خرید', 'widgets': ['actions','commitments','blockers','workboard','learning'],
            'tabs': [{'title': 'پرونده‌های قابل پیگیری', 'fields': FIELDS[:5]}], 'levels': {'manager':{'widgets':['decisions','blockers','commitments','stages','learning']}, 'executive':{'widgets':['decisions','blockers','stages','learning']}}}


def defaults():
    clusters = [('purchase_1','خرید خارجی — مدیریت اول',T.CLUSTER_ACCENTS['purchase_1']),
                ('purchase_2','خرید خارجی — مدیریت دوم',T.CLUSTER_ACCENTS['purchase_2']),
                ('logistics','حمل و گمرک',T.CLUSTER_ACCENTS['logistics']),('finance','مالی، ثبت سفارش و تعهد ارزی',T.CLUSTER_ACCENTS['finance']),
                ('followup','پیگیری',T.CLUSTER_ACCENTS['followup']),('process','تحلیل فرایند و سیستمی',T.CLUSTER_ACCENTS['process']),
                ('custom','کلاستر سفارشی',T.CLUSTER_ACCENTS['custom'])]
    return {'schema_version': 1, 'revision': 0, 'clusters': [default_cluster(*c) for c in clusters],
            'people': [], 'memberships': [], 'sources': []}


def validate(cfg):
    if cfg.get('schema_version') != 1: raise ValueError('نسخه ساختار پشتیبانی نمی‌شود.')
    for key in ('clusters', 'people', 'memberships', 'sources'):
        if not isinstance(cfg.get(key), list): raise ValueError(f'{key}: فهرست لازم است.')
    ids, people, pairs = set(), set(), set()
    context = dict(name='نام و نام خانوادگی',first_name='نام',last_name='نام خانوادگی',management='مدیریت',department='اداره',position='جایگاه',level='سطح',employee_code='کد',email='ایمیل',cluster='گروه',date='2026-01-01',report_type='روزانه')
    extra_fields={k for source in cfg['sources'] for k in source.get('mapping',{}) if k.startswith('custom_')}
    context.update({k:'' for k in extra_fields})
    def report(c):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', c.get('color', T.CLUSTER_ACCENTS['purchase_1'])): raise ValueError('رنگ HEX نامعتبر است.')
        if any(w not in WIDGETS for w in c.get('widgets', [])): raise ValueError('ویجت ناشناخته است.')
        for key in ('subject','body','signature','header'):
            if key in c:
                template(c[key], context)
                if len(c[key]) > 10000: raise ValueError('متن بیش از حد بلند است.')
        if any(ch in c.get('subject','') for ch in '\r\n'): raise ValueError('موضوع ایمیل باید یک خط باشد.')
        tabs = c.get('tabs', [])
        if not isinstance(tabs,list) or len(tabs)>12: raise ValueError('حداکثر ۱۲ تب مجاز است.')
        for tab in tabs:
            if not tab.get('title') or not isinstance(tab.get('fields'), list) or not tab['fields']:
                raise ValueError('هر تب عنوان و فهرست فیلد لازم دارد.')
            if any(f not in FIELDS and f not in extra_fields for f in tab['fields']): raise ValueError('فیلد خارج از فهرست قابل انتشار است.')
    for c in cfg['clusters']:
        cid = ident(c['id'])
        if cid in ids: raise ValueError('شناسه کلاستر تکراری است.')
        ids.add(cid)
        if not str(c.get('name','')).strip(): raise ValueError('نام کلاستر لازم است.')
        if not isinstance(c.get('active'),bool): raise ValueError('وضعیت کلاستر باید boolean باشد.')
        report(c)
        for level, override in c.get('levels',{}).items():
            if level not in LEVELS or not isinstance(override,dict): raise ValueError('سطح سازمانی نامعتبر است.')
            report(override)
    for p in cfg['people']:
        code = emp(p['employee_code'])
        if code != p['employee_code'] or code in people: raise ValueError('کد پرسنلی باید یکتا و استاندارد باشد.')
        people.add(code)
        if not re.fullmatch(r'[^\s@;<>]+@[^\s@;<>]+\.[^\s@;<>]+', p.get('email','')): raise ValueError('ایمیل نامعتبر است.')
        if not p.get('name') or not isinstance(p.get('active'),bool): raise ValueError('نام و وضعیت فرد لازم است.')
    for m in cfg['memberships']:
        key=(m['employee_code'],m['cluster_id'])
        if key in pairs: raise ValueError('عضویت فرد در کلاستر تکراری است.')
        pairs.add(key)
        if key[0] not in people or key[1] not in ids: raise ValueError('عضویت به فرد یا کلاستر ناموجود اشاره می‌کند.')
        if m.get('scope_employee_codes'):
            for code in str(m['scope_employee_codes']).split(','): emp(code.strip())
        if m['level'] not in LEVELS or not isinstance(m.get('active'),bool): raise ValueError('سطح یا وضعیت عضویت نامعتبر است.')
    seen=set()
    for s in cfg['sources']:
        if ident(s['id']) in seen: raise ValueError('شناسه منبع تکراری است.')
        seen.add(s['id'])
        if s['kind'] not in SOURCE_KINDS: raise ValueError('نوع منبع پشتیبانی نمی‌شود.')
        if not isinstance(s.get('mapping'),dict): raise ValueError('نگاشت ستون لازم است.')
        required=set(REQUIRED[s['kind']])
        if not required.issubset(s['mapping']) or any(not s['mapping'][k] for k in required):
            raise ValueError('نگاشت ستون‌های لازم کامل نیست.')
        from .contacts import required_mapping
        if not required_mapping(s['kind'],s['mapping']): raise ValueError('نام و نام خانوادگی یا دو ستون نام و نام خانوادگی را نگاشت کنید.')
        if len(set(s['mapping'].values()))!=len(s['mapping']): raise ValueError('یک ستون به چند فیلد نگاشت شده است.')
    return cfg


def atomic_write(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.gsi-',suffix='.tmp')
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        Path(tmp).unlink(missing_ok=True)


class CenterStore:
    def __init__(self, root=None):
        self.root=Path(root or os.environ.get('GSI_CONTROL_ROOT') or Path(os.environ.get('GSI_HOME',Path.home()/'.gsi'))/'control_center')
        self.path=self.root/'config.json'

    @property
    def namespace(self): return 'control_center:' + str(self.root.resolve())

    def load(self):
        from gsi.warehouse.store import Warehouse
        wh=Warehouse()
        with wh.db() as c:
            row=c.execute('SELECT payload FROM wh_config WHERE namespace=?',(self.namespace,)).fetchone()
            if row: return validate(json.loads(row[0]))
            cfg=validate(json.loads(self.path.read_text(encoding='utf-8'))) if self.path.exists() else defaults()
            c.execute('INSERT OR IGNORE INTO wh_config VALUES(?,?,?)',(self.namespace,cfg['revision'],json.dumps(cfg,ensure_ascii=False)))
        return cfg

    def save(self, cfg, expected_revision, actor='streamlit-operator'):
        from gsi.warehouse.store import Warehouse, RUN
        candidate=validate(copy.deepcopy(cfg))
        self.load()
        with Warehouse().db() as c:
            c.execute('BEGIN IMMEDIATE')
            current=json.loads(c.execute('SELECT payload FROM wh_config WHERE namespace=?',(self.namespace,)).fetchone()[0])
            if current['revision']!=expected_revision: raise ValueError('تنظیمات در نشست دیگری تغییر کرده؛ تازه‌سازی کنید.')
            candidate['revision']=expected_revision+1
            candidate['updated_at']=now();candidate['updated_by']=actor
            history={'namespace':self.namespace,'before':current,'after':candidate}
            c.execute('INSERT INTO wh_audit(at,run_id,kind,actor,payload) VALUES(?,?,?,?,?)',(now(),RUN.get(),'cluster_config',actor,json.dumps(history,ensure_ascii=False)))
            c.execute('UPDATE wh_config SET revision=?,payload=? WHERE namespace=?',(candidate['revision'],json.dumps(candidate,ensure_ascii=False),self.namespace))
        return candidate


def read_source(blob, filename, sheet=0):
    if len(blob)>20*1024*1024: raise ValueError('فایل از سقف ۲۰ مگابایت بزرگ‌تر است.')
    suffix=Path(filename).suffix.lower()
    if suffix=='.csv':
        import csv
        text=blob.decode('utf-8-sig')
        headers=next(csv.reader(io.StringIO(text)),[])
        df=pd.read_csv(io.StringIO(text),dtype=str,keep_default_na=False)
    elif suffix=='.xlsx':
        from .contacts import suggest
        raw=pd.read_excel(io.BytesIO(blob),sheet_name=sheet,header=None,dtype=str,keep_default_na=False)
        scores=[]
        for index,row in raw.head(20).iterrows():
            found=suggest([str(v) for v in row]);score=len(found)
            if 'employee_code' in found:score+=5
            if 'email' in found:score+=5
            scores.append((score,-index,index))
        header_row=max(scores)[2] if scores and max(scores)[0]>=5 else 0
        if raw.empty:raise ValueError('شیت خالی است.')
        raw=raw.loc[:,~raw.apply(lambda col:col.astype(str).str.strip().eq('').all())]
        headers=[str(v).strip() for v in raw.iloc[header_row].tolist()]
        df=raw.iloc[header_row+1:].copy();df.columns=headers;df=df.reset_index(drop=True)
    else: raise ValueError('فقط CSV با UTF-8 یا XLSX پذیرفته می‌شود.')
    if len(headers)!=len(set(headers)) or any(not h.strip() for h in headers): raise ValueError('سرستون خالی یا تکراری مجاز نیست.')
    if len(df)>50000: raise ValueError('بیش از ۵۰ هزار ردیف؛ فایل را به بخش‌های مشخص تقسیم کنید.')
    return df


def preview_import(cfg, source, blob, filename):
    if source['kind'] not in SOURCE_KINDS: raise ValueError('نوع منبع نامعتبر است.')
    df=read_source(blob,filename,source.get('sheet',0))
    mapping=source['mapping'];kind=source['kind']
    if not set(REQUIRED[kind]).issubset(mapping): raise ValueError('نگاشت ناقص است.')
    if len(mapping.values())!=len(set(mapping.values())): raise ValueError('نگاشت تکراری است.')
    missing=set(mapping.values())-set(df.columns)
    if missing: raise ValueError('ستون‌های منبع تغییر کرده‌اند: '+', '.join(sorted(missing)))
    out=copy.deepcopy(cfg); rows=[];seen=set()
    for idx,r in df.iterrows():
        row={key:str(r[col]).strip() for key,col in mapping.items()}
        if not any(row.values()): continue
        try:
            row['active']=active(row.get('active','true'))
            if kind=='contacts':
                from .contacts import level
                row['employee_code']=emp(row['employee_code']);row['email']=row['email'].lower();key=row['employee_code']
                row['name']=row.get('name') or ' '.join(x for x in (row.get('first_name',''),row.get('last_name','')) if x)
                if not row['name']: raise ValueError('نام و نام خانوادگی خالی است.')
                raw_level=row.get('level','')
                if raw_level and level(raw_level,default=None) is None: raise ValueError('سطح ناشناخته؛ مقدار جایگاه را جداگانه نگاشت کنید.')
                row['level']=level(raw_level or row.get('position',''))
                row={k:v for k,v in row.items() if v!=''}
            elif kind=='clusters':
                key=ident(row.pop('cluster_id'));row['id']=key
            else:
                from .contacts import level
                row['employee_code']=emp(row['employee_code']);row['level']=level(row.get('level',''))
                key=(row['employee_code'],row['cluster_id'])
            if key in seen: raise ValueError('کلید تکراری در فایل؛ اصلاح منبع لازم است.')
            seen.add(key);rows.append(row)
        except Exception as ex: raise ValueError(f'ردیف {idx+2}: {ex}') from ex
    target={'contacts':'people','clusters':'clusters','memberships':'memberships'}[kind]
    keyfn=(lambda r:r['employee_code']) if kind=='contacts' else ((lambda r:r['id']) if kind=='clusters' else (lambda r:(r['employee_code'],r['cluster_id'])))
    existing={keyfn(r):r for r in out[target]};added=updated=0
    for row in rows:
        key=keyfn(row)
        if key in existing: existing[key].update(row);updated+=1
        else:
            existing[key]=default_cluster(row['id'],row['name']) if kind=='clusters' else {}
            existing[key].update(row);added+=1
    out[target]=list(existing.values())
    assigned=0
    if kind=='contacts':
        membership={(m['employee_code'],m['cluster_id']):m for m in out['memberships']}
        for row in rows:
            cid=row.get('cluster_id') or source.get('default_cluster_id')
            if cid:
                key=(row['employee_code'],cid)
                member=membership.get(key,{})
                member.update(employee_code=row['employee_code'],cluster_id=cid,level=row.get('level','expert'),active=row['active'])
                membership[key]=member;assigned+=1
        out['memberships']=list(membership.values())
    validate(out)
    return out, {'rows':len(rows),'assigned':assigned,'added':added,'updated':updated,'sha256':hashlib.sha256(blob).hexdigest()}


def commit_import(store, cfg, source, blob, filename):
    result,summary=preview_import(cfg,source,blob,filename)
    receipt={'source_id':source['id'],'kind':source['kind'],'at':now(),**summary}
    from gsi.warehouse.store import Warehouse
    wh=Warehouse()
    receipt['file_id']=wh.blob(blob,filename,'cluster_import')
    wh.audit('cluster_import_validation',{'mapping':source,'receipt':receipt})
    result['last_import']=receipt
    result=store.save(result,cfg['revision'])
    return result,summary


def report_context(cfg, employee_code, cluster_id, report_kind):
    if report_kind not in KINDS: raise ValueError('نوع گزارش نامعتبر است.')
    person=next((p for p in cfg['people'] if p['employee_code']==employee_code and p['active']),None)
    cluster=next((c for c in cfg['clusters'] if c['id']==cluster_id and c['active']),None)
    member=next((m for m in cfg['memberships'] if m['employee_code']==employee_code and m['cluster_id']==cluster_id and m['active']),None)
    if not (person and cluster and member): raise ValueError('فرد، کلاستر و عضویت باید فعال باشند.')
    settings=copy.deepcopy(cluster);settings.update(cluster.get('levels',{}).get(member['level'],{}))
    return person,settings,member


def require_encryption():
    try:
        import cryptography
    except ModuleNotFoundError as ex:
        import sys
        raise RuntimeError(
            'برای خواندن یا ذخیره Snapshot رمزگذاری‌شده، cryptography در همین Python نصب شود: '
            + '"' + sys.executable + '" -m pip install "cryptography>=42.0"'
        ) from ex


def render_report(cfg, employee_code, cluster_id, report_kind='daily'):
    p,c,m=report_context(cfg,employee_code,cluster_id,report_kind)
    from .scope import warehouse_context
    current=warehouse_context(employee_code,m)
    if current is None:
        require_encryption()
        from gsi.personalization.service import PersonalWorkspace
        ws=PersonalWorkspace.from_env(employee_code)
        if not ws.store.paths.snapshot.exists(): raise ValueError('گزارش موفق در دیتاورهوس یا Snapshot شخصی وجود ندارد؛ ابتدا خط لوله را اجرا کنید.')
        ctx=ws.context();current=ctx.get('current') or {}
    records=current.get('records',[])
    if not isinstance(records,list): raise ValueError('داده گزارش نامعتبر است.')
    return render_records(cfg,p,c,m,report_kind,current)


def render_records(cfg,p,c,m,report_kind,current):
    employee_code=p['employee_code'];cluster_id=c['id']
    records=[dict(r,recipient_name=p['name'],recipient_management=p.get('management',''),recipient_department=p.get('department',''),recipient_position=p.get('position','')) for r in current.get('records',[])]
    date_text=str(current.get('ref_date') or 'نامشخص')
    values={k:str(p.get(k,'') or '') for k in ('name','first_name','last_name','management','department','position','employee_code','email')}
    values.update({k:str(p.get(k,'') or '') for src in cfg['sources'] for k in src.get('mapping',{}) if k.startswith('custom_')})
    records=[dict(r,**{k:v for k,v in p.items() if k.startswith('custom_')}) for r in records]
    values.update(cluster=c['name'],date=date_text,report_type=KINDS[report_kind],level=LEVELS[m['level']])
    e=lambda v:html.escape('—' if v is None else str(v))
    title=template(c['header'],values);body=template(c['body'],values)
    subject=template(c['subject'],values)
    limit= {'expert':80,'manager':40,'executive':15}[m['level']] if report_kind=='daily' else len(records)
    def table(rows, fields):
        if not rows:return '<p>موردی در داده منتشرشده ثبت نشده است.</p>'
        head=''.join(f'<th scope="col" style="padding:9px;background:{T.TEAL_WASH};text-align:right">'+e(LABELS.get(f,f.removeprefix('custom_').replace('_',' ') if f.startswith('custom_') else f))+'</th>' for f in fields)
        lines=''.join('<tr>'+''.join(f'<td style="padding:9px;border-bottom:1px solid {T.BORDER}">'+e(r.get(f))+'</td>' for f in fields)+'</tr>' for r in rows[:limit])
        return '<table width="100%" style="border-collapse:collapse;font-size:14px"><tr>'+head+'</tr>'+lines+'</table>'
    from .widgets import extra_widget, LABELS
    sections=[]
    from .widgets import actions
    unique_actions=actions(records)
    intro={'expert':'برای شروع، اقدام‌های موعددار و موانع پرونده‌های خود را مرور کنید.','manager':'مرور تیم را از موانع و تعیین مسئول اقدام‌ها شروع کنید.','executive':'موارد نیازمند تصمیم و موانع مشترک را در اولویت مرور قرار دهید.'}[m['level']]
    sections.append('<p>'+e(intro)+'</p><p>اقدام‌های ثبت‌شده: '+e(len(unique_actions))+' · اقدام‌های دارای مانع: '+e(sum(bool(r['مانع']) for r in unique_actions))+'</p>')
    for widget in c.get('widgets',[]):
        if widget in ('commitments','workboard','decisions','learning'):
            sections.append(extra_widget(widget,records,m['level'],date_text,table))
            continue
        if widget=='actions':
            rows=[{'پرونده':r.get('KEY_REG'),'اقدام':r.get('NEXT_ACTION_TITLE') or r.get('FX_ACTION_TITLE'),'موعد':r.get('NEXT_ACTION_DUE_DATE') or r.get('FX_ACTION_DUE_DATE')} for r in records if r.get('NEXT_ACTION_TITLE') or r.get('FX_ACTION_TITLE')]
            fields=['پرونده','اقدام','موعد']
        elif widget=='blockers':
            rows=[{'پرونده':r.get('KEY_REG'),'مانع':r.get('مانع فعلی')} for r in records if r.get('مانع فعلی')];fields=['پرونده','مانع']
        elif widget=='stages':
            from collections import Counter
            counts=Counter(str(r.get('مرحله جاری') or r.get('FX_CURRENT_STAGE') or 'نامشخص') for r in records)
            rows=[{'مرحله':k,'تعداد ردیف منتشرشده':v} for k,v in counts.items()];fields=['مرحله','تعداد ردیف منتشرشده']
        else: rows=records;fields=FIELDS[:5]
        sections.append('<h2 style="font-size:20px">'+e(WIDGETS[widget])+'</h2>'+table(rows,fields))
    for tab in c.get('tabs',[]): sections.append('<h2 style="font-size:20px">'+e(tab['title'])+'</h2>'+table(records,tab['fields']))
    clipped=current.get('truncated',False)
    note=f'تاریخ داده: {date_text} · {LEVELS[m["level"]]} · {KINDS[report_kind]} · ردیف منتشرشده: {len(records)} · سقف نمایش هر بخش: {limit}'
    if clipped:note+=' · Snapshot بخشی از داده است؛ برای گزارش کامل انتشار مجدد لازم است.'
    report=f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title></head><body style="background:{T.SURFACE_PAGE};color:{T.TEXT};font-family:Tahoma,Arial,sans-serif;line-height:1.9"><table role="presentation" width="100%"><tr><td style="padding:20px"><h1 style="font-size:26px;border-right:6px solid {c['color']};padding-right:14px">{e(title)}</h1><p>{e(body).replace(chr(10),'<br>')}</p><p>{e(p.get('management',''))} · {e(p.get('department',''))} · {e(p.get('position',''))}</p><p style="color:{T.TEXT_SECONDARY}">{e(note)}</p>{''.join(sections)}<p>{e(template(c['signature'],values))}</p></td></tr></table></body></html>'''
    return {'html':report,'subject':subject,'email':p['email'],'employee_code':employee_code,'cluster_id':cluster_id,'kind':report_kind,'revision':cfg['revision']}


def save_report(bundle):
    require_encryption()
    from gsi.personalization.store import EncryptedUserStore
    store=EncryptedUserStore.from_master_env(bundle['employee_code'])
    folder=store.paths.folder/'reports'/ident(bundle['cluster_id'])
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]
    path=folder/(stamp+'_'+ident(bundle['kind'])+'.html')
    atomic_write(path,bundle['html'].encode('utf-8'))
    receipt={k:v for k,v in bundle.items() if k not in ('html','email')}
    receipt.update(saved_at=now(),sha256=hashlib.sha256(bundle['html'].encode()).hexdigest())
    from gsi.warehouse.store import Warehouse
    Warehouse().audit('report_saved',dict(receipt,path=str(path)))
    return path


def outlook_draft(bundle):
    from gsi.integrations.daily_email import _outlook_session
    with _outlook_session() as win32:
        outlook=win32.Dispatch('Outlook.Application');mail=outlook.CreateItem(0)
        sender=os.environ.get('GSI_EMAIL_SENDER','').strip().lower()
        if sender:
            account=next((a for a in outlook.Session.Accounts if str(getattr(a,'SmtpAddress','')).lower()==sender),None)
            if account is None: raise ValueError('حساب فرستنده Outlook پیدا نشد.')
            mail.SendUsingAccount=account
        mail.Subject=bundle['subject'];mail.To=bundle['email'];mail.BodyFormat=2;mail.HTMLBody=bundle['html']
        if not mail.Recipients.ResolveAll(): raise ValueError('Outlook گیرنده را تأیید نکرد.')
        mail.Save();mail.Display()
    from gsi.warehouse.store import Warehouse
    Warehouse().audit('outlook_draft',{'recipient':bundle['email'],'cluster_id':bundle.get('cluster_id',''),'sent':False})
    return {'drafted':True,'sent':False}
