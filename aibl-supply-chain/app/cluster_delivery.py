"""Shared delivery UI: identical templates in the control center and main export tab."""
import streamlit as st
from gsi.control_center.core import LEVELS,KINDS,render_report,save_report,outlook_draft
from gsi.warehouse.store import Warehouse

def render(cfg,prefix):
    people={p['employee_code']:p for p in cfg['people'] if p['active']}
    clusters={c['id']:c for c in cfg['clusters'] if c['active']}
    members=[m for m in cfg['memberships'] if m['active'] and m['employee_code'] in people and m['cluster_id'] in clusters]
    if not members:
        st.info('مخاطب دارای عضویت فعال وجود ندارد. در مرکز مخاطبان، فایل اکسل و کلاستر مقصد را ثبت کنید.');return
    index=st.selectbox('مخاطب / کلاستر / سطح',range(len(members)),format_func=lambda i:f"{people[members[i]['employee_code']]['name']} / {clusters[members[i]['cluster_id']]['name']} / {LEVELS[members[i]['level']]}",key=prefix+'_member')
    member=members[index];kind=st.selectbox('نوع گزارش کلاستر',list(KINDS),format_func=lambda k:KINDS[k],key=prefix+'_kind')
    with Warehouse().db() as c:latest=c.execute("SELECT run_id FROM wh_current WHERE slot='report'").fetchone()
    signature=(cfg['revision'],member['employee_code'],member['cluster_id'],kind,latest)
    cachekey=prefix+'_report'
    if st.button('ساخت HTML با قالب و ویجت‌های کلاستر',key=prefix+'_build'):
        try:st.session_state[cachekey]=(signature,render_report(cfg,member['employee_code'],member['cluster_id'],kind))
        except Exception as ex:st.error(str(ex))
    cached=st.session_state.get(cachekey)
    if cached and cached[0]==signature:
        bundle=cached[1]
        st.write('گیرنده: '+bundle['email']);st.write('موضوع: '+bundle['subject'])
        import streamlit.components.v1 as components
        components.html(bundle['html'],height=620,scrolling=True)
        st.download_button('دریافت HTML کلاستر',bundle['html'],file_name=f"{member['employee_code']}_{member['cluster_id']}_{kind}.html",mime='text/html',key=prefix+'_download')
        if st.button('ذخیره در پوشه مخاطب',key=prefix+'_save'):
            try:st.success(str(save_report(bundle)))
            except Exception as ex:st.error(str(ex))
        if st.button('ساخت پیش‌نویس Outlook',key=prefix+'_draft'):
            try:outlook_draft(bundle);st.success('پیش‌نویس آماده شد؛ ارسال نشده است.')
            except Exception as ex:st.error(str(ex))
