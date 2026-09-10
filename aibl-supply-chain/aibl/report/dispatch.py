# -*- coding: utf-8 -*-
"""ارسال گزارش در لحظه — انتخاب پیوست، انتخاب گیرنده، متن ایمیل.

نسخهٔ یکسانِ ``hrperf/report/dispatch.py``، با سیاههٔ پیوست و
دفترچهٔ گیرندگانِ همین پکیج. عمداً کپی شده تا دو پکیج مستقل
بمانند — همان قاعده‌ای که برای ``aqua.py`` برقرار است.

## پرسشی که این ماژول از آن زاده شد

«اتلوک HTML دارد؛ می‌شود گزارش در متن ایمیل **داینامیک** باشد؟»

پاسخ کوتاه: **نه — و این محدودیت ما نیست، محدودیت خودِ ایمیل است.**

* **جاوااسکریپت در بدنهٔ ایمیل اجرا نمی‌شود.** هیچ کلاینت ایمیلی
  ``<script>`` را اجرا نمی‌کند؛ همه حذفش می‌کنند. این یک تصمیم امنیتی
  است، نه نقص اتلوک: ایمیل از فرستندهٔ ناشناس می‌آید و اجرای کد او روی
  دستگاه گیرنده، خودش یک آسیب‌پذیری است. پس نمودار زنده، فیلتر، و
  مرتب‌سازی **در بدنهٔ ایمیل ممکن نیست**.
* **اتلوک کلاسیک ویندوز** بدنه را با موتور **Word** رندر می‌کند: بدون
  flexbox، بدون grid، بدون ``background-image``، بدون ``max-width``، و
  ``margin``/``padding`` روی ``div`` و ``img`` نادیده گرفته می‌شود.
  پشتیبانی مایکروسافت از این نسخه **مهر ۲۰۲۶** تمام می‌شود.
* **اتلوک جدید ویندوز** (پیش‌فرض از فروردین ۲۰۲۶) موتور Chromium دارد و
  CSS مدرن را می‌فهمد — ولی **باز هم جاوااسکریپت اجرا نمی‌کند**.

## پس چه کردیم — سه لایه

۱. **بدنهٔ ایمیل: ثابت ولی کامل.** جدول‌محور، CSS درون‌خطی، امن روی موتور
   Word. سیگنال واقعی همان‌جاست: کاشی‌های KPI، ردیف‌های صدر جدول،
   تراشهٔ وضعیت با **آیکن و برچسب** (نه فقط رنگ)، و نوار پیشرفت که با
   ``<table>`` ساخته شده نه ``div``. روی اتلوک کلاسیک هم دقیقاً همین
   دیده می‌شود.
۲. **ارتقای تدریجی برای اتلوک جدید.** یک بلوک ``@media`` که فقط موتورهای
   مدرن می‌بینند: حالت تاریک، گوشهٔ گرد واقعی، و چیدمان واکنش‌گرا روی
   موبایل. کلاسیک آن را نادیده می‌گیرد و چیزی خراب نمی‌شود.
۳. **گزارش داینامیک به‌عنوان پیوست.** همان فایل HTML مستقل که در مرورگر
   باز می‌شود: فیلتر زنده، نمودار، نقشهٔ سیال. یک دکمهٔ بزرگ در بدنه به
   آن اشاره می‌کند.

راه چهارمی هم هست — **Actionable Message / Adaptive Card** مایکروسافت —
که واقعاً در بدنهٔ اتلوک تعاملی است. عمداً نساختیم: ثبت ارائه‌دهنده نزد
مایکروسافت لازم دارد، به Exchange Online گره می‌خورد، و کارت آن ظرفیت
یک گزارش را ندارد. اگر روزی لازم شد، لایهٔ ۱ همان‌جا جایگزین می‌شود.

## محرمانگی

نشانی گیرندگان **هرگز** لاگ، ذخیره یا در خروجی چاپ نمی‌شود — فقط تعداد.
همان قاعده‌ای که در `integrations/daily_email.py` برقرار است:
انتخابگرِ داشبورد نام و اداره را نشان می‌دهد و نشانی را پشت یک شناسه
نگه می‌دارد.
"""
from __future__ import annotations

