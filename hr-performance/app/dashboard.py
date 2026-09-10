# -*- coding: utf-8 -*-
"""داشبورد عملکرد منابع انسانی — ماژولار، با وزن‌دهی زنده.

وزن‌ها در **هر دو سطح** قابل تغییرند (آیتم داخل کلاستر، و کلاسترها) و
پس از هر تغییر بازنرمال می‌شوند تا مجموع همیشه ۱ بماند. دکمه «بازگشت به
وزن پیشنهادی» همیشه در دسترس است.
"""
from __future__ import annotations

import os
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="عملکرد منابع انسانی", page_icon="◈",
                   layout="wide", initial_sidebar_state="expanded")

from app.styles import band_chip, css, kpi_card
from hrperf.config.model import Cluster, Metric, PerformanceModel, load_model
from hrperf.config.settings import SETTINGS
from hrperf.pipeline import Pipeline
from hrperf.report import templates as tpl
from hrperf.report.builder import ReportSpec, build as build_report
from hrperf.report.theme import BANDS, SEQUENTIAL, SERIES, band_of, plotly_template
from hrperf.score.aggregate import contribution

try:
    import plotly.graph_objects as go
    import plotly.io as pio
    pio.templates["hrp"] = plotly_template()
    pio.templates.default = "hrp"
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

st.markdown(css(), unsafe_allow_html=True)
BASE_MODEL = load_model()


def short(t, n=30):
    t = str(t)
    return t if len(t) <= n else t[:n - 1] + "…"


# ══════════════════════════════════════════════════════════════════════════
#  داده
# ══════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner="در حال خواندن سورس‌ها…")
def load_long(ref_date: str, use_demo: bool):
    if use_demo:
        from tests.make_synthetic import build
        return build()
    from hrperf.dataio.sources import find_org_map, load_all, read_org_map
    long, src_people, _ = load_all(SETTINGS.INPUT_DIR)
    org = find_org_map(SETTINGS.INPUT_DIR)
    people = read_org_map(org) if org else None
    if people is None or people.empty:
        people = src_people if not src_people.empty else None
    return people, long


st.sidebar.markdown("### ◈ عملکرد منابع انسانی")
st.sidebar.caption("سنجش علّی، نه صرفاً همبستگی")

ref_date = st.sidebar.text_input("تاریخ مرجع",
                                 value=os.environ.get("HRP_TODAY") or str(date.today())).strip()
try:
    date.fromisoformat(ref_date)
except ValueError:
    st.sidebar.error("تاریخ باید YYYY-MM-DD باشد.")
    st.stop()

demo = st.sidebar.toggle("داده نمونه (بدون شبکه)", value=True,
                         help="برای دموی بدون اتصال به سورس‌های واقعی")
