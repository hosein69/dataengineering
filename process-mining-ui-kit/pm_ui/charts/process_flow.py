# -*- coding: utf-8 -*-
"""نقشهٔ جریان فرآیند (Process Flowgraph) — شبیه گراف‌های Celonis، تولیدشده با SVG خالص.

بدون هیچ کتابخانهٔ گراف بیرونی (D3، cytoscape، …)؛ فقط SVG + کمی JS برای
هاور. علت: خروجی باید هم داخل Streamlit (iframe از طریق
``components.v1.html``) و هم به‌صورت آفلاین در ایمیل اوتلوک قابل‌بازتولید
باشد، و هر وابستگی بیرونی یعنی ریسک شکستن روی شبکهٔ بدون اینترنت.

## چیدمان
گره‌ها به‌صورت خودکار لایه‌بندی می‌شوند (طولانی‌ترین مسیر از گره‌های آغازین)
و چون رابط RTL است، جریان از **راست به چپ** ترسیم می‌شود — لایهٔ صفر (شروع
فرآیند) سمت راست بوم می‌نشیند.

## شدت جریان
ضخامت هر یال متناسب با ``count`` آن (تعداد کیس‌هایی که از آن مسیر عبور
کرده‌اند) است — دقیقاً همان زبان بصری Celonis برای «مسیر غالب» در برابر
«انحراف کم‌تکرار».
"""
from __future__ import annotations

__contract__ = 1

import html as _html
import math
from typing import Dict, List, Optional, Sequence, TypedDict

from .. import tokens as T


class FlowNode(TypedDict, total=False):
    id: str
    label: str
    count: int
    status: str          # کلید STATUS در tokens.py؛ پیش‌فرض "good"
    hint: str             # زیرنویس کوچک (مثلاً میانگین زمان توقف)


class FlowEdge(TypedDict, total=False):
    source: str
    target: str
    count: int
    critical: bool        # اگر True، یال با رنگ بحرانی و ضخیم‌تر کشیده می‌شود
    label: str


def _esc(v: object) -> str:
    return _html.escape("" if v is None else str(v), quote=True)


def _layered_positions(nodes: Sequence[FlowNode], edges: Sequence[FlowEdge]) -> Dict[str, int]:
    """لایهٔ هر گره را با طولانی‌ترین مسیر از گره‌های بی‌ورودی حساب می‌کند."""
    ids = [n["id"] for n in nodes]
    incoming: Dict[str, List[str]] = {i: [] for i in ids}
    outgoing: Dict[str, List[str]] = {i: [] for i in ids}
    for e in edges:
        if e["source"] in outgoing and e["target"] in incoming:
            outgoing[e["source"]].append(e["target"])
            incoming[e["target"]].append(e["source"])

    layer: Dict[str, int] = {}
    roots = [i for i in ids if not incoming[i]] or ids[:1]
    for r in roots:
        layer[r] = 0
    # BFS/relaxation ساده که روی گراف‌های غیرحلقوی کوچک (تعداد گره‌های فرآیند) کافی است
    changed = True
    guard = 0
    while changed and guard < len(ids) + 5:
        changed = False
        guard += 1
        for e in edges:
            s, t = e.get("source"), e.get("target")
            if s in layer:
                nl = layer[s] + 1
                if t not in layer or layer[t] < nl:
                    layer[t] = nl
                    changed = True
    for i in ids:
        layer.setdefault(i, 0)
    return layer


def _layout(nodes: Sequence[FlowNode], edges: Sequence[FlowEdge], *,
            width: int, height: int, margin: int = 64) -> Dict[str, Dict[str, float]]:
    layer = _layered_positions(nodes, edges)
    by_layer: Dict[int, List[str]] = {}
    for nid, ly in layer.items():
        by_layer.setdefault(ly, []).append(nid)
    max_layer = max(by_layer) if by_layer else 0
    layer_gap = (width - 2 * margin) / max(1, max_layer)

    pos: Dict[str, Dict[str, float]] = {}
    for ly, members in by_layer.items():
        n = len(members)
        # RTL: لایهٔ صفر سمت راست بوم
        x = width - margin - ly * layer_gap
        slot = (height - 2 * margin) / max(1, n)
        for i, nid in enumerate(members):
            y = margin + slot * i + slot / 2
            pos[nid] = {"x": x, "y": y}
    return pos


def render_process_flowgraph(nodes: Sequence[FlowNode], edges: Sequence[FlowEdge], *,
                              title: str = "نقشهٔ جریان فرآیند",
                              width: int = 980, height: int = 520,
                              node_w: int = 158, node_h: int = 58) -> None:
    """گراف فرآیند را با ``components.v1.html`` رندر می‌کند (تعامل هاور با JS محلی)."""
    import streamlit.components.v1 as components

    html = _build_svg_document(nodes, edges, title=title, width=width, height=height,
                                node_w=node_w, node_h=node_h)
    components.html(html, height=height + 44, scrolling=False)


def flowgraph_svg(nodes: Sequence[FlowNode], edges: Sequence[FlowEdge], *,
                   width: int = 980, height: int = 520,
                   node_w: int = 158, node_h: int = 58) -> str:
    """فقط بدنهٔ SVG (بدون iframe/JS) — برای جای‌گذاری در خروجی HTML ایمیل."""
    return _build_svg(nodes, edges, width=width, height=height, node_w=node_w, node_h=node_h,
                       interactive=False)


