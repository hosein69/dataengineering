"""Offline, evidence-led process diagrams. No CDN, server, or network requests.

Observed adjacency is distinct from model order. Missing dates and simultaneous
observations cannot establish adjacency; no edge is invented across either gap.

Visual language borrows GSI's own design tokens (gsi/design/tokens.py, exposed
as CSS custom properties by gsi/design/css.py) instead of a private hex palette,
so these diagrams sit inside the same paper/teal/navy identity as every other
chart in the product rather than looking like a bolted-on generic admin widget.
"""
from __future__ import annotations
import html
import math
from collections import defaultdict
import pandas as pd

# Semantic roles mapped onto GSI's real tokens: --navy/--teal are the brand
# structural colors already used for headers and primary actions; --series-5
# is the violet slot of the validated 8-hue categorical ramp (gsi/design/tokens.py),
# picked here only to mark "return in layout" as visually distinct from both.
PALETTE = dict(blue='var(--navy)', teal='var(--teal)', purple='var(--series-5)')

def esc(value):
    return html.escape(str(value), quote=True)

def number(value, digits=0):
    try:
        n = float(value)
        return f'{n:,.{digits}f}' if math.isfinite(n) else '—'
    except (TypeError, ValueError):
        return '—'

def col(df, names):
    return next((n for n in names if n in df.columns), None)

def observed_model(eventlog, queue=None):
    """Pure projection; never mutates eventlog or infers SLA, responsibility, closure."""
    model = dict(nodes=[], edges=[], cases=0, events=0, ambiguous=0, undated=0, omitted=0, reason='')
    if not isinstance(eventlog, pd.DataFrame) or eventlog.empty:
        model['reason'] = 'Event Log کافی برای ساخت مسیر مشاهده‌شده موجود نیست.'
        return model
    ac = col(eventlog, ['ACTIVITY_FA', 'ACTIVITY_EN'])
    cc = col(eventlog, ['_CASE_KEY', 'CASE_KEY'])
    tc = col(eventlog, ['EVENTTIME', 'EVENT_DATE'])
    if not ac or not cc:
        model['reason'] = 'کلید پرونده و نام فعالیت برای استخراج ارتباط مراحل لازم است.'
        return model
    x = eventlog.copy()
    valid_case = x[cc].notna() & x[cc].astype(str).str.strip().ne('')
    x = x[valid_case].copy()
    model['omitted'] = int((~valid_case).sum())
    x[cc] = x[cc].astype(str)
    valid_act = x[ac].notna() & x[ac].astype(str).str.strip().ne('')
    model['omitted'] += int((~valid_act).sum())
    counts = x[valid_act].groupby(ac)[cc].nunique()
    acts = sorted(counts.index, key=lambda a: (-counts[a], str(a)))
    if '_SORTING' in x:
        ranks = pd.to_numeric(x['_SORTING'], errors='coerce').groupby(x[ac]).min().to_dict()
        acts.sort(key=lambda a: (ranks.get(a) if pd.notna(ranks.get(a)) else float('inf'), str(a)))
    qmap = {}
    if isinstance(queue, pd.DataFrame) and 'مرحله جاری' in queue:
        # Duplicate queue rows are ambiguous; do not silently choose one.
        for a, g in queue.groupby('مرحله جاری'):
            if len(g) == 1:
                qmap[str(a)] = g.iloc[0].to_dict()
    model['nodes'] = [dict(id=i, label=str(a), count=int(counts[a]),
                           wip=qmap.get(str(a), {}).get('تعداد پرونده'),
                           wait=qmap.get(str(a), {}).get('میانه انتظار (روز)')) for i, a in enumerate(acts)]
    ids = {n['label']: n['id'] for n in model['nodes']}
    model.update(cases=int(x[cc].nunique()), events=int(valid_act.sum()))
    if not tc:
        model['reason'] = 'تاریخ رویداد موجود نیست؛ فعالیت‌ها نمایش داده می‌شوند ولی اتصال زمانی ساخته نمی‌شود.'
        model['undated'] = len(x)
        return model
    x['_at'] = pd.to_datetime(x[tc], errors='coerce', utc=True)
    model['undated'] = int(x['_at'].isna().sum())
    acc = defaultdict(lambda: dict(cases=set(), gaps=[]))
    for case, group in x.groupby(cc, sort=False):
        # An undated event can lie anywhere in this case: adjacency is unproven.
        if group['_at'].isna().any():
            continue
        prev = None
        for at, group_at in group.sort_values('_at', kind='stable').groupby('_at', sort=True):
            if len(group_at) != 1:
                model['ambiguous'] += len(group_at)
                prev = None
                continue
            a = group_at.iloc[0][ac]
            if pd.isna(a) or not str(a).strip():
                prev = None
                continue
            a = str(a)
            if prev is not None:
                pa, pt = prev
                e = acc[(ids[pa], ids[a])]
                e['cases'].add(case)
                e['gaps'].append((at - pt).total_seconds() / 86400)
            prev = (a, at)
    for (src, dst), e in sorted(acc.items(), key=lambda item: (-len(item[1]['gaps']), item[0])):
        model['edges'].append(dict(source=src, target=dst, count=len(e['gaps']), cases=len(e['cases']),
                                   days=float(pd.Series(e['gaps']).median()),
                                   kind='repeat' if src == dst else 'return' if dst < src else 'forward'))
    return model

