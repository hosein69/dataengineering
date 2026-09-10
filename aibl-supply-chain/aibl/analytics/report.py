# -*- coding: utf-8 -*-
"""گزارش تحلیلی — یک صفحه HTML مستقل، خوانا و قابل استناد.

هر عدد این گزارش سه چیز همراه دارد: **n**، **بازه اطمینان**، و **تعریف
دقیق**. بدون این سه، عدد در جلسه قابل دفاع نیست.

نمودارها با SVG خام کشیده می‌شوند تا فایل روی شبکه داخلی و بدون اینترنت
هم کامل باز شود.
"""
from __future__ import annotations

__contract__ = 1

import html
from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from ..dataio.logging_setup import log
from .cycle import Leg, bottleneck, legs, what_if
from .drivers import Finding, OutcomeReport, analyse_all
from .evidence import MIN_N
from ..report import alborz as _AL
from ..report import brand as _B
from ..report import paykan as _pk

BRAND, DEEP = "#0f6e6e", "#0a4f4f"
SURFACE, RAISED, BORDER = "#fcfcfb", "#ffffff", "#e3e3dd"
TEXT, TEXT2, TEXT3 = "#0b0b0b", "#52514e", "#6e6e66"
# سه رنگِ جهتِ تغییر — از پالت وضعیتِ البرز، نه رنگ محلی.
#
# نسخهٔ قبل این‌ها را همین‌جا تعریف می‌کرد و بازرسیِ مرورگر رد کرد:
#
#     #0ca30c روی سفید → ۳٫۳۵    (متن ۱۲٫۵ پیکسلی، کف ۴٫۵)
#     #8a8a85 روی سفید → ۳٫۴۷
#
# یعنی خودِ عددهای «بهبود» — چیزی که خواننده دنبالش می‌گردد — کم‌رنگ‌ترین
# چیز صفحه بودند. حالا از توکن می‌آیند: ۶٫۵۴ و ۵٫۱۳ و ۵٫۹۲.
POS = _AL.STATUS["critical"]        #: بدتر شده
NEG = _AL.STATUS["good"]            #: بهتر شده
NEUTRAL = _AL.INK_2                 #: بی‌تغییر

_E = html.escape


def _pct(x: float) -> str:
    return f"{x * 100:,.1f}٪"


def _bar_row(f: Finding, scale: float) -> str:
    """یک ردیف: نرخ گروه در برابر بقیه، با بازه اطمینان روی همان محور."""
    def seg(r, color):
        w = max(r.p / scale * 100, 0.4)
        lo, hi = r.lo / scale * 100, r.hi / scale * 100
        return (f'<div class="track">'
                f'<div class="ci" style="right:{lo}%;width:{max(hi - lo, 0.4)}%"></div>'
                f'<div class="fill" style="width:{w}%;background:{color}"></div></div>'
                f'<div class="rv">{_E(r.fa())}</div>')

    tone = POS if f.crude.diff > 0 else NEG
    badge = ("robust" if f.robust else
             "weak" if f.crude.significant else "flat")
    adj = ("—" if f.adjusted is None
           else f"{f.adjusted * 100:+,.1f} واحد درصد (در {f.strata_used} لایه)")
    return f"""<tr>
<td class="lv"><b>{_E(f.factor_fa)}</b><div class="s">{_E(f.level)}</div></td>
<td>{seg(f.crude.exposed, tone)}</td>
<td>{seg(f.crude.control, NEUTRAL)}</td>
<td class="num" style="color:{tone}">{f.crude.diff * 100:+,.1f}</td>
<td class="num">{adj}</td>
<td class="num">{f.crude.e_value:,.1f}</td>
<td><span class="badge {badge}">{_E(f.verdict)}</span></td></tr>"""


