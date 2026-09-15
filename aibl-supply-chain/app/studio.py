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

from app import analytics, motion, process_view, warehouse_view
from app.styles import band_chip, css, kpi_card
from app.theme import (BAND_ORDER, BANDS, SEQUENTIAL, SERIES, STATUS, TEXT_SECONDARY,
                       band_of, plotly_template)
from aibl.studio_core.field_catalog import build_catalog, catalog_groups, unique_labels
from aibl.studio_core.filters import FilterState, apply_filters, filter_options
from aibl.report.supply_views import build_material_view, build_bl_view, build_dept_view
from aibl.config.settings import SETTINGS
from aibl.warehouse import warehouse_from_settings

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
@st.cache_data(show_spinner="در حال بارگذاری Snapshot از Warehouse…")
def load_data(ref_date: str):
    """Studio از SQLite می‌خواند؛ Pipeline فقط وقتی Snapshot همان تاریخ نیست اجرا می‌شود."""
    wh = warehouse_from_settings()
    if SETTINGS.STUDIO_SOURCE != "pipeline":
        snap = wh.load_snapshot(ref_date=ref_date)
        if snap is not None and snap.ref_date == ref_date:
            return snap.df, snap.main, dict(snap.extras), "", snap.run_id
    from aibl.pipeline import Pipeline
    r = Pipeline(today=date.fromisoformat(ref_date)).run(build_report=False)
    snap = wh.load_snapshot(run_id=r.warehouse_run_id) if r.warehouse_run_id else None
    if snap is not None:
        return snap.df, snap.main, dict(snap.extras), "", snap.run_id
    return r.df, r.main, dict(r.extras), r.dashboard_path, r.warehouse_run_id


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

if st.sidebar.button("⟳ به‌روزرسانی Warehouse", use_container_width=True):
    try:
        from aibl.pipeline import Pipeline
        with st.spinner("اجرای Pipeline و ثبت Snapshot در SQLite…"):
            Pipeline(today=date.fromisoformat(ref_date)).run(build_report=False)
        st.cache_data.clear()
        st.rerun()
    except Exception as ex:
        st.sidebar.error(f"به‌روزرسانی ناموفق: {ex}")

try:
    raw, main, extras, official_excel, warehouse_run_id = load_data(ref_date)
except Exception as ex:
    st.error(f"خط لوله اجرا نشد: {ex}")
    st.info("اول `python -m aibl.doctor` را بزنید تا مسیر سورس‌ها بررسی شود.")
    st.stop()

df = main if not main.empty else raw
WAREHOUSE = warehouse_from_settings()
ARTIFACT_ROOT = Path(os.getenv("AIBL_DAILY_REPORT_ROOT") or SETTINGS.daily_report_root)
st.sidebar.caption(f"Snapshot: **{warehouse_run_id or '—'}**")
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
expert_role = st.sidebar.multiselect(
    "نقش کارشناس", opts.get("expert_role", []), default=opts.get("expert_role", []),
    help="کارشناس ترخیص، خرید، اعتبارات، ثبت سفارش و رفع تعهد نقش‌های جدا هستند.")
expert = st.sidebar.multiselect("کارشناس مالک", opts.get("expert", []),
                                default=opts.get("expert", []))
search = st.sidebar.text_input("جستجوی سریع", placeholder="Material / Order / BL / Expert")
critical_only = st.sidebar.checkbox("فقط پرونده‌های بحرانی")

state = FilterState(criticality=crit, management=mgmt, transport=transport,
                    expert=expert, expert_role=expert_role, search=search,
                    critical_only=critical_only)
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

if "مانده تعهد" in fdf.columns:
    from aibl.studio_core.grain import safe_agg
    commit = fnum(safe_agg(fdf, "مانده تعهد", "sum"))
else:
    commit = "—"

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

(tab_over, tab_proc, tab_supply, tab_analytics, tab_fields, tab_data,
 tab_quality, tab_warehouse, tab_export) = st.tabs(
    ["نمای اجرایی", "⛓ فرآیند", "🧭 دید تأمین", "⊞ تحلیل", "🧩 سازنده گزارش",
     "▦ داده", "◍ کیفیت داده", "🗄 انبار داده", "📦 HTML خروجی"])


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
#  ۳) دید تأمین — کجا / کِی / دست کیست
# ══════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False)
def _supply_view(kind: str, frame: pd.DataFrame) -> pd.DataFrame:
    """نما را کش می‌کند تا با هر تعامل کوچک از نو ساخته نشود."""
    return {"material": build_material_view, "bl": build_bl_view,
            "dept": build_dept_view}[kind](frame)


