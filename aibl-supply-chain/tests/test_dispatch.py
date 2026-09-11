# -*- coding: utf-8 -*-
"""تست ارسال گزارش — پیوست، گیرنده، و بدنهٔ امن روی موتور Word اتلوک.

دو چیز اینجا قفل می‌شود:

۱. **محرمانگی گیرندگان.** برچسب انتخابگر نباید نشانی داشته باشد و
   خلاصهٔ ارسال نباید نشانی ببرد — فقط تعداد.
۲. **سازگاری با اتلوک کلاسیک.** بدنه نباید چیزی داشته باشد که موتور
   Word نمی‌فهمد؛ اگر روزی کسی `flex` یا `<script>` اضافه کند، همین
   تست جلویش را می‌گیرد.
"""
from __future__ import annotations

import os
import sys
import re
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from aibl.report import aqua  # noqa: E402
from aibl.report import dispatch as dp  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


def _hr():
    return pd.DataFrame({
        "HR_KEY_EMP": ["10201069", "10201070", "10201071", "10201072"],
        "HR_NAME": ["حسینی", "رضایی", "کریمی", "بدون‌نشانی"],
        "HR_OFFICE": ["اداره ترخیص", "اداره اعتبارات", "اداره ترخیص", "اداره ترخیص"],
        "HR_POST": ["کارشناس ترخیص", "رئیس اداره", "کارشناس ترخیص", "کارشناس"],
        "HR_STATUS": ["فعال", "فعال", "غیرفعال", "فعال"],
        "HR_EMAIL": ["a@x.invalid", "b@x.invalid", "c@x.invalid", "—"]})


def test_directory() -> None:
    print("\n── ۱) دفترچه گیرندگان ──")
    d = dp.directory(_hr())
    check("فقط پرسنل فعالِ دارای نشانی معتبر می‌آیند",
          {p.name for p in d} == {"حسینی", "رضایی"},
          str(sorted(p.name for p in d)))
    check("غیرفعال حذف می‌شود", all(p.name != "کریمی" for p in d))
    check("برچسب انتخابگر نشانی ندارد", all("@" not in p.label for p in d),
          str([p.label for p in d]))
    check("برچسب، اداره و پست را نشان می‌دهد",
          any("اداره ترخیص" in p.label and "کارشناس" in p.label for p in d))
    check("نشانی نقاب‌دار است", all("•" in p.masked for p in d),
          str([p.masked for p in d]))
    check("نشانی واقعی فقط با addresses() بیرون می‌آید",
          dp.addresses(d) == ["a@x.invalid", "b@x.invalid"], str(dp.addresses(d)))
    check("سورس بدون ستون ایمیل، فهرست خالی می‌دهد",
          dp.directory(_hr().drop(columns=["HR_EMAIL"])) == [])
    check("سورس خالی، خطا نمی‌دهد", dp.directory(pd.DataFrame()) == [])


