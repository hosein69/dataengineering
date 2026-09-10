# -*- coding: utf-8 -*-
"""تب فرآیند — روی لاگ رویدادی که خط لوله از قبل می‌ساخت.

مرحله `s80_eventlog` و `s85_conformance` شش جدول تولید می‌کنند
(لاگ رویداد، جدول پرونده، گلوگاه، واریانت، انطباق، ریشه‌یابی) ولی رابط
قبلی فقط `bottlenecks.head(12)` را نشان می‌داد. اینجا هر شش‌تا به یک
نمای فرآیندی تبدیل می‌شوند: جریان مراحل، گلوگاه گذارها، کاوشگر واریانت،
توزیع طول چرخه، انطباق و ریشه‌یابی، و خط زمان یک پرونده.

قواعد بصری: برچسب بلند فارسی کوتاه می‌شود ولی نام کامل در هاور می‌ماند؛
رنگ وضعیت همیشه با آیکن و برچسب می‌آید؛ محور تکی، بدون دو مقیاس.
"""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd
import streamlit as st

from .theme import BANDS, SEQUENTIAL, SERIES, STATUS, band_of, finalize

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

#: ترتیب معنادار مراحل چرخه عمر (از ثبت تا رفع تعهد)
STAGE_ORDER = ["PR", "PO", "ORDER_REG", "ALLOCATION", "FX_SUPPLY", "SHIPMENT",
               "DOCS", "CUSTOMS", "RELEASE", "SETTLEMENT"]
STAGE_FA = {
    "PR": "درخواست خرید", "PO": "سفارش خرید", "ORDER_REG": "ثبت سفارش",
    "ALLOCATION": "تخصیص ارز", "FX_SUPPLY": "تأمین ارز", "SHIPMENT": "حمل",
    "DOCS": "اسناد", "CUSTOMS": "گمرک", "RELEASE": "ترخیص",
    "SETTLEMENT": "رفع تعهد",
}


def short(t, n: int = 34) -> str:
    t = str(t)
    return t if len(t) <= n else t[:n - 1] + "…"


def _empty(msg: str) -> None:
    st.info(msg)


def _bar(y_labels, x_vals, full_labels, x_title, colors=None, hover_extra=""):
    """میله افقی با برچسب کوتاه روی محور و نام کامل در هاور."""
    fig = go.Figure(go.Bar(
        x=x_vals, y=y_labels, orientation="h",
        customdata=full_labels,
        marker=dict(color=colors if colors is not None else SEQUENTIAL[4],
                    line=dict(color="#fcfcfb", width=2)),
        text=[f"{v:,.1f}" if isinstance(v, float) else f"{v:,}" for v in x_vals],
        textposition="outside",
        hovertemplate="%{customdata}<br>" + x_title + " %{x:,.1f}" + hover_extra + "<extra></extra>"))
    # ⚠️ automargin پلاتلی برای برچسب بلند فارسی کفایت نمی‌کند و نام را به
    # دو-سه حرف می‌بُرد. پس ناودان برچسب صریح رزرو می‌شود (نمودار تمام‌عرض).
    fig.update_layout(
        height=max(260, 34 * len(x_vals) + 90), showlegend=False,
        xaxis_title=x_title, yaxis_title=None,
        yaxis=dict(autorange="reversed", tickfont=dict(size=11), automargin=False),
        margin=dict(t=16, r=24, b=44, l=330))
    return fig


