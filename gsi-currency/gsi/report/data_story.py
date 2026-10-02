# -*- coding: utf-8 -*-
"""دیتا استوری‌تلینگ (R10، مالک ۱۴۰۵/۰۷/۰۹): داستان تصویری پول، کالا، صف، تعهد، حمل و قطعات بحرانی.

هر فصل یک پرسش مالک را با **همان داده منتشرشده** جواب می‌دهد:

* پول از دفتر رویدادهای مالی (``fx_money_ledger``، مرحله ۵۶): خرید ارز، درخواست و تخصیص، تعهد و رفع تعهد،
  هر کدام با تاریخ و ارز خودش؛
* کالا و حمل از گزارش حمل و ترخیص و مسیر شواهد هر بارنامه (``shipping_clearance_report``)؛
* گروه قطعات و سطح بحرانی از مارت (``PART_GROUP`` و «کد طبقه بحرانی»).

قاعده‌ها (حافظه پروژه):

* مبلغ دو ارز هرگز جمع یا مقایسه نمی‌شود؛ هر ارز نمودار و جمله خودش را دارد. مقایسه میان ارزها فقط با
  شمار رویداد یا درصدِ هر ارز از کل خودش است.
* عدد ساخته نمی‌شود؛ نبودِ داده «داده نداریم» است، نه صفر. پرسشی که منبعی ندارد (مثل «خرید غیرضروری»)
  کارت «این داده در منبع‌ها نیست» می‌گیرد.
* مقایسه دوره‌ها از ابتدای ۱۴۰۴ هم‌زمانی را نشان می‌دهد، نه علت را.
* ثبت سفارشی که قطعاتش در چند گروه‌اند به یک گروه نسبت داده نمی‌شود («چند گروه»).

متن جمله‌ها از قالب ثابت و همین عددها ساخته می‌شود (بی‌مدل زبانی و بی‌حدس)؛ فقط وضعیت گفته می‌شود و
نام هیچ شخصی در داستان نیست.
"""
from __future__ import annotations

import html
import io
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from ..core.jalali import CalendarEngine, format_jalali, gregorian_to_jalali, jalali_to_gregorian
from ..design import icons as I
from ..design import tokens as T
from . import fx_insight as X

# ═══════════════════════════════ ثابت‌ها ═══════════════════════════════
START_1404 = jalali_to_gregorian(1404, 1, 1)
#: آغاز جنگ دوازده‌روزه (۱۴۰۴/۰۳/۲۳)؛ فقط نشانه زمانی روی نمودار، نه علت
WAR_MARK = jalali_to_gregorian(1404, 3, 23)
SEASONS = ("بهار", "تابستان", "پاییز", "زمستان")
CRITICAL_LEVELS = ("STOCKOUT", "CRITICAL", "BECOMING_CRITICAL")
LEVEL_FA = {"STOCKOUT": "توقف خط", "CRITICAL": "بحرانی", "BECOMING_CRITICAL": "در حال بحرانی شدن",
            "WATCH": "تحت نظر", "SAFE": "ایمن", "NO_CONSUMPTION": "بدون مصرف", "UNKNOWN": "نامشخص"}
CURRENCY_FA = {"EUR": "یورو", "USD": "دلار", "CNY": "یوآن", "AED": "درهم", "RUB": "روبل", "INR": "روپیه",
               "TRY": "لیر", "GBP": "پوند", "JPY": "ین", "CHF": "فرانک", "KRW": "وون", "IRR": "ریال"}
MULTI_GROUP = "چند گروه"
NO_GROUP = "گروه نامعلوم"
REQUEST_CODES = ("ALLOCATION_REQUEST", "ALLOCATION_REQUEST_REJECTED", "ALLOCATION_REQUEST_CLOSED",
                 "ALLOCATION_REQUEST_AMBIGUOUS")
_FA_DIGITS = str.maketrans("0123456789.,-", "۰۱۲۳۴۵۶۷۸۹٫٬−")


def fa(v: Any) -> str:
    """عدد/متن با رقم فارسی."""
    return str(v).translate(_FA_DIGITS)


def fnum(v: Optional[float], nd: int = 0) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return fa(f"{v:,.{nd}f}")


