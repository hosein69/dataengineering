# -*- coding: utf-8 -*-
"""گزارش روایتِ دادهٔ ماهانه — «این ماه چه چیزی عوض شد، و چه باید کرد».

## چرا یک گزارش تازه

گزارش‌های موجود **وضعیت** را می‌گویند: امروز چند پروندهٔ بحرانی داریم.
ولی کسی که ماهی یک بار نگاه می‌کند، وضعیت را نمی‌خواهد؛ **تغییر** را
می‌خواهد. «۳۷ بحرانی» بی‌معناست تا وقتی ندانیم ماه پیش ۴۶ بوده.

این ماژول همان دستور زبان روایت را روی محورِ زمان می‌گذارد: باز شدن با
عدد، گره‌ها، مسیر، و جمع‌بندی — ولی هر جمله‌اش از **اختلافِ** دو ماه
می‌آید، نه از یک عکسِ لحظه‌ای.

## سه قاعدهٔ صداقت

۱. **بدون ماهِ پیش، دلتا نداریم.** اگر مبنا نباشد، همین را می‌گوییم و
   عدد نمی‌سازیم. «۱۰۰٪ رشد» روی مبنای خالی، دروغ است.
۲. **درصد فقط روی مبنای معنادار.** زیر ``PCT_FLOOR`` تا، فقط عددِ مطلق
   می‌آید. «۲۰۰٪ بیشتر» وقتی ۱ به ۳ رسیده، خواننده را گمراه می‌کند.
۳. **جهتِ خوب را داده تعیین نمی‌کند، ما اعلام می‌کنیم.** هر سنجه
   می‌گوید کاهشش خوب است یا افزایشش؛ وگرنه رنگِ سبز و قرمز تصادفی
   می‌شود.

## نمودارها

بدون کتابخانه، SVG درون‌خطی — چون گزارش باید آفلاین و داخل ایمیل و در
چاپ هم درست باشد. دو شکل، هر کدام برای یک کار:

* ``spark()`` — یک سری در طول زمان. خطِ نازک با نقطهٔ آخر برجسته.
* ``movement()`` — مقایسهٔ **دو نقطه** برای چند سنجه (دمبلی). محورِ
  دوم نمی‌سازیم؛ هر سنجه روی مقیاسِ خودش نرمال می‌شود و عددش کنارش
  نوشته می‌شود.

رنگ از البرز می‌آید و متن توکنِ متن می‌پوشد، نه رنگِ سری — طبق همان
قاعده‌ای که در نظام طراحی نوشته شده.
"""
from __future__ import annotations

import html as _h
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from . import alborz as _AL
from . import narrative as _NR

#: زیر این مبنا، درصد گزارش نمی‌شود — فقط عددِ مطلق.
PCT_FLOOR = 20


@dataclass(frozen=True)
class Movement:
    """یک سنجه، بین دو ماه.

    ``good`` می‌گوید کدام جهت خوب است: ``"down"``، ``"up"`` یا
    ``"flat"`` (خنثی — نه سبز می‌شود نه قرمز).
    """
    label: str
    now: Optional[float]
    before: Optional[float] = None
    unit: str = ""
    good: str = "down"
    note: str = ""

    @property
    def has_base(self) -> bool:
        return self.before is not None and self.now is not None

    @property
    def delta(self) -> Optional[float]:
        return (self.now - self.before) if self.has_base else None

    @property
    def pct(self) -> Optional[float]:
        if not self.has_base or abs(self.before) < PCT_FLOOR:
            return None
        return (self.now - self.before) / abs(self.before) * 100.0

    @property
    def verdict(self) -> str:
        """``better`` / ``worse`` / ``same`` / ``unknown``."""
        d = self.delta
        if d is None:
            return "unknown"
        if abs(d) < 1e-9 or self.good == "flat":
            return "same"
        improved = (d < 0) if self.good == "down" else (d > 0)
        return "better" if improved else "worse"