if st.sidebar.button("↻ خواندن مجدد", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

try:
    people, long = load_long(ref_date, demo)
except Exception as ex:
    st.error(f"خواندن سورس‌ها ناموفق بود: {ex}")
    st.stop()

if long is None or long.empty:
    st.warning("هیچ رکورد شاخصی خوانده نشد. فایل‌ها را در پوشه ورودی بگذارید "
               "یا «داده نمونه» را روشن کنید.")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════
#  وزن‌دهی زنده — دو سطح
# ══════════════════════════════════════════════════════════════════════════
if "cluster_w" not in st.session_state:
    st.session_state.cluster_w = {k: c.weight for k, c in BASE_MODEL.clusters.items()}
if "metric_w" not in st.session_state:
    st.session_state.metric_w = {k: m.weight for k, m in BASE_MODEL.metrics.items()}

with st.sidebar.expander("⚖ وزن‌دهی", expanded=False):
    st.caption("پس از هر تغییر، وزن‌ها خودکار بازنرمال می‌شوند تا مجموع ۱ بماند.")
    if st.button("بازگشت به وزن پیشنهادی", use_container_width=True):
        st.session_state.cluster_w = {k: c.weight for k, c in BASE_MODEL.clusters.items()}
        st.session_state.metric_w = {k: m.weight for k, m in BASE_MODEL.metrics.items()}
        st.rerun()
    st.markdown("**سطح ۱ — کلاسترها**")
    for k, c in BASE_MODEL.clusters.items():
        if not c.scored:
            continue
        st.session_state.cluster_w[k] = st.slider(
            c.label, 0.0, 1.0, float(st.session_state.cluster_w.get(k, c.weight)),
            0.01, key=f"cw_{k}")
    st.markdown("**سطح ۲ — آیتم‌ها داخل کلاستر**")
    for k, c in BASE_MODEL.clusters.items():
        if not c.scored:
            continue
        items = BASE_MODEL.cluster_metrics(k)
        if not items:
            continue
        with st.expander(c.label, expanded=False):
            for m in items:
                st.session_state.metric_w[m.key] = st.slider(
                    short(m.label, 34), 0.0, 1.0,
                    float(st.session_state.metric_w.get(m.key, m.weight)),
                    0.01, key=f"mw_{m.key}")


def current_model() -> PerformanceModel:
    clusters = {k: Cluster(c.key, c.label,
                           float(st.session_state.cluster_w.get(k, c.weight)),
                           c.scored, c.rationale, c.color)
                for k, c in BASE_MODEL.clusters.items()}
    metrics = {k: Metric(**{**m.__dict__,
                            "weight": float(st.session_state.metric_w.get(k, m.weight))})
               for k, m in BASE_MODEL.metrics.items()}
    return PerformanceModel(clusters, metrics, BASE_MODEL.model_version).renormalize()


MODEL = current_model()


@st.cache_data(show_spinner="در حال محاسبه امتیاز…")
def run_pipeline(ref_date: str, cw: tuple, mw: tuple, _people, _long):
    model = current_model()
    return Pipeline(model=model).run(long=_long, people=_people,
                                     ref_date=ref_date, persist=False)


RUN = run_pipeline(ref_date, tuple(sorted(st.session_state.cluster_w.items())),
                   tuple(sorted(st.session_state.metric_w.items())), people, long)
LB = RUN.leaderboard

# ── فیلترها ──
st.sidebar.markdown("#### فیلترها")
def msel(col, label):
    if col not in LB.columns:
        return []
    opts = sorted(x for x in LB[col].dropna().astype(str).unique() if x)
    return st.sidebar.multiselect(label, opts, default=opts)

f_mg = msel("مدیریت", "مدیریت")
f_dep = msel("اداره", "اداره")
f_jf = msel("نوع کار", "نوع کار")
f_role = msel("نقش", "نقش")

view = LB.copy()
for col, sel in (("مدیریت", f_mg), ("اداره", f_dep), ("نوع کار", f_jf), ("نقش", f_role)):
    if sel and col in view.columns:
        view = view[view[col].astype(str).isin(sel)]

st.sidebar.markdown("---")
st.sidebar.caption(f"**{len(LB):,}** نفر · **{len(view):,}** پس از فیلتر")


# ══════════════════════════════════════════════════════════════════════════
#  سربرگ
# ══════════════════════════════════════════════════════════════════════════
st.markdown(f"# عملکرد منابع انسانی")
st.caption(f"تاریخ مرجع {ref_date} · {len(view):,} نفر · مدل {MODEL.model_version} · "
           f"{len(MODEL.scored_metrics)} شاخص امتیازی در {len([c for c in MODEL.clusters.values() if c.scored])} کلاستر")

perf = pd.to_numeric(view.get("عملکرد"), errors="coerce")
counts = {}
for v in perf.dropna():
    counts[band_of(v)[2]] = counts.get(band_of(v)[2], 0) + 1

cards = [("میانه عملکرد", f"{perf.median():.1f}" if perf.notna().any() else "—",
          "نیمه بالا/پایین", SERIES[0], "◎"),
         ("میانگین اطمینان",
          f"{pd.to_numeric(view.get('اطمینان'), errors='coerce').mean():.2f}"
          if "اطمینان" in view else "—", "پوشش × شواهد", SERIES[2], "◈")]
for _f, color, icon, label in BANDS:
    cards.append((label, f"{counts.get(label, 0):,}", "نفر", color, icon))
st.markdown('<div class="kpi-row">' + "".join(kpi_card(*c) for c in cards[:8]) + "</div>",
            unsafe_allow_html=True)
st.markdown('<div style="margin:12px 0 2px">' +
            "".join(band_chip(c, i, l) for _f, c, i, l in BANDS) + "</div>",
            unsafe_allow_html=True)

for w in RUN.warnings:
    st.info(w)

(t_over, t_people, t_cluster, t_fair, t_graph, t_causal,
 t_model, t_studio, t_export, t_send) = st.tabs(
    ["نمای کلی", "افراد", "کلاسترها", "⚖️ عدالت و توازن بار", "🕸 گراف سازمانی",
     "🔬 تحلیل علّی", "⚙️ مدل و وزن", "🧬 استودیوی کلاستر", "📦 خروجی",
     "✉️ ارسال گزارش"])


# ══════════════════════════════════════════════════════════════════════════
#  عدالت — پیش از هر رتبه‌بندی
# ══════════════════════════════════════════════════════════════════════════
with t_fair:
    st.markdown("##### توزیع بار پیش از قضاوت عملکرد")
    st.caption("رتبه‌بندی افرادی که بارِ نابرابر دارند، بدون دیدن آن نابرابری، "
               "خودش یک اجحاف است. این تب پیش از هر امتیازی خوانده می‌شود.")
    if not RUN.skew:
        st.info("ستون بار کاری در این اجرا موجود نیست، پس توزیع بار سنجیده نشد.")
    else:
        cols = st.columns(min(len(RUN.skew), 4))
        for box, sk in zip(cols, RUN.skew[:4]):
            with box, st.container(border=True):
                st.markdown(f"**{sk.group}**")
                st.metric("ضریب جینی", "—" if sk.gini != sk.gini else f"{sk.gini:.2f}",
                          sk.band, delta_color="off")
                st.caption(f"{sk.n} نفر · نسبت ۹۰/۱۰: "
                           + ("—" if sk.p90_p10 != sk.p90_p10 else f"{sk.p90_p10:.1f}")
                           + (f" · سهم ۲۰٪ پرکار: {sk.top20:.0%}" if sk.top20 == sk.top20 else ""))
                st.caption(sk.note)

        if not RUN.load_flags.empty:
            from hrperf.fairness.skew import rebalance_hint
            hint = rebalance_hint(RUN.load_flags)
            if hint:
                st.markdown("##### پیشنهاد توازن")
                hc = st.columns(len(hint))
                for box, (k, v) in zip(hc, hint.items()):
                    box.metric(k, f"{v:,}")
                st.caption("«قابل جابه‌جایی» یعنی حداکثر باری که با انتقال از "
                           "بیش‌بارها به کم‌بارها، هر دو طرف را به میانه نزدیک می‌کند.")
            st.markdown("##### وضعیت بار هر فرد")
            st.dataframe(RUN.load_flags.join(
                RUN.leaderboard.set_index(RUN.leaderboard.index)[["نام"]]
                if "نام" in RUN.leaderboard.columns else RUN.load_flags[[]]),
                use_container_width=True, height=280)

    lp = (RUN.fairness or {}).get("load_penalty")
    if lp is not None:
        st.markdown("##### آیا خودِ امتیاز به پرکارها اجحاف می‌کند؟")
        c1, c2, c3 = st.columns(3)
        c1.metric("همبستگی امتیاز با بار",
                  "—" if lp.corr != lp.corr else f"{lp.corr:+.2f}")
        c2.metric("جابه‌جایی رتبه پس از حذف اثر بار", f"{lp.mean_rank_shift:.1%}")
        c3.metric("داوری", lp.verdict)
        st.caption("اگر همبستگی منفی و جابه‌جایی رتبه محسوس باشد، رتبه‌بندی فعلی "
                   "بیشتر «چقدر کار برداشته‌ای» را می‌سنجد تا «چقدر خوب کار کرده‌ای».")

    gaps = (RUN.fairness or {}).get("gaps") or {}
    for col, gl in gaps.items():
        shown = [g for g in gl if g.enough]
        if not shown:
            continue
        st.markdown(f"##### شکاف امتیاز بر حسب «{col}»")
        st.dataframe(pd.DataFrame([{
            "گروه": g.group, "نفرات": g.n, "میانگین": round(g.mean, 1),
            "بازه ۹۵٪": f"{g.lo:.1f} – {g.hi:.1f}",
            "میانگین بقیه": round(g.others_mean, 1),
            "نسبت": round(g.ratio, 2),
            "پس از حذف اثر بار": (round(g.adjusted_mean, 1)
                                  if g.adjusted_mean is not None else None),
            "داوری": g.verdict} for g in shown]),
            use_container_width=True, hide_index=True)
        st.caption("«نسبت» زیر ۰٫۸ طبق قاعده چهارپنجم (EEOC 1978) قابل بررسی است. "
                   "این شاهدِ تبعیض نیست؛ نشانه‌ای است که باید علتش را پرسید.")


# ══════════════════════════════════════════════════════════════════════════
#  گراف سازمانی
# ══════════════════════════════════════════════════════════════════════════
with t_graph:
    st.markdown("##### بار از مسیر چه کسی می‌گذرد")
    st.caption("جدول می‌گوید هرکس چند پرونده دارد؛ گراف می‌گوید کارِ چه کسی از "
               "مسیر چه کسی رد می‌شود. تفاوت این دو، همان‌جایی است که بار پنهان "
               "می‌ماند.")
    g = RUN.graph
    if g is None or g.n == 0:
        st.info("داده کافی برای ساخت گراف نیست.")
    else:
        from hrperf.graph.org import hidden_load
        c1, c2, c3 = st.columns(3)
        c1.metric("گره", f"{g.n:,}")
        c2.metric("یال", f"{len(g.edges):,}")
        c3.metric("مؤلفه مستقل", f"{len({v.component for v in g.nodes.values()}):,}")
        st.dataframe(g.table().head(40), use_container_width=True, hide_index=True)
        hid = hidden_load(g)
        if hid:
            st.markdown("##### بارِ پنهان")
            st.caption("این افراد بارِ ثبت‌شدهٔ کمی دارند ولی روی مسیر کار دیگران‌اند. "
                       "در ارزیابی معمول نامرئی می‌مانند و اگر نباشند، چند جریان می‌خوابد.")
            st.dataframe(pd.DataFrame([{
                "فرد": h.label, "بار ثبت‌شده": round(h.load, 1),
                "رتبه بار": h.load_rank, "مرکزیت": round(h.betweenness, 3),
                "رتبه مرکزیت": h.between_rank, "فاصله رتبه": h.gap}
                for h in hid[:20]]), use_container_width=True, hide_index=True)
        else:
            st.success("هیچ «بار پنهانی» شناسایی نشد — رتبهٔ بار و رتبهٔ مرکزیت هم‌خوان‌اند.")


# ══════════════════════════════════════════════════════════════════════════
with t_over:
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("##### توزیع عملکرد")
        st.caption("رده‌ها با رنگ و آیکن و برچسب — رنگ به‌تنهایی حامل معنا نیست.")
        if HAS_PLOTLY and perf.notna().any():
            order = [l for _f, _c, _i, l in BANDS]
            vals = [counts.get(l, 0) for l in order]
            cols_ = [c for _f, c, _i, _l in BANDS]
            icons = [i for _f, _c, i, _l in BANDS]
            fig = go.Figure(go.Bar(
                x=[f"{i} {l}" for i, l in zip(icons, order)], y=vals,
                marker_color=cols_, marker_line=dict(color="#fcfcfb", width=2),
                text=[f"{v:,}" for v in vals], textposition="outside",
                hovertemplate="%{x}<br>%{y:,} نفر<extra></extra>"))
            fig.update_layout(height=330, showlegend=False, yaxis_title="نفر",
                              xaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)

    with c2, st.container(border=True):
        st.markdown("##### میانه عملکرد به تفکیک اداره")
        if HAS_PLOTLY and "اداره" in view.columns and not view.empty:
            g = (view.groupby("اداره")["عملکرد"].median()
                 .sort_values(ascending=False).head(12))
            fig = go.Figure(go.Bar(
                x=g.values, y=[short(i, 28) for i in g.index], orientation="h",
                customdata=list(g.index),
                marker=dict(color=[band_of(v)[0] for v in g.values],
                            line=dict(color="#fcfcfb", width=2)),
                text=[f"{v:.1f}" for v in g.values], textposition="outside",
                hovertemplate="%{customdata}<br>میانه %{x:.1f}<extra></extra>"))
            fig.update_layout(height=330, showlegend=False, xaxis_title="میانه عملکرد",
                              xaxis=dict(range=[0, max(60.0, float(g.max()) * 1.25)]),
                              yaxis=dict(autorange="reversed", automargin=False),
                              margin=dict(t=16, r=24, b=44, l=200))
            st.plotly_chart(fig, use_container_width=True)

    with st.container(border=True):
        st.markdown("##### نقش‌های کاری")
        st.caption("«کارشناس» یک شغل نیست — هفت شغل است. هر نقش فقط با "
                   "هم‌نقش خودش سنجیده می‌شود و شاخصی که برای آن نقش "
                   "بی‌معناست اصلاً محاسبه نمی‌گردد.")
        if not RUN.role_coverage.empty:
            st.dataframe(RUN.role_coverage, use_container_width=True,
                         hide_index=True)

    with st.container(border=True):
        st.markdown("##### گروه‌های همتا")
        st.caption("مقایسه فقط درون گروه انجام می‌شود. «صعود» یعنی گروه از حد "
                   "نصاب کوچک‌تر بوده و ناچار در سطح بالاتری سنجیده شده است.")
        st.dataframe(RUN.peer_summary, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════
with t_people:
    st.markdown("##### جدول عملکرد")
    st.caption("رتبه فقط درون گروه همتا معنا دارد.")
    show = [c for c in ["کد پرسنلی", "نام", "مدیریت", "اداره", "نوع کار", "نقش",
                        "عملکرد", "امتیاز منصفانه", "رتبه در گروه", "نفرات گروه",
                        "پوشش", "شواهد", "اطمینان"] if c in view.columns]
    st.dataframe(
        view[show], use_container_width=True, height=440, hide_index=True,
        column_config={
            "عملکرد": st.column_config.ProgressColumn("عملکرد", format="%.1f",
                                                      min_value=0, max_value=100),
            "امتیاز منصفانه": st.column_config.ProgressColumn(
                "منصفانه", format="%.1f", min_value=0, max_value=100),
            "پوشش": st.column_config.ProgressColumn("پوشش", format="%.0f%%",
                                                    min_value=0, max_value=1),
            "اطمینان": st.column_config.ProgressColumn("اطمینان", format="%.0f%%",
                                                       min_value=0, max_value=1),
        })

    st.markdown("---")
    st.markdown("##### چرا این عدد؟ — سهم شاخص‌ها")
    if "کد" in view.columns and not view.empty:
        who = st.selectbox("فرد", view["کد"].tolist(),
                           format_func=lambda k: f"{k} — "
                           f"{view.loc[view['کد'] == k, 'نام'].iloc[0]}"
                           if "نام" in view.columns else k)
        contrib = contribution(RUN.metric_scores, MODEL, who)
        if contrib.empty:
            st.info("برای این فرد شاخص امتیازی موجود نیست.")
        else:
            if HAS_PLOTLY:
                cc = contrib.head(12).iloc[::-1]
                fig = go.Figure(go.Bar(
                    x=cc["سهم"], y=[short(x, 30) for x in cc["شاخص"]],
                    orientation="h", customdata=cc["شاخص"],
                    marker=dict(color=["#0ca30c" if v >= 0 else "#d03b3b"
                                       for v in cc["سهم"]],
                                line=dict(color="#fcfcfb", width=2)),
                    text=[f"{v:+.2f}" for v in cc["سهم"]], textposition="outside",
                    hovertemplate="%{customdata}<br>سهم %{x:+.2f}<extra></extra>"))
                fig.update_layout(height=max(300, 30 * len(cc) + 90), showlegend=False,
                                  xaxis_title="سهم در امتیاز (واحد امتیاز)",
                                  yaxis=dict(automargin=False),
                                  margin=dict(t=16, r=24, b=44, l=230))
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(contrib, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════
with t_cluster:
    st.markdown("##### امتیاز کلاسترها")
    cs = RUN.scores.cluster_scores.copy()
    cs.columns = [MODEL.clusters[c].label if c in MODEL.clusters else c
                  for c in cs.columns]
    keys = view["کد"] if "کد" in view.columns else cs.index
    cs = cs.loc[[i for i in cs.index if i in set(keys)]]
    st.dataframe(cs.round(1), use_container_width=True, height=380)

    if HAS_PLOTLY and not cs.empty:
        med = cs.median().sort_values(ascending=False)
        fig = go.Figure(go.Bar(
            x=med.values, y=[short(i, 26) for i in med.index], orientation="h",
            customdata=list(med.index),
            marker=dict(color=SEQUENTIAL[4], line=dict(color="#fcfcfb", width=2)),
            text=[f"{v:.1f}" for v in med.values], textposition="outside",
            hovertemplate="%{customdata}<br>میانه %{x:.1f}<extra></extra>"))
        fig.update_layout(height=330, showlegend=False, xaxis_title="میانه امتیاز کلاستر",
                          xaxis=dict(range=[0, max(60.0, float(med.max()) * 1.25)]),
                          yaxis=dict(autorange="reversed", automargin=False),
                          margin=dict(t=16, r=24, b=44, l=190))
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
with t_causal:
    st.markdown("##### همبستگی خام در برابر اثر تعدیل‌شده")
    st.caption("جایی که این دو فرق دارند، تصمیم بر پایه همبستگی خام غلط "
               "می‌شد. «تعدیل برای» می‌گوید چه مخدوش‌کننده‌هایی خنثی شده‌اند.")
    if RUN.effects.empty:
        st.info("برای برآورد اثر، نمونه کافی نیست.")
    else:
        st.dataframe(RUN.effects, use_container_width=True, hide_index=True)
        if HAS_PLOTLY:
            e = RUN.effects.dropna(subset=["همبستگی خام", "اثر تعدیل‌شده"]).copy()
            if not e.empty:
                lbl = (e["از"].astype(str) + " → " + e["به"].astype(str)).map(
                    lambda t: short(t, 34))
                fig = go.Figure()
                fig.add_bar(y=lbl, x=e["همبستگی خام"], orientation="h",
                            name="همبستگی خام", marker_color=SERIES[3],
                            marker_line=dict(color="#fcfcfb", width=2))
                fig.add_bar(y=lbl, x=e["اثر تعدیل‌شده"], orientation="h",
                            name="اثر تعدیل‌شده", marker_color=SERIES[0],
                            marker_line=dict(color="#fcfcfb", width=2))
                fig.update_layout(height=max(360, 42 * len(e) + 100), barmode="group",
                                  xaxis_title="اندازه اثر",
                                  yaxis=dict(autorange="reversed", automargin=False),
                                  margin=dict(t=40, r=24, b=44, l=250))
                st.plotly_chart(fig, use_container_width=True)
        st.caption("⚠️ با داده مشاهده‌ای نمی‌توان علیت را اثبات کرد. این اعداد "
                   "«اثر تعدیل‌شده تحت فرض‌های DAG اعلام‌شده» هستند. ستون "
                   "E-value می‌گوید یک مخدوش‌کننده اندازه‌گیری‌نشده چقدر باید "
                   "قوی باشد تا نتیجه را برگرداند.")

    st.markdown("---")
    st.markdown("##### امتیاز منصفانه — پس از حذف اثر شرایط کار")
    st.caption("عملکرد واقعی منهای آنچه از حجم، سختی و تخصیص کار انتظار می‌رفت.")
    fair = RUN.fair.copy()
    fair.index.name = "کد"
    fair = fair.reset_index().rename(columns={"expected": "انتظار",
                                              "residual": "تفاوت", "fair": "منصفانه"})
    st.dataframe(fair.round(2), use_container_width=True, height=320, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════
with t_model:
    st.markdown("##### وزن‌های مؤثر")
    st.caption("وزن مؤثر = وزن آیتم داخل کلاستر × وزن کلاستر. مجموع همیشه ۱۰۰٪.")
    rows = []
    for k, m in MODEL.metrics.items():
        rows.append({
            "شاخص": m.label,
            "کلاستر": MODEL.clusters[m.cluster].label if m.cluster in MODEL.clusters else m.cluster,
            "نقش": {"scored": "امتیازی", "context": "زمینه"}.get(m.role, m.role),
            "ورود": {"direct": "مستقیم", "derived": "محاسبه‌شده"}.get(m.entry, m.entry),
            "جهت": {"higher": "بیشتر بهتر", "lower": "کمتر بهتر"}.get(m.direction, m.direction),
            "وزن در کلاستر": round(m.weight, 4),
            "وزن مؤثر (٪)": round(MODEL.effective_weight(k) * 100, 2),
        })
    wdf = pd.DataFrame(rows).sort_values("وزن مؤثر (٪)", ascending=False)
    st.dataframe(wdf, use_container_width=True, hide_index=True, height=420,
                 column_config={"وزن مؤثر (٪)": st.column_config.ProgressColumn(
                     "وزن مؤثر", format="%.2f%%", min_value=0, max_value=25)})
    st.metric("مجموع وزن مؤثر", f"{wdf['وزن مؤثر (٪)'].sum():.2f}%")

    # ── افزودن کلاستر و شاخص تازه ──
    st.markdown("---")
    st.markdown("##### کلاستر تازه")
    st.caption("مدل عملکرد یک قرارداد سازمانی است، نه ثابت مهندسی. اگر تغییرش "
               "نیازمند ویرایش فایل باشد، در عمل هرگز تغییر نمی‌کند.")
    from hrperf.config import editor as _ed
    with st.form("new_cluster"):
        f1, f2, f3 = st.columns([1, 1.4, 1])
        ck = f1.text_input("کلید انگلیسی", placeholder="compliance")
        cl = f2.text_input("عنوان فارسی", placeholder="انطباق و رعایت رویه")
        cw = f3.number_input("وزن", 0.0, 1.0, 0.10, 0.01)
        cr = st.text_area("دلیل این وزن (اجباری)",
                          placeholder="چرا این کلاستر این‌قدر مهم است؟ "
                                      "وزنی که دلیلش نوشته نشده، فردا قابل دفاع نیست.")
        if st.form_submit_button("افزودن کلاستر"):
            try:
                nm = _ed.add_cluster(MODEL, ck.strip(), cl.strip(), float(cw), cr.strip())
                path, backup = _ed.save(nm)
                st.success(f"کلاستر افزوده و ذخیره شد → {path.name} "
                           f"(پشتیبان نسخه قبل: {backup.name})")
                st.cache_data.clear()
                st.rerun()
            except _ed.EditError as ex:
                st.error(str(ex))

    st.markdown("##### شاخص تازه در یک کلاستر موجود")
    with st.form("new_metric"):
        g1, g2, g3 = st.columns([1, 1.4, 1])
        mk = g1.text_input("کلید شاخص", placeholder="procedure_errors")
        ml = g2.text_input("عنوان فارسی", placeholder="خطای رویه‌ای")
        mc = g3.selectbox("کلاستر", list(MODEL.clusters),
                          format_func=lambda k: MODEL.clusters[k].label)
        h1, h2, h3 = st.columns(3)
        mw = h1.number_input("وزن در کلاستر", 0.0, 1.0, 0.20, 0.05)
        md = h2.selectbox("جهت", _ed.DIRECTIONS,
                          format_func=lambda d: "بیشتر بهتر" if d == "higher" else "کمتر بهتر")
        mkind = h3.selectbox("نوع", _ed.KINDS)
        if st.form_submit_button("افزودن شاخص"):
            try:
                nm = _ed.add_metric(MODEL, mk.strip(), ml.strip(), mc, float(mw),
                                    direction=md, kind=mkind)
                path, backup = _ed.save(nm)
                st.success(f"شاخص افزوده شد → {path.name} (پشتیبان: {backup.name})")
                st.cache_data.clear()
                st.rerun()
            except _ed.EditError as ex:
                st.error(str(ex))

    hist = _ed.history()
    if hist:
        with st.expander(f"تاریخچه نسخه‌های مدل ({len(hist)} نسخه)"):
            st.dataframe(pd.DataFrame(hist, columns=["فایل", "زمان"]),
                         use_container_width=True, hide_index=True)
            st.caption("هر ذخیره، نسخه قبلی را کنار می‌گذارد. مقایسه دو دوره با "
                       "دو مدل متفاوت، مقایسه نیست — و باید بشود فهمید کدام عدد "
                       "با کدام مدل ساخته شده.")

    st.markdown("---")
    st.markdown("##### کالیبراسیون انقباض")
    st.caption("k از خود داده برآورد می‌شود. k بزرگ یعنی بیشترِ پراکندگی "
               "دیده‌شده نویزِ نمونه است نه تفاوت واقعی، پس انقباض شدیدتر است.")
    st.dataframe(RUN.calibration, use_container_width=True, hide_index=True)



# ══════════════════════════════════════════════════════════════════════════
#  استودیوی کلاستر — فضای برداری، پیشنهاد موتور، جابه‌جایی، رنگ، سورس تازه
# ══════════════════════════════════════════════════════════════════════════
with t_studio:
    from hrperf.config import editor as _ed
    from hrperf.dataio import registry as _reg
    from hrperf.model_engine import vectors as _ve
    from hrperf.report import fluid as _fluid

    st.markdown("##### کلاسترها در فضای برداری")
    st.caption("هر شاخص یک بردار است: ستون امتیازهایش روی همه افراد. شباهت دو "
               "شاخص یعنی همبستگی بردارهایشان. اینجا سنجیده می‌شود که آیا "
               "عضویت‌هایی که ما تعیین کرده‌ایم، با رفتار داده می‌خواند یا نه.")

    _member = {k: m.cluster for k, m in MODEL.metrics.items() if m.scored}
    _sc = RUN.metric_scores[[c for c in RUN.metric_scores.columns if c in _member]]
    _vec = _ve.vectors(_sc, MODEL)
    _sim = _ve.similarity(_vec) if not _vec.empty else pd.DataFrame()

    if _sim.empty:
        st.warning("برای فضای برداری، دست‌کم دو شاخص با داده کافی لازم است.")
    else:
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("**انسجام هر کلاستر**")
            st.dataframe(pd.DataFrame([
                {"کلاستر": MODEL.clusters[c.cluster].label, "اعضا": c.n,
                 "همبستگی درونی": None if not np.isfinite(c.mean_within) else round(c.mean_within, 2),
                 "با بیرون": None if not np.isfinite(c.mean_between) else round(c.mean_between, 2),
                 "داوری": c.verdict}
                for c in _ve.cohesion(_sim, _member)]),
                use_container_width=True, hide_index=True)
        with c2:
            st.markdown("**جای هر شاخص**")
            st.dataframe(pd.DataFrame([
                {"شاخص": MODEL.metrics[f.metric].label,
                 "کلاستر فعلی": MODEL.clusters[f.cluster].label if f.cluster in MODEL.clusters else f.cluster,
                 "شباهت به خودی": None if not np.isfinite(f.own) else round(f.own, 2),
                 "نزدیک‌ترین دیگر": MODEL.clusters[f.best_other].label if f.best_other in MODEL.clusters else "—",
                 "شباهت": None if not np.isfinite(f.best_other_sim) else round(f.best_other_sim, 2),
                 "داوری": f.verdict}
                for f in _ve.fit_table(_vec, _member)]),
                use_container_width=True, hide_index=True, height=300)

    # ── پیشنهاد موتور ──
    st.markdown("---")
    st.markdown("##### پیشنهاد موتور کلاستر")
    st.caption("موتور کلاستر را کشف نمی‌کند؛ کلاستر یک قرارداد سازمانی است. "
               "فقط می‌گوید داده با این قرارداد کجا نمی‌خواند — و دلیلش را "
               "می‌گوید. اعمال هر پیشنهاد با شماست.")
    _sugs = _ve.suggest(RUN.metric_scores, MODEL) if not _sim.empty else []
    if not _sugs:
        st.success("موتور پیشنهادی ندارد — مدل با دادهٔ این اجرا می‌خواند.")
    for i, sg in enumerate(_sugs):
        with st.container(border=True):
            a, b = st.columns([4, 1])
            name = MODEL.metrics[sg.metric].label if sg.metric in MODEL.metrics else sg.detail
            a.markdown(f"**{sg.title} — {name}**")
            if sg.metric:
                a.caption(sg.detail)
            a.write(sg.reason)
            if sg.kind == "move" and sg.to_cluster:
                if b.button("اعمال", key=f"apply_{i}", use_container_width=True):
                    try:
                        nm = _ed.move_metric(MODEL, sg.metric, sg.to_cluster)
                        for d in _ed.diff(MODEL, nm):
                            st.write("• " + d)
                        path, backup = _ed.save(nm)
                        st.success(f"اعمال و ذخیره شد → {path.name} (پشتیبان: {backup.name})")
                        st.session_state.metric_w = {}
                        st.cache_data.clear()
                        st.rerun()
                    except _ed.EditError as ex:
                        st.error(str(ex))

    # ── جابه‌جایی دستی و رنگ ──
    st.markdown("---")
    st.markdown("##### جابه‌جایی شاخص و رنگ کلاستر")
    m1, m2 = st.columns([1.2, 1])
    with m1:
        with st.form("move_metric"):
            mv = st.selectbox("شاخص", list(MODEL.metrics),
                              format_func=lambda k: MODEL.metrics[k].label)
            to = st.selectbox("به کلاستر", list(MODEL.clusters),
                              format_func=lambda k: MODEL.clusters[k].label)
            if st.form_submit_button("جابه‌جا کن"):
                try:
                    nm = _ed.move_metric(MODEL, mv, to)
                    for d in _ed.diff(MODEL, nm):
                        st.write("• " + d)
                    path, backup = _ed.save(nm)
                    st.success(f"ذخیره شد → {path.name} (پشتیبان: {backup.name})")
                    st.session_state.metric_w = {}
                    st.cache_data.clear()
                    st.rerun()
                except _ed.EditError as ex:
                    st.error(str(ex))
    with m2:
        st.caption("رنگ کلاستر در همهٔ خروجی‌ها یکی است. اگر بین دو گزارش عوض "
                   "شود، خواننده فکر می‌کند چیز دیگری را نگاه می‌کند.")
        _pal = _fluid.CATEGORICAL_LIGHT
        with st.form("colors"):
            _picked = {}
            for i, (k, c) in enumerate(MODEL.clusters.items()):
                _picked[k] = st.color_picker(
                    c.label, c.color or _pal[i % len(_pal)], key=f"col_{k}")
            if st.form_submit_button("ذخیره رنگ‌ها"):
                try:
                    nm = MODEL
                    for k, v in _picked.items():
                        nm = _ed.set_color(nm, k, v)
                    path, backup = _ed.save(nm, new_version=False)
                    st.success(f"رنگ‌ها ذخیره شد → {path.name}")
                    st.cache_data.clear()
                    st.rerun()
                except _ed.EditError as ex:
                    st.error(str(ex))

    # ── نقشهٔ سیال ──
    st.markdown("---")
    st.markdown("##### نقشهٔ سیال — دانلود و پیش‌نمایش")
    _payload = _fluid.build_payload(RUN.metric_scores, MODEL, RUN.people)
    _html = _fluid.render(_payload)
    st.download_button("⬇️ دانلود نقشهٔ سیال (HTML مستقل)", _html.encode("utf-8"),
                       file_name=f"HR_Cluster_Space_{ref_date}.html",
                       mime="text/html", use_container_width=True)
    with st.expander("پیش‌نمایش در همین صفحه", expanded=False):
        st.components.v1.html(_html, height=620, scrolling=False)

    # ── سورس تازه ──
    st.markdown("---")
    st.markdown("##### سورس تازه — بدون تغییر کد")
    st.caption("یک ورودی در sources.yaml کافی است. نگاشت به شاخصی که در مدل "
               "نیست پذیرفته نمی‌شود؛ وگرنه ستونی خوانده می‌شد که هیچ‌جا "
               "امتیاز نمی‌گیرد و کسی نمی‌فهمید چرا.")
    _specs = _reg.load()
    if _specs:
        st.dataframe(pd.DataFrame([
            {"کلید": k, "عنوان": v.label, "الگوی فایل": v.match,
             "ستون کلید فرد": v.person_key, "شاخص‌ها": len(v.metrics)}
            for k, v in _specs.items()]), use_container_width=True, hide_index=True)
    with st.form("new_source"):
        s1, s2, s3 = st.columns([1, 1.3, 1])
        sk = s1.text_input("کلید سورس", placeholder="bazresi")
        sl = s2.text_input("عنوان", placeholder="خروجی واحد بازرسی")
        sm = s3.text_input("الگوی نام فایل", value="*")
        spk = st.text_input("ستون کلید فرد در فایل", value="کد پرسنلی")
        st.caption("نگاشت ستون‌ها — هر خط:  نام ستون | کلید شاخص | ستون نمونه (اختیاری)")
        smap = st.text_area("نگاشت", height=110,
                            placeholder="نرخ تطابق | conformance_score | تعداد پرونده")
        if st.form_submit_button("افزودن سورس"):
            try:
                mm = []
                for line in smap.splitlines():
                    parts = [x.strip() for x in line.split("|") if x.strip()]
                    if len(parts) >= 2:
                        mm.append(_reg.MetricMap(parts[0], parts[1],
                                                 parts[2] if len(parts) > 2 else ""))
                if not sk.strip() or not mm:
                    raise _reg.RegistryError("کلید سورس و دست‌کم یک نگاشت لازم است.")
                new = dict(_specs)
                new[sk.strip()] = _reg.SourceSpec(
                    key=sk.strip(), label=sl.strip() or sk.strip(),
                    match=sm.strip() or "*", person_key=spk.strip(), metrics=mm)
                bad = _reg.validate(new, MODEL)
                if bad:
                    raise _reg.RegistryError("\n".join(bad))
                path = _reg.save(new)
                st.success(f"سورس ثبت شد → {path}. فایل‌های منطبق در اجرای بعدی "
                           f"خوانده می‌شوند.")
                st.cache_data.clear()
            except Exception as ex:
                st.error(str(ex))


# ══════════════════════════════════════════════════════════════════════════
with t_export:
    # ── خروجی HTML داینامیک و متحرک ──
    st.markdown("##### خروجی داینامیک و متحرک")
    st.caption("یک فایل HTML مستقل: فیلتر زنده، نمودار قابل انتخاب، و منحنی "
               "لورنتس عدالت. بدون وابستگی به اینترنت — روی شبکه داخلی هم کامل "
               "باز می‌شود.")
    from hrperf.report.dynamic import build_dynamic_html as _dyn

    _board = RUN.leaderboard.copy()
    if not RUN.load_flags.empty and "بار" in RUN.load_flags.columns:
        _board["بار کاری"] = RUN.load_flags["بار"].reindex(_board.index)
    _dims = [c for c in ("مدیریت", "اداره", "نوع کار", "گروه همتا")
             if c in _board.columns]
    _pick = st.multiselect("ابعاد قابل فیلتر در خروجی", _dims, default=_dims[:3])
    _html = _dyn(_board, ref_date, score_col="عملکرد", name_col="نام",
                 load_col="بار کاری" if "بار کاری" in _board.columns else "",
                 dims=_pick or _dims,
                 title="عملکرد منابع انسانی")
    e1, e2 = st.columns([1, 3])
    e1.download_button("⬇️ دانلود HTML داینامیک", _html.encode("utf-8"),
                       file_name=f"HRPerf_Dynamic_{ref_date}.html",
                       mime="text/html", key="dl_dyn")
    if e2.toggle("پیش‌نمایش زنده", value=False, key="prev_dyn"):
        components.html(_html, height=680, scrolling=True)

    st.markdown("---")
    st.markdown("##### ساخت گزارش")
    c1, c2, c3 = st.columns(3)
    with c1:
        pick = st.radio("قالب", list(tpl.TEMPLATES),
                        format_func=lambda k: f"{tpl.get(k).icon} {tpl.get(k).title}")
        st.caption(tpl.get(pick).description)
    with c2:
        st.markdown("**فرمت**")
        f_x = st.checkbox("Excel", True)
        f_h = st.checkbox("HTML داینامیک", True)
        f_p = st.checkbox("PDF", True)
        f_e = st.checkbox("بسته ایمیل", True)
    with c3:
        st.markdown("**محتوا**")
        vis = st.checkbox("نمودار/ویژوال", True)
        tab = st.checkbox("جدول‌ها", True)
        stem = st.text_input("نام فایل", f"HR {tpl.get(pick).title}")

    fmts = ([("excel")] if f_x else []) + (["html"] if f_h else []) \
        + (["pdf"] if f_p else []) + (["email"] if f_e else [])

    if st.button("🛠 ساخت گزارش", type="primary", use_container_width=True,
                 disabled=not fmts):
        out_dir = Path(SETTINGS.OUTPUT_DIR) / ref_date / "reports"
        spec = ReportSpec(template=pick, ref_date=ref_date,
                          title=f"عملکرد منابع انسانی — {tpl.get(pick).title}",
                          formats=fmts, visuals=vis, tables=tab,
                          file_stem=stem.strip() or "HR Performance")
        with st.spinner("در حال ساخت…"):
            filtered = RUN
            res = build_report(filtered, spec, out_dir)
        st.session_state.rep_files = {k: str(v) for k, v in res.files.items()}
        st.session_state.rep_msgs = res.messages
        st.rerun()

    files = st.session_state.get("rep_files") or {}
    for m in (st.session_state.get("rep_msgs") or []):
        (st.warning if str(m).startswith("⚠️") else st.write)(m)
    if files:
        mimes = {"excel": ("⬇ Excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                 "html": ("⬇ HTML", "text/html"), "pdf": ("⬇ PDF", "application/pdf"),
                 "email": ("⬇ بسته ایمیل", "text/html")}
        cols_ = st.columns(len(files))
        for i, (kind, path) in enumerate(files.items()):
            p = Path(path)
            if not p.exists():
                continue
            lab, mime = mimes.get(kind, (kind, "application/octet-stream"))
            cols_[i].download_button(lab, p.read_bytes(), file_name=p.name,
                                     mime=mime, use_container_width=True,
                                     key=f"dl_{kind}")

    st.markdown("---")
    st.markdown("##### پایگاه داده")
    st.caption("هر اجرا یک `run` ثبت می‌شود، پس روند زمانی بدون بازنویسی "
               "داده قبلی قابل پیگیری است.")
    if st.button("ثبت این اجرا در پایگاه داده", use_container_width=True):
        try:
            rid = Pipeline(model=MODEL)._persist(RUN, ref_date)
            st.success(f"ثبت شد — run_id = {rid} · {SETTINGS.DB_PATH}")
        except Exception as ex:
            st.error(f"ثبت ناموفق بود: {ex}")

st.caption("رتبه‌ها فقط درون گروه همتا (مدیریت + اداره + نوع کار) معنا دارند.")


# ══════════════════════════════════════════════════════════════════════════
#  ارسال گزارش در لحظه — پیوست دلخواه، گیرندهٔ دلخواه
# ══════════════════════════════════════════════════════════════════════════
with t_send:
    import tempfile as _tf
    from hrperf.report import dispatch as _dp
    from hrperf.report import fluid as _fl
    from hrperf.report.builder import ReportSpec as _Spec
    from hrperf.report.builder import build as _build

    st.markdown("##### ۱) کدام گزارش‌ها پیوست شوند؟")
    st.caption("هر مورد در لحظه ساخته می‌شود — نه از اجرای قبلی.")
    picks = {}
    cols = st.columns(4)
    for i, (key, (label, ext, why)) in enumerate(_dp.ARTIFACTS.items()):
        if key == "pdf":
            continue
        with cols[i % 4]:
            picks[key] = st.checkbox(label, value=key in ("excel", "dynamic"),
                                     key=f"pick_{key}", help=why)

    st.markdown("##### ۲) گیرندگان")
    people_dir = _dp.directory(RUN.people)
    if not people_dir:
        st.warning("در جدول پرسنلی این اجرا، ستون ایمیل با نشانی معتبر نبود. "
                   "برای انتخاب گیرنده، ستون `email` را به نقشه سازمانی اضافه "
                   "کنید — یا فهرست را از `HRP_EMAIL_TO` بدهید.")
        st.caption("نشانی‌ها هیچ‌جا لاگ یا ذخیره نمی‌شوند؛ فقط تعدادشان گزارش می‌شود.")
    else:
        by_label = {p.label: p for p in people_dir}
        c1, c2 = st.columns(2)
        to_sel = c1.multiselect("گیرندگان (To)", list(by_label),
                                help="نام و اداره نمایش داده می‌شود، نه نشانی")
        cc_sel = c2.multiselect("رونوشت (Cc)", list(by_label))
        chosen_to = [by_label[x] for x in to_sel]
        chosen_cc = [by_label[x] for x in cc_sel if x not in to_sel]
        if chosen_to or chosen_cc:
            st.caption("نشانی‌های نقاب‌دار برای تأیید: "
                       + "، ".join(p.masked for p in chosen_to + chosen_cc))

    st.markdown("##### ۳) متن ایمیل")
    subj = st.text_input("موضوع",
                         value=f"عملکرد منابع انسانی — {ref_date}")
    note = st.text_area(
        "یادداشت پایانی",
        value="رتبه‌ها فقط درون گروه همتا معنا دارند. جزئیات هر امتیاز در "
              "فایل‌های پیوست است.", height=70)

    with st.expander("چرا متن ایمیل داینامیک نیست؟", expanded=False):
        st.markdown(
            "**هیچ کلاینت ایمیلی جاوااسکریپت را اجرا نمی‌کند** — نه اتلوک "
            "کلاسیک، نه اتلوک جدید، نه وب‌میل. این تصمیم امنیتی است: ایمیل از "
            "فرستندهٔ ناشناس می‌آید و اجرای کد او روی دستگاه گیرنده خودش یک "
            "آسیب‌پذیری است. پس نمودار زنده، فیلتر و مرتب‌سازی در بدنهٔ ایمیل "
            "ممکن نیست.\n\n"
            "**اتلوک کلاسیک** بدنه را با موتور Word رندر می‌کند: بدون flexbox، "
            "بدون grid، بدون `background-image`. پشتیبانی مایکروسافت از آن "
            "مهر ۱۴۰۵ (اکتبر ۲۰۲۶) تمام می‌شود. **اتلوک جدید** موتور Chromium "
            "دارد و CSS مدرن را می‌فهمد، ولی باز هم جاوااسکریپت نه.\n\n"
            "**راه‌حل ما:** بدنهٔ ایمیل جدول‌محور و امن روی هر دو موتور — با "
            "کاشی KPI، ردیف‌های صدر جدول و تراشهٔ وضعیت؛ به‌علاوهٔ یک بلوک "
            "`@media` که فقط اتلوک جدید می‌بیند (حالت تاریک و چیدمان موبایل). "
            "گزارش داینامیک **پیوست** می‌شود و در مرورگر کاملاً زنده است.")

    st.markdown("##### ۴) ساخت و ارسال")
    b1, b2 = st.columns([1, 1])
    make = b1.button("🛠 ساخت پیش‌نمایش و پیوست‌ها", use_container_width=True)
    if make:
        out = Path(_tf.mkdtemp(prefix="hrp_send_"))
        files, names = [], []
        want = [k for k, v in picks.items() if v]
        if "excel" in want or "html" in want:
            fmts = [f for f in ("excel", "html") if f in want]
            res = _build(RUN, _Spec(template="executive", ref_date=ref_date,
                                    title=f"عملکرد منابع انسانی — {ref_date}",
                                    formats=fmts, file_stem="HR_گزارش"), out)
            for f in fmts:
                if res.files.get(f):
                    files.append(Path(res.files[f]))
        if "dynamic" in want:
            lb = LB.copy()
            if "case_load" in RUN.metric_raw.columns:
                lb["بار کاری"] = RUN.metric_raw["case_load"].reindex(
                    lb[lb.columns[0]]).to_numpy()
            from hrperf.report.dynamic import write_dynamic as _wd
            files.append(Path(_wd(lb, out / "HR_داشبورد_داینامیک.html",
                                  ref_date=ref_date)))
        if "fluid" in want:
            files.append(_fl.write(
                _fl.build_payload(RUN.metric_scores, MODEL, RUN.people),
                out / "HR_نقشه_سیال.html"))
        names = [f.name for f in files]

        bands = {k: 0 for _f, _c, _i, l in BANDS for k in [l]}
        for v in RUN.scores.performance.dropna():
            _c, _i, lab = band_of(v)
            bands[lab] = bands.get(lab, 0) + 1
        from hrperf.report import aqua as _aq
        kpis = [("نفرات", f"{len(RUN.people):,}", _aq.LIGHT["text"]),
                ("میانه عملکرد",
                 f"{float(RUN.scores.performance.median()):.1f}",
                 _aq.LIGHT["brand-strong"])]
        for lab, cnt in list(bands.items())[:2]:
            col, _i, _l = band_of(80 if "برجسته" in lab else 30)
            kpis.append((lab, f"{cnt:,}", col))

        top = LB.head(6)
        code_col = "کد پرسنلی" if "کد پرسنلی" in top.columns else top.columns[0]
        rows = []
        for _, r in top.iterrows():
            col, icon, lab = band_of(r.get("عملکرد"))
            rows.append([str(r.get(code_col, "")), str(r.get("نام", "")),
                         str(r.get("اداره", "")),
                         f"{float(r.get('عملکرد', 0)):.1f}",
                         _dp._chip(lab, col, icon)])
        body = _dp.outlook_body(
            subj, ref_date, kpis=kpis,
            headers=["کد پرسنلی", "نام", "اداره", "عملکرد", "وضعیت"],
            rows=rows, note=note, attachments=names)

        st.session_state.mail_body = body
        st.session_state.mail_files = [str(f) for f in files]
        st.success(f"{len(files)} پیوست ساخته شد.")

    if st.session_state.get("mail_body"):
        st.markdown("**پیش‌نمایش بدنهٔ ایمیل** — همان چیزی که در اتلوک دیده می‌شود")
        st.components.v1.html(st.session_state.mail_body, height=520, scrolling=True)
        files = [Path(f) for f in st.session_state.get("mail_files", [])]
        for f in files:
            if f.exists():
                st.download_button(f"⬇️ {f.name}", f.read_bytes(),
                                   file_name=f.name, key=f"dl_{f.name}")
        if people_dir and to_sel:
            s1, s2 = st.columns(2)
            if s1.button("📨 باز کردن در اتلوک (بدون ارسال)",
                         use_container_width=True):
                try:
                    r = _dp.send(subj, st.session_state.mail_body,
                                 _dp.addresses(chosen_to),
                                 _dp.addresses(chosen_cc), files, send_now=False)
                    st.success(r.summary)
                except Exception as ex:
                    st.error(str(ex))
            if s2.button("🚀 ارسال همین حالا", type="primary",
                         use_container_width=True):
                try:
                    r = _dp.send(subj, st.session_state.mail_body,
                                 _dp.addresses(chosen_to),
                                 _dp.addresses(chosen_cc), files, send_now=True)
                    st.success(r.summary)
                except Exception as ex:
                    st.error(str(ex))
            st.download_button(
                "⬇️ دریافت پروندهٔ .eml (روی سیستم بدون اتلوک)",
                _dp.eml(subj, st.session_state.mail_body,
                        _dp.addresses(chosen_to), _dp.addresses(chosen_cc), files),
                file_name=f"HR_{ref_date}.eml", mime="message/rfc822",
                use_container_width=True)
            st.caption("ارسال، عملی برگشت‌ناپذیر است — پیش‌فرض «باز کردن در "
                       "اتلوک» است تا پیش از فرستادن ببینید.")
