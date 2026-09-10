# -*- coding: utf-8 -*-
"""پوستر آموزشی «بکن و نکنِ داده» — قلاب آموزشی برای کارشناسان خرید.

## چرا این اسکریپت، نه یک فایل HTML دستی

رنگ‌ها از ``alborz`` می‌آیند و خودرو از ``paykan``. اگر پالت عوض شود،
پوستر با یک اجرا عوض می‌شود؛ هیچ رنگی اینجا تعریف نمی‌شود. همان قاعده‌ای
که برای رابط و گزارش برقرار است.

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
from aibl.report import brand as B             # noqa: E402
from aibl.report import paykan                 # noqa: E402
from aibl.resolve.expert_scope import OWNER_FIELDS, UNOBSERVABLE_STAGES  # noqa: E402
from aibl.stages.s80_eventlog import ACTIVITIES  # noqa: E402

W = 900


def digits(n) -> str:
    """رقم فارسی. پوستر فارسی با عدد لاتین، نیمه‌کاره به‌نظر می‌رسد."""
    return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))



# ── تصویرسازی: خط‌نازکِ یک‌دست، نه آیکن عمومی ──────────────────────────
def _art(inner: str, w: int = 168, h: int = 112) -> str:
    return (f'<svg class="art" viewBox="0 0 168 112" width="{w}" height="{h}" '
            f'aria-hidden="true"><g fill="none" stroke="{A.TEAL_INK}" '
            f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            f'{inner}</g></svg>')


ART_FORM = _art(f'''
 <rect x="46" y="12" width="76" height="92" rx="6"/>
 <path d="M60 34h48M60 50h48M60 66h30"/>
 <circle cx="118" cy="84" r="16" fill="{A.ICE}" stroke="{A.TEAL_INK}"/>
 <path d="M111 84l5 5 9-10"/>''')

ART_GUESS = _art(f'''
 <rect x="40" y="22" width="88" height="72" rx="6"/>
 <path d="M40 44h88M60 22v-10M108 22v-10"/>
 <path d="M76 62c0-7 6-11 10-9 5 2 5 9 0 12-3 2-4 4-4 7" stroke-width="2.6"/>
 <path d="M82 86v.5" stroke-width="3.4"/>''')

ART_SHIP = _art(f'''
 <path d="M22 82h124l-14 18H36z" fill="{A.ICE}" stroke="{A.TEAL_INK}"/>
 <path d="M40 82V60h36v22M84 82V50h30v32"/>
 <path d="M48 60h20M92 62h14"/>
 <path d="M14 104c8 0 8-6 16-6s8 6 16 6 8-6 16-6 8 6 16 6 8-6 16-6 8 6 16 6 8-6 16-6"/>''')

ART_GAP = _art(f'''
 <rect x="26" y="20" width="116" height="72" rx="5"/>
 <path d="M26 42h116M64 20v72M104 20v72"/>
 <rect x="66" y="44" width="36" height="20" fill="{A.BLIND_BG}" stroke="{A.AMBER_BLIND}"/>
 <path d="M76 50l16 8M92 50l-16 8" stroke="{A.AMBER_BLIND}"/>''')

ART_PICK = _art(f'''
 <rect x="34" y="18" width="100" height="26" rx="5"/>
 <path d="M112 27l6 7 6-7"/>
 <rect x="34" y="52" width="100" height="18" rx="4" fill="{A.ICE}" stroke="{A.TEAL_INK}"/>
 <rect x="34" y="76" width="100" height="18" rx="4"/>
 <path d="M46 61h40M46 85h56"/>''')

ART_LIVE = _art(f'''
 <path d="M24 92a60 60 0 0 1 120 0" stroke-width="2.4"/>
 <path d="M84 92l34-30" stroke-width="3"/>
 <circle cx="84" cy="92" r="5" fill="{A.TEAL_INK}"/>
 <path d="M34 74l6-6M134 74l-6-6M84 34v8"/>''')

DO = [
    (ART_FORM, "شمارهٔ درخواست خرید را همان روز بزن",
     "«ثبت درخواست خرید» یکی از دو مرحله‌ای است که <b>هیچ سورسی آن را "
     "نمی‌بیند</b>. تنها ردِ آن، ستونی است که شما پر می‌کنید. تا آن خانه "
     "خالی است، طول عمر پرونده از روز اول شمرده نمی‌شود."),
    (ART_SHIP, "شمارهٔ بارنامه را در سورس خرید بنویس",
     "این تنها بندی است که سفارش را به محموله گره می‌زند. بدون آن، خرید و "
     "حمل دو پروندهٔ بی‌ربط می‌مانند و هیچ‌کس نمی‌فهمد این بار، بارِ کدام "
     "سفارش است."),
    (ART_PICK, "کد تأمین‌کننده را انتخاب کن، تایپ نکن",
     "یک کد تایپ‌شده با یک فاصلهٔ اضافه، یک تأمین‌کنندهٔ تازه می‌سازد. آن‌وقت "
     "کارنامهٔ یک شرکت بین دو نام تکه‌تکه می‌شود و هیچ‌کدام واقعیت را "
     "نشان نمی‌دهد."),
]

DONT = [
    (ART_GUESS, "تاریخ را از حافظه ننویس",
     "تاریخ، طولِ مرحله را می‌سازد و طولِ مرحله، رتبهٔ بحرانی را. یک "
     "تاریخِ حدسی فقط یک خانه را خراب نمی‌کند؛ رتبهٔ همهٔ قطعاتِ آن "
     "تأمین‌کننده را جابه‌جا می‌کند."),
    (ART_GAP, "خانهٔ خالی را با صفر یا خط تیره پر نکن",
     "سامانه بین «نمی‌دانم» و «صفر» فرق می‌گذارد: اولی نقطهٔ کور است و "
     "علامت می‌خورد، دومی یک <b>عددِ واقعی</b>. خط تیره، نقطهٔ کور را "
     "پنهان می‌کند — همان چیزی که باید دیده شود."),
    (ART_LIVE, "منتظر گزارش ماهانه نمان",
     "گزارش ماه، عکسِ گذشته است. آنچه امروز پر می‌کنید، همین امروز در "
     "داشبورد دیده می‌شود. تصمیمی که یک ماه دیر بگیرید، دیگر تصمیم "
     "نیست؛ گزارشِ خسارت است."),
]


def _rows() -> str:
    out = []
    for i, ((a1, t1, b1), (a2, t2, b2)) in enumerate(zip(DO, DONT)):
        out.append(f'''
<div class="row">
  <div class="cell do">{a1}<div class="pill do-pill">✓ {t1}</div><p>{b1}</p></div>
  <div class="node"></div>
  <div class="cell dont">{a2}<div class="pill dont-pill">✕ {t2}</div><p>{b2}</p></div>
</div>''')
    return "".join(out)


def _owner_strip() -> str:
    cells = "".join(
        f'<div class="own"><span class="own-n">{digits(i)}</span>{fa}</div>'
        for i, (_code, fa) in enumerate(OWNER_FIELDS, 1))
    return cells


def _stage_strip() -> str:
    return "".join(f'<span class="stg">{fa}</span>'
                   for *_x, fa, _o, _s in [(c, e, fa, o, s)
                                           for c, e, fa, o, s in ACTIVITIES])


def html() -> str:
    blind = " · ".join(f"{k}" for k in UNOBSERVABLE_STAGES)
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>بکن و نکنِ داده — IKCO Global Sourcing</title>
<style>
 @font-face {{ font-family:'IRANSans'; src: local('IRANSans'), local('IRANSansWeb'),
   local('IRANSansX'), local('IRANSansX-Regular'); }}
 *{{box-sizing:border-box}}
 body{{margin:0;background:{A.PAGE};font-family:{A.FONT_STACK};color:{A.INK}}}
 .sheet{{width:{W}px;margin:0 auto;background:{A.CARD};overflow:hidden;
        box-shadow:{A.shadow_css()}}}

 /* ── سربرگ: نوار تمام‌عرضِ طیف‌دار، با پیکان به‌عنوان قهرمان ── */
 .head{{background:{A.teal_gradient_css("135deg")};color:{A.ON_TEAL};
        padding:30px 44px 0;position:relative}}
 .kicker{{font-size:12px;letter-spacing:.14em;color:{A.ON_TEAL_2};
          text-transform:uppercase}}
 h1{{font-size:44px;line-height:1.18;margin:8px 0 14px;font-weight:800}}
 .sub{{display:inline-block;border:1.6px solid {A.ON_TEAL_2};color:{A.ON_TEAL};
       padding:7px 16px;font-size:16px;letter-spacing:.02em}}
 .car{{display:block;width:600px;margin:18px auto -26px;
       filter:drop-shadow(0 16px 22px rgba(0,0,0,.28))}}

 /* ── مقدمه: دو قابِ سفید و یک پیکان ── */
 .intro{{padding:44px 44px 26px;text-align:center;background:{A.CARD}}}
 .flow{{display:flex;align-items:center;justify-content:center;gap:16px;
        margin-bottom:16px}}
 .box{{border:1.6px solid {A.TEAL};padding:8px 18px;min-width:190px;
       box-shadow:5px 5px 0 {A.ICE}}}
 .box .lbl{{font-size:11px;color:{A.TEAL_INK};letter-spacing:.06em}}
 .box .val{{font-size:19px;font-weight:800;color:{A.INK}}}
 .arrow{{font-size:22px;color:{A.TEAL_INK}}}
 .intro p{{max-width:640px;margin:0 auto;font-size:15px;line-height:2;
           color:{A.INK_2}}}

 /* ── نوار: دو ستون و ستون فقرات ── */
 .band{{background:{A.BAND};padding:26px 40px 34px;position:relative}}
 .heads{{display:flex;align-items:center;justify-content:center;gap:18px;
         margin-bottom:8px}}
 .col-h{{background:{A.PILL};border:1.6px solid {A.TEAL};padding:6px 30px;
         font-size:20px;font-weight:800;box-shadow:5px 5px 0 {A.ICE}}}
 .col-h.no{{border-color:{A.STATUS['serious']};box-shadow:5px 5px 0 #EFD6C6;
            color:{A.STATUS_ON_TINT['serious']}}}
 .col-h.yes{{color:{A.TEAL_INK}}}
 .dot{{width:34px;height:34px;border:1.6px solid {A.SPINE};background:{A.PILL};
       display:grid;place-items:center;color:{A.INK_2};font-size:15px}}
 .spine{{position:absolute;top:44px;bottom:0;left:50%;width:1.6px;
         background:{A.SPINE};transform:translateX(-50%)}}
 .row{{display:grid;grid-template-columns:1fr 34px 1fr;align-items:start;
       gap:0;margin-top:22px}}
 .cell{{padding:0 22px}}
 .cell.do{{text-align:right}}
 .cell.dont{{text-align:right;padding-top:74px}}
 .node{{position:relative;top:96px;height:1.6px;background:{A.SPINE}}}
 .art{{display:block;margin-bottom:12px}}
 .cell.do .art{{margin-right:6px}}
 .pill{{display:inline-block;background:{A.PILL};border:1.6px solid {A.TEAL};
        padding:7px 14px;font-size:15.5px;font-weight:800;line-height:1.5;
        box-shadow:4px 4px 0 {A.ICE};color:{A.TEAL_INK}}}
 .dont-pill{{border-color:{A.STATUS['serious']};box-shadow:4px 4px 0 #EFD6C6;
             color:{A.STATUS_ON_TINT['serious']}}}
 .cell p{{font-size:13.5px;line-height:2.05;color:{A.INK_2};margin:12px 0 0}}
 .cell b{{color:{A.INK}}}

 /* ── شش ستونِ مالکیت ── */
 .own-wrap{{padding:30px 44px 34px;background:{A.CARD}}}
 .sec-h{{text-align:center;margin-bottom:6px}}
 .sec-h .t{{display:inline-block;background:{A.PILL};border:1.6px solid {A.TEAL};
            padding:6px 26px;font-size:19px;font-weight:800;
            box-shadow:5px 5px 0 {A.ICE};color:{A.TEAL_INK}}}
 .sec-h .s{{font-size:13px;color:{A.INK_3};margin-top:16px}}
 .owns{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px}}
 .own{{background:{A.BAND_ALT};border-right:3px solid {A.TEAL};padding:12px 14px;
       font-size:14px;font-weight:700;color:{A.INK};display:flex;
       align-items:center;gap:10px}}
 .own-n{{width:22px;height:22px;background:{A.TEAL};color:{A.ON_TEAL};
         font-size:12px;display:grid;place-items:center;flex:0 0 auto}}

 /* ── سیزده فعالیت ── */
 .stage-wrap{{background:{A.BAND};padding:26px 44px 30px;text-align:center}}
 .stgs{{display:flex;flex-wrap:wrap;gap:7px;justify-content:center;
        margin-top:18px}}
 .stg{{background:{A.PILL};border:1px solid {A.RULE};padding:6px 11px;
       font-size:12px;color:{A.INK_2}}}
 .blind{{margin-top:16px;display:inline-block;background:{A.BLIND_BG};
         border-right:3px solid {A.AMBER_BLIND};padding:9px 14px;font-size:12.5px;
         color:{A.AMBER_BLIND};text-align:right;line-height:1.9}}

 /* ── پاصفحهٔ تیره ── */
 .foot{{background:{A.TEAL_DEEP};color:{A.ON_TEAL};padding:26px 44px;
        display:flex;align-items:center;justify-content:space-between;gap:20px}}
 .foot .org{{font-size:17px;font-weight:800;line-height:1.7}}
 .foot .org span{{display:block;font-size:12px;font-weight:400;
                  color:{A.ON_TEAL_2};letter-spacing:.03em}}
 .foot .tag{{font-size:11.5px;color:{A.ON_TEAL_2};letter-spacing:.06em;
             text-align:left}}
</style></head><body><div class="sheet">

 <div class="head">
   <div class="kicker">{B.LOCKUP_FULL}</div>
   <h1>بکن و نکنِ داده<br>در زنجیرهٔ تأمین</h1>
   <div class="sub">داده‌ای که شما می‌نویسید، تصمیمی است که فردا گرفته می‌شود</div>
   <div class="car">{paykan.svg(600, uid="hero", ground=False, crop=True, inline=True)}</div>
 </div>

 <div class="intro">
   <div class="flow">
     <div class="box"><div class="lbl">از</div><div class="val">ثبت درخواست خرید</div></div>
     <div class="arrow">←</div>
     <div class="box"><div class="lbl">تا</div><div class="val">ترخیص کامل</div></div>
   </div>
   <p>میان این دو، <b>{digits(len(ACTIVITIES))} رویداد</b> ثبت می‌شود و
      <b>{digits(len(OWNER_FIELDS))} ستون</b> هست که هیچ سامانه‌ای پرشان نمی‌کند —
      مالکشان شمایید. این شش راهنما از خطاهای واقعیِ همین ستون‌ها آمده،
      نه از توصیهٔ کلی.</p>
 </div>

 <div class="band">
   <div class="spine"></div>
   <div class="heads">
     <div class="col-h yes">بکن</div>
     <div class="dot">↓</div>
     <div class="col-h no">نکن</div>
   </div>
   {_rows()}
 </div>

 <div class="own-wrap">
   <div class="sec-h"><div class="t">شش ستونی که مالکشان شمایید</div>
     <div class="s">هیچ‌کدام از سورس‌ها این‌ها را نمی‌سازند. هر خانهٔ خالی،
        یک نقطهٔ کور در پروندهٔ همان قطعه است.</div></div>
   <div class="owns">{_owner_strip()}</div>
 </div>

 <div class="stage-wrap">
   <div class="sec-h"><div class="t">{digits(len(ACTIVITIES))} رویدادی که پرونده را می‌سازند</div></div>
   <div class="stgs">{_stage_strip()}</div>
   <div class="blind">دو مرحله را <b>هیچ سورسی نمی‌بیند</b> ({blind}) —
      این‌ها فقط از دستِ شما ثبت می‌شوند.</div>
 </div>

 <div class="foot">
   {paykan.mark(84, A.ON_TEAL_2)}
   <div class="org">{B.COMPANY} · {B.UNIT} ({B.UNIT_SHORT})
     <span>{B.DIVISION} ({B.DIVISION_SHORT}) · {B.TEAM}</span></div>
   <div class="tag">{A.TAGLINE}</div>
 </div>

</div></body></html>'''


def main() -> int:
    out = ROOT / "poster" / "IKCO_GS_data_dos_donts.html"
    out.write_text(html(), encoding="utf-8")
    print(f"✅ {out.relative_to(ROOT)} — {out.stat().st_size / 1024:,.0f} کیلوبایت")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