def _outcome_block(rep: OutcomeReport, labels: Optional[Dict[str, str]] = None) -> str:
    labels = labels or {}
    # پیامدی که اصلاً رخ نداده، جدولی از صفرها لازم ندارد — خودِ نبودش
    # یافته است و در یک جمله گفته می‌شود.
    if rep.base.k == 0:
        return (f'<div class="panel"><h3>{_E(rep.outcome.fa)}</h3>'
                f'<div class="def"><b>تعریف:</b> {_E(rep.outcome.definition)}</div>'
                f'<div class="base">در هیچ‌یک از <b>{rep.base.n:,}</b> ردیف این اجرا '
                f'رخ نداده است (کران بالای ۹۵٪: {_pct(rep.base.hi)}). '
                f'تحلیل محرک بی‌معناست.</div></div>')
    shown = [f for f in rep.findings if f.crude.enough][:14]
    if not shown:
        return (f'<div class="panel"><h3>{_E(rep.outcome.fa)}</h3>'
                f'<div class="note">هیچ محرکی با داده کافی (n ≥ {MIN_N}) پیدا نشد.</div></div>')
    scale = max([f.crude.exposed.hi for f in shown]
                + [f.crude.control.hi for f in shown] + [rep.base.hi]) or 1.0
    rows = "".join(_bar_row(f, scale) for f in shown)
    ctrl = (f'کنترل‌شده بر اساس <b>{_E(labels.get(rep.control, rep.control))}</b>' if rep.control
            else 'بدون کنترل مخدوش‌کننده (ستون کنترل در داده نبود)')
    return f"""<div class="panel">
<h3>{_E(rep.outcome.fa)}</h3>
<div class="def"><b>تعریف:</b> {_E(rep.outcome.definition)}</div>
<div class="base">نرخ پایه در کل داده: <b>{_E(rep.base.fa())}</b></div>
<div class="tw"><table>
<thead><tr><th>محرک</th><th>نرخ در این گروه</th><th>نرخ در بقیه</th>
<th>تفاضل (واحد درصد)</th><th>پس از کنترل</th><th>E-value</th><th>داوری</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<div class="note">{ctrl}. ستون «پس از کنترل» تفاضل را <b>درون لایه‌های</b> همان
متغیر می‌سنجد؛ اگر رابطه آنجا آب برود، توضیح ساده‌تری داشته است.
E-value می‌گوید یک مخدوش‌کننده مشاهده‌نشده چقدر باید قوی باشد تا این رابطه
را کاملاً توضیح دهد — عدد نزدیک ۱ یعنی شکننده.</div></div>"""


def _cycle_block(items: List[Leg], wi) -> str:
    if not items:
        return ""
    ok = [x for x in items if x.enough]
    mx = max([x.q3 for x in ok] or [1]) or 1
    rows = ""
    for x in items:
        if not x.enough:
            rows += (f'<tr><td class="lv"><b>{_E(x.frm)} ← {_E(x.to)}</b></td>'
                     f'<td colspan="2" class="note">داده کافی نیست (n={x.n})</td>'
                     f'<td class="num">{x.n:,}</td></tr>')
            continue
        left, w = x.q1 / mx * 100, max((x.q3 - x.q1) / mx * 100, 0.6)
        med = x.median / mx * 100
        rows += f"""<tr><td class="lv"><b>{_E(x.frm)} ← {_E(x.to)}</b>
{f'<div class="s">{_E(x.scope)}</div>' if x.scope else ''}</td>
<td class="wide"><div class="track"><div class="iqr" style="right:{left}%;width:{w}%"></div>
<div class="med" style="right:{med}%"></div></div></td>
<td class="num">{x.median:,.0f} روز <span class="s">({x.q1:,.0f}–{x.q3:,.0f})</span></td>
<td class="num">{x.n:,}</td></tr>"""
    whatif = ""
    if wi:
        whatif = f"""<div class="whatif"><b>پادواقعیت ساده:</b>
اگر {wi.slower_n:,} پرونده‌ی کندتر از میانه در این گام به میانه می‌رسیدند،
مجموعاً <b>{wi.days_saved:,.0f} روز</b> آزاد می‌شد — به‌طور میانگین
{wi.per_case:,.1f} روز برای هر پرونده.
<div class="note">{_E(wi.assumption)}</div></div>"""
    return f"""<div class="panel">
<h3>زمان کجا می‌رود</h3>
<div class="def"><b>روش:</b> فاصله روزهای بین دو رویداد متوالی تاریخ‌دار.
میانه و بازه میان‌چارکی گزارش می‌شود، نه میانگین — چند پرونده رهاشده
میانگین را چند برابر می‌کنند. مدت منفی (ترتیب خراب) کنار گذاشته شده است.</div>
<div class="tw"><table><thead><tr><th>گام چرخه</th>
<th>بازه میان‌چارکی</th><th>میانه</th><th>تعداد</th></tr></thead>
<tbody>{rows}</tbody></table></div>{whatif}</div>"""


