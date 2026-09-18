# -*- coding: utf-8 -*-
"""GSI Design System — لایه ۹: Dev Handoff.

خروجی این ماژول همان چیزی است که یک توسعه‌دهنده یا طراح تازه‌وارد لازم
دارد تا بدون پرسیدن، درست پیاده‌سازی کند:

* جدول توکن‌ها با مقدار دقیق و نام متغیر CSS
* فهرست کامپوننت‌ها با واریانت و حالت‌ها
* گزارش کنتراست با عدد اندازه‌گیری‌شده
* معادل‌های Auto Layout بین فیگما و CSS
* قواعد ریسپانسیو و چاپ

    python -m gsi.design.handoff            گزارش متنی
    python -m gsi.design.handoff --json     خروجی ماشین‌خوان برای فیگما
    python -m gsi.design.handoff --css      فقط متغیرهای CSS
"""
from __future__ import annotations

__contract__ = 3

import json
from typing import Any, Dict

from . import components as C
from . import css as CSS
from . import tokens as T
from ..factsheet import VERSION as PACKAGE_VERSION


def tokens_json() -> Dict[str, Any]:
    """توکن‌ها به شکل ماشین‌خوان — ورودی مستقیم Figma Variables."""
    return {
        "meta": {"system": "GSI Design System", "version": "2.0",
                 "package_version": PACKAGE_VERSION,
                 "figma": FIGMA_FILE,
                 "html_sample": HTML_SAMPLE,
                 "identity": {"navy": "Data / Trust", "teal": "Process / Flow",
                              "gold": "Decision"}},
        "color": {
            "surface": {"page": T.SURFACE_PAGE, "raised": T.SURFACE_RAISED,
                        "sunken": T.SURFACE_SUNKEN, "inverse": T.SURFACE_INVERSE},
            "border": {"default": T.BORDER, "strong": T.BORDER_STRONG,
                       "focus": T.BORDER_FOCUS},
            "text": {"primary": T.TEXT, "secondary": T.TEXT_SECONDARY,
                     "muted": T.TEXT_MUTED, "on-dark": T.TEXT_ON_DARK},
            "brand": {"navy": T.BRAND_NAVY, "teal": T.BRAND_TEAL, "gold": T.BRAND_GOLD,
                      "teal-ink": T.TEAL_INK, "gold-ink": T.GOLD_INK,
                      "teal-wash": T.TEAL_WASH, "gold-wash": T.GOLD_WASH,
                      "navy-wash": T.NAVY_WASH},
            "status": {s.key: {"ink": s.ink, "fill": s.fill, "wash": s.wash,
                               "icon": s.icon, "label": s.label,
                               "contrast_on_white": T.contrast(s.ink, T.SURFACE_RAISED)}
                       for s in T.STATUS_SCALE},
            "series": list(T.CATEGORICAL),
            "sequential": list(T.SEQUENTIAL),
        },
        "space": T.SPACE,
        "radius": T.RADIUS,
        "elevation": T.ELEVATION,
        "type": {k: {"size": v.size, "weight": v.weight, "line": v.line,
                     "track": v.track} for k, v in T.TYPE.items()},
        "motion": dict(T.MOTION, stagger_max=T.STAGGER_MAX,
                       reveal_failsafe_ms=T.REVEAL_FAILSAFE_MS),
        "breakpoint": T.BREAKPOINT,
        "components": C.INVENTORY,
        "figma_components": {
            "component_sets": list(FIGMA_COMPONENT_SETS),
            "standalone": list(FIGMA_STANDALONE_COMPONENTS),
            "variant_count": FIGMA_VARIANTS,
            "prototype_frames": FIGMA_PROTOTYPE_FRAMES,
            "prototype_reaction_nodes": FIGMA_PROTOTYPE_REACTION_NODES,
        },
        "accessibility": {
            "floors": {"AA_text": T.AA_TEXT, "AA_large": T.AA_LARGE,
                       "AAA_text": T.AAA_TEXT},
            "violations": [v._asdict() for v in T.audit()],
        },
    }


#: فایل فیگمای مرجع محصول و Design System V27.
#:
#: کد، منبع حقیقت توکن‌های runtime و خروجی‌های تولیدی است؛ Figma منبع حقیقت
#: visual/interaction specification محصول است. اختلاف بین این دو باید در Release
#: reconciliation حل شود و نباید یکی بی‌صدا دیگری را overwrite کند.
FIGMA_FILE = "https://www.figma.com/design/v3FIHcKem4vqZoZwcDWdZ2"

#: نمونه HTML تعاملی داخل همین پکیج؛ داده‌های آن Demo هستند، نه داده عملیاتی.
HTML_SAMPLE = "examples/GSI_V27_UI_SAMPLE.html"

