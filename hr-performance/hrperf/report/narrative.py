# -*- coding: utf-8 -*-
"""روایت — دستور زبانِ داستان‌گوییِ «البرز».

    نظام: البرز · نسخهٔ ۱٫۲
    مرجع: قالب نهاییِ فیگما، صفحهٔ «پوستر ۲۰۲۶»
    https://www.figma.com/design/XOPK0BH9oZpkSID19awXJe

## چرا این فایل هست

گزارشی که با جدول شروع می‌شود و با جدول تمام می‌شود، خوانده نمی‌شود؛
**اسکن** می‌شود. قالبی که سفارش‌دهنده در فیگما ساخت، همین را عوض می‌کند:
هر خروجی یک **روایت** است با ترتیبِ ثابت. این ماژول آن ترتیب را از یک
پوستر به یک **قاعده** تبدیل می‌کند تا همهٔ خروجی‌ها — HTML، ایمیل و
اکسل — یک شکل حرف بزنند.

## دستور زبان — هشت عنصر، همیشه به این ترتیب

| عنصر | کارش | نمونه از قالب |
|---|---|---|
| `eyebrow` | فصل را نام می‌گذارد | «داستان یک سفارش» |
| `opening` | روایت را باز می‌کند، **با عددِ واقعی** | «این گزارش دربارهٔ ۱٬۲۴۸ پرونده است…» |
| `chapter` | سرفصل با یک جملهٔ راهنما | «مسیرِ یک پرونده — از ثبت تا تحویل» |
| `knot` | گره: جایی که خواننده انتخاب دارد | «گرهٔ زمان — تاریخ‌گذاری» |
| `bridge` | خواننده را به گرهٔ بعد می‌برد | «حالا ردِ بار را دنبال کن» |
| `resolution` | جمع‌بندیِ گره‌ها | «اگر هر سه گره را درست ببندی» |
| `coda` | یک جمله که در ذهن می‌ماند | «مالکیت داده، مالکیت پرونده است.» |
| `badge` | مُهر پایان | «END OF REPORT · ۲۰۲۶» |

## قاعدهٔ نشکستنی

**`opening` و `resolution` هرگز متن ثابت نیستند.** هر دو از عددهای همان
گزارش ساخته می‌شوند. روایتی که با هر داده‌ای یک جمله بگوید، روایت نیست؛
شعار است — و همان ایرادی است که یک بار به پوستر گرفته شد.

هیچ رنگی اینجا تعریف نمی‌شود؛ همه از ``alborz`` می‌آید.
"""
from __future__ import annotations

__contract__ = 1

import html as _h
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import alborz as _AL

VERSION = "1.3"

#: هشت عنصرِ دستور زبان، به ترتیبِ روایت. تست این ترتیب را قفل می‌کند.
GRAMMAR: Tuple[str, ...] = ("eyebrow", "opening", "chapter", "knot",
                            "bridge", "resolution", "coda", "badge")

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(n) -> str:
    """رقم فارسی با جداکنندهٔ هزار. گزارشِ فارسی با عدد لاتین، دورگه است."""
    if isinstance(n, float):
        n = round(n)
    return f"{n:,}".replace(",", "٬").translate(_FA_DIGITS)


# ═══════════════════ ساختارهای روایت ═══════════════════
@dataclass(frozen=True)
class Chapter:
    """یک فصل از مسیر — نام، جملهٔ راهنما، و گام‌هایی که زیرش می‌آیند."""
    key: str
    title: str
    line: str
    steps: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Knot:
    """گره — جایی که خواننده بینِ راهِ درست و راهِ پرهزینه انتخاب دارد.

    ``bridge`` او را به گرهِ بعد می‌برد. گرهِ آخر پلی ندارد؛ به
    ``resolution`` می‌رسد.
    """
    no: int
    name: str
    do_title: str
    do_body: str
    dont_title: str
    dont_body: str
    bridge: str = ""


@dataclass
class Facts:
    """عددهایی که روایت از آن‌ها ساخته می‌شود — نه متن، فقط واقعیت."""
    total: int = 0
    subject: str = "پرونده"
    ref_date: str = ""
    critical: int = 0
    critical_label: str = "بحرانی"
    blind: int = 0
    median: Optional[float] = None
    median_label: str = "میانهٔ مقاومت"
    median_unit: str = "روز"
    extra: List[Tuple[str, str]] = field(default_factory=list)


# ═══════════════════ متنِ روایت، از عدد ═══════════════════
def opening(f: Facts) -> str:
    """بندِ آغاز — ساخته‌شده از عددهای همین گزارش، نه از قالبِ ثابت.

    اگر داده‌ای نباشد، روایت هم چیزی ادعا نمی‌کند و همین را می‌گوید.
    """
    if not f.total:
        return ("این گزارش خالی است: با فیلترهای فعلی هیچ "
                f"{f.subject}‌ای نماند. روایتی هم نیست که گفته شود.")
    s = [f"این گزارش دربارهٔ **{fa(f.total)} {f.subject}** است"]
    if f.ref_date:
        s.append(f" تا تاریخ {f.ref_date}")
    s.append(". ")
    if f.critical:
        share = f.critical / f.total * 100
        s.append(f"از این میان **{fa(f.critical)}** ({fa(share)}٪) "
                 f"{f.critical_label}‌اند")
        s.append(" — همان‌هایی که تصمیم می‌خواهند، نه گزارش. ")
    if f.median is not None:
        s.append(f"{f.median_label} **{fa(f.median)} {f.median_unit}** است. ")
    if f.blind:
        s.append(f"و **{fa(f.blind)} {f.subject}** نقطهٔ کور دارند: خانه‌ای "
                 "که هیچ سورسی پرش نمی‌کند و فقط از دستِ شما پر می‌شود.")
    return "".join(s).strip()


def resolution(f: Facts) -> Tuple[str, List[str]]:
    """جمع‌بندی — باز هم از عدد، نه از شعار. (عنوان، بندها)"""
    if not f.total:
        return ("چیزی برای جمع‌بندی نیست", ["فیلترها را بازتر کنید."])
    lines = []
    if f.critical:
        lines.append(f"**{fa(f.critical)} {f.subject}** امروز تصمیم می‌خواهد؛ "
                     "فردا همان‌ها گزارشِ خسارت‌اند.")
    if f.blind:
        share = f.blind / f.total * 100
        lines.append(f"**{fa(share)}٪** نقطهٔ کور دارند. هر خانه‌ای که "
                     "امروز پر شود، یک نقطهٔ کور کمتر است.")
    else:
        lines.append("هیچ نقطهٔ کوری نماند — ستون‌های مالکیتی پر شده‌اند.")
    for label, value in f.extra:
        lines.append(f"{label}: **{value}**")
    return ("اگر همین امروز دست به کار شوی", lines)


# ═══════════════════ HTML — نوار، گره، پل ═══════════════════
def _md(s: str) -> str:
    """تنها نشانه‌گذاریِ مجاز: ``**پررنگ**``. بقیه escape می‌شود."""
    out, bold = [], False
    for i, part in enumerate(_h.escape(s).split("**")):
        out.append(f"<b>{part}</b>" if bold else part)
        bold = not bold
    return "".join(out)


