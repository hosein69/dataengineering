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
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
