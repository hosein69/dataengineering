# -*- coding: utf-8 -*-
"""لایه حرکت — جلوه‌های بصری که به موس واکنش نشان می‌دهند.

Streamlit تگ ``<script>`` را از ``st.markdown`` حذف می‌کند، پس JS فقط داخل
``components.html`` (یک iframe هم‌مبدأ) اجرا می‌شود. دو تکنیک اینجا:

1. **هدر زنده** — یک بوم که ذراتش دنبال نشانگر می‌آیند و خطوط بین آن‌ها
   با نزدیک شدن موس پررنگ می‌شود. کاملاً خودبسنده داخل iframe.
2. **درخشش نشانگر روی کل صفحه** — یک اسکریپت کوچک که *در صورت امکان* به
   `window.parent.document` دست می‌زند و مختصات موس را روی متغیرهای CSS
   می‌نویسد. اگر مرورگر اجازه ندهد، بی‌صدا رد می‌شود و چیزی نمی‌شکند
   (بهسازی تدریجی — نه وابستگی).

کارت‌ها خودشان با CSS خالص به هاور واکنش می‌دهند (بلند شدن، درخشش لبه،
عبور نور)، چون CSS نیازی به JS ندارد و همیشه کار می‌کند.
"""
from __future__ import annotations

import json

import streamlit.components.v1 as components

from .theme import BRAND, BRAND_DEEP, FONT_STACK, TEXT, TEXT_SECONDARY


def hero(title: str, subtitle: str, stats: list, height: int = 240) -> None:
    """هدر زنده با بوم ذرات که به موس واکنش می‌دهد.

    ``stats``: فهرست ``(برچسب، مقدار، رنگ)`` که روی بوم شناور می‌شود.
    """
    payload = json.dumps({"title": title, "subtitle": subtitle, "stats": stats},
                         ensure_ascii=False)
    components.html(f"""
<div id="wrap">
  <canvas id="c"></canvas>
  <div id="ov">
    <div id="txt"><h1 id="t"></h1><p id="s"></p></div>
    <div id="stats"></div>
  </div>
</div>
<style>
  *{{box-sizing:border-box}}
  html,body{{margin:0;padding:0;background:transparent;overflow:hidden}}
  #wrap{{position:relative;width:100%;height:{height}px;border-radius:20px;
    overflow:hidden;background:linear-gradient(120deg,{BRAND_DEEP},{BRAND} 55%,#12908c);
    direction:rtl;font-family:{FONT_STACK}}}
  #c{{position:absolute;inset:0;width:100%;height:100%;display:block}}
  #ov{{position:absolute;inset:0;display:flex;align-items:center;
    justify-content:space-between;padding:26px 34px;pointer-events:none}}
  #t{{margin:0;font-size:34px;font-weight:700;color:#fff;letter-spacing:-.5px;
    text-shadow:0 2px 18px rgba(0,0,0,.28)}}
  #s{{margin:8px 0 0;font-size:14px;color:rgba(255,255,255,.86)}}
  #stats{{display:flex;gap:14px}}
  .st{{background:rgba(255,255,255,.13);backdrop-filter:blur(9px);
    -webkit-backdrop-filter:blur(9px);border:1px solid rgba(255,255,255,.22);
    border-radius:14px;padding:12px 16px;min-width:104px;text-align:center;
    transition:transform .45s cubic-bezier(.2,.8,.2,1),background .45s}}
  .st .v{{font-size:24px;font-weight:700;color:#fff;line-height:1.15}}
  .st .l{{font-size:11px;color:rgba(255,255,255,.82);margin-top:3px}}
  .st .d{{width:22px;height:3px;border-radius:2px;margin:7px auto 0}}
  @media (prefers-reduced-motion:reduce){{ .st{{transition:none}} }}
</style>
<script>
const D = {payload};
document.getElementById('t').textContent = D.title;
document.getElementById('s').textContent = D.subtitle;
document.getElementById('stats').innerHTML = D.stats.map(function(s){{
  return '<div class="st"><div class="v">'+s[1]+'</div><div class="l">'+s[0]+
         '</div><div class="d" style="background:'+s[2]+'"></div></div>';
}}).join('');

const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
let W=0, H=0, pts=[], mouse={{x:-9999,y:-9999}}, raf=null;

function size(){{
  const r = cv.getBoundingClientRect(), dpr = Math.min(devicePixelRatio||1, 2);
  W = r.width; H = r.height;
  cv.width = W*dpr; cv.height = H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  const n = Math.max(26, Math.min(70, Math.round(W/17)));
  pts = Array.from({{length:n}}, function(){{
    return {{x:Math.random()*W, y:Math.random()*H,
             vx:(Math.random()-.5)*.28, vy:(Math.random()-.5)*.28,
             r:Math.random()*1.7+.9}};
  }});
}}
addEventListener('resize', size);

const wrap = document.getElementById('wrap');
wrap.addEventListener('pointermove', function(e){{
  const r = cv.getBoundingClientRect();
  mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top;
  // کارت‌های آمار با فاصله از نشانگر کمی جابه‌جا می‌شوند (پارالاکس)
  document.querySelectorAll('.st').forEach(function(el){{
    const b = el.getBoundingClientRect();
    const dx = (e.clientX - (b.left+b.width/2))/26;
    const dy = (e.clientY - (b.top+b.height/2))/26;
    const d  = Math.hypot(dx,dy);
    const k  = Math.max(0, 1 - d/16);
    el.style.transform = 'translate('+(-dx*k*1.5).toFixed(2)+'px,'+
                          (-dy*k*1.5).toFixed(2)+'px) scale('+(1+k*.05).toFixed(3)+')';
    el.style.background = 'rgba(255,255,255,'+(0.13+k*0.11).toFixed(3)+')';
  }});
}});
wrap.addEventListener('pointerleave', function(){{
  mouse.x = mouse.y = -9999;
  document.querySelectorAll('.st').forEach(function(el){{
    el.style.transform=''; el.style.background='';
  }});
}});

function frame(){{
  ctx.clearRect(0,0,W,H);
  for (const p of pts){{
    p.x += p.vx; p.y += p.vy;
    if (p.x<0||p.x>W) p.vx*=-1;
    if (p.y<0||p.y>H) p.vy*=-1;
    // جذب ملایم به سمت نشانگر
    const dx = mouse.x-p.x, dy = mouse.y-p.y, d = Math.hypot(dx,dy);
    if (d < 150){{ p.x += dx/d*0.5; p.y += dy/d*0.5; }}
  }}
  // خطوط بین ذرات نزدیک — نزدیک نشانگر پررنگ‌تر
  for (let i=0;i<pts.length;i++){{
    for (let j=i+1;j<pts.length;j++){{
      const a=pts[i], b=pts[j], d=Math.hypot(a.x-b.x, a.y-b.y);
      if (d < 108){{
        const mx=(a.x+b.x)/2, my=(a.y+b.y)/2;
        const near = Math.max(0, 1 - Math.hypot(mouse.x-mx, mouse.y-my)/190);
        ctx.strokeStyle = 'rgba(255,255,255,'+((1-d/108)*(0.10+near*0.42)).toFixed(3)+')';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
      }}
    }}
  }}
  for (const p of pts){{
    const near = Math.max(0, 1 - Math.hypot(mouse.x-p.x, mouse.y-p.y)/190);
    ctx.fillStyle = 'rgba(255,255,255,'+(0.34+near*0.5).toFixed(3)+')';
    ctx.beginPath(); ctx.arc(p.x, p.y, p.r*(1+near*0.7), 0, 6.2832); ctx.fill();
  }}
  raf = requestAnimationFrame(frame);
}}
size();
if (reduced) {{ frame(); cancelAnimationFrame(raf); }} else {{ frame(); }}
</script>
""", height=height + 8)


