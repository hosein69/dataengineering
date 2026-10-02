# -*- coding: utf-8 -*-
"""سربرگ برند GSI: یک طرح برای همه گزارش‌های HTML، ایمیل و تصویر مستقل.

مالک (۱۴۰۵-۰۷-۰۸): هدر استاندارد گزارش‌ها «خیلی سیستمی و خلوت و متناسب با رنگ‌بندی موشن‌گرافیک»
باشد و «در عین سادگی حس خفن بودن» بدهد؛ همان در ایمیل و هدر گزارش‌ها.

* رنگ‌ها همان پالت موشن‌گرافیک هیئت مدیره است (فیروزه‌ای بسیار تیره، فیروزه‌ای، نعنایی و یک نقطه طلایی).
* نشان سپر همان فایلی است که در موشن‌گرافیک آمده (``assets/brand/gsi_mark.png``).
* نقش‌مایه سیستمی: شبکه نقطه‌ای کم‌رنگ، کمان‌های مداری و خط سه‌گره Data → Process → Decision.
* بافت پس‌زمینه SVG با کدگذاری URL در CSS است، بدون نویسه «کوچک‌تر»، تا DOMPurify در Streamlit آن را نگه دارد.
* ایمیل (Outlook) SVG و گرادیان CSS را نشان نمی‌دهد؛ برای ایمیل تصویر PNG همین طرح
  (``assets/brand/gsi_email_header.jpg``) با CID پیوست می‌شود و عنوان متن زنده زیر آن است.
"""
from __future__ import annotations

import base64
import functools
import html as _html
from pathlib import Path
from typing import Iterable, Sequence, Tuple
from urllib.parse import quote

#: پالت موشن‌گرافیک هیئت مدیره (board_motion) — تنها منبع رنگ سربرگ؛ مقدارها در tokens.py.
from . import tokens as _T
DEEP, DARK, PINE = _T.BAND_DEEP, _T.BAND_DARK, _T.BAND_PINE
TEAL, TEAL_2, MINT = _T.BAND_TEAL, _T.BAND_TEAL_2, _T.BAND_MINT
GOLD, INK, MUTE, ALERT = _T.BAND_GOLD, _T.BAND_INK, _T.BAND_MUTE, _T.BAND_ALERT

TAGLINE_FA = "هوشمندی روزانه زنجیره خرید ایران‌خودرو"
NAME_EN = "Global Sourcing Intelligence"
#: مالک (۱۴۰۵-۰۷-۰۸): عنوان همه‌جا «GSi» است؛ i کوچک و کمی ریزتر، و ادامه واژه Intelligence
#: بعد از i خیلی کم‌رنگ و شبیه بارکد. BRAND_TEXT برای جاهایی است که فقط متن ساده ممکن است
#: (عنوان پنجره، موضوع ایمیل، نام فایل).
BRAND_TEXT = "GSi"
BRAND_TAIL = "ntelligence"
BRAND_SUB = "Global Sourcing"
FLOW = ("Data", "Process", "Decision")

ROOT = Path(__file__).resolve().parents[2]
MARK_PATH = ROOT / "assets" / "brand" / "gsi_mark.png"
EMAIL_HEADER_PATH = ROOT / "assets" / "brand" / "gsi_email_header.jpg"
EMAIL_HEADER_CID = "gsi_header"
#: عرض نمایش تصویر سربرگ ایمیل (پیکسل CSS)؛ فایل دو برابر است تا روی نمایشگر پرتراکم تیز بماند.
EMAIL_HEADER_WIDTH = 820
EMAIL_HEADER_HEIGHT = 150


def esc(v) -> str:
    return _html.escape("" if v is None else str(v), quote=True)


@functools.lru_cache(maxsize=1)
def mark_data_uri() -> str:
    try:
        return "data:image/png;base64," + base64.b64encode(MARK_PATH.read_bytes()).decode("ascii")
    except OSError:
        return ""


