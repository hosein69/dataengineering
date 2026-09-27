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
from gsi.studio_core.runtime_data import bottleneck_view

from typing import Dict, Optional
import html

import pandas as pd
import streamlit as st

from .theme import (SURFACE, BANDS, BRAND_TEAL, SEQUENTIAL, SERIES, STATUS,
                    STATUS_INK, STATUS_WASH, TEXT, band_of)

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

#: ترتیب معنادار مراحل چرخه عمر (از ثبت تا رفع تعهد)
STAGE_ORDER = ["PR", "PO", "ORDER_REG", "ALLOCATION_QUEUE", "ALLOCATION", "FX_SUPPLY", "SHIPMENT",
               "DOCS", "CUSTOMS", "RELEASE", "SETTLEMENT"]
STAGE_FA = {
    "PR": "درخواست خرید", "PO": "سفارش خرید", "ORDER_REG": "ثبت سفارش",
    "ALLOCATION_QUEUE": "صف تخصیص", "ALLOCATION": "تخصیص ارز", "FX_SUPPLY": "تأمین ارز", "SHIPMENT": "حمل",
    "DOCS": "اسناد", "CUSTOMS": "گمرک", "RELEASE": "ترخیص",
    "SETTLEMENT": "رفع تعهد",
}


def short(t, n: int = 34) -> str:
    t = str(t)
    return t if len(t) <= n else t[:n - 1] + "…"


def _empty(msg: str) -> None:
    st.info(msg)


def _money_gauge(title: str, value: float, suffix: str = "", risk: bool = False):
    if not HAS_PLOTLY:
        st.metric(title, f"{value:,.0f}{suffix}")
        return
    # زمینه گیج از wash وضعیت‌ها می‌آید — همان رنگی که کاربر در نشان، در
    # جدول و در ایمیل هم می‌بیند. یعنی «ناحیه قرمز گیج» و «سلول بحرانی»
    # یک رنگ‌اند و مغز لازم نیست دو نگاشت جدا یاد بگیرد.
    if risk:   # زیاد = بد
        steps = [
            {"range": [0, 35], "color": STATUS_WASH["good"]},
            {"range": [35, 60], "color": STATUS_WASH["warning"]},
            {"range": [60, 80], "color": STATUS_WASH["serious"]},
            {"range": [80, 100], "color": STATUS_WASH["critical"]},
        ]
    else:      # زیاد = خوب
        steps = [{"range": [0, 50], "color": STATUS_WASH["critical"]},
                 {"range": [50, 80], "color": STATUS_WASH["warning"]},
                 {"range": [80, 100], "color": STATUS_WASH["good"]}]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=max(0, min(100, float(value or 0))),
        number={"suffix": suffix}, title={"text": title, "font": {"size": 15}},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": BRAND_TEAL},
               "steps": steps, "threshold": {"line": {"color": TEXT, "width": 2},
               "thickness": 0.75, "value": max(0, min(100, float(value or 0)))}}))
    fig.update_layout(height=220, margin=dict(l=18, r=18, t=55, b=10))
    st.plotly_chart(fig, use_container_width=True)