__contract__ = 1

#: ستون‌های محتملِ نشانی در سورس HR — هم نام استانداردشدهٔ adapter و هم
#: هدرهای خامی که فایل واقعی ممکن است داشته باشد.
EMAIL_COLUMNS = (
    "HR_EMAIL", "Email", "email", "EMAIL", "E-Mail", "e-mail", "E_MAIL",
    "Email Address", "EmailAddress", "Mail", "mail",
    "ایمیل", "ایمیل سازمانی", "پست الکترونیک", "پست الکترونیکی",
    "نشانی الکترونیکی", "آدرس ایمیل", "رایانامه",
)

import datetime as _dt
import html as _h
import os
import re
import subprocess as _sp
import sys as _sys
import time as _time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import aqua
from ..integrations.daily_email import NoRecipients, _EMAIL_RE

_L = aqua.LIGHT
_S = aqua.STATUS_LIGHT

#: پیوست‌هایی که می‌شود انتخاب کرد. کلید → (عنوان، پسوند، توضیح)
ARTIFACTS: Dict[str, Tuple[str, str, str]] = {
    "dashboard": ("داشبورد اکسل", ".xlsx",
                  "۱۷ شیت — خلاصه اجرایی، کالبدشکافی، تعیین تکلیف، تعهد ارزی"),
    "report": ("گزارش سازندهٔ گزارش", ".xlsx",
               "همان فیلدهایی که در تب «سازنده گزارش» انتخاب کرده‌اید"),
    "report_html": ("گزارش HTML", ".html",
                    "همان گزارش، با فیلتر و نمودار زنده در مرورگر"),
    "analysis": ("گزارش تحلیلی", ".html",
                 "محرک‌ها با بازه اطمینان و E-value، و زمان هر مرحله"),
    "audit": ("گزارش تعارض داده", ".xlsx",
              "جاهایی که دو سورس یک چیز را دو جور گفته‌اند"),
}


# ═══════════════════ دفترچه گیرندگان ═══════════════════
@dataclass(frozen=True)
class Person:
    """یک گیرندهٔ ممکن — نشانی پشت شناسه می‌ماند، نه در نمایش."""
    uid: str
    name: str
    unit: str
    role: str
    _address: str = field(repr=False, default="")

    @property
    def label(self) -> str:
        """آنچه در انتخابگر دیده می‌شود — بدون نشانی."""
        parts = [self.name] + [x for x in (self.unit, self.role) if x]
        return " · ".join(parts)

    @property
    def masked(self) -> str:
        """نشانی نقاب‌دار، فقط برای تأیید بصری کاربر."""
        a = self._address
        if "@" not in a:
            return "—"
        user, _, dom = a.partition("@")
        head = user[:2] if len(user) > 3 else user[:1]
        # نقاب با «•» نه «*». در markdown استریملیت، `**` علامت پررنگ است و
        # ستاره‌ها بی‌صدا حذف می‌شدند: «a.******@x» روی صفحه «a.@x» می‌شد
        # و کاربر فکر می‌کرد نشانی خراب است.
        return f"{head}{'•' * max(len(user) - len(head), 1)}@{dom}"


def find_email_column(hr) -> Optional[str]:
    """ستون نشانی را پیدا می‌کند — اول از روی نام، بعد از روی **محتوا**.

    فایل واقعی HR لزوماً هدرش «Email» نیست؛ می‌تواند «ایمیل»، «پست
    الکترونیک» یا هر نامِ دیگری باشد. اگر هیچ نامی نخواند، ستون‌ها را
    می‌گردیم و هر ستونی که مقدارهایش شکل نشانی دارند را برمی‌داریم.
    اینطور «ستون هست ولی اسمش را بلد نیستیم» دیگر به «گیرنده‌ای نیست»
    ترجمه نمی‌شود.
    """
    if hr is None or getattr(hr, "empty", True):
        return None
    cols = list(hr.columns)
    for cand in EMAIL_COLUMNS:
        if cand in cols:
            return cand
    norm = {str(c).strip().lower().replace(" ", "").replace("_", ""): c for c in cols}
    for cand in EMAIL_COLUMNS:
        key = cand.strip().lower().replace(" ", "").replace("_", "")
        if key in norm:
            return norm[key]
    # آخرین راه: تشخیص از روی محتوا
    best, best_hits = None, 0
    for c in cols:
        try:
            vals = hr[c].dropna().astype(str).head(200)
        except Exception:
            continue
        hits = sum(1 for v in vals if _EMAIL_RE.match(v.strip()))
        if hits > best_hits:
            best, best_hits = c, hits
    return best if best_hits else None


