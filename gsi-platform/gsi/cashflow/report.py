"""Dedicated offline HTML + Excel, shared financial result and lineage."""
import base64
import io
from datetime import date
from decimal import Decimal
from html import escape
import pandas as pd
from ..design import tokens as T
from ..version import PACKAGE_VERSION
from ..studio_core.excel_export import _style_sheet

TITLES={'chain':'زنجیره PI تا رفع تعهد','periods':'جریان نقد ماهانه','summary':'خلاصه پرونده و ارز','documents':'سفارش و بارنامه','conversions':'تبدیل ارز مستند','accounts':'منابع و مصارف حساب','events':'رویدادهای پذیرفته‌شده',
        'links':'مسیر مستند پول','movements':'گردش حساب','valuation':'ارزش‌گذاری تاریخی','timeline':'زنجیره اسناد',
        'measurements':'Snapshot سامانه‌ها','reconciliation':'تطبیق دفتر و سامانه','rate_register':'شناسنامه نرخ‌ها','rule_register':'شناسنامه قواعد',
        'deadlines':'مهلت‌های اعلامی','observations':'شواهد نیازمند تکمیل','issues':'مغایرت‌ها','source_diagnostics':'تشخیص تعارض سورس DWH','source_data':'داده ورودی اصلی'}
#: چرا یک بخش خالی است. «خالی» یعنی شاهدِ لازم در منبع نبود، نه اینکه آن مرحله
#: انجام نشده باشد. بدون این جمله، کاربر یک تبِ صفرردیفی را «نبودِ عملیات»
#: می‌خواند و این دقیقاً همان اشتباهِ تصمیم است که باید جلویش گرفته شود.
EMPTY_REASONS={
 'chain':'هیچ پرونده‌ای با شاهد قابل احتساب در این محدوده نیست.',
 'periods':'رویداد نقدی پذیرفته‌شده‌ای با تاریخ معتبر برای تجمیع ماهانه وجود ندارد.',
 'summary':'رویدادی با کد ثبت سفارش و ارز مشخص پذیرفته نشد.',
 'documents':'ستون سفارش یا بارنامه در شواهد پذیرفته‌شده پر نبود.',
 'conversions':'تبدیل ارز فقط با دو سند هم‌پرونده/هم‌تاریخ (FX_BUY و FX_SELL با group_id یکسان) ساخته می‌شود؛ چنین جفتی در منبع نبود.',
 'accounts':'منبع، شمارهٔ حساب «:OWN» ندارد؛ بدون حساب، منابع و مصارف ساخته نمی‌شود.',
 'links':'جدول ارتباط‌های مستند (Links) در ورودی نبود؛ ارتباط حدسی ساخته نمی‌شود.',
 'movements':'گردش حساب به رویداد نقدیِ دارای حساب مبدأ و مقصد نیاز دارد؛ شواهد این منبع حساب بانکی ندارند.',
 'valuation':'نرخ تأییدشده برای ارزش‌گذاری تاریخی موجود نیست؛ بدون نرخ، تبدیل انجام نمی‌شود.',
 'timeline':'رویداد دارای تاریخ معتبری برای ساخت زنجیره اسناد وجود ندارد.',
 'measurements':'مانده‌ای از سامانه‌ها (Snapshot) در ورودی ثبت نشده است.',
 'reconciliation':'تطبیق به هر دو طرف نیاز دارد: مانده گزارش‌شده سامانه و مانده دفتر رویداد؛ یکی از دو طرف موجود نیست.',
 'rate_register':'هیچ نرخ تأییدشده‌ای وارد نشده است؛ نرخ بدون تأیید در محاسبه به کار نمی‌رود.',
 'rule_register':'جدول قواعد (بخشنامه/مهلت) تأییدشده وارد نشده است؛ مهلت قانونی فرض نمی‌شود.',
 'deadlines':'مهلتی در ستون OF Deadline یا قواعد وارد نشده است.',
 'observations':'همهٔ شواهد قابل احتساب بودند؛ موردی برای تکمیل نماند.',
 'issues':'کنترل‌های اجراشده موردی ثبت نکردند.',
 'source_diagnostics':'تعارض سورسی در انبار داده گزارش نشد.',
 'source_data':'داده ورودی اصلی همراه این گزارش ذخیره نشده است.'}
