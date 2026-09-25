# -*- coding: utf-8 -*-
"""نمایش سامانهٔ طراحی — نمونهٔ اجرایی «پلتفرم هوش فرآیندی» (RTL/فارسی).

اجرا:  ``streamlit run app.py``

این فایل خودِ محصول نیست؛ نشان می‌دهد چطور از ``pm_ui`` برای ساختن یک
صفحهٔ کامل — چیدمان قابل‌تنظیم، KPI، نقشهٔ جریان فرآیند، کانبان، نمودار
شدت، و خروجی HTML/اکسل — استفاده کنید. تیم محصول این فایل را الگو
می‌گیرد و روی دادهٔ واقعی خودش سوار می‌کند.
"""
from __future__ import annotations

import streamlit as st

from pm_ui import mock_data, persian as fa, theme, tokens as T
from pm_ui import blocks as _register_blocks  # noqa: F401 — ثبت رندرکننده‌های بلوک
from pm_ui.export import build_excel_report, build_report_html
from pm_ui.layout import AUDIENCE_LABELS, AUDIENCES, DEFAULT_LAYOUT, move_block, render_layout

# ── ۱) پیکربندی اولیهٔ صفحه (Wide) و تزریق CSS سراسری ──────────────────────
theme.page_config(title="پلتفرم هوش فرآیندی — GSI UI Kit", icon="🧭")
theme.apply(font_source=theme.FontSource.SYSTEM_ONLY)  # فایل فونت را در static/fonts بگذارید و به LOCAL_STATIC تغییر دهید

if "layout" not in st.session_state:
    st.session_state.layout = [dict(b) for b in DEFAULT_LAYOUT]
if "audience" not in st.session_state:
    st.session_state.audience = "manager"

# ── ۲) دادهٔ آزمایشی — در استقرار واقعی با آداپتور دادهٔ سازمانی جایگزین شود ──
DATA = {
    "kpis": mock_data.kpi_cards(),
    "insights": mock_data.insight_cards(),
    "graph": mock_data.process_graph(),
    "evidence": mock_data.evidence_table(),
    "kanban": mock_data.kanban_columns(),
    "system": mock_data.system_stages(),
    "intensity": mock_data.intensity_series(),
    "heatmap": mock_data.heatmap_matrix(),
}

# ── ۳) نوار کناری — انتخاب مخاطب، شخصی‌سازی چیدمان، خروجی ───────────────────
with st.sidebar:
    st.markdown("### 🧭 پلتفرم هوش فرآیندی")
    st.caption(f"به‌روزرسانی: {fa.today_jalali_str()}")
    st.divider()

    st.markdown("**سطح مخاطب**")
    st.session_state.audience = st.radio(
        "سطح مخاطب", AUDIENCES, index=AUDIENCES.index(st.session_state.audience),
        format_func=lambda a: AUDIENCE_LABELS[a], label_visibility="collapsed")
    st.caption("هر سطح فقط بلوک‌های مرتبط با خودش را می‌بیند — "
              "بدون تغییر کد، فقط با ``visible_for`` در پیکربندی چیدمان.")

    st.divider()
    st.markdown("**ترتیب بلوک‌ها** (جابه‌جایی چه نوع، چه جایگاه)")
    ordered = sorted(st.session_state.layout, key=lambda b: b.get("order", 0))
    for b in ordered:
        c1, c2, c3 = st.columns([5, 1, 1])
        c1.caption(b.get("title") or b.get("type"))
        if c2.button("▲", key=f"up_{b['id']}", help="جابه‌جایی به بالا"):
            st.session_state.layout = move_block(st.session_state.layout, b["id"], delta=-1)
            st.rerun()
        if c3.button("▼", key=f"dn_{b['id']}", help="جابه‌جایی به پایین"):
            st.session_state.layout = move_block(st.session_state.layout, b["id"], delta=1)
            st.rerun()

    st.divider()
    st.markdown("**خروجی سبک برای ارسال**")
    st.caption("HTML/اکسل جدا از Streamlit ساخته می‌شوند — سبک و امن برای اوتلوک آفلاین.")
    html_bytes = build_report_html(
        title="گزارش پلتفرم هوش فرآیندی", subtitle=AUDIENCE_LABELS[st.session_state.audience],
        kpis=DATA["kpis"], nodes=DATA["graph"]["nodes"], edges=DATA["graph"]["edges"],
        kanban=DATA["kanban"]).encode("utf-8")
    st.download_button("⬇ دانلود HTML ایمیل", data=html_bytes,
                       file_name="گزارش_فرآیند.html", mime="text/html",
                       use_container_width=True)
    st.caption(f"حجم فایل: {len(html_bytes) / 1024:,.0f} کیلوبایت")

    xlsx_bytes = build_excel_report(kpis=DATA["kpis"], nodes=DATA["graph"]["nodes"],
                                    edges=DATA["graph"]["edges"])
    st.download_button("⬇ دانلود اکسل", data=xlsx_bytes, file_name="گزارش_فرآیند.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)

# ── ۴) سربرگ ────────────────────────────────────────────────────────────────
st.markdown(
    f"""<div style="background:linear-gradient(120deg,{T.BRAND_NAVY},{T.BRAND_TEAL});color:#fff;
    border-radius:{T.RADIUS['xl']}px;padding:22px 26px;margin-bottom:18px">
      <div style="font-size:22px;font-weight:800">اتاق کنترل فرآیندهای سازمانی</div>
      <div style="font-size:13px;color:rgba(255,255,255,.82);margin-top:6px">
        نمای {AUDIENCE_LABELS[st.session_state.audience]} — {fa.today_jalali_str()}
      </div>
    </div>""", unsafe_allow_html=True)

# ── ۵) چیدمان اصلی — از روی پیکربندی، نه کد ثابت ────────────────────────────
render_layout(st.session_state.layout, DATA, audience=st.session_state.audience)

st.divider()
st.caption(
    "این صفحه نمونهٔ اجرایی سامانهٔ طراحی داخلی است (پوشهٔ ``pm_ui``). "
    "خروجی HTML/اکسل کنار دکمه‌ها، همان چیزی است که کاربر نهایی واقعاً می‌بیند؛ "
    "Streamlit فقط موتور ساخت و پیش‌نمایش است.")
