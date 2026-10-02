# -*- coding: utf-8 -*-
"""انتخاب زبان عنوان ستون‌ها (فارسی / English) برای همه جدول‌های Studio.

به‌جای ویرایش تک‌تک ۱۴ ماژول نما، ``st.dataframe`` و ``st.data_editor``
یک بار در ورودی برنامه پوشانده می‌شوند: هر جدول پیش از رسم، عنوان
ستون‌هایش را با ``gsi.i18n.columns`` یک‌زبان می‌کند. خروجی ``data_editor``
به نام‌های اصلی برگردانده می‌شود تا کدی که ستون‌ها را با نام فارسی
می‌خواند (مثلاً ``ed["انتخاب"]``) دست نخورد.
"""
from __future__ import annotations

import types
from typing import Dict, Mapping

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from gsi.i18n import columns as C

KEY = "gsi_col_lang"
_FLAG = "_gsi_col_lang_installed"


def current() -> str:
    lang = st.session_state.get(KEY) or C.FA
    return lang if lang in C.LANGS else C.FA


def selector(container=None) -> str:
    """کلید انتخاب زبان در نوار کناری."""
    box = container if container is not None else st.sidebar
    box.radio("زبان عنوان ستون‌ها · Column language", list(C.LANGS),
              format_func=lambda k: C.LANG_LABELS[k], horizontal=True, key=KEY)
    return current()


def register(display: Mapping[str, str]) -> None:
    C.register_display(display)


def register_frame(df: pd.DataFrame) -> None:
    """برچسب‌های کاتالوگ را برای نماهایی که پیش از ساخت کاتالوگ اجرا می‌شوند ثبت می‌کند."""
    try:
        from gsi.studio_core.field_catalog import build_catalog, unique_labels
        C.register_display(unique_labels(build_catalog(df)))
    except Exception:
        pass


def display_map(display: Mapping[str, str], lang: str = "") -> Dict[str, str]:
    """{ستون: عنوان یکتا در زبان جاری} — جایگزین ``DISPLAY`` برای lab و خروجی Excel."""
    C.register_display(display)
    return C.rename_map(list(display.keys()), lang or current())


def _fix_config(cfg, mp: Mapping, lang: str):
    if not isinstance(cfg, dict):
        return cfg
    out = {}
    for k, v in cfg.items():
        nk = mp.get(k, k)
        if isinstance(v, str):
            v = C.label(v, lang)
        elif isinstance(v, dict) and v.get("label"):
            v = dict(v)
            v["label"] = C.label(v["label"], lang)
        out[nk] = v
    return out


def _fix_kwargs(kw: dict, mp: Mapping, lang: str) -> dict:
    kw = dict(kw)
    if "column_config" in kw:
        kw["column_config"] = _fix_config(kw["column_config"], mp, lang)
    if isinstance(kw.get("column_order"), (list, tuple)):
        kw["column_order"] = [mp.get(c, c) for c in kw["column_order"]]
    if isinstance(kw.get("disabled"), (list, tuple)):
        kw["disabled"] = [mp.get(c, c) for c in kw["disabled"]]
    return kw


def _wrap(orig, editor: bool):
    def call(self, data=None, *args, **kwargs):
        lang = current()
        if isinstance(data, pd.DataFrame):
            try:
                new, mp = C.localize_frame(data, lang)
                kwargs = _fix_kwargs(kwargs, mp, lang)
            except Exception:
                new, mp = data, {}
            res = orig(self, new, *args, **kwargs)
            if editor and mp and isinstance(res, pd.DataFrame):
                res = res.rename(columns={v: k for k, v in mp.items()})
            return res
        return orig(self, data, *args, **kwargs)
    call.__wrapped__ = orig
    call.__doc__ = orig.__doc__
    return call


def install() -> None:
    """یک بار در هر پردازه؛ اجرای دوباره بی‌اثر است."""
    if getattr(DeltaGenerator, _FLAG, False):
        return
    for name, editor in (("dataframe", False), ("data_editor", True)):
        orig = getattr(DeltaGenerator, name)
        wrapped = _wrap(orig, editor)
        setattr(DeltaGenerator, name, wrapped)
        bound = getattr(st, name, None)
        main = getattr(bound, "__self__", None)
        if isinstance(main, DeltaGenerator):
            setattr(st, name, types.MethodType(wrapped, main))
    setattr(DeltaGenerator, _FLAG, True)