def directory(hr) -> List[Person]:
    """فهرست گیرندگان ممکن از سورس HR همین اجرا.

    فقط پرسنل **فعال** با نشانی معتبر. هیچ نشانی‌ای بیرون از این ساختار
    منتشر نمی‌شود.
    """
    if hr is None or getattr(hr, "empty", True):
        return []
    col = find_email_column(hr)
    if col is None:
        return []

    def pick(row, *names):
        for n in names:
            v = row.get(n)
            if v is not None and str(v).strip() not in ("", "nan"):
                return str(v).strip()
        return ""

    out: List[Person] = []
    for _, row in hr.iterrows():
        addr = str(row.get(col, "") or "").strip()
        if not _EMAIL_RE.match(addr):
            continue
        status = pick(row, "HR_STATUS", "status")
        if status and ("غیرفعال" in status or "فعال" not in status):
            continue
        # adapter ستون‌ها را HR_FULL_NAME / HR_FIRST_NAME / HR_LAST_NAME
        # می‌سازد — «HR_NAME» هرگز وجود نداشته و همیشه «—» می‌داد.
        name = pick(row, "HR_FULL_NAME", "HR_NAME", "name", "نام")
        if not name:
            first, last = pick(row, "HR_FIRST_NAME"), pick(row, "HR_LAST_NAME")
            name = " ".join(x for x in (first, last) if x)
        out.append(Person(
            uid=pick(row, "KEY_EMP", "HR_KEY_EMP", "HR_CODE") or addr,
            name=name or "—",
            unit=pick(row, "HR_OFFICE", "HR_DEPT", "ORG_DEPT") or "",
            role=pick(row, "HR_POST", "post") or "",
            _address=addr.lower()))
    out.sort(key=lambda p: (p.unit, p.name))
    return out


def parse_addresses(raw: str) -> Tuple[List[str], List[str]]:
    """نشانی‌های تایپ‌شده → (معتبر، نامعتبر).

    بدون این، انتخاب گیرنده فقط از سورس HR ممکن بود و اگر آن سورس ستون
    Email نداشت، هیچ راهی برای فرستادن نبود — کاربر نام‌ها را داشت ولی
    جایی برای واردکردنشان نبود.

    جداکننده: کاما، نقطه‌ویرگول، فاصله یا خط جدید (فارسی «؛» هم).
    خروجی هیچ‌جا لاگ یا ذخیره نمی‌شود؛ فقط به لحظهٔ ارسال می‌رود.
    """
    parts = [p.strip().strip("<>").strip()
             for p in re.split(r"[,;\u061b\s\n]+", raw or "") if p.strip()]
    good, bad = [], []
    seen = set()
    for p in parts:
        low = p.lower()
        if _EMAIL_RE.match(low):
            if low not in seen:
                seen.add(low)
                good.append(low)
        else:
            bad.append(p)
    return good, bad


def addresses(chosen: Sequence[Person]) -> List[str]:
    """نشانی‌های واقعی — فقط در لحظهٔ ارسال، هرگز در لاگ."""
    return sorted({p._address for p in chosen if p._address})


# ═══════════════════ بدنهٔ ایمیل، امن روی موتور Word ═══════════════════
def _cell(content: str, **css) -> str:
    style = ";".join(f"{k.replace('_', '-')}:{v}" for k, v in css.items())
    return f'<td style="{style}">{content}</td>'


