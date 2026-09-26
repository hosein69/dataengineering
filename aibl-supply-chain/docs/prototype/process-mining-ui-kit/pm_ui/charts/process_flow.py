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

## شدت جریان و عملکرد (افزودهٔ بررسی UX v2)
دو حالت نمایش دارد:
    frequency   ضخامت یال متناسب با ``count`` (تعداد کیس) — پیش‌فرض،
                همان زبان بصری Celonis برای «مسیر غالب».
    performance رنگ یال از روی ``median_hours`` با طیف دنباله‌ای Teal
                (``tokens.SEQUENTIAL``) — کم‌رنگ=سریع، پررنگ=کند. طیف
                دسته‌ای هرگز برای این حالت استفاده نمی‌شود چون این یک
                کمیت پیوسته است، نه دسته (قاعدهٔ خودِ tokens.py).
ضخامت یال در هر دو حالت همیشه از فراوانی می‌آید — «سریع ولی کم‌تکرار» و
«کند ولی پرتکرار» نباید در یک بُعد گم شوند.

## انحراف (افزودهٔ بررسی UX v2)
یال با ``deviating=True`` جدا از رنگ (که خودش می‌تواند critical/غیرِ آن
باشد) با ``stroke-dasharray`` کشیده می‌شود؛ یعنی انحراف یک کانال دوم،
غیر از رنگ، دارد و در چاپ سیاه‌وسفید یا برای کاربر کوررنگ هم قابل تشخیص
می‌ماند.

