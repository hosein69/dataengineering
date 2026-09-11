# -*- coding: utf-8 -*-
"""پوستر آموزشی «بکن و نکنِ داده» — قلاب آموزشی برای کارشناسان خرید.

## چرا این اسکریپت، نه یک فایل HTML دستی

رنگ از ``alborz`` می‌آید، خودرو از ``paykan``، و **چیدمان از
``narrative``** — همان لایه‌ای که گزارش‌ها هم از آن می‌خوانند.

این نکتهٔ اصلی است: پوستر و گزارش دو پیاده‌سازیِ جدا ندارند. اگر
داشتند، دو حقیقت می‌شد و یکی‌شان زودتر از دیگری کهنه می‌شد. قالبِ فیگما
یک بار به کد ترجمه شد و هر دو از همان می‌خوانند؛ پوستر فقط «نمونه‌ای با
عددهای ثابت» است.

## محتوا از کجا می‌آید

از خودِ کد، نه از شعار:

* شش ستونِ «مالکش شمایید» از ``resolve/expert_scope.py::OWNER_FIELDS``
* دو مرحلهٔ نادیدنی از ``UNOBSERVABLE_STAGES``
* سیزده فعالیت از ``stages/s80_eventlog.py::ACTIVITIES``

پس هر عددی که روی پوستر است، در سامانه قابل ردیابی است. پوستری که
عددش را از جایی جز کد بگیرد، آموزش نمی‌دهد؛ تبلیغ می‌کند.

    python poster/make_poster.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aibl.report import alborz as A            # noqa: E402
from aibl.report import narrative as N         # noqa: E402
from aibl.report import brand as B             # noqa: E402
from aibl.report import paykan                 # noqa: E402
from aibl.resolve.expert_scope import OWNER_FIELDS, UNOBSERVABLE_STAGES  # noqa: E402
from aibl.stages.s80_eventlog import ACTIVITIES  # noqa: E402

W = 900


def digits(n) -> str:
    """رقم فارسی. پوستر فارسی با عدد لاتین، نیمه‌کاره به‌نظر می‌رسد."""
    return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))




def html() -> str:
    """پوستر — همان لایهٔ روایتی که گزارش‌ها از آن می‌خوانند.

    عددهای اینجا ثابت‌اند چون پوستر چاپ می‌شود. در گزارش، همین عددها از
    دادهٔ همان اجرا می‌آیند و بند به بند عوض می‌شوند — بدون هیچ تغییری
    در چیدمان.
    """
    facts = N.Facts(total=300, subject="پرونده", ref_date="۱۴۰۵/۰۶/۱۹",
                    critical=76, blind=81, median=46)
    own = [N.Chapter(code, fa_, N.MEANINGS.get(code, ""), ())
           for code, fa_ in OWNER_FIELDS]
    car = ('<div style="text-align:center;margin-top:8px">'
           + paykan.svg(460, uid="hero", ground=False, crop=True, inline=True)
           + "</div>")
    blind = " · ".join(UNOBSERVABLE_STAGES)
    n_ev = digits(len(ACTIVITIES))

    style = (
        "*{box-sizing:border-box}"
        f"body{{margin:0;background:{A.PAGE};font-family:{A.FONT_STACK};"
        f"color:{A.INK}}}"
        f".sheet{{width:{W}px;margin:0 auto;background:{A.CARD};"
        f"overflow:hidden;box-shadow:{A.shadow_css()}}}"
        ".pad{padding:0 44px}"
        f".blind{{margin:14px auto 0;max-width:620px;background:{A.BLIND_BG};"
        f"border-right:3px solid {A.AMBER_BLIND};padding:10px 14px;"
        f"font-size:12.5px;color:{A.AMBER_BLIND};line-height:1.9;"
        "text-align:right}"
        + N.css())

    parts = [
        N.hero(facts, kicker=B.LOCKUP_FULL,
               title="خوب بد زشت داده در زنجیرهٔ تأمین",
               subtitle="داده‌ای که شما می‌نویسید، تصمیمی است که فردا انجام می‌شود",
               art=car),
        '<div class="pad">',
        N.chapter("", "هر پرونده سه گره دارد. در هر گره یک انتخاب است: راهِ "
                  "درست یا راهِ پرهزینه. این مسیر را دنبال کن.", N.LEAD_PATH),
        N.knots(N.KNOTS),
        N.resolution_block(facts),
        N.chapter("", "هیچ‌کدام از سورس‌ها این‌ها را نمی‌سازند. هر خانهٔ خالی، "
                  "یک نقطهٔ کور در پروندهٔ همان قطعه است.", N.LEAD_TURN),
        N.facets(own, numbered=True),
        N.chapter("", "از لحظهٔ صدور سفارش تا ثبت رسید مالی — هر گام، یک سند؛ "
                  "هر سند، یک قدم به جلو.",
                  f"{n_ev} رویدادی که پرونده را می‌سازند"),
        N.journey(N.chapters()),
        f'<div class="blind">دو مرحله را <b>هیچ سورسی نمی‌بیند</b> ({blind}) '
        "— این‌ها فقط از دستِ شما ثبت می‌شوند.</div>",
        N.coda(N.CODA),
        "</div>",
        N.footer(org=f"{B.COMPANY} · {B.UNIT} ({B.UNIT_SHORT})",
                 unit=f"{B.DIVISION} ({B.DIVISION_SHORT}) · {B.TEAM}",
                 tagline=A.TAGLINE, ref_date="۱۴۰۵",
                 art=paykan.mark(84, A.ON_TEAL_2)),
    ]
    return ('<!doctype html><html lang="fa" dir="rtl"><head>'
            '<meta charset="utf-8">'
            f"<title>خوب بد زشت داده — {B.LOCKUP}</title>"
            f"<style>{style}</style></head><body>"
            f'<div class="sheet">{"".join(parts)}</div></body></html>')


def main() -> int:
    out = ROOT / "poster" / "IKCO_GS_data_dos_donts.html"
    out.write_text(html(), encoding="utf-8")
    print(f"✅ {out.relative_to(ROOT)} — {out.stat().st_size / 1024:,.0f} کیلوبایت")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