def _kpi(label: str, value: str, color: str) -> str:
    """یک کاشی KPI — با جدول ساخته می‌شود، نه div.

    موتور Word روی ``div`` پدینگ نمی‌گذارد؛ کاشی‌ای که با div ساخته شود
    در اتلوک کلاسیک به هم می‌ریزد.
    """
    return (
        f'<td width="150" style="padding:0 6px" valign="top">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0" bgcolor="{_L["raised"]}" '
        f'style="border:1px solid {_L["border-soft"]};border-radius:10px">'
        f'<tr><td style="padding:12px 14px;font-family:{aqua.FONT_XLSX},Tahoma,'
        f'sans-serif;text-align:right">'
        f'<div style="font-size:11px;color:{_L["text-2"]};'
        f'mso-line-height-rule:exactly;line-height:16px">{_h.escape(label)}</div>'
        f'<div style="font-size:22px;font-weight:bold;color:{color};'
        f'mso-line-height-rule:exactly;line-height:30px">{_h.escape(value)}</div>'
        f'</td></tr></table></td>')


def _chip(label: str, color: str, icon: str) -> str:
    """تراشهٔ وضعیت — رنگ به‌تنهایی هرگز حامل معنا نیست، آیکن و برچسب هم هست."""
    return (f'<span style="font-family:{aqua.FONT_XLSX},Tahoma,sans-serif;'
            f'font-size:11px;color:{color};font-weight:bold">'
            f'{icon} {_h.escape(label)}</span>')


def _bar(pct: float, color: str, width: int = 90) -> str:
    """نوار پیشرفت با جدول تودرتو — تنها شکلی که موتور Word درست می‌کشد."""
    fill = max(0, min(100, int(round(pct))))
    return (
        f'<table role="presentation" width="{width}" cellpadding="0" cellspacing="0" '
        f'border="0" bgcolor="{_L["border-soft"]}" '
        f'style="border-radius:4px"><tr>'
        f'<td width="{fill}%" bgcolor="{color}" '
        f'style="height:6px;line-height:6px;font-size:0;border-radius:4px">&nbsp;</td>'
        f'<td width="{100 - fill}%" style="height:6px;line-height:6px;font-size:0">'
        f'&nbsp;</td></tr></table>')


#: CSS ارتقای تدریجی — فقط موتورهای مدرن (اتلوک جدید، وب، موبایل) می‌بینند.
#: موتور Word این بلوک را نادیده می‌گیرد و هیچ‌چیز خراب نمی‌شود.
_PROGRESSIVE = f"""
<style type="text/css">
  @media screen and (max-width:620px) {{
    .stack {{ display:block !important; width:100% !important; }}
    .pad {{ padding:10px 14px !important; }}
  }}
  @media (prefers-color-scheme: dark) {{
    .bg  {{ background:{aqua.DARK['surface']} !important; }}
    .card{{ background:{aqua.DARK['raised']} !important;
            border-color:{aqua.DARK['border-soft']} !important; }}
    .ink {{ color:{aqua.DARK['text']} !important; }}
    .ink2{{ color:{aqua.DARK['text-2']} !important; }}
  }}
  a.cta:hover {{ background:{_L['accent']} !important; }}
</style>
"""