def wordmark_html(cls: str = "gw") -> str:
    """نشانه نوشتاری: «GS» پررنگ، «i» کوچک‌تر و ادامه «ntelligence» کم‌رنگ و بارکدی."""
    c = esc(cls)
    return (f'<span class="{c}" role="img" aria-label="GSi · Intelligence"><b class="{c}-gs">GS</b>'
            f'<b class="{c}-i">i</b><span class="{c}-tail" aria-hidden="true">{BRAND_TAIL}</span></span>')


def wordmark_css(sel: str = ".gw", size: float = 22.0, color: str = "#fff", faint: str = "") -> str:
    """CSS نشانه نوشتاری در اندازه ``size`` پیکسل؛ بدون نویسه «کوچک‌تر» (شرط DOMPurify).

    دنباله «ntelligence» متن بسیار کم‌رنگ با فاصله حروف باز است و زیر نیمه پایینش نوارهای
    عمودی با پهنای متفاوت (مثل بارکد) کشیده می‌شود."""
    z = float(size)
    faint = faint or "rgba(167,224,212,.16)"
    u = max(1.0, z / 26.0)            # پهنای پایه نوار؛ با اندازه نشانه بزرگ می‌شود

    def px(n: float) -> str:
        return f"{n*u:.1f}px"
    bars = (f"repeating-linear-gradient(90deg,rgba(167,224,212,.17) 0 {px(1)},transparent {px(1)} {px(3)},"
            f"rgba(167,224,212,.10) {px(3)} {px(5)},transparent {px(5)} {px(6)},rgba(167,224,212,.14) {px(6)} {px(7)},"
            f"transparent {px(7)} {px(10)},rgba(167,224,212,.08) {px(10)} {px(12)},transparent {px(12)} {px(13)})")
    return (f"{sel}{{direction:ltr;unicode-bidi:isolate;display:inline-flex;align-items:baseline;line-height:1;"
            f"white-space:nowrap;font-size:{z:.1f}px}}"
            f"{sel}-gs{{font-weight:800;letter-spacing:{z*.02:.2f}px;color:{color};font-size:1em}}"
            f"{sel}-i{{font-weight:700;color:{color};font-size:.8em;margin-inline-start:{z*.03:.2f}px}}"
            f"{sel}-tail{{font-weight:300;font-size:.42em;letter-spacing:.22em;color:{faint};"
            f"margin-inline-start:{z*.02:.2f}px;padding:0 .1em {z*.06:.2f}px 0;"
            f"background:{bars} left bottom/100% 45% no-repeat}}")


def email_wordmark(font: str = "Tahoma,Arial,sans-serif", size: int = 13, color: str = "") -> str:
    """نسخه ایمیل (Outlook): فقط استایل درون‌خطی و رنگ؛ گرادیان بارکد در Outlook دیده نمی‌شود."""
    color = color or MINT
    return (f'<span style="font-family:{font};white-space:nowrap;direction:ltr">'
            f'<span style="color:{color};font-weight:800;font-size:{size}px">GS</span>'
            f'<span style="color:{color};font-weight:700;font-size:{round(size*.8)}px">i</span>'
            f'<span style="color:{PINE};font-weight:300;font-size:{round(size*.6)}px;'
            f'letter-spacing:2px">{BRAND_TAIL}</span></span>')


def _svg_uri(svg: str) -> str:
    return "data:image/svg+xml," + quote(svg, safe=" =:/;,.-_()'")


