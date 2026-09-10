# -*- coding: utf-8 -*-
"""خروجی HTML خودبسنده — راست‌به‌چپ، فیلترپذیر، آماده چاپ/PDF."""
from __future__ import annotations

__contract__ = 1

import html
import json
from typing import Dict, List, Optional

import pandas as pd

from .theme import (BANDS, BORDER, BRAND, BRAND_DEEP, CARD, FONT_STACK,
                    HIGHLIGHT, RAISED, SURFACE, TEXT, TEXT2, TEXT3,
                    band_of)


def _rows(df: pd.DataFrame, cols: List[str], limit: int) -> str:
    out = []
    for _, r in df.head(limit).iterrows():
        tds = []
        for c in cols:
            v = r.get(c, "")
            txt = html.escape("" if pd.isna(v) else str(v))
            if c == "عملکرد" and pd.notna(v):
                col, ic, lab = band_of(v)
                txt = (f'<span style="color:{col};font-weight:700">{ic} '
                       f'{float(v):.1f}</span>')
                tds.append(f"<td>{txt}</td>")
                continue
            tds.append(f"<td>{txt}</td>")
        out.append("<tr>" + "".join(tds) + "</tr>")
    return "".join(out)


def build_html(leaderboard: pd.DataFrame, *, ref_date: str, title: str,
               template_title: str = "", sections: Optional[List[str]] = None,
               clusters: Optional[pd.DataFrame] = None,
               effects: Optional[pd.DataFrame] = None,
               peers: Optional[pd.DataFrame] = None,
               calibration: Optional[pd.DataFrame] = None,
               weights: Optional[pd.DataFrame] = None,
               max_rows: int = 500, show_visuals: bool = True) -> str:
    sections = sections or ["summary", "leaderboard"]
    lb = leaderboard.copy()
    cols = [c for c in ["کد پرسنلی", "نام", "مدیریت", "اداره", "نوع کار", "نقش",
                        "عملکرد", "امتیاز منصفانه", "رتبه در گروه",
                        "نفرات گروه", "پوشش", "اطمینان"]
            if c in lb.columns]

    n = len(lb)
    perf = pd.to_numeric(lb.get("عملکرد"), errors="coerce")
    band_counts = {}
    for _, v in perf.dropna().items():
        band_counts[band_of(v)[2]] = band_counts.get(band_of(v)[2], 0) + 1

    stats = [("نفرات", f"{n:,}", BRAND),
             ("میانه عملکرد", f"{perf.median():.1f}" if perf.notna().any() else "—", BRAND)]
    for floor, color, icon, label in BANDS:
        if band_counts.get(label):
            stats.append((label, f"{band_counts[label]:,}", color))
    stat_html = "".join(
        f'<div class="stat"><div class="v">{v}</div><div class="l">{html.escape(l)}</div>'
        f'<div class="d" style="background:{c}"></div></div>' for l, v, c in stats[:6])

    legend = "".join(
        f'<span class="band" style="background:{c}1a;color:{c};border-color:{c}44">'
        f'<i style="background:{c}"></i>{ic} {html.escape(lab)}</span>'
        for _f, c, ic, lab in BANDS)

    def table_section(key: str, frame: Optional[pd.DataFrame], heading: str) -> str:
        if key not in sections or frame is None or frame.empty:
            return ""
        cs = list(frame.columns)[:12]
        head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cs)
        body = _rows(frame, cs, 400)
        return (f'<div class="panel"><h3>{html.escape(heading)}</h3>'
                f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
                f'<tbody>{body}</tbody></table></div></div>')

    lb_head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
    records = json.dumps(lb[cols].fillna("").to_dict(orient="records"),
                         ensure_ascii=False, default=str).replace("</", "<\\/")

    extra = ""
    extra += table_section("clusters", clusters, "نمای کلاستری")
    extra += table_section("causal", effects, "اثر تعدیل‌شده در برابر همبستگی خام")
    extra += table_section("peers", peers, "گروه‌های همتا")
    extra += table_section("calibration", calibration, "کالیبراسیون انقباض")
    extra += table_section("weights", weights, "وزن‌های مدل")

    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — {html.escape(ref_date)}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:{SURFACE};color:{TEXT};font-family:{FONT_STACK};direction:rtl}}
