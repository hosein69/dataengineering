# -*- coding: utf-8 -*-
"""GSI personal Streamlit surface backed only by encrypted shared-folder files."""
from __future__ import annotations

import os
import sys
from html import escape
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import streamlit as st

from gsi.personalization import PersonalWorkspace
from gsi.personalization.identity import IdentityError
from gsi.personalization.store import ProfileStoreError
from app.styles import css as gsi_css

st.set_page_config(page_title="GSI · فضای شخصی", page_icon="◉", layout="wide")

st.markdown(gsi_css(), unsafe_allow_html=True)
st.markdown("""<style>
.gsi-my-hero{direction:rtl;background:#0b1f33;color:#fff;border-radius:20px;
padding:25px 30px;margin:4px 0 18px;border-right:6px solid #0a7c86}
.gsi-my-hero h1{color:#fff;font-size:29px;margin:4px 0 8px;line-height:1.5}
.gsi-my-hero p{color:#e4ebef;margin:0;line-height:1.9}
.gsi-my-hero .eyebrow{font-size:12px;color:#c8dfdf;font-weight:700}
.gsi-my-note{direction:rtl;background:#fbf8f1;border-right:4px solid #c79a4a;
padding:13px 17px;border-radius:10px;margin:12px 0;color:#3d5163;line-height:1.9}
@media(max-width:640px){.gsi-my-hero{padding:18px}.gsi-my-hero h1{font-size:22px}}
</style>""", unsafe_allow_html=True)

try:
    ws = PersonalWorkspace.from_env()
    ctx = ws.context()
    prefs = ctx["preferences"]
except (IdentityError, ProfileStoreError, OSError) as ex:
    st.error(str(ex))
    st.code("GSI_EMP_CODE=00123456\nGSI_PROFILE_ROOT=\\\\server\\share\\GSI\\Users\nGSI_PROFILE_USER_KEY_FILE=C:\\Secure\\gsi_profile.key")
    st.stop()

current = ctx.get("current") or {}
records = current.get("records", []) if isinstance(current, dict) else []
df = pd.DataFrame(records)
hr_scope = current.get("hr_scope") or {}
level = hr_scope.get("level", "expert")
level_fa = {"expert": "کارشناس", "head": "رئیس", "manager": "مدیر", "vice": "معاون"}.get(level, "کارشناس")
name = escape(str(hr_scope.get("name") or ws.employee_code))
organization = escape(str(hr_scope.get("organization") or "واحد نامشخص"))
heading = {"expert": "کارهای امروز من", "head": "صف و اقدام‌های تیم من",
           "manager": "گلوگاه‌های مدیریت من", "vice": "تصمیم‌های معاونت من"}.get(level, "کارهای امروز من")
st.markdown(f'<div class="gsi-my-hero"><div class="eyebrow">GSI · {level_fa} · {organization}</div>'
            f'<h1>{heading}</h1><p>{name} · داده‌های آخرین گزارش تأیید و منتشرشده</p></div>',
            unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"### {level_fa} · {name}")
    st.caption("سطح سازمانی از HR منتشرشده تعیین می‌شود.")
    compact = st.checkbox("حالت فشرده", value=bool(prefs.get("compact_mode", False)))
    critical = st.checkbox("فقط موارد بحرانی", value=bool(prefs.get("show_critical_only", False)))
    calendar = st.selectbox("تقویم", ["jalali", "gregorian"], index=0 if prefs.get("calendar") == "jalali" else 1)
    if st.button("ذخیره تنظیمات من", width="stretch"):
        try:
            ws.save_preferences({"compact_mode": compact,
                                 "show_critical_only": critical, "calendar": calendar})
            st.success("تنظیمات ذخیره شد.")
        except (ProfileStoreError, OSError, ValueError) as ex:
            st.error(f"تنظیمات ذخیره نشد: {ex}")
    st.caption("نمای شما از آخرین داده منتشرشده ساخته می‌شود.")

meta = ctx.get("snapshot_meta") or {}
c1, c2, c3 = st.columns(3)
c1.metric("پرونده‌های این دامنه", int(current.get("row_count", len(df)) or 0))
c2.metric("آخرین انتشار", meta.get("refreshed_at", "—"))
c3.metric("پوشش نمایش", "کامل" if not current.get("truncated") else "محدود؛ همه ردیف‌ها نمایش داده نشده‌اند")