@dataclass
class Month:
    """یک ماه: برچسبش، حقایقش، و سنجه‌هایی که حرکت کرده‌اند."""
    label: str
    facts: _NR.Facts
    movements: List[Movement] = field(default_factory=list)
    series: Sequence[Tuple[str, Sequence[float]]] = ()
    previous: str = ""


_TONE = {"better": ("good", "بهتر شد"),
         "worse": ("critical", "بدتر شد"),
         "same": ("neutral", "تغییری نکرد"),
         "unknown": ("unknown", "مبنای مقایسه ندارد")}


#: یکاهایی که بی‌فاصله می‌چسبند («۲۵٪»، نه «۲۵ ٪»)
_TIGHT = ("٪", "%")
#: یکاهایی که مقیاس‌اند نه شمارش — در «تغییر» تکرارشان بی‌معناست
#: («۴ از ۱۰۰ بیشتر» غلط است؛ «۴ بیشتر» درست).
_SCALE = ("از ",)


def _num(v: Optional[float], unit: str = "") -> str:
    if v is None:
        return "—"
    s = _NR.fa(int(round(v))) if abs(v - round(v)) < 1e-9 else _NR.fa(round(v, 1))
    if unit in _TIGHT:
        return f"{s}{unit}"
    return f"{s} {unit}".strip()


def sentence(m: Movement) -> str:
    """یک جملهٔ فارسیِ درست دربارهٔ این حرکت — بدون عددِ ساختگی."""
    if not m.has_base:
        return (f"<b>{_h.escape(m.label)}</b> الان {_num(m.now, m.unit)} است. "
                "ماه پیش مبنایی ثبت نشده، پس مقایسه‌ای نمی‌کنیم.")
    d = m.delta
    if abs(d) < 1e-9:
        return (f"<b>{_h.escape(m.label)}</b> روی {_num(m.now, m.unit)} ماند — "
                "دقیقاً همان ماه پیش.")
    word = "کمتر" if d < 0 else "بیشتر"
    # درصدِ نسبی را وقتی خودِ یکا درصد است نمی‌آوریم: «از ۷۷٪ به ۷۴٪،
    # ۳٪ کمتر» خواننده را گیج می‌کند — آن ۳٪ نسبتِ نسبت است.
    pct = None if m.unit in _TIGHT else m.pct
    tail = f" ({_NR.fa(abs(round(pct)))}٪)" if pct is not None else ""
    # یکای مقیاسی («از ۱۰۰») یک بار در کارت می‌آید، نه سه بار در جمله.
    scale = any(m.unit.startswith(p) for p in _SCALE)
    u = "" if scale else m.unit
    return (f"<b>{_h.escape(m.label)}</b> از {_num(m.before, u)} به "
            f"{_num(m.now, u)} رسید — {_num(abs(d), u)} {word}{tail}.")


# ─────────────────────────── نمودارها ───────────────────────────

def spark(values: Sequence[float], *, width: int = 168, height: int = 40,
          label: str = "") -> str:
    """خطِ روندِ یک سری. زیر دو نقطه، نموداری کشیده نمی‌شود."""
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return ('<span style="font-size:12px;color:%s">روند، مبنای کافی '
                'ندارد</span>' % _AL.INK_3)
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pad = 4
    step = (width - 2 * pad) / (len(vals) - 1)
    pts = [(pad + i * step, height - pad - (v - lo) / span * (height - 2 * pad))
           for i, v in enumerate(vals)]
    d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
                 for i, (x, y) in enumerate(pts))
    lx, ly = pts[-1]
    title = _h.escape(label or "روند")
    return (f'<svg class="nr-spark" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" role="img" '
            f'aria-label="{title}"><title>{title}</title>'
            f'<path d="{d}" fill="none" stroke="{_AL.TEAL}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="{_AL.TEAL}" '
            f'stroke="{_AL.CARD}" stroke-width="2"/></svg>')


#: پهنای ستونِ برچسب در نمودار دمبلی (راستِ تصویر، چون متن فارسی است)
LABEL_W = 150


