# -*- coding: utf-8 -*-
"""اجزای HTML مشترک چرخه ارز و گزارش مالی: یک نشانه‌گذاری برای Studio و HTML ارسالی.

Studio همین تکه‌ها را با ``st.html`` نشان می‌دهد و گزارش HTML مستقل همان‌ها را
کنار هم می‌گذارد. پس کارت، حلقه، مسیر مراحل، جدول و رنگ‌ها در هر دو یکی است و
کاربری که ایمیل را باز می‌کند همان تصویری را می‌بیند که کارشناس در Studio دیده.

تعامل فقط با CSS است (``input:checked`` و ``<details>``)، بدون JavaScript:

* Studio محتوای ``st.html`` را بدون iframe و بدون اجرای اسکریپت نشان می‌دهد؛
* گزارش HTML در Outlook، مرورگر اداری و حالت آفلاین باز می‌شود.

کلیک روی هر مرحله پرونده‌های همان مرحله را باز می‌کند و هر پرونده سلسله‌مراتب
«ثبت سفارش ← سفارش ← متریال» را همراه بارنامه‌ها، جریان پول و تصمیم‌های مالی
نشان می‌دهد. رنگ‌ها فقط از توکن‌های طراحی می‌آیند.
"""
from __future__ import annotations

import base64
import functools
import html
import zlib
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import pandas as pd

from ..design import icons as I
from ..design import brand as _BRAND
from ..design import tokens as T
from ..i18n import columns as C
from . import critical_board as CB
from . import fx_insight as X

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _css_icons(fn: Callable) -> Callable:
    """آیکن و گیج این جزء بدون SVG ساخته می‌شود (``st.html`` در Studio SVG را حذف
    می‌کند)؛ پس Studio و گزارش HTML دقیقاً یک نشانه‌گذاری دارند."""
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with I.css_icons():
            return fn(*args, **kwargs)
    return wrapper


# ═══════════════════════════════ کمکی ═══════════════════════════════
def esc(v: Any) -> str:
    return html.escape(X.s(v))


def L(text: str, lang: str = C.FA) -> str:
    """برچسب رابط در زبان خواسته‌شده؛ انگلیسی داخل ``<bdi>`` تا جهت متن نشکند."""
    if lang == C.EN:
        return f"<bdi>{html.escape(X.tr(text, C.EN))}</bdi>"
    return html.escape(text)


def amount(v: Any, ccy: str = "", nd: int = 2) -> str:
    x = X.n(v)
    if x is None:
        return '<span class="gx-na">—</span>'
    c = f' <small class="gx-ccy">{html.escape(ccy)}</small>' if ccy else ""
    return f'<span class="gx-num">{x:,.{nd}f}</span>{c}'


def days(v: Any) -> str:
    x = X.n(v)
    return "—" if x is None else f"{x:,.0f}"


def pct(v: Any, nd: int = 1, lang: str = C.FA) -> str:
    x = X.n(v)
    return "—" if x is None else f"{x:,.{nd}f}{'%' if lang == C.EN else '٪'}"


def E(v: Any, lang: str = C.FA) -> str:
    """مقدار شمارشی (مرحله، وضعیت، کجاست) در زبان خواسته‌شده، escape‌شده."""
    return html.escape(X.tr(v, lang))


def ccy_label(c: Any, lang: str = C.FA) -> str:
    """کد ارز همان‌طور که هست؛ فقط «نامشخص» (ارز نامعلوم) ترجمه می‌شود."""
    t = X.s(c) or "نامشخص"
    return html.escape(X.tr(t, lang) if t == "نامشخص" else t)


def uid(*parts: Any) -> str:
    return "g" + format(zlib.crc32("|".join(map(str, parts)).encode("utf-8")), "x")


def pill(text: str, tone: str, lang: str = C.FA) -> str:
    st = T.STATUS.get(tone, T.STATUS["unknown"])
    if not X.s(text):
        return ""
    return (f'<span class="gx-pill" style="color:{st.ink};background:{st.wash};border-color:{st.ink}">'
            f'{html.escape(st.icon)} {html.escape(X.tr(text, lang))}</span>')


def level_badge(code: str, lang: str = C.FA) -> str:
    if not code:
        return ""
    key, label, _ = CB.LEVELS.get(code, CB.LEVELS["UNKNOWN"])
    st = T.STATUS[key]
    return (f'<span class="gx-pill" style="color:{st.ink};background:{st.wash};border-color:{st.ink}">'
            f'{html.escape(st.icon)} {L(label, lang)}</span>')


def bar(p: Any, tone: str = "brand") -> str:
    """نوار پیشرفت؛ نامعلوم ← نوار خط‌چین خالی، بیش از ۱۰۰ ← رنگ بحرانی."""
    x = X.n(p)
    if x is None:
        return '<span class="gx-bar is-na"><i></i></span>'
    over = x > 100.5
    w = max(0.0, min(x, 100.0))
    cls = "gx-bar is-over" if over or tone == "critical" else "gx-bar"
    return f'<span class="{cls}"><i style="width:{w:.1f}%"></i></span>'


@_css_icons
def data_link(data: bytes, filename: str, label: str, icon: str = "file", mime: str = XLSX_MIME,
              lang: str = C.FA) -> str:
    """پیوند دانلود داخل خود HTML (data URI) — بدون سرور و بدون فایل جانبی."""
    b64 = base64.b64encode(data).decode("ascii")
    return (f'<a class="gx-dl" download="{html.escape(filename, quote=True)}" '
            f'href="data:{mime};base64,{b64}">{I.icon(icon, 16)}<span>{L(label, lang)}</span></a>')


