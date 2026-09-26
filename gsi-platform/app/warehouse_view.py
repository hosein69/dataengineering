"""Operator-only data warehouse room, available even when a required source is absent."""
from pathlib import Path
import tempfile
import pandas as pd
import streamlit as st
from gsi.warehouse.store import Warehouse

def run():
    st.title('دیتاورهوس و تاریخچه داده')
    st.caption('نسخه‌های ورودی، داده استاندارد، خطاها و گزارش‌های ثبت‌شده؛ آخرین اجرای ناموفق جایگزین گزارش موفق نمی‌شود.')
    wh=Warehouse(); st.code(str(wh.path))
    c1,c2=st.columns([1,2])
    with c1:
        if st.button('▶ واکشی سورس‌ها + Build کامل DWH',type='primary',width="stretch"):
            try:
                from gsi.pipeline import Pipeline
                with st.spinner('در حال واکشی، اعتبارسنجی، ساخت Core/Mart و Quality Gate…'):
                    r=Pipeline().run(build_report=True)
                st.success(f"Run موفق: {r.extras.get('warehouse_run_id','')[:12]}")
                st.cache_data.clear()
            except Exception as ex:
                st.error(f'Run منتشر نشد: {ex}')
    with c2:
        st.caption('Publish فقط بعد از Grain/Schema/FK/Integrity Gate انجام می‌شود؛ Run ناموفق current را جابه‌جا نمی‌کند.')
    imports,history,quality,profiler,data,issues,backup,historical=st.tabs(['ورود فایل','اجراها و تطبیق ردیف‌ها','کیفیت و قراردادها','پروفایل سورس','داده ذخیره‌شده','خطاها و لاگ','پشتیبان','تحلیل تاریخی V26'])
    with imports:
        source=st.selectbox('نوع منبع',['oracle','ntsw','fx_transaction','headers_map'])
        file=st.file_uploader('فایل اکسل',type=['xlsx','xlsm'],key='warehouse_input')
        if st.button('ثبت نسخه در دیتاورهوس',disabled=file is None):
            from gsi.warehouse.service import ingest_file
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    path=Path(tmp)/Path(file.name).name;path.write_bytes(file.getvalue())
                    rid,fid=ingest_file(path,source)
                st.success('نسخه ورودی و داده‌های قابل پردازش ثبت شد. این عملیات به‌تنهایی گزارش جامع را بازسازی نمی‌کند.')
                st.code(rid)
            except Exception as ex:st.error(str(ex))
    with history:
        with wh.read_db() as c:
            st.dataframe(pd.read_sql_query('SELECT * FROM wh_run ORDER BY started DESC LIMIT 100',c),hide_index=True)
            st.dataframe(pd.read_sql_query('SELECT * FROM wh_source_reconciliation ORDER BY id DESC LIMIT 300',c),hide_index=True)

    with quality:
        st.subheader('Reliability Gate / قرارداد Grain و Schema')
        st.caption('شاخه خراب تا حد ممکن قرنطینه می‌شود و Run برای تشخیص ادامه می‌یابد؛ فقط خطای ساختاری/بحرانی Publish را متوقف می‌کند. WARN/DEGRADED دیده می‌شوند اما کل فرآیند را نمی‌خوابانند.')
        with wh.read_db() as c:
            runs=pd.read_sql_query("SELECT id,started,finished,status,error FROM wh_run ORDER BY started DESC LIMIT 50",c)
        if runs.empty:
            st.info('هنوز Run ثبت نشده است.')
        else:
            rid=st.selectbox('Run برای ممیزی',runs['id'].tolist(),format_func=lambda x: x[:12])
            with wh.read_db() as c:
                q=pd.read_sql_query('SELECT contract,code,severity,passed,detail FROM wh_quality_check WHERE run_id=? ORDER BY seq',c,params=(rid,))
                cur=pd.read_sql_query('SELECT slot,run_id FROM wh_current ORDER BY slot',c)
            if q.empty: st.warning('این Run قدیمی است و Quality Gate جدید برای آن ثبت نشده است.')
            else:
                bad=q[q['passed']==0]
                c1,c2,c3,c4=st.columns(4)
                c1.metric('بحرانی / مسدودکننده',int(bad['severity'].isin(['BLOCK','CRITICAL','FATAL']).sum()))
                c2.metric('شاخه ناقص',int((bad['severity']=='DEGRADED').sum()))
                c3.metric('هشدار',int((bad['severity']=='WARN').sum()))
                c4.metric('کل کنترل‌ها',len(q))
                stale=bad[bad['code'].eq('STALE_FALLBACK_USED')]
                if not stale.empty:
                    st.warning(f'{len(stale)} سورس با آخرین Snapshot منتشرشده ادامه یافته است؛ این داده هرگز به‌عنوان تازه نمایش داده نمی‌شود.')
                st.dataframe(q,hide_index=True,width="stretch")
            st.caption('Pointerهای جاری باید به یک Run سالم اشاره کنند.')
            st.dataframe(cur,hide_index=True,width="stretch")

    with wh.read_db() as c:
        has_business=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='dwh_relation'").fetchone()
    if has_business:
        with st.expander('نقشه بیزینس و Relation Explorer',expanded=False):
            with wh.read_db() as c:
                dims=pd.read_sql_query("SELECT entity_type,count(*) AS n FROM dwh_entity GROUP BY entity_type ORDER BY entity_type",c)
                rel=pd.read_sql_query("SELECT left_type,right_type,source,frame,count(*) AS evidence_links FROM dwh_relation GROUP BY left_type,right_type,source,frame ORDER BY evidence_links DESC LIMIT 300",c)
                unresolved=pd.read_sql_query("SELECT run_id,source,frame,reason_code,count(*) AS n FROM dwh_unresolved_relation GROUP BY run_id,source,frame,reason_code ORDER BY n DESC LIMIT 200",c)
                hub=pd.read_sql_query("SELECT * FROM dwh_registration_hub LIMIT 500",c)
                has_ompi=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='dwh_bridge_order_material_pr_item'").fetchone()
                ompi=(pd.read_sql_query("SELECT order_key,material_key,pr_key,pr_item,evidence_count,source_rows,last_seen_run FROM dwh_bridge_order_material_pr_item ORDER BY order_key,material_key,pr_key,pr_item LIMIT 1000",c)
                      if has_ompi else pd.DataFrame())
            st.markdown('**Dimensions / Entities**'); st.dataframe(dims,hide_index=True,width="stretch")
            st.caption('As-of DWH run: ' + str(wh.current_run('dwh') or 'No published evidence'))
            st.markdown('**Direct-evidence bridges**'); st.dataframe(rel,hide_index=True,width="stretch")
            st.markdown('**Registration Hub — REG_FILE ≠ REG**'); st.dataframe(hub,hide_index=True,width="stretch")
            if not ompi.empty:
                st.markdown('**Order × Material × PR × PR Item — رابطه خرید بدون گم‌شدن PR**')
                st.caption('ردیف‌های خام تکراری حذف نمی‌شوند؛ در این Bridge به یک رابطه بیزینسی با evidence_count و source_rows تبدیل می‌شوند.')
                st.dataframe(ompi,hide_index=True,width="stretch")
            if not unresolved.empty:
                st.markdown('**Unresolved relations**'); st.dataframe(unresolved,hide_index=True,width="stretch")

    with profiler:
        st.subheader('Source Profiler — هدر و چند ردیف خام')
        st.caption('برای تشخیص تغییر ساختار، هدر واقعی و ردیف‌های فیزیکی Raw/Bronze همان نسخه فایل نمایش داده می‌شود.')
        from gsi.warehouse.store import loads
        with wh.read_db() as c:
            sheets=c.execute('''SELECT s.file_id,f.name,s.name,s.metadata
                                FROM wh_sheet s JOIN wh_file f ON f.id=s.file_id
                                ORDER BY f.created DESC,s.name LIMIT 500''').fetchall()
        if not sheets:
            st.info('هنوز Raw sheet ثبت نشده است.')
        else:
            chosen=st.selectbox('فایل / شیت',sheets,format_func=lambda r:f'{r[1]} | {r[2]} | {r[0][:10]}')
            fid,fname,sh,meta=chosen
            try:
                md=loads(meta)
            except Exception:
                md={}
            st.json(md,expanded=False)
            with wh.read_db() as c:
                rows=c.execute('SELECT row_no,payload FROM wh_raw_row WHERE file_id=? AND sheet=? ORDER BY row_no LIMIT 8',(fid,sh)).fetchall()
            decoded=[]
            for rn,payload in rows:
                try:
                    obj=loads(payload)
                except Exception:
                    obj=payload
                decoded.append({'_SOURCE_ROW':rn,'RAW':obj})
            st.dataframe(pd.DataFrame(decoded),hide_index=True,width="stretch")

    with data:
        from gsi.warehouse.marts import totals
        with wh.read_db() as c: files=c.execute("SELECT DISTINCT i.file_id,f.name FROM wh_ingest i JOIN wh_file f ON f.id=i.file_id WHERE i.source IN ('fx_transaction','ntsw') ORDER BY i.id DESC").fetchall()
        if files:
            chosen_file=st.selectbox('جمع مبالغ به تفکیک ارز و نسخه فایل',files,format_func=lambda r:r[1]+' | '+r[0][:12])
            st.dataframe(pd.DataFrame(totals(chosen_file[0])),hide_index=True)
            st.caption('جمع مبالغ با Decimal محاسبه می‌شود؛ ارزها، انواع مبلغ و نسخه‌های فایل با یکدیگر جمع نمی‌شوند.')
        with wh.read_db() as c: frames=c.execute('SELECT id,layer,name,row_count,created FROM wh_frame ORDER BY created DESC LIMIT 300').fetchall()
        if frames:
            choice=st.selectbox('جدول و نسخه',frames,format_func=lambda r:f'{r[2]} | {r[1]} | {r[3]} ردیف | {r[4]}')
            df=wh.read_frame(choice[0]);st.dataframe(df,hide_index=True)
            st.download_button('دریافت جدول CSV',df.to_csv(index=False).encode('utf-8-sig'),file_name='warehouse_' + choice[0] + '.csv', key='warehouse_csv_' + choice[0], on_click='ignore')
        else:st.info('هنوز جدولی ثبت نشده است.')
    with issues:
        with wh.read_db() as c:
            st.dataframe(pd.read_sql_query('SELECT * FROM wh_issue ORDER BY id DESC LIMIT 300',c),hide_index=True)
            st.dataframe(pd.read_sql_query('SELECT * FROM wh_audit ORDER BY id DESC LIMIT 300',c),hide_index=True)
    with backup:
        st.caption('پشتیبان سازگار ابتدا روی دیسک محلی ساخته می‌شود؛ پس از دانلود می‌توانید آن را در فولدر شبکه نگه دارید.')
        if st.button('آماده‌سازی پشتیبان SQLite'):
            with tempfile.TemporaryDirectory() as tmp:
                p=wh.backup(Path(tmp)/'warehouse_backup.sqlite')
                st.session_state['warehouse_backup_bytes'] = p.read_bytes()
        if 'warehouse_backup_bytes' in st.session_state:
            st.download_button('دریافت پشتیبان',st.session_state['warehouse_backup_bytes'],file_name='warehouse_backup.sqlite',key='warehouse_backup_download',on_click='ignore')

    with historical:
        st.caption('لایه سازگاری V26.17/18 برای روند KPI، Timeline پرونده، Transition و Audit تاریخی؛ مستقل از Warehouse اصلی V28.')
        try:
            from gsi.warehouse.historical_store import warehouse_from_settings
            from app.historical_warehouse_view import render as render_historical
            render_historical(warehouse_from_settings())
        except Exception as ex:
            st.error(f'Historical Warehouse: {ex}')
