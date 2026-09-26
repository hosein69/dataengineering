# -*- coding: utf-8 -*-
"""Interactive, offline HTML report customizer for GSI.

Presentation only: this module never mutates embedded report data, filters,
metrics, process semantics, evidence, or warehouse state.  It adds a local
layout editor to self-contained HTML exports so recipients can reorder, resize,
hide/restore and export a customized standalone HTML file.
"""
from __future__ import annotations

__contract__ = 1

SEED_HTML = '<script id="gsi-layout-seed" type="application/json">{}</script>'

TOOLBAR_HTML = r'''
<section id="gsi_customizer" class="gsi-customizer no-print" hidden aria-label="سفارشی‌سازی خروجی HTML">
  <div class="gsi-customizer__head">
    <div>
      <strong>سفارشی‌سازی خروجی HTML</strong>
      <span>جابه‌جایی، تغییر اندازه و حذف فقط ظاهر گزارش را تغییر می‌دهد؛ داده و محاسبات دست‌نخورده می‌ماند.</span>
    </div>
    <button type="button" class="btn btn--secondary btn--sm" data-gsi-custom-action="close">بستن ویرایش</button>
  </div>
  <div class="gsi-customizer__actions">
    <button type="button" class="btn btn--decision btn--sm" data-gsi-custom-action="download">⬇ دانلود HTML سفارشی</button>
    <button type="button" class="btn btn--secondary btn--sm" data-gsi-custom-action="restore">↩ بازگردانی موارد حذف‌شده</button>
    <button type="button" class="btn btn--secondary btn--sm" data-gsi-custom-action="reset">⟲ بازنشانی چیدمان</button>
  </div>
  <div class="gsi-customizer__hint">برای جابه‌جایی، دستگیره ⠿ را بکشید. دکمه‌های ↑ و ↓ جایگزین دسترس‌پذیر Drag & Drop هستند. اندازه هر بلوک را از فهرست همان بلوک تغییر دهید.</div>
  <div id="gsi_custom_hidden" class="gsi-custom-hidden" aria-live="polite"></div>
</section>
'''

CSS = r'''
/* ── GSI HTML Layout Customizer ────────────────────────────────────────── */
.gsi-customizer{border:1px solid var(--border,#dbe3e7);background:var(--raised,#fff);border-radius:16px;padding:14px 16px;box-shadow:0 10px 30px rgba(11,31,51,.08)}
.gsi-customizer__head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap}
.gsi-customizer__head>div{display:grid;gap:4px;min-width:0}.gsi-customizer__head strong{font-size:15px}.gsi-customizer__head span,.gsi-customizer__hint{font-size:12px;line-height:1.75;color:var(--text-2,#526575)}
.gsi-customizer__actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.gsi-customizer__hint{margin-top:10px}
.gsi-custom-hidden{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.gsi-custom-hidden:empty{display:none}
.gsi-custom-hidden button{border:1px dashed var(--border,#dbe3e7);background:transparent;border-radius:999px;padding:6px 10px;font:inherit;font-size:11px;cursor:pointer;color:var(--text,#0b1f33)}
.gsi-edit-mode [data-gsi-custom-item]{position:relative;outline:1px dashed rgba(10,124,134,.45);outline-offset:3px;min-width:0}
.gsi-edit-mode [data-gsi-custom-item].gsi-dragging{opacity:.5}.gsi-edit-mode [data-gsi-custom-item].gsi-drop-before{box-shadow:inset 0 4px 0 var(--brand,#0a7c86)}
.gsi-edit-mode [data-gsi-custom-item].gsi-drop-after{box-shadow:inset 0 -4px 0 var(--brand,#0a7c86)}
.gsi-edit-controls{display:none;position:absolute;z-index:40;top:6px;left:6px;direction:rtl;align-items:center;gap:4px;padding:4px;background:rgba(255,255,255,.96);border:1px solid var(--border,#dbe3e7);border-radius:10px;box-shadow:0 6px 18px rgba(11,31,51,.12)}
.gsi-edit-mode .gsi-edit-controls{display:flex}.gsi-edit-controls button,.gsi-edit-controls select{min-height:32px;border:1px solid var(--border,#dbe3e7);background:#fff;color:var(--text,#0b1f33);border-radius:7px;font:inherit;font-size:11px;padding:3px 7px}
.gsi-edit-controls .gsi-drag-handle{cursor:grab;font-weight:900;min-width:34px}.gsi-edit-controls .gsi-drag-handle:active{cursor:grabbing}
[data-gsi-hidden="true"]{display:none!important}
.gsi-custom-grid{display:grid!important;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px;align-items:start}
.gsi-custom-grid>[data-gsi-custom-item][data-gsi-size="full"]{grid-column:span 12}
.gsi-custom-grid>[data-gsi-custom-item][data-gsi-size="half"]{grid-column:span 6}
.gsi-custom-grid>[data-gsi-custom-item][data-gsi-size="third"]{grid-column:span 4}
.gsi-custom-grid>[data-gsi-custom-item][data-gsi-size="quarter"]{grid-column:span 3}
.gsi-custom-grid>[data-gsi-custom-item][data-gsi-size="auto"]{grid-column:span 6}
.gsi-custom-grid>.toolbar{grid-column:1/-1}
.gsi-custom-grid>.process-suite-head{grid-column:1/-1}
@media(max-width:900px){.gsi-custom-grid>[data-gsi-custom-item][data-gsi-size="third"],.gsi-custom-grid>[data-gsi-custom-item][data-gsi-size="quarter"]{grid-column:span 6}}
@media(max-width:680px){.gsi-custom-grid>[data-gsi-custom-item]{grid-column:1/-1!important}.gsi-edit-controls{position:relative;top:auto;left:auto;margin:0 0 8px;flex-wrap:wrap}}
@media print{#gsi_customizer,[data-gsi-custom-action],.gsi-edit-controls{display:none!important}.gsi-edit-mode [data-gsi-custom-item]{outline:none!important}}
'''

