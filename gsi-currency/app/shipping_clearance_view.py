# -*- coding: utf-8 -*-
"""محیط کاری «حمل و ترخیص» — گزارش جداگانه در دانه بارنامه.

این صفحه هیچ عددی را دوباره حساب نمی‌کند و خودش نشانه‌گذاری نمی‌سازد:

* مدل از :func:`gsi.report.shipping_clearance_report.build_model` می‌آید و یک‌بار در هر
  Snapshot ساخته می‌شود؛
* کارت‌ها، قیف، جدول‌ها و یادداشت‌ها **همان تکه‌های HTML** گزارش ارسالی‌اند، پس Studio و
  HTML یک تصویر نشان می‌دهند؛ فیلتر متن و بازه تاریخ Studio همان منطق فیلتر سمت کاربر HTML
  (:func:`filter_frame`) است؛
* HTML و Excel فقط هنگام کلیک ساخته می‌شوند (:mod:`app.lazy_download`؛ روی Streamlit
  قدیمی‌تر از 1.52 با دکمه «آماده‌سازی»).

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
from gsi.report import shipping_clearance_report as R

CSS = """<style>
.scv-head{background:var(--raised);border-radius:24px;padding:18px 22px;margin:4px 0 16px;
  box-shadow:%(raised)s;display:flex;gap:16px;align-items:center}
