# -*- coding: utf-8 -*-
"""GSI Design System — لایه ۲ و ۴: Auto Layout و Responsive به زبان CSS.

## Auto Layout در فیگما ↔ CSS

Auto Layout فیگما سه چیز است: **جهت**، **فاصله بین آیتم‌ها**، و **padding
ظرف**. هر سه معادل مستقیم در Flexbox دارند. این فایل همان سه مفهوم را به
صورت اولیه‌های نام‌دار می‌دهد تا طراح و توسعه‌دهنده یک واژگان داشته باشند:

    فیگما                      CSS اینجا
    ─────────────────────────  ──────────────────────────────
    Vertical auto layout       .stack        (+ .stack-{gap})
    Horizontal auto layout     .cluster      (+ .cluster-{gap})
    Space between              .split
    Wrap                       .cluster (پیش‌فرض wrap است)
    Fill container             .grow
    Hug contents               .hug
    Grid                       .grid-auto    (minmax responsive)

نتیجه عملی: هیچ‌جای گزارش «۱۳ پیکسل چشمی» نداریم. هر فاصله یک نام دارد و
آن نام در فیگما هم همان عدد است.

## Responsive

چهار نقطه شکست (``sm/md/lg/xl``) از :mod:`gsi.design.tokens` می‌آیند.
شبکه‌ها با ``minmax()`` خودشان می‌شکنند، پس بیشتر صفحه بدون media query
هم درست می‌ماند؛ media queryها فقط جایی هستند که **چیدمان** باید عوض شود،
نه فقط اندازه.

چاپ یک نقطه شکست واقعی است، نه فکر بعدی: همین گزارش با «چاپ/PDF» به دست
مدیر می‌رسد.
"""
from __future__ import annotations

__contract__ = 1

import re

from . import tokens as T


def _vars() -> str:
    """توکن‌ها به‌صورت CSS Custom Property — همان نام‌های فیگما."""
    rows = []
    add = rows.append
    add(f"--surface:{T.SURFACE_PAGE}")
    add(f"--raised:{T.SURFACE_RAISED}")
    add(f"--sunken:{T.SURFACE_SUNKEN}")
    add(f"--inverse:{T.SURFACE_INVERSE}")
    add(f"--paper:{T.SURFACE_PAPER}")
    add(f"--paper-soft:{T.SURFACE_PAPER_SOFT}")
    add(f"--paper-rule:{T.PAPER_RULE}")
    add(f"--pencil:{T.PENCIL}")
    add(f"--aqua-mist:{T.AQUA_MIST}")
    add(f"--lapis-wash:{T.LAPIS_WASH}")
    add(f"--border:{T.BORDER}")
    add(f"--border-strong:{T.BORDER_STRONG}")
    add(f"--focus:{T.BORDER_FOCUS}")
    add(f"--text:{T.TEXT}")
    add(f"--text-2:{T.TEXT_SECONDARY}")
    add(f"--text-3:{T.TEXT_MUTED}")
    add(f"--on-dark:{T.TEXT_ON_DARK}")
    add(f"--navy:{T.BRAND_NAVY}")
    add(f"--teal:{T.BRAND_TEAL}")
    add(f"--gold:{T.BRAND_GOLD}")
    add(f"--teal-ink:{T.TEAL_INK}")
    add(f"--gold-ink:{T.GOLD_INK}")
    add(f"--teal-wash:{T.TEAL_WASH}")
    add(f"--gold-wash:{T.GOLD_WASH}")
    add(f"--navy-wash:{T.NAVY_WASH}")
    for s in T.STATUS_SCALE:
        add(f"--st-{s.key}:{s.fill}")
        add(f"--st-{s.key}-ink:{s.ink}")
        add(f"--st-{s.key}-wash:{s.wash}")
    for i, c in enumerate(T.CATEGORICAL, 1):
        add(f"--series-{i}:{c}")
    for k, v in T.SPACE.items():
        add(f"--sp-{k}:{v}px")
    for k, v in T.RADIUS.items():
        add(f"--r-{k}:{v}px")
    for k, v in T.ELEVATION.items():
        add(f"--e-{k}:{v}")
    for k, v in T.MOTION.items():
        add(f"--{k.replace('_', '-')}:{v}")
    add(f"--font:{T.FONT_STACK}")
    add(f"--container:{T.CONTAINER_MAX}px")
    return ";".join(rows)


def _type_classes() -> str:
    out = []
    for name, t in T.TYPE.items():
        track = f";letter-spacing:{t.track}px" if t.track else ""
        out.append(f".t-{name}{{font-size:{t.size}px;font-weight:{t.weight};"
                   f"line-height:{t.line}{track}}}")
    return "\n".join(out)


def _auto_layout() -> str:
    """اولیه‌های Auto Layout — معادل مستقیم چیدمان خودکار فیگما."""
    gaps = "\n".join(
        f".stack-{k}{{gap:{v}px}} .cluster-{k}{{gap:{v}px}}"
        for k, v in T.SPACE.items() if k not in ("none",))
    return f"""
.stack{{display:flex;flex-direction:column;gap:{T.SPACE['md']}px}}
.cluster{{display:flex;flex-direction:row;flex-wrap:wrap;gap:{T.SPACE['sm']}px;align-items:center}}
.split{{display:flex;flex-direction:row;flex-wrap:wrap;gap:{T.SPACE['sm']}px;
  align-items:center;justify-content:space-between}}
.grow{{flex:1 1 auto;min-width:0}}
.hug{{flex:0 0 auto}}
.grid-auto{{display:grid;gap:{T.SPACE['sm']}px;
  grid-template-columns:repeat(auto-fit,minmax(var(--col,240px),1fr))}}
{gaps}
"""


