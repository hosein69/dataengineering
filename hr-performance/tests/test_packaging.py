# -*- coding: utf-8 -*-
"""تست بسته‌بندی و کف خوانایی رابط HRPerf.

هر بررسی اینجا از یک خرابی **واقعی در تولید** آمده.

بستهٔ AIBL نسخهٔ ۲۶٫۱۵٫۰ با دستوری ساخته شد که فایل‌های نقطه‌دار را
برنمی‌داشت؛ `.streamlit/config.toml` در بسته نبود. بدون آن، Streamlit تم
خودش را می‌گذارد و آن تم از `prefers-color-scheme` مرورگر پیروی می‌کند.
روی ویندوزِ حالت‌تاریک:

    متن `#FAFAFA` روی پس‌زمینهٔ `#E1F2E9`  →  نسبت کنتراست ۱٫۱۵:۱

نوار کناری و فیلترها نامرئی شدند. بسته‌های HRPerf با همان دستور ساخته
شده بودند و همان نقص را داشتند — و پیکربندی تمش هنوز پالت قدیمیِ
پیش‌آکوا را داشت.
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
    print("\n── ۱) پیکربندی تم ──")
    from hrperf.report.theme import STREAMLIT_THEME, config_toml, theme_env

    path = os.path.join(ROOT, ".streamlit", "config.toml")
    check("`.streamlit/config.toml` در مخزن هست", os.path.exists(path))
    text = io.open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    for key, val in STREAMLIT_THEME.items():
        check(f"config.toml مقدار {key} را دارد", f'{key} = "{val}"' in text, val)
    check("تم روشن است، نه پیروِ مرورگر", STREAMLIT_THEME["base"] == "light")
    check("پیکربندی با پالت آکوا می‌خواند، نه پالت قدیمی",
          "#1c5cab" not in text and "#fcfcfb" not in text)
    check("config_toml() همان چیزی است که روی دیسک است",
          config_toml().strip() == text.strip())
    check("راه‌انداز شش کلید تم را متغیر محیطی می‌کند", len(theme_env()) == 6)
    src = io.open(os.path.join(ROOT, "app/run_dashboard.py"), encoding="utf-8").read()
    check("راه‌انداز تم را به زیرفرآیند می‌دهد", "theme_env()" in src)


def test_package_contents() -> None:
    print("\n── ۲) بسته باید همان چیزی باشد که اجرا می‌شود ──")
    import make_package as mp

    names = {p.relative_to(mp.ROOT).as_posix() for p in mp.members()}
    check("جمع‌آورنده فایل نقطه‌دار را هم برمی‌دارد",
          ".streamlit/config.toml" in names, f"{len(names)} پرونده")
    check("پیکربندی تم جزء فهرست الزامی است",
          ".streamlit/config.toml" in mp.REQUIRED)
    check("فایل‌های موقت داخل بسته نمی‌روند",
          not any(n.endswith((".pyc", ".zip", ".log")) or "__pycache__" in n
                  for n in names))
    zips = [f for f in os.listdir(ROOT) if re.match(r"HRPerf_V\d+_\d+_\d+\.zip$", f)]
    if zips:
        newest = sorted(zips)[-1]
        inside = set(zipfile.ZipFile(os.path.join(ROOT, newest)).namelist())
        for req in mp.REQUIRED:
            check(f"{newest} شامل {req} است", req in inside)


def test_legibility_floor() -> None:
    print("\n── ۳) کف خوانایی در CSS ──")
    from app.styles import css
    sheet = css()
    check("حالت رنگی صریح روشن است", "color-scheme:light" in sheet)
    check("نوار کناری پس‌زمینهٔ صریح دارد",
          '[data-testid="stSidebarContent"]' in sheet)
    check("پوستهٔ ورودی‌ها رنگ صریح می‌گیرد",
          '[data-testid="stMultiSelect"] > div > div' in sheet)
    check("تراشهٔ انتخاب رنگ برند می‌گیرد نه قرمز پیش‌فرض",
          '[data-testid="stMultiSelectTagsContainer"] > span > span' in sheet)
    check("فونت به پرتال‌ها هم می‌رسد", "html,body,body *" in sheet)
    check("نام‌های نصبِ ایران‌سنس گره خورده‌اند",
          "@font-face" in sheet and "IRANSansWeb" in sheet)


def test_font_and_contrast() -> None:
    print("\n── ۴) فونت و کنتراست، اندازه‌گیری‌شده ──")
    from hrperf.report import aqua
    from hrperf.report.theme import (BANDS, RAISED, SURFACE, TEXT, TEXT2,
                                     band_text_color)

    check("ایران‌سنس اول زنجیرهٔ فونت است",
          aqua.FONT_STACK.strip().startswith("'IRANSans"), aqua.FONT_STACK[:34])
    check("فونت اکسل هنوز فونت سازمانی است", aqua.FONT_XLSX == "IRANSans Light")

    check("متن بدنه روی پس‌زمینه ≥ ۷:۱", contrast(TEXT, SURFACE) >= 7.0,
          f"{contrast(TEXT, SURFACE):.2f}:1")
    check("متن ثانویه روی کارت ≥ ۴٫۵:۱", contrast(TEXT2, RAISED) >= 4.5,
          f"{contrast(TEXT2, RAISED):.2f}:1")
    check("سفید روی دکمهٔ برند ≥ ۴٫۵:۱",
          contrast("#FFFFFF", aqua.LIGHT["brand-strong"]) >= 4.5,
          f"{contrast('#FFFFFF', aqua.LIGHT['brand-strong']):.2f}:1")

    for floor, color, _icon, label in BANDS:
        ink = band_text_color(floor)
        cr = contrast(ink, _over(color, 0.10, SURFACE))
        check(f"برچسب «{label}» روی تراشه ≥ ۴٫۵:۱", cr >= 4.5, f"{cr:.2f}:1")


def test_charts_never_inherit_theme() -> None:
    print("\n── ۵) نمودار نباید تم مرورگر را به ارث ببرد ──")
    src = io.open(os.path.join(ROOT, "app/dashboard.py"), encoding="utf-8").read()
    calls = re.findall(r"st\.plotly_chart\(([^\n]*)", src)
    check("همهٔ نمودارها از finalize() رد می‌شوند",
          all("finalize(" in c for c in calls), f"{len(calls)} فراخوانی")
    check("تم Streamlit روی نمودار خاموش است",
          all("theme=None" in c for c in calls))

    from hrperf.report.theme import RAISED, finalize
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("… plotly نصب نیست؛ بررسی زندهٔ شکل رد شد")
        return
    fig = finalize(go.Figure(go.Bar(x=[1], y=[2])))
    check("بومِ نمودار روی layout نشسته، نه روی قالب",
          fig.layout.paper_bgcolor == RAISED, str(fig.layout.paper_bgcolor))


def test_send_actually_sends() -> None:
    print("\n── ۶) «ارسال» یعنی ارسال، نه ذخیره ──")
    from hrperf.report import dispatch as dp

    src = io.open(os.path.join(ROOT, "hrperf/report/dispatch.py"),
                  encoding="utf-8").read()
    body = src[src.index("def send("):src.index("def eml(")]
    check("مسیر ارسال هیچ پیش‌نویسی نمی‌سازد", "mail.Save()" not in body)
    check("ارسال واقعی هنوز وجود دارد", "mail.Send()" in body)
    check("پیش‌نمایش هم هست", "mail.Display()" in body)

    good, bad = dp.parse_addresses("a@x.invalid; b@x.invalid, A@X.INVALID  زشت")
    check("نشانی دستی خوانده می‌شود", good == ["a@x.invalid", "b@x.invalid"],
          str(good))
    check("ورودی نامعتبر ارسال را نمی‌شکند", bad == ["زشت"], str(bad))
    check("ورودی خالی خطا نمی‌دهد", dp.parse_addresses("") == ([], []))

    dash = io.open(os.path.join(ROOT, "app/dashboard.py"), encoding="utf-8").read()
    check("تب ارسال ورود دستی نشانی دارد", "parse_addresses" in dash)
    check("ارسال دکمهٔ اصلی است", "🚀 ارسال به" in dash)
    check("ارسال دیگر به ستون ایمیلِ جدول پرسنلی گره نخورده",
          "if people_dir and to_sel:" not in dash)


if __name__ == "__main__":
    print("=" * 78)
    print("HRPerf — بسته‌بندی، کف خوانایی و ارسال")
    print("=" * 78)
    test_theme_config()
    test_package_contents()
    test_legibility_floor()
    test_font_and_contrast()
    test_charts_never_inherit_theme()
    test_send_actually_sends()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
