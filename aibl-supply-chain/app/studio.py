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
import streamlit.components.v1 as components

# هویت سازمانی پیش از set_page_config لازم است — عنوان پنجره از آن
# می‌آید و set_page_config باید نخستین فراخوانی st باشد.
from aibl.report import brand as _BRAND  # noqa: E402

st.set_page_config(page_title=f"{_BRAND.PRODUCT} · {_BRAND.LOCKUP}", page_icon="◈",
                   layout="wide", initial_sidebar_state="expanded")

from app import analytics, motion, process_view
from app.styles import band_chip, css, kpi_card
from app.theme import (BAND_ORDER, BANDS, SEQUENTIAL, SERIES, STATUS, TEXT_SECONDARY,
                       band_text_color, finalize,
                       band_of, plotly_template)
from aibl.studio_core.excel_export import (DEFAULT_CUSTOM_NAME, OfficialReportOverwrite,
                                            build_custom_excel)
from aibl.studio_core.field_catalog import build_catalog, catalog_groups, unique_labels
from aibl.studio_core.filters import FilterState, apply_filters, filter_options
from aibl.studio_core.html_export import build_dynamic_html
from aibl.report.supply_views import build_material_view, build_bl_view, build_dept_view

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
st.sidebar.markdown(f"### ◈ {_BRAND.PRODUCT_SHORT}")
st.sidebar.caption(_BRAND.LOCKUP_FULL)
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

commit = fnum(pd.to_numeric(fdf.get("مانده تعهد"), errors="coerce").sum()) \
    if "مانده تعهد" in fdf.columns else "—"

# ── هدر زنده ──────────────────────────────────────────────────────────────
motion.hero(
    _BRAND.PRODUCT,
    f"{_BRAND.LOCKUP_FULL}  ·  تاریخ مرجع {ref_date}  ·  {len(fdf):,} پرونده"
    f"  ·  {len(ALL_COLUMNS):,} فیلد قابل گزارش",
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
    "".join(band_chip(*band_of(k), text=band_text_color(k)) for k in BAND_ORDER) +
    '</div>', unsafe_allow_html=True)

(tab_over, tab_proc, tab_supply, tab_analytics, tab_evidence, tab_fields,
 tab_data, tab_quality, tab_export, tab_send) = st.tabs(
    ["نمای اجرایی", "⛓ فرآیند", "🧭 دید تأمین", "⊞ تحلیل", "🔬 گزارش تحلیلی",
     "🧩 سازنده گزارش", "▦ داده", "◍ کیفیت داده", "📦 خروجی",
     "✉️ ارسال گزارش"])


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
                st.plotly_chart(finalize(fig), use_container_width=True, theme=None)
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
                st.plotly_chart(finalize(fig), use_container_width=True, theme=None)
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
            st.plotly_chart(finalize(fig), use_container_width=True, theme=None)

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
            # ساخت Excel فقط با کلیک کاربر — نه در هر بازتولید صفحه
            if st.checkbox("آماده‌سازی خروجی Excel", key=f"prep_{kind}"):
                bio = io.BytesIO()
                with pd.ExcelWriter(bio, engine="openpyxl") as ew:
                    view.to_excel(ew, index=False, sheet_name="Supply View")
                st.download_button(
                    "⬇️ دانلود Excel", bio.getvalue(), file_name=fname,
                    mime=("application/vnd.openxmlformats-officedocument"
                          ".spreadsheetml.sheet"),
                    key=f"dl_{kind}")


# ══════════════════════════════════════════════════════════════════════════
#  ۴) گزارش تحلیلی — علیت سبک و قابل استناد
# ══════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False)
def _analysis_html(frame: pd.DataFrame, ref: str, labels: dict) -> str:
    from aibl.analytics.report import build_analysis_html
    return build_analysis_html(frame, ref, labels)


with tab_evidence:
    panel_open("گزارش تحلیلی",
               "نرخ تجربی با بازه اطمینان، و همان مقایسه پس از کنترل مخدوش‌کننده.")
    st.caption("عمداً بدون یادگیری ماشین: عددی که مبنای تصمیم می‌شود باید به یک "
               "جمله ساده تجزیه شود — «از n مورد مشابه، k مورد چنین شدند».")
    _ev = _analysis_html(fdf, ref_date, dict(DISPLAY))
    components.html(_ev, height=760, scrolling=True)
    st.download_button("⬇️ دانلود گزارش تحلیلی (HTML)", _ev.encode("utf-8"),
                       file_name=f"{_BRAND.FILE_PREFIX}_Analysis.html", mime="text/html",
                       key="dl_analysis")