def _a11y() -> str:
    """حلقه فوکوس، ناحیه لمسی، متن فقط-برای-صفحه‌خوان.

    حلقه فوکوس ``:focus-visible`` است نه ``:focus``: کاربر ماوس نباید بعد
    از هر کلیک حلقه ببیند، ولی کاربر کیبورد باید همیشه بداند کجاست.
    ``outline-offset`` مثبت است تا حلقه روی خود مرز کنترل نیفتد و گم نشود.
    """
    return f"""
:where(a,button,input,select,textarea,[tabindex]):focus-visible{{
  outline:3px solid var(--focus);outline-offset:2px;border-radius:var(--r-sm)}}
:where(a,button,input,select,textarea,[tabindex]):focus:not(:focus-visible){{outline:none}}
.sr-only{{position:absolute;width:1px;height:1px;padding:0;margin:-1px;
  overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}}
.skip-link{{position:absolute;right:{T.SPACE['md']}px;top:-64px;z-index:99;
  background:var(--navy);color:var(--on-dark);padding:{T.SPACE['sm']}px {T.SPACE['md']}px;
  border-radius:var(--r-md);font-weight:700;transition:top var(--dur-short) var(--ease-standard)}}
.skip-link:focus{{top:{T.SPACE['md']}px}}
button,select,input,.chip,.tabbtn{{min-height:36px}}
[aria-busy="true"]{{cursor:progress}}
"""


def _motion() -> str:
    """حرکت: فقط transform و opacity؛ روی GPU و بدون بازمحاسبه layout."""
    return f"""
@keyframes gsi-rise{{from{{opacity:0;transform:translate3d(0,12px,0)}}to{{opacity:1;transform:none}}}}
@keyframes gsi-grow-x{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@keyframes gsi-grow-y{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
@keyframes gsi-draw{{from{{stroke-dashoffset:var(--dash,1200)}}to{{stroke-dashoffset:0}}}}
@keyframes gsi-pop{{from{{opacity:0;transform:scale(.75)}}to{{opacity:1;transform:scale(1)}}}}
.reveal{{opacity:0}}
.reveal.in{{animation:gsi-rise var(--dur-medium) var(--ease-entrance) both;
  animation-delay:calc(min(var(--i,0),{T.STAGGER_MAX}) * var(--stagger))}}
.bar-mark{{transform-origin:right center;
  animation:gsi-grow-x var(--dur-medium) var(--ease-entrance) both;
  animation-delay:calc(min(var(--i,0),{T.STAGGER_MAX}) * var(--stagger))}}
.col-mark{{transform-origin:center bottom;
  animation:gsi-grow-y var(--dur-medium) var(--ease-entrance) both;
  animation-delay:calc(min(var(--i,0),{T.STAGGER_MAX}) * var(--stagger))}}
.line-mark{{stroke-dasharray:var(--dash,1200);
  animation:gsi-draw var(--dur-long) var(--ease-entrance) both}}
.dot-mark{{animation:gsi-pop var(--dur-short) var(--ease-entrance) both;
  animation-delay:calc(var(--i,0) * 5ms)}}
.card,.panel,.chartbox,.tabbtn,.btn,.chip,.kpi{{
  transition:transform var(--dur-short) var(--ease-standard),
             box-shadow var(--dur-short) var(--ease-standard),
             border-color var(--dur-micro) var(--ease-standard),
             background-color var(--dur-micro) var(--ease-standard),
             color var(--dur-micro) var(--ease-standard)}}
@media (prefers-reduced-motion:reduce){{
  *,*::before,*::after{{animation-duration:.001ms!important;animation-delay:0!important;
    transition-duration:.001ms!important;scroll-behavior:auto!important}}
  .reveal,.reveal.in{{opacity:1!important;transform:none!important}}
  .line-mark{{stroke-dashoffset:0!important}}
}}
"""


def _responsive() -> str:
    b = T.BREAKPOINT
    return f"""
.shell{{max-width:var(--container);margin-inline:auto;padding:{T.PAD_PAGE}px}}
@media (max-width:{b['lg'] - 1}px){{
  .grid-auto{{--col:220px}}
  .only-lg{{display:none!important}}
}}
@media (max-width:{b['md'] - 1}px){{
  .shell{{padding:{T.SPACE['sm']}px}}
  .grid-auto{{--col:100%}}
  .split{{flex-direction:column;align-items:stretch}}
  .t-display{{font-size:25px}} .t-h1{{font-size:21px}} .t-metric{{font-size:22px}}
  .toolbar label{{min-width:100%}}
  .only-md{{display:none!important}}
}}
@media (max-width:{b['sm'] - 1}px){{
  .t-h1{{font-size:19px}} .t-metric{{font-size:20px}}
  .hide-xs{{display:none!important}}
}}
@media print{{
  @page{{size:A4 landscape;margin:12mm}}
  .no-print,.tabbar,.toolbar,.pager,.btn,.chip{{display:none!important}}
  body{{background:#fff}}
  .reveal,.reveal.in,.bar-mark,.col-mark,.line-mark,.dot-mark{{
    animation:none!important;opacity:1!important;transform:none!important;
    stroke-dashoffset:0!important}}
  .panel,.card,.chartbox,.kpi{{box-shadow:none!important;break-inside:avoid;
    border:1px solid #c9d3d9}}
  .grid-auto{{--col:45%}}
  a[href]::after{{content:""}}
}}
@media (forced-colors:active){{
  .card,.panel,.chartbox,.kpi,.badge{{border:1px solid CanvasText}}
  .bar-mark,.col-mark{{forced-color-adjust:none}}
}}
"""