def texture_uri(width: int = 1200, height: int = 240, trace: bool = True) -> str:
    """شبکه نقطه‌ای، کمان‌های مداری و خط جریان؛ همه کم‌رنگ، هیچ‌کدام متن نیست."""
    w, h = int(width), int(height)
    cx, cy = w * 0.10, h * 0.50
    arcs = "".join(
        f"<circle cx='{cx:.0f}' cy='{cy:.0f}' r='{r}' fill='none' stroke='{MINT}' "
        f"stroke-opacity='{op}' stroke-width='1'/>"
        for r, op in ((h * 0.55, .10), (h * 0.85, .07), (h * 1.2, .05), (h * 1.65, .035)))
    dots = (f"<pattern id='d' width='22' height='22' patternUnits='userSpaceOnUse'>"
            f"<circle cx='1.2' cy='1.2' r='1.1' fill='{MINT}' fill-opacity='.10'/></pattern>")
    fade = (f"<linearGradient id='f' x1='0' x2='1'><stop offset='0' stop-color='#fff' stop-opacity='0'/>"
            f"<stop offset='.55' stop-color='#fff' stop-opacity='.9'/><stop offset='1' stop-color='#fff' "
            f"stop-opacity='.2'/></linearGradient><mask id='m'><rect width='{w}' height='{h}' fill='url(#f)'/></mask>")
    y = h * 0.82
    trace = (f"<path d='M{w*.42:.0f} {y:.0f} H{w*.70:.0f} l14 -14 H{w*.96:.0f}' fill='none' stroke='{TEAL_2}' "
             f"stroke-opacity='.28' stroke-width='1'/>"
             f"<circle cx='{w*.70:.0f}' cy='{y:.0f}' r='2.5' fill='{TEAL_2}' fill-opacity='.6'/>"
             f"<circle cx='{w*.96:.0f}' cy='{y-14:.0f}' r='3' fill='{GOLD}'/>") if trace else ""
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}' "
           f"preserveAspectRatio='xMidYMid slice'><defs>{dots}{fade}</defs>"
           f"<rect width='{w}' height='{h}' fill='url(#d)' mask='url(#m)'/>{arcs}{trace}</svg>")
    return _svg_uri(svg)


def band_css(scope: str = ".gsi-band") -> str:
    """CSS سربرگ؛ بدون نویسه «کوچک‌تر» (شرط DOMPurify در Streamlit)."""
    s = scope
    tex = texture_uri(trace=False)
    return f"""
{s}{{position:relative;overflow:hidden;isolation:isolate;border-radius:20px;color:{INK};
  background:linear-gradient(105deg,{DARK} 0%,{DEEP} 62%,{DEEP} 100%);
  padding:22px 28px 24px;box-shadow:0 18px 40px -24px rgba(3,21,18,.55);font-family:inherit}}
{s}::before{{content:"";position:absolute;inset:0;z-index:-1;background:url("{tex}") center/cover no-repeat}}
{s}[dir="rtl"]::before,[dir="rtl"] {s}::before{{transform:scaleX(-1)}}
{s}::after{{content:"";position:absolute;z-index:-1;width:360px;height:360px;top:-150px;
  inset-inline-start:-110px;border-radius:50%;
  background:radial-gradient(closest-side,rgba(95,179,160,.30),rgba(47,125,109,.10) 55%,transparent)}}
{s} .gb-top{{display:flex;align-items:center;gap:16px;flex-wrap:wrap}}
{s} .gb-mark{{width:44px;height:auto;flex:none;filter:drop-shadow(0 0 14px rgba(167,224,212,.28))}}
{s} .gb-id{{display:flex;flex-direction:column;gap:2px;min-width:0}}
{s} .gb-word{{direction:ltr;unicode-bidi:isolate;display:flex;align-items:center;gap:10px;line-height:1.1}}
{wordmark_css(s + " .gw", 30)}
{s} .gb-word>i{{width:1px;height:18px;background:{TEAL_2};opacity:.7}}
{s} .gb-word>span.gb-name{{font-size:12px;font-weight:600;color:{MUTE};letter-spacing:1.4px;text-transform:uppercase;white-space:nowrap}}
{s} .gb-tag{{font-size:11.5px;color:{MINT};opacity:.9}}
{s} .gb-flow{{direction:ltr;unicode-bidi:isolate;margin-inline-start:auto;display:flex;align-items:center;
  gap:8px;font-size:10.5px;letter-spacing:2.2px;text-transform:uppercase;color:{MUTE}}}
{s} .gb-flow u{{text-decoration:none;display:inline-block;width:22px;height:1px;background:{TEAL};opacity:.9}}
{s} .gb-flow .gb-dot{{width:6px;height:6px;border-radius:50%;background:{TEAL_2}}}
{s} .gb-flow .gb-dot.gold{{background:{GOLD};box-shadow:0 0 0 3px rgba(224,176,79,.18)}}
{s} .gb-rule{{height:1px;margin:16px 0 14px;background:linear-gradient(90deg,rgba(95,179,160,.0),
  rgba(95,179,160,.55) 18%,rgba(95,179,160,.18) 70%,rgba(95,179,160,0))}}
{s} .gb-main{{display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap}}
{s} .gb-titles{{flex:1 1 320px;min-width:0}}
{s} .gb-eyebrow{{font-size:10.5px;letter-spacing:1.6px;color:{TEAL_2};font-weight:700}}
{s} h1.gb-h1{{margin:2px 0 0;font-size:25px;line-height:1.35;font-weight:800;color:#fff}}
{s} .gb-sub{{margin-top:4px;font-size:12.5px;color:{MUTE}}}
{s} .gb-stats{{display:flex;gap:8px;flex-wrap:wrap}}
{s} .gb-stat{{display:flex;flex-direction:column;align-items:center;min-width:84px;padding:6px 12px;
  border-radius:12px;background:rgba(234,246,242,.06);border:1px solid rgba(167,224,212,.22);color:{INK}}}
{s} .gb-stat b{{font-size:19px;font-weight:800;line-height:1.3;color:#fff;font-variant-numeric:tabular-nums}}
{s} .gb-stat span{{font-size:10.5px;color:{MINT}}}
{s} .gb-stat[data-tone="stockout"],{s} .gb-stat[data-tone="critical"]{{border-color:rgba(224,83,63,.65)}}
{s} .gb-stat[data-tone="stockout"] span,{s} .gb-stat[data-tone="critical"] span{{color:{ALERT}}}
{s} .gb-stat[data-tone="serious"],{s} .gb-stat[data-tone="warning"]{{border-color:rgba(224,176,79,.6)}}
{s} .gb-actions{{display:flex;gap:8px;flex-wrap:wrap}}
{s} .gb-actions .btn{{background:rgba(234,246,242,.08);color:{INK};border:1px solid rgba(167,224,212,.3)}}
{s} .gb-actions .btn:hover{{background:rgba(234,246,242,.16)}}
{s} .gx-chips{{margin-inline-start:0}}
{s} .gx-chip{{background:rgba(234,246,242,.06);border:1px solid rgba(167,224,212,.22);color:{INK}}}
{s} .gx-chip b{{color:#fff}}
{s} .gx-chip.is-alert{{background:rgba(224,83,63,.12);border-color:rgba(224,83,63,.65);color:{ALERT}}}
{s} .gx-chip.is-alert b{{color:{ALERT}}}
{s} .gx-dl,{s} .gx-dls a{{background:rgba(234,246,242,.08);color:{INK};border:1px solid rgba(167,224,212,.3)}}
{s} .ltr{{direction:ltr;unicode-bidi:isolate}}
@media (max-width:640px){{{s}{{padding:18px 16px}} {s} .gb-flow{{display:none}} {s} h1.gb-h1{{font-size:21px}}}}
@media print{{{s}{{box-shadow:none;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  {s} .gb-actions{{display:none}}}}
"""


