# -*- coding: utf-8 -*-
"""اجزای پایه — کارت KPI، نشان وضعیت، و ابزارهای HTML امن.

اجزای این فایل با ``streamlit.components.v1.html`` رندر می‌شوند، نه با
``st.markdown``: عناصر بومی Streamlit (st.metric و ...) برای ظاهر لوکسِ
خواسته‌شده کافی نیستند و کنترل کامل روی چیدمان/گرادیان/سایه لازم است.
هر مقدار متنی پیش از درج در HTML از :func:`esc` عبور می‌کند تا از تزریق
جلوگیری شود؛ داده‌های ورودی همیشه غیرقابل‌اعتماد فرض می‌شوند.
"""
from __future__ import annotations

__contract__ = 1

import html as _html
from typing import Dict, Iterable, List, Optional, Sequence, TypedDict

from . import persian as fa
from . import tokens as T


def esc(value: object) -> str:
    return _html.escape("" if value is None else str(value), quote=True)


class KpiSpec(TypedDict, total=False):
    label: str          # عنوان کارت
    value: str          # مقدار نمایشی (از قبل با fa_number/fa_money قالب‌بندی‌شده)
    delta: str           # تغییر نسبت به دورهٔ قبل، مثلاً «‎+۱۲٪»
    delta_good: bool     # آیا این تغییر مثبت تلقی می‌شود؟
    status: str          # کلید STATUS برای رنگ نوار پایین کارت
    spark: Sequence[float]  # مقادیر روند برای ریزنمودار
    icon: str