def movement(items: Sequence[Movement], *, width: int = 560) -> str:
    """نمودار دمبلی: «از کجا به کجا» برای چند سنجه.

    هر سطر روی مقیاسِ **خودش** نرمال می‌شود و عددهایش کنارش نوشته
    می‌شود، پس هیچ محورِ دومی لازم نیست — همان چیزی که هرگز نباید ساخت.

    هر ریل برچسبِ مستقیم دارد. نسخهٔ اولِ این نمودار فقط نقطه‌ها را
    می‌کشید و خواننده نمی‌فهمید کدام ریل کدام سنجه است — رنگ به‌تنهایی
    هیچ سنجه‌ای را نام نمی‌برد.

    عددها **روی نمودار نمی‌آیند**: هر سنجه کارت و سطرِ جدولِ خودش را
    دارد و عددش آنجاست. گذاشتنِ عدد روی هر نقطه، هم شلوغ می‌کند هم با
    نقطهٔ کناری برخورد می‌کند. هاور (``<title>``) هر دو عدد و تغییر را
    می‌گوید.
    """
    rows = [m for m in items if m.has_base]
    if not rows:
        return ""
    h = 30
    height = len(rows) * h + 6
    out = [f'<svg class="nr-move" viewBox="0 0 {width} {height}" '
           f'width="100%" height="{height}" role="img" '
           f'aria-label="حرکتِ سنجه‌ها میان دو ماه">']
    x0, x1 = 12, width - LABEL_W   # ریل: کم سمت چپ، زیاد سمت راست
    for i, m in enumerate(rows):
        y = i * h + h / 2 + 3
        lo, hi = min(m.before, m.now), max(m.before, m.now)
        span = (hi - lo) or 1.0
        # محور **مقدار** را نشان می‌دهد، نه زمان را: کم چپ، زیاد راست.
        # نسخهٔ اول زمان را روی محور گذاشته بود و نتیجه‌اش این بود که
        # عددِ کوچک‌تر سمت راست می‌افتاد — یعنی نمودار خلافِ خودش را
        # می‌گفت.
        bx = x0 + (m.before - lo) / span * (x1 - x0)
        nx = x0 + (m.now - lo) / span * (x1 - x0)
        col = _AL.STATUS[_TONE[m.verdict][0]]
        out.append(
            f"<g><title>{_h.escape(m.label)}: "
            f"{_num(m.before, m.unit)} ← {_num(m.now, m.unit)} "
            f"({change(m)})</title>"
            f'<text x="{width - 8}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="12" fill="{_AL.INK_2}">{_h.escape(m.label)}</text>'
            f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
            f'stroke="{_AL.HAIRLINE}" stroke-width="1"/>'
            f'<line x1="{min(bx, nx):.1f}" y1="{y:.1f}" '
            f'x2="{max(bx, nx):.1f}" y2="{y:.1f}" '
            f'stroke="{_AL.RULE}" stroke-width="2.5" stroke-linecap="round"/>'
            f'<circle cx="{bx:.1f}" cy="{y:.1f}" r="4.5" fill="{_AL.CARD}" '
            f'stroke="{_AL.SPINE}" stroke-width="2"/>'
            f'<circle cx="{nx:.1f}" cy="{y:.1f}" r="5.5" fill="{col}" '
            f'stroke="{_AL.CARD}" stroke-width="2"/></g>')
    out.append("</svg>")
    return "".join(out)


def change(m: Movement) -> str:
    """تغییر را با **واژه** بنویس، نه با علامت.

    «۹-» در متنِ راست‌به‌چپ، منفی را آن‌سوی عدد می‌اندازد و خواننده
    «۹ منهای چیزی» می‌خواند. «۹ کمتر» هم بی‌ابهام است هم فارسی.
    """
    d = m.delta
    if d is None:
        return "—"
    if abs(d) < 1e-9:
        return "بدون تغییر"
    unit = "" if any(m.unit.startswith(p) for p in _SCALE) else m.unit
    return f"{_num(abs(d), unit)} {'کمتر' if d < 0 else 'بیشتر'}"