def compact(v: Optional[float]) -> str:
    """مبلغ خوانا: ۱٫۲ میلیون، ۳۴۰ هزار، ۲٫۱ میلیارد."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    a = abs(v)
    for div, unit in ((1e9, "میلیارد"), (1e6, "میلیون"), (1e3, "هزار")):
        if a >= div:
            x = v / div
            return fa(f"{x:,.1f}".rstrip("0").rstrip(".")) + " " + unit
    return fa(f"{v:,.0f}")


def money(v: Optional[float], cur: str) -> str:
    return f"{compact(v)} {CURRENCY_FA.get(cur, cur)}"


def _d(v: Any) -> Optional[date]:
    if v is None or not X.s(v):
        return None
    if isinstance(v, date):
        return v
    try:
        return CalendarEngine.parse(v)
    except Exception:
        return None


def jparts(d: date) -> Tuple[int, int, int]:
    return gregorian_to_jalali(d)


#: کلید دوره یک عدد است (سال×۱۰ + شماره دوره) تا مقایسه ستونی pandas درست کار کند
def half_key(d: date) -> int:
    jy, jm, _ = jparts(d)
    return jy * 10 + (1 if jm <= 6 else 2)


def half_label(k: int) -> str:
    return f"{'نیمه اول' if k % 10 == 1 else 'نیمه دوم'} {fa(k // 10)}"


def season_key(d: date) -> int:
    jy, jm, _ = jparts(d)
    return jy * 10 + (jm - 1) // 3


def season_label(k: int) -> str:
    return f"{SEASONS[k % 10]} {fa(k // 10)}"


def _seq_half(keys: Iterable[int]) -> List[int]:
    """همه نیم‌سال‌ها از کمینه تا بیشینه، بی‌جاافتادگی."""
    ks = sorted(set(keys))
    if not ks:
        return []
    out, k = [], ks[0]
    while k <= ks[-1]:
        out.append(k)
        k = k + 1 if k % 10 == 1 else (k // 10 + 1) * 10 + 1
    return out


def _seq_season(keys: Iterable[int]) -> List[int]:
    """همه فصل‌ها از کمینه تا بیشینه، بی‌جاافتادگی."""
    ks = sorted(set(keys))
    if not ks:
        return []
    out, k = [], ks[0]
    while k <= ks[-1]:
        out.append(k)
        k = k + 1 if k % 10 < 3 else (k // 10 + 1) * 10
    return out


def _med(xs: Sequence[float]) -> Optional[float]:
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return float(median(xs)) if xs else None


# ═══════════════════════════════ ورودی‌ها ═══════════════════════════════
def ledger(extras: Any) -> pd.DataFrame:
    """دفتر رویدادهای مالی با تاریخ تبدیل‌شده و مبلغ عددی؛ ردیف بی‌تاریخ نگه داشته می‌شود (DATE=None)."""
    try:
        ml = extras.get("fx_money_ledger") if extras is not None else None
    except Exception:
        ml = None
    if not isinstance(ml, pd.DataFrame) or ml.empty:
        return pd.DataFrame(columns=["KEY_REG", "EVENT_CODE", "DATE", "AMOUNT", "CURRENCY", "REFERENCE", "STATUS"])
    out = pd.DataFrame({
        "KEY_REG": ml["KEY_REG"].map(X.s) if "KEY_REG" in ml else "",
        "EVENT_CODE": ml["EVENT_CODE"].map(X.s),
        "DATE": ml["EVENT_DATE"].map(_d) if "EVENT_DATE" in ml else None,
        "AMOUNT": pd.to_numeric(ml.get("AMOUNT"), errors="coerce"),
        "CURRENCY": ml.get("CURRENCY", pd.Series("", index=ml.index)).map(lambda v: X.s(v).upper()),
        "REFERENCE": ml.get("REFERENCE", pd.Series("", index=ml.index)).map(X.s),
        "STATUS": ml.get("STATUS", pd.Series("", index=ml.index)).map(X.s),
    })
    return out.reset_index(drop=True)


def _col(df: pd.DataFrame, *names: str) -> pd.Series:
    for n in names:
        if n in df.columns:
            return df[n].map(X.s)
    return pd.Series([""] * len(df), index=df.index)


def groups_of(df: pd.DataFrame, key: str) -> Dict[str, str]:
    """کلید (ثبت سفارش یا بارنامه) ← گروه قطعه؛ چند گروه ← «چند گروه»، بی‌گروه ← «گروه نامعلوم»."""
    if df is None or df.empty or key not in df.columns:
        return {}
    g = pd.DataFrame({"k": _col(df, key), "g": _col(df, "PART_GROUP", "SUPPLY_GROUP")})
    out = {}
    for k, part in g[g["k"].ne("")].groupby("k"):
        gs = set(part["g"]) - {""}
        out[k] = next(iter(gs)) if len(gs) == 1 else (MULTI_GROUP if gs else NO_GROUP)
    return out


def level_of_reg(df: pd.DataFrame) -> Dict[str, str]:
    if df is None or df.empty or "KEY_REG" not in df.columns:
        return {}
    g = pd.DataFrame({"k": _col(df, "KEY_REG"), "c": _col(df, "کد طبقه بحرانی")})
    return {k: (X.worst_level(part["c"]) or "UNKNOWN") for k, part in g[g["k"].ne("")].groupby("k")}


# ═══════════════════════════════ مدل داستان ═══════════════════════════════
@dataclass
class Chapter:
    key: str
    icon: str
    title: str
    headline: str
    visual: str = ""
    insight: str = ""
    note: str = ""
    gaps: List[str] = field(default_factory=list)
    table: pd.DataFrame = field(default_factory=pd.DataFrame)
    tone: str = "brand"

    @property
    def has_data(self) -> bool:
        return bool(self.visual)


@dataclass
class Story:
    ref_date: str
    as_of: date
    hero: List[Tuple[str, str, str]]
    badges: List[Tuple[str, str, str]]
    chapters: List[Chapter]


# ═══════════════════════════════ نمودارها (SVG برای HTML مستقل) ═══════════════════════════════
PAL = T.CATEGORICAL


def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _label_step(n: int, width: float, px: float = 92) -> int:
    """هر چند برچسب یکی، تا برچسب‌های محور روی هم نیفتند."""
    return max(1, math.ceil(n / max(width / px, 1)))


def line_svg(xlabels: List[str], series: List[Tuple[str, List[Optional[float]], str]], w: int = 1100, h: int = 240,
             yfmt=compact, marker: Optional[int] = None, marker_label: str = "", pct: bool = False,
             axis: bool = True) -> str:
    """نمودار خطی چندسری؛ مقدار None شکاف خط است (بی‌داده، نه صفر)."""
    vals = [v for _, ys, _ in series for v in ys if v is not None]
    if not vals or not xlabels:
        return ""
    top = 100.0 if pct and max(vals) <= 100 else (max(vals) * 1.08 or 1.0)
    L, R, TP, B = (76, 48, 14, 34) if axis else (6, 6, 8, 8)
    n = len(xlabels)
    xs = [L + (w - L - R) * (i / max(n - 1, 1)) for i in range(n)]
    y = lambda v: TP + (h - TP - B) * (1 - v / top)  # noqa: E731
    out = [f'<svg class="ds-svg" viewBox="0 0 {w} {h}" role="img" preserveAspectRatio="xMidYMid meet">']
    for t in range(4 if axis else 0):
        v = top * t / 3
        out.append(f'<line x1="{L}" x2="{w - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="ds-gl"/>'
                   f'<text x="{L - 6}" y="{y(v) + 4:.1f}" class="ds-ax" text-anchor="end">'
                   f'{_esc(fa(f"{v:.0f}") + "٪" if pct else yfmt(v))}</text>')
    if not axis:
        out.append(f'<line x1="{L}" x2="{w - R}" y1="{h - B}" y2="{h - B}" class="ds-gl"/>')
    step = _label_step(n, w - L - R)
    for i, lab in enumerate(xlabels if axis else []):
        if (n - 1 - i) % step == 0:
            out.append(f'<text x="{xs[i]:.1f}" y="{h - 10}" class="ds-ax" text-anchor="middle">{_esc(lab)}</text>')
    if marker is not None and 0 <= marker < n:
        out.append(f'<line x1="{xs[marker]:.1f}" x2="{xs[marker]:.1f}" y1="{TP}" y2="{h - B}" class="ds-mark"/>'
                   f'<text x="{xs[marker] + 4:.1f}" y="{TP + 10}" class="ds-markt">{_esc(marker_label)}</text>')
    for name, ys, color in series:
        seg: List[str] = []
        for i, v in enumerate(ys):
            if v is None:
                if len(seg) > 1:
                    out.append(f'<polyline points="{" ".join(seg)}" fill="none" stroke="{color}" stroke-width="2.6" '
                               f'stroke-linejoin="round" stroke-linecap="round"/>')
                seg = []
                continue
            seg.append(f"{xs[i]:.1f},{y(v):.1f}")
        if len(seg) > 1:
            out.append(f'<polyline points="{" ".join(seg)}" fill="none" stroke="{color}" stroke-width="2.6" '
                       f'stroke-linejoin="round" stroke-linecap="round"/>')
        last = max((i for i, v in enumerate(ys) if v is not None), default=None)
        for i, v in enumerate(ys):
            if v is not None:
                r = 4.2 if i == last else 2.6
                out.append(f'<circle cx="{xs[i]:.1f}" cy="{y(v):.1f}" r="{r}" fill="{color}">'
                           f'<title>{_esc(name)} · {_esc(xlabels[i])}: {_esc(fa(f"{v:.0f}") + "٪" if pct else yfmt(v))}'
                           f'</title></circle>')
    out.append("</svg>")
    return "".join(out)


def bars_svg(xlabels: List[str], series: List[Tuple[str, List[Optional[float]], str]], w: int = 1100, h: int = 220,
             yfmt=lambda v: fnum(v), stacked: bool = False) -> str:
    """ستون‌های گروهی (یا روی‌هم برای شمار)؛ None = بی‌داده و ستونی کشیده نمی‌شود."""
    if not xlabels or not series:
        return ""
    if stacked:
        tops = [sum((ys[i] or 0) for _, ys, _ in series) for i in range(len(xlabels))]
    else:
        tops = [v for _, ys, _ in series for v in ys if v is not None]
    top = (max(tops) if tops else 0) * 1.1
    if not top:
        return ""
    L, R, TP, B = 76, 10, 12, 34
    n, k = len(xlabels), len(series)
    slot = (w - L - R) / n
    bw = slot * 0.66 / (1 if stacked else k)
    y = lambda v: TP + (h - TP - B) * (1 - v / top)  # noqa: E731
    out = [f'<svg class="ds-svg" viewBox="0 0 {w} {h}" role="img" preserveAspectRatio="xMidYMid meet">']
    for t in range(4):
        v = top * t / 3
        out.append(f'<line x1="{L}" x2="{w - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="ds-gl"/>'
                   f'<text x="{L - 6}" y="{y(v) + 4:.1f}" class="ds-ax" text-anchor="end">{_esc(yfmt(v))}</text>')
    step = _label_step(n, w - L - R)
    for i, lab in enumerate(xlabels):
        x0 = L + slot * i + slot * 0.17
        base = 0.0
        for j, (name, ys, color) in enumerate(series):
            v = ys[i]
            if v is None or v <= 0:
                continue
            if stacked:
                y1, y0 = y(base + v), y(base)
                base += v
                out.append(f'<rect x="{x0:.1f}" y="{y1:.1f}" width="{bw:.1f}" height="{max(y0 - y1, 0.5):.1f}" rx="2" '
                           f'fill="{color}"><title>{_esc(name)} · {_esc(lab)}: {_esc(yfmt(v))}</title></rect>')
            else:
                xx = x0 + bw * j
                out.append(f'<rect x="{xx:.1f}" y="{y(v):.1f}" width="{bw:.1f}" height="{max(y(0) - y(v), 0.5):.1f}" '
                           f'rx="3" fill="{color}"><title>{_esc(name)} · {_esc(lab)}: {_esc(yfmt(v))}</title></rect>')
        if (n - 1 - i) % step == 0:
            out.append(f'<text x="{L + slot * (i + .5):.1f}" y="{h - 10}" class="ds-ax" text-anchor="middle">'
                       f'{_esc(lab)}</text>')
    out.append("</svg>")
    return "".join(out)


def hbars(items: List[Tuple[str, Optional[float], str]], color: str = "", unit: str = "") -> str:
    """نوار افقی (HTML)؛ هر ردیف: برچسب، مقدار، متن کنار نوار."""
    vals = [v for _, v, _ in items if v is not None]
    if not vals:
        return ""
    top = max(vals) or 1
    rows = []
    for lab, v, txt in items:
        wpct = 0 if v is None else 100 * v / top
        rows.append(f'<div class="ds-hb"><span class="ds-hb-l">{_esc(lab)}</span><span class="ds-hb-t">'
                    f'<i style="width:{wpct:.1f}%;{("background:" + color) if color else ""}"></i></span>'
                    f'<b>{_esc(txt or fnum(v))}{_esc(unit)}</b></div>')
    return f'<div class="ds-hbs">{"".join(rows)}</div>'


def stack100(periods: List[str], parts: List[Tuple[str, List[float], str]]) -> str:
    """ستون ۱۰۰٪ هر دوره (سهم هر بخش از کل همان دوره و همان ارز)."""
    rows = []
    for i, p in enumerate(periods):
        tot = sum(v[i] for _, v, _ in parts)
        if not tot:
            continue
        segs = "".join(f'<i style="width:{100 * v[i] / tot:.2f}%;background:{c}" title="{_esc(n)}: {fa(round(100 * v[i] / tot))}٪"></i>'
                       for n, v, c in parts if v[i])
        rows.append(f'<div class="ds-st"><span class="ds-st-l">{_esc(p)}</span><span class="ds-st-b">{segs}</span></div>')
    legend = "".join(f'<span><i style="background:{c}"></i>{_esc(n)}</span>' for n, _, c in parts)
    return f'<div class="ds-sts">{"".join(rows)}</div><div class="ds-leg">{legend}</div>' if rows else ""


def ring(pct: Optional[float], label: str, tone: str = "brand") -> str:
    if pct is None:
        return ""
    c = T.STATUS["good"].fill if tone == "good" else T.TEAL_PALETTE[5]
    r, cx = 30, 38
    circ = 2 * math.pi * r
    return (f'<div class="ds-ring"><svg viewBox="0 0 76 76" width="76" height="76"><circle cx="{cx}" cy="{cx}" r="{r}" '
            f'class="ds-ring-bg"/><circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="{c}" stroke-width="8" '
            f'stroke-linecap="round" stroke-dasharray="{circ * min(pct, 100) / 100:.1f} {circ:.1f}" '
            f'transform="rotate(-90 {cx} {cx})"/><text x="{cx}" y="{cx + 5}" text-anchor="middle" class="ds-ring-t">'
            f'{fa(round(pct))}٪</text></svg><span>{_esc(label)}</span></div>')


def legend(series: List[Tuple[str, Any, str]]) -> str:
    return '<div class="ds-leg">' + "".join(f'<span><i style="background:{c}"></i>{_esc(n)}</span>'
                                             for n, _, c in series) + "</div>"


# ═══════════════════════════════ فصل‌ها ═══════════════════════════════
def _gap_chapter(key, icon, title, gaps) -> Chapter:
    return Chapter(key, icon, title, "داده لازم برای این فصل در Snapshot نیست.", gaps=gaps, tone="unknown")


def ch_money(led: pd.DataFrame) -> Chapter:
    """فصل ۱: چقدر ارز خریدیم و هر ارز در زمان چه شد (هر ارز جدا)."""
    fx = led[led["EVENT_CODE"].eq("FX_PURCHASE") & led["DATE"].notna()]
    title = "پول: خرید ارز در گذر زمان"
    if fx.empty:
        return _gap_chapter("money", "coins", title, ["خرید ارز با تاریخ در منبع fx_transaction نیست."])
    fx = fx.assign(S=fx["DATE"].map(season_key))
    seasons = _seq_season(fx["S"])
    labels = [season_label(s) for s in seasons]
    curs = fx["CURRENCY"].value_counts().index.tolist()
    since = fx[fx["DATE"] >= START_1404]
    parts = [money(since.loc[since["CURRENCY"].eq(c), "AMOUNT"].sum(min_count=1), c) for c in curs
             if since["CURRENCY"].eq(c).any()]
    head = (f"از ابتدای ۱۴۰۴، {fa(len(since))} خرید ارز ثبت شده: " + "، ".join(parts[:3]) + "."
            if len(since) else f"{fa(len(fx))} خرید ارز ثبت شده؛ از ابتدای ۱۴۰۴ خریدی در داده نیست.")
    minis = []
    rows = []
    for i, c in enumerate(curs[:4]):
        sub = fx[fx["CURRENCY"].eq(c)]
        ys = [sub.loc[sub["S"].eq(s), "AMOUNT"].sum(min_count=1) for s in seasons]
        ys = [None if pd.isna(v) else float(v) for v in ys]
        minis.append(f'<div class="ds-mini"><b>{_esc(CURRENCY_FA.get(c, c))}</b>'
                     f'{bars_svg(labels, [(CURRENCY_FA.get(c, c), ys, PAL[i % len(PAL)])], w=560, h=200, yfmt=compact)}</div>')
        rows += [{"ارز": c, "فصل": lab, "مبلغ خرید": v, "شمار خرید": int(sub["S"].eq(s).sum())}
                 for lab, s, v in zip(labels, seasons, ys)]
    count_parts = [(CURRENCY_FA.get(c, c), [float(fx.loc[fx["CURRENCY"].eq(c), "S"].eq(s).sum()) for s in seasons],
                    PAL[i % len(PAL)]) for i, c in enumerate(curs[:6])]
    visual = (f'<div class="ds-grid2">{"".join(minis)}</div>'
              f'<h4>سهم هر ارز از شمار خریدها در هر فصل</h4>{stack100(labels, count_parts)}')
    top_c = curs[0]
    insight = (f"بیشترین شمار خرید با {CURRENCY_FA.get(top_c, top_c)} بوده است. مبلغ ارزها با هم جمع یا "
               "مقایسه نمی‌شود؛ مقایسه میان ارزها با شمار خرید است.")
    return Chapter("money", "coins", title, head, visual, insight,
                   note="منبع: رویداد «خرید ارز» دفتر مالی (fx_transaction)، به ارز خود هر خرید.",
                   table=pd.DataFrame(rows))


def ch_money_goods(led: pd.DataFrame, bls: pd.DataFrame) -> Chapter:
    """فصل ۲: پول و کالا در یک خط زمانی؛ واگرایی ارز خریده‌شده و کالای تخلیه‌شده در همان ارز."""
    title = "پول و کالا: واگرایی خرید ارز و رسیدن کالا"
    fx = led[led["EVENT_CODE"].eq("FX_PURCHASE") & led["DATE"].notna() & led["AMOUNT"].notna()]
    goods = bls[bls["DISCHARGE"].notna() & bls["VALUE"].notna() & bls["CUR"].ne("")] if not bls.empty else bls
    curs = [c for c in fx["CURRENCY"].value_counts().index if not goods.empty and goods["CUR"].eq(c).any()]
    if not curs:
        gaps = []
        if fx.empty:
            gaps.append("خرید ارز با تاریخ و مبلغ در داده نیست.")
        if goods is None or goods.empty:
            gaps.append("ارزش فاکتور بارنامه (BLREG_BL_INVOICE_VALUE) با تاریخ تخلیه در داده نیست.")
        if not gaps:
            gaps.append("هیچ ارزی هم خرید ارز و هم ارزش کالای تخلیه‌شده ندارد؛ دو ارز مختلف مقایسه نمی‌شوند.")
        return _gap_chapter("goods", "trend", title, gaps)
    charts, rows, heads = [], [], []
    for c in curs[:2]:
        f = fx[fx["CURRENCY"].eq(c)].assign(S=lambda x: x["DATE"].map(season_key))
        g = goods[goods["CUR"].eq(c)].assign(S=lambda x: x["DISCHARGE"].map(season_key))
        seasons = _seq_season(list(f["S"]) + list(g["S"]))
        cf, cg, a, b = [], [], 0.0, 0.0
        for s in seasons:
            a += float(f.loc[f["S"].eq(s), "AMOUNT"].sum())
            b += float(g.loc[g["S"].eq(s), "VALUE"].sum())
            cf.append(a)
            cg.append(b)
            rows.append({"ارز": c, "فصل": season_label(s), "ارز خریده‌شده (انباشته)": a,
                         "ارزش کالای تخلیه‌شده (انباشته)": b})
        name = CURRENCY_FA.get(c, c)
        labels = [season_label(s) for s in seasons]
        mk = next((i for i, s in enumerate(seasons) if s >= season_key(WAR_MARK)), None)
        ser = [(f"ارز خریده‌شده ({name})", cf, PAL[0]), (f"کالای تخلیه‌شده ({name})", cg, PAL[1])]
        charts.append(f'<div><b>{_esc(name)}</b>{line_svg(labels, ser, marker=mk, marker_label="۱۴۰۴/۰۳/۲۳")}'
                      f'{legend(ser)}</div>')
        if a:
            heads.append(f"در {name}، کالای تخلیه‌شده برابر {fa(round(100 * b / a))}٪ ارز خریده‌شده است")
    cov = (bls["VALUE"].notna().sum() / len(bls) * 100) if len(bls) else 0
    head = ("؛ ".join(heads) + ".") if heads else "دو خط در یک ارز کنار هم آمده‌اند."
    return Chapter("goods", "trend", title, head, "".join(charts),
                   "فاصله دو خط یعنی ارزی که خریده شده و کالایش هنوز تخلیه‌شده دیده نمی‌شود (یا ارزش بارنامه‌اش ثبت نشده).",
                   note=(f"هر ارز جدا. ارزش کالا از ارزش فاکتور بارنامه با تاریخ تخلیه؛ {fa(round(cov))}٪ بارنامه‌ها "
                         "ارزش دارند. خط عمودی آغاز جنگ دوازده‌روزه است، فقط برای جهت‌یابی زمانی."),
                   table=pd.DataFrame(rows))


def ch_queue(led: pd.DataFrame, as_of: date) -> Chapter:
    """فصل ۳: صف تخصیص؛ ورود درخواست، تخصیص و رد در هر فصل و میانه انتظار."""
    title = "صف تخصیص: چقدر منتظر ماندیم"
    req = led[led["EVENT_CODE"].isin(REQUEST_CODES)]
    alloc = led[led["EVENT_CODE"].eq("ALLOCATION") & led["DATE"].notna()]
    if req.empty and alloc.empty:
        return _gap_chapter("queue", "queue", title, ["درخواست و تخصیص ارز (NTSW) در داده نیست."])
    rq_date = {r: d for r, d in zip(req["REFERENCE"], req["DATE"]) if r and d}
    waits = []
    for r, d, cur in zip(alloc["REFERENCE"], alloc["DATE"], alloc["CURRENCY"]):
        s = rq_date.get(r)
        if s and d >= s:
            waits.append((d, (d - s).days))
    keys = [season_key(d) for d in req["DATE"] if d] + [season_key(d) for d in alloc["DATE"]]
    seasons = _seq_season(keys)
    labels = [season_label(s) for s in seasons]
    reqd = req[req["DATE"].notna()]
    new = [float(reqd["DATE"].map(season_key).eq(s).sum()) for s in seasons]
    rej = [float(reqd[reqd["EVENT_CODE"].ne("ALLOCATION_REQUEST")]["DATE"].map(season_key).eq(s).sum()) for s in seasons]
    al = [float(alloc["DATE"].map(season_key).eq(s).sum()) for s in seasons]
    wait_by = [_med([w for d, w in waits if season_key(d) == s]) for s in seasons]
    ser = [("درخواست تازه", new, PAL[2]), ("تخصیص", al, PAL[0]), ("رد یا بسته‌شده (به فصل درخواست)", rej, PAL[5])]
    open_now = req[req["EVENT_CODE"].eq("ALLOCATION_REQUEST") & req["STATUS"].str.upper().eq("OPEN")]
    open_parts = [money(open_now.loc[open_now["CURRENCY"].eq(c), "AMOUNT"].sum(min_count=1), c)
                  for c in open_now["CURRENCY"].value_counts().index]
    known = [(i, v) for i, v in enumerate(wait_by) if v is not None]
    if len(known) >= 2:
        (i0, v0), (i1, v1) = known[0], known[-1]
        head = (f"میانه انتظار تخصیص از {fnum(v0)} روز در {labels[i0]} به {fnum(v1)} روز در {labels[i1]} "
                f"{'رسید' if v1 != v0 else 'ثابت ماند'}.")
    elif known:
        head = f"میانه انتظار تخصیص در {labels[known[0][0]]}: {fnum(known[0][1])} روز."
    else:
        head = f"{fa(len(reqd))} درخواست تخصیص با تاریخ ثبت شده؛ انتظار قابل سنجش نیست (تخصیص با درخواستش جفت نشد)."
    visual = (bars_svg(labels, ser, h=210) + legend(ser)
              + ("<h4>میانه روز انتظار از درخواست تا تخصیص</h4>"
                 + line_svg(labels, [("میانه انتظار (روز)", wait_by, PAL[6])], h=180, yfmt=fnum) if known else ""))
    insight = (f"اکنون {fa(len(open_now))} درخواست در صف است" + (f": {'، '.join(open_parts)}" if open_parts else "")
               + ".")
    rows = [{"فصل": l, "درخواست تازه": n, "تخصیص": a, "رد یا بسته‌شده": r, "میانه انتظار (روز)": w}
            for l, n, a, r, w in zip(labels, new, al, rej, wait_by)]
    return Chapter("queue", "queue", title, head, visual, insight,
                   note=("انتظار فقط برای درخواستی سنجیده می‌شود که تخصیصش با همان شناسه درخواست جفت شود. تاریخ رد در "
                         "منبع نیست؛ درخواست ردشده به فصل خود درخواست شمرده می‌شود."),
                   table=pd.DataFrame(rows))


#: رفع تعهد (مالک ۱۴۰۵/۰۷/۰۹): داشتن کد رهگیری ساتا؛ تاریخش «تاریخ اخذ کد رهگیری» است
SATA_TRACK_DATE, SATA_TRACK_NO = "SATA_TRACKING_DATE", "SATA_NO"
SETTLED, SETTLED_NO_DATE, PARTIAL = "settled", "settled_no_date", "partial"


def _has_code(v: Any) -> bool:
    t = X.s(v).replace(" ", "")
    return bool(t) and set(t) != {"0"}


def sata_settlement(df: Optional[pd.DataFrame], led: pd.DataFrame) -> pd.DataFrame:
    """رفع تعهد هر ثبت سفارش از کد رهگیری ساتا (هر بارنامه یک کد).

    بارنامه رفع تعهدشده است اگر کد رهگیری داشته باشد (کد، تاریخ اخذ کد، یا وضعیت «کد رهگیری دارد»). ثبت سفارش:
    همه بارنامه‌هایش کد دارند و همه تاریخ دارند ← «رفع تعهد با تاریخ» (دیرترین تاریخ اخذ کد)؛ همه کد دارند ولی
    تاریخ کامل نیست ← «تاریخ نامعلوم»؛ بخشی کد دارند ← «رفع بخشی». NTSW فقط مقایسه می‌شود (``NTSW_FULL``) و
    تاریخ را عوض نمی‌کند.
    """
    cols = ["KEY_REG", "STATE", "DATE", "FIRST_ALLOC", "BLS", "CODED", "NTSW_FULL"]
    if df is None or df.empty or not any(c in df.columns for c in (SATA_TRACK_DATE, SATA_TRACK_NO, "SATA_DATE")):
        return pd.DataFrame(columns=cols)
    reg = _col(df, "SATA_KEY_REG")
    reg = reg.where(reg.ne(""), _col(df, "KEY_REG"))
    dates = _col(df, SATA_TRACK_DATE, "SATA_DATE").map(_d)
    status = _col(df, "SATA_CREDIT_STATUS")
    coded = [bool(d) or _has_code(n) or "کد رهگیری دارد" in st
             for d, n, st in zip(dates, _col(df, SATA_TRACK_NO), status)]
    sx = pd.DataFrame({"R": reg, "B": _col(df, "CANONICAL_BL", "KEY_BL"), "D": dates, "C": coded})
    sx = sx[sx["R"].ne("") & sx["B"].ne("")]
    if sx.empty or not sx["C"].any():
        return pd.DataFrame(columns=cols)
    per_bl = sx.groupby(["R", "B"]).agg(D=("D", lambda v: max((d for d in v if d), default=None)), C=("C", "any"))
    ini = led[led["EVENT_CODE"].eq("COMMITMENT_INITIAL")].groupby(["KEY_REG", "CURRENCY"])["AMOUNT"].sum(min_count=1)
    rel = led[led["EVENT_CODE"].eq("COMMITMENT_RELEASED")].groupby(["KEY_REG", "CURRENCY"])["AMOUNT"].sum(min_count=1)
    full: Dict[str, bool] = {}
    for (r, c), a in ini.items():
        rv = rel.get((r, c))
        ok = bool(pd.notna(a) and a > 0 and rv is not None and pd.notna(rv) and rv >= a - 1e-6)
        full[r] = full.get(r, True) and ok
    alloc = led[led["EVENT_CODE"].eq("ALLOCATION") & led["DATE"].notna()].groupby("KEY_REG")["DATE"].min()
    recs = []
    for r, part in per_bl.groupby(level=0):
        n, nc = len(part), int(part["C"].sum())
        if not nc:
            continue
        ds = [d for d, c in zip(part["D"], part["C"]) if c and d]
        if nc == n and len(ds) == n:
            state, d = SETTLED, max(ds)
        elif nc == n:
            state, d = SETTLED_NO_DATE, None
        else:
            state, d = PARTIAL, None
        recs.append({"KEY_REG": r, "STATE": state, "DATE": d, "FIRST_ALLOC": alloc.get(r), "BLS": n, "CODED": nc,
                     "NTSW_FULL": full.get(r)})
    return pd.DataFrame(recs, columns=cols)


def ch_settlement(led: pd.DataFrame, settle: Optional[pd.DataFrame] = None) -> Chapter:
    """فصل ۴: تخصیص و رفع تعهد؛ درصد رفع تعهد هر دسته تعهد (نیم‌سال ایجاد) به تفکیک ارز."""
    title = "تعهد: تخصیص و رفع تعهد"
    ini = led[led["EVENT_CODE"].eq("COMMITMENT_INITIAL")]
    rel = led[led["EVENT_CODE"].eq("COMMITMENT_RELEASED")]
    alloc = led[led["EVENT_CODE"].eq("ALLOCATION") & led["DATE"].notna()]
    if ini.empty:
        return _gap_chapter("settle", "check", title, ["تعهد ارزی (NTSW) در داده نیست."])
    relmap = rel.groupby(["KEY_REG", "CURRENCY"])["AMOUNT"].sum(min_count=1).to_dict()
    recs = []
    for _, r in ini.iterrows():
        a, c = r["AMOUNT"], r["CURRENCY"]
        if not isinstance(r["DATE"], date) or pd.isna(a) or not a:
            continue
        rv = relmap.get((r["KEY_REG"], c))
        recs.append({"H": half_key(r["DATE"]), "CUR": c, "INI": float(a),
                     "REL": None if rv is None or pd.isna(rv) else float(rv)})
    if not recs:
        return _gap_chapter("settle", "check", title, ["تعهد ارزی با تاریخ و مبلغ در داده نیست."])
    x = pd.DataFrame(recs)
    halves = _seq_half(list(x["H"]) + [half_key(d) for d in alloc["DATE"]])
    labels = [half_label(h) for h in halves]
    curs = x["CUR"].value_counts().index.tolist()[:4]
    ser, rows = [], []
    for i, c in enumerate(curs):
        ys = []
        for h in halves:
            s = x[(x["H"] == h) & x["CUR"].eq(c)]
            known = s[s["REL"].notna()]
            ys.append(None if known.empty else 100 * known["REL"].sum() / known["INI"].sum())
            rows.append({"نیم‌سال تعهد": half_label(h), "ارز": c, "شمار تعهد": len(s),
                         "رفع تعهد (٪ مبلغ همان ارز)": ys[-1]})
        ser.append((CURRENCY_FA.get(c, c), ys, PAL[i % len(PAL)]))
    cnt = [("تعهد تازه (شمار)", [float(sum(1 for h in x["H"] if h == k)) for k in halves], PAL[3]),
           ("تخصیص (شمار)", [float(sum(1 for d in alloc["DATE"] if half_key(d) == k)) for k in halves], PAL[0])]
    full = int(sum(1 for _, r in x.iterrows() if r["REL"] is not None and r["REL"] >= r["INI"] - 1e-6))
    pct_full = 100 * full / len(x)
    head = (f"{fa(full)} تعهد از {fa(len(x))} تعهد ({fa(round(pct_full))}٪ به شمار) کامل رفع شده است.")
    visual = (f'<div class="ds-rings">{ring(pct_full, "تعهد کامل رفع‌شده در NTSW (شمار)", "good")}</div>'
              + "<h4>درصد رفع تعهد هر دسته تعهد، هر ارز جدا</h4>" + line_svg(labels, ser, h=200, pct=True) + legend(ser))
    settle = settle if settle is not None else pd.DataFrame(columns=["STATE"])
    dated = settle[settle["STATE"].eq(SETTLED)] if not settle.empty else settle
    gaps, note_date = [], ""
    if dated.empty:
        visual += "<h4>شمار تعهد تازه و تخصیص در هر نیم‌سال</h4>" + bars_svg(labels, cnt, h=180) + legend(cnt)
        gaps.append("«تاریخ اخذ کد رهگیری» ساتا در این Snapshot برای هیچ ثبت سفارشی که همه بارنامه‌هایش کد دارند نیست.")
        note_date = "تاریخ رفع تعهد در دسترس نیست؛ رفع تعهد به نیم‌سالِ ایجاد تعهد نسبت داده شد. "
    else:
        # تخصیص و رفع تعهد هر دو در دانه ثبت سفارش: نیم‌سال نخستین تخصیص در برابر نیم‌سال رفع تعهد
        first_alloc = alloc.groupby("KEY_REG")["DATE"].min()
        hs = _seq_half([half_key(d) for d in first_alloc] + [half_key(d) for d in dated["DATE"]])
        hl = [half_label(h) for h in hs]
        waits = [((d - a).days, half_key(d)) for d, a in zip(dated["DATE"], dated["FIRST_ALLOC"])
                 if isinstance(a, date) and d >= a]
        pair = [("ثبت سفارش با نخستین تخصیص", [float(sum(1 for d in first_alloc if half_key(d) == h)) for h in hs], PAL[0]),
                ("ثبت سفارش رفع تعهدشده", [float(sum(1 for d in dated["DATE"] if half_key(d) == h)) for h in hs], PAL[1])]
        wmed = [_med([w for w, k in waits if k == h]) for h in hs]
        visual += ("<h4>تخصیص و رفع تعهد در هر نیم‌سال (شمار ثبت سفارش)</h4>" + bars_svg(hl, pair, h=200) + legend(pair))
        if any(v is not None for v in wmed):
            visual += ("<h4>میانه روز از نخستین تخصیص تا رفع تعهد (به نیم‌سال رفع)</h4>"
                       + line_svg(hl, [("میانه روز", wmed, PAL[6])], h=170, yfmt=fnum))
            allw = _med([w for w, _ in waits])
            head = (f"{fa(int(settle['STATE'].isin((SETTLED, SETTLED_NO_DATE)).sum()))} ثبت سفارش برای همه "
                    f"بارنامه‌هایش کد رهگیری ساتا دارد (رفع تعهد)؛ میانه نخستین تخصیص تا رفع تعهد {fnum(allw)} روز است.")
        rows += [{"نیم‌سال تعهد": l, "ارز": "", "شمار تعهد": None, "رفع تعهد (٪ مبلغ همان ارز)": None,
                  "ثبت سفارش با نخستین تخصیص": a, "ثبت سفارش رفع تعهدشده": b, "میانه تخصیص تا رفع (روز)": w}
                 for l, a, b, w in zip(hl, pair[0][1], pair[1][1], wmed)]
        nod = int(settle["STATE"].eq(SETTLED_NO_DATE).sum())
        part = int(settle["STATE"].eq(PARTIAL).sum())
        diff = int((settle["STATE"].isin((SETTLED, SETTLED_NO_DATE)) & settle["NTSW_FULL"].eq(False)).sum())
        note_date = ("رفع تعهد = کد رهگیری ساتا برای همه بارنامه‌های ثبت سفارش؛ تاریخ = دیرترین «تاریخ اخذ کد "
                     f"رهگیری». {fa(nod)} ثبت سفارش کد کامل دارد ولی تاریخ همه کدها ثبت نشده (بی‌تاریخ) و "
                     f"{fa(part)} ثبت سفارش فقط برای بخشی از بارنامه‌ها کد دارد. در {fa(diff)} ثبت سفارشِ رفع‌تعهدشده، "
                     "NTSW هنوز رفع کامل نشان نمی‌دهد. ")
    return Chapter("settle", "check", title, head, visual,
                   "دسته‌های قدیمی‌تر باید رفع تعهد بیشتری داشته باشند؛ افت آن‌ها جای پیگیری است.",
                   note=note_date + "درصد هر ارز از مبلغ همان ارز است.",
                   gaps=gaps, table=pd.DataFrame(rows))


def ch_groups(led: pd.DataFrame, reg_group: Dict[str, str]) -> Chapter:
    """فصل ۵: پول و تخصیص به کدام گروه قطعات رفت (سهم در هر نیم‌سال؛ هر ارز جدا)."""
    title = "گروه قطعات: پول به کجا رفت"
    fx = led[led["EVENT_CODE"].eq("FX_PURCHASE") & led["DATE"].notna() & led["AMOUNT"].notna()]
    alloc = led[led["EVENT_CODE"].eq("ALLOCATION") & led["DATE"].notna()]
    if (fx.empty and alloc.empty) or not reg_group:
        gaps = []
        if not reg_group:
            gaps.append("گروه قطعه (PART_GROUP) برای ثبت سفارش‌ها در مارت نیست.")
        if fx.empty and alloc.empty:
            gaps.append("خرید ارز و تخصیص با تاریخ در داده نیست.")
        return _gap_chapter("groups", "layers", title, gaps)
    g = lambda r: reg_group.get(r, NO_GROUP)  # noqa: E731
    visual, rows, head = "", [], ""
    if not fx.empty:
        c = fx["CURRENCY"].value_counts().index[0]
        f = fx[fx["CURRENCY"].eq(c)].assign(G=lambda x: x["KEY_REG"].map(g), H=lambda x: x["DATE"].map(half_key))
        halves = _seq_half(f["H"])
        top = f.groupby("G")["AMOUNT"].sum().sort_values(ascending=False)
        names = top.index.tolist()[:6]
        parts = [(n, [float(f.loc[(f["G"] == n) & (f["H"] == h), "AMOUNT"].sum()) for h in halves], PAL[i % len(PAL)])
                 for i, n in enumerate(names)]
        rest = [float(f.loc[~f["G"].isin(names) & (f["H"] == h), "AMOUNT"].sum()) for h in halves]
        if any(rest):
            parts.append(("سایر", rest, T.TEXT_MUTED))
        visual += f"<h4>سهم هر گروه از خرید {CURRENCY_FA.get(c, c)} در هر نیم‌سال</h4>" + stack100(
            [half_label(h) for h in halves], parts)
        lead = names[0]
        share = 100 * top.iloc[0] / top.sum() if top.sum() else 0
        head = f"بیشترین سهم خرید {CURRENCY_FA.get(c, c)} ({fa(round(share))}٪) به «{lead}» رسیده است."
        rows += [{"ارز": c, "گروه": n, "نیم‌سال": half_label(h), "مبلغ خرید": v}
                 for n, ys, _ in parts for h, v in zip(halves, ys)]
    if not alloc.empty:
        a = alloc.assign(G=lambda x: x["KEY_REG"].map(g), H=lambda x: x["DATE"].map(half_key))
        halves = _seq_half(a["H"])
        top = a["G"].value_counts()
        names = top.index.tolist()[:6]
        cells = "".join(f"<th>{_esc(half_label(h))}</th>" for h in halves)
        mx = max([int(((a["G"] == n) & (a["H"] == h)).sum()) for n in names for h in halves] or [1]) or 1
        body = ""
        for n in names:
            tds = ""
            for h in halves:
                v = int(((a["G"] == n) & (a["H"] == h)).sum())
                tds += (f'<td><span class="ds-heat" style="opacity:{0.15 + 0.85 * v / mx:.2f}">{fa(v) if v else ""}'
                        f"</span></td>")
                rows.append({"گروه": n, "نیم‌سال": half_label(h), "شمار تخصیص": v})
            body += f"<tr><th>{_esc(n)}</th>{tds}</tr>"
        visual += f'<h4>شمار تخصیص هر گروه در هر نیم‌سال</h4><div class="ds-scroll"><table class="ds-heatt"><tr><th></th>{cells}</tr>{body}</table></div>'
        if not head:
            head = f"بیشترین شمار تخصیص به «{names[0]}» بوده است."
    multi = sum(1 for v in reg_group.values() if v == MULTI_GROUP)
    return Chapter("groups", "layers", title, head, visual,
                   "گروهی که سهمش بالا رفته و قطعه بحرانی هم دارد، داستان درستی است؛ سهم بالا بدون قطعه بحرانی جای پرسش است.",
                   note=(f"ثبت سفارشی که قطعاتش در چند گروه‌اند به یک گروه نسبت داده نمی‌شود («{MULTI_GROUP}»؛ "
                         f"{fa(multi)} ثبت سفارش). سهم پول فقط در یک ارز."),
                   table=pd.DataFrame(rows))


def ch_critical(df: pd.DataFrame, led: pd.DataFrame, reg_level: Dict[str, str], stage_of_reg: Dict[str, str]) -> Chapter:
    """فصل ۶: با چقدر پول مشکل قطعات بحرانی حل می‌شود، و پول به کدام سطح بحرانی رفت."""
    title = "قطعات بحرانی: هزینه حل مشکل"
    gaps = ["«خرید غیرضروری» برچسب منبعی ندارد؛ نشانه‌اش سطح بحرانی ثبت سفارش در زمان خرید است که در فصل «قطعات "
            "بحرانی در گذر زمان» از نخستین Snapshot انبار به بعد آمده؛ خریدهای پیش از آن سطحی ندارند."]
    if df is None or df.empty or "کد طبقه بحرانی" not in df.columns:
        return _gap_chapter("critical", "alert", title, ["سطح بحرانی در مارت نیست."] + gaps)
    x = pd.DataFrame({"O": _col(df, "KEY_ORDER"), "M": _col(df, "KEY_MATERIAL"), "L": _col(df, "کد طبقه بحرانی"),
                      "V": pd.to_numeric(df.get("MOGH_PI_VALUE_SUM"), errors="coerce") if "MOGH_PI_VALUE_SUM" in df
                      else float("nan"),
                      "C": _col(df, "MOGH_CURRENCY").str.upper(), "R": _col(df, "KEY_REG"),
                      "F": df["IS_FULL_CLEARED"].map(X.truthy) if "IS_FULL_CLEARED" in df else False})
    x = x[x["O"].ne("") & x["M"].ne("")].drop_duplicates(subset=["O", "M"])
    crit = x[x["L"].isin(CRITICAL_LEVELS) & ~x["F"]]
    unk = int(x["L"].eq("UNKNOWN").sum())
    if crit.empty:
        head = "هیچ قطعه بحرانی باز (ترخیص‌نشده) در این دامنه نیست."
        visual = ""
    else:
        by_cur = crit[crit["V"].notna() & crit["C"].ne("")].groupby("C")["V"].sum()
        nval = int((crit["V"].isna() | crit["C"].eq("")).sum())
        if len(by_cur):
            head = (f"{fa(len(crit))} قطعه بحرانی هنوز ترخیص نشده؛ ارزش PI آن‌ها "
                    + "، ".join(money(v, c) for c, v in by_cur.items()) + " است"
                    + (f" و {fa(nval)} قلم ارزش PI ندارد" if nval else "") + ".")
        else:
            head = f"{fa(len(crit))} قطعه بحرانی هنوز ترخیص نشده؛ ارزش PI هیچ‌کدام در داده نیست."
        stages = crit["R"].map(lambda r: stage_of_reg.get(r, "") or "مرحله نامعلوم").value_counts()
        lv = crit["L"].value_counts()
        visual = (f'<div class="ds-grid2"><div><h4>کجای مسیرند (شمار قلم)</h4>'
                  f'{hbars([(s, float(n), fa(n)) for s, n in stages.items()], T.STATUS["critical"].fill)}</div>'
                  f'<div><h4>کدام سطح</h4>{hbars([(LEVEL_FA.get(k, k), float(n), fa(n)) for k, n in lv.items()], T.STATUS["serious"].fill)}'
                  f'</div></div>')
        cards = "".join(f'<div class="ds-money"><b>{_esc(compact(v))}</b><span>{_esc(CURRENCY_FA.get(c, c))}</span></div>'
                        for c, v in by_cur.items())
        if cards:
            visual = f'<h4>ارزش PI قطعات بحرانی باز، هر ارز جدا</h4><div class="ds-moneys">{cards}</div>' + visual
    fx = led[led["EVENT_CODE"].eq("FX_PURCHASE") & led["AMOUNT"].notna()]
    if not fx.empty and reg_level:
        c = fx["CURRENCY"].value_counts().index[0]
        f = fx[fx["CURRENCY"].eq(c)].assign(Lv=lambda z: z["KEY_REG"].map(lambda r: reg_level.get(r, "UNKNOWN")))
        tot = f["AMOUNT"].sum()
        order = [*CRITICAL_LEVELS, "WATCH", "SAFE", "NO_CONSUMPTION", "UNKNOWN"]
        items = [(LEVEL_FA[k], float(f.loc[f["Lv"].eq(k), "AMOUNT"].sum()),
                  f"{fa(round(100 * f.loc[f['Lv'].eq(k), 'AMOUNT'].sum() / tot))}٪") for k in order
                 if tot and f["Lv"].eq(k).any()]
        visual += (f"<h4>خرید {CURRENCY_FA.get(c, c)} به تفکیک سطح بحرانی امروزِ ثبت سفارش</h4>"
                   + hbars(items, T.TEAL_PALETTE[5]))
    rows = crit.rename(columns={"O": "سفارش", "M": "متریال", "L": "سطح", "V": "ارزش PI", "C": "ارز", "R": "ثبت سفارش"})
    rows = rows.drop(columns=["F"]) if "F" in rows else rows
    return Chapter("critical", "alert", title, head, visual,
                   "ارزش بالا و مرحله «صف تخصیص» یعنی بیشترین اثر تصمیم ارزی همین‌جاست.",
                   note=(f"ارزش PI هر قلم یک بار، به ارز خودش. سطح بحرانی این فصل امروز است، نه زمان خرید؛ سطح در زمان "
                         f"خرید در فصل بعد است. {fa(unk)} قلم سطح نامشخص دارد."),
                   gaps=gaps, table=rows, tone="critical")


# ─────────────── قطعات بحرانی در گذر زمان (Snapshotهای منتشرشده انبار) ───────────────
def jdate(d: date) -> str:
    return fa(format_jalali(d))


HISTORY_COLS = ("KEY_ORDER", "CANONICAL_ORDER", "KEY_MATERIAL", "KEY_REG", "کد طبقه بحرانی", "PART_GROUP", "SUPPLY_GROUP")
LEVEL_RANK = {"STOCKOUT": 0, "CRITICAL": 1, "BECOMING_CRITICAL": 2}


def history_frame(df: pd.DataFrame) -> pd.DataFrame:
    """هر سفارش × متریال یک بار، با سطح بحرانی و گروه همان Snapshot."""
    if df is None or df.empty or "کد طبقه بحرانی" not in df.columns:
        return pd.DataFrame(columns=["K", "L", "G", "R"])
    o, m = _col(df, "KEY_ORDER", "CANONICAL_ORDER"), _col(df, "KEY_MATERIAL")
    x = pd.DataFrame({"K": o + "|" + m, "L": _col(df, "کد طبقه بحرانی"), "G": _col(df, "PART_GROUP", "SUPPLY_GROUP"),
                      "R": _col(df, "KEY_REG")})
    x = x[o.ne("") & m.ne("")]
    # یک قلم با چند ردیف: بدترین سطح همان Snapshot (همان قاعده گزارش‌ها)
    return (x.assign(_r=x["L"].map(lambda v: LEVEL_RANK.get(v, 9))).sort_values("_r")
            .drop_duplicates("K").drop(columns="_r").reset_index(drop=True))


def load_critical_history(limit: int = 400) -> List[Tuple[date, pd.DataFrame]]:
    """از انبار: هر Snapshot منتشرشده یک نقطه (آخرین انتشار هر تاریخ مرجع)، فقط ستون‌های لازم.

    انبار هیچ Snapshotی را پاک نمی‌کند؛ پس تاریخچه از نخستین Refresh انبار نسخه ۲ شروع می‌شود و با هر
    Refresh یک نقطه بیشتر دارد. هر خطا = تاریخچه خالی (فصل «داده کافی نیست» می‌گوید)، نه شکست صفحه.
    """
    try:
        from ..warehouse.framecodec import decode_columns
        from ..warehouse.store import Warehouse, loads
        wh = Warehouse(initialize=False)              # خواننده هرگز ساختار انبار را نمی‌سازد
        if not wh.path.exists():
            return []
        with wh.read_db(bind=False) as c:
            rows = c.execute(
                "SELECT r.seq,r.context,f.object_sha FROM wh_run r JOIN wh_frame f ON f.run_id=r.id "
                "WHERE f.layer='mart' AND f.name='df' AND r.id IN (SELECT run_id FROM wh_publish_event) "
                "ORDER BY r.seq").fetchall()
        latest: Dict[date, str] = {}
        for _, ctx, sha in rows:
            try:
                d = _d((loads(ctx) or {}).get("reference_date"))
            except Exception:
                d = None
            if d:
                latest[d] = sha
        out = []
        for d in sorted(latest)[-limit:]:
            out.append((d, history_frame(decode_columns(wh.objects.get(latest[d], "parquet"), HISTORY_COLS))))
        return out
    except Exception:
        return []


def _thin(runs: List[Tuple[date, pd.DataFrame]], max_points: int = 24) -> List[Tuple[date, pd.DataFrame]]:
    """بیش از ۲۴ نقطه: آخرین Snapshot هر ماه شمسی (روند خوانا می‌ماند)."""
    if len(runs) <= max_points:
        return runs
    last: Dict[Tuple[int, int], Tuple[date, pd.DataFrame]] = {}
    for d, f in runs:
        jy, jm, _ = jparts(d)
        last[(jy, jm)] = (d, f)
    return [last[k] for k in sorted(last)]


def ch_critical_history(runs: List[Tuple[date, pd.DataFrame]], led: Optional[pd.DataFrame] = None) -> Chapter:
    """فصل: اقلام توقف خط، بحرانی و در حال بحرانی شدن در هر Snapshot و جابه‌جایی‌شان."""
    title = "قطعات بحرانی در گذر زمان"
    runs = [(d, f) for d, f in sorted(runs, key=lambda t: t[0]) if f is not None and not f.empty]
    if len(runs) < 2:
        n = len(runs)
        msg = (f"تاریخچه سطح بحرانی از Snapshotهای منتشرشده انبار ساخته می‌شود و اکنون {fa(n)} Snapshot هست؛ "
               "با هر Refresh یک نقطه اضافه می‌شود و از دومین نقطه روند دیده می‌شود.")
        visual = ""
        if n:
            d, f = runs[0]
            visual = (f"<h4>وضعیت امروز ({_esc(jdate(d))})، شمار سفارش × متریال</h4>"
                      + hbars([(LEVEL_FA[k], float(f["L"].eq(k).sum()), fa(int(f["L"].eq(k).sum())))
                               for k in CRITICAL_LEVELS], T.STATUS["critical"].fill))
        return Chapter("crit_hist", "calendar", title, msg, visual, gaps=[msg], tone="unknown")
    pts = _thin(runs)
    labels = [jdate(d) for d, _ in pts]
    tone = {"STOCKOUT": T.STATUS["stockout"].fill, "CRITICAL": T.STATUS["critical"].fill,
            "BECOMING_CRITICAL": T.STATUS["serious"].fill}
    ser = [(LEVEL_FA[k], [float(f["L"].eq(k).sum()) for _, f in pts], tone[k]) for k in CRITICAL_LEVELS]
    unk = [int(f["L"].eq("UNKNOWN").sum()) for _, f in pts]
    (d0, f0), (d1, f1) = runs[0], runs[-1]
    a, b = f0.set_index("K")["L"], f1.set_index("K")["L"]
    crit0, crit1 = set(a[a.isin(CRITICAL_LEVELS)].index), set(b[b.isin(CRITICAL_LEVELS)].index)
    both = crit0 & crit1
    worse = sum(1 for k in both if LEVEL_RANK[b[k]] < LEVEL_RANK[a[k]])
    better = sum(1 for k in both if LEVEL_RANK[b[k]] > LEVEL_RANK[a[k]])
    gone = crit0 - crit1
    out_safe = sum(1 for k in gone if k in b.index and b[k] in ("WATCH", "SAFE", "NO_CONSUMPTION"))
    out_unknown = len(gone) - out_safe
    new = len(crit1 - crit0)
    # ماندگاری: از نخستین Snapshot پیاپی که قلم بحرانی بوده تا آخرین (کران پایین؛ تاریخچه از نخستین Snapshot است)
    since: Dict[str, date] = {}
    prev: set = set()
    for d, f in runs:
        cur = set(f.loc[f["L"].isin(CRITICAL_LEVELS), "K"])
        since = {k: since.get(k, d) if k in prev else d for k in cur}
        prev = cur
    days = {k: (d1 - v).days for k, v in since.items()}
    g1 = f1.set_index("K")["G"]
    grp = defaultdict(list)
    for k, v in days.items():
        grp[g1.get(k, "") or NO_GROUP].append(v)
    persist = sorted(((g, _med(v), len(v)) for g, v in grp.items()), key=lambda t: -(t[1] or 0))[:8]
    s0 = {k: int(a.eq(k).sum()) for k in CRITICAL_LEVELS}
    s1 = {k: int(b.eq(k).sum()) for k in CRITICAL_LEVELS}
    def _move(lab: str, k: str) -> str:
        return (f"{lab} در {fa(s1[k])} ماند" if s0[k] == s1[k] else f"{lab} از {fa(s0[k])} به {fa(s1[k])} رسید")
    head = (f"از {jdate(d0)} تا {jdate(d1)}، {_move('اقلام توقف خط', 'STOCKOUT')} و "
            f"{_move('اقلام بحرانی', 'CRITICAL')}.")
    flow = [("تازه وارد وضعیت بحرانی", new, "critical"), ("بدتر شد (یک پله به سوی توقف خط)", worse, "critical"),
            ("بهتر شد ولی هنوز بحرانی", better, "warning"), ("از وضعیت بحرانی بیرون آمد", out_safe, "good"),
            ("سطحش نامشخص شد (نه بهبود)", out_unknown, "unknown"), ("در هر دو تاریخ بحرانی", len(both), "neutral")]
    cards = "".join(f'<div class="ds-flow is-{t}"><b>{fa(n)}</b><span>{_esc(lab)}</span></div>' for lab, n, t in flow)
    visual = ("<h4>شمار اقلام در هر سطح، در هر Snapshot (سفارش × متریال)</h4>"
              + bars_svg(labels, ser, h=220, stacked=True) + legend(ser)
              + f"<h4>از {_esc(jdate(d0))} تا {_esc(jdate(d1))}</h4><div class=\"ds-flows\">{cards}</div>")
    if persist:
        visual += ("<h4>اقلام بحرانی امروز: میانه روزهای پیاپی در وضعیت بحرانی، به تفکیک گروه</h4>"
                   + hbars([(g, v, f"{fa(n)} قلم، میانه {fnum(v)} روز") for g, v, n in persist], T.STATUS["critical"].fill))
    visual += _purchase_level_at_time(runs, led)
    rows = [{"Snapshot": l, **{LEVEL_FA[k]: int(v[i]) for k, (_, v, _) in zip(CRITICAL_LEVELS, ser)}, "سطح نامشخص": u}
            for i, (l, u) in enumerate(zip(labels, unk))]
    return Chapter("crit_hist", "calendar", title, head, visual,
                   "قلمی که چند Snapshot پیاپی بحرانی مانده و سطحش بدتر شده، اولویت تصمیم ارزی و حمل است.",
                   note=(f"هر نقطه یک Snapshot منتشرشده انبار است ({fa(len(runs))} Snapshot"
                         + ("؛ بیش از ۲۴ نقطه، آخرین Snapshot هر ماه" if len(pts) < len(runs) else "")
                         + "). سطح بحرانی همان سطح محاسبه‌شده در آن Snapshot است. خروج به «نامشخص» بهبود شمرده "
                         "نمی‌شود. روزهای پیاپی کران پایین است، چون تاریخچه از نخستین Snapshot انبار شروع می‌شود."),
                   table=pd.DataFrame(rows), tone="critical")


def _purchase_level_at_time(runs: List[Tuple[date, pd.DataFrame]], led: Optional[pd.DataFrame]) -> str:
    """خرید ارز به تفکیک سطح بحرانیِ ثبت سفارش **در زمان خرید** (آخرین Snapshot هم‌روز یا پیش از خرید).

    خرید پیش از نخستین Snapshot سطحی ندارد و کنار گذاشته می‌شود. «بی‌قلم بحرانی در زمان خرید» داوری
    درباره ضرورت نیست (خرید برنامه‌ای هم همین‌جاست)؛ فقط وضعیت را نشان می‌دهد. فقط ارز پرشمارتر.
    """
    if led is None or led.empty or not runs:
        return ""
    fx = led[led["EVENT_CODE"].eq("FX_PURCHASE") & led["DATE"].notna() & led["AMOUNT"].notna()]
    fx = fx[fx["DATE"] >= runs[0][0]]
    if fx.empty:
        return ""
    by_run = []
    for d, f in runs:
        lv = {r: (X.worst_level(part["L"]) or "UNKNOWN") for r, part in f[f["R"].ne("")].groupby("R")} \
            if "R" in f.columns else {}
        by_run.append((d, lv))
    def level(reg, d):
        cur = None
        for rd, lv in by_run:
            if rd > d:
                break
            cur = lv
        return (cur or {}).get(reg, "UNKNOWN")
    c = fx["CURRENCY"].value_counts().index[0]
    f = fx[fx["CURRENCY"].eq(c)]
    f = f.assign(Lv=[level(r, d) for r, d in zip(f["KEY_REG"], f["DATE"])])
    tot = f["AMOUNT"].sum()
    if not tot:
        return ""
    crit = f["Lv"].isin(CRITICAL_LEVELS)
    items = [("ثبت سفارش با قلم بحرانی در زمان خرید", float(f.loc[crit, "AMOUNT"].sum())),
             ("بی‌قلم بحرانی در زمان خرید", float(f.loc[f["Lv"].isin(("WATCH", "SAFE", "NO_CONSUMPTION")), "AMOUNT"].sum())),
             ("سطح نامشخص در زمان خرید", float(f.loc[f["Lv"].eq("UNKNOWN"), "AMOUNT"].sum()))]
    return (f"<h4>خرید {_esc(CURRENCY_FA.get(c, c))} از {_esc(jdate(runs[0][0]))}، به سطح بحرانی در زمان خرید</h4>"
            + hbars([(lab, v, f"{fa(round(100 * v / tot))}٪ ({money(v, c)})") for lab, v in items if v],
                    T.TEAL_PALETTE[5]))


def _ship_rows(model) -> pd.DataFrame:
    """یک ردیف برای هر بارنامه با تاریخ ایستگاه‌های تاریخ‌دار (فقط شاهد قطعی، نه متعارض)."""
    j = getattr(model, "journey", None)
    if j is None or j.rows.empty:
        return pd.DataFrame(columns=["BL", "SHIP", "ARRIVE", "DISCHARGE", "COTAGE", "CLEAR", "CUR_ST"])
    recs = []
    for _, r in j.rows.iterrows():
        c = r["_CELLS"]
        g = lambda k: c[k]["date"] if c[k]["state"] in ("dated",) else None  # noqa: E731
        recs.append({"BL": r["بارنامه"], "SHIP": g("SHIP"), "ARRIVE": g("ARRIVE"), "DISCHARGE": g("DISCHARGE"),
                     "COTAGE": g("COTAGE"), "CLEAR": g("CLEAR"), "CUR_ST": r["_CUR"]})
    return pd.DataFrame(recs)


def ch_shipping(ship: pd.DataFrame, bl_group: Dict[str, str], as_of: date) -> Chapter:
    """فصل ۷: زمان حمل در سال‌های مختلف و کدام گروه قطعات بیشتر از تخلیه تا کوتاژ و ترخیص ماند."""
    title = "حمل: از تخلیه تا ترخیص"
    if ship.empty or ship["DISCHARGE"].isna().all():
        return _gap_chapter("ship", "ship", title, ["تاریخ تخلیه بارنامه‌ها در داده نیست."])
    s = ship.copy()
    s["Y"] = s["DISCHARGE"].map(lambda d: jparts(d)[0] if d else None)
    s["DC"] = [(c - d).days if c and d and c >= d else None for d, c in zip(s["DISCHARGE"], s["COTAGE"])]
    s["DX"] = [(c - d).days if c and d and c >= d else None for d, c in zip(s["DISCHARGE"], s["CLEAR"])]
    s["AD"] = [(d - a).days if a and d and d >= a else None for a, d in zip(s["ARRIVE"], s["DISCHARGE"])]
    s["OPEN"] = [(as_of - d).days if d and not c and as_of >= d else None for d, c in zip(s["DISCHARGE"], s["CLEAR"])]
    years = sorted(y for y in s["Y"].dropna().unique())
    labels = [fa(int(y)) for y in years]
    ser = [("تخلیه تا کوتاژ", [_med(s.loc[s["Y"].eq(y), "DC"].tolist()) for y in years], PAL[2]),
           ("تخلیه تا ترخیص کامل", [_med(s.loc[s["Y"].eq(y), "DX"].tolist()) for y in years], PAL[0])]
    dx = [(l, v) for l, v in zip(labels, ser[1][1]) if v is not None]
    if len(dx) >= 2:
        head = f"میانه تخلیه تا ترخیص کامل از {fnum(dx[0][1])} روز در {dx[0][0]} به {fnum(dx[-1][1])} روز در {dx[-1][0]} رسید."
    elif dx:
        head = f"میانه تخلیه تا ترخیص کامل در {dx[0][0]}: {fnum(dx[0][1])} روز."
    else:
        head = (f"{fa(int(s['OPEN'].notna().sum()))} بارنامه تخلیه‌شده هنوز ترخیص کامل ندارد؛ میانه ماندن "
                f"{fnum(_med(s['OPEN'].tolist()))} روز.")
    s["G"] = s["BL"].map(lambda b: bl_group.get(b, NO_GROUP))
    grp = []
    for gname, part in s.groupby("G"):
        done = _med(part["DX"].tolist())
        opn = _med(part["OPEN"].tolist())
        grp.append((gname, done, opn, int(part["DISCHARGE"].notna().sum())))
    grp_done = sorted([g for g in grp if g[1] is not None], key=lambda g: -g[1])[:8]
    grp_open = sorted([g for g in grp if g[2] is not None], key=lambda g: -g[2])[:8]
    visual = ""
    if any(v is not None for _, ys, _ in ser for v in ys):
        visual += "<h4>میانه روز در هر سال (سال تخلیه)</h4>" + bars_svg(labels, ser, h=200) + legend(ser)
    if grp_open:
        visual += ("<h4>بارنامه‌های باز: میانه روز از تخلیه تا امروز، به تفکیک گروه</h4>"
                   + hbars([(g, v, fnum(v) + " روز") for g, _, v, _ in grp_open], T.STATUS["serious"].fill))
    if grp_done:
        visual += ("<h4>ترخیص‌شده‌ها: میانه روز تخلیه تا ترخیص کامل، به تفکیک گروه</h4>"
                   + hbars([(g, v, fnum(v) + " روز") for g, v, _, _ in grp_done], T.TEAL_PALETTE[5]))
    insight = (f"بیشترین ماندن پس از تخلیه در گروه «{grp_open[0][0]}» است." if grp_open else
               "همه بارنامه‌های تخلیه‌شده این دامنه ترخیص شده‌اند.")
    rows = [{"گروه": g, "میانه تخلیه تا ترخیص (روز)": d, "میانه روز باز از تخلیه": o, "بارنامه تخلیه‌شده": n}
            for g, d, o, n in grp]
    return Chapter("ship", "ship", title, head, visual, insight,
                   note=("فقط تاریخ‌های قطعی مسیر شواهد (نه متعارض). بارنامه‌ای که قطعه چند گروه را دارد در «چند گروه» "
                         "است. علت ماندن از زمان استنتاج نمی‌شود."),
                   table=pd.DataFrame(rows))


PERIOD_BASE = "پیش از ۱۴۰۴"


def _period(d: date) -> str:
    return PERIOD_BASE if d < START_1404 else half_label(half_key(d))


def ch_since_1404(led: pd.DataFrame, ship: pd.DataFrame, as_of: date,
                  settle: Optional[pd.DataFrame] = None) -> Tuple[Chapter, List[Tuple[str, str, str]]]:
    """فصل ۸: از ابتدای ۱۴۰۴ چه تغییر کرد (هم‌زمانی، نه علت) و نشان‌های پیشرفت.

    کارت هر شاخص «از ۱۴۰۴» را با «پیش از ۱۴۰۴» می‌سنجد، هر دو تجمیعی: میانه همه رویدادهای دوره، پذیرش
    تجمیعی، و برای شمارها میانگین هر نیم‌سال (نیم‌سال جاری ناقص است و در میانگین نمی‌آید). روند هر نیم‌سال در
    نمودار کوچک کارت و جدول فصل است.
    """
    title = "از ۱۴۰۴ تا امروز: اثر تغییرات"
    req = led[led["EVENT_CODE"].isin(REQUEST_CODES) & led["DATE"].notna()]
    alloc = led[led["EVENT_CODE"].eq("ALLOCATION") & led["DATE"].notna()]
    fxp = led[led["EVENT_CODE"].eq("FX_PURCHASE") & led["DATE"].notna()]
    rq_date = {r: d for r, d in zip(req["REFERENCE"], req["DATE"]) if r}
    cur_half = half_key(as_of)
    after_keys = _seq_half([half_key(START_1404), cur_half])
    halves = [PERIOD_BASE] + [half_label(h) for h in after_keys]
    complete_after = [half_label(h) for h in after_keys if h != cur_half]
    # انتظار تخصیص (به دوره تخصیص)
    w = defaultdict(list)
    for r, d in zip(alloc["REFERENCE"], alloc["DATE"]):
        s0 = rq_date.get(r)
        if s0 and d >= s0:
            w[_period(d)].append((d - s0).days)
    # پذیرش درخواست (به دوره درخواست): تخصیص‌یافته ÷ (تخصیص‌یافته + رد یا بسته‌شده)
    acc, dec = Counter(), Counter()
    allocated_refs = set(alloc["REFERENCE"])
    for code, r, d in zip(req["EVENT_CODE"], req["REFERENCE"], req["DATE"]):
        p = _period(d)
        if r in allocated_refs:
            acc[p] += 1
            dec[p] += 1
        elif code != "ALLOCATION_REQUEST":
            dec[p] += 1
    clr = defaultdict(list)
    for d, c in zip(ship.get("DISCHARGE", []), ship.get("CLEAR", [])):
        if d and c and c >= d:
            clr[_period(c)].append((c - d).days)
    # نخستین تخصیص تا رفع تعهد (به دوره رفع؛ تاریخ اخذ کد رهگیری ساتا)
    stl = defaultdict(list)
    if settle is not None and not settle.empty:
        for d, a in zip(settle["DATE"], settle["FIRST_ALLOC"]):
            if isinstance(d, date) and isinstance(a, date) and d >= a:
                stl[_period(d)].append((d - a).days)
    counts = {"alloc_n": alloc["DATE"], "fx_n": fxp["DATE"],
              "clear_n": pd.Series([c for d, c in zip(ship.get("DISCHARGE", []), ship.get("CLEAR", []))
                                    if d and c and c >= d], dtype=object)}
    m: Dict[str, Dict[str, Optional[float]]] = {p: {} for p in halves}
    for p in halves:
        m[p]["wait"] = _med(w.get(p, []))
        m[p]["accept"] = (100 * acc[p] / dec[p]) if dec[p] else None
        m[p]["clear"] = _med(clr.get(p, []))
        m[p]["settle"] = _med(stl.get(p, []))
        for k, ds in counts.items():          # منبعِ بی‌رویداد = بی‌داده، نه صفر
            m[p][k] = float(sum(1 for d in ds if _period(d) == p)) if len(ds) else None

    def pooled(key: str) -> Tuple[Optional[float], Optional[float]]:
        """(پیش از ۱۴۰۴، از ۱۴۰۴) تجمیعی."""
        after = halves[1:]
        if key in ("wait", "clear", "settle"):
            src = {"wait": w, "clear": clr, "settle": stl}[key]
            return (_med(src.get(PERIOD_BASE, [])), _med([v for p in after for v in src.get(p, [])]))
        if key == "accept":
            da, aa = sum(dec[p] for p in after), sum(acc[p] for p in after)
            return ((100 * acc[PERIOD_BASE] / dec[PERIOD_BASE]) if dec[PERIOD_BASE] else None,
                    (100 * aa / da) if da else None)
        ds = [d for d in counts[key] if d]
        if not ds:
            return None, None
        before = [d for d in ds if d < START_1404]
        base = None
        if before:
            n_base = len(_seq_half([half_key(min(before)), half_key(START_1404) - 9]))   # تا نیمه دوم ۱۴۰۳
            base = len(before) / n_base
        aft = (sum(m[p][key] or 0 for p in complete_after) / len(complete_after)) if complete_after else None
        return base, aft

    metrics = [("wait", "میانه انتظار تخصیص", -1, " روز"), ("accept", "پذیرش درخواست تخصیص", 1, "٪"),
               ("clear", "میانه تخلیه تا ترخیص کامل", -1, " روز"),
               ("settle", "میانه نخستین تخصیص تا رفع تعهد", -1, " روز"),
               ("alloc_n", "شمار تخصیص در هر نیم‌سال", 1, ""), ("fx_n", "شمار خرید ارز در هر نیم‌سال", 1, ""),
               ("clear_n", "بارنامه ترخیص‌شده در هر نیم‌سال", 1, "")]
    rows, better, worse, cards = [], [], [], []
    for key, lab, good, unit in metrics:
        vals = [m[p][key] for p in halves]
        if all(v is None for v in vals):
            continue
        base, last = pooled(key)
        delta = (last - base) if base is not None and last is not None else None
        if delta and delta * good > 0:
            better.append((lab, base, last, unit))
        elif delta and delta * good < 0:
            worse.append((lab, base, last, unit))
        tone = "good" if delta and delta * good > 0 else "critical" if delta and delta * good < 0 else "neutral"
        arrow = "▲" if delta and delta > 0 else "▼" if delta and delta < 0 else "●"
        nd = 1 if key.endswith("_n") and ((last or 0) % 1 or (base or 0) % 1) else 0
        spark = line_svg([fa(p) for p in halves], [(lab, vals, PAL[0])], w=300, h=96, yfmt=fnum, pct=key == "accept",
                         axis=False)
        cards.append(f'<div class="ds-kpi is-{tone}"><span class="ds-kpi-l">{_esc(lab)}</span>'
                     f'<b>{_esc(fnum(last, nd) + unit if last is not None else "—")}</b>'
                     f'<span class="ds-kpi-d">{arrow} پیش از ۱۴۰۴: '
                     f'{_esc(fnum(base, nd) + unit if base is not None else "بی‌داده")}</span>{spark}'
                     f'<span class="ds-kpi-x"><span>{_esc(halves[-1])}</span><span>{PERIOD_BASE}</span></span></div>')
        rows.append({"شاخص": lab, **{p: v for p, v in zip(halves, vals)}, "از ۱۴۰۴ (تجمیعی)": last})
    if not rows:
        return _gap_chapter("since", "trend", title, ["رویداد تاریخ‌دار برای مقایسه دوره‌ها در داده نیست."]), []
    if better:
        b = better[0]
        nd = 1 if "نیم‌سال" in b[0] else 0
        head = (f"از ابتدای ۱۴۰۴، {fa(len(better))} شاخص بهتر شده" + (f" و {fa(len(worse))} شاخص بدتر" if worse else "")
                + f"؛ «{b[0]}» از {fnum(b[1], nd)}{b[3]} به {fnum(b[2], nd)}{b[3]} رسید.")
    elif worse:
        head = f"از ابتدای ۱۴۰۴، {fa(len(worse))} شاخص بدتر شده و شاخص بهترشده‌ای با مبنای پیش از ۱۴۰۴ دیده نمی‌شود."
    else:
        head = "برای مقایسه با پیش از ۱۴۰۴، داده دوره مبنا کافی نیست؛ روند دوره‌های ۱۴۰۴ به بعد آمده است."
    badges = _badges(m, halves)
    visual = f'<div class="ds-kpis">{"".join(cards)}</div>'
    return Chapter("since", "trend", title, head, visual,
                   "این مقایسه هم‌زمانی را نشان می‌دهد، نه علت را؛ شرایط جنگی، قاعده‌های تازه و حجم کار همه با هم اثر دارند.",
                   note=("عدد درشت هر کارت «از ۱۴۰۴» تجمیعی است و با «پیش از ۱۴۰۴» سنجیده می‌شود؛ شمارها میانگین هر "
                         "نیم‌سال‌اند و نیم‌سال جاری (ناقص) در میانگین نمی‌آید. پذیرش = تخصیص‌یافته ÷ (تخصیص‌یافته + رد "
                         "یا بسته‌شده). نمودار کوچک روند هر نیم‌سال است."),
                   table=pd.DataFrame(rows), tone="good" if len(better) >= len(worse) else "warning"), badges


def _badges(m: Dict[str, Dict[str, Optional[float]]], halves: List[str]) -> List[Tuple[str, str, str]]:
    """نشان‌های پیشرفت (گیمیفیکیشن): فقط از همین عددها، بی‌حدس."""
    out = []
    after = halves[1:]
    for key, lab, good, icon in (("clear", "ترخیص سریع‌تر", -1, "ship"), ("wait", "صف کوتاه‌تر", -1, "queue")):
        vals = [(p, m[p][key]) for p in after if m[p][key] is not None]
        streak = 0
        for (_, a), (_, b) in zip(vals, vals[1:]):
            streak = streak + 1 if (b - a) * good > 0 else 0
        if streak >= 1:
            out.append((icon, f"{lab}: {fa(streak)} نیم‌سال پیاپی", "good"))
        if vals:
            best = min(vals, key=lambda x: x[1] * -good)
            out.append(("flag", f"بهترین {lab.split()[0]}: {best[0]} ({fnum(best[1])} روز)", "brand"))
    acc = [(p, m[p]["accept"]) for p in after if m[p]["accept"] is not None]
    if acc and acc[-1][1] >= 80:
        out.append(("check", f"پذیرش تخصیص {fa(round(acc[-1][1]))}٪ در {acc[-1][0]}", "good"))
    return out


# ═══════════════════════════════ ساخت داستان ═══════════════════════════════
def _bl_values(df: pd.DataFrame) -> Dict[str, Tuple[Optional[float], str]]:
    if df is None or df.empty or "CANONICAL_BL" not in df.columns or "BLREG_BL_INVOICE_VALUE" not in df.columns:
        return {}
    out = {}
    for bl, part in df.groupby(df["CANONICAL_BL"].map(X.s)):
        if not bl:
            continue
        v = pd.to_numeric(part["BLREG_BL_INVOICE_VALUE"], errors="coerce").dropna().unique()
        c = {X.s(x).upper() for x in _col(part, "BLREG_BL_CURRENCY")} - {""}
        out[bl] = (float(v[0]) if len(v) == 1 and len(c) == 1 else None, next(iter(c)) if len(c) == 1 else "")
    return out


def _stage_of_reg(extras: Any) -> Dict[str, str]:
    try:
        lc = extras.get("fx_lifecycle") if extras is not None else None
    except Exception:
        lc = None
    if not isinstance(lc, pd.DataFrame) or lc.empty or "CURRENT_STAGE" not in lc.columns:
        return {}
    return {X.s(k): X.s(v) for k, v in zip(lc["KEY_REG"], lc["CURRENT_STAGE"])}


def build_story(df: Optional[pd.DataFrame], extras: Any = None, ref_date: Any = "", shipping_model: Any = None,
                critical_runs: Optional[List[Tuple[date, pd.DataFrame]]] = None) -> Story:
    """همه فصل‌ها از Snapshot منتشرشده. ``shipping_model`` اگر داده نشود از گزارش حمل ساخته می‌شود."""
    as_of = _d(ref_date) or date.today()
    df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    led = ledger(extras)
    if shipping_model is None and not df.empty:
        from . import shipping_clearance_report as SC
        shipping_model = SC.build_model(df, extras, ref_date)
    ship = _ship_rows(shipping_model) if shipping_model is not None else _ship_rows(None)
    vals = _bl_values(df)
    bls = pd.DataFrame([{"BL": b, "DISCHARGE": d, "VALUE": vals.get(b, (None, ""))[0], "CUR": vals.get(b, (None, ""))[1]}
                        for b, d in zip(ship.get("BL", []), ship.get("DISCHARGE", []))]) if not ship.empty else \
        pd.DataFrame(columns=["BL", "DISCHARGE", "VALUE", "CUR"])
    reg_group = groups_of(df, "KEY_REG")
    bl_group = groups_of(df.assign(CANONICAL_BL=_col(df, "CANONICAL_BL", "KEY_BL")) if not df.empty else df,
                         "CANONICAL_BL")
    settle = sata_settlement(df, led)
    since, badges = ch_since_1404(led, ship, as_of, settle)
    chapters = [since, ch_money(led), ch_money_goods(led, bls), ch_queue(led, as_of), ch_settlement(led, settle),
                ch_groups(led, reg_group), ch_critical(df, led, level_of_reg(df), _stage_of_reg(extras)),
                ch_critical_history(critical_runs if critical_runs is not None else load_critical_history(), led),
                ch_shipping(ship, bl_group, as_of)]
    chapters.append(_gaps_chapter(chapters))
    fx = led[led["EVENT_CODE"].eq("FX_PURCHASE") & led["DATE"].notna()]
    al = led[led["EVENT_CODE"].eq("ALLOCATION") & led["DATE"].notna()]
    cleared = ship[ship["CLEAR"].notna()] if not ship.empty else ship
    hero = [("coins", fa(int((fx["DATE"] >= START_1404).sum())), "خرید ارز از ابتدای ۱۴۰۴"),
            ("exchange", fa(int((al["DATE"] >= START_1404).sum())), "تخصیص از ابتدای ۱۴۰۴"),
            ("ship", fa(int(sum(1 for c in cleared.get("CLEAR", []) if c and c >= START_1404))),
             "بارنامه ترخیص‌شده از ابتدای ۱۴۰۴")]
    return Story(X.s(ref_date), as_of, hero, badges, chapters)


def _gaps_chapter(chapters: List[Chapter]) -> Chapter:
    gaps = []
    for c in chapters:
        gaps += [f"{c.title}: {g}" for g in c.gaps]
    gaps += ["مصرف روزانه قطعات از SAP (حرکت ۲۶۱/۲۰۱) در منبع‌ها نیست؛ نیاز روزانه فقط از Oracle است.",
             "هزینه دموراژ و فری‌تایم قراردادی در منبع‌ها نیست."]
    return Chapter("gaps", "search", "داده‌هایی که هنوز نداریم",
                   f"{fa(len(gaps))} پرسش هنوز منبع داده ندارد؛ با افزودن همین ستون‌ها داستان کامل‌تر می‌شود.",
                   visual='<ul class="ds-gaps">' + "".join(f"<li>{_esc(g)}</li>" for g in gaps) + "</ul>",
                   tone="unknown")


# ═══════════════════════════════ HTML مستقل ═══════════════════════════════
def css() -> str:
    teal, st = T.TEAL_PALETTE, T.STATUS
    return f"""