# ══════════════════════════════════════════════════════════════════════════
#  ۵) سازنده گزارش — دسترسی به هر ۳۶۷ فیلد
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
            file_name=f"{_BRAND.FILE_PREFIX}_{ref_date}.csv", mime="text/csv")


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
            stem = st.text_input("نام فایل", f"{_BRAND.FILE_PREFIX} {T.title}")
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
                          title=f"{_BRAND.LOCKUP} — {T.title}", formats=formats,
                          visuals=want_vis, tables=want_tab,
                          max_rows=int(rows_cap), file_stem=stem.strip() or f"{_BRAND.FILE_PREFIX} {T.title}")
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
                   "۱۷ شیت کامل، ساخته‌شده توسط خط لوله — فیلترنشده.")
        if official_excel and Path(official_excel).exists():
            st.download_button("⬇ دانلود Excel رسمی", Path(official_excel).read_bytes(),
                               file_name=Path(official_excel).name,
                               mime=("application/vnd.openxmlformats-officedocument"
                                     ".spreadsheetml.sheet"))

st.caption(f"{_BRAND.LOCKUP_FULL} — لایه نمایش و خروجی روی همان "
           "Pipeline/Rulebook موجود؛ منطق کسب‌وکار در موتور باقی می‌ماند.")


# ══════════════════════════════════════════════════════════════════════════
#  ارسال گزارش در لحظه — پیوست دلخواه، گیرندهٔ دلخواه
# ══════════════════════════════════════════════════════════════════════════
with tab_send:
    from pathlib import Path as _P

    from aibl.config.settings import SETTINGS as _CFG
    from aibl.report import dispatch as _dp
    from aibl.report import narrative as _NR

    with st.container(border=True):
        panel_open("۱ · کدام گزارش‌ها پیوست شوند؟",
                   "فایل‌های همین اجرا — نه اجرای دیروز.")
        out_root = _P(_CFG.OUTPUT_DIR)
        avail = {}
        if official_excel and _P(official_excel).exists():
            avail["dashboard"] = _P(official_excel)
        audit = out_root / "AIBL_Data_Conflicts_Audit.xlsx"
        if audit.exists():
            avail["audit"] = audit
        for k in ("AIBL_Analysis.html", "AIBL_تحلیل.html"):
            if (out_root / k).exists():
                avail["analysis"] = out_root / k
                break
        for kind, path in (st.session_state.get("report_files") or {}).items():
            if _P(path).exists():
                avail["report_html" if kind == "html" else "report"] = _P(path)

        picks = {}
        cols = st.columns(3)
        for i, (key, (label, _ext, why)) in enumerate(_dp.ARTIFACTS.items()):
            with cols[i % 3]:
                here = key in avail
                picks[key] = st.checkbox(
                    label, value=here and key in ("dashboard", "analysis"),
                    disabled=not here, key=f"aibl_pick_{key}",
                    help=why if here else f"{why} — هنوز ساخته نشده")
        missing = [_dp.ARTIFACTS[k][0] for k in _dp.ARTIFACTS if k not in avail]
        if missing:
            st.caption("ساخته‌نشده: " + "، ".join(missing)
                       + " — از تب «سازنده گزارش» بسازید تا اینجا قابل انتخاب شود.")

    with st.container(border=True):
        panel_open("۲ · گیرندگان",
                   "نشانی‌ها هیچ‌جا لاگ یا ذخیره نمی‌شوند؛ فقط تعدادشان.")
        hr = extras.get("hr")
        people_dir = _dp.directory(hr) if hr is not None else []
        chosen_to, chosen_cc = [], []
        if people_dir:
            by_label = {p.label: p for p in people_dir}
            c1, c2 = st.columns(2)
            to_sel = c1.multiselect("گیرندگان (To) — از سورس HR", list(by_label))
            cc_sel = c2.multiselect("رونوشت (Cc) — از سورس HR", list(by_label))
            chosen_to = [by_label[x] for x in to_sel]
            chosen_cc = [by_label[x] for x in cc_sel if x not in to_sel]
            if chosen_to or chosen_cc:
                st.caption("نشانی نقاب‌دار برای تأیید: "
                           + "، ".join(p.masked for p in chosen_to + chosen_cc))
        else:
            st.info("سورس HR با ستون Email در این اجرا نبود — نشانی‌ها را "
                    "پایین دستی وارد کنید.")

        # ── ورود دستی ───────────────────────────────────────────────────
        # قبلاً فقط انتخابگرِ HR بود؛ اگر آن سورس ستون Email نداشت،
        # هیچ راهی برای فرستادن نمی‌ماند — کاربر نام‌ها را داشت و جایی
        # برای واردکردنشان نبود.
        m1, m2 = st.columns(2)
        raw_to = m1.text_area(
            "یا نشانی‌ها را دستی بنویسید (To)", height=76, key="aibl_raw_to",
            placeholder="name@example.com؛ name2@example.com",
            help="جداکننده: کاما، نقطه‌ویرگول، فاصله یا خط جدید.")
        raw_cc = m2.text_area(
            "دستی (Cc)", height=76, key="aibl_raw_cc", placeholder="—")
        typed_to, bad_to = _dp.parse_addresses(raw_to)
        typed_cc, bad_cc = _dp.parse_addresses(raw_cc)
        if bad_to or bad_cc:
            st.warning("این‌ها نشانی معتبر نیستند و نادیده گرفته می‌شوند: "
                       + "، ".join(bad_to + bad_cc))

        to_addr = sorted(set(_dp.addresses(chosen_to)) | set(typed_to))
        cc_addr = sorted((set(_dp.addresses(chosen_cc)) | set(typed_cc)) - set(to_addr))
        if to_addr:
            st.success(f"{len(to_addr)} گیرنده"
                       + (f" و {len(cc_addr)} رونوشت" if cc_addr else "")
                       + " آمادهٔ ارسال است.")

    with st.container(border=True):
        panel_open("۳ · متن ایمیل")
        subj = st.text_input("موضوع", value=_BRAND.subject(ref_date))
        note = st.text_area(
            "یادداشت پایانی", height=70,
            value="یک متریال بحرانی، کل پرونده را بحرانی می‌کند؛ علت آن در "
                  "فایل پیوست تا سطح متریال قابل مشاهده است.")
        with st.expander("چرا متن ایمیل داینامیک نیست؟"):
            st.markdown(
                "**هیچ کلاینت ایمیلی جاوااسکریپت را اجرا نمی‌کند** — نه اتلوک "
                "کلاسیک، نه اتلوک جدید، نه وب‌میل. اجرای کد فرستندهٔ ناشناس "
                "روی دستگاه گیرنده، خودش یک آسیب‌پذیری است.\n\n"
                "**اتلوک کلاسیک** بدنه را با موتور Word رندر می‌کند (بدون "
                "flexbox، بدون grid) و پشتیبانی‌اش مهر ۱۴۰۵ تمام می‌شود. "
                "**اتلوک جدید** موتور Chromium دارد ولی باز هم جاوااسکریپت نه.\n\n"
                "**راه‌حل:** بدنهٔ جدول‌محور و امن روی هر دو موتور، به‌علاوهٔ "
                "گزارش داینامیک به‌عنوان **پیوست** که در مرورگر زنده است.")

    with st.container(border=True):
        panel_open("۴ · ارسال",
                   "پیش‌نمایش خودش ساخته می‌شود؛ دکمهٔ جداگانه‌ای لازم نیست.")
        # بدنه در هر رندر ساخته می‌شود. قبلاً پشت دکمهٔ «ساخت پیش‌نمایش»
        # بود و تا کاربر آن را نمی‌زد، هیچ دکمهٔ ارسالی ظاهر نمی‌شد.
        files = [avail[k] for k, v in picks.items() if v and k in avail]
        crit = int((fdf[CODE_COL].astype(str).isin(["STOCKOUT", "CRITICAL"])).sum()) \
            if CODE_COL in fdf.columns else 0
        from app.theme import STATUS as _ST, TEXT as _TX, BRAND as _BR
        kpis = [("پرونده", f"{len(fdf):,}", _TX),
                ("بحرانی", f"{crit:,}", _ST["critical"])]
        if RES_COL in fdf.columns:
            med = pd.to_numeric(fdf[RES_COL], errors="coerce").median()
            if pd.notna(med):
                kpis.append(("میانه مقاومت (روز)", f"{med:.0f}", _BR))
        cols_show = [c for c in ("CANONICAL_PART_NO", "CANONICAL_BL",
                                 "STATUS_WHERE", "WAITING_ON_SCOPE")
                     if c in fdf.columns][:4]
        rows = []
        for _, r in fdf.head(6).iterrows():
            row = [str(r.get(c, "")) for c in cols_show]
            if CODE_COL in fdf.columns:
                col, icon, lab = band_of(str(r.get(CODE_COL, "")))[:3]
                row.append(_dp._chip(lab, col, icon))
            rows.append(row)
        heads = [DISPLAY.get(c, c) for c in cols_show] + (["وضعیت"] if rows and
                 len(rows[0]) > len(cols_show) else [])
        # روایتِ ایمیل از همان دادهٔ فیلترشده می‌آید که KPIها از آن آمدند،
        # پس اگر کاربر فیلتر را عوض کند، متن ایمیل هم عوض می‌شود.
        _blind = 0
        for _c in ("PART_OWNER_SOURCE_GAP", "PART_OWNER_DATA_GAP"):
            if _c in fdf.columns:
                _blind = int(fdf[_c].astype(str).str.strip().ne("").sum())
                break
        _med = None
        if RES_COL in fdf.columns:
            _m = pd.to_numeric(fdf[RES_COL], errors="coerce").median()
            _med = None if pd.isna(_m) else float(_m)
        story = _NR.Facts(total=int(len(fdf)), subject="پرونده",
                          ref_date=str(ref_date), critical=crit,
                          blind=_blind, median=_med)
        body = _dp.outlook_body(subj, ref_date, kpis=kpis, headers=heads,
                                rows=rows, note=note, story=story,
                                attachments=[f.name for f in files])
        st.session_state.aibl_mail = body
        st.session_state.aibl_files = [str(f) for f in files]

        mail_html = st.session_state.get("aibl_mail", "")
        files = [_P(f) for f in st.session_state.get("aibl_files", [])]

        # دکمهٔ ارسال **همیشه** دیده می‌شود. قبلاً وقتی گیرنده‌ای نبود کل
        # بلوک پنهان می‌شد و کاربر نتیجه می‌گرفت که «این برنامه دکمهٔ ارسال
        # ندارد و فقط پیش‌نمایش می‌دهد». کنترلِ غیرفعالِ دلیل‌دار، بهتر از
        # کنترلِ نامرئی است.
        ready = bool(to_addr)
        if not ready:
            st.info("دکمهٔ ارسال تا وقتی گیرنده‌ای نباشد غیرفعال است — "
                    "در بخش ۲ از فهرست HR انتخاب کنید یا نشانی را دستی بنویسید.")
        # برچسب دکمه از بسترِ همین سیستم می‌آید، نه از آرزوی ما.
        # روی مک، COM اتلوک وجود ندارد؛ دکمه‌ای به نام «ارسال» که فقط
        # پنجره باز کند، همان اشتباهی است که یک بار روی ویندوز شد.
        act, act_help = _dp.action_label()
        direct = _dp.can_send_directly()
        if True:
            s1, s2 = st.columns([2, 1])
            if s1.button(f"🚀 {act} به {len(to_addr)} گیرنده" if ready
                         else f"🚀 {act} (گیرنده انتخاب نشده)",
                         type="primary", use_container_width=True,
                         help=act_help, disabled=not ready):
                try:
                    st.success(_dp.send(subj, mail_html, to_addr, cc_addr,
                                        files, send_now=direct).summary)
                except Exception as ex:
                    st.error(str(ex))
            if direct and s2.button("پیش‌نمایش در اتلوک",
                                    use_container_width=True,
                                    disabled=not ready,
                                    help="پنجرهٔ اتلوک باز می‌شود؛ ارسال با خود شماست."):
                try:
                    st.success(_dp.send(subj, mail_html, to_addr, cc_addr,
                                        files, send_now=False).summary)
                except Exception as ex:
                    st.error(str(ex))
            if not direct:
                s2.caption("روی این سیستم، فرستادنِ نهایی یک کلیک در "
                           "کلاینت ایمیل خودتان است.")
            st.download_button(
                "⬇️ پروندهٔ .eml (سیستمی که اتلوک ندارد)",
                _dp.eml(subj, mail_html, to_addr or ["-"], cc_addr, files),
                file_name=f"{_BRAND.FILE_PREFIX}_{ref_date}.eml",
                mime="message/rfc822", use_container_width=True,
                disabled=not ready)
            st.caption(f"{len(files)} پیوست همراه می‌رود. "
                       + ("ارسال برگشت‌ناپذیر است." if direct else
                          "پیام باز می‌شود؛ تا خودتان نفرستید، نرفته است."))

        with st.expander("پیش‌نمایش متن ایمیل", expanded=False):
            if mail_html:
                st.components.v1.html(mail_html, height=480, scrolling=True)
