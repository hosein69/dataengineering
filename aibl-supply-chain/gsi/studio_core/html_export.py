# -*- coding: utf-8 -*-
"""خروجی HTML خودبسنده — ساخته‌شده روی سیستم طراحی GSI.

## جریان کاربر (UX Flow)

صفحه به ترتیبی چیده شده که تصمیم‌گیرنده واقعاً می‌خواند، نه به ترتیبی که
داده تولید می‌شود:

    ۱ سربرگ        کجاییم، چه تاریخی، چقدر بحرانی           (زمینه)
    ۲ مسیر تصمیم   سرخط ← وضعیت/گره/اقدام ← یافته‌ها        (چه خبر است)
    ۳ فیلتر        برش بزن                                   (کنترل)
    ۴ سنجه         عدد کلیدی همین برش                        (چقدر)
    ۵ نمودار       شکل مسئله                                 (چرا)
    ۶ فرآیند       کجا کند می‌شود                            (کجا)
    ۷ جدول         ردیف‌ها، برای پیگیری                       (چه کسی/کدام)

هر لایه پاسخ یک سؤال است و تا سؤال قبلی جواب نگیرد، لایه بعد معنا ندارد.

## معماری این فایل پس از بازطراحی

نشانه‌گذاری، شیوه‌نامه و نمودارها هرکدام یک منبع دارند:

    gsi/design/tokens.py      رنگ، فاصله، تایپ، حرکت، نقاط شکست
    gsi/design/css.py         Auto Layout، Responsive، دسترس‌پذیری، چاپ
    gsi/design/components.py  کامپوننت‌ها و واریانت‌ها
    gsi/design/charts_js.py   نشانه‌های SVG داخل مرورگر

پیش از این، نسخه‌ای از این فایل **دو پیاده‌سازی رقیب** از یک runtime داشت و
هر دو emit می‌شدند؛ مرورگر با ``Identifier 'S' has already been declared``
کل بلوک دوم را رها می‌کرد و گزارش خالی بالا می‌آمد. حالا فقط یک بلوک
اجرایی وجود دارد و تست رگرسیون JS را در **scope مشترک** می‌سنجد.

## قاعده‌های تغییرناپذیر

* جمع‌ها **دانه‌ای** هستند: کلید دانه هر ستون به JS می‌رود و پیش از تجمیع
  یکتاسازی می‌شود، وگرنه فیلتر کردن «جمع مانده تعهد» را چند برابر می‌کند.
* هیچ منبع بیرونی بارگذاری نمی‌شود — گزارش از داخل Outlook و شبکه اداری
  باز می‌شود.
* رنگ هرگز تنها حامل معنا نیست؛ هر وضعیت آیکن و برچسب دارد.
"""
from __future__ import annotations

__contract__ = 3

import html
import json
from typing import Dict, List, Optional

import pandas as pd

from ..design import charts_js as CJ
from ..design import components as C
from ..design import css as CSS
from .. import audience as AUD
from .. import voice as V
from ..design import tokens as T
from .grain import (GRAIN_KEYS, KIND_ADDITIVE, KIND_RATIO, column_grain,
                    measure_kind, prefix_grain_map, safe_agg)

#: پالت وضعیت — از سیستم طراحی. ساختار قدیمی (رنگ، آیکن) حفظ شده تا
#: مصرف‌کننده‌های موجود تغییری نبینند.
BANDS: Dict[str, tuple] = {s.label: (s.fill, s.icon) for s in T.STATUS_SCALE}
BAND_INK: Dict[str, str] = {s.label: s.ink for s in T.STATUS_SCALE}
BAND_ORDER: List[str] = list(BANDS)

BRAND, BRAND_DEEP = T.BRAND_TEAL, T.BRAND_NAVY
SURFACE, RAISED, BORDER = T.SURFACE_PAGE, T.SURFACE_RAISED, T.BORDER
TEXT, TEXT2, TEXT3 = T.TEXT, T.TEXT_SECONDARY, T.TEXT_MUTED

#: مراحل زنجیره تأمین — لنگر ذهنی «الان کجای مسیریم».
SUPPLY_FLOW = ("تأمین قطعه", "ثبت سفارش و ارز", "حمل بین‌الملل",
               "گمرک و ترخیص", "ورود قطعه", "پشتیبانی تولید")


def _measure_cols(df: pd.DataFrame, cols: List[str]) -> Dict[str, str]:
    """{ستون عددی: تجمیع بامعنا}.

    شناسه‌ها (شماره سفارش، کد متریال) کنار گذاشته می‌شوند — جمع زدنشان
    بی‌معناست. ستون نسبتی (مقاومت، درصد، امتیاز) میانگین می‌گیرد، نه جمع.
    """
    out: Dict[str, str] = {}
    for c in cols:
        if c not in df.columns:
            continue
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        if not (s.notna().mean() > 0.5 and s.notna().any()):
            continue
        kind = measure_kind(c, df[c])
        if kind == KIND_ADDITIVE:
            out[c] = "sum"
        elif kind == KIND_RATIO:
            out[c] = "mean"
    return out