def css() -> str:
    """سبکِ روایت — **کپیِ قالب نهاییِ فیگما**، نه تفسیر آن.

    هر عدد اینجا از خودِ قالب خوانده شده: فاصله‌ها، گوشه‌ها، وزن‌ها و
    اندازه‌ها. رنگ‌ها از ``alborz`` می‌آیند و هیچ‌کدام اینجا تعریف
    نمی‌شوند.

    کنتراستِ همان رنگ‌ها اندازه‌گیری شد و همه از کف رد شدند:
    سفید روی قرصِ فصل ۶٫۰۹، سفید روی قرصِ فاز ۴٫۷۱، عنوان روی
    روشن‌ترین توقفِ طیف ۵٫۲۶، معنیِ ستون روی کارت ۵٫۲۹.
    """
    g = _AL.header_gradient_css(_AL.HEADER_ANGLE)
    grain = _grain_uri()
    return f"""
/* ── روایت — قالب نهایی ─────────────────────────────────────────────
   ترتیب همیشه یکی است: سربرگِ تیره → قلاب → گره‌ها → نتیجه →
   مسیر → پاصفحهٔ مُهردار. */

/* سربرگِ تیره — **صحنهٔ ۹۰۰×۵۲۰ قالب**، نه تفسیر آن.

   هر طول با ``--u`` نوشته شده: در مرورگرِ امروز یک‌نهمِ ``cqw`` (یعنی
   عرضِ نوار تقسیم بر ۹۰۰) و در موتورهای قدیمی ۱px. پس در عرض ۹۰۰
   دقیقاً همان قالب است و در هر عرض دیگری همان نسبت‌ها — بدون
   ``transform`` و بدون آنکه متن از انتخاب و چاپ بیفتد.

   لبهٔ راستِ سه بلوکِ بالا در قالب یکی نیست و عمداً یکی‌اش نمی‌کنیم:
   سرسطرِ سازمان تا ۶۹۰ می‌آید، عنوان تا ۷۵۵ و نوارِ تمرکز تا ۸۱۴.
   همین ناهم‌ترازیِ حساب‌شده است که نوار را «چیده‌شده» نشان می‌دهد.

   زیرعنوان و بندِ آغاز در قالب **فیزیکاً چپ**اند (۴۴)، کنارِ خودرو که
   از ۴۳۰ شروع می‌شود — نه زیرِ آن. */
/* لفافِ بیرونی کانتینر است، نه خودِ نوار: یک کوئریِ کانتینر عنصرِ
   کانتینر را نمی‌تواند بازطراحی کند، فقط فرزندانش را. */
.nr-hero-wrap{{--u:1px}}
@supports (container-type:inline-size){{
  .nr-hero-wrap{{container-type:inline-size;--u:calc(1cqw/9)}}}}
.nr-hero{{position:relative;overflow:hidden;isolation:isolate;
  background:{g};color:{_AL.ON_TEAL};
  min-height:calc(520*var(--u));
  box-shadow:inset 0 9px 18px -2px {_AL.rgba(_AL.EMBOSS_DARK, .34)},
             inset 0 -4px 12px -3px {_AL.rgba(_AL.EMBOSS_LIGHT, .12)}}}
.nr-grain{{position:absolute;inset:0;pointer-events:none;z-index:9;
  mix-blend-mode:overlay;background-repeat:repeat;
  background-size:calc(200*var(--u)) calc(200*var(--u))}}

/* لایهٔ تزئین — غبارِ داده، دو خطِ افقی. هرگز جلوی متن نمی‌آید و اگر
   عنوان بلند شد کش نمی‌آید؛ به همان صحنهٔ ۵۲۰ چسبیده می‌ماند. */
.nr-deco{{position:absolute;inset:0;pointer-events:none;z-index:0}}
.nr-deco svg{{position:absolute;left:0;top:0;width:100%;
  height:calc(520*var(--u));display:block;overflow:visible}}
.nr-rule-top{{position:absolute;left:calc(44*var(--u));top:calc(112*var(--u));
  width:calc(812*var(--u));height:.5px;background:{_AL.rgba(_AL.DUST, .094)}}}
.nr-rule-title{{position:absolute;left:calc(44*var(--u));top:calc(332*var(--u));
  width:calc(380*var(--u));height:.6px;background:{_AL.rgba(_AL.DUST, .188)}}}

/* نشانِ حک‌شده — ۱۳۰×۱۲۰ در (۳۸،۳۲). ``screen`` + همان فیلترِ قالب
   آن را از فلزِ خاکستری به فلزِ تیل می‌برد. */
.nr-emblem{{position:absolute;left:calc(38*var(--u));top:calc(32*var(--u));
  width:calc(130*var(--u));height:calc(120*var(--u));
  opacity:.92;mix-blend-mode:screen;z-index:1}}
.nr-emblem img,.nr-emblem svg{{width:100%;height:100%;display:block;
  object-fit:contain;
  filter:grayscale(1) brightness(1.08) sepia(.6) hue-rotate(118deg)
         saturate(1.7) drop-shadow(0 0 calc(7*var(--u)) {_AL.rgba(_AL.ICE, .28)})}}

/* قاب پیکان — ۴۳۰×۱۸۹ در (۴۳۰،۳۰۰)، با سه خطِ حرکتِ کجِ ۳ درجه. */
.nr-car{{position:absolute;left:calc(430*var(--u));top:calc(300*var(--u));
  width:calc(430*var(--u));height:calc(189*var(--u));
  overflow:hidden;z-index:1}}
.nr-car img,.nr-car>svg.pk{{position:absolute;inset:0;width:100%;height:100%;
  object-fit:contain;display:block}}
.nr-motion{{position:absolute;left:0;top:calc(108*var(--u));
  width:calc(205*var(--u));height:calc(34*var(--u));
  opacity:.55;transform:rotate(3deg);transform-origin:left center}}

/* سرسطرِ سازمان و نوارِ تمرکز — ارتفاعشان ثابت است، پس مطلق می‌مانند. */
.nr-hero .kick{{position:absolute;top:calc(170*var(--u));
  right:calc(210*var(--u));width:calc(722*var(--u));z-index:2;
  margin:0;text-align:right;line-height:1;
  font-size:calc(11*var(--u));font-weight:500;
  letter-spacing:calc(2*var(--u));opacity:.7;color:{_AL.ON_TEAL_2}}}
.nr-focus{{position:absolute;left:calc(44*var(--u));top:calc(188*var(--u));
  width:calc(770*var(--u));height:calc(3*var(--u));z-index:2;
  background:linear-gradient(90deg,{_AL.rgba(_AL.DUST, 0)},{_AL.rgba(_AL.DUST, .25)} 50%,{_AL.rgba(_AL.DUST, 0)})}}

/* از عنوان به پایین در جریان می‌ماند تا عنوانِ بلندترِ یک گزارش،
   به‌جای بریدن، بقیه را پایین بِبَرد و نوار خودش بلند شود. */
/* نوار خودش padding ندارد: ``cqw`` جعبهٔ **محتوا** را می‌سنجد، و هر
   padding روی نوار واحد را کوچک می‌کرد و کلِ صحنه را ۹۰٪ می‌ساخت. */
.nr-flow{{position:relative;z-index:2;
  padding:calc(222*var(--u)) calc(44*var(--u)) calc(36*var(--u))}}
/* جعبهٔ عنوان در قالب از ۴۴ بیرون می‌زند تا به ۷۷۰ برسد (از -۱۵ تا
   ۷۵۵). همان را می‌دهیم، وگرنه در عرض‌های کوچک روی لبه می‌شکند. */
.nr-hero h2{{margin:0 calc(101*var(--u)) 0 calc(-59*var(--u));
  font-size:calc(40*var(--u));font-weight:900;line-height:1.08;
  text-align:right;color:{_AL.TITLE_TOP};
  background-image:linear-gradient({_AL.TITLE_ANGLE},{_AL.TITLE_TOP} 25%,{_AL.TITLE_BOT} 75%);
  -webkit-background-clip:text;background-clip:text;
  -webkit-text-fill-color:transparent;
  text-shadow:2px 4px 3px {_AL.rgba(_AL.ENGRAVE_DARK, .69)}, -1px -1px 1.5px {_AL.rgba(_AL.ENGRAVE_LIGHT, .16)}}}
@supports not ((-webkit-background-clip:text) or (background-clip:text)){{
  .nr-hero h2{{-webkit-text-fill-color:{_AL.TITLE_TOP};background-image:none}}}}
/* قاب زیرعنوان — چپ، با خطِ ۱٫۵ روی لبهٔ چپ؛ عیناً قالب. */
.nr-hero .sub{{width:max-content;max-width:100%;
  margin:calc(78.8*var(--u)) auto 0 0;
  padding:calc(9*var(--u)) calc(20*var(--u));
  border-left:calc(1.5*var(--u)) solid {_AL.ON_TEAL_2};
  font-size:calc(17*var(--u));font-weight:700;line-height:1.6;
  text-align:right;opacity:.92;color:{_AL.ON_TEAL}}}
/* بندِ آغازِ روایت — خطِ ۳۶×۱٫۵ فیزیکاً چپ، متنِ راست‌چین کنارش. */
.nr-lead{{display:flex;direction:ltr;align-items:flex-start;
  gap:calc(14*var(--u));width:calc(722*var(--u));max-width:100%;
  margin:calc(62.8*var(--u)) auto 0 0}}
.nr-lead .rule{{flex:0 0 calc(36*var(--u));height:calc(1.5*var(--u));
  margin-top:calc(9*var(--u));background:{_AL.ON_TEAL_2};opacity:.45}}
.nr-lead p{{direction:rtl;margin:0;width:calc(360*var(--u));max-width:100%;
  font-size:calc(12*var(--u));line-height:1.7;text-align:right;
  opacity:.78;color:{_AL.ON_TEAL_2}}}
.nr-lead b{{color:{_AL.ON_TEAL};opacity:1}}
/* زیر ۶۲۰: صحنه دیگر جا نمی‌شود. به‌جای برخورد، می‌ایستد و ستونی
   می‌شود — خودرو زیر متن، و نوار به اندازهٔ محتوا بلند. */
@container (max-width:620px){{
  .nr-hero{{display:flex;flex-direction:column;min-height:0}}
  .nr-deco svg{{height:calc(320*var(--u))}}
  .nr-rule-title{{display:none}}
  .nr-emblem{{width:calc(96*var(--u));height:calc(88*var(--u))}}
  .nr-hero .kick{{position:static;order:0;width:auto;
    margin:calc(150*var(--u)) calc(44*var(--u)) 0}}
  .nr-focus{{position:static;order:1;width:auto;
    margin:calc(10*var(--u)) calc(44*var(--u)) 0}}
  .nr-flow{{order:2;padding-top:calc(26*var(--u))}}
  .nr-hero h2{{margin-inline:0}}
  .nr-hero .sub{{width:auto;white-space:normal;margin-top:calc(22*var(--u))}}
  .nr-lead{{width:auto;margin-top:calc(24*var(--u))}}
  .nr-lead p{{width:auto;flex:1 1 auto}}
  .nr-car{{position:static;order:3;width:auto;height:auto;
    aspect-ratio:430/189;margin:0 calc(44*var(--u)) calc(28*var(--u))}}
  .nr-car img{{position:static}}
  .nr-motion{{display:none}}}}
@supports not (container-type:inline-size){{
  @media (max-width:620px){{
    .nr-hero .sub{{width:auto;white-space:normal}}
    .nr-lead{{width:100%}}
    .nr-lead p{{width:auto;flex:1 1 auto}}}}}}

/* قرصِ فصل — همان شکلِ قالب: گوشهٔ ۴، پرِ تیل تیره، متن سفید */
.nr-pill{{display:inline-block;background:{_AL.TEAL_INK};color:{_AL.ON_TEAL};
  border-radius:4px;padding:5px 18px;font-size:12px;font-weight:700}}
.nr-pill.alt{{background:{_AL.TEAL}}}

/* قلاب */
.nr-hook{{text-align:center;padding:22px 0 28px}}
.nr-hook p{{margin:10px auto 0;max-width:820px;font-size:14px;line-height:2;
  color:{_AL.INK_2}}}
.nr-hook b{{color:{_AL.INK}}}

/* گره‌ها */
.nr-knot{{margin-bottom:4px}}
.nr-knot .no{{display:flex;align-items:center;justify-content:center;gap:8px;
  padding-bottom:8px}}
.nr-knot .no i{{font-style:normal;width:26px;height:26px;border-radius:50%;
  background:{_AL.TEAL};color:{_AL.ON_TEAL};font-size:12px;font-weight:800;
  display:flex;align-items:center;justify-content:center}}
.nr-knot .no span{{font-size:12px;color:{_AL.TEAL_INK}}}
.nr-row{{display:grid;grid-template-columns:1fr 34px 1fr;align-items:stretch}}
.nr-col{{padding:0 22px}}
.nr-col.no-go{{padding-top:74px}}
.nr-gutter{{position:relative}}
.nr-gutter::before{{content:"";position:absolute;top:0;bottom:0;left:50%;
  width:1.6px;background:{_AL.SPINE};transform:translateX(-50%)}}
.nr-card{{background:{_AL.PILL};border:1.6px solid {_AL.TEAL};
  box-shadow:4px 4px 0 {_AL.ICE};padding:10px 14px;margin-bottom:12px}}
.nr-card.no-go{{border-color:{_AL.STATUS['serious']};
  box-shadow:4px 4px 0 {_AL.SHADOW_WARN}}}
.nr-card .h{{font-size:16px;font-weight:800;line-height:1.7;color:{_AL.TEAL_INK}}}
.nr-card.no-go .h{{color:{_AL.STATUS_ON_TINT['serious']}}}
.nr-card .b{{font-size:14px;line-height:2;color:{_AL.INK_2};margin-top:6px}}
.nr-card .b b{{color:{_AL.INK}}}

/* پلِ بین گره‌ها — خط، حباب، خط */
.nr-link{{display:flex;align-items:center;justify-content:center;gap:10px;
  padding:18px 0}}
.nr-link .ln{{flex:0 1 120px;height:1px;background:{_AL.SPINE}}}
.nr-link .bb{{background:{_AL.PILL};border:1.2px solid {_AL.SPINE};
  border-radius:20px;padding:5px 14px;font-size:11px;color:{_AL.INK_3};
  white-space:nowrap}}

/* نتیجه — خط، برچسب، خط + کارت‌های عددی */
.nr-res{{padding-top:32px;text-align:center}}
.nr-res .bar{{display:flex;align-items:center;gap:12px}}
.nr-res .bar .ln{{flex:1 1 auto;height:1px;background:{_AL.SPINE}}}
.nr-res .cards{{display:flex;flex-wrap:wrap;gap:16px;justify-content:center;
  margin-top:16px}}
.nr-res .c{{box-sizing:border-box;background:{_AL.PILL};border:1px solid {_AL.BAND_ALT};
  border-radius:10px;box-shadow:0 3px 10px {_AL.rgba(_AL.TEAL, .07)};
  padding:14px 18px;min-width:210px;max-width:320px;text-align:right;
  font-size:13px;line-height:1.95;color:{_AL.INK_2}}}
.nr-res .c b{{color:{_AL.INK}}}

/* مسیر — فازِ برچسب‌دار، گام‌های شماره‌دار، اتصال عمودی */
.nr-journey{{text-align:center;padding-top:6px}}
.nr-phase{{margin-bottom:0}}
.nr-steps{{display:flex;flex-wrap:wrap;align-items:flex-start;
  justify-content:center;padding-top:12px}}
.nr-step{{display:flex;flex-direction:column;align-items:center;gap:6px;
  width:140px}}
.nr-step i{{font-style:normal;width:30px;height:30px;border-radius:50%;
  background:{_AL.PILL};border:1.6px solid {_AL.TEAL};color:{_AL.TEAL_INK};
  font-size:13px;font-weight:800;display:flex;align-items:center;
  justify-content:center}}
.nr-step span{{font-size:11px;line-height:1.65;color:{_AL.INK_2}}}
.nr-hop{{flex:0 0 24px;height:2px;background:{_AL.SPINE};margin-top:14px}}
.nr-drop{{width:2px;height:14px;background:{_AL.TEAL};margin:0 auto}}

/* کارت‌های ستون — همان کارت قالب: ۲۴۶ پهنا، گوشهٔ ۱۰، سایهٔ تیلِ رقیق */
.nr-cards{{display:flex;flex-wrap:wrap;gap:14px;justify-content:center;
  padding-top:12px}}
.nr-c{{box-sizing:border-box;background:{_AL.PILL};border:1px solid {_AL.BAND_ALT};border-radius:10px;
  box-shadow:0 3px 10px {_AL.rgba(_AL.TEAL, .07)};padding:16px 16px 14px;
  width:246px;text-align:right}}
.nr-c .k{{display:flex;align-items:center;justify-content:space-between;gap:8px}}
.nr-c .k i{{font-style:normal;width:22px;height:22px;background:{_AL.TEAL};
  color:{_AL.ON_TEAL};font-size:11px;font-weight:800;display:flex;
  align-items:center;justify-content:center;flex:0 0 auto}}
.nr-c .t{{font-size:13px;font-weight:700;line-height:1.75;color:{_AL.INK}}}
.nr-c .m{{font-size:11px;line-height:1.7;color:{_AL.INK_3};margin-top:8px}}

/* رابطِ «ادامه ↓» */
.nr-cont{{text-align:center;padding-top:18px}}
.nr-cont .v{{width:2px;height:20px;background:{_AL.TEAL};margin:0 auto}}
.nr-cont .p{{display:inline-block;margin-top:4px;background:{_AL.TEAL};
  color:{_AL.ON_TEAL};border-radius:10px;padding:3px 12px;font-size:10px}}

/* پاصفحهٔ مُهردار */
.nr-foot{{background:{_AL.TEAL_DEEP};color:{_AL.ON_TEAL};padding:22px 44px;
  display:flex;align-items:center;justify-content:space-between;gap:20px;
  margin-top:24px}}
.nr-foot .org{{font-size:17px;font-weight:900;text-align:right}}
.nr-foot .org span{{display:block;font-size:11px;font-weight:400;
  color:{_AL.ON_TEAL_2};margin-top:4px}}
.nr-foot .tag{{font-size:11.5px;letter-spacing:.7px;color:{_AL.ON_TEAL_2};
  text-align:left}}
.nr-badge{{display:inline-block;margin-top:8px;font-size:9px;
  letter-spacing:1.8px;border:1px solid {_AL.ON_TEAL_2};color:{_AL.ON_TEAL_2};
  padding:3px 9px}}

/* ── همان ظرافت، روی سربرگِ گزارش‌ها ──────────────────────────────────
   گزارش‌ها سربرگ خودشان را دارند (عنوان + آمار + دکمهٔ چاپ)، نه بلوک
   کاملِ پوستر. ولی بافت، حکِ عنوان و عمقِ نوار باید یکی باشد؛ وگرنه
   پوستر و گزارش دو جنس به‌نظر می‌رسند. */
header{{position:relative;overflow:hidden;
  box-shadow:inset 0 9px 18px -2px {_AL.rgba(_AL.EMBOSS_DARK, .34)},
             inset 0 -4px 12px -3px {_AL.rgba(_AL.EMBOSS_LIGHT, .12)}}}
header::after{{content:"";position:absolute;inset:0;pointer-events:none;
  background-image:url({grain});background-repeat:repeat;
  mix-blend-mode:overlay;opacity:.14;
  background-size:200px 200px}}
header>*{{position:relative;z-index:1}}
header h1{{color:{_AL.TITLE_TOP};
  background-image:linear-gradient({_AL.TITLE_ANGLE},
    {_AL.TITLE_TOP} 25%,{_AL.TITLE_BOT} 75%);
  -webkit-background-clip:text;background-clip:text;
  -webkit-text-fill-color:transparent;
  text-shadow:2px 4px 3px {_AL.rgba(_AL.ENGRAVE_DARK, .69)},
  -1px -1px 1px {_AL.rgba(_AL.ENGRAVE_LIGHT, .12)}}}
@media print{{ header::after{{display:none}} }}

@media print{{
  .nr-knot,.nr-card,.nr-res .c,.nr-c,.nr-phase{{break-inside:avoid}}
  .nr-hero,.nr-foot{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
}}
@media (max-width:760px){{
  .nr-row{{grid-template-columns:1fr}}
  .nr-col.no-go{{padding-top:0}}
  .nr-gutter{{display:none}}
  .nr-hero h2{{font-size:30px}}
}}
"""


