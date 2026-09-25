# -*- coding: utf-8 -*-
"""خروجی HTML **مستقل و کامل** — همان چیزی که واقعاً دست مخاطب نهایی می‌رود.

## این با ``html_report.py`` چه فرقی دارد

``html_report.py`` عمداً کم‌جان است: فقط جدول، برای ایمیل اوتلوک که موتور
رندرش (Word) از Flexbox/Grid/SVG/جاوااسکریپت پشتیبانی نمی‌کند یا ناقص
پشتیبانی می‌کند. این فایل برعکس است — **کامل‌ترین** بازتولید ظاهر و
عملکرد بصری خود پلتفرم: کارت KPI با گرادیان و سایه، کارت شاهد، نقشهٔ
جریان فرآیند (SVG واقعی، نه جدول مسیرها)، نمودار شدت و نقشهٔ حرارتی
(SVG استاتیک به‌جای Plotly تعاملی)، جدول شواهد، خط لولهٔ سیستمی، و تخته
کانبان — یعنی همان چیزی که تیم محصول در Streamlit می‌بیند، منهای
تعامل زنده (فیلتر، زوم نمودار).

با این حال هنوز **سبک** است: بدون جاوااسکریپت، بدون فراخوانی هیچ‌چیز از
اینترنت، بدون هیچ کتابخانهٔ بیرونی — یک فایل HTML خودبسنده که با
دوبار‌کلیک از روی فولدر شبکه در هر مرورگری باز می‌شود، **و فونت فارسی هم
واقعاً در خودِ فایل جاسازی شده** (Vazirmatn، متن‌باز SIL OFL، به‌صورت
base64) — نه فرض «شاید روی سیستم مقصد نصب باشد». اگر فقط به فونت
سیستمی تکیه می‌کردیم، روی اکثر ویندوزهای اداری چیزی جز Tahoma دیده
نمی‌شد؛ IRANSansWeb دارایی مجوزدار است و نمی‌شود بدون فایل واقعی آن را
جاسازی کرد، پس Vazirmatn (سومین اولویت در خواستهٔ اولیه) همان چیزی است
که تضمین‌شده رندر می‌شود.

## کِی از کدام استفاده کنیم

    html_report.build_report_html        پیوست/بدنهٔ ایمیل اوتلوک
    standalone_html.build_standalone_html  فایلی که روی فولدر شبکه می‌گذارید
                                            یا به‌عنوان پیوست غیرایمیلی می‌فرستید
                                            (مثلاً از طریق پیام‌رسان داخلی)
"""
from __future__ import annotations

__contract__ = 1

import base64
import functools
import html as _html
from pathlib import Path
from typing import Any, Mapping, Optional

from .. import persian as fa
from .. import tokens as T
from ..charts import (flowgraph_svg, heatmap_svg, intensity_area_svg,
                      kanban_board_html, system_flow_html)
from ..components import evidence_table_html, insight_row_html, kpi_row_html

STANDALONE_FONT_STACK = T.FONT_STACK

#: pm_ui/export/standalone_html.py → ریشهٔ پروژه → static/fonts/...
_VAZIRMATN_FILE = Path(__file__).resolve().parent.parent.parent / "static" / "fonts" / "Vazirmatn-Variable.woff2"


def _esc(v: object) -> str:
    return _html.escape("" if v is None else str(v), quote=True)


@functools.lru_cache(maxsize=1)
def _embedded_font_face() -> str:
    """Vazirmatn را به‌صورت base64 در خودِ سند جاسازی می‌کند — یک فایل، بدون
    هیچ وابستگی بیرونی، و فونت فارسی هرجا باز شود درست دیده می‌شود.

    اگر فایل فونت یافت نشد (مثلاً کسی پوشهٔ ``static/fonts`` را حذف کرده)،
    بی‌صدا رد می‌شود؛ سند همچنان با پشتهٔ فونت سیستمی باز می‌شود، فقط بدون
    تضمین ظاهر فارسی — بهتر از شکستن کامل ساخت گزارش.
    """
    try:
        data = _VAZIRMATN_FILE.read_bytes()
    except OSError:
        return ""
    b64 = base64.b64encode(data).decode("ascii")
    return f"""
@font-face {{
  font-family: 'Vazirmatn';
  src: url('data:font/woff2;base64,{b64}') format('woff2-variations'),
       url('data:font/woff2;base64,{b64}') format('woff2');
  font-weight: 100 900;
  font-style: normal;
}}"""


def _section(title: str, body: str, *, note: Optional[str] = None) -> str:
    note_html = f'<p class="pm-sec-note">{_esc(note)}</p>' if note else ""
    return f"""
<section class="pm-card">
  <h2>{_esc(title)}</h2>
  {note_html}
  {body}
</section>"""