#: صفحه‌های واقعی فایل Figma، به ترتیب ساختار محصول.
FIGMA_PAGES = (
    ("00 · Cover", "هویت GSI و جهت طراحی Data • Process • Decision"),
    ("01 · Foundations", "استراتژی، مخاطبان، اصول UX، Responsive و Accessibility baseline"),
    ("02 · Design Tokens", "رنگ، وضعیت، تایپوگرافی، spacing، radius، breakpoint و motion"),
    ("03 · Components", "کامپوننت‌های reusable و Variantهای کنترل/ناوبری/داده/feedback"),
    ("04 · Patterns", "Timeline، Case Action، Money Flow، Inventory، Unknown≠Zero و Filter"),
    ("05 · User Flows", "مسیرهای کارشناس، مدیر میانی، مدیر ارشد و تحلیل‌گر"),
    ("06 · Wireframes", "Desktop و Mobile low-fidelity قبل از visual polish"),
    ("07 · Desktop Screens", "Expert Home، Case Detail، Manager، Executive و Analyst"),
    ("08 · Mobile Screens", "Action Queue، Case Detail و Draft Email"),
    ("09 · Prototype", "مسیر کلیک‌پذیر Success/Error با Back و Retry"),
    ("10 · Handoff · Documentation", "WCAG audit، Responsive contract، UX evaluation و Dev QA"),
)

#: Variable collectionهای publishable واقعی فایل Figma. Primitive و Size داخلی و hidden هستند.
FIGMA_COLLECTIONS = (
    ("GSI · Color", 54), ("GSI · Spacing", 12), ("GSI · Radius", 6),
    ("GSI · Breakpoint", 4), ("GSI · Container", 1), ("GSI · Type", 48),
    ("GSI · Font", 3), ("GSI · Motion", 12),
)

FIGMA_COMPONENT_SETS = (
    "Button", "Input", "Select", "Search", "Checkbox", "Radio", "Toggle",
    "Badge", "Tabs", "Card", "Sidebar", "Table", "Toast", "State Panel",
)
FIGMA_STANDALONE_COMPONENTS = ("Navbar", "Modal", "Tooltip", "Breadcrumb", "Pagination")
FIGMA_VARIANTS = 80
FIGMA_PROTOTYPE_FRAMES = 6
FIGMA_PROTOTYPE_REACTION_NODES = 10

#: نگاشت Auto Layout فیگما ↔ CSS. همین جدول در فایل فیگما هم نوشته می‌شود.
AUTOLAYOUT_MAP = (
    ("Vertical auto layout", ".stack", "flex-direction:column"),
    ("Horizontal auto layout", ".cluster", "flex-direction:row; flex-wrap:wrap"),
    ("Space between", ".split", "justify-content:space-between"),
    ("Fill container", ".grow", "flex:1 1 auto"),
    ("Hug contents", ".hug", "flex:0 0 auto"),
    ("Wrap / responsive grid", ".grid-auto", "grid-template-columns:repeat(auto-fit,minmax(--col,1fr))"),
    ("Item spacing", ".stack-{token} / .cluster-{token}", "gap:var(--sp-{token})"),
    ("Padding", "--sp-{token}", "padding:var(--sp-{token})"),
)