DEFAULT_EMPTY_REASON='شاهد لازم برای ساخت این بخش در منابع ورودی وجود نداشت.'


def empty_reason(key):
    return EMPTY_REASONS.get(key, DEFAULT_EMPTY_REASON)


LABELS={'matched_in_shipment_currency':'وجه مرتبط به ارز بارنامه','unfunded_shipment':'بارنامه بدون وجه مرتبط','warehouse_evidence':'شاهد انبار','rate_regime':'رژیم نرخ','reference_rate':'نرخ مرجع','reference_difference':'اختلاف با نرخ مرجع؛ نه سود قطعی','period':'ماه میلادی','fx_in':'ورودی تبدیل ارز','fx_out':'خروجی تبدیل ارز','case_id':'کد ثبت سفارش / شناسه دفتر مستقل','order_id':'سفارش','bl_id':'بارنامه','currency':'ارز','paid':'پرداخت',
 'registration_value':'ارزش PI/ثبت تجاری','allocation_requested':'مبلغ درخواست تخصیص','funding':'تأمین وجه','purchased':'ارز خریداری‌شده','refund':'برگشت وجه','fees':'کارمزد',
 'allocation':'تخصیص مصوب','allocation_used':'مصرف تخصیص','allocation_remaining':'مانده تخصیص ثبت‌شده',
 'quota':'سهمیه مصوب','quota_used':'مصرف سهمیه','quota_remaining':'مانده سهمیه ثبت‌شده',
 'commitment':'تعهد اولیه','settled':'رفع تعهد مستند','accepted_return':'عودت پذیرفته‌شده بانک',
 'settlement_evidence':'اسناد رفع تعهد ثبت‌شده','return_evidence':'اسناد عودت ثبت‌شده',
 'commitment_remaining':'مانده تعهد ثبت‌شده','customs_value':'ارزش اظهار گمرکی','shipment_value':'ارزش حمل',
 'untraced_payment':'پرداخت بدون ارتباط منبع','unmatched_payment':'پرداخت بدون ارتباط بارنامه',
 'account':'حساب','opening':'مانده ابتدا','inflow':'ورودی','outflow':'خروجی','net_movement':'خالص گردش',
 'closing':'مانده پایان','closing_rate':'نرخ پایان','closing_value':'ارزش پایان','event_id':'شناسه رویداد',
 'date':'تاریخ','kind':'نوع رویداد','amount':'مبلغ','from_account':'از حساب','to_account':'به حساب',
 'document':'مرجع سند','source':'منبع','status':'وضعیت','group_id':'گروه تبدیل','due_date':'مهلت',
 'rule_id':'قاعده','note':'توضیح','rate':'نرخ','rate_date':'تاریخ نرخ','rate_source':'منبع نرخ',
 'reporting_currency':'ارز گزارش','value':'ارزش تاریخی','signed_amount':'گردش علامت‌دار',
 'stage':'مرحله','dates':'تاریخ‌های شاهد','documents':'اسناد','days_remaining':'روز تا مهلت','basis':'مبنا',
 'code':'کد کنترل','reference':'مرجع','severity':'شدت','detail':'توضیح کنترل',
 'link_id':'شناسه ارتباط','from_event':'رویداد مبدأ','to_event':'رویداد مقصد','from_amount':'مبلغ مبدأ',
 'to_amount':'مبلغ مقصد','authorization':'مجوز جابجایی','from_currency':'ارز مبدأ','to_currency':'ارز مقصد',
 'source_case':'پرونده مبدأ','target_case':'پرونده مقصد','target_kind':'نوع مقصد','implied_rate':'نرخ ضمنی سند',
 'measurement_id':'شناسه Snapshot','metric':'شاخص','observed_at':'زمان مشاهده','reported_value':'مانده گزارش‌شده',
 'ledger_value':'مانده دفتر رویداد','variance':'اختلاف','verification_status':'اعتبار قاعده','provenance_status':'کامل‌بودن منشأ نرخ',
 'relation_type':'نوع رابطه','reversal_of':'ابطالِ رویداد','source_event_id':'شناسه بومی منبع','recorded_at':'زمان ثبت',
 'settlement_method':'روش ایفای تعهد','conversion_basis':'مبنای تبدیل','rate_id':'شناسه نرخ','rate_side':'سمت نرخ','rate_market':'بازار نرخ',
 'stage_no':'ترتیب مرحله','event_count':'تعداد شاهد','amounts':'مبالغ شاهد','linked_amount':'مبلغ لینک‌شده','gap_code':'کد شکاف'}


