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


def _hue(h):
    """فام، برای اثباتِ اینکه رنگ سازمانی عوض نشده — فقط اشباعش."""
    import colorsys
    r, g, b = (v / 255 for v in _rgb(h))
    return colorsys.rgb_to_hls(r, g, b)[0] * 360

def contrast(fg, bg):
    a, b = _lum(_rgb(fg)), _lum(_rgb(bg))
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _over(fg, alpha, bg):  # noqa: D401
    f, b = _rgb(fg), _rgb(bg)
    return "#%02X%02X%02X" % tuple(
        round(f[i] * alpha + b[i] * (1 - alpha)) for i in range(3))



def _newest_zip(names):
    """تازه‌ترین بسته را **عددی** انتخاب کن، نه الفبایی.

    مرتب‌سازی متنی ``V3_9_0`` را بعد از ``V3_10_0`` می‌گذارد، و آن‌وقت
    بازرسی بی‌صدا روی بستهٔ کهنه اجرا می‌شود و «سبز» می‌دهد در حالی که
    بستهٔ واقعی ناقص است. دقیقاً همان جنسِ خطایی که این تست برای
    گرفتنش نوشته شده بود.
    """
    def key(n):
        return tuple(int(x) for x in re.findall(r"\d+", n))
    return max(names, key=key) if names else None

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
    newest = _newest_zip(zips)
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
    # برچسب دیگر هاردکد نیست — روی مک «ارسال» دروغ می‌شد. آنچه باید
    # قفل بماند این است که دکمه **اصلی** است و متنش از بستر می‌آید.
    check("ارسال دکمهٔ اصلی است", 'type="primary"' in studio
          and "action_label()" in studio and "🚀 {act} به" in studio)
    check("ارسال دیگر پشت دکمهٔ «ساخت پیش‌نمایش» قفل نیست",
          'st.button("🛠 ساخت پیش‌نمایش"' not in studio)


def test_hr_recipients_resolve() -> None:
    print("\n── ۷) گیرندگان باید از سورس HR پیدا شوند ──")
    import pandas as pd
    from aibl.report import dispatch as dp

    src = io.open(os.path.join(ROOT, "aibl/stages/s30_org.py"), encoding="utf-8").read()
    check("مرحلهٔ سازمانی، جدول HR را منتشر می‌کند",
          'ctx.extras["hr"]' in src,
          "بدون این، تب ارسال هیچ گیرنده‌ای نمی‌بیند")

    # همان شکل واقعیِ خروجی adapter — نه یک شکل ساختگی
    hr = pd.DataFrame({
        "HR_FULL_NAME": ["علی رضایی", "مریم احمدی", "سارا کریمی"],
        "HR_FIRST_NAME": ["علی", "مریم", "سارا"],
        "HR_LAST_NAME": ["رضایی", "احمدی", "کریمی"],
        "HR_EMAIL": ["a@x.invalid", "m@x.invalid", None],
        "HR_OFFICE": ["اداره راهبری"] * 3,
        "HR_POST": ["کارشناس/کارمند"] * 3,
        "HR_STATUS": ["فعال", "فعال", "غیرفعال"],
        "KEY_EMP": ["10201069", "10201070", "10201071"]})

    d = dp.directory(hr)
    check("گیرنده از HR واقعی پیدا می‌شود", len(d) == 2, f"{len(d)} نفر")
    check("نام از HR_FULL_NAME خوانده می‌شود، نه «—»",
          all(p.name != "—" for p in d), str([p.name for p in d]))
    check("برچسب، اداره و پست را دارد",
          all("اداره راهبری" in p.label for p in d))
    check("برچسب هنوز نشانی ندارد", all("@" not in p.label for p in d))

    # هدر واقعی لزوماً «Email» نیست
    for header in ("ایمیل", "پست الکترونیک", "E-Mail", "Email Address"):
        alt = hr.rename(columns={"HR_EMAIL": header})
        check(f"ستون «{header}» شناخته می‌شود",
              dp.find_email_column(alt) == header)

    # و اگر هیچ نامی نخواند، از روی محتوا
    weird = hr.rename(columns={"HR_EMAIL": "ستون بی‌نام ۷"})
    check("ستون ناشناس از روی محتوا پیدا می‌شود",
          dp.find_email_column(weird) == "ستون بی‌نام ۷")
    check("و همان‌قدر گیرنده می‌دهد", len(dp.directory(weird)) == 2)
    check("سورس بدون هیچ نشانی، خطا نمی‌دهد",
          dp.directory(hr.drop(columns=["HR_EMAIL"])) == [])


def test_send_button_always_present() -> None:
    print("\n── ۸) دکمهٔ ارسال باید دیده شود ──")
    studio = io.open(os.path.join(ROOT, "app/studio.py"), encoding="utf-8").read()
    check("دکمهٔ ارسال به‌جای پنهان‌شدن، غیرفعال می‌شود",
          "disabled=not ready" in studio,
          "کنترل نامرئی یعنی «این قابلیت وجود ندارد»")
    check("دلیل غیرفعال‌بودن به کاربر گفته می‌شود",
          "گیرنده انتخاب نشده" in studio)
    check("تب ارسال جدول HR را از extras می‌گیرد",
          'extras.get("hr")' in studio)