def _components() -> str:
    """ظاهر کامپوننت‌ها. رفتار و واریانت‌ها در ``components.py`` تعریف می‌شوند."""
    return f"""
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:linear-gradient(180deg,#fff 0%,var(--surface) 100%);color:var(--text);direction:rtl;
  font-family:var(--font);font-size:13px;line-height:1.75;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}}
h1,h2,h3,h4{{margin:0}} p{{margin:0}}

/* ── App bar: mostly white editorial masthead, not a SaaS hero banner ── */
.appbar{{position:relative;background:linear-gradient(180deg,#fff 0%,var(--paper-soft) 100%);
  color:var(--text);border:1px solid var(--paper-rule);border-radius:var(--r-xl);padding:{T.SPACE['xl']}px;
  box-shadow:var(--e-raised);overflow:hidden}}
.appbar::before{{content:"";position:absolute;right:0;top:0;width:8px;height:100%;background:var(--teal)}}
.appbar::after{{content:"";position:absolute;left:24px;bottom:15px;width:86px;height:2px;
  background:var(--gold);opacity:.55;transform:rotate(-1deg)}}
.appbar .eyebrow{{color:var(--teal-ink)}}
.appbar .sub{{color:var(--text-2)}}
.brandmark{{display:inline-flex;align-items:center;gap:{T.SPACE['xs']}px;font-weight:800}}
.brandmark i{{width:10px;height:10px;border-radius:3px;display:inline-block;
  background:var(--gold);box-shadow:0 0 0 3px rgba(199,154,74,.22)}}
.stat-pill{{display:flex;flex-direction:column;align-items:center;
  background:#fff;border:1px solid var(--border);
  border-radius:var(--r-md);padding:{T.SPACE['xs']}px {T.SPACE['md']}px;min-width:96px}}
.stat-pill b{{font-size:20px;font-weight:800;line-height:1.25}}
.stat-pill span{{font-size:11px;opacity:.88}}

/* ── Surfaces ── */
.panel{{background:var(--raised);border:1px solid var(--border);
  border-radius:var(--r-lg);padding:{T.PAD_PANEL}px;box-shadow:var(--e-raised)}}
.card,.kpi{{background:var(--raised);border:1px solid var(--border);
  border-radius:var(--r-md);padding:{T.PAD_CARD}px;box-shadow:var(--e-raised)}}
.card:hover,.kpi:hover,.chartbox:hover{{transform:translate3d(0,-2px,0);
  box-shadow:var(--e-overlay);border-color:var(--border-strong)}}
.kpi .l,.card .l{{font-size:12px;color:var(--text-2)}}
.kpi b,.card b{{display:block;font-size:26px;font-weight:800;margin-top:4px;
  letter-spacing:-.4px;font-variant-numeric:tabular-nums}}
.kpi .g,.card .g{{font-size:11px;color:var(--text-3);margin-top:4px}}
.kpi[data-tone]{{border-top:3px solid var(--tone,var(--teal))}}

/* ── Buttons: variant × size × state ── */
.btn{{display:inline-flex;align-items:center;justify-content:center;
  gap:{T.SPACE['xs']}px;border:1px solid transparent;border-radius:var(--r-md);
  padding:9px {T.SPACE['md']}px;font:inherit;font-weight:800;cursor:pointer;
  background:var(--navy);color:var(--on-dark);white-space:nowrap}}
.btn:hover{{transform:translate3d(0,-1px,0);box-shadow:var(--e-overlay)}}
.btn:active{{transform:translate3d(0,1px,0);box-shadow:none}}
.btn[disabled],.btn[aria-disabled="true"]{{opacity:.45;cursor:not-allowed;transform:none}}
.btn--primary{{background:var(--navy)}}
.btn--decision{{background:var(--gold);color:#2a1f05;border-color:var(--gold-ink)}}
.btn--secondary{{background:var(--raised);color:var(--teal-ink);border-color:var(--border-strong)}}
.btn--secondary:hover{{border-color:var(--teal);background:var(--teal-wash)}}
.btn--ghost{{background:transparent;color:var(--teal-ink);border-color:transparent}}
.btn--ghost:hover{{background:var(--teal-wash);box-shadow:none}}
.btn--sm{{padding:5px {T.SPACE['sm']}px;font-size:12px;min-height:32px}}

/* ── Badge / status pill ── */
.badge{{display:inline-flex;align-items:center;gap:6px;border-radius:var(--r-pill);
  padding:3px 10px;font-size:11.5px;font-weight:800;
  color:var(--tone-ink);background:var(--tone-wash);border:1px solid var(--tone-ink)}}
.badge i{{font-style:normal;width:14px;height:14px;display:inline-grid;place-items:center;
  border-radius:4px;background:var(--tone);color:#fff;font-size:9px;line-height:1}}
.badge--solid{{color:#fff;background:var(--tone);border-color:var(--tone-ink)}}
.badge--quiet{{background:transparent;border-color:var(--border-strong);color:var(--text-2)}}

/* ── Tabs ── */
.tabbar{{display:flex;gap:6px;overflow-x:auto;padding:{T.SPACE['xs']}px 0;
  border-bottom:1px solid var(--border);scrollbar-width:thin}}
.tabbtn{{border:1px solid var(--border);background:var(--raised);color:var(--teal-ink);
  border-radius:var(--r-md);padding:8px {T.SPACE['md']}px;white-space:nowrap;
  font:inherit;font-weight:700;cursor:pointer}}
.tabbtn:hover{{border-color:var(--teal)}}
.tabbtn[aria-selected="true"]{{background:var(--navy);color:var(--on-dark);border-color:var(--navy)}}

/* ── Form controls ── */
label{{font-size:12px;color:var(--text-2);min-width:150px}}
input,select{{width:100%;margin-top:5px;padding:8px 10px;border:1px solid var(--border-strong);
  border-radius:var(--r-sm);background:var(--raised);font:inherit;color:var(--text)}}
.toolbar{{background:var(--raised);border:1px solid var(--border);
  border-radius:var(--r-lg);padding:{T.SPACE['sm']}px}}
.chip{{border:1px solid var(--border-strong);background:var(--raised);color:var(--teal-ink);
  border-radius:var(--r-pill);padding:5px {T.SPACE['sm']}px;font:inherit;font-size:11.5px;
  font-weight:700;cursor:pointer}}
.chip:hover{{background:var(--navy);border-color:var(--navy);color:var(--on-dark)}}
.chip[aria-pressed="true"]{{background:var(--teal);border-color:var(--teal);color:#fff}}

/* ── Editorial / data-journalism accents (restrained 80/15/5 rule) ── */
.editorial-lead{{position:relative;background:var(--paper);border:1px solid var(--paper-rule);
  border-radius:var(--r-lg);padding:var(--sp-lg);box-shadow:none}}
.editorial-lead::after{{content:"";display:block;width:84px;height:2px;margin-top:12px;
  background:var(--teal);opacity:.7;transform:rotate(-.8deg);transform-origin:right}}
.annotation{{position:relative;padding:9px 14px 9px 10px;color:var(--text-2);font-size:12px;
  background:transparent;border-right:2px solid var(--gold);font-style:normal}}
.annotation::before{{content:"✎";color:var(--pencil);margin-left:7px;font-size:12px}}
.paper-note{{background:var(--paper-soft);border:1px solid var(--paper-rule);border-radius:var(--r-md);
  padding:var(--sp-md)}}
.story-rule{{height:1px;background:linear-gradient(90deg,transparent,var(--paper-rule) 15%,var(--paper-rule) 85%,transparent)}}

/* ── Table ── */
.tablewrap{{border:1px solid var(--border);border-radius:var(--r-md);overflow:auto;
  max-height:640px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{position:sticky;top:0;z-index:1;background:var(--navy);color:var(--on-dark);
  padding:10px;text-align:right;white-space:nowrap;font-weight:700}}
td{{padding:8px 10px;border-bottom:1px solid var(--border);color:var(--text-2);
  white-space:nowrap;font-variant-numeric:tabular-nums}}
tbody tr:nth-child(even) td{{background:#fbfcfd}}
tbody tr:hover td{{background:var(--teal-wash);color:var(--text)}}
.num{{text-align:left;direction:ltr}}

/* Task-first material cards: Figma mobile 6:54, existing design tokens. */
.material-mobile{{display:none}}
.material-card{{padding:14px;border:1px solid var(--border);border-radius:var(--r-md);background:var(--raised);overflow-wrap:anywhere}}
.material-card strong{{color:var(--navy);font-size:15px}}
.material-card p{{margin:6px 0;color:var(--text-2)}}
.material-card dl{{margin:10px 0 0}}
.material-card dt{{font-weight:700;color:var(--teal-ink);margin-top:10px}}
.material-card dd{{margin:4px 0;white-space:pre-wrap;line-height:1.75}}
.advisory-gaps td{{white-space:normal;min-width:170px;overflow-wrap:anywhere}}
@media(max-width:639px){{
 .material-mobile{{display:grid;gap:12px}}
 .material-table{{display:none}}
}}

/* ── Chart frame ── */
.chartbox{{position:relative;background:linear-gradient(180deg,var(--raised),var(--paper-soft));border:1px solid var(--border);
  border-radius:var(--r-lg);padding:{T.SPACE['md']}px;margin:0;display:flex;
  flex-direction:column;box-shadow:var(--e-raised)}}
.chartbox figcaption{{margin-bottom:{T.SPACE['sm']}px}}
.chartbox h4{{font-size:14px;font-weight:800;color:var(--text)}}
.chartbox .ask{{display:block;font-size:11.5px;color:var(--text-3);margin-top:3px}}
.chartbox svg{{width:100%;height:auto;display:block}}
/* بدون این، برچسب راست‌به‌چپ زیر میله می‌رود: در سند rtl مقدار
   text-anchor="end" یعنی «انتهای منطقی» که سمت چپ است. */
svg text{{direction:ltr;unicode-bidi:plaintext}}
.chart-label{{font:600 11.5px var(--font);fill:var(--text-2);text-anchor:end}}
.chart-value{{font:800 11.5px var(--font);fill:var(--teal-ink);text-anchor:start}}
.tick{{font:11px var(--font);fill:var(--text-3)}}
.axis-title{{font:700 11.5px var(--font);fill:var(--text-2)}}
.grid-line{{stroke:var(--paper-rule);stroke-width:1;stroke-dasharray:2 5;opacity:.72}}
.axis-line{{stroke:var(--pencil);stroke-width:1;opacity:.72}}
.median-line{{stroke:var(--text-3);stroke-width:1;stroke-dasharray:5 4;opacity:.8}}
/* عمق ظریف: سایهٔ کوچک زیر هر نشانه، نه رنگ تخت بدون بافت — چیزی که
   نمودار پیش‌فرض اکسل/PowerPoint هرگز ندارد. transition فقط filter/transform
   است تا با prefers-reduced-motion (بالاتر در همین فایل) سازگار بماند. */
.bar-mark{{fill:var(--teal);stroke:var(--navy);stroke-width:.8;
  filter:drop-shadow(0 1px 1.5px rgba(11,31,51,.16));
  transition:filter var(--dur-short,.15s) var(--ease-entrance,ease)}}
.bar-mark:hover{{filter:drop-shadow(0 2px 4px rgba(11,31,51,.24)) brightness(1.06)}}
.col-mark{{fill:var(--teal);stroke:var(--navy);stroke-width:.8;
  filter:drop-shadow(0 1px 1.5px rgba(11,31,51,.16));
  transition:filter var(--dur-short,.15s) var(--ease-entrance,ease)}}
.col-mark:hover{{filter:drop-shadow(0 2px 4px rgba(11,31,51,.24)) brightness(1.06)}}
.line-mark{{stroke:var(--navy);stroke-width:2.4;fill:none;stroke-linecap:round;
  stroke-linejoin:round}}
.area-mark{{fill:var(--teal);opacity:.12}}
.dot-mark{{fill:var(--teal);opacity:.86;stroke:#fff;stroke-width:1.2;
  filter:drop-shadow(0 1px 2px rgba(11,31,51,.2));
  transition:r var(--dur-short,.15s) var(--ease-entrance,ease)}}
.dot-mark:hover{{r:6.5}}
.slice-mark{{stroke:var(--raised);stroke-width:3;
  filter:drop-shadow(0 1px 2px rgba(11,31,51,.14));
  transition:filter var(--dur-short,.15s) var(--ease-entrance,ease),opacity var(--dur-short,.15s)}}
.slice-mark:hover{{filter:drop-shadow(0 3px 6px rgba(11,31,51,.26)) brightness(1.05)}}
.donut-group:hover .slice-mark:not(:hover){{opacity:.42}}
.chartfoot{{display:flex;gap:{T.SPACE['sm']}px;flex-wrap:wrap;align-items:center;
  margin-top:{T.SPACE['xs']}px;padding-top:{T.SPACE['xs']}px;
  border-top:1px solid var(--border);font-size:11.5px;color:var(--text-3)}}
.legend-item{{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text-2);
  padding:3px 6px;border-radius:7px;transition:background var(--dur-short,.15s)}}
.legend-item:hover{{background:var(--sunken)}}
.legend-item i{{width:11px;height:11px;border-radius:3px;display:inline-block;flex:none}}
.legend-item .lk{{flex:1}} .legend-item b{{color:var(--text)}}

/* ── Tooltip سفارشی: جایگزین <title> بومی مرورگر ──────────────────────────
   <title> همان جعبهٔ زشت پیش‌فرض سیستم‌عامل است که هر نمودار اکسل/Chart.js
   پیش‌فرض هم دارد؛ همین یکی به‌تنهایی نمودار را «ساده» نشان می‌دهد. */
.gsi-tip{{position:fixed;z-index:60;pointer-events:none;background:var(--navy);
  color:#fff;font:600 11.5px var(--font);padding:7px 10px;border-radius:9px;
  box-shadow:0 8px 20px rgba(11,31,51,.28);opacity:0;transform:translateY(4px);
  transition:opacity .12s,transform .12s;max-width:240px;line-height:1.6}}
.gsi-tip.show{{opacity:1;transform:translateY(0)}}
.gsi-tip b{{color:#fff;font-weight:800}}
.gsi-tip .gsi-tip-muted{{color:#c7d4dc}}

/* ── Empty state ── */
.emptybox{{display:flex;gap:{T.SPACE['sm']}px;align-items:center;justify-content:center;
  min-height:120px;background:var(--sunken);border-radius:var(--r-md);
  padding:{T.SPACE['md']}px;text-align:center}}
.emptybox p{{margin:0;font-size:12px;color:var(--text-3);max-width:46ch}}
.emptymark{{font-size:20px;color:var(--text-3)}}

/* ── Alert ── */
.alert{{border:1px solid var(--tone-ink);border-right:4px solid var(--tone-ink);
  background:var(--tone-wash);color:var(--tone-ink);border-radius:var(--r-md);
  padding:{T.SPACE['sm']}px {T.SPACE['md']}px;font-size:12.5px}}

/* ── Narrative (UX flow anchor) ── */
.story{{background:var(--raised);border:1px solid var(--border);
  border-top:3px solid var(--gold);border-radius:var(--r-lg);
  padding:{T.SPACE['lg']}px;box-shadow:var(--e-raised)}}
.scr{{background:var(--sunken);border-radius:var(--r-md);padding:{T.SPACE['sm']}px {T.SPACE['md']}px}}
.scr b{{display:block;font-size:11px;letter-spacing:.4px;color:var(--teal-ink);
  margin-bottom:4px}}
.scr p{{font-size:13px;color:var(--text-2)}}
.finding{{background:var(--raised);border:1px solid var(--border);
  border-right:4px solid var(--tone-ink,var(--teal));border-radius:var(--r-md);
  padding:{T.SPACE['sm']}px {T.SPACE['md']}px}}
.finding h5{{margin:0 0 5px;font-size:12px;color:var(--tone-ink,var(--teal-ink));font-weight:800}}
.finding .mag{{font-size:14px;font-weight:700;color:var(--text);margin-bottom:4px}}
.finding .cmp{{font-size:11.5px;color:var(--text-3);margin-bottom:6px}}
.finding .sow{{font-size:12px;color:var(--text-2);border-top:1px dashed var(--border);
  padding-top:6px}}
.finding .sow span{{color:var(--tone-ink,var(--teal-ink));font-weight:800}}

/* ── Process ribbon (UX flow) ── */
.flow{{display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
.flow-step{{background:var(--raised);border:1px solid var(--border);color:var(--teal-ink);
  padding:5px {T.SPACE['sm']}px;border-radius:var(--r-pill);font-size:11.5px;font-weight:700}}
.flow-step[aria-current="step"]{{background:var(--navy);color:var(--on-dark);border-color:var(--navy)}}
.flow-arrow{{color:var(--text-3)}}
.note{{font-size:11.5px;color:var(--text-3)}}
.pager{{display:flex;justify-content:center;align-items:center;gap:{T.SPACE['sm']}px;
  padding:{T.SPACE['sm']}px;font-size:12px;color:var(--text-2)}}

/* ── Composer isolation ── */
.pane[hidden]{{display:none!important}}
.pane{{min-width:0}}
[data-composer-block]{{min-width:0}}

/* ── Process Mining — Figma process-first vocabulary ── */
.process-suite{{display:grid;gap:var(--sp-lg)}}
.process-viz{{background:var(--raised);border:1px solid var(--border);border-radius:var(--r-lg);
  padding:var(--sp-lg);box-shadow:var(--e-raised);overflow:hidden}}
.process-viz .pv-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:var(--sp-md);
  margin-bottom:var(--sp-md)}}
.process-viz h3{{font-size:16px;font-weight:800;color:var(--text)}}
.process-viz .pv-head p{{font-size:11.5px;color:var(--text-3);margin-top:3px}}
.process-flow{{display:flex;align-items:stretch;gap:8px;overflow-x:auto;padding:4px 2px 10px;scrollbar-width:thin}}
.flow-node{{min-width:164px;max-width:190px;display:flex;flex-direction:column;gap:7px;
  background:var(--sunken);border:1px solid var(--border);border-radius:var(--r-md);padding:12px;
  border-top:3px solid var(--tone,var(--teal))}}
.flow-node[data-tone="critical"]{{--tone:var(--st-critical-ink);background:var(--st-critical-wash)}}
.flow-node[data-tone="warning"]{{--tone:var(--st-warning-ink);background:var(--st-warning-wash)}}
.flow-node[data-tone="neutral"]{{--tone:var(--teal)}}
.flow-node .flow-step{{align-self:flex-start;background:transparent;border:0;padding:0;border-radius:0;
  color:var(--text-3);font:700 10px var(--font)}}
.flow-node strong{{font-size:12.5px;color:var(--text)}}
.flow-node .flow-metrics{{display:grid;gap:4px;font-size:10.5px;color:var(--text-3)}}
.flow-node .flow-metrics span{{display:flex;justify-content:space-between;gap:8px}}
.flow-node .flow-metrics b{{color:var(--text);font-variant-numeric:tabular-nums}}
.process-flow>.flow-arrow{{display:grid;place-items:center;min-width:18px;color:var(--teal);font-size:18px}}
.rank-list,.bn-list{{display:grid;gap:9px}}
.rank-row{{display:grid;grid-template-columns:minmax(150px,1.2fr) minmax(120px,3fr) 90px 90px;
  gap:10px;align-items:center}}
.rank-label{{font-weight:700;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.rank-track{{height:9px;background:var(--sunken);border-radius:var(--r-pill);overflow:hidden}}
.rank-track>span,.variant-share>span{{display:block;height:100%;background:linear-gradient(90deg,var(--teal),#37a9af);
  border-radius:inherit}}
.rank-row small{{color:var(--text-3)}}
.bn-card{{display:flex;align-items:center;gap:12px;border:1px solid var(--border);border-radius:var(--r-md);
  background:var(--raised);padding:10px 12px}}
.bn-rank{{width:28px;height:28px;display:grid;place-items:center;border-radius:9px;background:var(--navy);
  color:#fff;font-weight:800;flex:none}}
.bn-main{{flex:1;min-width:0;display:grid;gap:6px}}
.bn-main strong{{font-size:12.5px;color:var(--text)}} .bn-main small{{color:var(--text-3)}}
.heatmap-wrap{{overflow:auto;border:1px solid var(--border);border-radius:var(--r-md)}}
.heatmap{{min-width:760px;border-collapse:separate;border-spacing:2px;background:var(--raised)}}
.heatmap th{{position:static;background:var(--sunken);color:var(--text-2);font-size:10px;max-width:120px;
  white-space:normal;line-height:1.35;border-radius:5px}}
.heatmap td{{text-align:center;min-width:72px;height:58px;border:0;border-radius:6px;color:var(--navy);
  vertical-align:middle}}
.heatmap td b{{display:block;font-size:13px}} .heatmap td small{{font-size:9px;color:inherit}}
.heatmap .hm-empty{{background:var(--sunken);color:var(--text-3)}}
.variant-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}}
.variant-card{{display:grid;gap:8px;background:var(--raised);border:1px solid var(--border);border-radius:var(--r-md);padding:12px}}
.variant-top{{display:flex;align-items:center;gap:8px}} .variant-top span{{color:var(--text-3);font-weight:800}}
.variant-top b{{margin-right:auto;font-size:12px}} .variant-top em{{font-style:normal;color:var(--teal-ink);font-weight:800}}
.variant-route{{font-size:11px;color:var(--text-2);line-height:1.8;white-space:normal}}
.variant-share{{height:6px;background:var(--sunken);border-radius:var(--r-pill);overflow:hidden}}
.variant-card small{{color:var(--text-3)}}
.conf-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.conf-card{{display:grid;gap:2px;background:var(--sunken);border-radius:var(--r-md);padding:12px;border:1px solid var(--border)}}
.conf-card b{{font-size:22px;color:var(--navy)}} .conf-card span{{font-weight:700;color:var(--text-2)}} .conf-card small{{color:var(--text-3)}}
.conf-score{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-top:12px;padding:12px;
  border-right:3px solid var(--teal);background:var(--teal-wash);border-radius:var(--r-md)}}
.conf-score b{{font-size:20px;color:var(--teal-ink)}}
.process-funnel{{display:flex;flex-direction:column;align-items:center;gap:6px}}
.funnel-step{{min-width:28%;display:flex;justify-content:space-between;gap:12px;padding:8px 12px;
  color:#fff;background:linear-gradient(90deg,var(--navy),var(--teal));border-radius:8px;transition:width var(--dur-medium) var(--ease-standard)}}
.funnel-step strong{{font-size:11.5px}} .funnel-step span{{font-size:10.5px;opacity:.9}}
.timeline-toolbar{{max-width:420px;margin-bottom:12px}}
.case-timeline{{position:relative;display:grid;gap:0;padding-right:16px}}
.case-timeline:before{{content:"";position:absolute;right:6px;top:8px;bottom:8px;width:2px;background:var(--border)}}
.tl-item{{position:relative;display:flex;gap:12px;padding:9px 0}}
.tl-dot{{position:relative;z-index:1;width:13px;height:13px;border-radius:50%;background:var(--teal);
  box-shadow:0 0 0 4px var(--teal-wash);margin-right:-16px;margin-left:12px;margin-top:4px;flex:none}}
.tl-item div{{display:grid;gap:2px}} .tl-item b{{font-size:12.5px}} .tl-item small{{color:var(--text-3)}}

/* ── Kanban / Action Board ── */
.kanban-metrics{{display:grid;grid-template-columns:repeat(5,minmax(90px,1fr));gap:8px;margin-bottom:14px}}
.kanban-metrics>div{{display:grid;gap:2px;background:var(--sunken);border:1px solid var(--border);
  border-radius:var(--r-md);padding:10px}}
.kanban-metrics b{{font-size:21px;color:var(--navy)}} .kanban-metrics span{{font-size:10.5px;color:var(--text-3)}}
.kanban-metrics [data-tone="critical"]{{background:var(--st-critical-wash);border-color:var(--st-critical-ink)}}
.kanban-metrics [data-tone="serious"]{{background:var(--st-serious-wash);border-color:var(--st-serious-ink)}}
.kanban-board{{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(250px,1fr);gap:12px;overflow-x:auto;
  padding-bottom:8px;scrollbar-width:thin;align-items:start}}
.kanban-col{{background:var(--sunken);border:1px solid var(--border);border-radius:var(--r-lg);padding:10px;min-height:180px}}
.kanban-col>header{{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:4px 4px 10px}}
.kanban-col>header h3{{font-size:13px}} .kanban-col>header span{{min-width:28px;height:24px;display:grid;place-items:center;
  background:var(--raised);border:1px solid var(--border);border-radius:var(--r-pill);font-size:10.5px;font-weight:800}}
.kanban-col[data-tone="critical"]{{border-color:var(--st-critical-ink);background:var(--st-critical-wash)}}
.kanban-col[data-tone="warning"]{{border-color:var(--st-warning-ink);background:var(--st-warning-wash)}}
.kanban-col[data-tone="critical"]>header h3{{color:var(--st-critical-ink)}}
.kanban-col[data-tone="warning"]>header h3{{color:var(--st-warning-ink)}}
.kanban-more{{margin-top:9px;padding:7px;text-align:center;font-size:10.5px;font-weight:700;color:var(--text-3);border-top:1px dashed var(--border)}}
.kanban-stack{{display:grid;gap:9px}}
.kanban-card{{background:var(--raised);border:1px solid var(--border);border-right:4px solid var(--tone,var(--teal));
  border-radius:var(--r-md);padding:11px;box-shadow:0 1px 2px rgba(11,31,51,.06),0 1px 1px rgba(11,31,51,.04);
  display:grid;gap:7px;transition:box-shadow var(--dur-short,.15s) var(--ease-standard,ease),
  transform var(--dur-short,.15s) var(--ease-standard,ease)}}
.kanban-card:hover{{box-shadow:0 10px 22px rgba(11,31,51,.14),0 3px 6px rgba(11,31,51,.08);
  transform:translateY(-2px)}}
.kanban-card[data-tone="critical"],.priority[data-tone="critical"]{{--tone:var(--st-critical-ink)}}
.kanban-card[data-tone="serious"],.priority[data-tone="serious"]{{--tone:var(--st-serious-ink)}}
.kanban-card[data-tone="warning"],.priority[data-tone="warning"]{{--tone:var(--st-warning-ink)}}
.kanban-card[data-tone="neutral"],.priority[data-tone="neutral"]{{--tone:var(--border-strong)}}
.kc-top{{display:flex;align-items:center;justify-content:space-between;gap:8px}}
.kc-top>b{{font-size:11.5px;color:var(--teal-ink);direction:ltr}}
.priority{{font-size:9px;font-weight:800;color:var(--tone);background:color-mix(in srgb,var(--tone) 12%,var(--raised));
  border:1px solid var(--tone);border-radius:var(--r-pill);padding:2px 8px;letter-spacing:.02em}}
.kanban-card h4{{font-size:12.5px;line-height:1.7;color:var(--text)}}
.kc-meta{{font-size:10.5px;color:var(--text-3);display:flex;align-items:center;flex-wrap:wrap;gap:6px}}
.kanban-card p{{font-size:11px;color:var(--text-2)}}
/* آواتار مسئول: دایرهٔ گرادیانی با حرف اول به‌جای فقط ایموجی 👤 — به همان
   میزان که Chip اولویت رنگی هویت وضعیت را حمل می‌کند، این هویت مالک را. */
.kc-avatar{{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;
  border-radius:50%;background:linear-gradient(135deg,var(--teal),var(--navy));color:#fff;
  font-size:9px;font-weight:800;flex:none}}
/* Chip موعد: رنگ وضعیت (معوق/نزدیک/آینده) به‌جای متن خاکستری یکنواخت —
   همان اطلاعاتی که قبلاً فقط در عدد «−۱۲۹ روز» پنهان بود، حالا رنگ هم دارد. */
.kc-due{{font-size:10px;font-weight:800;border-radius:var(--r-pill);padding:2px 8px;white-space:nowrap}}
.kc-due[data-tone="overdue"]{{color:var(--st-critical-ink);background:var(--st-critical-wash)}}
.kc-due[data-tone="soon"]{{color:var(--st-warning-ink);background:var(--st-warning-wash)}}
.kc-due[data-tone="future"]{{color:var(--st-good-ink);background:var(--st-good-wash)}}
.kc-gap{{font-size:10.5px;color:var(--st-warning-ink);background:var(--st-warning-wash);border-radius:7px;padding:6px 8px}}
.kanban-card details{{font-size:10.5px;color:var(--text-3)}}

/* ── Data quality block ── */
.dq-list{{display:grid;gap:8px}} .dq-row{{display:grid;grid-template-columns:minmax(160px,1.2fr) 3fr 58px;gap:10px;align-items:center}}
.dq-row>div{{height:7px;background:var(--sunken);border-radius:var(--r-pill);overflow:hidden}}
.dq-row i{{display:block;height:100%;background:var(--teal)}} .dq-row b{{font-size:11px;color:var(--text-2)}}

@media (max-width:{T.BREAKPOINT['md'] - 1}px){{
  .rank-row{{grid-template-columns:1fr 1.8fr 70px}} .rank-row small{{display:none}}
  .kanban-metrics{{grid-template-columns:repeat(2,1fr)}}
  .process-viz{{padding:var(--sp-md)}}
}}
"""


