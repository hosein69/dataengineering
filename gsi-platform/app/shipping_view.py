# -*- coding: utf-8 -*-
"""RTL shipping evidence cockpit over the current published, filtered frame."""
from __future__ import annotations

from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

from gsi.design import tokens as T
from gsi.report.shipping_insights import build_shipping_insights

try:
    import plotly.express as px
except ImportError:
    px = None


def render(frame: pd.DataFrame, as_of: date | str) -> None:
    st.markdown("### 🚢 حمل و شواهد بارنامه")
    st.caption("دامنه = فیلتر فعلی و Snapshot منتشرشده؛ دانهٔ هر پرونده یک بارنامه است. "
               "فاصله‌های زمانی، عملکرد یا تقصیر حمل و هزینهٔ دموراژ را ثابت نمی‌کنند.")
    dossiers, coverage = build_shipping_insights(frame, as_of)
    if dossiers.empty:
        st.info("در این برش بارنامهٔ معتبر وجود ندارد. سفارش‌های بدون بارنامه از جمعیت اصلی حذف نشده‌اند.")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("بارنامه یکتا", f"{len(dossiers):,}")
    c2.metric("شاهد تخلیه", f"{int(dossiers['تخلیه'].ne('').sum()):,}")
    c3.metric("دریافت ترخیصیه", f"{int(dossiers['دریافت ترخیصیه'].ne('').sum()):,}")
    c4.metric("مغایرت تاریخ/حمل", f"{int(dossiers['مغایرت شواهد'].ne('').sum()):,}")

    st.markdown("#### پوشش شواهد")
    st.caption("مخرج هر ستون، بارنامه‌های همین برش است؛ تاریخ متعارض در «دارای شاهد» شمرده نمی‌شود.")
    if px is not None:
        fig = px.bar(coverage, x="پوشش (%)", y="شاهد", orientation="h",
                     hover_data=["دارای شاهد", "متعارض", "بارنامه واجدشرایط"],
                     color_discrete_sequence=[T.BRAND_TEAL])
        fig.update_layout(height=330, yaxis=dict(autorange="reversed"),
                          xaxis=dict(range=[0, 100], title="پوشش شواهد (%)"),
                          margin=dict(l=12, r=12, t=12, b=12))
        st.plotly_chart(fig, width="stretch")
    else:
        st.dataframe(coverage, width="stretch", hide_index=True)

    left, right = st.columns(2)
    with left:
        st.markdown("#### سبد روش حمل")
        counts = dossiers.groupby("روش حمل", dropna=False)["بارنامه"].nunique().reset_index(name="بارنامه")
        if px is not None:
            fig = px.bar(counts, x="روش حمل", y="بارنامه", color_discrete_sequence=[T.BRAND_TEAL])
            fig.update_layout(height=320, margin=dict(l=12, r=12, t=12, b=12))
            st.plotly_chart(fig, width="stretch")
        else:
            st.dataframe(counts, width="stretch", hide_index=True)
    with right:
        st.markdown("#### فاصلهٔ تخلیه تا دریافت ترخیصیه")
        observed = dossiers.dropna(subset=["تخلیه تا دریافت ترخیصیه (روز)"]).copy()
        early = int(observed["تخلیه تا دریافت ترخیصیه (روز)"].lt(0).sum())
        elapsed = observed.loc[observed["تخلیه تا دریافت ترخیصیه (روز)"].ge(0)]
        if not elapsed.empty and px is not None:
            fig = px.box(elapsed, x="روش حمل", y="تخلیه تا دریافت ترخیصیه (روز)",
                         points="all", hover_data=["بارنامه"],
                         color_discrete_sequence=[T.BRAND_TEAL])
            fig.update_layout(height=320, margin=dict(l=12, r=12, t=12, b=12))
            st.plotly_chart(fig, width="stretch")
        elif not elapsed.empty:
            st.dataframe(elapsed[["بارنامه", "روش حمل", "تخلیه تا دریافت ترخیصیه (روز)"]],
                         width="stretch", hide_index=True)
        else:
            st.info("دو تاریخ قابل اتصال برای این فاصله موجود نیست.")
        st.caption(f"{len(elapsed):,} از {len(dossiers):,} بارنامه واجد فاصلهٔ غیرمنفی؛ "
                   f"{early:,} مورد دریافت ترخیصیه پیش از تخلیه، در جدول تفصیلی محفوظ؛ "
                   "تاریخ دریافت ترخیصیه با تاریخ صدور یا زمان پرداخت یکی نیست.")

    st.markdown("#### پرونده‌های نیازمند تکمیل شاهد")
    issues = dossiers.loc[dossiers["مغایرت شواهد"].ne("") | dossiers["دادهٔ لازم"].ne("")].copy()
    if not issues.empty:
        issues = issues.assign(_critical=issues["اقلام بحرانی یکتا"],
                               _age=issues["روز سپری‌شده پس از تخلیه (بدون ترخیص کامل)"].fillna(-1))
        issues = issues.sort_values(["_critical", "_age"], ascending=False).drop(columns=["_critical", "_age"])
    st.caption("ترتیب پیگیری: تعداد متریال بحرانی، سپس روز سپری‌شده پس از تخلیه؛ "
               "این ترتیب نمرهٔ کارشناس حمل نیست.")
    st.dataframe(issues if not issues.empty else dossiers, width="stretch", hide_index=True)
    st.caption("برای مرحلهٔ بعد: بوکینگ، توقف هر هاب، سوئیچ سند، ETA، فری‌تایم قرارداد، "
               "صورت‌حساب و مالک تأییدشده را با شماره بارنامه/کانتینر ثبت کنید.")
    with st.expander("قرارداد تحلیل و داده‌های هنوز ناموجود"):
        st.markdown("دادهٔ فعلی اجازهٔ امتیاز ۵ محوری یا نسبت‌دادن دموراژ به فرد را نمی‌دهد. "
                    "مدت‌ها توصیفی‌اند؛ هر تاریخ متعارض کنار گذاشته و در ستون مغایرت نشان داده می‌شود. "
                    "مرجع قواعد: `transport.operational_analysis` و دانش آفلاین حمل.")
    if st.checkbox("آماده‌سازی اکسل شواهد حمل", key="shipping_prepare_excel"):
        data = BytesIO()
        # Source descriptions/identifiers may be untrusted spreadsheet text.
        def safe_cell(value):
            return "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
        with pd.ExcelWriter(data, engine="openpyxl") as writer:
            dossiers.applymap(safe_cell).to_excel(writer, index=False, sheet_name="بارنامه")
            coverage.to_excel(writer, index=False, sheet_name="پوشش شواهد")
            for sheet in writer.book.worksheets:
                sheet.sheet_view.rightToLeft = True
                sheet.freeze_panes = "A2"
                sheet.auto_filter.ref = sheet.dimensions
        st.download_button("دانلود اکسل حمل", data.getvalue(), file_name="GSI_Shipping_Evidence.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="shipping_download_excel")