# Every value below is a GSI design token (gsi/design/tokens.py via gsi/design/css.py's
# :root block) rather than a private hex/px literal, so spacing, radius, elevation,
# motion and color stay identical to the rest of the product — including on a future
# brand/theme change, since these diagrams then move with it automatically.
STYLE = '''<style>
.pm-workspace{min-width:0;color:var(--text);font-family:var(--font)}
.pm-workspace *{box-sizing:border-box}
.pm-workspace svg text{font-family:var(--font)}
.pm-workspace .pm-kpis{display:flex;flex-wrap:wrap;gap:var(--sp-sm);margin:var(--sp-md) 0}
.pm-kpi{flex:1;min-width:125px;background:var(--sunken);border:1px solid var(--border);border-radius:var(--r-md);padding:var(--sp-sm) var(--sp-md);box-shadow:var(--e-raised)}
.pm-kpi b{display:block;font-size:26px;line-height:1.35;color:var(--text)}
.pm-kpi span{font-size:12px;color:var(--text-3)}
.pm-toolbar{display:flex;flex-wrap:wrap;gap:var(--sp-xs);align-items:center;justify-content:space-between;margin:var(--sp-sm) 0}
.pm-actions{display:flex;flex-wrap:wrap;gap:6px}
.pm-workspace button,.pm-workspace select{font:inherit;font-size:12px;border:1px solid var(--border-strong);border-radius:var(--r-sm);background:var(--raised);color:var(--text);padding:7px var(--sp-sm);cursor:pointer;min-height:36px;
  transition:background var(--dur-short) var(--ease-standard),box-shadow var(--dur-short) var(--ease-standard)}
.pm-workspace button:hover{background:color-mix(in srgb,var(--teal) 12%,var(--raised));box-shadow:var(--e-overlay)}
.pm-workspace button:disabled{opacity:.42;cursor:not-allowed;box-shadow:none;background:var(--sunken)}
.pm-workspace button:focus-visible,.pm-workspace select:focus-visible{outline:3px solid var(--focus);outline-offset:3px}
.pm-legend{display:flex;flex-wrap:wrap;gap:var(--sp-md);font-size:12px;color:var(--text-3)}
.pm-legend i{display:inline-block;width:25px;border-top:3px solid;margin-inline-end:6px;vertical-align:middle}
.pm-viewport{overflow:auto;background:var(--sunken);border:1px solid var(--border);border-radius:var(--r-lg);direction:ltr;max-height:740px;box-shadow:var(--e-raised)}
.pm-viewport svg{display:block;width:100%;max-width:none!important;min-width:860px;height:auto}
.pm-workspace .pm-note{font-size:12px;color:var(--text-3);line-height:1.9;margin:var(--sp-sm) 0}
.pm-evidence{margin-top:var(--sp-md);border-top:1px solid var(--border);padding-top:var(--sp-sm)}
.pm-evidence summary{cursor:pointer;font-size:13px;font-weight:700;transition:color var(--dur-short) var(--ease-standard)}
.pm-evidence summary:hover{color:var(--teal-ink)}
.pm-table-scroll{overflow:auto;max-height:420px}
.pm-workspace table{width:100%;border-collapse:collapse;white-space:nowrap;font-size:12px}
.pm-workspace th,.pm-workspace td{padding:11px var(--sp-sm);border-bottom:1px solid var(--border);text-align:right}
.pm-workspace th{background:var(--sunken);position:sticky;top:0}
.pm-workspace .pm-selected{background:color-mix(in srgb,var(--teal) 14%,var(--raised))}
.pm-workspace [data-node]{cursor:pointer;outline:none}
.pm-workspace [data-node] rect{transition:filter var(--dur-short) var(--ease-standard)}
.pm-workspace [data-node]:hover rect:first-of-type,.pm-workspace [data-node]:focus rect:first-of-type{filter:drop-shadow(0 3px 7px rgba(11,31,51,.22))}
.pm-workspace [data-node]:focus rect{stroke:var(--navy);stroke-width:3}
.pm-workspace [data-node].pm-node-active rect:first-of-type{stroke:var(--navy);stroke-width:3;filter:drop-shadow(0 5px 11px rgba(11,31,51,.28))}
.pm-workspace [data-edge]{transition:opacity var(--dur-short) var(--ease-standard)}
.pm-workspace .pm-muted{opacity:.14}
.pm-quality{display:flex;flex-wrap:wrap;gap:var(--sp-xs);margin:var(--sp-sm) 0}.pm-qchip{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border-radius:var(--r-pill);background:var(--raised);border:1px solid var(--border);font-size:11px;color:var(--text-2)}.pm-qchip b{color:var(--text)}
.pm-workspace .pm-detail{padding:var(--sp-sm) var(--sp-md);background:color-mix(in srgb,var(--teal) 10%,var(--raised));
  border-inline-start:3px solid var(--teal);border-radius:var(--r-sm);font-size:13px;min-height:46px;line-height:1.8}
.pm-route{display:flex;align-items:center;gap:var(--sp-xs);flex-wrap:wrap;margin:var(--sp-sm) 0}
.pm-route b{background:var(--teal-wash);border:1px solid var(--teal);color:var(--text);border-radius:var(--r-sm);padding:8px 12px;font-weight:600;font-size:13px}
.pm-route span{color:var(--teal-ink)}
.pm-workspace .pm-variant{border:1px solid var(--border);border-radius:var(--r-md);padding:var(--sp-md);margin-top:var(--sp-sm);
  background:var(--raised);box-shadow:var(--e-raised);transition:box-shadow var(--dur-short) var(--ease-standard)}
.pm-workspace .pm-variant:hover{box-shadow:var(--e-overlay)}
.pm-variant-head{display:flex;gap:var(--sp-md);flex-wrap:wrap;align-items:center;justify-content:space-between}
.pm-share{height:6px;background:var(--sunken);border-radius:var(--r-pill);overflow:hidden;margin-top:var(--sp-sm)}
.pm-share i{height:100%;display:block;background:linear-gradient(90deg,var(--navy),var(--teal));transition:width var(--dur-medium) var(--ease-standard)}
@media(max-width:600px){.pm-kpi{min-width:40%;padding:10px}.pm-workspace .pm-kpi b{font-size:22px}.pm-toolbar{align-items:stretch}.pm-toolbar label{width:100%}.pm-viewport{max-height:540px}}
@media print{.pm-toolbar,.pm-detail{display:none!important}.pm-viewport{overflow:visible;max-height:none;border:0;box-shadow:none}.pm-viewport svg{min-width:0;width:100%!important}.pm-workspace .pm-muted{opacity:1}.pm-table-scroll{max-height:none;overflow:visible}.pm-workspace th{position:static}.pm-workspace{break-inside:auto}.pm-evidence{display:block}}
</style>'''