def _render_money_flow_control(extras: Dict) -> None:
    summary = extras.get("fx_control_summary")
    timeline = extras.get("fx_stage_timeline")
    ledger = extras.get("fx_ledger")
    realloc = extras.get("fx_reallocations")
    bridge = extras.get("fx_rate_bridge")
    legacy_signals = extras.get("legacy_case_signals")
    legacy_catalog = extras.get("legacy_knowledge_catalog")
    case_actions = extras.get("case_actions")
    if summary is None or summary.empty:
        return

    with st.container(border=True):
        st.markdown("#### 💸 Money Flow Control Tower")
        st.caption("پرونده‌محور: نرخ و تبدیل ارز، انتقال بین REG/Order/BL، مراحل واقعی، Evidence و زمان باقی‌مانده. Signal کنترلی به‌تنهایی حکم تقلب نیست.")

        srt = summary.sort_values(["FX_CONTROL_RISK_SCORE", "FX_UNAUTHORIZED_REALLOCATION_COUNT"], ascending=False)
        keys = srt["KEY_REG"].astype(str).tolist()
        pick = st.selectbox("ثبت سفارش برای مشاهده جریان پول", keys, key="money_control_reg")
        row = srt[srt["KEY_REG"].astype(str) == str(pick)].iloc[0]
        lrow = None
        if ledger is not None and not ledger.empty:
            z = ledger[ledger["KEY_REG"].astype(str) == str(pick)]
            if not z.empty:
                lrow = z.iloc[0]

        c = st.columns(6)
        c[0].metric("مرحله جاری", str(row.get("FX_CURRENT_STAGE") or "—"))
        c[1].metric("روز تا نزدیک‌ترین مهلت",
                    f"{int(row.get('FX_DAYS_REMAINING', 0)):+d}" if str(row.get("FX_DEADLINE_DATE") or "") else "—")
        c[2].metric("خرید ارز", f"{float(lrow.get('FX_PURCHASED_AMOUNT', 0) if lrow is not None else 0):,.2f}")
        c[3].metric("خروج ریالی ثبت‌شده", f"{float(lrow.get('FX_RIAL_OUTFLOW_REPORTED', 0) if lrow is not None else 0):,.0f}")
        c[4].metric("اثر ریالی تبدیل", f"{float(row.get('FX_CONVERSION_IMPACT_RIAL', 0) or 0):,.0f}")
        c[5].metric("جابجایی بدون شاهد مجوز", f"{int(row.get('FX_UNAUTHORIZED_REALLOCATION_COUNT', 0) or 0):,}")
        if str(row.get("FX_DEADLINE_DATE") or ""):
            st.caption(f"نزدیک‌ترین مهلت: **{row.get('FX_DEADLINE_DATE')}** · مبنا: {row.get('FX_DEADLINE_BASIS') or '—'}")

        g1, g2, g3 = st.columns(3)
        with g1:
            _money_gauge("ریسک کنترل پول", float(row.get("FX_CONTROL_RISK_SCORE", 0) or 0), "%", risk=True)
        with g2:
            _money_gauge("پیشرفت مراحل", float(row.get("FX_STAGE_PROGRESS_PCT", 0) or 0), "%")
        with g3:
            _money_gauge("پوشش شواهد", float(lrow.get("FX_TRACE_SCORE", 0) if lrow is not None else 0), "%")

        if timeline is not None and not timeline.empty:
            t = timeline[timeline["KEY_REG"].astype(str) == str(pick)].sort_values("STAGE_ORDER")
            # هفت حالت گام، اما فقط پنج معنا: انجام‌شده، در جریان، ناقص،
            # هشدار، و گذشته از مهلت. هر کدام به ink وضعیت متناظر نگاشت
            # می‌شود تا با بقیه گزارش یک زبان داشته باشد؛ آیکن هم در کنارش
            # می‌آید، چون رنگ تنها حامل معنا نیست.
            color = {"DONE": STATUS_INK["good"], "CURRENT": BRAND_TEAL,
                     "PARTIAL": SERIES[2], "WARNING": STATUS_INK["warning"],
                     "OVERDUE": STATUS_INK["critical"],
                     "EVIDENCE_GAP": SERIES[4], "PENDING": STATUS_INK["neutral"]}
            icon = {"DONE": "✓", "CURRENT": "●", "PARTIAL": "◐", "WARNING": "!", "OVERDUE": "×",
                    "EVIDENCE_GAP": "?", "PENDING": "○"}
            cards = []
            for _, x in t.iterrows():
                stt = str(x.get("STATUS") or "PENDING")
                ev = str(x.get("EVENT_DATE") or "")
                due = str(x.get("DUE_DATE") or "")
                days = x.get("DAYS_REMAINING")
                dtext = ""
                if due:
                    try:
                        dtext = f"مهلت {due} · {int(days):+d} روز"
                    except Exception:
                        dtext = f"مهلت {due}"
                sub = " · ".join(v for v in [ev, dtext, str(x.get("EVIDENCE") or "")] if v)
                cards.append(
                    '<div style="min-width:145px;flex:1;background:#fff;border:1px solid {c}55;'
                    'border-top:4px solid {c};border-radius:12px;padding:10px 9px;text-align:center">'
                    '<div style="font-size:20px;color:{c};font-weight:800">{i}</div>'
                    '<div style="font-weight:800;font-size:13px">{title}</div>'
                    '<div style="font-size:10px;color:#667;margin-top:5px;line-height:1.6">{sub}</div>'
                    '<div style="font-size:9px;color:{c};margin-top:4px">{status}</div></div>'.format(
                        c=color.get(stt, '#777'), i=icon.get(stt, '○'),
                        title=html.escape(str(x.get('STAGE_FA') or '')),
                        sub=html.escape(sub), status=html.escape(stt)))
            st.markdown('<div style="display:flex;gap:7px;overflow-x:auto;padding:5px 1px 12px">' + ''.join(cards) + '</div>', unsafe_allow_html=True)
            with st.expander("جزئیات مراحل و مبنای Deadline"):
                st.dataframe(t.drop(columns=["FX_CASE_KEY"], errors="ignore"), use_container_width=True, hide_index=True)

        # ── Case Action Queue: پیشنهاد سیستم + Draft Email با تأیید انسانی ──
        st.markdown("##### 🎯 پیشنهاد اقدام پرونده")
        st.caption("پیشنهادها از داده و Rule Basis ساخته می‌شوند؛ ارسال ایمیل خودکار نیست. کاربر Draft را بازبینی و سپس در Outlook ارسال می‌کند.")
        if case_actions is not None and not case_actions.empty:
            az = case_actions[case_actions["KEY_REG"].astype(str) == str(pick)].copy()
            if not az.empty:
                prio_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
                az["_rank"] = az["PRIORITY"].map(prio_order).fillna(0)
                az = az.sort_values(["_rank", "DAYS_REMAINING"], ascending=[False, True], na_position="last")
                options = az["ACTION_ID"].astype(str).tolist()
                labels = {str(r["ACTION_ID"]): f"{r['PRIORITY']} · {r['TITLE']}" for _, r in az.iterrows()}
                action_id = st.selectbox("اقدام پیشنهادی", options, format_func=lambda x: labels.get(str(x), str(x)), key=f"gsi_action_{pick}")
                act = az[az["ACTION_ID"].astype(str) == str(action_id)].iloc[0]
                ac = st.columns(4)
                ac[0].metric("اولویت", str(act.get("PRIORITY") or "—"))
                ac[1].metric("مالک پیشنهادی", str(act.get("OWNER_ROLE") or "—"))
                ac[2].metric("موعد داخلی", str(act.get("DUE_DATE") or "—"))
                days = act.get("DAYS_REMAINING")
                ac[3].metric("روز تا اقدام", "—" if pd.isna(days) else f"{int(days):+d}")
                st.write(str(act.get("RATIONALE") or ""))
                if str(act.get("EVIDENCE_GAPS") or ""):
                    st.warning("شواهد ناقص: " + str(act.get("EVIDENCE_GAPS")))
                st.caption("مبنای پیشنهاد: " + str(act.get("RULE_BASIS") or "—"))
                with st.expander("همه پیشنهادهای این پرونده"):
                    show = [c for c in ["ACTION_ID", "PRIORITY", "TITLE", "OWNER_ROLE", "DUE_DATE", "DAYS_REMAINING", "EVIDENCE_GAPS", "RULE_BASIS", "STATUS"] if c in az.columns]
                    st.dataframe(az[show], use_container_width=True, hide_index=True)
                recipients = st.text_input("گیرنده ایمیل (یک یا چند نشانی با ; جدا شود)", key=f"gsi_action_to_{pick}", placeholder="case-owner@example.com")
                if st.button("✉️ باز کردن پیش‌نویس ایمیل در Outlook", key=f"gsi_action_mail_{pick}", type="primary"):
                    try:
                        from gsi.integrations.daily_email import create_case_action_email
                        create_case_action_email(act.to_dict(), to=recipients, send=False, display=True)
                        st.success("پیش‌نویس Outlook ساخته شد؛ قبل از ارسال متن و گیرندگان را بازبینی کنید.")
                    except Exception as ex:
                        st.error(f"ساخت Draft Outlook انجام نشد: {ex}")
            else:
                st.success("برای این پرونده در حال حاضر اقدام پیشنهادی باز تولید نشده است.")
        else:
            st.info("Case Action Queue در این اجرا ساخته نشده است.")

        r1, r2 = st.columns(2)
        with r1:
            st.markdown("##### 🔁 جابه‌جایی بین پرونده‌ها")
            if realloc is not None and not realloc.empty:
                rz = realloc[(realloc["FROM_REG"].astype(str) == str(pick)) | (realloc["TO_REG"].astype(str) == str(pick))]
                if not rz.empty:
                    st.dataframe(rz, use_container_width=True, hide_index=True, height=220)
                else:
                    st.success("برای این پرونده سیگنال جابه‌جایی بین‌پرونده‌ای ثبت نشده است.")
            else:
                st.success("سیگنال جابه‌جایی بین‌پرونده‌ای ثبت نشده است.")
        with r2:
            st.markdown("##### 💱 پل نرخ و تبدیل ارز")
            if bridge is not None and not bridge.empty:
                bz = bridge[bridge["KEY_REG"].astype(str) == str(pick)]
                if not bz.empty:
                    show = [c for c in ["PURCHASE_DATE", "PURCHASE_AMOUNT", "PURCHASE_CURRENCY", "PURCHASE_RATE_RIAL",
                            "PAID_AMOUNT", "PAID_CURRENCY", "PAID_RATE_RIAL", "CONVERSION_RATE_TARGET_PER_SOURCE",
                            "CONVERSION_FEE_RIAL", "IMPACT_RIAL", "STATUS"] if c in bz.columns]
                    st.dataframe(bz[show], use_container_width=True, hide_index=True, height=220)
                else:
                    st.info("تراکنش ارزی قابل نمایش برای این پرونده وجود ندارد.")
            else:
                st.info("داده پل نرخ/تبدیل موجود نیست.")

        st.markdown("##### 🧠 انتقال دانش تاریخی — Root Cause و Evidence")
        st.caption("این بخش فقط راهنمای بررسی است. دانش Legacy به‌صورت fail-closed نگه داشته می‌شود و بدون سند رسمی جاری، مهلت/جریمه/حکم حقوقی ایجاد نمی‌کند.")
        if legacy_signals is not None and not legacy_signals.empty:
            kz = legacy_signals[legacy_signals["KEY_REG"].astype(str) == str(pick)]
            if not kz.empty:
                show = [c for c in ["SIGNAL_CODE", "SIGNAL_TYPE", "TITLE", "BASIS",
                                     "CONFIDENCE", "SOURCE_ID", "SOURCE_LOCATION",
                                     "EVIDENCE_REQUIREMENTS"] if c in kz.columns]
                st.dataframe(kz[show], use_container_width=True, hide_index=True, height=260)
            else:
                st.success("برای این پرونده Root-cause candidate تاریخی قابل استناد به داده موجود پیدا نشد.")
        else:
            st.info("Signal انتقال دانش برای این اجرا ساخته نشده است.")
        if lrow is not None:
            gaps = str(lrow.get("FX_RATE_SEMANTIC_GAPS") or "")
            evreq = str(lrow.get("FX_EVIDENCE_REQUIREMENTS") or "")
            if gaps:
                st.warning("شکاف معنایی نرخ/تبدیل: " + gaps)
            if evreq:
                with st.expander("شواهد پیشنهادی برای بستن Investigation Gap"):
                    st.write(evreq)
        if legacy_catalog is not None and not legacy_catalog.empty:
            with st.expander("کاتالوگ دانش منتقل‌شده و Provenance"):
                cols = [c for c in ["KNOWLEDGE_ID", "KIND", "TITLE", "SOURCE_ID",
                                     "SOURCE_DATE", "SOURCE_LOCATION", "BINDING",
                                     "AUTO_ENFORCE", "CONFIDENCE"] if c in legacy_catalog.columns]
                st.dataframe(legacy_catalog[cols], use_container_width=True, hide_index=True, height=320)