def test_brand_identity() -> None:
    print("\n── ۹) هویت سازمانی روی سطح‌های دیده‌شده ──")
    from aibl.report import brand as b

    check("نام سازمان IKCO است", b.COMPANY == "IKCO")
    check("واحد، Global Sourcing با کد GS است",
          b.UNIT == "Global Sourcing" and b.UNIT_SHORT == "GS")
    check("معاونت، Governance and Integration با کد GI است",
          b.DIVISION == "Governance and Integration" and b.DIVISION_SHORT == "GI")
    check("تیم، Data Analytics and KPI است", b.TEAM == "Data Analytics and KPI")
    check("موضوع ایمیل با نام سازمان شروع می‌شود",
          b.subject("1405/06/19").startswith("IKCO GS"), b.subject("1405/06/19"))
    check("پیشوند نام فایل سازمانی است", b.FILE_PREFIX == "IKCO_GS")

    studio = io.open(os.path.join(ROOT, "app/studio.py"), encoding="utf-8").read()
    for gone in ('page_title="AIBL Studio"', '### ◈ AIBL Studio',
                 'value=f"AIBL — گزارش زنجیره تأمین'):
        check(f"برند قدیمی حذف شد: {gone[:34]}", gone not in studio)
    check("سربرگ از ماژول برند می‌خواند", "_BRAND.LOCKUP_FULL" in studio)

    # لایهٔ عمق: همان فام، انتهای تیره — نه رنگ تازه
    import colorsys

    def hue(x):
        x = x.lstrip("#")
        r, g, bl = (int(x[i:i + 2], 16) / 255 for i in (0, 2, 4))
        return colorsys.rgb_to_hls(r, g, bl)[0] * 360

    def light(x):
        x = x.lstrip("#")
        r, g, bl = (int(x[i:i + 2], 16) / 255 for i in (0, 2, 4))
        return colorsys.rgb_to_hls(r, g, bl)[1] * 100

    dh = abs(hue(b.DEEP) - hue(b.GREEN))
    check("زمینهٔ عمیق همان فام سبز سازمانی است (≤ ۱۰ درجه)", dh <= 10,
          f"{dh:.1f}°")
    check("سبز متن روی کاغذ هم‌فام استاندارد است (≤ ۵ درجه)",
          abs(hue(b.GREEN_INK) - hue(b.GREEN)) <= 5,
          f"{abs(hue(b.GREEN_INK) - hue(b.GREEN)):.1f}°")
    check("چیزی که عوض شد روشنایی بود، نه فام",
          light(b.DEEP) < light(b.GREEN) - 10,
          f"{light(b.DEEP):.1f}٪ در برابر {light(b.GREEN):.1f}٪")
    check("کاغذ گرم هم‌فام طلاست — به همین دلیل کنار هم می‌نشینند",
          abs(hue(b.PAPER) - hue(b.GOLD)) <= 3,
          f"{abs(hue(b.PAPER) - hue(b.GOLD)):.1f}°")
    check("متن بدنه روی کاغذ عاجی ≥ ۷:۱",
          contrast(b.INK_DEEP, b.PAPER) >= 7.0,
          f"{contrast(b.INK_DEEP, b.PAPER):.2f}:1")
    check("کم‌رنگ‌ترین متن مجاز روی کاغذ ≥ ۴٫۵:۱",
          contrast(b.INK_FAINT, b.PAPER) >= 4.5,
          f"{contrast(b.INK_FAINT, b.PAPER):.2f}:1")
    check("طلا وقتی متن است ≥ ۴٫۵:۱ (طلای روشن فقط برای خط مو)",
          contrast(b.GOLD_INK, b.PAPER) >= 4.5,
          f"{contrast(b.GOLD_INK, b.PAPER):.2f}:1")
    check("سفید روی زمینهٔ عمیق ≥ ۷:۱",
          contrast("#FFFFFF", b.DEEP) >= 7.0,
          f"{contrast('#FFFFFF', b.DEEP):.2f}:1")

    # پالت استاندارد سازمان، نه یک انتخاب تازه
    check("سبز سازمانی", b.GREEN == "#00784B")
    check("سرمه‌ای سازمانی", b.NAVY == "#0A3A69")
    check("کهربایی سازمانی", b.ORANGE == "#E88400")
    check("سفید روی سبز سازمانی ≥ ۴٫۵:۱",
          contrast("#FFFFFF", b.GREEN) >= 4.5,
          f"{contrast('#FFFFFF', b.GREEN):.2f}:1")
    check("سفید روی سرمه‌ای ≥ ۴٫۵:۱",
          contrast("#FFFFFF", b.NAVY) >= 4.5,
          f"{contrast('#FFFFFF', b.NAVY):.2f}:1")
    check("متن بدنه روی پس‌زمینهٔ سازمانی ≥ ۷:۱",
          contrast(b.INK, b.PAGE) >= 7.0, f"{contrast(b.INK, b.PAGE):.2f}:1")


