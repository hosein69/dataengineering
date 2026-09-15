# -*- coding: utf-8 -*-
"""خروجی HTML خودبسنده — راست‌به‌چپ، فیلترپذیر، آماده چاپ/PDF.

سه تفاوت بنیادی با نسخه قبل:

1. **راست‌به‌چپ و فارسی.** نسخه قبل ``dir="ltr"`` با برچسب انگلیسی بود.
2. **پالت اعتبارسنجی‌شده.** پالت قبلی «در حال بحرانی شدن» و «تحت نظر» را
   با ΔE ۹٫۸ نشان می‌داد (کف ۱۵) — عملاً تفکیک‌ناپذیر. حالا پالت وضعیت
   ثابت با آیکن و برچسب.
3. **جمع‌های دانه‌ای، حتی هنگام فیلتر مرورگری.** کلید دانه‌ی هر ستون عددی
   به JS داده می‌شود و جمع‌ها **پیش از محاسبه بر همان کلید یکتا** می‌شوند.
   بدون این، کاربر فیلتر می‌کرد و «جمع مانده تعهد» چند برابر می‌شد —
   بی‌صدا و بدون خطا.
"""
from __future__ import annotations

__contract__ = 5

import html
import json
from typing import Dict, List, Optional

import pandas as pd

from .grain import (GRAIN_KEYS, KIND_ADDITIVE, KIND_RATIO, column_grain,
                    measure_kind, prefix_grain_map, safe_agg)

#: پالت وضعیت (ثابت، هرگز تم‌پذیر) — همیشه با آیکن و برچسب
BANDS = {
    "توقف خط":            ("#a32828", "⏹"),
    "بحرانی":             ("#d03b3b", "⬤"),
    "در حال بحرانی شدن":  ("#ec835a", "◤"),
    "تحت نظر":            ("#fab219", "◆"),
    "ایمن":               ("#0ca30c", "✓"),
    "بدون مصرف":          ("#8a8a85", "—"),
    "نامشخص":             ("#b5b5ae", "?"),
}
BAND_ORDER = list(BANDS)

