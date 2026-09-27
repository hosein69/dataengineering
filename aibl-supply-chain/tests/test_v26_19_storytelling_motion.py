# -*- coding: utf-8 -*-
"""V26.19 — روایت داده، تحلیل فرآیند، فیلتر تاریخ، کنتراست و حرکت.

این مجموعه چهار چیز را قفل می‌کند که هرکدام یک‌بار در تولید شکسته بودند:

۱. **کنتراست پالت.** ادعا نمی‌شود؛ محاسبه می‌شود. هر توکن متنی باید کف
   WCAG AA را بگذراند و :func:`audit_contrast` باید فهرست خالی بدهد.
۲. **برچسب SVG در سند راست‌به‌چپ.** بدون قاعده ``unicode-bidi:plaintext``
   هر برچسب نمودار زیر میله می‌رفت. اینجا وجود همان قاعده تضمین می‌شود.
۳. **نمایان شدن محتوا.** لایه حرکت نباید هیچ عنصری را برای همیشه نامرئی
   بگذارد: مهلت ایمنی، ``beforeprint`` و ``prefers-reduced-motion`` هر سه
   باید در خروجی باشند.
۴. **دانه‌ی روایت.** روایت باید با «پس چه» بیاید، نه فهرست عدد.
"""
from __future__ import annotations

import json
import re
import subprocess
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from aibl.report import design_system as ds
from aibl.report.storytelling import (build_story, process_metrics,
                                      trend_series, Finding)
from aibl.studio_core.chart_catalog import (CHART_SPECS, CHART_TITLES,
                                            HISTORY_CHARTS)
from aibl.studio_core.html_export import build_dynamic_html
from aibl.integrations.daily_email import (build_email_html, _kpi_cards,
                                           _attach_deltas, _outlook_session)

PASS: list = []
FAIL: list = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(("✅ " if ok else "❌ ") + name + (f" → {detail}" if detail else ""))


def _sample(n: int = 400) -> pd.DataFrame:
    base = pd.Timestamp("2026-05-01")
    return pd.DataFrame({
        "CASE_KEY": [f"C{i}" for i in range(n)],
        "KEY_MATERIAL": [f"MAT-{i%40:03d}" for i in range(n)],
        "CANONICAL_ORDER": [f"ORD-{i%55:04d}" for i in range(n)],
        "KEY_REG": [f"REG-{i%50}" for i in range(n)],
        "ORG_DEPT": [["خرید خارجی", "گمرک و ترخیص", "حمل"][i % 3] for i in range(n)],
        "بحرانی (کوتاه)": [["توقف خط", "بحرانی", "تحت نظر", "ایمن"][i % 4] for i in range(n)],
        "مقاومت (روز)": [float(i % 60) for i in range(n)],
        "روزهای رسوب": [float(i % 95) for i in range(n)],
        "مانده تعهد": [float((i % 30) * 1000) for i in range(n)],
        "روزهای تأخیر": [float(i % 45 - 10) for i in range(n)],
        "تاریخ ثبت سفارش": [base + pd.Timedelta(days=i % 180) for i in range(n)],
    })


def _eventlog(cases: int = 60) -> pd.DataFrame:
    acts = ["ثبت سفارش", "تخصیص ارز", "حمل بین‌الملل", "اظهار گمرکی", "ترخیص"]
    rows = []
    for c in range(cases):
        t = pd.Timestamp("2026-04-01") + pd.Timedelta(days=c % 20)
        for k, a in enumerate(acts):
            rows.append({"_CASE_KEY": f"C{c}", "CASE_KEY": f"C{c}",
                         "ACTIVITY_FA": a, "EVENTTIME": t})
            t += pd.Timedelta(days=3 + (c % 7) + k)
    return pd.DataFrame(rows)