def test_alborz_design_system() -> None:
    print("\n── ۱۰) نظام طراحی البرز ──")
    from aibl.report import alborz as A

    check("نام و نسخه اعلام شده", A.NAME_EN == "Alborz Design System" and A.VERSION,
          f"{A.NAME_EN} {A.VERSION}")
    check("زمینه گرادیان است، نه رنگ تخت", len(A.PAGE_STOPS) >= 3)
    # سربرگ گرادیان است، پس «یک رنگ» ندارد و باید روی **هر توقف**
    # سنجیده شود. نسخهٔ ۱٫۰ فقط ادعا می‌کرد طیفش آکواست و همین از
    # نظر پنهان ماند که انتهای روشنِ آن طیف (#00A693) سفید را ۳٫۰۵
    # و متن ثانویه را ۲٫۷۹ می‌داد — هر دو زیر کف.
    check("سربرگ گرادیان چندتوقفی است", len(A.HEADER_STOPS) >= 3,
          f"{len(A.HEADER_STOPS)} توقف")
    for _pos, stop in A.HEADER_STOPS:
        check(f"سفید روی توقف {stop} ≥ ۴٫۵:۱", contrast(A.ON_AQUA, stop) >= 4.5,
              f"{contrast(A.ON_AQUA, stop):.2f}:1")
        check(f"متن ثانویه روی توقف {stop} ≥ ۴٫۵:۱",
              contrast(A.ON_AQUA_2, stop) >= 4.5,
              f"{contrast(A.ON_AQUA_2, stop):.2f}:1")
    check("پاصفحه هم متن خوانا دارد",
          contrast(A.ON_FOOTER, A.FOOTER) >= 4.5,
          f"{contrast(A.ON_FOOTER, A.FOOTER):.2f}:1")

    # لایهٔ ۲۰۲۶: تقسیم کارِ پنج رنگِ فرستاده، اندازه‌گیری‌شده نه سلیقه‌ای.
    # TEAL/JADE فقط زیر متن سفید می‌نشینند و ICE/MIST/FOG فقط زیر متن تیره.
    for name, c in (("TEAL", A.TEAL), ("JADE", A.JADE)):
        check(f"سفید روی {name} ≥ ۴٫۵:۱", contrast(A.ON_TEAL, c) >= 4.5,
              f"{contrast(A.ON_TEAL, c):.2f}:1")
    for name, c in (("ICE", A.ICE), ("MIST", A.MIST), ("FOG", A.FOG)):
        check(f"مرکب روی {name} ≥ ۴٫۵:۱", contrast(A.INK, c) >= 4.5,
              f"{contrast(A.INK, c):.2f}:1")
    for name, c in (("TEAL_INK", A.TEAL_INK), ("JADE_INK", A.JADE_INK)):
        check(f"{name} روی نوار روشن ≥ ۴٫۵:۱", contrast(c, A.BAND) >= 4.5,
              f"{contrast(c, A.BAND):.2f}:1")
    check("فام لایهٔ ۲۰۲۶ همان خانوادهٔ سازمانی است",
          abs(_hue(A.TEAL) - _hue(A.AQUA_700)) < 12,
          f"{abs(_hue(A.TEAL) - _hue(A.AQUA_700)):.1f}°")
    check("عمق دو لایه دارد، نه حاشیهٔ خاکستری",
          A.shadow_css().count("rgba") == 2, A.shadow_css()[:46] + "…")
    check("ایران‌سنس اول زنجیرهٔ فونت است",
          A.FONT_STACK.strip().startswith("'IRANSans"))

    # کنتراست هر متن روی سطح خودش — اندازه‌گیری، نه ادعا
    pairs = [("متن بدنه روی کارت", A.INK, A.CARD, 7.0),
             ("متن ثانویه روی کارت", A.INK_2, A.CARD, 4.5),
             ("کم‌رنگ‌ترین متن روی کارت", A.INK_3, A.CARD, 4.5),
             ("کاهی وقتی متن است", A.STRAW_INK, A.CARD, 4.5),
             ("متن بدنه روی زمینه", A.INK, A.PAGE, 7.0),
             ("سفید روی آکوای تیره", "#FFFFFF", A.AQUA_900, 7.0),
             ("سفید روی آکوای روشن", "#FFFFFF", A.AQUA_500, 3.0),
             ("متن روشن روی پاورقی", A.ON_FOOTER, A.FOOTER, 4.5),
             ("کهربایی ناحیهٔ کور", A.AMBER_BLIND, A.BLIND_BG, 4.5)]
    worst = 99.0
    for name, fg, bg, need in pairs:
        cr = contrast(fg, bg)
        worst = min(worst, cr / need)
        check(f"{name} ≥ {need}:۱", cr >= need, f"{cr:.2f}:1")
    check("هیچ جفتی زیر حدش نیست", worst >= 1.0)

    # رنگ وضعیت رزرو است و متنش جدا محاسبه شده
    check("هفت وضعیت تعریف شده", len(A.STATUS) == 7, str(sorted(A.STATUS)))
    check("برای هر وضعیت، رنگ متن روی ته‌رنگ هست",
          set(A.STATUS_ON_TINT) == set(A.STATUS))
    for key, raw in A.STATUS.items():
        tint = _over(raw, 0.10, A.PAGE)
        cr = contrast(A.STATUS_ON_TINT[key], tint)
        check(f"برچسب «{key}» روی ته‌رنگ ≥ ۴٫۵:۱", cr >= 4.5, f"{cr:.2f}:1")

    # هر دو پکیج باید یک نظام داشته باشند
    here = io.open(os.path.join(ROOT, "aibl/report/alborz.py"), encoding="utf-8").read()
    twin = os.path.join(os.path.dirname(ROOT), "hr-performance/hrperf/report/alborz.py")
    if os.path.exists(twin):
        other = io.open(twin, encoding="utf-8").read()
        def vals(src):
            import re as _re
            return _re.findall(r'"#[0-9A-Fa-f]{6}"', src)
        check("پالت البرز در هر دو پکیج یکی است", vals(here) == vals(other),
              f"{len(vals(here))} مقدار")

    # پلتفرم واقعاً از آن می‌خواند
    css = io.open(os.path.join(ROOT, "app/styles.py"), encoding="utf-8").read()
    check("رابط از ماژول البرز می‌خواند", "alborz as _AL" in css)
    check("زمینهٔ رابط، گرادیان البرز است", "page_gradient_css()" in css)
    check("کارت‌های رابط، عمق البرز دارند", "shadow_css()" in css)