# ═══════════════════════════════ CSS ═══════════════════════════════
def css() -> str:
    """شیوه‌نامه همه اجزا؛ فقط توکن‌ها. در Studio و HTML یکی است."""
    raised, inset, overlay = T.ELEVATION["raised"], T.ELEVATION["inset"], T.ELEVATION["overlay"]
    R = T.RADIUS
    grad = f"linear-gradient(135deg,{T.TEAL_PALETTE[3]},{T.TEAL_PALETTE[7]})"
    stage_rules = "\n".join(
        f".gx-r{i}:checked~.gx-rail .gx-st{i}{{background:{grad};color:{T.TEXT_ON_BRAND};box-shadow:{overlay}}}"
        f".gx-r{i}:checked~.gx-rail .gx-st{i} .gx-st-lab,.gx-r{i}:checked~.gx-rail .gx-st{i} .gx-st-n"
        f"{{color:{T.TEXT_ON_BRAND}}}"
        f".gx-r{i}:checked~.gx-rail .gx-st{i} .gx-st-ic{{background:rgba(255,255,255,.18);color:{T.TEXT_ON_BRAND};box-shadow:none}}"
        f".gx-r{i}:checked~.gx-panels .gx-p{i}{{display:block}}"
        f".gx-r{i}:focus-visible~.gx-rail .gx-st{i}{{outline:3px solid {T.BORDER_FOCUS};outline-offset:2px}}"
        for i in range(len(X.STAGES)))
    tab_rules = "\n".join(
        f".gx-t{i}:checked~.gx-tabs .gx-tb{i}{{background:{T.TEAL_INK};color:{T.TEXT_ON_BRAND}}}"
        f".gx-t{i}:checked~.gx-tabs .gx-tb{i} .mi-svg{{color:{T.TEXT_ON_BRAND}}}"
        f".gx-t{i}:checked~.gx-tpanes .gx-tp{i}{{display:block}}"
        f".gx-t{i}:focus-visible~.gx-tabs .gx-tb{i}{{outline:3px solid {T.BORDER_FOCUS};outline-offset:2px}}"
        for i in range(10))
    from ..design.css import _vars
    return f"""
.gx{{{_vars()}}}
.gx{{color:{T.TEXT};font-family:{T.FONT_STACK};direction:rtl;line-height:1.75;font-size:13px}}
[dir="ltr"] .gx,.gx[dir="ltr"]{{direction:ltr}}
.gx *{{box-sizing:border-box}}
.gx h1,.gx h2,.gx h3,.gx h4,.gx h5{{margin:0;line-height:1.4;color:{T.TEXT};font-family:inherit}}
.gx small{{color:{T.TEXT_MUTED};font-size:11px}}
.gx .ltr,.gx .gx-key{{direction:ltr;unicode-bidi:isolate}}
.gx-num{{font-variant-numeric:tabular-nums;white-space:nowrap}}
.gx-na{{color:{T.TEXT_MUTED}}}
.gx-ccy{{font-weight:700;color:{T.TEXT_SECONDARY}}}
.gx-card{{background:{T.SURFACE_RAISED};border-radius:{R['xl']}px;box-shadow:{raised};padding:16px 18px}}
.gx-sec{{margin:22px 0 10px;display:flex;gap:10px;align-items:center}}
.gx-sec h3{{font-size:16px;font-weight:800}}
.gx-part>.gx-sec:first-child{{margin-top:0}}
.gx-sec small{{margin-inline-start:auto}}
.gx-note{{font-size:12px;color:{T.TEXT_SECONDARY};margin:4px 0 10px}}
.gx-pill{{display:inline-flex;align-items:center;gap:5px;border:1px solid;border-radius:{R['pill']}px;
  padding:1px 9px;font-size:11px;font-weight:800;white-space:nowrap;line-height:1.7}}
.gx-chip{{display:inline-flex;align-items:center;gap:6px;border-radius:{R['pill']}px;padding:3px 11px;
  background:{T.SURFACE_SUNKEN};color:{T.TEXT_SECONDARY};font-size:11.5px;font-weight:700;white-space:nowrap}}
.gx-chip b{{color:{T.TEAL_INK}}}
.gx-chip.is-alert{{background:{T.STATUS['critical'].wash};color:{T.STATUS['critical'].ink}}}
.gx-chip.is-alert b{{color:{T.STATUS['critical'].ink}}}
.gx-chips{{display:flex;flex-wrap:wrap;gap:6px;align-items:center}}
.gx-bar{{display:inline-block;width:92px;height:8px;border-radius:{R['pill']}px;background:{T.SURFACE_SUNKEN};
  box-shadow:{inset};overflow:hidden;vertical-align:middle}}
.gx-bar i{{display:block;height:100%;border-radius:{R['pill']}px;background:linear-gradient(270deg,{T.TEAL_PALETTE[3]},{T.TEAL_PALETTE[7]})}}
.gx-bar.is-over i{{background:{T.STATUS['critical'].fill}}}
.gx-bar.is-na{{background:transparent;box-shadow:none;border:1px dashed {T.BORDER_STRONG}}}
.gx-bar.is-na i{{display:none}}
.gx .mi-kpis{{grid-template-columns:repeat(auto-fit,minmax(124px,1fr));gap:12px}}
.gx .mi-kpi{{flex-direction:column;align-items:flex-start;gap:9px;padding:13px 14px 12px}}
.gx .mi-kpi .mi-tile{{width:36px;height:36px;border-radius:{R['sm'] + 2}px}}
.gx .mi-kpi-val{{font-size:21px}}
.gx .mi-kpi-lab{{font-size:11.5px;line-height:1.45}}
.gx-dl{{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:{R['md']}px;
  background:{T.SURFACE_RAISED};color:{T.TEAL_INK};font-weight:800;font-size:12px;text-decoration:none;
  box-shadow:{raised};border:1px solid {T.BORDER}}}
.gx-dl:hover{{background:{T.TEAL_WASH}}}
.gx-dl.is-primary{{background:{grad};color:{T.TEXT_ON_BRAND};border-color:transparent}}
.gx-dls{{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0}}
.gx-empty{{padding:18px;text-align:center;color:{T.TEXT_MUTED};background:{T.SURFACE_RAISED};
  border-radius:{R['lg']}px;box-shadow:{inset}}}
/* ── جدول ── */
.gx-tbl{{overflow:auto;background:{T.SURFACE_RAISED};border-radius:{R['lg']}px;box-shadow:{raised};margin:6px 0 14px}}
.gx-tbl table{{width:100%;border-collapse:collapse;font-size:12px}}
.gx-tbl th{{position:sticky;top:0;background:{T.SURFACE_SUNKEN};color:{T.TEXT_SECONDARY};text-align:start;
  padding:9px 10px;white-space:nowrap;font-weight:800;z-index:1}}
.gx-tbl td{{padding:8px 10px;border-top:1px solid {T.BORDER};vertical-align:top;white-space:nowrap}}
.gx-tbl tr:hover td{{background:{T.TEAL_WASH}}}
.gx-tbl td.n{{white-space:nowrap;font-variant-numeric:tabular-nums}}
.gx-tbl td.w{{min-width:230px;max-width:460px;white-space:normal}}
/* ── مسیر مراحل (کلیک‌پذیر) ── */
.gx-x{{position:relative}}
.gx-r,.gx-t,.gx-f{{position:absolute;opacity:0;width:1px;height:1px;pointer-events:none}}
.gx-x{{container-type:inline-size}}
.gx-rail{{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;padding:12px;
  background:{T.SURFACE_RAISED};border-radius:{R['xl']}px;box-shadow:{raised}}}
.gx label.gx-st,.gx label.gx-tb,.gx label.gx-fl{{min-width:0;max-width:none}}
.gx-st{{position:relative;display:flex;flex-direction:column;align-items:center;gap:4px;padding:10px 6px 9px;min-width:0;
  border-radius:{R['lg']}px;cursor:pointer;text-align:center;color:{T.TEXT_SECONDARY};
  transition:background .15s ease,box-shadow .15s ease;user-select:none}}
.gx-st:hover{{background:{T.TEAL_WASH}}}
.gx-st-ic{{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  background:{T.SURFACE_RAISED};color:{T.BRAND_TEAL};box-shadow:{raised}}}
.gx-st.is-empty .gx-st-ic{{color:{T.TEXT_MUTED};box-shadow:{inset}}}
.gx-st-n{{font-size:19px;font-weight:800;color:{T.TEAL_INK};line-height:1.1}}
.gx-st.is-empty .gx-st-n{{color:{T.TEXT_MUTED};font-weight:600}}
.gx-st-lab{{font-size:11px;line-height:1.35;color:{T.TEXT_SECONDARY};overflow-wrap:anywhere}}
.gx-st-share{{position:absolute;inset-inline:10px;bottom:3px;height:3px;border-radius:3px;background:{T.SURFACE_SUNKEN};overflow:hidden}}
.gx-st-share i{{display:block;height:100%;background:{T.TEAL_PALETTE[4]}}}
.gx-st-alert{{position:absolute;top:6px;inset-inline-start:8px;width:9px;height:9px;border-radius:50%;
  background:{T.STATUS['critical'].fill};box-shadow:0 0 0 2px {T.SURFACE_RAISED}}}
.gx-hint{{font-size:11.5px;color:{T.TEXT_MUTED};margin:8px 4px 12px;display:flex;gap:6px;align-items:center}}
.gx-panels{{margin-top:4px}}
.gx-panel{{display:none}}
.gx-phead{{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:4px 0 12px}}
.gx-phead h4{{font-size:16px;font-weight:800}}
.gx-phead .gx-dl{{margin-inline-start:auto}}
.gx-vals{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}}
.gx-val{{background:{T.SURFACE_RAISED};border-radius:{R['md']}px;box-shadow:{raised};padding:8px 12px;font-size:12px}}
.gx-val b{{font-size:15px;color:{T.TEXT}}} .gx-val>span{{display:block;color:{T.TEXT_MUTED};font-size:11px}}
/* ── پرونده (ثبت سفارش) ── */
.gx-regs{{display:grid;gap:10px}}
.gx-reg{{background:{T.SURFACE_RAISED};border-radius:{R['lg']}px;box-shadow:{raised};overflow:hidden}}
.gx-reg>summary{{list-style:none;cursor:pointer;display:grid;align-items:center;gap:12px;padding:12px 16px;
  grid-template-columns:minmax(150px,1.2fr) auto minmax(70px,.5fr) minmax(150px,1fr) minmax(150px,1fr) auto auto 12px}}
.gx-reg>summary::-webkit-details-marker{{display:none}}
.gx-reg>summary::after{{content:"";width:9px;height:9px;border-right:2px solid {T.TEXT_MUTED};
  border-bottom:2px solid {T.TEXT_MUTED};transform:rotate(135deg);justify-self:end;transition:transform .15s ease}}
.gx-reg[open]>summary::after{{transform:rotate(45deg)}}
[dir="ltr"] .gx-reg:not([open])>summary::after{{transform:rotate(-45deg)}}
.gx-reg[open]>summary{{background:{T.TEAL_WASH}}}
.gx-reg.is-crit{{box-shadow:{raised},inset -4px 0 0 {T.STATUS['critical'].fill}}}
[dir="ltr"] .gx-reg.is-crit{{box-shadow:{raised},inset 4px 0 0 {T.STATUS['critical'].fill}}}
.gx-id b{{display:block;font-size:13.5px;color:{T.TEXT}}} .gx-id small{{display:block}}
.gx-m{{font-size:12px}} .gx-m b{{display:block;font-size:14px;color:{T.TEXT}}} .gx-m small{{display:block}}
.gx-cnt{{font-size:11px;color:{T.TEXT_MUTED};white-space:nowrap}}
.gx-body{{padding:4px 16px 16px;border-top:1px solid {T.BORDER}}}
.gx-mini{{display:flex;gap:4px;align-items:center;margin:12px 0 4px;flex-wrap:wrap}}
.gx-mini i{{width:22px;height:6px;border-radius:3px;background:{T.SURFACE_SUNKEN}}}
.gx-mini i.is-done{{background:{T.TEAL_PALETTE[4]}}}
.gx-mini i.is-current{{background:{T.TEAL_INK};width:34px}}
.gx-mini i.is-gap{{background:transparent;border:1.5px dashed {T.STATUS['serious'].ink}}}
.gx-mini span{{font-size:11px;color:{T.TEXT_SECONDARY};margin-inline-start:8px}}
/* flex، نه grid با auto-fit: بخش تمام‌عرض همه ستون‌های خالی را نگه می‌داشت و جدول بارنامه سرریز می‌شد */
.gx-grid{{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px}}
.gx-box{{flex:1 1 300px;min-width:0;overflow-x:auto;background:{T.SURFACE_PAGE};border-radius:{R['md']}px;padding:12px 14px;box-shadow:{inset}}}
.gx-box.is-bls{{flex:2 1 420px}}
.gx-box.is-wide{{flex-basis:100%}}
.gx-box h5{{font-size:12.5px;font-weight:800;display:flex;gap:8px;align-items:center;margin-bottom:8px;color:{T.TEAL_INK}}}
.gx-box table{{width:100%;border-collapse:collapse;font-size:11.5px}}
.gx-box th{{text-align:start;color:{T.TEXT_MUTED};font-weight:700;padding:3px 6px;white-space:nowrap}}
.gx-box td{{padding:4px 6px;border-top:1px solid {T.BORDER};vertical-align:top}}
.gx-foot{{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;margin-top:12px;font-size:11.5px;color:{T.TEXT_SECONDARY}}}
.gx-foot .gx-dl{{margin-inline-start:auto}}
/* ── درخت سفارش ← متریال ── */
.gx-tree{{list-style:none;margin:0;padding:0;display:grid;gap:6px}}
.gx-tree details{{background:{T.SURFACE_RAISED};border-radius:{R['sm']}px;box-shadow:{raised}}}
.gx-tree summary{{cursor:pointer;display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;padding:7px 10px;font-size:12px}}
.gx-tree summary b{{color:{T.TEXT}}}
.gx-tree ul{{list-style:none;margin:0;padding:4px 12px 10px;display:grid;gap:4px;border-inline-start:2px solid {T.TEAL_PALETTE[1]};
  margin-inline-start:14px}}
.gx-tree li.gx-mat{{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;font-size:11.5px;padding:4px 0}}
.gx-mat .gx-key{{font-weight:800;color:{T.TEAL_INK}}}
.gx-dotlvl{{width:8px;height:8px;border-radius:50%;display:inline-block;flex:none}}
/* ── جریان پول ── */
.gx-flow{{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:8px}}
.gx-fstep{{background:{T.SURFACE_RAISED};border-radius:{R['md']}px;padding:9px 10px;box-shadow:{raised};position:relative}}
.gx-fstep span{{display:block;font-size:11px;color:{T.TEXT_MUTED}}}
.gx-fstep b{{display:block;font-size:13.5px;color:{T.TEXT};margin:2px 0 6px}}
.gx-fstep .gx-bar{{width:100%}}
.gx-fstep.is-na b{{color:{T.TEXT_MUTED}}}
.gx-fstep em{{font-style:normal;font-size:10.5px;color:{T.STATUS['serious'].ink}}}
.gx-ccyhead{{display:flex;align-items:center;gap:10px;margin:14px 0 8px}}
.gx-ccyhead b{{font-size:20px;color:{T.TEAL_INK};letter-spacing:.5px}}
.gx-dec{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}}
.gx-dec article{{background:{T.SURFACE_RAISED};border-radius:{R['md']}px;box-shadow:{raised};padding:12px 14px;font-size:12px;display:grid;gap:4px}}
.gx-dec article b{{font-size:14px}}
.gx-dec p{{margin:0;font-size:12px;line-height:1.75;color:{T.TEXT_SECONDARY}}}
.gx-dec .gx-act{{background:{T.TEAL_WASH};color:{T.TEAL_INK};border-radius:{R['sm']}px;padding:6px 8px}}
/* ── تب‌های گزارش ── */
.gx-tabs{{display:flex;flex-wrap:wrap;gap:6px;padding:6px;background:{T.SURFACE_RAISED};border-radius:{R['pill']}px;
  box-shadow:{raised};margin:16px 0 18px;position:sticky;top:8px;z-index:5}}
.gx-tb{{display:inline-flex;align-items:center;gap:7px;padding:8px 15px;border-radius:{R['pill']}px;cursor:pointer;
  font-weight:800;font-size:12.5px;color:{T.TEXT_SECONDARY};user-select:none}}
.gx-tb:hover{{background:{T.TEAL_WASH}}}
.gx-tb .mi-svg{{color:{T.BRAND_TEAL}}}
.gx-tpane{{display:none}}
/* ── صفحه مستقل ── */
.gx-page{{margin:0;background:{T.SURFACE_PAGE}}}
.gx-wrap{{max-width:{T.CONTAINER_MAX}px;margin:0 auto;padding:22px 16px 48px}}
.gx-hero{{display:flex;flex-wrap:wrap;gap:16px;align-items:center;background:{T.SURFACE_RAISED};border-radius:{R['xl']}px;
  box-shadow:{raised};padding:20px 24px}}
.gx-hero .mi-tile{{width:56px;height:56px;border-radius:18px}}
.gx-hero .k{{font-size:11px;font-weight:800;color:{T.BRAND_TEAL};letter-spacing:.3px}}
.gx-hero h1{{font-size:23px;font-weight:800;margin:2px 0}}
.gx-hero p{{margin:0;font-size:12px;color:{T.TEXT_SECONDARY}}}
.gx-hero .gx-chips{{margin-inline-start:auto}}
.gx-legal{{margin-top:26px;font-size:11px;color:{T.TEXT_MUTED};line-height:1.9;border-top:1px solid {T.BORDER};padding-top:12px}}
{stage_rules}
{tab_rules}
.gx-f:checked~.gx-panels .gx-reg:not(.is-crit){{display:none}}
.gx-fl{{display:inline-flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;font-weight:700;color:{T.TEXT_SECONDARY};
  margin:10px 4px 0;user-select:none}}
.gx-fl i{{width:30px;height:17px;border-radius:{R['pill']}px;background:{T.SURFACE_SUNKEN};box-shadow:{inset};position:relative}}
.gx-fl i::after{{content:"";position:absolute;top:2px;inset-inline-start:2px;width:13px;height:13px;border-radius:50%;
  background:{T.SURFACE_RAISED};box-shadow:{raised};transition:inset-inline-start .15s ease}}
.gx-f:checked~.gx-fl i{{background:{T.STATUS['critical'].fill}}}
.gx-f:checked~.gx-fl i::after{{inset-inline-start:15px}}
@media (max-width:900px){{.gx-reg>summary{{grid-template-columns:1fr 1fr}}.gx-reg>summary::after{{display:none}}}}
@container (max-width:760px){{.gx-rail{{grid-template-columns:repeat(auto-fit,minmax(92px,1fr))}}}}
@media print{{.gx-tabs,.gx-rail,.gx-hint,.gx-dl,.gx-fl{{display:none!important}}.gx-tpane,.gx-panel{{display:block!important}}
  .gx-card,.gx-reg,.gx-tbl,.gx-hero{{box-shadow:none;border:1px solid {T.BORDER}}}}}
{I.minimal_css()}
{I.css_icons_css()}
"""