def build_dynamic_html(df: pd.DataFrame, ref_date: str, title: str = "GSI",
                       max_rows: int = 2500, selected_fields=None,
                       labels: Optional[Dict[str, str]] = None,
                       template_title: str = "", subtitle: str = "",
                       show_visuals: bool = True, tabs: Optional[List[Dict]] = None,
                       charts: Optional[List[str]] = None,
                       process_extras: Optional[Dict] = None,
                       audience: Optional[str] = None) -> str:
    """HTML خودبسنده با تب‌های واقعی، فیلتر زنده و نمای مخاطب‌محور.

    ``audience`` تعیین می‌کند این فایل برای چه کسی ساخته شود. سه نمای
    عملیاتی (کارشناس / مدیر میانی / مدیر ارشد) درون **یک** فایل‌اند و
    خواننده با یک کلیک بینشان جابه‌جا می‌شود؛ چون در عمل، مدیری که عدد
    عجیبی می‌بیند می‌خواهد همان‌جا به ردیف‌ها برسد، و کارشناسی که کارش
    تمام شد می‌خواهد ببیند تصویر کلی چه شد.

    اما نمای **تحلیل‌گر** — کیفیت داده، پوشش، انطباق — فقط وقتی داخل فایل
    می‌رود که صریحاً خواسته شود. دلیلش پنهان‌کاری نیست: این اعداد برای کسی
    مفیدند که می‌تواند دربارهٔ آنها کاری بکند، و برای بقیه فقط اعتماد را
    بی‌دلیل خرد می‌کنند. جایشان داشبورد Streamlit و شیت «سلامت سیستم» است.
    """
    aud = AUD.get(audience)
    default_cols = ["KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_REG",
                    "CANONICAL_EXPERT", "ORG_DEPT", "TRANSPORT_MODE",
                    "بحرانی (کوتاه)", "مقاومت (روز)"]
    requested = list(selected_fields or default_cols)
    labels = labels or {}
    raw_tabs = tabs or [{"title": "گزارش", "fields": requested, "max_rows": max_rows}]
    norm_tabs = []
    for i, tab in enumerate(raw_tabs):
        title_i = str(tab.get("title") or f"تب {i+1}")
        fields_i = [c for c in tab.get("fields", requested) if c in df.columns]
        if not fields_i:
            fields_i = [c for c in requested if c in df.columns] or list(df.columns[:12])
        norm_tabs.append({"id": f"pane_{i}", "title": title_i, "fields": fields_i,
                          "max_rows": int(tab.get("max_rows") or max_rows),
                          "chart": str(tab.get("chart") or "")})

    pm = prefix_grain_map()
    band_col = "بحرانی (کوتاه)" if "بحرانی (کوتاه)" in df.columns else None
    all_needed: List[str] = []
    for tab in norm_tabs:
        for c in tab["fields"]:
            if c not in all_needed:
                all_needed.append(c)
    for k in GRAIN_KEYS.values():
        if k in df.columns and k not in all_needed:
            all_needed.append(k)
    if band_col and band_col not in all_needed:
        all_needed.append(band_col)
    # وابستگی نمودارها hidden وارد payload می‌شود: نمودار presentation است و
    # نباید کاربر را مجبور کند فیلد پشتیبان را به جدول اضافه کند.
    for c in ("روزهای رسوب", "مقاومت (روز)", "مانده تعهد", "روزهای تأخیر",
              "مقاومت انبار (روز)", "STAGE_FA", "ORDER_STAGE_FA", "CASE_KEY"):
        if c in df.columns and c not in all_needed:
            all_needed.append(c)

    cap = max(t["max_rows"] for t in norm_tabs)
    data = df[all_needed].head(cap).copy()
    for c in data.columns:
        if pd.api.types.is_datetime64_any_dtype(data[c]):
            data[c] = data[c].dt.strftime("%Y-%m-%d")
    data = data.fillna("")
    records = json.dumps(data.to_dict(orient="records"), ensure_ascii=False,
                         default=str).replace("</", "<" + "\\/")

    def tab_meta(tab):
        cols = tab["fields"]
        measures = _measure_cols(df, cols)
        grain_of = {c: (GRAIN_KEYS.get(column_grain(c, pm)) or "") for c in cols}
        filters = []
        for c in cols:
            vals = sorted({str(x) for x in data[c].tolist() if str(x).strip()})
            if 1 < len(vals) <= 40:
                filters.append((c, labels.get(c, c), vals))
            if len(filters) >= 5:
                break
        return measures, grain_of, filters

    # ── ۱) سربرگ ──
    stats = []
    if band_col:
        vc = df[band_col].astype(str).value_counts()
        for b in ("توقف خط", "بحرانی"):
            n = int(vc.get(b, 0))
            if n:
                stats.append((b, f"{n:,}"))
    actions = C.button("چاپ / ذخیره PDF", variant="secondary", icon="🖨",
                       onclick="window.print()")
    header = C.app_bar(
        title,
        eyebrow="GSI · GLOBAL SOURCING INTELLIGENCE · DATA • PROCESS • DECISION",
        subtitle=(f"{template_title}{' · ' if template_title else ''}"
                  f"تاریخ مرجع {V.fa_digits(ref_date)}{' · ' + subtitle if subtitle else ''}"),
        stats=stats, actions=actions)

    legend_html = C.legend(T.STATUS_SCALE)
    flow_html = C.flow(SUPPLY_FLOW)

    # ── نوار انتخاب مخاطب ──
    # سه نمای عملیاتی همیشه هستند؛ نمای تحلیل‌گر فقط اگر همین فایل برای او
    # ساخته شده باشد. یعنی مدیری که این فایل را باز می‌کند، اصلاً گزینه‌ای
    # به نام «کیفیت داده» نمی‌بیند — نه اینکه ببیند و برایش قفل باشد.
    shown = [k for k in AUD.ORDER
             if k != AUD.ANALYST or aud.key == AUD.ANALYST]
    persona_html = (
        '<div class="cluster cluster-xs no-print" role="group" '
        'aria-label="نمای گزارش برای">'
        '<span class="t-overline" style="align-self:center">این گزارش را ببین به‌عنوان</span>'
        + "".join(
            f'<button type="button" class="chip persona" data-aud="{k}" '
            f'aria-pressed="{str(k == aud.key).lower()}" '
            f'title="{html.escape(AUD.PROFILES[k].who)}">'
            f'{html.escape(AUD.PROFILES[k].fa)}</button>' for k in shown)
        + '</div>')

    aud_json = json.dumps({
        k: {"fa": p.fa, "question": p.question, "sections": list(p.sections),
            "max_findings": p.max_findings, "table_rows": p.table_rows,
            "depth": p.narrative_depth, "charts": list(p.charts),
            "quality": p.show_data_quality, "provenance": p.show_provenance,
            "closing": p.closing}
        for k, p in AUD.PROFILES.items() if k in shown},
        ensure_ascii=False)

    buttons = "".join(
        f'<button class="tabbtn" type="button" role="tab" id="tab_{i}" '
        f'aria-selected="{str(i == 0).lower()}" aria-controls="{t["id"]}" '
        f'data-pane="{t["id"]}">{html.escape(t["title"])}</button>'
        for i, t in enumerate(norm_tabs))

    # ── پنل‌های تب ──
    panes, metas = [], []
    for i, tab in enumerate(norm_tabs):
        cols = tab["fields"]
        measures, grain_of, filters = tab_meta(tab)
        head = "".join(f'<th scope="col">{html.escape(labels.get(c, c))}</th>'
                       for c in cols)
        fhtml = "".join(
            f'<label for="f_{i}_{j}">{html.escape(lab)}'
            f'<select id="f_{i}_{j}" data-f="{html.escape(c)}" data-pane="{tab["id"]}">'
            f'<option value="">همه</option>'
            + "".join(f"<option>{html.escape(v)}</option>" for v in vals)
            + "</select></label>"
            for j, (c, lab, vals) in enumerate(filters))
        toolbar = (f'<div class="toolbar cluster cluster-sm no-print">{fhtml}'
                   f'<div class="cluster cluster-xs hug">'
                   + C.button("استخراج Excel این برش", variant="secondary", icon="⬇",
                              onclick="downloadFilteredXlsx()", attrs='data-role="export"')
                   + "</div></div>") if fhtml else ""
        hidden = ' hidden' if i else ""
        table = C.panel(
            f'<div class="tablewrap"><table><caption class="sr-only">'
            f'{html.escape(tab["title"])}</caption><thead><tr>{head}</tr></thead>'
            f'<tbody id="tb_{i}"></tbody></table></div>'
            f'<div class="pager no-print" id="pager_{i}"></div>',
            title=tab["title"],
            aside=f'<span class="note" id="cnt_{i}" role="status" aria-live="polite"></span>',
            section="table")
        panes.append(
            f'<section id="{tab["id"]}" class="pane stack stack-md" role="tabpanel" '
            f'aria-labelledby="tab_{i}"{hidden}>'
            f'{toolbar}'
            f'<div class="grid-auto" style="--col:190px" id="cards_{i}"></div>'
            f'<div class="grid-auto" style="--col:370px" id="charts_{i}"></div>'
            f'{table}</section>')
        metas.append({"id": tab["id"], "fields": cols, "max_rows": tab["max_rows"],
                      "grain": grain_of, "agg": measures, "title": tab["title"]})

    # ── نمودارها و لاگ فرآیند ──
    chart_keys = list(charts or []) if show_visuals else []
    try:
        from .designs import CHART_QUESTIONS, EMAIL_CHARTS
        chart_labels = {k: EMAIL_CHARTS.get(k, k) for k in chart_keys}
        chart_questions = {k: CHART_QUESTIONS.get(k, "") for k in chart_keys}
    except Exception:
        chart_labels = {k: k for k in chart_keys}
        chart_questions = {k: "" for k in chart_keys}
    proc_payload = {}
    for key in ("bottlenecks", "variants", "conformance_root_causes",
                "conformance_cases", "case_table", "case_actions",
                "fx_ledger", "fx_control_summary", "fx_stage_timeline",
                "fx_rate_bridge", "fx_reallocations", "fx_anomalies",
                "supply_position", "warehouse_declaration"):
        t = (process_extras or {}).get(key)
        if isinstance(t, pd.DataFrame) and not t.empty:
            x = t.copy()
            for c in x.columns:
                if pd.api.types.is_datetime64_any_dtype(x[c]):
                    x[c] = x[c].dt.strftime("%Y-%m-%d %H:%M:%S")
            proc_payload[key] = x.fillna("").to_dict(orient="records")

    chart_json = json.dumps({"keys": chart_keys, "labels": chart_labels,
                             "questions": chart_questions}, ensure_ascii=False)
    proc_json = json.dumps(proc_payload, ensure_ascii=False, default=str)
    series_json = json.dumps(list(T.CATEGORICAL), ensure_ascii=False)
    band_fill_json = json.dumps({s.label: s.fill for s in T.STATUS_SCALE},
                                ensure_ascii=False)
    band_ink_json = json.dumps(BAND_INK, ensure_ascii=False)

    story_panel = (
        '<section id="story" class="story reveal" data-section="story" aria-labelledby="story_h">'
        '<div class="t-overline" style="color:var(--gold-ink)">◈ مسیر تصمیم</div>'
        '<h2 class="t-h2" id="story_h" style="margin:4px 0 12px"></h2>'
        '<p class="note" id="story_q"></p>'
        '<div class="grid-auto" style="--col:250px" id="story_scr"></div>'
        '<div class="grid-auto" style="--col:272px" id="story_findings" '
        'style="margin-top:12px"></div></section>')

    process_panel = C.panel(
        '<div id="process_kpis" class="grid-auto" style="--col:180px"></div>'
        '<div id="process_map"></div><div id="process_bottlenecks"></div>'
        '<div id="process_variants" data-section="variants"></div>'
        '<div id="process_roots" data-section="factors"></div>'
        '<div id="process_fx" data-section="fx"></div>'
        '<div id="process_wh" data-section="warehouse"></div>'
        '<div class="cluster cluster-xs no-print" style="margin-top:14px">'
        + C.button("استخراج Excel این برش", variant="secondary", icon="⬇",
                   onclick="downloadFilteredXlsx()")
        + C.button("چاپ / PDF", variant="ghost", icon="🖨", onclick="window.print()")
        + "</div>",
        title="⛓ Process Explorer — روایت فرآیند",
        note=("ابتدا ببینید فرآیند کجا کند می‌شود؛ سپس واریانت و ریشه انحراف را "
              "بررسی کنید. این نما از Event Log همین اجرا ساخته شده است."),
        pid="process", section="process")

    runtime = _runtime(chart_json, proc_json, series_json, band_fill_json, band_ink_json)

    return f"""<!doctype html><html lang="fa" dir="rtl"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>{html.escape(title)}</title>
<style>{CSS.stylesheet()}</style>
</head><body>
{C.skip_link()}
<div class="shell stack stack-md">
{header}
{persona_html}
<div class="cluster cluster-sm">{flow_html}</div>
{legend_html}
<nav class="tabbar no-print" role="tablist" aria-label="تب‌های گزارش">{buttons}</nav>
<div class="toolbar split no-print">
  <label for="q" class="grow" style="max-width:460px">جستجوی سراسری تب فعال
    <input id="q" type="search" placeholder="جستجو در فیلدهای همان تب"
           aria-describedby="q_hint"></label>
  <span id="q_hint" class="sr-only">نتیجه بلافاصله روی سنجه‌ها، نمودارها و جدول اعمال می‌شود.</span>
  {C.button("استخراج Excel این برش", variant="decision", icon="⬇", onclick="downloadFilteredXlsx()")}
</div>
<main id="main" class="stack stack-md">
{story_panel}
{process_panel}
{''.join(panes)}
</main>
<footer class="note" style="padding:8px 0 0">
<span id="aud_closing"></span>
GSI · Global Sourcing Intelligence — این سند خودبسنده است و هیچ منبع بیرونی بارگذاری نمی‌کند.
</footer>
</div>
<script>
const DATA={records};
const TAB_META={json.dumps(metas, ensure_ascii=False)};
const LABELS={json.dumps({c: labels.get(c, c) for c in all_needed}, ensure_ascii=False)};
const AUDIENCES={aud_json};
let AUD={json.dumps(aud.key, ensure_ascii=False)};
</script>
{runtime}
</body></html>"""