# ═════════════════ مک: بستر ارسال، مسیر داده و راه‌انداز ═════════════════
def test_cross_platform():
    """محیط کار به مک منتقل شد. سه چیز آنجا فرق می‌کند و هر سه اینجا قفل است.

    ۱. **ارسال.** «ارسال با یک کلیک» از COM اتلوکِ ویندوز می‌آمد. مک آن
       را ندارد. راهِ غلط این بود که دکمه همان «ارسال» بماند و بی‌صدا به
       «باز کردن» تنزل کند — دقیقاً همان شکایتی که یک بار روی ویندوز
       شنیدیم («ایمیل ذخیره می‌کند به‌جای فرستادن»).
    ۲. **مسیر داده.** مسیر UNC روی مک وجود ندارد؛ اشتراک زیر /Volumes
       سوار می‌شود و جداکننده «/» است نه «\\».
    ۳. **راه‌انداز.** بدون بیتِ اجرا، دوبار کلیک روی مک هیچ نمی‌کند.
    """
    print("\n── مک: بستر ارسال، مسیر داده و راه‌انداز " + "─" * 26)
    import tempfile
    from unittest import mock
    from aibl.report import dispatch as _dp
    from aibl.report.alborz import FONT_STACK as _AL_FONT

    # ── ۱) بستر از سیستم‌عامل خوانده می‌شود، نه از آرزو ──
    for plat, want, direct in [("win32", _dp.OUTLOOK_COM, True),
                               ("darwin", _dp.MAC_OPEN, False),
                               ("linux", _dp.EML_ONLY, False)]:
        with mock.patch.object(_dp._sys, "platform", plat):
            check(f"بستر روی {plat} = {want}", _dp.backend() == want,
                  _dp.backend())
            check(f"ارسال مستقیم روی {plat}: {'بله' if direct else 'نه'}",
                  _dp.can_send_directly() is direct)
            label = _dp.action_label()[0]
            check(f"برچسب دکمه روی {plat} صادق است",
                  ("ارسال" == label) is direct, label)

    # ── ۲) روی مک، send_now دروغ نمی‌گوید ──
    with mock.patch.object(_dp._sys, "platform", "darwin"):
        try:
            _dp.send("موضوع", "<p>متن</p>", ["a@example.com"], send_now=True)
            check("send_now روی مک صریحاً خطا می‌دهد", False, "خطایی نداد")
        except RuntimeError as ex:
            check("send_now روی مک صریحاً خطا می‌دهد", "مک" in str(ex))
            check("خطا راهِ جایگزین را می‌گوید", "باز کردن" in str(ex))

    # ── ۳) روی مک، «باز کردن» واقعاً پیام کامل را می‌سازد ──
    with tempfile.TemporaryDirectory() as tmp:
        env = {"AIBL_HOME": tmp}
        calls = []

        def fake_call(cmd, **kw):
            calls.append(cmd)
            return 0

        with mock.patch.object(_dp._sys, "platform", "darwin"), \
             mock.patch.dict(os.environ, env), \
             mock.patch.object(_dp._sp, "call", fake_call):
            res = _dp.send("موضوع", "<p>متن گزارش</p>",
                           ["yek@example.com", "do@example.com"],
                           ["cc@example.com"], send_now=False)

        check("پیام در کلاینت باز شد", res.displayed and not res.sent)
        check("شمارش گیرنده درست است", res.to_count == 2 and res.cc_count == 1,
              f"{res.to_count} + {res.cc_count}")
        check("فرمانِ باز کردن، open مکِ است",
              bool(calls) and calls[0][0] == "open", str(calls[:1]))

        spool = os.path.join(tmp, "outbox")
        emls = [f for f in os.listdir(spool)] if os.path.isdir(spool) else []
        check("پیام روی دیسک ساخته شد", len(emls) == 1, str(emls))
        if emls:
            path = os.path.join(spool, emls[0])
            check("نام پرونده هیچ نشانی‌ای ندارد", "@" not in emls[0], emls[0])
            check("پوشهٔ صندوق ۷۰۰ است",
                  (os.stat(spool).st_mode & 0o777) == 0o700,
                  oct(os.stat(spool).st_mode & 0o777))
            check("پروندهٔ پیام ۶۰۰ است",
                  (os.stat(path).st_mode & 0o777) == 0o600,
                  oct(os.stat(path).st_mode & 0o777))
            raw = io.open(path, encoding="utf-8", errors="replace").read()
            check("بدنهٔ HTML داخل پیام هست", "متن گزارش" in raw)
            check("گیرنده‌ها داخل پیام هستند", "yek@example.com" in raw)

        # ── ۴) خلاصه هرگز نشانی نشان نمی‌دهد ──
        check("خلاصه هیچ نشانی‌ای فاش نمی‌کند",
              "@" not in res.summary, res.summary)

    # ── ۵) پاکسازی صندوق: نشانی‌ها روی دیسک تلنبار نمی‌شوند ──
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "outbox")
        os.makedirs(d)
        old = os.path.join(d, "dispatch-19700101-000000-1.eml")
        io.open(old, "w").write("x")
        os.utime(old, (0, 0))
        keep = os.path.join(d, "dispatch-new.eml")
        io.open(keep, "w").write("x")
        _dp._prune_spool(__import__("pathlib").Path(d))
        check("پیام کهنه (>۷ روز) پاک شد", not os.path.exists(old))
        check("پیام تازه دست‌نخورده ماند", os.path.exists(keep))

    # ── ۶) رابط، برچسب را از بستر می‌گیرد نه هاردکد ──
    ui = io.open(os.path.join(ROOT, "app/studio.py"), encoding="utf-8").read()
    check("رابط برچسب دکمه را از بستر می‌گیرد", "action_label()" in ui)
    check("رابط send_now را از بستر می‌گیرد", "send_now=direct" in ui)
    check("رابط دیگر «ارسال» را هاردکد نمی‌کند",
          '🚀 ارسال به' not in ui)

    # ── ۷) راه‌انداز مک ──
    launcher = os.path.join(ROOT, "run_mac.command")
    check("راه‌انداز مک وجود دارد", os.path.exists(launcher))
    if os.path.exists(launcher):
        check("بیت اجرا دارد", bool(os.stat(launcher).st_mode & 0o111),
              oct(os.stat(launcher).st_mode & 0o777))
        txt = io.open(launcher, encoding="utf-8").read()
        check("shebang دارد", txt.startswith("#!/bin/bash"))
        check("نسخهٔ پایتون را می‌سنجد", "3, 11" in txt or "(3, 11)" in txt)
    mk = io.open(os.path.join(ROOT, "make_package.py"), encoding="utf-8").read()
    check("راه‌انداز مک بسته‌بندی می‌شود", '"run_mac.command"' in mk)
    check("بسته‌بندی بیت اجرا را بازرسی می‌کند", "EXECUTABLE" in mk)
    check("راهنمای مک بسته‌بندی می‌شود", '"INSTALL_MAC.md"' in mk)
    check("راهنمای مک وجود دارد",
          os.path.exists(os.path.join(ROOT, "INSTALL_MAC.md")))

    # ── ۸) فونت: زنجیره روی مک هم به فارسیِ خوانا می‌رسد ──
    check("زنجیرهٔ فونت، جانشین مک دارد", "SF Arabic" in _AL_FONT,
          _AL_FONT[:60])
    css = io.open(os.path.join(ROOT, "app/styles.py"), encoding="utf-8").read()
    check("نام PostScript مکِ ایران‌سنس هم پوشش دارد",
          "IRANSansX-Light" in css)

    # ── ۹) مسیر شبکه روی مک ──
    from aibl.config import settings as _st
    with mock.patch.object(_st, "_IS_WINDOWS", False), \
         mock.patch.object(_st, "_NET", "/Volumes/data-share/Global Sourcing"):
        got = _st._net("03-Data", "01-Foreign")
        check("مسیر مک با «/» ساخته می‌شود",
              got == "/Volumes/data-share/Global Sourcing/03-Data/01-Foreign", got)
    with mock.patch.object(_st, "_IS_WINDOWS", True), \
         mock.patch.object(_st, "_NET", r"\\ikco.com\data-share\Global Sourcing"):
        got = _st._net("03-Data")
        check("مسیر ویندوز همان UNC می‌ماند", got == r"\\ikco.com\data-share\Global Sourcing\03-Data", got)
    src = io.open(os.path.join(ROOT, "aibl/config/settings.py"),
                  encoding="utf-8").read()
    check("هیچ مسیر سورسی دیگر با «\\» چسبانده نمی‌شود",
          "rf\"{_NET}" not in src)
    check("ریشهٔ اشتراک با AIBL_NET قابل تغییر است", '"AIBL_NET"' in src)


