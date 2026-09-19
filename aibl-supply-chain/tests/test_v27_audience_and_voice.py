# -*- coding: utf-8 -*-
"""V27 — مخاطب، لحن، و صداقتِ عددی که به خواننده نشان داده می‌شود.

دو چیز اینجا قفل می‌شود که تا پیش از این هیچ تستی نمی‌سنجید:

**۱) گزارش برای چه کسی ساخته شده.** یک خروجی برای سه خواننده، یعنی هیچ‌کدام
آن را مال خودش نمی‌داند. کارشناس در انبوه نمودار گم می‌شود و مدیر ارشد در
انبوه ردیف؛ هیچ‌کدام فایل را باز نمی‌کند و سیستم — با وجود درست بودن —
بی‌اثر می‌ماند.

**۲) چه چیزی *نباید* دیده شود.** درصد صحت داده و امتیاز انطباق در نمای
مدیر، اعتماد را بی‌دلیل خرد می‌کنند: عددی که نمی‌شود دربارهٔ آن کاری کرد،
فقط تردید می‌سازد. جایشان داشبورد تحلیلی است.
"""
from __future__ import annotations

import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


def _sample() -> pd.DataFrame:
    return pd.DataFrame({
        "KEY_MATERIAL": ["M1", "M2", "M3"],
        "CANONICAL_ORDER": ["O1", "O2", "O3"],
        "بحرانی (کوتاه)": ["بحرانی", "ایمن", "تحت نظر"],
        "مقاومت (روز)": [4, 50, 22],
        "ORG_DEPT": ["A", "B", "A"],
    })


def _html(aud=None, **kw):
    from gsi.studio_core.html_export import build_dynamic_html
    df = _sample()
    return build_dynamic_html(df, "2026-08-31", selected_fields=list(df.columns),
                              audience=aud, **kw)


# ═══════════════════════════════════════════════════════════════════════════
def test_profiles() -> None:
    print("\n── ۱) پروفایل مخاطب ──")
    from gsi import audience as A

    check("چهار پروفایل تعریف شده است", len(A.PROFILES) == 4, str(list(A.PROFILES)))
    check("پیش‌فرض کارشناس است، چون پرتعدادترین خواننده است",
          A.DEFAULT == A.EXPERT)
    check("هر پروفایل پرسشی دارد که خواننده‌اش صبح می‌پرسد",
          all(p.question.endswith("؟") for p in A.PROFILES.values()))
    check("هر پروفایل می‌گوید برای چه کسی است",
          all(len(p.who) > 15 for p in A.PROFILES.values()))

    e, m, x = A.PROFILES[A.EXPERT], A.PROFILES[A.MANAGER], A.PROFILES[A.EXECUTIVE]
    check("هرچه بالاتر، ردیف کمتر و یافته کمتر",
          e.table_rows > m.table_rows > x.table_rows
          and e.max_findings > m.max_findings > x.max_findings,
          f"ردیف {e.table_rows}/{m.table_rows}/{x.table_rows} · "
          f"یافته {e.max_findings}/{m.max_findings}/{x.max_findings}")
    check("عمق روایت برای کارشناس بیشترین و برای مدیر ارشد کمترین است",
          e.narrative_depth > m.narrative_depth > x.narrative_depth)
    check("مدیر ارشد جدول بلند نمی‌گیرد", x.table_rows <= 10)

    # ── قاعده‌ای که کل این ماژول برای آن ساخته شد ──
    ops = (A.EXPERT, A.MANAGER, A.EXECUTIVE)
    check("هیچ پروفایل عملیاتی سنجه کیفیت داده نمی‌بیند",
          not any(A.PROFILES[k].show_data_quality for k in ops))
    check("فقط تحلیل‌گر کیفیت داده می‌بیند",
          A.PROFILES[A.ANALYST].show_data_quality)
    check("بخش quality فقط در پروفایل تحلیل‌گر است",
          [k for k in A.PROFILES if "quality" in A.PROFILES[k].sections] == [A.ANALYST])

    check("انتخاب با متغیر محیطی کار می‌کند",
          (os.environ.update({A.AUDIENCE_ENV: A.MANAGER}) or A.get().key) == A.MANAGER)
    os.environ.pop(A.AUDIENCE_ENV, None)
    check("نام ناشناخته به پیش‌فرض برمی‌گردد، نه خطا",
          A.get("مدیرعامل_مریخ").key == A.DEFAULT)