## ساده‌سازی درجه‌بندی‌شده (افزودهٔ بررسی UX v2)
به‌جای خطای سخت روی سقف تعداد فعالیت، ``abstraction`` (۰ تا ۱۰۰، پیش‌فرض
۱۰۰ یعنی دقت کامل) کم‌فراوانی‌ترین یال‌ها را کنار می‌گذارد؛ گره‌های بدون
یال باقی‌مانده هم به‌تبع آن پنهان می‌شوند. تابع همیشه تعداد «نمایش‌داده‌شده
از کل» را برمی‌گرداند تا هیچ داده‌ای بی‌آن‌که گفته شود پنهان نماند —
دقیقاً همان قاعدهٔ «داده‌ی ناموجود هرگز صفر نیست» که در بقیهٔ محصول هست،
اعمال‌شده روی «داده‌ی فیلترشده».
"""
from __future__ import annotations

__contract__ = 2

import html as _html
import math
from typing import Dict, List, Literal, NamedTuple, Optional, Sequence, Tuple, TypedDict

from .. import tokens as T

Mode = Literal["frequency", "performance"]


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
    deviating: bool        # اگر True، یال جدا از رنگ با خط‌چین کشیده می‌شود (انحراف از انطباق)
    median_hours: float     # میانهٔ ساعت گذار — پایهٔ حالت «عملکرد»
    label: str


class AbstractionSummary(NamedTuple):
    """خروجی همراهِ رندر — همیشه «نمایش‌داده‌شده از کل» را می‌گوید، هرگز پنهان بی‌اعلام."""
    shown_nodes: int
    total_nodes: int
    shown_edges: int
    total_edges: int

    @property
    def is_full(self) -> bool:
        return self.shown_nodes == self.total_nodes and self.shown_edges == self.total_edges


def _esc(v: object) -> str:
    return _html.escape("" if v is None else str(v), quote=True)


def _layered_positions(nodes: Sequence[FlowNode], edges: Sequence[FlowEdge]) -> Dict[str, int]:
    """لایهٔ هر گره را با طولانی‌ترین مسیر از گره‌های بی‌ورودی حساب می‌کند.

    فرآیندهای واقعی معمولاً حلقه دارند (مثلاً «اصلاح مدارک» که به «بررسی
    مدارک» برمی‌گردد). بدون شناسایی این یال‌های برگشتی، رگرسیونِ طولانی‌ترین
    مسیر روی حلقه هرگز به تعادل نمی‌رسد و لایه‌ها نامحدود رشد می‌کنند —
    نتیجه‌اش گره‌هایی است که بیرون از بومِ SVG قرار می‌گیرند و از نما حذف
    می‌شوند. راه‌حل استاندارد ترسیم گراف لایه‌ای (Sugiyama): با یک پیمایش
    DFS یال‌های برگشتی (back edge — به گرهٔ در حال پیمایش) شناسایی و از
    محاسبهٔ لایه کنار گذاشته می‌شوند؛ در ترسیم همچنان رسم می‌شوند.
    """
    ids = [n["id"] for n in nodes]
    outgoing: Dict[str, List[str]] = {i: [] for i in ids}
    for e in edges:
        if e.get("source") in outgoing and e.get("target") in outgoing:
            outgoing[e["source"]].append(e["target"])

    # ── شناسایی یال‌های برگشتی با DFS (رنگ‌آمیزی سفید/خاکستری/سیاه) ──
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {i: WHITE for i in ids}
    back_edges: set = set()

    def dfs(u: str) -> None:
        color[u] = GRAY
        for v in outgoing.get(u, []):
            if color.get(v) == GRAY:
                back_edges.add((u, v))
            elif color.get(v) == WHITE:
                dfs(v)
        color[u] = BLACK

    for i in ids:
        if color[i] == WHITE:
            dfs(i)

    forward_edges = [e for e in edges
                     if (e.get("source"), e.get("target")) not in back_edges]

    incoming: Dict[str, List[str]] = {i: [] for i in ids}
    for e in forward_edges:
        if e.get("source") in incoming and e.get("target") in incoming:
            incoming[e["target"]].append(e["source"])

    layer: Dict[str, int] = {}
    roots = [i for i in ids if not incoming[i]] or ids[:1]
    for r in roots:
        layer[r] = 0
    # روی یال‌های forward (بدون حلقه) رگرسیون طولانی‌ترین مسیر همیشه به
    # تعادل می‌رسد؛ سقف len(ids) صرفاً محافظ در برابر دادهٔ بدشکل است.
    changed = True
    guard = 0
    while changed and guard < len(ids) + 1:
        changed = False
        guard += 1
        for e in forward_edges:
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


def apply_abstraction(nodes: Sequence[FlowNode], edges: Sequence[FlowEdge],
                       abstraction: int) -> Tuple[List[FlowNode], List[FlowEdge], AbstractionSummary]:
    """کم‌فراوانی‌ترین یال‌ها را طبق ``abstraction`` (۰..۱۰۰، ۱۰۰=دقت کامل) کنار می‌گذارد.

    قاعده: هرگز کمتر از یک یال باقی نمی‌ماند (اگر یالی هست)، و پیش‌فرض
    فراخوان همیشه باید ۱۰۰ باشد — دقت، انتخابی است، نه پیش‌فرض کاهش‌یافته.
    """
    total_nodes, total_edges = len(nodes), len(edges)
    abstraction = max(0, min(100, int(abstraction)))
    if abstraction >= 100 or not edges:
        return list(nodes), list(edges), AbstractionSummary(total_nodes, total_nodes, total_edges, total_edges)

    ranked = sorted(edges, key=lambda e: -int(e.get("count", 0)))
    keep_n = max(1, round(total_edges * abstraction / 100))
    kept_keys = {(e.get("source"), e.get("target")) for e in ranked[:keep_n]}
    shown_edges = [e for e in edges if (e.get("source"), e.get("target")) in kept_keys]
    used_ids = {e.get("source") for e in shown_edges} | {e.get("target") for e in shown_edges}
    shown_nodes = [n for n in nodes if n["id"] in used_ids]
    return shown_nodes, shown_edges, AbstractionSummary(len(shown_nodes), total_nodes,
                                                        len(shown_edges), total_edges)


def _performance_color(edge: FlowEdge, all_durations: Sequence[float]) -> str:
    """یال را از روی ``median_hours`` به یکی از ۶ پلهٔ ``tokens.SEQUENTIAL`` نگاشت می‌دهد."""
    hours = edge.get("median_hours")
    if hours is None or not all_durations:
        return T.STATUS["neutral"].fill
    lo, hi = min(all_durations), max(all_durations)
    span = (hi - lo) or 1.0
    idx = min(len(T.SEQUENTIAL) - 1, int(((hours - lo) / span) * len(T.SEQUENTIAL)))
    return T.SEQUENTIAL[idx]


def render_process_flowgraph(nodes: Sequence[FlowNode], edges: Sequence[FlowEdge], *,
                              title: str = "نقشهٔ جریان فرآیند",
                              width: int = 980, height: int = 520,
                              node_w: int = 158, node_h: int = 58,
                              mode: Mode = "frequency", abstraction: int = 100,
                              highlight_edges: Optional[Sequence[Tuple[str, str]]] = None) -> AbstractionSummary:
    """گراف فرآیند را با ``components.v1.html`` رندر می‌کند و خلاصهٔ ساده‌سازی را برمی‌گرداند.

    فراخوان (معمولاً :mod:`pm_ui.blocks`) باید ``AbstractionSummary`` را در
    یک برچسب «نمایش N از M» نشان دهد؛ خودِ این تابع هیچ متن وضعیتی رندر
    نمی‌کند تا مسئولیت «گفتن چه چیزی پنهان شد» همیشه صریح و کنار خودِ
    کنترل (اسلایدر) بماند، نه مدفون داخل iframe نمودار.

    ``highlight_edges`` — مثلاً از :func:`pm_ui.charts.variant_explorer.selected_path_edges`
    — یال‌های آن واریانت را پررنگ و بقیه را کم‌رنگ می‌کند (همان تعامل
    «انتخاب واریانت روی نقشه» در بررسی UX v2). ``None``/خالی یعنی بدون
    فیلتر، همهٔ یال‌ها یکسان.
    """
    import streamlit.components.v1 as components

    shown_nodes, shown_edges, summary = apply_abstraction(nodes, edges, abstraction)
    html = _build_svg_document(shown_nodes, shown_edges, title=title, width=width, height=height,
                                node_w=node_w, node_h=node_h, mode=mode,
                                highlight_edges=set(highlight_edges) if highlight_edges else None)
    components.html(html, height=height + 44, scrolling=False)
    return summary


def flowgraph_svg(nodes: Sequence[FlowNode], edges: Sequence[FlowEdge], *,
                   width: int = 980, height: int = 520,
                   node_w: int = 158, node_h: int = 58,
                   mode: Mode = "frequency", abstraction: int = 100) -> str:
    """فقط بدنهٔ SVG (بدون iframe/JS) — برای جای‌گذاری در خروجی HTML مستقل (نه ایمیل؛
    ایمیل جدول ساده می‌گیرد، نگاه کنید به ``pm_ui/export/html_report.py``)."""
    shown_nodes, shown_edges, _ = apply_abstraction(nodes, edges, abstraction)
    return _build_svg(shown_nodes, shown_edges, width=width, height=height, node_w=node_w, node_h=node_h,
                       interactive=False, mode=mode)


def _build_svg(nodes: Sequence[FlowNode], edges: Sequence[FlowEdge], *,
               width: int, height: int, node_w: int, node_h: int,
               interactive: bool, mode: Mode = "frequency",
               highlight_edges: Optional[set] = None) -> str:
    pos = _layout(nodes, edges, width=width, height=height)
    counts = [max(0, int(e.get("count", 1))) for e in edges] or [1]
    max_count = max(counts)
    durations = [float(e["median_hours"]) for e in edges if e.get("median_hours") is not None]
    highlight_node_ids: set = set()
    if highlight_edges:
        for s, t in highlight_edges:
            highlight_node_ids.add(s)
            highlight_node_ids.add(t)

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
        deviating = bool(e.get("deviating"))
        count = max(0, int(e.get("count", 1)))
        # ضخامت همیشه از فراوانی می‌آید، در هر دو حالت — سرعت و تکرار دو بُعد جدا هستند
        weight = 1.6 + (count / max_count) * 7.0
        if mode == "performance" and not deviating:
            color = _performance_color(e, durations)
            opacity = 0.95
        else:
            color = T.STATUS["critical"].fill if critical else T.AQUA_700
            opacity = 0.92 if critical else (0.35 + 0.5 * (count / max_count))
        if deviating:
            color = T.STATUS["critical"].fill
        marker = "url(#arrow-crit)" if (critical or deviating) else "url(#arrow)"
        dash = ' stroke-dasharray="7,5"' if deviating else ""
        edge_key = (e.get("source"), e.get("target"))
        if highlight_edges is not None:
            opacity = opacity if edge_key in highlight_edges else 0.12

        x1, y1 = s["x"] - node_w / 2, s["y"]
        x2, y2 = t["x"] + node_w / 2, t["y"]
        mx = (x1 + x2) / 2
        path = f"M{x1:.1f},{y1:.1f} C{mx:.1f},{y1:.1f} {mx:.1f},{y2:.1f} {x2:.1f},{y2:.1f}"
        lbl = e.get("label") or (f"{count:,}".replace(",", "،"))
        lx, ly = mx, (y1 + y2) / 2 - 8
        edge_class = "edge edge-crit" if (critical or deviating) else "edge"
        edge_svgs.append(
            f'<g class="{edge_class}" data-src="{_esc(e.get("source"))}" data-tgt="{_esc(e.get("target"))}">'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-opacity="{opacity:.2f}" '
            f'stroke-width="{weight:.1f}" stroke-linecap="round"{dash} marker-end="{marker}"></path>'
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
        node_opacity = 1.0 if (highlight_edges is None or n["id"] in highlight_node_ids) else 0.4
        node_svgs.append(f"""
