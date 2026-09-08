# -*- coding: utf-8 -*-
"""Self-contained dynamic HTML export: CSS + JavaScript, no server required."""
from __future__ import annotations
import json, html
from typing import Iterable, List
import pandas as pd

STATUS_COLORS = {
    "توقف خط": "#C0392B", "بحرانی": "#C0392B", "در حال بحرانی شدن": "#F39C12",
    "تحت نظر": "#F1C40F", "ایمن": "#27AE60", "بدون مصرف": "#95A5A6", "نامشخص": "#95A5A6"
}

def build_dynamic_html(df: pd.DataFrame, ref_date: str, title: str = "AIBL Studio", max_rows: int = 5000, selected_fields=None) -> str:
    default_cols = ["KEY_MATERIAL","CANONICAL_ORDER","CANONICAL_BL","KEY_REG","CANONICAL_EXPERT","ORG_DEPT","روش حمل","بحرانی (کوتاه)","مقاومت (روز)","BL_CRITICAL","ORDER_CRITICAL"]
    requested = list(selected_fields or default_cols)
    cols = [c for c in requested if c in df.columns]
    if not cols: cols = list(df.columns[:15])
    data = df[cols].head(max_rows).copy().fillna("")
    records = []
    for _, row in data.iterrows():
        d = {str(c): row[c].item() if hasattr(row[c], "item") else row[c] for c in cols}
        records.append(d)
    json_data = json.dumps(records, ensure_ascii=False, default=str).replace("</", "<\\/")
    filter_defs = []
    for c, label in [("بحرانی (کوتاه)", "Criticality"), ("ORG_DEPT", "Management"), ("CANONICAL_EXPERT", "Expert"), ("روش حمل", "Transport")]:
        if c in cols:
            vals = sorted({str(x) for x in data[c].tolist() if str(x)})[:80]
            filter_defs.append((c, label, vals))
    filter_html = ''.join(
        f'<label>{html.escape(label)}<select data-filter="{html.escape(c)}"><option value="">All</option>' +
        ''.join(f'<option>{html.escape(v)}</option>' for v in vals) + '</select></label>'
        for c, label, vals in filter_defs
    )
    head = ''.join(f'<th>{html.escape(str(c))}</th>' for c in cols)
    return f'''<!doctype html><html lang="en" dir="ltr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — {html.escape(ref_date)}</title>
<style>
:root{{--navy:#173b36;--aqua:#1e9e9e;--bg:#f3f7f6;--card:#fff;--muted:#657875;--border:#dce8e5;--critical:#c0392b;--warning:#f39c12;--watch:#f1c40f;--safe:#27ae60;--inactive:#95a5a6}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(135deg,#fff,var(--bg));font-family:"IRANSans Light",IRANSans,Tahoma,Arial,sans-serif;color:#173b36}}
.shell{{max-width:1500px;margin:auto;padding:26px}} header{{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:20px}} h1{{margin:0;font-size:30px}} .muted{{color:var(--muted)}}
.toolbar,.cards,.grid{{display:grid;gap:14px}} .toolbar{{grid-template-columns:2fr repeat(3,1fr);background:var(--card);padding:14px;border:1px solid var(--border);border-radius:16px;position:sticky;top:8px;z-index:4;box-shadow:0 8px 28px #173b3612}}
label{{font-size:12px;color:var(--muted)}} input,select{{width:100%;margin-top:6px;padding:10px;border:1px solid var(--border);border-radius:10px;background:#fff;font:inherit}}
.cards{{grid-template-columns:repeat(5,1fr);margin:18px 0}} .card{{padding:16px;border-radius:16px;background:#fff;border:1px solid var(--border);box-shadow:0 5px 20px #173b3610}} .card b{{font-size:25px;display:block;margin-top:5px}} .critical{{color:var(--critical)}}
.grid{{grid-template-columns:1fr 1fr;margin-top:16px}} .panel{{background:#fff;border:1px solid var(--border);border-radius:16px;padding:16px;overflow:auto}} .bar{{display:flex;height:24px;border-radius:8px;overflow:hidden;background:#edf2f1}} .seg{{height:100%;min-width:2px}} table{{width:100%;border-collapse:collapse;font-size:12px}} th{{position:sticky;top:0;background:var(--navy);color:#fff;padding:9px;white-space:nowrap}} td{{padding:8px;border-bottom:1px solid var(--border);white-space:nowrap}} tr:hover td{{background:#f4faf8}}
button{{border:0;border-radius:10px;padding:10px 14px;background:var(--navy);color:#fff;font:inherit;cursor:pointer}} .empty{{padding:25px;text-align:center;color:var(--muted)}}
@media(max-width:1000px){{.toolbar,.cards,.grid{{grid-template-columns:1fr 1fr}}}} @media print{{.toolbar,button{{display:none}}body{{background:#fff}}}}
</style></head><body><div class="shell"><header><div><h1>{html.escape(title)}</h1><div class="muted">Reference date: {html.escape(ref_date)} · Dynamic client-side report</div></div><button onclick="window.print()">Print / PDF</button></header>
<div class="toolbar"><label>Search<input id="q" placeholder="Material / Order / BL / Registration / Expert"></label>{filter_html}</div>
<div class="cards" id="cards"><div class="card">Visible rows<b id="rows">0</b></div><div class="card">Critical materials<b id="critical" class="critical">0</b></div><div class="card">Critical BLs<b id="bls" class="critical">0</b></div><div class="card">Critical Orders<b id="orders" class="critical">0</b></div><div class="card">Min resistance<b id="minres">—</b></div></div>
<div class="grid"><div class="panel"><h3>Criticality Mix</h3><div class="bar" id="mix"></div><div id="mixLegend" class="muted" style="margin-top:10px;font-size:12px"></div></div><div class="panel"><h3>Live Result</h3><div id="summary" class="muted"></div></div></div>
<div class="panel" style="margin-top:16px"><div style="display:flex;justify-content:space-between;align-items:center"><h3>Filtered Records</h3><span id="count" class="muted"></span></div><div style="max-height:620px;overflow:auto"><table><thead><tr>{head}</tr></thead><tbody id="tbody"></tbody></table></div></div>
</div><script>
const DATA={json_data}; const COLS={json.dumps(cols, ensure_ascii=False)};
const colors={{"توقف خط":"#C0392B","بحرانی":"#C0392B","در حال بحرانی شدن":"#F39C12","تحت نظر":"#F1C40F","ایمن":"#27AE60","بدون مصرف":"#95A5A6","نامشخص":"#95A5A6"}};
const q=document.getElementById('q'); const selects=[...document.querySelectorAll('select[data-filter]')];
function val(r,c){{return String(r[c]??'')}}
function filtered(){{let a=DATA; const needle=q.value.trim().toLowerCase(); if(needle)a=a.filter(r=>COLS.some(c=>val(r,c).toLowerCase().includes(needle))); selects.forEach(s=>{{if(s.value)a=a.filter(r=>val(r,s.dataset.filter)===s.value)}}); return a}}
function render(){{const a=filtered(); document.getElementById('rows').textContent=a.length.toLocaleString(); document.getElementById('count').textContent=`${{a.length.toLocaleString()}} of ${{DATA.length.toLocaleString()}} rows`;
const crit=a.filter(r=>['CRITICAL','STOCKOUT'].includes(val(r,'کد طبقه بحرانی'))||['بحرانی','توقف خط'].includes(val(r,'بحرانی (کوتاه)'))); document.getElementById('critical').textContent=new Set(crit.map(r=>val(r,'KEY_MATERIAL')).filter(Boolean)).size.toLocaleString(); document.getElementById('bls').textContent=new Set(a.filter(r=>String(r['BL_CRITICAL'])==='True'||String(r['BL_CRITICAL'])==='1').map(r=>val(r,'CANONICAL_BL')).filter(Boolean)).size.toLocaleString(); document.getElementById('orders').textContent=new Set(a.filter(r=>String(r['ORDER_CRITICAL'])==='True'||String(r['ORDER_CRITICAL'])==='1').map(r=>val(r,'CANONICAL_ORDER')).filter(Boolean)).size.toLocaleString(); const rs=a.map(r=>Number(r['مقاومت (روز)'])).filter(Number.isFinite); document.getElementById('minres').textContent=rs.length?Math.min(...rs).toFixed(1)+' d':'—';
const counts={{}}; a.forEach(r=>{{const k=val(r,'بحرانی (کوتاه)')||'نامشخص';counts[k]=(counts[k]||0)+1}}); const total=a.length||1; document.getElementById('mix').innerHTML=Object.entries(counts).map(([k,n])=>`<div class="seg" title="${{k}}: ${{n}}" style="width:${{100*n/total}}%;background:${{colors[k]||'#1E9E9E'}}"></div>`).join(''); document.getElementById('mixLegend').textContent=Object.entries(counts).map(([k,n])=>`${{k}}: ${{n}}`).join(' · ');
const body=document.getElementById('tbody'); body.innerHTML=a.slice(0,3000).map(r=>'<tr>'+COLS.map(c=>`<td>${{String(r[c]??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')}}</td>`).join('')+'</tr>').join(''); document.getElementById('summary').textContent='Filters recalculate KPIs, criticality mix and the table instantly in the browser.';}}
[q,...selects].forEach(x=>x.addEventListener('input',render)); render();
</script></body></html>'''
