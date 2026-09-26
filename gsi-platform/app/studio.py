# -*- coding: utf-8 -*-
"""GSI Studio — پلتفرم تحلیل و گزارش‌سازی زنجیره تأمین.

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

st.set_page_config(page_title="GSI | Global Sourcing Intelligence", page_icon="◆",
                   layout="wide", initial_sidebar_state="expanded")

from app import analytics, motion, process_view, process_cockpit
from app.styles import band_chip, css, kpi_card
from app.theme import (SURFACE, BAND_ORDER, BANDS, SEQUENTIAL, SERIES, STATUS, TEXT_SECONDARY,
                       band_of, plotly_template)
from gsi.studio_core.excel_export import (DEFAULT_CUSTOM_NAME, OfficialReportOverwrite,
                                            build_custom_excel)
from gsi.studio_core.field_catalog import build_catalog, catalog_groups, unique_labels
from gsi.studio_core.filters import FilterState, apply_filters, filter_options
from gsi.studio_core.html_export import build_dynamic_html
from gsi.report.supply_views import build_material_view, build_bl_view, build_dept_view
from gsi.report.financial_summary import commitment_display, commitment_equivalent_display

try:
    import plotly.express as px
    import plotly.graph_objects as go
    import plotly.io as pio
    pio.templates["gsi"] = plotly_template()
    pio.templates.default = "gsi"
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

st.markdown(css(), unsafe_allow_html=True)

# Knowledge Desk V29.3 is static/shared-folder only; no background HTTP service is started.

BAND_COL = "بحرانی (کوتاه)"
CODE_COL = "کد طبقه بحرانی"
RES_COL = "مقاومت (روز)"


# ══════════════════════════════════════════════════════════════════════════
#  داده
# ══════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner="در حال خواندن Snapshot منتشرشده…")
def load_data(ref_date: str):
    # UI is read-only by default. A date mismatch must never trigger a 30+ minute ETL.
    # Exact snapshot is preferred; otherwise the last published good snapshot is shown
    # explicitly as stale. Refresh is only the sidebar button / REFRESH_GSI_DATA.cmd.
    from gsi.warehouse.service import last_report
    stored = last_report(ref_date)
    if stored is not None:
        df, main, extras, report = stored
        extras['runtime_status'] = 'PUBLISHED_SNAPSHOT'
        return df, main, extras, report
    fallback = last_report(None)
    if fallback is None:
        raise RuntimeError("هیچ Snapshot منتشرشده‌ای در انبار داده وجود ندارد. ابتدا REFRESH_GSI_DATA.cmd را اجرا کنید.")
    df, main, extras, report = fallback
    extras['runtime_status'] = 'STALE_PUBLISHED_SNAPSHOT'
    extras['stale_snapshot'] = True
    extras['requested_reference_date'] = ref_date
    return df, main, extras, report


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
st.sidebar.markdown("### ◆ GSI")
st.sidebar.caption("Global Sourcing Intelligence")
from gsi.factsheet import VERSION as GSI_RUNTIME_VERSION
st.sidebar.success(f"Build {GSI_RUNTIME_VERSION} · Studio Runtime")
# مسیر مطلق فایل روی سرور (نام کاربر/پوشه) دیگر به کاربر نهایی نمایش داده
# نمی‌شود؛ برای پشتیبانی در VERIFY_RUNTIME و doctor موجود است.
st.sidebar.markdown("<small>▦ Data &nbsp;•&nbsp; ⛓ Process &nbsp;•&nbsp; ◉ Decision</small>", unsafe_allow_html=True)

_surface = st.sidebar.radio("محیط کاری", ["اتاق کنترل و گزارش جامع", "اعتماد داده و کیفیت", "مخاطبان، کلاسترها و منابع", "دیتاورهوس", "دستیار دانش بازرگانی"], key="gsi_surface")
if _surface == "دیتاورهوس":
    from app.warehouse_view import run as warehouse_run
    warehouse_run()
    st.stop()

if _surface == "دستیار دانش بازرگانی":
    from app.learning_view import run as learning_run
    learning_run()
    st.stop()

if _surface == "مخاطبان، کلاسترها و منابع":
    from app.control_center import run as run_control_center
    run_control_center()
    st.stop()

from gsi.core.jalali import date_label, to_iso
from gsi.warehouse.service import published_reference_date
# پیش‌فرض = تاریخ مرجع Snapshot منتشرشده (نه امروز). قبلاً فردای هر Refresh،
# همان آخرین Snapshot سالم با برچسب «کهنه» نمایش داده می‌شد.
_default_ref = os.environ.get("GSI_TODAY") or published_reference_date() or str(date.today())
_raw_ref = st.sidebar.text_input("تاریخ مرجع (شمسی یا میلادی)", value=_default_ref,
                                 help="مثال: 1405/06/09 یا 2026-08-31").strip()
ref_date = to_iso(_raw_ref) or ""
if not ref_date:
    st.sidebar.error("تاریخ معتبر نیست؛ نمونه: 1405/06/09 یا 2026-08-31")
    st.stop()
st.sidebar.caption(f"تاریخ انتخاب‌شده: {date_label(ref_date)}")
os.environ["GSI_TODAY"] = ref_date

if st.sidebar.button("↻ اجرای مجدد خط لوله", width="stretch"):
    from gsi.pipeline import Pipeline
    try:
        Pipeline().run(build_report=True)
    except Exception as ex:
        from app.runtime_errors import render_pipeline_exception
        render_pipeline_exception(st, ex)
    else:
        st.cache_data.clear()
        st.rerun()

try:
    raw, main, extras, official_excel = load_data(ref_date)
except Exception as ex:
    from app.runtime_errors import render_pipeline_exception
    render_pipeline_exception(st, ex)
    st.stop()

# صفحه اعتماد داده بعد از بارگذاری Snapshot می‌آید، چون روی فریم‌های
# `trust_*` همان اجرای منتشرشده کار می‌کند نه روی یک محاسبه تازه.
if _surface == "اعتماد داده و کیفیت":
    from app.trust_view import run as trust_run
    trust_run(extras, ref_date)
    st.stop()

df = main if not main.empty else raw
from gsi.studio_core.runtime_data import ensure_resistance_columns
df = ensure_resistance_columns(df)

# Calm editorial masthead + transparent data-health cue. Reliability complexity
# stays one click away in the DWH room instead of dominating the analytical UI.
try:
    from gsi.warehouse.store import Warehouse
    _wh = Warehouse()
    _rid = _wh.current_run('report')
    _health_label = 'داده‌ها آماده تحلیل‌اند'
    _health_note = 'آخرین Snapshot منتشرشده'
    if extras.get('runtime_status') == 'STALE_PUBLISHED_SNAPSHOT':
        _health_label = 'Snapshot تاریخ درخواستی موجود نیست · نمایش آخرین Snapshot سالم'
        _pref = extras.get('published_reference_date') or 'نامشخص'
        _health_note = f'تاریخ Snapshot نمایش‌داده‌شده: {_pref} · Refresh فقط با فرمان صریح'
    elif extras.get('runtime_status') == 'UPDATE_IN_PROGRESS':
        _health_label = 'به‌روزرسانی در حال اجراست · نمایش آخرین Snapshot سالم'
        _pref = extras.get('published_reference_date') or 'نامشخص'
        _health_note = f'تاریخ Snapshot نمایش‌داده‌شده: {_pref}'
    elif extras.get('runtime_status') == 'QUALITY_GATE_BLOCKED':
        _health_label = 'انتشار جدید به‌دلیل کنترل کیفیت متوقف شد · نمایش آخرین Snapshot سالم'
        _pref = extras.get('published_reference_date') or 'نامشخص'
        _health_note = f'نسخه نمایشی معتبر: {_pref} · جزئیات در دیتاورهوس'
    if _rid:
        with _wh.db() as _c:
            _run = _c.execute('SELECT finished FROM wh_run WHERE id=?',(_rid,)).fetchone()
            _q = _c.execute("SELECT severity,count(*) FROM wh_quality_check WHERE run_id=? AND passed=0 GROUP BY severity",(_rid,)).fetchall()
        _bad = {k:int(v) for k,v in _q}
        if _bad.get('DEGRADED',0) or _bad.get('WARN',0):
            _health_label = f"داده‌ها منتشر شده‌اند · {_bad.get('DEGRADED',0)} شاخه ناقص"
        _health_note = f"آخرین انتشار: \u2066{(_run[0] if _run else '')[:16].replace('T',' ')}\u2069"
    _banner = f'''<div class="gsi-editorial-lead">
      <div class="gsi-editorial-kicker">GSI · روایت عملیاتی زنجیره تأمین</div>
      <div class="gsi-editorial-title">از داده تا تصمیم؛ مسیر روشن، جزئیات قابل پیگیری</div>
      <div class="gsi-editorial-deck">نمای اصلی آرام و خلاصه است؛ هر عدد تا منبع، قاعده و فرآیند قابل Drill-down می‌ماند.</div>
      <div style="margin-top:10px"><span class="gsi-data-health"><i></i>{_health_label} · {_health_note}</span></div>
    </div>'''
    st.markdown(_banner, unsafe_allow_html=True)
except Exception:
    pass

# ── فرمول مقاومت قابل تنظیم توسط کاربر ───────────────────────────────
# تنظیمات در session می‌ماند و در هر rerun پیش از ساخت Catalog اعمال می‌شود،
# بنابراین ستون‌های محاسباتی سفارشی مثل سایر فیلدها وارد گزارش می‌شوند.
st.session_state.setdefault("resistance_num_cols", ["STOCK_SAPCO", "STOCK_IKCO"])
st.session_state.setdefault("resistance_den_col", "DAILY_NEED")
st.session_state.setdefault("resistance_require_all", True)
_num_cols_cfg=[c for c in st.session_state.resistance_num_cols if c in df.columns]
_den_cfg=st.session_state.resistance_den_col if st.session_state.resistance_den_col in df.columns else "DAILY_NEED"
if _num_cols_cfg and _den_cfg in df.columns:
    _nums=df[_num_cols_cfg].apply(pd.to_numeric,errors="coerce")
    _total=_nums.sum(axis=1,min_count=(len(_num_cols_cfg) if st.session_state.resistance_require_all else 1))
    _den=pd.to_numeric(df[_den_cfg],errors="coerce")
    df["موجودی سفارشی"]=_total
    df["مقاومت سفارشی (روز)"]=(_total/_den.where(_den>0)).round(1)

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

# ── جست‌وجوی جامع متریال در شواهد مستقیم Commercial Expert ─────────────
# این جست‌وجو عمداً از BL/Base mart مستقل است. شرح، PR و Order در match کد
# متریال دخالت ندارند؛ اگر KEY_MATERIAL یکسان باشد تمام ردیف‌های سورس باید دیده شوند.
def _material_evidence_hits(evidence: pd.DataFrame, query: str) -> pd.DataFrame:
    from gsi.warehouse.material_search import search_material
    return search_material(evidence, query)


def _commercial_text_hits(lines: pd.DataFrame, query: str) -> pd.DataFrame:
    """Fallback for non-material searches (Order/PR/description)."""
    if lines is None or not isinstance(lines, pd.DataFrame) or lines.empty or not query.strip():
        return pd.DataFrame()
    from gsi.core.text import clean_part_no, clean_order_ref, clean_key
    q = query.strip(); q_low = q.lower(); q_material = clean_part_no(q)
    candidates = [c for c in [
        "KEY_MATERIAL", "KEY_ORDER", "KEY_PR", "MOGH_PR_ITEM",
        "MOGH_MATERIAL", "MOGH_MATERIAL_DESC", "MOGH_MATERIAL_SHORT",
        "MOGH_ORDER_REF", "MOGH_PR_NO", "MOGH_ROW_NO"
    ] if c in lines.columns]
    if not candidates:
        return pd.DataFrame()
    mask = pd.Series(False, index=lines.index)
    hay = lines[candidates].fillna("").astype(str).agg(" | ".join, axis=1).str.lower()
    mask |= hay.str.contains(q_low, regex=False, na=False)
    if "KEY_MATERIAL" in lines.columns and q_material:
        mask |= lines["KEY_MATERIAL"].fillna("").map(clean_part_no).eq(q_material)
    if "KEY_ORDER" in lines.columns:
        oq = clean_order_ref(q)
        if oq: mask |= lines["KEY_ORDER"].fillna("").map(clean_order_ref).eq(oq)
    if "KEY_PR" in lines.columns:
        pq = clean_key(q)
        if pq: mask |= lines["KEY_PR"].fillna("").map(clean_key).eq(pq)
    keep=[c for c in ["MOGH_ROW_NO","KEY_ORDER","KEY_PR","MOGH_PR_ITEM","KEY_MATERIAL",
                      "MOGH_MATERIAL_DESC","MOGH_MATERIAL_SHORT"] if c in lines.columns]
    return lines.loc[mask, keep].copy()

_source_hits = pd.DataFrame()
if search.strip():
    try:
        _material_evidence = extras.get("material_evidence")
    except Exception:
        _material_evidence = None
    try:
        _commercial_lines = extras.get("commercial_lines")
    except Exception:
        _commercial_lines = None

    _source_hits = _material_evidence_hits(_material_evidence, search)
    if _source_hits.empty:
        _source_hits = _commercial_text_hits(_commercial_lines, search)

    if not _source_hits.empty:
        st.success(
            f"جست‌وجوی منبع Commercial Expert: {len(_source_hits):,} ردیف پیدا شد. "
            "این نتیجه مستقل از جدول پایه است و در KPIها تزریق نمی‌شود."
        )
        st.dataframe(_source_hits, width="stretch", hide_index=True)
        if "KEY_MATERIAL" in _source_hits.columns:
            _desc_cols=[c for c in ["MOGH_MATERIAL_DESC","MOGH_MATERIAL_SHORT"] if c in _source_hits.columns]
            if _desc_cols:
                _desc_count=len(_source_hits[_desc_cols].fillna("").astype(str).drop_duplicates())
                if _desc_count > 1:
                    st.info(f"برای همین کد متریال {_desc_count} ترکیب شرح متفاوت در سورس وجود دارد؛ کد متریال معیار match باقی مانده است.")
    else:
        st.warning(
            "در ایندکس مستقیم Commercial Expert رکوردی برای این جست‌وجو پیدا نشد. "
            "اگر کد را در فایل می‌بینید، اجرای Pipeline را پس از نصب این نسخه یک‌بار کامل انجام دهید تا Material Evidence Index ساخته شود."
        )


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

commit = commitment_display(fdf) if "مانده تعهد" in fdf.columns else "—"
commit_eq = commitment_equivalent_display(fdf) if "مانده تعهد" in fdf.columns else "—"

# ── هدر زنده ──────────────────────────────────────────────────────────────
motion.hero(
    "GSI | Global Sourcing Intelligence",
    f"Data • Process • Decision  |  تاریخ مرجع {date_label(ref_date)} · {len(fdf):,} پرونده · {len(ALL_COLUMNS):,} فیلد قابل گزارش",
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
    ("جمع مانده تعهد", commit, "Native / NTSW", STATUS["neutral"], "₪"),
    ("معادل مانده تعهد", commit_eq, "EUR / IRR با نرخ همان پرونده", STATUS["neutral"], "€"),
]
st.markdown('<div class="kpi-row">' + "".join(kpi_card(*c) for c in cards) + "</div>",
            unsafe_allow_html=True)

st.markdown(
    '<div style="margin:12px 0 2px">' +
    "".join(band_chip(*band_of(k)) for k in BAND_ORDER) +
    '</div>', unsafe_allow_html=True)

(tab_cockpit, tab_over, tab_proc, tab_supply, tab_formula, tab_analytics, tab_fields, tab_data,
 tab_quality, tab_export) = st.tabs(
    ["◈ مرکز عملیات", "نمای اجرایی", "⛓ فرآیند", "🧭 دید تأمین", "🧮 فرمول مقاومت", "⊞ تحلیل", "🧩 سازنده گزارش",
     "▦ داده", "◍ کیفیت داده", "📦 خروجی"])

# Figma v1 — نمای Process-first. تمام اعداد از اجرای واقعی می‌آیند.
with tab_cockpit:
    process_cockpit.render(fdf, extras, ref_date)
    # A transient SQLite writer must not take the whole cockpit down. Lazy marts
    # report their own read-busy state; values remain Missing rather than zero.
    if hasattr(extras, "load_errors"):
        _dwh_read_errors = extras.load_errors()
        if _dwh_read_errors:
            st.warning(
                "بخشی از نماهای تحلیلی موقتاً در حال به‌روزرسانی دیتاورهاوس بودند؛ "
                "داشبورد با داده‌های در دسترس نمایش داده شده است. با بازاجرای صفحه، "
                "نماهای موقت دوباره خوانده می‌شوند."
            )


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
                    marker_line=dict(color=SURFACE, width=2),
                    text=[f"{v:,}" for v in vals], textposition="outside",
                    hovertemplate="%{x}<br>%{y:,} پرونده<extra></extra>"))
                fig.update_layout(height=340, showlegend=False,
                                  yaxis_title="تعداد پرونده", xaxis_title=None,
                                  uniformtext=dict(minsize=10, mode="show"))
                st.plotly_chart(fig, width="stretch")
        else:
            st.info("ستون طبقه بحرانی در این اجرا موجود نیست.")

    with c2, st.container(border=True):
        panel_open("کم‌مقاومت‌ترین قطعات",
                   "مقاومت = موجودی ÷ نیاز روزانه. پایین‌ترین‌ها اول.")
        if {"KEY_MATERIAL", RES_COL} <= set(fdf.columns) and HAS_PLOTLY:
            x = fdf[["KEY_MATERIAL", RES_COL]].copy()
            x[RES_COL] = pd.to_numeric(x[RES_COL], errors="coerce")
            x = (x.replace([float("inf"), -float("inf")], float("nan")).dropna()
                 .groupby("KEY_MATERIAL", as_index=False)[RES_COL].min()
                 .nsmallest(15, RES_COL))
            if not x.empty:
                fig = go.Figure(go.Bar(
                    x=x[RES_COL], y=x["KEY_MATERIAL"], orientation="h",
                    marker_color=[band_of(
                        "STOCKOUT" if v <= 0 else "CRITICAL" if v < 10
                        else "BECOMING_CRITICAL" if v < 20
                        else "WATCH" if v < 45 else "SAFE")[0] for v in x[RES_COL]],
                    marker_line=dict(color=SURFACE, width=2),
                    text=[f"{v:,.1f}" for v in x[RES_COL]], textposition="outside",
                    hovertemplate="%{y}<br>مقاومت %{x:.1f} روز<extra></extra>"))
                fig.update_layout(height=340, showlegend=False,
                                  xaxis_title="مقاومت (روز)", yaxis_title=None,
                                  yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, width="stretch")
            else:
                from gsi.studio_core.runtime_data import resistance_diagnostic
                st.info(resistance_diagnostic(fdf))
        elif not HAS_PLOTLY:
            st.info("کتابخانه Plotly برای نمایش نمودار نصب نیست.")
        else:
            from gsi.studio_core.runtime_data import resistance_diagnostic
            st.info(resistance_diagnostic(fdf))

    c3, c4 = st.columns([1, 1])
    with c3, st.container(border=True):
        panel_open("بار سازمانی", "تعداد پرونده به تفکیک مدیریت.")
        if "ORG_DEPT" in fdf.columns and HAS_PLOTLY and not fdf.empty:
            g = (fdf.groupby("ORG_DEPT", dropna=False).size()
                 .reset_index(name="Cases").sort_values("Cases", ascending=False).head(12))
            fig = go.Figure(go.Bar(
                x=g["Cases"], y=g["ORG_DEPT"].astype(str), orientation="h",
                marker_color=SERIES[0], marker_line=dict(color=SURFACE, width=2),
                text=[f"{v:,}" for v in g["Cases"]], textposition="outside",
                hovertemplate="%{y}<br>%{x:,} پرونده<extra></extra>"))
            fig.update_layout(height=320, showlegend=False, xaxis_title="پرونده",
                              yaxis_title=None, yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, width="stretch")

    with c4, st.container(border=True):
        panel_open("گلوگاه فرآیند", "از لاگ رویداد (استاندارد Celonis).")
        b = extras.get("bottlenecks")
        if b is not None and not b.empty:
            st.dataframe(b.head(12), width="stretch", hide_index=True)
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
    for tab, kind, fname in [(sv1, "material", "GSI_Material_View.xlsx"),
                             (sv2, "bl", "GSI_BL_View.xlsx"),
                             (sv3, "dept", "GSI_Department_View.xlsx")]:
        with tab:
            if kind == "material" and search.strip() and not _source_hits.empty:
                st.markdown("#### شواهد منبع برای متریال جست‌وجوشده")
                st.caption("این ردیف‌ها در Grain اصلی Commercial Expert هستند؛ اختلاف شرح یا PR باعث حذفشان نمی‌شود.")
                st.dataframe(_source_hits, width="stretch", hide_index=True)
            view = _supply_view(kind, fdf)
            if view.empty:
                if kind == "material" and search.strip() and not _source_hits.empty:
                    st.info("این متریال در Commercial Expert وجود دارد اما هنوز در Population جدول پایه/BL mart رابطه اثبات‌شده ندارد؛ بنابراین فقط در شواهد منبع نمایش داده می‌شود.")
                    continue
                st.info("داده کافی برای این نما وجود ندارد.")
                continue
            st.dataframe(view, width="stretch", hide_index=True)
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
#  ۳٫۵) فرمول مقاومت — تنظیم کاربر
# ══════════════════════════════════════════════════════════════════════════
with tab_formula:
    panel_open("فرمول مقاومت و قطعات بحرانی",
               "صورت و مخرج را خودتان انتخاب کنید. پیش‌فرض مطابق تعریف عملیاتی فعلی است.")
    numeric_candidates=[]
    for c in df.columns:
        v=pd.to_numeric(df[c],errors="coerce")
        if v.notna().any(): numeric_candidates.append(c)
    defaults=[c for c in st.session_state.resistance_num_cols if c in numeric_candidates]
    chosen_num=st.multiselect(
        "ستون‌های صورت (موجودی)", numeric_candidates, default=defaults,
        format_func=lab, key="resistance_num_cols")
    den_default=st.session_state.resistance_den_col if st.session_state.resistance_den_col in numeric_candidates else ("DAILY_NEED" if "DAILY_NEED" in numeric_candidates else numeric_candidates[0])
    chosen_den=st.selectbox("ستون مخرج (نیاز روزانه)", numeric_candidates,
                            index=numeric_candidates.index(den_default),
                            format_func=lab, key="resistance_den_col")
    st.checkbox("فقط وقتی همه اجزای صورت موجودند مقاومت قطعی بساز", value=True,
                key="resistance_require_all",
                help="روشن = Missing هرگز صفر نمی‌شود. خاموش = از اجزای موجود حداقل قابل اثبات ساخته می‌شود.")

    st.info("پیش‌فرض بحرانی: موجودی ساپکو + موجودی ایران‌خودرو؛ مخرج = نیاز روزانه Oracle. مقاومت نزد سازنده/درراه/گمرک جداگانه نمایش داده می‌شوند و می‌توانید برای تحلیل سفارشی به صورت اضافه‌شان کنید.")
    preview_cols=[c for c in ["KEY_MATERIAL", "ORC_DAILY_NEED_SHEET1", "ORC_DAILY_NEED_SAPCO_IK",
                              "DAILY_NEED", "STOCK_IKCO", "STOCK_SAPCO", "SUPPLIER_QTY",
                              "IN_TRANSIT_QTY", "IN_CUSTOMS_QTY", "موجودی سفارشی",
                              "مقاومت سفارشی (روز)", "مقاومت انبار (روز)",
                              "مقاومت نزد سازنده (روز)", "مقاومت در راه (روز)",
                              "مقاومت در گمرک (روز)", "ORC_FOREIGN_SHARE"] if c in df.columns]
    st.dataframe(fdf[preview_cols].head(500),width="stretch",hide_index=True)

    st.markdown("#### فیلدهای هر Template")
    st.caption("هر Template مستقل است؛ فیلدی که اینجا انتخاب نمی‌شود در آن گزارش/HTML ارسال نمی‌شود.")
    st.session_state.setdefault("template_field_overrides", {})
    from gsi.studio_core import templates as _tpl_formula
    for _k,_t in _tpl_formula.TEMPLATES.items():
        _default=st.session_state.template_field_overrides.get(_k, [c for c in _t.default_fields if c in df.columns])
        _pick=st.multiselect(f"{_t.icon} {_t.title}", ALL_COLUMNS,
                             default=[c for c in _default if c in ALL_COLUMNS],
                             format_func=lab,key=f"tpl_fields_{_k}")
        st.session_state.template_field_overrides[_k]=_pick


# ══════════════════════════════════════════════════════════════════════════
with tab_fields:
    st.markdown(
        f'<div class="panel"><h3>سازنده گزارش</h3><p class="hint">'
        f'هر <b>{len(ALL_COLUMNS):,}</b> فیلدی که خط لوله تولید می‌کند اینجا '
        f'قابل انتخاب است — از هر ۱۳ سورس. فیلدهای انتخابی مستقیماً به جدول، '
        f'Excel و HTML می‌روند.</p></div>', unsafe_allow_html=True)

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
        if st.button("انتخاب همه", width="stretch"):
            st.session_state.sel_fields = list(ALL_COLUMNS)
            st.rerun()
    with fc4:
        if st.button("بازنشانی", width="stretch"):
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
            if bc1.button("افزودن این گروه", key=f"add_{gname}", width="stretch"):
                st.session_state.sel_fields = list(
                    dict.fromkeys(st.session_state.sel_fields + [s.column for s in shown]))
                st.rerun()
            if bc2.button("حذف این گروه", key=f"rm_{gname}", width="stretch"):
                drop = {s.column for s in shown}
                st.session_state.sel_fields = [c for c in st.session_state.sel_fields
                                               if c not in drop]
                st.rerun()
            rows = [{"فیلد": s.label, "ستون": s.column,
                     "پرشدگی": s.fill_pct, "نوع": s.dtype,
                     "انتخاب": s.column in sel} for s in shown]
            ed = st.data_editor(
                pd.DataFrame(rows), hide_index=True, width="stretch",
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
        st.dataframe(view, width="stretch", height=560, hide_index=True)
        st.download_button(
            "⬇ دانلود CSV این نما", view.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"GSI_{ref_date}.csv", mime="text/csv")


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
        width="stretch", hide_index=True, height=520,
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
                         width="stretch", hide_index=True)


# ══════════════════════════════════════════════════════════════════════════
#  ۷) خروجی — سازنده گزارش با قالب، فرمت و کنترل صحت
# ══════════════════════════════════════════════════════════════════════════
with tab_export:
    with st.expander('گزارش مخاطبان و کلاسترها — قالب‌های اختصاصی',expanded=True):
        from gsi.control_center.core import CenterStore
        from app.cluster_delivery import render as render_cluster_delivery
        try: render_cluster_delivery(CenterStore().load(),'studio_delivery')
        except Exception as ex: st.error(str(ex))
    from gsi.studio_core import templates as tpl
    from gsi.studio_core.composer import (BLOCKS, DEFAULT_BLOCKS, HEADER_PRESETS, SIZES,
        PROCESS_VIEWS, KANBAN_MODES, KANBAN_CARD_FIELDS, normalize_blocks,
        normalize_tabs, new_tab)
    from gsi import audience as audience_profiles
    from gsi.studio_core.grain import GRAIN_FA, column_grain, measure_kind, KIND_FA
    from gsi.studio_core.report_builder import ReportSpec, build as build_report
    from gsi.studio_core.designs import (ReportDesign, save_design, load_design,
                                          list_designs, EMAIL_CHARTS)
    from gsi.integrations.daily_email import make_email_charts, build_email_html

    sel_cols = [c for c in st.session_state.sel_fields if c in fdf.columns]
    _default_html_charts = ["criticality", "low_resistance", "stage_distribution", "org_workload", "transport_mix", "commitment"]
    # Persona is a presentation/security boundary.  Each persona owns a separate
    # Composer document; sharing one ``report_tabs`` list made manager/expert
    # layouts silently overwrite each other.
    st.session_state.setdefault("report_persona", "expert")
    _persona_now = st.session_state.report_persona
    if "report_tabs_by_persona" not in st.session_state:
        legacy_tabs = st.session_state.get("report_tabs")
        st.session_state.report_tabs_by_persona = {}
        if legacy_tabs:
            st.session_state.report_tabs_by_persona[_persona_now] = normalize_tabs(
                legacy_tabs, list(sel_cols), _persona_now,
                st.session_state.get("html_chart_keys", _default_html_charts))
    if _persona_now not in st.session_state.report_tabs_by_persona:
        persona_defaults = _default_html_charts if _persona_now in {"manager", "executive"} else ["criticality", "low_resistance"]
        st.session_state.report_tabs_by_persona[_persona_now] = [
            new_tab("نمای اصلی", list(sel_cols), _persona_now, persona_defaults)]
    st.session_state.report_tabs = normalize_tabs(
        st.session_state.report_tabs_by_persona[_persona_now], list(sel_cols),
        _persona_now, st.session_state.get("html_chart_keys", _default_html_charts))
    st.session_state.report_tabs_by_persona[_persona_now] = st.session_state.report_tabs
    if "html_chart_keys" not in st.session_state:
        st.session_state.html_chart_keys = list(_default_html_charts)  # legacy fallback only
    if "email_chart_keys" not in st.session_state:
        st.session_state.email_chart_keys = ["criticality", "low_resistance", "stock_vs_total"]
    st.session_state.setdefault("studio_email_to", "")
    st.session_state.setdefault("studio_email_cc", "")
    st.session_state.setdefault("studio_email_header", "هوشمندی روزانه زنجیره تأمین خودرو")
    st.session_state.setdefault("studio_email_subtitle", "تأمین قطعه · ارز · حمل بین‌الملل · گمرک · پشتیبانی تولید")
    st.session_state.setdefault("studio_email_intro", "این گزارش برای تصمیم‌گیری روزانه تأمین، حمل، گمرک و پشتیبانی تولید تهیه شده است.")
    st.session_state.setdefault("studio_html_header", "هوشمندی زنجیره خرید خارجی")
    st.session_state.setdefault("studio_html_subtitle", "Data • Process • Decision")
    st.session_state.setdefault("studio_header_preset", "figma_aqua")
    with st.container(border=True):
        panel_open("۰ · طرح‌های ذخیره‌شده",
                   "طرح فقط تنظیمات گزارش را ذخیره می‌کند؛ داده و اطلاعات گیرندگان ایمیل ذخیره نمی‌شود.")
        d1, d2, d3 = st.columns([2, 1, 1])
        design_name = d1.text_input("نام طرح", value="گزارش عملیاتی من", key="design_name")
        saved = list_designs()
        chosen = d2.selectbox("بازیابی طرح", ["—"] + saved, key="chosen_design")
        if d3.button("↥ ذخیره طرح", width="stretch"):
            design = ReportDesign(
                name=design_name.strip() or "گزارش",
                template=st.session_state.get("report_template_pick", "executive"),
                fields=list(sel_cols),
                tabs=st.session_state.report_tabs,
                formats=["excel","html","pdf"],
                visuals=True, tables=True,
                max_rows=5000,
                file_stem=design_name.strip() or "GSI Report",
                html_charts=list(dict.fromkeys(k for _t in st.session_state.report_tabs for k in _t.get("charts", []))),
                email_charts=list(st.session_state.email_chart_keys),
                email_to=st.session_state.studio_email_to,
                email_cc=st.session_state.studio_email_cc,
                email_subject=st.session_state.get("studio_subject", ""),
                email_header=st.session_state.studio_email_header,
                email_subtitle=st.session_state.studio_email_subtitle,
                email_intro=st.session_state.studio_email_intro,
                html_header=st.session_state.studio_html_header,
                html_subtitle=st.session_state.studio_html_subtitle,
                html_header_preset=st.session_state.studio_header_preset,
                persona=st.session_state.report_persona,
                title="GSI",
            )
            save_design(design)
            st.success("طرح ذخیره شد.")
        if chosen != "—" and st.button("↧ بارگذاری طرح", width="stretch"):
            try:
                d = load_design(chosen)
                st.session_state.sel_fields = [c for c in d.fields if c in df.columns]
                _legacy_charts = [x for x in (getattr(d, "html_charts", []) or d.email_charts) if x in EMAIL_CHARTS]
                _loaded_tabs = [x for x in d.tabs if x.get("fields")]
                _loaded_persona = getattr(d, "persona", "expert") or "expert"
                _norm_loaded = normalize_tabs(
                    _loaded_tabs or [new_tab("نمای اصلی", list(sel_cols), _loaded_persona, _legacy_charts)],
                    list(sel_cols), _loaded_persona, _legacy_charts)
                st.session_state.report_tabs_by_persona[_loaded_persona] = _norm_loaded
                st.session_state.report_tabs = _norm_loaded
                st.session_state.html_chart_keys = list(_legacy_charts)  # backward-compatible default only
                st.session_state.email_chart_keys = [x for x in d.email_charts if x in EMAIL_CHARTS]
                st.session_state.studio_email_to = getattr(d, "email_to", "")
                st.session_state.studio_email_cc = getattr(d, "email_cc", "")
                st.session_state.studio_email_header = getattr(d, "email_header", "") or "هوشمندی روزانه زنجیره تأمین خودرو"
                st.session_state.studio_email_subtitle = getattr(d, "email_subtitle", "") or "تأمین قطعه · ارز · حمل بین‌الملل · گمرک · پشتیبانی تولید"
                st.session_state.studio_email_intro = getattr(d, "email_intro", "")
                st.session_state.studio_html_header = getattr(d, "html_header", "") or "هوشمندی زنجیره خرید خارجی"
                st.session_state.studio_html_subtitle = getattr(d, "html_subtitle", "") or "Data • Process • Decision"
                st.session_state.studio_header_preset = getattr(d, "html_header_preset", "figma_aqua") or "figma_aqua"
                st.session_state.report_persona = _loaded_persona
                if getattr(d, "email_subject", ""):
                    st.session_state.studio_subject = d.email_subject
                st.session_state.report_template_pick = d.template
                st.rerun()
            except Exception as ex:
                st.error(f"بارگذاری طرح ناموفق بود: {ex}")

    with st.container(border=True):
        panel_open("۱ · قالب گزارش",
                   "قالب فقط چیدمان و نقطه شروع فیلدهاست؛ انتخاب نهایی فیلد با شماست.")
        keys = list(tpl.TEMPLATES)
        pick = st.radio(
            "قالب", keys, horizontal=True, label_visibility="collapsed",
            format_func=lambda k: f"{tpl.TEMPLATES[k].icon} {tpl.TEMPLATES[k].title}",
            key="report_template_pick")
        T = tpl.get(pick)
        st.caption(T.description)
        c1, c2 = st.columns([1, 1])
        if c1.button("استفاده از فیلدهای پیش‌فرض این قالب", width="stretch"):
            st.session_state.sel_fields = [c for c in T.default_fields if c in df.columns]
            st.rerun()
        c2.caption(f"بخش‌ها: " + " · ".join(tpl.SECTIONS.get(x, x) for x in T.sections))

    with st.container(border=True):
        panel_open("۱٫۲ · مخاطب خروجی",
                   "Persona مستقل از Template است؛ یک قالب فرآیندی می‌تواند برای مدیر یا کارشناس ساخته شود.")
        persona_keys = [k for k,_ in audience_profiles.choices()]
        st.radio("مخاطب", persona_keys, horizontal=True, key="report_persona",
                 format_func=lambda k: audience_profiles.get(k).fa)
        st.caption(audience_profiles.get(st.session_state.report_persona).question)
        _other_personas = [k for k in persona_keys if k != st.session_state.report_persona]
        pc1, pc2 = st.columns([2,1])
        _copy_to = pc1.selectbox("کپی چیدمان فعلی برای Persona دیگر (اختیاری)", ["—"] + _other_personas,
                                format_func=lambda k: "—" if k == "—" else audience_profiles.get(k).fa,
                                key="copy_composer_to_persona")
        if pc2.button("کپی Composer", disabled=_copy_to == "—", width="stretch"):
            import copy
            _copied=[]
            for _t in st.session_state.report_tabs:
                _x=copy.deepcopy(_t); _x["id"] = new_tab("x", [], _copy_to)["id"]
                _copied.append(_x)
            st.session_state.report_tabs_by_persona[_copy_to] = _copied
            st.success("چیدمان کپی شد؛ تنظیمات دو Persona از این لحظه مستقل‌اند.")

    with st.container(border=True):
        panel_open("۱٫۵ · Composer واقعی تب‌ها",
                   "هر تب یک سند مستقل است: Block، نمودار، Process View، Kanban و فیلدهای خودش را دارد. هیچ انتخابی بین تب‌ها به اشتراک گذاشته نمی‌شود.")
        try:
            from gsi.studio_core.streamlit_dragdrop import draggable_list
            _has_native_dnd = True
        except Exception:
            draggable_list = None
            _has_native_dnd = False
        try:
            from streamlit_sortables import sort_items
            _has_sortables = True
        except Exception:
            _has_sortables = False

        persona_blocks = DEFAULT_BLOCKS.get(st.session_state.report_persona, DEFAULT_BLOCKS["expert"])
        # Persona may change after tabs exist. Keep authored choices but upgrade schema.
        tabs_work = normalize_tabs(st.session_state.report_tabs, list(sel_cols),
                                   st.session_state.report_persona, _default_html_charts)

        # Reorder the tabs themselves. Stable tab ids keep every widget/state attached
        # to the correct tab even after reordering.
        if _has_sortables and len(tabs_work) > 1:
            tab_labels = [f"{t['title']} 〔{t['id']}〕" for t in tabs_work]
            sorted_tabs = sort_items(tab_labels, direction="horizontal", key="report_tab_order_v284")
            order_ids = [x.rsplit("〔",1)[1].rstrip("〕") for x in sorted_tabs]
            by_id = {t["id"]: t for t in tabs_work}
            tabs_work = [by_id[x] for x in order_ids if x in by_id]
            st.caption("↔ خود تب‌ها را هم می‌توانید جابه‌جا کنید.")

        next_tabs = []
        remove_id = None
        for i, tab in enumerate(tabs_work):
            tid = tab["id"]
            with st.expander(f"تب {i+1} · {tab.get('title','تب')}", expanded=(i==0)):
                a, b, c = st.columns([1.15, 2.7, .65])
                title_i = a.text_input("عنوان تب", value=tab.get("title","تب"), key=f"tab_title_{tid}")
                fields_i = b.multiselect(
                    "فیلدهای جدول این تب", ALL_COLUMNS,
                    default=[x for x in tab.get("fields", sel_cols) if x in ALL_COLUMNS],
                    format_func=lab, key=f"tab_fields_{tid}")
                if c.button("حذف", key=f"tab_rm_{tid}", disabled=len(tabs_work) <= 1):
                    remove_id = tid

                st.markdown("**چیدمان Blockها**")
                current_blocks = normalize_blocks(tab.get("blocks") or persona_blocks,
                                                  st.session_state.report_persona)
                picked = st.multiselect(
                    "Blockهای این تب", list(BLOCKS), default=current_blocks,
                    format_func=lambda k: BLOCKS[k], key=f"tab_blocks_{tid}")
                ordered = [x for x in current_blocks if x in picked] + [x for x in picked if x not in current_blocks]
                # Primary ordering path: the offline Streamlit Components v1 drag/drop
                # shipped in the user's Process Explorer package. No npm/pip package.
                dnd_order = None
                if _has_native_dnd and ordered:
                    try:
                        dnd_order = draggable_list(
                            [{"id": k, "label": BLOCKS[k], "badge": "Block"} for k in ordered],
                            key=f"gsi_report_blocks_dnd_{tid}")
                    except Exception:
                        dnd_order = None
                if dnd_order:
                    rank = {k:i for i,k in enumerate(dnd_order)}
                    ordered = sorted(ordered, key=lambda k: rank.get(k, len(rank)))
                elif _has_sortables and ordered:
                    labels_order = [f"{BLOCKS[k]} 〔{k}〕" for k in ordered]
                    sorted_labels = sort_items(labels_order, direction="vertical",
                                               key=f"report_blocks_sort_{tid}")
                    ordered = [x.rsplit("〔",1)[1].rstrip("〕") for x in sorted_labels]
                if ordered:
                    st.caption("↕ Drag & Drop بالا، ترتیب دقیق Blockها در HTML را تعیین می‌کند؛ حذف/اضافه از Multiselect انجام می‌شود.")
                block_sizes = dict(tab.get("block_sizes") or {})
                if ordered:
                    with st.expander("اندازه Blockها در HTML", expanded=False):
                        for bk in ordered:
                            block_sizes[bk] = st.selectbox(
                                f"{BLOCKS[bk]}", list(SIZES),
                                index=list(SIZES).index(block_sizes.get(bk, "full")) if block_sizes.get(bk, "full") in SIZES else 0,
                                format_func=lambda z: SIZES[z], key=f"tab_block_size_{tid}_{bk}")

                chart_prev = [x for x in list(tab.get("charts") or []) if x in EMAIL_CHARTS]
                if "charts" in ordered:
                    chart_pick = st.multiselect(
                        "نمودارهای همین تب — اضافه/حذف",
                        list(EMAIL_CHARTS), default=chart_prev,
                        format_func=lambda k: EMAIL_CHARTS[k], key=f"tab_charts_{tid}")
                    chart_i = [x for x in chart_prev if x in chart_pick] + [x for x in chart_pick if x not in chart_prev]
                    corder = None
                    if _has_native_dnd and chart_i:
                        try:
                            corder = draggable_list(
                                [{"id": k, "label": EMAIL_CHARTS[k], "badge": "Chart"} for k in chart_i],
                                key=f"gsi_report_charts_dnd_{tid}")
                        except Exception:
                            corder = None
                    if corder:
                        cr = {k:i for i,k in enumerate(corder)}; chart_i = sorted(chart_i, key=lambda k: cr.get(k, len(cr)))
                    chart_sizes = dict(tab.get("chart_sizes") or {})
                    with st.expander("اندازه نمودارهای این تب", expanded=False):
                        for ck in chart_i:
                            chart_sizes[ck] = st.selectbox(
                                EMAIL_CHARTS[ck], list(SIZES),
                                index=list(SIZES).index(chart_sizes.get(ck, "half")) if chart_sizes.get(ck, "half") in SIZES else 1,
                                format_func=lambda z: SIZES[z], key=f"tab_chart_size_{tid}_{ck}")
                else:
                    chart_i = []; chart_sizes = {}

                process_prev = [x for x in list(tab.get("process_views") or []) if x in PROCESS_VIEWS]
                if "process" in ordered:
                    process_pick = st.multiselect(
                        "Process Viewهای همین تب — اضافه/حذف",
                        list(PROCESS_VIEWS), default=process_prev,
                        format_func=lambda k: PROCESS_VIEWS[k], key=f"tab_process_{tid}")
                    process_i = [x for x in process_prev if x in process_pick] + [x for x in process_pick if x not in process_prev]
                    porder = None
                    if _has_native_dnd and process_i:
                        try:
                            porder = draggable_list(
                                [{"id": k, "label": PROCESS_VIEWS[k], "badge": "Process"} for k in process_i],
                                key=f"gsi_report_process_dnd_{tid}")
                        except Exception:
                            porder = None
                    if porder:
                        pr = {k:i for i,k in enumerate(porder)}; process_i = sorted(process_i, key=lambda k: pr.get(k, len(pr)))
                    process_sizes = dict(tab.get("process_sizes") or {})
                    with st.expander("اندازه نماهای فرآیندی", expanded=False):
                        for pk in process_i:
                            process_sizes[pk] = st.selectbox(
                                PROCESS_VIEWS[pk], list(SIZES),
                                index=list(SIZES).index(process_sizes.get(pk, "full")) if process_sizes.get(pk, "full") in SIZES else 0,
                                format_func=lambda z: SIZES[z], key=f"tab_process_size_{tid}_{pk}")
                    st.caption("Process Map، Aging، Bottleneck، Heatmap، Variants، Conformance، Funnel و Timeline مستقل و قابل جابه‌جایی‌اند.")
                else:
                    process_i = []; process_sizes = {}

                kanban_mode = tab.get("kanban_mode", "due_window")
                kanban_fields = list(tab.get("kanban_card_fields") or [])
                if "kanban" in ordered:
                    k1, k2 = st.columns([1, 2])
                    kanban_mode = k1.selectbox(
                        "ساختار Board", list(KANBAN_MODES),
                        index=list(KANBAN_MODES).index(kanban_mode) if kanban_mode in KANBAN_MODES else 0,
                        format_func=lambda k: KANBAN_MODES[k], key=f"tab_kanban_mode_{tid}")
                    kanban_fields = k2.multiselect(
                        "جزئیات کارت Kanban", list(KANBAN_CARD_FIELDS),
                        default=[x for x in kanban_fields if x in KANBAN_CARD_FIELDS],
                        format_func=lambda k: KANBAN_CARD_FIELDS[k], key=f"tab_kanban_fields_{tid}")
                else:
                    kanban_fields = []

                max_i = st.number_input("حداکثر ردیف همین تب (۰ = مقدار عمومی)", 0, 100000,
                                        int(tab.get("max_rows") or 0), 100,
                                        key=f"tab_max_rows_{tid}")
                next_tabs.append({
                    "id": tid, "title": title_i, "fields": fields_i,
                    "blocks": ordered, "block_sizes": {k:block_sizes.get(k,"full") for k in ordered},
                    "charts": chart_i, "chart_sizes": {k:chart_sizes.get(k,"half") for k in chart_i},
                    "process_views": process_i, "process_sizes": {k:process_sizes.get(k,"full") for k in process_i}, "kanban_mode": kanban_mode,
                    "kanban_card_fields": kanban_fields, "max_rows": int(max_i),
                })

        if remove_id:
            next_tabs = [t for t in next_tabs if t["id"] != remove_id]
            st.session_state.report_tabs = next_tabs
            st.session_state.report_tabs_by_persona[st.session_state.report_persona] = next_tabs
            st.rerun()
        st.session_state.report_tabs = next_tabs
        st.session_state.report_tabs_by_persona[st.session_state.report_persona] = next_tabs

        tadd1, tadd2 = st.columns([1,1])
        if tadd1.button("＋ افزودن تب مستقل", width="stretch"):
            st.session_state.report_tabs.append(new_tab(
                f"تب {len(st.session_state.report_tabs)+1}", list(sel_cols),
                st.session_state.report_persona, []))
            st.session_state.report_tabs_by_persona[st.session_state.report_persona] = st.session_state.report_tabs
            st.rerun()
        if tadd2.button("⧉ کپی تب آخر", width="stretch"):
            import copy
            clone = copy.deepcopy(st.session_state.report_tabs[-1])
            clone["id"] = new_tab("x", [], st.session_state.report_persona)["id"]
            clone["title"] = clone.get("title", "تب") + " — کپی"
            st.session_state.report_tabs.append(clone)
            st.session_state.report_tabs_by_persona[st.session_state.report_persona] = st.session_state.report_tabs
            st.rerun()

    with st.container(border=True):
        panel_open("۱٫۷ · Header و هویت خروجی",
                   "Header HTML و Email مستقل‌اند و همراه Design ذخیره می‌شوند.")
        h1,h2 = st.columns([1,2])
        preset = h1.selectbox("قالب Header HTML", list(HEADER_PRESETS),
                              key="studio_header_preset",
                              format_func=lambda k: HEADER_PRESETS[k]["fa"])
        if h1.button("اعمال متن پیش‌فرض Header", width="stretch"):
            st.session_state.studio_html_header = HEADER_PRESETS[preset]["title"]
            st.session_state.studio_html_subtitle = HEADER_PRESETS[preset]["subtitle"]
            st.rerun()
        h2.text_input("عنوان Header HTML", key="studio_html_header")
        h2.text_input("زیرعنوان Header HTML", key="studio_html_subtitle")

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
            want_learning = st.checkbox("چت‌بات", value=True,
                                        help="دستیار آفلاین Shared Folder در HTML فعال می‌شود؛ محتوای تکمیلی اختیاری است.")
        with c:
            st.markdown("**دامنه**")
            rows_cap = st.number_input("حداکثر ردیف", 100, 100000,
                                       int(T.max_rows), 100)
            stem = st.text_input("نام فایل", f"GSI {T.title}")
        st.caption(f"فیلدهای انتخابی: **{len(sel_cols):,}** — از تب «سازنده گزارش» "
                   f"تغییرشان دهید.")

    with st.container(border=True):
        panel_open("۲٫۴ · چت‌بات",
                   "چت‌بات مستقل از محتوای تکمیلی است؛ اگر chatbot.html ساخته شده باشد در HTML گزارش نمایش داده می‌شود.")
        from gsi.knowledge_desk import load_config as _load_kb_cfg, discover_lessons as _discover_lessons
        _kcfg = _load_kb_cfg()
        _lessons = _discover_lessons(_kcfg.lessons_path)
        _lesson_ids = [str(x.get("id")) for x in _lessons]
        _lesson_id = st.selectbox("محتوای تکمیلی HTML (اختیاری)", _lesson_ids,
                                  index=0,
                                  format_func=lambda x: next((str(z.get("title", "")) for z in _lessons if str(z.get("id"))==x), x),
                                  disabled=(not want_learning), key="studio_learning_lesson") if _lesson_ids else ""
        _selected_lesson = next((z for z in _lessons if str(z.get("id")) == _lesson_id), None)
        from gsi.knowledge_desk import path_to_file_uri as _kb_file_uri
        _kb_entry = Path(_kcfg.chatbot_path) if _kcfg.chatbot_path else None
        _kb_href = _kb_file_uri(str(_kb_entry)) if (_kb_entry and _kb_entry.exists()) else ""
        if _kcfg.enabled and _kb_href:
            st.caption("چت‌بات HTML آماده است · حالت آفلاین Shared-Folder-only")
        else:
            st.caption("چت‌بات هنوز ساخته نشده؛ از محیط «دستیار دانش بازرگانی» مسیرها را انتخاب و آن را ایجاد کنید.")

    with st.container(border=True):
        panel_open("۲٫۵ · نمودارهای ایمیل",
                   "نمودارهای HTML دیگر global نیستند؛ داخل Composer و برای هر تب جدا انتخاب می‌شوند. ایمیل انتخاب مستقل خود را دارد.")
        email_pick = st.multiselect(
            "نمودارهای ایمیل", list(EMAIL_CHARTS.keys()),
            default=[x for x in st.session_state.email_chart_keys if x in EMAIL_CHARTS],
            format_func=lambda k: EMAIL_CHARTS[k], key="email_chart_picker")
        st.session_state.email_chart_keys = email_pick

    with st.container(border=True):
        panel_open("۲٫۷ · دامنه دسترسی خروجی",
                   "Scope قبل از embed شدن داده در HTML/Excel اعمال می‌شود؛ فیلتر داخل مرورگر کنترل امنیتی نیست.")
        dept_opts = sorted(x for x in fdf.get("ORG_DEPT", pd.Series(dtype=str)).dropna().astype(str).unique() if x.strip())
        expert_opts = sorted(x for x in fdf.get("CANONICAL_EXPERT", pd.Series(dtype=str)).dropna().astype(str).unique() if x.strip())
        ac1, ac2, ac3 = st.columns([1,1,1])
        scoped_depts = ac1.multiselect("اداره‌های مجاز", dept_opts, key="access_departments")
        scoped_experts = ac2.multiselect("کارشناسان مجاز", expert_opts, key="access_experts")
        allow_sensitive = ac3.checkbox("اجازه فیلد حساس", value=False, key="allow_sensitive")

    # ── کنترل صحت، پیش از ساخت ──
    with st.container(border=True):
        panel_open("۳ · کنترل صحت محاسبات",
                   "هر ستون عددی با دانه‌ی خودش تجمیع می‌شود تا دوباره‌شماری رخ ندهد.")
        from gsi.studio_core.grain import fanout as _fanout, integrity_report as _integ
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
            st.dataframe(fo, width="stretch", hide_index=True)
        integ = _integ(fdf, sel_cols, DISPLAY)
        if not integ.empty:
            with st.expander(f"ردپای محاسباتی {len(integ)} ستون عددی", expanded=False):
                st.dataframe(integ, width="stretch", hide_index=True)

    # ── ساخت ──
    formats = ([("excel") ] if f_xls else []) + (["html"] if f_html else []) \
        + (["pdf"] if f_pdf else [])
    if st.button("🛠 ساخت گزارش", type="primary", width="stretch",
                 disabled=not formats):
        out_dir = (Path(os.getenv("GSI_DAILY_REPORT_ROOT",
                                  str(Path(official_excel).parent)))
                   / ref_date / "reports")
        template_fields = st.session_state.get("template_field_overrides", {}).get(pick) or sel_cols
        spec = ReportSpec(template=pick, fields=template_fields, ref_date=ref_date,
                          title=f"GSI — {T.title}", formats=formats,
                          persona=st.session_state.report_persona,
                          visuals=want_vis, tables=want_tab,
                          max_rows=int(rows_cap), file_stem=(stem.strip() or f"GSI {T.title}") + " - " + audience_profiles.get(st.session_state.report_persona).fa,
                          tabs=st.session_state.report_tabs,
                          html_charts=list(dict.fromkeys(k for _t in st.session_state.report_tabs for k in _t.get("charts", []))),
                          email_charts=list(st.session_state.email_chart_keys),
                          departments=list(scoped_depts), experts=list(scoped_experts),
                          deny_sensitive=not allow_sensitive,
                          warehouse_run_id=str(extras.get("warehouse_run_id", "") or ""),
                          html_header=st.session_state.studio_html_header,
                          html_subtitle=st.session_state.studio_html_subtitle,
                          html_header_preset=st.session_state.studio_header_preset,
                          learning_enabled=bool(want_learning),
                          learning_lesson=(_selected_lesson or {}),
                          anythingllm_embed={},
                          knowledge_chat=({"chatbot_href": _kb_href} if (_kcfg.enabled and _kb_href) else {}))
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
                                      mime=mime, width="stretch",
                                      key=f"dl_{kind}")

    with st.container(border=True):
        panel_open("۵ · پیش‌نمایش و ارسال ایمیل",
                   "TO/CC، عنوان، مقدمه و نمودارها قابل تنظیم‌اند؛ تنظیمات همراه Design ذخیره می‌شوند.")
        from gsi.integrations.daily_email import configured_recipients, email_font_status
        if not st.session_state.studio_email_to:
            st.session_state.studio_email_to = "; ".join(configured_recipients())
        em1, em2 = st.columns(2)
        em1.text_input("TO (با ; یا , جدا کنید)", key="studio_email_to")
        em2.text_input("CC (اختیاری)", key="studio_email_cc")
        eh1, eh2 = st.columns([1,2])
        email_header_preset = eh1.selectbox("Header پیشنهادی ایمیل", list(HEADER_PRESETS),
                                            format_func=lambda k: HEADER_PRESETS[k]["fa"],
                                            key="studio_email_header_preset")
        if eh1.button("اعمال Header پیشنهادی ایمیل", width="stretch"):
            st.session_state.studio_email_header = HEADER_PRESETS[email_header_preset]["title"]
            st.session_state.studio_email_subtitle = HEADER_PRESETS[email_header_preset]["subtitle"]
            st.rerun()
        eh2.text_input("Header ایمیل", key="studio_email_header")
        eh2.text_input("زیرعنوان Header ایمیل", key="studio_email_subtitle")
        st.text_area("متن مقدمه ایمیل", key="studio_email_intro", height=90)
        fs = email_font_status()
        if not fs.get("ok"):
            st.caption("⚠️ IRANSans برای نمودارهای ایمیل روی این سیستم پیدا نشد؛ در صورت نیاز GSI_FONT_PATH را تنظیم کنید.")
        if st.button("✉️ ساخت HTML ایمیل", width="stretch", disabled=not st.session_state.email_chart_keys):
            email_dir = Path(os.getenv("GSI_DAILY_REPORT_ROOT", str(Path(official_excel).parent))) / ref_date / "reports"
            email_dir.mkdir(parents=True, exist_ok=True)
            assets = email_dir / "email_assets"
            charts = make_email_charts(fdf, assets, selected=st.session_state.email_chart_keys, extras=extras)
            email_artifact = Path((files.get("html") or files.get("excel") or official_excel))
            body = build_email_html(date.fromisoformat(ref_date), fdf, charts, email_artifact,
                                    header_title=st.session_state.studio_email_header,
                                    header_subtitle=st.session_state.studio_email_subtitle,
                                    intro_text=st.session_state.studio_email_intro)
            email_path = email_dir / f"{ref_date}_GSI_Selected_Email.html"
            email_path.write_text(body, encoding="utf-8")
            st.download_button("⬇ دانلود HTML ایمیل", email_path.read_bytes(),
                               file_name=email_path.name, mime="text/html",
                               key="dl_selected_email")

        st.markdown("---")
        e1,e2=st.columns([2,1])
        studio_subject=e1.text_input("موضوع ایمیل",value=f"GSI Studio — گزارش فیلترشده — {ref_date}",key="studio_subject")
        display_only=e2.checkbox("فقط نمایش در Outlook",value=True,key="studio_display")
        if st.button("📨 ارسال/نمایش همین گزارش فیلترشده در Outlook",width="stretch"):
            try:
                from gsi.integrations.daily_email import create_studio_email
                outdir=Path(os.getenv("GSI_DAILY_REPORT_ROOT",str(Path(official_excel).parent)))/ref_date/"studio";outdir.mkdir(parents=True,exist_ok=True)
                xlsx=outdir/f"{ref_date}_GSI_Studio_Filtered.xlsx"
                build_custom_excel(fdf,xlsx,["kpi","table","process"],ref_date,max_rows=int(rows_cap),selected_fields=sel_cols,field_labels=DISPLAY,process_tables={k:extras.get(k) for k in ("eventlog","case_table","bottlenecks","variants","conformance_cases","conformance_root_causes")})
                html_attachment = Path(files["html"]) if files.get("html") and Path(files["html"]).exists() else None
                r=create_studio_email(day=date.fromisoformat(ref_date),df=fdf,excel=xlsx,html_report=html_attachment,
                    selected_charts=st.session_state.email_chart_keys,process_extras=extras,
                    send=not display_only,display=display_only,subject=studio_subject,
                    to=st.session_state.studio_email_to,cc=st.session_state.studio_email_cc,
                    header_title=st.session_state.studio_email_header,header_subtitle=st.session_state.studio_email_subtitle,
                    intro_text=st.session_state.studio_email_intro)
                st.success(f"Outlook آماده شد · {r['recipients']} گیرنده · {r['charts']} نمودار")
            except Exception as ex:st.error(f"Outlook: {ex}")
            st.caption(f"{len(charts)} نمودار در ایمیل قرار گرفت.")

    with st.container(border=True):
        panel_open("گزارش رسمی خط لوله",
                   "۱۷ شیت کامل، ساخته‌شده توسط خط لوله — فیلترنشده.")
        if official_excel and Path(official_excel).exists():
            # Do NOT read the often-large Systemmatic Material workbook on every
            # Streamlit rerun. Preparing download bytes is now explicit and lazy.
            _xp = Path(official_excel)
            _sig = f"{_xp.resolve()}|{_xp.stat().st_size}|{_xp.stat().st_mtime_ns}"
            if st.session_state.get("official_excel_sig") != _sig:
                st.session_state.pop("official_excel_bytes", None)
                st.session_state["official_excel_sig"] = _sig
            if "official_excel_bytes" not in st.session_state:
                st.caption(f"Excel رسمی آماده است · {_xp.stat().st_size/1024/1024:.1f} MB · برای جلوگیری از کندی صفحه فقط هنگام درخواست خوانده می‌شود.")
                if st.button("آماده‌سازی دانلود Excel رسمی", key="prepare_official_excel_download", width="stretch"):
                    with st.spinner("در حال آماده‌سازی فایل برای دانلود…"):
                        st.session_state["official_excel_bytes"] = _xp.read_bytes()
                    st.rerun()
            else:
                st.download_button("⬇ دانلود Excel رسمی", st.session_state["official_excel_bytes"],
                                   file_name=_xp.name,
                                   mime=("application/vnd.openxmlformats-officedocument"
                                         ".spreadsheetml.sheet"),
                                   key="download_official_excel")

st.caption("GSI | Global Sourcing Intelligence — Data • Process • Decision؛ لایه نمایش و خروجی روی همان Pipeline/Rulebook موجود؛ "
           "منطق کسب‌وکار در موتور GSI باقی می‌ماند.")

from gsi.cashflow.ui import render as render_cashflow
with tab_export:
    render_cashflow(fdf, extras, ref_date)