# ═════════════════ روایت — قالب فیگما، به‌صورت کد ═════════════════
def test_narrative():
    """خروجی باید **داستان** بگوید، و داستان باید از داده بیاید.

    قالب نهایی در فیگما ساخته شد و این تست همان قالب را روی خروجی‌ها
    قفل می‌کند. سه چیز سنجیده می‌شود:

    ۱. **دستور زبان** هشت عنصر دارد و ترتیبش عوض نمی‌شود.
    ۲. **متن از عدد می‌آید.** دو گزارش با دو داده، دو بندِ آغاز دارند.
       بندی که با هر داده‌ای یک چیز بگوید، روایت نیست؛ شعار است — و
       همان ایرادی است که یک بار به پوستر گرفته شد.
    ۳. **رنگ از البرز می‌آید.** هیچ رنگی در ماژول روایت تعریف نمی‌شود.
    """
    print("\n── روایت " + "─" * 58)
    from aibl.report import narrative as N
    from aibl.report import alborz as _AL

    # ── ۱) دستور زبان ──
    check("هشت عنصر دستور زبان تعریف شده", len(N.GRAMMAR) == 8, str(len(N.GRAMMAR)))
    check("ترتیب روایت قفل است",
          N.GRAMMAR == ("eyebrow", "opening", "chapter", "knot", "bridge",
                        "resolution", "coda", "badge"))
    for fn in ("hero", "eyebrow", "chapter", "knots", "resolution_block",
               "coda", "badge", "footer", "journey", "facets", "css",
               "email_open", "email_resolution", "email_coda", "excel_cover"):
        check(f"«{fn}» در ماژول روایت هست", hasattr(N, fn))

    # ── ۲) متن از عدد می‌آید، نه از قالبِ ثابت ──
    a = N.Facts(total=300, subject="پرونده", critical=76, blind=81, median=46)
    b = N.Facts(total=1200, subject="پرونده", critical=4, blind=0, median=9)
    oa, ob = N.plain_opening(a), N.plain_opening(b)
    check("بندِ آغاز با دادهٔ متفاوت، متفاوت است", oa != ob)
    check("عددِ واقعی داخل بند می‌آید", "۳۰۰" in oa and "۱٬۲۰۰" in ob)
    check("درصد بحرانی محاسبه می‌شود", "۲۵٪" in oa, oa[:70])
    check("نبودِ نقطهٔ کور، ادعای دروغ نمی‌سازد", "نقطهٔ کور" not in ob)
    empty = N.plain_opening(N.Facts())
    check("گزارش خالی، صادقانه خالی اعلام می‌شود", "خالی است" in empty, empty[:46])
    check("گزارش خالی عددِ جعلی نمی‌سازد", "۰" not in empty)
    _t, lines = N.resolution(a)
    check("جمع‌بندی هم از عدد می‌آید", any("۷۶" in x for x in lines))

    # ── ۳) رنگ فقط از البرز ──
    src = io.open(os.path.join(ROOT, "aibl/report/narrative.py"), encoding="utf-8").read()
    body = src[src.index("def css("):]
    hexes = set(re.findall(r"#[0-9A-Fa-f]{6}", body))
    check("هیچ رنگِ ثابتی در لایهٔ رندرِ روایت نیست", not hexes,
          str(sorted(hexes)[:4]))
    check("روایت از البرز می‌خواند", "alborz as _AL" in src)

    # ── ۴) بلوک‌های قالب واقعاً رندر می‌شوند ──
    html = N.css() + N.hero(a, kicker="K", title="T", subtitle="S") \
        + N.chapter("", "x", "lead") + N.knots(N.KNOTS) \
        + N.resolution_block(a) + N.journey(N.chapters()) \
        + N.facets(N.chapters(), numbered=True) + N.coda(N.CODA) \
        + N.footer(org="O", unit="U", tagline="T", ref_date="۱۴۰۵")
    for cls in ("nr-hero", "nr-pill", "nr-knot", "nr-gutter", "nr-link",
                "nr-res", "nr-journey", "nr-step", "nr-cards", "nr-c",
                "nr-cont", "nr-foot", "nr-badge"):
        check(f"بلوک «{cls}» رندر می‌شود", cls in html)
    check("عنوان سربرگ حک‌شده است (سایهٔ دولایه)", "text-shadow:2px 4px 3px" in html)
    check("مُهر پایان می‌آید", "END OF REPORT" in html)
    check("گره‌ها شماره‌دارند", ">۱<" in html and ">۲<" in html)
    check("پلِ بین گره‌ها هست", N.KNOTS[0].bridge in html)

    # ── ۵) نسخهٔ ایمیل باید روی موتور Word هم بنشیند ──
    mail = N.email_open(a, "lead") + N.email_resolution(a) + N.email_coda("c")
    check("ایمیل با جدول ساخته می‌شود، نه flex/grid",
          "display:flex" not in mail and "display:grid" not in mail)
    check("ایمیل bgcolor دارد (اگر CSS نادیده گرفته شد، زمینه می‌ماند)",
          "bgcolor=" in mail)
    check("ایمیل به کلاس CSS بیرونی تکیه ندارد", 'class="nr-' not in mail)

    # ── ۶) خروجی‌ها واقعاً از روایت می‌خوانند ──
    for rel, label in (("aibl/studio_core/html_export.py", "گزارش تفصیلی"),
                      ("aibl/analytics/report.py", "گزارش تحلیلی"),
                      ("aibl/report/dispatch.py", "ایمیل"),
                      ("aibl/studio_core/excel_export.py", "اکسل"),
                      ("app/studio.py", "رابط")):
        txt = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
        check(f"{label} از روایت می‌خواند", "_NR." in txt, rel)
    # ── ۷) سربرگ: صحنهٔ ۹۰۰×۵۲۰ قالب، مو‌به‌مو ──
    #
    # این بخش یک بار با عددهای «حدسی» نوشته شده بود و همان بود که
    # سربرگ را شبیه قالب نمی‌کرد. حالا هر عدد از خودِ پروندهٔ صادرشدهٔ
    # فیگما خوانده شده و اینجا قفل است. اگر کسی یکی‌شان را گرد کند،
    # این تست می‌افتد.
    hero = N.hero(a, kicker="K", title="T", subtitle="S", art="<i></i>")
    css = N.css()
    for probe, why in (
            ("--u:calc(1cqw/9)", "واحدِ صحنه: عرض تقسیم بر ۹۰۰"),
            ("min-height:calc(520*var(--u))", "ارتفاع صحنه"),
            ("calc(222*var(--u)) calc(44*var(--u)) calc(36*var(--u))",
             "حاشیهٔ ستونِ متن"),
            ("left:calc(38*var(--u));top:calc(32*var(--u))", "جای نشان"),
            ("width:calc(130*var(--u));height:calc(120*var(--u))", "اندازهٔ نشان"),
            ("left:calc(430*var(--u));top:calc(300*var(--u))", "جای خودرو"),
            ("width:calc(430*var(--u));height:calc(189*var(--u))", "قاب خودرو"),
            ("top:calc(108*var(--u))", "جای خط‌های حرکت"),
            ("top:calc(170*var(--u))", "جای سرسطرِ سازمان"),
            ("right:calc(210*var(--u));width:calc(722*var(--u))",
             "لبهٔ راستِ سرسطر روی ۶۹۰"),
            ("top:calc(188*var(--u))", "جای نوار تمرکز"),
            ("width:calc(770*var(--u));height:calc(3*var(--u))", "نوار تمرکز"),
            ("margin:0 calc(101*var(--u)) 0 calc(-59*var(--u))",
             "جعبهٔ عنوان از -۱۵ تا ۷۵۵"),
            ("font-size:calc(40*var(--u))", "اندازهٔ عنوان"),
            ("line-height:1.08", "ارتفاع سطرِ عنوان"),
            ("top:calc(112*var(--u))", "خطِ بالا"),
            ("width:calc(812*var(--u))", "عرضِ خطِ بالا"),
            ("top:calc(332*var(--u))", "خطِ زیرِ عنوان"),
            ("width:calc(380*var(--u))", "عرضِ خطِ زیرِ عنوان"),
            ("border-left:calc(1.5*var(--u)) solid", "خطِ قاب زیرعنوان"),
            ("font-size:calc(17*var(--u))", "اندازهٔ زیرعنوان"),
            ("flex:0 0 calc(36*var(--u))", "خطِ کنارِ بندِ آغاز"),
            ("width:calc(360*var(--u))", "عرضِ بندِ آغاز"),
            ("letter-spacing:calc(2*var(--u))", "فاصلهٔ حروفِ سرسطر")):
        check(f"{why} با قالب می‌خواند", probe in css, probe)

    check("طیف سربرگ چهار توقفِ قالب را دارد", len(_AL.HEADER_STOPS) == 4)
    check("زاویهٔ طیف گرد نشده", _AL.HEADER_ANGLE == "130.872deg")
    check("طیف قالب در CSS می‌آید", _AL.HEADER_DEEP.lower() in css.lower())

    # غبارِ داده — ۱۱۳ نقطه در ۸ ردیف، به‌علاوهٔ ۳ نقطهٔ KPI.
    check("غبار داده ۱۱۳ نقطهٔ قالب را دارد", len(N._DUST) == 113,
          str(len(N._DUST)))
    check("سه نقطهٔ KPI هست", len(N._KPI_DOTS) == 3)
    check("هر ۱۱۶ دایره رندر می‌شود", hero.count("<circle") == 116,
          str(hero.count("<circle")))
    check("نقطهٔ شاخصِ KPI کهربایی است", _AL.GOLD in hero)

    # بافت: همان feTurbulence قالب، نه یک نویزِ دلخواه.
    grain = N._grain_uri()
    import base64 as _b64
    raw = _b64.b64decode(grain.split(",", 1)[1]).decode("utf-8")
    check("بافت با پارامترهای قالب ساخته می‌شود",
          'baseFrequency="0.65 0.25"' in raw and 'numOctaves="4"' in raw
          and 'seed="5"' in raw, raw[:90])
    check("بافتِ نوار درون‌خطی است، نه فایل بیرونی",
          grain.startswith("data:image/svg+xml;base64,"))
    check("سربرگ گزارش‌ها هم همان بافت را می‌گیرد", "header::after" in css)
    check("عنوانِ گزارش هم حک می‌شود", "header h1" in css)
    check("خطِ بندِ آغاز **پیش از** متن می‌آید (در قالب فیزیکاً چپ است)",
          hero.index('class="rule"') < hero.index("<p>"))
    check("در عرض کم، صحنه می‌ایستد و ستونی می‌شود",
          "@container (max-width:620px)" in css)
    check("کوئریِ کانتینر روی لفافِ بیرونی است، نه خودِ نوار",
          "container-type:inline-size" in css
          and ".nr-hero-wrap{container-type" in css.replace("\n", ""))

    # نشان و خودروِ **واقعیِ** قالب در بسته‌اند — نه بازسازیِ حدسی.
    from aibl.report import assets as _AS
    check("نشانِ حک‌شدهٔ قالب در بسته هست", _AS.has("emblem"))
    check("تصویر پیکانِ قالب در بسته هست", _AS.has("paykan"))
    check("هیچ جایگاهی خالی نمانده", not _AS.missing(), str(_AS.missing()))
    check("نشان در سربرگ می‌نشیند", 'class="nr-emblem"' in hero)
    check("خودرو در سربرگ می‌نشیند", 'class="nr-car"' in hero)
    check("جایگاهِ نبوده جعل نمی‌شود", _AS.img("__not_a_slot__") == "")



