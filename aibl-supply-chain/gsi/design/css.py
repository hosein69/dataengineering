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

from . import tokens as T


def _vars() -> str:
    """توکن‌ها به‌صورت CSS Custom Property — همان نام‌های فیگما."""
    rows = []
    add = rows.append
    add(f"--surface:{T.SURFACE_PAGE}")
    add(f"--raised:{T.SURFACE_RAISED}")
    add(f"--sunken:{T.SURFACE_SUNKEN}")
    add(f"--inverse:{T.SURFACE_INVERSE}")
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
body{{margin:0;background:var(--surface);color:var(--text);direction:rtl;
  font-family:var(--font);font-size:13px;line-height:1.75;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}}
h1,h2,h3,h4{{margin:0}} p{{margin:0}}

/* ── App bar ── */
.appbar{{background:linear-gradient(135deg,var(--navy) 0%,#123047 55%,var(--teal) 140%);
  color:var(--on-dark);border-radius:var(--r-xl);padding:{T.SPACE['xl']}px;
  box-shadow:var(--e-overlay)}}
.appbar .eyebrow{{opacity:.82}}
.appbar .sub{{opacity:.9}}
.brandmark{{display:inline-flex;align-items:center;gap:{T.SPACE['xs']}px;font-weight:800}}
.brandmark i{{width:10px;height:10px;border-radius:3px;display:inline-block;
  background:var(--gold);box-shadow:0 0 0 3px rgba(199,154,74,.22)}}
.stat-pill{{display:flex;flex-direction:column;align-items:center;
  background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.24);
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

/* ── Chart frame ── */
.chartbox{{background:var(--raised);border:1px solid var(--border);
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
.grid-line{{stroke:var(--border);stroke-width:1;shape-rendering:crispEdges}}
.axis-line{{stroke:var(--border-strong);stroke-width:1.2}}
.median-line{{stroke:var(--text-3);stroke-width:1;stroke-dasharray:5 4;opacity:.8}}
.bar-mark{{fill:var(--teal);stroke:var(--navy);stroke-width:.8}}
.col-mark{{fill:var(--teal);stroke:var(--navy);stroke-width:.8}}
.line-mark{{stroke:var(--navy);stroke-width:2.4;fill:none;stroke-linecap:round;
  stroke-linejoin:round}}
.area-mark{{fill:var(--teal);opacity:.12}}
.dot-mark{{fill:var(--teal);opacity:.82;stroke:#fff;stroke-width:.8}}
.slice-mark{{stroke:#fff;stroke-width:2}}
.chartfoot{{display:flex;gap:{T.SPACE['sm']}px;flex-wrap:wrap;align-items:center;
  margin-top:{T.SPACE['xs']}px;padding-top:{T.SPACE['xs']}px;
  border-top:1px solid var(--border);font-size:11.5px;color:var(--text-3)}}
.legend-item{{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text-2)}}
.legend-item i{{width:11px;height:11px;border-radius:3px;display:inline-block;flex:none}}
.legend-item .lk{{flex:1}} .legend-item b{{color:var(--text)}}

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
"""


def stylesheet() -> str:
    """کل شیوه‌نامه سیستم طراحی — یک رشته، بدون هیچ وابستگی بیرونی.

    هیچ ``<link>`` یا ``<script src>`` خارجی وجود ندارد: این گزارش از داخل
    Outlook و روی شبکه اداری باز می‌شود و هر منبع بیرونی یعنی صفحه‌ای که
    ممکن است بدون شبکه خالی یا بی‌استایل بالا بیاید.
    """
    return (f":root{{{_vars()}}}\n"
            + _components()
            + _type_classes() + "\n"
            + _auto_layout()
            + _a11y()
            + _motion()
            + _responsive())


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
