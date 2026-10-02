# -*- coding: utf-8 -*-
"""آیکن‌های خطی و اجزای مینیمال (کاشی آیکن، گیج حلقه‌ای، تایم‌لاین نقطه‌ای).

زبان بصری از فایل مرجع مینیمال: آیکن خطی نازک با گوشه گرد داخل کاشی
مربعِ گرد با سایه نرم دوطرفه، گیج دایره‌ای با کمان گرادیانی، تایم‌لاین با
نقطه‌های روی خط و برچسب کپسولی، کارت سفید بدون مرز.

* همه آیکن‌ها ``stroke="currentColor"`` دارند؛ رنگ از CSS می‌آید.
* همه رنگ‌ها از ``gsi.design.tokens``؛ هیچ هگز دستی.
* خروجی رشته HTML/SVG مستقل است: هم در Streamlit (``unsafe_allow_html``)
  و هم در گزارش HTML آفلاین (بدون فونت یا اسکریپت بیرونی) کار می‌کند.
"""
from __future__ import annotations

import contextlib
import contextvars
import html
import math
import urllib.parse
import zlib
from typing import Iterable, Iterator, Optional, Sequence, Tuple

from gsi.design import tokens as T

# ── آیکن‌ها: 24×24، خط 1.7، بدون پُر ─────────────────────────────────────
_P = {
    "home": '<path d="M4 11.5 12 5l8 6.5"/><path d="M6.5 10v9h11v-9"/><path d="M10 19v-5h4v5"/>',
    "file": '<path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10A.5.5 0 0 1 6 20V4a.5.5 0 0 1 .5-.5Z"/><path d="M14 3.5V8h4"/><path d="M9 12.5h6M9 16h4"/>',
    "stamp": '<path d="M9 4.5h6l-1 6h-4Z"/><path d="M5 14.5h14v3H5Z"/><path d="M7 20.5h10"/>',
    "queue": '<rect x="4" y="5" width="16" height="3.5" rx="1.7"/><rect x="4" y="10.3" width="11" height="3.5" rx="1.7"/><rect x="4" y="15.6" width="7" height="3.5" rx="1.7"/>',
    "coins": '<ellipse cx="9" cy="7" rx="5" ry="2.3"/><path d="M4 7v4c0 1.3 2.2 2.3 5 2.3s5-1 5-2.3V7"/><path d="M10 15.6c.8 1 2.6 1.7 5 1.7 2.8 0 5-1 5-2.3v-4c0-1.2-1.9-2.2-4.4-2.3"/><path d="M20 15v4c0 1.3-2.2 2.3-5 2.3-2.3 0-4.2-.7-4.8-1.6"/>',
    "exchange": '<path d="M5 8.5h13l-3.5-3.5"/><path d="M19 15.5H6l3.5 3.5"/>',
    "bank": '<path d="M3.5 9 12 4l8.5 5"/><path d="M5.5 9.5v7.5M10 9.5v7.5M14 9.5v7.5M18.5 9.5v7.5"/><path d="M3.5 19.5h17"/>',
    "send": '<path d="M20.5 3.5 10 14"/><path d="M20.5 3.5 14 20.5l-4-6.5-6.5-4Z"/>',
    "ship": '<path d="M3.5 15.5 5.5 19h13l2-3.5Z"/><path d="M6.5 15.5V10h11v5.5"/><path d="M12 10V5.5M9.5 7.5h5"/>',
    "box": '<path d="M12 3.5 20 7.5v9L12 20.5 4 16.5v-9Z"/><path d="M4 7.5l8 4 8-4M12 11.5v9"/>',
    "customs": '<path d="M12 3.5 19 6v5.5c0 4.3-3 7.6-7 9-4-1.4-7-4.7-7-9V6Z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
    "doc_check": '<rect x="5.5" y="3.5" width="13" height="17" rx="2"/><path d="M9 3.5V6h6V3.5"/><path d="M9 13l2 2 4-4"/>',
    "shield": '<path d="M12 3.5 19 6v5.5c0 4.3-3 7.6-7 9-4-1.4-7-4.7-7-9V6Z"/>',
    "alert": '<path d="M12 4.5 20.5 19h-17Z"/><path d="M12 10v4.2M12 16.8v.1"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="4"/><path d="M9.5 9.5h5v5h-5Z"/>',
    "clock": '<circle cx="12" cy="12" r="8"/><path d="M12 7.5V12l3 2"/>',
    "calendar": '<rect x="4" y="5.5" width="16" height="14" rx="2.5"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.7l1-1"/>',
    "flow": '<circle cx="6" cy="6" r="2.2"/><circle cx="18" cy="12" r="2.2"/><circle cx="6" cy="18" r="2.2"/><path d="M8.2 6.5c4.8.5 7.3 2.2 7.6 4.3M8.2 17.5c4.8-.5 7.3-2.2 7.6-4.3"/>',
    "chart": '<path d="M4 19.5h16"/><path d="M4 15.5c2.5 0 3-5 5.5-5s3 3.5 5.5 3.5 3-6 5-6"/>',
    "bars": '<path d="M4 19.5h16"/><rect x="6" y="11" width="3" height="6" rx="1.2"/><rect x="11" y="7" width="3" height="10" rx="1.2"/><rect x="16" y="13" width="3" height="4" rx="1.2"/>',
    "database": '<ellipse cx="12" cy="6" rx="7" ry="2.5"/><path d="M5 6v12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V6"/><path d="M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5"/>',
    "users": '<circle cx="9" cy="8.5" r="3"/><path d="M3.5 19c.6-3 2.8-4.5 5.5-4.5s4.9 1.5 5.5 4.5"/><path d="M15 5.8a3 3 0 0 1 0 5.4M17 14.7c1.8.6 3 2 3.5 4.3"/>',
    "book": '<path d="M5 4.5h5.5a2 2 0 0 1 2 2V20a1.5 1.5 0 0 0-1.5-1.5H5Z"/><path d="M19 4.5h-5a2 2 0 0 0-2 2V20a1.5 1.5 0 0 1 1.5-1.5H19Z"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="m15.5 15.5 4 4"/>',
    "layers": '<path d="M12 4 20 8.5l-8 4.5-8-4.5Z"/><path d="m4 12.5 8 4.5 8-4.5M4 16.5 12 21l8-4.5"/>',
    "flag": '<path d="M5.5 20.5V4.5"/><path d="M5.5 5h11l-2 3.5 2 3.5h-11"/>',
    "truck": '<path d="M3.5 6.5h10v9h-10Z"/><path d="M13.5 9.5h4l3 3v3h-7"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/>',
    "warehouse": '<path d="M3.5 9 12 4.5 20.5 9v11h-17Z"/><path d="M7.5 20v-7h9v7M7.5 16h9"/>',
    "check": '<circle cx="12" cy="12" r="8"/><path d="m8.5 12.3 2.4 2.4 4.6-5"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="2.8"/>',
    "trend": '<path d="M4 17l5-5 3.5 3.5L20 8"/><path d="M15 8h5v5"/>',
    "gauge": '<path d="M4.5 16a7.5 7.5 0 1 1 15 0"/><path d="m12 16 3.5-4.5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 3.5v2.5M12 18v2.5M3.5 12H6M18 12h2.5M6 6l1.8 1.8M16.2 16.2 18 18M6 18l1.8-1.8M16.2 7.8 18 6"/>',
    "wallet": '<rect x="3.5" y="6" width="17" height="13" rx="3"/><path d="M3.5 10h17"/><circle cx="16.5" cy="14.5" r="1"/>',
    "dot": '<circle cx="12" cy="12" r="3.5"/>',
}