def legend() -> str:
    """راهنما — تعهدی که پالت روی خودش گذاشته: رنگ تنها حاملِ معنا نیست."""
    parts = ['<div class="nr-legend">']
    parts.append(f'<span><i style="background:{_AL.CARD};'
                 f'border:2px solid {_AL.SPINE}"></i>ماه پیش</span>')
    for key, (tone, word) in _TONE.items():
        if key == "unknown":
            continue
        parts.append(f'<span><i style="background:{_AL.STATUS[tone]}"></i>'
                     f'{word}</span>')
    parts.append("</div>")
    return "".join(parts)


CSS = f"""
/* ── گزارش ماهانه ───────────────────────────────────────────────── */
.nr-mo{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
  gap:14px;margin:18px 0}}
.nr-mo .m{{background:{_AL.PILL};border:1.4px solid {_AL.HAIRLINE};
  border-inline-start:4px solid {_AL.SPINE};padding:12px 14px}}
.nr-mo .m.better{{border-inline-start-color:{_AL.STATUS['good']}}}
.nr-mo .m.worse{{border-inline-start-color:{_AL.STATUS['critical']}}}
.nr-mo .m .k{{font-size:12px;color:{_AL.INK_3}}}
.nr-mo .m .v{{font-size:26px;font-weight:900;color:{_AL.INK};line-height:1.2;
  margin-top:2px}}
.nr-mo .m .s{{font-size:13px;line-height:1.9;color:{_AL.INK_2};margin-top:6px}}
.nr-mo .m .s b{{color:{_AL.INK}}}
.nr-mo .m .sp{{margin-top:8px}}
.nr-legend{{display:flex;flex-wrap:wrap;gap:14px;justify-content:center;
  margin:6px 0 16px;font-size:12px;color:{_AL.INK_2}}}
.nr-legend i{{display:inline-block;width:10px;height:10px;border-radius:50%;
  margin-inline-end:6px;vertical-align:-1px}}
.nr-move{{display:block;margin:4px 0 2px}}
.nr-spark{{display:block}}
.nr-mo-tbl{{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}}
.nr-mo-tbl th,.nr-mo-tbl td{{padding:7px 10px;text-align:right;
  border-bottom:1px solid {_AL.HAIRLINE};color:{_AL.INK_2}}}
.nr-mo-tbl th{{color:{_AL.INK};font-weight:700;
  background:{_AL.BAND}}}
.nr-mo-tbl td b{{color:{_AL.INK}}}
@media print{{.nr-mo{{grid-template-columns:1fr 1fr}}}}
"""


def cards(items: Sequence[Movement]) -> str:
    """یک کارت برای هر سنجه: عدد، جمله، و روندش اگر داشته باشد."""
    out = ['<div class="nr-mo">']
    for i, m in enumerate(items):
        v = m.verdict
        out.append(
            f'<div class="m {v}"{_NR.rise(i)}>'
            f'<div class="k">{_h.escape(m.label)}</div>'
            f'<div class="v">{_NR.counted(m.now) if m.now is not None else "—"}'
            f'{(" " + _h.escape(m.unit)) if m.unit else ""}</div>'
            f'<div class="s">{sentence(m)}</div>'
            + (f'<div class="s">{_h.escape(m.note)}</div>' if m.note else "")
            + "</div>")
    out.append("</div>")
    return "".join(out)


def table(items: Sequence[Movement]) -> str:
    """جدولِ همان اعداد — تعهدِ «رنگ تنها حاملِ معنا نیست»."""
    rows = "".join(
        f"<tr><td><b>{_h.escape(m.label)}</b></td>"
        f"<td>{_num(m.before, m.unit)}</td>"
        f"<td>{_num(m.now, m.unit)}</td>"
        f"<td>{change(m)}</td>"
        f"<td>{_TONE[m.verdict][1]}</td></tr>" for m in items)
    return (f'<table class="nr-mo-tbl"><thead><tr>'
            f"<th>سنجه</th><th>ماه پیش</th><th>این ماه</th>"
            f"<th>تغییر</th><th>نتیجه</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")