#: بافت ریز روی نوار سربرگ. قالب فیگما دو افکت «نویز» و «بافت» دارد که
#: هیچ معادل مستقیمی در CSS ندارند؛ این ``feTurbulence`` همان دانه‌دانگی
#: را می‌سازد و چون data-URI است، هیچ چیزی از شبکه گرفته نمی‌شود.
def _grain_uri() -> str:
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
           '<filter id="g"><feTurbulence type="fractalNoise"'
           ' baseFrequency="0.65 0.25" numOctaves="4" seed="5"'
           ' stitchTiles="stitch"/>'
           '<feColorMatrix type="saturate" values="0"/></filter>'
           '<rect width="100%" height="100%" filter="url(#g)"/></svg>')
    import base64 as _b
    return "data:image/svg+xml;base64," + _b.b64encode(svg.encode()).decode()


def _grain(opacity: float = 0.13) -> str:
    return (f'<div class="nr-grain" style="background-image:url({_grain_uri()});'
            f'opacity:{opacity}"></div>')


#: غبارِ داده — **۱۱۳ نقطهٔ خودِ قالب**، نه بازسازیِ حدسی. هشت ردیف که
#: از راست‌بالا باز می‌شوند و پنج نقطهٔ تنها که رو به عنوان محو می‌شوند.
#: هر چهارتایی ``(x, y, قطر, شفافیت)`` روی صحنهٔ ۹۰۰×۵۲۰ است.
#:
#: پیش از این، اینجا هفت «پرتو» بود که من ساخته بودم — و همین بود که
#: سربرگ را شبیهِ قالب نمی‌کرد. حدس جای داده را نمی‌گیرد.
_DUST: Tuple[Tuple[float, float, float, float], ...] = (
    (536,28,3.5,0.784), (556,24,3.5,0.753), (576,21,4,0.784), (598,26,3,0.627), (618,22,3.5,0.753), (640,28,4,0.816),
    (662,24,3,0.722), (682,30,3.5,0.847), (704,26,4,0.878), (726,22,3,0.784), (748,28,3.5,0.816), (770,24,4,0.91),
    (793,30,3,0.753), (814,26,3.5,0.847), (835,22,4,0.878), (857,28,3,0.784), (500,48,3,0.502), (522,46,3.5,0.627),
    (546,44,4,0.722), (568,48,3,0.753), (590,44,3.5,0.784), (612,48,4,0.816), (634,44,3,0.784), (656,50,3.5,0.847),
    (678,46,4,0.878), (700,50,3,0.816), (722,46,3.5,0.878), (744,50,4,0.91), (766,46,3,0.847), (788,50,3.5,0.91),
    (810,46,4,0.941), (832,50,3,0.847), (854,46,3.5,0.878), (875,50,4,0.816), (480,68,2.5,0.251), (503,66,3,0.408),
    (526,64,3.5,0.565), (550,68,3,0.659), (572,64,4,0.753), (595,68,3,0.784), (618,66,3.5,0.816), (640,70,4,0.847),
    (663,66,3,0.784), (685,70,3.5,0.878), (708,66,4,0.847), (730,70,3,0.91), (752,66,3.5,0.941), (775,70,4,0.91),
    (797,66,3,0.941), (820,70,3.5,0.91), (842,66,4,0.941), (864,70,3,0.878), (884,66,3.5,0.847), (488,88,2.5,0.188),
    (512,86,3,0.314), (535,88,3.5,0.471), (558,86,3,0.596), (581,88,4,0.69), (604,86,3,0.753), (627,90,3.5,0.784),
    (650,86,4,0.847), (672,90,3,0.878), (695,86,3.5,0.847), (718,90,4,0.91), (740,86,3,0.941), (763,90,3.5,0.91),
    (786,86,4,0.941), (808,90,3,0.91), (831,86,3.5,0.816), (853,90,4,0.753), (875,86,3,0.69), (524,108,2.5,0.22),
    (548,106,3,0.376), (571,108,3.5,0.533), (595,106,3,0.659), (618,110,4,0.753), (641,106,3,0.784), (664,110,3.5,0.847),
    (687,106,4,0.816), (710,110,3,0.753), (733,106,3.5,0.69), (756,110,4,0.596), (779,106,3,0.502), (802,108,3.5,0.408),
    (825,106,4,0.314), (848,108,3,0.22), (560,128,2.5,0.251), (584,126,3,0.408), (608,130,3.5,0.565), (632,126,3,0.627),
    (656,130,4,0.659), (680,126,3,0.596), (704,130,3.5,0.502), (728,126,4,0.408), (752,128,3,0.314), (775,126,3.5,0.22),
    (798,128,4,0.157), (596,148,2.5,0.188), (622,148,3,0.314), (648,150,3.5,0.408), (674,148,3,0.345), (700,150,4,0.251),
    (726,148,3,0.157), (752,150,3.5,0.094), (634,170,2.5,0.157), (662,170,3,0.251), (690,172,3.5,0.188), (718,170,3,0.125),
    (672,192,2.5,0.094), (702,196,2,0.063), (648,214,2,0.047), (726,210,2.5,0.039), (684,234,2,0.031),
)

