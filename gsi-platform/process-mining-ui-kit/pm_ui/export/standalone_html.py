# -*- coding: utf-8 -*-
"""Self-contained RTL HTML export for GSI process intelligence.

No JavaScript, no external URLs and no bundled font binary. The CSS asks for
IRANSansWeb first; an organization may install/provide the licensed font in its
own environment. This package intentionally does not redistribute font files.
"""
from __future__ import annotations

__contract__ = 2

import html as _html
from typing import Any, Mapping, Optional, Sequence

from .. import persian as fa
from .. import tokens as T
from ..charts import flowgraph_svg, heatmap_svg, intensity_area_svg, kanban_board_html, system_flow_html
from ..components import evidence_table_html, insight_row_html, kpi_row_html

STANDALONE_FONT_STACK = T.FONT_STACK


def _esc(v: object) -> str:
    return _html.escape("" if v is None else str(v), quote=True)


def _section(title: str, body: str, *, note: Optional[str] = None) -> str:
    note_html = f'<p class="pm-sec-note">{_esc(note)}</p>' if note else ""
    return f'<section class="pm-card"><h2>{_esc(title)}</h2>{note_html}{body}</section>'


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{_esc(v)}</td>" for v in row) + "</tr>" for row in rows)
    if not body:
        body = f'<tr><td colspan="{max(1, len(headers))}" class="pm-empty">داده‌ای برای نمایش مشاهده نشد.</td></tr>'
    return f'<div class="pm-table-wrap"><table class="pm-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _case_status_html(rows: Sequence[Mapping[str, Any]]) -> str:
    return _table(
        ["پرونده", "وضعیت مشاهده‌شده", "مرحله فعلی", "مالک فعلی", "کیفیت شاهد", "اقدام بعدی", "زمان مشاهده"],
        [[r.get("case_key"), r.get("case_state"), r.get("current_activity"), r.get("owner_team"),
          r.get("evidence_quality"), r.get("next_action"), r.get("observed_at")] for r in rows[:100]],
    )


def _routes_html(rows: Sequence[Mapping[str, Any]]) -> str:
    ranked = sorted(rows, key=lambda r: (-int(r.get("unique_cases", 0)), -int(r.get("occurrences", 0))))
    return _table(
        ["مبدأ", "مقصد", "پرونده یکتا", "دفعات عبور", "میانه فاصله رویداد (ساعت)", "صدک ۹۰ (ساعت)"],
        [[r.get("from_activity"), r.get("to_activity"), r.get("unique_cases"), r.get("occurrences"),
          r.get("median_hours"), r.get("p90_hours")] for r in ranked],
    )


def _handoff_html(handoff: Mapping[str, Any]) -> str:
    if handoff.get("status") != "ready":
        return f'<div class="pm-not-computable">قابل محاسبه نیست — {_esc(handoff.get("note", "شاهد کافی وجود ندارد."))}</div>'
    rows = handoff.get("rows", [])
    return _table(
        ["پرونده", "واحد فرستنده", "واحد گیرنده", "مالک فعلی", "ارسال", "پذیرش", "سند پذیرش", "علت برگشت"],
        [[r.get("case_key"), r.get("from_team"), r.get("to_team"), r.get("owner_team"), r.get("sent_at"),
          r.get("accepted_at"), r.get("document_ref"), r.get("return_reason")] for r in rows[:100]],
    )


def _patterns_html(patterns: Mapping[str, Any]) -> str:
    if not patterns.get("enabled"):
        return f'<div class="pm-not-computable">{_esc(patterns.get("note"))}</div>'
    summary = _table(
        ["شناسه الگو", "عنوان", "تعداد تطبیق", "پرونده یکتا"],
        [[r.get("id"), r.get("label"), r.get("match_count"), r.get("unique_cases")]
         for r in patterns.get("summary", [])],
    )
    matches = _table(
        ["الگو", "پرونده", "فعالیت‌های مشاهده‌شده", "ردیف‌های شاهد"],
        [[r.get("pattern_label"), r.get("case_key"), " ← ".join(r.get("activities", [])),
          ", ".join(str(x) for x in r.get("source_rows", []))]
         for r in patterns.get("matches", [])[:100]],
    )
    return summary + '<h3 class="pm-subhead">نمونه تطبیق‌های قابل ردیابی</h3>' + matches