JS = r'''
(function(){
'use strict';
const STORAGE_KEY='gsi_html_layout_v2::'+document.title;
let editMode=false;
let state={version:2,scopes:{}};
let baseline=null;
let dragItem=null;

function parseSeed(){
 const el=document.getElementById('gsi-layout-seed');
 if(!el)return null;
 try{const v=JSON.parse(el.textContent||'{}');return v&&v.scopes&&Object.keys(v.scopes).length?v:null}catch(_){return null}
}
function readStored(){try{const v=JSON.parse(localStorage.getItem(STORAGE_KEY)||'null');return v&&v.scopes?v:null}catch(_){return null}}
function writeStored(){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(state))}catch(_){}
}
function escSel(v){return (window.CSS&&CSS.escape)?CSS.escape(v):String(v).replace(/["\\]/g,'\\$&')}
function itemKey(el){return el.dataset.gsiItemKey||''}
function labelFor(el){
 if(el.dataset.gsiLabel)return el.dataset.gsiLabel;
 const h=el.querySelector('h2,h3,h4,figcaption');
 return (h&&h.textContent||itemKey(el)||'بخش').trim().replace(/\s+/g,' ').slice(0,70)
}
function defaultSize(el){return el.dataset.gsiDefaultSize||'full'}
function markStructure(){
 document.querySelectorAll('.pane').forEach((pane,pi)=>{
   pane.dataset.gsiScope='pane:'+(pane.id||pi);
   pane.classList.add('gsi-custom-grid');
   pane.querySelectorAll(':scope > section[data-composer-block]').forEach(el=>{
     el.dataset.gsiCustomItem='block';
     el.dataset.gsiItemKey='block:'+el.dataset.composerBlock;
     el.dataset.gsiDefaultSize='full';
     if(!el.dataset.gsiSize)el.dataset.gsiSize='full';
   });
   pane.querySelectorAll('[id^="charts_"]').forEach((box,ci)=>{
     box.dataset.gsiScope='charts:'+(pane.id||pi)+':'+ci;
     box.classList.add('gsi-custom-grid');
     box.querySelectorAll(':scope > .gsi-chart-item').forEach(el=>{
       el.dataset.gsiCustomItem='chart';
       el.dataset.gsiDefaultSize='half';
       if(!el.dataset.gsiSize)el.dataset.gsiSize='half';
     });
   });
   pane.querySelectorAll('.process-suite').forEach((box,si)=>{
     box.dataset.gsiScope='process:'+(pane.id||pi)+':'+si;
     box.classList.add('gsi-custom-grid');
     box.querySelectorAll(':scope > .gsi-process-item').forEach(el=>{
       el.dataset.gsiCustomItem='process';
       el.dataset.gsiDefaultSize='full';
       if(!el.dataset.gsiSize)el.dataset.gsiSize='full';
     });
   });
 });
}
function scopes(){return [...document.querySelectorAll('[data-gsi-scope]')].filter(x=>x.querySelector(':scope > [data-gsi-custom-item]'))}
function capture(){
 const out={version:2,scopes:{}};
 scopes().forEach(box=>{out.scopes[box.dataset.gsiScope]=[...box.querySelectorAll(':scope > [data-gsi-custom-item]')].map(el=>({key:itemKey(el),size:el.dataset.gsiSize||defaultSize(el),hidden:el.dataset.gsiHidden==='true'}))});
 return out
}
function apply(layout){
 if(!layout||!layout.scopes)return;
 markStructure();
 scopes().forEach(box=>{
   const spec=layout.scopes[box.dataset.gsiScope];if(!Array.isArray(spec))return;
   const byKey=new Map([...box.querySelectorAll(':scope > [data-gsi-custom-item]')].map(el=>[itemKey(el),el]));
   spec.forEach(it=>{const el=byKey.get(it.key);if(!el)return;el.dataset.gsiSize=it.size||defaultSize(el);el.dataset.gsiHidden=it.hidden?'true':'false';box.appendChild(el);byKey.delete(it.key)});
   byKey.forEach(el=>{if(!el.dataset.gsiSize)el.dataset.gsiSize=defaultSize(el);if(!el.dataset.gsiHidden)el.dataset.gsiHidden='false'});
 });
 refreshControls();renderHidden();
}
function persist(){state=capture();writeStored();renderHidden()}
function move(el,delta){
 const box=el.parentElement;if(!box)return;const items=[...box.querySelectorAll(':scope > [data-gsi-custom-item]')];const i=items.indexOf(el),j=Math.max(0,Math.min(items.length-1,i+delta));if(i===j)return;
 if(j>i)box.insertBefore(el,items[j].nextSibling);else box.insertBefore(el,items[j]);persist();
}
function controlBar(el){
 let bar=el.querySelector(':scope > .gsi-edit-controls');if(bar)return bar;
 bar=document.createElement('div');bar.className='gsi-edit-controls no-print';bar.setAttribute('aria-label','کنترل چیدمان '+labelFor(el));
 const drag=document.createElement('button');drag.type='button';drag.className='gsi-drag-handle';drag.textContent='⠿';drag.title='برای جابه‌جایی بکشید';
 const up=document.createElement('button');up.type='button';up.textContent='↑';up.title='انتقال به بالا/قبل';up.addEventListener('click',()=>move(el,-1));
 const down=document.createElement('button');down.type='button';down.textContent='↓';down.title='انتقال به پایین/بعد';down.addEventListener('click',()=>move(el,1));
 const size=document.createElement('select');size.title='اندازه بلوک';[['full','تمام'],['half','نیم'],['third','یک‌سوم'],['quarter','یک‌چهارم']].forEach(([v,t])=>{const o=document.createElement('option');o.value=v;o.textContent=t;size.appendChild(o)});size.value=el.dataset.gsiSize==='auto'?'half':(el.dataset.gsiSize||defaultSize(el));size.addEventListener('change',()=>{el.dataset.gsiSize=size.value;persist()});
 const hide=document.createElement('button');hide.type='button';hide.textContent='✕';hide.title='حذف از خروجی';hide.addEventListener('click',()=>{el.dataset.gsiHidden='true';persist()});
 bar.append(drag,up,down,size,hide);el.prepend(bar);return bar
}
function bindDrag(el){
 if(el.dataset.gsiDragBound==='1')return;el.dataset.gsiDragBound='1';
 el.addEventListener('dragstart',e=>{if(!editMode){e.preventDefault();return}dragItem=el;el.classList.add('gsi-dragging');try{e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',itemKey(el))}catch(_){} });
 el.addEventListener('dragend',()=>{el.classList.remove('gsi-dragging');document.querySelectorAll('.gsi-drop-before,.gsi-drop-after').forEach(x=>x.classList.remove('gsi-drop-before','gsi-drop-after'));dragItem=null;persist()});
 el.addEventListener('dragover',e=>{if(!editMode||!dragItem||dragItem===el||dragItem.parentElement!==el.parentElement)return;e.preventDefault();const r=el.getBoundingClientRect(),after=(e.clientY-r.top)>r.height/2;el.classList.toggle('gsi-drop-after',after);el.classList.toggle('gsi-drop-before',!after)});
 el.addEventListener('dragleave',()=>el.classList.remove('gsi-drop-before','gsi-drop-after'));
 el.addEventListener('drop',e=>{if(!editMode||!dragItem||dragItem===el||dragItem.parentElement!==el.parentElement)return;e.preventDefault();const r=el.getBoundingClientRect(),after=(e.clientY-r.top)>r.height/2;el.classList.remove('gsi-drop-before','gsi-drop-after');el.parentElement.insertBefore(dragItem,after?el.nextSibling:el);persist()});
}
function refreshControls(){
 markStructure();
 document.querySelectorAll('[data-gsi-custom-item]').forEach(el=>{controlBar(el);bindDrag(el);el.draggable=editMode});
}
function renderHidden(){
 const box=document.getElementById('gsi_custom_hidden');if(!box)return;box.innerHTML='';
 const hidden=[...document.querySelectorAll('[data-gsi-custom-item][data-gsi-hidden="true"]')];
 hidden.forEach(el=>{const b=document.createElement('button');b.type='button';b.textContent='↩ '+labelFor(el);b.addEventListener('click',()=>{el.dataset.gsiHidden='false';persist()});box.appendChild(b)});
 if(!hidden.length){const s=document.createElement('span');s.className='note';s.textContent='هیچ بخشی از خروجی حذف نشده است.';box.appendChild(s)}
}
function setEdit(on){editMode=!!on;document.body.classList.toggle('gsi-edit-mode',editMode);const p=document.getElementById('gsi_customizer');if(p)p.hidden=!editMode;const t=document.querySelector('[data-gsi-custom-action="toggle"]');if(t)t.setAttribute('aria-pressed',String(editMode));refreshControls()}
function restoreHidden(){document.querySelectorAll('[data-gsi-custom-item][data-gsi-hidden="true"]').forEach(el=>el.dataset.gsiHidden='false');persist()}
function resetLayout(){if(!baseline)return;state=JSON.parse(JSON.stringify(baseline));try{localStorage.removeItem(STORAGE_KEY)}catch(_){}apply(state)}
function cleanedClone(){
 const clone=document.documentElement.cloneNode(true);clone.querySelector('body')?.classList.remove('gsi-edit-mode');
 clone.querySelectorAll('.gsi-edit-controls').forEach(x=>x.remove());clone.querySelectorAll('[draggable]').forEach(x=>x.removeAttribute('draggable'));clone.querySelectorAll('[data-gsi-drag-bound]').forEach(x=>x.removeAttribute('data-gsi-drag-bound'));
 const panel=clone.querySelector('#gsi_customizer');if(panel)panel.hidden=true;const tog=clone.querySelector('[data-gsi-custom-action="toggle"]');if(tog)tog.setAttribute('aria-pressed','false');
 const seed=clone.querySelector('#gsi-layout-seed');if(seed)seed.textContent=JSON.stringify(capture());
 return '<!doctype html>\n'+clone.outerHTML
}
function downloadCustom(){persist();const blob=new Blob([cleanedClone()],{type:'text/html;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='GSI_custom_'+new Date().toISOString().slice(0,10)+'.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function bindGlobal(){
 document.querySelectorAll('[data-gsi-custom-action="toggle"]').forEach(b=>b.addEventListener('click',()=>setEdit(!editMode)));
 document.querySelectorAll('[data-gsi-custom-action="close"]').forEach(b=>b.addEventListener('click',()=>setEdit(false)));
 document.querySelectorAll('[data-gsi-custom-action="download"]').forEach(b=>b.addEventListener('click',downloadCustom));
 document.querySelectorAll('[data-gsi-custom-action="restore"]').forEach(b=>b.addEventListener('click',restoreHidden));
 document.querySelectorAll('[data-gsi-custom-action="reset"]').forEach(b=>b.addEventListener('click',resetLayout));
}
window.gsiCustomizerRefresh=function(){markStructure();if(state&&state.scopes)apply(state);else refreshControls()};
markStructure();baseline=capture();state=parseSeed()||readStored()||JSON.parse(JSON.stringify(baseline));apply(state);bindGlobal();setEdit(false);
})();
'''