.scv-head .mi-tile{width:54px;height:54px;border-radius:18px}
.scv-head .k{font-size:11px;font-weight:800;color:var(--brand);letter-spacing:.3px}
.scv-head h2{font-size:24px!important;margin:4px 0!important;color:var(--text)!important}
.scv-head p{font-size:12px;color:var(--text-2);margin:0}
%(minimal)s
</style>""" % {"minimal": I.minimal_css().replace("%", "%%"), "raised": T.ELEVATION["raised"]}

_MODEL = "_gsi_shipping_clearance_model"


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


def _signature(df: Optional[pd.DataFrame], extras: Any, ref_date: str) -> tuple:
    try:
        run_id = extras.get("warehouse_run_id") if extras is not None else None
    except Exception:
        run_id = None
    if df is None or df.empty:
        return (str(ref_date), run_id, (0, 0), 0)
    # دامنه (فیلتر Studio) شکل قاب را عوض نکند هم کلیدها را عوض می‌کند
    keys = [c for c in ("CANONICAL_BL", "KEY_BL", "CANONICAL_ORDER", "KEY_ORDER", "KEY_MATERIAL") if c in df.columns]
    digest = int(pd.util.hash_pandas_object(df[keys].astype(str), index=False).sum()) if keys else 0
    return (str(ref_date), run_id, df.shape, digest)


def _model(df: pd.DataFrame, extras: Any, ref_date: str) -> R.ShippingModel:
    """مدل یک‌بار در هر Snapshot ساخته می‌شود، نه در هر بازاجرای صفحه."""
    sig = _signature(df, extras, ref_date)
    cached = st.session_state.get(_MODEL)
    if cached and cached[0] == sig:
        return cached[1]
    m = R.build_model(df, extras, ref_date)
    st.session_state[_MODEL] = (sig, m)
    return m


def _dl(col, label: str, make, file_name: str, key: str, mime: str, primary: bool = False, sig: tuple = (),
        icon: str = ":material/download:") -> None:
    """دانلود با ساخت فایل فقط هنگام نیاز، روی هر Streamlit از 1.49 به بالا."""
    snap = (st.session_state.get(_MODEL) or (None,))[0]
    LD.download(col, label, make, file_name=file_name, mime=mime, key=key, sig=(snap,) + tuple(sig),
                icon=icon, primary=primary)


def _grid(frame: pd.DataFrame, lang: str, title: str) -> None:
    with st.expander(title):
        if frame is None or frame.empty:
            st.info("داده‌ای نیست.")
            return
        st.dataframe(R.display_frame(frame, lang), hide_index=True, width="stretch")


def _html_bytes(m: R.ShippingModel, lang: str) -> bytes:
    # HTML ارسالی کل دامنه را دارد و فیلتر سمت کاربر خودش را؛ مدل همین‌جا بسته می‌شود نه هنگام کلیک
    return R.build_html(m, lang=lang).encode("utf-8")


def run(df: pd.DataFrame, extras: Any, ref_date: str) -> None:
    st.html(R.style_tag())
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="scv-head">{I.icon_tile("ship", size=26, active=True)}<div>'
                '<div class="k">بارنامه · حمل · گمرک · ترخیص</div><h2>حمل و ترخیص</h2><p>هر پرونده یک '
                'بارنامه است: وضعیت ترخیص، روزهای پس از تخلیه، مدت هر مرحله به تفکیک روش حمل، فهرست پیگیری با '
                'کارشناس سفارش‌ها، پارت‌های فایل کارشناسان (نزد سازنده تا گمرک، حتی بی‌بارنامه) و کمبود داده. همین نماها در گزارش HTML ارسالی و فایل Excel هستند.</p></div></div>',
                unsafe_allow_html=True)
    lang = _lang()
    m = _model(df, extras, ref_date)
    safe_ref = str(ref_date or "report").replace("/", "-")
    suffix = "_EN" if lang == "en" else ""

    c1, c2 = st.columns(2)
    _dl(c1, "گزارش HTML حمل و ترخیص", functools.partial(_html_bytes, m, lang),
        f"GSI_SHIPPING_CLEARANCE_{safe_ref}{suffix}.html", "scv_dl_html", "text/html", primary=True, sig=(lang,),
        icon=":material/mail:")
    _dl(c2, "Excel حمل و ترخیص", functools.partial(R.build_excel, m, lang),
        f"GSI_SHIPPING_CLEARANCE_{safe_ref}{suffix}.xlsx", "scv_dl_xlsx", R.XLSX_MIME, primary=True, sig=(lang,))

    if m.empty:
        _html(R.kpi_section(m, lang))
        return

    # فیلتر همه گزارش (R10): بازه تاریخ مدل را از بارنامه‌ها و پارت‌های داخل بازه دوباره می‌سازد، پس
    # کارت‌ها، قیف، مدت‌ها و جدول‌ها با هم عوض می‌شوند؛ جستجوی متن فقط جدول‌ها را می‌پالاید
    f1, f2, f3, f4, f5 = st.columns([3, 1.2, 1.2, 1.6, 1.6])
    q = f1.text_input("جستجو در جدول‌ها", key="scv_q", placeholder="بارنامه، سفارش، متریال، کارشناس، کشتی …")
    a = f2.text_input("از تاریخ", key="scv_a", placeholder="1405/01/01")
    b = f3.text_input("تا تاریخ", key="scv_b", placeholder="1405/12/29")
    basis = f4.selectbox("مبنای تاریخ", R.BASIS_KEYS, key="scv_basis")
    f5.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    und = f5.checkbox("ردیف‌های بی‌تاریخ هم باشند", value=False, key="scv_u")
    st.caption(R.NOTE_FILTER + " " + R.NOTE_FILTER_SCOPE)
    for label, v in (("از تاریخ", a), ("تا تاریخ", b)):
        if str(v).strip() and not R._norm_date(v):
            st.warning(f"«{label}» تاریخ معتبر نیست و نادیده گرفته شد.")
    m = _filtered(m, df, extras, ref_date, a, b, und, basis)
    flt = functools.partial(R.filter_frame, text=q)
    dossiers, follow, gaps, expert = flt(m.dossiers), flt(m.follow_up), flt(m.gaps), flt(m.expert)

    st.markdown("<style>" + I.nth_icons_css('.stTabs:not(.stTabs .stTabs) [role="tablist"] > [data-testid="stTab"]',
                                            [ic for ic, _, _ in R.SECTIONS], 16) + "</style>", unsafe_allow_html=True)
    tabs = dict(zip([fn for _, _, fn in R.SECTIONS], st.tabs([title for _, title, _ in R.SECTIONS])))
    with tabs[R.journey_section]:
        _html(R.journey_section(m, lang, frame=flt(m.journey.rows)))
        _grid(R.J.export_frame(m.journey, lang), lang,
              "جدول تعاملی مسیر شواهد")
    with tabs[R.kpi_section]:
        _html(R.kpi_section(m, lang))
        _grid(m.ages, lang, "جدول دسته‌های روز پس از تخلیه")
    with tabs[R.stages_section]:
        _html(R.stages_section(m, lang))
        _grid(m.durations, lang, "جدول تعاملی مدت‌ها")
    with tabs[R.dossier_section]:
        _html(R.dossier_section(m, lang, frame=dossiers))
        _grid(dossiers, lang, "جدول تعاملی پرونده بارنامه‌ها")
    with tabs[R.followup_section]:
        _html(R.followup_section(m, lang, frame=follow))
        _grid(follow, lang, "جدول تعاملی پیگیری ترخیص")
    with tabs[R.expert_section]:
        _html(R.expert_section(m, lang, frame=expert))
        _grid(expert, lang, "جدول تعاملی پارت‌های کارشناسان")
    with tabs[R.gaps_section]:
        _html(R.gaps_section(m, lang, frame=gaps))
        _grid(m.coverage, lang, "جدول تعاملی پوشش شواهد")
        _grid(gaps, lang, "جدول تعاملی کمبود و مغایرت")


def _filtered(m: R.ShippingModel, df: pd.DataFrame, extras: Any, ref_date: str, a: str, b: str, und: bool,
              basis: str) -> R.ShippingModel:
    """مدل بازه‌خورده؛ برای همان ورودی‌ها در session نگه داشته می‌شود تا هر بازاجرا دوباره ساخته نشود."""
    if not (R._norm_date(a) or R._norm_date(b)):
        return m
    key = ((st.session_state.get(_MODEL) or (None,))[0], R._norm_date(a), R._norm_date(b), bool(und), basis)
    cached = st.session_state.get(_MODEL + "_f")
    if cached and cached[0] == key:
        return cached[1]
    out = R.filtered_model(m, df, extras, ref_date, start=a, end=b, include_undated=und, basis=basis)
    st.session_state[_MODEL + "_f"] = (key, out)
    return out
