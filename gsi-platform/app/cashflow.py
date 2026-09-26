"""Standalone financial workspace; published DWH is the default source."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import date
import streamlit as st
from gsi.cashflow.ui import render
st.set_page_config(page_title='GSI | جریان وجوه و رفع تعهد',layout='wide')
# Same RTL layout, fonts and design tokens as Studio/Dashboard (this page used
# to render left-to-right with Streamlit's default theme).
from app.styles import css
st.markdown(css(), unsafe_allow_html=True)
from gsi.core.jalali import date_label
from gsi.warehouse.service import published_reference_date
_published=published_reference_date()
# Default = the published snapshot's reference date, not today: NTSW balance
# snapshots are dated on that day, and another as-of turns every reconciliation
# into DATE_MISMATCH.
asof=st.sidebar.date_input('تاریخ گزارش',date.fromisoformat(_published) if _published else date.today())
st.sidebar.caption(f'تاریخ انتخاب‌شده: {date_label(asof)}')
if _published and asof.isoformat()!=_published:
    st.sidebar.warning(f'تاریخ Snapshot منتشرشده {date_label(_published)} است؛ تطبیق مانده‌ها در تاریخ دیگر «عدم تطابق تاریخ» می‌گیرد.')
st.sidebar.caption('گزارش از آخرین اجرای منتشرشده ساخته می‌شود. نبودِ شاهد با انجام‌نشدن مرحله متفاوت است.')
render(None,{},asof)
