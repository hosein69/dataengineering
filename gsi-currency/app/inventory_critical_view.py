# -*- coding: utf-8 -*-
"""محیط کاری «کنترل موجودی و اقلام بحرانی» — رسیدگی به تفکیک متریال، سفارش و بارنامه.

این صفحه هیچ عددی را دوباره حساب نمی‌کند و خودش نشانه‌گذاری نمی‌سازد: مدل و تکه‌های
HTML از :mod:`gsi.report.inventory_critical_report` می‌آیند؛ **همان تکه‌هایی** که
گزارش HTML ارسالی می‌سازد. پس Studio و HTML یک تصویر نشان می‌دهند. Excel و HTML فقط
هنگام کلیک ساخته می‌شوند (:mod:`app.lazy_download`؛ روی Streamlit 1.51 با دکمه «آماده‌سازی»).

جدول تعاملی Streamlit (مرتب‌سازی و جستجو) زیر هر بخش در یک بازشو می‌ماند.
"""
from __future__ import annotations

import functools
from typing import Any, Optional

import pandas as pd
import streamlit as st

from app import lazy_download as LD
from gsi.design import icons as I
from gsi.design import tokens as T
from gsi.report import critical_board as CB
from gsi.report import fx_html as H
from gsi.report import inventory_critical_report as R

XLSX = H.XLSX_MIME

CSS = """<style>
.icr-head{background:var(--raised);border-radius:24px;padding:18px 22px;margin:4px 0 16px;
  box-shadow:%(raised)s;display:flex;gap:16px;align-items:center}
.icr-head .mi-tile{width:54px;height:54px;border-radius:18px}
.icr-head .k{font-size:11px;font-weight:800;color:var(--brand);letter-spacing:.3px}
.icr-head h2{font-size:24px!important;margin:4px 0!important;color:var(--text)!important}
.icr-head p{font-size:12px;color:var(--text-2);margin:0}
%(minimal)s
</style>""" % {"minimal": I.minimal_css().replace("%", "%%"), "raised": T.ELEVATION["raised"]}

_MODEL_KEY = "_gsi_inv_model"


def _lang() -> str:
    try:
        from app.col_lang import current
        return current()
    except Exception:
        return "fa"


def _html(fragment: str) -> None:
    """تکه HTML مشترک؛ ظرف ``div`` اول می‌آید تا پاک‌سازی DOMPurify چیزی را حذف نکند."""
    ltr = ' dir="ltr"' if _lang() == "en" else ""
    st.html(f'<div class="gx gx-host"{ltr}>{fragment}</div>')


def _signature(df: Optional[pd.DataFrame], extras: Any, ref_date: str, levels: tuple) -> tuple:
    try:
        run_id = extras.get("warehouse_run_id")
    except Exception:
        run_id = None
    # دامنه تاریخی همان Snapshot را با ردیف‌های دیگر می‌دهد؛ شمار ردیف به‌تنهایی کافی نیست.
    rows = 0 if df is None else int(pd.util.hash_pandas_object(df.index, index=False).sum())
    return (ref_date, run_id, levels, 0 if df is None else len(df), rows, 0 if df is None else df.shape[1])


def _model(df: pd.DataFrame, extras: Any, ref_date: str, levels: tuple) -> R.InventoryModel:
    """مدل یک‌بار در هر Snapshot و هر انتخاب سطح ساخته می‌شود، نه در هر بازاجرای صفحه."""
    sig = _signature(df, extras, ref_date, levels)
    cached = st.session_state.get(_MODEL_KEY)
    if cached and cached[0] == sig:
        return cached[1]
    model = R.build_model(df, extras, ref_date, levels=levels)
    st.session_state[_MODEL_KEY] = (sig, model)
    return model


def _dl(col, label: str, make, file_name: str, key: str, primary: bool = False, sig: tuple = (),
        mime: str = XLSX, icon: str = ":material/download:") -> None:
    """دانلود با ساخت فایل فقط هنگام نیاز (همان الگوی fx_lifecycle_view)."""
    snap = (st.session_state.get(_MODEL_KEY) or (None,))[0]
    LD.download(col, label, make, file_name=file_name, mime=mime, key=key, sig=(snap,) + tuple(sig),
                icon=icon, primary=primary)


def _html_bytes(model: R.InventoryModel, lang: str) -> bytes:
    return R.build_html(model, lang=lang).encode("utf-8")


def _table(frame: pd.DataFrame, title: str) -> None:
    with st.expander(title):
        if frame.empty:
            st.info("داده‌ای نیست.")
            return
        st.dataframe(frame.drop(columns=["کد سطح"], errors="ignore"), hide_index=True, width="stretch")


def run(df: pd.DataFrame, extras: Any, ref_date: str) -> None:
    st.html(H.style_tag() + f"<style>{R.inv_css()}</style>")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="icr-head">{I.icon_tile("warehouse", size=26, active=True)}<div>'
                '<div class="k">کنترل موجودی · متریال · سفارش · بارنامه</div><h2>کنترل موجودی و اقلام بحرانی</h2>'
                '<p>موجودی Oracle و مقدار پارت‌های کارشناسان (نزد سازنده، آماده حمل، در راه، در گمرک) کنار سطح بحرانی و '
                'مقاومت؛ هر متریال، سفارش و بارنامه یک ردیف، با فهرست رسیدگی و بررسی‌های کنترل موجودی. همین نماها در '
                'گزارش HTML ارسالی و Excel هستند.</p></div></div>', unsafe_allow_html=True)
    lang = _lang()
    opts = list(CB.LEVELS.keys())[:5]
    c1, c2, c3 = st.columns([3, 2, 2])
    levels = c1.multiselect("سطوح بحرانی", opts, default=list(CB.DEFAULT_LEVELS),
                            format_func=CB.level_label, key="icr_levels")
    levels = tuple(levels) or CB.DEFAULT_LEVELS
    model = _model(df, extras, ref_date, levels)
    _dl(c2, "Excel کنترل موجودی و اقلام بحرانی", functools.partial(R.build_excel, model, lang),
        f"GSI_INVENTORY_CRITICAL_{ref_date}.xlsx", "icr_dl_xlsx", primary=True, sig=(levels, lang))
    _dl(c3, "گزارش HTML برای ارسال", functools.partial(_html_bytes, model, lang),
        f"GSI_INVENTORY_CRITICAL_{ref_date}.html", "icr_dl_html", sig=(levels, lang), mime="text/html",
        icon=":material/mail:")

    _html(R.kpis_section(model, lang))
    if model.empty:
        return
    st.markdown("<style>" + I.nth_icons_css('.stTabs:not(.stTabs .stTabs) [role="tablist"] > [data-testid="stTab"]',
                                            [ic for ic, _, _ in R.SECTIONS], 16) + "</style>",
                unsafe_allow_html=True)
    tabs = st.tabs([t for _, t, _ in R.SECTIONS])
    frames = (model.materials, model.orders, model.bls, model.followup, model.checks)
    for tab, (_, title, fn), frame in zip(tabs, R.SECTIONS, frames):
        with tab:
            _html(fn(model, lang, max_rows=200))
            _table(frame, f"جدول تعاملی {title}")