<g class="node" data-id="{_esc(n['id'])}" transform="translate({x:.1f},{y:.1f})" opacity="{node_opacity:.2f}">
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
                         title: str, width: int, height: int, node_w: int, node_h: int,
                         mode: Mode = "frequency", highlight_edges: Optional[set] = None) -> str:
    svg = _build_svg(nodes, edges, width=width, height=height, node_w=node_w, node_h=node_h,
                      interactive=True, mode=mode, highlight_edges=highlight_edges)
    return f"""
<div class="pm-flow" dir="rtl">
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:{T.FONT_STACK}}}
  .pm-flow{{background:{T.SURFACE_RAISED};border:1px solid {T.BORDER};
    border-radius:{T.RADIUS['lg']}px;padding:14px 16px;box-shadow:{T.SHADOW_CARD}}}
  .pm-flow h4{{margin:0 0 8px;font-size:15px;color:{T.INK};font-weight:700}}
  .node-label{{font-size:12px;font-weight:700;fill:{T.INK}}}
  .node-count{{font-size:14px;font-weight:700;fill:{T.AQUA_700}}}
  .node-hint{{font-size:9.5px;fill:{T.INK_MUTED}}}
  .edge-label{{font-size:10px;fill:{T.INK_MUTED}}}
  .node{{cursor:pointer;transition:filter .15s}}
  .node:hover rect:first-child{{filter:drop-shadow(0 4px 10px rgba(15,23,42,.18))}}
  .edge{{transition:opacity .2s}}
</style>
<h4>{_esc(title)}</h4>
{svg}
</div>"""
