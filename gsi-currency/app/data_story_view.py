# -*- coding: utf-8 -*-
"""محیط کاری «دیتا استوری‌تلینگ» (R10، مالک ۱۴۰۵/۰۷/۰۹).

این صفحه عددی نمی‌سازد؛ داستان از :func:`gsi.report.data_story.build_story` می‌آید و یک‌بار در هر
Snapshot ساخته می‌شود. نمودارها SVG هستند و ``st.html`` آن‌ها را پاک می‌کند، پس همان صفحه HTML ارسالی
داخل ``components.html`` (iframe) نشان داده می‌شود: Studio و فایل HTML یک تصویرند. HTML و Excel فقط
هنگام کلیک ساخته می‌شوند (:mod:`app.lazy_download`، سازگار با Streamlit 1.51).
"""
from __future__ import annotations

import functools
from typing import Any, Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from app import lazy_download as LD
from gsi.report import data_story as D

_STORY = "_gsi_data_story"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _signature(df: Optional[pd.DataFrame], extras: Any, ref_date: str) -> tuple:
    try:
        run_id = extras.get("warehouse_run_id") if extras is not None else None
    except Exception:
        run_id = None
    if df is None or df.empty:
        return (str(ref_date), run_id, (0, 0), 0)
    keys = [c for c in ("KEY_REG", "CANONICAL_BL", "KEY_ORDER", "KEY_MATERIAL") if c in df.columns]
    digest = int(pd.util.hash_pandas_object(df[keys].astype(str), index=False).sum()) if keys else 0
    return (str(ref_date), run_id, df.shape, digest)


def _story(df: pd.DataFrame, extras: Any, ref_date: str) -> tuple:
    """(داستان، صفحه HTML) یک‌بار در هر Snapshot، نه در هر بازاجرای صفحه."""
    sig = _signature(df, extras, ref_date)
    cached = st.session_state.get(_STORY)
    if cached and cached[0] == sig:
        return cached[1], cached[2]
    s = D.build_story(df, extras, ref_date)
    page = D.build_html(s)
    st.session_state[_STORY] = (sig, s, page)
    return s, page


def _height(s: D.Story) -> int:
    """ارتفاع تقریبی صفحه (components.html خودش بلند نمی‌شود)؛ کمی بیشتر، و اسکرول برای احتیاط."""
    h = 620
    for c in s.chapters:
        v = c.visual or ""
        h += 300 + 330 * v.count('class="ds-svg"') + 34 * v.count('class="ds-hb"') + 30 * v.count('class="ds-st"') \
            + 48 * v.count("<tr>") + 36 * v.count("<li>") + (120 if c.insight else 0)
    return int(min(max(h, 900), 16000))


def _html_bytes(page: str) -> bytes:
    return page.encode("utf-8")


def run(df: pd.DataFrame, extras: Any, ref_date: str) -> None:
    s, page = _story(df, extras, ref_date)
    safe_ref = str(ref_date or "report").replace("/", "-")
    snap = (st.session_state.get(_STORY) or (None,))[0]
    c1, c2, c3 = st.columns([1, 1, 2])
    LD.download(c1, "داستان HTML", functools.partial(_html_bytes, page), file_name=f"GSI_DATA_STORY_{safe_ref}.html",
                mime="text/html", key="ds_dl_html", sig=(snap,), icon=":material/mail:", primary=True)
    LD.download(c2, "داده فصل‌ها (Excel)", functools.partial(D.build_excel, s),
                file_name=f"GSI_DATA_STORY_{safe_ref}.xlsx", mime=XLSX_MIME, key="ds_dl_xlsx", sig=(snap,),
                primary=False)
    c3.caption("همه تاریخ‌های Snapshot منتشرشده؛ هر ارز جدا؛ «—» یعنی بی‌داده، نه صفر. این فصل‌ها در سازنده گزارش "
               "هم به‌صورت Block «دیتا استوری‌تلینگ» افزودنی‌اند.")
    components.html(page, height=_height(s), scrolling=True)