def style_tag() -> str:
    return f"<style>{css()}</style>"


# ═══════════════════════════ جدول عمومی ═══════════════════════════
def _codes(v: Any, lang: str) -> Any:
    """فهرست کدها («R4، R5») در حالت انگلیسی ویرگول لاتین می‌گیرد؛ متن فارسی داده دست نمی‌خورد."""
    t = X.s(v)
    if lang == C.EN and "، " in t and not C.is_persian(t.replace("، ", "")):
        return t.replace("، ", ", ")
    return v


def table(frame: pd.DataFrame, lang: str = C.FA, numeric: Sequence[str] = (), cells: Optional[Dict[str, Callable]] = None,
          max_rows: int = 500) -> str:
    """جدول HTML سبک؛ ستون‌های عددی با سه‌رقم جداکننده، نامعلوم «—»."""
    if frame is None or frame.empty:
        return f'<div class="gx-empty">{L("داده‌ای نیست", lang)}</div>'
    cells = cells or {}
    shown = frame.head(max_rows)
    # ستون متنی بلند (مثل فهرست گام‌های بی‌شاهد) عرض کافی می‌گیرد تا ردیف‌ها بلند نشوند
    wide = {c for c in shown.columns if c not in numeric and c not in cells
            and shown[c].map(lambda v: len(X.s(v))).max() > 36}
    head = "".join(f"<th>{L(str(c), lang)}</th>" for c in frame.columns)
    body = []
    for _, r in shown.iterrows():
        tds = []
        for c in frame.columns:
            v = r[c]
            if c in cells:
                tds.append(f"<td>{cells[c](v, r)}</td>")
            elif c in numeric:
                x = X.n(v)
                tds.append(f'<td class="n">{"—" if x is None else f"{x:,.2f}"}</td>')
            else:
                txt = html.escape(X.tr(v, lang)) if c in X.ENUM_COLS else esc(_codes(v, lang))
                tds.append(f'<td class="w">{txt or "—"}</td>' if c in wide else f"<td>{txt or '—'}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    more = (f'<div class="gx-note">{len(frame) - max_rows:,} {L("ردیف دیگر در فایل Excel", lang)}</div>'
            if len(frame) > max_rows else "")
    return f'<div class="gx-tbl"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>{more}'


# ═══════════════════════════ KPI ها ═══════════════════════════
@_css_icons
def kpis(fx: X.FxData, lang: str = C.FA) -> str:
    regs = fx.reg_table
    closed = int(regs["STAGE_CODE"].eq("CLOSED").sum()) if not regs.empty else 0
    over = int(regs["LINK_STATUS"].eq("حمل بیش از ارزش ثبت سفارش").sum()) if not regs.empty else 0
    ccy = int(regs["LINK_STATUS"].eq("ارز بارنامه ≠ ارز ثبت سفارش").sum()) if not regs.empty else 0
    overdue = int(regs["STAGE_STATUS"].eq(X.OVERDUE).sum()) if not regs.empty else 0
    crit = int(regs["CRITICAL_LEVEL"].isin(CB.DEFAULT_LEVELS).sum()) if not regs.empty else 0
    items = [("stamp", "ثبت سفارش در جریان", f"{len(regs) - closed:,}", "brand"),
             ("shield", "رفع تعهد کامل", f"{closed:,}", "brand"),
             ("queue", "در صف تخصیص", f"{len(fx.queue):,}", "brand"),
             ("alert", "ثبت سفارش با متریال بحرانی", f"{crit:,}", "critical" if crit else "brand"),
             ("clock", "مرحله سررسید گذشته", f"{overdue:,}", "critical" if overdue else "brand"),
             ("ship", "حمل بیش از ارزش ثبت سفارش", f"{over:,}", "critical" if over else "brand"),
             ("exchange", "ارز بارنامه متفاوت", f"{ccy:,}", "critical" if ccy else "brand")]
    return '<div class="mi-kpis">' + "".join(
        I.kpi_tile(ic, C.label(lab, lang) if lang == C.EN else lab, v, tone=tone) for ic, lab, v, tone in items) + "</div>"


# ═══════════════════════ نمای کلیک‌پذیر مراحل ═══════════════════════
def _values_html(values: List[Dict[str, Any]], lang: str) -> str:
    out = []
    for v in values:
        c = X.s(v.get("CURRENCY"))
        if c == "نامشخص":
            out.append(f'<div class="gx-val"><b>—</b><span>{v["REGISTRATIONS"]:,} {L("ثبت سفارش با ارز نامعلوم", lang)}</span></div>')
            continue
        unk = int(v.get("UNKNOWN_VALUE_REGS") or 0)
        extra = f' · {unk:,} {L("ارزش نامعلوم", lang)}' if unk else ""
        un = X.n(v.get("UNSHIPPED_VALUE"))
        over = int(v.get("OVERSHIPPED_REGS") or 0)
        at_most = f' ({L("حداکثر", lang)})' if int(v.get("UNSHIPPED_UPPER_BOUND_REGS") or 0) else ""
        out.append(f'<div class="gx-val"><b>{amount(v.get("REG_VALUE"), c)}</b>'
                   f'<span>{v["REGISTRATIONS"]:,} {L("ثبت سفارش", lang)}{extra}</span>'
                   f'<span>{L("مانده حمل‌نشده", lang)}{at_most}: {amount(un, c) if un is not None else "—"}'
                   + (f' · {over:,} {L("حمل بیش از ارزش", lang)}' if over else "") + '</span></div>')
    return f'<div class="gx-vals">{"".join(out)}</div>' if out else ""


def _mini_path(path: List[Dict[str, str]], lang: str) -> str:
    cur = next((p["label"] for p in path if p["state"] == "current"), "")
    cells = "".join(f'<i class="is-{p["state"]}" title="{E(p["label"], lang)} · {E(p["status"], lang)}"></i>'
                    for p in path)
    gaps = sum(1 for p in path if p["state"] == "gap")
    note = (f'{L("مرحله جاری", lang)}: {E(cur, lang)}' if cur else L("همه مراحل انجام شده", lang))
    if gaps:
        note += f' · {L("گام‌های بدون شاهد", lang)}: {gaps:,}'
    return f'<div class="gx-mini">{cells}<span>{note}</span></div>'


def _lvl_dot(code: str) -> str:
    key = CB.LEVELS.get(code, CB.LEVELS["UNKNOWN"])[0]
    return f'<span class="gx-dotlvl" style="background:{T.STATUS[key].fill}"></span>'