SCRIPT = r'''<script>(function(){
const s=document.currentScript, root=s.previousElementSibling;if(!root||!root.classList.contains('pm-workspace'))return;
const svg=root.querySelector('svg'), view=root.querySelector('.pm-viewport'), detail=root.querySelector('.pm-detail');if(!svg)return;
const edges=Array.from(svg.querySelectorAll('[data-edge]')), nodes=Array.from(svg.querySelectorAll('[data-node]'));
const zoomLabel=root.querySelector('[data-zoom]'), zoomIn=root.querySelector('[data-pm-action="in"]'), zoomOut=root.querySelector('[data-pm-action="out"]');
let zoom=1;
function applyZoom(){svg.style.width=(zoom*100)+'%';zoomLabel.textContent=Math.round(zoom*100)+'%';zoomLabel.setAttribute('aria-label','بزرگ‌نمایی '+Math.round(zoom*100)+' درصد');zoomOut.disabled=zoom<=1;zoomIn.disabled=zoom>=3;}
function focus(id){const node=svg.querySelector('[data-node="'+id+'"]');
 edges.forEach(e=>e.classList.toggle('pm-muted',id!=='' && e.dataset.source!==id && e.dataset.target!==id));
 nodes.forEach(e=>{const related=id!=='' && edges.some(p=>(p.dataset.source===id&&p.dataset.target===e.dataset.node)||(p.dataset.target===id&&p.dataset.source===e.dataset.node));e.classList.toggle('pm-muted',id!=='' && e.dataset.node!==id && !related);e.classList.toggle('pm-node-active',id!==''&&e.dataset.node===id)});
 root.querySelectorAll('tbody tr[data-source]').forEach(e=>e.classList.toggle('pm-selected',id!==''&&(e.dataset.source===id||e.dataset.target===id)));
 detail.textContent=node?node.getAttribute('aria-label'):'یک فعالیت را انتخاب کنید تا مسیرهای مرتبط و شواهد آن برجسته شوند.';
 root.querySelector('select').value=id;
}
nodes.forEach(n=>{n.addEventListener('click',()=>focus(n.dataset.node));n.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();focus(n.dataset.node)}else if(e.key==='Escape'){e.preventDefault();focus('')}})});
window.addEventListener('beforeprint',()=>root.querySelectorAll('details').forEach(d=>{d.dataset.wasOpen=d.open?'1':'0';d.open=true;}));
window.addEventListener('afterprint',()=>root.querySelectorAll('details').forEach(d=>{d.open=d.dataset.wasOpen==='1';}));
root.querySelector('select').addEventListener('change',e=>focus(e.target.value));
root.querySelectorAll('[data-pm-action]').forEach(b=>b.addEventListener('click',()=>{const a=b.dataset.pmAction;
 if(a==='reset'){zoom=1;focus('');view.scrollLeft=0;view.scrollTop=0;}else if(a==='in')zoom=Math.min(3,zoom+.25);else if(a==='out')zoom=Math.max(1,zoom-.25);
 if(a==='svg'){const copy=svg.cloneNode(true);copy.removeAttribute('style');copy.querySelectorAll('[class]').forEach(e=>e.removeAttribute('class'));copy.querySelectorAll('[tabindex]').forEach(e=>e.removeAttribute('tabindex'));const blob=new Blob([new XMLSerializer().serializeToString(copy)],{type:'image/svg+xml;charset=utf-8'});const u=URL.createObjectURL(blob),link=document.createElement('a');link.href=u;link.download='gsi-observed-process.svg';link.click();setTimeout(()=>URL.revokeObjectURL(u),1000);return;}
 applyZoom();
}));
view.addEventListener('keydown',e=>{if(e.key==='+'||e.key==='='){e.preventDefault();zoom=Math.min(3,zoom+.25);applyZoom()}else if(e.key==='-'){e.preventDefault();zoom=Math.max(1,zoom-.25);applyZoom()}else if(e.key==='0'){e.preventDefault();zoom=1;view.scrollLeft=0;view.scrollTop=0;applyZoom()}else if(e.key==='Escape'){focus('')}});
applyZoom();
})();</script>'''