def build_standalone_html(*, title: str, data: Mapping[str, Any], subtitle: str = "",
                          audience_label: str = "") -> str:
    kpis = data.get("kpis", [])
    insights = data.get("insights", [])
    graph = data.get("graph", {"nodes": [], "edges": []})
    evidence = data.get("evidence")
    kanban = data.get("kanban", [])
    system = data.get("system", [])
    intensity = data.get("intensity", {"labels": [], "series": {}})
    heatmap = data.get("heatmap", {"z": [], "x": [], "y": []})
    case_status = data.get("case_status", [])
    route_metrics = data.get("route_metrics", [])
    handoff = data.get("handoff", {})
    patterns = data.get("patterns", {})

    sections = []
    if kpis:
        sections.append(_section("شاخص‌های اصلی", kpi_row_html(kpis),
                                 note="حداکثر چهار شاخص؛ اعداد فقط از دامنه و شاهد فعلی ساخته شده‌اند."))
    if case_status:
        sections.append(_section("۱) وضعیت و اقدام", _case_status_html(case_status),
                                 note="وضعیت، مالک، کیفیت شاهد و اقدام فقط در صورت وجود صریح در منبع نمایش داده می‌شوند؛ مقدار غایب «مشاهده نشده» است."))
    if graph.get("nodes"):
        graph_html = flowgraph_svg(graph["nodes"], graph["edges"], width=980, height=460)
        graph_html += '<h3 class="pm-subhead">جدول مسیرها</h3>' + _routes_html(route_metrics)
        sections.append(_section("۲) مسیر فرآیند", graph_html,
                                 note="پرونده یکتا و دفعات عبور جدا هستند. میانه/P90 فقط فاصله رویدادهای مشاهده‌شده‌اند؛ نه اتلاف یا SLA."))
    sections.append(_section("۳) تحویل بین واحدها", _handoff_html(handoff), note=handoff.get("note")))
    sections.append(_section("مشاهدات الگوی صریح", _patterns_html(patterns),
                             note="الگوها اقتباس مفهومی از constraint/taxonomy matching هستند و به‌تنهایی ریسک، تخلف یا اقدام خودکار محسوب نمی‌شوند."))
    if insights:
        sections.append(_section("شواهد و یافته‌ها", insight_row_html(insights, columns=1)))
    if intensity.get("labels") or heatmap.get("z"):
        charts = []
        if intensity.get("labels"):
            charts.append(f'<div style="flex:1 1 380px">{intensity_area_svg(intensity["labels"], intensity["series"], title="روند حجم کیس")}</div>')
        if heatmap.get("z"):
            charts.append(f'<div style="flex:1 1 320px">{heatmap_svg(heatmap["z"], heatmap["x"], heatmap["y"], title="شدت فعالیت هفتگی")}</div>')
        sections.append(_section("روند و شدت جریان", f'<div style="display:flex;gap:20px;flex-wrap:wrap">{"".join(charts)}</div>'))
    if evidence:
        sections.append(_section("شواهد رویداد", evidence_table_html(evidence)))
    if system:
        sections.append(_section("خط لولهٔ سیستمی", system_flow_html(system)))
    if kanban:
        sections.append(_section("وضعیت کیس‌ها در هر مرحله", kanban_board_html(kanban)))

    sub_line = f'<div class="pm-sub">{_esc(subtitle)}</div>' if subtitle else ""
    audience_line = f'<div class="pm-audience">نمای {_esc(audience_label)}</div>' if audience_label else ""
    return f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>{_esc(title)}</title><style>
*{{box-sizing:border-box}} html{{direction:rtl}} body{{margin:0;background:{T.SURFACE_PAGE};color:{T.INK};font-family:{STANDALONE_FONT_STACK};direction:rtl}}
.pm-wrap{{max-width:{T.CONTAINER_MAX}px;margin:0 auto;padding:28px 24px 60px}}
.pm-header{{background:{T.BRAND_NAVY};color:#fff;border-radius:{T.RADIUS['lg']}px;padding:28px 32px}}
.pm-header h1{{margin:0 0 4px;font-size:32px;font-weight:700;line-height:1.35;letter-spacing:0}}
.pm-sub{{font-size:14px;color:rgba(255,255,255,.82);line-height:1.75}} .pm-audience{{font-size:12px;color:rgba(255,255,255,.65);margin-top:10px}}
.pm-card{{background:{T.SURFACE_RAISED};border:1px solid {T.BORDER};border-radius:{T.RADIUS['lg']}px;box-shadow:{T.SHADOW_CARD};padding:22px 24px;margin-top:20px}}
.pm-card h2{{margin:0 0 14px;font-size:20px;font-weight:700;color:{T.INK};letter-spacing:0}} .pm-subhead{{font-size:15px;margin:22px 0 10px;color:{T.INK}}} .pm-sec-note{{margin:-8px 0 14px;font-size:12.5px;color:{T.INK_MUTED};line-height:1.7}}
.pm-table-wrap{{overflow:auto}} .pm-table{{width:100%;border-collapse:collapse;font-size:12px;line-height:1.65}} .pm-table th{{background:{T.SURFACE_SUNKEN};color:{T.INK};text-align:right;padding:10px;border:1px solid {T.BORDER};white-space:nowrap}} .pm-table td{{padding:9px 10px;border:1px solid {T.BORDER};vertical-align:top}} .pm-empty{{color:{T.INK_MUTED};text-align:center!important}}
.pm-not-computable{{background:{T.GOLD_WASH};border:1px solid {T.GOLD_INK};border-radius:{T.RADIUS['md']}px;padding:14px 16px;color:{T.GOLD_INK};font-size:13px}}
.pm-footer{{margin-top:28px;padding-top:16px;border-top:1px solid {T.BORDER};font-size:11.5px;color:{T.INK_MUTED};line-height:1.8}}
</style></head><body><div class="pm-wrap"><header class="pm-header"><h1>{_esc(title)}</h1>{sub_line}{audience_line}</header>
{''.join(sections)}
<div class="pm-footer">تولید شده در {_esc(fa.today_jalali_str())}. سند آفلاین است و هیچ منبع اینترنتی یا فونت باینری توزیع‌شده ندارد. IRANSansWeb در صورت نصب/تأمین مجاز سازمان در اولویت پشته فونت قرار می‌گیرد.</div>
</div></body></html>"""