if df.empty:
    st.info("در آخرین گزارش شما ردیفی ثبت نشده است." if meta.get("refreshed_at") else "هنوز گزارشی برای شما منتشر نشده است.")
    st.stop()

view = df.copy()
if critical:
    codes = view.get("کد طبقه بحرانی", pd.Series("", index=view.index))
    labels = view.get("بحرانی (کوتاه)", pd.Series("", index=view.index))
    view = view[codes.isin(["STOCKOUT", "CRITICAL"]) | labels.isin(["بحرانی", "توقف"])]

next_actions = view.get("NEXT_ACTION_TITLE", pd.Series("", index=view.index)).fillna("").astype(str).str.strip()
fx_actions = view.get("FX_ACTION_TITLE", pd.Series("", index=view.index)).fillna("").astype(str).str.strip()
critical_labels = view.get("بحرانی (کوتاه)", pd.Series("", index=view.index)).fillna("").astype(str)
deadline = pd.to_numeric(view.get("FX_TIME_DAYS_LEFT", pd.Series(index=view.index, dtype=object)), errors="coerce")
mc1, mc2, mc3 = st.columns(3)
mc1.metric("نیازمند اقدام", int((next_actions.ne("") | fx_actions.ne("")).sum()))
mc2.metric("بحرانی یا توقف", int(critical_labels.isin(["بحرانی", "توقف"]).sum()))
mc3.metric("مهلت عبورکرده با شاهد", int(deadline.lt(0).sum()))

if level != "expert":
    grouping = "ORG_DEPT" if level == "vice" else "CANONICAL_EXPERT"
    if grouping in view.columns:
        queue = (view.assign(_group=view[grouping].fillna("نامشخص").astype(str))
                 .groupby("_group", dropna=False).size().sort_values(ascending=False)
                 .rename("پرونده").head(12).reset_index()
                 .rename(columns={"_group": "واحد" if level == "vice" else "کارشناس"}))
        st.subheader("توزیع کار در دامنه من")
        st.dataframe(queue, width="stretch", hide_index=True)
st.markdown('<div class="gsi-my-note">از ردیف‌های نیازمند اقدام شروع کنید؛ عدد یا مالک نامعلوم را تأییدشده فرض نکنید. '
            'برای هر پرونده، مانع و موعد را پیش از ارجاع بررسی کنید.</div>', unsafe_allow_html=True)
st.subheader("اقدام‌های نیازمند پیگیری" if level != "expert" else "اقدامات من")
action_cols = [c for c in ["KEY_REG", "مرحله جاری", "FX_CURRENT_STAGE", "NEXT_ACTION_TITLE", "NEXT_ACTION_PRIORITY", "NEXT_ACTION_DUE_DATE", "NEXT_ACTION_OWNER", "FX_ACTION_TITLE", "FX_ACTION_PRIORITY", "FX_ACTION_DUE_DATE", "مانع فعلی"] if c in view.columns]
if action_cols:
    act = view[action_cols].copy()
    if "NEXT_ACTION_TITLE" in act.columns:
        act = act[act["NEXT_ACTION_TITLE"].fillna("").astype(str).str.strip().ne("")]
    elif "FX_ACTION_TITLE" in act.columns:
        act = act[act["FX_ACTION_TITLE"].fillna("").astype(str).str.strip().ne("")]
    if "NEXT_ACTION_PRIORITY" in act.columns:
        order = {"بحرانی": 0, "فوری": 1, "بالا": 2, "متوسط": 3, "پایین": 4}
        act = act.assign(_priority=act["NEXT_ACTION_PRIORITY"].map(order).fillna(5))
        act = act.sort_values("_priority", kind="stable").drop(columns="_priority")
    st.dataframe(act.head(50), width="stretch", hide_index=True)
    if len(act) > 50:
        st.caption(f"۵۰ اقدام اول از {len(act)} اقدام نمایش داده شده است؛ همه پرونده‌ها در جدول پایین هستند.")
else:
    st.caption("ستون اقدام در Snapshot موجود نیست.")

st.subheader("پرونده‌های دامنه من" if level != "expert" else "پرونده‌های من")
cols = [c for c in ["KEY_REG", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_MATERIAL", "مرحله جاری", "بحرانی (کوتاه)", "مقاومت (روز)", "مانع فعلی"] if c in view.columns]
st.dataframe(view[cols] if cols else view, width="stretch", hide_index=True, height=480)
