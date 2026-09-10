# -*- coding: utf-8 -*-
"""تست بسته‌بندی و کف خوانایی رابط.

هر بررسی اینجا از یک خرابی **واقعی در تولید** آمده، نه از تصور.

نسخهٔ ۲۶٫۱۵٫۰ با یک دستور فوریِ پوسته بسته‌بندی شد و آن دستور فایل‌های
نقطه‌دار را برنداشت؛ `.streamlit/config.toml` در بسته نبود. بدون آن،
Streamlit تم خودش را می‌گذارد و آن تم از `prefers-color-scheme` مرورگر
پیروی می‌کند. روی ویندوزِ حالت‌تاریک نتیجه این شد:

    متن `#FAFAFA` روی پس‌زمینهٔ `#E1F2E9`  →  نسبت کنتراست ۱٫۱۵:۱

نوار کناری، برچسب فیلترها و تراشه‌های انتخاب نامرئی شدند و کاربر گزارش
داد «امکانات از بین رفته». هیچ تستی این را نگرفت، چون همهٔ تست‌ها روی
درخت کد اجرا می‌شدند نه روی بستهٔ تحویلی.
"""
from __future__ import annotations

import io
import os
import re
import sys
import zipfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


# ── ابزار سنجش کنتراست (WCAG 2.1) ────────────────────────────────────────
def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(fg, bg):
    a, b = _lum(_rgb(fg)), _lum(_rgb(bg))
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _over(fg, alpha, bg):
    f, b = _rgb(fg), _rgb(bg)
    return "#%02X%02X%02X" % tuple(
        round(f[i] * alpha + b[i] * (1 - alpha)) for i in range(3))


def test_theme_config() -> None:
    print("\n── ۱) پیکربندی تم؛ نبودنش رابط را از کار می‌اندازد ──")
    from app.theme import STREAMLIT_THEME, config_toml, theme_env

    path = os.path.join(ROOT, ".streamlit", "config.toml")
    check("`.streamlit/config.toml` در مخزن هست", os.path.exists(path))
    text = io.open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    for key, val in STREAMLIT_THEME.items():
        check(f"config.toml مقدار {key} را دارد", f'{key} = "{val}"' in text, val)
    check("تم روشن است، نه پیروِ مرورگر", STREAMLIT_THEME["base"] == "light")
    check("config_toml() همان چیزی را می‌سازد که روی دیسک است",
          config_toml().strip() == text.strip())

    env = theme_env()
    check("راه‌انداز شش کلید تم را به‌صورت متغیر محیطی می‌فرستد", len(env) == 6,
          str(sorted(env)))
    check("نام متغیرها همان چیزی است که Streamlit می‌خواند",
          env.get("STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR") ==
          STREAMLIT_THEME["secondaryBackgroundColor"])

    for launcher in ("app/run_platform.py", "app/run_dashboard.py"):
        src = io.open(os.path.join(ROOT, launcher), encoding="utf-8").read()
        check(f"{launcher} تم را به زیرفرآیند می‌دهد", "theme_env()" in src)


def test_package_contents() -> None:
    print("\n── ۲) بسته باید همان چیزی باشد که اجرا می‌شود ──")
    import make_package as mp

    names = {p.relative_to(mp.ROOT).as_posix() for p in mp.members()}
    check("جمع‌آورنده، فایل نقطه‌دار را هم برمی‌دارد",
          ".streamlit/config.toml" in names,
          f"{len(names)} پرونده")
    check("پیکربندی تم جزء فهرست الزامی است",
          ".streamlit/config.toml" in mp.REQUIRED)
    check("app/ و aibl/ کامل داخل فهرست‌اند",
          "app/studio.py" in names and "aibl/pipeline.py" in names)
    check("فایل‌های موقت داخل بسته نمی‌روند",
          not any(n.endswith((".pyc", ".zip", ".log")) or "__pycache__" in n
                  for n in names))

    zips = [f for f in os.listdir(ROOT) if re.match(r"AIBL_V\d+_\d+_\d+\.zip$", f)]
    newest = sorted(zips)[-1] if zips else None
    if newest:
        inside = set(zipfile.ZipFile(os.path.join(ROOT, newest)).namelist())
        for req in mp.REQUIRED:
            check(f"{newest} شامل {req} است", req in inside)


def test_legibility_floor() -> None:
    print("\n── ۳) کف خوانایی در CSS ──")
    from app.styles import css
    sheet = css()

    check("حالت رنگی صریح روشن است", "color-scheme: light" in sheet)
    check("نوار کناری پس‌زمینهٔ صریح دارد",
          '[data-testid="stSidebarContent"]' in sheet)
    check("پوستهٔ ورودی‌ها رنگ صریح می‌گیرد",
          '[data-testid="stMultiSelect"] > div > div' in sheet)
    check("تراشهٔ انتخاب، رنگ برند می‌گیرد نه قرمز پیش‌فرض",
          '[data-testid="stMultiSelectTagsContainer"] > span > span' in sheet)
    check("فونت به پرتال‌ها هم می‌رسد", "html, body, body *" in sheet)
    check("نام‌های مختلف نصبِ ایران‌سنس به یک خانواده گره خورده‌اند",
          "@font-face" in sheet and "IRANSansWeb" in sheet)