def _text(x, y, text, size=16, color='var(--text)', weight=400, anchor='middle'):
    # SVG start/end are logical under RTL; callers use physical left/right anchors.
    # font-family repeats the CSS var() here (SVG presentation attributes accept
    # var() in every browser this product targets) and is also pinned by the
    # ".pm-workspace svg text" rule in STYLE, so it never silently falls back to
    # a generic sans-serif the way a bare "Tahoma, Arial" literal would.
    anchor = {'start': 'end', 'end': 'start'}.get(anchor, anchor)
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="var(--font)" font-size="{size}" font-weight="{weight}" fill="{color}" direction="rtl" unicode-bidi="plaintext">{esc(text)}</text>'

def _lines(label, limit=22):
    # Full unabridged name remains in the title, detail, selector and evidence table.
    words = str(label).split(); lines = ['']
    for word in words:
        if len(lines[-1]) + len(word) + 1 > limit and lines[-1]: lines.append('')
        lines[-1] += (' ' if lines[-1] else '') + word
    return [(s[:limit-1]+'…' if len(s)>limit else s) for s in lines[:2]][:1] + ([lines[1][:limit-1]+'…' if len(lines)>2 or len(lines[1])>limit else lines[1]] if len(lines)>1 else [])

# Shared soft drop-shadow for node cards, matching .bar-mark/.slice-mark in
# gsi/design/charts_js.py — the same small elevation cue used on every other
# chart mark in the product, so a process-flow node reads as the same kind of
# object as a bar or a donut slice, not a different visual system.
_NODE_SHADOW_DEF = '<defs><filter id="pmNodeShadow" x="-20%" y="-40%" width="140%" height="180%"><feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="rgb(11,31,51)" flood-opacity=".18"/></filter></defs>'