def display(v):
    if v is None or (not isinstance(v,(list,dict)) and pd.isna(v)):return '—'
    if isinstance(v,Decimal):return format(v,'f')
    if isinstance(v,date):return v.isoformat()
    return str(v)


def excel_bytes(result):
    # Use the package's established Excel stack and style contract at application runtime.
    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine='openpyxl') as writer:
        meta=pd.DataFrame([{'موضوع':k,'شرح':v} for k,v in result['meta'].items()])
        meta.to_excel(writer,sheet_name='راهنما',index=False)
        for key,title in TITLES.items():
            df=result.get(key)
            if df is None:continue
            df=df.copy()
            # Full-precision Decimal source remains in HTML; Excel supports 15 significant digits.
            for col in df:
                df[col]=df[col].map(lambda v:float(v) if isinstance(v,Decimal) and len(v.as_tuple().digits)<=15 else (str(v) if isinstance(v,Decimal) else v))
            if df.empty:
                # شیت با فقط سرستون، برای کاربر «خرابی» است. علت را می‌نویسیم.
                df=pd.DataFrame({'وضعیت':['شاهدی برای این بخش ساخته نشد'],
                                 'علت':[empty_reason(key)],
                                 'ستون‌های این بخش':[' · '.join(str(LABELS.get(str(c),c)) for c in df.columns) or '—']})
            df.rename(columns=LABELS).to_excel(writer,sheet_name=title[:31],index=False)
        for ws in writer.book:
            _style_sheet(ws);ws.sheet_view.rightToLeft=True
            for row in ws.iter_rows(min_row=2):
                for c in row:
                    if isinstance(c.value,str):c.data_type='s';c.number_format='@'  # block spreadsheet formula injection
                    elif isinstance(c.value,(int,float)):c.number_format='#,##0.00'
    return buf.getvalue()