def outlook_body(title: str, ref_date: str,
                 kpis: Sequence[Tuple[str, str, str]] = (),
                 rows: Sequence[Sequence[str]] = (),
                 headers: Sequence[str] = (),
                 note: str = "", attachments: Sequence[str] = (),
                 live_url: str = "") -> str:
    """بدنهٔ ایمیل — ثابت، ولی حامل سیگنال واقعی.

    روی موتور Word اتلوک کلاسیک همان‌قدر درست دیده می‌شود که روی اتلوک
    جدید: هیچ چیدمانی به flexbox یا grid تکیه ندارد.
    """
    kpi_cells = "".join(_kpi(l, v, c) for l, v, c in kpis) or "<td>&nbsp;</td>"

    head_cells = "".join(
        f'<th align="right" bgcolor="{_L["header"]}" '
        f'style="padding:8px 10px;font-family:{aqua.FONT_XLSX},Tahoma,sans-serif;'
        f'font-size:11px;color:{_L["on-header"]};font-weight:bold;'
        f'border:0">{_h.escape(str(h))}</th>' for h in headers)

    body_rows = []
    for i, r in enumerate(rows):
        bg = _L["surface"] if i % 2 else _L["raised"]
        tds = "".join(
            f'<td align="right" style="padding:7px 10px;'
            f'font-family:{aqua.FONT_XLSX},Tahoma,sans-serif;font-size:11px;'
            f'color:{_L["text"]};border-bottom:1px solid {_L["border-soft"]}">'
            f'{c}</td>' for c in r)
        body_rows.append(f'<tr bgcolor="{bg}">{tds}</tr>')

    table = ""
    if headers and body_rows:
        table = (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0" style="border:1px solid {_L["border-soft"]};'
            f'border-radius:10px;border-collapse:separate">'
            f'<tr>{head_cells}</tr>{"".join(body_rows)}</table>')

    att = ""
    if attachments:
        items = "".join(
            f'<tr><td style="padding:4px 0;font-family:{aqua.FONT_XLSX},Tahoma,'
            f'sans-serif;font-size:12px;color:{_L["text-2"]}">'
            f'📎 {_h.escape(a)}</td></tr>' for a in attachments)
        att = (f'<table role="presentation" width="100%" cellpadding="0" '
               f'cellspacing="0" border="0" bgcolor="{_L["highlight"]}" '
               f'style="border:1px solid {_L["border-soft"]};border-radius:10px">'
               f'<tr><td style="padding:12px 16px">'
               f'<div style="font-family:{aqua.FONT_XLSX},Tahoma,sans-serif;'
               f'font-size:12px;font-weight:bold;color:{_L["text"]};'
               f'padding-bottom:4px">پیوست‌ها</div>'
               f'<table role="presentation" cellpadding="0" cellspacing="0" '
               f'border="0">{items}</table>'
               f'<div style="font-family:{aqua.FONT_XLSX},Tahoma,sans-serif;'
               f'font-size:11px;color:{_L["text-3"]};padding-top:6px">'
               f'گزارش داینامیک را با مرورگر باز کنید — فیلتر و نمودار زنده '
               f'در بدنهٔ ایمیل کار نمی‌کند، چون هیچ کلاینت ایمیلی جاوااسکریپت '
               f'را اجرا نمی‌کند.</div>'
               f'</td></tr></table>')

    cta = ""
    if live_url:
        # VML تا گوشهٔ گرد و پس‌زمینهٔ دکمه روی موتور Word هم دیده شود.
        cta = f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td>
<!--[if mso]>
<v:roundrect xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:w="urn:schemas-microsoft-com:office:word"
 href="{_h.escape(live_url)}" style="height:40px;v-text-anchor:middle;width:210px"
 arcsize="24%" stroke="f" fillcolor="{_L['cta']}">
<w:anchorlock/><center style="color:{_L['on-cta']};font-family:Tahoma,sans-serif;
 font-size:13px;font-weight:bold">گشودن گزارش زنده</center>
</v:roundrect>
<![endif]-->
<!--[if !mso]><!-- -->
<a class="cta" href="{_h.escape(live_url)}"
 style="background:{_L['cta']};color:{_L['on-cta']};display:inline-block;
 font-family:{aqua.FONT_XLSX},Tahoma,sans-serif;font-size:13px;font-weight:bold;
 line-height:40px;text-align:center;text-decoration:none;width:210px;
 border-radius:10px">گشودن گزارش زنده</a>
<!--<![endif]-->
</td></tr></table>"""

    return f"""<!doctype html>