def report() -> str:
    """گزارش متنی Dev Handoff."""
    L = []
    a = L.append
    a("═" * 78)
    a("GSI Design System — Dev Handoff")
    a("Navy = Data/Trust · Teal = Process/Flow · Gold = Decision")
    a("═" * 78)

    a("\n── ۱) UI Basics — رنگ ─────────────────────────────────────────────")
    a(f"{'توکن':26s} {'مقدار':10s} {'CSS':22s} کنتراست روی سفید")
    for name, value, var in (
            ("text/primary", T.TEXT, "--text"),
            ("text/secondary", T.TEXT_SECONDARY, "--text-2"),
            ("text/muted", T.TEXT_MUTED, "--text-3"),
            ("brand/navy", T.BRAND_NAVY, "--navy"),
            ("brand/teal", T.BRAND_TEAL, "--teal"),
            ("brand/teal-ink", T.TEAL_INK, "--teal-ink"),
            ("brand/gold", T.BRAND_GOLD, "--gold"),
            ("brand/gold-ink", T.GOLD_INK, "--gold-ink"),
            ("border/strong", T.BORDER_STRONG, "--border-strong")):
        a(f"{name:26s} {value:10s} {var:22s} {T.contrast(value, T.SURFACE_RAISED):>6.2f}")

    a("\n── وضعیت: سه نقش رنگی ──")
    a(f"{'وضعیت':22s} {'ink':9s} {'fill':9s} {'wash':9s} {'کنتراست ink':>12s}")
    for s in T.STATUS_SCALE:
        a(f"{s.icon} {s.label:20s} {s.ink:9s} {s.fill:9s} {s.wash:9s} "
          f"{T.contrast(s.ink, T.SURFACE_RAISED):>12.2f}")

    a("\n── ۲) Auto Layout — فیگما ↔ CSS ───────────────────────────────────")
    a(f"{'فیگما':28s} {'کلاس':30s} معادل")
    for fig, klass, equiv in AUTOLAYOUT_MAP:
        a(f"{fig:28s} {klass:30s} {equiv}")
    a(f"\nشبکه فاصله (۴ پیکسلی): "
      + "  ".join(f"{k}={v}" for k, v in T.SPACE.items()))

    a("\n── ۳) کامپوننت‌ها و واریانت‌ها ─────────────────────────────────────")
    for name, spec in C.INVENTORY.items():
        parts = []
        for key in ("variants", "tones", "sizes"):
            if spec.get(key):
                parts.append(f"{key}: {', '.join(map(str, spec[key]))}")
        a(f"• {name}")
        for p in parts:
            a(f"    {p}")
        a(f"    states: {', '.join(map(str, spec.get('states', [])))}")

    a("\n── ۴) Responsive ──────────────────────────────────────────────────")
    for k, v in T.BREAKPOINT.items():
        a(f"  {k:4s} ≥ {v}px")
    a(f"  container max: {T.CONTAINER_MAX}px")
    a("  شبکه‌ها با minmax خودشان می‌شکنند؛ media query فقط جایی است که")
    a("  «چیدمان» عوض می‌شود، نه صرفاً اندازه. چاپ یک نقطه شکست واقعی است.")

    a("\n── ۵) تایپوگرافی ──────────────────────────────────────────────────")
    a(f"{'سبک':12s} {'اندازه':>7s} {'وزن':>5s} {'ارتفاع خط':>10s}")
    for k, v in T.TYPE.items():
        a(f"{k:12s} {v.size:>6}px {v.weight:>5} {v.line:>10}")

    a("\n── ۶) Motion ──────────────────────────────────────────────────────")
    for k, v in T.MOTION.items():
        a(f"  {k:16s} {v}")
    a(f"  سقف آبشار: {T.STAGGER_MAX} پله · مهلت ایمنی نمایان‌سازی: {T.REVEAL_FAILSAFE_MS}ms")
    a("  فقط transform و opacity انیمیت می‌شوند (GPU، بدون بازمحاسبه layout).")
    a("  prefers-reduced-motion اختیاری نیست.")

    a("\n── ۷) Accessibility ───────────────────────────────────────────────")
    bad = T.audit()
    a(f"  کف‌ها: متن {T.AA_TEXT} · درشت/گرافیکی {T.AA_LARGE}")
    a(f"  نتیجه ممیزی: {'PASS — صفر تخلف' if not bad else f'FAIL — {len(bad)} تخلف'}")
    for v in bad:
        a(f"    ✗ {v.name}: {v.ratio} < {v.floor}")
    a("  حلقه فوکوس: :focus-visible با outline ۳px و offset ۲px")
    a("  ناحیه لمسی: حداقل ۳۶px ارتفاع روی هر کنترل")
    a("  رنگ هرگز تنها حامل معنا نیست: هر وضعیت آیکن و برچسب دارد.")
    a("  skip-link، landmark، aria-live روی شمارنده، و caption برای هر جدول.")

    a("\n── ۸) Dev Handoff ─────────────────────────────────────────────────")
    a("  متغیرهای CSS:  python -m gsi.design.handoff --css")
    a("  توکن ماشین‌خوان: python -m gsi.design.handoff --json")
    a("  شیوه‌نامه کامل در gsi/design/css.py :: stylesheet()")
    a(f"\n  مرجع Figma: {FIGMA_FILE}")
    a(f"  نمونه HTML: {HTML_SAMPLE}")
    a(f"  {sum(n for _, n in FIGMA_COLLECTIONS)} متغیر publishable در "
      f"{len(FIGMA_COLLECTIONS)} مجموعه: "
      + " · ".join(f"{n}({c})" for n, c in FIGMA_COLLECTIONS))
    a(f"  {len(FIGMA_PAGES)} صفحه GSI · {len(FIGMA_COMPONENT_SETS)} Component Set · "
      f"{FIGMA_VARIANTS} Variant · {len(FIGMA_STANDALONE_COMPONENTS)} Component مستقل")
    a(f"  Prototype: {FIGMA_PROTOTYPE_FRAMES} frame · "
      f"{FIGMA_PROTOTYPE_REACTION_NODES} node دارای reaction")
    for name, what in FIGMA_PAGES:
        a(f"    {name:30s} {what}")
    a("  قرارداد Release: runtime tokens از کد، visual/interaction spec از Figma؛")
    a("  هر اختلاف باید پیش از Release صریحاً reconciliation شود.")
    a("═" * 78)
    return "\n".join(L)


def css_variables() -> str:
    """فقط بلوک ``:root`` — برای چسباندن در هر پروژه دیگر."""
    sheet = CSS.stylesheet()
    return sheet[:sheet.index("}") + 1]


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="GSI Design System — dev handoff")
    ap.add_argument("--json", action="store_true", help="توکن ماشین‌خوان")
    ap.add_argument("--css", action="store_true", help="متغیرهای CSS")
    args = ap.parse_args(argv)
    if args.json:
        print(json.dumps(tokens_json(), ensure_ascii=False, indent=2))
    elif args.css:
        print(css_variables())
    else:
        print(report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
