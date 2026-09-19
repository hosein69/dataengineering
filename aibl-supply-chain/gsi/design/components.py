# -*- coding: utf-8 -*-
"""GSI Design System — لایه ۳: کامپوننت‌ها و واریانت‌ها.

هر کامپوننت اینجا دقیقاً همان چیزی است که در فیگما یک **Component Set**
است: یک ساختار ثابت با چند **Property** که واریانت می‌سازد.

    کامپوننت      Propertyها                                 حالت‌ها
    ───────────   ────────────────────────────────────────   ──────────────────
    Button        variant(primary/decision/secondary/ghost)   hover active focus disabled
                  size(md/sm), icon(on/off)
    Badge         tone(۷ وضعیت), style(soft/solid/quiet)      —
    KPI Card      tone(neutral + ۷ وضعیت), delta(on/off)      hover
    Panel         padding(lg), header(on/off)                 —
    Chart frame    question(on/off), footer(on/off)           hover
    Empty state   —                                           —
    Alert         tone(۷ وضعیت)                                —
    Finding       tone(۷ وضعیت)                                hover
    Flow step     current(true/false)                          —

## چرا HTML اینجا ساخته می‌شود و نه در html_export

تا پیش از این، نشانه‌گذاری هر کارت داخل یک f-string ۴۰۰ کاراکتری وسط
منطق گزارش نوشته می‌شد. نتیجه این بود که دو کارت در دو بخش گزارش، دو
padding و دو شعاع متفاوت داشتند بی‌آنکه کسی تصمیم گرفته باشد. با متمرکز
کردن نشانه‌گذاری، «واریانت» یک انتخاب صریح می‌شود نه یک تفاوت تصادفی.

همه توابع خروجی **HTML امن** می‌دهند: هر مقدار متنی از :func:`esc`
می‌گذرد. هیچ ورودی داده‌ای مستقیم در نشانه‌گذاری تزریق نمی‌شود.
"""
from __future__ import annotations

__contract__ = 1

import html as _html
from typing import Dict, Iterable, List, Optional, Sequence

from . import tokens as T


def esc(value) -> str:
    """متن امن برای درج در HTML."""
    return _html.escape("" if value is None else str(value), quote=True)


def _tone_vars(tone: Optional[str]) -> str:
    """متغیرهای رنگ یک وضعیت را روی خود عنصر می‌نشاند.

    به‌جای ساختن یک کلاس به ازای هر وضعیت، سه متغیر CSS ست می‌شود و
    کامپوننت از ``var(--tone-ink)`` می‌خواند. همان الگوی Variant فیگما،
    ولی بدون انفجار تعداد کلاس.
    """
    s = T.STATUS.get(tone or "")
    if not s:
        return ""
    return (f"--tone:{s.fill};--tone-ink:{s.ink};--tone-wash:{s.wash};")


# ═══════════════════════════════════════════════════════════════════════════
# Auto Layout — همان سه اولیه‌ای که فیگما دارد
# ═══════════════════════════════════════════════════════════════════════════
def stack(*children: str, gap: str = "md", cls: str = "", attrs: str = "") -> str:
    """چیدمان عمودی (Vertical auto layout)."""
    klass = " ".join(x for x in ("stack", f"stack-{gap}", cls) if x)
    return f'<div class="{klass}" {attrs}>' + "".join(children) + "</div>"


def cluster(*children: str, gap: str = "sm", cls: str = "", attrs: str = "") -> str:
    """چیدمان افقی با wrap (Horizontal auto layout)."""
    klass = " ".join(x for x in ("cluster", f"cluster-{gap}", cls) if x)
    return f'<div class="{klass}" {attrs}>' + "".join(children) + "</div>"


def split(right: str, left: str, cls: str = "") -> str:
    """دو سر، فاصله در میان (Space between)."""
    return f'<div class="split {cls}">{right}{left}</div>'


def grid(*children: str, col: int = 240, gap: str = "sm", cls: str = "",
         attrs: str = "") -> str:
    """شبکه خودشکن — بدون media query هم درست می‌ماند."""
    return (f'<div class="grid-auto {cls}" style="--col:{col}px" {attrs}>'
            + "".join(children) + "</div>")


# ═══════════════════════════════════════════════════════════════════════════
# کامپوننت‌ها
# ═══════════════════════════════════════════════════════════════════════════
BUTTON_VARIANTS = ("primary", "decision", "secondary", "ghost")


