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

__contract__ = 2

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
TEXT, TEXT2, TEXT3 = "#0b0b0b", "#52514e", "#7a7a73"


def _measure_cols(df: pd.DataFrame, cols: List[str]) -> Dict[str, str]:
    """{ستون عددی: تجمیع بامعنا}.

    شناسه‌ها (شماره سفارش، کد متریال) کنار گذاشته می‌شوند — جمع زدنشان
    بی‌معناست. ستون نسبتی (مقاومت، درصد، امتیاز) میانگین می‌گیرد، نه جمع.
    """
    out: Dict[str, str] = {}
    for c in cols:
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
                       max_rows: int = 5000, selected_fields=None,
                       labels: Optional[Dict[str, str]] = None,
                       template_title: str = "", subtitle: str = "",
                       show_visuals: bool = True) -> str:
    default_cols = ["KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_REG",
                    "CANONICAL_EXPERT", "ORG_DEPT", "روش حمل", "بحرانی (کوتاه)",
                    "مقاومت (روز)"]
    requested = list(selected_fields or default_cols)
    cols = [c for c in requested if c in df.columns]
    if not cols:
        cols = [c for c in default_cols if c in df.columns] or list(df.columns[:12])
    labels = labels or {}
    pm = prefix_grain_map()

    # ستون‌های کلید دانه باید در داده‌ی JS باشند تا جمع‌ها یکتاسازی شوند،
    # حتی اگر کاربر آن‌ها را برای نمایش انتخاب نکرده باشد.
    grain_keys_present = [k for k in GRAIN_KEYS.values() if k in df.columns]
    carry = [c for c in grain_keys_present if c not in cols]
    band_col = "بحرانی (کوتاه)" if "بحرانی (کوتاه)" in df.columns else None
    if band_col and band_col not in cols and band_col not in carry:
        carry.append(band_col)

    data = df[cols + carry].head(max_rows).copy()
    for c in data.columns:
        if pd.api.types.is_datetime64_any_dtype(data[c]):
            data[c] = data[c].dt.strftime("%Y-%m-%d")
    data = data.fillna("")

    records = json.dumps(
        data.to_dict(orient="records"), ensure_ascii=False, default=str
    ).replace("</", "<\\/")

    measures = _measure_cols(df, cols)
    numeric = list(measures)
    grain_of = {c: (GRAIN_KEYS.get(column_grain(c, pm)) or "") for c in numeric}

    # فیلترها: ستون‌های کم‌کاردینالیتی
    filters = []
    for c in cols:
        try:
            vals = sorted({str(x) for x in data[c].tolist() if str(x).strip()})
        except Exception:
            continue
        if 1 < len(vals) <= 40:
            filters.append((c, labels.get(c, c), vals))
        if len(filters) >= 5:
            break

    filter_html = "".join(
        f'<label>{html.escape(lab)}<select data-f="{html.escape(c)}">'
        f'<option value="">همه</option>'
        + "".join(f"<option>{html.escape(v)}</option>" for v in vals)
        + "</select></label>"
        for c, lab, vals in filters)

    head = "".join(f"<th>{html.escape(labels.get(c, c))}</th>" for c in cols)

    # شاخص‌های سربرگ — در پایتون و **دانه‌ای** محاسبه می‌شوند
    head_stats = []
    if band_col:
        vc = df[band_col].astype(str).value_counts()
        for b in ("توقف خط", "بحرانی"):
            head_stats.append((b, int(vc.get(b, 0)), BANDS[b][0], BANDS[b][1]))
    for c in [x for x in numeric if measures[x] == "sum"][:2]:
        head_stats.append((labels.get(c, c), safe_agg(df, c, "sum", pm), BRAND, "Σ"))

    stat_html = "".join(
        f'<div class="stat"><div class="v">{v:,.0f}</div>'
        f'<div class="l">{html.escape(str(lab))}</div>'
        f'<div class="d" style="background:{col}"></div></div>'
        for lab, v, col, _ic in head_stats)

    legend_html = "".join(
        f'<span class="band" style="background:{c}1a;color:{c};border-color:{c}44">'
        f'<i style="background:{c}"></i>{ic} {html.escape(b)}</span>'
        for b, (c, ic) in BANDS.items())

    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — {html.escape(ref_date)}</title>