def cursor_glow() -> None:
    """درخشش نرمی که دنبال نشانگر می‌آید — روی کل صفحه.

    تلاش می‌کند به سند والد دست بزند؛ اگر مرورگر اجازه ندهد بی‌صدا رد
    می‌شود. هیچ بخشی از رابط به این وابسته نیست.
    """
    components.html("""
<script>
(function(){
  try{
    var d = window.parent && window.parent.document;
    if(!d || d.getElementById('aibl-glow')) return;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var g = d.createElement('div');
    g.id = 'aibl-glow';
    g.style.cssText = 'position:fixed;left:0;top:0;width:520px;height:520px;'+
      'margin:-260px 0 0 -260px;border-radius:50%;pointer-events:none;z-index:0;'+
      'background:radial-gradient(circle,rgba(15,110,110,.10) 0%,rgba(15,110,110,.05) 38%,transparent 66%);'+
      'transition:opacity .5s;opacity:0;will-change:transform';
    d.body.appendChild(g);
    var tx=0,ty=0,cx=0,cy=0;
    d.addEventListener('pointermove',function(e){ tx=e.clientX; ty=e.clientY; g.style.opacity='1'; });
    d.addEventListener('pointerleave',function(){ g.style.opacity='0'; });
    (function loop(){
      cx += (tx-cx)*0.085; cy += (ty-cy)*0.085;
      g.style.transform = 'translate('+cx.toFixed(1)+'px,'+cy.toFixed(1)+'px)';
      requestAnimationFrame(loop);
    })();
  }catch(e){ /* مبدأ متفاوت — بی‌صدا رد شو */ }
})();
</script>
""", height=0)