def button(label: str, *, variant: str = "primary", size: str = "md",
           icon: str = "", onclick: str = "", attrs: str = "",
           aria_label: str = "") -> str:
    """دکمه.

    ``decision`` عمداً کمیاب است: طلایی یعنی «از تو کاری خواسته شده».
    اگر هر دکمه‌ای طلایی باشد، دیگر چیزی را علامت نمی‌زند.
    """
    if variant not in BUTTON_VARIANTS:
        variant = "primary"
    cls = f"btn btn--{variant}" + (" btn--sm" if size == "sm" else "")
    ic = f'<span aria-hidden="true">{esc(icon)}</span>' if icon else ""
    oc = f' onclick="{onclick}"' if onclick else ""
    al = f' aria-label="{esc(aria_label)}"' if aria_label else ""
    return f'<button class="{cls}" type="button"{oc}{al} {attrs}>{ic}{esc(label)}</button>'


def badge(label: str, *, tone: str = "neutral", style: str = "soft",
          icon: Optional[str] = None) -> str:
    """نشان وضعیت — رنگ + آیکن + متن، هر سه با هم.

    رنگ هرگز تنها حامل معنا نیست؛ آیکن و برچسب همیشه همراه‌اند.
    """
    s = T.STATUS.get(tone)
    ic = icon if icon is not None else (s.icon if s else "")
    mod = {"solid": " badge--solid", "quiet": " badge--quiet"}.get(style, "")
    icon_html = f'<i aria-hidden="true">{esc(ic)}</i>' if ic else ""
    return (f'<span class="badge{mod}" style="{_tone_vars(tone)}">'
            f'{icon_html}{esc(label)}</span>')


def kpi(label: str, value: str, *, hint: str = "", tone: str = "",
        delta: str = "", delta_good: Optional[bool] = None, index: int = 0) -> str:
    """کارت سنجه.

    ``delta`` بدون مبنای مقایسه بی‌معناست، پس وقتی داده‌ی دوره قبل نباشد
    اصلاً رندر نمی‌شود — به‌جای نمایش «۰٪» که خواننده آن را «بدون تغییر»
    می‌خواند.
    """
    d = ""
    if str(delta).strip():
        dt = ("good" if delta_good else "bad") if delta_good is not None else "flat"
        ink = {"good": T.STATUS["good"].ink, "bad": T.STATUS["critical"].ink,
               "flat": T.TEXT_SECONDARY}[dt]
        d = (f'<div class="g" style="color:{ink};font-weight:800">{esc(delta)}</div>')
    tone_attr = f' data-tone="{esc(tone)}" style="{_tone_vars(tone)}--tone:{T.STATUS[tone].ink if tone in T.STATUS else T.BRAND_TEAL}"' if tone else ""
    return (f'<div class="kpi reveal" style="--i:{index}"{tone_attr}>'
            f'<div class="l">{esc(label)}</div><b>{esc(value)}</b>{d}'
            + (f'<div class="g">{esc(hint)}</div>' if hint else "") + "</div>")


def panel(body: str, *, title: str = "", aside: str = "", note: str = "",
          cls: str = "", pid: str = "", section: str = "") -> str:
    """ظرف سطح‌بالا با سرتیتر اختیاری.

    ``section`` نام بخش در پروفایل مخاطب است. اگر داده شود، این پنل با
    ``data-section`` علامت می‌خورد و با جابه‌جایی مخاطب پنهان یا نمایان
    می‌شود — بدون آنکه دوباره ساخته شود.
    """
    head = ""
    if title or aside:
        head = split(f'<h3 class="t-h3">{esc(title)}</h3>',
                     aside or "", cls="panel-head")
    n = f'<p class="note">{esc(note)}</p>' if note else ""
    ident = f' id="{esc(pid)}"' if pid else ""
    sect = f' data-section="{esc(section)}"' if section else ""
    return (f'<section class="panel reveal {cls}"{ident}{sect}>'
            f'{head}{n}{body}</section>')


def chart_frame(title: str, svg: str, *, question: str = "", footer: str = "",
                index: int = 0) -> str:
    """قاب نمودار با «سؤالی که جواب می‌دهد».

    زیرنویس سؤال اختیاری نیست از نظر طراحی: نموداری که نمی‌شود گفت به چه
    سؤالی جواب می‌دهد، جای آن در گزارش نیست.
    """
    q = f'<span class="ask">{esc(question)}</span>' if question else ""
    f = f'<div class="chartfoot">{footer}</div>' if footer else ""
    return (f'<figure class="chartbox reveal" style="--i:{index}">'
            f'<figcaption><h4>{esc(title)}</h4>{q}</figcaption>{svg}{f}</figure>')


def empty_state(message: str, *, mark: str = "◇") -> str:
    """حالت خالی — همیشه می‌گوید **چرا** خالی است، نه فقط «داده‌ای نیست»."""
    return (f'<div class="emptybox"><span class="emptymark" aria-hidden="true">'
            f'{esc(mark)}</span><p>{esc(message)}</p></div>')


