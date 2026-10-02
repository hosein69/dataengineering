"""Operator-only data warehouse room, available even when a required source is absent."""
from pathlib import Path
from datetime import datetime, timezone
import json
import tempfile
import zipfile
import pandas as pd
import streamlit as st
from gsi.warehouse.store import Warehouse

#: نام فارسی نوع رویدادهای دفتر تغییرات و علت آن‌ها
CHANGE_KIND_FA = {'baseline':'خط مبنا','new':'ردیف تازه','changed':'تغییر','gone':'دیده نشد','back':'برگشت',
                  'schema':'تغییر ساختار','rekey':'بازتعریف کلید'}
CHANGE_CAUSE_FA = {'data':'داده منبع','program':'برنامه یا تنظیمات','data+program':'داده و برنامه','unknown':'نامعلوم'}
LOAD_MODE_FA = {'parsed':'خوانده شد','reused':'بدون تغییر؛ از بایگانی','missing':'فایلی پیدا نشد'}


def _file_names(text):
    try:
        return '، '.join(str(x.get('name','')) for x in json.loads(text or '[]')) or '—'
    except Exception:
        return '—'


def _backup_zip(dest):
    """فایل SQLite پشتیبان و پوشه بایگانی کنارش در یک ZIP (شیءها از قبل فشرده‌اند)."""
    target=dest.with_suffix('.zip')
    objects=dest.with_name(dest.name+'.objects')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as zf:
        zf.write(dest,arcname=dest.name)
        if objects.is_dir():
            for path in sorted(objects.rglob('*')):
                if path.is_file():
                    zf.write(path,arcname=str(Path(objects.name)/path.relative_to(objects)))
    return target