.ds{{max-width:1180px;margin:0 auto}}
.ds-hero{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:18px 0}}
.ds-hero div{{background:{T.SURFACE_RAISED};border-radius:{T.RADIUS['xl']}px;box-shadow:{T.ELEVATION['raised']};padding:18px 20px;
  display:flex;gap:14px;align-items:center}}
.ds-hero b{{display:block;font-size:34px;line-height:1.1;color:{T.TEAL_INK};font-weight:900}}
.ds-hero span{{color:{T.TEXT_MUTED};font-size:13px}}
.ds-badges{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}}
.ds-badge{{display:inline-flex;gap:8px;align-items:center;border-radius:{T.RADIUS['pill']}px;padding:7px 14px;font-size:12px;
  font-weight:800;background:{T.TEAL_WASH};color:{T.TEAL_INK}}}
.ds-badge.is-good{{background:{st['good'].wash};color:{st['good'].ink}}}
.ds-toc{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px}}
.ds-toc a{{display:inline-flex;gap:6px;align-items:center;text-decoration:none;color:{T.TEXT_SECONDARY};font-size:12px;font-weight:700;
  background:{T.SURFACE_RAISED};border:1px solid {T.BORDER};border-radius:{T.RADIUS['pill']}px;padding:6px 12px}}
.ds-ch{{background:{T.SURFACE_RAISED};border-radius:{T.RADIUS['xl']}px;box-shadow:{T.ELEVATION['raised']};padding:22px 26px;margin:0 0 22px;
  border-inline-start:6px solid {teal[4]}}}
