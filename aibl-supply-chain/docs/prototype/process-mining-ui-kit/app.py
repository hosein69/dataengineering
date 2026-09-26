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
from pm_ui.export import MAX_OUTLOOK_BYTES, build_excel_report, build_report_html, build_standalone_html
from pm_ui.charts import STATE_KEY_PREFIX, default_variant_id
from pm_ui.layout import (AUDIENCE_LABELS, AUDIENCES, DEFAULT_LAYOUT, REGISTRY, add_block,
                          draggable_block_list, move_block, remove_block, render_layout,
                          reorder_blocks)

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
    "variants": mock_data.process_variants(),
    "conformance": mock_data.conformance_summary(),
    "root_cause": mock_data.root_cause_rows(),
    "evidence": mock_data.evidence_table(),
    "kanban": mock_data.kanban_columns(),
    "system": mock_data.system_stages(),
    "intensity": mock_data.intensity_series(),
    "heatmap": mock_data.heatmap_matrix(),
}

# پیش از رندر اول، واریانت پیش‌فرض (مسیر غالب) را می‌گذاریم — تا اولین
# نمایی که کاربر می‌بیند هم مسیر مرجع را روی نقشه برجسته نشان دهد، نه فقط
# پس از اولین تعامل با کاوشگر واریانت.
_variant_state_key = f"{STATE_KEY_PREFIX}variant_explorer"
if _variant_state_key not in st.session_state:
    st.session_state[_variant_state_key] = default_variant_id(DATA["variants"])

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
    st.markdown("**ترتیب و ترکیب بلوک‌ها**")
    st.caption("بکشید و رها کنید، یا با ▲/▼ (برای کاربر بدون موس/کیبورد) جابه‌جا کنید.")

    ordered = sorted(st.session_state.layout, key=lambda b: b.get("order", 0))
    dnd_items = [{"id": b["id"], "label": b.get("title") or b.get("type", ""), "badge": b.get("size", "")}
                for b in ordered]
    new_order = draggable_block_list(dnd_items, key="layout_dnd")
    # Streamlit نگه می‌دارد آخرین مقداری که این کامپوننت فرستاده را — یعنی
    # new_order بعد از یک بار رهاسازی، در همهٔ اجراهای بعدی هم همان مقدار
    # قبلی را برمی‌گرداند، نه None. اگر فقط بر اساس «truthy بودن» rerun کنیم،
    # حلقهٔ بی‌پایان می‌سازیم. فقط وقتی واقعاً با ترتیب فعلی فرق دارد اعمال کن.
    if new_order and new_order != [b["id"] for b in ordered]:
        st.session_state.layout = reorder_blocks(st.session_state.layout, new_order)
        st.rerun()

    for b in ordered:
        st.caption(b.get("title") or b.get("type"))
        # عمداً سه ستون تقریباً هم‌عرض، نه ستون‌های باریک ۱/۴ی کنار برچسب:
        # در Streamlit 1.64 دکمه‌ای که در ستون خیلی باریک بیفتد (کمتر از
        # ~۶۰px) متنش کاملاً نامرئی می‌شود — باگی از خودِ ویجت، نه از CSS
        # این پروژه؛ با پهن‌تر کردن ستون دکمه، بدون نیاز به دور زدن نسخه،
        # دور زده می‌شود.
        c1, c2, c3 = st.columns(3)
        if c1.button("▲", key=f"up_{b['id']}", help="جابه‌جایی به بالا", use_container_width=True):
            st.session_state.layout = move_block(st.session_state.layout, b["id"], delta=-1)
            st.rerun()
        if c2.button("▼", key=f"dn_{b['id']}", help="جابه‌جایی به پایین", use_container_width=True):
            st.session_state.layout = move_block(st.session_state.layout, b["id"], delta=1)
            st.rerun()
        if c3.button("✕ حذف", key=f"rm_{b['id']}", help="حذف این بلوک از چیدمان",
                    use_container_width=True):
            st.session_state.layout = remove_block(st.session_state.layout, b["id"])
            st.rerun()

    present_types = {b.get("type") for b in st.session_state.layout}
    addable = sorted(t for t in REGISTRY if t not in present_types)
    if addable:
        with st.form("add_block_form", border=False):
            new_type = st.selectbox("➕ افزودن بلوک", addable, label_visibility="collapsed")
            if st.form_submit_button("افزودن به پایین چیدمان", use_container_width=True):
                st.session_state.layout = add_block(
                    st.session_state.layout,
                    {"id": new_type, "type": new_type, "size": "full", "visible_for": []})
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

    email_export = build_report_html(
        title=REPORT_TITLE, subtitle=AUDIENCE_LABELS[st.session_state.audience],
        kpis=DATA["kpis"], nodes=DATA["graph"]["nodes"], edges=DATA["graph"]["edges"],
        kanban=DATA["kanban"])
    html_bytes = email_export.html.encode("utf-8")
    st.download_button("⬇ دانلود HTML ایمیل", data=html_bytes,
                       file_name="گزارش_فرآیند.html", mime="text/html",
                       use_container_width=True)
    if email_export.within_budget:
        st.caption(f"✅ حجم فایل: {email_export.size_bytes / 1024:,.1f} کیلوبایت — "
                  f"زیر سقف امن اوتلوک ({MAX_OUTLOOK_BYTES // 1000} کیلوبایت)")
    else:
        st.warning(f"⚠ حجم فایل: {email_export.size_bytes / 1024:,.1f} کیلوبایت — "
                  f"بالاتر از سقف امن اوتلوک ({MAX_OUTLOOK_BYTES // 1000} کیلوبایت)")
    for note in email_export.trimmed_notes:
        st.caption(f"ℹ {note}")

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
