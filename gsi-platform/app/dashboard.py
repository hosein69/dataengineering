# -*- coding: utf-8 -*-
"""داشبورد زنده GSI — Streamlit.

اجرا:
    streamlit run app/dashboard.py
    # یا با پورت دلخواه:
    streamlit run app/dashboard.py --server.port 8600

خروجی‌ها: HTML مستقل (با CSS و JS درون‌خط)، PDF (از طریق چاپ مرورگر)،
و اکسل کامل.

## اصول طراحی

پالت: آکوا، طیف سبز، سفید، خاکستری. پس‌زمینه متحرک عمداً **کم‌شتاب و
کم‌کنتراست** است — حرکت باید عمق بدهد نه اینکه چشم را از عدد بدزدد.
انیمیشن فقط جایی است که معنا دارد: نبض روی کارت‌های بحرانی، یعنی «این
عدد در حال بدتر شدن است».

هر کارت یک سؤال تصمیم‌ساز را جواب می‌دهد؛ کارتی که تصمیمی را عوض نکند
حذف شده است.
"""
from __future__ import annotations

import base64
import io
import os
import sys
from pathlib import Path
from datetime import date
from typing import Any, Dict, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from gsi.studio_core.html_export import build_dynamic_html
from gsi.factsheet import VERSION as GSI_RUNTIME_VERSION

try:
    import plotly.express as px
    import plotly.graph_objects as go
    _HAS_PLOTLY = True
except Exception:                                     # pragma: no cover
    _HAS_PLOTLY = False

# منطق خالص در ui_kit است تا بدون Streamlit هم قابل تست باشد
from app.ui_kit import (AQUA, AQUA_DEEP, AQUA_SOFT, AMBER, BAND_COLORS,  # noqa: E402
                        GREEN, GREEN_SOFT, GREY, GREY_BG, RED, WHITE,
                        band_count as _band_count, card_html, detail_columns,
                        export_html, kpis, num as _num)

st.set_page_config(page_title="GSI — مغز لجستیک",
                   page_icon="◈", layout="wide",
                   initial_sidebar_state="expanded")