def graph_svg(nodes, edges, title):
    """Deterministic left-to-right layout; labels retain native RTL shaping."""
    shown = nodes[:12]; ids = {n['id']:i for i,n in enumerate(shown)}
    selected = [e for e in edges if e['source'] in ids and e['target'] in ids][:24]
    upper = [e for e in selected if ids[e['target']] > ids[e['source']]+1]
    lower = [e for e in selected if ids[e['target']] <= ids[e['source']]]
    step=278; w=max(1000, len(shown)*step+96); y=112+len(upper)*42; h=y+200+len(lower)*42
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="min-width:{max(860,int(w*.82))}px" role="img" aria-label="{esc(title)}"><title>{esc(title)}</title><desc>مسیرهای مشاهده‌شده از چپ به راست؛ خط‌چین برای بازگشت در چیدمان یا تکرار. اعداد روی اتصال تعداد رخداد گذار هستند.</desc>'+_NODE_SHADOW_DEF+f'<rect width="{w}" height="{h}" fill="var(--sunken)"/>']
    out += [_text(48,36,'OBSERVED PROCESS / مسیر مشاهده‌شده',14,anchor='start'),_text(w-48,36,'جهت خواندن مسیر: چپ به راست',14,anchor='end')]
    maxn=max([e['count'] for e in selected] or [1]); up=0; down=0
    for idx,e in enumerate(selected):
        a,b=ids[e['source']],ids[e['target']]; ax=48+a*step; bx=48+b*step
        color=PALETTE['teal'] if a==b else PALETTE['purple'] if b<a else PALETTE['blue']
        if b==a+1:
            sx,sy,tx,ty=ax+220,y+68,bx,y+68; path=f'M {sx} {sy} H {tx-10}'; lx=(sx+tx)/2;ly=sy-16;head=f'M {tx} {ty} L {tx-12} {ty-5} L {tx-12} {ty+5} Z'
        elif b>a:
            track=70+up*42;up+=1;sx=ax+110;tx=bx+110;ty=y
            path=f'M {sx} {y} V {track} H {tx} V {ty-10}';lx=(sx+tx)/2;ly=track-6;head=f'M {tx} {ty} L {tx-5} {ty-12} L {tx+5} {ty-12} Z'
        else:
            track=y+172+down*42;down+=1;sx=ax+142;tx=bx+78;ty=y+136
            path=f'M {sx} {ty} V {track} H {tx} V {ty+10}';lx=(sx+tx)/2;ly=track+6;head=f'M {tx} {ty} L {tx-5} {ty+12} L {tx+5} {ty+12} Z'
        dash=' stroke-dasharray="7 5"' if b<=a else ''
        out.append(f'<g data-edge="{idx}" data-source="{e["source"]}" data-target="{e["target"]}"><title>{esc(nodes[e["source"]]["label"])} → {esc(nodes[e["target"]]["label"])} · {number(e["count"])} گذار · {number(e["days"],1)} روز</title><path d="{path}" fill="none" stroke="{color}" stroke-width="{2+3*e["count"]/maxn:.1f}" stroke-linecap="round"{dash}/><path d="{head}" fill="{color}"/><rect x="{lx-23}" y="{ly-16}" width="46" height="24" rx="6" fill="var(--raised)" stroke="{color}"/>'+_text(lx,ly+1,number(e['count']),14,color)+ '</g>')
    for n in shown:
        nx=48+ids[n['id']]*step;ny=y
        desc=f'{n["label"]}؛ {number(n["count"])} پرونده رسیده؛ WIP {number(n.get("wip"))}؛ میانه انتظار {number(n.get("wait"),1)} روز'
        out.append(f'<g data-node="{n["id"]}" tabindex="0" role="button" aria-label="{esc(desc)}"><title>{esc(desc)}</title><rect x="{nx}" y="{ny}" width="220" height="136" rx="10" fill="var(--raised)" stroke="var(--teal)" stroke-width="2" filter="url(#pmNodeShadow)"/><rect x="{nx}" y="{ny}" width="220" height="7" rx="3" fill="var(--teal)"/>')
        for j,line in enumerate(_lines(n['label'])):out.append(_text(nx+110,ny+36+j*23,line,16,weight=700))
        out += [_text(nx+110,ny+88,f'{number(n["count"])} پرونده',16),_text(nx+110,ny+115,f'WIP {number(n.get("wip"))}  ·  انتظار {number(n.get("wait"),1)} روز',13,'var(--text-3)'),'</g>']
    out.append('</svg>')
    return ''.join(out),len(shown),len(selected)

