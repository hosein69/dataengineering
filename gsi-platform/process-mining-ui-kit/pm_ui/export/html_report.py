# -*- coding: utf-8 -*-
"""خروجی HTML سبک برای ارسال ایمیل اوتلوک سازمانی.

## چرا این ماژول از ``pm_ui.charts`` استفاده نمی‌کند

آن‌چه در Streamlit می‌بینید (کارت با گرادیان، گراف SVG با هاور، تخته
کانبان با اسکرول) و آن‌چه در ایمیل باز می‌شود دو چیز متفاوت‌اند:
Streamlit یک صفحهٔ وب کامل با مرورگر مدرن پشت آن است؛ Outlook کلاینت
دسکتاپ با موتور رندر Word را برای HTML به کار می‌برد که **Flexbox،
CSS Grid، و اغلب انیمیشن را نادیده می‌گیرد یا می‌شکند**. تزریق همان
HTML/CSS داشبورد در ایمیل یعنی برای مدیری که Outlook دسکتاپ دارد، گزارش
درهم‌ریخته باز شود.

قاعده‌های این ماژول:
    • فقط ``<table>`` برای چیدمان (سازگارترین روش با موتور رندر Word)
    • بدون Flex/Grid/انیمیشن/جاوااسکریپت
    • بدون فراخوانی فونت از اینترنت — فقط پشتهٔ فونت سیستمی
    • بدون تصویر بیرونی — کل سند یک فایل خودبسندهٔ کوچک است
    • گراف فرآیند به‌جای SVG تعاملی، به «جدول مسیرهای پرتکرار» ساده می‌شود
"""
from __future__ import annotations

__contract__ = 1

import html as _html
from datetime import datetime
from typing import Iterable, List, Mapping, Optional, Sequence

from .. import persian as fa
from .. import tokens as T

# پشتهٔ فونت ایمیل — عمداً بدون @font-face؛ اکثر کلاینت‌های ایمیل، فونت
# بیرونی/وب را بارگذاری نمی‌کنند یا با تأخیر امنیتی مسدودش می‌کنند.
EMAIL_FONT_STACK = "'IRANSansWeb','IRANSans','Tahoma','Segoe UI',Arial,sans-serif"


def _esc(v: object) -> str:
    return _html.escape("" if v is None else str(v), quote=True)


def kpi_table_html(kpis: Sequence[Mapping]) -> str:
    """ردیف کارت KPI با جدول HTML — رندر یکسان در Outlook، Gmail و مرورگر."""
    cells = []
    for k in kpis:
        status = T.status_of(k.get("status") or "good")
        cells.append(f"""
<td width="25%" style="padding:6px" valign="top">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background:{T.SURFACE_RAISED};border:1px solid {T.BORDER};
                border-top:3px solid {status.fill};border-radius:{T.RADIUS['md']}px">
    <tr><td style="padding:14px 16px">
      <div style="font-size:12px;color:{T.INK_MUTED};font-weight:600">{_esc(k.get('label',''))}</div>
      <div style="font-size:22px;font-weight:700;color:{T.INK};margin-top:6px">{_esc(k.get('value',''))}</div>
      <div style="font-size:11px;color:{status.ink};margin-top:4px;font-weight:700">{_esc(k.get('delta',''))}</div>
    </td></tr>
  </table>
</td>""")
    # چهارتایی چیده می‌شود؛ اگر تعداد کمتر باشد، سلول خالی برای حفظ عرض اضافه می‌شود
    rows = []
    row = []
    for i, cell in enumerate(cells, 1):
        row.append(cell)
        if i % 4 == 0:
            rows.append(row); row = []
    if row:
        while len(row) < 4:
            row.append('<td width="25%"></td>')
        rows.append(row)
    body = "".join(f"<tr>{''.join(r)}</tr>" for r in rows)
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{body}</table>'


def top_routes_table_html(nodes: Sequence[Mapping], edges: Sequence[Mapping], *, top_n: int = 6) -> str:
    """Outlook-safe route table; unique cases, occurrences and observed timing stay distinct."""
    labels = {n.get("id"): n.get("label", n.get("id")) for n in nodes}
    ranked = sorted(edges, key=lambda e: (-int(e.get("count", 0)), -int(e.get("occurrences", 0))))[:top_n]
    rows = []
    for e in ranked:
        rows.append(f"""
<tr>
  <td style="padding:8px 10px;border-bottom:1px solid {T.BORDER};color:{T.INK};font-weight:600">{_esc(labels.get(e.get('source'), e.get('source')))}</td>
  <td style="padding:8px 10px;border-bottom:1px solid {T.BORDER};color:{T.INK};font-weight:600">{_esc(labels.get(e.get('target'), e.get('target')))}</td>
  <td style="padding:8px 10px;border-bottom:1px solid {T.BORDER};text-align:center">{_esc(e.get('count',0))}</td>
  <td style="padding:8px 10px;border-bottom:1px solid {T.BORDER};text-align:center">{_esc(e.get('occurrences',0))}</td>
  <td style="padding:8px 10px;border-bottom:1px solid {T.BORDER};text-align:center">{_esc(e.get('median_hours',''))}</td>
  <td style="padding:8px 10px;border-bottom:1px solid {T.BORDER};text-align:center">{_esc(e.get('p90_hours',''))}</td>
</tr>""")
    head = f"""
<tr style="background:{T.SURFACE_SUNKEN}">
  <th style="padding:8px 10px;text-align:right;font-size:12px;color:{T.INK_MUTED}">مبدأ</th>
  <th style="padding:8px 10px;text-align:right;font-size:12px;color:{T.INK_MUTED}">مقصد</th>
  <th style="padding:8px 10px;font-size:12px;color:{T.INK_MUTED}">پرونده یکتا</th>
  <th style="padding:8px 10px;font-size:12px;color:{T.INK_MUTED}">دفعات عبور</th>
  <th style="padding:8px 10px;font-size:12px;color:{T.INK_MUTED}">میانه ساعت</th>
  <th style="padding:8px 10px;font-size:12px;color:{T.INK_MUTED}">P90 ساعت</th>
</tr>"""
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border:1px solid {T.BORDER};border-radius:{T.RADIUS["md"]}px;overflow:hidden">'
            f"{head}{''.join(rows)}</table>")