_KPI_DOTS: Tuple[Tuple[float, float, float, float], ...] = (
    (494,300,5,0.878), (510,318,4,0.753), (524,334,3,0.565),
)

#: رابطِ نقطه‌های KPI — دو خطِ ۱۶ تایی با چرخش ۵۲ درجه.
_KPI_LINKS: Tuple[Tuple[float, float, str, float], ...] = (
    (497, 302, "GOLD", 0.502),
    (513, 320, "DUST", 0.376),
)


def _deco() -> str:
    """لایهٔ تزئینِ سربرگ — غبار، نقطه‌های KPI و رابط‌هایشان.

    همه در یک ``<svg>`` با ``viewBox="0 0 900 520"`` می‌نشینند تا با
    صحنه بکشند؛ رنگ‌ها از ``alborz`` می‌آیند و هیچ‌کدام اینجا تعریف
    نمی‌شوند.
    """
    p = [f'<circle cx="{x + d / 2:g}" cy="{y + d / 2:g}" r="{d / 2:g}" '
         f'fill="{_AL.DUST}" opacity="{o:g}"/>' for x, y, d, o in _DUST]
    for i, (x, y, d, o) in enumerate(_KPI_DOTS):
        fill = _AL.GOLD if i == 0 else _AL.DUST
        p.append(f'<circle cx="{x + d / 2:g}" cy="{y + d / 2:g}" r="{d / 2:g}" '
                 f'fill="{fill}" opacity="{o:g}"/>')
    for x, y, tok, o in _KPI_LINKS:
        c = _AL.GOLD if tok == "GOLD" else _AL.DUST
        p.append(f'<line x1="{x:g}" y1="{y:g}" x2="{x + 16:g}" y2="{y:g}" '
                 f'stroke="{c}" stroke-opacity="{o:g}" stroke-width="0.8" '
                 f'transform="rotate(52 {x:g} {y:g})"/>')
    return ('<div class="nr-deco" aria-hidden="true">'
            '<svg viewBox="0 0 900 520" preserveAspectRatio="none">'
            + "".join(p) + "</svg>"
            f'<div class="nr-rule-top"></div>'
            f'<div class="nr-rule-title"></div></div>')