def _chip(text: str) -> str:
    return f'<div class="nr-pill alt">{_h.escape(text)}</div>'


def build(month: Month, *, title: str, org: str, unit: str, tagline: str,
          kicker: str, subtitle: str = "", lead: str = "",
          chapters_=None, knots_=None, coda_text: str = "") -> str:
    """گزارش ماهانه، کامل — از سربرگ تا مُهر پایان.

    ترتیب همان دستور زبانِ روایت است، فقط روی محورِ زمان:

        سربرگ → این ماه چه شد → سنجه‌ها → جدول → گره‌ها → مسیر → جمع‌بندی

    عنوانِ بخشِ دوم از خودِ داده می‌آید: اگر هیچ سنجه‌ای مبنا نداشته
    باشد، به‌جای «بهتر شد/بدتر شد» صادقانه می‌گوید مبنایی نیست.
    """
    movs = list(month.movements)
    with_base = [m for m in movs if m.has_base]
    better = sum(1 for m in with_base if m.verdict == "better")
    worse = sum(1 for m in with_base if m.verdict == "worse")

    if not with_base:
        verdict = (f"این اولین ماهی است که ثبت می‌شود. هر عددی که اینجا "
                   f"می‌بینید مبنای ماهِ بعد است — نه قضاوتِ امروز.")
    elif better and not worse:
        verdict = (f"از {_NR.fa(len(with_base))} سنجه، "
                   f"<b>{_NR.fa(better)}</b> بهتر شد و هیچ‌کدام بدتر نشد.")
    elif worse and not better:
        verdict = (f"از {_NR.fa(len(with_base))} سنجه، "
                   f"<b>{_NR.fa(worse)}</b> بدتر شد و هیچ‌کدام بهتر نشد.")
    else:
        verdict = (f"از {_NR.fa(len(with_base))} سنجه، "
                   f"<b>{_NR.fa(better)}</b> بهتر شد و "
                   f"<b>{_NR.fa(worse)}</b> بدتر. ماه، یک‌دست نبود.")

    prev = (f" نسبت به {_h.escape(month.previous)}"
            if month.previous and with_base else "")

    sparks = ""
    if month.series:
        cells = "".join(
            f'<div class="m"{_NR.rise(i)}><div class="k">{_h.escape(name)}</div>'
            f'<div class="sp">{spark(vals, label=name)}</div></div>'
            for i, (name, vals) in enumerate(month.series))
        sparks = f'<div class="nr-mo">{cells}</div>'

    parts = [
        _NR.hero(month.facts, kicker=kicker, title=title, subtitle=subtitle),
        '<div class="nr-sheet">',
        _chip(f"{month.label} — روایتِ داده"),
        f'<div class="nr-hook"{_NR.rise(0)}><p>{verdict}{prev}</p></div>',
        movement(movs) if with_base else "",
        legend() if with_base else "",
        cards(movs),
        table(movs),
        sparks,
    ]
    if chapters_:
        parts += [_chip("مسیر — از رویداد تا عدد"), _NR.journey(chapters_)]
    if knots_:
        parts += [_chip("همان گره‌های همیشگی"), _NR.knots(knots_)]
    parts += [
        _NR.resolution_block(month.facts),
        _NR.coda(coda_text or "عدد، وقتی تنها بیاید خبر است؛ وقتی کنارِ "
                              "ماهِ پیش بیاید، تصمیم است."),
        "</div>",
        _NR.footer(org=org, unit=unit, tagline=tagline,
                   ref_date=month.facts.ref_date),
        _NR.motion_js(),
    ]
    return "".join(p for p in parts if p)


