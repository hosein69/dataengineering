# -*- coding: utf-8 -*-
"""AIBL Studio — پلتفرم تحلیل و گزارش‌سازی زنجیره تأمین.

بازنویسی کامل رابط. سه تغییر بنیادی نسبت به نسخه قبل:

1. **کل داده قابل گزارش است.** نسخه قبل کاتالوگ فیلد را دستی می‌نوشت و
   فقط ۲۲ ستون از ۳۶۷ ستون خط لوله را نشان می‌داد — ۹۴٪ داده در رابط
   کاربری وجود نداشت. حالا کاتالوگ از خود adapterها مشتق می‌شود، پس هر
   ستون هر سورس (و هر adapter جدیدی که اضافه شود) خودبه‌خود قابل انتخاب،
   قابل فیلتر و قابل خروجی‌گیری است.
2. **کیفیت داده دیده می‌شود.** برای هر فیلد درصد پرشدگی نمایش داده می‌شود،
   چون «ستون خالی» و «ستون پرِ صفر» دو چیز کاملاً متفاوت‌اند.
3. **رابط قابل ارائه است.** پالت وضعیت اعتبارسنجی‌شده، هدر زنده‌ی
   واکنش‌گر به موس، و کارت‌هایی که با نشانگر حرکت می‌کنند.
"""
from __future__ import annotations

import io
import os
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd
import streamlit as st

st.set_page_config(page_title="AIBL Studio", page_icon="◈",
                   layout="wide", initial_sidebar_state="expanded")

from app import analytics, motion, process_view
from app.styles import band_chip, css, kpi_card
from app.theme import (BAND_ORDER, BANDS, SEQUENTIAL, SERIES, STATUS, TEXT_SECONDARY,
                       band_of, plotly_template)
from aibl.studio_core.excel_export import (DEFAULT_CUSTOM_NAME, OfficialReportOverwrite,
                                            build_custom_excel)
from aibl.studio_core.field_catalog import build_catalog, catalog_groups, unique_labels
from aibl.studio_core.filters import FilterState, apply_filters, filter_options
from aibl.studio_core.html_export import build_dynamic_html

try:
    import plotly.express as px
    import plotly.graph_objects as go
    import plotly.io as pio
    pio.templates["aibl"] = plotly_template()
    pio.templates.default = "aibl"
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

st.markdown(css(), unsafe_allow_html=True)

BAND_COL = "بحرانی (کوتاه)"
CODE_COL = "کد طبقه بحرانی"
RES_COL = "مقاومت (روز)"


# ══════════════════════════════════════════════════════════════════════════
#  داده
# ══════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner="در حال اجرای خط لوله…")
def load_data(ref_date: str):
    # AIBL_TODAY بیرون از این تابع ست می‌شود — در cache hit بدنه اجرا نمی‌شود.
    from aibl.pipeline import Pipeline
    r = Pipeline().run(build_report=True)
    return r.df, r.main, dict(r.extras), r.dashboard_path


def panel_open(title: str, hint: str = "") -> None:
    """عنوان کارت — داخل همان ظرفی که نمودار در آن رندر می‌شود."""
    st.markdown(f'<div style="margin:2px 2px 8px"><div style="font-size:15px;'
                f'font-weight:700;color:var(--text)">{title}</div>'
                + (f'<div style="font-size:12px;color:var(--text-3);margin-top:2px">'
                   f'{hint}</div>' if hint else "")
                + '</div>', unsafe_allow_html=True)


def fnum(x, nd: int = 0) -> str:
    try:
        return f"{float(x):,.{nd}f}"
    except Exception:
        return "—"


# ── نوار کناری ────────────────────────────────────────────────────────────
st.sidebar.markdown("### ◈ AIBL Studio")
st.sidebar.caption("تحلیل و گزارش‌سازی زنجیره تأمین")

_default_ref = os.environ.get("AIBL_TODAY") or str(date.today())
ref_date = st.sidebar.text_input("تاریخ مرجع", value=_default_ref).strip()
try:
    date.fromisoformat(ref_date)
except ValueError:
    st.sidebar.error("تاریخ باید به شکل YYYY-MM-DD باشد.")
    st.stop()
