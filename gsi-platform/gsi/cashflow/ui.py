"""Published financial workspace shared by standalone, Dashboard and Studio."""
from __future__ import annotations
from hashlib import sha256
from html import escape
import logging
import pandas as pd
from .engine import build_cashflow, EVENT_COLUMNS, MEASUREMENT_COLUMNS, text
from .inputs import read_input, import_reference_rates
from .dwh import bundle_from_dwh, FinancialSourceUnavailable
from .report import excel_bytes, html_report
from .presentation import CSS, cases, select_rows, display_frame, stage_cards, SUMMARY_COLUMNS, SETTLEMENT_COLUMNS


def render_result(result):
    import streamlit as st
    options=['همه ثبت سفارش‌ها']+cases(result)
    # State is validated against the new publication before widgets are created.
    if st.session_state.get('fin_case') not in options:st.session_state.pop('fin_case',None)
    c1,c2=st.columns([3,1])
    selected=c1.selectbox('کد ثبت سفارش',options,key='fin_case')
    selected='' if selected==options[0] else selected
    summary=result.get('summary',pd.DataFrame())
    currencies=sorted(set(summary.get('currency',pd.Series(dtype=str)).dropna().astype(str)))
    curopts=['همه ارزها']+currencies
    if st.session_state.get('fin_currency_filter') not in curopts:st.session_state.pop('fin_currency_filter',None)
    currency=c2.selectbox('ارز اصلی سند',curopts,key='fin_currency_filter')
    currency='' if currency==curopts[0] else currency
    ev=select_rows(result.get('events'),selected,currency)
    ms=select_rows(result.get('measurements'),selected,currency)
    obs=select_rows(result.get('observations'),selected,currency)
    a,b,c,d=st.columns(4)
    a.metric('ثبت سفارش در محدوده',len(cases({'events':ev,'measurements':ms,'observations':obs})))
    b.metric('رویداد پذیرفته‌شده',len(ev));c.metric('مانده مشاهده‌شده',len(ms));d.metric('شاهد نیازمند تکمیل',len(obs))
    flow,settlement,evidence,quality=st.tabs(['جریان وجوه','رفع تعهد و تطبیق','اسناد و منشأ','کنترل‌های کیفیت'])
    def table(key,columns=None):
        df=select_rows(result.get(key),selected,currency)
        if df.empty:st.info('شاهد قابل نمایش در این محدوده وجود ندارد؛ این پیام به معنی انجام‌نشدن مرحله نیست.')
        else:st.dataframe(display_frame(df,columns),hide_index=True,width='stretch')
    with flow:
        st.subheader('مسیر وجوه در یک نگاه')
        # همان Process Explorer آفلاینِ بستهٔ فلوچارت، روی شواهد Cash Flow واقعی.
        # این نما صرفاً projection است و هیچ event/link جدیدی نمی‌سازد.
        try:
            import streamlit.components.v1 as components
            from .process_design import build_cashflow_process_html
            components.html(build_cashflow_process_html(result=result, instance_id='cashflow_streamlit', compact=True),
                            height=980, scrolling=True)
        except Exception:
            logging.getLogger(__name__).exception('Cashflow process explorer render failed')
            st.warning('نقشهٔ فرآیند قابل رندر نبود؛ جدول‌های شاهد همچنان در دسترس‌اند.')
        if selected:
            chain=select_rows(result.get('chain'),selected)
            st.caption('مراحل در سطح ثبت سفارش‌اند؛ مبالغ هر ارز جدا نمایش داده می‌شود.')
            st.markdown(stage_cards(chain),unsafe_allow_html=True)
        else:st.caption('برای دیدن مراحل و شکاف‌های یک پرونده، کد ثبت سفارش را انتخاب کنید.')
        st.caption('دانه جدول: کد ثبت سفارش × ارز. مبلغ ارزهای مختلف با هم جمع نمی‌شود.')
        table('summary',SUMMARY_COLUMNS)
        with st.expander('جریان ماهانه و ارتباط‌های مستند'):
            table('periods');table('links')
    with settlement:
        st.subheader('تعهد، رفع مستند و مانده سامانه')
        st.markdown('<div class="fin-note">مانده سامانه یک مشاهده است، نه تراکنش. کاهش مانده یا مانده صفر، به‌تنهایی سند رفع تعهد نیست. «—» یعنی نامعلوم.</div>',unsafe_allow_html=True)
        table('summary',SETTLEMENT_COLUMNS)
        st.markdown('**تطبیق با مانده گزارش‌شده در منبع**')
        table('reconciliation',['case_id','currency','reported_value','ledger_value','variance','status','observed_at','source','document'])
        with st.expander('مهلت‌ها و اسناد رفع / عودت تعهد'):
            table('deadlines');table('measurements')
    with evidence:
        st.caption('شناسه ثبت سفارش، مرجع سفارش و بارنامه ستون‌های جدا دارند. انتخاب پرونده از روی شباهت عددی انجام نمی‌شود.')
        table('events',['case_id','order_id','bl_id','kind','date','amount','currency','source','document','status'])
        with st.expander('شواهد نیازمند تکمیل و شناسه‌های ممیزی'):
            table('observations');table('events')
    with quality:
        st.caption('کنترل‌های این بخش مربوط به کل گزارش ساخته‌شده است؛ فیلتر پرونده موارد نامرتبط را پنهان نمی‌کند.')
        for key in ('issues','source_diagnostics'):
            df=result.get(key)
            if isinstance(df,pd.DataFrame) and not df.empty:st.dataframe(display_frame(df),hide_index=True,width='stretch')
        if result.get('issues',pd.DataFrame()).empty:st.success('در کنترل‌های اجراشده، موردی ثبت نشده است.')