def build_analysis_html(df: pd.DataFrame, ref_date: str,
                        labels: Optional[Dict[str, str]] = None,
                        title: str = "") -> str:
    # عنوان پیش‌فرض از هویت سازمانی می‌آید. «AIBL» نام داخلی
    # پکیج پایتون است و روی سندی که به مدیر می‌رسد جایی ندارد.
    title = title or f"{_B.PRODUCT} — گزارش تحلیلی"
    """گزارش تحلیلی کامل به‌صورت یک رشته HTML."""
    labels = labels or {}
    reports = analyse_all(df, labels=labels)
    items = legs(df)
    top = bottleneck(items)
    wi = what_if(df, top) if top else None

    blocks = "".join(_outcome_block(r, labels) for r in reports)
    if not blocks:
        blocks = ('<div class="panel"><h3>یافته‌ای گزارش نشد</h3>'
                  f'<div class="note">هیچ پیامدی در این اجرا داده کافی '
                  f'(n ≥ {MIN_N}) نداشت. این خودش یک یافته است: نمونه کوچک‌تر '
                  f'از آن است که بتوان از آن نتیجه‌ای دفاع‌پذیر گرفت.</div></div>')

    headline = ""
    strong = [f for r in reports for f in r.findings if f.robust]
    if strong:
        f0 = strong[0]
        headline = (f'قوی‌ترین یافته: «{_E(f0.factor_fa)} = {_E(f0.level)}» با '
                    f'{f0.crude.diff * 100:+,.1f} واحد درصد تفاوت، پس از کنترل '
                    f'بر {_E(labels.get(f0.control, f0.control))} هم می‌ماند.')
    elif reports:
        headline = ("هیچ رابطه‌ای پس از کنترل مخدوش‌کننده پایدار نماند — "
                    "یعنی تفاوت‌های خام، توضیح ساده‌تری داشتند.")

    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_E(title)} — {_E(ref_date)}</title><style>
*{{box-sizing:border-box}}
body{{margin:0;background:{SURFACE};color:{TEXT};direction:rtl;
font-family:'IRANSans Light',IRANSans,Vazirmatn,Tahoma,Arial,sans-serif}}
.shell{{max-width:1280px;margin:auto;padding:22px}}
header{{background:{_AL.header_gradient_css()};color:{_AL.ON_AQUA};
border-radius:18px;padding:24px 26px}}
/* پیکان در سربرگ: لایهٔ زمینه، نه آیکن. هم‌فامِ سربرگ و کم‌جان تا
   عنوان رویش بخواند؛ در چاپ حذف می‌شود تا جوهر هدر نرود. */
header{{position:relative;overflow:hidden}}
header>*{{position:relative;z-index:1}}
.pk{{position:absolute;left:16px;bottom:-4px;opacity:.4;z-index:0;
     pointer-events:none}}