def page(month: Month, **kw) -> str:
    """صفحهٔ کاملِ HTML — خودبسنده، بدون هیچ درخواستِ شبکه."""
    body = build(month, **kw)
    return ('<!doctype html><html lang="fa" dir="rtl"><head>'
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{_h.escape(kw.get("title", "گزارش ماهانه"))}</title>'
            f"<style>{_sheet_css()}{_NR.css()}{CSS}</style></head>"
            f"<body>{body}</body></html>")


def _sheet_css() -> str:
    return f"""
*{{box-sizing:border-box}}
body{{margin:0;background:{_AL.page_gradient_css()};
  font-family:{_AL.FONT_STACK};color:{_AL.INK}}}
.nr-sheet{{max-width:900px;margin:0 auto;padding:26px 30px 34px;
  background:{_AL.CARD}}}
.nr-hero-wrap{{max-width:900px;margin:0 auto}}
"""


# ═══════════════ اتصال به دادهٔ عملکرد ═══════════════

#: ستون‌ها. نبودِ ستون یعنی حذفِ همان سنجه، نه صفرِ ساختگی.
_PERF = "عملکرد"
_COVER = "پوشش"
_CONF = "اطمینان"


def _median_of(df, col) -> Optional[float]:
    if col not in df.columns:
        return None
    import pandas as _pd
    m = _pd.to_numeric(df[col], errors="coerce").median()
    return None if m != m else float(m)


def _mean_of(df, col) -> Optional[float]:
    if col not in df.columns:
        return None
    import pandas as _pd
    m = _pd.to_numeric(df[col], errors="coerce").mean()
    return None if m != m else float(m)


def _below(df, col, floor) -> Optional[int]:
    if col not in df.columns:
        return None
    import pandas as _pd
    return int((_pd.to_numeric(df[col], errors="coerce") < floor).sum())


def from_frames(now, before=None, *, label: str, ref_date: str,
                previous: str = "", history=(), action_floor: float = 45.0) -> Month:
    """ماه را از دو کارنامه بساز — این ماه و ماه پیش.

    ``before`` می‌تواند ``None`` باشد؛ آن‌وقت دلتایی ساخته نمی‌شود و
    گزارش می‌گوید این اولین ماه است.
    """
    def pair(fn, *a):
        return fn(now, *a), (fn(before, *a) if before is not None else None)

    perf_n, perf_b = pair(_median_of, _PERF)
    cov_n, cov_b = pair(_mean_of, _COVER)
    conf_n, conf_b = pair(_mean_of, _CONF)
    act_n, act_b = pair(_below, _PERF, action_floor)
    tot_n = int(len(now))
    tot_b = int(len(before)) if before is not None else None

    movs: List[Movement] = []
    if perf_n is not None:
        movs.append(Movement("میانهٔ عملکرد", perf_n, perf_b, "از ۱۰۰",
                             good="up"))
    if act_n is not None:
        movs.append(Movement("نیازمند اقدام", act_n, act_b, "نفر", good="down",
                             note="کسانی که امتیازشان زیر کفِ اقدام است."))
    if cov_n is not None:
        movs.append(Movement("میانگین پوشش",
                             None if cov_n is None else round(cov_n * 100, 1),
                             None if cov_b is None else round(cov_b * 100, 1),
                             "٪", good="up",
                             note="پوششِ کم یعنی امتیاز روی شواهدِ کم ساخته "
                                  "شده — نه اینکه عملکرد بد است."))
    if conf_n is not None:
        movs.append(Movement("میانگین اطمینان",
                             None if conf_n is None else round(conf_n * 100, 1),
                             None if conf_b is None else round(conf_b * 100, 1),
                             "٪", good="up"))
    movs.append(Movement("نفراتِ سنجیده‌شده", tot_n, tot_b, "نفر", good="flat"))

    facts = _NR.Facts(total=tot_n, subject="نفر", ref_date=ref_date,
                      critical=act_n or 0, critical_label="نیازمند اقدام",
                      blind=0, median=perf_n, median_label="میانهٔ امتیاز",
                      median_unit="از ۱۰۰")
    return Month(label=label, facts=facts, movements=movs,
                 series=list(history), previous=previous)
