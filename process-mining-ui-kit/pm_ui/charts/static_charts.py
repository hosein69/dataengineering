# -*- coding: utf-8 -*-
"""نمودارهای استاتیک SVG — نسخهٔ سبک و بدون جاوااسکریپت نمودارهای Plotly.

``intensity_chart.py`` برای داشبورد زندهٔ Streamlit تعاملی است (زوم، هاور
دقیق) و به Plotly متکی است. اما خروجی HTML مستقل (که دست مخاطب نهایی
می‌رود، نه تیم تحلیل) نباید چند مگابایت کتابخانهٔ Plotly را همراه خودش
حمل کند یا به اینترنت برای بارگذاری آن نیاز داشته باشد. این ماژول همان
دو نمودار را به‌صورت SVG خالص — سبک، خودبسنده، بدون هیچ وابستگی بیرونی —
برای آن خروجی بازتولید می‌کند.
"""
from __future__ import annotations

__contract__ = 1

import html as _html
from typing import Mapping, Sequence

from .. import tokens as T


def _esc(v: object) -> str:
    return _html.escape("" if v is None else str(v), quote=True)


def intensity_area_svg(labels: Sequence[str], series: Mapping[str, Sequence[float]], *,
                        width: int = 760, height: int = 300, title: str = "") -> str:
    """نمودار ناحیه‌ای استاتیک — همان دادهٔ نمودار تعاملی، بدون JS."""
    margin_l, margin_r, margin_t, margin_b = 44, 16, 16, 28
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    all_vals = [v for vs in series.values() for v in vs] or [0, 1]
    lo, hi = min(0, min(all_vals)), max(all_vals) or 1
    span = (hi - lo) or 1.0
    n = max(1, len(labels))
    step = plot_w / max(1, n - 1)

    def y_of(v: float) -> float:
        return margin_t + plot_h - ((v - lo) / span) * plot_h

    palette = list(T.SEQUENTIAL[2:]) + list(T.CATEGORICAL)
    grid = []
    for i in range(5):
        gy = margin_t + plot_h * i / 4
        val = hi - span * i / 4
        grid.append(f'<line x1="{margin_l}" y1="{gy:.1f}" x2="{width-margin_r}" y2="{gy:.1f}" '
                    f'stroke="{T.BORDER}" stroke-width="1"></line>'
                    f'<text x="{width-margin_r+4}" y="{gy+4:.1f}" font-size="10" '
                    f'fill="{T.INK_MUTED}">{_esc(f"{val:,.0f}")}</text>')

    paths = []
    for i, (name, values) in enumerate(series.items()):
        color = palette[i % len(palette)]
        pts = [(margin_l + j * step, y_of(v)) for j, v in enumerate(values)]
        line = " ".join(f"{'L' if j else 'M'}{x:.1f},{y:.1f}" for j, (x, y) in enumerate(pts))
        area = line + f" L{pts[-1][0]:.1f},{margin_t+plot_h} L{margin_l},{margin_t+plot_h} Z"
        paths.append(f'<path d="{area}" fill="{color}22"></path>'
                     f'<path d="{line}" fill="none" stroke="{color}" stroke-width="2.2" '
                     f'stroke-linejoin="round" stroke-linecap="round"></path>')

    legend = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;margin-inline-end:14px">'
        f'<span style="width:9px;height:9px;border-radius:50%;background:{palette[i % len(palette)]};'
        f'display:inline-block"></span>{_esc(name)}</span>'
        for i, name in enumerate(series.keys()))

    xt_idx = list(range(0, n, max(1, n // 6)))
    xticks = "".join(
        f'<text x="{margin_l+i*step:.1f}" y="{height-8}" font-size="9.5" text-anchor="middle" '
        f'fill="{T.INK_MUTED}" unicode-bidi="plaintext">{_esc(labels[i])}</text>'
        for i in xt_idx if i < len(labels))

    title_html = f'<div style="font-size:15px;font-weight:800;color:{T.INK};margin-bottom:6px">{_esc(title)}</div>' if title else ""
    return f"""
<div>
  {title_html}
  <div style="font-size:12px;margin-bottom:6px">{legend}</div>
  <svg viewBox="0 0 {width} {height}" width="100%" style="direction:ltr" role="img" aria-label="{_esc(title)}">
    {''.join(grid)}
    {''.join(paths)}
    {xticks}
  </svg>
</div>"""


def heatmap_svg(z: Sequence[Sequence[float]], x: Sequence[str], y: Sequence[str], *,
                 width: int = 560, height: int = 260, title: str = "") -> str:
    """نقشهٔ حرارتی استاتیک با طیف آکوا/Teal دنباله‌ای."""
    label_w = 60
    plot_w = width - label_w
    cols = max(1, len(x))
    rows = max(1, len(y))
    cell_w = plot_w / cols
    cell_h = height / rows
    flat = [v for row in z for v in row] or [0]
    lo, hi = min(flat), max(flat) or 1
    span = (hi - lo) or 1.0

    def color_for(v: float) -> str:
        t = (v - lo) / span
        idx = min(len(T.SEQUENTIAL) - 1, int(t * (len(T.SEQUENTIAL) - 1)))
        return T.SEQUENTIAL[idx]

    cells = []
    for ri, row in enumerate(z):
        cells.append(f'<text x="{label_w-8}" y="{ri*cell_h+cell_h/2+4:.1f}" font-size="10" '
                     f'text-anchor="end" fill="{T.INK_MUTED}" unicode-bidi="plaintext">{_esc(y[ri] if ri < len(y) else "")}</text>')
        for ci, v in enumerate(row):
            cx = label_w + ci * cell_w
            cells.append(f'<rect x="{cx:.1f}" y="{ri*cell_h:.1f}" width="{cell_w-2:.1f}" height="{cell_h-2:.1f}" '
                        f'rx="3" fill="{color_for(v)}"><title>{_esc(v)}</title></rect>')
    xlabels = "".join(
        f'<text x="{label_w+ci*cell_w+cell_w/2:.1f}" y="{height+14}" font-size="9.5" '
        f'text-anchor="middle" fill="{T.INK_MUTED}" unicode-bidi="plaintext">{_esc(xv)}</text>'
        for ci, xv in enumerate(x))

    title_html = f'<div style="font-size:15px;font-weight:800;color:{T.INK};margin-bottom:6px">{_esc(title)}</div>' if title else ""
    return f"""
<div>
  {title_html}
  <svg viewBox="0 0 {width} {height+22}" width="100%" style="direction:ltr" role="img" aria-label="{_esc(title)}">
    {''.join(cells)}
    {xlabels}
  </svg>
</div>"""