def _motion(color: str) -> str:
    """سه خطِ حرکتِ پشت خودرو — همان سه خطِ ۲۰۵ تاییِ قالب.

    در قالب هرکدام یک تصویرِ ۲۰۵×۰٫۷ بود؛ اینجا خط برداری‌اند تا در
    هر مقیاسی تیز بمانند. فاصله‌شان (۱۰۸، ۱۲۲، ۱۳۶) و چرخشِ ۳ درجه و
    شفافیتِ ۵۵٪ از خودِ قالب است.
    """
    ls = "".join(
        f'<line x1="0" y1="{i * 14 + 1:g}" x2="205" y2="{i * 14 + 1:g}" '
        f'stroke="{color}" stroke-width="{1 if i == 2 else 0.7}"/>'
        for i in range(3))
    return ('<svg class="nr-motion" viewBox="0 0 205 34" '
            f'preserveAspectRatio="none" aria-hidden="true">{ls}</svg>')


def hero(f: Facts, *, kicker: str, title: str, subtitle: str = "",
         art: str = "", emblem: str = "") -> str:
    """سربرگِ تیره — کپیِ قالب نهایی، نه تفسیر آن.

    چیدمان و عددها از خودِ فیگما آمده‌اند: نوار با padding ‎۲۸/۴۴‎ و
    فاصلهٔ ۱۸، عنوان ۵۲ با ارتفاع سطر ۱۱۰٪ و سایهٔ دولایهٔ حک، قاب
    زیرعنوان با خط ۱٫۶، و بندِ آغاز که خطِ ۴۸×۲ در **انتهایش** می‌نشیند
    (در راست‌به‌چپ یعنی سمت چپ) — نه اولش.

    نشان و خودرو از ``report/assets/`` برداشته می‌شوند — همان
    پرونده‌هایی که از قالب صادر شده‌اند. اگر نباشند، نشان نمایش داده
    **نمی‌شود** (جعل نمی‌شود) و جای خودرو به نقش‌مایهٔ برداری برمی‌گردد.
    """
    from . import assets as _AS

    sub = f'<div class="sub">{_h.escape(subtitle)}</div>' if subtitle else ""
    # نشان و خودرو: **پروندهٔ واقعیِ قالب** اگر هست، وگرنه بازگشت امن.
    # نشان جعل نمی‌شود؛ نبودنش یعنی نمایش داده نمی‌شود.
    emblem = emblem or _AS.img("emblem")
    art = _AS.img("paykan") or art
    emb = f'<div class="nr-emblem">{emblem}</div>' if emblem else ""
    car = (f'<div class="nr-car">{art}{_motion(_AL.DUST)}</div>') if art else ""
    return (
        f'<div class="nr-hero-wrap"><div class="nr-hero">'
        f'{_grain(0.14)}{_deco()}{emb}{car}'
        f'<p class="kick">{_h.escape(kicker)}</p>'
        f'<div class="nr-focus"></div>'
        f'<div class="nr-flow">'
        f'<h2>{_h.escape(title)}</h2>{sub}'
        f'<div class="nr-lead"><div class="rule"></div>'
        f'<p>{_md(opening(f))}</p></div>'
        f"</div></div></div>")