<html lang="fa" dir="rtl" xmlns:v="urn:schemas-microsoft-com:vml"
      xmlns:o="urn:schemas-microsoft-com:office:office">
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<!--[if mso]><xml><o:OfficeDocumentSettings>
<o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]-->
<title>{_h.escape(title)}</title>{_PROGRESSIVE}</head>
<body class="bg" style="margin:0;padding:0;background:{_L['surface']}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       bgcolor="{_L['surface']}"><tr><td align="center" style="padding:18px 10px">

<table role="presentation" width="820" cellpadding="0" cellspacing="0" border="0"
       style="width:820px;max-width:820px">

  <tr><td bgcolor="{_L['header']}" class="pad"
      style="padding:20px 24px;border-radius:12px 12px 0 0">
    <div style="font-family:{aqua.FONT_XLSX},Tahoma,sans-serif;font-size:20px;
      font-weight:bold;color:{_L['on-header-title']};
      mso-line-height-rule:exactly;line-height:28px">{_h.escape(title)}</div>
    <div style="font-family:{aqua.FONT_XLSX},Tahoma,sans-serif;font-size:12px;
      color:{_L['on-header-link']};padding-top:4px">تاریخ مرجع {_h.escape(ref_date)}</div>
  </td></tr>

  <tr><td class="card pad" bgcolor="{_L['raised']}"
      style="padding:18px 18px 8px;border:1px solid {_L['border-soft']};
      border-top:0">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"
           width="100%"><tr>{kpi_cells}</tr></table>
  </td></tr>

  <tr><td class="card pad" bgcolor="{_L['raised']}"
      style="padding:6px 18px 18px;border:1px solid {_L['border-soft']};
      border-top:0;border-bottom:0">{table}</td></tr>

  <tr><td class="card pad" bgcolor="{_L['raised']}"
      style="padding:0 18px 18px;border:1px solid {_L['border-soft']};
      border-top:0;border-bottom:0">{cta}</td></tr>

  <tr><td class="card pad" bgcolor="{_L['raised']}"
      style="padding:0 18px 18px;border:1px solid {_L['border-soft']};
      border-top:0">{att}</td></tr>

  <tr><td bgcolor="{_L['sunken']}" class="pad"
      style="padding:12px 20px;border-radius:0 0 12px 12px">
    <div class="ink2" style="font-family:{aqua.FONT_XLSX},Tahoma,sans-serif;
      font-size:11px;color:{_L['text-3']};mso-line-height-rule:exactly;
      line-height:18px">{_h.escape(note)}</div>
  </td></tr>