.shell{{max-width:1500px;margin:auto;padding:22px}}
header{{background:linear-gradient(120deg,{BRAND_DEEP},{BRAND});border-radius:18px;
padding:22px 26px;color:#fff;display:flex;justify-content:space-between;
align-items:center;gap:18px;flex-wrap:wrap}}
h1{{margin:0;font-size:26px}} .sub{{opacity:.88;font-size:13px;margin-top:6px}}
.stats{{display:flex;gap:12px;flex-wrap:wrap}}
.stat{{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.22);
border-radius:12px;padding:10px 14px;min-width:96px;text-align:center}}
.stat .v{{font-size:21px;font-weight:700}} .stat .l{{font-size:11px;opacity:.86}}
.stat .d{{height:3px;border-radius:2px;margin-top:6px}}
.legend{{margin:14px 0 6px;display:flex;gap:7px;flex-wrap:wrap}}
.band{{display:inline-flex;align-items:center;gap:5px;border:1px solid;
border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600}}
.band i{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.toolbar{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px;background:{RAISED};
padding:14px;border:1px solid {BORDER};border-radius:14px;margin:14px 0;
position:sticky;top:8px;z-index:5}}
label{{font-size:12px;color:{TEXT2}}}
input,select{{width:100%;margin-top:5px;padding:9px;border:1px solid {BORDER};
border-radius:9px;background:#fff;font:inherit}}
.panel{{background:{RAISED};border:1px solid {BORDER};border-radius:14px;
padding:16px;margin-top:14px}}
.panel h3{{margin:0 0 10px;font-size:15px}}
.scroll{{max-height:620px;overflow:auto}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{position:sticky;top:0;background:{BRAND_DEEP};color:#fff;padding:9px;
white-space:nowrap;text-align:right}}
td{{padding:7px 9px;border-bottom:1px solid {BORDER};white-space:nowrap}}
tr:hover td{{background:{HIGHLIGHT}}}
button{{border:0;border-radius:10px;padding:10px 16px;background:#fff;
color:{BRAND_DEEP};font:inherit;font-weight:700;cursor:pointer}}
.note{{font-size:11px;color:{TEXT3};margin-top:8px;line-height:1.8}}
@media print{{.toolbar,button{{display:none!important}}body{{background:#fff}}
header{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.panel{{break-inside:avoid}} th{{position:static}}}}
</style></head><body><div class="shell">
<header><div><h1>{html.escape(title)}</h1>
<div class="sub">{html.escape(template_title)} · تاریخ مرجع {html.escape(ref_date)} · {n:,} نفر</div></div>
<div class="stats">{stat_html}</div>
<button onclick="window.print()">چاپ / ذخیره PDF</button></header>
<div class="legend">{legend}</div>
<div class="toolbar">
  <label>جستجو<input id="q" placeholder="نام / کد پرسنلی / اداره"></label>
  <label>مدیریت<select id="f1"><option value="">همه</option></select></label>
  <label>نوع کار<select id="f2"><option value="">همه</option></select></label>
</div>
<div class="panel"><div style="display:flex;justify-content:space-between;align-items:center">
<h3>جدول عملکرد</h3><span class="note" id="cnt"></span></div>
<div class="scroll"><table><thead><tr>{lb_head}</tr></thead><tbody id="tb"></tbody></table></div>
<div class="note">رتبه‌ها فقط درون گروه همتا معنا دارند؛ مقایسه بین گروه‌های
مختلف کار و اداره انجام نمی‌شود.</div></div>
{extra}
</div><script>
const DATA={records}, COLS={json.dumps(cols, ensure_ascii=False)};
const BANDS={json.dumps([[f,c,i,l] for f,c,i,l in BANDS], ensure_ascii=False)};
function band(v){{for(const[f,c,i,l]of BANDS){{if(v>=f)return[c,i,l];}}return['{TEXT3}','?','نامشخص'];}}
const q=document.getElementById('q'),f1=document.getElementById('f1'),f2=document.getElementById('f2');
function uniq(k){{return [...new Set(DATA.map(r=>String(r[k]??'')).filter(Boolean))].sort();}}
if(COLS.includes('مدیریت')) uniq('مدیریت').forEach(v=>f1.add(new Option(v,v)));
if(COLS.includes('نوع کار')) uniq('نوع کار').forEach(v=>f2.add(new Option(v,v)));
function rows(){{
  let a=DATA; const n=q.value.trim().toLowerCase();
  if(n)a=a.filter(r=>COLS.some(c=>String(r[c]??'').toLowerCase().includes(n)));
  if(f1.value)a=a.filter(r=>String(r['مدیریت']??'')===f1.value);
  if(f2.value)a=a.filter(r=>String(r['نوع کار']??'')===f2.value);
  return a;
}}
function esc(s){{return String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');}}
function render(){{
  const a=rows();
  document.getElementById('cnt').textContent=a.length.toLocaleString('fa-IR')+' از '+DATA.length.toLocaleString('fa-IR')+' نفر';
  document.getElementById('tb').innerHTML=a.slice(0,3000).map(r=>'<tr>'+COLS.map(c=>{{
    const v=r[c];
    if(c==='عملکرد'&&v!==''&&v!=null){{const[col,ic]=band(Number(v));
      return `<td><span style="color:${{col}};font-weight:700">${{ic}} ${{Number(v).toFixed(1)}}</span></td>`;}}
    return `<td>${{esc(v)}}</td>`;}}).join('')+'</tr>').join('');
}}
[q,f1,f2].forEach(x=>x.addEventListener('input',render)); render();
</script></body></html>"""
