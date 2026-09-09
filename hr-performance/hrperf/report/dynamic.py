# -*- coding: utf-8 -*-
"""خروجی HTML داینامیک و متحرک — یک فایل، بدون اینترنت.

## چه چیزی این را از یک جدول متفاوت می‌کند

* **فیلتر زنده** روی مدیریت/اداره/نوع کار — همه نمودارها بازساخته می‌شوند.
* **نمودار قابل انتخاب** — کاربر خودش بُعد و معیار را عوض می‌کند.
* **حرکت هدفمند** — میله‌ها با انیمیشن کوتاه رشد می‌کنند تا چشم مسیر
  تغییر را دنبال کند. حرکت برای تزئین نیست؛ فقط جایی به‌کار رفته که
  تغییرِ مقدار را قابل دنبال‌کردن می‌کند، و با
  ``prefers-reduced-motion`` کاملاً خاموش می‌شود.
* **منحنی لورنتس عدالت** — توزیع بار، کنار امتیاز. این همان چیزی است که
  یک جدول رتبه‌بندی هرگز نشان نمی‌دهد.

بدون هیچ کتابخانه بیرونی: فایل روی شبکه داخلی باز می‌شود و وابستگی به
CDN یعنی صفحه‌ای که سرِ کار خالی است.
"""
from __future__ import annotations

__contract__ = 1

import html
import json
from typing import Dict, List, Optional, Sequence

import pandas as pd

from ..fairness.skew import gini, lorenz

#: پالت رسته‌ای اعتبارسنجی‌شده (همان پالت AIBL؛ هر شش بررسی را رد می‌کند).
CATEGORICAL = ["#00918a", "#96690a", "#b81269", "#3358d4",
               "#a83a12", "#8347c9", "#1a8a2e"]
OTHER = "#8a8a85"
BRAND, DEEP = "#0d6e66", "#0a4f4a"
SURFACE, RAISED, BORDER = "#fbfbfa", "#ffffff", "#e4e4de"
TEXT, TEXT2, TEXT3 = "#0b0b0b", "#52514e", "#6e6e66"

#: طیف امتیاز — ترتیبی، تک‌خانواده، از کم به زیاد.
SCORE_BANDS = [(0, 45, "#a32828", "نیازمند اقدام"),
               (45, 60, "#d9822b", "قابل بهبود"),
               (60, 75, "#c9a227", "مطلوب"),
               (75, 101, "#0ca30c", "برجسته")]

_E = html.escape


def _band_color(v: float) -> str:
    for lo, hi, c, _ in SCORE_BANDS:
        if lo <= v < hi:
            return c
    return OTHER


