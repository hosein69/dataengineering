# -*- coding: utf-8 -*-
"""رندر نماهای Kanban/Scrum به‌صورت SVG درون‌خط.

هیچ کتابخانهٔ نموداری بیرونی استفاده نمی‌شود: فایل HTML باید خودبسنده بماند و
بدون اینترنت و بدون سرور روی همان رایانه باز شود. همهٔ نمودارها SVG ساده‌اند، پس
در چاپ و PDF هم درست درمی‌آیند.

هر پنل وقتی داده ندارد، **علت** را می‌گوید. «نمودار خالی» بدون علت، همان چیزی
است که کاربر را به تصمیم اشتباه می‌برد.
"""
from __future__ import annotations

import html
from typing import Dict, List, Optional, Sequence

import pandas as pd

from ..design import tokens as T

#: پالت سری داده از توکن‌های بسته می‌آید، نه رنگ دستی. قاعدهٔ سیستم طراحی
#: (tests/test_design_system.py) هر رنگ هگز دستی در gsi/ و app/ را رد می‌کند.
SERIES_INK = tuple(T.CATEGORICAL)
#: رنگ هشدار و مبنای تاریخی، از همان مقیاس وضعیت.
ALERT_INK = T.STATUS["critical"].ink
BENCH_INK = T.STATUS["warning"].ink


def _esc(v) -> str:
    return html.escape("" if v is None else str(v))


def _num(v, nd: int = 0) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(f):
        return "—"
    return f"{f:,.{nd}f}"


def panel(title: str, body: str, note: str = "", cls: str = "") -> str:
    return (f'<section class="process-viz {cls}"><div class="pv-head"><div>'
            f'<h3>{_esc(title)}</h3>'
            + (f'<p>{_esc(note)}</p>' if note else '')
            + f'</div></div>{body}</section>')


def _why(title: str, reason: str) -> str:
    return panel(title, f'<div class="empty">{_esc(reason)}</div>')


CHART_CSS = f"""
<style>
.gsi-chart{{width:100%;height:auto;display:block;overflow:visible}}
.gsi-chart text{{font-size:9px;fill:var(--text-3,{T.TEXT_MUTED})}}
.gsi-chart .axis{{stroke:var(--border,{T.BORDER});stroke-width:1}}
.gsi-chart .grid{{stroke:var(--border,{T.BORDER});stroke-width:.5;stroke-dasharray:3 3}}
.gsi-legend{{display:flex;flex-wrap:wrap;gap:{T.SPACE['2xs']}px {T.SPACE['sm']}px;margin-top:{T.SPACE['xs']}px;font-size:11px}}
.gsi-legend span{{display:inline-flex;align-items:center;gap:5px}}
.gsi-legend i{{width:11px;height:3px;border-radius:2px;display:inline-block}}
.lane{{display:grid;grid-template-columns:minmax(90px,150px) 1fr;gap:{T.SPACE['2xs']}px;align-items:center;margin:5px 0}}
.lane-name{{font-size:11px;text-align:left;direction:rtl;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.lane-track{{position:relative;height:22px;background:var(--sunken,{T.SURFACE_SUNKEN});border-radius:6px}}
.lane-dot{{position:absolute;top:50%;width:9px;height:9px;margin:-4.5px 0 0 -4.5px;border-radius:50%;background:var(--brand,{T.BRAND_TEAL});opacity:.8}}
.lane-dot[data-alert="1"]{{background:{ALERT_INK};opacity:1}}
.lane-mark{{position:absolute;top:2px;bottom:2px;width:2px;background:{BENCH_INK}}}
.lane-mark[data-k="p85"]{{background:{ALERT_INK}}}
.cov-row{{display:grid;grid-template-columns:minmax(110px,190px) 1fr auto;gap:{T.SPACE['xs']}px;align-items:center;margin:5px 0;font-size:11px}}
.cov-bar{{display:flex;height:16px;border-radius:5px;overflow:hidden;background:var(--sunken,{T.SURFACE_SUNKEN})}}
.cov-bar b{{display:block;background:var(--brand,{T.BRAND_TEAL})}}
.cov-bar i{{display:block;background:repeating-linear-gradient(45deg,{T.SURFACE_SUNKEN},{T.SURFACE_SUNKEN} 4px,{T.BORDER} 4px,{T.BORDER} 8px)}}
</style>
"""