</table>
</td></tr></table></body></html>"""


# ═══════════════════ بسترِ ارسال ═══════════════════
#: چه چیزی روی این سیستم ممکن است.
#:
#: مسیر «ارسال با یک کلیک» از COM اتلوکِ **ویندوز** می‌آید. اتلوک مک چنین
#: رابطی ندارد و «اتلوک جدید» حتی AppleScript قدیمی را هم برداشته. پس
#: به‌جای ادعای پشتیبانی، همان چیزی را می‌گوییم که واقعاً هست: روی مک
#: پیام با همهٔ پیوست‌ها در کلاینت ایمیل **باز** می‌شود و فرستادنش یک
#: کلیکِ خودِ کاربر است.
OUTLOOK_COM = "outlook-com"      #: ویندوز + اتلوک کلاسیک + pywin32
MAC_OPEN = "mac-open"            #: مک — پیام در کلاینت پیش‌فرض باز می‌شود
EML_ONLY = "eml-only"            #: بقیه — فقط دانلود پروندهٔ .eml


def backend() -> str:
    """بسترِ ارسالِ همین سیستم."""
    if _sys.platform.startswith("win"):
        return OUTLOOK_COM
    if _sys.platform == "darwin":
        return MAC_OPEN
    return EML_ONLY


def can_send_directly() -> bool:
    """آیا «ارسال» روی این سیستم واقعاً یعنی فرستادن؟"""
    return backend() == OUTLOOK_COM


def action_label() -> Tuple[str, str]:
    """(برچسب دکمهٔ اصلی، توضیحش) — متناسب با همین سیستم.

    رابط نباید روی مک دکمهٔ «ارسال» نشان بدهد و بعد فقط پنجره باز کند؛
    یک بار همین اتفاق روی ویندوز افتاد (ذخیره به‌جای ارسال) و کاربر
    درست نتیجه گرفت که برنامه کاری را که گفته انجام نمی‌دهد.
    """
    if can_send_directly():
        return ("ارسال", "پیام فرستاده می‌شود؛ این کار برگشت‌ناپذیر است.")
    if backend() == MAC_OPEN:
        return ("باز کردن در کلاینت ایمیل",
                "همان پیام با همین پیوست‌ها در اتلوک/Mail باز می‌شود؛ "
                "فرستادنش با خود شماست.")
    return ("دانلود پروندهٔ .eml",
            "روی این سیستم کلاینتی برای باز کردن مستقیم نیست.")


#: پیام‌های ساخته‌شده روی مک اینجا می‌نشینند تا کلاینت بازشان کند.
#: نشانی گیرنده داخل همین پرونده است، پس پوشه ۷۰۰ است، پرونده ۶۰۰، و
#: هر چه از 7 روز گذشته باشد پاک می‌شود — سیاههٔ نشانی‌ها روی دیسک
#: تلنبار نمی‌شود. نام پرونده هیچ نشانی‌ای ندارد.
SPOOL_TTL_DAYS = 7


def spool_dir() -> Path:
    d = Path(os.environ.get("AIBL_HOME") or (Path.home() / ".aibl")) / "outbox"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def _prune_spool(d: Path) -> None:
    cutoff = _time.time() - SPOOL_TTL_DAYS * 86400
    for p in d.glob("dispatch-*.eml"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def _open_in_client(subject: str, body_html: str, to: Sequence[str],
                    cc: Sequence[str], files: Sequence[Path],
                    res: "Dispatch") -> "Dispatch":
    """پیام را می‌سازد و به کلاینت ایمیلِ مک می‌سپارد."""
    d = spool_dir()
    _prune_spool(d)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = d / f"dispatch-{stamp}-{os.getpid()}.eml"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(eml(subject, body_html, to, cc, files))
    for app in ("Microsoft Outlook", "Mail"):
        rc = _sp.call(["open", "-a", app, str(path)],
                      stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        if rc == 0:
            res.displayed = True
            res.note = f"در «{app}» باز شد — فرستادنش با شماست."
            return res
    _sp.check_call(["open", str(path)])
    res.displayed = True
    res.note = "در کلاینت ایمیل پیش‌فرض باز شد — فرستادنش با شماست."
    return res


# ═══════════════════ ارسال ═══════════════════
@dataclass
class Dispatch:
    """نتیجهٔ یک ارسال — بدون هیچ نشانی."""
    to_count: int = 0
    cc_count: int = 0
    attachments: List[str] = field(default_factory=list)
    sent: bool = False
    displayed: bool = False
    note: str = ""

    @property
    def summary(self) -> str:
        state = "ارسال شد" if self.sent else ("در کلاینت ایمیل باز شد" if self.displayed
                                              else "آماده شد")
        return (f"{state} — {self.to_count} گیرنده"
                + (f" و {self.cc_count} رونوشت" if self.cc_count else "")
                + (f" · {len(self.attachments)} پیوست" if self.attachments else "")
                + (f" · {self.note}" if self.note else ""))


def send(subject: str, body_html: str,
         to: Sequence[str], cc: Sequence[str] = (),
         attachments: Sequence[Path] = (), send_now: bool = False) -> Dispatch:
    """ایمیل را در اتلوک می‌سازد و در صورت درخواست می‌فرستد.

    ``send_now=True`` پیام را می‌فرستد و **هیچ پیش‌نویسی نمی‌سازد**.
    ``send_now=False`` پیام را در کلاینت باز می‌کند تا کاربر پیش از
    فرستادن ببیند. هیچ‌کدام از این دو، پیام را در «پیش‌نویس» رها نمی‌کند.

    ``send_now=True`` فقط روی بستر :data:`OUTLOOK_COM` معنا دارد
    (ویندوز + اتلوک کلاسیک). روی مک صریحاً خطا می‌دهد به‌جای اینکه
    بی‌صدا به «باز کردن» تنزل کند؛ رابط باید با :func:`action_label`
    از اول برچسبِ درست را نشان بدهد.
    """
    to = [t for t in to if t]
    if not to:
        raise NoRecipients("هیچ گیرنده‌ای انتخاب نشده است.")
    files = [Path(a) for a in attachments if Path(a).exists()]
    res = Dispatch(to_count=len(to), cc_count=len([c for c in cc if c]),
                   attachments=[f.name for f in files])
    kind = backend()
    if kind == MAC_OPEN:
        if send_now:
            raise RuntimeError(
                "روی مک، «ارسال» خودکار ممکن نیست: آن مسیر از COM اتلوکِ "
                "ویندوز می‌آید و اتلوک مک چنین رابطی ندارد. با گزینهٔ "
                "«باز کردن در کلاینت ایمیل» همان پیام با همین پیوست‌ها "
                "باز می‌شود و فرستادنش یک کلیک خودتان است.")
        return _open_in_client(subject, body_html, to, cc, files, res)
    if kind == EML_ONLY:
        raise RuntimeError(
            "روی این سیستم‌عامل کلاینتی برای ارسال مستقیم نیست. "
            "پروندهٔ .eml را دانلود کنید و با کلاینت خودتان بازش کنید.")
    try:
        import win32com.client as win32
    except ImportError as ex:
        raise RuntimeError(
            "ارسال از داخل پلتفرم به اتلوک کلاسیکِ ویندوز و pywin32 نیاز "
            "دارد. روی این ویندوز pywin32 نصب نیست: "
            "`pip install pywin32`. تا آن‌وقت پروندهٔ .eml راهِ ارسال است."
        ) from ex
    outlook = win32.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)
    mail.BodyFormat = 2
    mail.Subject = subject
    mail.To = "; ".join(to)
    if cc:
        mail.CC = "; ".join([c for c in cc if c])
    sender = os.environ.get("AIBL_EMAIL_SENDER", "").strip().lower()
    if sender:
        try:
            for acc in outlook.Session.Accounts:
                if getattr(acc, "SmtpAddress", "").lower() == sender:
                    mail._oleobj_.Invoke(*(64209, 0, 8, 0, acc))
                    break
        except Exception:
            pass
    for f in files:
        mail.Attachments.Add(str(f.resolve()))
    mail.HTMLBody = body_html
    if send_now:
        # عمداً بدون Save(). قبلاً Save() همیشه اجرا می‌شد و یک رونوشت در
        # پوشهٔ «پیش‌نویس» جا می‌گذاشت؛ کاربری که «ارسال» زده بود، پیام را
        # در Drafts می‌دید و نتیجه می‌گرفت که برنامه به‌جای فرستادن،
        # ذخیره کرده است. حالا ارسال یعنی ارسال.
        mail.Send()
        res.sent = True
    else:
        mail.Display()
        res.displayed = True
    return res


def eml(subject: str, body_html: str, to: Sequence[str], cc: Sequence[str] = (),
        attachments: Sequence[Path] = ()) -> bytes:
    """پروندهٔ ``.eml`` — راه ارسال روی سیستمی که اتلوک ندارد.

    کاربر فایل را باز می‌کند و اتلوک همان پیام را با پیوست‌ها نشان
    می‌دهد. بدون این، پلتفرم روی لینوکس هیچ راه ارسالی نداشت.
    """
    from email.message import EmailMessage
    import mimetypes

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.set_content("این پیام HTML است؛ با کلاینتی که HTML نشان می‌دهد بازش کنید.")
    msg.add_alternative(body_html, subtype="html")
    for a in attachments:
        p = Path(a)
        if not p.exists():
            continue
        ctype, _ = mimetypes.guess_type(p.name)
        maintype, _, subtype = (ctype or "application/octet-stream").partition("/")
        msg.add_attachment(p.read_bytes(), maintype=maintype, subtype=subtype,
                           filename=p.name)
    return msg.as_bytes()