os.environ["AIBL_TODAY"] = ref_date

if st.sidebar.button("↻ اجرای مجدد خط لوله", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

try:
    raw, main, extras, official_excel = load_data(ref_date)
except Exception as ex:
    st.error(f"خط لوله اجرا نشد: {ex}")
    st.info("اول `python -m aibl.doctor` را بزنید تا مسیر سورس‌ها بررسی شود.")
    st.stop()

df = main if not main.empty else raw
CATALOG = build_catalog(df)
GROUPS = catalog_groups(CATALOG)
SPEC_BY_COL = {s.column: s for s in CATALOG}
ALL_COLUMNS = [s.column for s in CATALOG]
# نام نمایشی یکتا — چند سورس برچسب یکسان دارند («شرح کالا»، «وضعیت»، …)
DISPLAY = unique_labels(CATALOG)


def lab(col: str) -> str:
    """نام نمایشی یکتا — مستقیماً برای rename ستون‌ها امن است."""
    return DISPLAY.get(col, str(col))


# ── فیلترها ───────────────────────────────────────────────────────────────
st.sidebar.markdown("#### فیلترها")
opts = filter_options(df)
crit = st.sidebar.multiselect("طبقه بحرانی", opts["criticality"], default=opts["criticality"])
mgmt = st.sidebar.multiselect("مدیریت", opts["management"], default=opts["management"])
transport = st.sidebar.multiselect("روش حمل", opts["transport"], default=opts["transport"])
expert = st.sidebar.multiselect("کارشناس", opts.get("expert", []), default=opts.get("expert", []))
search = st.sidebar.text_input("جستجوی سریع", placeholder="Material / Order / BL / Expert")
critical_only = st.sidebar.checkbox("فقط پرونده‌های بحرانی")

state = FilterState(criticality=crit, management=mgmt, transport=transport,
                    expert=expert, search=search, critical_only=critical_only)
fdf = apply_filters(df, state)

st.sidebar.markdown("---")
st.sidebar.caption(f"**{len(df):,}** ردیف · **{len(ALL_COLUMNS):,}** فیلد در کاتالوگ")
st.sidebar.caption(f"**{len(fdf):,}** ردیف پس از فیلتر")


# ── محاسبات KPI ───────────────────────────────────────────────────────────
def band_count(code: str) -> int:
    if CODE_COL not in fdf.columns:
        return 0
    return int((fdf[CODE_COL].astype(str) == code).sum())


def uniq_where(flag: str, key: str) -> int:
    if not {flag, key} <= set(fdf.columns):
        return 0
    m = fdf[flag].fillna(False).astype(bool)
    return int(fdf.loc[m, key].replace("", pd.NA).nunique())


min_res = "—"
if RES_COL in fdf.columns:
    v = pd.to_numeric(fdf[RES_COL], errors="coerce").min()
    min_res = fnum(v, 1) if pd.notna(v) else "—"

commit = fnum(pd.to_numeric(fdf.get("مانده تعهد"), errors="coerce").sum()) \
    if "مانده تعهد" in fdf.columns else "—"

# ── هدر زنده ──────────────────────────────────────────────────────────────
motion.hero(
    "AIBL Studio",
    f"تاریخ مرجع {ref_date} · {len(fdf):,} پرونده · {len(ALL_COLUMNS):,} فیلد قابل گزارش",
    [["توقف خط", str(band_count("STOCKOUT")), STATUS["stockout"]],
     ["بحرانی", str(band_count("CRITICAL")), STATUS["critical"]],
     ["بارنامه بحرانی", str(uniq_where("BL_CRITICAL", "CANONICAL_BL")), STATUS["serious"]],
     ["کمترین مقاومت", min_res, STATUS["warning"]]],
    height=200,
)
motion.cursor_glow()

# ── ردیف KPI ──────────────────────────────────────────────────────────────
cards = [
    ("توقف خط", str(band_count("STOCKOUT")), "موجودی صفر", STATUS["stockout"], "⏹"),
    ("بحرانی", str(band_count("CRITICAL")), "مقاومت زیر ۱۰ روز", STATUS["critical"], "⬤"),
    ("در حال بحرانی شدن", str(band_count("BECOMING_CRITICAL")), "بین ۱۰ تا ۲۰ روز", STATUS["serious"], "◤"),
    ("تحت نظر", str(band_count("WATCH")), "بین ۲۰ تا ۴۵ روز", STATUS["warning"], "◆"),
    ("ایمن", str(band_count("SAFE")), "بیش از ۴۵ روز", STATUS["good"], "✓"),
    ("کمترین مقاومت", min_res, "بحرانی‌ترین قطعه", STATUS["stockout"], "⏱"),
    ("سفارش بحرانی", str(uniq_where("ORDER_CRITICAL", "CANONICAL_ORDER")), "پرونده‌های درگیر", STATUS["serious"], "◈"),
    ("جمع مانده تعهد", commit, "سورس NTSW", STATUS["neutral"], "₪"),
]
st.markdown('<div class="kpi-row">' + "".join(kpi_card(*c) for c in cards) + "</div>",
            unsafe_allow_html=True)

st.markdown(
    '<div style="margin:12px 0 2px">' +
    "".join(band_chip(*band_of(k)) for k in BAND_ORDER) +
    '</div>', unsafe_allow_html=True)

(tab_over, tab_proc, tab_analytics, tab_fields, tab_data,
 tab_quality, tab_export) = st.tabs(
    ["نمای اجرایی", "⛓ فرآیند", "⊞ تحلیل", "🧩 سازنده گزارش",
     "▦ داده", "◍ کیفیت داده", "📦 خروجی"])


# ══════════════════════════════════════════════════════════════════════════
#  ۱) نمای اجرایی
# ══════════════════════════════════════════════════════════════════════════
with tab_over:
    c1, c2 = st.columns([1, 1])

    with c1, st.container(border=True):
        panel_open("ترکیب طبقه بحرانی",
                   "هر طبقه با رنگ، آیکن و برچسب — رنگ به‌تنهایی حامل معنا نیست.")
        if CODE_COL in fdf.columns and HAS_PLOTLY:
            counts = fdf[CODE_COL].astype(str).value_counts()
            codes = [c for c in BAND_ORDER if c in counts.index]
            if codes:
                vals = [int(counts[c]) for c in codes]
                colors = [BANDS[c][0] for c in codes]
                labels = [f"{BANDS[c][1]} {BANDS[c][2]}" for c in codes]
                fig = go.Figure(go.Bar(
                    x=labels, y=vals, marker_color=colors,
                    marker_line=dict(color="#fcfcfb", width=2),
                    text=[f"{v:,}" for v in vals], textposition="outside",
                    hovertemplate="%{x}<br>%{y:,} پرونده<extra></extra>"))
                fig.update_layout(height=340, showlegend=False,
                                  yaxis_title="تعداد پرونده", xaxis_title=None,
                                  uniformtext=dict(minsize=10, mode="show"))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("ستون طبقه بحرانی در این اجرا موجود نیست.")

    with c2, st.container(border=True):
        panel_open("کم‌مقاومت‌ترین قطعات",
                   "مقاومت = موجودی ÷ نیاز روزانه. پایین‌ترین‌ها اول.")
        if {"KEY_MATERIAL", RES_COL} <= set(fdf.columns) and HAS_PLOTLY:
            x = fdf[["KEY_MATERIAL", RES_COL]].copy()
            x[RES_COL] = pd.to_numeric(x[RES_COL], errors="coerce")
            x = x.dropna().nsmallest(15, RES_COL)
            if not x.empty:
                fig = go.Figure(go.Bar(
                    x=x[RES_COL], y=x["KEY_MATERIAL"], orientation="h",
                    marker_color=[band_of(
                        "STOCKOUT" if v <= 0 else "CRITICAL" if v < 10
                        else "BECOMING_CRITICAL" if v < 20
                        else "WATCH" if v < 45 else "SAFE")[0] for v in x[RES_COL]],
                    marker_line=dict(color="#fcfcfb", width=2),
                    text=[f"{v:,.1f}" for v in x[RES_COL]], textposition="outside",
                    hovertemplate="%{y}<br>مقاومت %{x:.1f} روز<extra></extra>"))
                fig.update_layout(height=340, showlegend=False,
                                  xaxis_title="مقاومت (روز)", yaxis_title=None,
                                  yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("مقاومت عددی برای این فیلتر محاسبه نشده است.")

    c3, c4 = st.columns([1, 1])
    with c3, st.container(border=True):
        panel_open("بار سازمانی", "تعداد پرونده به تفکیک مدیریت.")
        if "ORG_DEPT" in fdf.columns and HAS_PLOTLY and not fdf.empty:
            g = (fdf.groupby("ORG_DEPT", dropna=False).size()
                 .reset_index(name="Cases").sort_values("Cases", ascending=False).head(12))
            fig = go.Figure(go.Bar(
                x=g["Cases"], y=g["ORG_DEPT"].astype(str), orientation="h",
                marker_color=SERIES[0], marker_line=dict(color="#fcfcfb", width=2),
                text=[f"{v:,}" for v in g["Cases"]], textposition="outside",
                hovertemplate="%{y}<br>%{x:,} پرونده<extra></extra>"))
            fig.update_layout(height=320, showlegend=False, xaxis_title="پرونده",
                              yaxis_title=None, yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, use_container_width=True)

    with c4, st.container(border=True):
        panel_open("گلوگاه فرآیند", "از لاگ رویداد (استاندارد Celonis).")
        b = extras.get("bottlenecks")
        if b is not None and not b.empty:
            st.dataframe(b.head(12), use_container_width=True, hide_index=True)
        else:
            st.info("لاگ رویداد برای این اجرا در دسترس نیست.")


# ══════════════════════════════════════════════════════════════════════════
#  ۲) فرآیند — کاوش لاگ رویداد، گلوگاه، واریانت و انطباق
# ══════════════════════════════════════════════════════════════════════════
with tab_proc:
    process_view.render(extras, fdf)


# ══════════════════════════════════════════════════════════════════════════
#  ۳) تحلیل — جدول متقاطع روی هر فیلد
# ══════════════════════════════════════════════════════════════════════════
with tab_analytics:
    analytics.render(fdf, CATALOG, lab)


# ══════════════════════════════════════════════════════════════════════════
#  ۴) سازنده گزارش — دسترسی به هر ۳۶۷ فیلد
# ══════════════════════════════════════════════════════════════════════════
with tab_fields:
    st.markdown(
        f'<div class="panel"><h3>سازنده گزارش</h3><p class="hint">'
        f'هر <b>{len(ALL_COLUMNS):,}</b> فیلدی که خط لوله تولید می‌کند اینجا '
        f'قابل انتخاب است — از هر ۱۳ سورس. فیلدهای انتخابی مستقیماً به جدول، '
        f'Excel و HTML می‌روند.</p></div>', unsafe_allow_html=True)

    DEFAULTS = [c for c in ["KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_REG",
                            "CANONICAL_EXPERT", "ORG_DEPT", "روش حمل", BAND_COL, RES_COL]
                if c in SPEC_BY_COL]
    if "sel_fields" not in st.session_state:
        st.session_state.sel_fields = list(DEFAULTS)

    fc1, fc2, fc3, fc4 = st.columns([2, 1, 1, 1])
    with fc1:
        q = st.text_input("جستجوی فیلد", placeholder="نام فارسی یا نام ستون…").strip().lower()
    with fc2:
        only_filled = st.checkbox("فقط فیلدهای دارای داده", value=False,
                                  help="فیلدهایی که در این اجرا حداقل یک مقدار دارند")
    with fc3:
        if st.button("انتخاب همه", use_container_width=True):
            st.session_state.sel_fields = list(ALL_COLUMNS)
            st.rerun()
    with fc4:
        if st.button("بازنشانی", use_container_width=True):
            st.session_state.sel_fields = list(DEFAULTS)
            st.rerun()

    sel = set(st.session_state.sel_fields)
    st.caption(f"انتخاب‌شده: **{len(sel):,}** از {len(ALL_COLUMNS):,} فیلد")

    for gname, specs in GROUPS.items():
        shown = [s for s in specs
                 if (not q or q in s.label.lower() or q in s.column.lower())
                 and (not only_filled or s.fill_pct > 0)]
        if not shown:
            continue
        n_sel = sum(1 for s in shown if s.column in sel)
        with st.expander(f"{gname} — {len(shown)} فیلد"
                         + (f" · {n_sel} انتخاب‌شده" if n_sel else ""),
                         expanded=bool(q)):
            bc1, bc2 = st.columns([1, 1])
            if bc1.button("افزودن این گروه", key=f"add_{gname}", use_container_width=True):
                st.session_state.sel_fields = list(
                    dict.fromkeys(st.session_state.sel_fields + [s.column for s in shown]))
                st.rerun()
            if bc2.button("حذف این گروه", key=f"rm_{gname}", use_container_width=True):
                drop = {s.column for s in shown}
                st.session_state.sel_fields = [c for c in st.session_state.sel_fields
                                               if c not in drop]
                st.rerun()
            rows = [{"فیلد": s.label, "ستون": s.column,
                     "پرشدگی": s.fill_pct, "نوع": s.dtype,
                     "انتخاب": s.column in sel} for s in shown]
            ed = st.data_editor(
                pd.DataFrame(rows), hide_index=True, use_container_width=True,
                key=f"ed_{gname}",
                column_config={
                    "انتخاب": st.column_config.CheckboxColumn("انتخاب", width="small"),
                    "پرشدگی": st.column_config.ProgressColumn(
                        "پرشدگی", format="%.0f%%", min_value=0, max_value=100),
                    "فیلد": st.column_config.TextColumn("فیلد", disabled=True),
                    "ستون": st.column_config.TextColumn("نام ستون", disabled=True),
                    "نوع": st.column_config.TextColumn("نوع", disabled=True, width="small"),
                })
            picked = set(ed.loc[ed["انتخاب"], "ستون"])
            group_cols = {s.column for s in shown}
            new_sel = [c for c in st.session_state.sel_fields
                       if c not in group_cols or c in picked]
            new_sel += [c for c in picked if c not in new_sel]
            if new_sel != st.session_state.sel_fields:
                st.session_state.sel_fields = new_sel
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════
#  ۵) داده
# ══════════════════════════════════════════════════════════════════════════
with tab_data:
    cols = [c for c in st.session_state.sel_fields if c in fdf.columns]
    if not cols:
        st.warning("هیچ فیلدی انتخاب نشده — از تب «سازنده گزارش» فیلد اضافه کنید.")
    else:
        st.markdown(f'<div class="panel"><h3>جدول زنده</h3><p class="hint">'
                    f'{len(fdf):,} ردیف × {len(cols):,} فیلد — با نام فارسی ستون‌ها.'
                    f'</p></div>', unsafe_allow_html=True)
        view = fdf[cols].rename(columns={c: lab(c) for c in cols})
        st.dataframe(view, use_container_width=True, height=560, hide_index=True)
        st.download_button(
            "⬇ دانلود CSV این نما", view.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"AIBL_{ref_date}.csv", mime="text/csv")


# ══════════════════════════════════════════════════════════════════════════
#  ۶) کیفیت داده
# ══════════════════════════════════════════════════════════════════════════
with tab_quality:
    st.markdown('<div class="panel"><h3>کیفیت داده به تفکیک سورس</h3>'
                '<p class="hint">ستون خالی و ستون پرِ صفر دو چیز متفاوت‌اند. '
                'اینجا معلوم می‌شود کدام رابطه برقرار نشده.</p></div>',
                unsafe_allow_html=True)

    qrows = [{"گروه": s.group, "فیلد": s.label, "ستون": s.column,
              "پرشدگی": s.fill_pct, "سورس": s.source or "محاسباتی"} for s in CATALOG]
    qdf = pd.DataFrame(qrows)

    gsum = (qdf.groupby("گروه")
            .agg(فیلد=("ستون", "count"), میانگین_پرشدگی=("پرشدگی", "mean"),
                 خالی=("پرشدگی", lambda s: int((s == 0).sum())))
            .reset_index().sort_values("میانگین_پرشدگی"))
    gsum["میانگین_پرشدگی"] = gsum["میانگین_پرشدگی"].round(1)

    # عمداً بدون نمودار میله‌ای: نام گروه‌ها (نقش سورس) بلندند و برچسب محور
    # به سه حرف بریده می‌شد — میله بدون برچسب خوانا نیست. جدول زیر همان
    # بزرگی را با نوار پیشرفت نشان می‌دهد و نام کامل را هم نگه می‌دارد.
    m1, m2, m3 = st.columns(3)
    m1.metric("میانگین پرشدگی کل", f"{qdf['پرشدگی'].mean():.0f}%")
    m2.metric("فیلدهای کاملاً خالی", f"{int((qdf['پرشدگی'] == 0).sum()):,}")
    m3.metric("فیلدهای دارای داده", f"{int((qdf['پرشدگی'] > 0).sum()):,}")

    st.dataframe(
        gsum.rename(columns={"میانگین_پرشدگی": "میانگین پرشدگی"}),
        use_container_width=True, hide_index=True, height=520,
        column_config={
            "گروه": st.column_config.TextColumn("گروه / سورس", width="large"),
            "فیلد": st.column_config.NumberColumn("تعداد فیلد", width="small"),
            "میانگین پرشدگی": st.column_config.ProgressColumn(
                "میانگین پرشدگی", format="%.0f%%", min_value=0, max_value=100),
            "خالی": st.column_config.NumberColumn("کاملاً خالی", width="small"),
        })

    empty = qdf[qdf["پرشدگی"] == 0]
    if not empty.empty:
        with st.expander(f"⚠️ {len(empty)} فیلد در این اجرا هیچ مقداری ندارند"):
            st.dataframe(empty[["گروه", "فیلد", "ستون", "سورس"]],
                         use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════
#  ۷) خروجی — سازنده گزارش با قالب، فرمت و کنترل صحت
# ══════════════════════════════════════════════════════════════════════════
with tab_export:
    from aibl.studio_core import templates as tpl
    from aibl.studio_core.grain import GRAIN_FA, column_grain, measure_kind, KIND_FA
    from aibl.studio_core.report_builder import ReportSpec, build as build_report

    sel_cols = [c for c in st.session_state.sel_fields if c in fdf.columns]

    with st.container(border=True):
        panel_open("۱ · قالب گزارش",
                   "قالب فقط چیدمان و نقطه شروع فیلدهاست؛ انتخاب نهایی فیلد با شماست.")
        keys = list(tpl.TEMPLATES)
        pick = st.radio(
            "قالب", keys, horizontal=True, label_visibility="collapsed",
            format_func=lambda k: f"{tpl.TEMPLATES[k].icon} {tpl.TEMPLATES[k].title}")
        T = tpl.get(pick)
        st.caption(T.description)
        c1, c2 = st.columns([1, 1])
        if c1.button("استفاده از فیلدهای پیش‌فرض این قالب", use_container_width=True):
            st.session_state.sel_fields = [c for c in T.default_fields if c in df.columns]
            st.rerun()
        c2.caption(f"بخش‌ها: " + " · ".join(tpl.SECTIONS.get(x, x) for x in T.sections))

    with st.container(border=True):
        panel_open("۲ · محتوا و فرمت")
        a, b, c = st.columns([1, 1, 1])
        with a:
            st.markdown("**فرمت خروجی**")
            f_xls = st.checkbox("Excel", value=True)
            f_html = st.checkbox("HTML داینامیک (فیلترپذیر)", value=True)
            f_pdf = st.checkbox("PDF", value=True)
        with b:
            st.markdown("**محتوا**")
            want_vis = st.checkbox("نمودارها / ویژوال", value=True)
            want_tab = st.checkbox("جدول‌ها", value=True)
        with c:
            st.markdown("**دامنه**")
            rows_cap = st.number_input("حداکثر ردیف", 100, 100000,
                                       int(T.max_rows), 100)
            stem = st.text_input("نام فایل", f"AIBL {T.title}")
        st.caption(f"فیلدهای انتخابی: **{len(sel_cols):,}** — از تب «سازنده گزارش» "
                   f"تغییرشان دهید.")

    # ── کنترل صحت، پیش از ساخت ──
    with st.container(border=True):
        panel_open("۳ · کنترل صحت محاسبات",
                   "هر ستون عددی با دانه‌ی خودش تجمیع می‌شود تا دوباره‌شماری رخ ندهد.")
        from aibl.studio_core.grain import fanout as _fanout, integrity_report as _integ
        fo = _fanout(fdf)
        if not fo.empty:
            risky = fo[fo["ضریب تکرار"] > 1.0]
            if not risky.empty:
                st.warning(
                    "دانه‌های زیر در این فیلتر تکرار دارند؛ جمع ساده روی آن‌ها "
                    "چند برابر می‌شد و به‌جایش تجمیع دانه‌ای اعمال می‌شود: "
                    + "، ".join(f"{r['دانه']} ×{r['ضریب تکرار']}"
                                for _, r in risky.iterrows()))
            else:
                st.success("در این فیلتر هیچ دانه‌ای تکرار ندارد — جمع ساده و "
                           "جمع دانه‌ای یکی می‌شوند.")
            st.dataframe(fo, use_container_width=True, hide_index=True)
        integ = _integ(fdf, sel_cols, DISPLAY)
        if not integ.empty:
            with st.expander(f"ردپای محاسباتی {len(integ)} ستون عددی", expanded=False):
                st.dataframe(integ, use_container_width=True, hide_index=True)

    # ── ساخت ──
    formats = ([("excel") ] if f_xls else []) + (["html"] if f_html else []) \
        + (["pdf"] if f_pdf else [])
    if st.button("🛠 ساخت گزارش", type="primary", use_container_width=True,
                 disabled=not formats):
        out_dir = (Path(os.getenv("AIBL_DAILY_REPORT_ROOT",
                                  str(Path(official_excel).parent)))
                   / ref_date / "reports")
        spec = ReportSpec(template=pick, fields=sel_cols, ref_date=ref_date,
                          title=f"AIBL — {T.title}", formats=formats,
                          visuals=want_vis, tables=want_tab,
                          max_rows=int(rows_cap), file_stem=stem.strip() or f"AIBL {T.title}")
        with st.spinner("در حال ساخت گزارش…"):
            try:
                res = build_report(fdf, extras, spec, DISPLAY, out_dir)
                st.session_state.report_files = {k: str(v) for k, v in res.files.items()}
                st.session_state.report_msgs = res.messages
            except Exception as ex:
                st.session_state.report_files = {}
                st.session_state.report_msgs = [f"⚠️ ساخت ناموفق بود: {ex}"]
        st.rerun()

    files = st.session_state.get("report_files") or {}
    msgs = st.session_state.get("report_msgs") or []
    if msgs:
        with st.container(border=True):
            panel_open("۴ · خروجی‌ها")
            for m in msgs:
                (st.warning if str(m).startswith("⚠️") else st.write)(m)
            mimes = {
                "excel": ("⬇ دانلود Excel", "application/vnd.openxmlformats-"
                          "officedocument.spreadsheetml.sheet"),
                "html": ("⬇ دانلود HTML داینامیک", "text/html"),
                "pdf": ("⬇ دانلود PDF", "application/pdf"),
            }
            dl = st.columns(max(len(files), 1))
            for i, (kind, path) in enumerate(files.items()):
                p = Path(path)
                if not p.exists():
                    continue
                label, mime = mimes.get(kind, (f"⬇ {kind}", "application/octet-stream"))
                dl[i].download_button(label, p.read_bytes(), file_name=p.name,
                                      mime=mime, use_container_width=True,
                                      key=f"dl_{kind}")

    with st.container(border=True):
        panel_open("گزارش رسمی خط لوله",
                   "۱۳ شیت کامل، ساخته‌شده توسط خط لوله — فیلترنشده.")
        if official_excel and Path(official_excel).exists():
            st.download_button("⬇ دانلود Excel رسمی", Path(official_excel).read_bytes(),
                               file_name=Path(official_excel).name,
                               mime=("application/vnd.openxmlformats-officedocument"
                                     ".spreadsheetml.sheet"))

st.caption("AIBL Studio — لایه نمایش و خروجی روی همان Pipeline/Rulebook موجود؛ "
           "منطق کسب‌وکار در موتور AIBL باقی می‌ماند.")
