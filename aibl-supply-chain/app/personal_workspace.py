# -*- coding: utf-8 -*-
"""GSI personal Streamlit surface backed only by encrypted shared-folder files."""
from __future__ import annotations

import os
import pandas as pd
import streamlit as st

from gsi.personalization import PersonalWorkspace
from gsi.personalization.identity import IdentityError
from gsi.personalization.store import ProfileStoreError

st.set_page_config(page_title="GSI · فضای شخصی", page_icon="◉", layout="wide")

st.markdown("# GSI · فضای شخصی")
st.caption("Data • Process • Decision · این نما داده را فقط از Shared Folder رمزگذاری‌شده می‌خواند.")

try:
    ws = PersonalWorkspace.from_env()
except (IdentityError, ProfileStoreError) as ex:
    st.error(str(ex))
    st.code("GSI_EMP_CODE=00123456\nGSI_PROFILE_ROOT=\\\\server\\share\\GSI\\Users\nGSI_PROFILE_KEY_FILE=C:\\Secure\\gsi_profile.key")
    st.stop()

prefs = ws.preferences()
ctx = ws.context()
current = ctx.get("current") or {}
records = current.get("records", []) if isinstance(current, dict) else []
df = pd.DataFrame(records)

with st.sidebar:
    st.markdown(f"### کاربر {ws.employee_code}")
    audience = st.selectbox("نمای من", ["expert", "manager", "executive", "analyst"],
                            index=["expert", "manager", "executive", "analyst"].index(prefs.get("audience", "expert")))
    compact = st.checkbox("حالت فشرده", value=bool(prefs.get("compact_mode", False)))
    critical = st.checkbox("فقط موارد بحرانی", value=bool(prefs.get("show_critical_only", False)))
    calendar = st.selectbox("تقویم", ["jalali", "gregorian"], index=0 if prefs.get("calendar") == "jalali" else 1)
    if st.button("ذخیره تنظیمات من", use_container_width=True):
        ws.save_preferences({"audience": audience, "compact_mode": compact,
                             "show_critical_only": critical, "calendar": calendar})
        st.success("تنظیمات در profile.gsi ذخیره شد.")
    st.caption("هیچ IP/API برای خواندن Profile یا Snapshot استفاده نمی‌شود.")

meta = ctx.get("snapshot_meta") or {}
c1, c2, c3 = st.columns(3)
c1.metric("ردیف Snapshot", int(current.get("row_count", len(df)) or 0))
c2.metric("آخرین Refresh", meta.get("refreshed_at", "—"))
c3.metric("پوشش منتشرشده", "کامل" if not current.get("truncated") else "محدود")

if df.empty:
    st.info("current.gsi هنوز برای این کد پرسنلی منتشر نشده است.")
    st.stop()

view = df.copy()
if critical and "بحرانی (کوتاه)" in view.columns:
    view = view[~view["بحرانی (کوتاه)"].astype(str).isin(["", "ایمن", "GOOD", "بدون مصرف"])]

st.subheader("اقدامات من")
action_cols = [c for c in ["KEY_REG", "مرحله جاری", "FX_CURRENT_STAGE", "FX_ACTION_TITLE", "FX_ACTION_PRIORITY", "FX_ACTION_DUE_DATE", "مانع فعلی"] if c in view.columns]
if action_cols:
    act = view[action_cols].copy()
    if "FX_ACTION_TITLE" in act.columns:
        act = act[act["FX_ACTION_TITLE"].fillna("").astype(str).str.strip().ne("")]
    st.dataframe(act.head(50), use_container_width=True, hide_index=True)
else:
    st.caption("ستون اقدام در Snapshot موجود نیست.")

st.subheader("پرونده‌های من")
cols = [c for c in ["KEY_REG", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_MATERIAL", "مرحله جاری", "بحرانی (کوتاه)", "مقاومت (روز)", "مانع فعلی"] if c in view.columns]
st.dataframe(view[cols] if cols else view, use_container_width=True, hide_index=True, height=480)