def _runtime(chart_json: str, proc_json: str, series_json: str,
             band_fill_json: str, band_ink_json: str) -> str:
    """تنها بلوک اجرایی صفحه.

    همه توابع اینجا یک‌بار تعریف می‌شوند. هر تعریف دوباره در scope سراسری،
    مرورگر را با ``Identifier ... has already been declared`` متوقف می‌کند و
    گزارش را خالی بالا می‌آورد؛ تست ۲۱ دقیقاً همین را می‌سنجد.
    """
    charts_lib = CJ.chart_runtime(series_json, band_fill_json, band_ink_json)
    body = r"""
const CHART_CFG=__CHART_CFG__; const PROC=__PROC__;
__CHARTS_LIB__
__REVEAL_JS__

let active=0;
const PAGE={};
/* اندازه صفحه از پروفایل مخاطب می‌آید: مدیر ارشد ۱۰ ردیف
   می‌بیند و کارشناس ۲۰۰ — همان جدول، دو نیاز متفاوت. */
function pageSize(){return audCfg().table_rows||100}
const q=document.getElementById('q');
function S(r,c){return String(r?.[c]??'')}
function N(r,c){const v=parseFloat(S(r,c));return Number.isFinite(v)?v:null}

/* ── فیلتر: تنها نقطه‌ای که «برش فعال» تعریف می‌شود ── */
function rows(t){
 let a=DATA;
 const n=(q&&q.value?q.value:'').trim().toLowerCase();
 if(n)a=a.filter(r=>t.fields.some(c=>S(r,c).toLowerCase().includes(n)));
 document.querySelectorAll('select[data-pane="'+t.id+'"]').forEach(s=>{
  if(s.value)a=a.filter(r=>S(r,s.dataset.f)===s.value)});
 return a.slice(0,t.max_rows)}

/* ── تجمیع دانه‌ای: بدون این، فیلتر کردن جمع‌ها را چند برابر می‌کند ── */
function gvals(a,c,grain){const k=grain[c],seen=new Set(),out=[];
 for(const r of a){if(k){const key=S(r,k).trim();if(key){if(seen.has(key))continue;seen.add(key)}}
 const v=parseFloat(S(r,c));if(Number.isFinite(v))out.push(v)}return out}
function gagg(a,c,grain,agg){const v=gvals(a,c,grain);if(!v.length)return 0;
 if(agg[c]==='mean')return v.reduce((s,x)=>s+x,0)/v.length;
 return v.reduce((s,x)=>s+x,0)}

function countBy(a,fields){const m={};a.forEach(r=>{let v='';
 for(const f of fields){v=S(r,f).trim();if(v)break}v=v||'نامشخص';m[v]=(m[v]||0)+1});
 return Object.entries(m).map(([k,v])=>({k,v}))}
function topCount(a,fields){return countBy(a,fields).sort((x,y)=>y.v-x.v).slice(0,12)}
function bandRows(a,fields){return countBy(a,fields).map(x=>({k:x.k,v:x.v,
 c:GSI_BAND_FILL[x.k]||null,ink:GSI_BAND_INK[x.k]||null}))}
function sumUnique(a,valCol,keyFields){const seen=new Set();let sum=0;
 for(const r of a){let key='';for(const f of keyFields){key=S(r,f).trim();if(key)break}
 if(key){if(seen.has(key))continue;seen.add(key)}
 const v=parseFloat(S(r,valCol));if(Number.isFinite(v))sum+=v}return sum}
function stageRows(a){return topCount(a,['STAGE_FA','ORDER_STAGE_FA','LIFECYCLE_STAGE'])}

/* ── انتخاب نمودار ── */
function chartFor(k,a,i){
 const title=CHART_CFG.labels[k]||k,o={q:(CHART_CFG.questions||{})[k]||'',i:i};
 if(k==='low_resistance')return barChart(a.map(r=>({k:S(r,'KEY_MATERIAL'),
   v:parseFloat(S(r,'مقاومت (روز)'))})),title,Object.assign({fill:'var(--st-critical)',
   ink:'var(--st-critical-ink)'},o));
 if(k==='criticality')return donutChart(bandRows(a,['بحرانی (کوتاه)','کد طبقه بحرانی']),title,o);
 if(k==='risk_mix')return donutChart(countBy(a,['طبقه ریسک']),title,o);
 if(k==='org_workload')return barChart(topCount(a,['ORG_DEPT','ORG_VICE']),title,o);
 if(k==='expert_workload')return barChart(topCount(a,['CANONICAL_EXPERT']),title,o);
 if(k==='transport_mix')return donutChart(countBy(a,['TRANSPORT_MODE']),title,o);
 if(k==='stage_distribution')return barChart(stageRows(a),title,o);
 if(k==='top_orders')return barChart(topCount(a,['CANONICAL_ORDER','KEY_ORDER']),title,o);
 if(k==='top_bl')return barChart(topCount(a,['CANONICAL_BL','KEY_BL']),title,o);
 if(k==='supplier_mix')return barChart(topCount(a,['SUPPLIER','VENDOR_CODE']),title,o);
 if(k==='sediment_vs_resistance'||k==='stock_vs_total'){
  const pts=[];for(const r of a){const x=N(r,'روزهای رسوب'),y=N(r,'مقاومت (روز)');
   if(x===null||y===null)continue;pts.push({x,y,k:S(r,'KEY_MATERIAL'),b:S(r,'بحرانی (کوتاه)')})}
  return scatterChart(pts,title,Object.assign({xlabel:'روزهای رسوب',ylabel:'مقاومت (روز)',
   quad:'رسوب بالا و مقاومت بالا'},o))}
 if(k==='delay_vs_commitment'){
  const pts=[];for(const r of a){const x=N(r,'روزهای تأخیر'),y=N(r,'مانده تعهد');
   if(x===null||y===null)continue;pts.push({x,y,k:S(r,'CANONICAL_ORDER'),b:S(r,'بحرانی (کوتاه)')})}
  return scatterChart(pts,title,Object.assign({xlabel:'روزهای تأخیر',ylabel:'مانده تعهد',
   quad:'تأخیر و مبلغ، هر دو بالا'},o))}
 if(k==='pareto_delay'){const m={};for(const r of a){const d=N(r,'روزهای تأخیر');
   if(d===null||d<=0)continue;const key=S(r,'CANONICAL_ORDER').trim()||S(r,'KEY_REG').trim();
   if(!key)continue;m[key]=Math.max(m[key]||0,d)}
  return paretoChart(Object.entries(m).map(([k2,v])=>({k:k2,v})),title,o)}
 if(k==='commitment'){
  const over=a.filter(r=>(parseFloat(S(r,'روزهای تأخیر'))||0)>0);
  const open=a.filter(r=>(parseFloat(S(r,'روزهای تأخیر'))||0)<=0&&(parseFloat(S(r,'مانده تعهد'))||0)>0);
  const done=a.filter(r=>(parseFloat(S(r,'مانده تعهد'))||0)<=0);
  return barChart([
   {k:'معوق',v:sumUnique(over,'مانده تعهد',['KEY_REG','CANONICAL_ORDER']),
    c:'var(--st-critical)',ink:'var(--st-critical-ink)'},
   {k:'در مهلت',v:sumUnique(open,'مانده تعهد',['KEY_REG','CANONICAL_ORDER']),
    c:'var(--st-warning)',ink:'var(--st-warning-ink)'},
   {k:'تسویه‌شده',v:sumUnique(done,'مانده تعهد',['KEY_REG','CANONICAL_ORDER']),
    c:'var(--st-good)',ink:'var(--st-good-ink)'}],title,o)}
 if(k==='overdue_bucket'){const bins={'بدون تأخیر':0,'۱ تا ۷ روز':0,'۸ تا ۳۰ روز':0,
   '۳۱ تا ۶۰ روز':0,'بیش از ۶۰ روز':0};
  a.forEach(r=>{const d=parseFloat(S(r,'روزهای تأخیر'));
   if(!Number.isFinite(d)||d<=0)bins['بدون تأخیر']++;else if(d<=7)bins['۱ تا ۷ روز']++;
   else if(d<=30)bins['۸ تا ۳۰ روز']++;else if(d<=60)bins['۳۱ تا ۶۰ روز']++;
   else bins['بیش از ۶۰ روز']++});
  return barChart(Object.entries(bins).map(([k2,v])=>({k:k2,v})),title,o)}
 if(k==='bottlenecks'){const b=PROC.bottlenecks||[];
  if(b.length)return barChart(b.slice(0,10).map(x=>({k:S(x,'از فعالیت')+' ← '+S(x,'به فعالیت'),
   v:+x['میانه روز']||0})),title,Object.assign({fill:'var(--st-serious)',
   ink:'var(--st-serious-ink)'},o));
  return barChart(stageRows(a),title+' — جایگزین: توزیع مرحله فعلی',o)}
 return frame(title,emptyBox('فیلد لازم برای این نمودار در برش فعلی وجود ندارد.'),'','',i)}

/* نمودار هم مخاطب دارد: مدیر ارشد یک نمودار می‌بیند و تحلیل‌گر شش تا.
   نمودارِ بی‌ربط، بی‌ضرر نیست — جای نمودار مربوط را می‌گیرد و خواننده را
   وامی‌دارد خودش فیلتر کند. اگر پروفایل نموداری نخواسته، هیچ‌کدام از
   نمودارهای موجود حذف نمی‌شود؛ فقط همان‌هایی می‌مانند که خواسته شده‌اند. */
function chartsFor(){
 const want=audCfg().charts||[],have=CHART_CFG.keys||[];
 const pick=have.filter(k=>want.includes(k));
 return pick.length?pick:have;
}
function renderCharts(i,a){const e=document.getElementById('charts_'+i);
 if(!e)return;e.innerHTML=chartsFor().map((k,j)=>chartFor(k,a,j)).join('');
 gsiReveal(e)}

/* ── Process Explorer ── */
function renderProcess(a){
 const cfg=audCfg();
 const b=PROC.bottlenecks||[],v=PROC.variants||[],rc=PROC.conformance_root_causes||[];
 const q=PROC.stage_queue||[];

 /* صداقت دامنه: این جدول‌ها روی **کل** داده محاسبه شده‌اند، نه روی برش
    فیلترشده. محاسبه دوبارهٔ فرآیند در مرورگر یعنی دو منطق موازی که با هم
    فرق می‌کنند. پس به‌جای تظاهر، دامنه صریح اعلام می‌شود. */
 const scoped=(a.length&&DATA.length&&a.length<DATA.length)
  ?'<span class="badge badge--quiet" data-tone="neutral">کل سازمان — مستقل از فیلتر فعلی</span>':'';

 /* صف جاری: چیزی که جدول گذار هرگز نشان نمی‌داد.
    گذار وقتی ثبت می‌شود که پرونده از مرحله خارج شده باشد؛ پرونده‌ای که
    هشت ماه گیر کرده و خارج نشده، در آن جدول هیچ ردیفی ندارد. */
 const map=document.getElementById('process_map');
 if(map){map.innerHTML=q.length?(barChart(q.slice(0,10).map(x=>({
   k:S(x,'مرحله جاری'),v:+x['تعداد پرونده']||0})),
   'صف جاری — چند پرونده در هر مرحله منتظرند',
   {q:'الان کجا پرونده جمع شده است؟'})+scoped)
  :(b.length?barChart(b.slice(0,10).map(x=>({
    k:S(x,'از فعالیت')+' ← '+S(x,'به فعالیت'),v:+x['میانه روز']||0})),
    'گذارهای مشاهده‌شده — میانه انتظار',{q:'کدام گذار بیشترین زمان را می‌خورد؟'})+scoped
   :(stageRows(a).length?barChart(stageRows(a),'توزیع مرحله فعلی',
    {q:'پرونده‌ها اکنون در کدام مرحله‌اند؟'})
    :emptyBox('لاگ تاریخی برای اندازه‌گیری هنوز کافی نیست. با اجرای روزانه، Transition Log ساخته می‌شود.')));
  gsiReveal(map)}

 const t=document.getElementById('process_bottlenecks');
 if(t){
  let html_='';
  if(q.length)html_+='<div class="tablewrap" style="margin-top:12px"><table>'
   +'<caption class="note">صف جاری: پرونده‌هایی که همین حالا در هر مرحله منتظرند. '
   +'«انتظار» زمان سپری‌شده از آخرین رویداد است، نه زمان کار.</caption>'
   +'<thead><tr><th scope="col">مرحله جاری</th><th scope="col">پرونده منتظر</th>'
   +'<th scope="col">میانه انتظار</th><th scope="col">بیشترین انتظار</th></tr></thead><tbody>'
   +q.slice(0,10).map(x=>'<tr><td>'+esc2(S(x,'مرحله جاری'))+'</td><td class="num">'
    +fmt(x['تعداد پرونده'])+'</td><td class="num">'+fmt(x['میانه انتظار (روز)'])
    +' روز</td><td class="num">'+fmt(x['بیشترین انتظار (روز)'])+' روز</td></tr>').join('')
   +'</tbody></table></div>';
  if(b.length&&cfg.depth>1)html_+='<div class="tablewrap" style="margin-top:12px"><table>'
   +'<caption class="note">گذارهای کامل‌شده. میانه و صدک ۹۰ گزارش می‌شوند چون '
   +'توزیع دُم‌دار است و میانگین با یک پرونده طولانی جابه‌جا می‌شود.</caption>'
   +'<thead><tr><th scope="col">از</th><th scope="col">به</th>'
   +'<th scope="col">میانه</th><th scope="col">صدک ۹۰</th>'
   +'<th scope="col">پرونده</th></tr></thead><tbody>'
   +b.slice(0,10).map(x=>'<tr><td>'+esc2(S(x,'از فعالیت'))+'</td><td>'+esc2(S(x,'به فعالیت'))
    +'</td><td class="num">'+fmt(x['میانه روز'])+' روز</td><td class="num">'
    +fmt(x['صدک ۹۰ روز'])+' روز</td><td class="num">'+fmt(x['تعداد پرونده'])
    +'</td></tr>').join('')+'</tbody></table></div>';
  t.innerHTML=html_||'<p class="note">تا زمانی که Event Log کافی شود، توزیع مرحله فعلی '
   +'به‌عنوان نمای جایگزین نمایش داده می‌شود و هیچ گلوگاه فرضی ساخته نمی‌شود.</p>';
 }

 const pv=document.getElementById('process_variants');
 if(pv)pv.innerHTML=(v.length&&cfg.sections.includes('variants'))?(
  '<h4 class="t-h4" style="margin-top:16px">مسیرهای مشاهده‌شده</h4>'
  /* نسخه قبلی اینجا می‌نوشت «سهم کم یعنی فرآیند هر بار از نو اجرا می‌شود».
     تنوع مسیر سه علت کاملاً متفاوت دارد و این جمله یکی را قطعی می‌گرفت. */
  +'<p class="note">تنوع مسیر به‌تنهایی خوب یا بد نیست: می‌تواند از تفاوت مشروع '
  +'خریدها (هوایی/دریایی، برات/دیداری)، از نقص داده، یا از بی‌انضباطی بیاید. '
  +'ستون «پرونده بسته» می‌گوید میانه بر چند نمونه بنا شده است.</p>'
  +'<div class="tablewrap"><table><thead><tr><th scope="col">مسیر</th>'
  +'<th scope="col">پرونده</th><th scope="col">سهم</th>'
  +'<th scope="col">پرونده بسته</th><th scope="col">میانه چرخه</th></tr></thead><tbody>'
  +v.slice(0,12).map(x=>'<tr><td style="white-space:normal;max-width:520px">'+esc2(S(x,'VARIANT'))
  +'</td><td class="num">'+fmt(x['تعداد پرونده'])+'</td><td class="num">'+fmt(x['سهم (٪)'])
  +'٪</td><td class="num">'+fmt(x['پرونده بسته'])+'</td><td class="num">'
  +(((+x['پرونده بسته']||0)>0)?(fmt(x['میانه چرخه'])+' روز'):'—')+'</td></tr>').join('')
  +'</tbody></table></div>'):'';

 const pr=document.getElementById('process_roots');
 /* «علت ریشه‌ای» نبود، همبستگی بود. نام و متن هر دو اصلاح شده‌اند. */
 if(pr)pr.innerHTML=(rc.length&&cfg.depth>2)?(
  '<h4 class="t-h4" style="margin-top:16px">عوامل همراه با انحراف — نیازمند بررسی</h4>'
  +'<p class="note">این نمودار همبستگی نشان می‌دهد، نه علت. گروهی که پرونده‌های '
  +'دشوارتری به آن سپرده شده هم اینجا بالا می‌آید؛ پیش از هر اقدامی، ترکیب '
  +'پرونده‌های گروه بررسی شود.</p>'
  +barChart(rc.slice(0,8).map(x=>({k:S(x,'بُعد')+': '+S(x,'مقدار'),
    v:+x['اثر تفاضلی (واحد درصد)']||0})),
   'اختلاف نرخ انحراف نسبت به پایه (واحد درصد)',
   {q:'کدام گروه‌ها نرخ انحراف بالاتری دارند؟'})):'';
 renderFx();
 renderWarehouse();
}

/* ── اظهار انبار / سامانه جامع انبارها ──
   آخرین حلقه زنجیره شاهد: کالا ترخیص شد، ولی به انبار رسید؟
   عمداً «تخلف» نمی‌گوید — مهلت قانونی needs_verification است. */
function renderWarehouse(){
 const el=document.getElementById('process_wh');if(!el)return;
 const wh=PROC.warehouse_declaration||[];
 if(!wh.length){el.innerHTML='';return}
 const by=k=>wh.filter(x=>S(x,'WH_STATUS')===k).length;
 const gap=by('OVERDUE')+by('CRITICAL_GAP');
 const cards=[['اظهار شده',by('DECLARED'),'good'],['اظهار با تأخیر',by('LATE'),'warning'],
  ['شکاف شاهد انبار',gap,'serious'],['شکاف کهنه',by('CRITICAL_GAP'),'critical'],
  ['تناقض ترتیب تاریخ',by('SEQUENCE_CONFLICT'),'warning'],
  ['در مهلت پایش',by('PENDING'),''],['هنوز ترخیص نشده',by('NOT_CLEARED'),'']]
  .map((x,i)=>'<div class="kpi reveal" style="--i:'+i
   +(x[2]?';--tone:var(--st-'+x[2]+'-ink)':'')+'"'+(x[2]?' data-tone="'+x[2]+'"':'')
   +'><div class="l">'+esc2(x[0])+'</div><b>'+fmt(x[1])+'</b></div>').join('');
 /* بدترین‌ها بالا: شکاف کهنه، بعد شکاف، بعد تأخیر — با عمر شکاف نزولی. */
 const rank={CRITICAL_GAP:0,OVERDUE:1,SEQUENCE_CONFLICT:2,LATE:3,PENDING:4,
             DECLARED:5,NOT_CLEARED:6,UNKNOWN:7};
 const rows=wh.slice().sort((a,b)=>{
  const d=(rank[S(a,'WH_STATUS')]??9)-(rank[S(b,'WH_STATUS')]??9);
  return d||((+b['WH_AGE_DAYS']||0)-(+a['WH_AGE_DAYS']||0))}).slice(0,15);
 const num=v=>{const s=String(v??'').trim();return s===''||s==='nan'?'—':fmt(v)};
 const tab='<div class="tablewrap"><table>'
  +'<caption class="note">'+fmt(rows.length)+' از '+fmt(wh.length)
  +' ردیف · گرین: بارنامه × کالا · مبنای ترخیص در ستون آخر اعلام شده است.</caption>'
  +'<thead><tr><th scope="col">بارنامه</th><th scope="col">وضعیت اظهار</th>'
  +'<th scope="col">تاریخ ترخیص</th><th scope="col">قبض انبار</th>'
  +'<th scope="col">فاصله (روز)</th><th scope="col">عمر شکاف (روز)</th>'
  +'<th scope="col">مبنا</th></tr></thead><tbody>'
  +rows.map(x=>'<tr><td>'+esc2(S(x,'CANONICAL_BL'))+'</td><td>'
   +esc2(S(x,'WH_STATUS_FA'))+'</td><td>'+esc2(S(x,'WH_CLEAR_DATE')||'—')+'</td><td>'
   +esc2(S(x,'WH_RECEIPT_DATE')||'—')+'</td><td class="num">'+num(x['WH_LAG_DAYS'])
   +'</td><td class="num">'+num(x['WH_AGE_DAYS'])+'</td><td>'
   +esc2(S(x,'WH_CLEAR_BASIS')||'—')+'</td></tr>').join('')
  +'</tbody></table></div>';
 el.innerHTML='<h4 class="t-h4" style="margin-top:16px">اظهار انبار — سامانه جامع انبارها</h4>'
  +'<p class="note">زنجیره شاهد با ترخیص تمام نمی‌شود: کالای ترخیص‌شده باید قبض انبار '
  +'الکترونیکی بگیرد. مهلت قانونی اظهار needs_verification است و خودکار اعمال نمی‌شود؛ '
  +'آنچه اینجا می‌بینید شکاف <em>شاهد</em> است، نه حکم تخلف.</p>'
  +'<div class="grid-auto" style="--col:180px">'+cards+'</div>'+tab;
}

/* ── برج کنترل جریان پول / FX Traceability ── */
function renderFx(){
 const el=document.getElementById('process_fx');if(!el)return;
 const fx=PROC.fx_ledger||[],fxc=PROC.fx_control_summary||[];
 if(!fx.length&&!fxc.length){el.innerHTML='';return}
 const bad=fx.filter(x=>(+x['FX_ANOMALY_COUNT']||0)>0).length;
 const open=fx.filter(x=>(+x['FX_NTSW_BALANCE']||0)>0).length;
 const high=fxc.filter(x=>['HIGH','CRITICAL'].includes(S(x,'FX_CONTROL_RISK_BAND'))).length;
 const overdue=fxc.filter(x=>S(x,'FX_DEADLINE_STATUS')==='OVERDUE').length;
 const unauth=fxc.reduce((s,x)=>s+(+x['FX_UNAUTHORIZED_REALLOCATION_COUNT']||0),0);
 const cgap=fxc.filter(x=>S(x,'FX_CONVERSION_STATUS')==='EVIDENCE_GAP').length;
 const cards=[['پرونده ارزی',fx.length,''],['ریسک بالا/بحرانی جریان پول',high,'critical'],
  ['Deadline عبورکرده',overdue,'stockout'],['جابجایی بدون شاهد مجوز',unauth,'serious'],
  ['شکاف شاهد تبدیل ارز',cgap,'warning'],['مانده تعهد مثبت',open,''],
  ['ناهنجاری ثبت‌شده',bad,'warning']]
  .map((x,i)=>'<div class="kpi reveal" style="--i:'+i
   +(x[2]?';--tone:var(--st-'+x[2]+'-ink)':'')+'"'+(x[2]?' data-tone="'+x[2]+'"':'')
   +'><div class="l">'+esc2(x[0])+'</div><b>'+fmt(x[1])+'</b></div>').join('');
 /* جدول از دفترکل FX می‌آید و با امتیاز ریسک کنترلی مرتب می‌شود. */
 const byReg={};fxc.forEach(x=>{byReg[S(x,'KEY_REG')]=x});
 const src=fx.length?fx:fxc;
 const rowsFx=src.slice().sort((a,b)=>
  (+b['FX_CONTROL_RISK_SCORE']||0)-(+a['FX_CONTROL_RISK_SCORE']||0)).slice(0,15);
 const tab=rowsFx.length?('<div class="tablewrap"><table><thead><tr>'
  +'<th scope="col">ثبت سفارش</th><th scope="col">مرحله جاری</th><th scope="col">ریسک</th>'
  +'<th scope="col">روز باقی</th><th scope="col">مانده تعهد</th>'
  +'<th scope="col">اثر تبدیل (ریال)</th><th scope="col">جابجایی بدون مجوز</th>'
  +'</tr></thead><tbody>'
  +rowsFx.map(x=>{const c=byReg[S(x,'KEY_REG')]||x;
   /* «۰ روز باقی» برای پرونده‌ای که اصلاً مهلتی ندارد گمراه‌کننده است:
      بدون تاریخ مهلت «—» نشان داده می‌شود، نه صفر. */
   const hasDue=String(c['FX_DEADLINE_DATE']||'').trim()!=='';
   return '<tr><td>'+esc2(S(x,'KEY_REG'))+'</td><td>'+esc2(S(c,'FX_CURRENT_STAGE')||S(x,'FX_MONEY_STAGE'))
    +'</td><td class="num">'+fmt(c['FX_CONTROL_RISK_SCORE'])+'</td><td class="num">'
    +(hasDue?fmt(c['FX_DAYS_REMAINING']):'—')+'</td><td class="num">'+fmt(x['FX_NTSW_BALANCE'])
    +'</td><td class="num">'+fmt(c['FX_CONVERSION_IMPACT_RIAL'])+'</td><td class="num">'
    +fmt(c['FX_UNAUTHORIZED_REALLOCATION_COUNT'])+'</td></tr>'}).join('')
  +'</tbody></table></div>'):'<p class="note">دفترکل FX در این اجرا موجود نیست.</p>';
 el.innerHTML='<h4 class="t-h4" style="margin-top:16px">رهگیری مالی-ارزی / FX Traceability — Money Flow Control Tower</h4>'
  +'<p class="note">مرحله جاری، ریسک کنترلی، نزدیک‌ترین مهلت و جابه‌جایی بدون مجوز هر پرونده.</p>'
  +'<div class="grid-auto" style="--col:180px">'+cards+'</div>'+tab;
 gsiReveal(el)}

/* ── روایت این برش ──
   سه چیز که نسخه قبلی اشتباه می‌کرد و اینجا اصلاح شده:
   ۱) «هیچ ریسک فعالی نیست» فقط از بحرانی‌بودن موجودی نتیجه گرفته می‌شد؛
      حالا همه ابعاد ریسکِ در دسترس سنجیده می‌شوند.
   ۲) گلوگاه از میانگین می‌آمد؛ حالا میانه، و کنارش شمار پرونده.
   ۳) عمق و تعداد یافته‌ها ثابت بود؛ حالا از پروفایل مخاطب می‌آید. */
function audCfg(){return AUDIENCES[AUD]||AUDIENCES[Object.keys(AUDIENCES)[0]]}

/* شمارش ابعاد ریسک — نه فقط موجودی. */
function riskFacets(a){
 const f=[];
 const band=r=>S(r,'بحرانی (کوتاه)')||S(r,'کد طبقه بحرانی');
 const crit=a.filter(r=>['توقف خط','بحرانی','STOCKOUT','CRITICAL'].includes(band(r)));
 const critM=new Set(crit.map(r=>S(r,'KEY_MATERIAL').trim()).filter(Boolean));
 if(crit.length)f.push({k:'موجودی',n:critM.size||crit.length,
   t:'قطعه در طبقه بحرانی یا توقف خط',tone:'critical'});
 const fxc=PROC.fx_control_summary||[];
 const over=fxc.filter(x=>S(x,'FX_DEADLINE_STATUS')==='OVERDUE').length;
 if(over)f.push({k:'مهلت ارزی',n:over,t:'پرونده با مهلت عبورکرده',tone:'stockout'});
 const unauth=fxc.reduce((s,x)=>s+(+x['FX_UNAUTHORIZED_REALLOCATION_COUNT']||0),0);
 if(unauth)f.push({k:'مجوز جابه‌جایی',n:unauth,t:'جابه‌جایی بدون شاهد مجوز',tone:'serious'});
 const wh=PROC.warehouse_declaration||[];
 const gap=wh.filter(x=>['OVERDUE','CRITICAL_GAP'].includes(S(x,'WH_STATUS'))).length;
 if(gap)f.push({k:'اظهار انبار',n:gap,t:'شکاف شاهد پس از ترخیص',tone:'serious'});
 const waits=a.map(r=>N(r,'انتظار جاری (روز)')).filter(v=>v!==null);
 const stuck=waits.filter(v=>v>60).length;
 if(stuck)f.push({k:'توقف طولانی',n:stuck,t:'پرونده بیش از ۶۰ روز بدون رویداد',tone:'warning'});
 return f;
}

function renderStory(a){
 const cfg=audCfg(),depth=cfg.depth,maxF=cfg.max_findings;
 const band=r=>S(r,'بحرانی (کوتاه)')||S(r,'کد طبقه بحرانی');
 const crit=a.filter(r=>['توقف خط','بحرانی','STOCKOUT','CRITICAL'].includes(band(r)));
 const mats=new Set(),critMats=new Set();
 for(const r of a){const m=S(r,'KEY_MATERIAL').trim();if(m)mats.add(m)}
 for(const r of crit){const m=S(r,'KEY_MATERIAL').trim();if(m)critMats.add(m)}
 const rs=a.map(r=>N(r,'مقاومت (روز)')).filter(v=>v!==null).sort((x,y)=>x-y);
 const med=rs.length?(rs.length%2?rs[rs.length>>1]:(rs[(rs.length>>1)-1]+rs[rs.length>>1])/2):null;
 const nCrit=critMats.size||crit.length;
 const unit=critMats.size?' قطعه':' ردیف';
 const facets=riskFacets(a);

 const q=document.getElementById('story_q');
 if(q)q.textContent=cfg.question;

 const h=document.getElementById('story_h');
 if(h){
  if(nCrit)h.textContent='ریسک توقف خط: '+fmt(nCrit)+unit+' بحرانی در این برش';
  else if(facets.length)h.textContent='ریسک فعال این برش: '
   +facets.map(x=>x.k+' ('+fmt(x.n)+')').join(' · ');
  /* صادق: «موجودی بحرانی نداریم» با «هیچ ریسکی نیست» یکی نیست. */
  else h.textContent='در ابعادی که این گزارش می‌سنجد، ریسک فعالی دیده نشد.';
 }

 let situation='این برش '+fmt(a.length)+' ردیف'
  +(mats.size?('، '+fmt(mats.size)+' قطعه یکتا'):'')+' دارد.';
 let complication=nCrit?(fmt(nCrit)+unit+' در وضعیت بحرانی یا توقف خط است'
  +(mats.size?(' — '+(nCrit/mats.size*100).toLocaleString('fa-IR',{minimumFractionDigits:1,maximumFractionDigits:1})+'٪ از قطعات این برش'):'')+'.')
  :'قطعه‌ای در طبقه بحرانی نیست.';
 if(facets.length>1)complication+=' ابعاد دیگر ریسک: '
  +facets.filter(x=>x.k!=='موجودی').map(x=>x.k+' '+fmt(x.n)).join('، ')+'.';
 if(med!==null&&depth>1)complication+=' میانه مقاومت '+fmt(med)
  +' روز است (میانه، نه میانگین — توزیع راست‌چوله است).';

 const bn=(PROC.bottlenecks||[])[0];
 const qs=(PROC.stage_queue||[])[0];
 let resolution;
 if(nCrit){const worst=a.filter(r=>N(r,'مقاومت (روز)')!==null)
   .sort((x,y)=>N(x,'مقاومت (روز)')-N(y,'مقاومت (روز)'))[0];
  resolution='پیگیری امروز از کم‌مقاومت‌ترین قطعه شروع شود'
   +(worst?(': '+S(worst,'KEY_MATERIAL')):'')+'.'}
 else if(facets.length)resolution='اقدام امروز روی «'+facets[0].k+'» است: '
   +fmt(facets[0].n)+' '+facets[0].t+'.';
 else resolution='این برش اقدام فوری نمی‌خواهد؛ ظرفیت پیگیری صرف تعهد معوق یا صف طولانی شود.';
 if(depth>1){
  if(qs)resolution+=' بزرگ‌ترین صف فعلی «'+S(qs,'مرحله جاری')+'» با '
   +fmt(qs['تعداد پرونده'])+' پرونده و میانه انتظار '+fmt(qs['میانه انتظار (روز)'])+' روز است.';
  else if(bn)resolution+=' طولانی‌ترین گذار «'+S(bn,'از فعالیت')+' ← '+S(bn,'به فعالیت')
   +'» با میانه '+fmt(bn['میانه روز'])+' روز است.';
 }

 const scr=document.getElementById('story_scr');
 if(scr){scr.innerHTML=[['وضعیت',situation],['گره',complication],['اقدام',resolution]]
  .map(x=>'<div class="scr"><b>'+x[0]+'</b><p>'+esc2(x[1])+'</p></div>').join('')}

 const box=document.getElementById('story_findings');
 if(box){const items=[];
  if(nCrit)items.push(['ریسک توقف خط',fmt(nCrit)+unit+' بحرانی',
   mats.size?((nCrit/mats.size*100).toLocaleString('fa-IR',{minimumFractionDigits:1,maximumFractionDigits:1})+'٪ از قطعات این برش'):'',
   'پیگیری از کم‌مقاومت‌ترین قطعه شروع شود.','critical']);
  facets.filter(x=>x.k!=='موجودی').forEach(x=>items.push(
   [x.k,fmt(x.n)+' مورد',x.t,'بررسی و رفع شکاف شاهد یا مهلت، پیش از رسیدن به مرحله بعد.',x.tone]));
  if(med!==null&&depth>1)items.push(['پوشش مقاومت','میانه '+fmt(med)+' روز',
   'میانه گزارش می‌شود چون توزیع راست‌چوله است',
   'قطعات دهک پایین پیش از رسیدن به طبقه بحرانی سفارش‌گذاری شوند.',
   med<15?'warning':'good']);
  if(qs&&depth>1)items.push(['بزرگ‌ترین صف','«'+S(qs,'مرحله جاری')+'»',
   fmt(qs['تعداد پرونده'])+' پرونده منتظر · میانه '+fmt(qs['میانه انتظار (روز)'])
   +' روز · بیشترین '+fmt(qs['بیشترین انتظار (روز)'])+' روز',
   'ظرفیت پیگیری به همین مرحله داده شود؛ بیشترین اثر بر زمان چرخه اینجاست.','serious']);
  box.innerHTML=items.slice(0,maxF).map((x,i)=>'<article class="finding reveal" style="--i:'+i
   +';--tone:var(--st-'+x[4]+');--tone-ink:var(--st-'+x[4]+'-ink);--tone-wash:var(--st-'+x[4]+'-wash)">'
   +'<h5>'+esc2(x[0])+'</h5><p class="mag">'+esc2(x[1])+'</p>'
   +(x[2]?'<p class="cmp">'+esc2(x[2])+'</p>':'')
   +'<p class="sow"><span aria-hidden="true">←</span> '+esc2(x[3])+'</p></article>').join('');
  gsiReveal(box)}}

/* ── جابه‌جایی مخاطب ── */
function setAudience(k){
 if(!AUDIENCES[k])return;
 AUD=k;
 document.querySelectorAll('.persona').forEach(b=>
  b.setAttribute('aria-pressed',String(b.dataset.aud===k)));
 const cfg=audCfg();
 document.querySelectorAll('[data-section]').forEach(el=>{
  el.hidden=!cfg.sections.includes(el.dataset.section)});
 const cl=document.getElementById('aud_closing');
 if(cl)cl.textContent=cfg.closing?cfg.closing+' ':'';
 try{localStorage.setItem('gsi_aud',k)}catch(e){}
 render(active);
}

/* ── جدول و سنجه‌ها ── */
function pageMove(i,d){PAGE[i]=Math.max(0,(PAGE[i]||0)+d);render(i)}
function render(i){
 const t=TAB_META[i],a=rows(t);
 renderStory(a);
 const cards=[{l:'ردیف',v:a.length.toLocaleString('fa-IR'),g:''}];
 Object.keys(t.agg).slice(0,4).forEach(c=>cards.push({
  l:(t.agg[c]==='mean'?'میانگین ':'جمع ')+(LABELS[c]||c),
  v:fmt(gagg(a,c,t.grain,t.agg)),
  g:t.grain[c]?('یکتا بر '+t.grain[c]):'دانه ردیف'}));
 const cb=document.getElementById('cards_'+i);
 if(cb){cb.innerHTML=cards.map((x,j)=>'<div class="kpi reveal" style="--i:'+j+'">'
  +'<div class="l">'+esc2(x.l)+'</div><b>'+x.v+'</b><div class="g">'+esc2(x.g)+'</div></div>').join('');
  gsiReveal(cb)}
 const PAGE_SIZE=pageSize();
 const pages=Math.max(1,Math.ceil(a.length/PAGE_SIZE));
 PAGE[i]=Math.min(PAGE[i]||0,pages-1);
 const start=PAGE[i]*PAGE_SIZE,view=a.slice(start,start+PAGE_SIZE);
 const cnt=document.getElementById('cnt_'+i);
 if(cnt)cnt.textContent=a.length.toLocaleString('fa-IR')+' ردیف · صفحه '
  +(PAGE[i]+1).toLocaleString('fa-IR')+' از '+pages.toLocaleString('fa-IR');
 const tb=document.getElementById('tb_'+i);
 if(tb)tb.innerHTML=view.map(r=>'<tr>'+t.fields.map(c=>'<td>'+esc2(S(r,c))+'</td>').join('')+'</tr>').join('');
 const pg=document.getElementById('pager_'+i);
 if(pg)pg.innerHTML='<button class="btn btn--secondary btn--sm" type="button"'
  +(PAGE[i]<=0?' disabled':'')+' onclick="pageMove('+i+',-1)">صفحه قبل</button>'
  +'<span>نمایش '+Math.min(start+1,a.length).toLocaleString('fa-IR')+' تا '
  +Math.min(start+PAGE_SIZE,a.length).toLocaleString('fa-IR')+' از '
  +a.length.toLocaleString('fa-IR')+'</span>'
  +'<button class="btn btn--secondary btn--sm" type="button"'
  +(PAGE[i]>=pages-1?' disabled':'')+' onclick="pageMove('+i+',1)">صفحه بعد</button>';
 renderCharts(i,a);renderProcess(a);gsiReveal()}

function activate(i){active=i;PAGE[i]=0;
 document.querySelectorAll('.tabbtn').forEach((b,j)=>b.setAttribute('aria-selected',j===i));
 document.querySelectorAll('.pane').forEach((p,j)=>{if(j===i)p.removeAttribute('hidden');
  else p.setAttribute('hidden','')});
 if(q)q.value='';render(i)}

__XLSX__

document.querySelectorAll('.tabbtn').forEach((b,i)=>b.addEventListener('click',()=>activate(i)));
if(q)q.addEventListener('input',()=>{PAGE[active]=0;render(active)});
document.querySelectorAll('select[data-f]').forEach(s=>s.addEventListener('change',()=>{
 PAGE[active]=0;render(active)}));
document.querySelectorAll('.persona').forEach(b=>
 b.addEventListener('click',()=>setAudience(b.dataset.aud)));
/* نمای انتخابی هر خواننده یادش می‌ماند — ولی فقط در مرورگر خودش. */
try{const k=localStorage.getItem('gsi_aud');if(k&&AUDIENCES[k])AUD=k}catch(e){}
setAudience(AUD);
"""
    body = (body
            .replace("__CHART_CFG__", chart_json)
            .replace("__PROC__", proc_json)
            .replace("__CHARTS_LIB__", charts_lib)
            .replace("__REVEAL_JS__", CSS.REVEAL_JS)
            .replace("__XLSX__", _XLSX_JS))
    return "<script>" + body + "</script>"