#: نمادهای قدیمی ← آیکن خطی (کارت‌های KPI و برچسب‌ها)
GLYPH_TO_ICON = {
    "⏹": "stop", "⬤": "alert", "◤": "trend", "◆": "eye", "✓": "check", "⏱": "clock",
    "◈": "box", "₪": "wallet", "€": "exchange", "▦": "database", "⛓": "flow", "◉": "gauge",
}

#: مراحل چرخه ارز ← آیکن
STAGE_ICON = {
    "REG_FILE": "file", "ORDER_REG": "stamp", "ALLOC_QUEUE": "queue", "ALLOCATION_QUEUE": "queue",
    "SWIFT_CONVERSION": "send", "CUSTOMS": "box", "ALLOCATION": "coins",
    "FX_PURCHASE": "exchange", "FUNDING": "bank", "SWIFT": "send", "SHIPMENT": "ship",
    "ARRIVAL": "box", "CLEARANCE": "customs", "BANK_DOCS": "doc_check", "SETTLEMENT": "shield",
    "CLOSED": "check",
}

NAMES: Tuple[str, ...] = tuple(_P)

_TONES = {
    "brand": (T.BRAND_TEAL, T.TEAL_WASH),
    "deep": (T.TEAL_INK, T.TEAL_WASH),
    "muted": (T.TEXT_MUTED, T.SURFACE_SUNKEN),
    "danger": (T.STATUS["stockout"].ink, T.SURFACE_RAISED),
    "critical": (T.STATUS["critical"].ink, T.SURFACE_RAISED),
    "serious": (T.STATUS["serious"].ink, T.SURFACE_RAISED),
    "good": (T.STATUS["good"].ink, T.SURFACE_RAISED),
}