with tab_supply:
    panel_open("دید تأمین",
               "پاسخ به چهار سؤال: الان کجاست؟ از کِی؟ دست کیست؟ معطل چه کسی است؟")
    st.caption("مالک و مسئول قطعه در هر سه نما «کارشناس خرید» است — "
               "حتی وقتی توپ در زمین حوزه دیگری باشد.")
    sv1, sv2, sv3 = st.tabs(["متریال محور", "بارنامه محور", "اداره محور"])
    for tab, kind, fname in [(sv1, "material", "AIBL_Material_View.xlsx"),
                             (sv2, "bl", "AIBL_BL_View.xlsx"),
                             (sv3, "dept", "AIBL_Department_View.xlsx")]:
        with tab:
            view = _supply_view(kind, fdf)
            if view.empty:
                st.info("داده کافی برای این نما وجود ندارد.")
                continue
            st.dataframe(view, use_container_width=True, hide_index=True)
            st.caption("برای تحویل، این نما را در Report Builder داخل HTML قرار دهید؛ دریافت‌کننده از همان HTML خروجی Excel/PDF می‌گیرد.")


# ══════════════════════════════════════════════════════════════════════════
with tab_fields:
    st.markdown(
        f'<div class="panel"><h3>سازنده گزارش</h3><p class="hint">'
        f'هر <b>{len(ALL_COLUMNS):,}</b> فیلدی که خط لوله تولید می‌کند اینجا '
        f'قابل انتخاب است — از هر ۱۳ سورس. فیلدهای انتخابی مستقیماً به جدول، '
        f'HTML تعاملی می‌روند؛ Excel/PDF توسط دریافت‌کننده از همان HTML ساخته می‌شود.</p></div>', unsafe_allow_html=True)

    DEFAULTS = [c for c in ["KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_REG",
                            "CANONICAL_EXPERT", "ORG_DEPT", "TRANSPORT_MODE", BAND_COL, RES_COL]
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
with tab_warehouse:
    warehouse_view.render(WAREHOUSE, fdf, current_run_id=warehouse_run_id or None)


with tab_export:
    from aibl.studio_core import templates as tpl
    from aibl.studio_core.report_builder import ReportSpec, build as build_report
    from aibl.studio_core.designs import (ReportDesign, save_design, load_design,
                                          list_designs, EMAIL_CHARTS)
    from aibl.studio_core.chart_catalog import (CHART_SPECS, CHART_TITLES,
                                                 DEFAULT_HTML_CHARTS, DEFAULT_EMAIL_CHARTS)
    from aibl.integrations.daily_email import configured_recipients

    sel_cols = [c for c in st.session_state.sel_fields if c in fdf.columns]
    if "report_tabs" not in st.session_state:
        st.session_state.report_tabs = [{"title": "نمای اصلی", "fields": list(sel_cols)}]
    if "html_chart_keys" not in st.session_state:
        st.session_state.html_chart_keys = [x for x in DEFAULT_HTML_CHARTS if x in CHART_TITLES]
    if "email_chart_keys" not in st.session_state:
        st.session_state.email_chart_keys = [x for x in DEFAULT_EMAIL_CHARTS if x in CHART_TITLES]
    if "studio_email_to" not in st.session_state:
        st.session_state.studio_email_to = "; ".join(configured_recipients())
    st.session_state.setdefault("studio_email_cc", "")
    st.session_state.setdefault("studio_email_header", "هوشمندی روزانه زنجیره تأمین خودرو")
    st.session_state.setdefault("studio_email_intro", "این گزارش برای تصمیم‌گیری روزانه تأمین، حمل، گمرک و پشتیبانی تولید تهیه شده است.")

    st.info("**Artifact اصلی این نسخه فقط HTML است.** گیرنده داخل همان فایل می‌تواند "
            "برش فعال را به Excel واقعی صادر کند یا با دکمه «PDF / چاپ» همان گزارش را "
            "با موتور مرورگر به PDF ذخیره کند. SQLite/Studio هیچ فایل Excel را به‌عنوان منبع داده نگه نمی‌دارد.")

    with st.container(border=True):
        panel_open("۰ · طرح‌های ذخیره‌شده",
                   "طرح گزارش بیرون از پکیج ذخیره می‌شود؛ تنظیمات ایمیل نیز می‌تواند داخل Warehouse به‌صورت Profile پایدار ذخیره شود.")
        d1, d2, d3 = st.columns([2, 1, 1])
        design_name = d1.text_input("نام طرح", value="گزارش HTML من", key="design_name")
        saved = list_designs()
        chosen = d2.selectbox("بازیابی طرح", ["—"] + saved, key="chosen_design")
        if d3.button("↥ ذخیره طرح", use_container_width=True):
            design = ReportDesign(
                name=design_name.strip() or "گزارش",
                template=st.session_state.get("report_template_pick", "executive"),
                fields=list(sel_cols), tabs=st.session_state.report_tabs,
                formats=["html"], visuals=True, tables=True, max_rows=5000,
                file_stem=design_name.strip() or "AIBL Report",
                html_charts=list(st.session_state.html_chart_keys),
                email_charts=list(st.session_state.email_chart_keys), title="AIBL")
            save_design(design)
            st.success("طرح HTML ذخیره شد.")
        if chosen != "—" and st.button("↧ بارگذاری طرح", use_container_width=True):
            try:
                d = load_design(chosen)
                st.session_state.sel_fields = [c for c in d.fields if c in df.columns]
                st.session_state.report_tabs = [x for x in d.tabs if x.get("fields")] or [{"title":"نمای اصلی","fields":list(sel_cols)}]
                st.session_state.html_chart_keys = [x for x in (getattr(d, "html_charts", []) or d.email_charts) if x in CHART_TITLES]
                st.session_state.email_chart_keys = [x for x in d.email_charts if x in CHART_TITLES]
                st.session_state.report_template_pick = d.template
                st.rerun()
            except Exception as ex:
                st.error(f"بارگذاری طرح ناموفق بود: {ex}")

    with st.container(border=True):
        panel_open("۱ · قالب و تب‌های HTML",
                   "فیلتر، KPI و Process Explorer داخل فایل آفلاین کار می‌کنند؛ هر تب می‌تواند جداگانه Excel شود.")
        keys = list(tpl.TEMPLATES)
        pick = st.radio("قالب", keys, horizontal=True, label_visibility="collapsed",
                        format_func=lambda k: f"{tpl.TEMPLATES[k].icon} {tpl.TEMPLATES[k].title}",
                        key="report_template_pick")
        T = tpl.get(pick)
        st.caption(T.description)
        if st.button("استفاده از فیلدهای پیش‌فرض این قالب", use_container_width=True):
            st.session_state.sel_fields = [c for c in T.default_fields if c in df.columns]
            st.rerun()

        for i, tab in enumerate(st.session_state.report_tabs):
            c1, c2, c3 = st.columns([1, 3, .7])
            title_i = c1.text_input("عنوان تب", value=tab.get("title","تب"), key=f"tab_title_{i}")
            fields_i = c2.multiselect("فیلدهای تب", ALL_COLUMNS,
                default=[c for c in tab.get("fields", sel_cols) if c in ALL_COLUMNS],
                format_func=lab, key=f"tab_fields_{i}")
            remove = c3.button("حذف", key=f"tab_rm_{i}", disabled=len(st.session_state.report_tabs) <= 1)
            st.session_state.report_tabs[i] = {"title": title_i, "fields": fields_i}
            if remove:
                st.session_state.report_tabs.pop(i); st.rerun()
        if st.button("＋ افزودن تب", use_container_width=True):
            st.session_state.report_tabs.append({"title": f"تب {len(st.session_state.report_tabs)+1}", "fields": list(sel_cols)})
            st.rerun()

    with st.container(border=True):
        panel_open("۲ · محتوای Artifact")
        a,b,c = st.columns(3)
        want_vis = a.checkbox("نمودارها / ویژوال", value=True)
        want_tab = b.checkbox("جدول‌ها", value=True)
        rows_cap = c.number_input("حداکثر ردیف داخل HTML", 100, 50000, min(int(T.max_rows),50000), 100)
        stem = st.text_input("نام فایل HTML", f"AIBL {T.title}")
        st.caption(f"{len(sel_cols):,} فیلد انتخاب شده است. برای فایل‌های بزرگ، فقط فیلدهای لازم را داخل HTML بگذارید؛ تاریخچه کامل در SQLite می‌ماند.")

    with st.container(border=True):
        panel_open("۲٫۵ · کاتالوگ نمودارها",
                   "نمودار HTML و نمودار داخل ایمیل مستقل انتخاب می‌شوند. نمودار فرآیند اگر Event Log کافی نباشد، به توزیع مرحله فعلی fallback می‌کند.")
        hc, ec = st.columns(2)
        html_pick = hc.multiselect("نمودارهای داخل HTML", list(CHART_TITLES),
            default=[x for x in st.session_state.html_chart_keys if x in CHART_TITLES],
            format_func=lambda k: f"{CHART_SPECS[k].group} · {CHART_TITLES[k]}", key="html_chart_picker")
        email_pick = ec.multiselect("نمودارهای داخل ایمیل", list(CHART_TITLES),
            default=[x for x in st.session_state.email_chart_keys if x in CHART_TITLES],
            format_func=lambda k: f"{CHART_SPECS[k].group} · {CHART_TITLES[k]}", key="email_chart_picker")
        st.session_state.html_chart_keys = html_pick
        st.session_state.email_chart_keys = email_pick

    with st.container(border=True):
        panel_open("۳ · کنترل صحت محاسبات",
                   "تجمیع‌های داخل HTML نیز از Grain Registry پیروی می‌کنند.")
        from aibl.studio_core.grain import fanout as _fanout, integrity_report as _integ
        fo = _fanout(fdf)
        risky = fo[fo["ضریب تکرار"] > 1.0] if not fo.empty else pd.DataFrame()
        if not risky.empty:
            st.warning("دانه‌های دارای fan-out: " + "، ".join(
                f"{r['دانه']} ×{r['ضریب تکرار']}" for _,r in risky.iterrows()))
        if not fo.empty:
            st.dataframe(fo, use_container_width=True, hide_index=True)
        integ = _integ(fdf, sel_cols, DISPLAY)
        if not integ.empty:
            with st.expander(f"ردپای محاسباتی {len(integ)} ستون عددی"):
                st.dataframe(integ, use_container_width=True, hide_index=True)

    def _build_html_artifact():
        out_dir = ARTIFACT_ROOT / ref_date / "reports"
        spec = ReportSpec(template=pick, fields=sel_cols, ref_date=ref_date,
                          title=f"AIBL — {T.title}", formats=["html"],
                          visuals=want_vis, tables=want_tab, max_rows=int(rows_cap),
                          file_stem=stem.strip() or f"AIBL {T.title}",
                          tabs=st.session_state.report_tabs,
                          html_charts=list(st.session_state.html_chart_keys),
                          email_charts=list(st.session_state.email_chart_keys),
                          warehouse_run_id=warehouse_run_id or "")
        res = build_report(fdf, extras, spec, DISPLAY, out_dir)
        p = res.files.get("html")
        if p:
            WAREHOUSE.audit("REPORT_HTML_BUILT", run_id=warehouse_run_id or None,
                            actor="studio", entity_type="report", entity_id=p.name,
                            message=f"rows={len(fdf)} fields={len(sel_cols)} template={pick}")
        return res

    if st.button("🛠 ساخت فایل HTML نهایی", type="primary", use_container_width=True):
        with st.spinner("ساخت HTML خودبسنده…"):
            try:
                res = _build_html_artifact()
                st.session_state.report_files = {k:str(v) for k,v in res.files.items()}
                st.session_state.report_msgs = res.messages
            except Exception as ex:
                st.session_state.report_files = {}
                st.session_state.report_msgs = [f"⚠️ ساخت ناموفق بود: {ex}"]
        st.rerun()

    files = st.session_state.get("report_files") or {}
    msgs = st.session_state.get("report_msgs") or []
    html_path = Path(files["html"]) if files.get("html") else None
    if msgs:
        with st.container(border=True):
            panel_open("۴ · Artifact قابل ارسال")
            for m in msgs:
                (st.warning if str(m).startswith("⚠️") else st.write)(m)
            if html_path and html_path.exists():
                st.download_button("⬇ دانلود HTML نهایی", html_path.read_bytes(), file_name=html_path.name,
                                   mime="text/html", use_container_width=True, key="dl_html_primary")
                st.success("همین یک فایل را ارسال کنید. داخل فایل: فیلتر زنده + Export Excel + PDF/Print وجود دارد.")

    with st.container(border=True):
        panel_open("۵ · Email Composer / Outlook",
                   "TO، CC، Subject، Header و متن ایمیل از همین‌جا تنظیم می‌شوند. فقط HTML attach می‌شود؛ Excel/PDF داخل خود HTML ساخته می‌شود.")

        profs = WAREHOUSE.list_profiles("email_composer")
        pc1, pc2, pc3 = st.columns([2, 1, 1])
        profile_name = pc1.text_input("نام پروفایل ایمیل", value="گزارش روزانه", key="email_profile_name")
        profile_pick = pc2.selectbox("پروفایل‌های ذخیره‌شده", ["—"] + profs, key="email_profile_pick")
        if pc3.button("ذخیره پروفایل", use_container_width=True, key="save_email_profile"):
            WAREHOUSE.save_profile("email_composer", profile_name.strip() or "گزارش روزانه", {
                "to": st.session_state.studio_email_to, "cc": st.session_state.studio_email_cc,
                "subject": st.session_state.get("studio_subject", f"AIBL — زنجیره تأمین خودرو — {ref_date}"),
                "header": st.session_state.studio_email_header, "intro": st.session_state.studio_email_intro,
                "charts": list(st.session_state.email_chart_keys),
            })
            st.success("پروفایل ایمیل داخل همان Warehouse ذخیره شد.")
        if profile_pick != "—" and st.button("بارگذاری پروفایل ایمیل", use_container_width=True, key="load_email_profile"):
            ep = WAREHOUSE.load_profile("email_composer", profile_pick)
            st.session_state.studio_email_to = ep.get("to", "")
            st.session_state.studio_email_cc = ep.get("cc", "")
            st.session_state.studio_subject = ep.get("subject", f"AIBL — زنجیره تأمین خودرو — {ref_date}")
            st.session_state.studio_email_header = ep.get("header", "هوشمندی روزانه زنجیره تأمین خودرو")
            st.session_state.studio_email_intro = ep.get("intro", "")
            st.session_state.email_chart_keys = [x for x in ep.get("charts", []) if x in CHART_TITLES]
            st.rerun()

        to_cc = st.columns(2)
        to_cc[0].text_input("TO (با ; یا , جدا کنید)", key="studio_email_to")
        to_cc[1].text_input("CC (اختیاری)", key="studio_email_cc")
        st.text_input("Subject", value=f"AIBL — گزارش زنجیره تأمین خودرو — {ref_date}", key="studio_subject")
        st.text_input("Header ایمیل", key="studio_email_header")
        st.text_area("متن مقدمه ایمیل", key="studio_email_intro", height=90)
        display_only = st.checkbox("فقط نمایش در Outlook؛ ارسال نکن", value=True, key="studio_display")
        from aibl.integrations.daily_email import email_font_status
        _font = email_font_status()
        if _font.get("ok"):
            st.success(f"فونت نمودار ایمیل: {_font.get('family')} · آماده")
        else:
            st.warning("IRANSans برای PNG نمودارهای ایمیل روی این سیستم پیدا نشد. "
                       "AIBL_FONT_PATH را به فایل فونت نصب‌شده/دارای مجوز سازمان اشاره دهید. "
                       "متن Outlook همچنان IRANSans را درخواست می‌کند ولی گیرنده نیز باید فونت را داشته باشد.")
        if st.button("📨 ساخت/نمایش ایمیل در Outlook", use_container_width=True):
            try:
                if not (html_path and html_path.exists()):
                    res = _build_html_artifact()
                    html_path = Path(res.files["html"])
                    st.session_state.report_files = {k:str(v) for k,v in res.files.items()}
                from aibl.integrations.daily_email import create_studio_email
                r = create_studio_email(day=date.fromisoformat(ref_date), df=fdf,
                        html_report=html_path, selected_charts=st.session_state.email_chart_keys,
                        process_extras=extras, to=st.session_state.studio_email_to,
                        cc=st.session_state.studio_email_cc, subject=st.session_state.studio_subject,
                        header_title=st.session_state.studio_email_header, intro_text=st.session_state.studio_email_intro,
                        send=not display_only, display=display_only)
                WAREHOUSE.audit("REPORT_HTML_EMAIL", run_id=warehouse_run_id or None,
                                actor="studio", entity_type="report", entity_id=html_path.name,
                                message=f"to={r['recipients']} cc={r['cc']} sent={r['sent']}")
                st.success(f"Outlook آماده شد · TO: {r['recipients']} · CC: {r['cc']} · {r['charts']} نمودار · فقط HTML")
            except Exception as ex:
                st.error(f"Outlook: {ex}")

st.caption("AIBL Studio — SQLite لایه ماندگار داده و Process Log است؛ HTML artifact قابل ارسال است و Excel/PDF از داخل همان HTML تولید می‌شود.")