.ds-ch.is-critical{{border-inline-start-color:{st['critical'].fill}}}
.ds-ch.is-good{{border-inline-start-color:{st['good'].fill}}}
.ds-ch.is-warning{{border-inline-start-color:{st['warning'].fill}}}
.ds-ch.is-unknown{{border-inline-start-color:{st['unknown'].fill}}}
.ds-ch-h{{display:flex;gap:12px;align-items:center;margin-bottom:6px}}
.ds-ch-n{{font-size:11px;font-weight:800;color:{T.TEXT_MUTED};letter-spacing:.3px}}
.ds-ch h2{{margin:0;font-size:19px;color:{T.TEXT}}}
.ds-head{{font-size:20px;line-height:1.7;font-weight:800;color:{T.TEAL_INK};margin:8px 0 14px}}
.ds-ins{{display:flex;gap:8px;align-items:flex-start;background:{T.GOLD_WASH};color:{T.GOLD_INK};border-radius:{T.RADIUS['md']}px;
  padding:10px 14px;font-size:13px;font-weight:700;margin:14px 0 6px}}
.ds-note{{font-size:11.5px;color:{T.TEXT_MUTED};margin-top:8px;line-height:1.8}}
.ds-ch h4{{margin:16px 0 6px;font-size:13px;color:{T.TEXT_SECONDARY}}}
.ds-svg{{width:100%;height:auto;display:block;direction:ltr}}
.ds-gl{{stroke:{T.BORDER};stroke-width:1}}
.ds-ax{{font-size:12px;fill:{T.TEXT_MUTED};font-family:inherit}}
.ds-mark{{stroke:{T.BRAND_GOLD};stroke-width:1.5;stroke-dasharray:4 3}}
.ds-markt{{font-size:10px;fill:{T.GOLD_INK};font-family:inherit}}
.ds-leg{{display:flex;flex-wrap:wrap;gap:12px;font-size:11.5px;color:{T.TEXT_SECONDARY};margin:4px 0 6px}}
.ds-leg span{{display:inline-flex;gap:6px;align-items:center}} .ds-leg i{{width:12px;height:12px;border-radius:4px;display:inline-block}}
.ds-grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}}
.ds-mini b{{font-size:13px;color:{T.TEXT_SECONDARY}}}
.ds-sts{{display:grid;gap:6px}} .ds-st{{display:grid;grid-template-columns:130px 1fr;gap:10px;align-items:center;font-size:12px}}
.ds-st-l{{color:{T.TEXT_SECONDARY};font-weight:700}}
.ds-st-b{{display:flex;height:18px;border-radius:9px;overflow:hidden;background:{T.SURFACE_SUNKEN}}} .ds-st-b i{{display:block;height:100%}}
.ds-hbs{{display:grid;gap:7px}} .ds-hb{{display:grid;grid-template-columns:minmax(120px,190px) 1fr minmax(90px,max-content);gap:10px;align-items:center;font-size:12.5px}}
.ds-hb-l{{color:{T.TEXT_SECONDARY};font-weight:700}} .ds-hb b{{font-variant-numeric:tabular-nums;color:{T.TEXT}}}
.ds-hb-t{{height:14px;border-radius:7px;background:{T.SURFACE_SUNKEN};overflow:hidden}}
.ds-hb-t i{{display:block;height:100%;border-radius:7px;background:{teal[5]}}}
.ds-rings{{display:flex;gap:18px;flex-wrap:wrap}} .ds-ring{{display:flex;gap:10px;align-items:center;font-size:12.5px;color:{T.TEXT_SECONDARY}}}
.ds-ring-bg{{fill:none;stroke:{T.SURFACE_SUNKEN};stroke-width:8}} .ds-ring-t{{font-size:15px;font-weight:900;fill:{T.TEXT};font-family:inherit}}
.ds-moneys{{display:flex;flex-wrap:wrap;gap:12px}}
.ds-money{{background:{st['critical'].wash};border-radius:{T.RADIUS['lg']}px;padding:12px 18px;min-width:130px}}
.ds-money b{{display:block;font-size:22px;color:{st['critical'].ink}}} .ds-money span{{font-size:12px;color:{T.TEXT_MUTED}}}
.ds-heatt{{border-collapse:separate;border-spacing:4px;font-size:12px}} .ds-heatt th{{color:{T.TEXT_SECONDARY};font-weight:700;text-align:start}}
.ds-heat{{display:inline-flex;min-width:42px;height:26px;align-items:center;justify-content:center;border-radius:8px;
  background:{teal[5]};color:{T.SURFACE_RAISED};font-weight:800}}