def _minify_css(css: str) -> str:
    """Whitespace/comment-only compaction — never touches a selector, a value,
    or their order, so it cannot change how anything renders. Quoted strings
    (``content:"..."``) are protected before whitespace collapsing so a
    future multi-char ``content`` value is never corrupted by this pass.
    """
    strings: list = []

    def _stash(m: "re.Match") -> str:
        strings.append(m.group(0))
        return f"\x00{len(strings) - 1}\x00"

    out = re.sub(r'"[^"]*"|\'[^\']*\'', _stash, css)
    out = re.sub(r"/\*.*?\*/", "", out, flags=re.S)
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\s*([{}:;,])\s*", r"\1", out)
    out = re.sub(r";}", "}", out)
    out = re.sub(r"\x00(\d+)\x00", lambda m: strings[int(m.group(1))], out)
    return out.strip()


def stylesheet() -> str:
    """کل شیوه‌نامه سیستم طراحی — یک رشته، بدون هیچ وابستگی بیرونی.

    هیچ ``<link>`` یا ``<script src>`` خارجی وجود ندارد: این گزارش از داخل
    Outlook و روی شبکه اداری باز می‌شود و هر منبع بیرونی یعنی صفحه‌ای که
    ممکن است بدون شبکه خالی یا بی‌استایل بالا بیاید.
    """
    return _minify_css(
        f":root{{{_vars()}}}\n"
        + _components()
        + _type_classes() + "\n"
        + _auto_layout()
        + _a11y()
        + _motion()
        + _responsive()
    )


#: اسکریپت نمایان‌سازی تدریجی — بومی مرورگر، صفر بایت وابستگی.
#: سه تور ایمنی، چون «نامرئی ماندن محتوا» بدترین شکست یک گزارش است.
REVEAL_JS = (
    "function gsiRevealAll(){document.querySelectorAll('.reveal:not(.in)')"
    ".forEach(function(e){e.classList.add('in')})}\n"
    "function gsiReveal(root){"
    "var q=(root||document).querySelectorAll('.reveal:not(.in)');"
    "if(!('IntersectionObserver' in window)||matchMedia('(prefers-reduced-motion:reduce)').matches){"
    "q.forEach(function(e){e.classList.add('in')});return}"
    "var io=new IntersectionObserver(function(es){es.forEach(function(x){"
    "if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target)}})},"
    "{rootMargin:'0px 0px -6% 0px',threshold:.05});"
    "q.forEach(function(e){io.observe(e)});"
    f"setTimeout(gsiRevealAll,{T.REVEAL_FAILSAFE_MS})}}\n"
    "window.addEventListener('beforeprint',gsiRevealAll);"
)
