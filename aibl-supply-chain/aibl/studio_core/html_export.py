# -*- coding: utf-8 -*-
"""خروجی HTML خودبسنده — راست‌به‌چپ، فیلترپذیر، آماده چاپ/PDF.

سه تفاوت بنیادی با نسخه‌های اولیه:

1. **راست‌به‌چپ و فارسی.** نسخه قبل ``dir="ltr"`` با برچسب انگلیسی بود.
2. **پالت اعتبارسنجی‌شده.** پالت قبلی «در حال بحرانی شدن» و «تحت نظر» را
   با ΔE ۹٫۸ نشان می‌داد (کف ۱۵) — عملاً تفکیک‌ناپذیر. حالا پالت وضعیت
   ثابت با آیکن و برچسب.
3. **جمع‌های دانه‌ای، حتی هنگام فیلتر مرورگری.** کلید دانه‌ی هر ستون عددی
   به JS داده می‌شود و جمع‌ها **پیش از محاسبه بر همان کلید یکتا** می‌شوند.
   بدون این، کاربر فیلتر می‌کرد و «جمع مانده تعهد» چند برابر می‌شد —
   بی‌صدا و بدون خطا.

## نسخه ۲۶٫۱۹ — چهار اصلاح که روی خروجی واقعی دیده می‌شد

**الف) برچسب نمودارها زیر میله‌ها پنهان می‌شد.** در سند ``dir="rtl"``،
``text-anchor="end"`` در SVG به معنای «انتهای منطقی» است، نه «سمت چپ». برای
متن راست‌به‌چپ، انتهای منطقی سمت **چپ** است، پس هر برچسبی که قرار بود از
لبه میله به بیرون برود، به داخل میله می‌رفت و ناخوانا می‌شد. اندازه‌گیری در
Chromium:

    text-anchor="end"                          → جعبه متن [۲۷۲ … ۳۷۴]  ← روی میله
    direction:ltr + unicode-bidi:plaintext     → جعبه متن [۱۷۰ … ۲۷۲]  ← درست

اصلاح یک قاعده CSS است روی همه متن‌های SVG؛ ``plaintext`` جهت هر برچسب را
از نخستین حرف قوی خودش می‌گیرد، پس «ثبت سفارش» راست‌به‌چپ و ``MAT-003``
چپ‌به‌راست درست رندر می‌شوند.

**ب) نمودار پراکنش محور نداشت.** ابری از نقطه بدون مقیاس، برچسب محور و خط
روند، تصمیمی را عوض نمی‌کند. حالا محورِ عددگذاری‌شده، خطوط راهنما، خطوط
میانه (چهار ربع) و خط رگرسیون با ضریب همبستگی دارد.

**ج) فیلتر تاریخ وجود نداشت.** ستون تاریخ در payload بود ولی هیچ راهی برای
بریدن بازه نبود؛ «۹۰ روز اخیر» یعنی دانلود Excel و کار دستی.

**د) روایت، سه جمله ثابت بود.** حالا ساختار وضعیت/گره/اقدام با یافته‌های
کمّی و مقایسه با اجرای قبلی از :mod:`aibl.report.storytelling` می‌آید.

## چرا هیچ کتابخانه‌ای بارگذاری نمی‌شود

این فایل از داخل Outlook و روی شبکه اداری باز می‌شود. هر ``<script src>``
خارجی یعنی یا انتظار برای شبکه‌ای که ممکن است مسدود باشد، یا گزارشی که
آفلاین خالی باز می‌شود. همه نمودارها SVG دست‌ساز و همه حرکت‌ها CSS خالص‌اند.
"""
from __future__ import annotations

__contract__ = 6

import html
import json
import re
from typing import Dict, List, Optional

import pandas as pd

from ..report import design_system as ds
from .grain import (GRAIN_KEYS, KIND_ADDITIVE, KIND_RATIO, column_grain,
                    measure_kind, prefix_grain_map, safe_agg)

#: پالت وضعیت (ثابت، هرگز تم‌پذیر) — همیشه با آیکن و برچسب.
#: مقادیر از :mod:`aibl.report.design_system` می‌آیند تا HTML، ایمیل و
#: داشبورد یک منبع رنگ داشته باشند و کنتراست یک‌جا سنجیده شود.
BANDS = {s.label: (s.fill, s.icon) for s in ds.STATUS_SCALE}
#: رنگ متن هر طبقه — تیره‌تر از رنگ سطح، سنجیده‌شده روی سفید (WCAG AA).
BAND_INK = {s.label: s.ink for s in ds.STATUS_SCALE}
BAND_ORDER = list(BANDS)

BRAND, BRAND_DEEP = ds.BRAND, ds.BRAND_DEEP
SURFACE, RAISED, BORDER = ds.SURFACE, ds.SURFACE_RAISED, ds.BORDER
TEXT, TEXT2, TEXT3 = ds.TEXT, ds.TEXT_SECONDARY, ds.TEXT_MUTED

#: ستون تاریخِ متنی با این الگو شناسایی می‌شود (payload تاریخ‌ها را به
#: ``YYYY-MM-DD`` تبدیل می‌کند، پس مقایسه رشته‌ای در JS دقیقاً درست است).
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _measure_cols(df: pd.DataFrame, cols: List[str]) -> Dict[str, str]:
    """{ستون عددی: تجمیع بامعنا}.

    شناسه‌ها (شماره سفارش، کد متریال) کنار گذاشته می‌شوند — جمع زدنشان
    بی‌معناست. ستون نسبتی (مقاومت، درصد، امتیاز) میانگین می‌گیرد، نه جمع.
    """
    out: Dict[str, str] = {}
    for c in cols:
        if pd.api.types.is_datetime64_any_dtype(df[c]) or pd.api.types.is_timedelta64_dtype(df[c]):
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        if not (s.notna().mean() > 0.5 and s.notna().any()):
            continue
        kind = measure_kind(c, s)
        if kind == KIND_ADDITIVE:
            out[c] = "sum"
        elif kind == KIND_RATIO:
            out[c] = "mean"
    return out


def _date_columns(df: pd.DataFrame, cols: List[str], payload: pd.DataFrame) -> List[str]:
    """ستون‌هایی که فیلتر بازه تاریخ روی آن‌ها معنا دارد.

    دو منبع: نوع datetime در دیتافریم اصلی، و ستون متنی که غالب مقادیرش
    الگوی ISO دارند (بسیاری از سورس‌ها تاریخ را رشته می‌دهند). ستونی که
    فقط چند مقدار تاریخ‌نما دارد وارد نمی‌شود — فیلتری که ۹۰٪ ردیف‌ها را
    بی‌دلیل حذف کند، بدتر از نبودن فیلتر است.
    """
    out: List[str] = []
    for c in cols:
        if c not in payload.columns:
            continue
        if c in df.columns and pd.api.types.is_datetime64_any_dtype(df[c]):
            out.append(c)
            continue
        vals = [str(x) for x in payload[c].tolist() if str(x).strip()]
        if len(vals) >= 3 and sum(1 for v in vals if _ISO_DATE.match(v)) / len(vals) > 0.8:
            out.append(c)
    return out


def _story_payload(df: pd.DataFrame, extras: Optional[Dict], ref_date: str,
                   want_trend: bool) -> Dict:
    """روایت و معیارهای فرآیند/روند — هرگز باعث شکست ساخت گزارش نمی‌شود.

    ساخت روایت یک لایه ارائه است. اگر به هر دلیلی (ستون غایب، تاریخچه
    خراب) شکست بخورد، گزارش باید همچنان ساخته شود؛ پس شکست اینجا به یک
    payload خالی تبدیل می‌شود، نه به استثنا.
    """
    try:
        from ..report.storytelling import build_story, load_history
        trend = load_history() if want_trend else {"dates": [], "series": {}, "deltas": {}, "points": 0}
        return build_story(df, extras or {}, trend, ref_date=ref_date).as_dict()
    except Exception:
        return {"headline": "", "situation": "", "complication": "", "resolution": "",
                "findings": [], "process": {}, "trend": {"dates": [], "series": {}, "deltas": {}, "points": 0}}