def _tree(orders: List[Dict[str, Any]], lang: str, open_first: bool = True) -> str:
    if not orders:
        return f'<div class="gx-note">{L("سفارشی برای این ثبت سفارش در مارت نیست", lang)}</div>'
    items = []
    for i, o in enumerate(orders):
        mats = "".join(
            f'<li class="gx-mat">{_lvl_dot(m["level"] or "UNKNOWN")}<span class="gx-key">{esc(m["key"])}</span>'
            f'<span>{esc(m["desc"]) or "—"}</span>{level_badge(m["level"], lang)}'
            + (f'<small>{L("مقاومت (روز)", lang)}: {days(m["resistance"])}</small>' if m["resistance"] is not None else "")
            + (f'<small>{E(m["where"], lang)}</small>' if m["where"] else "")
            + (f'<small>{L("در راه", lang)} {days(m.get("in_transit"))} · {L("در گمرک", lang)} {days(m.get("in_customs"))}</small>'
               if m.get("in_transit") or m.get("in_customs") else "")
            + (f'<small>{L("منبع", lang)}: {E(m["source"], lang)}</small>' if m["source"] != "مارت" else "")
            + "</li>" for m in o["materials"])
        pi = amount(o["pi_value"], o["pi_currency"]) if o["pi_value"] is not None else '<span class="gx-na">—</span>'
        items.append(
            f'<li><details{" open" if open_first and i == 0 else ""}><summary>{I.icon("box", 15)}'
            f'<b>{L("سفارش", lang)} <span class="gx-key">{esc(o["key"])}</span></b>'
            + (f'<small class="ltr">PR {esc(o["pr"])}</small>' if o["pr"] else "")
            + f'<span>{esc(o["status"]) or "—"}</span><small>PI: {pi}</small>{level_badge(o["level"], lang)}'
            + (pill("ابطال", "neutral", lang) if o["cancelled"] else "")
            + f'<small>{len(o["materials"]):,} {L("متریال", lang)}</small>'
            # R8: بارنامه‌ها در سطح سفارش؛ منبعی نمی‌گوید کدام بارنامه کدام متریال را حمل می‌کند
            + (f'<small>{L("بارنامه‌های سفارش", lang)}: <span class="ltr">'
               f'{html.escape((", " if lang == C.EN else "، ").join(o.get("bls") or []))}</span></small>'
               if o.get("bls") else "")
            + '</summary>'
            f'<ul>{mats or "<li class=gx-mat>—</li>"}</ul></details></li>')
    return f'<ul class="gx-tree">{"".join(items)}</ul>'


def _bls_box(bls: List[Dict[str, Any]], lang: str) -> str:
    if not bls:
        return f'<div class="gx-note">{L("بارنامه‌ای به این ثبت سفارش وصل نیست", lang)}</div>'
    rows = "".join(
        f'<tr><td class="gx-key"><b>{esc(b["key"])}</b></td><td class="n">{amount(b["value"], b["currency"])}</td>'
        f'<td class="n">{pct(b["share_pct"], lang=lang)}</td><td>{(L(b["where"], lang) if X.s(b["where"]) else "—")}<br>{pill(b["clearance"], X.CLEAR_TONE.get(b["clearance"], "unknown"), lang)}</td>'
        f'<td class="n">{days(b["demurrage_days"])}</td><td>{pill(b["status"], X.LINK_TONE.get(b["status"], "unknown"), lang)}'
        + (f'<br><small>{E(b["flags"], lang)}</small>' if b["flags"] else "") + "</td></tr>" for b in bls)
    heads = ["بارنامه", "ارزش فاکتور", "سهم (٪)", "کجاست", "روزهای رسوب", "وضعیت پیوند"]
    return ("<table><thead><tr>" + "".join(f"<th>{L(h, lang)}</th>" for h in heads)
            + f"</tr></thead><tbody>{rows}</tbody></table>")


def _flow_steps(rec: Dict[str, Any], lang: str, base: Optional[float] = None) -> str:
    """گام‌های پول یک ارز؛ طول نوار نسبت به بزرگ‌ترین گام همان ارز."""
    vals = [X.n(rec.get(k)) for k, _ in X.MONEY_STEPS]
    top = base or max([abs(v) for v in vals if v is not None] or [0]) or None
    cells = []
    for (k, fa), v in zip(X.MONEY_STEPS, vals):
        unk = rec.get("N_UNKNOWN_" + k)
        note = f'<em>{int(unk):,} {L("بی‌شاهد", lang)}</em>' if unk else ""
        if v is None:
            cells.append(f'<div class="gx-fstep is-na"><span>{L(fa, lang)}</span><b>—</b>{bar(None)}{note}</div>')
        else:
            cells.append(f'<div class="gx-fstep"><span>{L(fa, lang)}</span><b class="gx-num">{v:,.2f}</b>'
                         f'{bar(abs(v) / top * 100 if top else None)}{note}</div>')
    return f'<div class="gx-flow">{"".join(cells)}</div>'


def _money_box(money: List[Dict[str, Any]], lang: str) -> str:
    if not money:
        return f'<div class="gx-note">{L("شاهد مبلغی برای این ثبت سفارش نیست", lang)}</div>'
    out = []
    for m in money:
        c = X.s(m.get("CURRENCY")) or "نامشخص"
        st = X.s(m.get("RECON_STATUS"))
        gaps = X.s(m.get("EVIDENCE_GAPS"))
        gaps_fa = "، ".join(X.MONEY_FA.get(g.strip(), g.strip()) for g in gaps.split("|") if g.strip())
        rejected = X.n(m.get("REJECTED_REQUEST_AMOUNT"))
        out.append(f'<div class="gx-ccyhead"><b class="ltr">{ccy_label(c, lang)}</b>'
                   f'{pill(X.RECON_FA.get(st, st), X.RECON_TONE.get(st, "unknown"), lang)}'
                   + (f'<small>{L("بدون شاهد", lang)}: {E(gaps_fa, lang)}</small>' if gaps_fa else "")
                   + (f'<small>{L(X.REJECTED_FA, lang)}: <span class="gx-num">{rejected:,.2f}</span> '
                      f'({L("جزو تقاضا نیست", lang)})</small>' if rejected is not None else "")
                   + f'</div>{_flow_steps(m, lang)}')
    # گام‌ها به چند ارز (مثلاً ثبت سفارش یورو، تخصیص دلار): شکاف هر ارز از همین است، نه از نبود شاهد
    cross = next((X.s(m.get("CROSS_CURRENCY_NOTE")) for m in money if X.s(m.get("CROSS_CURRENCY_NOTE"))), "")
    head = f'<div class="gx-note"><b>{L("گام‌ها در چند ارز", lang)}</b>: {E(cross, lang)}</div>' if cross else ""
    return head + "".join(out)


def _decisions_box(decs: List[Dict[str, Any]], lang: str) -> str:
    if not decs:
        return ""
    cards = "".join(
        f'<article><b>{amount(d.get("OBSERVED_GAP_AMOUNT"), X.s(d.get("CURRENCY")))}</b>'
        f'<small>{E(d.get("STAGE_CODE"), lang)} · {E(d.get("PROCESS_OWNER"), lang)}</small>'
        f'<p>{E(d.get("AMOUNT_MEANING"), lang)}</p><p>{E(d.get("POSSIBLE_CAUSE"), lang)}</p>'
        f'<p class="gx-act">{E(d.get("SUGGESTED_ACTION"), lang)}</p></article>' for d in decs)
    return f'<div class="gx-dec">{cards}</div>'


@_css_icons
def reg_details(node: Dict[str, Any], lang: str = C.FA, excel: str = "", open_: bool = False) -> str:
    """یک ثبت سفارش به‌صورت ``<details>``: خلاصه در سطر اول، سلسله‌مراتب در بدنه."""
    lvl = X.s(node.get("CRITICAL_LEVEL"))
    crit = lvl in CB.DEFAULT_LEVELS
    status = X.s(node.get("STAGE_STATUS"))
    lower = f' ({L("حداقل", lang)})' if node.get("SHIPPED_IS_LOWER_BOUND") else ""
    counts = (f'{int(node.get("ORDER_COUNT") or 0):,} {L("سفارش", lang)} · {int(node.get("MATERIAL_COUNT") or 0):,} '
              f'{L("متریال", lang)} · {int(node.get("BL_COUNT") or 0):,} {L("بارنامه", lang)}')
    summary = (
        f'<summary><span class="gx-id"><b>{L("ثبت سفارش", lang)} <span class="gx-key">{esc(node.get("KEY_REG"))}</span></b>'
        f'<small>{L("پرونده", lang)} <span class="gx-key">{esc(node.get("REG_FILE_NO")) or "—"}</span> · {esc(node.get("EXPERT")) or "—"}</small></span>'
        f'<span>{pill(status, X.STATUS_TONE.get(status, "unknown"), lang)}</span>'
        f'<span class="gx-m"><b>{days(node.get("STAGE_DAYS"))}</b><small>{L("روز در مرحله", lang)}</small></span>'
        f'<span class="gx-m"><b>{amount(node.get("REG_VALUE"), X.s(node.get("REG_CURRENCY")))}</b>'
        f'<small>{L("ارزش ثبت سفارش", lang)}</small></span>'
        f'<span class="gx-m">{bar(node.get("SHIPPED_PCT"))} <b style="display:inline">{pct(node.get("SHIPPED_PCT"), lang=lang)}</b>'
        f'<small>{L("حمل‌شده", lang)}{lower} · {E(node.get("LINK_STATUS"), lang)}</small></span>'
        f'<span>{level_badge(lvl, lang)}</span><span class="gx-cnt">{counts}</span></summary>')
    foot = []
    if X.s(node.get("GAP_STAGES")):
        foot.append(f'{L("گام‌های بدون شاهد", lang)}: {E(node.get("GAP_STAGES"), lang)}')
    if X.s(node.get("DEADLINE_DATE")) or X.n(node.get("DAYS_REMAINING")) is not None:
        dr = X.n(node.get("DAYS_REMAINING"))
        foot.append(f'{L("مهلت رفع تعهد", lang)}: <span class="ltr">{esc(node.get("DEADLINE_DATE")) or "—"}</span>'
                    + (f' ({abs(dr):,.0f} {L("روز گذشته", lang)})' if dr is not None and dr < 0
                       else (f' ({dr:,.0f} {L("روز", lang)})' if dr is not None else "")))
    if X.s(node.get("COMMITMENT_BALANCE_TEXT")):
        foot.append(f'{L("مانده تعهد", lang)}: <span class="ltr">{esc(node.get("COMMITMENT_BALANCE_TEXT"))}</span>')
    if X.s(node.get("QUEUE_STATE_FA")):
        foot.append(f'{L("وضعیت صف", lang)}: {E(node.get("QUEUE_STATE_FA"), lang)}')
    if X.s(node.get("CURRENCY_CHECK")):
        # ارز تخصیص، خرید یا تعهد با ارز ثبت سفارش فرق دارد: گزارش می‌شود، ادغام نمی‌شود
        foot.append(f'<b>{L("مغایرت ارز گام‌ها", lang)}</b>: {E(node.get("CURRENCY_CHECK"), lang)}')
    if X.s(node.get("REJECTED_REQUEST_CURRENCIES")):
        foot.append(f'{L("ارز درخواست‌های ردشده", lang)}: '
                    f'<span class="ltr">{esc(_codes(node.get("REJECTED_REQUEST_CURRENCIES"), lang))}</span>')
    decs = _decisions_box(node.get("decisions") or [], lang)
    body = (
        f'<div class="gx-body">{_mini_path(node.get("path") or [], lang)}<div class="gx-grid">'
        f'<section class="gx-box"><h5>{I.icon("layers", 16)}{L("سفارش‌ها و متریال‌ها", lang)}</h5>{_tree(node.get("orders") or [], lang)}</section>'
        f'<section class="gx-box is-bls"><h5>{I.icon("ship", 16)}{L("بارنامه‌ها", lang)}</h5>{_bls_box(node.get("bls") or [], lang)}</section>'
        f'<section class="gx-box is-wide"><h5>{I.icon("coins", 16)}{L("جریان پول", lang)}</h5>{_money_box(node.get("money") or [], lang)}</section>'
        + (f'<section class="gx-box is-wide"><h5>{I.icon("flag", 16)}{L("تصمیم‌های مالی", lang)}</h5>{decs}</section>' if decs else "")
        + f'</div><div class="gx-foot">{"".join(f"<span>{x}</span>" for x in foot)}{excel}</div></div>')
    return (f'<details class="gx-reg{" is-crit" if crit else ""}"{" open" if open_ else ""}>'
            f'{summary}{body}</details>')


