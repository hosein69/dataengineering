# -*- coding: utf-8 -*-
"""ثبت رندرکننده‌های هر نوع بلوک در موتور چیدمان (:mod:`pm_ui.layout.engine`).

``data`` یک دیکشنری با کلیدهای ``kpis``، ``graph``، ``kanban``، ``system``،
``intensity``، ``heatmap`` است — همان ساختاری که :mod:`pm_ui.mock_data`
تولید می‌کند. برای اتصال به دادهٔ واقعی، فقط تابعی هم‌ساختار با
``mock_data`` بنویسید و همان دیکشنری را به ``render_layout`` بدهید؛ خود
بلوک‌ها نیازی به تغییر ندارند.
"""
from __future__ import annotations

from typing import Any, Dict

from . import components as C
from .charts import (render_intensity_area, render_kanban_board,
                     render_process_flowgraph, render_system_flow,
                     render_throughput_heatmap)
from .layout.engine import register


@register("kpi_row")
def _kpi_row(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    C.render_kpi_row(data.get("kpis", []), columns=props.get("columns"))


@register("process_flow")
def _process_flow(props: Dict[str, Any], data: Dict[str, Any]) -> None:
    g = data.get("graph", {"nodes": [], "edges": []})
    render_process_flowgraph(g.get("nodes", []), g.get("edges", []),
                              title=props.get("title", "نقشهٔ جریان فرآیند"),
                              height=props.get("height", 460))


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