def _flow_html() -> str:
    parts = []
    for i, word in enumerate(FLOW):
        if i:
            parts.append("<u></u>")
        gold = " gold" if i == len(FLOW) - 1 else ""
        parts.append(f'<span class="gb-dot{gold}"></span>{esc(word)}')
    return "".join(parts)


def band_raw(title_html: str, *, sub_html: str = "", eyebrow_html: str = "", side_html: str = "",
             tag: str = TAGLINE_FA, scope_class: str = "gsi-band", dir: str = "") -> str:
    """سربرگ با تکه‌های HTML آماده (برای گزارش‌هایی که عنوان و تراشه‌هایشان را خودشان می‌سازند)."""
    mark = mark_data_uri()
    img = f'<img class="gb-mark" src="{mark}" alt="{BRAND_TEXT}">' if mark else ""
    eb = f'<div class="gb-eyebrow">{eyebrow_html}</div>' if eyebrow_html else ""
    sub = f'<div class="gb-sub">{sub_html}</div>' if sub_html else ""
    d = f' dir="{esc(dir)}"' if dir else ""
    return (f'<header class="{esc(scope_class)}"{d} role="banner">'
            f'<div class="gb-top">{img}<div class="gb-id">'
            f'<div class="gb-word">{wordmark_html()}<i></i><span class="gb-name">{esc(BRAND_SUB)}</span></div>'
            f'<div class="gb-tag">{esc(tag)}</div></div>'
            f'<div class="gb-flow" aria-label="Data, Process, Decision">{_flow_html()}</div></div>'
            f'<div class="gb-rule"></div>'
            f'<div class="gb-main"><div class="gb-titles">{eb}<h1 class="gb-h1">{title_html}</h1>{sub}</div>'
            f'{side_html}</div></header>')