def eyebrow(text: str, alt: bool = False) -> str:
    """قرصِ فصل — همان شکل قالب، نه یک برچسب ساده."""
    return (f'<div class="nr-pill{" alt" if alt else ""}">'
            f'{_h.escape(text)}</div>')


def open_block(f: Facts, lead: str = "") -> str:
    """بندِ آغاز روی زمینهٔ روشن — وقتی سربرگِ تیره جای دیگری است."""
    return (f'<div class="nr-hook">{eyebrow(lead) if lead else ""}'
            f'<p>{_md(opening(f))}</p></div>')


def chapter(title: str, line: str = "", lead: str = "") -> str:
    """قلاب: قرصِ فصل بالا، یک جملهٔ راهنما زیرش — هر دو وسط‌چین."""
    return (f'<div class="nr-hook">{eyebrow(lead or title)}'
            + (f"<p>{_md(line)}</p>" if line else "") + "</div>")


def knots(items: Sequence[Knot]) -> str:
    """گره‌ها: شماره، دو ستونِ پله‌ای، ستون فقرات، و پلِ حبابی بینشان."""
    out = []
    for i, k in enumerate(items):
        out.append(
            f'<div class="nr-knot">'
            f'<div class="no"><i>{fa(k.no)}</i><span>{_h.escape(k.name)}</span></div>'
            f'<div class="nr-row">'
            f'<div class="nr-col no-go">'
            f'<div class="nr-card no-go"><div class="h">{_h.escape(k.dont_title)}</div>'
            f'<div class="b">{_md(k.dont_body)}</div></div></div>'
            f'<div class="nr-gutter"></div>'
            f'<div class="nr-col">'
            f'<div class="nr-card"><div class="h">{_h.escape(k.do_title)}</div>'
            f'<div class="b">{_md(k.do_body)}</div></div></div>'
            f"</div></div>")
        if k.bridge:
            out.append(f'<div class="nr-link"><div class="ln"></div>'
                       f'<div class="bb">{_h.escape(k.bridge)} ↓</div>'
                       f'<div class="ln"></div></div>')
    return "".join(out)


def resolution_block(f: Facts) -> str:
    """نتیجه: خط ← برچسب ← خط، و زیرش کارت‌های عددی."""
    title, lines = resolution(f)
    cards = "".join(f'<div class="c">{_md(x)}</div>' for x in lines)
    return (f'<div class="nr-res"><div class="bar"><div class="ln"></div>'
            f'{eyebrow(title)}<div class="ln"></div></div>'
            f'<div class="cards">{cards}</div></div>')


def coda(text: str) -> str:
    """جملهٔ ماندگار، به شکلِ رابطِ «ادامه» — خواننده را جلو می‌برد."""
    return (f'<div class="nr-cont"><div class="v"></div>'
            f'<div class="p">{_h.escape(text)}</div></div>')


def badge(ref_date: str = "") -> str:
    tail = f" · {_h.escape(ref_date)}" if ref_date else ""
    return f'<span class="nr-badge">END OF REPORT{tail}</span>'


def footer(*, org: str, unit: str, tagline: str, ref_date: str = "",
           art: str = "") -> str:
    """پاصفحهٔ تیره — شعار و مُهر چپ، هویت سازمانی راست."""
    return (f'<div class="nr-foot">'
            f'<div class="tag">{_h.escape(tagline)}<br>{badge(ref_date)}</div>'
            f'<div class="org">{_h.escape(org)}<span>{_h.escape(unit)}</span></div>'
            f"{art}</div>")