def build_dynamic_html(df: pd.DataFrame, ref_date: str, title: str = "AIBL",
                       max_rows: int = 2500, selected_fields=None,
                       labels: Optional[Dict[str, str]] = None,
                       template_title: str = "", subtitle: str = "",
                       show_visuals: bool = True, show_tables: bool = True, show_process: bool = False,
                       tabs: Optional[List[Dict]] = None, charts: Optional[List[str]] = None,
                       process_extras: Optional[Dict] = None, max_payload_cells: int = 180000,
                       lineage: Optional[Dict[str, str]] = None) -> str:
    """HTML خودبسنده با تب‌های واقعی و فیلتر زنده."""
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
    all_needed = []
    for tab in norm_tabs:
        for c in tab["fields"]:
            if c not in all_needed:
                all_needed.append(c)
    for k in GRAIN_KEYS.values():
        if k in df.columns and k not in all_needed:
            all_needed.append(k)
    if band_col and band_col not in all_needed:
        all_needed.append(band_col)
    # نمودارها presentation هستند و نباید کاربر را مجبور کنند فیلدهای پشتیبان
    # را به جدول اضافه کند. وابستگی نمودارها به‌صورت hidden داخل payload می‌آید.
    chart_fields = {
        "criticality": ["بحرانی (کوتاه)", "کد طبقه بحرانی"],
        "low_resistance": ["KEY_MATERIAL", "مقاومت (روز)"],
        "stock_vs_total": ["KEY_MATERIAL", "مقاومت انبار (روز)", "مقاومت (روز)"],
        "sediment_vs_resistance": ["KEY_MATERIAL", "روزهای رسوب", "مقاومت (روز)", "بحرانی (کوتاه)"],
        "delay_vs_commitment": ["CANONICAL_ORDER", "KEY_REG", "روزهای تأخیر", "مانده تعهد", "بحرانی (کوتاه)"],
        "risk_mix": ["طبقه ریسک"],
        "commitment": ["مانده تعهد", "روزهای تأخیر", "KEY_REG", "CANONICAL_ORDER"],
        "overdue_bucket": ["روزهای تأخیر"],
        "pareto_delay": ["روزهای تأخیر", "CANONICAL_ORDER", "KEY_REG", "CANONICAL_BL"],
        "org_workload": ["ORG_DEPT", "ORG_VICE"],
        "expert_workload": ["CANONICAL_EXPERT"],
        "transport_mix": ["TRANSPORT_MODE", "CL_TRANSPORT_MODE_CODE", "MOGH_TRANSPORT_MODE_CODE"],
        "stage_distribution": ["STAGE_FA", "ORDER_STAGE_FA", "LIFECYCLE_STAGE"],
        "bottlenecks": ["STAGE_FA", "ORDER_STAGE_FA", "LIFECYCLE_STAGE", "CASE_KEY"],
        "top_orders": ["CANONICAL_ORDER", "KEY_ORDER"],
        "top_bl": ["CANONICAL_BL", "KEY_BL"],
        "supplier_mix": ["SUPPLIER", "VENDOR_CODE", "MFR_VENDOR_CODE"],
    }
    for ck in list(charts or []):
        for c in chart_fields.get(str(ck), []):
            if c in df.columns and c not in all_needed:
                all_needed.append(c)
    if show_process:
        for c in ("STAGE_FA", "ORDER_STAGE_FA", "LIFECYCLE_STAGE"):
            if c in df.columns and c not in all_needed:
                all_needed.append(c)
    # Process filtering needs the case identity in the browser payload even when
    # CASE_KEY is not a visible report column. It remains hidden from the table.
    if show_process and "CASE_KEY" in df.columns and "CASE_KEY" not in all_needed:
        all_needed.append("CASE_KEY")

    # V26.18: never silently shrink the requested row count based on number of
    # columns.  The former max_payload_cells safeguard was the reason a 3,000
    # row request could become ~900 rows.  Browser performance is now handled
    # by paginated DOM rendering; the payload keeps every row requested by the
    # report/tab contract.
    requested_cap = max(t["max_rows"] for t in norm_tabs)
    requested_cap = len(df) if requested_cap <= 0 else requested_cap
    payload_truncated = len(df) > requested_cap
    safe_cap = min(len(df), requested_cap)
    data = df[all_needed].head(safe_cap).copy()
    for c in data.columns:
        if pd.api.types.is_datetime64_any_dtype(data[c]):
            data[c] = data[c].dt.strftime("%Y-%m-%d")
    data = data.fillna("")
    records = json.dumps(data.astype(object).values.tolist(), ensure_ascii=False, default=str).replace("</", "<" + "\\/" )
    col_index = {c: i for i, c in enumerate(data.columns)}
    date_cols = _date_columns(df, all_needed, data)

    def tab_meta(tab):
        cols = tab["fields"]
        measures = _measure_cols(df, cols)
        grain_of = {c: (GRAIN_KEYS.get(column_grain(c, pm)) or "") for c in cols}
        filters = []
        for c in cols:
            if c in date_cols:          # بازه تاریخ کنترل مخصوص خودش را دارد
                continue
            vals = sorted({str(x) for x in data[c].tolist() if str(x).strip()})
            if 1 < len(vals) <= 40:
                filters.append((c, labels.get(c, c), vals))
            if len(filters) >= 5:
                break
        return measures, grain_of, filters

    stat_html = ""
    if band_col:
        vc = df[band_col].astype(str).value_counts()
        stat_html = "".join(
            f'<span class="hstat"><b>{int(vc.get(b,0)):,}</b>{html.escape(b)}</span>'
            for b in ("توقف خط", "بحرانی") if int(vc.get(b,0)) > 0)
    legend_html = "".join(
        f'<span class="lg" style="--c:{BAND_INK[b]};--f:{c}">'
        f'<i aria-hidden="true">{icon}</i>{html.escape(b)}</span>'
        for b,(c,icon) in BANDS.items())
    buttons = "".join(
        f'<button class="tabbtn{" active" if i==0 else ""}" role="tab" '
        f'aria-selected="{str(i==0).lower()}" data-pane="{t["id"]}">'
        f'{html.escape(t["title"])}</button>' for i,t in enumerate(norm_tabs))

    panes, metas = [], []
    for i, tab in enumerate(norm_tabs):
        cols = tab["fields"]
        measures, grain_of, filters = tab_meta(tab)
        head = "".join(f"<th>{html.escape(labels.get(c,c))}</th>" for c in cols)
        fhtml = "".join(
            f'<label>{html.escape(lab)}<select data-f="{html.escape(c)}" data-pane="{tab["id"]}">'
            f'<option value="">همه</option>' +
            "".join(f'<option>{html.escape(v)}</option>' for v in vals) +
            "</select></label>" for c,lab,vals in filters)
        # ── کنترل بازه تاریخ ──
        pane_dates = [c for c in cols if c in date_cols] or list(date_cols)
        dhtml = ""
        if pane_dates:
            opts = "".join(f'<option value="{html.escape(c)}">{html.escape(labels.get(c,c))}</option>'
                           for c in pane_dates)
            picker = (f'<select class="datecol" data-pane="{tab["id"]}" aria-label="ستون تاریخ">{opts}</select>'
                      if len(pane_dates) > 1 else
                      f'<input type="hidden" class="datecol" data-pane="{tab["id"]}" value="{html.escape(pane_dates[0])}">'
                      f'<span class="datecol-name">{html.escape(labels.get(pane_dates[0], pane_dates[0]))}</span>')
            presets = "".join(
                f'<button class="chip" onclick="datePreset({i},{d})">{lab}</button>'
                for lab, d in (("۷ روز", 7), ("۳۰ روز", 30), ("۹۰ روز", 90), ("۱ سال", 365)))
            dhtml = (f'<div class="daterange" data-pane="{tab["id"]}">'
                     f'<div class="dr-head"><span class="dr-title">بازه تاریخ</span>{picker}</div>'
                     f'<div class="dr-inputs">'
                     f'<label>از<input type="date" class="dfrom" data-pane="{tab["id"]}"></label>'
                     f'<label>تا<input type="date" class="dto" data-pane="{tab["id"]}"></label></div>'
                     f'<div class="dr-chips">{presets}'
                     f'<button class="chip ghost" onclick="datePreset({i},0)">همه بازه</button></div>'
                     f'<div class="dr-note" id="drnote_{i}"></div></div>')
        hidden = ' style="display:none"' if i else ''
        table_html = (
            f'<div class="panel reveal"><div class="panel-head">'
            f'<h3>{html.escape(tab["title"])}</h3><span class="note" id="cnt_{i}"></span></div>'
            f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead>'
            f'<tbody id="tb_{i}"></tbody></table></div><div class="pager" id="pager_{i}"></div></div>' if show_tables else
            f'<div class="note" id="cnt_{i}"></div>')
        panes.append(
            f'<section id="{tab["id"]}" class="pane" role="tabpanel"{hidden}>'
            f'<div class="toolbar">{fhtml}</div>{dhtml}<div class="cards" id="cards_{i}"></div>'
            f'<div class="chartgrid" id="charts_{i}"></div>{table_html}</section>')
        metas.append({"id":tab["id"],"fields":cols,"max_rows":tab["max_rows"],
                      "grain":grain_of,"agg":measures,
                      "title":tab["title"],"dates":pane_dates})

    chart_keys = list(charts or []) if show_visuals else []
    try:
        from .chart_catalog import CHART_TITLES, CHART_SPECS, HISTORY_CHARTS
        chart_labels = {k: CHART_TITLES[k] for k in chart_keys if k in CHART_TITLES}
        chart_kinds = {k: CHART_SPECS[k].kind for k in chart_keys if k in CHART_SPECS}
        chart_questions = {k: CHART_SPECS[k].question for k in chart_keys if k in CHART_SPECS}
        history_keys = list(HISTORY_CHARTS)
    except Exception:
        chart_labels = {k: k for k in chart_keys}
        chart_kinds, chart_questions, history_keys = {}, {}, []
    proc_payload = {}
    for key in ("bottlenecks", "variants", "conformance_root_causes", "conformance_cases", "case_table", "eventlog"):
        t = (process_extras or {}).get(key)
        if isinstance(t, pd.DataFrame) and not t.empty:
            x=t.copy()
            for c in x.columns:
                if pd.api.types.is_datetime64_any_dtype(x[c]): x[c]=x[c].dt.strftime("%Y-%m-%d %H:%M:%S")
            proc_payload[key]=x.fillna("").to_dict(orient="records")
    chart_json=json.dumps({"keys":chart_keys,"labels":chart_labels,"kinds":chart_kinds,
                           "questions":chart_questions,"history":history_keys},ensure_ascii=False)
    proc_json=json.dumps(proc_payload,ensure_ascii=False,default=str)
    wants_trend = any(k in set(history_keys) for k in chart_keys)
    story = _story_payload(df, process_extras, ref_date, wants_trend)
    story_json = json.dumps(story, ensure_ascii=False, default=str)
    report_meta = dict(lineage or {})
    report_meta.update({"ref_date": ref_date, "title": title, "payload_rows": len(data), "source_rows": len(df)})
    report_meta_json = json.dumps(report_meta, ensure_ascii=False, default=str)
    run_id = str(report_meta.get("warehouse_run_id") or "").strip()
    lineage_text = (f" · Snapshot {html.escape(run_id)}" if run_id else "")
    band_ink_json = json.dumps(BAND_INK, ensure_ascii=False)
    band_fill_json = json.dumps({b: c for b, (c, _ic) in BANDS.items()}, ensure_ascii=False)
    series_json = json.dumps(list(ds.CATEGORICAL), ensure_ascii=False)

    dynamic_js = r"""<script>
const CHART_CFG=__CHART_CFG__; const PROC=__PROC__; const STORY=__STORY__;
const BAND_INK=__BAND_INK__; const BAND_FILL=__BAND_FILL__; const SERIES=__SERIES__;
const DATE_COLS=__DATE_COLS__;
const _esc2=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
function V(r,c){if(Array.isArray(r)){const i=COL_INDEX[c];return i===undefined?'':(r[i]??'')}return r?.[c]??''}
function S(r,c){return String(V(r,c))}
function N(r,c){const v=parseFloat(S(r,c));return Number.isFinite(v)?v:null}
const DSTATE={};
function dstate(i){return DSTATE[i]||(DSTATE[i]={col:'',from:'',to:''})}
function dateOf(r,col){const v=S(r,col).slice(0,10);return /^\d{4}-\d{2}-\d{2}$/.test(v)?v:''}
function rows(t){
 /* شاخص تب از خود TAB_META گرفته می‌شود تا امضای rows(t) دست‌نخورده بماند
    و هیچ فراخوانی‌ای نتواند بازه تاریخ را سهواً جا بیندازد. */
 const i=TAB_META.indexOf(t);
 const query=String(q?.value||'').trim().toLowerCase();
 const sels=[...document.querySelectorAll('select[data-f][data-pane="'+t.id+'"]')];
 const d=(i<0)?null:dstate(i), dc=d&&d.col&&(d.from||d.to)?d.col:'';
 return DATA.filter(r=>{
  for(const s of sels){if(s.value&&S(r,s.dataset.f)!==s.value)return false}
  if(dc){const v=dateOf(r,dc);if(!v)return false;if(d.from&&v<d.from)return false;if(d.to&&v>d.to)return false}
  if(query&&!t.fields.some(c=>S(r,c).toLowerCase().includes(query)))return false;
  return true}).slice(0,t.max_rows)}
function fmt(v){return (Math.round((Number(v)||0)*100)/100).toLocaleString('fa-IR')}
function fmtShort(v){const n=Number(v)||0,a=Math.abs(n);
 if(a>=1e9)return (n/1e9).toLocaleString('fa-IR',{maximumFractionDigits:1})+'G';
 if(a>=1e6)return (n/1e6).toLocaleString('fa-IR',{maximumFractionDigits:1})+'M';
 if(a>=1e4)return (n/1e3).toLocaleString('fa-IR',{maximumFractionDigits:0})+'K';
 return fmt(n)}
function _chartBox(t,i,q){return '<figure class="chartbox reveal"><figcaption><h4>'+_esc2(t)+'</h4>'+(q?'<span class="ask">'+_esc2(q)+'</span>':'')+'</figcaption>'+i+'</figure>'}
function _empty(msg){return '<div class="emptybox"><span class="emptymark" aria-hidden="true">◇</span><p>'+_esc2(msg)+'</p></div>'}
function ticks(min,max,count){if(!(max>min))return [min];const span=max-min,raw=span/count,p=Math.pow(10,Math.floor(Math.log10(raw)||0)),n=raw/p;
 const step=(n<=1?1:n<=2?2:n<=5?5:10)*p,start=Math.ceil(min/step)*step,out=[];
 for(let v=start;v<=max+step*0.001;v+=step)out.push(Math.round(v*1e6)/1e6);
 return out.length?out:[min,max]}
/* ── میله افقی: خطوط راهنما، مرز سطح رنگی و ورود آبشاری ── */
function _bar(rowsIn,title,opt){opt=opt||{};
 if(!rowsIn||!rowsIn.length)return _chartBox(title,_empty('داده کافی برای این نمودار در برش فعلی نیست.'),opt.q);
 let rs=rowsIn.slice().filter(x=>Number.isFinite(+x.v)).sort((a,b)=>b.v-a.v).slice(0,10);
 if(!rs.length)return _chartBox(title,_empty('همه مقادیر این نمودار در برش فعلی تهی‌اند.'),opt.q);
 const mx=Math.max(...rs.map(x=>+x.v),1),W=760,L=248,R=74,B=26,T=14,BH=22,GAP=12;
 const H=T+B+rs.length*(BH+GAP);const plot=W-L-R;
 let g='';ticks(0,mx,4).forEach(tv=>{const x=L+tv/mx*plot;
  g+='<line x1="'+x+'" y1="'+T+'" x2="'+x+'" y2="'+(H-B)+'" class="grid"></line>'
   +'<text x="'+x+'" y="'+(H-B+16)+'" text-anchor="middle" class="tick">'+fmtShort(tv)+'</text>'});
 let s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+_esc2(title)+'" preserveAspectRatio="xMidYMid meet">'+g;
 s+='<line x1="'+L+'" y1="'+T+'" x2="'+L+'" y2="'+(H-B)+'" class="axis"></line>';
 rs.forEach((x,i)=>{const y=T+i*(BH+GAP),w=Math.max(3,+x.v/mx*plot),fill=x.c||opt.color||'var(--accent)',ink=x.ink||opt.ink||'var(--deep)';
  s+='<text x="'+(L-10)+'" y="'+(y+BH*0.72)+'" class="chart-label">'+_esc2(x.k)+'</text>'
   +'<rect x="'+L+'" y="'+y+'" width="'+w+'" height="'+BH+'" rx="4" class="chart-bar" style="--i:'+i+';fill:'+fill+';stroke:'+ink+'"><title>'+_esc2(x.k)+' — '+fmt(x.v)+'</title></rect>'
   +'<text x="'+(L+w+7)+'" y="'+(y+BH*0.72)+'" class="chart-value">'+fmtShort(x.v)+'</text>'});
 return _chartBox(title,s+'</svg>',opt.q)}
/* ── دونات: مرز سفید، درصد روی راهنما، مجموع در مرکز ── */
function _donut(rs,title,opt){opt=opt||{};
 const total=rs.reduce((s,x)=>s+(+x.v||0),0);
 if(!total)return _chartBox(title,_empty('هیچ دسته‌ای در این برش مقدار ندارد.'),opt.q);
 rs=rs.slice().sort((a,b)=>b.v-a.v);
 const cx=124,cy=124,R=88,r=52;let a=-Math.PI/2,path='';
 rs.forEach((x,i)=>{const v=+x.v||0,b=a+v/total*Math.PI*2,la=(b-a)>Math.PI?1:0,
  p1=[cx+R*Math.cos(a),cy+R*Math.sin(a)],p2=[cx+R*Math.cos(b),cy+R*Math.sin(b)],
  q1=[cx+r*Math.cos(b),cy+r*Math.sin(b)],q2=[cx+r*Math.cos(a),cy+r*Math.sin(a)];
  path+='<path d="M'+p1+' A'+R+' '+R+' 0 '+la+' 1 '+p2+' L'+q1+' A'+r+' '+r+' 0 '+la+' 0 '+q2+' Z" class="slice" fill="'+(x.c||SERIES[i%SERIES.length])+'"><title>'+_esc2(x.k)+' — '+fmt(v)+' ('+(v/total*100).toFixed(1)+'٪)</title></path>';a=b});
 const leg=rs.map((x,i)=>'<div class="legend-item"><i style="background:'+(x.c||SERIES[i%SERIES.length])+'"></i><span class="lk">'+_esc2(x.k)+'</span><b>'+fmt(x.v)+'</b><span class="lp">'+((+x.v||0)/total*100).toFixed(0)+'٪</span></div>').join('');
 return _chartBox(title,'<div class="donut-wrap"><svg viewBox="0 0 248 248" role="img" aria-label="'+_esc2(title)+'"><g class="slices">'+path+'</g><text x="124" y="120" text-anchor="middle" class="donut-total">'+fmtShort(total)+'</text><text x="124" y="142" text-anchor="middle" class="donut-sub">ردیف</text></svg><div class="legend">'+leg+'</div></div>',opt.q)}
/* ── پراکنش: محور عددگذاری‌شده، چهار ربع بر مبنای میانه، خط رگرسیون ── */
function _scatter(arr,title,xc,yc,opt){opt=opt||{};
 const pts=[];for(const r of arr){const x=N(r,xc),y=N(r,yc);if(x===null||y===null)continue;
  pts.push({x:x,y:y,k:S(r,opt.key||'KEY_MATERIAL')||S(r,'CANONICAL_ORDER'),b:S(r,'بحرانی (کوتاه)')})}
 if(pts.length<3)return _chartBox(title,_empty('برای سنجش رابطه دست‌کم سه پرونده با هر دو مقدار لازم است.'),opt.q);
 const W=760,H=340,L=64,T=18,R=22,B=52,pw=W-L-R,ph=H-T-B;
 const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);
 const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
 const xr=(x1-x0)||1,yr=(y1-y0)||1;
 const px=v=>L+(v-x0)/xr*pw, py=v=>T+ph-(v-y0)/yr*ph;
 const med=a=>{const s=a.slice().sort((p,q)=>p-q),m=s.length>>1;return s.length%2?s[m]:(s[m-1]+s[m])/2};
 const mx=med(xs),my=med(ys);
 let s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+_esc2(title)+'" preserveAspectRatio="xMidYMid meet">';
 /* ربع پرخطر: بالای میانه محور افقی و زیر میانه محور عمودی */
 s+='<rect x="'+px(mx)+'" y="'+py(my)+'" width="'+(L+pw-px(mx))+'" height="'+(T+ph-py(my))+'" class="quad"></rect>';
 ticks(y0,y1,4).forEach(tv=>{const y=py(tv);s+='<line x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" class="grid"></line><text x="'+(L-8)+'" y="'+(y+4)+'" text-anchor="end" class="tick">'+fmtShort(tv)+'</text>'});
 ticks(x0,x1,5).forEach(tv=>{const x=px(tv);s+='<line x1="'+x+'" y1="'+T+'" x2="'+x+'" y2="'+(T+ph)+'" class="grid"></line><text x="'+x+'" y="'+(T+ph+18)+'" text-anchor="middle" class="tick">'+fmtShort(tv)+'</text>'});
 s+='<line x1="'+px(mx)+'" y1="'+T+'" x2="'+px(mx)+'" y2="'+(T+ph)+'" class="median"></line>';
 s+='<line x1="'+L+'" y1="'+py(my)+'" x2="'+(W-R)+'" y2="'+py(my)+'" class="median"></line>';
 s+='<line x1="'+L+'" y1="'+(T+ph)+'" x2="'+(W-R)+'" y2="'+(T+ph)+'" class="axis"></line><line x1="'+L+'" y1="'+T+'" x2="'+L+'" y2="'+(T+ph)+'" class="axis"></line>';
 const n=pts.length,sx=xs.reduce((a,b)=>a+b,0),sy=ys.reduce((a,b)=>a+b,0);
 const mxa=sx/n,mya=sy/n;let sxy=0,sxx=0,syy=0;
 for(const p of pts){sxy+=(p.x-mxa)*(p.y-mya);sxx+=(p.x-mxa)**2;syy+=(p.y-mya)**2}
 const shown=pts.slice(0,600);
 shown.forEach((p,i)=>{const c=BAND_FILL[p.b]||'var(--accent)';
  s+='<circle cx="'+px(p.x).toFixed(1)+'" cy="'+py(p.y).toFixed(1)+'" r="4.5" class="dot" style="--i:'+(i%60)+';fill:'+c+'"><title>'+_esc2(p.k||'—')+'\n'+_esc2(opt.xlabel||xc)+': '+fmt(p.x)+'\n'+_esc2(opt.ylabel||yc)+': '+fmt(p.y)+'</title></circle>'});
 let rtxt='';
 if(sxx>0&&syy>0){const slope=sxy/sxx,inter=mya-slope*mxa,r=sxy/Math.sqrt(sxx*syy);
  const ya=slope*x0+inter,yb=slope*x1+inter;
  const cl=v=>Math.min(Math.max(v,y0),y1);
  s+='<line x1="'+px(x0)+'" y1="'+py(cl(ya))+'" x2="'+px(x1)+'" y2="'+py(cl(yb))+'" class="trend-line" style="--dash:900"></line>';
  rtxt='<span class="stat">همبستگی r = '+r.toFixed(2)+'</span><span class="stat">'+(Math.abs(r)<0.2?'رابطه‌ای دیده نمی‌شود':Math.abs(r)<0.5?'رابطه ضعیف':Math.abs(r)<0.75?'رابطه متوسط':'رابطه قوی')+'</span>'}
 s+='<text x="'+(L+pw/2)+'" y="'+(H-10)+'" text-anchor="middle" class="axis-title">'+_esc2(opt.xlabel||xc)+'</text>';
 s+='<text transform="translate(16,'+(T+ph/2)+') rotate(-90)" text-anchor="middle" class="axis-title">'+_esc2(opt.ylabel||yc)+'</text>';
 const more=pts.length>shown.length?'<span class="stat">نمایش '+fmt(shown.length)+' از '+fmt(pts.length)+' نقطه</span>':'';
 return _chartBox(title,s+'</svg><div class="chartfoot"><span class="stat quadmark">ربع تیره = '+_esc2(opt.quad||'ناحیه پرخطر')+'</span>'+rtxt+more+'</div>',opt.q)}
/* ── روند: از snapshot تاریخی، نه از برش جاری ── */
function _trend(metric,title,opt){opt=opt||{};
 const tr=(STORY.trend)||{},ds=tr.dates||[],ser=(tr.series||{})[metric];
 if(!ser||ser.filter(v=>v!==null).length<2)
  return _chartBox(title,_empty('برای نمودار روند دست‌کم دو اجرای ثبت‌شده لازم است. با اجرای روزانه، تاریخچه ساخته می‌شود.'),opt.q);
 const vals=ser.map(v=>v===null?null:+v),ok=vals.filter(v=>v!==null);
 const lo=Math.min(...ok),hi=Math.max(...ok),span=(hi-lo)||Math.abs(hi)||1;
 const W=760,H=250,L=62,T=22,R=20,B=44,pw=W-L-R,ph=H-T-B;
 const n=vals.length,px=i=>L+(n<2?pw/2:i/(n-1)*pw),py=v=>T+ph-(v-lo+span*0.08)/(span*1.16)*ph;
 let line='',area='',first=true,prev=null;
 vals.forEach((v,i)=>{if(v===null)return;const X=px(i),Y=py(v);
  if(first){line='M'+X+' '+Y;area='M'+X+' '+(T+ph)+' L'+X+' '+Y;first=false}
  else{line+=' L'+X+' '+Y;area+=' L'+X+' '+Y}prev=X});
 if(prev!==null)area+=' L'+prev+' '+(T+ph)+' Z';
 let g='';ticks(lo,hi,3).forEach(tv=>{const Y=py(tv);
  g+='<line x1="'+L+'" y1="'+Y+'" x2="'+(W-R)+'" y2="'+Y+'" class="grid"></line><text x="'+(L-8)+'" y="'+(Y+4)+'" text-anchor="end" class="tick">'+fmtShort(tv)+'</text>'});
 let lab='';const step=Math.max(1,Math.ceil(n/6));
 ds.forEach((d,i)=>{if(i%step&&i!==n-1)return;lab+='<text x="'+px(i)+'" y="'+(T+ph+18)+'" text-anchor="middle" class="tick">'+_esc2(String(d).slice(5))+'</text>'});
 const lastI=vals.map((v,i)=>v===null?-1:i).filter(i=>i>=0).pop();
 const dot=lastI>=0?'<circle cx="'+px(lastI)+'" cy="'+py(vals[lastI])+'" r="5" class="trend-dot"></circle>':'';
 const d=(tr.deltas||{})[metric];
 let badge='';
 if(d){const up=d.change>0,good=d.improving;
  badge='<span class="delta '+(good===null?'flat':good?'good':'bad')+'">'+(up?'▲':d.change<0?'▼':'■')+' '+fmt(Math.abs(d.change))+(d.pct!==null&&d.pct!==undefined?' ('+fmt(Math.abs(d.pct))+'٪)':'')+' '+(good===null?'بدون تغییر':good?'بهبود':'بدتر')+'</span>'}
 const svg='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+_esc2(title)+'" preserveAspectRatio="xMidYMid meet">'+g+lab
  +'<path d="'+area+'" class="trend-area"></path><path d="'+line+'" class="trend-line" style="--dash:1800" fill="none"></path>'+dot
  +'<line x1="'+L+'" y1="'+(T+ph)+'" x2="'+(W-R)+'" y2="'+(T+ph)+'" class="axis"></line></svg>';
 return _chartBox(title,svg+'<div class="chartfoot">'+badge+'<span class="stat">'+fmt(n)+' اجرای ثبت‌شده · از snapshot تاریخی، مستقل از فیلتر این برش</span></div>',opt.q)}
/* ── پارتو: میله نزولی + منحنی تجمعی + خط مرجع ۸۰٪ ── */
function _pareto(rowsIn,title,opt){opt=opt||{};
 let rs=(rowsIn||[]).filter(x=>Number.isFinite(+x.v)&&+x.v>0).sort((a,b)=>b.v-a.v);
 if(rs.length<2)return _chartBox(title,_empty('برای تحلیل تمرکز دست‌کم دو دسته با مقدار مثبت لازم است.'),opt.q);
 const total=rs.reduce((s,x)=>s+ +x.v,0);rs=rs.slice(0,12);
 const W=760,H=310,L=58,T=20,R=52,B=74,pw=W-L-R,ph=H-T-B,bw=pw/rs.length,mx=Math.max(...rs.map(x=>+x.v));
 let s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+_esc2(title)+'" preserveAspectRatio="xMidYMid meet">';
 ticks(0,mx,4).forEach(tv=>{const y=T+ph-tv/mx*ph;s+='<line x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" class="grid"></line><text x="'+(L-8)+'" y="'+(y+4)+'" text-anchor="end" class="tick">'+fmtShort(tv)+'</text>'});
 const y80=T+ph-0.8*ph;
 s+='<line x1="'+L+'" y1="'+y80+'" x2="'+(W-R)+'" y2="'+y80+'" class="ref80"></line><text x="'+(W-R+4)+'" y="'+(y80-5)+'" class="tick">۸۰٪</text>';
 let cum=0,pathD='',reach=0;
 rs.forEach((x,i)=>{const h=(+x.v)/mx*ph,X=L+i*bw+bw*0.16,Y=T+ph-h;
  s+='<rect x="'+X+'" y="'+Y+'" width="'+(bw*0.68)+'" height="'+Math.max(h,1)+'" rx="3" class="pareto-bar" style="--i:'+i+'"><title>'+_esc2(x.k)+' — '+fmt(x.v)+'</title></rect>';
  cum+=+x.v;const cy=T+ph-(cum/total)*ph,cx2=X+bw*0.34;
  pathD+=(i?' L':'M')+cx2+' '+cy;
  if(!reach&&cum/total>=0.8)reach=i+1;
  s+='<text x="'+cx2+'" y="'+(T+ph+16)+'" text-anchor="middle" class="tick tick-cat" transform="rotate(-28 '+cx2+' '+(T+ph+16)+')">'+_esc2(String(x.k).slice(0,16))+'</text>'});
 s+='<path d="'+pathD+'" class="trend-line" style="--dash:1400" fill="none"></path>';
 s+='<line x1="'+L+'" y1="'+(T+ph)+'" x2="'+(W-R)+'" y2="'+(T+ph)+'" class="axis"></line></svg>';
 const msg=reach?('۸۰٪ از کل روی '+fmt(reach)+' دسته نخست متمرکز است — همان‌جا بیشترین بازده اقدام است.')
   :'تمرکز کمتر از قاعده ۸۰/۲۰ است؛ اثر روی دسته‌های زیادی پخش شده.';
 return _chartBox(title,s+'<div class="chartfoot"><span class="stat">'+_esc2(msg)+'</span></div>',opt.q)}
function _countBy(a,fields){let m={};a.forEach(r=>{let v='';for(const f of fields){v=S(r,f).trim();if(v)break}v=v||'نامشخص';m[v]=(m[v]||0)+1});return Object.entries(m).map(([k,v])=>({k,v}))}
function _topCount(a,fields){return _countBy(a,fields).sort((x,y)=>y.v-x.v).slice(0,12)}
function _sumUnique(a,valCol,keyFields){let seen=new Set(),sum=0;for(const r of a){let key='';for(const f of keyFields){key=S(r,f).trim();if(key)break}if(key){if(seen.has(key))continue;seen.add(key)}let v=parseFloat(S(r,valCol));if(Number.isFinite(v))sum+=v}return sum}
function _bandRows(a,fields){return _countBy(a,fields).map(x=>({k:x.k,v:x.v,c:BAND_FILL[x.k]||null,ink:BAND_INK[x.k]||null}))}
function _grouped(rs,title,opt){opt=opt||{};
 rs=rs.filter(x=>Number.isFinite(+x.a)||Number.isFinite(+x.b)).slice(0,10);
 if(!rs.length)return _chartBox(title,_empty('دو معیار لازم برای مقایسه در این برش وجود ندارد.'),opt.q);
 const mx=Math.max(...rs.flatMap(x=>[+x.a||0,+x.b||0]),1),W=760,L=248,R=70,T=14,B=26,RH=30,GAP=12;
 const H=T+B+rs.length*(RH+GAP),plot=W-L-R;
 let g='';ticks(0,mx,4).forEach(tv=>{const x=L+tv/mx*plot;g+='<line x1="'+x+'" y1="'+T+'" x2="'+x+'" y2="'+(H-B)+'" class="grid"></line><text x="'+x+'" y="'+(H-B+16)+'" text-anchor="middle" class="tick">'+fmtShort(tv)+'</text>'});
 let s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+_esc2(title)+'" preserveAspectRatio="xMidYMid meet">'+g;
 rs.forEach((x,i)=>{const y=T+i*(RH+GAP),wa=(+x.a||0)/mx*plot,wb=(+x.b||0)/mx*plot;
  s+='<text x="'+(L-10)+'" y="'+(y+20)+'" class="chart-label">'+_esc2(x.k)+'</text>'
   +'<rect x="'+L+'" y="'+y+'" width="'+Math.max(wa,1)+'" height="12" rx="3" class="chart-bar series-b" style="--i:'+i+'"><title>'+_esc2(opt.a||'الف')+' — '+fmt(x.a)+'</title></rect>'
   +'<rect x="'+L+'" y="'+(y+16)+'" width="'+Math.max(wb,1)+'" height="12" rx="3" class="chart-bar series-a" style="--i:'+i+'"><title>'+_esc2(opt.b||'ب')+' — '+fmt(x.b)+'</title></rect>'});
 s+='</svg><div class="chartfoot"><span class="legend-item"><i class="sw-b"></i>'+_esc2(opt.a||'انبار')+'</span><span class="legend-item"><i class="sw-a"></i>'+_esc2(opt.b||'کل با درراه/گمرک')+'</span></div>';
 return _chartBox(title,s,opt.q)}
function _stageRows(a){return _topCount(a,['STAGE_FA','ORDER_STAGE_FA','LIFECYCLE_STAGE'])}
function _chart(k,a){const title=CHART_CFG.labels[k]||k,o={q:(CHART_CFG.questions||{})[k]||''};
 if(k==='low_resistance')return _bar(a.map(r=>({k:S(r,'KEY_MATERIAL'),v:parseFloat(S(r,'مقاومت (روز)'))})),title,Object.assign({color:'var(--st-critical)',ink:'var(--st-critical-ink)'},o));
 if(k==='criticality')return _donut(_bandRows(a,['بحرانی (کوتاه)','کد طبقه بحرانی']),title,o);
 if(k==='risk_mix')return _donut(_countBy(a,['طبقه ریسک']),title,o);
 if(k==='org_workload')return _bar(_topCount(a,['ORG_DEPT','ORG_VICE']),title,o);
 if(k==='expert_workload')return _bar(_topCount(a,['CANONICAL_EXPERT']),title,o);
 if(k==='transport_mix')return _donut(_countBy(a,['TRANSPORT_MODE','CL_TRANSPORT_MODE_CODE','MOGH_TRANSPORT_MODE_CODE']),title,o);
 if(k==='stage_distribution')return _bar(_stageRows(a),title,o);
 if(k==='top_orders')return _bar(_topCount(a,['CANONICAL_ORDER','KEY_ORDER']),title,o);
 if(k==='top_bl')return _bar(_topCount(a,['CANONICAL_BL','KEY_BL']),title,o);
 if(k==='supplier_mix')return _bar(_topCount(a,['SUPPLIER','VENDOR_CODE','MFR_VENDOR_CODE']),title,o);
 if(k==='trend_critical')return _trend('متریال بحرانی',title,o);
 if(k==='trend_commitment')return _trend('مانده تعهد معوق',title,o);
 if(k==='trend_resistance')return _trend('میانگین مقاومت',title,o);
 if(k==='sediment_vs_resistance')return _scatter(a,title,'روزهای رسوب','مقاومت (روز)',Object.assign({xlabel:'روزهای رسوب',ylabel:'مقاومت (روز)',key:'KEY_MATERIAL',quad:'رسوب بالا و مقاومت بالا'},o));
 if(k==='delay_vs_commitment')return _scatter(a,title,'روزهای تأخیر','مانده تعهد',Object.assign({xlabel:'روزهای تأخیر',ylabel:'مانده تعهد',key:'CANONICAL_ORDER',quad:'تأخیر و مبلغ، هر دو بالا'},o));
 if(k==='pareto_delay'){const m={};for(const r of a){const d=N(r,'روزهای تأخیر');if(d===null||d<=0)continue;
   let key=S(r,'CANONICAL_ORDER').trim()||S(r,'KEY_REG').trim()||S(r,'CANONICAL_BL').trim();if(!key)continue;m[key]=Math.max(m[key]||0,d)}
  return _pareto(Object.entries(m).map(([k2,v])=>({k:k2,v})),title,o)}
 if(k==='stock_vs_total'){let m=new Map();for(const r of a){let key=S(r,'KEY_MATERIAL').trim();if(!key||m.has(key))continue;let x=parseFloat(S(r,'مقاومت انبار (روز)')),y=parseFloat(S(r,'مقاومت (روز)'));if(Number.isFinite(x)||Number.isFinite(y))m.set(key,{k:key,a:x,b:y})}
  return _grouped([...m.values()].sort((x,y)=>(+x.b||999999)-(+y.b||999999)).slice(0,10),title,Object.assign({a:'مقاومت انبار',b:'کل با درراه/گمرک'},o))}
 if(k==='commitment'){let overdue=a.filter(r=>(parseFloat(S(r,'روزهای تأخیر'))||0)>0),open=a.filter(r=>(parseFloat(S(r,'روزهای تأخیر'))||0)<=0&&(parseFloat(S(r,'مانده تعهد'))||0)>0),closed=a.filter(r=>(parseFloat(S(r,'مانده تعهد'))||0)<=0);
  return _bar([{k:'معوق',v:_sumUnique(overdue,'مانده تعهد',['KEY_REG','CANONICAL_ORDER']),c:'var(--st-critical)',ink:'var(--st-critical-ink)'},
               {k:'در مهلت',v:_sumUnique(open,'مانده تعهد',['KEY_REG','CANONICAL_ORDER']),c:'var(--st-warning)',ink:'var(--st-warning-ink)'},
               {k:'تسویه‌شده',v:_sumUnique(closed,'مانده تعهد',['KEY_REG','CANONICAL_ORDER']),c:'var(--st-good)',ink:'var(--st-good-ink)'}],title,o)}
 if(k==='overdue_bucket'){let bins={'بدون تأخیر':0,'۱ تا ۷ روز':0,'۸ تا ۳۰ روز':0,'۳۱ تا ۶۰ روز':0,'بیش از ۶۰ روز':0};
  a.forEach(r=>{let d=parseFloat(S(r,'روزهای تأخیر'));if(!Number.isFinite(d)||d<=0)bins['بدون تأخیر']++;else if(d<=7)bins['۱ تا ۷ روز']++;else if(d<=30)bins['۸ تا ۳۰ روز']++;else if(d<=60)bins['۳۱ تا ۶۰ روز']++;else bins['بیش از ۶۰ روز']++});
  return _bar(Object.entries(bins).map(([k2,v])=>({k:k2,v})),title,o)}
 if(k==='bottlenecks'){let b=processStats(a).bottlenecks||[];if(b.length)return _bar(b.slice(0,10).map(x=>({k:S(x,'از فعالیت')+' ← '+S(x,'به فعالیت'),v:+x['میانگین روز']||0})),title,Object.assign({color:'var(--st-serious)',ink:'var(--st-serious-ink)'},o));
  let st=_stageRows(a);return _bar(st,title+' — جایگزین: توزیع مرحله فعلی',o)}
 return _chartBox(title,_empty('فیلد لازم برای این نمودار در برش فعلی وجود ندارد.'),o.q)}
function _charts(i,a){let e=document.getElementById('charts_'+i);if(e){e.innerHTML=(CHART_CFG.keys||[]).map(k=>_chart(k,a)).join('');aiblReveal(e)}}
function processStats(a){
 const ev=PROC.eventlog||[];
 const fallback=()=>({bottlenecks:(PROC.bottlenecks||[]).slice().sort((x,y)=>(+y['میانگین روز']||0)-(+x['میانگین روز']||0)),variants:PROC.variants||[],roots:PROC.conformance_root_causes||[]});
 if(!ev.length)return fallback();
 let keys=new Set(); a.forEach(r=>{let k=S(r,'_CASE_KEY')||S(r,'CASE_KEY');if(k)keys.add(k)}); if(!keys.size)return fallback();
 let e=ev.filter(x=>keys.has(S(x,'_CASE_KEY')||S(x,'CASE_KEY'))).slice().sort((x,y)=>{let k=(S(x,'_CASE_KEY')||S(x,'CASE_KEY')).localeCompare(S(y,'_CASE_KEY')||S(y,'CASE_KEY'));return k||new Date(x.EVENTTIME)-new Date(y.EVENTTIME)||(+x._SORTING||0)-(+y._SORTING||0)}), m=new Map(), cm=new Map();
 e.forEach(x=>{let c=S(x,'_CASE_KEY')||S(x,'CASE_KEY'),z=cm.get(c)||[];z.push(x);cm.set(c,z)});
 for(const [c,z] of cm.entries())for(let i=0;i<z.length-1;i++){let d=(new Date(z[i+1].EVENTTIME)-new Date(z[i].EVENTTIME))/86400000;if(!Number.isFinite(d))continue;let k=S(z[i],'ACTIVITY_FA')+'\u0000'+S(z[i+1],'ACTIVITY_FA'),qq=m.get(k)||{from:S(z[i],'ACTIVITY_FA'),to:S(z[i+1],'ACTIVITY_FA'),sum:0,n:0,max:0,waits:[],cases:new Set()};qq.sum+=d;qq.n++;qq.max=Math.max(qq.max,d);qq.waits.push(d);qq.cases.add(c);m.set(k,qq)}
 const med=arr=>{if(!arr.length)return 0;const s=arr.slice().sort((p,q)=>p-q),h=s.length>>1;return s.length%2?s[h]:(s[h-1]+s[h])/2};
 const pct=(arr,p)=>{if(!arr.length)return 0;const s=arr.slice().sort((x,y)=>x-y);return s[Math.min(s.length-1,Math.floor(p*s.length))]};
 let b=[...m.values()].map(z=>({'از فعالیت':z.from,'به فعالیت':z.to,'میانگین روز':z.n?z.sum/z.n:0,'میانه روز':med(z.waits),'صدک ۹۰':pct(z.waits,0.9),'بیشینه روز':z.max,'تعداد':z.n,'تعداد پرونده':z.cases.size,'مجموع روز':z.sum})).sort((x,y)=>(+y['مجموع روز']||0)-(+x['مجموع روز']||0));
 let vm=new Map(),cyc=[];
 for(const [c,z] of cm.entries()){if(!z.length)continue;let variant=z.map(x=>S(x,'ACTIVITY_FA')).join(' ← '),first=new Date(z[0].EVENTTIME),last=new Date(z[z.length-1].EVENTTIME),days=(last-first)/86400000,qq=vm.get(variant)||{n:0,sum:0};qq.n++;if(Number.isFinite(days)){qq.sum+=days;cyc.push(days)}vm.set(variant,qq)}
 let total=cm.size||1,v=[...vm.entries()].map(([k,z])=>({VARIANT:k,'تعداد پرونده':z.n,'میانگین throughput':z.n?z.sum/z.n:0,'سهم (٪)':z.n/total*100})).sort((x,y)=>y['تعداد پرونده']-x['تعداد پرونده']);
 let rework=0;for(const [c,z] of cm.entries()){const seen={};let dup=false;for(const x of z){const k2=S(x,'ACTIVITY_FA');if(seen[k2]){dup=true;break}seen[k2]=1}if(dup)rework++}
 const top5=v.slice(0,5).reduce((s,x)=>s+x['تعداد پرونده'],0);
 const allW=[...m.values()].flatMap(z=>z.waits),cut=med(allW),tot=allW.reduce((s,x)=>s+x,0);
 return {bottlenecks:b,variants:v,roots:PROC.conformance_root_causes||[],
  metrics:{cases:total,cycle_median:med(cyc),cycle_p90:pct(cyc,0.9),rework:rework/total*100,
   concentration:top5/total*100,variants:v.length,
   flow:tot>0?allW.filter(w=>w<=cut).reduce((s,x)=>s+x,0)/tot*100:null}}
}
function _procKpis(mt){if(!mt)return '';
 const items=[['میانه زمان چرخه',fmt(mt.cycle_median)+' روز','نیمی از پرونده‌ها زودتر از این تمام می‌شوند'],
  ['صدک ۹۰ زمان چرخه',fmt(mt.cycle_p90)+' روز','دم بلند توزیع — همان‌جا تعهد می‌سوزد'],
  ['کارایی جریان',mt.flow===null?'—':fmt(mt.flow)+'٪','سهم زمان مؤثر از کل چرخه'],
  ['نرخ دوباره‌کاری',fmt(mt.rework)+'٪','پرونده‌هایی که فعالیتی را تکرار کرده‌اند'],
  ['تمرکز واریانت',fmt(mt.concentration)+'٪','سهم ۵ مسیر پرتکرار از کل پرونده‌ها'],
  ['تنوع مسیر',fmt(mt.variants)+' مسیر','هرچه بیشتر، فرآیند کمتر استاندارد است']];
 return '<div class="kpistrip">'+items.map((x,i)=>'<div class="kpi reveal" style="--i:'+i+'"><div class="l">'+x[0]+'</div><b>'+x[1]+'</b><div class="g">'+x[2]+'</div></div>').join('')+'</div>'}
function _process(a){
 const ps=processStats(a||[]),e=document.getElementById('process_map'),b=ps.bottlenecks||[],t=document.getElementById('process_bottlenecks'),v=ps.variants||[],rc=ps.roots||[];
 if(!e)return;
 const kp=document.getElementById('process_kpis');if(kp){kp.innerHTML=_procKpis(ps.metrics);aiblReveal(kp)}
 if(!b.length){let st=_stageRows(a);e.innerHTML=st.length?_bar(st,'نقطه شروع فرآیند — توزیع مرحله فعلی',{q:'پرونده‌ها اکنون در کدام مرحله متوقف‌اند؟'}):_empty('لاگ تاریخی برای اندازه‌گیری گذارها هنوز کافی نیست. با اجرای روزانه Warehouse، Transition Log به‌تدریج ساخته می‌شود.');if(t)t.innerHTML='<div class="note">تا زمانی که Event Log کافی شود، توزیع مرحله فعلی به‌عنوان نمای جایگزین نمایش داده می‌شود و هیچ گلوگاه فرضی ساخته نمی‌شود.</div>'}
 else{
  let r=b.slice(0,10);
  let max=Math.max(...r.map(x=>+x['میانه روز']||+x['میانگین روز']||0),1),W=980,L=252,R=86,T=18,B=26,RH=26,GAP=16;
  let H=T+B+r.length*(RH+GAP),plot=W-L-R,g='';
  ticks(0,max,4).forEach(tv=>{const x=L+tv/max*plot;g+='<line x1="'+x+'" y1="'+T+'" x2="'+x+'" y2="'+(H-B)+'" class="grid"></line><text x="'+x+'" y="'+(H-B+16)+'" text-anchor="middle" class="tick">'+fmtShort(tv)+'</text>'});
  let svg='<svg viewBox="0 0 '+W+' '+H+'" class="proc-svg" role="img" aria-label="گلوگاه فرآیند" preserveAspectRatio="xMidYMid meet">'+g;
  r.forEach((x,i)=>{const y=T+i*(RH+GAP),val=+x['میانه روز']||+x['میانگین روز']||0,w=Math.max(4,val/max*plot),p90=+x['صدک ۹۰']||0,w9=Math.min(plot,p90/max*plot);
   if(p90>val)svg+='<rect x="'+L+'" y="'+(y+RH*0.28)+'" width="'+w9+'" height="'+(RH*0.44)+'" rx="3" class="p90-bar"><title>صدک ۹۰: '+fmt(p90)+' روز</title></rect>';
   svg+='<text x="'+(L-12)+'" y="'+(y+RH*0.72)+'" class="chart-label">'+_esc2(S(x,'از فعالیت')+' ← '+S(x,'به فعالیت'))+'</text>'
    +'<rect x="'+L+'" y="'+y+'" width="'+w+'" height="'+RH+'" rx="5" class="proc-bar" style="--i:'+i+'"><title>میانه '+fmt(val)+' روز روی '+fmt(x['تعداد پرونده'])+' پرونده</title></rect>'
    +'<text x="'+(L+Math.max(w,w9)+8)+'" y="'+(y+RH*0.72)+'" class="chart-value">'+fmt(val)+' روز</text>'});
  e.innerHTML=svg+'<line x1="'+L+'" y1="'+(H-B)+'" x2="'+(W-R)+'" y2="'+(H-B)+'" class="axis"></line></svg><div class="chartfoot"><span class="legend-item"><i class="sw-a"></i>میانه انتظار</span><span class="legend-item"><i class="sw-p90"></i>صدک ۹۰</span><span class="stat">مرتب‌شده بر مجموع زمان تلف‌شده، نه بر میانگین تکی</span></div>';
  t.innerHTML='<table class="proc-table"><thead><tr><th>از</th><th>به</th><th>میانه انتظار</th><th>صدک ۹۰</th><th>پرونده</th><th>مجموع روز</th></tr></thead><tbody>'+r.map(x=>'<tr><td>'+_esc2(S(x,'از فعالیت'))+'</td><td>'+_esc2(S(x,'به فعالیت'))+'</td><td>'+fmt(x['میانه روز']||x['میانگین روز'])+'</td><td>'+fmt(x['صدک ۹۰'])+'</td><td>'+fmt(x['تعداد پرونده'])+'</td><td>'+fmt(x['مجموع روز'])+'</td></tr>').join('')+'</tbody></table>'
 }
 const pv=document.getElementById('process_variants'); if(pv)pv.innerHTML=v.length?'<h4>واریانت‌های پرتکرار</h4><div class="note">سهم کم ۵ مسیر نخست یعنی فرآیند عملاً هر بار از نو اجرا می‌شود.</div><table class="proc-table"><thead><tr><th>مسیر</th><th>پرونده</th><th>سهم</th><th>میانگین چرخه</th></tr></thead><tbody>'+v.slice(0,12).map(x=>'<tr><td class="pathcell">'+_esc2(S(x,'VARIANT'))+'</td><td>'+fmt(x['تعداد پرونده'])+'</td><td>'+fmt(x['سهم (٪)'])+'٪</td><td>'+fmt(x['میانگین throughput'])+' روز</td></tr>').join('')+'</tbody></table>':'';
 const pr=document.getElementById('process_roots'); if(pr)pr.innerHTML=rc.length?'<h4>محرک‌های انحراف / ریشه‌یابی</h4>'+_bar(rc.slice(0,8).map(x=>({k:S(x,'بُعد'),v:+x['اثر تفاضلی (واحد درصد)']||0})),'اثر تفاضلی (واحد درصد)',{q:'کدام ویژگی بیشترین همبستگی را با انحراف دارد؟'}):''
}
function crc32(bytes){let t=window._crcTable;if(!t){t=[];for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=(c&1)?0xEDB88320^(c>>>1):c>>>1;t[n]=c>>>0}window._crcTable=t}let c=0xFFFFFFFF;for(const b of bytes)c=t[(c^b)&255]^(c>>>8);return (c^0xFFFFFFFF)>>>0}
const u8=s=>new TextEncoder().encode(s);
function zipStore(files){let chunks=[],central=[],offset=0;for(const [name,data] of files){let nb=u8(name),db=typeof data==='string'?u8(data):data,crc=crc32(db),head=new Uint8Array(30+nb.length);let dv=new DataView(head.buffer);dv.setUint32(0,0x04034b50,true);dv.setUint16(4,20,true);dv.setUint16(6,0,true);dv.setUint16(8,0,true);dv.setUint16(10,0,true);dv.setUint16(12,0,true);dv.setUint32(14,crc,true);dv.setUint32(18,db.length,true);dv.setUint32(22,db.length,true);dv.setUint16(26,nb.length,true);dv.setUint16(28,0,true);head.set(nb,30);chunks.push(head,db);let cd=new Uint8Array(46+nb.length),cv=new DataView(cd.buffer);cv.setUint32(0,0x02014b50,true);cv.setUint16(4,20,true);cv.setUint16(6,20,true);cv.setUint16(8,0,true);cv.setUint16(10,0,true);cv.setUint16(12,0,true);cv.setUint16(14,0,true);cv.setUint32(16,crc,true);cv.setUint32(20,db.length,true);cv.setUint32(24,db.length,true);cv.setUint16(28,nb.length,true);cv.setUint16(30,0,true);cv.setUint16(32,0,true);cv.setUint16(34,0,true);cv.setUint16(36,0,true);cv.setUint32(38,0,true);cv.setUint32(42,offset,true);cd.set(nb,46);central.push(cd);offset+=head.length+db.length}let csize=central.reduce((s,x)=>s+x.length,0),end=new Uint8Array(22),ed=new DataView(end.buffer);ed.setUint32(0,0x06054b50,true);ed.setUint16(8,files.length,true);ed.setUint16(10,files.length,true);ed.setUint32(12,csize,true);ed.setUint32(16,offset,true);let all=chunks.concat(central,[end]);return new Blob(all,{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})}
function xmlEsc(s){return String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&apos;')}
function colName(n){let s='';while(n){let r=(n-1)%26;s=String.fromCharCode(65+r)+s;n=Math.floor((n-1)/26)}return s}
function excelSerial(v){let d=new Date(v);if(!Number.isFinite(+d))return null;return (+d-Date.UTC(1899,11,30))/86400000}
function cellXml(v,ref,header=false){if(header)return '<c r="'+ref+'" s="1" t="inlineStr"><is><t>'+xmlEsc(v)+'</t></is></c>';if(typeof v==='number'&&Number.isFinite(v))return '<c r="'+ref+'" s="2"><v>'+v+'</v></c>';if(typeof v==='boolean')return '<c r="'+ref+'" t="b"><v>'+(v?1:0)+'</v></c>';if(typeof v==='string'&&/^\d{4}-\d{2}-\d{2}(?:[T ][0-9:.+-Z]+)?$/.test(v)){let n=excelSerial(v);if(n!==null)return '<c r="'+ref+'" s="3"><v>'+n+'</v></c>'}return '<c r="'+ref+'" t="inlineStr"><is><t>'+xmlEsc(v)+'</t></is></c>'}
function makeXlsx(rows,fields,sheet='داده فیلترشده'){let safe=String(sheet||'Data').replace(/[\\/*?:\[\]]/g,' ').slice(0,31)||'Data',head=fields.map((c,i)=>cellXml(LABELS[c]||c,colName(i+1)+'1',true)).join(''),body=rows.map((r,i)=>'<row r="'+(i+2)+'">'+fields.map((c,j)=>cellXml(V(r,c),colName(j+1)+(i+2))).join('')+'</row>').join(''),last=colName(Math.max(fields.length,1))+(rows.length+1);let sh='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:'+last+'"/><sheetViews><sheetView workbookViewId="0" rightToLeft="1"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData><row r="1">'+head+'</row>'+body+'</sheetData><autoFilter ref="A1:'+last+'"/></worksheet>';let wb='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="'+xmlEsc(safe)+'" sheetId="1" r:id="rId1"/></sheets></workbook>';let styles='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-mm-dd hh:mm"/></numFmts><fonts count="2"><font><sz val="11"/><name val="IRANSans"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="IRANSans"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0A4F4F"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment horizontal="right"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"><alignment horizontal="right"/></xf><xf numFmtId="4" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"><alignment horizontal="right"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"><alignment horizontal="right"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';let rel='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>';let wrel='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>';let ct='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>';return zipStore([['[Content_Types].xml',ct],['_rels/.rels',rel],['xl/workbook.xml',wb],['xl/_rels/workbook.xml.rels',wrel],['xl/styles.xml',styles],['xl/worksheets/sheet1.xml',sh]])}
function downloadFilteredXlsx(){let t=TAB_META[active],a=rows(t);let blob=makeXlsx(a,t.fields,t.title),url=URL.createObjectURL(blob),x=document.createElement('a');x.href=url;x.download='AIBL_filtered_'+(REPORT_META.ref_date||new Date().toISOString().slice(0,10))+'.xlsx';x.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function exportPdf(){window.print()}
/* ── روایت این برش: وضعیت ← گره ← اقدام، با یافته‌های کمّی ── */
function sliceStory(a,i){
 const t=TAB_META[i],full=(STORY.findings||[]);
 const bandOf=r=>S(r,'بحرانی (کوتاه)')||S(r,'کد طبقه بحرانی');
 const crit=a.filter(r=>['توقف خط','بحرانی','STOCKOUT','CRITICAL'].includes(bandOf(r)));
 const mats=new Set(),critMats=new Set();
 for(const r of a){const m=S(r,'KEY_MATERIAL').trim();if(m)mats.add(m)}
 for(const r of crit){const m=S(r,'KEY_MATERIAL').trim();if(m)critMats.add(m)}
 const rs=a.map(r=>N(r,'مقاومت (روز)')).filter(v=>v!==null).sort((x,y)=>x-y);
 const median=rs.length?(rs.length%2?rs[rs.length>>1]:(rs[(rs.length>>1)-1]+rs[rs.length>>1])/2):null;
 const d=dstate(i),win=(d.col&&(d.from||d.to))?(' بازه «'+_esc2(d.from||'ابتدا')+' تا '+_esc2(d.to||'انتها')+'» روی «'+_esc2(LABELS[d.col]||d.col)+'» فعال است.'):'';
 let situation='روایت این برش: '+fmt(a.length)+' ردیف'+(mats.size?('، '+fmt(mats.size)+' قطعه یکتا'):'')+' در نما است.'+win;
 const nCrit=critMats.size||crit.length;
 let complication=nCrit?(fmt(nCrit)+(critMats.size?' قطعه':' ردیف')+' در وضعیت بحرانی یا توقف خط است'+(mats.size?(' — '+(nCrit/mats.size*100).toFixed(1)+'٪ از قطعات این برش'):'')+'.')
   :'هیچ قطعه بحرانی در این برش نیست.';
 if(median!==null)complication+=' میانه مقاومت '+fmt(median)+' روز است (میانه، نه میانگین — توزیع راست‌چوله است).';
 const ps=processStats(a),bn=(ps.bottlenecks||[])[0];
 let resolution;
 if(nCrit){const worst=a.filter(r=>N(r,'مقاومت (روز)')!==null).sort((x,y)=>N(x,'مقاومت (روز)')-N(y,'مقاومت (روز)'))[0];
  resolution='پیگیری امروز از کم‌مقاومت‌ترین قطعه شروع شود'+(worst?(': '+_esc2(S(worst,'KEY_MATERIAL'))):'')+'.'}
 else resolution='این برش اقدام فوری نمی‌خواهد؛ ظرفیت پیگیری را صرف تعهد معوق یا گلوگاه کنید.';
 if(bn)resolution+=' بزرگ‌ترین گلوگاه «'+_esc2(S(bn,'از فعالیت'))+' ← '+_esc2(S(bn,'به فعالیت'))+'» با میانه '+fmt(bn['میانه روز']||bn['میانگین روز'])+' روز انتظار است.';
 else resolution+=' لاگ گذار هنوز برای محاسبه گلوگاه کافی نیست؛ توزیع مرحله فعلی نقطه شروع است.';
 const head=document.getElementById('story_headline');
 if(head)head.textContent=nCrit?('ریسک توقف خط: '+fmt(nCrit)+(critMats.size?' قطعه':' ردیف')+' بحرانی در این برش'):(STORY.headline||'هیچ ریسک فعالی در این برش دیده نمی‌شود.');
 const set=(id,v)=>{const el=document.getElementById(id);if(el)el.innerHTML=v};
 set('story_situation',situation);set('story_complication',complication);set('story_resolution',resolution);
 const box=document.getElementById('story_findings');
 if(box){box.innerHTML=full.map((f,j)=>'<article class="finding reveal" style="--i:'+j+';--tone:'+_esc2(f.color||'var(--t2)')+'">'
  +'<h5>'+_esc2(f.headline)+'</h5><p class="mag">'+_esc2(f.magnitude)+'</p>'
  +'<p class="cmp">'+_esc2(f.comparison)+'</p><p class="sow"><span aria-hidden="true">←</span> '+_esc2(f.so_what)+'</p></article>').join('');
  aiblReveal(box)}
}
const PAGE_SIZE=100, PAGE={};
function pageMove(i,delta){PAGE[i]=Math.max(0,(PAGE[i]||0)+delta);render(i)}
function dateBounds(col){let lo='',hi='';for(const r of DATA){const v=dateOf(r,col);if(!v)continue;if(!lo||v<lo)lo=v;if(!hi||v>hi)hi=v}return [lo,hi]}
function datePreset(i,days){const t=TAB_META[i];if(!t.dates||!t.dates.length)return;
 const d=dstate(i),sel=document.querySelector('.datecol[data-pane="'+t.id+'"]');
 d.col=(sel&&sel.value)||t.dates[0];
 const box=q0=>document.querySelector(q0+'[data-pane="'+t.id+'"]');
 const f=box('.dfrom'),to=box('.dto');
 if(!days){d.from='';d.to='';if(f)f.value='';if(to)to.value=''}
 else{const [lo,hi]=dateBounds(d.col);if(!hi)return;
  const end=new Date(hi+'T00:00:00Z'),start=new Date(end.getTime()-days*86400000);
  let s=start.toISOString().slice(0,10);if(lo&&s<lo)s=lo;
  d.from=s;d.to=hi;if(f)f.value=s;if(to)to.value=hi}
 PAGE[i]=0;render(i)}
function syncDates(i){const t=TAB_META[i];if(!t.dates||!t.dates.length)return;
 const d=dstate(i),g=s=>document.querySelector(s+'[data-pane="'+t.id+'"]');
 const sel=g('.datecol'),f=g('.dfrom'),to=g('.dto');
 d.col=(sel&&sel.value)||t.dates[0];d.from=(f&&f.value)||'';d.to=(to&&to.value)||''}
function dateNote(i,a){const el=document.getElementById('drnote_'+i);if(!el)return;
 const d=dstate(i);if(!d.col){el.textContent='';return}
 const [lo,hi]=dateBounds(d.col);
 el.textContent=(d.from||d.to)
  ? ('بازه فعال: '+(d.from||'ابتدا')+' تا '+(d.to||'انتها')+' — '+a.length.toLocaleString('fa-IR')+' ردیف')
  : ('کل بازه موجود: '+(lo||'—')+' تا '+(hi||'—'));}
function render(i){const t=TAB_META[i];syncDates(i);const a=rows(t);sliceStory(a,i);dateNote(i,a);
 const cards=[{l:'ردیف',v:a.length.toLocaleString('fa-IR'),g:''}];
 Object.keys(t.agg).slice(0,4).forEach(c=>cards.push({l:(t.agg[c]==='mean'?'میانگین ':'جمع ')+(LABELS[c]||c),v:fmt(gagg(a,c,t.grain,t.agg)),g:t.grain[c]?('یکتا بر '+t.grain[c]):'دانه ردیف'}));
 let pages=Math.max(1,Math.ceil(a.length/PAGE_SIZE));PAGE[i]=Math.min(PAGE[i]||0,pages-1);
 let start=PAGE[i]*PAGE_SIZE,view=a.slice(start,start+PAGE_SIZE);
 document.getElementById('cnt_'+i).textContent=a.length.toLocaleString('fa-IR')+' ردیف · صفحه '+(PAGE[i]+1).toLocaleString('fa-IR')+' از '+pages.toLocaleString('fa-IR');
 const cbox=document.getElementById('cards_'+i);
 cbox.innerHTML=cards.map((x,j)=>'<div class="card reveal" style="--i:'+j+'"><div class="l">'+x.l+'</div><b>'+x.v+'</b><div class="g">'+x.g+'</div></div>').join('');aiblReveal(cbox);
 const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
 let tb=document.getElementById('tb_'+i);if(tb)tb.innerHTML=view.map(r=>'<tr>'+t.fields.map(c=>'<td>'+esc(S(r,c))+'</td>').join('')+'</tr>').join('');
 let pg=document.getElementById('pager_'+i);if(pg)pg.innerHTML='<button '+(PAGE[i]<=0?'disabled':'')+' onclick="pageMove('+i+',-1)">صفحه قبل</button><span>نمایش '+Math.min(start+1,a.length).toLocaleString('fa-IR')+' تا '+Math.min(start+PAGE_SIZE,a.length).toLocaleString('fa-IR')+' از '+a.length.toLocaleString('fa-IR')+'</span><button '+(PAGE[i]>=pages-1?'disabled':'')+' onclick="pageMove('+i+',1)">صفحه بعد</button>';
 _charts(i,a);_process(a);aiblReveal()}
function gvals(a,c,grain){const k=grain[c],seen=new Set(),out=[];for(const r of a){if(k){const key=S(r,k).trim();if(key){if(seen.has(key))continue;seen.add(key)}}const v=parseFloat(S(r,c));if(Number.isFinite(v))out.push(v)}return out}
function gagg(a,c,grain,agg){const v=gvals(a,c,grain);if(!v.length)return 0;if(agg[c]==='mean')return v.reduce((s,x)=>s+x,0)/v.length;return v.reduce((s,x)=>s+x,0)}
function activate(i){active=i;PAGE[i]=0;document.querySelectorAll('.tabbtn').forEach((b,j)=>{b.classList.toggle('active',j===i);b.setAttribute('aria-selected',j===i)});document.querySelectorAll('.pane').forEach((p,j)=>p.style.display=j===i?'block':'none');q.value='';render(i)}
document.querySelectorAll('.tabbtn').forEach((b,i)=>b.addEventListener('click',()=>activate(i)));
q.addEventListener('input',()=>{PAGE[active]=0;render(active)});
document.querySelectorAll('select,input[type=date]').forEach(s=>s.addEventListener('change',()=>{PAGE[active]=0;render(active)}));
render(0);
</script>"""
    for token, value in (("__CHART_CFG__", chart_json), ("__PROC__", proc_json),
                         ("__STORY__", story_json), ("__BAND_INK__", band_ink_json),
                         ("__BAND_FILL__", band_fill_json), ("__SERIES__", series_json),
                         ("__DATE_COLS__", json.dumps(date_cols, ensure_ascii=False))):
        dynamic_js = dynamic_js.replace(token, value)

    trunc_note = (f'<div class="payload-note">طبق سقف ردیف انتخاب‌شده در گزارش، {safe_cap:,} ردیف از {len(df):,} ردیف وارد Artifact شده است. این محدودیت انتخاب کاربر/قالب است و هیچ کاهش خودکار بر اساس حجم یا تعداد ستون اعمال نشده است.</div>' if payload_truncated else '')
    process_panel = (
        '<div class="panel process-panel reveal"><div class="panel-head"><h3>⛓ Process Explorer — روایت فرآیند</h3></div>'
        '<div class="note">این نما با فیلتر فعال دوباره محاسبه می‌شود؛ در صورت وجود CASE_KEY فقط پرونده‌های همان برش لحاظ می‌شوند. '
        'معیارها بر میانه و صدک ۹۰ بنا شده‌اند، نه میانگین — توزیع زمان انتظار در زنجیره تأمین راست‌چوله است.</div>'
        '<div id="process_kpis"></div>'
        '<div id="process_map" class="process-map"></div><div id="process_bottlenecks"></div>'
        '<div id="process_variants" class="subpanel"></div><div id="process_roots" class="subpanel"></div>'
        '<div class="process-actions"><button class="export-btn" onclick="downloadFilteredXlsx()">⬇ استخراج داده فیلترشده (Excel)</button>'
        '<button class="export-btn secondary" onclick="exportPdf()">🖨 PDF / چاپ</button></div></div>'
        if show_process else '<div id="process_kpis" style="display:none"></div><div id="process_map" style="display:none"></div><div id="process_bottlenecks" style="display:none"></div><div id="process_variants" style="display:none"></div><div id="process_roots" style="display:none"></div>')

    status_vars = "".join(f"--st-{s.key}:{s.fill};--st-{s.key}-ink:{s.ink};--st-{s.key}-wash:{s.wash};"
                          for s in ds.STATUS_SCALE)
    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{--deep:{ds.BRAND_DEEP};--accent:{ds.BRAND};--brand-ink:{ds.BRAND_INK};--link:{ds.ACCENT_INK};
--text:{ds.TEXT};--t2:{ds.TEXT_SECONDARY};--t3:{ds.TEXT_MUTED};--border:{ds.BORDER};--border-2:{ds.BORDER_STRONG};
--raised:{ds.SURFACE_RAISED};--surface:{ds.SURFACE};--sunken:{ds.SURFACE_SUNKEN};{status_vars}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--surface);color:var(--text);font-family:'IRANSans','IRANSans Light',Tahoma,Arial,sans-serif;direction:rtl;-webkit-font-smoothing:antialiased;line-height:1.75}}
.shell{{max-width:1500px;margin:auto;padding:20px 18px 48px}}
/* ── هدر ── */
header{{background:linear-gradient(135deg,var(--deep) 0%,#0b5a58 58%,var(--accent) 100%);color:#fff;border-radius:18px;padding:22px 24px;display:flex;gap:20px;justify-content:space-between;align-items:center;flex-wrap:wrap;box-shadow:0 12px 34px rgba(8,64,63,.16)}}
.eyebrow{{font-size:11px;letter-spacing:.9px;opacity:.86;margin-bottom:6px}}
h1{{margin:0;font-size:25px;font-weight:800;letter-spacing:-.2px}}
.sub{{font-size:12.5px;opacity:.92;margin-top:7px}}
.stats{{display:flex;gap:10px;flex-wrap:wrap}}
.hstat{{display:flex;flex-direction:column;align-items:center;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.26);border-radius:12px;padding:9px 15px;font-size:11px;min-width:92px}}
.hstat b{{font-size:20px;font-weight:800;line-height:1.25}}
header button{{background:#fff;color:var(--deep);border:0;border-radius:11px;padding:10px 16px;font-family:inherit;font-weight:800;cursor:pointer}}
/* ── زنجیره و راهنما ── */
.supply-chain{{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:16px 0 6px}}
.supply-step{{background:var(--raised);border:1px solid var(--border);color:var(--brand-ink);padding:6px 12px;border-radius:999px;font-size:11.5px;font-weight:700}}
.supply-arrow{{color:var(--t3)}}
.bandlegend{{display:flex;gap:14px;flex-wrap:wrap;padding:10px 2px;font-size:11.5px}}
.lg{{display:inline-flex;align-items:center;gap:6px;color:var(--c);font-weight:700}}
.lg i{{font-style:normal;width:17px;height:17px;display:inline-grid;place-items:center;border-radius:5px;background:var(--f);color:#fff;font-size:10px;line-height:1}}
/* ── تب ── */
.tabbar{{display:flex;gap:7px;overflow:auto;padding:10px 0;border-bottom:1px solid var(--border)}}
.tabbtn{{border:1px solid var(--border);background:var(--raised);color:var(--brand-ink);border-radius:11px;padding:10px 17px;white-space:nowrap;font-family:inherit;font-weight:700;cursor:pointer}}
.tabbtn:hover{{border-color:var(--accent)}} .tabbtn.active{{background:var(--deep);color:#fff;border-color:var(--deep)}}
/* ── روایت ── */
.story{{background:var(--raised);border:1px solid var(--border);border-top:4px solid var(--accent);border-radius:16px;padding:20px 22px;margin:16px 0;box-shadow:0 8px 24px rgba(8,64,63,.06)}}
.story .eyebrow{{color:var(--brand-ink);font-weight:800;opacity:1}}
.story h2{{margin:2px 0 14px;font-size:20px;color:var(--text);line-height:1.6}}
.story-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}}
.scr{{background:var(--sunken);border-radius:12px;padding:13px 15px}}
.scr b{{display:block;font-size:11px;letter-spacing:.4px;color:var(--brand-ink);margin-bottom:5px}}
.scr p{{margin:0;font-size:13px;color:var(--t2)}}
.findings{{display:grid;grid-template-columns:repeat(auto-fit,minmax(272px,1fr));gap:12px;margin-top:14px}}
.finding{{background:var(--raised);border:1px solid var(--border);border-right:4px solid var(--tone);border-radius:12px;padding:13px 15px}}
.finding h5{{margin:0 0 6px;font-size:12px;color:var(--tone);font-weight:800;letter-spacing:.2px}}
.finding .mag{{margin:0 0 5px;font-size:14px;font-weight:700;color:var(--text)}}
.finding .cmp{{margin:0 0 7px;font-size:11.5px;color:var(--t3)}}
.finding .sow{{margin:0;font-size:12px;color:var(--t2);border-top:1px dashed var(--border);padding-top:7px}}
.finding .sow span{{color:var(--tone);font-weight:800}}
/* ── ابزار و فیلتر ── */
.toolbar{{display:flex;align-items:end;gap:12px;flex-wrap:wrap;background:var(--raised);border:1px solid var(--border);border-radius:14px;padding:13px;margin:14px 0}}
label{{font-size:12px;color:var(--t2);min-width:150px}}
input,select{{width:100%;margin-top:5px;padding:9px 10px;border:1px solid var(--border-2);border-radius:9px;background:#fff;font:inherit;color:var(--text)}}
input:focus,select:focus{{outline:2px solid var(--accent);outline-offset:1px;border-color:var(--accent)}}
.daterange{{background:var(--raised);border:1px solid var(--border);border-radius:14px;padding:13px 15px;margin:0 0 14px;display:grid;gap:10px}}
.dr-head{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.dr-title{{font-size:12px;font-weight:800;color:var(--brand-ink)}}
.dr-head select{{width:auto;min-width:190px;margin-top:0}}
.datecol-name{{font-size:12px;color:var(--t3);background:var(--sunken);border-radius:7px;padding:4px 9px}}
.dr-inputs{{display:flex;gap:12px;flex-wrap:wrap}} .dr-inputs label{{min-width:170px}}
.dr-chips{{display:flex;gap:7px;flex-wrap:wrap}}
.chip{{border:1px solid var(--border-2);background:var(--raised);color:var(--brand-ink);border-radius:999px;padding:6px 14px;font-family:inherit;font-size:11.5px;font-weight:700;cursor:pointer;transition:background-color var(--dur-micro,140ms),border-color var(--dur-micro,140ms),color var(--dur-micro,140ms)}}
.chip:hover{{background:var(--deep);border-color:var(--deep);color:#fff}}
.chip.ghost{{color:var(--t3)}} .dr-note{{font-size:11.5px;color:var(--t3)}}
/* ── کارت KPI ── */
.cards,.kpistrip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin:14px 0}}
.card,.kpi{{background:var(--raised);border:1px solid var(--border);border-radius:14px;padding:14px 15px}}
.card .l,.kpi .l{{font-size:11.5px;color:var(--t2)}}
.card b,.kpi b{{display:block;font-size:23px;font-weight:800;margin-top:4px;letter-spacing:-.3px}}
.card .g,.kpi .g{{font-size:11px;color:var(--t3);margin-top:4px}}
/* ── پنل و جدول ── */
.panel,.subpanel{{background:var(--raised);border:1px solid var(--border);border-radius:16px;padding:17px;margin-top:14px}}
.subpanel:empty{{display:none}}
.panel-head{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px}}
.panel h3{{margin:0;font-size:15.5px;color:var(--text)}} .panel h4{{margin:0 0 9px;font-size:13.5px;color:var(--brand-ink)}}
.tablewrap{{max-height:640px;overflow:auto;border:1px solid var(--border);border-radius:11px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{position:sticky;top:0;background:var(--deep);color:#fff;padding:10px;white-space:nowrap;text-align:right;font-weight:700;z-index:1}}
td{{padding:8px 10px;border-bottom:1px solid var(--border);white-space:nowrap;color:var(--t2)}}
tbody tr:nth-child(even) td{{background:#fbfcfc}} tbody tr:hover td{{background:var(--sunken);color:var(--text)}}
.proc-table{{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px}}
.proc-table th{{position:static;padding:9px}} .proc-table td{{padding:8px;white-space:normal}}
.pathcell{{max-width:520px;font-size:11.5px;color:var(--t3)}}
/* ── نمودار ── */
.chartgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:13px;margin:14px 0}}
.chartbox{{background:var(--raised);border:1px solid var(--border);border-radius:16px;padding:15px 16px;margin:0;display:flex;flex-direction:column}}
.chartbox figcaption{{margin-bottom:10px}}
.chartbox h4{{margin:0;font-size:14px;color:var(--text);font-weight:800}}
.chartbox .ask{{display:block;font-size:11.5px;color:var(--t3);margin-top:3px}}
.chartbox svg{{width:100%;height:auto;display:block}}
svg text{{direction:ltr;unicode-bidi:plaintext}}   /* ← اصلاح ۲۶٫۱۹: بدون این، برچسب RTL زیر میله می‌رفت */
.chart-label{{font:600 11.5px 'IRANSans','IRANSans Light',Tahoma,Arial;fill:var(--t2);text-anchor:end}}
.chart-value{{font:800 11.5px 'IRANSans','IRANSans Light',Tahoma;fill:var(--brand-ink);text-anchor:start}}
.tick{{font:11px 'IRANSans',Tahoma,Arial;fill:var(--t3)}}
.tick-cat{{font-size:10px}}
.axis-title{{font:700 11.5px 'IRANSans',Tahoma;fill:var(--t2)}}
.grid{{stroke:var(--border);stroke-width:1;shape-rendering:crispEdges}}
.axis{{stroke:var(--border-2);stroke-width:1.2}}
.median{{stroke:var(--t3);stroke-width:1;stroke-dasharray:5 4;opacity:.75}}
.ref80{{stroke:var(--st-serious-ink);stroke-width:1.2;stroke-dasharray:6 4}}
.quad{{fill:var(--st-critical);opacity:.07}}
.chart-bar{{fill:var(--accent);stroke:var(--deep);stroke-width:.9}}
.chart-bar.series-a{{fill:var(--accent);stroke:var(--deep)}} .chart-bar.series-b{{fill:#95a5a6;stroke:#4c5a5a}}
.pareto-bar{{fill:var(--accent);stroke:var(--deep);stroke-width:.9;transform-origin:center bottom;animation:aibl-grow-y var(--dur-medium,420ms) var(--ease-entrance,cubic-bezier(.22,1,.36,1)) both;animation-delay:calc(var(--i,0) * var(--stagger,55ms))}}
@keyframes aibl-grow-y{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
.proc-bar{{fill:var(--accent);stroke:var(--deep);stroke-width:.9}}
.p90-bar{{fill:var(--accent);opacity:.2}}
.slice{{stroke:#fff;stroke-width:2}}
.dot{{fill:var(--accent);opacity:.8;stroke:#fff;stroke-width:.8}}
.trend-line{{stroke:var(--deep);stroke-width:2.4;fill:none;stroke-linecap:round;stroke-linejoin:round}}
.trend-area{{fill:var(--accent);opacity:.12}}
.trend-dot{{fill:var(--deep);stroke:#fff;stroke-width:2}}
.chartfoot{{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:9px;padding-top:9px;border-top:1px solid var(--border);font-size:11.5px;color:var(--t3)}}
.stat{{color:var(--t3)}} .quadmark::before{{content:'';display:inline-block;width:11px;height:11px;border-radius:3px;background:var(--st-critical);opacity:.22;margin-left:6px;vertical-align:-1px}}
.delta{{font-weight:800;border-radius:999px;padding:3px 11px}}
.delta.good{{color:var(--st-good-ink);background:var(--st-good-wash)}}
.delta.bad{{color:var(--st-critical-ink);background:var(--st-critical-wash)}}
.delta.flat{{color:var(--t2);background:var(--sunken)}}
.legend{{display:flex;flex-direction:column;gap:2px}}
.legend-item{{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--t2)}}
.legend-item i{{width:11px;height:11px;border-radius:3px;display:inline-block;flex:none}}
.legend-item .lk{{flex:1}} .legend-item b{{color:var(--text)}} .legend-item .lp{{color:var(--t3);min-width:34px;text-align:left}}
.sw-a{{background:var(--accent)}} .sw-b{{background:#95a5a6}} .sw-p90{{background:var(--accent);opacity:.3}}
.donut-wrap{{display:flex;gap:26px;align-items:center;justify-content:center;flex-wrap:wrap}}
.donut-wrap svg{{max-width:248px}}
.donut-total{{font:800 25px 'IRANSans',Tahoma;fill:var(--deep)}} .donut-sub{{font:11px 'IRANSans',Tahoma;fill:var(--t3)}}
.emptybox{{display:flex;gap:10px;align-items:center;justify-content:center;min-height:120px;background:var(--sunken);border-radius:12px;padding:18px;text-align:center}}
.emptymark{{font-size:20px;color:var(--t3)}} .emptybox p{{margin:0;font-size:12px;color:var(--t3);max-width:46ch}}
.process-map{{overflow:auto;padding:14px;background:var(--sunken);border-radius:13px;margin-top:10px}}
.proc-svg{{min-width:760px}}
.note{{font-size:11.5px;color:var(--t3);margin-top:6px}}
.export-btn{{border:0;border-radius:11px;padding:10px 16px;background:var(--deep);color:#fff;font-family:inherit;font-weight:800;cursor:pointer}}
.export-btn.secondary{{background:var(--raised);color:var(--brand-ink);border:1px solid var(--border-2)}}
.process-actions{{display:flex;gap:9px;margin-top:14px;flex-wrap:wrap}}
.pager{{display:flex;justify-content:center;align-items:center;gap:12px;padding:12px;font-size:12px;color:var(--t2)}}
.pager button{{border:1px solid var(--border-2);background:var(--raised);color:var(--brand-ink);border-radius:9px;padding:7px 13px;font-family:inherit;cursor:pointer}}
.pager button:disabled{{opacity:.4;cursor:default}}
.payload-note{{margin:14px 0;padding:11px 15px;border:1px solid var(--st-warning);border-right:4px solid var(--st-warning-ink);background:var(--st-warning-wash);border-radius:11px;font-size:12px;color:var(--st-warning-ink)}}
{ds.motion_css()}
@media print{{
 .tabbar,.toolbar,.daterange,.pager,header button,.process-actions{{display:none!important}}
 body{{background:#fff}} .panel,.chartbox,.story,.card,.kpi{{box-shadow:none;break-inside:avoid}}
 .chartgrid{{grid-template-columns:repeat(2,1fr)}}
}}
@media (max-width:640px){{
 .shell{{padding:12px 12px 32px}} header{{padding:16px}} h1{{font-size:20px}}
 .chartgrid{{grid-template-columns:1fr}} .donut-wrap{{gap:14px}}
}}
</style></head><body><div class="shell">
<header><div><div class="eyebrow">AIBL · AUTOMOTIVE SUPPLY CHAIN INTELLIGENCE</div><h1>{html.escape(title)}</h1><div class="sub">{html.escape(template_title)}{' · ' if template_title else ''}تاریخ مرجع {html.escape(ref_date)}{' · ' + html.escape(subtitle) if subtitle else ''}{lineage_text}</div></div>
<div class="stats">{stat_html}</div><button onclick="exportPdf()">PDF / چاپ</button></header>
<div class="supply-chain"><span class="supply-step">تأمین قطعه</span><span class="supply-arrow">←</span><span class="supply-step">ثبت سفارش و ارز</span><span class="supply-arrow">←</span><span class="supply-step">حمل بین‌الملل</span><span class="supply-arrow">←</span><span class="supply-step">گمرک و ترخیص</span><span class="supply-arrow">←</span><span class="supply-step">ورود قطعه</span><span class="supply-arrow">←</span><span class="supply-step">پشتیبانی تولید خودرو</span></div><div class="bandlegend">{legend_html}</div><div class="tabbar" role="tablist">{buttons}</div>
{trunc_note}<section id="story" class="story reveal"><div class="eyebrow">◈ مسیر تصمیم</div><h2 id="story_headline"></h2>
<div class="story-grid"><div class="scr"><b>وضعیت</b><p id="story_situation"></p></div><div class="scr"><b>گره</b><p id="story_complication"></p></div><div class="scr"><b>اقدام</b><p id="story_resolution"></p></div></div>
<div class="findings" id="story_findings"></div></section>
<div class="toolbar"><label style="display:block;max-width:420px;flex:1">جستجوی سراسری تب فعال<input id="q" placeholder="جستجو در فیلدهای همان تب"></label><button class="export-btn" onclick="downloadFilteredXlsx()">⬇ استخراج داده فیلترشده (Excel)</button></div>
{process_panel}{''.join(panes)}
</div>
<script>
const DATA={records}; const COL_INDEX={json.dumps(col_index,ensure_ascii=False)}; const TAB_META={json.dumps(metas,ensure_ascii=False)};
const REPORT_META={report_meta_json};
const LABELS={json.dumps({c:labels.get(c,c) for c in all_needed},ensure_ascii=False)};
{ds.REVEAL_JS}
const q=document.getElementById('q'); let active=0;
</script>""" + dynamic_js + """</body></html>"""