#: خروجی Excel داخل مرورگر — بدون سرور، بدون کتابخانه.
#: ZIP با ذخیره‌سازی بدون فشرده‌سازی (method 0) ساخته می‌شود تا نیازی به
#: پیاده‌سازی deflate در جاوااسکریپت نباشد.
_XLSX_JS = r"""
function crc32(b){let t=window._crcT;if(!t){t=[];for(let n=0;n<256;n++){let c=n;
 for(let k=0;k<8;k++)c=(c&1)?0xEDB88320^(c>>>1):c>>>1;t[n]=c>>>0}window._crcT=t}
 let c=0xFFFFFFFF;for(const x of b)c=t[(c^x)&255]^(c>>>8);return (c^0xFFFFFFFF)>>>0}
const u8=s=>new TextEncoder().encode(s);
function zipStore(files){let chunks=[],central=[],offset=0;
 for(const [name,data] of files){const nb=u8(name),db=typeof data==='string'?u8(data):data,
  crc=crc32(db),head=new Uint8Array(30+nb.length),dv=new DataView(head.buffer);
  dv.setUint32(0,0x04034b50,true);dv.setUint16(4,20,true);dv.setUint32(14,crc,true);
  dv.setUint32(18,db.length,true);dv.setUint32(22,db.length,true);dv.setUint16(26,nb.length,true);
  head.set(nb,30);chunks.push(head,db);
  const cd=new Uint8Array(46+nb.length),cv=new DataView(cd.buffer);
  cv.setUint32(0,0x02014b50,true);cv.setUint16(4,20,true);cv.setUint16(6,20,true);
  cv.setUint32(16,crc,true);cv.setUint32(20,db.length,true);cv.setUint32(24,db.length,true);
  cv.setUint16(28,nb.length,true);cv.setUint32(42,offset,true);cd.set(nb,46);
  central.push(cd);offset+=head.length+db.length}
 const csize=central.reduce((s,x)=>s+x.length,0),end=new Uint8Array(22),ed=new DataView(end.buffer);
 ed.setUint32(0,0x06054b50,true);ed.setUint16(8,files.length,true);ed.setUint16(10,files.length,true);
 ed.setUint32(12,csize,true);ed.setUint32(16,offset,true);
 return new Blob(chunks.concat(central,[end]),
  {type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})}
function xmlEsc(s){return String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;')
 .replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&apos;')}
function colName(n){let s='';while(n){const r=(n-1)%26;s=String.fromCharCode(65+r)+s;
 n=Math.floor((n-1)/26)}return s}
function excelSerial(v){const d=new Date(v);if(!Number.isFinite(+d))return null;
 return (+d-Date.UTC(1899,11,30))/86400000}
function cellXml(v,ref,header){
 if(header)return '<c r="'+ref+'" s="1" t="inlineStr"><is><t>'+xmlEsc(v)+'</t></is></c>';
 const n=parseFloat(v);
 if(v!==''&&v!==null&&Number.isFinite(n)&&String(v).trim()===String(n))
  return '<c r="'+ref+'" s="2"><v>'+n+'</v></c>';
 if(typeof v==='string'&&/^\d{4}-\d{2}-\d{2}/.test(v)){const sv=excelSerial(v);
  if(sv!==null)return '<c r="'+ref+'" s="3"><v>'+sv+'</v></c>'}
 return '<c r="'+ref+'" t="inlineStr"><is><t>'+xmlEsc(v)+'</t></is></c>'}
function makeXlsx(rowsIn,fields,sheet){
 const safe=String(sheet||'Data').replace(/[\\/*?:\[\]]/g,' ').slice(0,31)||'Data';
 const head=fields.map((c,i)=>cellXml(LABELS[c]||c,colName(i+1)+'1',true)).join('');
 const body=rowsIn.map((r,i)=>'<row r="'+(i+2)+'">'
  +fields.map((c,j)=>cellXml(S(r,c),colName(j+1)+(i+2))).join('')+'</row>').join('');
 const last=colName(Math.max(fields.length,1))+(rowsIn.length+1);
 const sh='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:'+last+'"/><sheetViews><sheetView workbookViewId="0" rightToLeft="1"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData><row r="1">'+head+'</row>'+body+'</sheetData><autoFilter ref="A1:'+last+'"/></worksheet>';
 const wb='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="'+xmlEsc(safe)+'" sheetId="1" r:id="rId1"/></sheets></workbook>';
 const styles='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-mm-dd"/></numFmts><fonts count="2"><font><sz val="11"/><name val="IRANSans"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="IRANSans"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0B1F33"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment horizontal="right"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"><alignment horizontal="right"/></xf><xf numFmtId="4" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"><alignment horizontal="right"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"><alignment horizontal="right"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';
 const rel='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>';
 const wrel='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>';
 const ct='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>';
 return zipStore([['[Content_Types].xml',ct],['_rels/.rels',rel],['xl/workbook.xml',wb],
  ['xl/_rels/workbook.xml.rels',wrel],['xl/styles.xml',styles],['xl/worksheets/sheet1.xml',sh]])}
function downloadFilteredXlsx(){const t=TAB_META[active],a=rows(t);
 const blob=makeXlsx(a,t.fields,t.title),url=URL.createObjectURL(blob),
  x=document.createElement('a');
 x.href=url;x.download='GSI_filtered_'+new Date().toISOString().slice(0,10)+'.xlsx';
 x.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
"""