def render(extras: Dict, fdf: pd.DataFrame) -> None:
    ev: Optional[pd.DataFrame] = extras.get("eventlog")
    cases: Optional[pd.DataFrame] = extras.get("case_table")
    bott: Optional[pd.DataFrame] = extras.get("bottlenecks")
    variants: Optional[pd.DataFrame] = extras.get("variants")
    conf: Optional[pd.DataFrame] = extras.get("conformance_cases")
    roots: Optional[pd.DataFrame] = extras.get("conformance_root_causes")

    if ev is None or ev.empty:
        _empty("لاگ رویداد برای این اجرا ساخته نشده است. "
               "مرحله `s80_eventlog` به تاریخ‌های چرخه نیاز دارد.")
        return

    # ── خلاصه فرآیند ──
    n_cases = int(ev["_CASE_KEY"].nunique()) if "_CASE_KEY" in ev else 0
    n_acts = int(ev["ACTIVITY_FA"].nunique()) if "ACTIVITY_FA" in ev else 0
    n_var = int(len(variants)) if variants is not None else 0
    thr = pd.to_numeric(cases["THROUGHPUT_DAYS"], errors="coerce") \
        if cases is not None and "THROUGHPUT_DAYS" in cases else pd.Series(dtype=float)
    rework = int(pd.to_numeric(cases.get("REWORK_COUNT"), errors="coerce").fillna(0).sum()) \
        if cases is not None and "REWORK_COUNT" in cases else 0

    k = st.columns(5)
    k[0].metric("پرونده", f"{n_cases:,}")
    k[1].metric("رویداد", f"{len(ev):,}")
    k[2].metric("فعالیت متمایز", f"{n_acts:,}")
    k[3].metric("مسیر متمایز", f"{n_var:,}")
    k[4].metric("میانه طول چرخه",
                f"{thr.median():,.0f} روز" if not thr.empty and thr.notna().any() else "—")

    st.markdown("---")

    # ── ۱) گلوگاه گذارها (تمام‌عرض — نام گذار طولانی است) ──
    with st.container(border=True):
        st.markdown("##### ⛓ گلوگاه گذارها")
        st.caption("میانگین روزهای انتظار بین دو فعالیت پیاپی. "
                   "بلندترین میله، کندترین گذار فرآیند است.")
        if bott is not None and not bott.empty and HAS_PLOTLY:
            b = bott.copy().head(12)
            full = (b["از فعالیت"].astype(str) + " ← " + b["به فعالیت"].astype(str))
            lbl = full.map(lambda t: short(t, 34))
            avg = pd.to_numeric(b["میانگین روز"], errors="coerce").fillna(0)
            fig = _bar(lbl, avg, full, "میانگین روز",
                       colors=avg, hover_extra=" روز")
            fig.update_traces(marker=dict(
                color=avg, colorscale=[[0, SEQUENTIAL[1]], [1, SEQUENTIAL[6]]],
                line=dict(color="#fcfcfb", width=2), showscale=False))
            st.plotly_chart(finalize(fig), use_container_width=True, theme=None)
            with st.expander("جدول گلوگاه‌ها"):
                st.dataframe(bott, use_container_width=True, hide_index=True)
        else:
            _empty("گذار قابل اندازه‌گیری‌ای ثبت نشده است.")

    # ── ۲) توزیع طول چرخه ──
    with st.container(border=True):
        st.markdown("##### ⏱ توزیع طول چرخه")
        st.caption("طول چرخه هر پرونده از اولین تا آخرین رویداد. "
                   "دُم راست، پرونده‌های گیرکرده‌اند.")
        if not thr.empty and thr.notna().any() and HAS_PLOTLY:
            v = thr.dropna()
            fig = go.Figure(go.Histogram(
                x=v, nbinsx=min(24, max(5, int(len(v) ** 0.5) * 3)),
                marker=dict(color=SEQUENTIAL[3],
                            line=dict(color="#fcfcfb", width=2)),
                hovertemplate="%{x} روز<br>%{y} پرونده<extra></extra>"))
            med = float(v.median())
            fig.add_vline(x=med, line_width=2, line_dash="dash",
                          line_color=STATUS["critical"],
                          annotation_text=f"میانه {med:,.0f} روز",
                          annotation_position="top")
            fig.update_layout(height=320, showlegend=False, bargap=0.06,
                              xaxis_title="طول چرخه (روز)", yaxis_title="تعداد پرونده",
                              margin=dict(t=30, r=24, b=44, l=24))
            st.plotly_chart(finalize(fig), use_container_width=True, theme=None)
            q = v.quantile([.5, .75, .9, 1.0])
            st.caption(f"میانه {q[.5]:,.0f} · صدک۷۵ {q[.75]:,.0f} · "
                       f"صدک۹۰ {q[.9]:,.0f} · بیشینه {q[1.0]:,.0f} روز"
                       + (f" · {rework:,} بازکاری" if rework else ""))
        else:
            _empty("طول چرخه محاسبه نشده است.")

    # ── ۳) کاوشگر واریانت ──
    with st.container(border=True):
        st.markdown("##### 🗺 کاوشگر مسیر (واریانت)")
        st.caption("هر مسیر یک ترتیب متمایز از فعالیت‌هاست. "
                   "مسیر پرتکرار، فرآیند واقعی سازمان است — نه آنچه روی کاغذ است.")
        if variants is not None and not variants.empty:
            v = variants.copy()
            share = pd.to_numeric(v.get("سهم (٪)"), errors="coerce").fillna(0)
            v_show = v.assign(**{"سهم (٪)": share})
            st.dataframe(
                v_show, use_container_width=True, hide_index=True, height=260,
                column_config={
                    "VARIANT": st.column_config.TextColumn("مسیر", width="large"),
                    "تعداد پرونده": st.column_config.NumberColumn("پرونده", width="small"),
                    "میانگین throughput": st.column_config.NumberColumn(
                        "میانگین طول چرخه (روز)", format="%.0f"),
                    "سهم (٪)": st.column_config.ProgressColumn(
                        "سهم", format="%.0f%%", min_value=0, max_value=100),
                })
        else:
            _empty("واریانتی استخراج نشد.")

    # ── ۴) انطباق و ریشه‌یابی ──
    c3, c4 = st.columns([1, 1])
    with c3, st.container(border=True):
        st.markdown("##### 🔍 انطباق فرآیند")
        st.caption("امتیاز ۱۰۰ یعنی پرونده دقیقاً مسیر مرجع را رفته است.")
        if conf is not None and not conf.empty:
            sc = pd.to_numeric(conf.get("score"), errors="coerce")
            dev = int((conf.get("deviation", pd.Series(dtype=str))
                       .astype(str) != "بدون انحراف").sum())
            m = st.columns(3)
            m[0].metric("میانگین انطباق",
                        f"{sc.mean():,.0f}%" if sc.notna().any() else "—")
            m[1].metric("پرونده دارای انحراف", f"{dev:,}")
            m[2].metric("پرونده منطبق", f"{len(conf) - dev:,}")
            st.dataframe(conf, use_container_width=True, hide_index=True, height=220)
        else:
            _empty("بررسی انطباق انجام نشده است.")

    with c4, st.container(border=True):
        st.markdown("##### 🧭 ریشه‌یابی انحراف")
        st.caption("«اثر تفاضلی» = نرخ انحراف این گروه منهای نرخ پایه. "
                   "عدد مثبت بزرگ یعنی این بُعد واقعاً محرک انحراف است.")
        if roots is not None and not roots.empty:
            r = roots.copy()
            eff_col = "اثر تفاضلی (واحد درصد)"
            if eff_col in r.columns:
                r = r.sort_values(eff_col, ascending=False)
            st.dataframe(
                r, use_container_width=True, hide_index=True, height=300,
                column_config={
                    "بُعد": st.column_config.TextColumn("بُعد", width="small"),
                    "مقدار": st.column_config.TextColumn("مقدار", width="medium"),
                })
        else:
            _empty("ریشه‌یابی در دسترس نیست.")

    # ── ۵) خط زمان یک پرونده ──
    with st.container(border=True):
        st.markdown("##### 📌 خط زمان پرونده")
        st.caption("یک پرونده را انتخاب کنید تا ترتیب واقعی رویدادهایش دیده شود.")
        keys = sorted(ev["_CASE_KEY"].astype(str).unique().tolist())
        if not keys:
            _empty("پرونده‌ای در لاگ نیست.")
            return
        pick = st.selectbox("پرونده", keys, key="proc_case")
        sub = ev[ev["_CASE_KEY"].astype(str) == str(pick)].copy()
        if "EVENTTIME" in sub:
            sub["EVENTTIME"] = pd.to_datetime(sub["EVENTTIME"], errors="coerce")
        sort_col = "_SORTING" if "_SORTING" in sub else "EVENTTIME"
        sub = sub.sort_values(["EVENTTIME", sort_col], na_position="last")

        if HAS_PLOTLY and "EVENTTIME" in sub and sub["EVENTTIME"].notna().any():
            band = band_of(str(sub["CRITICALITY"].iloc[0])) if "CRITICALITY" in sub else band_of("")
            fig = go.Figure(go.Scatter(
                x=sub["EVENTTIME"], y=sub["ACTIVITY_FA"].astype(str),
                mode="lines+markers",
                line=dict(color=SERIES[0], width=2),
                marker=dict(size=12, color=band[0], line=dict(color="#fcfcfb", width=2)),
                customdata=sub.get("LIFECYCLE_STAGE", pd.Series([""] * len(sub))).astype(str),
                hovertemplate="%{y}<br>%{x|%Y-%m-%d}<br>مرحله: %{customdata}<extra></extra>"))
            fig.update_layout(height=max(260, 44 * len(sub) + 80), showlegend=False,
                              xaxis_title="زمان", yaxis_title=None,
                              yaxis=dict(autorange="reversed"),
                              margin=dict(t=16, r=24, b=44, l=24))
            st.plotly_chart(finalize(fig), use_container_width=True, theme=None)
            st.markdown(
                f'<span class="band" style="background:{band[0]}1a;color:{band[0]};'
                f'border-color:{band[0]}44"><span class="g" style="background:{band[0]}">'
                f'</span>{band[1]} {band[2]}</span>', unsafe_allow_html=True)

        cols = [c for c in ["ACTIVITY_FA", "EVENTTIME", "LIFECYCLE_STAGE", "RESOURCE",
                            "ORG_UNIT", "BL_NO", "PART_NO", "CASE_VALUE", "CURRENCY"]
                if c in sub.columns]
        st.dataframe(sub[cols], use_container_width=True, hide_index=True)

    # ── خروجی لاگ رویداد ──
    st.download_button(
        "⬇ دانلود لاگ رویداد (CSV — سازگار با Celonis/Disco)",
        ev.to_csv(index=False).encode("utf-8-sig"),
        file_name="AIBL_EventLog.csv", mime="text/csv")
