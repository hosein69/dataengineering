"""Operator-only Streamlit audience/source control center."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from gsi.control_center.core import (CenterStore, LEVELS, KINDS, WIDGETS, FIELDS,
    SOURCE_KINDS, REQUIRED, OPTIONAL, default_cluster, ident, emp, active,
    read_source, preview_import, commit_import, render_report, save_report, outlook_draft)


def run():
    st.title('مرکز مخاطبان، کلاسترها و منابع')
    st.caption('محیط اپراتور اتاق کنترل؛ اطلاعات شخصی و دامنه دسترسی از Snapshot منتشرشده خوانده می‌شود.')
    store=CenterStore()
    try: cfg=store.load()
    except Exception as ex:
        st.error(f'تنظیمات خوانده نشد؛ فایل موجود جایگزین نشد: {ex}');return
    st.caption(f'نسخه تنظیمات: {cfg["revision"]} | محل: {store.root}')
    if st.button('تازه‌سازی تنظیمات',key='cc_refresh'): st.rerun()
    clusters, people, memberships, sources, reports, history=st.tabs([
        'کلاستر و قالب', 'افراد و ایمیل‌ها', 'عضویت و سطح', 'منابع و نگاشت', 'پیش‌نمایش و خروجی', 'سابقه و پشتیبان'])

    def persist(candidate):
        try:
            store.save(candidate,cfg['revision']);st.success('تنظیمات ذخیره شد.');st.rerun()
        except Exception as ex: st.error(str(ex))

    with clusters:
        choices=['__new__']+[c['id'] for c in cfg['clusters']]
        names={c['id']:c['name'] for c in cfg['clusters']}
        selected=st.selectbox('کلاستر',choices,format_func=lambda x:names.get(x,'ایجاد کلاستر جدید'))
        current=next((c for c in cfg['clusters'] if c['id']==selected),default_cluster('new_cluster','کلاستر جدید'))
        if selected != '__new__':
            directory={p['employee_code']:p for p in cfg['people']}
            grouped=[]
            for member in cfg['memberships']:
                if member['cluster_id']==selected:
                    person=directory.get(member['employee_code'],{})
                    grouped.append({'کد':member['employee_code'],'نام و نام خانوادگی':person.get('name',''),'مدیریت':person.get('management',''),'اداره':person.get('department',''),
                        'ایمیل':person.get('email',''),'سطح':LEVELS[member['level']],
                        'فعال':member['active'] and person.get('active',False)})
            st.caption('گیرندگان دسته‌بندی‌شده این کلاستر')
            st.dataframe(pd.DataFrame(grouped),use_container_width=True)
        layer=st.selectbox('تنظیم برای', ['base']+list(LEVELS),format_func=lambda x:LEVELS.get(x,'قالب پایه کلاستر'))
        effective=copy.deepcopy(current)
        if layer!='base':effective.update(current.get('levels',{}).get(layer,{}))
        with st.form('cluster_form_'+selected+'_'+layer):
            cid=st.text_input('شناسه ثابت',current['id'],disabled=selected!='__new__' or layer!='base')
            name=st.text_input('نام کلاستر',current['name'],disabled=layer!='base')
            enabled=st.checkbox('کلاستر فعال',current['active'],disabled=layer!='base')
            header=st.text_input('سربرگ گزارش',effective['header'])
            color=st.color_picker('رنگ تأکیدی کلاستر',effective['color'])
            widgets=st.multiselect('ویجت‌ها به ترتیب نمایش',list(WIDGETS),default=effective['widgets'],format_func=lambda x:WIDGETS[x])
            tabs=st.text_area('تب‌ها و ستون‌ها — JSON قابل ویرایش',json.dumps(effective['tabs'],ensure_ascii=False,indent=2),height=210)
            st.caption('فیلدهای مجاز: '+', '.join(FIELDS+[k for src in cfg['sources'] for k in src.get('mapping',{}) if k.startswith('custom_')]))
            subject=st.text_input('موضوع ایمیل',effective['subject'])
            body=st.text_area('متن اختصاصی ایمیل',effective['body'])
            signature=st.text_area('امضا',effective['signature'])
            st.caption('متغیرها: {name} نام و نام خانوادگی، {management} مدیریت، {department} اداره، {position} جایگاه، {level} سطح، {cluster} کلاستر، {date} تاریخ، {report_type} نوع گزارش')
            submitted=st.form_submit_button('ذخیره قالب')
        if submitted:
            try:
                new=copy.deepcopy(cfg);c=copy.deepcopy(current)
                values=dict(header=header,color=color,widgets=widgets,tabs=json.loads(tabs),subject=subject,body=body,signature=signature)
                if layer=='base':c.update(values);c.update(id=ident(cid),name=name,active=enabled)
                else:c.setdefault('levels',{})[layer]=values
                if selected=='__new__':new['clusters'].append(c)
                else:new['clusters']=[c if x['id']==selected else x for x in new['clusters']]
                persist(new)
            except Exception as ex:st.error(str(ex))
        if layer!='base' and selected!='__new__' and st.button('حذف تنظیم اختصاصی این سطح و بازگشت به پایه'):
            new=copy.deepcopy(cfg)
            next(c for c in new['clusters'] if c['id']==selected).get('levels',{}).pop(layer,None)
            persist(new)

    with people:
        st.info('هر کد پرسنلی یک رکورد دارد. غیرفعال‌کردن فرد، تاریخچه و پوشه شخصی او را حذف نمی‌کند.')
        frame=pd.DataFrame(cfg['people'],columns=['employee_code','name','email','management','department','position','level','active'])
        with st.form('cc_people_form'):
            edited=st.data_editor(frame,num_rows='dynamic',hide_index=True,use_container_width=True,
                column_config={'employee_code':st.column_config.TextColumn('کد پرسنلی',required=True),
                    'name':'نام و نام خانوادگی','management':'مدیریت','department':'اداره','position':'جایگاه سازمانی','level':st.column_config.SelectboxColumn('سطح گزارش',options=list(LEVELS)), 'email':'ایمیل','active':st.column_config.CheckboxColumn('فعال',default=True)})
            save_people=st.form_submit_button('ذخیره افراد و ایمیل‌ها')
        if save_people:
            try:
                rows=edited.fillna('').to_dict('records')
                for row in rows:row['employee_code']=emp(row['employee_code']);row['active']=active(row['active']);row['email']=row['email'].strip().lower()
                new=copy.deepcopy(cfg);old_people={p['employee_code']:p for p in cfg['people']};new['people']=[dict(old_people.get(r['employee_code'],{}),**r) for r in rows];persist(new)
            except Exception as ex:st.error(str(ex))

    with memberships:
        st.caption('یک فرد می‌تواند در چند کلاستر عضو باشد؛ گزارش هر کلاستر جدا ساخته می‌شود. عضویت، دامنه داده را افزایش نمی‌دهد.')
        frame=pd.DataFrame(cfg['memberships'],columns=['employee_code','cluster_id','level','scope_employee_codes','active'])
        with st.form('cc_members_form'):
            edited=st.data_editor(frame,num_rows='dynamic',hide_index=True,use_container_width=True,column_config={
                'employee_code':st.column_config.SelectboxColumn('کد پرسنلی',options=[p['employee_code'] for p in cfg['people']],required=True),
                'cluster_id':st.column_config.SelectboxColumn('شناسه کلاستر',options=[c['id'] for c in cfg['clusters']],required=True),
                'level':st.column_config.SelectboxColumn('سطح',options=list(LEVELS),required=True),
                'scope_employee_codes':st.column_config.TextColumn('کدهای تحت پوشش — اختیاری، جدا با کاما'),
                'active':st.column_config.CheckboxColumn('فعال',default=True)})
            submitted=st.form_submit_button('ذخیره عضویت‌ها')
        if submitted:
            try:
                rows=edited.fillna('').to_dict('records')
                for row in rows:row['active']=active(row['active'])
                new=copy.deepcopy(cfg);new['memberships']=rows;persist(new)
            except Exception as ex:st.error(str(ex))

    with sources:
        from gsi.control_center.contacts import LABELS, suggest
        import io
        st.caption('فایل را انتخاب کنید؛ نگاشت پیشنهادی و مخاطبان پیش از ذخیره نمایش داده می‌شوند.')
        chosen=st.selectbox('منبع', ['__new__']+[x['id'] for x in cfg['sources']],key='cc_source')
        old=next((x for x in cfg['sources'] if x['id']==chosen),{})
        sid=st.text_input('شناسه منبع',old.get('id','contacts_01'),disabled=chosen!='__new__')
        kind=st.selectbox('نوع منبع',list(SOURCE_KINDS),index=list(SOURCE_KINDS).index(old.get('kind','contacts')),format_func=lambda x:SOURCE_KINDS[x])
        location=st.text_input('مسیر فایل در فولدر شبکه',old.get('path',''))
        upload=st.file_uploader('یا پیوست فایل اکسل / CSV',type=['xlsx','csv'],key='cc_source_file_'+chosen)
        blob=None
        try:
            if upload is not None: blob=upload.getvalue();filename=upload.name
            elif location:
                path=Path(location)
                if path.stat().st_size>20*1024*1024:raise ValueError('حداکثر اندازه فایل ۲۰ مگابایت است.')
                blob=path.read_bytes();filename=path.name
            if blob is not None:
                sheet=0
                if filename.lower().endswith('.xlsx'):
                    with pd.ExcelFile(io.BytesIO(blob)) as workbook:names=workbook.sheet_names
                    sheet=st.selectbox('شیت مخاطبان',names,index=names.index(old['sheet']) if old.get('sheet') in names else 0)
                df=read_source(blob,filename,sheet)
                st.dataframe(df.head(20),hide_index=True)
                guessed=suggest(df.columns);mapping={}
                for field in REQUIRED[kind]+OPTIONAL[kind]:
                    cols=['']+list(df.columns);prior=old.get('mapping',{}).get(field,guessed.get(field,''))
                    col=st.selectbox(LABELS.get(field,field)+(' — لازم' if field in REQUIRED[kind] else ' — اختیاری'),cols,index=cols.index(prior) if prior in cols else 0,key='map_'+chosen+'_'+kind+'_'+field)
                    if col:mapping[field]=col
                if kind=='contacts':
                    import re
                    extras=st.multiselect('ستون‌های اضافی قابل استفاده در قالب گزارش',[col for col in df.columns if col not in mapping.values()])
                    for col in extras:
                        key='custom_'+re.sub(r'[^\w]+','_',str(col)).strip('_')
                        if key in mapping:raise ValueError('نام دو ستون اضافی یکسان شده است؛ عنوان را اصلاح کنید.')
                        mapping[key]=col
                    if extras:st.caption('متغیرهای قالب: '+', '.join('{'+k+'}' for k in mapping if k.startswith('custom_')))
                st.caption('نام کامل یا هر دو ستون نام و نام خانوادگی لازم است. جایگاه اختیاری است؛ بدون آن، سطح گزارش کارشناس خواهد بود. نام‌های مدیریتی ناشناخته را با ستون سطح گزارش یا تب عضویت تعیین کنید.')
                cluster=''
                if kind=='contacts':
                    choices=['']+[c['id'] for c in cfg['clusters'] if c['active']]
                    cluster=st.selectbox('عضویت مخاطبان واردشده در کلاستر',choices,format_func=lambda x:next((c['name'] for c in cfg['clusters'] if c['id']==x),'فقط ثبت مخاطبان؛ عضویت بعداً'))
                spec=dict(id=ident(sid),kind=kind,path=location,sheet=sheet,mapping=mapping)
                if cluster:spec['default_cluster_id']=cluster
                base=copy.deepcopy(cfg)
                base['sources']=[x for x in base['sources'] if x['id']!=spec['id']]+[spec]
                candidate,summary=preview_import(base,spec,blob,filename)
                target={'contacts':'people','clusters':'clusters','memberships':'memberships'}[kind]
                st.write('پیش‌نمایش ورود',summary)
                st.dataframe(pd.DataFrame(candidate[target]).rename(columns=LABELS),hide_index=True)
                if st.button('ذخیره منبع و اعمال مخاطبان / تنظیمات'):
                    commit_import(store,base,spec,blob,filename);st.success('ذخیره شد. مخاطبان در تب افراد و عضویت‌ها قابل مشاهده‌اند.');st.rerun()
        except Exception as ex:st.error(str(ex))

    with reports:
        st.caption('قالب، سربرگ، متن ایمیل، بخش‌ها و ویجت‌های کلاستر انتخاب‌شده در همین خروجی اعمال می‌شوند.')
        from app.cluster_delivery import render as render_delivery
        render_delivery(cfg,'center_delivery')

    with history:
        st.download_button('دریافت پشتیبان تنظیمات',json.dumps(cfg,ensure_ascii=False,indent=2),file_name=f'control_center_revision_{cfg["revision"]}.json',mime='application/json')
        st.caption('تنظیمات دارای ایمیل افراد است؛ فولدر مرکز باید دسترسی مخصوص اپراتور داشته باشد.')
        from gsi.warehouse.store import Warehouse
        with Warehouse().db() as con:
            rows=con.execute("SELECT at,actor,payload FROM wh_audit WHERE kind='cluster_config' ORDER BY id DESC LIMIT 30").fetchall()
        st.write(rows)
        backup=st.file_uploader('بازگردانی پشتیبان با ایجاد نسخه جدید',type=['json'],key='cc_restore')
        if backup is not None and st.button('اعتبارسنجی و بازگردانی پشتیبان'):
            try:persist(json.loads(backup.getvalue().decode('utf-8')))
            except Exception as ex:st.error(str(ex))