def build_dynamic_html(people: pd.DataFrame, ref_date: str,
                       score_col: str = "performance",
                       name_col: str = "full_name",
                       load_col: str = "",
                       dims: Sequence[str] = (),
                       cluster_cols: Optional[Dict[str, str]] = None,
                       labels: Optional[Dict[str, str]] = None,
                       title: str = "عملکرد منابع انسانی") -> str:
    """یک صفحه کامل و مستقل از داده افراد."""
    df = people.copy()
    if score_col not in df.columns:
        return _empty(title, ref_date, "ستون امتیاز در داده نیست.")

    labels = dict(labels or {})
    labels.setdefault(score_col, "امتیاز عملکرد")
    labels.setdefault(name_col, "نام")
    if load_col:
        labels.setdefault(load_col, "بار کاری")
    dims = [c for c in (dims or []) if c in df.columns]
    cluster_cols = {k: v for k, v in (cluster_cols or {}).items() if k in df.columns}
    keep = [c for c in ([name_col, score_col, load_col] + list(dims)
                        + list(cluster_cols)) if c and c in df.columns]
    data = df[keep].copy()
    for c in data.columns:
        if pd.api.types.is_datetime64_any_dtype(data[c]):
            data[c] = data[c].dt.strftime("%Y-%m-%d")
    data = data.fillna("")

    records = json.dumps(data.to_dict(orient="records"),
                         ensure_ascii=False, default=str).replace("</", "<\\/")
    numeric = [c for c in keep
               if pd.to_numeric(df[c], errors="coerce").notna().any()
               and c != name_col]

    filters = ""
    for c in dims:
        vals = sorted({str(x) for x in data[c] if str(x).strip()})
        if 1 < len(vals) <= 60:
            filters += (f'<label>{_E(labels.get(c, c))}<select data-f="{_E(c)}">'
                        f'<option value="">همه</option>'
                        + "".join(f"<option>{_E(v)}</option>" for v in vals)
                        + "</select></label>")

    dim_opts = "".join(f'<option value="{_E(c)}">{_E(labels.get(c, c))}</option>'
                       for c in dims)
    meas_opts = ('<option value="__count__">تعداد نفرات</option>'
                 + "".join(f'<option value="{_E(c)}">میانگین {_E(labels.get(c, c))}</option>'
                           for c in numeric))
    band_legend = "".join(
        f'<span class="bd" style="--c:{c}"><i></i>{_E(lab)} ({lo}–{hi if hi<101 else 100})</span>'
        for lo, hi, c, lab in SCORE_BANDS)

    g = gini(df[load_col]) if load_col and load_col in df.columns else float("nan")
    gini_txt = ("—" if g != g else
                f"{g:.2f}".translate(str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫")))
    lz = lorenz(df[load_col]) if load_col and load_col in df.columns else []

    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_E(title)} — {_E(ref_date)}</title><style>
*{{box-sizing:border-box}}
body{{margin:0;background:{SURFACE};color:{TEXT};direction:rtl;
font-family:'IRANSans Light',IRANSans,Vazirmatn,Tahoma,Arial,sans-serif}}
.shell{{max-width:1400px;margin:auto;padding:20px}}
header{{background:linear-gradient(120deg,{DEEP},{BRAND});color:#fff;
border-radius:18px;padding:22px 26px;display:flex;justify-content:space-between;
align-items:center;gap:18px;flex-wrap:wrap;position:relative;overflow:hidden}}
header::after{{content:"";position:absolute;inset:-40% -10% auto auto;width:420px;
height:420px;border-radius:50%;background:radial-gradient(circle,#ffffff22,transparent 70%);
animation:drift 18s ease-in-out infinite}}
@keyframes drift{{0%,100%{{transform:translate(0,0)}}50%{{transform:translate(-30px,26px)}}}}
h1{{margin:0;font-size:24px}} .sub{{opacity:.9;font-size:13px;margin-top:5px}}
.kpis{{display:flex;gap:10px;flex-wrap:wrap;position:relative;z-index:1}}
.kpi{{background:#ffffff24;border:1px solid #ffffff30;border-radius:12px;
padding:9px 14px;min-width:104px;text-align:center}}
.kpi b{{display:block;font-size:20px}} .kpi span{{font-size:11px;opacity:.9}}
.legend{{display:flex;gap:8px;flex-wrap:wrap;margin:13px 0 4px}}
.bd{{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;
border:1px solid color-mix(in srgb,var(--c) 40%,transparent);border-radius:999px;
padding:2px 10px;color:var(--c);background:color-mix(in srgb,var(--c) 10%,transparent)}}
.bd i{{width:8px;height:8px;border-radius:50%;background:var(--c)}}
.bar-tools{{display:grid;grid-template-columns:2fr repeat(auto-fit,minmax(140px,1fr));
gap:11px;background:{RAISED};border:1px solid {BORDER};border-radius:14px;
padding:13px;margin:13px 0;position:sticky;top:8px;z-index:5}}
label{{font-size:11.5px;color:{TEXT2}}}
input,select{{width:100%;margin-top:4px;padding:8px;border:1px solid {BORDER};
border-radius:9px;background:#fff;font:inherit}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:13px}}
.panel{{background:{RAISED};border:1px solid {BORDER};border-radius:15px;
padding:16px;margin-top:13px}}
.panel h3{{margin:0 0 4px;font-size:15px}}
.chead{{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;
flex-wrap:wrap;margin-bottom:9px}}
.picks{{display:flex;gap:9px;flex-wrap:wrap}}
.picks select{{min-width:140px;margin-top:3px;padding:6px 8px}}
.chart{{width:100%;overflow-x:auto}}
.chart svg{{display:block;max-width:100%;direction:ltr}}
.chart text{{unicode-bidi:plaintext}}
.chart rect,.chart .grow{{transition:width .55s cubic-bezier(.22,1,.36,1),
height .55s cubic-bezier(.22,1,.36,1),y .55s cubic-bezier(.22,1,.36,1),
x .55s cubic-bezier(.22,1,.36,1)}}
.chart path.line{{transition:stroke-dashoffset 1s ease}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{position:sticky;top:0;background:{DEEP};color:#fff;padding:8px;
text-align:right;white-space:nowrap}}
td{{padding:7px 8px;border-bottom:1px solid {BORDER};white-space:nowrap}}
tr:hover td{{background:#f3faf8}}
.note{{font-size:11.5px;color:{TEXT3};line-height:1.95;margin-top:8px}}
.tip{{position:fixed;pointer-events:none;background:#111;color:#fff;font-size:12px;
padding:6px 9px;border-radius:7px;opacity:0;transition:opacity .12s;z-index:60;
white-space:nowrap;box-shadow:0 3px 14px #0003}}
button{{border:0;border-radius:10px;padding:9px 15px;background:#fff;color:{DEEP};
font:inherit;font-weight:700;cursor:pointer}}
@media (prefers-reduced-motion:reduce){{
  *{{animation:none!important;transition:none!important}}}}
@media print{{.bar-tools,button{{display:none!important}}
body{{background:#fff}} .panel{{break-inside:avoid}}
header{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body><div class="shell">
<header><div><h1>{_E(title)}</h1>
<div class="sub">تاریخ مرجع {_E(ref_date)} · {len(df):,} نفر</div></div>
<div class="kpis">
  <div class="kpi"><b id="kn">—</b><span>نفرات</span></div>
  <div class="kpi"><b id="km">—</b><span>میانه امتیاز</span></div>
  <div class="kpi"><b id="kg">{gini_txt}</b><span>جینی بار</span></div>
</div>
<button onclick="window.print()">چاپ / PDF</button></header>
<div class="legend">{band_legend}</div>
<div class="bar-tools"><label>جستجو<input id="q" placeholder="نام یا هر ستون"></label>{filters}</div>

<div class="panel"><div class="chead"><h3>مقایسه گروهی</h3>
<div class="picks">
<label>گروه‌بندی<select id="cdim">{dim_opts}</select></label>
<label>معیار<select id="cmeas">{meas_opts}</select></label></div></div>
<div id="bar" class="chart"></div>
<div class="note">هر میله برچسب مستقیم دارد؛ رنگ فقط برای تفکیک است.</div></div>

<div class="grid">
<div class="panel"><h3>توزیع امتیاز</h3><div id="hist" class="chart"></div>
<div class="note">میانگین، دنبالهٔ توزیع را پنهان می‌کند. خط‌چین، میانه است.</div></div>
<div class="panel"><h3>عدالت توزیع بار — منحنی لورنتس</h3>
<div id="lorenz" class="chart"></div>
<div class="note">خط‌چین قطری یعنی توزیع کاملاً برابر. هرچه منحنی از آن
دورتر باشد، بار روی افراد کمتری متمرکز است.</div></div>
</div>

<div class="panel"><div class="chead"><h3>فهرست افراد</h3>
<span class="note" id="cnt"></span></div>
<div style="max-height:520px;overflow:auto"><table id="tbl"></table></div></div>
</div><script>
const DATA={records}, DIMS={json.dumps(list(dims), ensure_ascii=False)},
      NUM={json.dumps(numeric, ensure_ascii=False)},
      NAME={json.dumps(name_col, ensure_ascii=False)},
      SCORE={json.dumps(score_col, ensure_ascii=False)},
      LOAD={json.dumps(load_col, ensure_ascii=False)},
      CATS={json.dumps(CATEGORICAL, ensure_ascii=False)},
      OTHER={json.dumps(OTHER, ensure_ascii=False)},
      BANDS={json.dumps([[a,b,c,d] for a,b,c,d in SCORE_BANDS], ensure_ascii=False)},
      LZ={json.dumps(lz, ensure_ascii=False)},
      LAB={json.dumps(labels, ensure_ascii=False)};
const S=(r,c)=>String(r[c]??''), N=(r,c)=>parseFloat(r[c]);
const q=document.getElementById('q'), sels=[...document.querySelectorAll('select[data-f]')];
const tip=document.createElement('div'); tip.className='tip'; document.body.appendChild(tip);
const show=(e,t)=>{{tip.textContent=t;tip.style.opacity=1;
  tip.style.left=Math.min(e.clientX+12,innerWidth-tip.offsetWidth-8)+'px';
  tip.style.top=(e.clientY-34)+'px';}};
const hide=()=>tip.style.opacity=0;
const NS='http://www.w3.org/2000/svg';
const el=(n,a)=>{{const x=document.createElementNS(NS,n);for(const k in a)x.setAttribute(k,a[k]);return x;}};
const fa=v=>(Math.round(v*100)/100).toLocaleString('fa-IR');
const bandOf=v=>{{for(const[lo,hi,c]of BANDS)if(v>=lo&&v<hi)return c;return OTHER;}};

function rows(){{
  let a=DATA; const n=q.value.trim().toLowerCase();
  if(n) a=a.filter(r=>Object.values(r).some(v=>String(v).toLowerCase().includes(n)));
  sels.forEach(s=>{{if(s.value) a=a.filter(r=>S(r,s.dataset.f)===s.value);}});
  return a;
}}
function group(a,dim,meas){{
  const m=new Map();
  a.forEach(r=>{{const k=(S(r,dim)||'—').trim()||'—';
    if(!m.has(k))m.set(k,[]); m.get(k).push(r);}});
  let out=[];
  m.forEach((rs,k)=>{{
    let v;
    if(meas==='__count__') v=rs.length;
    else{{const xs=rs.map(r=>N(r,meas)).filter(Number.isFinite);
      v=xs.length?xs.reduce((s,x)=>s+x,0)/xs.length:0;}}
    out.push({{k,v,n:rs.length}});}});
  out.sort((x,y)=>y.v-x.v);
  if(out.length>7){{const rest=out.slice(7), s=rest.reduce((t,x)=>t+x.v,0)/rest.length;
    out=out.slice(0,7).concat([{{k:'سایر ('+rest.length+')',v:s,n:0,other:1}}]);}}
  return out;
}}
function drawBar(box,rs,unit){{
  box.innerHTML='';
  if(!rs.length){{box.innerHTML='<div class="note">داده‌ای نیست.</div>';return;}}
  const W=Math.max(box.clientWidth||760,460),rh=32,pad=12,labW=190,
        H=pad*2+rs.length*rh,max=Math.max(...rs.map(r=>Math.abs(r.v)),1),pw=W-labW-84;
  const svg=el('svg',{{viewBox:`0 0 ${{W}} ${{H}}`,width:W,height:H,role:'img'}});
  rs.forEach((r,i)=>{{
    const y=pad+i*rh,bw=Math.max(pw*Math.abs(r.v)/max,2),x=W-labW-bw;
    const b=el('rect',{{x:W-labW,y:y+6,width:0,height:rh-14,rx:4,
      fill:r.other?OTHER:CATS[i%CATS.length]}});
    b.addEventListener('mousemove',e=>show(e,r.k+' — '+fa(r.v)+(unit?' '+unit:'')
      +((r.n&&!unit)?' · '+fa(r.n)+' نفر':'')));
    b.addEventListener('mouseleave',hide); svg.appendChild(b);
    requestAnimationFrame(()=>{{b.setAttribute('width',bw);b.setAttribute('x',x);}});
    const t=el('text',{{x:W-labW+10,y:y+rh/2+4,'text-anchor':'start','font-size':12,fill:'{TEXT2}'}});
    t.textContent=r.k.length>24?r.k.slice(0,23)+'…':r.k; svg.appendChild(t);
    const v=el('text',{{x:x-7,y:y+rh/2+4,'text-anchor':'end','font-size':12,
      'font-weight':700,fill:'{TEXT}'}});
    v.textContent=fa(r.v); svg.appendChild(v);
  }});
  box.appendChild(svg);
}}
function drawHist(box,vals){{
  box.innerHTML='';
  const v=vals.filter(Number.isFinite).sort((a,b)=>a-b);
  if(v.length<3){{box.innerHTML='<div class="note">داده کافی نیست.</div>';return;}}
  const lo=v[0],hi=v[v.length-1];
  if(hi===lo){{box.innerHTML='<div class="note">همه برابرند ('+fa(lo)+').</div>';return;}}
  const k=Math.min(16,Math.max(6,Math.ceil(Math.sqrt(v.length)))),w=(hi-lo)/k,
        bins=new Array(k).fill(0);
  v.forEach(x=>{{let i=Math.floor((x-lo)/w); if(i>=k)i=k-1; if(i<0)i=0; bins[i]++;}});
  const med=v.length%2?v[(v.length-1)/2]:(v[v.length/2-1]+v[v.length/2])/2;
  const W=Math.max(box.clientWidth||440,320),H=210,pad=26,base=H-30,
        max=Math.max(...bins,1),bw=(W-pad*2)/k;
  const svg=el('svg',{{viewBox:`0 0 ${{W}} ${{H}}`,width:W,height:H,role:'img'}});
  for(let gI=0;gI<=3;gI++){{const y=base-(base-pad)*gI/3;
    svg.appendChild(el('line',{{x1:pad,x2:W-pad,y1:y,y2:y,stroke:'{BORDER}','stroke-width':1}}));}}
  bins.forEach((c,i)=>{{
    const h=(base-pad)*c/max,x=pad+i*bw, mid=lo+(i+.5)*w;
    const rect=el('rect',{{x:x+1,y:base,width:Math.max(bw-2,1),height:0,rx:4,fill:bandOf(mid)}});
    rect.addEventListener('mousemove',e=>show(e,fa(lo+i*w)+' تا '+fa(lo+(i+1)*w)+' → '+c+' نفر'));
    rect.addEventListener('mouseleave',hide); svg.appendChild(rect);
    requestAnimationFrame(()=>{{rect.setAttribute('height',h);rect.setAttribute('y',base-h);}});
  }});
  svg.appendChild(el('line',{{x1:pad,x2:W-pad,y1:base,y2:base,stroke:'{TEXT3}','stroke-width':1}}));
  const mx=pad+(W-pad*2)*(med-lo)/(hi-lo);
  svg.appendChild(el('line',{{x1:mx,x2:mx,y1:pad-4,y2:base,stroke:'{TEXT}',
    'stroke-width':2,'stroke-dasharray':'5 4'}}));
  const mt=el('text',{{x:mx,y:pad-8,'text-anchor':'middle','font-size':11,fill:'{TEXT}'}});
  mt.textContent='میانه '+fa(med); svg.appendChild(mt);
  box.appendChild(svg);
}}
function drawLorenz(box,pts){{
  box.innerHTML='';
  if(!pts||pts.length<3){{box.innerHTML='<div class="note">ستون بار در داده نیست.</div>';return;}}
  const W=Math.max(box.clientWidth||440,320),H=250,pad=32,S2=Math.min(W-pad*2,H-pad*2);
  const svg=el('svg',{{viewBox:`0 0 ${{W}} ${{H}}`,width:W,height:H,role:'img'}});
  const ox=(W-S2)/2, oy=pad;
  svg.appendChild(el('line',{{x1:ox,y1:oy+S2,x2:ox+S2,y2:oy,stroke:'{TEXT3}',
    'stroke-width':2,'stroke-dasharray':'6 5'}}));
  const d=pts.map((p,i)=>(i?'L':'M')+(ox+p[0]*S2)+' '+(oy+S2-p[1]*S2)).join(' ');
  const path=el('path',{{d,fill:'none',stroke:'{BRAND}','stroke-width':2.5,
    'stroke-linecap':'round'}});
  svg.appendChild(path);
  const len=path.getTotalLength?path.getTotalLength():0;
  if(len){{path.setAttribute('stroke-dasharray',len);path.setAttribute('stroke-dashoffset',len);
    path.classList.add('line'); requestAnimationFrame(()=>path.setAttribute('stroke-dashoffset',0));}}
  pts.forEach(p=>{{const c=el('circle',{{cx:ox+p[0]*S2,cy:oy+S2-p[1]*S2,r:8,fill:'transparent'}});
    c.addEventListener('mousemove',e=>show(e,
      'کم‌بارترین '+Math.round(p[0]*100)+'٪ افراد، '+Math.round(p[1]*100)+'٪ بار را دارند'));
    c.addEventListener('mouseleave',hide); svg.appendChild(c);}});
  [['۰٪',ox,oy+S2+16],['۱۰۰٪ افراد',ox+S2,oy+S2+16]].forEach(([t,x,y],i)=>{{
    const e2=el('text',{{x,y,'text-anchor':i?'end':'start','font-size':11,fill:'{TEXT3}'}});
    e2.textContent=t; svg.appendChild(e2);}});
  box.appendChild(svg);
}}
function drawTable(a){{
  const cols=[NAME,SCORE].concat(LOAD?[LOAD]:[]).concat(DIMS).filter(Boolean);
  const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;');
  document.getElementById('tbl').innerHTML=
    '<thead><tr>'+cols.map(c=>`<th>${{esc(LAB[c]||c)}}</th>`).join('')+'</tr></thead><tbody>'+
    a.slice(0,600).map(r=>'<tr>'+cols.map(c=>{{
      if(c===SCORE){{const v=N(r,c);
        return `<td><b style="color:${{bandOf(v)}}">${{Number.isFinite(v)?fa(v):'—'}}</b></td>`;}}
      return `<td>${{esc(r[c])}}</td>`;}}).join('')+'</tr>').join('')+'</tbody>';
}}
function render(){{
  const a=rows();
  document.getElementById('cnt').textContent=
    a.length.toLocaleString('fa-IR')+' از '+DATA.length.toLocaleString('fa-IR')+' نفر';
  document.getElementById('kn').textContent=a.length.toLocaleString('fa-IR');
  const sc=a.map(r=>N(r,SCORE)).filter(Number.isFinite).sort((x,y)=>x-y);
  document.getElementById('km').textContent=sc.length
    ? fa(sc.length%2?sc[(sc.length-1)/2]:(sc[sc.length/2-1]+sc[sc.length/2])/2) : '—';
  const cd=document.getElementById('cdim'), cm=document.getElementById('cmeas');
  if(cd&&cm) drawBar(document.getElementById('bar'),
    group(a,cd.value,cm.value), cm.value==='__count__'?'نفر':'');
  drawHist(document.getElementById('hist'),a.map(r=>N(r,SCORE)));
  drawLorenz(document.getElementById('lorenz'),LZ);
  drawTable(a);
}}
[q,...sels].forEach(x=>x.addEventListener('input',render));
['cdim','cmeas'].forEach(id=>{{const e2=document.getElementById(id);
  if(e2)e2.addEventListener('change',render);}});
addEventListener('resize',render);
render();
</script></body></html>"""


def _empty(title: str, ref_date: str, why: str) -> str:
    return (f'<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
            f'<title>{_E(title)}</title></head><body style="font-family:Tahoma;'
            f'direction:rtl;padding:30px"><h2>{_E(title)} — {_E(ref_date)}</h2>'
            f'<p>{_E(why)}</p></body></html>')


def write_dynamic(people: pd.DataFrame, path, ref_date: str = "", **kw) -> str:
    """صفحه را روی دیسک می‌نویسد (اتمیک)."""
    import os
    body = build_dynamic_html(people, ref_date, **kw)
    path = str(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(body)
    os.replace(tmp, path)
    return path