def test_voice() -> None:
    print("\n── ۲) لحن ──")
    from gsi import voice as V

    check("بزرگ‌نمایی خنثی می‌شود",
          "فاجعه" not in V.plain("این فاجعه است") and "وحشتناک" not in V.plain("وحشتناک"))
    check("ادعای علّی به همبستگی تبدیل می‌شود",
          "علت اصلی" not in V.plain("علت اصلی تأخیر، گمرک است"))
    check("واژگان اتهامی به «مانع» تبدیل می‌شود",
          "مقصر" not in V.plain("مقصر این تأخیر کیست")
          and "کوتاهی" not in V.plain("کوتاهی در پیگیری"))
    check("علامت تعجب پیاپی جمع می‌شود", V.plain("فوری!!!").count("!") == 1)

    check("عدد بدون مخرج منتشر نمی‌شود",
          V.quantify(147, 1204, "قلم") == "۱۴۷ قلم از ۱٬۲۰۴",
          V.quantify(147, 1204, "قلم"))
    check("سهم همیشه با صورت و مخرج می‌آید",
          "۱۴۷" in V.share(147, 1204) and "۱٬۲۰۴" in V.share(147, 1204))
    check("مخرج صفر، درصد نمی‌سازد", V.share(5, 0) == V.UNKNOWN)

    check("نمونه کوچک صریحاً کم اعلام می‌شود", "کم است" in V.evidence(2))
    check("نبود شاهد، سلامت گزارش نمی‌شود", V.evidence(0) == f"({V.NO_EVIDENCE})")
    check("چهار حالت ندانستن از هم جدا مانده‌اند",
          len(set(V.STATES)) == 4)

    check("اقدام بدون مالک، «تعیین نشده» می‌گوید نه حدس",
          "مالک: تعیین نشده" in V.action("پیگیری"))
    check("یافته بدون اقدام، خودش را لو می‌دهد",
          "اقدام: هنوز تعریف نشده" in V.bullet("مشاهده‌ای بدون اقدام"))
    check("تیتر وقتی چیزی نیست، صادق می‌ماند",
          "دیده نشد" in V.headline(0, 100, "ریسک فعال"))
    check("ارقام فارسی با جداکننده درست",
          V.fa_num(1204) == "۱٬۲۰۴" and V.fa_num(3.5) == "۳٫۵")


def test_html_respects_audience() -> None:
    print("\n── ۳) خروجی HTML، مخاطب‌محور ──")
    from gsi import audience as A

    pages = {k: _html(k) for k in (A.EXPERT, A.MANAGER, A.EXECUTIVE, A.ANALYST)}

    for k, h in pages.items():
        check(f"نمای «{A.PROFILES[k].fa}» ساخته می‌شود", len(h) > 20000)

    check("سه نمای عملیاتی در هر فایل هست تا خواننده جابه‌جا شود",
          all(h.count('class="chip persona"') >= 3
              for k, h in pages.items()))
    check("نمای تحلیل‌گر فقط در فایل تحلیل‌گر پیشنهاد می‌شود",
          pages[A.ANALYST].count('data-aud="analyst"') == 1
          and all('data-aud="analyst"' not in pages[k]
                  for k in (A.EXPERT, A.MANAGER, A.EXECUTIVE)))
    check("پرسش هر مخاطب در صفحه نوشته می‌شود",
          all(A.PROFILES[k].question in pages[k] for k in pages))

    check("بخش‌ها با data-section علامت خورده‌اند تا جابه‌جایی کار کند",
          all(h.count("data-section") >= 6 for h in pages.values()))
    check("اندازه صفحه از پروفایل می‌آید، نه عدد ثابت",
          all("audCfg().table_rows" in h for h in pages.values())
          and all("PAGE_SIZE=100" not in h for h in pages.values()))
    check("انتخاب مخاطب ماندگار می‌شود ولی فقط در مرورگر خود خواننده",
          "localStorage.setItem('gsi_aud'" in pages[A.EXPERT])


def test_html_hides_what_is_not_for_the_reader() -> None:
    print("\n── ۴) آنچه عمداً دیده نمی‌شود ──")
    from gsi import audience as A

    # سنجه‌هایی که مخاطبشان تحلیل‌گر است و در نمای عملیاتی فقط تردید می‌سازند
    QUALITY_WORDS = ("پوشش داده", "درصد صحت", "شکاف اسکیما", "سلامت سورس",
                     "کیفیت داده")
    for k in (A.EXPERT, A.MANAGER, A.EXECUTIVE):
        h = _html(k)
        hits = [w for w in QUALITY_WORDS if w in h]
        check(f"نمای «{A.PROFILES[k].fa}» سنجه کیفیت داده را نشان نمی‌دهد",
              not hits, "، ".join(hits) or "پاک")

    check("این اعداد در شیت سلامت سیستم جای خود را دارند",
          "rule_window_table" in open(
              os.path.join(ROOT, "gsi/report/system_health.py"),
              encoding="utf-8").read())


def test_no_overclaiming_in_output() -> None:
    print("\n── ۵) بدون ادعای بیش از داده ──")
    h = _html()
    visible = re.sub(r"/\*.*?\*/", "", h, flags=re.S)

    check("«هیچ ریسکی نیست» ادعا نمی‌شود؛ دامنه سنجش اعلام می‌شود",
          "در ابعادی که این گزارش می‌سنجد" in visible
          and "هیچ ریسک فعالی در این برش دیده نمی‌شود" not in visible)
    check("ریسک چندبعدی سنجیده می‌شود، نه فقط موجودی",
          "function riskFacets(" in h
          and all(x in h for x in ("مهلت ارزی", "اظهار انبار", "مجوز جابه‌جایی")))
    check("تنوع مسیر قطعی تفسیر نمی‌شود",
          "هر بار از نو اجرا می‌شود" not in visible
          and "خوب یا بد نیست" in visible)
    check("همبستگی، علت نامیده نمی‌شود",
          "همبستگی نشان می‌دهد، نه علت" in visible)
    check("دامنه جدول‌های فرآیند صریح است",
          "مستقل از فیلتر فعلی" in h)
    check("«انتظار» با «زمان کار» یکی گرفته نمی‌شود",
          "زمان سپری‌شده از آخرین رویداد است، نه زمان کار" in visible)


def main() -> int:
    print("=" * 78)
    print("V27 — مخاطب، لحن و صداقت خروجی")
    print("=" * 78)
    test_profiles()
    test_voice()
    test_html_respects_audience()
    test_html_hides_what_is_not_for_the_reader()
    test_no_overclaiming_in_output()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    for f in FAIL:
        print(f"   ❌ {f}")
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
