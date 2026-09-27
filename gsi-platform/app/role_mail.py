# -*- coding: utf-8 -*-
"""Review and dispatch HR-routed role mail from the published snapshot."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from app.styles import css
from gsi.integrations.role_mail import from_published, render_html, dispatch
from gsi.resolve.expert_roles import ROLES

st.set_page_config(page_title="GSI · ایمیل مسئولیت‌ها", layout="wide", page_icon="✉")
st.markdown(css(), unsafe_allow_html=True)
st.title("ایمیل کارهای هر شخص")
st.caption("گیرنده و رونوشت از HR همان گزارش منتشرشده می‌آیند. ارسال بدون دستور صریح انجام نمی‌شود.")

roles = {r.key: r.fa for r in ROLES}
with st.container(border=True):
    selected = st.multiselect("حوزه کارشناسی", list(roles), default=list(roles),
                              format_func=lambda k: roles[k])
    cc = st.multiselect("رونوشت", ["head", "manager", "vice"], default=["head", "manager"],
                        format_func=lambda x: {"head": "رئیس", "manager": "مدیر", "vice": "معاون"}[x])
    st.caption("حوزه حمل هنوز مالک کارشناسی مستقل در داده‌های این نسخه ندارد؛ تا تعیین سورس و نام مالک، ایمیل حمل تولید نمی‌شود.")

if not selected:
    st.info("حداقل یک حوزه کارشناسی انتخاب کنید.")
    st.stop()
try:
    plans, skipped, ref_date = from_published(cc_levels=cc, role_keys=selected)
except (ValueError, OSError) as ex:
    st.error(str(ex))
    st.stop()

if skipped:
    st.warning("برخی موردها به علت تطبیق نامطمئن کنار گذاشته شدند: " +
               " · ".join(f"{k}: {v}" for k, v in sorted(skipped.items())))
st.metric("پیام اختصاصی آماده بازبینی", len(plans))
st.caption(f"تاریخ مرجع: {ref_date or 'نامعلوم'} · هیچ داده زنده‌ای از فایل‌های عملیاتی دوباره خوانده نشد.")
if not plans:
    st.info("اقدام نقش‌محور با مالک و نشانی قطعی در این Snapshot پیدا نشد.")
    st.stop()

index = pd.DataFrame([{"کارشناس": p.name, "نقش": p.role_label, "To": p.to,
                       "CC": "; ".join(p.cc) or "—", "تعداد پرونده": len(p.cases)} for p in plans])
st.dataframe(index, width="stretch", hide_index=True)
chosen = st.selectbox("پیش‌نمایش پیام", range(len(plans)),
                      format_func=lambda i: f"{plans[i].name} · {plans[i].role_label} · {len(plans[i].cases)} پرونده")
st.components.v1.html(render_html(plans[chosen], ref_date=ref_date), height=460, scrolling=True)

left, right = st.columns(2)
if left.button("ساخت Draft جداگانه برای همه", width="stretch"):
    try:
        out = dispatch(plans, ref_date=ref_date, send=False)
        st.success(f"{len(out)} پیش‌نویس در Classic Outlook ذخیره شد.")
    except Exception as ex:
        st.error(f"ساخت Draft متوقف شد: {ex}")

ack = right.checkbox("گیرندگان، رونوشت و پیش‌نمایش‌ها را بررسی کردم و ارسال را می‌خواهم")
if right.button("ارسال پیام‌های این Snapshot", disabled=not ack or bool(skipped), width="stretch"):
    try:
        out = dispatch(plans, ref_date=ref_date, send=True)
        st.success(f"{len(out)} پیام ارسال شد؛ ثبت هر اجرا از ارسال دوباره جلوگیری می‌کند.")
    except Exception as ex:
        st.error("ارسال متوقف شد؛ وضعیت Outlook و دفتر ارسال را پیش از تلاش دوباره بررسی کنید: " + str(ex))