@media print{{.pk{{display:none}}}}
h1{{margin:0;font-size:25px}} .sub{{opacity:.9;font-size:13px;margin-top:6px}}
.head-note{{margin-top:12px;background:rgba(255,255,255,.14);border-radius:10px;
padding:10px 14px;font-size:13px;line-height:1.9}}
.panel{{background:{RAISED};border:1px solid {BORDER};border-radius:16px;
padding:18px;margin-top:16px}}
h3{{margin:0 0 10px;font-size:17px}}
.def,.base{{font-size:12.5px;color:{TEXT2};line-height:2;margin-bottom:8px}}
.base b{{color:{TEXT};font-size:14px}}
.tw{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;min-width:820px}}
th{{background:{DEEP};color:#fff;padding:9px;text-align:right;white-space:nowrap;
font-weight:600}}
td{{padding:9px;border-bottom:1px solid {BORDER};vertical-align:middle}}
td.lv{{white-space:nowrap}} td.lv .s{{font-size:11px;color:{TEXT3};margin-top:2px}}
td.num{{white-space:nowrap;font-variant-numeric:tabular-nums}}
td.wide{{width:38%}}
.track{{position:relative;height:15px;background:#f1f0ec;border-radius:7px;
overflow:hidden;min-width:120px}}
.fill{{height:100%;border-radius:7px}}
.ci{{position:absolute;top:0;height:100%;background:rgba(11,11,11,.13)}}
.iqr{{position:absolute;top:0;height:100%;background:{BRAND};opacity:.32;border-radius:7px}}
.med{{position:absolute;top:-2px;width:2px;height:19px;background:{TEXT}}}
.rv{{font-size:11px;color:{TEXT2};margin-top:3px;white-space:nowrap}}
.badge{{display:inline-block;border-radius:999px;padding:2px 10px;font-size:11px;
font-weight:700;white-space:nowrap}}
.badge.robust{{background:#E7F1E7;color:{_AL.STATUS_ON_TINT["good"]};border:1px solid #BBD8BC}}
.badge.weak{{background:#fab2191a;color:#8a6100;border:1px solid #fab21955}}
.badge.flat{{background:#8a8a851a;color:{TEXT3};border:1px solid #8a8a8555}}
.note{{font-size:11.5px;color:{TEXT3};line-height:1.95;margin-top:9px}}
.whatif{{margin-top:12px;background:#f4faf8;border:1px solid {BORDER};
border-radius:12px;padding:12px 14px;font-size:13px;line-height:2}}
.method{{font-size:12px;color:{TEXT2};line-height:2.1}}
.method code{{background:#f1f0ec;padding:1px 5px;border-radius:4px}}
button{{border:0;border-radius:10px;padding:10px 16px;background:#fff;color:{DEEP};
font:inherit;font-weight:700;cursor:pointer;margin-top:14px}}
@media print{{button{{display:none}} body{{background:#fff}}
.panel{{break-inside:avoid}} header{{-webkit-print-color-adjust:exact;
print-color-adjust:exact}}}}
</style></head><body><div class="shell">
<header><div class="pk">{_pk.mark(150, _AL.TEAL_EDGE)}</div>
<h1>{_E(title)}</h1>

<div class="sub">تاریخ مرجع {_E(ref_date)} · {len(df):,} ردیف · حداقل نمونه برای هر یافته: {MIN_N}</div>
{f'<div class="head-note">{headline}</div>' if headline else ''}
<button onclick="window.print()">چاپ / ذخیره PDF</button></header>
{blocks}
{_cycle_block(items, wi)}
<div class="panel"><h3>روش، و حدودش</h3><div class="method">
<b>چه چیزی اینجا هست.</b> نرخ تجربی هر پیامد با بازه اطمینان
<code>Wilson</code>، مقایسه هر گروه با بقیه، و همان مقایسه <b>درون لایه‌های</b>
یک متغیر کنترل. برای زمان، میانه و بازه میان‌چارکی بین رویدادهای تاریخ‌دار.
<br><br>
<b>چرا یادگیری ماشین به کار نرفت.</b> عددی که مبنای تصمیم می‌شود باید به یک
جمله ساده تجزیه شود: «از n مورد مشابه، k مورد چنین شدند.» خروجی مدل
جعبه‌سیاه چنین جمله‌ای ندارد و در برابر کسی که با نتیجه مخالف است قابل دفاع
نیست. ضمناً در این اندازه داده (هزارها، نه میلیون‌ها)، نرخ تجربی با بازه
اطمینان هم دقیق‌تر است و هم صادق‌تر.
<br><br>
<b>این گزارش چه چیزی را ثابت نمی‌کند.</b> داده مشاهده‌ای است، نه آزمایش
تصادفی. «همراهی پایدار» یعنی رابطه پس از کنترلِ <i>یک</i> مخدوش‌کننده باقی
مانده — نه اینکه علت اثبات شده. <code>E-value</code> صریح می‌گوید یک عامل
مشاهده‌نشده چقدر باید قوی باشد تا کل رابطه را توضیح دهد؛ هرچه به ۱ نزدیک‌تر،
نتیجه شکننده‌تر.
<br><br>
<b>مرزهایی که رعایت شده.</b> هیچ گروهی با کمتر از {MIN_N} مورد گزارش نمی‌شود.
معناداری با روش محافظه‌کارانه «عدم هم‌پوشانی بازه‌ها» سنجیده می‌شود که از
آزمون رسمی سخت‌گیرتر است. ردیف‌هایی که مدت منفی می‌دهند (ترتیب رویداد خراب)
از تحلیل زمان کنار گذاشته می‌شوند.
<br><br>
<b>منابع.</b> Wilson (1927) برای بازه نسبت · VanderWeele &amp; Ding (2017),
<i>Annals of Internal Medicine</i> 167(4):268-274 برای E-value ·
Mantel &amp; Haenszel (1959) برای تجمیع لایه‌ای.
</div></div></div></body></html>"""


def write_analysis(df: pd.DataFrame, path, ref_date: str = "",
                   labels: Optional[Dict[str, str]] = None) -> str:
    """گزارش تحلیلی را روی دیسک می‌نویسد و مسیرش را برمی‌گرداند."""
    import os
    ref_date = ref_date or date.today().isoformat()
    body = build_analysis_html(df, ref_date, labels)
    path = str(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(body)
    os.replace(tmp, path)
    log.info(f"📈 گزارش تحلیلی ساخته شد: {path}")
    return path