def test_body_is_outlook_safe() -> None:
    print("\n── ۲) بدنهٔ امن روی موتور Word ──")
    body = dp.outlook_body(
        "AIBL — گزارش زنجیره تأمین", "1405/06/09",
        kpis=[("پرونده", "۱٬۲۴۰", aqua.INK),
              ("بحرانی", "۳۸", aqua.STATUS_LIGHT["critical"])],
        headers=["شماره فنی", "بارنامه", "کجاست", "توپ در زمین"],
        rows=[["P-1188", "BL-9021", "گمرک", "کارشناس حمل و لجستیک"],
              ["P-2043", "BL-7710", "تخصیص ارز", "کارشناس بازرگانی"]],
        note="یک متریال بحرانی، کل پرونده را بحرانی می‌کند.",
        attachments=["AIBL_Dashboard.xlsx"], live_url="https://x.invalid/r")

    low = body.lower()
    for token in ("<script", "flex", "display:grid", "<svg", "position:absolute"):
        check(f"بدنه بدون «{token}» است — موتور Word نمی‌فهمدش", token not in low)

    # ``background-image`` ممنوع نیست؛ **تکیه** بر آن ممنوع است. موتور
    # Word آن را نمی‌کشد، پس هر جا بیاید باید همان عنصر ``bgcolor`` هم
    # داشته باشد و VML هم برایش گذاشته شده باشد. قاعدهٔ قبلی («اصلاً
    # نیاید») طیفِ سربرگ را هم ممنوع می‌کرد، در حالی که با سه لایهٔ
    # نشست، سربرگ روی هر کلاینتی درست دیده می‌شود.
    for m in re.finditer(r"<t[dh][^>]*background-image[^>]*>", low):
        check("هر background-image یک bgcolor پشتوانه دارد",
              "bgcolor=" in m.group(0), m.group(0)[:70])
    if "background-image" in low:
        check("طیف سربرگ برای اتلوک نسخهٔ VML دارد", "v:fill" in low and "gradient" in low)
    check("چیدمان جدول‌محور است", body.count("<table") >= 5, str(body.count("<table")))
    check("CSS درون‌خطی است، نه کلاس", 'style="' in body)
    check("VML هست تا دکمه روی اتلوک کلاسیک گرد بماند", "v:roundrect" in body)
    check("mso برای ارتفاع خط تنظیم شده", "mso-line-height-rule" in body)
    check("ارتقای تدریجی فقط داخل @media است",
          "@media" in body and "prefers-color-scheme" in body)
    check("راست‌به‌چپ و فارسی است", 'dir="rtl"' in body and 'lang="fa"' in body)
    # ایمیل تا دیروز پالت نسل قبل را داشت و گیرنده یک جنس می‌دید و در
    # گزارش جنسی دیگر. حالا همان توکن‌های البرز را می‌پوشد.
    from aibl.report import mail as _mail
    check("پالت ایمیل از البرز می‌آید",
          _mail.PALETTE["header"] in body and _mail.PALETTE["surface"] in body)
    check("پالت نسل قبل دیگر نیست",
          "#005349" not in body and "#E1F2E9" not in body)
    check("سرسطرِ سازمان در سربرگ ایمیل هست", "IKCO" in body)
    check("توضیح صادقانه دربارهٔ نبودِ داینامیک هست", "جاوااسکریپت" in body)
    check("پیوست‌ها در بدنه نام برده می‌شوند", "AIBL_Dashboard.xlsx" in body)

    chip = dp._chip("بحرانی", aqua.STATUS_LIGHT["critical"], "⬤")
    check("تراشهٔ وضعیت آیکن و برچسب دارد، نه فقط رنگ",
          "⬤" in chip and "بحرانی" in chip)


def test_send_guards() -> None:
    print("\n── ۳) محافظ‌های ارسال ──")
    r = dp.Dispatch(to_count=4, cc_count=2, attachments=["a.xlsx", "b.html"])
    check("خلاصه فقط تعداد می‌گوید", "4 گیرنده" in r.summary and "@" not in r.summary,
          r.summary)
    check("خلاصه تعداد پیوست را هم می‌گوید", "2 پیوست" in r.summary)
    try:
        dp.send("x", "<html></html>", [])
        check("ارسال بدون گیرنده رد می‌شود", False, "اجازه داد!")
    except Exception as ex:
        check("ارسال بدون گیرنده رد می‌شود", "گیرنده" in str(ex),
              str(ex)[:44] + "…")

    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "AIBL_Dashboard.xlsx"
        f.write_bytes(b"x")
        raw = dp.eml("موضوع", "<html><body>x</body></html>",
                     ["a@x.invalid"], ["b@x.invalid"], [f])
        check("پروندهٔ eml ساخته می‌شود", b"Subject" in raw)
        check("eml رونوشت دارد", b"Cc:" in raw)
        check("eml پیوست را می‌برد", b"AIBL_Dashboard.xlsx" in raw)
        missing = dp.eml("م", "<html></html>", ["a@x.invalid"],
                         attachments=[Path(td) / "nope.xlsx"])
        check("پیوست ناموجود، ارسال را نمی‌شکند", b"Subject" in missing)


def test_artifacts() -> None:
    print("\n── ۴) سیاههٔ پیوست‌ها ──")
    check("هر پیوست عنوان، پسوند و دلیل دارد",
          all(len(v) == 3 and all(v) for v in dp.ARTIFACTS.values()),
          str(list(dp.ARTIFACTS)))
    check("داشبورد اکسل در سیاهه هست", "dashboard" in dp.ARTIFACTS)
    check("گزارش تحلیلی در سیاهه هست", "analysis" in dp.ARTIFACTS)
    check("گزارش تعارض داده در سیاهه هست", "audit" in dp.ARTIFACTS)


if __name__ == "__main__":
    print("=" * 78)
    print("AIBL — تست ارسال گزارش")
    print("=" * 78)
    test_directory()
    test_body_is_outlook_safe()
    test_send_guards()
    test_artifacts()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
