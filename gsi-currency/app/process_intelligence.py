"""Explicit export of the current authorized case scope."""
from __future__ import annotations

import os


def render(df, extras, ref_date=""):
    import streamlit as st
    with st.expander("بسته فرآیندی آفلاین • HTML / Outlook / Excel"):
        st.caption(
            "سه نمای مرتبط: وضعیت و اقدام، مسیر فرآیند و تحویل بین واحدها. "
            "گزارش از دامنه فعلی ساخته می‌شود؛ ایمیل فقط پیش‌نویس است و الگوی صریح به‌تنهایی ریسک/تخلف نیست."
        )
        cfg = os.environ.get("GSI_PROCESS_PATTERN_CONFIG", "").strip()
        if cfg:
            st.caption("پیکربندی الگوی رویدادی صریح از GSI_PROCESS_PATTERN_CONFIG فعال است؛ هیچ قاعده‌ای خودکار ساخته نمی‌شود.")
        if st.button("ساخت بسته فرآیندی", key="offline_process_build"):
            try:
                from gsi.studio_core.report_builder import _filtered_process_extras
                from gsi.process_intelligence.core import build_bundle, zip_bundle
                from gsi.process_intelligence.patterns import load_spec
                scoped = _filtered_process_extras(extras, df)
                spec = load_spec(cfg) if cfg else None
                files = build_bundle(
                    scoped.get("eventlog"), source="current scoped snapshot",
                    reference=ref_date or "unspecified", pattern_spec=spec,
                )
                st.download_button(
                    "دریافت ZIP گزارش و پیش‌نویس", zip_bundle(files),
                    "GSI_PROCESS_EXPORT.zip", "application/zip")
            except (ValueError, RuntimeError, OSError, KeyError) as e:
                st.error("خروجی متوقف شد: " + str(e))