@_css_icons
def stage_explorer(model: List[Dict[str, Any]], key: str = "x", lang: str = C.FA, selected: str = "",
                   stage_excel: Optional[Dict[str, str]] = None, reg_excel: Optional[Dict[str, str]] = None,
                   critical_filter: bool = True, more_note: str = "") -> str:
    """مسیر مراحل کلیک‌پذیر؛ کلیک روی هر مرحله، ثبت سفارش‌های همان مرحله را باز می‌کند.

    ``stage_excel`` و ``reg_excel`` پیوندهای دانلود آماده (فقط در HTML مستقل)."""
    if not model:
        return f'<div class="gx-empty">{L("داده چرخه ارز در Snapshot نیست", lang)}</div>'
    gid = uid("explorer", key)
    total = sum(s["count"] for s in model) or 1
    sel = selected or next((s["code"] for s in model if s["count"]), model[0]["code"])
    radios, labels, panels = [], [], []
    for i, s in enumerate(model):
        rid = f"{gid}-{i}"
        radios.append(f'<input type="radio" class="gx-r gx-r{i}" name="{gid}" id="{rid}"'
                      f'{" checked" if s["code"] == sel else ""}>')
        alert = f'<span class="gx-st-alert" title="{L("سررسید گذشته یا بحرانی", lang)}"></span>' if (s["overdue"] or s["critical_regs"]) else ""
        labels.append(
            f'<label for="{rid}" class="gx-st gx-st{i}{" is-empty" if not s["count"] else ""}" title="{E(s["label"], lang)}">'
            f'{alert}<span class="gx-st-ic">{I.icon(I.STAGE_ICON.get(s["code"], "dot"), 17)}</span>'
            f'<span class="gx-st-n">{s["count"]:,}</span><span class="gx-st-lab">{L(s["label"], lang)}</span>'
            f'<span class="gx-st-share"><i style="width:{s["count"] / total * 100:.1f}%"></i></span></label>')
        chips = [f'<span class="gx-chip"><b>{s["count"]:,}</b>{L("ثبت سفارش", lang)}</span>']
        if s["days_median"] is not None:
            chips.append(f'<span class="gx-chip">{L("میانه روز در مرحله", lang)} <b>{days(s["days_median"])}</b></span>')
        if s["days_max"] is not None:
            chips.append(f'<span class="gx-chip">{L("بیشترین", lang)} <b>{days(s["days_max"])}</b></span>')
        if s["overdue"]:
            chips.append(f'<span class="gx-chip is-alert"><b>{s["overdue"]:,}</b>{L("سررسید گذشته", lang)}</span>')
        if s["critical_regs"]:
            chips.append(f'<span class="gx-chip is-alert"><b>{s["critical_regs"]:,}</b>{L("با متریال بحرانی", lang)}</span>')
        if s["with_gaps"]:
            chips.append(f'<span class="gx-chip"><b>{s["with_gaps"]:,}</b>{L("با گام بدون شاهد", lang)}</span>')
        regs_html = "".join(reg_details(r, lang, excel=(reg_excel or {}).get(X.s(r.get("KEY_REG")), ""))
                            for r in s["regs"])
        if not s["count"]:
            regs_html = f'<div class="gx-empty">{L("در این مرحله ثبت سفارشی نیست", lang)}</div>'
        hidden = (f'<div class="gx-note">{s["hidden"]:,} {L("ثبت سفارش دیگر", lang)} {more_note}</div>'
                  if s.get("hidden") else "")
        panels.append(
            f'<section class="gx-panel gx-p{i}"><div class="gx-phead">{I.icon_tile(I.STAGE_ICON.get(s["code"], "dot"), size=18)}'
            f'<h4>{L(s["label"], lang)}</h4><div class="gx-chips">{"".join(chips)}</div>'
            f'{(stage_excel or {}).get(s["code"], "")}</div>{_values_html(s["values"], lang)}'
            f'<div class="gx-regs">{regs_html}</div>{hidden}</section>')
    flt = ""
    if critical_filter:
        fid = f"{gid}-crit"
        flt = (f'<input type="checkbox" class="gx-f" id="{fid}">'
               f'<label class="gx-fl" for="{fid}"><i></i>{L("فقط ثبت سفارش‌های دارای متریال بحرانی", lang)}</label>')
    return (f'<div class="gx gx-x">{"".join(radios)}{flt}<div class="gx-rail">{"".join(labels)}</div>'
            f'<div class="gx-hint">{I.icon("eye", 14)}{L("روی هر مرحله کلیک کنید تا ثبت سفارش‌های آن، سفارش‌ها، متریال‌ها، بارنامه‌ها و جریان پولشان را ببینید.", lang)}</div>'
            f'<div class="gx-panels">{"".join(panels)}</div></div>')


# ═══════════════════════ جریان پول (گزارش مالی) ═══════════════════════
@_css_icons
def money_section(fx: X.FxData, lang: str = C.FA) -> str:
    """گزارش مالی: جریان پول هر ارز، جدول هر ثبت سفارش و تصمیم‌های مالی."""
    m = X.money(fx)
    if m.empty:
        return f'<div class="gx-empty">{L("تطبیق صفر تا صد مبالغ در Snapshot نیست", lang)}</div>'
    totals = X.money_totals(m)
    parts = [f'<div class="gx-note">{L("پول در هر گام به ارز خودش است و جمع فقط داخل یک ارز انجام می‌شود. «—» یعنی شاهد نیست، نه صفر؛ عدد «بی‌شاهد» تعداد ثبت سفارش‌هایی است که آن گام را ندارند.", lang)}</div>']
    for _, t in totals.iterrows():
        c = X.s(t["CURRENCY"])
        unsummed = ("" if bool(t.get("SUMMED", True)) else
                    f'<div class="gx-note">{L("ارز نامعلوم؛ مبلغ‌ها جمع زده نمی‌شوند و ریز هر ثبت سفارش در جدول پایین است.", lang)}</div>')
        parts.append(f'<div class="gx-card" style="margin-bottom:12px"><div class="gx-ccyhead"><b class="ltr">{ccy_label(c, lang)}</b>'
                     f'<span class="gx-chip"><b>{int(t["REGISTRATIONS"]):,}</b>{L("ثبت سفارش", lang)}</span></div>'
                     f'{unsummed}{_flow_steps(t.to_dict(), lang)}</div>')
    heads = X.money_display(fx)
    numeric = [fa for _, fa in X.MONEY_STEPS] + [X.REJECTED_FA]
    tone = {X.RECON_FA[k]: t for k, t in X.RECON_TONE.items() if k in X.RECON_FA}
    parts.append(f'<div class="gx-sec">{I.icon_tile("bars", size=16)}<h3>{L("ریز جریان پول هر ثبت سفارش", lang)}</h3></div>')
    parts.append(table(heads, lang, numeric=numeric, cells={
        "ثبت سفارش": lambda v, r: f'<b class="gx-key">{esc(v)}</b>',
        "ارز": lambda v, r: f'<b class="ltr">{esc(v)}</b>',
        "وضعیت تطبیق": lambda v, r: pill(X.s(v), tone.get(X.s(v), "unknown"), lang)}))
    decs = X.decisions(fx).to_dict("records")
    if decs:
        parts.append(f'<div class="gx-sec">{I.icon_tile("flag", size=16)}<h3>{L("تصمیم‌های مالی", lang)}</h3>'
                     f'<small>{L("مبلغ‌ها جمع‌پذیر نیستند", lang)}</small></div>')
        for d in decs:
            d["STAGE_CODE"] = f'{X.s(d.get("KEY_REG"))} · {X.s(d.get("STAGE_CODE"))}'
        parts.append(_decisions_box(decs, lang))
    return "".join(parts)


# ═══════════════════════ بارنامه ↔ ثبت سفارش ═══════════════════════
@_css_icons
def bl_link_section(fx: X.FxData, lang: str = C.FA, limit: int = 60) -> str:
    rec = fx.recon
    if rec.empty:
        return f'<div class="gx-empty">{L("پیوند بارنامه/ثبت سفارش در Snapshot نیست", lang)}</div>'
    rec = rec.copy()
    rec["_sev"] = pd.to_numeric(rec.get("SEVERITY"), errors="coerce").fillna(0)
    rec = rec.sort_values(["_sev", "KEY_REG"], ascending=[False, True])
    cards = []
    for _, r in rec.head(limit).iterrows():
        reg = X.s(r["KEY_REG"])
        tone = X.LINK_TONE.get(X.s(r["STATUS"]), "unknown")
        ring_tone = {"warning": "serious"}.get(tone, tone) if tone in ("critical", "warning") else "brand"
        sp = X.n(r.get("SHIPPED_PCT"))
        gauge = I.ring(sp, 84, label=X.tr("حمل‌شده", lang), tone=ring_tone, uid=uid("bl", reg),
                       text=pct(sp, 0, lang) if lang == C.EN and sp is not None else "")
        lower = f' ({L("حداقل", lang)})' if X.truthy(r.get("SHIPPED_IS_LOWER_BOUND")) else ""
        upper = (f' ({L("حداکثر", lang)})' if lower and (X.n(r.get("UNSHIPPED_VALUE")) or 0) > 0 else "")
        ccy = X.s(r.get("REG_CURRENCY"))
        cards.append(
            f'<div class="gx-card" style="display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:center;margin-bottom:10px">'
            f'<div>{gauge}</div><div><div class="gx-chips" style="margin-bottom:8px"><b style="font-size:14px">'
            f'{L("ثبت سفارش", lang)} <span class="gx-key">{html.escape(reg)}</span></b>{pill(X.s(r["STATUS"]), tone, lang)}</div>'
            f'<div class="gx-vals"><div class="gx-val"><b>{amount(r.get("REG_VALUE"), ccy)}</b><span>{L("ارزش ثبت سفارش", lang)}</span></div>'
            f'<div class="gx-val"><b>{amount(r.get("SHIPPED_VALUE"), ccy)}</b><span>{L("حمل‌شده", lang)}{lower}</span></div>'
            f'<div class="gx-val"><b>{amount(r.get("UNSHIPPED_VALUE"), ccy)}</b><span>{L("مانده حمل‌نشده", lang)}{upper}</span></div>'
            f'<div class="gx-val"><b style="font-size:12px">{E(r.get("REG_VALUE_BASIS"), lang) or "—"}</b><span>{L("مبنای ارزش", lang)}</span></div></div>'
            + (f'<div class="gx-note">{E(r.get("FLAGS"), lang)}</div>' if X.s(r.get("FLAGS")) else "")
            + _currency_check_note(fx, reg, lang)
            + f'<div class="gx-box">{_bls_box(X.bls(fx, reg), lang)}</div></div></div>')
    more = (f'<div class="gx-note">{len(rec) - limit:,} {L("ثبت سفارش دیگر در فایل Excel", lang)}</div>'
            if len(rec) > limit else "")
    note = L("هر بارنامه با ارزش فاکتور و ارز خودش به ثبت سفارشش وصل است. حمل‌شده فقط از بارنامه‌های هم‌ارز جمع می‌شود و هیچ نرخ تبدیلی اعمال نمی‌شود.", lang)
    return f'<div class="gx-note">{note}</div>{"".join(cards)}{more}'