def test_chart_series():
    """سریِ نمودار — **اندازه‌گیری‌شده**، نه انتخابِ سلیقه‌ای.

    اینجا همان ریاضیِ ``validate_palette.js`` بازنویسی شده تا ادعای
    البرز در خودِ مخزن قابل بررسی باشد و به یک ابزار بیرونی گره نخورد:
    OKLab، شبیه‌سازی کوررنگی، و ΔE روی **همهٔ** جفت‌ها — نه فقط مجاورها.

    سریِ قبلی هشت‌تایی بود و همین آزمون را نمی‌گذراند: دو آبیِ
    ``#2F74D0`` و ``#1478A0`` در دید عادی ΔE ۸٫۱ فاصله داشتند.
    """
    print("\\n── سریِ نمودار " + "─" * 54)
    import math
    from aibl.report import alborz as _AL

    def _lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def _rgb(h):
        h = h.lstrip("#")
        return [_lin(int(h[i:i + 2], 16)) for i in (0, 2, 4)]

    def _oklab(rgb):
        r, g, b = rgb
        l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
        m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
        s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
        return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)

    #: ماتریس‌های Brettel/Viénot — همان‌هایی که ابزار سنجش به کار می‌برد
    _CVD = {
        "protan": ((0.152286, 1.052583, -0.204868),
                   (0.114503, 0.786281, 0.099216),
                   (-0.003882, -0.048116, 1.051998)),
        "deutan": ((0.367322, 0.860646, -0.227968),
                   (0.280085, 0.672501, 0.047413),
                   (-0.011820, 0.042940, 0.968881)),
    }

    def _sim(rgb, kind):
        m = _CVD[kind]
        return [max(0.0, min(1.0, sum(m[i][j] * rgb[j] for j in range(3))))
                for i in range(3)]

    def _dE(a, b, kind=None):
        ra, rb = _rgb(a), _rgb(b)
        if kind:
            ra, rb = _sim(ra, kind), _sim(rb, kind)
        pa, pb = _oklab(ra), _oklab(rb)
        return 100 * math.dist(pa, pb)

    S = list(_AL.SERIES)
    check("سریِ نمودار هفت اسلات دارد", len(S) == 7, str(len(S)))
    check("اسلات اول تیلِ برند است", S[0] == "#008E82", S[0])

    worst_n = min((_dE(a, b), a, b) for i, a in enumerate(S) for b in S[i + 1:])
    check("کفِ دیدِ عادی روی همهٔ جفت‌ها ≥ ۱۵",
          worst_n[0] >= 15.0, f"{worst_n[0]:.1f}  {worst_n[1]}↔{worst_n[2]}")

    for kind in ("protan", "deutan"):
        w = min((_dE(a, b, kind), a, b)
                for i, a in enumerate(S) for b in S[i + 1:])
        check(f"کفِ کوررنگی ({kind}) روی همهٔ جفت‌ها ≥ ۶",
              w[0] >= 6.0, f"{w[0]:.1f}  {w[1]}↔{w[2]}")

    def _lum(h):
        r, g, b = _rgb(h)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def _cr(a, b):
        x, y = _lum(a), _lum(b)
        hi, lo = max(x, y), min(x, y)
        return (hi + 0.05) / (lo + 0.05)

    # کنتراست: معامله‌ای که آگاهانه پذیرفته شد. سه رنگ روی زمینه زیر
    # ۳:۱ می‌افتند و تیره‌کردنشان تفکیک را می‌شکند (اندازه‌گیری‌شده).
    # پس اینجا **تعهدِ جبران** را می‌سنجیم، نه عددِ کنتراست را.
    low = [c for c in S if _cr(c, _AL.PAGE) < 3.0]
    check("رنگ‌های کم‌کنتراست همان سه‌تای مستندند، نه بیشتر",
          len(low) <= 3, f"{len(low)}: {low}")
    check("هیچ رنگی زیر ۲٫۵:۱ نیست (کفِ مطلق)",
          min(_cr(c, _AL.PAGE) for c in S) >= 2.5,
          f"{min(_cr(c, _AL.PAGE) for c in S):.2f}")
    #: تعهد: راهنما + برچسب + جدول. رنگ تنها حاملِ معنا نیست.
    for rel, why in [("aibl/studio_core/html_export.py", "گزارش تفصیلی"),
                     ("app/studio.py", "رابط")]:
        txt = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
        check(f"{why} راهنمای رنگ دارد", ("legend" in txt or "راهنما" in txt), rel)
    check("معاملهٔ کنتراست در البرز مستند شده",
          "معاملهٔ کنتراست" in io.open(
              os.path.join(ROOT, "aibl/report/alborz.py"), encoding="utf-8").read())

    # چرخش ممنوع — سری هشتم رنگِ سری اول را نمی‌گیرد
    check("سریِ هشتم «سایر» می‌شود، نه تکرارِ اولی",
          _AL.series_color(7) == _AL.SERIES_OTHER
          and _AL.series_color(7) not in S)
    check("«سایر» روی کارت خوانا می‌ماند", _cr(_AL.SERIES_OTHER, _AL.CARD) >= 3.0,
          f"{_cr(_AL.SERIES_OTHER, _AL.CARD):.2f}")

    # رنگ وضعیت هرگز سریِ بعدی نمی‌شود
    clash = set(S) & set(_AL.STATUS.values())
    check("رنگ وضعیت با سری قاطی نمی‌شود", not clash, str(sorted(clash)))

    # هیچ مصرف‌کننده‌ای پالت خودش را نسازد
    import re as _re
    for rel in ["aibl/report/charts.py", "aibl/studio_core/html_export.py",
                "app/theme.py"]:
        txt = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
        cycles = _re.findall(r"%\s*len\((?:SERIES|CATEGORICAL|_pal|palette)", txt)
        check(f"«{rel}» پالت را نمی‌چرخاند", not cycles, str(cycles[:2]))