def alert(message: str, *, tone: str = "warning", title: str = "") -> str:
    """پیام وضعیت داده/سامانه."""
    t = f"<b>{esc(title)}</b> — " if title else ""
    return (f'<div class="alert" role="status" style="{_tone_vars(tone)}">'
            f'{t}{esc(message)}</div>')


def finding(headline: str, magnitude: str, comparison: str, so_what: str,
            *, tone: str = "neutral", index: int = 0) -> str:
    """کارت یافته — بزرگی، مقایسه، و «پس چه».

    هر سه جزء اجباری‌اند. یافته‌ای که «پس چه» ندارد، عدد است نه یافته.
    """
    return (f'<article class="finding reveal" style="--i:{index};{_tone_vars(tone)}">'
            f'<h5>{esc(headline)}</h5>'
            f'<p class="mag">{esc(magnitude)}</p>'
            f'<p class="cmp">{esc(comparison)}</p>'
            f'<p class="sow"><span aria-hidden="true">←</span> {esc(so_what)}</p>'
            f'</article>')


def flow(steps: Sequence[str], *, current: str = "", label: str = "زنجیره تأمین") -> str:
    """نوار مسیر فرآیند — لنگر ذهنی «الان کجای زنجیره‌ایم»."""
    out: List[str] = []
    for i, s in enumerate(steps):
        cur = ' aria-current="step"' if s == current else ""
        out.append(f'<span class="flow-step"{cur}>{esc(s)}</span>')
        if i < len(steps) - 1:
            out.append('<span class="flow-arrow" aria-hidden="true">←</span>')
    return (f'<nav class="flow" aria-label="{esc(label)}">' + "".join(out) + "</nav>")


def legend(items: Iterable) -> str:
    """راهنمای وضعیت — رنگ، آیکن و برچسب کنار هم."""
    out = []
    for s in items:
        out.append(f'<span class="badge" style="{_tone_vars(s.key)}">'
                   f'<i aria-hidden="true">{esc(s.icon)}</i>{esc(s.label)}</span>')
    return ('<div class="cluster cluster-xs" role="list" '
            'aria-label="راهنمای طبقه بحرانی">' + "".join(out) + "</div>")


def app_bar(title: str, *, eyebrow: str = "", subtitle: str = "",
            stats: Sequence = (), actions: str = "") -> str:
    """سربرگ گزارش — هویت، زمینه، و سنجه‌های سرصفحه."""
    pills = "".join(
        f'<div class="stat-pill"><b>{esc(v)}</b><span>{esc(k)}</span></div>'
        for k, v in stats)
    eb = (f'<div class="brandmark t-overline eyebrow"><i aria-hidden="true"></i>'
          f'{esc(eyebrow)}</div>') if eyebrow else ""
    sub = f'<div class="sub t-small">{esc(subtitle)}</div>' if subtitle else ""
    return (f'<header class="appbar split">'
            f'<div class="stack stack-2xs grow">{eb}'
            f'<h1 class="t-h1">{esc(title)}</h1>{sub}</div>'
            f'<div class="cluster cluster-xs hug">{pills}</div>'
            f'<div class="cluster cluster-xs hug no-print">{actions}</div>'
            f'</header>')


def skip_link(target: str = "#main") -> str:
    """پرش به محتوا — اولین چیزی که کاربر کیبورد به آن می‌رسد."""
    return f'<a class="skip-link" href="{esc(target)}">پرش به محتوای گزارش</a>'


#: فهرست کامپوننت‌ها برای Dev Handoff — نام، واریانت‌ها، حالت‌ها.
INVENTORY: Dict[str, Dict[str, object]] = {
    "Button": {"variants": list(BUTTON_VARIANTS), "sizes": ["md", "sm"],
               "states": ["default", "hover", "active", "focus-visible", "disabled"]},
    "Badge": {"variants": ["soft", "solid", "quiet"],
              "tones": [s.key for s in T.STATUS_SCALE], "states": ["default"]},
    "KPI Card": {"variants": ["plain", "toned", "with-delta"],
                 "states": ["default", "hover"]},
    "Panel": {"variants": ["plain", "with-header", "with-note"], "states": ["default"]},
    "Chart frame": {"variants": ["plain", "with-question", "with-footer"],
                    "states": ["default", "hover"]},
    "Empty state": {"variants": ["default"], "states": ["default"]},
    "Alert": {"tones": [s.key for s in T.STATUS_SCALE], "states": ["default"]},
    "Finding": {"tones": [s.key for s in T.STATUS_SCALE], "states": ["default", "hover"]},
    "Flow step": {"variants": ["default", "current"], "states": ["default"]},
    "Tab": {"variants": ["default", "selected"],
            "states": ["default", "hover", "focus-visible"]},
    "Table": {"variants": ["default"], "states": ["row-hover", "zebra", "sticky-header"]},
}
