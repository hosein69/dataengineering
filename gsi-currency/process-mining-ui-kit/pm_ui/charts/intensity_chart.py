# -*- coding: utf-8 -*-
"""نمودارهای تعاملی شدت جریان — با Plotly، هم‌سو با هویت بصری آکوا.

این‌جا برخلاف :mod:`process_flow` و :mod:`kanban` از Plotly استفاده
می‌شود چون تعامل غنی (زوم، هاور دقیق، انتخاب بازه) با SVG دستی به‌صرفه
نیست و Plotly همین حالا در نیازمندی‌های پروژه‌های خواهر (aibl-supply-chain،
hr-performance) حاضر است. نمودار در خودِ Streamlit تعاملی است؛ برای خروجی
HTML ایمیل باید یک تصویر PNG ثابت جایگزین آن شود (نگاه کنید به
``export/html_report.py``) چون Outlook جاوااسکریپت اجرا نمی‌کند.
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict, Mapping, Optional, Sequence

from .. import tokens as T


def plotly_layout_template() -> dict:
    """قالب مشترک Plotly: شبکهٔ ملایم، فونت فارسی، جداکنندهٔ اعشار محلی."""
    axis = dict(
        showgrid=True, gridcolor=T.BORDER, gridwidth=1, zeroline=False,
        linecolor=T.BORDER_STRONG, ticks="outside", tickcolor=T.BORDER_STRONG,
        ticklen=4, tickfont=dict(size=11, color=T.INK_SOFT), automargin=True,
    )
    return dict(
        font=dict(family=T.FONT_STACK, size=12, color=T.INK),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=list(T.CATEGORICAL),
        xaxis={**axis, "side": "bottom"},
        yaxis={**axis, "side": "right"},   # RTL: محور مقدار سمت راست
        margin=dict(t=44, r=24, b=40, l=16),
        hoverlabel=dict(bgcolor=T.SURFACE_RAISED, bordercolor=T.BORDER_STRONG,
                        font=dict(family=T.FONT_STACK, size=12, color=T.INK)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=11, color=T.INK_SOFT), bgcolor="rgba(0,0,0,0)"),
        separators="٫٬",
    )


def render_intensity_area(labels: Sequence[str], series: Mapping[str, Sequence[float]], *,
                           title: str = "شدت جریان فرآیند در طول زمان",
                           height: int = 340, use_container_width: bool = True) -> None:
    """نمودار ناحیه‌ای تعاملی با گرادیان شدت — برای روند حجم کیس در طول زمان.

    ``labels`` باید از قبل قالب‌بندی‌شده باشد (مثلاً با
    ``pm_ui.persian.jalali_compact``) چون این تابع خودش تاریخ تبدیل نمی‌کند.
    """
    import plotly.graph_objects as go
    import streamlit as st

    fig = go.Figure()
    palette = list(T.SEQUENTIAL[2:]) + list(T.CATEGORICAL)
    for i, (name, values) in enumerate(series.items()):
        color = palette[i % len(palette)]
        fig.add_trace(go.Scatter(
            x=list(labels), y=list(values), name=name, mode="lines",
            line=dict(width=2.4, color=color, shape="spline", smoothing=0.35),
            fill="tozeroy", fillcolor=color + "26",
            hovertemplate="%{y:,.0f}<extra>" + name + "</extra>",
        ))
    fig.update_layout(**plotly_layout_template(), title=dict(text=title, x=0, xanchor="left",
                       font=dict(size=14, color=T.INK)), height=height)
    st.plotly_chart(fig, use_container_width=use_container_width, config={"displaylogo": False})


def render_throughput_heatmap(z: Sequence[Sequence[float]], x_labels: Sequence[str],
                               y_labels: Sequence[str], *,
                               title: str = "شدت فعالیت — روز هفته × ساعت",
                               height: int = 320) -> None:
    """نقشهٔ حرارتی شدت فعالیت (مثلاً حجم رویداد در هر روز/ساعت) با طیف آکوا."""
    import plotly.graph_objects as go
    import streamlit as st

    fig = go.Figure(data=go.Heatmap(
        z=z, x=list(x_labels), y=list(y_labels),
        colorscale=[[i / (len(T.SEQUENTIAL) - 1), c] for i, c in enumerate(T.SEQUENTIAL)],
        hovertemplate="%{y} — %{x}<br>%{z:,.0f}<extra></extra>",
        colorbar=dict(outlinewidth=0, tickfont=dict(size=10, color=T.INK_SOFT)),
    ))
    layout = plotly_layout_template()
    layout.pop("legend", None)
    fig.update_layout(**layout, title=dict(text=title, x=0, xanchor="left",
                       font=dict(size=14, color=T.INK)), height=height)
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