#: حالت «آیکن CSS»: ``st.html`` در Streamlit هر ``<svg>`` را حذف می‌کند (DOMPurify با
#: پروفایل HTML)، پس اجزایی که هم در Studio و هم در گزارش HTML رندر می‌شوند آیکن
#: و گیج را با ماسک/گرادیان CSS می‌سازند. پیش‌فرض همان SVG درون‌خطی است.
_CSS_MODE: contextvars.ContextVar[bool] = contextvars.ContextVar("gsi_css_icons", default=False)


@contextlib.contextmanager
def css_icons(on: bool = True) -> Iterator[None]:
    """در این بلوک ``icon``/``icon_tile``/``kpi_tile``/``stepper``/``ring`` بدون SVG
    خروجی می‌دهند؛ CSS لازم در ``css_icons_css()`` است."""
    token = _CSS_MODE.set(on)
    try:
        yield
    finally:
        _CSS_MODE.reset(token)


def css_mode() -> bool:
    return _CSS_MODE.get()


def _key(name: str) -> str:
    k = GLYPH_TO_ICON.get(name, name)
    return k if k in _P else "dot"


def icon(name: str, size: int = 20, title: str = "", stroke: float = 1.7) -> str:
    """یک آیکن SVG خطی. نام ناشناخته ← نقطه (هرگز خطا نمی‌دهد)."""
    body = _P.get(GLYPH_TO_ICON.get(name, name), _P["dot"])
    t = f"<title>{html.escape(title)}</title>" if title else ""
    aria = f'role="img" aria-label="{html.escape(title)}"' if title else 'aria-hidden="true"'
    if _CSS_MODE.get():
        tip = f' title="{html.escape(title)}"' if title else ""
        return (f'<i class="mi-svg mi-ic mi-ic-{_key(name)}" style="width:{size}px;height:{size}px"'
                f' {aria}{tip}></i>')
    return (f'<svg class="mi-svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="{stroke}" stroke-linecap="round" '
            f'stroke-linejoin="round" {aria}>{t}{body}</svg>')


def tone_color(tone: str) -> str:
    return _TONES.get(tone, _TONES["brand"])[0]


def icon_tile(name: str, tone: str = "brand", size: int = 20, active: bool = False) -> str:
    """کاشی مربع گرد با سایه نرم و آیکن خطی در مرکز."""
    cls = "mi-tile is-active" if active else "mi-tile"
    return (f'<span class="{cls}" style="color:{tone_color(tone)}">'
            f'{icon(name, size)}</span>')