def _sparkline_svg(values: Sequence[float], color: str, *, width: int = 96, height: int = 28) -> str:
    if not values or len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    step = width / (len(values) - 1)
    pts = [(i * step, height - ((v - lo) / span) * (height - 4) - 2) for i, v in enumerate(values)]
    path = " ".join(f"{'L' if i else 'M'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    area = path + f" L{pts[-1][0]:.1f},{height} L0,{height} Z"
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'preserveAspectRatio="none" aria-hidden="true">'
            f'<path d="{area}" fill="{color}22"></path>'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round"></path></svg>')


def _kpi_card_html(spec: KpiSpec, index: int) -> str:
    status = T.status_of(spec.get("status") or "good")
    delta = str(spec.get("delta", "")).strip()
    delta_html = ""
    if delta:
        good = spec.get("delta_good")
        color = status.ink if good is None else (T.STATUS["good"].ink if good else T.STATUS["critical"].ink)
        arrow = "▲" if delta.strip().startswith(("+", "‎+")) else ("▼" if delta.strip().startswith("-") else "•")
        delta_html = f'<div class="d" style="color:{color}">{arrow} {esc(delta)}</div>'
    icon = spec.get("icon", "")
    icon_html = f'<span class="ic">{esc(icon)}</span>' if icon else ""
    spark = spec.get("spark")
    spark_html = _sparkline_svg(list(spark), status.fill) if spark else ""
    return f"""
<div class="kpi" style="--i:{index}">
  <div class="bar" style="background:{status.fill}"></div>
  <div class="top"><span class="lab">{icon_html}{esc(spec.get('label',''))}</span></div>
  <div class="val pm-num">{esc(spec.get('value',''))}</div>
  <div class="foot">{delta_html}<div class="spark">{spark_html}</div></div>
</div>"""


def render_kpi_row(kpis: Iterable[KpiSpec], *, height: int = 168,
                    columns: Optional[int] = None) -> None:
    """ردیف کارت‌های KPI لوکس را با ``components.v1.html`` رندر می‌کند.

    ``columns`` را خالی بگذارید تا شبکه خودش با CSS Grid بر اساس عرض
    جمع شود (ریسپانسیو بدون media query دستی).

    عمداً از ``streamlit.components.v1.html`` استفاده شده، نه ``st.iframe``
    (نگارش‌های جدیدتر Streamlit)، چون محیط شما آفلاین است و ممکن است
    Streamlit نصب‌شده نسخهٔ قدیمی‌تری باشد که ``st.iframe`` را ندارد؛
    ``components.v1.html`` از نگارش ۱٫۰ به بعد همیشه در دسترس است.
    """
    import streamlit.components.v1 as components

    items = list(kpis)
    cards = "".join(_kpi_card_html(k, i) for i, k in enumerate(items))
    col_css = f"repeat({columns}, 1fr)" if columns else "repeat(auto-fit, minmax(190px, 1fr))"
    html = f"""
<div class="wrap">
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:{T.FONT_STACK};direction:rtl}}
  .wrap{{display:grid;grid-template-columns:{col_css};gap:12px}}
  .kpi{{
    position:relative;overflow:hidden;background:{T.SURFACE_RAISED};
    border:1px solid {T.BORDER};border-radius:{T.RADIUS['lg']}px;
    padding:16px 18px 14px;box-shadow:{T.SHADOW_CARD};
    transition:transform .28s cubic-bezier(.22,1,.36,1), box-shadow .28s;
    animation:rise .45s cubic-bezier(.22,1,.36,1) both;
    animation-delay:calc(var(--i) * 55ms);
  }}
  .kpi:hover{{transform:translateY(-3px);box-shadow:{T.SHADOW_CARD_HOVER}}}
  .kpi .bar{{position:absolute;inset:0 0 auto 0;height:3px}}
  .kpi .top{{display:flex;align-items:center;justify-content:space-between}}
  .kpi .lab{{font-size:12.5px;color:{T.INK_MUTED};font-weight:600}}
  .kpi .ic{{margin-left:6px}}
  .kpi .val{{font-size:26px;font-weight:800;color:{T.INK};margin-top:8px;
    line-height:1.15;unicode-bidi:plaintext}}
  .kpi .foot{{display:flex;align-items:center;justify-content:space-between;margin-top:10px}}
  .kpi .d{{font-size:12px;font-weight:700}}
  .kpi .spark{{line-height:0}}
  @keyframes rise{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
  @media (prefers-reduced-motion:reduce){{.kpi{{animation:none;transition:none}}}}
</style>
{cards}
</div>"""
    # ارتفاع iframe باید از پیش مشخص شود (بدون اندازه‌گیری خودکار محتوا)،
    # پس تعداد ردیف را با همان تعداد ستونِ فرضی (یا ۴ پیش‌فرض) تخمین می‌زنیم؛
    # کمی فضای خالی اضافه، بسیار بهتر از بریده‌شدن کارت آخر است.
    rows = -(-len(items) // max(1, columns or 4))
    components.html(html, height=height * max(1, rows), scrolling=False)


class InsightSpec(TypedDict, total=False):
    icon: str            # اموجی یا نویسهٔ آیکن (۴۰px، بالای متن)
    headline: str         # جملهٔ اصلی — ادعای شواهدمحور، نه فقط عنوان
    body: str              # جملهٔ توضیحی زیر عنوان


def _insight_card_html(spec: InsightSpec, index: int) -> str:
    icon = spec.get("icon", "")
    icon_html = f'<div class="ic" aria-hidden="true">{esc(icon)}</div>' if icon else ""
    return f"""
<div class="insight" style="--i:{index}">
  {icon_html}
  <div class="head">{esc(spec.get('headline',''))}</div>
  {f'<div class="body">{esc(spec.get("body",""))}</div>' if spec.get('body') else ''}
</div>"""


def render_insight_row(cards: Iterable[InsightSpec], *, height: int = 150,
                        columns: Optional[int] = None) -> None:
    """کارت «شاهد/بینش» — آیکن + جملهٔ اصلی + جملهٔ توضیحی، همه وسط‌چین.

    این همان الگوی «Stats Card» در صفحهٔ فیگمای ``GSI / Cash Flow /
    Evidence-first`` است (آیکن ۴۰px، پدینگ ۲۴px، فاصلهٔ ۲۴px بین آیکن و
    متن، ۴px بین عنوان و توضیح) — برخلاف :func:`render_kpi_row` که برای
    «سنجهٔ عددی» است، این برای «ادعای شواهدمحور» است (مثلاً «بیشترین
    گلوگاه فرآیند در مرحلهٔ ترخیص گمرکی است»)، نه یک عدد تنها.
    """
    import streamlit.components.v1 as components

    items = list(cards)
    cards_html = "".join(_insight_card_html(c, i) for i, c in enumerate(items))
    col_css = f"repeat({columns}, 1fr)" if columns else "repeat(auto-fit, minmax(280px, 1fr))"
    html = f"""
<div class="wrap">
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:{T.FONT_STACK};direction:rtl}}
  .wrap{{display:grid;grid-template-columns:{col_css};gap:12px}}
  .insight{{
    background:{T.SURFACE_RAISED};border:1px solid {T.BORDER};
    border-radius:{T.RADIUS['lg']}px;box-shadow:{T.SHADOW_CARD};
    padding:{T.SPACE['xl']}px;text-align:center;
    display:flex;flex-direction:column;align-items:center;
    animation:rise .4s cubic-bezier(.22,1,.36,1) both;
    animation-delay:calc(var(--i) * 50ms);
    transition:box-shadow .25s, transform .25s;
  }}
  .insight:hover{{transform:translateY(-2px);box-shadow:{T.SHADOW_CARD_HOVER}}}
  .insight .ic{{font-size:40px;line-height:1;margin-bottom:{T.SPACE['xl']}px;color:{T.BRAND_TEAL}}}
  .insight .head{{font-size:24px;font-weight:800;line-height:1.2;color:{T.INK};
    letter-spacing:-.48px;unicode-bidi:plaintext}}
  .insight .body{{font-size:14px;font-weight:400;line-height:1.4;color:{T.INK_SOFT};
    margin-top:{T.SPACE['2xs']}px;unicode-bidi:plaintext}}
  @keyframes rise{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
  @media (prefers-reduced-motion:reduce){{.insight{{animation:none;transition:none}}}}
</style>
{cards_html}
</div>"""
    rows = -(-len(items) // max(1, columns or 3))
    components.html(html, height=height * max(1, rows), scrolling=False)


class EvidenceColumn(TypedDict, total=False):
    key: str
    label: str


class EvidenceTableSpec(TypedDict, total=False):
    title: str                    # عنوان — مثلاً «رفع تعهد و مانده»
    subtitle: str                   # جملهٔ دانه/گرِین — مثلاً «دانه: کد ثبت سفارش × ارز»
    columns: Sequence[EvidenceColumn]  # ستون‌ها، از راست به چپ همان ترتیب نمایش
    rows: Sequence[Dict[str, object]]    # هر ردیف: دیکشنری key→مقدار (از قبل قالب‌بندی‌شده)
    source_meta: str                      # «منبع: … · نوع شاهد: … · زمان مشاهده: …»
    gap_warning: str                       # جملهٔ بحرانی — شکاف شواهد
    gap_note: str                           # توضیح یک‌خطی که از نبود شاهد نتیجهٔ قطعی گرفته نمی‌شود
    actions: Sequence[str]                    # برچسب پیوندهای اقدام (فقط نمایشی؛ دکمهٔ واقعی در Streamlit است)


def render_evidence_table(spec: EvidenceTableSpec, *, height: int = 420) -> None:
    """جدول «شواهد اول» — عنوان، دانه، جدول واقعی، فراداده منبع، و هشدار شکاف شواهد.

    الگوی دقیق پنل «Settlement / Evidence comparison» در همان صفحهٔ فیگما:
    هر عدد باید منبع، ارز/واحد، و زمان مشاهده داشته باشد؛ نبودِ یک سند
    هرگز به «انجام‌نشدن قطعی» ترجمه نمی‌شود — به همین دلیل ``gap_warning``
    جدا از ``gap_note`` نمایش داده می‌شود: یکی ادعا، دیگری احتیاط در تفسیر.
    """
    import streamlit.components.v1 as components

    columns = list(spec.get("columns", []))
    rows = list(spec.get("rows", []))
    thead = "".join(f'<th>{esc(c.get("label", c.get("key", "")))}</th>' for c in columns)
    tbody = "".join(
        "<tr>" + "".join(f'<td>{esc(r.get(c.get("key", ""), "—"))}</td>' for c in columns) + "</tr>"
        for r in rows
    ) or f'<tr><td colspan="{max(1, len(columns))}" class="empty">داده‌ای برای این برش ثبت نشده</td></tr>'

    gap_html = ""
    if spec.get("gap_warning"):
        gap_html = f'<div class="gap">⚠ {esc(spec["gap_warning"])}</div>'
    note_html = f'<div class="note">{esc(spec["gap_note"])}</div>' if spec.get("gap_note") else ""
    source_html = f'<div class="meta">{esc(spec["source_meta"])}</div>' if spec.get("source_meta") else ""
    actions_html = ""
    if spec.get("actions"):
        links = "".join(f'<span class="action">{esc(a)}</span>' for a in spec["actions"])
        actions_html = f'<div class="actions">{links}</div>'

    html = f"""
<div class="evtable" dir="rtl">
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:{T.FONT_STACK}}}
  .evtable{{background:{T.SURFACE_RAISED};border:1px solid {T.BORDER};
    border-radius:{T.RADIUS['lg']}px;box-shadow:{T.SHADOW_CARD};
    padding:{T.SPACE['xl']}px;display:flex;flex-direction:column;gap:{T.SPACE['lg']}px}}
  .evtable h3{{margin:0;font-size:24px;font-weight:800;color:{T.INK}}}
  .evtable .sub{{font-size:14px;color:{T.INK_MUTED};margin-top:-{T.SPACE['sm']}px}}
  table{{width:100%;border-collapse:collapse;font-size:14px}}
  th{{background:{T.SURFACE_SUNKEN};color:{T.INK_SOFT};font-weight:700;font-size:13px;
    padding:10px 12px;text-align:center;border-bottom:1px solid {T.BORDER}}}
  td{{padding:12px;text-align:center;color:{T.INK};font-weight:600;font-size:15px;
    border-bottom:1px solid {T.BORDER};unicode-bidi:plaintext}}
  td.empty{{color:{T.INK_MUTED};font-weight:400;font-size:12.5px;padding:22px 12px}}
  .meta{{font-size:12.5px;color:{T.INK_MUTED}}}
  .gap{{font-size:15px;font-weight:800;color:{T.STATUS['warning'].ink};
    background:{T.STATUS['warning'].wash};border-radius:{T.RADIUS['sm']}px;
    padding:10px 14px}}
  .note{{font-size:13px;color:{T.INK_SOFT};line-height:1.7}}
  .actions{{display:flex;gap:{T.SPACE['lg']}px}}
  .action{{font-size:14px;font-weight:700;color:{T.BRAND_TEAL};cursor:default}}
</style>
<h3>{esc(spec.get('title',''))}</h3>
{f'<div class="sub">{esc(spec["subtitle"])}</div>' if spec.get('subtitle') else ''}
<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>
{source_html}
{gap_html}
{note_html}
{actions_html}
</div>"""
    components.html(html, height=height, scrolling=True)


def status_badge(status_key: str, *, style: str = "soft") -> str:
    """نشان وضعیت HTML — برای درج داخل ``st.markdown(unsafe_allow_html=True)``."""
    s = T.status_of(status_key)
    solid = style == "solid"
    bg = s.fill if solid else s.wash
    color = "#fff" if solid else s.ink
    return (f'<span style="display:inline-flex;align-items:center;gap:6px;'
            f'background:{bg};color:{color};border-radius:999px;padding:3px 11px;'
            f'font-size:12px;font-weight:700;border:1px solid {s.fill}33">'
            f'<span aria-hidden="true">{esc(s.icon)}</span>{esc(s.label)}</span>')


def legend_html(keys: Optional[List[str]] = None) -> str:
    """راهنمای رنگ وضعیت‌ها — برای پایین نمودارها."""
    keys = keys or [s.key for s in T.STATUS_SCALE]
    chips = "".join(status_badge(k) for k in keys)
    return f'<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">{chips}</div>'