def flow_html(extras, uid='flow'):
    model=observed_model(extras.get('eventlog'),extras.get('stage_queue'))
    if not model['nodes']:
        return '<section class="process-viz"><h3>نقشه مسیر مشاهده‌شده</h3><div class="empty">'+esc(model['reason'] or 'فعالیت معتبری موجود نیست.')+'</div></section>'
    svg,nn,ne=graph_svg(model['nodes'],model['edges'],'نقشه جریان واقعی پرونده‌ها')
    options='<option value="">همه فعالیت‌ها</option>'+''.join(f'<option value="{n["id"]}">{esc(n["label"])}</option>' for n in model['nodes'][:12])
    rows=[]
    for e in model['edges']:
        a=model['nodes'][e['source']]['label'];b=model['nodes'][e['target']]['label']
        kind={'forward':'رو به جلو','return':'بازگشت در چیدمان','repeat':'تکرار مشاهده‌شده'}[e['kind']]
        rows.append(f'<tr data-source="{e["source"]}" data-target="{e["target"]}"><td>{esc(a)}</td><td>{esc(b)}</td><td>{number(e["count"])}</td><td>{number(e["cases"])}</td><td>{number(e["days"],1)}</td><td>{kind}</td></tr>')
    kpis=''.join(f'<div class="pm-kpi"><b>{number(v)}</b><span>{label}</span></div>' for v,label in [(model['cases'],'پرونده در دامنه'),(model['events'],'رویداد دارای فعالیت'),(len(model['edges']),'نوع گذار مشاهده‌شده'),(sum(e['count'] for e in model['edges'] if e['kind']=='repeat'),'تکرار متوالی')])
    note=f'نمایش {nn} از {len(model["nodes"])} فعالیت و {ne} از {len(model["edges"])} اتصال؛ جدول زیر همه گذارهای استخراج‌شده را نگه می‌دارد. ترتیب چیدمان از رتبه مرحله؛ اتصال فقط از توالی زمانی همان پرونده. برگشت در چیدمان الزاماً انحراف نیست.'
    quality=f'{model["undated"]} رویداد بدون تاریخ: اتصال‌های پرونده مربوطه محاسبه نشده‌اند. {model["ambiguous"]} رویداد هم‌زمان: اتصال از روی ترتیب نامعلوم ساخته نشده. {model["omitted"]} ردیف فاقد کلید/فعالیت. مقدار ناموجود با «—» نمایش داده می‌شود.'
    toolbar=f'<div class="pm-toolbar"><label>تمرکز بر فعالیت <select aria-label="تمرکز بر فعالیت">{options}</select></label><div class="pm-actions"><button type="button" data-pm-action="in" aria-label="بزرگ‌نمایی" title="بزرگ‌نمایی (+)">＋</button><span data-zoom aria-live="polite">100%</span><button type="button" data-pm-action="out" aria-label="کوچک‌نمایی" title="کوچک‌نمایی (-)">−</button><button type="button" data-pm-action="reset" title="بازگشت به نمای کامل (0)">نمای کامل</button><button type="button" data-pm-action="svg">دریافت SVG</button></div></div>'
    legend=f'<div class="pm-legend"><span><i style="color:{PALETTE["blue"]}"></i>گذار رو به جلو</span><span><i style="color:{PALETTE["purple"]};border-top-style:dashed"></i>بازگشت در چیدمان</span><span><i style="color:{PALETTE["teal"]};border-top-style:dashed"></i>تکرار فعالیت</span><span>ضخامت / عدد خط = تعداد گذار</span></div>'
    quality_strip=(f'<div class="pm-quality" role="status" aria-label="کیفیت شواهد فرآیند">'
                   f'<span class="pm-qchip"><b>{number(model["undated"])}</b> بدون تاریخ</span>'
                   f'<span class="pm-qchip"><b>{number(model["ambiguous"])}</b> هم‌زمان/مبهم</span>'
                   f'<span class="pm-qchip"><b>{number(model["omitted"])}</b> فاقد کلید/فعالیت</span></div>')
    table='<details class="pm-evidence"><summary>شواهد گذارها · تعداد پرونده و فاصله زمانی</summary><div class="pm-table-scroll"><table><thead><tr><th>از فعالیت</th><th>به فعالیت</th><th>تعداد گذار</th><th>پرونده یکتا</th><th>میانه فاصله (روز)</th><th>نوع مسیر</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></details>'
    # STYLE is injected once by the caller (_process_suite_html), not per-view —
    # see variants_html for the same convention and why.
    return '<section class="process-viz pm-workspace" dir="rtl"><div class="pv-head"><div><span class="t-overline">PROCESS EXPLORER</span><h3>مسیر واقعی پرونده‌ها</h3><p>حرکت، تکرار و فاصله زمانی بین رویدادها</p></div><span class="badge badge--quiet">آفلاین · SVG</span></div><div class="pm-kpis">'+kpis+'</div>'+legend+quality_strip+toolbar+'<div class="pm-viewport" tabindex="0" aria-label="نقشه قابل پیمایش">'+svg+'</div><p class="pm-note">'+esc(note)+'</p><div class="pm-detail" aria-live="polite">یک فعالیت را انتخاب کنید تا مسیرهای مرتبط و شواهد آن برجسته شوند.</div>'+table+'<p class="pm-note">'+esc(model['reason'])+' '+esc(quality)+' فاصله رویدادها زمان کار خالص یا SLA نیست.</p></section>'+SCRIPT