# ══════════════════════════════════════════════════════════════════════════
#  Cumulative Flow
# ══════════════════════════════════════════════════════════════════════════
def cumulative_flow_html(cfd: Optional[pd.DataFrame]) -> str:
    title = "Cumulative Flow — انباشت پرونده در مراحل"
    if not isinstance(cfd, pd.DataFrame) or cfd.empty:
        return _why(title, "Event Log تاریخ‌دار کافی برای ساخت روند انباشتی نیست.")
    periods = list(dict.fromkeys(cfd["دوره"].astype(str)))
    stages = list(dict.fromkeys(cfd.sort_values("ترتیب")["مرحله"].astype(str)))
    if len(periods) < 2:
        return _why(title, "برای روند، دست‌کم دو دورهٔ زمانی لازم است؛ داده فقط یک دوره دارد.")
    lookup = {(str(r["مرحله"]), str(r["دوره"])): float(r["پرونده رسیده (انباشتی)"])
              for r in cfd.to_dict("records")}
    top = max(lookup.values() or [1]) or 1
    W, H, PAD_L, PAD_B, PAD_T = 640, 190, 34, 26, 8
    iw, ih = W - PAD_L - 8, H - PAD_B - PAD_T

    def x(i):
        return PAD_L + iw * (i / max(len(periods) - 1, 1))

    def y(v):
        return PAD_T + ih - ih * (v / top)

    paths = []
    for si, stage in enumerate(stages[:10]):
        pts = " ".join(f"{x(i):.1f},{y(lookup.get((stage, p), 0)):.1f}"
                       for i, p in enumerate(periods))
        ink = SERIES_INK[si % len(SERIES_INK)]
        paths.append(f'<polyline points="{pts}" fill="none" stroke="{ink}" '
                     f'stroke-width="2" stroke-linejoin="round"><title>{_esc(stage)}</title></polyline>')
    grid = "".join(f'<line class="grid" x1="{PAD_L}" x2="{W-8}" y1="{y(top*f):.1f}" y2="{y(top*f):.1f}"/>'
                   f'<text x="{PAD_L-5}" y="{y(top*f)+3:.1f}" text-anchor="end">{_num(top*f)}</text>'
                   for f in (0, .5, 1))
    step = max(1, len(periods) // 6)
    ticks = "".join(f'<text x="{x(i):.1f}" y="{H-8}" text-anchor="middle">{_esc(p)}</text>'
                    for i, p in enumerate(periods) if i % step == 0)
    legend = '<div class="gsi-legend">' + "".join(
        f'<span><i style="background:{SERIES_INK[i % len(SERIES_INK)]}"></i>{_esc(s)}</span>'
        for i, s in enumerate(stages[:10])) + '</div>'
    svg = (f'<svg class="gsi-chart" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="{_esc(title)}">{grid}'
           f'<line class="axis" x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{H-PAD_B}"/>'
           f'<line class="axis" x1="{PAD_L}" y1="{H-PAD_B}" x2="{W-8}" y2="{H-PAD_B}"/>'
           + "".join(paths) + ticks + '</svg>')
    return panel(title, svg + legend,
                 "هر منحنی «پروندهٔ رسیده تا پایان آن دوره» است؛ فاصلهٔ عمودی دو منحنی، کارِ در جریانِ بین آن دو مرحله.")


# ══════════════════════════════════════════════════════════════════════════
#  Throughput
# ══════════════════════════════════════════════════════════════════════════
def throughput_html(thr: Optional[pd.DataFrame]) -> str:
    title = "Throughput — پرونده بسته‌شده در هر دوره"
    if not isinstance(thr, pd.DataFrame) or thr.empty:
        return _why(title, "پروندهٔ بسته‌شده‌ای با تاریخ پایان در این دامنه نیست؛ نرخ تحویل قابل محاسبه نیست.")
    rows = thr.to_dict("records")
    top = max([float(r["پرونده بسته‌شده"] or 0) for r in rows] or [1]) or 1
    W, H, PAD_L, PAD_B, PAD_T = 640, 170, 34, 26, 8
    iw, ih = W - PAD_L - 8, H - PAD_B - PAD_T
    bw = iw / max(len(rows), 1)
    bars, line_pts = [], []
    for i, r in enumerate(rows):
        v = float(r["پرونده بسته‌شده"] or 0)
        h = ih * (v / top)
        bx = PAD_L + i * bw + bw * .18
        bars.append(f'<rect x="{bx:.1f}" y="{PAD_T+ih-h:.1f}" width="{bw*.64:.1f}" '
                    f'height="{max(h,1):.1f}" rx="3" fill="{SERIES_INK[0]}" opacity=".85">'
                    f'<title>{_esc(r["دوره"])}: {_num(v)}</title></rect>')
        m = r.get("میانه متحرک ۴ دوره")
        if m is not None and not pd.isna(m):
            line_pts.append(f"{PAD_L + i*bw + bw/2:.1f},{PAD_T+ih-ih*(float(m)/top):.1f}")
    roll = (f'<polyline points="{" ".join(line_pts)}" fill="none" stroke="{SERIES_INK[4]}" '
            f'stroke-width="2" stroke-dasharray="5 3"/>') if len(line_pts) > 1 else ""
    step = max(1, len(rows) // 6)
    ticks = "".join(f'<text x="{PAD_L+i*bw+bw/2:.1f}" y="{H-8}" text-anchor="middle">{_esc(r["دوره"])}</text>'
                    for i, r in enumerate(rows) if i % step == 0)
    grid = "".join(f'<line class="grid" x1="{PAD_L}" x2="{W-8}" y1="{PAD_T+ih-ih*f:.1f}" y2="{PAD_T+ih-ih*f:.1f}"/>'
                   f'<text x="{PAD_L-5}" y="{PAD_T+ih-ih*f+3:.1f}" text-anchor="end">{_num(top*f)}</text>'
                   for f in (0, .5, 1))
    svg = (f'<svg class="gsi-chart" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(title)}">'
           + grid + "".join(bars) + roll + ticks
           + f'<line class="axis" x1="{PAD_L}" y1="{H-PAD_B}" x2="{W-8}" y2="{H-PAD_B}"/></svg>')
    legend = ('<div class="gsi-legend">'
              f'<span><i style="background:{SERIES_INK[0]}"></i>پرونده بسته‌شده</span>'
              f'<span><i style="background:{SERIES_INK[4]}"></i>میانه متحرک ۴ دوره</span></div>')
    return panel(title, svg + legend,
                 "نرخ تحویل مشاهده‌شده است، نه ظرفیت وعده‌داده‌شده؛ میانه متحرک برای دیدن روند است نه پیش‌بینی.")


# ══════════════════════════════════════════════════════════════════════════
#  Aging WIP
# ══════════════════════════════════════════════════════════════════════════
def aging_wip_html(aging: Optional[pd.DataFrame]) -> str:
    title = "Aging WIP — سن پروندهٔ باز در هر مرحله"
    if not isinstance(aging, pd.DataFrame) or aging.empty:
        return _why(title, "پروندهٔ بازی با سن قابل محاسبه در این دامنه نیست.")
    top = max([float(r["سن (روز)"] or 0) for r in aging.to_dict("records")] or [1]) or 1
    lanes = []
    for stage, g in aging.groupby("مرحله جاری", sort=False):
        marks = ""
        for key, col in (("p50", "صدک ۵۰ تاریخی"), ("p85", "صدک ۸۵ تاریخی")):
            v = g[col].dropna()
            if len(v):
                marks += (f'<span class="lane-mark" data-k="{key}" '
                          f'style="right:{min(100, float(v.iloc[0])/top*100):.1f}%" '
                          f'title="{"میانه" if key=="p50" else "صدک ۸۵"} تاریخی: {_num(v.iloc[0],1)} روز"></span>')
        dots = "".join(
            f'<span class="lane-dot" data-alert="{1 if r["هشدار"].startswith("بیش از صدک ۸۵") else 0}" '
            f'style="right:{min(100, float(r["سن (روز)"] or 0)/top*100):.1f}%" '
            f'title="{_esc(r["پرونده"])} — {_num(r["سن (روز)"],1)} روز؛ {_esc(r["هشدار"] or "بدون مقایسهٔ تاریخی")}"></span>'
            for r in g.to_dict("records"))
        lanes.append(f'<div class="lane"><div class="lane-name" title="{_esc(stage)}">{_esc(stage)}'
                     f' <small>({len(g)})</small></div>'
                     f'<div class="lane-track">{marks}{dots}</div></div>')
    scale = (f'<div class="note" style="text-align:left;direction:ltr">0 … {_num(top,1)} روز</div>')
    legend = ('<div class="gsi-legend">'
              f'<span><i style="background:{T.BRAND_TEAL};height:9px;width:9px;border-radius:50%"></i>پروندهٔ باز</span>'
              f'<span><i style="background:{ALERT_INK};height:9px;width:9px;border-radius:50%"></i>گذشته از صدک ۸۵ تاریخی</span>'
              f'<span><i style="background:{BENCH_INK}"></i>میانه تاریخی همین مرحله</span></div>')
    return panel(title, "".join(lanes) + scale + legend,
                 "صدک‌ها از رفتار گذشتهٔ همین سازمان می‌آیند؛ «هدف» نیستند. مرحله‌ای که مبنای تاریخی ندارد، مقایسه‌ای هم ندارد.")


# ══════════════════════════════════════════════════════════════════════════
#  توزیع زمان چرخه / دوباره‌کاری / تحویل — فهرست رتبه‌ای
# ══════════════════════════════════════════════════════════════════════════
def _rank_rows(rows: Sequence[dict], label_key: str, value_key: str,
               detail: str = "", unit: str = "") -> str:
    top = max([float(r.get(value_key) or 0) for r in rows] or [1]) or 1
    out = []
    for r in rows:
        v = float(r.get(value_key) or 0)
        pct = min(100, max(3, v / top * 100))
        out.append(f'<div class="rank-row"><div class="rank-label">{_esc(r.get(label_key))}</div>'
                   f'<div class="rank-track"><span style="width:{pct:.1f}%"></span></div>'
                   f'<b>{_num(v, 1)}{_esc(unit)}</b>'
                   f'<small>{_esc(detail.format(**r) if detail else "")}</small></div>')
    return '<div class="rank-list">' + "".join(out) + '</div>'


def cycle_percentiles_html(cyc: Optional[pd.DataFrame]) -> str:
    title = "توزیع زمان چرخه — صدک‌های مشاهده‌شده"
    if not isinstance(cyc, pd.DataFrame) or cyc.empty:
        return _why(title, "پروندهٔ بسته‌شده‌ای با زمان چرخهٔ قابل محاسبه نیست؛ صدک ساخته نمی‌شود.")
    rows = cyc.head(12).to_dict("records")
    body = _rank_rows(rows, "گروه", "صدک ۸۵ (روز)",
                      "میانه {صدک ۵۰ (روز)} · صدک ۹۵ {صدک ۹۵ (روز)} · {پرونده بسته} پرونده بسته", " روز")
    return panel(title, body,
                 "میله بر اساس صدک ۸۵ است: «۸۵٪ پرونده‌ها تا این عدد بسته شده‌اند». گروه با کمتر از ۳ مشاهده صدک نمی‌گیرد.")


def rework_html(rw: Optional[pd.DataFrame]) -> str:
    title = "دوباره‌کاری — فعالیتی که تکرار می‌شود"
    if not isinstance(rw, pd.DataFrame) or rw.empty:
        return _why(title, "در Event Log این دامنه، هیچ پرونده‌ای یک فعالیت را دوبار ثبت نکرده است.")
    body = _rank_rows(rw.head(12).to_dict("records"), "فعالیت", "کل تکرار اضافه",
                      "{پرونده با تکرار} پرونده · بیشترین تکرار {بیشترین تکرار در یک پرونده}")
    return panel(title, body,
                 "تکرار یک فعالیت لزوماً خطا نیست؛ ولی جایی است که باید علت پرسیده شود.")


def handoff_html(ho: Optional[pd.DataFrame]) -> str:
    title = "تحویل بین واحدها — کار کجا دست‌به‌دست می‌شود"
    if not isinstance(ho, pd.DataFrame) or ho.empty:
        return _why(title, "ستون واحد سازمانی/منبع در Event Log این دامنه پر نیست؛ مسیر تحویل ساخته نمی‌شود.")
    rows = [{**r, "_pair": f'{r["از"]} ← {r["به"]}'} for r in ho.head(12).to_dict("records")]
    body = _rank_rows(rows, "_pair", "تعداد تحویل",
                      "{پرونده} پرونده · میانه فاصله {میانه فاصله (روز)} روز")
    return panel(title, body,
                 "فاصلهٔ زیاد بین دو واحد، زمان انتظار است نه زمان کار.")


def stage_coverage_html(cov: Optional[pd.DataFrame]) -> str:
    title = "پوشش شاهد در هر مرحله"
    if not isinstance(cov, pd.DataFrame) or cov.empty:
        return _why(title, "ماتریس مرحله‌ای در این اجرا ساخته نشده است.")
    rows = []
    for r in cov.to_dict("records"):
        have = int(r["پرونده دارای شاهد"] or 0)
        miss = int(r["پرونده بدون شاهد"] or 0)
        total = max(have + miss, 1)
        rows.append(f'<div class="cov-row"><span title="{_esc(r["مرحله"])}">{_esc(r["مرحله"])}</span>'
                    f'<span class="cov-bar"><b style="width:{have/total*100:.1f}%" '
                    f'title="{have} پرونده دارای شاهد"></b>'
                    f'<i style="width:{miss/total*100:.1f}%" title="{miss} پرونده بدون شاهد"></i></span>'
                    f'<b>{_num(r["پوشش (٪)"],1)}٪</b></div>')
    legend = (f'<div class="gsi-legend"><span><i style="background:{T.BRAND_TEAL}"></i>دارای شاهد</span>'
              f'<span><i style="background:{T.BORDER}"></i>بدون شاهد (اندازه‌گیری نشده)</span></div>')
    return panel(title, "".join(rows) + legend,
                 "«بدون شاهد» یعنی اندازه‌گیری نشده، نه انجام‌نشده. این دو را یکی گرفتن، همان تصمیم اشتباه است.")


#: کلید نما → تابع رندر. ترتیب همان ترتیبی است که در Composer دیده می‌شود.
RENDERERS = {
    "cfd": ("cfd", cumulative_flow_html),
    "throughput": ("throughput", throughput_html),
    "aging_wip": ("aging_wip", aging_wip_html),
    "cycle_percentiles": ("cycle_percentiles", cycle_percentiles_html),
    "rework": ("rework", rework_html),
    "handoff": ("handoff", handoff_html),
    "stage_coverage": ("stage_coverage", stage_coverage_html),
}


def render(view: str, extras) -> Optional[str]:
    """HTML یک نمای Kanban/Scrum، یا None اگر این کلید از این ماژول نیست."""
    spec = RENDERERS.get(view)
    if spec is None:
        return None
    from ..report.process_insights import build_all
    cache = getattr(extras, "_gsi_process_insights", None)
    if cache is None:
        cache = build_all(extras)
        try:
            setattr(extras, "_gsi_process_insights", cache)
        except (AttributeError, TypeError):
            pass
    key, fn = spec
    return fn(cache.get(key))
