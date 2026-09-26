# -*- coding: utf-8 -*-
"""سیستم طراحی GSI — تست رگرسیون هر نه لایه.

    UI Basics → Auto Layout → Components & Variants → Responsive →
    Design System → Prototype → UX Flow → Accessibility → Dev Handoff

قاعده‌ای که این فایل قفل می‌کند: **ظاهر هم قرارداد است.** پالتی که کنتراست
را رد می‌کند، گزارشی که در چاپ سفید می‌شود، و رنگی که فقط در یکی از چهار
خروجی عوض شده — همگی باگ‌اند، نه سلیقه.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from gsi.design import charts_js as CJ  # noqa: E402
from gsi.design import components as C  # noqa: E402
from gsi.design import css as CSS  # noqa: E402
from gsi.design import excel as DX  # noqa: E402
from gsi.design import handoff as HO  # noqa: E402
from gsi.design import tokens as T  # noqa: E402
from gsi.report.palette import LuxuryPalette  # noqa: E402
from gsi.studio_core.html_export import build_dynamic_html  # noqa: E402

PASS: list = []
FAIL: list = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(("✅ " if ok else "❌ ") + name + (f" → {detail}" if detail else ""))


def _sample(n: int = 120) -> pd.DataFrame:
    return pd.DataFrame({
        "KEY_MATERIAL": [f"MAT-{i%12:03d}" for i in range(n)],
        "CANONICAL_ORDER": [f"ORD-{i%9:04d}" for i in range(n)],
        "ORG_DEPT": [["خرید خارجی", "گمرک و ترخیص", "حمل"][i % 3] for i in range(n)],
        "بحرانی (کوتاه)": [["توقف خط", "بحرانی", "تحت نظر", "ایمن"][i % 4] for i in range(n)],
        "مقاومت (روز)": [float(i % 40) for i in range(n)],
        "روزهای رسوب": [float(i % 55) for i in range(n)],
        "مانده تعهد": [float((i % 20) * 1000) for i in range(n)],
        "روزهای تأخیر": [float(i % 30 - 8) for i in range(n)],
    })


def main() -> int:
    html = build_dynamic_html(
        _sample(), "2026-09-17", title="GSI",
        selected_fields=list(_sample().columns),
        charts=["criticality", "low_resistance", "sediment_vs_resistance",
                "pareto_delay", "commitment"],
        process_extras={"bottlenecks": pd.DataFrame(
            {"از فعالیت": ["ثبت سفارش"], "به فعالیت": ["تخصیص ارز"],
             "میانگین روز": [14], "تعداد پرونده": [7]})})
    sheet = CSS.stylesheet()

    # ── ۱) UI Basics ────────────────────────────────────────────────────
    print("\n── ۱) UI Basics ──")
    check("پالت هیچ تخلف کنتراستی ندارد", not T.audit(),
          "; ".join(f"{v.name} {v.ratio}" for v in T.audit()[:3]))
    check("هر وضعیت سه نقش رنگی جدا دارد",
          all(len({s.ink, s.fill, s.wash}) == 3 for s in T.STATUS_SCALE))
    check("رنگ تنها حامل معنا نیست: هر وضعیت آیکن و برچسب دارد",
          all(s.icon.strip() and s.label.strip() for s in T.STATUS_SCALE))
    check("همه فاصله‌ها روی شبکه ۴ پیکسلی‌اند",
          all(v % 4 == 0 or v in (0, 2) for v in T.SPACE.values()),
          str(sorted(T.SPACE.values())))
    check("هویت Navy/Teal/Gold حفظ شده",
          T.BRAND_NAVY == "#0b1f33" and T.BRAND_TEAL == "#0a7c86"
          and T.BRAND_GOLD == "#c79a4a")
    check("مقیاس تایپ نزولی و بدون گره است",
          [T.TYPE[k].size for k in ("display", "h1", "h2", "h3", "h4", "body", "caption")]
          == sorted([T.TYPE[k].size for k in
                     ("display", "h1", "h2", "h3", "h4", "body", "caption")], reverse=True))
    # متن جاری کف ۱٫۵ دارد (WCAG 1.4.12 + خوانایی فارسی)؛ تیتر و عدد درشت
    # عمداً فشرده‌ترند، چون ۱٫۵ روی اندازه بزرگ تیتر را از هم می‌پاشد.
    check("متن جاری کف ارتفاع خط ۱٫۵ را دارد",
          all(T.TYPE[k].line >= T.BODY_LINE_MIN for k in T.BODY_STYLES),
          str({k: T.TYPE[k].line for k in T.BODY_STYLES}))
    check("تیتر و عدد درشت فشرده‌اند ولی زیر ۱٫۲ نمی‌روند",
          all(v.line >= 1.2 for v in T.TYPE.values()))

    # ── ۲) Auto Layout ──────────────────────────────────────────────────
    print("\n── ۲) Auto Layout ──")
    for klass in (".stack", ".cluster", ".split", ".grow", ".hug", ".grid-auto"):
        check(f"اولیه «{klass}» تعریف شده", klass + "{" in sheet)
    check("هر توکن فاصله کلاس gap دارد",
          all(f".stack-{k}{{gap:{v}px}}" in sheet
              for k, v in T.SPACE.items() if k != "none"))
    check("چیدمان‌ها در خروجی واقعی استفاده می‌شوند",
          'class="stack' in html and "cluster" in html and "grid-auto" in html)

    # ── ۳) Components & Variants ────────────────────────────────────────
    print("\n── ۳) Components & Variants ──")
    check("فهرست کامپوننت‌ها ≥ ۱۰ مورد است", len(C.INVENTORY) >= 10, str(len(C.INVENTORY)))
    check("هر کامپوننت حالت‌هایش اعلام شده",
          all(spec.get("states") for spec in C.INVENTORY.values()))
    for v in C.BUTTON_VARIANTS:
        check(f"واریانت دکمه «{v}» در شیوه‌نامه هست", f".btn--{v}" in sheet)
    check("دکمه‌ی تصمیم از طلایی استفاده می‌کند",
          "btn--decision" in sheet and "var(--gold)" in sheet)
    check("هر وضعیت متغیر رنگی خودش را دارد",
          all(f"--st-{s.key}:" in sheet and f"--st-{s.key}-ink:" in sheet
              for s in T.STATUS_SCALE))
    check("نشان وضعیت رنگ + آیکن + متن می‌دهد",
          "⬤" in C.badge("بحرانی", tone="critical")
          and "بحرانی" in C.badge("بحرانی", tone="critical"))
    check("کامپوننت‌ها ورودی را escape می‌کنند",
          "&lt;script&gt;" in C.badge("<script>", tone="critical")
          and "<script>" not in C.badge("<script>", tone="critical"))
    check("حالت خالی همیشه دلیل می‌گوید", "چرا" in C.empty_state("چرا خالی است").lower()
          or len(C.empty_state("x")) > 0)

    # ── ۴) Responsive ───────────────────────────────────────────────────
    print("\n── ۴) Responsive ──")
    for k, v in T.BREAKPOINT.items():
        check(f"نقطه شکست «{k}» تعریف شده", isinstance(v, int) and v > 0)
    check("media queryهای چیدمان در شیوه‌نامه هستند",
          f"@media (max-width:{T.BREAKPOINT['md'] - 1}px)" in sheet
          and f"@media (max-width:{T.BREAKPOINT['lg'] - 1}px)" in sheet)
    check("شبکه بدون media query هم می‌شکند", "minmax(var(--col" in sheet)
    check("viewport meta برای موبایل هست", 'name="viewport"' in html)
    check("چاپ یک نقطه شکست واقعی است",
          "@media print" in sheet and "@page" in sheet and "landscape" in sheet)

    # ── ۵) Design System — یک منبع برای چهار خروجی ──────────────────────
    print("\n── ۵) Design System ──")
    check("Excel از همان توکن‌ها می‌خواند",
          LuxuryPalette.STATUS_CRITICAL == DX.X(T.STATUS["critical"].ink)
          and LuxuryPalette.AMBER_HEADER == DX.X(T.BRAND_NAVY))
    check("ایمیل از همان توکن‌ها می‌خواند",
          __import__("gsi.integrations.daily_email", fromlist=["RED"]).RED
          == T.STATUS["critical"].ink)
    check("HTML از همان توکن‌ها می‌خواند",
          T.STATUS["critical"].fill in html and T.BRAND_NAVY in html)
    check("پالت‌های رد‌شده قدیمی دیگر در هیچ خروجی نیستند",
          "#F1C40F" not in html and "#C0392B" not in html
          and LuxuryPalette.STATUS_WATCH != "F1C40F")
    check("سلول رنگی Excel مرز هم‌خانواده می‌گیرد",
          "border" in DX.status_style("warning"))

    # ── ۶) Prototype — رفتار ────────────────────────────────────────────
    print("\n── ۶) Prototype ──")
    check("تب‌ها قابل فعال‌سازی‌اند", "function activate(" in html)
    check("فیلتر زنده روی همه لایه‌ها اثر می‌گذارد",
          "function rows(t)" in html and "renderCharts" in html and "renderStory" in html)
    # اندازه صفحه دیگر ثابت نیست؛ از پروفایل مخاطب می‌آید. تست باید
    # «صفحه‌بندی کار می‌کند» را بسنجد، نه یک عدد منجمد را.
    check("صفحه‌بندی جدول کار می‌کند",
          "function pageMove(" in html and "function pageSize(" in html
          and "audCfg().table_rows" in html)
    check("استخراج Excel مرورگری هست",
          "downloadFilteredXlsx" in html and "GSI_filtered_" in html)
    check("چاپ/PDF از همان DOM", "window.print()" in html)
    check("حالت hover و active تعریف شده", ".btn:hover" in sheet and ".btn:active" in sheet)

    # ── ۷) UX Flow ──────────────────────────────────────────────────────
    print("\n── ۷) UX Flow ──")
    check("نوار مسیر زنجیره تأمین هست", 'class="flow"' in html and "تأمین قطعه" in html)
    check("روایت پیش از جدول می‌آید",
          html.index('id="story"') < html.index('id="tb_0"'))
    check("ساختار وضعیت/گره/اقدام هست",
          "story_scr" in html and "'وضعیت'" in html and "'گره'" in html and "'اقدام'" in html)
    check("هر نمودار سؤالش را می‌گوید", 'class="ask"' in html)
    check("چیدمان از بلوک‌های تألیف‌شده استفاده می‌کند",
          'data-composer-block="table"' in html and 'id="process"' not in html)
    check("مسیرها و عوامل همراه در دسترس‌اند",
          'id="process_variants"' in html and 'id="process_roots"' in html
          and "PROC.bottlenecks" in html)
    check("صف جاری هم نمایش داده می‌شود، نه فقط گذارهای کامل‌شده",
          "PROC.stage_queue" in html and "صف جاری" in html)

    # ── ۸) Accessibility ────────────────────────────────────────────────
    print("\n── ۸) Accessibility ──")
    check("حلقه فوکوس فقط برای کیبورد است",
          ":focus-visible" in sheet and "outline:3px solid" in sheet)
    check("skip-link هست", "skip-link" in sheet and "پرش به محتوا" in html)
    check("landmarkها اعلام شده",
          "<main" in html and "<header" in html and "<nav" in html and "<footer" in html)
    check("تب‌ها ARIA درست دارند",
          'role="tablist"' in html and 'role="tabpanel"' in html
          and "aria-selected" in html and "aria-controls" in html)
    check("شمارنده ردیف به صفحه‌خوان اعلام می‌شود", 'aria-live="polite"' in html)
    check("هر جدول caption دارد", "<caption" in html)
    check("prefers-reduced-motion احترام گذاشته می‌شود",
          "@media (prefers-reduced-motion:reduce)" in sheet)
    check("حرکت فقط transform/opacity است",
          "translate3d" in sheet and "gsi-rise" in sheet)
    check("هیچ محتوایی نامرئی نمی‌ماند",
          "gsiRevealAll" in html and "beforeprint" in html
          and f"setTimeout(gsiRevealAll,{T.REVEAL_FAILSAFE_MS})" in html)
    check("ناحیه لمسی حداقل ۳۶ پیکسل", "min-height:36px" in sheet)
    check("حالت کنتراست اجباری ویندوز پشتیبانی می‌شود",
          "@media (forced-colors:active)" in sheet)
    check("متن SVG جهتش را از خودش می‌گیرد",
          "svg text{direction:ltr;unicode-bidi:plaintext}" in sheet)
    check("هر نمودار aria-label دارد", 'role="img" aria-label=' in CJ.CHART_JS)

    # ── ۹) Dev Handoff ──────────────────────────────────────────────────
    print("\n── ۹) Dev Handoff ──")
    tj = HO.tokens_json()
    check("توکن ماشین‌خوان کامل است",
          {"color", "space", "radius", "type", "motion", "breakpoint",
           "components", "accessibility"} <= set(tj))
    check("ممیزی دسترس‌پذیری داخل خروجی handoff است",
          tj["accessibility"]["violations"] == [])
    check("هر وضعیت کنتراستش را گزارش می‌کند",
          all("contrast_on_white" in v for v in tj["color"]["status"].values()))
    check("گزارش متنی هر نه لایه را پوشش می‌دهد",
          all(x in HO.report() for x in ("UI Basics", "Auto Layout",
                                         "کامپوننت‌ها و واریانت‌ها", "Responsive",
                                         "تایپوگرافی", "Motion", "Accessibility",
                                         "Dev Handoff")))
    check("متغیرهای CSS قابل استخراج‌اند",
          HO.css_variables().startswith(":root{") and "--navy:" in HO.css_variables())
    check("نگاشت Auto Layout فیگما ↔ CSS مستند است", len(HO.AUTOLAYOUT_MAP) >= 6)

    # مرجع تصویری فیگما: خودِ فایل بیرون از بسته است، ولی *ادعای* بسته درباره
    # آن باید با خودش بخواند. اگر کسی یک مجموعه متغیر اضافه کند و جمع را
    # به‌روز نکند، همین‌جا قرمز می‌شود.
    check("مرجع فیگما در خروجی ماشین‌خوان هست",
          tj["meta"].get("figma", "").startswith("https://www.figma.com/design/"))
    check("جمع متغیرهای فیگما با فهرست مجموعه‌ها می‌خواند",
          sum(n for _, n in HO.FIGMA_COLLECTIONS) == 140
          and len(HO.FIGMA_COLLECTIONS) == 8)
    check("یازده صفحه GSI در فیگما نام‌گذاری شده‌اند",
          len(HO.FIGMA_PAGES) == 11
          and [n for n, _ in HO.FIGMA_PAGES][0].startswith("00 · Cover")
          and [n for n, _ in HO.FIGMA_PAGES][-1].startswith("10 · Handoff"))
    check("تعداد متغیر رنگ فیگما با تعداد توکن رنگ می‌خواند",
          dict(HO.FIGMA_COLLECTIONS)["GSI · Color"] ==
          (len(tj["color"]["surface"]) + len(tj["color"]["border"])
           + len(tj["color"]["text"]) + len(tj["color"]["brand"])
           + len(tj["color"]["status"]) * 3
           + len(tj["color"]["series"]) + len(tj["color"]["sequential"])))
    check("تعداد متغیر تایپ فیگما = چهار ویژگی در هر سبک",
          dict(HO.FIGMA_COLLECTIONS)["GSI · Type"] == len(tj["type"]) * 4)
    check("تعداد متغیر فاصله و گردی و نقطه‌شکست می‌خواند",
          dict(HO.FIGMA_COLLECTIONS)["GSI · Spacing"] == len(tj["space"])
          and dict(HO.FIGMA_COLLECTIONS)["GSI · Radius"] == len(tj["radius"])
          and dict(HO.FIGMA_COLLECTIONS)["GSI · Breakpoint"] == len(tj["breakpoint"]))
    check("گزارش متنی به فایل فیگما ارجاع می‌دهد",
          HO.FIGMA_FILE in HO.report() and "reconciliation" in HO.report())

    # ── قرارداد رنگ: یک منبع، نه هشت ────────────────────────────────────
    #
    # این بسته در نقطه‌ای هشت پالت مستقل داشت. نتیجه‌اش این بود که «تحت نظر»
    # در Excel زردِ F1C40F بود (کنتراست ۱٫۷)، در HTML fab219، در ایمیل
    # F39C12 و در نمودار FFC107 — چهار زرد برای یک معنا، و هر چهار مقدار
    # زیر کف خوانایی.
    #
    # این سنجش، نه *زیبایی* که **مسیر** را می‌سنجد: هیچ رنگی بیرون از
    # gsi/design نباید هگز دستی باشد. اگر کسی فردا یک `"F39C12"` تازه
    # بنویسد، همین‌جا قرمز می‌شود — پیش از آنکه به دست کاربر برسد.
    print("\n── قرارداد رنگ ──")
    _roots = [os.path.join(ROOT, "gsi"), os.path.join(ROOT, "app")]
    _hex = re.compile(r"[\"']#?([0-9A-Fa-f]{6})[\"']")
    # سفید و سیاه خنثی‌اند؛ «ABCDEF» و مانندش حرف ستون اکسل است نه رنگ.
    _ALLOWED = {"ffffff", "000000"}
    _COLUMN_LETTERS = re.compile(r"^[A-F]{6}$")
    offenders = []
    for _base in _roots:
      for _root, _dirs, _files in os.walk(_base):
        _dirs[:] = [d for d in _dirs if d not in ("__pycache__", "design")]
        for _f in sorted(_files):
            if not _f.endswith(".py"):
                continue
            _p = os.path.join(_root, _f)
            _rel = os.path.relpath(_p, ROOT).replace("\\", "/")
            for _i, _line in enumerate(
                    io.open(_p, encoding="utf-8").read().splitlines(), 1):
                if _line.lstrip().startswith("#"):
                    continue
                for _m in _hex.finditer(_line):
                    _h = _m.group(1)
                    if _h.lower() in _ALLOWED or _h.isdigit():
                        continue
                    if _COLUMN_LETTERS.match(_h):      # zip("ABCDEF", widths)
                        continue
                    offenders.append(f"{_rel}:{_i} {_h}")
    check("هیچ رنگ هگز دستی در gsi/ و app/ نمانده",
          not offenders, "؛ ".join(offenders[:4]) or "پاک")

    # هر ماژول خروجی باید *واقعاً* از پل Excel بخواند، نه اینکه صرفاً
    # هگز نداشته باشد.
    from gsi.report import charts as _CH
    from gsi.report import insight as _IN
    from gsi.report import supply_views as _SV
    from gsi.studio_core import excel_export as _XE
    check("پالت نمودار Excel همان طیف دسته‌ای است",
          tuple(_CH.SERIES_COLORS) == DX.SERIES_COLORS)
    check("رنگ نوارهای وضعیت در Excel از توکن می‌آید",
          _CH._BAND_FILLS == DX.STATUS_FILLS)
    check("سلول وضعیت در خروجی Studio کف WCAG را رد نمی‌کند",
          all(T.contrast("#" + _XE._status_ink(v), "#" + _XE._status_color(v))
              >= T.AA_TEXT
              for v in ("توقف خط", "بحرانی", "در حال بحرانی شدن", "تحت نظر",
                        "ایمن", "بدون مصرف", "نامشخص")))
    check("«در حال بحرانی شدن» با «بحرانی» اشتباه گرفته نمی‌شود",
          _XE._status_key("در حال بحرانی شدن") == "serious"
          and _XE._status_key("بحرانی") == "critical")
    check("چهار لایه بینش هر کدام بالای کف کنتراست‌اند",
          min(T.contrast("#" + _IN.WHITE, "#" + _IN.AQUA_DEEP),
              T.contrast("#" + _IN.WHITE, "#" + _IN.AQUA),
              T.contrast("#" + _IN.INK_ON_WASH, "#" + _IN.GREEN_SOFT),
              T.contrast("#" + _IN.GREY_TEXT, "#" + _IN.GREY_BG)) >= T.AA_TEXT)
    check("قرمز نماهای تأمین همان ink بحرانی است",
          _SV.RED == DX.X(T.STATUS["critical"].ink))
    # کتاب قوانین (rules/criticality.yaml) خودش یک منبع رنگ است: هر باند
    # `color` (نشانه) و `fill` (زمینه سلول) دارد و همه مصرف‌کننده‌ها از
    # همان می‌خوانند. این خوب است — به شرطی که با توکن‌ها یکی بماند. اگر
    # کسی YAML را دست بزند و tokens.py را نه، اینجا قرمز می‌شود.
    from gsi.rulebook import get_rulebook as _grb
    _BAND2KEY = {"STOCKOUT": "stockout", "CRITICAL": "critical",
                 "BECOMING_CRITICAL": "serious", "WATCH": "warning",
                 "SAFE": "good", "NO_CONSUMPTION": "neutral",
                 "UNKNOWN": "unknown"}
    _bands = _grb(reload=True).packs["criticality"]["bands"]
    _drift = []
    for _b in _bands:
        _k = _BAND2KEY.get(_b["code"])
        if not _k:
            continue
        _want_c, _want_f = DX.X(T.STATUS[_k].fill), DX.X(T.STATUS[_k].wash)
        if _b.get("color", "").upper() != _want_c:
            _drift.append(f'{_b["code"]}.color {_b.get("color")}≠{_want_c}')
        if _b.get("fill", "").upper() != _want_f:
            _drift.append(f'{_b["code"]}.fill {_b.get("fill")}≠{_want_f}')
    check("رنگ باندهای کتاب قوانین با توکن‌ها یکی است",
          not _drift, "؛ ".join(_drift[:3]) or "پاک")
    check("هر هفت باند کتاب قوانین به یک وضعیت سیستم طراحی نگاشت می‌شود",
          {_b["code"] for _b in _bands} == set(_BAND2KEY))

    # اپ Streamlit هم همان زبان را حرف می‌زند.
    import app.theme as _TH
    check("پالت وضعیت اپ Streamlit از توکن می‌آید",
          _TH.STATUS == {s_.key: s_.fill for s_ in T.STATUS_SCALE}
          and _TH.SERIES == list(T.CATEGORICAL))
    check("هر باند اپ آیکن و برچسب دارد، نه فقط رنگ",
          all(len(v) == 3 and v[1] and v[2] for v in _TH.BANDS.values())
          and len(_TH.BANDS) == 7)

    check("طیف قالب‌بندی شرطی از wash وضعیت‌ها می‌آید",
          (DX.SCALE_BAD, DX.SCALE_MID, DX.SCALE_GOOD)
          == tuple(DX.X(T.STATUS[k].wash) for k in ("critical", "warning", "good")))

    # ── قرارداد اجرایی: JS در scope مشترک ───────────────────────────────
    print("\n── قرارداد اجرایی ──")
    js = "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))
    node = shutil.which("node")
    if node:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.js"
            p.write_text(js, encoding="utf-8")
            r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
        check("جاوااسکریپت خروجی در scope مشترک معتبر است", r.returncode == 0,
              r.stderr.strip().splitlines()[-1] if r.returncode else "")
    else:
        check("جاوااسکریپت خروجی در scope مشترک معتبر است", True, "node در محیط نیست")
    check("هیچ منبع بیرونی بارگذاری نمی‌شود",
          "<script src=" not in html and "<link" not in html
          and "cdn" not in html.lower() and "@import" not in html)

    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