def kanban_summary_table_html(columns: Sequence[Mapping], *, max_cards: int = 3) -> str:
    """خلاصهٔ کانبان به‌صورت جدول ستونی — بدون اسکرول/فلکس، سازگار با ایمیل."""
    n = max(1, len(columns))
    width = f"{100 // n}%"
    heads, bodies = [], []
    for col in columns:
        status = T.status_of(col.get("status") or "good")
        cards = list(col.get("cards", []))[:max_cards]
        more = len(col.get("cards", [])) - len(cards)
        heads.append(f'<th width="{width}" style="padding:8px;border-bottom:2px solid {status.fill};'
                    f'font-size:12px;color:{T.INK}">{_esc(col.get("title",""))} '
                    f'({_esc(fa.fa_number(len(col.get("cards", []))))})</th>')
        items = "".join(
            f'<div style="font-size:11px;color:{T.INK_SOFT};padding:4px 0;'
            f'border-bottom:1px solid {T.BORDER}">{_esc(c.get("title",""))}</div>'
            for c in cards)
        if more > 0:
            items += (f'<div style="font-size:10.5px;color:{T.INK_MUTED};padding:4px 0">'
                      f'و {_esc(fa.fa_number(more))} مورد دیگر…</div>')
        bodies.append(f'<td width="{width}" valign="top" style="padding:8px">{items}</td>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border:1px solid {T.BORDER};border-radius:{T.RADIUS["md"]}px">'
            f"<tr>{''.join(heads)}</tr><tr>{''.join(bodies)}</tr></table>")


def build_report_html(*, title: str, kpis: Sequence[Mapping],
                       nodes: Sequence[Mapping], edges: Sequence[Mapping],
                       kanban: Optional[Sequence[Mapping]] = None,
                       subtitle: Optional[str] = None,
                       footer_note: str = "این گزارش به‌صورت خودکار و آفلاین تولید شده است.") -> str:
    """سند کامل HTML — سبک، راست‌به‌چپ، خودبسنده، آماده برای پیوست ایمیل.

    اندازهٔ خروجی معمولاً چند ده کیلوبایت است (بدون فونت/تصویر جاسازی‌شده)،
    پس ارسال از طریق اوتلوک سازمانی با هیچ محدودیت اندازه‌ای برخورد نمی‌کند.
    """
    sub = f'<div style="font-size:13px;color:{T.INK_MUTED};margin-top:4px">{_esc(subtitle)}</div>' if subtitle else ""
    kanban_html = ""
    if kanban:
        kanban_html = (f'<h2 style="font-size:15px;color:{T.INK};margin:22px 0 8px">وضعیت کیس‌ها بر اساس مرحله</h2>'
                       f"{kanban_summary_table_html(kanban)}")
    generated = fa.today_jalali_str()
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title>
</head>
<body style="margin:0;padding:20px;background:{T.SURFACE_PAGE};font-family:{EMAIL_FONT_STACK};color:{T.INK}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:900px;margin:0 auto">
<tr><td>

<div style="background:{T.INK};color:#fff;border-radius:{T.RADIUS['lg']}px;padding:20px 24px">
  <div style="font-size:20px;font-weight:700">{_esc(title)}</div>
  {sub}
  <div style="font-size:11px;color:#cbd5e1;margin-top:10px">تولید شده در {_esc(generated)}</div>
</div>

<h2 style="font-size:15px;color:{T.INK};margin:22px 0 8px">شاخص‌های کلیدی عملکرد</h2>
{kpi_table_html(kpis)}

<h2 style="font-size:15px;color:{T.INK};margin:22px 0 8px">پرتکرارترین مسیرهای فرآیند</h2>
{top_routes_table_html(nodes, edges)}

{kanban_html}

<div style="margin-top:24px;padding-top:12px;border-top:1px solid {T.BORDER};
            font-size:10.5px;color:{T.INK_MUTED}">{_esc(footer_note)}</div>

</td></tr>
</table>
</body>
</html>"""
