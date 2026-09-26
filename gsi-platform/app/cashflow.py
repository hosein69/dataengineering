"""Standalone financial workspace; published DWH is the default source."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import date
import streamlit as st
from gsi.cashflow.ui import render
st.set_page_config(page_title='GSI | جریان وجوه و رفع تعهد',layout='wide')
asof=st.sidebar.date_input('تاریخ گزارش',date.today())
st.sidebar.caption('گزارش از آخرین اجرای منتشرشده ساخته می‌شود. نبودِ شاهد با انجام‌نشدن مرحله متفاوت است.')
render(None,{},asof)