def _currency_check_note(fx: X.FxData, reg: str, lang: str) -> str:
    """ارز تخصیص، خرید و تعهد کنار ارز ثبت سفارش؛ فقط وقتی با هم فرق دارند."""
    lc = fx.lc_by_reg.get(reg)
    check = X.s(lc.get("CURRENCY_CHECK")) if lc is not None else ""
    if not check:
        return ""
    return f'<div class="gx-note"><b>{L("مغایرت ارز گام‌ها", lang)}</b>: {E(check, lang)}</div>'


# ═══════════════════════════ صف تخصیص ═══════════════════════════
QUEUE_HEADS = {"QUEUE_RANK": "رتبه صف", "KEY_REG": "ثبت سفارش", "QUEUE_STATE": "وضعیت صف", "QUEUE_ENTER_DATE": "ورود به صف",
               "WAIT_DAYS": "روز انتظار", "OPEN_AMOUNT": "مبلغ باز", "CURRENCY": "ارز", "REQUESTS_OPEN": "درخواست باز",
               "CRITICAL_LEVEL": "بحرانی بودن سفارش", "CRITICAL_MATERIALS": "متریال بحرانی", "ORDERS": "سفارش‌ها",
               "EXPERT": "کارشناس", "WAIT_NOTE": "توضیح تاریخ"}


@_css_icons
def queue_section(fx: X.FxData, lang: str = C.FA) -> str:
    q = fx.queue
    if q.empty:
        return f'<div class="gx-empty">{L("درخواست تخصیص بازی در NTSW دیده نشد", lang)}</div>'
    q = q.copy()
    # جمع هر ارز فقط با کد شناخته‌شده؛ مبلغ‌های بی‌ارز یا با متن ناشناخته («نامشخص»، «حواله»)
    # با هم جمع نمی‌شوند و فقط شمار پرونده‌هایشان در کاشی جدا می‌آید.
    from ..finance.registration import currency_coder
    code_of = currency_coder()
    codes = q["CURRENCY"].map(lambda c: code_of(X.s(c)) if X.s(c) else "")
    known = codes.ne("")
    by = q.loc[known].groupby(codes[known])["OPEN_AMOUNT"].apply(
        lambda s: sum(x for x in (X.n(v) for v in s) if x is not None) if any(X.n(v) is not None for v in s) else None)
    tiles = [I.kpi_tile("coins", f'{C.label("مبلغ باز صف", lang) if lang == C.EN else "مبلغ باز صف"} ({X.tr(c, lang)})',
                        "—" if v is None else f"{v:,.2f}") for c, v in by.items()]
    unknown = int((~known & q["OPEN_AMOUNT"].map(lambda v: X.n(v) is not None)).sum())
    if unknown:
        tiles.append(I.kpi_tile("coins", C.label("پرونده صف با ارز نامعلوم", lang) if lang == C.EN
                                else "پرونده صف با ارز نامعلوم", f"{unknown:,}"))
    tiles.append(I.kpi_tile("queue", C.label("پرونده در صف", lang) if lang == C.EN else "پرونده در صف", f"{len(q):,}"))
    wait = pd.to_numeric(q.get("WAIT_DAYS"), errors="coerce")
    tiles.append(I.kpi_tile("clock", C.label("بیشترین انتظار (روز)", lang) if lang == C.EN else "بیشترین انتظار (روز)",
                            days(wait.max() if wait.notna().any() else None)))
    q["QUEUE_STATE"] = q["QUEUE_STATE"].map(lambda v: X.QUEUE_FA.get(X.s(v), X.s(v)))
    q = q.sort_values(["QUEUE_RANK"], na_position="last")
    if "WAIT_NOTE" in q.columns and not q["WAIT_NOTE"].map(X.s).any():
        q = q.drop(columns="WAIT_NOTE")
    view = q[[c for c in QUEUE_HEADS if c in q.columns]].rename(columns=QUEUE_HEADS)
    return (f'<div class="gx-note">{L("مرتب‌سازی: اول بحرانی‌ترین متریال سفارش، سپس طولانی‌ترین انتظار. مبلغ باز به ارز درخواست است و جمع بین‌ارزی نمی‌شود.", lang)}</div>'
            f'<div class="mi-kpis">{"".join(tiles)}</div>'
            + table(view, lang, numeric=["مبلغ باز"], cells={
                "بحرانی بودن سفارش": lambda v, r: level_badge(X.s(v), lang) or "—",
                "ثبت سفارش": lambda v, r: f'<b class="gx-key">{esc(v)}</b>'}))


# ═══════════════════════════════ ترخیص ═══════════════════════════════
def clearance_frame(fx: X.FxData) -> pd.DataFrame:
    rows = []
    for bl, g in fx.mart_by_bl.items():
        full = any(X.truthy(v) for v in X._col(g, "IS_FULL_CLEARED"))
        part = any(X.truthy(v) for v in X._col(g, "IS_PARTIAL_CLEARED"))
        dem = [x for x in (X.n(v) for v in X._col(g, "روزهای رسوب")) if x is not None]
        lvl = X.worst_level(X._col(g, "BL_CRITICAL_LEVEL"))
        rows.append({"بارنامه": bl, "ثبت سفارش": "، ".join(X._uniq(X._col(g, "KEY_REG"))),
                     "کجاست": " · ".join(X._uniq(X._col(g, "STATUS_WHERE"))),
                     "وضعیت ترخیص": "ترخیص کامل" if full else ("ترخیص جزئی" if part else "ترخیص نشده"),
                     "کوتاژ": X._first(X._col(g, "COTAGE_NO")),
                     "تاریخ تخلیه": X._first(X._col(g, "BL_DISCHARGE_DATE", "DISCHARGE_DATE")),
                     "تاریخ ترخیص کامل": X._first(X._col(g, "FULL_CLEAR_DATE")),
                     "روزهای رسوب": max(dem) if dem else None, "گمرک مقصد": X._first(X._col(g, "DEST_CUSTOMS")),
                     "کارشناس": X._first(X._col(g, "CANONICAL_EXPERT")), "سطح بحرانی": lvl})
    out = pd.DataFrame(rows, columns=["بارنامه", "ثبت سفارش", "کجاست", "وضعیت ترخیص", "کوتاژ", "تاریخ تخلیه",
                                      "تاریخ ترخیص کامل", "روزهای رسوب", "گمرک مقصد", "کارشناس", "سطح بحرانی"])
    return out.sort_values("روزهای رسوب", ascending=False, na_position="last").reset_index(drop=True)


@_css_icons
def clearance_section(fx: X.FxData, lang: str = C.FA) -> str:
    t = clearance_frame(fx)
    if t.empty:
        return f'<div class="gx-empty">{L("داده‌ای برای ترخیص نیست", lang)}</div>'
    dem = pd.to_numeric(t["روزهای رسوب"], errors="coerce")
    tiles = [("box", "بارنامه ترخیص‌نشده", int(t["وضعیت ترخیص"].eq("ترخیص نشده").sum()), True),
             ("customs", "ترخیص جزئی", int(t["وضعیت ترخیص"].eq("ترخیص جزئی").sum()), False),
             ("check", "ترخیص کامل", int(t["وضعیت ترخیص"].eq("ترخیص کامل").sum()), False)]
    k = "".join(I.kpi_tile(ic, C.label(lab, lang) if lang == C.EN else lab, f"{v:,}",
                           tone="critical" if alert and v else "brand") for ic, lab, v, alert in tiles)
    k += I.kpi_tile("clock", C.label("بیشترین رسوب (روز)", lang) if lang == C.EN else "بیشترین رسوب (روز)",
                    days(dem.max() if dem.notna().any() else None))
    return f'<div class="mi-kpis">{k}</div>' + table(t, lang, cells={
        "بارنامه": lambda v, r: f'<b class="gx-key">{esc(v)}</b>',
        "وضعیت ترخیص": lambda v, r: pill(X.s(v), X.CLEAR_TONE.get(X.s(v), "unknown"), lang),
        "روزهای رسوب": lambda v, r: days(v),
        "سطح بحرانی": lambda v, r: level_badge(X.s(v), lang) or "—"})


# ═══════════════════════════════ بحرانی ═══════════════════════════════
@_css_icons
def critical_section(fx: X.FxData, df: pd.DataFrame, lang: str = C.FA, levels: Sequence[str] = CB.DEFAULT_LEVELS,
                     key: str = "crit", stage_excel: Optional[Dict[str, str]] = None, max_regs: Optional[int] = 40) -> str:
    """اقلام بحرانی به تفکیک مرحله چرخه، با همان مسیر کلیک‌پذیر و همان کارت‌های تابلوی بحرانی."""
    model = X.explorer(fx, critical_only=True, levels=levels, max_regs=max_regs)
    sel = X.busiest_stage(pd.DataFrame([{"STAGE_CODE": s["code"], "REGISTRATIONS": s["count"]} for s in model]))
    explorer = stage_explorer(model, key=key, lang=lang, selected=sel, stage_excel=stage_excel, critical_filter=False,
                              more_note=L("در فایل Excel اقلام بحرانی", lang))
    names = ("، " if lang != C.EN else ", ").join(C.label(CB.level_label(c), lang) if lang == C.EN else CB.level_label(c)
                                                  for c in levels)
    return (f'<div class="gx-note">{L("سطوح بحرانی", lang)}: {html.escape(names)}. '
            f'{L("هر مرحله فقط ثبت سفارش‌هایی را نشان می‌دهد که دست‌کم یک متریال بحرانی دارند و درخت هر سفارش فقط متریال‌های بحرانی را دارد.", lang)}</div>'
            f'{explorer}<div class="gx-sec">{I.icon_tile("alert", "critical", 16)}<h3>{L("تابلوی متریال‌ها و بارنامه‌های بحرانی", lang)}</h3></div>'
            f'{CB.critical_fragment(df, levels=levels, lang=lang)}')


