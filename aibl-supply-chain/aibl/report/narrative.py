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

VERSION = "1.2"

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
    g = _AL.header_gradient_css("135deg")
    grain = _grain_uri()
    return f"""
/* ── روایت — قالب نهایی ─────────────────────────────────────────────
   ترتیب همیشه یکی است: سربرگِ تیره → قلاب → گره‌ها → نتیجه →
   مسیر → پاصفحهٔ مُهردار. */

/* سربرگِ تیره — عددها از قالب نهاییِ فیگما */
.nr-hero{{position:relative;overflow:hidden;
  background:{g};color:{_AL.ON_TEAL};padding:28px 44px;
  box-shadow:inset 0 9px 18px {_AL.rgba(_AL.EMBOSS_DARK, .34)},
             inset 0 -4px 12px {_AL.rgba(_AL.EMBOSS_LIGHT, .12)},
             0 10px 22px {_AL.rgba(_AL.SHADOW_CAST, .16)}}}
.nr-grain{{position:absolute;inset:0;pointer-events:none;
  mix-blend-mode:overlay;background-repeat:repeat}}
.nr-wash{{position:absolute;left:-10%;bottom:-30%;width:70%;height:90%;
  pointer-events:none;
  background:radial-gradient(ellipse at center,
    {_AL.rgba(_AL.EMBOSS_LIGHT, .10)} 0%, transparent 68%)}}
.nr-emblem{{position:absolute;top:26px;left:44px;width:150px;height:140px;
  opacity:.9;pointer-events:none}}
.nr-emblem img,.nr-emblem svg{{width:100%;height:auto;display:block}}
.nr-hero-in{{position:relative;display:flex;flex-direction:column;
  align-items:flex-end;gap:18px}}
.nr-titles{{display:flex;flex-direction:column;align-items:flex-end;gap:10px;
  width:100%}}
.nr-hero .kick{{font-size:14px;font-weight:500;letter-spacing:1.6px;
  color:{_AL.ON_TEAL_2}}}
.nr-hero h2{{margin:0;font-size:52px;font-weight:900;line-height:1.1;
  text-align:right;color:{_AL.TITLE_ENGRAVED};
  text-shadow:2px 3px 2.5px {_AL.rgba(_AL.ENGRAVE_DARK, .68)},
  -1px -1px 1px {_AL.rgba(_AL.ENGRAVE_LIGHT, .12)}}}
.nr-hero .sub{{padding:8px 18px;border:1.6px solid {_AL.ON_TEAL_2};
  font-size:18px;color:{_AL.ON_TEAL}}}
/* ترکیب بصری: در قالب، «انفجار داده» و خودرو **کنار هم**اند نه زیر هم؛
   یک ردیف به ارتفاع ۲۲۰ که بُرست از چپ و خودرو از راست می‌نشیند. */
.nr-visual{{position:relative;width:100%;min-height:220px}}
.nr-burst{{position:absolute;left:6px;top:42px;width:300px;max-width:38%;
  height:auto;pointer-events:none}}
/* راست‌به‌چپ: برای چسباندن خودرو به لبهٔ **راست**، حاشیهٔ خودکار
   باید سمت چپ باشد — یعنی margin-inline-end. */
.nr-car{{position:relative;width:500px;max-width:60%;
  margin-inline-end:auto}}
.nr-car svg.nr-motion{{position:absolute;left:-46px;top:52%;width:300px;
  max-width:78%;height:auto;pointer-events:none;transform:translateY(-50%)}}
.nr-car>div,.nr-car>svg:not(.nr-motion){{position:relative}}
.nr-lead{{display:flex;align-items:center;justify-content:flex-start;gap:12px;
  padding-top:20px;width:100%}}
.nr-lead .rule{{flex:0 0 48px;height:2px;background:{_AL.ON_TEAL_2}}}
.nr-lead p{{margin:0;max-width:560px;font-size:14px;line-height:1.8;
  text-align:right;color:{_AL.ON_TEAL_2}}}
.nr-lead b{{color:{_AL.ON_TEAL}}}

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
  box-shadow:inset 0 9px 18px {_AL.rgba(_AL.EMBOSS_DARK, .34)},
             inset 0 -4px 12px {_AL.rgba(_AL.EMBOSS_LIGHT, .12)},
             0 10px 22px {_AL.rgba(_AL.SHADOW_CAST, .16)}}}
header::after{{content:"";position:absolute;inset:0;pointer-events:none;
  background-image:url({grain});background-repeat:repeat;
  mix-blend-mode:overlay;opacity:.13}}
header>*{{position:relative;z-index:1}}
header h1{{color:{_AL.TITLE_ENGRAVED};
  text-shadow:2px 3px 2.5px {_AL.rgba(_AL.ENGRAVE_DARK, .68)},
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
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160">'
           '<filter id="g"><feTurbulence type="fractalNoise" baseFrequency="0.82"'
           ' numOctaves="3" stitchTiles="stitch"/>'
           '<feColorMatrix type="saturate" values="0"/></filter>'
           '<rect width="160" height="160" filter="url(#g)"/></svg>')
    import base64 as _b
    return "data:image/svg+xml;base64," + _b.b64encode(svg.encode()).decode()


def _grain(opacity: float = 0.13) -> str:
    return (f'<div class="nr-grain" style="background-image:url({_grain_uri()});'
            f'opacity:{opacity}"></div>')


#: «انفجار داده» — هفت پرتو با طول‌های دقیقِ قالب، نقطه‌هایشان، هستهٔ
#: مرکزی و چهار میلهٔ KPI. عددها از خودِ فیگما خوانده شده‌اند.
_RAYS = ((98, -26), (132, -14), (165, -3), (205, 6), (185, 16), (150, 27),
         (118, 38))
_KPI = (14, 24, 36, 28)


def _databurst(color: str, glow: str) -> str:
    parts = ['<svg class="nr-burst" viewBox="0 0 300 150" width="300" '
             'height="150" aria-hidden="true">']
    cx, cy = 268, 74
    for i, (ln, dy) in enumerate(_RAYS):
        y = cy + dy
        parts.append(f'<rect x="{cx - ln}" y="{y}" width="{ln}" '
                     f'height="{2 if i == 3 else 1}" fill="{color}" '
                     f'opacity="{0.55 if i == 3 else 0.34}"/>')
        for k, frac in enumerate((0.22, 0.55, 0.82)):
            if i % 2 and k == 2:
                continue
            r = 3.5 if (i == 3 and k == 2) else 2
            parts.append(f'<circle cx="{cx - ln * frac:.0f}" cy="{y + 0.5:.0f}" '
                         f'r="{r}" fill="{glow}" opacity="0.8"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="7" fill="{glow}" opacity="0.9"/>')
    for i, h in enumerate(_KPI):
        parts.append(f'<rect x="{18 + i * 11}" y="{132 - h}" width="6" '
                     f'height="{h}" fill="{color}" opacity="0.5"/>')
    parts.append("</svg>")
    return "".join(parts)


def _motion(color: str) -> str:
    """پنج خط حرکت پشت خودرو — همان پنج ``LINE`` قالب."""
    ls = "".join(
        f'<line x1="0" y1="{18 + i * 15}" x2="300" y2="{12 + i * 15}" '
        f'stroke="{color}" stroke-width="1" opacity="{0.30 - i * 0.04:.2f}" '
        f'stroke-dasharray="{"2 7" if i % 2 else "18 12"}"/>' for i in range(5))
    return ('<svg class="nr-motion" viewBox="0 0 300 90" width="300" height="90" '
            f'aria-hidden="true">{ls}</svg>')


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
    return (
        f'<div class="nr-hero">{_grain()}<div class="nr-wash"></div>{emb}'
        f'<div class="nr-hero-in">'
        f'<div class="nr-titles"><div class="kick">{_h.escape(kicker)}</div>'
        f'<h2>{_h.escape(title)}</h2>{sub}</div>'
        f'<div class="nr-visual">{_databurst(_AL.ON_TEAL_2, _AL.ICE)}'
        f'<div class="nr-car">{_motion(_AL.ON_TEAL_2)}{art}</div></div>'
        f'<div class="nr-lead"><p>{_md(opening(f))}</p><div class="rule"></div>'
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


# ═══════════════════ محتوای این پکیج — زنجیرهٔ تأمین ═══════════════════
#: ابروها — نامِ فصل‌ها، از قالب نهایی فیگما
LEAD_OPENING = "داستان یک سفارش"
LEAD_PATH = "مسیرِ یک پرونده — از ثبت تا تحویل"
LEAD_TURN = "نقطهٔ عطف داستان"

#: جملهٔ پایانی. یک جمله، نه یک بند.
CODA = "مالکیت داده، مالکیت پرونده است."

#: سه گره. هر گره یک انتخاب واقعی است که کارشناس خرید هر روز دارد،
#: و هر دو طرفش از رفتار سامانه می‌آید نه از توصیهٔ اخلاقی.
KNOTS: Tuple[Knot, ...] = (
    Knot(1, "گرهٔ زمان — تاریخ‌گذاری",
         "✓ شمارهٔ درخواست خرید را همان روز بزن",
         "«ثبت درخواست خرید» یکی از دو مرحله‌ای است که **هیچ سورسی آن را "
         "نمی‌بیند**. تنها ردِ آن، ستونی است که شما پر می‌کنید. تا آن خانه "
         "خالی است، طول عمر پرونده از روز اول شمرده نمی‌شود.",
         "✕ تاریخ را از حافظه ننویس",
         "تاریخ، طولِ مرحله را می‌سازد و طولِ مرحله، رتبهٔ بحرانی را. یک "
         "تاریخِ حدسی فقط یک خانه را خراب نمی‌کند؛ رتبهٔ همهٔ قطعاتِ آن "
         "تأمین‌کننده را جابه‌جا می‌کند.",
         "حالا ردِ بار را دنبال کن"),
    Knot(2, "گرهٔ داده — ثبتِ دقیق",
         "✓ شمارهٔ بارنامه را در سورس خرید بنویس",
         "این تنها بندی است که سفارش را به محموله گره می‌زند. بدون آن، خرید "
         "و حمل دو پروندهٔ بی‌ربط می‌مانند و هیچ‌کس نمی‌فهمد این بار، بارِ "
         "کدام سفارش است.",
         "✕ خانهٔ خالی را با صفر یا خط تیره پر نکن",
         "سامانه بین «نمی‌دانم» و «صفر» فرق می‌گذارد: اولی نقطهٔ کور است و "
         "علامت می‌خورد، دومی یک **عددِ واقعی**. خط تیره، نقطهٔ کور را پنهان "
         "می‌کند — همان چیزی که باید دیده شود.",
         "حالا به داشبورد نگاه کن"),
    Knot(3, "گرهٔ هویت — کد تأمین‌کننده",
         "✓ کد تأمین‌کننده را انتخاب کن، تایپ نکن",
         "یک کد تایپ‌شده با یک فاصلهٔ اضافه، یک تأمین‌کنندهٔ تازه می‌سازد. "
         "آن‌وقت کارنامهٔ یک شرکت بین دو نام تکه‌تکه می‌شود و هیچ‌کدام "
         "واقعیت را نشان نمی‌دهد.",
         "✕ منتظر گزارش ماهانه نمان",
         "گزارش ماه، عکسِ گذشته است. آنچه امروز پر می‌کنید، همین امروز در "
         "داشبورد دیده می‌شود. تصمیمی که یک ماه دیر بگیرید، دیگر تصمیم "
         "نیست؛ گزارشِ خسارت است."),
)

#: معنیِ یک‌خطیِ هر ستونِ مالکیتی — کنار نام، نه به‌جایش.
MEANINGS: Dict[str, str] = {
    "MOGH_KEY_PR": "ردپای شروع سفارش در سیستم",
    "MOGH_PO_SENT_DATE": "لحظه‌ای که تعهد آغاز می‌شود",
    "MOGH_VENDOR_CODE": "هویت طرف مقابل در زنجیرهٔ تأمین",
    "MOGH_PI_VALUE_SUM": "رقم واقعی که تکلیف مالی را روشن می‌کند",
    "MOGH_BL_NO": "سند فیزیکی جابجایی کالا",
    "MOGH_CLEARED_QTY_SUM": "آنچه واقعاً از گمرک رد شده است",
}

#: پنج فصلِ مسیر. سیزده رویداد پشت هم فهرست است؛ همان سیزده‌تا زیر این
#: پنج فصل، مسیر است. کلیدها ستون‌های ``s80_eventlog.ACTIVITIES``اند، پس
#: اگر رویدادی اضافه شود، تست نبودنش را در همین نگاشت می‌گیرد.
JOURNEY: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("start", "آغاز سفارش", ("PO_SENT_DATE", "NTSW_COMMIT_DATE")),
    ("finance", "تأمین مالی", ("NTSW_ALLOC_DATE", "BUY_DATE")),
    ("transit", "حمل و ورود کالا", ("BL_DATE", "ARRIVAL_DATE", "DISCHARGE_DATE")),
    ("customs", "اسناد و گمرک", ("DOC_SUBMIT_DATE", "COT_DATE", "SATA_DATE")),
    ("release", "ترخیص و بسته‌شدن پرونده",
     ("PARTIAL_CLEAR_DATE", "FULL_CLEAR_DATE", "FIN_RECEIPT_DATE")),
)


def chapters() -> List[Chapter]:
    """فصل‌های مسیر، با نام فارسیِ رویدادها از خودِ لاگ رویداد.

    نام‌ها اینجا کپی نمی‌شوند؛ از ``ACTIVITIES`` خوانده می‌شوند تا اگر
    آنجا عوض شد، روایت هم عوض شود و دو حقیقت نداشته باشیم.
    """
    from ..stages.s80_eventlog import ACTIVITIES
    fa_of = {col: fa_name for col, _en, fa_name, _o, _s in ACTIVITIES}
    out = []
    for key, title, cols in JOURNEY:
        steps = tuple(fa_of[c] for c in cols if c in fa_of)
        out.append(Chapter(key, title, "", steps))
    return out