def journey(chapters_: Iterable[Chapter]) -> str:
    """مسیر — فازِ برچسب‌دار، گام‌های شماره‌دار، اتصال عمودی بین فازها.

    سیزده رویداد پشت هم فهرست است؛ همان سیزده‌تا زیر فازهای برچسب‌دار،
    مسیر است — و مسیر در ذهن می‌ماند.
    """
    parts, n, chaps = ['<div class="nr-journey">'], 0, list(chapters_)
    for ci, c in enumerate(chaps):
        steps = []
        for si, s in enumerate(c.steps):
            n += 1
            if si:
                steps.append('<div class="nr-hop"></div>')
            steps.append(f'<div class="nr-step"><i>{fa(n)}</i>'
                         f"<span>{_h.escape(s)}</span></div>")
        parts.append(f'<div class="nr-phase">{eyebrow(c.title, alt=ci % 2 == 0)}'
                     f'<div class="nr-steps">{"".join(steps)}</div></div>')
        if ci < len(chaps) - 1:
            parts.append('<div class="nr-drop"></div>')
    parts.append("</div>")
    return "".join(parts)


def facets(items: Iterable[Chapter], numbered: bool = False) -> str:
    """کارت‌های **غیرترتیبی** — همان کارتِ «ستون مالکیت» در قالب.

    ``journey`` شماره می‌گذارد چون رویدادها ترتیب دارند. کلاسترهای
    عملکرد ترتیب ندارند؛ شماره‌گذاری‌شان یک ترتیبِ ساختگی می‌سازد که در
    داده وجود ندارد. ``numbered`` فقط جایی روشن می‌شود که شماره واقعاً
    معنا دارد — مثل شش ستونِ مالکیت.
    """
    out = []
    for i, c in enumerate(items, 1):
        num = f"<i>{fa(i)}</i>" if numbered else ""
        out.append(f'<div class="nr-c"><div class="k">'
                   f'<div class="t">{_h.escape(c.title)}</div>{num}</div>'
                   + (f'<div class="m">{_h.escape(c.line)}</div>' if c.line else "")
                   + "</div>")
    return f'<div class="nr-cards">{"".join(out)}</div>'

# ═══════════════════ روایت در ایمیل ═══════════════════
#: اتلوک کلاسیک با موتور Word نه flexbox می‌فهمد نه grid و نه کلاس CSS
#: خارجی. پس نسخهٔ ایمیلِ روایت با **جدول و سبکِ درون‌خطی** ساخته می‌شود
#: و ``bgcolor`` هم می‌گیرد تا اگر CSS نادیده گرفته شد، باز زمینه بماند.
def email_open(f: Facts, lead: str = "", font: str = "Tahoma") -> str:
    """بندِ آغاز، به شکلی که موتور Word هم درست نشانش بدهد."""
    kicker = ""
    if lead:
        kicker = (f'<div style="font-family:{font},sans-serif;font-size:10px;'
                  f'letter-spacing:1px;color:{_AL.TEAL_INK};padding-bottom:5px">'
                  f'{_h.escape(lead)}</div>')
    return (f'<table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" border="0" bgcolor="{_AL.BAND}" '
            f'style="border-right:3px solid {_AL.TEAL}">'
            f'<tr><td style="padding:14px 18px">{kicker}'
            f'<div style="font-family:{font},sans-serif;font-size:13px;'
            f'color:{_AL.INK_2};mso-line-height-rule:exactly;line-height:24px">'
            f'{_md(opening(f))}</div></td></tr></table>')


def email_resolution(f: Facts, font: str = "Tahoma") -> str:
    title, lines = resolution(f)
    items = "".join(
        f'<tr><td style="font-family:{font},sans-serif;font-size:12px;'
        f'color:{_AL.INK_2};mso-line-height-rule:exactly;line-height:22px;'
        # RLM پیش از گلوله: بدون آن، دوسویه‌سازی گلوله را به وسط جمله
        # می‌برد و کنار عدد شبیه رقم «۰» دیده می‌شود.
        f'padding:3px 0">\u200f• {_md(x)}</td></tr>' for x in lines)
    return (f'<table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" border="0" bgcolor="{_AL.BAND_ALT}" '
            f'style="border-right:3px solid {_AL.TEAL}">'
            f'<tr><td style="padding:14px 18px">'
            f'<div style="font-family:{font},sans-serif;font-size:14px;'
            f'font-weight:bold;color:{_AL.TEAL_INK};padding-bottom:6px">'
            f'{_h.escape(title)}</div>'
            f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'border="0">{items}</table></td></tr></table>')


def email_coda(text: str, font: str = "Tahoma") -> str:
    return (f'<div style="font-family:{font},sans-serif;font-size:12px;'
            f'font-weight:bold;color:{_AL.TEAL_INK};text-align:center;'
            f'padding:14px 0 2px">{_h.escape(text)}</div>')



# ═══════════════════ روایت در اکسل ═══════════════════
def excel_cover(ws, f: Facts, *, title: str, chapters_: Optional[Iterable[Chapter]] = None,
                numbered: bool = True, coda_text: str = "",
                lead: str = "") -> None:
    """شیتِ «روایت» را روی یک worksheet باز می‌نویسد.

    اکسل هم اولین چیزی که باز می‌شود باید بگوید **این فایل دربارهٔ چیست**.
    بدون این، کاربر با یک جدول خام روبه‌رو می‌شود و خودش باید داستان را
    بسازد — و هر کس داستان متفاوتی می‌سازد.

    وابستگی به openpyxl اینجا داخل تابع وارد می‌شود تا ماژول روایت روی
    محیطی که فقط HTML می‌سازد هم بالا بیاید.
    """
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    def rgb(h):
        return h.replace("#", "").upper()

    ink = Font(name=_AL.FONT_XLSX, size=11, color=rgb(_AL.INK))
    ink2 = Font(name=_AL.FONT_XLSX, size=10, color=rgb(_AL.INK_2))
    head = Font(name=_AL.FONT_XLSX, size=16, bold=True, color=rgb(_AL.ON_TEAL))
    lead_f = Font(name=_AL.FONT_XLSX, size=9, color=rgb(_AL.TEAL_INK))
    sec = Font(name=_AL.FONT_XLSX, size=12, bold=True, color=rgb(_AL.TEAL_INK))
    band = PatternFill("solid", fgColor=rgb(_AL.BAND))
    band2 = PatternFill("solid", fgColor=rgb(_AL.BAND_ALT))
    deep = PatternFill("solid", fgColor=rgb(_AL.TEAL_DEEP))
    edge = Side(style="thin", color=rgb(_AL.RULE))
    wrap = Alignment(horizontal="right", vertical="top", wrap_text=True,
                     readingOrder=2)
    mid = Alignment(horizontal="right", vertical="center", readingOrder=2)

    ws.sheet_view.rightToLeft = True
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 108
    r = 1

    ws.merge_cells(f"A{r}:B{r}")
    ws[f"A{r}"] = title
    ws[f"A{r}"].font = head
    ws[f"A{r}"].fill = deep
    ws[f"A{r}"].alignment = mid
    ws.row_dimensions[r].height = 34
    r += 2

    if lead:
        ws[f"B{r}"] = lead
        ws[f"B{r}"].font = lead_f
        ws[f"B{r}"].alignment = mid
        r += 1
    ws[f"B{r}"] = plain_opening(f)
    ws[f"B{r}"].font = ink
    ws[f"B{r}"].fill = band
    ws[f"B{r}"].alignment = wrap
    ws.row_dimensions[r].height = 62
    r += 2

    if chapters_:
        n = 0
        for c in chapters_:
            ws[f"B{r}"] = c.title
            ws[f"B{r}"].font = sec
            ws[f"B{r}"].alignment = mid
            r += 1
            if c.line:
                ws[f"B{r}"] = c.line
                ws[f"B{r}"].font = ink2
                ws[f"B{r}"].alignment = mid
                r += 1
            for s in c.steps:
                n += 1
                ws[f"A{r}"] = fa(n) if numbered else "•"
                ws[f"A{r}"].font = ink2
                ws[f"A{r}"].alignment = mid
                ws[f"B{r}"] = s
                ws[f"B{r}"].font = ink
                ws[f"B{r}"].alignment = mid
                ws[f"B{r}"].border = Border(bottom=edge)
                r += 1
            r += 1

    res_title, lines = resolution(f)
    ws[f"B{r}"] = res_title
    ws[f"B{r}"].font = sec
    ws[f"B{r}"].alignment = mid
    ws[f"B{r}"].fill = band2
    r += 1
    for line in lines:
        ws[f"B{r}"] = line.replace("**", "")
        ws[f"B{r}"].font = ink
        ws[f"B{r}"].alignment = wrap
        ws[f"B{r}"].fill = band2
        ws.row_dimensions[r].height = 30
        r += 1
    r += 1

    if coda_text:
        ws[f"B{r}"] = coda_text
        ws[f"B{r}"].font = sec
        ws[f"B{r}"].alignment = Alignment(horizontal="center", readingOrder=2)