def render(df,extras,ref_date):
    import streamlit as st
    st.markdown('<style>'+CSS+'</style>',unsafe_allow_html=True)
    st.markdown('<div class="fin-hero"><div class="fin-eyebrow">GSI / FINANCIAL WORKSPACE</div><h2>جریان وجوه و رفع تعهد</h2><p>از تخصیص تا پرداخت؛ هر مبلغ همراه با ارز، سند و منشأ آن.</p></div>',unsafe_allow_html=True)
    with st.expander('ورود اختیاری دفتر مستقل و تنظیمات گزارش',expanded=False):
        st.caption('گزارش عملیاتی با داده منتشرشده موجود ساخته می‌شود و به بارگذاری فایل جدید نیاز ندارد. ورود دستی، یک گزارش مستقل و با برچسب جدا می‌سازد.')
        source=st.file_uploader('دفتر مستقل Excel / CSV (اختیاری)',type=['xlsx','csv'],key='cashflow_input')
        rate_file=st.file_uploader('نرخ مستند برای ارزش‌گذاری اختیاری',type=['xlsx','csv'],key='cashflow_rates')
        lf=st.file_uploader('ارتباط‌های مستند دفتر مستقل (اختیاری)',type=['csv'],key='cashflow_links')
        target=st.selectbox('ارز ارزش‌گذاری اختیاری',['IRR','USD','EUR','CNY','AED'],key='cashflow_currency')
        st.caption('بدون نرخ تأییدشده، تبدیل ارز انجام نمی‌شود؛ گزارش در ارز اصلی سند قابل استفاده است.')
        st.download_button('قالب رویدادها',pd.DataFrame(columns=EVENT_COLUMNS).to_csv(index=False).encode('utf-8-sig'),'Events.csv','text/csv',key='cashflow_template',on_click='ignore')
        st.download_button('قالب مانده‌های سامانه',pd.DataFrame(columns=MEASUREMENT_COLUMNS).to_csv(index=False).encode('utf-8-sig'),'Measurements.csv','text/csv',key='cashflow_measurement_template',on_click='ignore')
    try:
        bundle=read_input(source) if source else bundle_from_dwh(ref_date,scope=df)
        if source:
            bundle['origin']='UPLOADED_LEDGER'
            if df is not None:
                keys={text(v) for col in ('KEY_REG','CANONICAL_REG') if col in df for v in df[col] if text(v)}
                for key in ('events','measurements'):
                    if key in bundle:bundle[key]=bundle[key].loc[bundle[key]['case_id'].map(text).isin(keys)].copy()
        rid=text(bundle.get('warehouse_run_id'))
        st.caption(f"منبع: {'دفتر مستقل بارگذاری‌شده' if source else 'داده منتشرشده سامانه'} · اجرای مبنا: {rid or 'منتشر نشده'} · تاریخ گزارش: {ref_date}")
        if not source and bundle.get('scope_status')=='EMPTY_OR_UNRESOLVED':
            st.warning('محدوده انتخاب‌شده ثبت سفارش قابل اتصال ندارد. برای رفع ابهام کل داده‌ها جایگزین این محدوده نمی‌شوند.')
        signature=sha256((repr(df.to_dict('list') if df is not None else None)+str(ref_date)+target+rid).encode()+b''.join(f.getvalue() for f in (source,rate_file,lf) if f is not None)).hexdigest()
        cached=st.session_state.get('cashflow_result')
        if cached and cached[0]!=signature:
            st.session_state.pop('cashflow_result',None);cached=None
        build=st.button('به‌روزرسانی گزارش',key='cashflow_build',type='primary')
        if build or cached is None:
            if rate_file:bundle['rates']=pd.read_csv(rate_file,dtype=str,keep_default_na=False) if rate_file.name.endswith('.csv') else import_reference_rates(rate_file)
            if lf and source:bundle['links']=pd.read_csv(lf,dtype=str,keep_default_na=False)
            elif lf:st.warning('ارتباط دستی فقط در دفتر مستقل اعمال می‌شود؛ روابط گزارش عملیاتی از شواهد سامانه می‌آید.')
            result=build_cashflow(bundle['events'],bundle.get('links'),bundle.get('rates'),as_of=ref_date,reporting_currency=target,rules=bundle.get('rules'),measurements=bundle.get('measurements'))
            result['meta'].update(input_origin=bundle.get('origin',''),warehouse_run_id=rid,
                                  scope_status=bundle.get('scope_status','UPLOADED_SCOPE'),source_priority=bundle.get('source_priority',''))
            result['source_diagnostics']=bundle.get('diagnostics',pd.DataFrame())
            x=excel_bytes(result);h=html_report(result,x)
            cached=(signature,result,x,h);st.session_state['cashflow_result']=cached
        _,result,x,h=cached
        if not cases(result):st.info('در اجرای منتشرشده، شواهد مالی قابل نمایش برای این محدوده موجود نیست. پوشش منابع و کنترل‌ها را بررسی کنید.')
        render_result(result)
        st.divider()
        st.caption('خروجی شامل کل محدوده گزارش ساخته‌شده است؛ انتخاب نمایشی پرونده، فایل ممیزی را ناقص نمی‌کند.')
        name='GSI_Finance_'+(rid[:12] or 'independent')+'_'+str(ref_date)
        a,b=st.columns(2)
        a.download_button('دریافت Excel کامل',x,name+'.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',key='cashflow_excel',on_click='ignore',width='stretch')
        b.download_button('دریافت گزارش تعاملی',h.encode(),name+'.html','text/html',key='cashflow_html',on_click='ignore',width='stretch')
    except FinancialSourceUnavailable:
        st.session_state.pop('cashflow_result',None)
        logging.getLogger(__name__).exception('Published financial source unavailable')
        st.error('منبع مالی منتشرشده قابل خواندن نیست. گزارش تازه ساخته نشد؛ سلامت پایگاه داده را بررسی کنید.')
    except (ValueError,KeyError,TypeError):
        st.session_state.pop('cashflow_result',None)
        logging.getLogger(__name__).exception('Financial report input contract failed')
        st.error('ساخت گزارش به علت ناسازگاری داده متوقف شد. جزئیات در لاگ ثبت شده است.')