def variants_html(frame):
    if not isinstance(frame,pd.DataFrame) or frame.empty:
        return '<section class="process-viz"><h3>مسیرهای پرتکرار</h3><div class="empty">Variant کافی موجود نیست.</div></section>'
    cards=[]
    for i,r in enumerate(frame.head(10).to_dict('records'),1):
        raw=r.get('VARIANT',r.get('مسیر',''))
        route='' if pd.isna(raw) else str(raw)
        # This delimiter is the canonical serializer in s80_eventlog.py.
        steps=route.split(' ← ')
        badges='<span aria-hidden="true">←</span>'.join('<b>'+esc(s)+'</b>' for s in steps)
        share=pd.to_numeric(r.get('سهم (٪)'),errors='coerce')
        bar=f'<div class="pm-share"><i style="width:{min(100,max(0,float(share))):.2f}%"></i></div>' if pd.notna(share) else ''
        cards.append(f'<article class="pm-variant"><div class="pm-variant-head"><strong>مسیر {i:02d}</strong><span>{number(r.get("تعداد پرونده"))} پرونده · سهم {number(share,1)}٪</span></div><div class="pm-route">{badges}</div><div class="pm-note">بسته: {number(r.get("پرونده بسته"))} · میانه چرخه: {number(r.get("میانه چرخه"),1)} روز</div>{bar}</article>')
    # STYLE is injected once by the caller (_process_suite_html) so two views on
    # the same page (flow_map + variants) don't each embed their own copy of it.
    return '<section class="process-viz pm-workspace" dir="rtl"><span class="t-overline">VARIANT EXPLORER</span><h3>مسیرهای پرتکرار؛ مقایسه توالی فعالیت‌ها</h3><p class="pm-note">طول نوار، سهم واقعی از کل است؛ پرتکرار بودن به معنی بهتر بودن مسیر نیست. نمایش '+str(min(10,len(frame)))+' از '+str(len(frame))+' مسیر.</p>'+''.join(cards)+'</section>'