def html_report(result,xlsx=None):
    from .presentation import CSS, STAGE_LABELS, STATUS_LABELS, cases
    from .process_design import build_cashflow_process_html
    meta=result['meta']; tables=[]; buttons=[]
    preferred=['summary','chain','reconciliation','deadlines','events','measurements','observations','issues']
    ordered=preferred+[k for k in TITLES if k not in preferred]
    present=[k for k in ordered if result.get(k) is not None]
    # بخش‌های بدون شاهد حذف نمی‌شوند (سند ممیزی باید کامل بماند) ولی جلوی
    # بخش‌های دارای داده را هم نمی‌گیرند: به انتهای فهرست و زیر یک عنوان جدا می‌روند.
    filled=[k for k in present if len(result[k])>0]
    blank=[k for k in present if len(result[k])==0]
    ordered=filled+blank
    for key in ordered:
        df=result.get(key)
        if df is None:continue
        i=len(tables); title=TITLES[key]
        if blank and key==blank[0]:
            buttons.append(f'<div class="navgroup">بخش‌های بدون شاهد ({len(blank)})</div>')
        buttons.append(f'<button role="tab" class="{"blank" if df.empty else ""}" aria-controls="pane{i}" aria-selected="{str(i==0).lower()}" onclick="tab({i})">{escape(title)}<span>{len(df)}</span></button>')
        heads=''.join('<th scope="col">'+escape(LABELS.get(str(c),str(c)))+'</th>' for c in df.columns)
        rows=[]
        for row in df.to_dict('records'):
            cells=[]
            for col in df.columns:
                value=display(row[col]); tone=''
                if col=='stage':value=STAGE_LABELS.get(value,value)
                if col=='status':
                    tone='ok' if value in {'MATCH','OBSERVED','POSTED','SOURCE_FACT'} else 'gap' if value in {'CONFLICT','MISMATCH','EVIDENCE_GAP'} else ''
                    value=STATUS_LABELS.get(value,value)
                cell=escape(value)
                if col=='status':cell='<span class="fin-status '+tone+'">'+cell+'</span>'
                cells.append('<td>'+cell+'</td>')
            rows.append('<tr data-case="'+escape(str(row.get('case_id','')),quote=True)+'" data-currency="'+escape(str(row.get('currency','')),quote=True)+'">'+''.join(cells)+'</tr>')
        note=empty_reason(key) if df.empty else ('دانه: کد ثبت سفارش × ارز؛ مبلغ‌ها قابل جمع بین ارزها نیستند.' if key=='summary' else 'مانده سامانه، مشاهده است؛ اختلاف آن با دفتر، به‌تنهایی اثبات رفع تعهد نیست.' if key=='reconciliation' else 'شواهد و شناسه‌های ممیزی، بدون حذف ستون‌های اصلی.')
        tables.append(f'<section role="tabpanel" id="pane{i}" {"hidden" if i else ""}><div class="section-title"><div><h2>{escape(title)}</h2><p>{note}</p></div><span class="count">{len(df)} ردیف</span></div><div class="scroll"><table><thead><tr>{heads}</tr></thead><tbody>{"".join(rows)}</tbody></table></div><p class="empty" {"" if df.empty else "hidden"}>{escape(empty_reason(key))}<br><small>این پیام دربارهٔ <b>نبودِ شاهد در منبع</b> است، نه دربارهٔ انجام‌نشدن آن مرحله.</small></p></section>')
    opts=''.join('<option value="'+escape(c,quote=True)+'">'+escape(c)+'</option>' for c in cases(result))
    ev=len(result.get('events',[]));obs=len(result.get('observations',[]));n=len(result.get('issues',[]))
    run=escape(str(meta.get('warehouse_run_id') or 'دفتر مستقل / بدون اجرای منتشرشده'))
    download=f'<a class="primary" download="GSI_Cashflow.xlsx" href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{base64.b64encode(xlsx).decode()}">دریافت Excel</a>' if xlsx else ''
    css=CSS+"""
    *{box-sizing:border-box}body{margin:0;background:#f2f5f5;color:#18373f;font-size:14px;font-family:__GSI_FONT__;line-height:1.8}
    .navgroup{margin:14px 0 4px;padding:0 12px;font-size:10px;letter-spacing:1px;color:#8aa1a6}
    nav button.blank{opacity:.72}nav button.blank span{background:#f0f3f3;border-radius:10px;padding:1px 6px}
    .empty small{display:block;margin-top:6px;color:#8aa1a6}
    .shell{display:grid;grid-template-columns:242px minmax(0,1fr);min-height:100vh;direction:rtl}aside{background:#fff;border-left:1px solid #dce5e7;padding:26px 18px;position:sticky;top:0;height:100vh;overflow:auto}
    .brand{font-size:27px;font-weight:bold;color:#163d46;padding:0 12px 28px}.brand small{display:block;font-size:10px;letter-spacing:1.2px;color:#68868c;font-weight:normal}
    nav{display:flex;flex-direction:column;gap:5px}button,a{font:inherit;text-decoration:none;cursor:pointer}nav button{display:flex;justify-content:space-between;align-items:center;text-align:right;border:0;background:transparent;border-radius:9px;padding:10px 12px;color:#506a70;font-size:12px}
    nav button span{font-size:10px;color:#72888e}nav button[aria-selected=true]{background:#e1f1ec;color:#15624d;font-weight:bold}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #178e76;outline-offset:3px}
    main{min-width:0;padding:28px 36px}.topline{display:flex;justify-content:space-between;gap:16px;color:#647c82;font-size:12px}.actions{display:flex;gap:8px}.actions a,.actions button{border:1px solid #cbd9dc;border-radius:8px;background:white;padding:9px 17px;color:#234b54}.actions .primary{background:#126956;color:white;border-color:#126956}
    .fin-hero{margin-top:22px}.fin-hero h1{font-size:30px;margin:8px 0}.provenance{display:flex;flex-wrap:wrap;gap:18px;font-size:11px;word-break:break-all}.provenance b{color:#e2f2ef;font-weight:normal}
    .metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:20px 0}.metric{background:white;border:1px solid #dce5e7;padding:18px 20px;border-radius:12px}.metric small{color:#71888d;font-size:11px}.metric strong{display:block;font-size:29px;font-weight:normal;color:#173e47}.metric em{font-size:10px;color:#647c82;font-style:normal}
    .filters{display:flex;gap:12px;flex-wrap:wrap;align-items:end;margin:24px 0 18px}.filters label{display:flex;flex-direction:column;gap:5px;font-size:11px;color:#506a70}.filters input,.filters select{padding:12px 14px;border:1px solid #cddcde;border-radius:9px;background:#fff;font:inherit;font-size:13px;min-width:210px;color:#23454d}
    section{background:white;border:1px solid #dce5e7;border-radius:14px;overflow:hidden}.section-title{padding:20px 24px;display:flex;justify-content:space-between;align-items:center;gap:10px}.section-title h2{font-size:18px;margin:0}.section-title p{font-size:11px;color:#687f85;margin:5px 0}.count{white-space:nowrap;background:#f1f5f5;padding:5px 10px;border-radius:20px;font-size:11px;color:#698187}.scroll{overflow:auto;max-height:540px}table{border-collapse:collapse;width:100%;font-size:12px}th{background:#f1f6f5;color:#56747a;text-align:right;padding:14px 18px;white-space:nowrap;font-weight:normal;position:sticky;top:0}td{padding:15px 18px;border-bottom:1px solid #edf2f2;white-space:nowrap}tbody tr:hover{background:#f6faf9}.empty{padding:20px;color:#71878d}footer{margin:18px 0;color:#798e93;font-size:10px}
    @media(max-width:900px){.shell{grid-template-columns:1fr}aside{position:static;height:auto;padding:12px;border-left:0}.brand{padding:4px 8px 12px;font-size:21px}.brand small{display:inline;margin-right:15px}nav{flex-direction:row;overflow:auto}nav button{flex-shrink:0;gap:10px}main{padding:18px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.filters input,.filters select{min-width:0;width:100%}.filters label{flex:1;min-width:130px}.topline{flex-wrap:wrap}.fin-hero h1{font-size:24px}.section-title{padding:16px}.section-title .count{display:none}}
    @media print{aside,.actions,.filters{display:none}.shell{display:block}main{padding:0}section[hidden]{display:block}.scroll{max-height:none;overflow:visible}table{font-size:9px}.metrics{grid-template-columns:repeat(4,1fr)}}
    """.replace('__GSI_FONT__', T.FONT_STACK)
    js="""let active=0;function norm(s){return s.toLowerCase().replace(/[۰-۹]/g,c=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(c)).replace(/ي/g,'ی').replace(/ك/g,'ک')}function applyFilters(){const q=norm(document.getElementById('search').value),c=document.getElementById('case').value;document.querySelectorAll('[role=tabpanel]').forEach(p=>{let n=0;p.querySelectorAll('tbody tr').forEach(r=>{r.hidden=!(norm(r.textContent).includes(q)&&(!c||!r.dataset.case||r.dataset.case===c));if(!r.hidden)n++});p.querySelector('.count').textContent=n+' ردیف';p.querySelector('.empty').hidden=n!==0})}function tab(i){active=i;document.querySelectorAll('[role=tabpanel]').forEach(s=>s.hidden=s.id!=='pane'+i);document.querySelectorAll('[role=tab]').forEach((b,j)=>b.setAttribute('aria-selected',j===i?'true':'false'));applyFilters()}document.querySelector('[role=tablist]').addEventListener('keydown',e=>{const bs=[...document.querySelectorAll('[role=tab]')];if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();const j=(active+(e.key==='ArrowLeft'?1:-1)+bs.length)%bs.length;tab(j);bs[j].focus()}});"""
    title='جریان وجوه و رفع تعهد'
    process_html=build_cashflow_process_html(result=result,instance_id='cashflow_process',compact=False)
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GSI | {title}</title><style>{css}</style></head><body><div class="shell"><aside><div class="brand">GSI<small>FINANCIAL WORKSPACE</small></div><nav role="tablist" aria-label="بخش‌های گزارش"><button role="tab" aria-selected="true" onclick="document.getElementById('cashflow_process').scrollIntoView({{behavior:'smooth'}})">نقشه مسیر پول<span>FLOW</span></button>{''.join(buttons)}</nav></aside><main><div class="topline"><span>فضای مالی / گزارش مبتنی بر شواهد</span><div class="actions">{download}<button onclick="print()">چاپ گزارش</button></div></div><header class="fin-hero"><div class="fin-eyebrow">EVIDENCE / CASH FLOW / COMMITMENT</div><h1>{title}</h1><p>هر مبلغ، یک مسیر روشن؛ از درخواست تخصیص تا رفع تعهد، با Drill-down تا شاهد.</p><div class="provenance"><span>تاریخ گزارش <b>{escape(str(meta['as_of']))}</b></span><span>منبع <b>{escape(str(meta.get('input_origin','دفتر مستقل')))}</b></span><span>اجرای مبنا <b>{run}</b></span></div></header><div class="metrics"><div class="metric"><small>ثبت سفارش</small><strong>{len(cases(result))}</strong><em>شناسه مستقل از شماره پرونده</em></div><div class="metric"><small>رویداد پذیرفته‌شده</small><strong>{ev}</strong><em>با منشأ و سند ثبت‌شده</em></div><div class="metric"><small>شاهد نیازمند تکمیل</small><strong>{obs}</strong><em>خارج از جمع قطعی</em></div><div class="metric"><small>کنترل و مغایرت</small><strong>{n}</strong><em>در کل محدوده گزارش</em></div></div><div class="fin-note">مانده سامانه ≠ تراکنش مالی. کاهش مانده به‌تنهایی اثبات رفع تعهد نیست؛ مبلغ ارزهای مختلف با هم جمع نمی‌شود. «—» یعنی نامعلوم.</div>{process_html}<div class="filters"><label>کد ثبت سفارش<select id="case" onchange="applyFilters()"><option value="">همه ثبت سفارش‌ها</option>{opts}</select></label><label>جست‌وجو در شواهد<input id="search" oninput="applyFilters()" placeholder="سفارش، سند یا نام منبع"></label></div>{''.join(tables)}<footer>GSI {PACKAGE_VERSION} · خروجی Excel شامل کل گزارش است. فیلتر نمایشی، داده ممیزی را حذف نمی‌کند. کنترل‌های عمومی ممکن است به کل گزارش مربوط باشند.<br>{escape(str(meta.get('legal_status','')))}</footer></main></div><script>{js}</script></body></html>'''