def band_html(title: str, *, subtitle: str = "", eyebrow: str = "", stats: Sequence[Tuple[str, str, str]] = (),
              actions: str = "", tag: str = TAGLINE_FA, scope_class: str = "gsi-band", dir: str = "") -> str:
    """سربرگ یک گزارش. ``stats``: (برچسب، مقدار، کلید وضعیت یا «»). ``actions`` HTML آماده است."""
    pills = "".join(
        f'<div class="gb-stat"{f" data-tone={chr(34)}{esc(t)}{chr(34)}" if t else ""}>'
        f'<b>{esc(v)}</b><span>{esc(k)}</span></div>' for k, v, t in stats)
    side = (f'<div class="gb-stats">{pills}</div>' if pills else "") + \
           (f'<div class="gb-actions no-print">{actions}</div>' if actions else "")
    return band_raw(esc(title), sub_html=esc(subtitle), eyebrow_html=esc(eyebrow), side_html=side,
                    tag=tag, scope_class=scope_class, dir=dir)


# ── ایمیل ────────────────────────────────────────────────────────────────
def email_header_html(title: str, subtitle: str = "", *, font: str = "Tahoma,Arial,sans-serif",
                      with_image: bool = True) -> str:
    """ردیف‌های جدول سربرگ ایمیل (برای ``<table>`` بیرونی): تصویر برند با CID و عنوان زنده.

    Outlook رنگ ``bgcolor`` سلول را نشان می‌دهد ولی SVG و گرادیان را نه؛ پس طرح برند تصویر است و
    عنوان متن، روی همان رنگ تیره."""
    img = (f'<tr><td bgcolor="{DEEP}" style="background:{DEEP};padding:0;line-height:0;font-size:0">'
           f'<img src="cid:{EMAIL_HEADER_CID}" width="{EMAIL_HEADER_WIDTH}" alt="{BRAND_TEXT} · {esc(NAME_EN)}" '
           f'style="display:block;width:100%;max-width:{EMAIL_HEADER_WIDTH}px;height:auto;border:0"></td></tr>'
           if with_image else "")
    sub = (f'<div style="color:{MUTE};font-size:12.5px;margin-top:4px;font-family:{font}">{esc(subtitle)}</div>'
           if subtitle else "")
    return (f'{img}<tr><td bgcolor="{DEEP}" style="background:{DEEP};padding:4px 28px 22px;font-family:{font};'
            f'border-bottom:3px solid {GOLD}">'
            f'<div style="color:#ffffff;font-size:22px;font-weight:800;line-height:1.5;font-family:{font}">'
            f'{esc(title)}</div>{sub}</td></tr>')


def email_footer_html(font: str = "Tahoma,Arial,sans-serif") -> str:
    return (f'<tr><td bgcolor="{DEEP}" style="background:{DEEP};padding:12px 24px;color:{MUTE};font-size:11px;'
            f'font-family:{font}">{email_wordmark(font)} · {esc(NAME_EN)} · '
            f'زنجیره تأمین صنعت خودرو · Data • Process • Decision</td></tr>')


def attach_email_header(mail) -> bool:
    """تصویر سربرگ را در پیام Outlook به‌صورت درون‌خطی (CID) پیوست می‌کند."""
    path = EMAIL_HEADER_PATH
    if not path.exists():
        return False
    try:
        att = mail.Attachments.Add(str(path.resolve()), 1, 0, path.name)
        acc = att.PropertyAccessor
    except AttributeError:
        return False
    acc.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F", EMAIL_HEADER_CID)
    try:
        acc.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3716001F", "inline")
        acc.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x7FFE000B", True)  # پنهان از فهرست پیوست
    except Exception:
        pass
    return True