CSS = f"""
<style>


html, body, [class*="css"] {{
    font-family: 'IRANSans Light', 'IRANSans', Tahoma, Arial, sans-serif !important;
    direction: rtl;
}}

/* ── پس‌زمینه متحرک: سه لکه نور که آرام جابه‌جا می‌شوند ── */
.stApp {{
    background: linear-gradient(135deg, {WHITE} 0%, {GREY_BG} 100%);
    /* ⚠️ position را اینجا override نکنید.
       Streamlit خودش .stApp را «position:absolute; inset:0» می‌گذارد و
       #stAppViewContainer (که absolute است) ارتفاعش را از همان می‌گیرد.
       با «position:relative» ارتفاع .stApp صفر می‌شد، ViewContainer هم صفر،
       و چون overflow آن hidden است کل داشبورد سفیدِ خالی رندر می‌شد —
       عناصر در DOM بودند ولی هیچ‌چیز نقاشی نمی‌شد.
       لکه‌های پس‌زمینه position:fixed هستند و به viewport لنگر می‌اندازند،
       پس برای جلوه بصری هیچ نیازی به relative نیست. */
    overflow-x: hidden;
}}
.stApp::before, .stApp::after {{
    content: "";
    position: fixed;
    border-radius: 50%;
    filter: blur(90px);
    opacity: .22;
    z-index: 0;
    pointer-events: none;
}}
.stApp::before {{
    width: 46vw; height: 46vw;
    background: radial-gradient(circle, {AQUA} 0%, transparent 68%);
    top: -12vw; right: -10vw;
    animation: drift1 26s ease-in-out infinite alternate;
}}
.stApp::after {{
    width: 38vw; height: 38vw;
    background: radial-gradient(circle, {AQUA_SOFT} 0%, transparent 70%);
    bottom: -14vw; left: -8vw;
    animation: drift2 32s ease-in-out infinite alternate;
}}
@keyframes drift1 {{
    0%   {{ transform: translate(0,0) scale(1); }}
    100% {{ transform: translate(-6vw, 7vh) scale(1.14); }}
}}
@keyframes drift2 {{
    0%   {{ transform: translate(0,0) scale(1.08); }}
    100% {{ transform: translate(7vw, -6vh) scale(1); }}
}}
.block-container {{ position: relative; z-index: 1; padding-top: 1.4rem; }}

/* ── کارت‌ها ── */
.kpi {{
    background: rgba(255,255,255,.80);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(15,110,110,.14);
    border-radius: 18px;
    padding: 18px 20px 16px;
    box-shadow: 0 6px 26px rgba(15,110,110,.09);
    transition: transform .22s cubic-bezier(.2,.8,.2,1), box-shadow .22s;
    height: 100%;
}}
.kpi:hover {{
    transform: translateY(-5px);
    box-shadow: 0 14px 40px rgba(15,110,110,.17);
}}
.kpi .lbl {{
    font-size: .82rem; color: {GREY}; font-weight: 400;
    letter-spacing: .2px; margin-bottom: 6px;
}}
.kpi .val {{
    font-size: 2.05rem; font-weight: 800; color: {AQUA_DEEP};
    line-height: 1.12; font-variant-numeric: tabular-nums;
}}
.kpi .sub {{ font-size: .72rem; color: {GREY}; margin-top: 6px; opacity: .85; }}
.kpi .bar {{
    height: 3px; border-radius: 3px; margin-top: 12px;
    background: linear-gradient(90deg, {AQUA} 0%, {AQUA_SOFT} 100%);
}}

/* کارت بحرانی: نبض ملایم — یعنی این عدد در حال بدتر شدن است */
.kpi.crit {{ border-color: rgba(146,43,33,.32); }}
.kpi.crit .val {{ color: {RED}; }}
.kpi.crit .bar {{ background: linear-gradient(90deg, {RED} 0%, {AMBER} 100%); }}
.kpi.crit::after {{
    content: ""; position: absolute; inset: 0; border-radius: 18px;
    box-shadow: 0 0 0 0 rgba(146,43,33,.28);
    animation: pulse 2.6s ease-out infinite; pointer-events: none;
}}
@keyframes pulse {{
    0%   {{ box-shadow: 0 0 0 0 rgba(146,43,33,.30); }}
    70%  {{ box-shadow: 0 0 0 16px rgba(146,43,33,0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(146,43,33,0); }}
}}
div[data-testid="column"] > div {{ position: relative; }}

h1, h2, h3 {{ color: {AQUA_DEEP} !important; font-weight: 800 !important; }}
hr {{ border-color: rgba(15,110,110,.14); }}
section[data-testid="stSidebar"] {{
    background: rgba(255,255,255,.92);
    border-left: 1px solid rgba(15,110,110,.12);
}}
.stDataFrame {{ border-radius: 14px; overflow: hidden; }}
@media print {{
    .stApp::before, .stApp::after, section[data-testid="stSidebar"] {{ display: none; }}
    .kpi {{ break-inside: avoid; box-shadow: none; }}
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
from app.styles import css as _gsi_shared_css
st.markdown(_gsi_shared_css(), unsafe_allow_html=True)


# ═══════════ داده ═══════════
# First paint نباید منتظر ETL بماند.
# اندازه‌گیری روی همین بسته (۶ ردیف، دادهٔ آزمون):
#     Pipeline().run(build_report=True)   → ۳٫۵۴ ثانیه
#     Pipeline().run(build_report=False)  → ۱٫۷۳ ثانیه
#     last_report()  (Snapshot منتشرشده)  → ۰٫۰۰۵ ثانیه
# روی دادهٔ واقعی (۶۳۱ هزار ردیف، ۱۷ فایل) ستون اول دقیقه‌ای است و ستون سوم
# تقریباً ثابت می‌ماند، چون فقط دو فریم mart را از کش/SQLite می‌خواند.
# بنابراین مسیر پیش‌فرضِ باز شدن صفحه، خواندن اجرای منتشرشده است؛ اجرای دوبارهٔ
# خط لوله فقط وقتی انجام می‌شود که اجرای منتشرشده‌ای برای آن تاریخ نباشد یا
# کاربر صریحاً دکمهٔ «اجرای مجدد خط لوله» را بزند. این تغییر هیچ عددی را عوض
# نمی‌کند: همان Snapshotی خوانده می‌شود که خط لوله خودش منتشر کرده است.
@st.cache_data(show_spinner="در حال خواندن اجرای منتشرشده…", max_entries=3, ttl=900)
def load_published(today: Optional[str] = None) -> Optional[Dict[str, Any]]:
    from gsi.warehouse.service import last_report
    found = last_report(today)
    stale = False
    if found is None:
        found = last_report(None)
        stale = found is not None
    if found is None:
        return None
    df, main, extras, report = found
    # extras stays lazy; opening the UI never materializes all analytical marts.
    extras['runtime_status'] = 'STALE_PUBLISHED_SNAPSHOT' if stale else 'PUBLISHED_SNAPSHOT'
    extras['stale_snapshot'] = stale
    if stale:
        extras['requested_reference_date'] = today
    return {"df": df, "main": main, "to_resolve": pd.DataFrame(),
            "extras": extras, "dashboard": report}


@st.cache_data(show_spinner="در حال اجرای خط لوله…", max_entries=2, ttl=3600)
def load_pipeline(today: Optional[str] = None) -> Dict[str, Any]:
    # ست‌کردن GSI_TODAY بیرون از این تابع انجام می‌شود؛ در cache hit بدنه
    # اجرا نمی‌شود و تاریخ مرجع واقعی با تاریخ نمایش‌داده‌شده فرق می‌کرد.
    from gsi.pipeline import Pipeline
    try:
        res = Pipeline().run(build_report=True)
        return {
            "df": res.df, "main": res.main, "to_resolve": res.to_resolve,
            "extras": dict(res.extras), "dashboard": res.dashboard_path,
        }
    except Exception as ex:
        from gsi.warehouse.writer_lock import WarehouseBusyError
        if not isinstance(ex, WarehouseBusyError):
            raise
        from gsi.warehouse.service import last_report
        fallback = last_report(None)
        if fallback is None:
            raise
        df, main, extras, report = fallback
        # dict(extras) نگاشت تنبل را همین‌جا کامل باز می‌کرد.
        extras['runtime_status'] = 'UPDATE_IN_PROGRESS'
        extras['runtime_diagnostic'] = ex.as_dict()
        extras['stale_snapshot'] = True
        return {"df":df, "main":main, "to_resolve":pd.DataFrame(), "extras":extras, "dashboard":report}


card = card_html


def num(df: pd.DataFrame, col: str) -> pd.Series:
    return _num(df, col)


# ═══════════ نوار کناری ═══════════
st.sidebar.markdown(f"### ◈ GSI\n<span style='color:{GREY}'>مغز شناختی لجستیک</span>",
                    unsafe_allow_html=True)
st.sidebar.success(f"Build {GSI_RUNTIME_VERSION} · Dashboard Runtime")
ref_date = st.sidebar.text_input("تاریخ مرجع (YYYY-MM-DD)",
                                 value=os.environ.get("GSI_TODAY") or str(date.today()))
_rerun = st.sidebar.button("اجرای مجدد خط لوله", width="stretch",
                           help="خط لوله را از روی فایل‌های منبع دوباره اجرا می‌کند. "
                                "بدون این دکمه، صفحه آخرین اجرای منتشرشده را می‌خواند.")
if _rerun:
    st.cache_data.clear()

try:
    date.fromisoformat(ref_date.strip())
except ValueError:
    st.sidebar.error("تاریخ مرجع باید به شکل YYYY-MM-DD باشد.")
    st.stop()
ref_date = ref_date.strip()
os.environ["GSI_TODAY"] = ref_date

try:
    data = None if _rerun else load_published(ref_date)
    if _rerun:
        data = load_pipeline(ref_date)
    elif data is None:
        st.error("هیچ Snapshot منتشرشده‌ای وجود ندارد. برای ساخت اولیه، دکمه «اجرای مجدد خط لوله» را بزنید یا REFRESH_GSI_DATA.cmd را اجرا کنید.")
        st.stop()
except Exception as ex:                               # pragma: no cover
    from app.runtime_errors import render_pipeline_exception
    render_pipeline_exception(st, ex)
    st.stop()

df = data["main"] if not data["main"].empty else data["df"]
all_df = data["df"] if not data["df"].empty else df
_status = (data.get('extras') or {}).get('runtime_status')
if _status == 'PUBLISHED_SNAPSHOT':
    _rid = str((data.get('extras') or {}).get('warehouse_run_id') or '')[:12] or 'نامشخص'
    st.sidebar.caption(f"منبع صفحه: اجرای منتشرشده `{_rid}` · تاریخ مرجع {ref_date}"
                       "  \nبرای خواندن دوبارهٔ فایل‌های منبع، «اجرای مجدد خط لوله» را بزنید.")
if _status == 'STALE_PUBLISHED_SNAPSHOT':
    _pref = (data.get('extras') or {}).get('published_reference_date') or 'نامشخص'
    st.sidebar.warning(f"Snapshot تاریخ {ref_date} موجود نیست؛ آخرین Snapshot سالم ({_pref}) نمایش داده می‌شود. Refresh خودکار اجرا نشده است.")
elif _status == 'UPDATE_IN_PROGRESS':
    _pref = (data.get('extras') or {}).get('published_reference_date') or 'نامشخص'
    st.warning(f'به‌روزرسانی دیگری در حال اجراست؛ این صفحه آخرین Snapshot سالم را نمایش می‌دهد (تاریخ مرجع: {_pref}).')
from gsi.studio_core.runtime_data import ensure_criticality_columns
df = ensure_criticality_columns(df)
all_df = ensure_criticality_columns(all_df)

# ── سلامت داده امروز، پیش از هر عددی ────────────────────────────────────
# اگر سورسی ناقص بوده، خواننده باید قبل از KPIها بداند؛ وگرنه یک عدد
# سبز را «همه‌چیز مرتب» می‌خواند در حالی که مبنایش ناقص بوده.
try:
    from gsi import health as _health
    from gsi.config.settings import SETTINGS as _S
    _hp = _health.load(str(Path(_S.daily_report_path(_S.today)).parent))
except Exception:
    _hp = None
if _hp and (_hp.get("verdict") != _health.OK or _hp.get("blocking")):
    _c = _hp.get("counts", {})
    _bits = [f"وضعیت داده امروز: **{_hp.get('verdict')}**"]
    if _hp.get("blocking"):
        _bits.append("سورس الزامیِ ناموجود: " + "، ".join(_hp["blocking"]))
    _bits.append(f"سورس سالم/ناقص/خراب: {_c.get('سورس سالم',0)} / "
                 f"{_c.get('سورس ناقص',0)} / {_c.get('سورس خراب/ردشده',0)}")
    (st.error if _hp.get("blocking") else st.warning)(
        " — ".join(_bits) + "  \nجزئیات در شیت «۱۷. سلامت سیستم» گزارش رسمی است.")

# فیلترها
if "بحرانی (کوتاه)" in df.columns:
    bands = sorted(set(df["بحرانی (کوتاه)"].astype(str)))
    pick = st.sidebar.multiselect("طبقه بحرانی", bands, default=bands)
    df = df[df["بحرانی (کوتاه)"].astype(str).isin(pick)]
if "ORG_DEPT" in df.columns:
    depts = sorted({str(x) or "نامشخص" for x in df["ORG_DEPT"]})
    pd_ = st.sidebar.multiselect("مدیریت", depts, default=depts)
    df = df[df["ORG_DEPT"].astype(str).isin(pd_)]

st.sidebar.markdown("---")
from gsi.studio_core.report_builder import _filtered_process_extras
st.sidebar.markdown("### گزارش برای چه کسی؟")
# ── انتخاب مخاطب خروجی HTML ──
#
# داشبورد خودش همیشه نمای «تحلیل‌گر» است: اینجا کسی نشسته که می‌تواند
# دربارهٔ کیفیت داده کاری بکند، پس بنر سلامت داده بالای صفحه می‌ماند.
# اما فایل HTML که از اینجا بیرون می‌رود، مخاطب دیگری دارد و آن اعداد
# برای او فقط تردید می‌سازند بدون آنکه بتواند کاری بکند.
from gsi import audience as _AUD

_aud_labels = {k: fa for k, fa in _AUD.choices()}
_aud_key = st.sidebar.radio(
    "نمای فایل HTML خروجی",
    options=list(_aud_labels),
    format_func=lambda k: _aud_labels[k],
    index=list(_aud_labels).index(_AUD.DEFAULT),
    help="خودِ داشبورد همیشه نمای تحلیل‌گر است؛ این انتخاب فقط روی فایل "
         "HTML که دانلود می‌کنید اثر دارد.")
st.sidebar.caption(_AUD.PROFILES[_aud_key].question)
if not _AUD.PROFILES[_aud_key].show_data_quality:
    st.sidebar.caption("سنجه‌های کیفیت داده در این فایل نمی‌آیند — جایشان "
                       "همین داشبورد و شیت «۱۷. سلامت سیستم» است.")

st.sidebar.markdown("---")
st.sidebar.markdown("### شخصی‌سازی مدیرانه")
show_critical_only = st.sidebar.checkbox("فقط پرونده‌های بحرانی", value=False)
if show_critical_only:
    if "BL_CRITICAL" in df.columns or "ORDER_CRITICAL" in df.columns:
        mask = pd.Series(False, index=df.index)
        if "BL_CRITICAL" in df.columns: mask |= df["BL_CRITICAL"].astype(bool)
        if "ORDER_CRITICAL" in df.columns: mask |= df["ORDER_CRITICAL"].astype(bool)
        df = df[mask]
show_causes = st.sidebar.checkbox("نمایش علت متریال بحرانی", value=True)
compact_mode = st.sidebar.checkbox("حالت مدیریتی فشرده", value=False)

data = {**data, "extras": _filtered_process_extras(data["extras"], df)}
st.sidebar.caption(f"{len(df):,} ردیف پس از فیلتر")

# ═══════════ مرکز عملیات فرآیند — Figma v1 ═══════════
from app import process_cockpit
process_cockpit.render(df, data["extras"], ref_date)
st.markdown("---")

# ═══════════ سربرگ ═══════════
st.markdown(f"# مغز شناختی لجستیک\n"
            f"<span style='color:{GREY}'>تاریخ مرجع {ref_date} — "
            f"{len(df):,} پرونده</span>", unsafe_allow_html=True)

# ═══════════ کارت‌ها ═══════════
def band_count(code: str) -> int:
    return _band_count(df, code)


c = st.columns(4)
c[0].markdown(card("توقف خط", band_count("STOCKOUT"), "موجودی صفر",
                   critical=band_count("STOCKOUT") > 0), unsafe_allow_html=True)
c[1].markdown(card("قطعات بحرانی", band_count("CRITICAL"), "مقاومت زیر ۱۰ روز",
                   critical=band_count("CRITICAL") > 0), unsafe_allow_html=True)
c[2].markdown(card("در حال بحرانی شدن", band_count("BECOMING_CRITICAL"),
                   "بین ۱۰ تا ۲۰ روز"), unsafe_allow_html=True)
low = num(df, "مقاومت (روز)").min()
c[3].markdown(card("کمترین مقاومت", "—" if pd.isna(low) else f"{low:,.1f} روز",
                   "بحرانی‌ترین قطعه", critical=(not pd.isna(low) and low < 10)),
              unsafe_allow_html=True)

c = st.columns(5)
from gsi.report.financial_summary import commitment_display, commitment_equivalent_display
bal = commitment_display(df)
bal_eq = commitment_equivalent_display(df)
overdue = int((num(df, "روزهای تأخیر").fillna(0) > 0).sum())
c[0].markdown(card("جمع مانده تعهد", bal, "Native؛ ثبت سفارش یکتا/ارز"), unsafe_allow_html=True)
c[1].markdown(card("معادل مانده تعهد", bal_eq, "EUR / IRR؛ فقط شاهد همان پرونده"), unsafe_allow_html=True)
c[2].markdown(card("تعهدات معوق", overdue, "عبور از مهلت قانونی",
                   critical=overdue > 0), unsafe_allow_html=True)
c[3].markdown(card("میانگین رسوب", f"{num(df, 'روزهای رسوب').mean():,.1f} روز"
                   if num(df, "روزهای رسوب").notna().any() else "—",
                   "از تاریخ تخلیه"), unsafe_allow_html=True)
c[4].markdown(card("میانگین ریسک", f"{num(df, 'امتیاز ریسک').mean():,.1f}"
                   if num(df, "امتیاز ریسک").notna().any() else "—",
                   "موتور ۸ مؤلفه‌ای"), unsafe_allow_html=True)

_cov_measured = ("COMMERCIAL_COVERAGE_STATE" in all_df.columns
                 and (all_df["COMMERCIAL_COVERAGE_STATE"] == "measured").any())
missing_commercial = int(all_df.loc[all_df["ORDER_MISSING_COMMERCIAL_EXPERT"].astype(bool), "CANONICAL_ORDER"].replace("", pd.NA).nunique()) if "ORDER_MISSING_COMMERCIAL_EXPERT" in all_df.columns and "CANONICAL_ORDER" in all_df.columns else 0
# ── ردیف حاکمیت: مالکیت قطعه و پاسخگویی ──
_owned = int(df["PART_OWNER"].astype(str).str.strip().ne("").sum()) if "PART_OWNER" in df.columns else 0
_gap = int(df["PART_OWNER_DATA_GAP"].astype(str).str.strip().ne("").sum()) if "PART_OWNER_DATA_GAP" in df.columns else 0
_wait = df["WAITING_ON_SCOPE"].astype(str).str.strip() if "WAITING_ON_SCOPE" in df.columns else pd.Series(dtype=str)
_wait = _wait[_wait.ne("")].value_counts()
_age = num(df, "STATUS_AGE_DAYS")

c = st.columns(4)
c[0].markdown(card("سفارش خارج از Commercial Expert Data",
                   missing_commercial if _cov_measured else "سنجیده نشد",
                   "در جریان اصلی هست؛ بدون انتساب کارشناس خرید" if _cov_measured
                   else "سورس Commercial Expert Data بارگذاری نشد",
                   critical=bool(_cov_measured and missing_commercial > 0)),
              unsafe_allow_html=True)
c[1].markdown(card("قطعه دارای مالک", _owned,
                   f"کارشناس خرید — از {len(df)} ردیف",
                   critical=(len(df) > 0 and _owned < len(df))),
              unsafe_allow_html=True)
c[2].markdown(card("ردیف با شکاف داده مالک", _gap,
                   "داده ناقص است ولی ردیف حذف نشده — علت ثبت شده",
                   critical=_gap > 0), unsafe_allow_html=True)
c[3].markdown(card("بیشترین انتظار روی",
                   _wait.index[0] if not _wait.empty else "—",
                   f"{int(_wait.iloc[0])} ردیف معطل" if not _wait.empty
                   else "معطلی ثبت‌نشده"), unsafe_allow_html=True)

c = st.columns(4)
c[0].markdown(card("کهنه‌ترین وضعیت",
                   "—" if not _age.notna().any() else f"{_age.max():,.0f} روز",
                   "از آخرین رویداد تاریخ‌دار",
                   critical=bool(_age.notna().any() and _age.max() > 90)),
              unsafe_allow_html=True)
c[1].markdown(card("میانگین سن وضعیت",
                   "—" if not _age.notna().any() else f"{_age.mean():,.0f} روز",
                   "میانگین روزهای سکون پرونده‌ها"), unsafe_allow_html=True)

st.markdown("---")

# ═══════════ هشدارهای سطح پرونده ═══════════
if "BL_CRITICAL" in df.columns or "ORDER_CRITICAL" in df.columns:
    st.markdown("## 🔴 بحرانی بودن پرونده — علت تا سطح متریال")
    gcols = [c for c in ["CANONICAL_BL", "CANONICAL_ORDER", "BL_CRITICAL", "ORDER_CRITICAL",
                         "BL_CRITICAL_MATERIALS", "ORDER_CRITICAL_MATERIALS",
                         "BL_CRITICAL_REASON", "ORDER_CRITICAL_REASON",
                         "ORDER_MISSING_COMMERCIAL_EXPERT", "ORDER_MISSING_COMMERCIAL_REASON"] if c in df.columns]
    g = df[gcols].copy()
    subset=[c for c in ["CANONICAL_BL","CANONICAL_ORDER"] if c in g.columns]
    if subset:
        g = g.drop_duplicates(subset=subset, keep="first")
    if "BL_CRITICAL" in g.columns or "ORDER_CRITICAL" in g.columns:
        mask = pd.Series(False, index=g.index)
        if "BL_CRITICAL" in g.columns: mask |= g["BL_CRITICAL"].astype(bool)
        if "ORDER_CRITICAL" in g.columns: mask |= g["ORDER_CRITICAL"].astype(bool)
        g = g[mask]
    if not g.empty:
        st.dataframe(g, width="stretch", hide_index=True)
    else:
        st.success("در این فیلتر هیچ بارنامه یا سفارش بحرانی ثبت نشده است.")

# ═══════════ نمودارها ═══════════
if _HAS_PLOTLY:
    t1, t2, t3, t4 = st.tabs(["بحرانی بودن", "پراکنش", "فرآیند", "سازمان"])

    with t1:
        if "بحرانی (کوتاه)" in df.columns:
            vc = df["بحرانی (کوتاه)"].value_counts()
            fig = go.Figure(go.Bar(
                x=list(vc.index), y=list(vc.values),
                marker_color=[BAND_COLORS.get(str(k), AQUA) for k in vc.index],
                text=list(vc.values), textposition="outside"))
            fig.update_layout(title="توزیع طبقه بحرانی قطعات",
                              plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)", height=420,
                              font=dict(family="IRANSans Light"))
            st.plotly_chart(fig, width="stretch")

        top = df[["KEY_MATERIAL", "مقاومت (روز)"]].copy() \
            if "KEY_MATERIAL" in df.columns else pd.DataFrame()
        if not top.empty:
            top["مقاومت (روز)"] = pd.to_numeric(top["مقاومت (روز)"], errors="coerce")
            top = (top.dropna().groupby("KEY_MATERIAL", as_index=False)["مقاومت (روز)"].min()
                   .nsmallest(15, "مقاومت (روز)"))
            if not top.empty:
                fig = px.bar(top, x="مقاومت (روز)", y="KEY_MATERIAL",
                             orientation="h", title="پانزده قطعه کم‌مقاومت",
                             color="مقاومت (روز)",
                             color_continuous_scale=[[0, RED], [.5, AMBER], [1, GREEN]])
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                                  paper_bgcolor="rgba(0,0,0,0)", height=520,
                                  font=dict(family="IRANSans Light"))
                st.plotly_chart(fig, width="stretch")

    with t2:
        st.caption("ربع پایین‌راست خطرناک‌ترین ناحیه است: مقاومت کم و رسوب زیاد.")
        need = {"مقاومت (روز)", "روزهای رسوب"}
        if need <= set(df.columns):
            sc = df.copy()
            sc["مقاومت (روز)"] = pd.to_numeric(sc["مقاومت (روز)"], errors="coerce")
            sc["روزهای رسوب"] = pd.to_numeric(sc["روزهای رسوب"], errors="coerce")
            sc["امتیاز ریسک"] = pd.to_numeric(sc.get("امتیاز ریسک"), errors="coerce")
            sc = sc.dropna(subset=["مقاومت (روز)", "روزهای رسوب"])
            if not sc.empty:
                fig = px.scatter(
                    sc, x="روزهای رسوب", y="مقاومت (روز)",
                    size=sc["امتیاز ریسک"].fillna(10).clip(lower=6),
                    color=sc.get("بحرانی (کوتاه)"),
                    color_discrete_map=BAND_COLORS,
                    hover_name=sc.get("KEY_MATERIAL"),
                    title="مقاومت در برابر روزهای رسوب")
                fig.add_hline(y=10, line_dash="dot", line_color=RED,
                              annotation_text="آستانه بحرانی ۱۰ روز")
                fig.add_hline(y=20, line_dash="dot", line_color=AMBER,
                              annotation_text="آستانه ۲۰ روز")
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                                  paper_bgcolor="rgba(0,0,0,0)", height=560,
                                  font=dict(family="IRANSans Light"))
                st.plotly_chart(fig, width="stretch")

        if {"FX_NTSW_BALANCE_EUR_EQ", "روزهای تأخیر"} <= set(df.columns):
            # Cross-currency scatter must share one unit. Use only source-backed
            # EUR equivalents; unavailable cases are not coerced to zero.
            keep = [c for c in ["CANONICAL_REG", "CANONICAL_ORDER",
                                "FX_NTSW_BALANCE_EUR_EQ", "روزهای تأخیر"] if c in df.columns]
            s2 = df[keep].copy()
            s2["FX_NTSW_BALANCE_EUR_EQ"] = pd.to_numeric(s2["FX_NTSW_BALANCE_EUR_EQ"], errors="coerce")
            s2["روزهای تأخیر"] = pd.to_numeric(s2["روزهای تأخیر"], errors="coerce")
            if "CANONICAL_REG" in s2.columns:
                s2 = s2.drop_duplicates("CANONICAL_REG")
            s2 = s2.dropna(subset=["FX_NTSW_BALANCE_EUR_EQ", "روزهای تأخیر"])
            s2 = s2[s2["FX_NTSW_BALANCE_EUR_EQ"] > 0]
            if not s2.empty:
                fig = px.scatter(s2, x="روزهای تأخیر", y="FX_NTSW_BALANCE_EUR_EQ",
                                 color_discrete_sequence=[AMBER],
                                 hover_name=s2.get("CANONICAL_ORDER"),
                                 title="معادل یورویی مانده تعهد در برابر روزهای تأخیر")
                fig.update_yaxes(title="مانده تعهد — معادل EUR منبع‌محور")
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                                  paper_bgcolor="rgba(0,0,0,0)", height=480,
                                  font=dict(family="IRANSans Light"))
                st.plotly_chart(fig, width="stretch")

    with t3:
        bott = data["extras"].get("bottlenecks")
        from gsi.studio_core.runtime_data import bottleneck_view
        b, metric = bottleneck_view(bott, limit=10)
        if not b.empty:
            b["گذار"] = b["از فعالیت"].astype(str) + " ← " + b["به فعالیت"].astype(str)
            fig = px.bar(b, x=metric, y="گذار", orientation="h",
                         title="گلوگاه‌های فرآیند", color_discrete_sequence=[AQUA])
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)", height=480,
                              font=dict(family="IRANSans Light"))
            st.plotly_chart(fig, width="stretch")
        var = data["extras"].get("variants")
        if var is not None and not var.empty:
            st.dataframe(var.head(12), width="stretch")

    with t4:
        col = "ORG_DEPT" if "ORG_DEPT" in df.columns else None
        if col:
            vc = df[col].astype(str).replace("", "نامشخص").value_counts().head(10)
            fig = px.bar(x=list(vc.values), y=list(vc.index), orientation="h",
                         title="بار کاری بر حسب مدیریت",
                         color_discrete_sequence=[AQUA_DEEP])
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)", height=460,
                              font=dict(family="IRANSans Light"))
            st.plotly_chart(fig, width="stretch")
else:
    st.warning("برای نمودارها plotly لازم است:  pip install plotly")

# ═══════════ جدول ═══════════
st.markdown("---")
st.subheader("جزئیات پرونده‌ها")
show = detail_columns(df)
st.dataframe(df[show], width="stretch", height=420)

# ═══════════ خروجی‌ها ═══════════
st.markdown("---")
st.subheader("خروجی‌ها")
e1, e2, e3 = st.columns(3)

# اکسل کامل (همان ۱۳ شیت)
try:
    with open(data["dashboard"], "rb") as f:
        e1.download_button("دانلود اکسل کامل (۱۳ شیت)", f.read(),
                           file_name=os.path.basename(data["dashboard"]),
                           mime=("application/vnd.openxmlformats-officedocument"
                                 ".spreadsheetml.sheet"),
                           width="stretch")
except Exception:
    e1.info("فایل اکسل در دسترس نیست.")

# اکسل داده فیلترشده
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as w:
    df[show].to_excel(w, sheet_name="داده فیلترشده", index=False)
e2.download_button("دانلود داده فیلترشده", buf.getvalue(),
                   file_name="GSI_filtered.xlsx",
                   mime=("application/vnd.openxmlformats-officedocument"
                         ".spreadsheetml.sheet"),
                   width="stretch")


# HTML مستقل و تعاملی: همان فیلترها + نمودار + Process Explorer + Excel فیلترشده
html = build_dynamic_html(
    df, ref_date, title="GSI — مغز شناختی لجستیک",
    selected_fields=show, max_rows=max(10000, len(df)),
    labels={c: c for c in show},
    template_title="Executive Process Investigation",
    subtitle=f"{len(df):,} ردیف پس از فیلتر",
    charts=["criticality", "low_resistance", "stock_vs_total", "risk_mix", "org_workload"],
    process_extras=data["extras"], audience=_aud_key)
e3.download_button(f"⬇ دانلود HTML — نمای {_aud_labels[_aud_key]}", html.encode("utf-8"),
                   file_name=f"GSI_{ref_date}_{_aud_key}.html", mime="text/html",
                   width="stretch")

st.markdown("### ✉️ ارسال گزارش از همین پنل")
ec1, ec2, ec3 = st.columns([2, 1, 1])
email_subject = ec1.text_input("موضوع ایمیل", f"GSI — گزارش فیلترشده — {ref_date}")
email_display = ec2.checkbox("نمایش در Outlook", value=True)
email_send = ec3.checkbox("ارسال واقعی", value=False,
                           help="ارسال واقعی از حساب Outlook انتخاب‌شده انجام می‌شود.")
if st.button("📨 ساخت / نمایش / ارسال گزارش فیلترشده", type="primary", width="stretch"):
    try:
        from gsi.integrations.daily_email import create_studio_email
        outdir = Path(os.getenv("GSI_DAILY_REPORT_ROOT", str(Path(data["dashboard"]).parent))) / ref_date / "studio"
        outdir.mkdir(parents=True, exist_ok=True)
        xlsx = outdir / f"{ref_date}_GSI_Studio_Filtered.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
            df[show].to_excel(w, sheet_name="داده فیلترشده", index=False)
        r = create_studio_email(
            day=date.fromisoformat(ref_date), df=df, excel=xlsx,
            selected_charts=["criticality", "low_resistance", "stock_vs_total"],
            send=email_send, display=email_display, subject=email_subject)
        st.success(f"Outlook آماده شد · {r['recipients']} گیرنده · {r['charts']} نمودار · {'ارسال شد' if r['sent'] else 'نمایش/پیش‌نویس'}")
    except Exception as ex:
        st.error(f"ارسال ایمیل ناموفق بود: {ex}")
st.caption("برای PDF: فایل HTML را در مرورگر باز کنید و دکمه «ذخیره به PDF» "
           "را بزنید (یا Ctrl+P ← Save as PDF).")

# Dedicated evidence-led financial outputs use the current case scope.
from gsi.cashflow.ui import render as render_cashflow
render_cashflow(df, data["extras"], ref_date)