def plain_opening(f: Facts) -> str:
    """همان بندِ آغاز، بدون HTML — برای اکسل و متنِ ساده."""
    return opening(f).replace("**", "")


# ═══════════════════ محتوای این پکیج — عملکرد منابع انسانی ═══════════════
LEAD_OPENING = "داستان یک کارنامه"
LEAD_PATH = "مسیرِ یک امتیاز — از رویداد تا رتبه"
LEAD_TURN = "نقطهٔ عطف داستان"

CODA = "امتیاز، قضاوت نیست؛ نقشهٔ کار است."

#: سه گره. هر گره یک سوءبرداشتِ رایج دربارهٔ همین گزارش است — و هر دو
#: طرفش از رفتار خودِ موتور می‌آید، نه از توصیهٔ مدیریتی.
KNOTS: Tuple[Knot, ...] = (
    Knot(1, "گرهٔ مقایسه — بار کاری",
         "✓ امتیاز را کنار بارِ کاری بخوان",
         "«بار و پیچیدگی» یک کلاسترِ **کنترل** است، نه یک نمره. دو نفر با "
         "امتیاز برابر و بارِ نابرابر، دو کارنامهٔ متفاوت دارند. موتور بار "
         "را می‌سنجد تا مقایسه منصفانه شود، نه تا کسی امتیاز اضافه بگیرد.",
         "✕ دو نفر را فقط از روی عدد کل مقایسه نکن",
         "عدد کل، میانگینِ وزن‌دارِ هشت کلاستر است. دو نفر می‌توانند به یک "
         "عدد برسند و در **هیچ** کلاستری شبیه هم نباشند. مقایسهٔ بی‌تفکیک، "
         "دقیقاً همان چیزی را پنهان می‌کند که باید دیده شود.",
         "حالا به جنسِ خطا نگاه کن"),
    Knot(2, "گرهٔ داده — کیفیت ثبت",
         "✓ پیش از داوری، «کیفیت داده» را ببین",
         "کلاسترِ «کیفیت داده و ردیابی‌پذیری» می‌گوید چقدر از پروندهٔ این "
         "نفر اصلاً **قابل سنجش** بوده. امتیازِ پایین روی دادهٔ ناقص، حرفی "
         "دربارهٔ عملکرد نمی‌زند؛ حرفی دربارهٔ ثبت می‌زند.",
         "✕ نبودِ داده را «عملکرد ضعیف» نخوان",
         "خانهٔ خالی و عددِ بد یک چیز نیستند. موتور این دو را جدا نگه "
         "می‌دارد و گزارش هم باید همین کار را بکند؛ وگرنه کسی که سامانه "
         "برایش داده نساخته، بابت سکوتِ سامانه جریمه می‌شود.",
         "حالا بازه را ببین، نه نقطه را"),
    Knot(3, "گرهٔ زمان — یک دوره یک عکس نیست",
         "✓ روند را در چند دوره بخوان",
         "یک دوره، یک نمونه است. کارنامه وقتی معنا دارد که جهتش معلوم "
         "باشد: رو به بهبود یا رو به افت. همین گزارش را کنار دورهٔ قبل "
         "بگذارید، نه به‌تنهایی.",
         "✕ رتبه را به‌جای فاصله نخوان",
         "رتبهٔ ۵ و ۶ می‌توانند صدم‌درصد فاصله داشته باشند یا ده واحد. "
         "ترتیب، اندازهٔ تفاوت را نشان نمی‌دهد — و تصمیمی که روی ترتیب "
         "بنشیند، روی نویز نشسته است."),
)

#: معنیِ یک‌خطیِ کلاسترها وقتی برچسبِ مدل به‌تنهایی گویا نیست.
MEANINGS: Dict[str, str] = {
    "reliability": "آنچه خط تولید واقعاً می‌بیند",
    "conformance": "انحراف از مسیر مرجع، از روی لاگ رویداد",
    "responsiveness": "پرونده چند روز منتظر این نفر ماند",
    "stewardship": "تعهد و سندی که نباید معوق بماند",
    "data_quality": "چقدر از این پرونده اصلاً قابل سنجش بود",
    "collaboration": "تحویلِ تمیز به حوزهٔ بعد",
    "workload": "زمینهٔ مقایسه — نه نمره",
    "exposure": "پولی که در معرض خطر است",
}


def chapters() -> List[Chapter]:
    """فصل‌ها = کلاسترهای همین مدل، به ترتیبِ وزن.

    از ``config/model.yaml`` خوانده می‌شوند نه کپی؛ اگر کسی کلاستر اضافه
    یا وزنی را عوض کند، روایت هم همان را می‌گوید.
    """
    try:
        from ..config.model import load_model
        model = load_model()
        items = sorted(model.clusters.values(),
                       key=lambda c: -getattr(c, "weight", 0))
    except Exception:
        return [Chapter(k, v, "", ()) for k, v in MEANINGS.items()]
    return [Chapter(c.key, c.label, MEANINGS.get(c.key, ""), ()) for c in items]