<style>
:root{{--brand:{BRAND};--deep:{BRAND_DEEP};--surface:{SURFACE};--raised:{RAISED};
--border:{BORDER};--text:{TEXT};--t2:{TEXT2};--t3:{TEXT3}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--surface);color:var(--text);
font-family:'IRANSans Light',IRANSans,Vazirmatn,Tahoma,Arial,sans-serif;direction:rtl}}
.shell{{max-width:1500px;margin:auto;padding:22px}}
header{{background:linear-gradient(120deg,var(--deep),var(--brand));border-radius:18px;
padding:22px 26px;color:#fff;display:flex;justify-content:space-between;
align-items:center;gap:18px;flex-wrap:wrap}}
h1{{margin:0;font-size:26px}} .sub{{opacity:.88;font-size:13px;margin-top:6px}}
.stats{{display:flex;gap:12px;flex-wrap:wrap}}
.stat{{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.22);
border-radius:12px;padding:10px 14px;min-width:96px;text-align:center}}
.stat .v{{font-size:21px;font-weight:700}} .stat .l{{font-size:11px;opacity:.86;margin-top:2px}}
.stat .d{{height:3px;border-radius:2px;margin-top:6px}}
.legend{{margin:14px 0 6px;display:flex;gap:7px;flex-wrap:wrap}}
.band{{display:inline-flex;align-items:center;gap:5px;border:1px solid;border-radius:999px;
padding:2px 10px;font-size:12px;font-weight:600}}
.band i{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.toolbar{{display:grid;grid-template-columns:2fr repeat(auto-fit,minmax(150px,1fr));
gap:12px;background:var(--raised);padding:14px;border:1px solid var(--border);
border-radius:14px;margin:14px 0;position:sticky;top:8px;z-index:5}}
label{{font-size:12px;color:var(--t2)}}
input,select{{width:100%;margin-top:5px;padding:9px;border:1px solid var(--border);
border-radius:9px;background:#fff;font:inherit}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:14px 0}}
.card{{background:var(--raised);border:1px solid var(--border);border-radius:14px;padding:14px}}
.card .l{{font-size:12px;color:var(--t2)}} .card b{{display:block;font-size:24px;margin-top:4px}}
.card .g{{font-size:11px;color:var(--t3);margin-top:4px}}
.panel{{background:var(--raised);border:1px solid var(--border);border-radius:14px;
padding:16px;margin-top:14px}}
.panel h3{{margin:0 0 10px;font-size:15px}}
.mix{{display:flex;height:26px;border-radius:8px;overflow:hidden;background:#f0efec;gap:2px}}
.seg{{height:100%;min-width:2px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{position:sticky;top:0;background:var(--deep);color:#fff;padding:9px;
white-space:nowrap;text-align:right}}
td{{padding:7px 9px;border-bottom:1px solid var(--border);white-space:nowrap}}
tr:hover td{{background:#f4faf8}}
button{{border:0;border-radius:10px;padding:10px 16px;background:#fff;color:var(--deep);
font:inherit;font-weight:700;cursor:pointer}}
.note{{font-size:11px;color:var(--t3);margin-top:8px;line-height:1.8}}
@media print{{
  .toolbar,button{{display:none!important}}
  body{{background:#fff}} header{{background:var(--deep)!important;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .panel,.card{{break-inside:avoid}} th{{position:static}}
}}
</style></head><body><div class="shell">
<header>
  <div><h1>{html.escape(title)}</h1>
  <div class="sub">{html.escape(template_title)}{' · ' if template_title else ''}تاریخ مرجع {html.escape(ref_date)}{' · ' + html.escape(subtitle) if subtitle else ''}</div></div>
  <div class="stats">{stat_html}</div>
  <button onclick="window.print()">چاپ / ذخیره PDF</button>
</header>
<div class="legend">{legend_html}</div>
<div class="toolbar"><label>جستجو<input id="q" placeholder="جستجو در همه ستون‌های نمایش‌داده‌شده"></label>{filter_html}</div>
<div class="cards" id="cards"></div>
{'<div class="panel"><h3>ترکیب طبقه بحرانی</h3><div class="mix" id="mix"></div><div class="note" id="mixleg"></div></div>' if (show_visuals and band_col) else ''}
<div class="panel"><div style="display:flex;justify-content:space-between;align-items:center">
<h3>جدول تفصیلی</h3><span class="note" id="cnt"></span></div>
<div style="max-height:640px;overflow:auto"><table><thead><tr>{head}</tr></thead>
<tbody id="tb"></tbody></table></div>
<div class="note">جمع‌های عددی پیش از محاسبه بر کلید دانه‌ی همان ستون یکتا می‌شوند،
پس با فیلتر کردن هم دوباره‌شماری رخ نمی‌دهد.</div></div>
</div><script>
const DATA={records}, COLS={json.dumps(cols, ensure_ascii=False)};
const NUM={json.dumps(numeric, ensure_ascii=False)}, GRAIN={json.dumps(grain_of, ensure_ascii=False)};
const AGG={json.dumps(measures, ensure_ascii=False)};
const LAB={json.dumps({c: labels.get(c, c) for c in cols}, ensure_ascii=False)};
const BAND={json.dumps(band_col or "", ensure_ascii=False)};
const COLORS={json.dumps({b: c for b, (c, _i) in BANDS.items()}, ensure_ascii=False)};
const ORDER={json.dumps(BAND_ORDER, ensure_ascii=False)};
const q=document.getElementById('q'), sels=[...document.querySelectorAll('select[data-f]')];
const S=(r,c)=>String(r[c]??'');

function rows(){{
  let a=DATA; const n=q.value.trim().toLowerCase();
  if(n) a=a.filter(r=>COLS.some(c=>S(r,c).toLowerCase().includes(n)));
  sels.forEach(s=>{{ if(s.value) a=a.filter(r=>S(r,s.dataset.f)===s.value); }});
  return a;
}}
/* جمع دانه‌ای: پیش از جمع، بر کلید دانه یکتا می‌شود — همان قاعده‌ای که
   در پایتون اعمال شده، تا عدد فیلترشده با عدد سربرگ هم‌خانواده بماند. */
function gvals(a,c){{
  const k=GRAIN[c], seen=new Set(), out=[];
  for(const r of a){{
    if(k){{ const key=S(r,k).trim(); if(key){{ if(seen.has(key)) continue; seen.add(key); }} }}
    const v=parseFloat(r[c]); if(Number.isFinite(v)) out.push(v);
  }}
  return out;
}}
/* جمع برای ستون انباشتنی، میانگین برای ستون نسبتی — جمعِ «مقاومت (روز)»
   بی‌معناست، همان‌طور که جمعِ شماره سفارش. */
function gagg(a,c){{
  const v=gvals(a,c);
  if(!v.length) return 0;
  if(AGG[c]==='mean') return v.reduce((s,x)=>s+x,0)/v.length;
  return v.reduce((s,x)=>s+x,0);
}}
function fmt(v){{return (Math.round(v*100)/100).toLocaleString('fa-IR')}}

function render(){{
  const a=rows();
  document.getElementById('cnt').textContent=
    a.length.toLocaleString('fa-IR')+' از '+DATA.length.toLocaleString('fa-IR')+' ردیف';
  const cards=[{{l:'ردیف نمایش‌داده‌شده',v:a.length.toLocaleString('fa-IR'),g:''}}];
  NUM.slice(0,4).forEach(c=>{{
    const k=GRAIN[c], pre=(AGG[c]==='mean'?'میانگین ':'جمع ');
    cards.push({{l:pre+(LAB[c]||c), v:fmt(gagg(a,c)),
                 g: k? ('یکتا بر '+k) : 'دانه ردیف'}});
  }});
  document.getElementById('cards').innerHTML=cards.map(x=>
    `<div class="card"><div class="l">${{x.l}}</div><b>${{x.v}}</b><div class="g">${{x.g}}</div></div>`).join('');
  const mix=document.getElementById('mix');
  if(mix && BAND){{
    const cnt={{}}; a.forEach(r=>{{const k=S(r,BAND)||'نامشخص';cnt[k]=(cnt[k]||0)+1}});
    const tot=a.length||1;
    const keys=ORDER.filter(k=>cnt[k]).concat(Object.keys(cnt).filter(k=>!ORDER.includes(k)));
    mix.innerHTML=keys.map(k=>`<div class="seg" title="${{k}}: ${{cnt[k]}}" style="width:${{100*cnt[k]/tot}}%;background:${{COLORS[k]||'#8a8a85'}}"></div>`).join('');
    document.getElementById('mixleg').textContent=keys.map(k=>`${{k}}: ${{cnt[k].toLocaleString('fa-IR')}}`).join('  ·  ');
  }}
  const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  document.getElementById('tb').innerHTML=a.slice(0,3000).map(r=>
    '<tr>'+COLS.map(c=>{{
      const v=esc(r[c]);
      if(c===BAND && COLORS[r[c]]) return `<td><span style="color:${{COLORS[r[c]]}};font-weight:700">${{v}}</span></td>`;
      return `<td>${{v}}</td>`;
    }}).join('')+'</tr>').join('');
}}
[q,...sels].forEach(x=>x.addEventListener('input',render));
render();
</script></body></html>"""