def test_measured_contrast() -> None:
    print("\n── ۴) کنتراست، اندازه‌گیری‌شده نه ادعاشده ──")
    from aibl.report import aqua
    from app.theme import (BAND_ORDER, STATUS, STATUS_TEXT, SURFACE, TEXT,
                           TEXT_SECONDARY, band_of, band_text_color)

    check("متن بدنه روی پس‌زمینه ≥ ۷:۱", contrast(TEXT, SURFACE) >= 7.0,
          f"{contrast(TEXT, SURFACE):.2f}:1")
    check("متن ثانویه روی پس‌زمینه ≥ ۴٫۵:۱",
          contrast(TEXT_SECONDARY, SURFACE) >= 4.5,
          f"{contrast(TEXT_SECONDARY, SURFACE):.2f}:1")
    check("سفید روی دکمهٔ برند ≥ ۴٫۵:۱",
          contrast("#FFFFFF", aqua.LIGHT["brand-strong"]) >= 4.5,
          f"{contrast('#FFFFFF', aqua.LIGHT['brand-strong']):.2f}:1")

    # تراشهٔ طبقه: پس‌زمینه همان رنگ وضعیت با ۱۰٪ شفافیت روی سطح صفحه
    worst = ("", 99.0)
    for code in BAND_ORDER:
        dot = band_of(code)[0]
        ink = band_text_color(code)
        tint = _over(dot, 0.10, SURFACE)
        cr = contrast(ink, tint)
        if cr < worst[1]:
            worst = (code, cr)
        check(f"برچسب «{band_of(code)[2]}» روی تراشه ≥ ۴٫۵:۱", cr >= 4.5,
              f"{cr:.2f}:1")
    check("بدترین تراشه هم زیر حد نمی‌رود", worst[1] >= 4.5,
          f"{worst[0]} = {worst[1]:.2f}:1")

    check("رنگ متن تراشه برای هر وضعیت تعریف شده",
          set(STATUS_TEXT) >= set(STATUS) - {"unknown"} or
          set(STATUS_TEXT) == set(aqua.STATUS_ON_TINT_LIGHT))


def test_charts_never_inherit_theme() -> None:
    print("\n── ۵) نمودار نباید تم مرورگر را به ارث ببرد ──")
    files = ["app/studio.py", "app/dashboard.py", "app/analytics.py",
             "app/process_view.py"]
    calls = bare = 0
    for f in files:
        src = io.open(os.path.join(ROOT, f), encoding="utf-8").read()
        for m in re.finditer(r"st\.plotly_chart\(([^\n]*)", src):
            calls += 1
            if "finalize(" not in m.group(1):
                bare += 1
    check("همهٔ نمودارها از finalize() رد می‌شوند", bare == 0,
          f"{calls} فراخوانی، {bare} بدون finalize")
    check("تم Streamlit روی نمودار خاموش است",
          all("theme=None" in io.open(os.path.join(ROOT, f), encoding="utf-8").read()
              for f in files))

    from app.theme import SURFACE_RAISED, finalize
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("… plotly نصب نیست؛ بررسی زندهٔ شکل رد شد")
        return
    fig = finalize(go.Figure(go.Bar(x=[1, 2], y=[3, 4])))
    check("بومِ نمودار روی layout نشسته، نه روی قالب",
          fig.layout.paper_bgcolor == SURFACE_RAISED
          and fig.layout.plot_bgcolor == SURFACE_RAISED,
          str(fig.layout.paper_bgcolor))


def test_send_actually_sends() -> None:
    print("\n── ۶) «ارسال» یعنی ارسال، نه ذخیره ──")
    from aibl.report import dispatch as dp

    src = io.open(os.path.join(ROOT, "aibl/report/dispatch.py"),
                  encoding="utf-8").read()
    body = src[src.index("def send("):src.index("def eml(")]
    check("مسیر ارسال هیچ پیش‌نویسی نمی‌سازد", "mail.Save()" not in body,
          "Save() حذف شد")
    check("ارسال واقعی هنوز وجود دارد", "mail.Send()" in body)
    check("پیش‌نمایش هم هست", "mail.Display()" in body)

    good, bad = dp.parse_addresses("a@x.invalid; b@x.invalid, a@X.INVALID  زشت")
    check("نشانی دستی خوانده می‌شود", good == ["a@x.invalid", "b@x.invalid"],
          str(good))
    check("تکراری حذف می‌شود (بی‌توجه به بزرگی حروف)", len(good) == 2)
    check("ورودی نامعتبر جدا می‌شود و ارسال را نمی‌شکند", bad == ["زشت"], str(bad))
    check("ورودی خالی خطا نمی‌دهد", dp.parse_addresses("") == ([], []))

    studio = io.open(os.path.join(ROOT, "app/studio.py"), encoding="utf-8").read()
    check("تب ارسال ورود دستی نشانی دارد", "parse_addresses" in studio)
    check("ارسال دکمهٔ اصلی است", 'type="primary"' in studio
          and "🚀 ارسال به" in studio)
    check("ارسال دیگر پشت دکمهٔ «ساخت پیش‌نمایش» قفل نیست",
          'st.button("🛠 ساخت پیش‌نمایش"' not in studio)


if __name__ == "__main__":
    print("=" * 78)
    print("AIBL — بسته‌بندی، کف خوانایی و ارسال")
    print("=" * 78)
    test_theme_config()
    test_package_contents()
    test_legibility_floor()
    test_measured_contrast()
    test_charts_never_inherit_theme()
    test_send_actually_sends()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