# ── تصویر مستقل (برای ساخت PNG با مرورگر) ─────────────────────────────────
def art_html(width: int = 1536, height: int = 512, font_css: str = "", tagline: str = TAGLINE_FA,
             mark_uri: str = "", base_line: bool = True) -> str:
    """صفحه‌ای که فقط طرح برند است (نسبت ۳ به ۱ مثل هدر قبلی)؛ برای خروجی PNG و سربرگ ایمیل."""
    w, h = int(width), int(height)
    k = h / 512.0
    mark = mark_uri or mark_data_uri()
    tex = texture_uri(w, h)
    flow = _flow_html()
    return f"""<!doctype html><html lang="fa"><head><meta charset="utf-8"><style>
{font_css}
html,body{{margin:0;padding:0;background:{DEEP}}}
.art{{position:relative;width:{w}px;height:{h}px;overflow:hidden;isolation:isolate;color:{INK};
  font-family:'Ravi','IRANSansWeb','IRANSans',Tahoma,sans-serif;
  background:linear-gradient(105deg,{DARK} 0%,{DEEP} 58%,{DEEP} 100%)}}
.art::before{{content:"";position:absolute;inset:0;z-index:-1;background:url("{tex}") center/cover no-repeat}}
.glow{{position:absolute;z-index:-1;left:{-150*k:.0f}px;top:{-190*k:.0f}px;width:{900*k:.0f}px;height:{900*k:.0f}px;
  border-radius:50%;background:radial-gradient(closest-side,rgba(95,179,160,.30),rgba(47,125,109,.10) 55%,transparent)}}
.row{{position:absolute;inset:0;display:flex;align-items:center;direction:ltr;padding:0 {110*k:.0f}px;gap:{64*k:.0f}px}}
.mark{{height:{300*k:.0f}px;filter:drop-shadow(0 0 {34*k:.0f}px rgba(167,224,212,.30))}}
.vr{{width:1px;height:{250*k:.0f}px;background:linear-gradient(180deg,transparent,rgba(95,179,160,.7),transparent)}}
.id{{display:flex;flex-direction:column;gap:{14*k:.0f}px}}
.word{{display:flex;align-items:center;gap:{26*k:.0f}px;line-height:1}}
{wordmark_css(".word .gw", 128*k)}
.word>i{{width:{2*k:.1f}px;height:{92*k:.0f}px;background:{TEAL_2}}}
.word>span.name{{font-size:{27*k:.0f}px;font-weight:600;color:{MUTE};letter-spacing:{4*k:.1f}px;text-transform:uppercase;white-space:nowrap}}
.flow{{display:flex;align-items:center;gap:{16*k:.0f}px;font-size:{25*k:.0f}px;letter-spacing:{7*k:.1f}px;
  text-transform:uppercase;color:{MUTE};margin-top:{6*k:.0f}px}}
.flow u{{text-decoration:none;display:inline-block;width:{54*k:.0f}px;height:{1.5*k:.1f}px;background:{TEAL}}}
.flow .gb-dot{{width:{11*k:.0f}px;height:{11*k:.0f}px;border-radius:50%;background:{TEAL_2}}}
.flow .gb-dot.gold{{background:{GOLD};box-shadow:0 0 0 {6*k:.0f}px rgba(224,176,79,.18)}}
.tag{{direction:rtl;text-align:left;font-size:{34*k:.0f}px;color:{MINT};margin-top:{10*k:.0f}px}}
.base{{position:absolute;left:0;right:0;bottom:0;height:{3*k:.1f}px;
  background:linear-gradient(90deg,transparent 0%,{TEAL} 30%,{GOLD} 70%,transparent 100%);opacity:.8}}
</style></head><body><div class="art"><div class="glow"></div><div class="row">
<img class="mark" src="{mark}" alt=""><div class="vr"></div>
<div class="id"><div class="word">{wordmark_html()}<i></i><span class="name">{esc(BRAND_SUB)}</span></div>
<div class="flow">{flow}</div><div class="tag">{esc(tagline)}</div></div></div>{'<div class="base"></div>' if base_line else ''}</div></body></html>"""