def run():
    st.title('دیتاورهوس و تاریخچه داده')
    st.caption('نسخه‌های ورودی، داده استاندارد، خطاها و گزارش‌های ثبت‌شده؛ آخرین اجرای ناموفق جایگزین گزارش موفق نمی‌شود.')
    wh=Warehouse(); st.code(str(wh.path))
    c1,c2=st.columns([1,2])
    with c1:
        if st.button('▶ بارفرش انبار داده (فقط فایل‌های تغییرکرده دوباره خوانده می‌شوند)',type='primary',width="stretch"):
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
    imports,history,changes,quality,profiler,data,issues,backup,historical=st.tabs(['ورود فایل','اجراها و دفتر فایل‌ها','تغییرات','کیفیت و قراردادها','پروفایل سورس','داده ذخیره‌شده','خطاها و لاگ','پشتیبان','تحلیل تاریخی V26'])
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
            runs_all=pd.read_sql_query('SELECT seq,id,started,finished,status,error,timings FROM wh_run ORDER BY seq DESC LIMIT 100',c)
        st.dataframe(runs_all,hide_index=True,width="stretch")
        if not runs_all.empty:
            st.markdown('**دفتر فایل‌ها — هر سورس در هر اجرا**')
            st.caption('«بدون تغییر؛ از بایگانی» یعنی فایل‌ها، برنامه و تنظیمات همان اجرای قبلی بودند و خروجی بایگانی‌شده همان اجرا بدون خواندن دوباره به کار رفت.')
            pick=st.selectbox('اجرا',runs_all.index,format_func=lambda i:f"#{runs_all.seq[i]} · {str(runs_all.started[i])[:16]} · {runs_all.status[i]}",key='wh_ledger_run')
            with wh.read_db() as c:
                ledger=pd.read_sql_query('SELECT source,mode,reused_run,seconds,files FROM wh_source_load WHERE run_id=? ORDER BY source',c,params=(runs_all.id[pick],))
            if ledger.empty:
                st.info('برای این اجرا بارگذاری سورسی ثبت نشده است.')
            else:
                ledger=pd.DataFrame({'سورس':ledger['source'],'وضعیت':ledger['mode'].map(lambda m:LOAD_MODE_FA.get(m,m)),
                                     'اجرای مبدأ':ledger['reused_run'].fillna('').str[:12],'ثانیه':ledger['seconds'],
                                     'فایل‌ها':ledger['files'].map(_file_names)})
                st.dataframe(ledger,hide_index=True,width="stretch")
        with wh.read_db() as c:
            st.dataframe(pd.read_sql_query('SELECT * FROM wh_source_reconciliation ORDER BY id DESC LIMIT 300',c),hide_index=True)

    with changes:
        st.caption('هر بارفرش فقط تفاوت‌ها را ثبت می‌کند: ردیف تازه، فیلد تغییرکرده با مقدار قبلی و جدید، ردیفی که دیگر دیده نشد و ردیفی که برگشت. '
                   'جابه‌جایی ردیف در فایل یا ذخیره دوباره فایل بدون تغییر محتوا، تغییر حساب نمی‌شود. هیچ سابقه‌ای پاک نمی‌شود.')
        with wh.read_db() as c:
            runs_ch=pd.read_sql_query("SELECT r.seq,r.id,r.started,r.status,"
                                      "(SELECT count(*) FROM src_change x WHERE x.seq=r.seq AND x.field IS NULL AND x.kind<>'baseline') AS n "
                                      "FROM wh_run r ORDER BY r.seq DESC LIMIT 200",c)
        if runs_ch.empty:
            st.info('هنوز اجرایی ثبت نشده است.')
        else:
            pick=st.selectbox('اجرا',runs_ch.index,format_func=lambda i:f"#{runs_ch.seq[i]} · {str(runs_ch.started[i])[:16]} · {runs_ch.status[i]} · {runs_ch.n[i]} رویداد",key='wh_changes_run')
            seq=int(runs_ch.seq[pick])
            with wh.read_db() as c:
                summary=pd.read_sql_query('SELECT source,frame,kind,cause,count(*) AS n FROM src_change WHERE seq=? AND field IS NULL '
                                          'GROUP BY source,frame,kind,cause ORDER BY source,frame,kind',c,params=(seq,))
                fields=pd.read_sql_query('SELECT source,frame,rkey,occ,field,old,new FROM src_change WHERE seq=? AND field IS NOT NULL '
                                         'ORDER BY source,frame,rkey,occ,field LIMIT 5000',c,params=(seq,))
            if summary.empty:
                st.success('در این اجرا هیچ ردیف منبعی تغییر نکرد.')
            else:
                st.dataframe(pd.DataFrame({'سورس':summary['source'],'فریم':summary['frame'],
                                           'رویداد':summary['kind'].map(lambda k:CHANGE_KIND_FA.get(k,k)),
                                           'علت':summary['cause'].map(lambda k:CHANGE_CAUSE_FA.get(k,k)),'تعداد':summary['n']}),
                             hide_index=True,width="stretch")
            if not fields.empty:
                st.markdown('**فیلدهای تغییرکرده**')
                st.caption('کلید ردیف همان کلیدی است که برای هر فریم در gsi/config/source_keys.yaml تعریف شده؛ مقدارها به شکل متعارف ذخیره می‌شوند.')
                st.dataframe(fields.rename(columns={'source':'سورس','frame':'فریم','rkey':'کلید ردیف','occ':'تکرار',
                                                    'field':'فیلد','old':'مقدار قبلی','new':'مقدار جدید'}),
                             hide_index=True,width="stretch")
            with wh.read_db() as c:
                tracked=c.execute('SELECT source,frame,rows FROM src_frame_state ORDER BY source,frame').fetchall()
            if tracked:
                st.markdown('**محتوای یک فریم به تاریخ همین اجرا**')
                chosen=st.selectbox('فریم',tracked,format_func=lambda r:f'{r[0]}/{r[1]} · {r[2]:,} ردیف جاری',key='wh_asof_frame')
                if st.button('نمایش وضعیت فریم در این اجرا',key='wh_asof_show'):
                    from gsi.warehouse.history import frame_as_of
                    with wh.read_db() as c:
                        asof=frame_as_of(c,chosen[0],chosen[1],seq,with_location=True)
                    st.caption(f'{len(asof):,} ردیف؛ ستون‌های جای ردیف همان جایی است که این نسخه اولین بار دیده شد.')
                    st.dataframe(asof,hide_index=True,width="stretch")

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
            from gsi.warehouse.excel import _load_archived_rows
            try:
                rows=_load_archived_rows(wh,fid,sh)[:8]
            except Exception as ex:
                rows=[]
                st.warning(f'بایگانی خانه‌های این کاربرگ خوانده نشد: {ex}')
            st.dataframe(pd.DataFrame([{'_SOURCE_ROW':r.get('row') if isinstance(r,dict) else None,'RAW':r} for r in rows]),
                         hide_index=True,width="stretch")

    with data:
        from gsi.warehouse.marts import totals
        with wh.read_db() as c: files=c.execute("SELECT DISTINCT i.file_id,f.name FROM wh_ingest i JOIN wh_file f ON f.id=i.file_id WHERE i.source IN ('fx_transaction','ntsw') ORDER BY i.id DESC").fetchall()
        if files:
            chosen_file=st.selectbox('جمع مبالغ به تفکیک ارز و نسخه فایل',files,format_func=lambda r:r[1]+' | '+r[0][:12])
            st.dataframe(pd.DataFrame(totals(chosen_file[0])),hide_index=True)
            st.caption('جمع مبالغ با Decimal محاسبه می‌شود؛ ارزها، انواع مبلغ و نسخه‌های فایل با یکدیگر جمع نمی‌شوند. '
                       'مبلغی که ارزش کد شناخته‌شده ندارد («نامشخص»، «حواله») و درخواست تخصیص رد، باطل یا بسته‌شده '
                       'در جمع نمی‌آیند و فقط شمرده می‌شوند.')
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
        st.caption('پشتیبان سازگار روی دیسک محلی، کنار انبار داده، ساخته می‌شود: فایل SQLite و پوشه بایگانی (فایل‌های منبع و فریم‌ها). '
                   'شیءهای بایگانی تغییرناپذیرند و تا جای ممکن hardlink می‌شوند، پس پشتیبان تقریباً جای تازه نمی‌گیرد. '
                   'برای نگه‌داری در فولدر شبکه، ZIP را دریافت کنید.')
        if st.button('ساخت پشتیبان کامل'):
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            dest=wh.path.parent/'backups'/f'warehouse_{stamp}.sqlite'
            try:
                with st.spinner('در حال ساخت پشتیبان…'):
                    made=wh.backup(dest)
                st.session_state['warehouse_backup_path']=str(made)
                st.success(f'پشتیبان ساخته شد: {made}')
            except Exception as ex:
                st.error(f'پشتیبان ساخته نشد: {ex}')
        made=st.session_state.get('warehouse_backup_path')
        if made and Path(made).exists():
            if st.button('آماده‌سازی ZIP برای دریافت'):
                with st.spinner('در حال ساخت ZIP…'):
                    st.session_state['warehouse_backup_zip']=str(_backup_zip(Path(made)))
            zpath=st.session_state.get('warehouse_backup_zip')
            if zpath and Path(zpath).exists():
                size=Path(zpath).stat().st_size
                if size>1_500_000_000:
                    st.warning(f'ZIP پشتیبان {size/1e9:.1f} گیگابایت است؛ آن را مستقیم از این مسیر کپی کنید: {zpath}')
                else:
                    st.download_button('دریافت پشتیبان (ZIP)',Path(zpath).read_bytes(),file_name=Path(zpath).name,
                                       key='warehouse_backup_download',on_click='ignore')

    with historical:
        st.caption('لایه سازگاری V26.17/18 برای روند KPI، Timeline پرونده، Transition و Audit تاریخی؛ مستقل از Warehouse اصلی V28.')
        try:
            from gsi.warehouse.historical_store import warehouse_from_settings
            from app.historical_warehouse_view import render as render_historical
            render_historical(warehouse_from_settings())
        except Exception as ex:
            st.error(f'Historical Warehouse: {ex}')