# ═══════════════════════ Excelهای کل گزارش ═══════════════════════
def report_workbooks(fx: X.FxData, df: pd.DataFrame, ref_date: str = "", lang: str = C.FA,
                     levels: Sequence[str] = CB.DEFAULT_LEVELS) -> List[tuple]:
    """سه Excel کل گزارش: (داده، نام فایل، عنوان، آیکن، شرح). گزارش مستقل و Block
    «دانلود Excel» گزارش‌ساز هر دو از همین فهرست می‌سازند."""
    from . import fx_excel as XL
    return [
        (XL.stage_workbook(fx, lang=lang), f"GSI_FX_STAGES_{ref_date}.xlsx", "پرونده‌ها به تفکیک مرحله", "layers",
         "خلاصه هر مرحله، ارزش به تفکیک ارز، ثبت سفارش‌ها و سلسله‌مراتب مرحله ← ثبت سفارش ← سفارش ← متریال"),
        (XL.registration_workbook(fx, None, lang=lang), f"GSI_FX_FINANCE_ALL_{ref_date}.xlsx",
         "ریز مالی همه ثبت سفارش‌ها", "coins",
         "جریان پول هر ارز، رویدادهای مبلغی، بارنامه‌ها، سفارش‌ها، متریال‌ها، مراحل و تصمیم‌های مالی"),
        (XL.critical_workbook(fx, df, levels=levels, lang=lang), f"GSI_CRITICAL_BY_STAGE_{ref_date}.xlsx",
         "اقلام بحرانی به تفکیک مرحله", "alert",
         "متریال‌ها و بارنامه‌های بحرانی، ماتریس مرحله × سطح و سلسله‌مراتب بحرانی"),
    ]


@_css_icons
def download_cards(downloads: Sequence[tuple], lang: str = C.FA) -> str:
    return "".join(
        f'<div class="gx-card" style="display:flex;gap:14px;align-items:center;margin-bottom:10px">{I.icon_tile(ic, size=20)}'
        f'<div style="flex:1"><b>{L(lab, lang)}</b><div class="gx-note" style="margin:0">{L(desc, lang)}</div></div>'
        f'{data_link(data, name, "دریافت فایل Excel", "file", lang=lang).replace("gx-dl", "gx-dl is-primary", 1)}</div>'
        for data, name, lab, ic, desc in downloads)


# ═══════════════════════════ گزارش مستقل ═══════════════════════════
TABS = [("gauge", "نمای کلی چرخه"), ("coins", "جریان پول (گزارش مالی)"), ("link", "بارنامه ↔ ثبت سفارش"),
        ("queue", "صف تخصیص ارز"), ("customs", "ترخیص"), ("alert", "اقلام بحرانی"), ("file", "دانلود Excel")]


@_css_icons
def tabs_html(panes: List[str], lang: str = C.FA, key: str = "rep", names: Sequence = TABS) -> str:
    gid = uid("tabs", key)
    radios = "".join(f'<input type="radio" class="gx-t gx-t{i}" name="{gid}" id="{gid}-{i}"{" checked" if i == 0 else ""}>'
                     for i in range(len(panes)))
    labels = "".join(f'<label class="gx-tb gx-tb{i}" for="{gid}-{i}">{I.icon(ic, 16)}{L(t, lang)}</label>'
                     for i, (ic, t) in enumerate(names[:len(panes)]))
    body = "".join(f'<section class="gx-tpane gx-tp{i}">{p}</section>' for i, p in enumerate(panes))
    return f'{radios}<nav class="gx-tabs">{labels}</nav><div class="gx-tpanes">{body}</div>'


@_css_icons
def build_report(df: pd.DataFrame, extras: Any, ref_date: str = "", lang: str = C.FA, title: str = "",
                 levels: Sequence[str] = CB.DEFAULT_LEVELS, embed_excel: bool = True, max_reg_workbooks: int = 80,
                 max_regs_per_stage: Optional[int] = 60, embed_fonts: Optional[bool] = None,
                 subtitle: str = "", fx: Optional[X.FxData] = None) -> str:
    """گزارش HTML مستقل «چرخه ارز و گزارش مالی» — همان اجزای Studio، بدون هیچ منبع بیرونی.

    Excelها داخل خود فایل جاسازی می‌شوند: پرونده‌ها به تفکیک مرحله، ریز مالی همه
    ثبت سفارش‌ها، اقلام بحرانی و ریز مالی هر ثبت سفارش (تا ``max_reg_workbooks``)."""
    from ..design import fonts as F
    from ..design.css import stylesheet
    from . import fx_excel as XL

    fx = fx or X.load(df, extras, ref_date)
    title = title or X.tr("گزارش مالی و چرخه ارز و رفع تعهد", lang)
    stage_x, reg_x, crit_x, downloads = {}, {}, {}, []
    if embed_excel and fx.available:
        stage_x = {code: data_link(XL.stage_workbook(fx, stages=[code], lang=lang),
                                   f"GSI_FX_STAGE_{code}_{ref_date}.xlsx", "Excel پرونده‌های این مرحله", lang=lang)
                   for code, _ in X.STAGES if (fx.reg_table["STAGE_CODE"] == code).any()}
        order = fx.reg_table.sort_values(["STAGE_DAYS"], ascending=False, na_position="last")["KEY_REG"].tolist()
        for reg in order[:max_reg_workbooks]:
            reg_x[reg] = data_link(XL.registration_workbook(fx, [reg], lang=lang),
                                   f"GSI_FX_REG_{reg}_{ref_date}.xlsx", "Excel ریز مالی این ثبت سفارش", lang=lang)
        crit_x = {code: data_link(XL.critical_workbook(fx, df, levels=levels, stages=[code], lang=lang),
                                  f"GSI_CRITICAL_STAGE_{code}_{ref_date}.xlsx", "Excel اقلام بحرانی این مرحله", lang=lang)
                  for code, _ in X.STAGES
                  if ((fx.reg_table["STAGE_CODE"] == code) & fx.reg_table["CRITICAL_LEVEL"].isin(levels)).any()}
        downloads = report_workbooks(fx, df, ref_date, lang, levels)
    more = L("در فایل Excel «پرونده‌ها به تفکیک مرحله»", lang)
    model = X.explorer(fx, max_regs=max_regs_per_stage) if fx.available else []
    sel = X.busiest_stage(X.stage_summary(fx)) if fx.available else ""
    overview = (kpis(fx, lang) + f'<div class="gx-sec">{I.icon_tile("flow", size=16)}<h3>{L("تعداد ثبت سفارش در هر مرحله", lang)}</h3>'
                f'<small>{L("مرحله جاری: گام بعد از پیشرفته‌ترین گام انجام‌شده", lang)}</small></div>'
                + stage_explorer(model, key="overview", lang=lang, selected=sel, stage_excel=stage_x, reg_excel=reg_x,
                                 more_note=more)) if fx.available else f'<div class="gx-empty">{L("جدول چرخه ارز در Snapshot نیست", lang)}</div>'
    dl_html = download_cards(downloads, lang)
    dl_note = (f'<div class="gx-note">{L("ریز مالی هر ثبت سفارش جداگانه، داخل همان ثبت سفارش در «نمای کلی چرخه» است", lang)}'
               + (f' ({L("برای", lang)} {len(reg_x):,} {L("ثبت سفارش با بیشترین روز در مرحله", lang)})' if reg_x else "")
               + '.</div>') if downloads else f'<div class="gx-empty">{L("جاسازی Excel خاموش است", lang)}</div>'
    panes = [overview, money_section(fx, lang), bl_link_section(fx, lang), queue_section(fx, lang),
             clearance_section(fx, lang),
             critical_section(fx, df, lang, levels, stage_excel=crit_x), dl_html + dl_note]
    regs = fx.reg_table
    # R8: بارنامه/سفارش یکتا روی اجتماع ثبت سفارش‌ها؛ بارنامه دو ثبت‌سفارشی دو بار شمرده نمی‌شود
    uc = X.unique_counts(fx) if not regs.empty else {"bls": 0, "orders": 0}
    chips = (f'<div class="gx-chips"><span class="gx-chip"><b>{len(regs):,}</b>{L("ثبت سفارش", lang)}</span>'
             f'<span class="gx-chip"><b>{uc["bls"]:,}</b>{L("بارنامه", lang)}</span>'
             f'<span class="gx-chip"><b>{uc["orders"]:,}</b>{L("سفارش", lang)}</span></div>')
    font_css = F.html_font_css() if (embed_fonts is None or embed_fonts) else ""
    sub = subtitle or (f'{L("تاریخ مرجع", lang)} <span class="ltr">{html.escape(ref_date)}</span>' if ref_date else "")
    # انگلیسی چپ‌به‌راست: در صفحه راست‌چین، «برچسب: مقدار» انگلیسی وارونه خوانده می‌شود
    page_dir = 'lang="en" dir="ltr"' if lang == C.EN else 'lang="fa" dir="rtl"'
    return (f'<!DOCTYPE html><html {page_dir}><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f'<style>{font_css}{stylesheet()}{css()}</style></head><body class="gx gx-page"><main class="gx-wrap">'
            f'{_BRAND.band_raw(L(title, lang), sub_html=sub, eyebrow_html=L("خرید ارز · رفع تعهد · گزارش مالی", lang), side_html=chips, tag=L(_BRAND.TAGLINE_FA, lang))}'
            f'{tabs_html(panes, lang)}'
            f'<p class="gx-legal">{L("این گزارش از همان Snapshot و همان اجزای Studio ساخته شده و به هیچ منبع بیرونی وصل نمی‌شود. قواعد: نامعلوم هرگز صفر نیست؛ جمع فقط داخل یک ارز است؛ ارزش بارنامه یک بار شمرده می‌شود و روی ردیف متریال تکرار نمی‌شود.", lang)}</p>'
            '</main></body></html>')


