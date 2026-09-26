# -*- coding: utf-8 -*-
"""ثبت رندرکننده‌های هر نوع بلوک در موتور چیدمان (:mod:`pm_ui.layout.engine`).

``data`` یک دیکشنری با کلیدهای ``kpis``، ``graph``، ``kanban``، ``system``،
``intensity``، ``heatmap`` است — همان ساختاری که :mod:`pm_ui.mock_data`
تولید می‌کند. برای اتصال به دادهٔ واقعی، فقط تابعی هم‌ساختار با
``mock_data`` بنویسید و همان دیکشنری را به ``render_layout`` بدهید؛ خود
بلوک‌ها نیازی به تغییر ندارند.

## بلوک‌های افزودهٔ بررسی UX v2

``variant_explorer``، ``conformance`` و ``root_cause`` سه بلوک تازه‌اند
(یافتهٔ اصلی بررسی: این سه در نسخهٔ قدیمی تب فرآیند بودند ولی روی این
سامانهٔ طراحی تازه پیاده‌سازی نشده بودند). ``process_flow`` هم گسترش
یافته: کنترل «فراوانی/عملکرد» و اسلایدر سادگی نمایش داخل خودِ بلوک
است (نه یک تنظیم پنهان در ``props``) تا کاربر هر بار مستقیماً می‌بیند
چه چیزی روی نقشهٔ جلوی چشمش تغییر می‌کند.

هر دو بلوک ``process_flow`` و ``variant_explorer`` روی کلید مشترک
``_pm_selected_variant__variant_explorer`` در ``st.session_state``
هماهنگ می‌شوند: انتخاب یک واریانت در یکی، بلافاصله مسیرش را در دیگری
برجسته می‌کند.
"""
from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from . import components as C
from .charts import (STATE_KEY_PREFIX, render_intensity_area, render_kanban_board,
                     render_process_flowgraph, render_system_flow,
                     render_throughput_heatmap, render_variant_explorer,
                     selected_path_edges)
from .layout.engine import register

_VARIANT_KEY = "variant_explorer"  # کلید مشترک بین بلوک نقشه و بلوک کاوشگر واریانت


@register("kpi_row")
def _kpi_row(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    C.render_kpi_row(data.get("kpis", []), columns=props.get("columns"))


@register("insight_row")
def _insight_row(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    C.render_insight_row(data.get("insights", []), columns=props.get("columns"))


@register("evidence_table")
def _evidence_table(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    spec = data.get("evidence")
    if spec:
        C.render_evidence_table(spec, height=props.get("height", 420))


@register("process_flow")
def _process_flow(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    g = data.get("graph", {"nodes": [], "edges": []})
    block_id = props.get("_block_id", "flow")

    ctrl_l, ctrl_r = st.columns([2, 3])
    with ctrl_l:
        mode_label = st.radio("حالت نمایش", ["فراوانی", "عملکرد"], horizontal=True,
                              key=f"mode_{block_id}", label_visibility="collapsed")
    mode = "performance" if mode_label == "عملکرد" else "frequency"
    with ctrl_r:
        abstraction = st.slider("سادگی نمایش (هرگز پیش‌فرض کمتر از ۱۰۰٪ نیست)",
                                0, 100, 100, key=f"abstraction_{block_id}")

    variant_id = st.session_state.get(f"{STATE_KEY_PREFIX}{_VARIANT_KEY}")
    variants = data.get("variants")
    # variant_id خالی یعنی «هنوز چیزی انتخاب نشده» — در آن حالت None می‌دهیم
    # تا نقشه چیزی را کم‌رنگ نکند؛ به‌جای صدا زدن selected_path_edges با
    # یک id نامعتبر که یک مجموعهٔ خالی برمی‌گرداند و همه چیز را کم‌رنگ می‌کند.
    highlight = (selected_path_edges(variants, variant_id)
                if (variants and variant_id and props.get("follow_variant", True)) else None)

    summary = render_process_flowgraph(
        g.get("nodes", []), g.get("edges", []),
        title=props.get("title", "نقشهٔ جریان فرآیند"), height=props.get("height", 460),
        mode=mode, abstraction=abstraction, highlight_edges=highlight)

    if summary.is_full:
        st.caption("نمایش کامل — هیچ فعالیت یا مسیری پنهان نشده است.")
    else:
        st.caption(f"نمایش ساده‌شده — {summary.shown_nodes} از {summary.total_nodes} فعالیت، "
                  f"{summary.shown_edges} از {summary.total_edges} مسیر. "
                  "برای دقت کامل، اسلایدر را به ۱۰۰٪ برگردانید.")


@register("variant_explorer")
def _variant_explorer(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    variants = data.get("variants", [])
    if not variants:
        st.info("واریانتی برای دامنهٔ جاری ثبت نشده.")
        return
    render_variant_explorer(variants, key=_VARIANT_KEY)


@register("conformance")
def _conformance(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    spec = data.get("conformance")
    if spec:
        C.render_conformance_tile(spec, height=props.get("height", 100))


@register("root_cause")
def _root_cause(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    rows = data.get("root_cause", [])
    if rows:
        C.render_root_cause_bars(rows, height=props.get("height"))


@register("kanban")
def _kanban(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    render_kanban_board(data.get("kanban", []), height=props.get("height", 420))


@register("system_flow")
def _system_flow(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    render_system_flow(data.get("system", []), height=props.get("height", 150))


@register("intensity_chart")
def _intensity_chart(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    series = data.get("intensity", {"labels": [], "series": {}})
    render_intensity_area(series.get("labels", []), series.get("series", {}),
                          title=props.get("title", "روند حجم کیس"),
                          height=props.get("height", 320))


@register("heatmap")
def _heatmap(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    hm = data.get("heatmap", {"z": [], "x": [], "y": []})
    render_throughput_heatmap(hm.get("z", []), hm.get("x", []), hm.get("y", []),
                              title=props.get("title", "شدت فعالیت هفتگی"),
                              height=props.get("height", 300))
