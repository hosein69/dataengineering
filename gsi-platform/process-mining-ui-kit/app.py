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
from pm_ui.export import build_excel_report, build_report_html, build_standalone_html
from pm_ui.layout import AUDIENCE_LABELS, AUDIENCES, DEFAULT_LAYOUT, move_block, render_layout

# ── ۱) پیکربندی اولیهٔ صفحه (Wide) و تزریق CSS سراسری ──────────────────────
theme.page_config(title="پلتفرم هوش فرآیندی — GSI UI Kit", icon="🧭")
theme.apply(font_source=theme.FontSource.SYSTEM_ONLY)  # IRANSansWeb در صورت نصب سازمانی؛ هیچ فایل فونت باینری در بسته توزیع نمی‌شود

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
        st.caption(b.get("title") or b.get("type"))
        # عمداً از دو ستون تقریباً هم‌عرض استفاده شده، نه یک ستون باریک ۱/۷ی
        # کنار برچسب: در Streamlit 1.64 دکمه‌ای که در ستون خیلی باریک بیفتد
        # (کمتر از ~۶۰px) متنش کاملاً نامرئی می‌شود — باگی از خودِ ویجت، نه
        # از CSS این پروژه؛ با پهن‌تر کردن ستون دکمه، بدون نیاز به دور زدن
        # نسخه، دور زده می‌شود.
        c1, c2 = st.columns(2)
        if c1.button("▲ بالا", key=f"up_{b['id']}", help="جابه‌جایی به بالا",
                    use_container_width=True):
            st.session_state.layout = move_block(st.session_state.layout, b["id"], delta=-1)
            st.rerun()
        if c2.button("▼ پایین", key=f"dn_{b['id']}", help="جابه‌جایی به پایین",
                    use_container_width=True):
            st.session_state.layout = move_block(st.session_state.layout, b["id"], delta=1)
            st.rerun()

    st.divider()
    st.markdown("**خروجی سبک برای ارسال**")
    st.caption("HTML/اکسل جدا از Streamlit ساخته می‌شوند — سبک و امن برای اوتلوک آفلاین.")
    # عنوان گزارش — عمداً یک متغیر واحد، نه رشتهٔ جداگانه در هر خروجی:
    # Streamlit عنوان خودش را دارد (نام ابزار برای تیم محصول)؛ HTML عنوان
    # گزارش را دارد (چیزی که واقعاً دست مخاطب می‌رود) — این دو نباید به‌طور
    # مستقل و ناهماهنگ از هم ساخته شوند. TODO: این عنوان را با نام واقعی
    # گزارش سازمانی خودتان جایگزین کنید.
    REPORT_TITLE = "گزارش پلتفرم هوش فرآیندی"

    html_bytes = build_report_html(
        title=REPORT_TITLE, subtitle=AUDIENCE_LABELS[st.session_state.audience],
        kpis=DATA["kpis"], nodes=DATA["graph"]["nodes"], edges=DATA["graph"]["edges"],
        kanban=DATA["kanban"]).encode("utf-8")
    st.download_button("⬇ دانلود HTML ایمیل", data=html_bytes,
                       file_name="گزارش_فرآیند.html", mime="text/html",
                       use_container_width=True)
    st.caption(f"حجم فایل: {len(html_bytes) / 1024:,.0f} کیلوبایت")

    standalone_bytes = build_standalone_html(
        title=REPORT_TITLE, subtitle=AUDIENCE_LABELS[st.session_state.audience],
        audience_label="", data=DATA).encode("utf-8")
    st.download_button("⬇ دانلود HTML مستقل (کامل)", data=standalone_bytes,
                       file_name="گزارش_فرآیند_کامل.html", mime="text/html",
                       use_container_width=True)
    st.caption(f"حجم فایل: {len(standalone_bytes) / 1024:,.0f} کیلوبایت — "
              "برای فولدر شبکه/اشتراک مستقیم، نه پیوست ایمیل")

    xlsx_bytes = build_excel_report(kpis=DATA["kpis"], nodes=DATA["graph"]["nodes"],
                                    edges=DATA["graph"]["edges"])
    st.download_button("⬇ دانلود اکسل", data=xlsx_bytes, file_name="گزارش_فرآیند.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)

# ── ۴) سربرگ ────────────────────────────────────────────────────────────────
st.markdown(
    f"""<div style="background:linear-gradient(120deg,{T.BRAND_NAVY},{T.BRAND_TEAL});color:#fff;
    border-radius:{T.RADIUS['xl']}px;padding:22px 26px;margin-bottom:18px">
      <div style="font-size:22px;font-weight:700">اتاق کنترل فرآیندهای سازمانی</div>
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
