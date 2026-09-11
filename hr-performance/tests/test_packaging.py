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
        newest = _newest_zip(zips)
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

    # سربرگ گرادیان است، پس «یک رنگ» ندارد و باید روی **هر توقف** سنجیده
    # شود. نسخهٔ ۱٫۰ فقط ادعا می‌کرد طیفش آکواست؛ همین از نظر پنهان نگه
    # داشت که انتهای روشنِ آن طیف (#00A693) سفید را ۳٫۰۵ و متن ثانویه را
    # ۲٫۷۹ می‌داد — هر دو زیر کف. حالا خودِ توقف‌ها سنجیده می‌شوند.
    from hrperf.report import alborz as A
    check("سربرگ گرادیان چندتوقفی است", len(A.HEADER_STOPS) >= 3,
          f"{len(A.HEADER_STOPS)} توقف")
    for _pos, stop in A.HEADER_STOPS:
        check(f"سفید روی توقف {stop} ≥ ۴٫۵:۱", contrast(A.ON_AQUA, stop) >= 4.5,
              f"{contrast(A.ON_AQUA, stop):.2f}:1")
        check(f"متن ثانویه روی توقف {stop} ≥ ۴٫۵:۱",
              contrast(A.ON_AQUA_2, stop) >= 4.5,
              f"{contrast(A.ON_AQUA_2, stop):.2f}:1")

    # لایهٔ ۲۰۲۶: تقسیم کارِ پنج رنگ، اندازه‌گیری‌شده نه سلیقه‌ای.
    # TEAL/JADE فقط زیر متن سفید، و ICE/MIST/FOG فقط زیر متن تیره.
    for name, c in (("TEAL", A.TEAL), ("JADE", A.JADE)):
        check(f"سفید روی {name} ≥ ۴٫۵:۱", contrast(A.ON_TEAL, c) >= 4.5,
              f"{contrast(A.ON_TEAL, c):.2f}:1")
    for name, c in (("ICE", A.ICE), ("MIST", A.MIST), ("FOG", A.FOG)):
        check(f"مرکب روی {name} ≥ ۴٫۵:۱", contrast(A.INK, c) >= 4.5,
              f"{contrast(A.INK, c):.2f}:1")
    for name, c in (("TEAL_INK", A.TEAL_INK), ("JADE_INK", A.JADE_INK)):
        check(f"{name} روی نوار روشن ≥ ۴٫۵:۱", contrast(c, A.BAND) >= 4.5,
              f"{contrast(c, A.BAND):.2f}:1")


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
    # برچسب دیگر هاردکد نیست — روی مک «ارسال» دروغ می‌شد. آنچه باید
    # قفل بماند این است که دکمه **اصلی** است و متنش از بستر می‌آید.
    check("ارسال دکمهٔ اصلی است", 'type="primary"' in dash
          and "action_label()" in dash and "🚀 {act} به" in dash)
    check("ارسال دیگر به ستون ایمیلِ جدول پرسنلی گره نخورده",
          "if people_dir and to_sel:" not in dash)


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
    from hrperf.report import dispatch as _dp
    from hrperf.report.alborz import FONT_STACK as _AL_FONT

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
        env = {"HRP_HOME": tmp}
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
    ui = io.open(os.path.join(ROOT, "app/dashboard.py"), encoding="utf-8").read()
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
    from hrperf.report import narrative as N
    from hrperf.report import alborz as _AL

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
    src = io.open(os.path.join(ROOT, "hrperf/report/narrative.py"), encoding="utf-8").read()
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
    for rel, label in (("hrperf/report/html.py", "گزارش HTML"),
                      ("hrperf/report/dynamic.py", "داشبورد"),
                      ("hrperf/report/dispatch.py", "ایمیل"),
                      ("hrperf/report/excel.py", "اکسل"),
                      ("app/dashboard.py", "رابط")):
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
    from hrperf.report import assets as _AS
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
    from hrperf.report import alborz as _AL

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
    for rel, why in [("hrperf/report/html.py", "گزارش HTML"),
                     ("app/dashboard.py", "رابط")]:
        txt = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
        check(f"{why} راهنمای رنگ دارد", ("legend" in txt or "راهنما" in txt), rel)
    check("معاملهٔ کنتراست در البرز مستند شده",
          "معاملهٔ کنتراست" in io.open(
              os.path.join(ROOT, "hrperf/report/alborz.py"), encoding="utf-8").read())

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
    for rel in ["hrperf/report/fluid.py", "hrperf/report/theme.py",
                "app/dashboard.py"]:
        txt = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
        cycles = _re.findall(r"%\s*len\((?:SERIES|CATEGORICAL|_pal|palette)", txt)
        check(f"«{rel}» پالت را نمی‌چرخاند", not cycles, str(cycles[:2]))

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
    test_cross_platform()
    test_narrative()
    test_chart_series()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