def ring(pct: Optional[float], size: int = 86, stroke: int = 8, label: str = "",
         sub: str = "", tone: str = "brand", uid: str = "", text: str = "") -> str:
    """گیج حلقه‌ای با کمان گرادیانی. ``pct=None`` یعنی نامعلوم: کمان رسم نمی‌شود."""
    r = (size - stroke) / 2
    c = 2 * math.pi * r
    gid = f"mig{uid or zlib.crc32(repr((label, sub, pct, size)).encode()) % 10**8}"
    known = pct is not None and not (isinstance(pct, float) and math.isnan(pct))
    p = max(0.0, min(float(pct), 100.0)) if known else 0.0
    over = known and float(pct) > 100.5
    a, b = (T.TEAL_PALETTE[3], T.TEAL_PALETTE[7]) if tone == "brand" else (tone_color(tone), tone_color(tone))
    if _CSS_MODE.get():
        return _css_ring(known, p, over, a, b, size, stroke, label, sub, text, pct)
    arc = ""
    if known and p > 0:
        arc = (f'<circle cx="{size/2}" cy="{size/2}" r="{r:.2f}" fill="none" stroke="url(#{gid})" '
               f'stroke-width="{stroke}" stroke-linecap="round" stroke-dasharray="{c * p / 100:.2f} {c:.2f}" '
               f'transform="rotate(-90 {size/2} {size/2})"/>')
    track_dash = "" if known else ' stroke-dasharray="3 5"'
    val = html.escape(text) if text else (f"{float(pct):.0f}٪" if known else "—")
    label_html = f'<div class="mi-ring-lab">{html.escape(label)}</div>' if label else ""
    sub_html = f'<div class="mi-ring-sub">{html.escape(sub)}</div>' if sub else ""
    warn = f' style="color:{T.STATUS["critical"].ink}"' if over else ""
    fs = max(10, min(15, size // 6))
    return (f'<div class="mi-ring" style="--ring:{size}px;font-size:{fs}px">'
            f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" aria-hidden="true">'
            f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs>'
            f'<circle cx="{size/2}" cy="{size/2}" r="{r:.2f}" fill="none" stroke="{T.SURFACE_SUNKEN}" '
            f'stroke-width="{stroke}"{track_dash}/>{arc}</svg>'
            f'<div class="mi-ring-val"{warn}>{val}</div></div>{label_html}{sub_html}')


def _css_ring(known: bool, p: float, over: bool, a: str, b: str, size: int, stroke: int,
              label: str, sub: str, text: str, pct) -> str:
    """همان گیج ``ring`` با ``conic-gradient``؛ نامعلوم ← حلقه خط‌چین بدون کمان."""
    val = html.escape(text) if text else (f"{float(pct):.0f}٪" if known else "—")
    label_html = f'<div class="mi-ring-lab">{html.escape(label)}</div>' if label else ""
    sub_html = f'<div class="mi-ring-sub">{html.escape(sub)}</div>' if sub else ""
    warn = f' style="color:{T.STATUS["critical"].ink}"' if over else ""
    fs = max(10, min(15, size // 6))
    cls = "mi-ring mi-cring" + ("" if known else " is-na")
    return (f'<div class="{cls}" style="--ring:{size}px;--sw:{stroke}px;--p:{p:.1f}%;--a:{a};--b:{b};'
            f'font-size:{fs}px"><div class="mi-ring-val"{warn}>{val}</div></div>'
            f'{label_html}{sub_html}')


def stepper(steps: Sequence[Tuple], show_icons: bool = True) -> str:
    """تایم‌لاین نقطه‌ای. هر گام (کد، برچسب، وضعیت[، عدد]) با وضعیت
    ``done`` / ``current`` / ``gap`` / ``todo``؛ عدد اختیاری بالای نقطه می‌نشیند."""
    items = []
    for st in steps:
        code, lab, state = st[0], st[1], st[2]
        n = st[3] if len(st) > 3 else None
        ic = icon(STAGE_ICON.get(code, "dot"), 16) if show_icons else ""
        badge = f'<span class="mi-step-n">{html.escape(str(n))}</span>' if n is not None else ""
        items.append(f'<li class="mi-step is-{state}">{badge}<span class="mi-dot">{ic}</span>'
                     f'<span class="mi-step-lab">{html.escape(lab)}</span></li>')
    return f'<ol class="mi-stepper">{"".join(items)}</ol>'


def kpi_tile(name: str, label: str, value: str, sub: str = "", tone: str = "brand") -> str:
    """کارت KPI مینیمال: کاشی آیکن + عدد + برچسب."""
    s = f'<div class="mi-kpi-sub">{html.escape(sub)}</div>' if sub else ""
    return (f'<div class="mi-kpi">{icon_tile(name, tone)}'
            f'<div class="mi-kpi-body"><div class="mi-kpi-val">{html.escape(str(value))}</div>'
            f'<div class="mi-kpi-lab">{html.escape(label)}</div>{s}</div></div>')


def minimal_css() -> str:
    """CSS اجزای مینیمال؛ فقط رنگ توکن‌ها و سایه نرم ELEVATION."""
    raised, inset, overlay = T.ELEVATION["raised"], T.ELEVATION["inset"], T.ELEVATION["overlay"]
    return f"""
.mi-svg {{ display:block; flex:none; }}
.mi-tile {{ display:inline-flex; align-items:center; justify-content:center; width:42px; height:42px;
  border-radius:{T.RADIUS['md']}px; background:{T.SURFACE_RAISED}; box-shadow:{raised}; flex:none; }}
.mi-tile.is-active {{ background:linear-gradient(135deg,{T.TEAL_PALETTE[3]},{T.TEAL_PALETTE[7]});
  color:{T.TEXT_ON_BRAND} !important; box-shadow:{overlay}; }}
.mi-kpis {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); gap:14px; margin:6px 0 16px; }}
.mi-kpi {{ display:flex; gap:12px; align-items:center; padding:14px 16px; background:{T.SURFACE_RAISED};
  border-radius:{T.RADIUS['lg']}px; box-shadow:{raised}; }}
.mi-kpi-val {{ font-size:22px; font-weight:700; color:{T.TEXT}; line-height:1.15; }}
.mi-kpi-lab {{ font-size:12px; color:{T.TEXT_SECONDARY}; margin-top:2px; }}
.mi-kpi-sub {{ font-size:11px; color:{T.TEXT_MUTED}; }}
.mi-ring {{ position:relative; width:var(--ring); height:var(--ring); margin:0 auto; }}
.mi-ring svg {{ display:block; }}
.mi-ring-val {{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
  font-weight:700; font-size:inherit; color:{T.TEAL_INK}; text-align:center; line-height:1.1; }}
.mi-ring-lab {{ text-align:center; font-size:12px; color:{T.TEXT_SECONDARY}; margin-top:6px; }}
.mi-ring-sub {{ text-align:center; font-size:11px; color:{T.TEXT_MUTED}; }}
.mi-stepper {{ list-style:none; display:flex; gap:0; padding:18px 4px 6px; margin:0 0 10px; overflow-x:auto;
  background:{T.SURFACE_RAISED}; border-radius:{T.RADIUS['xl']}px; box-shadow:{raised}; }}
.mi-step {{ position:relative; flex:1 1 0; min-width:60px; display:flex; flex-direction:column;
  align-items:center; gap:8px; text-align:center; }}
.mi-step::before {{ content:""; position:absolute; top:15px; inset-inline-end:50%; width:100%; height:3px;
  background:{T.SURFACE_SUNKEN}; border-radius:3px; z-index:0; }}
.mi-step:first-child::before {{ display:none; }}
.mi-step.is-done::before, .mi-step.is-current::before {{
  background:linear-gradient(270deg,{T.TEAL_PALETTE[3]},{T.TEAL_PALETTE[6]}); }}
[dir="ltr"] .mi-step.is-done::before, [dir="ltr"] .mi-step.is-current::before {{
  background:linear-gradient(90deg,{T.TEAL_PALETTE[3]},{T.TEAL_PALETTE[6]}); }}
.mi-dot {{ position:relative; z-index:1; width:32px; height:32px; border-radius:50%; display:flex;
  align-items:center; justify-content:center; background:{T.SURFACE_RAISED}; color:{T.TEXT_MUTED};
  box-shadow:{raised}; }}
.mi-step.is-done .mi-dot {{ color:{T.BRAND_TEAL}; box-shadow:{inset}; }}
.mi-step.is-current .mi-dot {{ color:{T.TEXT_ON_BRAND}; box-shadow:{overlay};
  background:linear-gradient(135deg,{T.TEAL_PALETTE[3]},{T.TEAL_PALETTE[7]}); }}
.mi-step.is-gap .mi-dot {{ color:{T.STATUS['serious'].ink}; outline:2px dashed {T.STATUS['serious'].ink};
  outline-offset:2px; }}
.mi-step-n {{ font-size:17px; font-weight:800; color:{T.TEAL_INK}; line-height:1; }}
.mi-stepper:has(.mi-step-n) .mi-step::before {{ top:39px; }}
.mi-step-lab {{ font-size:11px; color:{T.TEXT_SECONDARY}; line-height:1.4; padding:3px 8px;
  border-radius:{T.RADIUS['pill']}px; }}
.mi-step.is-current .mi-step-lab {{ background:{T.TEAL_INK}; color:{T.TEXT_ON_BRAND}; font-weight:700; }}
.mi-card {{ background:{T.SURFACE_RAISED}; border-radius:{T.RADIUS['xl']}px; box-shadow:{raised};
  padding:16px 18px; }}
.mi-row {{ display:flex; gap:14px; align-items:center; }}
.mi-title {{ display:flex; gap:10px; align-items:center; font-weight:700; color:{T.TEXT}; margin:14px 0 8px; }}
"""


def section_title(name: str, text: str) -> str:
    return f'<div class="mi-title">{icon_tile(name, size=18)}<span>{html.escape(text)}</span></div>'


def rings_row(items: Iterable[Tuple[Optional[float], str, str]], size: int = 86) -> str:
    cells = "".join(f'<div class="mi-card" style="text-align:center">{ring(p, size, label=l, sub=s, uid=str(i))}</div>'
                    for i, (p, l, s) in enumerate(items))
    return f'<div class="mi-kpis">{cells}</div>'


def mask_url(name: str) -> str:
    """آیکن به‌صورت data-URI برای ``mask-image`` (رنگ از ``currentColor`` عنصر)."""
    body = _P.get(GLYPH_TO_ICON.get(name, name), _P["dot"])
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" '
           f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
    return 'url("data:image/svg+xml;charset=utf-8,' + urllib.parse.quote(svg, safe="") + '")'


def _mask_data(name: str) -> str:
    """data-URI فشرده (فقط کاراکترهای لازم کد می‌شوند و هیچ ``<`` خامی نمی‌ماند؛
    DOMPurify تگ ``<style>`` حاوی ``<`` را حذف می‌کند)."""
    body = _P[_key(name)].replace('"', "'")
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
           f"stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>{body}</svg>")
    for a, b in (("%", "%25"), ("#", "%23"), ("<", "%3C"), (">", "%3E"), ('"', "%22")):
        svg = svg.replace(a, b)
    return f'url("data:image/svg+xml,{svg}")'


def css_icons_css(names: Optional[Sequence[str]] = None) -> str:
    """CSS حالت ``css_icons``: کلاس ماسک برای هر آیکن + گیج conic-gradient."""
    rules = [
        ".mi-ic{display:inline-block;flex:none;vertical-align:middle;background-color:currentColor;"
        "-webkit-mask:var(--mi-m) no-repeat center/contain;mask:var(--mi-m) no-repeat center/contain;"
        "-webkit-print-color-adjust:exact;print-color-adjust:exact}",
        ".mi-cring::before{content:'';position:absolute;inset:0;border-radius:50%;"
        f"background:conic-gradient(var(--a) 0,var(--b) var(--p),{T.SURFACE_SUNKEN} 0);"
        "-webkit-mask:radial-gradient(farthest-side,transparent calc(100% - var(--sw)),black calc(100% - var(--sw) + .5px));"
        "mask:radial-gradient(farthest-side,transparent calc(100% - var(--sw)),black calc(100% - var(--sw) + .5px));"
        "-webkit-print-color-adjust:exact;print-color-adjust:exact}",
        f".mi-cring.is-na::before{{background:none;border:var(--sw) dashed {T.SURFACE_SUNKEN};"
        "-webkit-mask:none;mask:none;box-sizing:border-box}",
    ]
    rules += [f".mi-ic-{n}{{--mi-m:{_mask_data(n)}}}" for n in (names or NAMES)]
    return "\n".join(rules)


def nth_icons_css(item_selector: str, names: Sequence[str], size: int = 18, inner: str = "") -> str:
    """آیکن خطی پیش از n-امین عنصر (ناوبری رادیویی، تب‌ها) — فقط CSS، بدون فونت آیکن.

    فونت آیکن Streamlit در بعضی کلاینت‌ها با فونت فارسی بازنویسی می‌شود و نام
    آیکن به‌صورت متن دیده می‌شود؛ ماسک SVG به هیچ فونتی وابسته نیست."""
    rules = [f"{item_selector}{inner}::before{{content:'';flex:none;width:{size}px;height:{size}px;"
             f"background-color:currentColor;-webkit-mask:no-repeat center/contain;mask:no-repeat center/contain;"
             f"margin-inline-end:8px;display:inline-block;vertical-align:middle}}"]
    for i, n in enumerate(names, 1):
        u = mask_url(n)
        rules.append(f"{item_selector}:nth-child({i}){inner}::before{{-webkit-mask-image:{u};mask-image:{u}}}")
    return "\n".join(rules)