.ds-kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}}
.ds-kpi{{border-radius:{T.RADIUS['lg']}px;background:{T.SURFACE_PAGE};padding:14px 16px;display:flex;flex-direction:column;gap:4px}}
.ds-kpi b{{font-size:28px;color:{T.TEXT}}} .ds-kpi-l{{font-size:12.5px;font-weight:800;color:{T.TEXT_SECONDARY}}}
.ds-kpi-d{{font-size:12px;font-weight:700;color:{T.TEXT_MUTED}}}
.ds-kpi-x{{display:flex;justify-content:space-between;font-size:10.5px;color:{T.TEXT_MUTED}}}
.ds-scroll{{overflow-x:auto}}
.ds-flows{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.ds-flow{{border-radius:{T.RADIUS['lg']}px;padding:12px 14px;background:{T.SURFACE_PAGE};display:flex;flex-direction:column;gap:2px}}
.ds-flow b{{font-size:24px;color:{T.TEXT}}} .ds-flow span{{font-size:12px;color:{T.TEXT_SECONDARY};font-weight:700}}
.ds-flow.is-critical{{background:{st['critical'].wash}}} .ds-flow.is-critical b{{color:{st['critical'].ink}}}
.ds-flow.is-good{{background:{st['good'].wash}}} .ds-flow.is-good b{{color:{st['good'].ink}}}
.ds-flow.is-warning{{background:{st['warning'].wash}}} .ds-flow.is-unknown{{background:{st['unknown'].wash}}}
.ds-kpi.is-good .ds-kpi-d{{color:{st['good'].ink}}} .ds-kpi.is-critical .ds-kpi-d{{color:{st['critical'].ink}}}
.ds-gaps{{margin:0;padding-inline-start:18px;line-height:2;font-size:13px;color:{T.TEXT_SECONDARY}}}
.ds-empty{{color:{T.TEXT_MUTED};font-size:13px}}
.ds details{{margin-top:10px}} .ds summary{{cursor:pointer;font-size:12px;color:{T.TEXT_MUTED}}}
.ds table.ds-data{{border-collapse:collapse;font-size:11.5px;margin-top:6px}}
.ds table.ds-data td,.ds table.ds-data th{{border-bottom:1px solid {T.BORDER};padding:4px 8px;text-align:start}}
@media print{{.ds-toc{{display:none}}}}
"""


def _table_html(t: pd.DataFrame, limit: int = 40) -> str:
    if t is None or t.empty:
        return ""
    cols = [c for c in t.columns if not str(c).startswith("_")]
    head = "".join(f"<th>{_esc(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{_esc(_cell(r[c]))}</td>" for c in cols) + "</tr>"
                   for _, r in t.head(limit).iterrows())
    return f'<details><summary>داده این فصل</summary><table class="ds-data"><tr>{head}</tr>{body}</table></details>'


def _cell(v: Any) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if isinstance(v, float):
        return fnum(v, 0 if abs(v) >= 100 or v == int(v) else 1)
    return fa(v) if isinstance(v, int) else str(v)


def chapter_html(c: Chapter, n: int) -> str:
    body = c.visual or ('<div class="ds-empty">' + "<br>".join(_esc(g) for g in c.gaps) + "</div>")
    ins = (f'<div class="ds-ins">{I.icon("flag", 16)}<span>{_esc(c.insight)}</span></div>' if c.insight else "")
    note = f'<div class="ds-note">{_esc(c.note)}</div>' if c.note else ""
    return (f'<section class="ds-ch is-{c.tone}" id="ds-{c.key}"><div class="ds-ch-h">{I.icon_tile(c.icon, size=20)}'
            f'<div><div class="ds-ch-n">فصل {fa(n)}</div><h2>{_esc(c.title)}</h2></div></div>'
            f'<div class="ds-head">{_esc(c.headline)}</div>{body}{ins}{note}{_table_html(c.table)}</section>')


def body_html(s: Story) -> str:
    hero = "".join(f'<div>{I.icon_tile(ic, size=24, active=True)}<span><b>{_esc(v)}</b>{_esc(lab)}</span></div>'
                   for ic, v, lab in s.hero)
    badges = "".join(f'<span class="ds-badge is-{tone}">{I.icon(ic, 14)}{_esc(t)}</span>' for ic, t, tone in s.badges)
    toc = "".join(f'<a href="#ds-{c.key}">{I.icon(c.icon, 14)}{_esc(c.title.split(":")[0])}</a>' for c in s.chapters)
    chs = "".join(chapter_html(c, i + 1) for i, c in enumerate(s.chapters))
    return (f'<div class="ds"><div class="ds-hero">{hero}</div>'
            + (f'<div class="ds-badges">{badges}</div>' if badges else "")
            + f'<nav class="ds-toc">{toc}</nav>{chs}</div>')


def build_html(story: Story, title: str = "", embed_fonts: Optional[bool] = None) -> str:
    """صفحه آفلاین «دیتا استوری‌تلینگ»؛ همان صفحه داخل Studio (iframe) نشان داده می‌شود."""
    from ..design import brand as B
    from ..design import fonts as F
    from ..design.css import stylesheet
    from . import fx_html as H
    title = title or "داستان داده‌های ارز، کالا و حمل"
    ref = format_jalali(story.as_of) if story.as_of else ""
    font_css = F.html_font_css() if (embed_fonts is None or embed_fonts) else ""
    band = B.band_raw(html.escape(title), sub_html=f"تاریخ مرجع <span class=\"ltr\">{html.escape(ref)}</span>",
                      eyebrow_html="پول · کالا · صف · تعهد · حمل", tag=B.TAGLINE_FA)
    return (f'<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f'<style>{font_css}{stylesheet()}{H.css()}{css()}</style></head><body class="gx gx-page"><main class="gx-wrap">'
            f'{band}{body_html(story)}<p class="gx-legal">ساخته‌شده از همان Snapshot منتشرشده، بی‌منبع بیرونی. «—» یعنی '
            f'بی‌داده، نه صفر. مبلغ ارزهای مختلف هرگز با هم جمع نمی‌شود.</p></main></body></html>')


def build_excel(story: Story) -> bytes:
    """داده هر فصل در یک شیت (برای بررسی و ساختن نمودار خود کاربر)."""
    from openpyxl import Workbook

    from . import fx_excel as XL
    wb = Workbook()
    wb.remove(wb.active)
    XL.add_key_values(wb, "خلاصه", [(c.title, c.headline) for c in story.chapters], title="دیتا استوری‌تلینگ",
                      note="هر ارز جدا؛ «—» یعنی بی‌داده.")
    used = set()
    for i, c in enumerate(story.chapters, 1):
        if c.table is None or c.table.empty:
            continue
        name = f"{i}-{c.title.split(':')[0]}"[:31]
        if name in used:
            continue
        used.add(name)
        XL.add_frame(wb, name, c.table, title=c.title, note=c.note)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