def test_monthly():
    """گزارش ماهانه — **تغییر** را می‌گوید، و هرگز دلتای ساختگی نمی‌سازد.

    سه قاعدهٔ صداقت اینجا قفل است:

    ۱. بدون ماهِ پیش، هیچ دلتایی ساخته نمی‌شود.
    ۲. درصد فقط روی مبنای معنادار می‌آید.
    ۳. جهتِ «خوب» را داده تعیین نمی‌کند؛ سنجه اعلامش می‌کند.
    """
    print("\n── گزارش ماهانه " + "─" * 52)
    from aibl.report import monthly as M
    from aibl.report import narrative as N

    # ۱) بدون مبنا، دلتا نداریم
    solo = M.Movement("سنجه", 12, None, "مورد")
    check("بدون ماهِ پیش، دلتا ساخته نمی‌شود", solo.delta is None)
    check("بدون ماهِ پیش، حکم «نامعلوم» است", solo.verdict == "unknown")
    check("جمله دربارهٔ نبودِ مبنا صادق است", "مقایسه" in M.sentence(solo),
          M.sentence(solo)[:60])
    check("تغییرِ بی‌مبنا خط تیره است", M.change(solo) == "—")

    # ۲) درصد فقط روی مبنای معنادار
    tiny = M.Movement("کوچک", 3, 1, "مورد")
    big = M.Movement("بزرگ", 37, 46, "پرونده")
    check("روی مبنای زیر کف، درصد نمی‌آید", tiny.pct is None,
          str(M.PCT_FLOOR))
    check("روی مبنای معنادار، درصد می‌آید", big.pct is not None)
    check("درصد درست حساب می‌شود", abs(big.pct + 19.565) < 0.01,
          f"{big.pct:.2f}")

    # ۳) جهتِ خوب را سنجه اعلام می‌کند
    down_ok = M.Movement("بحرانی", 37, 46, good="down")
    up_ok = M.Movement("تحویل", 37, 46, good="up")
    flat = M.Movement("حجم", 37, 46, good="flat")
    check("کاهش، وقتی کاهش خوب است، «بهتر» است", down_ok.verdict == "better")
    check("همان کاهش، وقتی افزایش خوب است، «بدتر» است", up_ok.verdict == "worse")
    check("سنجهٔ خنثی رنگِ قضاوت نمی‌گیرد", flat.verdict == "same")

    # ۴) نوشتنِ تغییر با واژه، نه با علامت
    check("«کمتر» نوشته می‌شود، نه «−»", "کمتر" in M.change(down_ok)
          and "-" not in M.change(down_ok), M.change(down_ok))
    check("نبودِ تغییر صریح گفته می‌شود",
          M.change(M.Movement("x", 7, 7)) == "بدون تغییر")

    # ۵) نمودار: زیر دو نقطه کشیده نمی‌شود
    check("روند با یک نقطه کشیده نمی‌شود", "<svg" not in M.spark([5]))
    check("روند با دو نقطه کشیده می‌شود", "<svg" in M.spark([5, 9]))
    sv = M.movement([down_ok, up_ok])
    check("هر ریل برچسبِ مستقیم دارد", sv.count("<text") >= 2, str(sv.count("<text")))
    check("هر ریل هاور دارد", sv.count("<title>") >= 2)
    check("نمودار بدون مبنا اصلاً نمی‌آید", M.movement([solo]) == "")

    # ۶) تعهدِ پالت: راهنما و جدول، کنارِ رنگ
    check("راهنمای رنگ می‌آید", "nr-legend" in M.legend())
    tbl = M.table([down_ok, solo])
    check("جدولِ همان اعداد هم می‌آید", "<table" in tbl and "بدون تغییر" not in tbl)
    check("سطرِ بی‌مبنا در جدول صادق است", "مبنای مقایسه ندارد" in tbl)

    # ۷) صفحهٔ کامل
    f = N.Facts(total=300, subject="پرونده", ref_date="۱۴۰۵/۰۶/۳۱",
                critical=37, blind=12, median=18)
    mo = M.Month(label="شهریور ۱۴۰۵", facts=f, previous="مرداد",
                 movements=[down_ok, up_ok, solo],
                 series=[("روند", [61, 58, 52, 49, 46, 37])])
    html = M.page(mo, title="روایتِ دادهٔ شهریور", org="O", unit="U",
                  tagline="T", kicker="K", subtitle="S")
    check("صفحه خودبسنده است (بدون درخواست شبکه)",
          'src="http' not in html and "url(http" not in html
          and "@import" not in html)
    check("سربرگ قالب را دارد", "nr-hero" in html and "nr-deco" in html)
    check("حرکت هست ولی محتوا به آن گره نخورده",
          "IntersectionObserver" in html and "nr-anim" in html)
    check("جدول و راهنما هر دو در صفحه‌اند",
          "nr-mo-tbl" in html and "nr-legend" in html)

    # ۸) اولین ماه: به‌جای دلتا، صادقانه اعلام می‌کند
    first = M.Month(label="مهر", facts=f, movements=[solo])
    h1 = M.build(first, title="T", org="O", unit="U", tagline="T", kicker="K")
    check("اولین ماه، «مبنای ماهِ بعد» را می‌گوید", "اولین ماهی" in h1)
    check("اولین ماه نمودار دمبلی ندارد", "nr-move" not in h1)

    # ۹) رنگ فقط از البرز
    src = io.open(os.path.join(ROOT, "aibl/report/monthly.py"),
                  encoding="utf-8").read()
    hexes = set(re.findall(r"#[0-9A-Fa-f]{6}", src))
    check("هیچ رنگِ ثابتی در گزارش ماهانه نیست", not hexes, str(sorted(hexes)[:3]))

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
    test_hr_recipients_resolve()
    test_send_button_always_present()
    test_brand_identity()
    test_alborz_design_system()
    test_cross_platform()
    test_narrative()
    test_chart_series()
    test_monthly()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
