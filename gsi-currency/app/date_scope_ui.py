# -*- coding: utf-8 -*-
"""کنترل‌های «دامنه تاریخی» Studio؛ منطق در :mod:`gsi.studio_core.date_scope` است."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from gsi.studio_core import date_scope as DS


def controls(df: pd.DataFrame, key: str, container=None) -> DS.ScopeResult:
    """چهار بازه تاریخ (درخواست، ثبت سفارش، PO، IL) → فریم محدودشده و شرح آن.

    هر مرز یک متن است (شمسی یا میلادی) تا تقویم میلادی ``date_input`` تحمیل نشود.
    دامنه‌ای که ستونش در این داده نیست غیرفعال نشان داده می‌شود.
    """
    box = container or st
    ranges = {}
    errors = []
    with box.expander("دامنه تاریخی (کنار حداکثر ردیف)", expanded=False):
        st.caption("مرز خالی یعنی بی‌مرز. تاریخ را شمسی (1405/01/01) یا میلادی (2026-03-21) بنویسید. "
                   "چند بازه با هم «و» می‌شوند.")
        for k, (title, _en, cands) in DS.DATE_SCOPES.items():
            cols = DS.available_columns(df, k)
            c1, c2, c3 = st.columns([1, 1, 1])
            start = c1.text_input(f"{title} از", key=f"{key}_{k}_from", disabled=not cols)
            end = c2.text_input("تا", key=f"{key}_{k}_to", disabled=not cols)
            keep = c3.checkbox("ردیف بی‌تاریخ هم بماند", key=f"{key}_{k}_keep", disabled=not cols)
            if not cols:
                st.caption(f"{title}: هیچ‌کدام از ستون‌های {', '.join(cands)} در این داده نیست.")
                continue
            try:
                ranges[k] = DS.DateRange(DS.parse_bound(start), DS.parse_bound(end), bool(keep))
            except ValueError as ex:
                errors.append(str(ex))
        for e in errors:
            st.error(e)
    res = DS.apply_date_scope(df, ranges)
    note = DS.describe(res)
    if note:
        box.caption(note)
    return res