def build_standalone_html(*, title: str, data: Mapping[str, Any],
                          subtitle: str = "", audience_label: str = "") -> str:
    """سند کامل HTML — برای بازکردن مستقیم در مرورگر از فولدر شبکه.

    ``data`` همان ساختاری است که به ``pm_ui.layout.render_layout`` هم داده
    می‌شود (``kpis``, ``insights``, ``graph``, ``evidence``, ``kanban``,
    ``system``, ``intensity``, ``heatmap``) — یک منبع داده، هم برای
    Streamlit، هم برای این خروجی.
    """
    kpis = data.get("kpis", [])
    insights = data.get("insights", [])
    graph = data.get("graph", {"nodes": [], "edges": []})
    evidence = data.get("evidence")
    kanban = data.get("kanban", [])
    system = data.get("system", [])
    intensity = data.get("intensity", {"labels": [], "series": {}})
    heatmap = data.get("heatmap", {"z": [], "x": [], "y": []})

    sections = []
    if kpis:
        sections.append(_section("شاخص‌های کلیدی عملکرد", kpi_row_html(kpis)))
    if insights:
        sections.append(_section("شواهد و یافته‌ها", insight_row_html(insights, columns=1)))
    if graph.get("nodes"):
        sections.append(_section(
            "نقشهٔ جریان فرآیند",
            flowgraph_svg(graph["nodes"], graph["edges"], width=980, height=460),
            note="ضخامت هر مسیر متناسب با تعداد کیس‌هایی است که از آن عبور کرده‌اند."))
    if intensity.get("labels") or heatmap.get("z"):
        charts = []
        if intensity.get("labels"):
            charts.append(f'<div style="flex:1 1 380px">{intensity_area_svg(intensity["labels"], intensity["series"], title="روند حجم کیس")}</div>')
        if heatmap.get("z"):
            charts.append(f'<div style="flex:1 1 320px">{heatmap_svg(heatmap["z"], heatmap["x"], heatmap["y"], title="شدت فعالیت هفتگی")}</div>')
        sections.append(_section("روند و شدت جریان",
                                 f'<div style="display:flex;gap:20px;flex-wrap:wrap">{"".join(charts)}</div>'))
    if evidence:
        sections.append(_section("شواهد رویداد", evidence_table_html(evidence)))
    if system:
        sections.append(_section("خط لولهٔ سیستمی", system_flow_html(system)))
    if kanban:
        sections.append(_section("وضعیت کیس‌ها در هر مرحله", kanban_board_html(kanban)))

    sub_line = f'<div class="pm-sub">{_esc(subtitle)}</div>' if subtitle else ""
    audience_line = f'<div class="pm-audience">نمای {_esc(audience_label)}</div>' if audience_label else ""

    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>{_esc(title)}</title>
<style>
{_embedded_font_face()}
  *{{box-sizing:border-box}}
  html{{direction:rtl}}
  body{{margin:0;background:{T.SURFACE_PAGE};color:{T.INK};
    font-family:{STANDALONE_FONT_STACK};direction:rtl}}
  .pm-wrap{{max-width:{T.CONTAINER_MAX}px;margin:0 auto;padding:28px 24px 60px}}
  .pm-header{{background:{T.BRAND_NAVY};color:#fff;border-radius:{T.RADIUS['lg']}px;
    padding:28px 32px}}
  .pm-header h1{{margin:0 0 4px;font-size:28px;font-weight:800}}
  .pm-sub{{font-size:14px;color:rgba(255,255,255,.82)}}
  .pm-audience{{font-size:12px;color:rgba(255,255,255,.65);margin-top:10px}}
  .pm-card{{background:{T.SURFACE_RAISED};border:1px solid {T.BORDER};
    border-radius:{T.RADIUS['lg']}px;box-shadow:{T.SHADOW_CARD};
    padding:22px 24px;margin-top:20px}}
  .pm-card h2{{margin:0 0 14px;font-size:17px;font-weight:800;color:{T.INK}}}
  .pm-sec-note{{margin:-8px 0 14px;font-size:12.5px;color:{T.INK_MUTED}}}
  .pm-footer{{margin-top:28px;padding-top:16px;border-top:1px solid {T.BORDER};
    font-size:11.5px;color:{T.INK_MUTED};line-height:1.8}}
</style>
</head>
<body>
<div class="pm-wrap">

  <header class="pm-header">
    <h1>{_esc(title)}</h1>
    {sub_line}
    {audience_line}
  </header>

  {''.join(sections)}

  <div class="pm-footer">
    تولید شده در {_esc(fa.today_jalali_str())} — این نسخهٔ کامل HTML است (برای بازکردن
    مستقیم در مرورگر یا اشتراک‌گذاری غیرایمیلی). برای ارسال از طریق ایمیل اوتلوک
    سازمانی، از نسخهٔ سبک استفاده کنید (دکمهٔ «دانلود HTML ایمیل»).
    داده‌های این نمونه ساختگی‌اند و صرفاً ظرفیت طراحی را نشان می‌دهند.
  </div>

</div>
</body>
</html>"""