def _history() -> pd.DataFrame:
    return pd.DataFrame({
        "تاریخ": [f"2026-09-{d:02d}" for d in range(1, 11)],
        "متریال بحرانی": [80, 78, 76, 77, 72, 70, 71, 66, 64, 61],
        "متریال توقف خط": [12, 11, 11, 10, 9, 9, 8, 7, 7, 6],
        "مانده تعهد معوق": [9.0e6 - 5e4 * i for i in range(10)],
        "میانگین مقاومت": [30 + 0.4 * i for i in range(10)],
        "میانگین رسوب": [50 - 0.5 * i for i in range(10)],
    })


def main() -> int:
    # ── ۱) کنتراست سنجیده‌شده ──
    bad = ds.audit_contrast()
    check("پالت کف WCAG AA را می‌گذراند", not bad,
          "; ".join(f"{n} {r}" for n, _f, _b, r in bad[:3]))
    check("نسبت کنتراست درست محاسبه می‌شود",
          ds.contrast_ratio("#000000", "#ffffff") == 21.0
          and ds.contrast_ratio("#ffffff", "#ffffff") == 1.0)
    check("هر طبقه وضعیت رنگ متن جدا از رنگ سطح دارد",
          all(s.ink != s.fill for s in ds.STATUS_SCALE))
    check("مرز سطح رنگی کف ۳ را دارد، حتی برای زرد",
          all(ds.contrast_ratio(s.stroke, ds.SURFACE_RAISED) >= ds.AA_LARGE
              for s in ds.STATUS_SCALE))

    # ── ۲) کاتالوگ نمودار ──
    kinds = {s.kind for s in CHART_SPECS.values()}
    check("کاتالوگ شامل شکل‌های روند و پارتو هم هست",
          {"bar", "donut", "scatter", "grouped", "trend", "pareto"} <= kinds,
          str(sorted(kinds)))
    check("نمودارهای روند علامت‌گذاری شده‌اند",
          set(HISTORY_CHARTS) and all(CHART_SPECS[k].kind == "trend" for k in HISTORY_CHARTS))
    check("هر نمودار یک سؤال تصمیم‌ساز دارد",
          all(s.question.strip() for s in CHART_SPECS.values()))

    # ── ۳) روند و مقایسه با اجرای قبلی ──
    tr = trend_series(_history())
    d = tr["deltas"]["متریال بحرانی"]
    check("دلتا جهت «بهتر» هر KPI را می‌فهمد", d["change"] == -3.0 and d["improving"] is True,
          json.dumps(d, ensure_ascii=False))
    up = trend_series(_history())["deltas"]["میانگین مقاومت"]
    check("برای KPIای که بالاتر بهتر است، افزایش «بهبود» شمرده می‌شود",
          up["change"] > 0 and up["improving"] is True)
    check("نبود تاریخچه خطا نیست", trend_series(None)["points"] == 0)
    check("تاریخچه تک‌ردیفی دلتا نمی‌سازد",
          trend_series(_history().head(1))["deltas"] == {})

    # ── ۴) تحلیل فرآیند ──
    pm = process_metrics({"eventlog": _eventlog()})
    check("معیار فرآیند بر میانه و صدک ۹۰ بنا شده، نه میانگین",
          pm["cycle_median"] is not None and pm["cycle_p90"] is not None
          and pm["cycle_p90"] >= pm["cycle_median"])
    check("گلوگاه بر مجموع زمان تلف‌شده مرتب می‌شود",
          pm["bottlenecks"] and pm["bottlenecks"][0]["total_days"]
          >= pm["bottlenecks"][-1]["total_days"])
    check("کارایی جریان، دوباره‌کاری و تمرکز واریانت محاسبه می‌شوند",
          pm["flow_efficiency"] is not None and pm["rework_rate"] is not None
          and pm["variant_concentration"] is not None)
    check("قانون لیتل برای اعتبارسنجی متقابل ظرفیت می‌آید",
          pm["wip_littles_law"] is not None)
    # بدون لاگ رویداد هیچ گلوگاه فرضی ساخته نمی‌شود
    fallback = process_metrics({}, _sample().assign(STAGE_FA="گمرک"))
    check("بدون Event Log گلوگاه فرضی ساخته نمی‌شود",
          fallback["basis"] == "stage" and fallback["bottleneck"] is None)

    # ── ۵) روایت ──
    df = _sample()
    st = build_story(df, {"eventlog": _eventlog()}, tr, ref_date="2026-09-15")
    check("روایت ساختار وضعیت/گره/اقدام دارد",
          all([st.headline, st.situation, st.complication, st.resolution]))
    check("هر یافته «پس چه» دارد", st.findings
          and all(f.so_what.strip() for f in st.findings))
    check("هر یافته بزرگی و مبنای مقایسه دارد",
          all(f.magnitude.strip() and f.comparison.strip() for f in st.findings))
    check("اقدام به موضوع مشخص اشاره می‌کند",
          any(f.focus.strip() for f in st.findings))
    check("رنگ یافته از پالت سنجیده‌شده می‌آید",
          all(f.color in {s.ink for s in ds.STATUS_SCALE} for f in st.findings))
    empty = build_story(df.head(0), {}, tr)
    check("برش خالی روایت صریح دارد، نه خطا",
          "خالی" in empty.headline and not empty.findings)

    # ── ۶) HTML: فیلتر تاریخ، اصلاح RTL، حرکت ──
    html = build_dynamic_html(
        df, "2026-09-15", max_rows=400,
        selected_fields=["KEY_MATERIAL", "ORG_DEPT", "بحرانی (کوتاه)",
                         "مقاومت (روز)", "مانده تعهد", "تاریخ ثبت سفارش"],
        charts=["criticality", "trend_critical", "sediment_vs_resistance",
                "pareto_delay", "commitment"],
        show_process=True, process_extras={"eventlog": _eventlog()})
    check("فیلتر بازه تاریخ در خروجی هست",
          'class="daterange"' in html and "datePreset(" in html
          and 'class="dfrom"' in html and 'class="dto"' in html)
    check("ستون تاریخ به‌درستی شناسایی شده",
          '"تاریخ ثبت سفارش"' in html and '"dates": ["تاریخ ثبت سفارش"]' in html)
    check("ستون تاریخ به‌عنوان فیلتر افتادنی تکرار نشده",
          html.count('data-f="تاریخ ثبت سفارش"') == 0)
    # اصلاح اصلی ۲۶٫۱۹ — بدون این قاعده، برچسب زیر میله می‌رود
    check("متن SVG جهتش را از خودش می‌گیرد (اصلاح برچسب RTL)",
          "svg text{direction:ltr;unicode-bidi:plaintext}" in html)
    check("لایه حرکت reduced-motion را احترام می‌گذارد",
          "@media (prefers-reduced-motion:reduce)" in html)
    check("حرکت فقط transform/opacity است، نه width/top",
          "translate3d" in html and "animation:aibl-rise" in html)
    check("هیچ محتوایی نامرئی نمی‌ماند: مهلت ایمنی و beforeprint",
          "aiblRevealAll" in html and "beforeprint" in html
          and f"setTimeout(aiblRevealAll,{ds.REVEAL_FAILSAFE_MS})" in html)
    check("هیچ کتابخانه بیرونی بارگذاری نمی‌شود",
          "<script src=" not in html and "cdn" not in html.lower()
          and "<link" not in html)
    check("پراکنش محور، خط روند و ضریب همبستگی دارد",
          "axis-title" in html and "trend-line" in html and "همبستگی r" in html)
    check("پارتو منحنی تجمعی و خط ۸۰٪ دارد",
          "ref80" in html and "pareto-bar" in html)
    check("نمودار روند مبنایش را صریح می‌گوید",
          "snapshot تاریخی" in html)
    check("روایت زنده در HTML بازمحاسبه می‌شود",
          "function sliceStory(" in html and 'id="story_findings"' in html)
    check("معیارهای فرآیند در HTML می‌آیند",
          "کارایی جریان" in html and "نرخ دوباره‌کاری" in html
          and "تمرکز واریانت" in html)
    check("قرارداد نسخه‌های قبل نشکسته",
          "روایت این برش" in html and "downloadFilteredXlsx" in html
          and "PAGE_SIZE=100" in html and "function rows(t)" in html
          and "function exportPdf(){window.print()}" in html)
    check("چرخه رویداد تکراری نشده",
          html.count("addEventListener('click'") == 1)

    node = shutil.which("node")
    if node:
        js = "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.js"
            p.write_text(js, encoding="utf-8")
            r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
        check("JavaScript خروجی از نظر syntax معتبر است", r.returncode == 0,
              r.stderr[-160:])
    else:
        check("JavaScript خروجی از نظر syntax معتبر است", True, "node در محیط نیست")

    # ── ۷) ایمیل ──
    mail = build_email_html(pd.Timestamp("2026-09-15").date(), df, [],
                            Path("2026-09-15_AIBL_Interactive_Report.html"),
                            header_title="هدر اختصاصی", intro_text="مقدمه اختصاصی",
                            process_extras={"eventlog": _eventlog()},
                            footer_note="پانویس اختصاصی مدیر")
    check("ایمیل بلوک روایت دارد",
          "مسیر تصمیم" in mail and "وضعیت" in mail and "گره" in mail and "اقدام" in mail)
    check("هدر، مقدمه و پانویس کاستوم رعایت می‌شوند",
          "هدر اختصاصی" in mail and "مقدمه اختصاصی" in mail and "پانویس اختصاصی مدیر" in mail)
    check("ایمیل بدون روایت هم ساخته می‌شود",
          "مسیر تصمیم" not in build_email_html(
              pd.Timestamp("2026-09-15").date(), df, [], Path("r.html"), show_story=False))
    # کارت KPI نباید از عرض جدول بیرون بزند
    cards = _kpi_cards([{"label": f"K{i}", "value": i, "tone": "red", "note": "n"}
                        for i in range(6)])
    widths = {int(x.rstrip("%")) for x in re.findall(r"width:(\d+)%", cards)}
    check("کارت‌های KPI از ۱۰۰٪ عرض بیرون نمی‌زنند",
          cards.count("<tr>") == 2 and all(w * 3 <= 100 for w in widths),
          str(sorted(widths)))
    kp = _attach_deltas([{"label": "متریال بحرانی", "value": 61, "tone": "red"}], tr)
    check("KPI ایمیل نشان تغییر نسبت به اجرای قبلی می‌گیرد",
          "بهبود" in kp[0].get("delta", ""), kp[0].get("delta", ""))
    check("رنگ متن KPI از پالت سنجیده‌شده می‌آید",
          ds.STATUS["critical"].ink in mail and "#F39C12" not in mail)

    # ── ۸) هات‌فیکس Outlook COM ──
    # روی لینوکس pywin32 نیست؛ قرارداد این است که پیام راهنما بدهد نه
    # ImportError خام — و در هر مسیری COM را متوازن رها کند.
    try:
        with _outlook_session():
            check("مدیر زمینه Outlook روی ویندوز باز می‌شود", True)
    except RuntimeError as ex:
        check("نبودن pywin32 پیام راهنما می‌دهد، نه ImportError خام",
              "pywin32" in str(ex))
    except Exception as ex:      # pragma: no cover
        check("نبودن pywin32 پیام راهنما می‌دهد، نه ImportError خام", False, repr(ex))
    src = Path(__file__).resolve().parents[1] / "aibl" / "integrations" / "daily_email.py"
    text = src.read_text(encoding="utf-8")
    check("COM روی نخ جاری مقداردهی می‌شود", "pythoncom.CoInitialize()" in text)
    check("COM در مسیر خطا هم آزاد می‌شود",
          "finally:" in text and "CoUninitialize" in text)
    check("هیچ فراخوانی Outlook خارج از مدیر زمینه نمانده",
          text.count('win32.Dispatch("Outlook.Application")') == 2
          and text.count("with _outlook_session()") == 2)

    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