def _bar(y_labels, x_vals, full_labels, x_title, colors=None, hover_extra=""):
    """میله افقی با برچسب کوتاه روی محور و نام کامل در هاور."""
    fig = go.Figure(go.Bar(
        x=x_vals, y=y_labels, orientation="h",
        customdata=full_labels,
        marker=dict(color=colors if colors is not None else SEQUENTIAL[4],
                    line=dict(color=SURFACE, width=2)),
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

    # V26.18: Control Tower مستقل از لاگ فرآیندی عمومی است.
    _render_money_flow_control(extras)

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
        st.caption("مدت بین دو فعالیت پیاپی، با شاخص اعلام‌شده روی نمودار. "
                   "بلندترین میله، کندترین گذار فرآیند است.")
        b, metric = bottleneck_view(bott)
        if not b.empty and HAS_PLOTLY:
            full = (b["از فعالیت"].astype(str) + " ← " + b["به فعالیت"].astype(str))
            lbl = full.map(lambda t: short(t, 34))
            avg = b[metric]
            fig = _bar(lbl, avg, full, metric,
                       colors=avg, hover_extra=" روز")
            fig.update_traces(marker=dict(
                color=avg, colorscale=[[0, SEQUENTIAL[1]], [1, SEQUENTIAL[-1]]],
                line=dict(color=SURFACE, width=2), showscale=False))
            st.plotly_chart(fig, use_container_width=True)
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
                            line=dict(color=SURFACE, width=2)),
                hovertemplate="%{x} روز<br>%{y} پرونده<extra></extra>"))
            med = float(v.median())
            fig.add_vline(x=med, line_width=2, line_dash="dash",
                          line_color=STATUS["critical"],
                          annotation_text=f"میانه {med:,.0f} روز",
                          annotation_position="top")
            fig.update_layout(height=320, showlegend=False, bargap=0.06,
                              xaxis_title="طول چرخه (روز)", yaxis_title="تعداد پرونده",
                              margin=dict(t=30, r=24, b=44, l=24))
            st.plotly_chart(fig, use_container_width=True)
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
                marker=dict(size=12, color=band[0], line=dict(color=SURFACE, width=2)),
                customdata=sub.get("LIFECYCLE_STAGE", pd.Series([""] * len(sub))).astype(str),
                hovertemplate="%{y}<br>%{x|%Y-%m-%d}<br>مرحله: %{customdata}<extra></extra>"))
            fig.update_layout(height=max(260, 44 * len(sub) + 80), showlegend=False,
                              xaxis_title="زمان", yaxis_title=None,
                              yaxis=dict(autorange="reversed"),
                              margin=dict(t=16, r=24, b=44, l=24))
            st.plotly_chart(fig, use_container_width=True)
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
        file_name="GSI_EventLog.csv", mime="text/csv")