# ═══════════════════ بلوک گزارش‌ساز HTML و بخش ایمیل ═══════════════════
@_css_icons
def composer_block(df: pd.DataFrame, extras: Any, ref_date: str = "", key: str = "blk", lang: str = C.FA,
                   embed_excel: bool = True, max_regs_per_stage: Optional[int] = 40, max_embedded_regs: int = 400,
                   levels: Sequence[str] = CB.DEFAULT_LEVELS) -> str:
    """بلوک «چرخه ارز و گزارش مالی» گزارش‌ساز HTML: همان KPI، مراحل کلیک‌پذیر با
    سلسله‌مراتب و جریان پول Studio. ``css()`` یک بار در ``<style>`` صفحه می‌آید؛
    ``extras`` باید پیش‌تر به دامنه همان گزارش محدود شده باشد."""
    from . import fx_excel as XL

    fx = X.load(df, extras, ref_date)
    if not fx.available:
        return f'<div class="gx"><div class="gx-empty">{L("جدول چرخه ارز در Snapshot نیست", lang)}</div></div>'
    model = X.explorer(fx, max_regs=max_regs_per_stage)
    sel = X.busiest_stage(X.stage_summary(fx))
    dls = ""
    if embed_excel and len(fx.reg_table) <= max_embedded_regs:
        items = [(XL.stage_workbook(fx, lang=lang), f"GSI_FX_STAGES_{ref_date}.xlsx", "پرونده‌ها به تفکیک مرحله", "layers"),
                 (XL.registration_workbook(fx, None, lang=lang), f"GSI_FX_FINANCE_ALL_{ref_date}.xlsx",
                  "ریز مالی همه ثبت سفارش‌ها", "coins"),
                 (XL.critical_workbook(fx, df, levels=levels, lang=lang), f"GSI_CRITICAL_BY_STAGE_{ref_date}.xlsx",
                  "اقلام بحرانی به تفکیک مرحله", "alert")]
        dls = '<div class="gx-dls">' + "".join(data_link(d, n, lab, ic, lang=lang) for d, n, lab, ic in items) + "</div>"
    return ('<div class="gx">' + kpis(fx, lang) + dls
            + f'<div class="gx-sec">{I.icon_tile("flow", size=16)}<h3>{L("تعداد ثبت سفارش در هر مرحله", lang)}</h3>'
              f'<small>{L("مرحله جاری: گام بعد از پیشرفته‌ترین گام انجام‌شده", lang)}</small></div>'
            + stage_explorer(model, key=key, lang=lang, selected=sel,
                             more_note=L("در فایل Excel «پرونده‌ها به تفکیک مرحله»", lang))
            + f'<div class="gx-sec">{I.icon_tile("coins", size=16)}<h3>{L("جریان پول (گزارش مالی)", lang)}</h3></div>'
            + money_section(fx, lang) + "</div>")


# هر بخش گزارش مستقل یک Block جدای گزارش‌ساز است (V29.20) تا هر کدام جدا اضافه، حذف،
# جابه‌جا و اندازه‌بندی شود. هر Block عنوان خودش را دارد، چون جایش دیگر ثابت نیست و
# ویرایشگر چیدمان داخل HTML هم نام Block را از همین عنوان می‌خواند.
PARTS: Dict[str, tuple] = {
    "fx_kpi": ("gauge", "شاخص‌های چرخه ارز"),
    "fx_stages": ("flow", "تعداد ثبت سفارش در هر مرحله"),
    "fx_money": ("coins", "جریان پول (گزارش مالی)"),
    "fx_bl_link": ("link", "بارنامه ↔ ثبت سفارش"),
    "fx_queue": ("queue", "صف تخصیص ارز"),
    "fx_clearance": ("customs", "ترخیص"),
    "fx_critical": ("alert", "اقلام بحرانی"),
    "fx_downloads": ("file", "دانلود Excel"),
}


@_css_icons
def composer_part(part: str, df: pd.DataFrame, extras: Any = None, ref_date: str = "", key: str = "blk",
                  lang: str = C.FA, fx: Optional[X.FxData] = None, embed_excel: bool = True,
                  max_regs_per_stage: Optional[int] = 40, max_embedded_regs: int = 400,
                  levels: Sequence[str] = CB.DEFAULT_LEVELS) -> str:
    """یک بخش چرخه ارز به‌تنهایی، با همان اجزای گزارش مستقل و Studio.

    ``fx`` اگر داده شود دوباره ساخته نمی‌شود (گزارش‌ساز آن را یک بار برای همه
    تب‌ها می‌سازد). ``key`` باید در صفحه یکتا باشد؛ مسیر مراحل با آن نام‌گذاری می‌شود."""
    if part not in PARTS:
        raise KeyError(part)
    ic, title = PARTS[part]
    fx = fx if fx is not None else X.load(df, extras, ref_date)
    small = (f'<small>{L("مرحله جاری: گام بعد از پیشرفته‌ترین گام انجام‌شده", lang)}</small>'
             if part == "fx_stages" else "")
    head = (f'<div class="gx-sec">{I.icon_tile(ic, "critical" if part == "fx_critical" else "brand", 16)}'
            f'<h3>{L(title, lang)}</h3>{small}</div>')
    if not fx.available:
        body = f'<div class="gx-empty">{L("جدول چرخه ارز در Snapshot نیست", lang)}</div>'
    elif part == "fx_kpi":
        body = kpis(fx, lang)
    elif part == "fx_stages":
        body = stage_explorer(X.explorer(fx, max_regs=max_regs_per_stage), key=key, lang=lang,
                              selected=X.busiest_stage(X.stage_summary(fx)),
                              more_note=L("در فایل Excel «پرونده‌ها به تفکیک مرحله»", lang))
    elif part == "fx_money":
        body = money_section(fx, lang)
    elif part == "fx_bl_link":
        body = bl_link_section(fx, lang)
    elif part == "fx_queue":
        body = queue_section(fx, lang)
    elif part == "fx_clearance":
        body = clearance_section(fx, lang)
    elif part == "fx_critical":
        body = critical_section(fx, df, lang, levels, key=key, max_regs=max_regs_per_stage)
    elif not embed_excel:
        body = f'<div class="gx-empty">{L("جاسازی Excel خاموش است", lang)}</div>'
    elif len(fx.reg_table) > max_embedded_regs:
        body = (f'<div class="gx-empty">{L("شمار ثبت سفارش‌های این گزارش برای جاسازی Excel زیاد است", lang)} '
                f'({len(fx.reg_table):,}). {L("فایل‌ها را از Studio، محیط کاری «چرخه ارز و رفع تعهد» بگیرید.", lang)}</div>')
    else:
        body = download_cards(report_workbooks(fx, df, ref_date, lang, levels), lang)
    return f'<div class="gx gx-part" data-fx-part="{html.escape(part, quote=True)}">{head}{body}</div>'


def email_section(fx: X.FxData, lang: str = C.FA, attachment: str = "") -> str:
    """خلاصه چرخه ارز برای بدنه ایمیل Outlook: فقط جدول با استایل درون‌خطی (Outlook
    کلاس، ``<style>`` و تعامل CSS را اجرا نمی‌کند). نسخه تعاملی همان گزارش پیوست است."""
    if not fx.available:
        return ""
    summ = X.stage_summary(fx)
    summ = summ[summ["REGISTRATIONS"] > 0]
    th = (f'style="background:{T.BRAND_TEAL};color:{T.TEXT_ON_BRAND};padding:7px 9px;font-weight:700;'
          'text-align:right;white-space:nowrap"')
    td = f'style="padding:6px 9px;border-top:1px solid {T.BORDER};text-align:right"'
    tdn = f'style="padding:6px 9px;border-top:1px solid {T.BORDER};text-align:right;white-space:nowrap"'

    def head(cols: Sequence[str]) -> str:
        return "<tr>" + "".join(f"<th {th}>{L(c, lang)}</th>" for c in cols) + "</tr>"

    stage_rows = "".join(
        f"<tr><td {td}>{E(r.STAGE, lang)}</td><td {tdn}>{int(r.REGISTRATIONS):,}</td><td {tdn}>{days(r.DAYS_MEDIAN)}</td>"
        f"<td {tdn}>{int(r.OVERDUE or 0):,}</td><td {tdn}>{int(r.CRITICAL_REGS or 0):,}</td></tr>"
        for r in summ.itertuples())
    tot = X.money_totals(X.money(fx))
    steps = [("REGISTRATION_AMOUNT", "ارزش ثبت سفارش"), ("SHIPPED_BL_VALUE", "حمل‌شده (بارنامه)"),
             ("COMMITMENT_BALANCE", "مانده تعهد")]

    def num(v: Any) -> str:
        x = X.n(v)
        return "—" if x is None else f"{x:,.2f}"

    money_rows = "".join(
        f"<tr><td {tdn}><b>{ccy_label(r['CURRENCY'], lang)}</b></td><td {tdn}>{int(r['REGISTRATIONS']):,}</td>"
        + "".join(f"<td {tdn}>{num(r.get(k))}</td>" for k, _ in steps) + "</tr>"
        for _, r in tot.iterrows()) if not tot.empty else ""
    title = (f'<div style="margin:20px 0 8px;font-size:17px;font-weight:800;color:{T.BRAND_NAVY}">'
             f'{L("چرخه ارز و رفع تعهد", lang)}</div>')
    table_open = (f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:12px;'
                  f'border:1px solid {T.BORDER};margin:0 0 12px">')
    stage_tbl = (table_open + head(["مرحله", "ثبت سفارش", "میانه روز در مرحله", "سررسید گذشته", "با متریال بحرانی"])
                 + stage_rows + "</table>") if stage_rows else ""
    money_tbl = (table_open + head(["ارز", "ثبت سفارش"] + [fa for _, fa in steps]) + money_rows + "</table>"
                 if money_rows else "")
    note = (f'<div style="background:{T.TEAL_WASH};border:1px solid {T.BORDER};border-radius:10px;padding:10px 13px;'
            f'font-size:12px;line-height:1.9">{L("پول در هر گام به ارز خودش است و جمع فقط داخل یک ارز انجام می‌شود. «—» یعنی شاهد نیست، نه صفر؛ عدد «بی‌شاهد» تعداد ثبت سفارش‌هایی است که آن گام را ندارند.", lang)}'
            + (f' {L("ارز نامعلوم ردیف جدا دارد و جمع زده نمی‌شود.", lang)}'
               if not tot.empty and "SUMMED" in tot and not tot["SUMMED"].all() else "")
            + (f'<br>{L("نسخه تعاملی (کلیک روی هر مرحله، سلسله‌مراتب ثبت سفارش ← سفارش ← متریال و فایل‌های Excel) پیوست است", lang)}: '
               f'<b dir="ltr" style="white-space:nowrap">{html.escape(attachment)}</b>' if attachment else "") + "</div>")
    return title + stage_tbl + money_tbl + note


def write_report(df: pd.DataFrame, extras: Any, ref_date: str, out_dir: Any, lang: str = C.FA, **kwargs: Any):
    """گزارش مستقل را در ``out_dir`` می‌نویسد و مسیرش را برمی‌گرداند."""
    from pathlib import Path
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"GSI_FX_LIFECYCLE_{ref_date or 'report'}{'_EN' if lang == C.EN else ''}.html"
    p.write_text(build_report(df, extras, ref_date, lang=lang, **kwargs), encoding="utf-8")
    return p