def _build_svg(nodes: Sequence[FlowNode], edges: Sequence[FlowEdge], *,
               width: int, height: int, node_w: int, node_h: int,
               interactive: bool) -> str:
    pos = _layout(nodes, edges, width=width, height=height)
    counts = [max(0, int(e.get("count", 1))) for e in edges] or [1]
    max_count = max(counts)

    defs = f"""
<defs>
  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="{T.INK_MUTED}"></path>
  </marker>
  <marker id="arrow-crit" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="{T.STATUS['critical'].fill}"></path>
  </marker>
</defs>"""

    edge_svgs: List[str] = []
    for e in edges:
        s, t = pos.get(e.get("source", "")), pos.get(e.get("target", ""))
        if not s or not t:
            continue
        critical = bool(e.get("critical"))
        count = max(0, int(e.get("count", 1)))
        weight = 1.6 + (count / max_count) * 7.0
        color = T.STATUS["critical"].fill if critical else T.AQUA_700
        opacity = 0.92 if critical else (0.35 + 0.5 * (count / max_count))
        marker = "url(#arrow-crit)" if critical else "url(#arrow)"

        x1, y1 = s["x"] - node_w / 2, s["y"]
        x2, y2 = t["x"] + node_w / 2, t["y"]
        mx = (x1 + x2) / 2
        path = f"M{x1:.1f},{y1:.1f} C{mx:.1f},{y1:.1f} {mx:.1f},{y2:.1f} {x2:.1f},{y2:.1f}"
        lbl = e.get("label") or (f"{count:,}".replace(",", "،"))
        lx, ly = mx, (y1 + y2) / 2 - 8
        edge_class = "edge edge-crit" if critical else "edge"
        edge_svgs.append(
            f'<g class="{edge_class}" data-src="{_esc(e.get("source"))}" data-tgt="{_esc(e.get("target"))}">'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-opacity="{opacity:.2f}" '
            f'stroke-width="{weight:.1f}" stroke-linecap="round" marker-end="{marker}"></path>'
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" class="edge-label" '
            f'unicode-bidi="plaintext">{_esc(lbl)}</text></g>')

    node_svgs: List[str] = []
    for n in nodes:
        p = pos.get(n["id"])
        if not p:
            continue
        status = T.status_of(n.get("status") or "good")
        x, y = p["x"] - node_w / 2, p["y"] - node_h / 2
        label = n.get("label", n.get("id", ""))
        count = n.get("count")
        count_txt = f'{int(count):,}'.replace(",", "،") if count is not None else ""
        hint = n.get("hint", "")
        node_svgs.append(f"""
<g class="node" data-id="{_esc(n['id'])}" transform="translate({x:.1f},{y:.1f})">
  <rect width="{node_w}" height="{node_h}" rx="{T.RADIUS['md']}" ry="{T.RADIUS['md']}"
        fill="{T.SURFACE_RAISED}" stroke="{status.ink}" stroke-width="1.4"></rect>
  <rect width="6" height="{node_h}" rx="3" fill="{status.fill}"></rect>
  <text x="{node_w/2}" y="22" text-anchor="middle" class="node-label" unicode-bidi="plaintext">{_esc(label)}</text>
  <text x="{node_w/2}" y="40" text-anchor="middle" class="node-count" unicode-bidi="plaintext">{_esc(count_txt)}</text>
  {f'<text x="{node_w/2}" y="53" text-anchor="middle" class="node-hint" unicode-bidi="plaintext">{_esc(hint)}</text>' if hint else ""}
</g>""")

    hover_js = ""
    if interactive:
        hover_js = """
<script>
document.querySelectorAll('.node').forEach(function(n){
  n.addEventListener('mouseenter', function(){
    var id = n.getAttribute('data-id');
    document.querySelectorAll('.edge').forEach(function(ed){
      var on = ed.getAttribute('data-src') === id || ed.getAttribute('data-tgt') === id;
      ed.style.opacity = on ? '1' : '0.12';
    });
  });
  n.addEventListener('mouseleave', function(){
    document.querySelectorAll('.edge').forEach(function(ed){ ed.style.opacity = '1'; });
  });
});
</script>"""

    return f"""
<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img"
     xmlns="http://www.w3.org/2000/svg" style="direction:ltr">
  {defs}
  <g class="edges">{"".join(edge_svgs)}</g>
  <g class="nodes">{"".join(node_svgs)}</g>
</svg>
{hover_js}"""


def _build_svg_document(nodes: Sequence[FlowNode], edges: Sequence[FlowEdge], *,
                         title: str, width: int, height: int, node_w: int, node_h: int) -> str:
    svg = _build_svg(nodes, edges, width=width, height=height, node_w=node_w, node_h=node_h,
                      interactive=True)
    return f"""
<div class="pm-flow" dir="rtl">
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:{T.FONT_STACK}}}
  .pm-flow{{background:{T.SURFACE_RAISED};border:1px solid {T.BORDER};
    border-radius:{T.RADIUS['lg']}px;padding:14px 16px;box-shadow:{T.SHADOW_CARD}}}
  .pm-flow h4{{margin:0 0 8px;font-size:15px;color:{T.INK};font-weight:800}}
  .node-label{{font-size:12px;font-weight:700;fill:{T.INK}}}
  .node-count{{font-size:14px;font-weight:800;fill:{T.AQUA_700}}}
  .node-hint{{font-size:9.5px;fill:{T.INK_MUTED}}}
  .edge-label{{font-size:10px;fill:{T.INK_MUTED}}}
  .node{{cursor:pointer;transition:filter .15s}}
  .node:hover rect:first-child{{filter:drop-shadow(0 4px 10px rgba(15,23,42,.18))}}
  .edge{{transition:opacity .2s}}
</style>
<h4>{_esc(title)}</h4>
{svg}
</div>"""
