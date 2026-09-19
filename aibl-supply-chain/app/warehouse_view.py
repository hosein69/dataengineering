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
    imports,history,data,issues,backup=st.tabs(['ورود فایل','اجراها و تطبیق ردیف‌ها','داده ذخیره‌شده','خطاها و لاگ','پشتیبان'])
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
        with wh.db() as c:
            st.dataframe(pd.read_sql_query('SELECT * FROM wh_run ORDER BY started DESC LIMIT 100',c),hide_index=True)
            st.dataframe(pd.read_sql_query('SELECT * FROM wh_source_reconciliation ORDER BY id DESC LIMIT 300',c),hide_index=True)
    with data:
        from gsi.warehouse.marts import totals
        with wh.db() as c: files=c.execute("SELECT DISTINCT i.file_id,f.name FROM wh_ingest i JOIN wh_file f ON f.id=i.file_id WHERE i.source IN ('fx_transaction','ntsw') ORDER BY i.id DESC").fetchall()
        if files:
            chosen_file=st.selectbox('جمع مبالغ به تفکیک ارز و نسخه فایل',files,format_func=lambda r:r[1]+' | '+r[0][:12])
            st.dataframe(pd.DataFrame(totals(chosen_file[0])),hide_index=True)
            st.caption('جمع مبالغ با Decimal محاسبه می‌شود؛ ارزها، انواع مبلغ و نسخه‌های فایل با یکدیگر جمع نمی‌شوند.')
        with wh.db() as c: frames=c.execute('SELECT id,layer,name,row_count,created FROM wh_frame ORDER BY created DESC LIMIT 300').fetchall()
        if frames:
            choice=st.selectbox('جدول و نسخه',frames,format_func=lambda r:f'{r[2]} | {r[1]} | {r[3]} ردیف | {r[4]}')
            df=wh.read_frame(choice[0]);st.dataframe(df,hide_index=True)
            st.download_button('دریافت جدول CSV',df.to_csv(index=False).encode('utf-8-sig'),file_name='warehouse_table.csv')
        else:st.info('هنوز جدولی ثبت نشده است.')
    with issues:
        with wh.db() as c:
            st.dataframe(pd.read_sql_query('SELECT * FROM wh_issue ORDER BY id DESC LIMIT 300',c),hide_index=True)
            st.dataframe(pd.read_sql_query('SELECT * FROM wh_audit ORDER BY id DESC LIMIT 300',c),hide_index=True)
    with backup:
        st.caption('پشتیبان سازگار ابتدا روی دیسک محلی ساخته می‌شود؛ پس از دانلود می‌توانید آن را در فولدر شبکه نگه دارید.')
        if st.button('آماده‌سازی پشتیبان SQLite'):
            with tempfile.TemporaryDirectory() as tmp:
                p=wh.backup(Path(tmp)/'warehouse_backup.sqlite')
                st.download_button('دریافت پشتیبان',p.read_bytes(),file_name='warehouse_backup.sqlite')