BRAND, BRAND_DEEP = "#0f6e6e", "#0a4f4f"
SURFACE, RAISED, BORDER = "#fcfcfb", "#ffffff", "#e3e3dd"
TEXT, TEXT2, TEXT3 = "#0b0b0b", "#52514e", "#6e6e66"


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
        kind = measure_kind(c, df[c])
        if kind == KIND_ADDITIVE:
            out[c] = "sum"
        elif kind == KIND_RATIO:
            out[c] = "mean"
    return out


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
        "sediment_vs_resistance": ["KEY_MATERIAL", "روزهای رسوب", "مقاومت (روز)"],
        "risk_mix": ["طبقه ریسک"],
        "commitment": ["مانده تعهد", "روزهای تأخیر", "KEY_REG", "CANONICAL_ORDER"],
        "overdue_bucket": ["روزهای تأخیر"],
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

    stat_html = ""
    if band_col:
        vc = df[band_col].astype(str).value_counts()
        stat_html = " · ".join(f'<span><b>{html.escape(b)}</b> {int(vc.get(b,0)):,}</span>'
                              for b in ("توقف خط", "بحرانی") if int(vc.get(b,0)) > 0)
    legend_html = " · ".join(
        f'<span style="color:{c};font-weight:700">{html.escape(b)} {icon}</span>'
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
        hidden = ' style="display:none"' if i else ''
        table_html = (
            f'<div class="panel"><div style="display:flex;justify-content:space-between;align-items:center">'
            f'<h3>{html.escape(tab["title"])}</h3><span class="note" id="cnt_{i}"></span></div>'
            f'<div style="max-height:640px;overflow:auto"><table><thead><tr>{head}</tr></thead>'
            f'<tbody id="tb_{i}"></tbody></table></div><div class="pager" id="pager_{i}"></div></div>' if show_tables else
            f'<div class="note" id="cnt_{i}"></div>')
        panes.append(
            f'<section id="{tab["id"]}" class="pane" role="tabpanel"{hidden}>'
            f'<div class="toolbar">{fhtml}</div><div class="cards" id="cards_{i}"></div>'
            f'<div class="chartgrid" id="charts_{i}"></div>{table_html}</section>')
        metas.append({"id":tab["id"],"fields":cols,"max_rows":tab["max_rows"],
                      "grain":grain_of,"agg":measures})

    chart_keys = list(charts or []) if show_visuals else []
    try:
        from .designs import EMAIL_CHARTS
        chart_labels = {k: EMAIL_CHARTS[k] for k in chart_keys if k in EMAIL_CHARTS}
    except Exception:
        chart_labels = {k: k for k in chart_keys}
    proc_payload = {}
    for key in ("bottlenecks", "variants", "conformance_root_causes", "conformance_cases", "case_table", "eventlog"):
        t = (process_extras or {}).get(key)
        if isinstance(t, pd.DataFrame) and not t.empty:
            x=t.copy()
            for c in x.columns:
                if pd.api.types.is_datetime64_any_dtype(x[c]): x[c]=x[c].dt.strftime("%Y-%m-%d %H:%M:%S")
            proc_payload[key]=x.fillna("").to_dict(orient="records")
    chart_json=json.dumps({"keys":chart_keys,"labels":chart_labels},ensure_ascii=False)
    proc_json=json.dumps(proc_payload,ensure_ascii=False,default=str)
    report_meta = dict(lineage or {})
    report_meta.update({"ref_date": ref_date, "title": title, "payload_rows": len(data), "source_rows": len(df)})
    report_meta_json = json.dumps(report_meta, ensure_ascii=False, default=str)
    run_id = str(report_meta.get("warehouse_run_id") or "").strip()
    lineage_text = (f" · Snapshot {html.escape(run_id)}" if run_id else "")
    dynamic_js = r"""<script>
const CHART_CFG=%s; const PROC=%s;
const _esc2=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
function V(r,c){if(Array.isArray(r)){const i=COL_INDEX[c];return i===undefined?'':(r[i]??'')}return r?.[c]??''}
function S(r,c){return String(V(r,c))}
function rows(t){const query=String(q?.value||'').trim().toLowerCase(), sels=[...document.querySelectorAll('select[data-pane="'+t.id+'"]')];return DATA.filter(r=>{for(const s of sels){if(s.value&&S(r,s.dataset.f)!==s.value)return false}if(query&&!t.fields.some(c=>S(r,c).toLowerCase().includes(query)))return false;return true}).slice(0,t.max_rows)}
function fmt(v){return (Math.round((Number(v)||0)*100)/100).toLocaleString('fa-IR')}
function _chartBox(t,i){return '<div class="chartbox"><h4>'+_esc2(t)+'</h4>'+i+'</div>'}
function _bar(rows,title,cls='chart-bar'){if(!rows.length)return _chartBox(title,'<div class="note">داده کافی نیست.</div>');rows=rows.slice().filter(x=>Number.isFinite(+x.v)).sort((a,b)=>b.v-a.v).slice(0,10).reverse();let mx=Math.max(...rows.map(x=>+x.v),1),W=760,H=Math.max(190,rows.length*34+35),L=250,B=W-L-28,svg='<svg viewBox="0 0 '+W+' '+H+'" role="img">';rows.forEach((x,i)=>{let y=10+i*34,w=Math.max(3,+x.v/mx*B);svg+='<text x="'+(L-10)+'" y="'+(y+21)+'" text-anchor="end" class="chart-label">'+_esc2(x.k)+'</text><rect x="'+L+'" y="'+y+'" width="'+w+'" height="22" rx="5" class="'+cls+'"></rect><text x="'+(L+w+8)+'" y="'+(y+17)+'" class="chart-value">'+fmt(x.v)+'</text>'});return _chartBox(title,svg+'</svg>')}
function _donut(rows,title){let total=rows.reduce((s,x)=>s+(+x.v||0),0);if(!total)return _chartBox(title,'<div class="note">داده کافی نیست.</div>');let colors=['#0f6e6e','#d03b3b','#ec835a','#fab219','#6c7a89','#3f8f8f','#9b59b6'],cx=120,cy=120,R=82,r=48,a=-Math.PI/2,path='';rows.forEach((x,i)=>{let v=+x.v||0,b=a+v/total*Math.PI*2,la=(b-a)>Math.PI?1:0, p1=[cx+R*Math.cos(a),cy+R*Math.sin(a)],p2=[cx+R*Math.cos(b),cy+R*Math.sin(b)],q1=[cx+r*Math.cos(b),cy+r*Math.sin(b)],q2=[cx+r*Math.cos(a),cy+r*Math.sin(a)];path+='<path d="M'+p1+' A'+R+' '+R+' 0 '+la+' 1 '+p2+' L'+q1+' A'+r+' '+r+' 0 '+la+' 0 '+q2+' Z" fill="'+colors[i%%colors.length]+'"></path>';a=b});let leg=rows.map((x,i)=>'<div class="legend-item"><i style="background:'+colors[i%%colors.length]+'"></i>'+_esc2(x.k)+' <b>'+fmt(x.v)+'</b></div>').join('');return _chartBox(title,'<div class="donut-wrap"><svg viewBox="0 0 240 240"><g>'+path+'</g><text x="120" y="116" text-anchor="middle" class="donut-total">'+fmt(total)+'</text><text x="120" y="137" text-anchor="middle" class="donut-sub">ردیف</text></svg><div>'+leg+'</div></div>')}
function _scatter(rows,title){let pts=rows.map(r=>({x:+S(r,'روزهای رسوب'),y:+S(r,'مقاومت (روز)'),k:S(r,'KEY_MATERIAL')})).filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y));if(!pts.length)return _chartBox(title,'<div class="note">دو متغیر لازم برای این نمودار وجود ندارد.</div>');let W=760,H=310,L=58,T=20,R=20,B=48,xm=Math.max(...pts.map(p=>p.x),1),ym=Math.max(...pts.map(p=>p.y),1);let s='<svg viewBox="0 0 '+W+' '+H+'"><line x1="'+L+'" y1="'+(H-B)+'" x2="'+(W-R)+'" y2="'+(H-B)+'" class="axis"></line><line x1="'+L+'" y1="'+T+'" x2="'+L+'" y2="'+(H-B)+'" class="axis"></line>';pts.slice(0,500).forEach(p=>{let x=L+p.x/xm*(W-L-R),y=H-B-p.y/ym*(H-B-T);s+='<circle cx="'+x+'" cy="'+y+'" r="5" class="dot"><title>'+_esc2(p.k)+' · رسوب '+fmt(p.x)+' · مقاومت '+fmt(p.y)+'</title></circle>'});return _chartBox(title,s+'</svg>')}
function _countBy(a,fields){let m={};a.forEach(r=>{let v='';for(const f of fields){v=S(r,f).trim();if(v)break}v=v||'نامشخص';m[v]=(m[v]||0)+1});return Object.entries(m).map(([k,v])=>({k,v}))}
function _topCount(a,fields){return _countBy(a,fields).sort((x,y)=>y.v-x.v).slice(0,12)}
function _sumUnique(a,valCol,keyFields){let seen=new Set(),sum=0;for(const r of a){let key='';for(const f of keyFields){key=S(r,f).trim();if(key)break}if(key){if(seen.has(key))continue;seen.add(key)}let v=parseFloat(S(r,valCol));if(Number.isFinite(v))sum+=v}return sum}
function _grouped(rows,title){rows=rows.filter(x=>Number.isFinite(+x.a)||Number.isFinite(+x.b)).slice(0,10);if(!rows.length)return _chartBox(title,'<div class="note">داده کافی نیست.</div>');let mx=Math.max(...rows.flatMap(x=>[+x.a||0,+x.b||0]),1),W=760,H=Math.max(220,rows.length*38+45),L=250,B=W-L-30,svg='<svg viewBox="0 0 '+W+' '+H+'">';rows.slice().reverse().forEach((x,i)=>{let y=12+i*38,wa=(+x.a||0)/mx*B,wb=(+x.b||0)/mx*B;svg+='<text x="'+(L-10)+'" y="'+(y+20)+'" text-anchor="end" class="chart-label">'+_esc2(x.k)+'</text><rect x="'+L+'" y="'+y+'" width="'+wa+'" height="11" rx="3" fill="#95A5A6"></rect><rect x="'+L+'" y="'+(y+14)+'" width="'+wb+'" height="11" rx="3" fill="#0f6e6e"></rect>'});svg+='</svg><div class="note">■ خاکستری: انبار &nbsp; ■ سبز: کل با درراه/گمرک</div>';return _chartBox(title,svg)}
function _stageRows(a){return _topCount(a,['STAGE_FA','ORDER_STAGE_FA','LIFECYCLE_STAGE'])}
function _chart(k,a){const title=CHART_CFG.labels[k]||k;
 if(k==='low_resistance')return _bar(a.map(r=>({k:S(r,'KEY_MATERIAL'),v:parseFloat(S(r,'مقاومت (روز)'))})),title);
 if(k==='criticality')return _donut(_countBy(a,['بحرانی (کوتاه)','کد طبقه بحرانی']),title);
 if(k==='risk_mix')return _donut(_countBy(a,['طبقه ریسک']),title);
 if(k==='org_workload')return _bar(_topCount(a,['ORG_DEPT','ORG_VICE']),title);
 if(k==='expert_workload')return _bar(_topCount(a,['CANONICAL_EXPERT']),title);
 if(k==='transport_mix')return _donut(_countBy(a,['TRANSPORT_MODE','CL_TRANSPORT_MODE_CODE','MOGH_TRANSPORT_MODE_CODE']),title);
 if(k==='stage_distribution')return _bar(_stageRows(a),title);
 if(k==='top_orders')return _bar(_topCount(a,['CANONICAL_ORDER','KEY_ORDER']),title);
 if(k==='top_bl')return _bar(_topCount(a,['CANONICAL_BL','KEY_BL']),title);
 if(k==='supplier_mix')return _bar(_topCount(a,['SUPPLIER','VENDOR_CODE','MFR_VENDOR_CODE']),title);
 if(k==='sediment_vs_resistance')return _scatter(a,title);
 if(k==='stock_vs_total'){let m=new Map();for(const r of a){let key=S(r,'KEY_MATERIAL').trim();if(!key||m.has(key))continue;let x=parseFloat(S(r,'مقاومت انبار (روز)')),y=parseFloat(S(r,'مقاومت (روز)'));if(Number.isFinite(x)||Number.isFinite(y))m.set(key,{k:key,a:x,b:y})}return _grouped([...m.values()].sort((x,y)=>(+x.b||999999)-(+y.b||999999)).slice(0,10),title)}
 if(k==='commitment'){let overdue=a.filter(r=>(parseFloat(S(r,'روزهای تأخیر'))||0)>0),open=a.filter(r=>(parseFloat(S(r,'روزهای تأخیر'))||0)<=0&&(parseFloat(S(r,'مانده تعهد'))||0)>0),closed=a.filter(r=>(parseFloat(S(r,'مانده تعهد'))||0)<=0);return _bar([{k:'معوق',v:_sumUnique(overdue,'مانده تعهد',['KEY_REG','CANONICAL_ORDER'])},{k:'در مهلت',v:_sumUnique(open,'مانده تعهد',['KEY_REG','CANONICAL_ORDER'])},{k:'تسویه‌شده',v:_sumUnique(closed,'مانده تعهد',['KEY_REG','CANONICAL_ORDER'])}],title)}
 if(k==='overdue_bucket'){let bins={'بدون تأخیر':0,'۱ تا ۷ روز':0,'۸ تا ۳۰ روز':0,'۳۱ تا ۶۰ روز':0,'بیش از ۶۰ روز':0};a.forEach(r=>{let d=parseFloat(S(r,'روزهای تأخیر'));if(!Number.isFinite(d)||d<=0)bins['بدون تأخیر']++;else if(d<=7)bins['۱ تا ۷ روز']++;else if(d<=30)bins['۸ تا ۳۰ روز']++;else if(d<=60)bins['۳۱ تا ۶۰ روز']++;else bins['بیش از ۶۰ روز']++});return _bar(Object.entries(bins).map(([k,v])=>({k,v})),title)}
 if(k==='bottlenecks'){let b=processStats(a).bottlenecks||[];if(b.length)return _bar(b.slice(0,10).map(x=>({k:S(x,'از فعالیت')+' ← '+S(x,'به فعالیت'),v:+x['میانگین روز']||0})),title);let st=_stageRows(a);return _bar(st,title+' — جایگزین: توزیع مرحله فعلی')}
 return _chartBox(title,'<div class="note">فیلد لازم برای این نمودار در برش فعلی وجود ندارد.</div>')}
function _charts(i,a){let e=document.getElementById('charts_'+i);if(e)e.innerHTML=(CHART_CFG.keys||[]).map(k=>_chart(k,a)).join('')}
function processStats(a){
 const ev=PROC.eventlog||[];
 const fallback=()=>({bottlenecks:(PROC.bottlenecks||[]).slice().sort((x,y)=>(+y['میانگین روز']||0)-(+x['میانگین روز']||0)),variants:PROC.variants||[],roots:PROC.conformance_root_causes||[]});
 if(!ev.length)return fallback();
 let keys=new Set(); a.forEach(r=>{let k=S(r,'_CASE_KEY')||S(r,'CASE_KEY');if(k)keys.add(k)}); if(!keys.size)return fallback();
 let e=ev.filter(x=>keys.has(S(x,'_CASE_KEY')||S(x,'CASE_KEY'))).slice().sort((x,y)=>{let k=(S(x,'_CASE_KEY')||S(x,'CASE_KEY')).localeCompare(S(y,'_CASE_KEY')||S(y,'CASE_KEY'));return k||new Date(x.EVENTTIME)-new Date(y.EVENTTIME)||(+x._SORTING||0)-(+y._SORTING||0)}), m=new Map(), cm=new Map();
 e.forEach(x=>{let c=S(x,'_CASE_KEY')||S(x,'CASE_KEY'),z=cm.get(c)||[];z.push(x);cm.set(c,z)});
 for(const [c,z] of cm.entries())for(let i=0;i<z.length-1;i++){let d=(new Date(z[i+1].EVENTTIME)-new Date(z[i].EVENTTIME))/86400000;if(!Number.isFinite(d))continue;let k=S(z[i],'ACTIVITY_FA')+'\u0000'+S(z[i+1],'ACTIVITY_FA'),q=m.get(k)||{from:S(z[i],'ACTIVITY_FA'),to:S(z[i+1],'ACTIVITY_FA'),sum:0,n:0,max:0,cases:new Set()};q.sum+=d;q.n++;q.max=Math.max(q.max,d);q.cases.add(c);m.set(k,q)}
 let b=[...m.values()].map(z=>({'از فعالیت':z.from,'به فعالیت':z.to,'میانگین روز':z.n?z.sum/z.n:0,'بیشینه روز':z.max,'تعداد':z.n,'تعداد پرونده':z.cases.size})).sort((x,y)=>(+y['میانگین روز']||0)-(+x['میانگین روز']||0));
 let vm=new Map();for(const [c,z] of cm.entries()){if(!z.length)continue;let variant=z.map(x=>S(x,'ACTIVITY_FA')).join(' ← '),first=new Date(z[0].EVENTTIME),last=new Date(z[z.length-1].EVENTTIME),days=(last-first)/86400000,q=vm.get(variant)||{n:0,sum:0};q.n++;if(Number.isFinite(days))q.sum+=days;vm.set(variant,q)}
 let total=cm.size||1,v=[...vm.entries()].map(([k,z])=>({VARIANT:k,'تعداد پرونده':z.n,'میانگین throughput':z.n?z.sum/z.n:0,'سهم (٪)':z.n/total*100})).sort((x,y)=>y['تعداد پرونده']-x['تعداد پرونده']);
 let roots=PROC.conformance_root_causes||[]; return {bottlenecks:b,variants:v,roots:roots}
}
function _process(a){
 const ps=processStats(a||[]),e=document.getElementById('process_map'),b=ps.bottlenecks||[],t=document.getElementById('process_bottlenecks'),v=ps.variants||[],rc=ps.roots||[];
 if(!e)return;
 if(!b.length){let st=_stageRows(a);e.innerHTML=st.length?_bar(st,'نقطه شروع فرآیند — توزیع مرحله فعلی'):'<div class="note">لاگ تاریخی برای اندازه‌گیری گذارها هنوز کافی نیست. با اجرای روزانه Warehouse، Transition Log به‌تدریج ساخته می‌شود.</div>';if(t)t.innerHTML='<div class="note">تا زمانی که Event Log کافی شود، توزیع مرحله فعلی به‌عنوان نمای جایگزین نمایش داده می‌شود و هیچ گلوگاه فرضی ساخته نمی‌شود.</div>'}
 else{
  let r=b.slice().sort((a,b)=>(+b['میانگین روز']||0)-(+a['میانگین روز']||0)).slice(0,10);
  let max=Math.max(...r.map(x=>+x['میانگین روز']||0),1),W=980,H=Math.max(260,r.length*52+60),L=250,B=W-L-40,svg='<svg viewBox="0 0 '+W+' '+H+'" class="proc-svg">';
  r.forEach((x,i)=>{let y=30+i*52,w=Math.max(5,(+x['میانگین روز']||0)/max*B);svg+='<text x="'+(L-12)+'" y="'+(y+19)+'" text-anchor="end" class="chart-label">'+_esc2(S(x,'از فعالیت')+' ← '+S(x,'به فعالیت'))+'</text><rect x="'+L+'" y="'+y+'" width="'+w+'" height="28" rx="7" class="proc-bar"></rect><text x="'+(L+w+8)+'" y="'+(y+19)+'" class="chart-value">'+fmt(x['میانگین روز'])+' روز</text>'});e.innerHTML=svg+'</svg>'
  t.innerHTML='<table class="proc-table"><tr><th>از</th><th>به</th><th>میانگین انتظار</th><th>پرونده</th></tr>'+r.map(x=>'<tr><td>'+_esc2(S(x,'از فعالیت'))+'</td><td>'+_esc2(S(x,'به فعالیت'))+'</td><td>'+fmt(x['میانگین روز'])+' روز</td><td>'+fmt(x['تعداد پرونده'])+'</td></tr>').join('')+'</table>'
 }
 const pv=document.getElementById('process_variants'); if(pv&&v.length)pv.innerHTML='<h4>واریانت‌های پرتکرار</h4><table class="proc-table"><tr><th>مسیر</th><th>پرونده</th><th>سهم</th><th>میانگین چرخه</th></tr>'+v.slice(0,12).map(x=>'<tr><td>'+_esc2(S(x,'VARIANT'))+'</td><td>'+fmt(x['تعداد پرونده'])+'</td><td>'+fmt(x['سهم (٪)'])+'%%</td><td>'+fmt(x['میانگین throughput'])+' روز</td></tr>').join('')+'</table>';
 const pr=document.getElementById('process_roots'); if(pr&&rc.length)pr.innerHTML='<h4>محرک‌های انحراف / ریشه‌یابی</h4>'+_bar(rc.slice(0,8).map(x=>({k:S(x,'بُعد'),v:+x['اثر تفاضلی (واحد درصد)']||0})),'اثر تفاضلی (واحد درصد)')
}
function crc32(bytes){let t=window._crcTable;if(!t){t=[];for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=(c&1)?0xEDB88320^(c>>>1):c>>>1;t[n]=c>>>0}window._crcTable=t}let c=0xFFFFFFFF;for(const b of bytes)c=t[(c^b)&255]^(c>>>8);return (c^0xFFFFFFFF)>>>0}
const u8=s=>new TextEncoder().encode(s);
function zipStore(files){let chunks=[],central=[],offset=0;for(const [name,data] of files){let nb=u8(name),db=typeof data==='string'?u8(data):data,crc=crc32(db),head=new Uint8Array(30+nb.length);let dv=new DataView(head.buffer);dv.setUint32(0,0x04034b50,true);dv.setUint16(4,20,true);dv.setUint16(6,0,true);dv.setUint16(8,0,true);dv.setUint16(10,0,true);dv.setUint16(12,0,true);dv.setUint32(14,crc,true);dv.setUint32(18,db.length,true);dv.setUint32(22,db.length,true);dv.setUint16(26,nb.length,true);dv.setUint16(28,0,true);head.set(nb,30);chunks.push(head,db);let cd=new Uint8Array(46+nb.length),cv=new DataView(cd.buffer);cv.setUint32(0,0x02014b50,true);cv.setUint16(4,20,true);cv.setUint16(6,20,true);cv.setUint16(8,0,true);cv.setUint16(10,0,true);cv.setUint16(12,0,true);cv.setUint16(14,0,true);cv.setUint32(16,crc,true);cv.setUint32(20,db.length,true);cv.setUint32(24,db.length,true);cv.setUint16(28,nb.length,true);cv.setUint16(30,0,true);cv.setUint16(32,0,true);cv.setUint16(34,0,true);cv.setUint16(36,0,true);cv.setUint32(38,0,true);cv.setUint32(42,offset,true);cd.set(nb,46);central.push(cd);offset+=head.length+db.length}let csize=central.reduce((s,x)=>s+x.length,0),end=new Uint8Array(22),ed=new DataView(end.buffer);ed.setUint32(0,0x06054b50,true);ed.setUint16(8,files.length,true);ed.setUint16(10,files.length,true);ed.setUint32(12,csize,true);ed.setUint32(16,offset,true);let all=chunks.concat(central,[end]);return new Blob(all,{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})}
function xmlEsc(s){return String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&apos;')}
function colName(n){let s='';while(n){let r=(n-1)%%26;s=String.fromCharCode(65+r)+s;n=Math.floor((n-1)/26)}return s}
function excelSerial(v){let d=new Date(v);if(!Number.isFinite(+d))return null;return (+d-Date.UTC(1899,11,30))/86400000}
function cellXml(v,ref,header=false){if(header)return '<c r="'+ref+'" s="1" t="inlineStr"><is><t>'+xmlEsc(v)+'</t></is></c>';if(typeof v==='number'&&Number.isFinite(v))return '<c r="'+ref+'" s="2"><v>'+v+'</v></c>';if(typeof v==='boolean')return '<c r="'+ref+'" t="b"><v>'+(v?1:0)+'</v></c>';if(typeof v==='string'&&/^\d{4}-\d{2}-\d{2}(?:[T ][0-9:.+-Z]+)?$/.test(v)){let n=excelSerial(v);if(n!==null)return '<c r="'+ref+'" s="3"><v>'+n+'</v></c>'}return '<c r="'+ref+'" t="inlineStr"><is><t>'+xmlEsc(v)+'</t></is></c>'}
function makeXlsx(rows,fields,sheet='داده فیلترشده'){let safe=String(sheet||'Data').replace(/[\\/*?:\[\]]/g,' ').slice(0,31)||'Data',head=fields.map((c,i)=>cellXml(LABELS[c]||c,colName(i+1)+'1',true)).join(''),body=rows.map((r,i)=>'<row r="'+(i+2)+'">'+fields.map((c,j)=>cellXml(V(r,c),colName(j+1)+(i+2))).join('')+'</row>').join(''),last=colName(Math.max(fields.length,1))+(rows.length+1);let sh='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:'+last+'"/><sheetViews><sheetView workbookViewId="0" rightToLeft="1"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData><row r="1">'+head+'</row>'+body+'</sheetData><autoFilter ref="A1:'+last+'"/></worksheet>';let wb='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="'+xmlEsc(safe)+'" sheetId="1" r:id="rId1"/></sheets></workbook>';let styles='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-mm-dd hh:mm"/></numFmts><fonts count="2"><font><sz val="11"/><name val="IRANSans"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="IRANSans"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0A4F4F"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment horizontal="right"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"><alignment horizontal="right"/></xf><xf numFmtId="4" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"><alignment horizontal="right"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"><alignment horizontal="right"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';let rel='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>';let wrel='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>';let ct='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>';return zipStore([['[Content_Types].xml',ct],['_rels/.rels',rel],['xl/workbook.xml',wb],['xl/_rels/workbook.xml.rels',wrel],['xl/styles.xml',styles],['xl/worksheets/sheet1.xml',sh]])}
function downloadFilteredXlsx(){let t=TAB_META[active],a=rows(t);let blob=makeXlsx(a,t.fields,t.title),url=URL.createObjectURL(blob),x=document.createElement('a');x.href=url;x.download='AIBL_filtered_'+(REPORT_META.ref_date||new Date().toISOString().slice(0,10))+'.xlsx';x.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function exportPdf(){window.print()}
function story(a){let crit=a.filter(r=>['توقف خط','بحرانی','STOCKOUT','CRITICAL'].includes(S(r,'بحرانی (کوتاه)')||S(r,'کد طبقه بحرانی'))).length;let rs=a.map(r=>parseFloat(S(r,'مقاومت (روز)'))).filter(Number.isFinite);let min=rs.length?Math.min(...rs):null;let wait=(processStats(a).bottlenecks||[])[0];let txt='روایت این برش: ';if(crit)txt+='از '+fmt(crit)+' ردیف، '+fmt(crit)+' ردیف در وضعیت بحرانی/توقف قرار دارند. ';else txt+='در این برش، مورد بحرانی ثبت نشده است. ';if(min!==null)txt+='کمترین مقاومت '+fmt(min)+' روز است. ';if(wait)txt+='بزرگ‌ترین گلوگاه ثبت‌شده «'+S(wait,'از فعالیت')+' ← '+S(wait,'به فعالیت')+'» با '+fmt(wait['میانگین روز'])+' روز انتظار است. ';else txt+='لاگ گذار هنوز برای محاسبه گلوگاه کافی نیست؛ توزیع مرحله فعلی به‌عنوان نقطه شروع نشان داده می‌شود. ';txt+='برای ادامه، از Process Explorer به واریانت‌ها و ریشه انحراف بروید.';document.getElementById('story').innerHTML='<b>◈ مسیر تصمیم</b><br>'+_esc2(txt)}
const PAGE_SIZE=100, PAGE={};
function pageMove(i,delta){PAGE[i]=Math.max(0,(PAGE[i]||0)+delta);render(i)}
function render(i){const t=TAB_META[i],a=rows(t);story(a);const cards=[{l:'ردیف',v:a.length.toLocaleString('fa-IR'),g:''}];Object.keys(t.agg).slice(0,4).forEach(c=>cards.push({l:(t.agg[c]==='mean'?'میانگین ':'جمع ')+(LABELS[c]||c),v:fmt(gagg(a,c,t.grain,t.agg)),g:t.grain[c]?('یکتا بر '+t.grain[c]):'دانه ردیف'}));let pages=Math.max(1,Math.ceil(a.length/PAGE_SIZE));PAGE[i]=Math.min(PAGE[i]||0,pages-1);let start=PAGE[i]*PAGE_SIZE,view=a.slice(start,start+PAGE_SIZE);document.getElementById('cnt_'+i).textContent=a.length.toLocaleString('fa-IR')+' ردیف · صفحه '+(PAGE[i]+1).toLocaleString('fa-IR')+' از '+pages.toLocaleString('fa-IR');document.getElementById('cards_'+i).innerHTML=cards.map(x=>'<div class="card"><div class="l">'+x.l+'</div><b>'+x.v+'</b><div class="g">'+x.g+'</div></div>').join('');const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');let tb=document.getElementById('tb_'+i);if(tb)tb.innerHTML=view.map(r=>'<tr>'+t.fields.map(c=>'<td>'+esc(S(r,c))+'</td>').join('')+'</tr>').join('');let pg=document.getElementById('pager_'+i);if(pg)pg.innerHTML='<button '+(PAGE[i]<=0?'disabled':'')+' onclick="pageMove('+i+',-1)">صفحه قبل</button><span>نمایش '+Math.min(start+1,a.length).toLocaleString('fa-IR')+' تا '+Math.min(start+PAGE_SIZE,a.length).toLocaleString('fa-IR')+' از '+a.length.toLocaleString('fa-IR')+'</span><button '+(PAGE[i]>=pages-1?'disabled':'')+' onclick="pageMove('+i+',1)">صفحه بعد</button>';_charts(i,a);_process(a)}
function gvals(a,c,grain){const k=grain[c],seen=new Set(),out=[];for(const r of a){if(k){const key=S(r,k).trim();if(key){if(seen.has(key))continue;seen.add(key)}}const v=parseFloat(S(r,c));if(Number.isFinite(v))out.push(v)}return out}
function gagg(a,c,grain,agg){const v=gvals(a,c,grain);if(!v.length)return 0;if(agg[c]==='mean')return v.reduce((s,x)=>s+x,0)/v.length;return v.reduce((s,x)=>s+x,0)}
function activate(i){active=i;PAGE[i]=0;document.querySelectorAll('.tabbtn').forEach((b,j)=>{b.classList.toggle('active',j===i);b.setAttribute('aria-selected',j===i)});document.querySelectorAll('.pane').forEach((p,j)=>p.style.display=j===i?'block':'none');q.value='';render(i)}
document.querySelectorAll('.tabbtn').forEach((b,i)=>b.addEventListener('click',()=>activate(i)));q.addEventListener('input',()=>{PAGE[active]=0;render(active)});document.querySelectorAll('select').forEach(s=>s.addEventListener('change',()=>{PAGE[active]=0;render(active)}));render(0);
</script>""" % (chart_json, proc_json)
    trunc_note = (f'<div class="payload-note">طبق سقف ردیف انتخاب‌شده در گزارش، {safe_cap:,} ردیف از {len(df):,} ردیف وارد Artifact شده است. این محدودیت انتخاب کاربر/قالب است و هیچ کاهش خودکار بر اساس حجم یا تعداد ستون اعمال نشده است.</div>' if payload_truncated else '')
    process_panel = (
        '<div class="panel process-panel"><h3>⛓ Process Explorer — روایت فرآیند</h3><div class="note">این نما با فیلتر فعال دوباره محاسبه می‌شود؛ در صورت وجود CASE_KEY فقط پرونده‌های همان برش لحاظ می‌شوند.</div><div id="process_map" class="process-map"></div><div id="process_bottlenecks"></div><div id="process_variants" class="panel"></div><div id="process_roots" class="panel"></div><div class="process-actions"><button class="export-btn" onclick="downloadFilteredXlsx()">⬇ استخراج داده فیلترشده (Excel)</button><button class="export-btn secondary" onclick="exportPdf()">🖨 PDF / چاپ</button></div></div>'
        if show_process else '<div id="process_map" style="display:none"></div><div id="process_bottlenecks" style="display:none"></div><div id="process_variants" style="display:none"></div><div id="process_roots" style="display:none"></div>')
    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
:root{{--deep:#0a4f4f;--accent:#0f6e6e;--text:#0b0b0b;--t2:#52514e;--t3:#6e6e66;--border:#e3e3dd;--raised:#fff;--surface:#fcfcfb}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--surface);color:var(--text);font-family:'IRANSans','IRANSans Light',Tahoma,Arial,sans-serif;direction:rtl}}
.shell{{max-width:1500px;margin:auto;padding:18px}} header{{background:var(--deep);color:#fff;border-radius:16px;padding:20px;display:flex;gap:18px;justify-content:space-between;align-items:center}}
h1{{margin:0;font-size:24px}} .sub{{font-size:12px;opacity:.85;margin-top:6px}} .stats{{display:flex;gap:14px;font-size:12px}}
header button{{background:#fff;color:var(--deep);border:0;border-radius:10px;padding:9px 13px;font-weight:700}}
.legend{{padding:12px 4px;font-size:12px}} .tabbar{{display:flex;gap:6px;overflow:auto;padding:8px 0;border-bottom:1px solid var(--border)}}
.tabbtn{{border:1px solid var(--border);background:#fff;color:var(--deep);border-radius:10px;padding:10px 16px;white-space:nowrap}}
.tabbtn.active{{background:var(--deep);color:#fff}} .toolbar{{display:flex;align-items:end;gap:10px;flex-wrap:wrap;background:var(--raised);border:1px solid var(--border);border-radius:14px;padding:12px;margin:12px 0}}
label{{font-size:12px;color:var(--t2);min-width:150px}} input,select{{width:100%;margin-top:5px;padding:9px;border:1px solid var(--border);border-radius:9px;background:#fff;font:inherit}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:12px 0}} .card{{background:var(--raised);border:1px solid var(--border);border-radius:14px;padding:14px}}
.card .l{{font-size:12px;color:var(--t2)}} .card b{{display:block;font-size:22px;margin-top:4px}} .card .g{{font-size:11px;color:var(--t3);margin-top:4px}}
.panel{{background:var(--raised);border:1px solid var(--border);border-radius:14px;padding:16px;margin-top:12px}} .chartgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:12px;margin:12px 0}} .chartbox{{background:#fff;border:1px solid var(--border);border-radius:14px;padding:14px}} .chartbox h4{{margin:0 0 8px;color:var(--deep)}} .chart-label{{font:11px 'IRANSans','IRANSans Light',Tahoma,Arial;fill:var(--t2)}} .chart-bar{{fill:#0f6e6e}} .process-map{{overflow:auto;padding:14px;background:linear-gradient(135deg,#f7fbfa,#fff);border-radius:12px}} .proc-svg{{min-width:760px}} .proc-bar{{fill:#0f6e6e}} .dot{{fill:#d03b3b;opacity:.78}} .axis{{stroke:#9aa5a5;stroke-width:1}} .chart-value{{font:700 11px 'IRANSans','IRANSans Light',Tahoma;fill:var(--deep)}} .donut-wrap{{display:flex;gap:24px;align-items:center;justify-content:center;flex-wrap:wrap}} .donut-total{{font:800 24px 'IRANSans','IRANSans Light',Tahoma;fill:var(--deep)}} .donut-sub{{font:11px 'IRANSans','IRANSans Light',Tahoma;fill:var(--t3)}} .legend-item{{margin:7px 0;font-size:12px}} .legend-item i{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-left:7px}} .proc-flow{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;direction:rtl}} .proc-box{{padding:10px 14px;border:2px solid var(--deep);border-radius:12px;background:#fff;min-width:130px;text-align:center;font-weight:700}} .proc-arrow{{font-size:20px;color:var(--deep)}} .proc-table{{width:100%;border-collapse:collapse;font-size:12px}} .proc-table th{{background:var(--deep);color:#fff;padding:8px}} .proc-table td{{padding:7px;border-bottom:1px solid var(--border)}} .panel h3{{margin:0 0 10px;font-size:15px}}
table{{width:100%;border-collapse:collapse;font-size:12px}} th{{position:sticky;top:0;background:var(--deep);color:#fff;padding:9px;white-space:nowrap;text-align:right}}
td{{padding:7px 9px;border-bottom:1px solid var(--border);white-space:nowrap}} tr:hover td{{background:#f4faf8}} .note{{font-size:11px;color:var(--t3);margin-top:8px}} .story{{background:linear-gradient(135deg,#0a4f4f,#0f6e6e);color:#fff;border-radius:14px;padding:16px 18px;margin:12px 0;line-height:1.9;box-shadow:0 8px 24px rgba(10,79,79,.12)}} .story b{{color:#fff}} .export-btn{{border:0;border-radius:10px;padding:10px 14px;background:var(--deep);color:#fff;font-family:inherit;font-weight:800;cursor:pointer}} .export-btn.secondary{{background:#fff;color:var(--deep);border:1px solid var(--border)}} .process-actions{{display:flex;gap:8px;margin-top:12px}} .pager{{display:flex;justify-content:center;align-items:center;gap:12px;padding:12px;font-size:12px}} .pager button{{border:1px solid var(--border);background:#fff;color:var(--deep);border-radius:8px;padding:7px 12px;font-family:inherit}} .pager button:disabled{{opacity:.35}} .supply-chain{{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:10px 0 2px}} .supply-step{{background:#edf7f5;border:1px solid #cfe8e3;color:var(--deep);padding:6px 10px;border-radius:999px;font-size:11px;font-weight:700}} .supply-arrow{{color:#789}} .payload-note{{margin:12px 0;padding:10px 14px;border:1px solid #e7c46a;background:#fff8df;border-radius:10px;font-size:12px}}
@media print{{.tabbar,.toolbar,header button{{display:none!important}}}}
</style></head><body><div class="shell">
<header><div><div style="font-size:11px;letter-spacing:.4px;opacity:.82;margin-bottom:5px">AIBL · AUTOMOTIVE SUPPLY CHAIN INTELLIGENCE</div><h1>{html.escape(title)}</h1><div class="sub">{html.escape(template_title)}{' · ' if template_title else ''}تاریخ مرجع {html.escape(ref_date)}{' · ' + html.escape(subtitle) if subtitle else ''}{lineage_text}</div></div>
<div class="stats">{stat_html}</div><button onclick="exportPdf()">PDF / چاپ</button></header>
<div class="supply-chain"><span class="supply-step">تأمین قطعه</span><span class="supply-arrow">←</span><span class="supply-step">ثبت سفارش و ارز</span><span class="supply-arrow">←</span><span class="supply-step">حمل بین‌الملل</span><span class="supply-arrow">←</span><span class="supply-step">گمرک و ترخیص</span><span class="supply-arrow">←</span><span class="supply-step">ورود قطعه</span><span class="supply-arrow">←</span><span class="supply-step">پشتیبانی تولید خودرو</span></div><div class="legend">{legend_html}</div><div class="tabbar" role="tablist">{buttons}</div>
{trunc_note}<div id="story" class="story"></div><div class="toolbar"><label style="display:block;max-width:420px;flex:1">جستجوی سراسری تب فعال<input id="q" placeholder="جستجو در فیلدهای همان تب"></label><button class="export-btn" onclick="downloadFilteredXlsx()">⬇ استخراج داده فیلترشده (Excel)</button></div>
{process_panel}{''.join(panes)}
</div>
<script>
const DATA={records}; const COL_INDEX={json.dumps(col_index,ensure_ascii=False)}; const TAB_META={json.dumps(metas,ensure_ascii=False)};
const REPORT_META={report_meta_json};
const LABELS={json.dumps({c:labels.get(c,c) for c in all_needed},ensure_ascii=False)};
const q=document.getElementById('q'); let active=0;
</script>""" + dynamic_js + """</body></html>"""
