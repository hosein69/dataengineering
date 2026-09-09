# -*- coding: utf-8 -*-
"""تست گزارش تحلیلی و نمودارهای داینامیک.

بخش ۱ تا ۴ روی داده‌ای با **اثر کاشته‌شده** کار می‌کند: می‌دانیم پاسخ درست
چیست، پس می‌شود سنجید که تحلیل آن را پیدا می‌کند و مخدوش‌کننده محض را
اشتباهاً «یافته» اعلام نمی‌کند.

اجرا:  python tests/test_analytics.py
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aibl.analytics import cycle  # noqa: E402
from aibl.analytics.drivers import Outcome, analyse  # noqa: E402
from aibl.analytics.evidence import (MIN_N, contrast,  # noqa: E402
                                     median_iqr, stratified_diff, wilson)
from aibl.analytics.report import build_analysis_html  # noqa: E402
from aibl.studio_core.html_export import CATEGORICAL, build_dynamic_html  # noqa: E402

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


def planted(n: int = 1200, seed: int = 7) -> pd.DataFrame:
    """داده با پاسخ معلوم.

    * «روش حمل = هوایی» اثر **واقعی** ‎+۲۰ واحد درصد دارد.
    * «نوع پرونده» هیچ اثری ندارد ولی با مدیریت شدیداً همبسته است —
      یک مخدوش‌کننده محض که تحلیل خام باید فریبش را بخورد و تحلیل
      کنترل‌شده نباید.
    """
    rng = np.random.default_rng(seed)
    dept = rng.choice(["مواد اولیه", "قطعات تولیدی"], n, p=[.6, .4])
    mode = rng.choice(["دریایی", "هوایی", "زمینی"], n, p=[.55, .25, .20])
    kind = np.where(dept == "مواد اولیه",
                    rng.choice(["عادی", "فوری"], n, p=[.85, .15]),
                    rng.choice(["عادی", "فوری"], n, p=[.15, .85]))
    p = np.where(dept == "مواد اولیه", .20, .45) + np.where(mode == "هوایی", .20, 0)
    crit = rng.random(n) < p
    base = pd.Timestamp("2026-01-01")

    def jd(off):
        return [(base + pd.Timedelta(days=int(x))).strftime("%Y/%m/%d") for x in off]

    d0 = rng.integers(0, 60, n)
    return pd.DataFrame({
        "کد طبقه بحرانی": np.where(crit, "CRITICAL", "SAFE"),
        "روش حمل": mode, "ORG_DEPT": dept, "نوع پرونده": kind,
        "روزهای تأخیر": rng.integers(0, 30, n),
        "روزهای رسوب": rng.integers(0, 70, n),
        "BL_DATE": jd(d0), "ARRIVAL_DATE": jd(d0 + rng.integers(8, 40, n)),
        "DISCHARGE_DATE": jd(d0 + rng.integers(45, 60, n)),
        "COT_DATE": jd(d0 + rng.integers(62, 120, n)),
    })


_OC = Outcome("c", "بحرانی شدن", "طبقه بحرانی برابر CRITICAL باشد.",
              lambda d: d["کد طبقه بحرانی"].eq("CRITICAL"))


# ═══════════ ۱) پایه‌های آماری ═══════════
def test_evidence() -> None:
    print("\n── ۱) نرخ، بازه اطمینان، و کف نمونه ──")
    r = wilson(50, 100)
    check("نرخ درست محاسبه می‌شود", abs(r.p - 0.5) < 1e-9)
    check("بازه، نرخ را در بر می‌گیرد", r.lo < r.p < r.hi, f"{r.lo:.3f}–{r.hi:.3f}")
    check("بازه Wilson روی نسبت صفر از بازه بیرون نمی‌زند",
          wilson(0, 40).lo >= 0 and wilson(0, 40).hi <= 1)
    check("روی نسبت یک هم همین‌طور",
          wilson(40, 40).lo >= 0 and wilson(40, 40).hi <= 1)
    check("نمونه بزرگ‌تر ⇒ بازه باریک‌تر",
          wilson(500, 1000).width < wilson(50, 100).width)
    check("n صفر خطا نمی‌دهد", wilson(0, 0).n == 0)
    check(f"زیر کف نمونه (n<{MIN_N}) «کافی» شمرده نمی‌شود",
          not wilson(3, 10).enough and wilson(10, MIN_N).enough)

    m, q1, q3, n = median_iqr(pd.Series([1, 2, 3, 4, 100]))
    check("میانه در برابر مقدار پرت مقاوم است", m == 3, str(m))
    check("بازه میان‌چارکی گزارش می‌شود", q1 == 2 and q3 == 4, f"{q1}–{q3}")
    check("ستون خالی، صفر نمونه می‌دهد", median_iqr(pd.Series([], dtype=float))[3] == 0)


# ═══════════ ۲) اثر واقعی پیدا می‌شود ═══════════
def test_real_effect() -> None:
    print("\n── ۲) اثر کاشته‌شده باید پیدا شود ──")
    df = planted()
    rep = analyse(df, _OC, factors=["روش حمل"], control="ORG_DEPT")
    air = next(f for f in rep.findings if f.level == "هوایی")
    check("تفاضل خام نزدیک اثر واقعی (+۲۰) است",
          15 < air.crude.diff * 100 < 27, f"{air.crude.diff * 100:+.1f}")
    check("پس از کنترل هم می‌ماند",
          air.adjusted is not None and 15 < air.adjusted * 100 < 27,
          f"{air.adjusted * 100:+.1f}")
    check("داوری «پایدار» است", air.robust, air.verdict)
    check("E-value بزرگ‌تر از ۱ است", air.crude.e_value > 1.5, f"{air.crude.e_value:.2f}")


# ═══════════ ۳) مخدوش‌کننده محض نباید «یافته» شود ═══════════
def test_confounder() -> None:
    print("\n── ۳) مخدوش‌کننده محض نباید یافته اعلام شود ──")
    df = planted()
    rep = analyse(df, _OC, factors=["نوع پرونده"], control="ORG_DEPT")
    urgent = next(f for f in rep.findings if f.level == "فوری")
    check("مقایسه خام فریب می‌خورد (تفاوت بزرگ نشان می‌دهد)",
          abs(urgent.crude.diff) > 0.08, f"{urgent.crude.diff * 100:+.1f}")
    check("ولی پس از کنترل فرو می‌ریزد",
          urgent.adjusted is not None and abs(urgent.adjusted) < 0.05,
          f"{urgent.adjusted * 100:+.1f}")
    check("و «پایدار» اعلام نمی‌شود", not urgent.robust, urgent.verdict)
    check("داوری صریح می‌گوید کم‌رنگ شده",
          "کم‌رنگ" in urgent.verdict, urgent.verdict)


# ═══════════ ۴) محافظه‌کاری ═══════════
def test_guards() -> None:
    print("\n── ۴) هرجا شواهد کم است، ادعا نمی‌شود ──")
    small = planted(n=30)
    rep = analyse(small, _OC, factors=["روش حمل"], control="ORG_DEPT")
    if rep is not None:
        check("در نمونه کوچک، هیچ محرکی «کافی» اعلام نمی‌شود",
              all(not f.crude.enough for f in rep.findings)
              or not any(f.robust for f in rep.findings))
    else:
        check("در نمونه کوچک اصلاً گزارشی ساخته نمی‌شود", True)

    tiny = planted(n=10)
    check("زیر کف نمونه، تحلیل None برمی‌گرداند",
          analyse(tiny, _OC, factors=["روش حمل"]) is None)

    # لایه‌بندی وقتی هیچ لایه‌ای داده کافی ندارد
    d = planted(n=60)
    adj, used, _ = stratified_diff(d["روش حمل"].eq("هوایی"),
                                   d["کد طبقه بحرانی"].eq("CRITICAL"),
                                   pd.Series(range(len(d))).astype(str))
    check("لایه‌های تک‌نفره ⇒ تفاضل کنترل‌شده None، نه عددی بی‌پشتوانه",
          adj is None and used == 0, f"adj={adj}")

    df = planted()
    y = df["کد طبقه بحرانی"].eq("NEVER")
    c = contrast("هیچ", df["روش حمل"].eq("هوایی"), y)
    check("پیامدی که هرگز رخ نمی‌دهد، معنادار اعلام نمی‌شود", not c.significant)


# ═══════════ ۵) زمان ═══════════
def test_cycle() -> None:
    print("\n── ۵) زمان کجا می‌رود ──")
    df = planted()
    legs = cycle.legs(df)
    check("گام‌های چرخه از رویدادهای تاریخ‌دار ساخته می‌شوند", len(legs) >= 2, str(len(legs)))
    check("هر گام میانه و تعداد دارد",
          all(x.n > 0 and x.median == x.median for x in legs))
    top = cycle.bottleneck(legs)
    check("گلوگاه شناسایی می‌شود", top is not None and top.enough, top.frm if top else "—")
    wi = cycle.what_if(df, top)
    check("پادواقعیت محاسبه می‌شود", wi is not None)
    check("صرفه‌جویی مثبت و متناسب است",
          wi.days_saved > 0 and wi.per_case > 0, f"{wi.days_saved:,.0f} روز")
    check("فرضِ پادواقعیت صریح نوشته می‌شود", "فرض:" in wi.assumption)

    # تاریخ معکوس نباید مدت منفی وارد تحلیل کند
    bad = df.copy()
    bad.loc[bad.index[:50], "ARRIVAL_DATE"] = "2025/01/01"
    check("مدت منفی از تحلیل زمان کنار می‌رود",
          all(x.median >= 0 for x in cycle.legs(bad)))


# ═══════════ ۶) گزارش HTML ═══════════
def test_report_html() -> None:
    print("\n── ۶) گزارش تحلیلی HTML ──")
    h = build_analysis_html(planted(), "2026-09-09")
    for probe in ("نرخ پایه", "E-value", "همراهی پایدار پس از کنترل",
                  "زمان کجا می‌رود", "پادواقعیت", "روش، و حدودش",
                  "VanderWeele", "Wilson"):
        check(f"بخش «{probe}» در گزارش هست", probe in h)
    check("هشدار «علت اثبات نشده» صریح آمده", "ثابت نمی‌کند" in h)
    check("بدون وابستگی به اینترنت است (هیچ src بیرونی)",
          "http://" not in h and "https://" not in h.replace("http://www.w3.org", ""))
    check("سند راست‌به‌چپ و فارسی است", 'dir="rtl"' in h and 'lang="fa"' in h)

    empty = build_analysis_html(pd.DataFrame({"x": [1, 2, 3]}), "2026-09-09")
    check("داده بی‌ربط ⇒ گزارش خالی ولی سالم", "یافته‌ای گزارش نشد" in empty)

    # پیامدی که هرگز رخ نمی‌دهد ⇒ جدول صفرها چاپ نمی‌شود
    d = planted()
    d["کد طبقه بحرانی"] = "SAFE"
    h2 = build_analysis_html(d, "2026-09-09")
    check("پیامد رخ‌نداده، جدول صفر تولید نمی‌کند", "رخ نداده است" in h2)


# ═══════════ ۷) نمودارهای داینامیک ═══════════
def test_dynamic_charts() -> None:
    print("\n── ۷) نمودار داینامیک در HTML سازنده گزارش ──")
    df = planted(n=200)
    df["KEY_MATERIAL"] = [f"M{i%40}" for i in range(len(df))]
    h = build_dynamic_html(df, "2026-09-09",
                           selected_fields=["KEY_MATERIAL", "روش حمل", "ORG_DEPT",
                                            "روزهای رسوب"],
                           show_visuals=True)
    for probe in ("نمودار مقایسه‌ای", "توزیع مقادیر", "drawBar", "drawHist",
                  "renderCharts", 'id="cdim"', 'id="cmeas"', 'id="hcol"'):
        check(f"«{probe}» در خروجی هست", probe in h)
    check("نمودار با هر فیلتر بازساخته می‌شود", "renderCharts(a);" in h)
    # واژه CDN در توضیحِ «چرا از CDN استفاده نشده» هست؛ آنچه اهمیت دارد
    # نبودِ تگ بیرونی است، نه نبودِ واژه.
    check("هیچ اسکریپت یا استایل بیرونی بارگذاری نمی‌شود",
          not re.search(r"<(script|link)[^>]+(src|href)\s*=\s*[\"']https?://", h),
          "پیدا شد" if re.search(r"<(script|link)[^>]+(src|href)\s*=\s*[\"']https?://", h) else "")
    check("نمودار با SVG خام ساخته می‌شود", "createElementNS" in h)
    check("تولتیپ دارد", "showTip" in h and "mousemove" in h)
    check("رسته هشتم به «سایر» می‌رود، نه رنگ تازه", "سایر (" in h)
    check("پالت رسته‌ای اعتبارسنجی‌شده به‌کار رفته",
          all(c in h for c in CATEGORICAL[:3]))
    check("هر میله برچسب مستقیم دارد (رنگ تنها حامل معنا نیست)",
          "text-anchor" in h and "lab.textContent" in h)

    off = build_dynamic_html(df, "2026-09-09", selected_fields=["روش حمل"],
                             show_visuals=False)
    check("با خاموش کردن ویژوال، نمودار ساخته نمی‌شود",
          "نمودار مقایسه‌ای" not in off)


if __name__ == "__main__":
    print("=" * 78)
    print("AIBL — گزارش تحلیلی و نمودارهای داینامیک")
    print("=" * 78)
    test_evidence()
    test_real_effect()
    test_confounder()
    test_guards()
    test_cycle()
    test_report_html()
    test_dynamic_charts()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
