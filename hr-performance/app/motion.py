# -*- coding: utf-8 -*-
"""لایه حرکت — جلوه‌های بصری که به موس واکنش نشان می‌دهند.

نسخهٔ همسانِ ``aibl-supply-chain/app/motion.py``. عمداً کپی شده تا دو
پکیج مستقل بمانند؛ هر تغییر باید در **هر دو** اعمال شود.

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

from hrperf.report.theme import FONT_STACK
from hrperf.report import alborz as _AL
from hrperf.report import paykan as _pk



def hero(title: str, subtitle: str, stats: list, height: int = 240,
         kicker: str = "IKCO · GLOBAL SOURCING (GS) · DATA ANALYTICS AND KPI") -> None:
    """سربرگِ زنده — **همان سربرگِ پوستر، که نفس می‌کشد**.

    تا حالا این نوار نویزِ خودش را داشت: ذراتی که تصادفی پخش می‌شدند.
    حالا ذرات از همان ۱۱۳ نقطهٔ «غبار داده»ی قالب شروع می‌کنند
    (``narrative.dust()``)، پس حالتِ سکونِ نوار عیناً قالب است و حرکت،
    انحرافِ نرمی حول همان نقطه‌هاست. کاربر همان چیزی را می‌بیند که در
    پوستر و گزارش دیده، فقط زنده.

    نشان و خودرو هم همان پرونده‌های قالب‌اند (``report/assets``). اگر
    نبودند، نشان کشیده نمی‌شود و خودرو به نقش‌مایهٔ برداری برمی‌گردد.

    ``stats``: فهرست ``(برچسب، مقدار، رنگ)``.
    """
    from hrperf.report import narrative as _NR
    from hrperf.report import assets as _AS

    # نقطه‌ها روی صحنهٔ ۹۰۰×۵۲۰ قالب‌اند؛ به نسبت، نه به پیکسل، می‌روند
    # تا در هر عرضی همان الگو بماند.
    seeds = [[round(x / 900, 5), round(y / 520, 5), d / 2, o]
             for x, y, d, o in _NR.dust()]
    payload = json.dumps({"title": title, "subtitle": subtitle,
                          "stats": stats, "seeds": seeds,
                          "dust": _AL.DUST, "gold": _AL.GOLD},
                         ensure_ascii=False)

    emblem = _AS.img("emblem", 104) or ""
    car = _AS.img("paykan", 300) or _pk.svg(
        288, uid="hero", ground=False, crop=True, inline=True,
        body=_AL.TEAL_MID, glass=_AL.TEAL_EDGE, shade=_AL.TEAL_DEEP,
        chrome=_AL.TEAL_EDGE, tyre=_AL.TEAL_DEEP)
    grain = _NR._grain_uri()

    components.html(f"""
<div id="wrap">
  <canvas id="c"></canvas>
  <div id="grain"></div>
  <div id="emb">{emblem}</div>
  <div id="car">{car}</div>
  <div id="rule"></div>
  <div id="ov">
    <div id="txt"><div id="k"></div><h1 id="t"></h1><p id="s"></p></div>
    <div id="stats"></div>
  </div>
</div>
<style>
  *{{box-sizing:border-box}}
  html,body{{margin:0;padding:0;background:transparent;overflow:hidden}}
  #wrap{{position:relative;width:100%;height:{height}px;border-radius:20px;
    overflow:hidden;direction:rtl;font-family:{FONT_STACK};
    background:{_AL.header_gradient_css(_AL.HEADER_ANGLE)};
    box-shadow:inset 0 9px 18px -2px {_AL.rgba(_AL.EMBOSS_DARK, .34)},
               inset 0 -4px 12px -3px {_AL.rgba(_AL.EMBOSS_LIGHT, .12)}}}
  #c{{position:absolute;inset:0;width:100%;height:100%;display:block}}
  /* همان بافتِ قالب — بدون آن، نوار پلاستیکی به‌نظر می‌رسد */
  #grain{{position:absolute;inset:0;pointer-events:none;z-index:2;
    background-image:url({grain});background-size:200px 200px;
    mix-blend-mode:overlay;opacity:.14}}
  /* نشان: فیزیکاً چپ، مثل قالب. screen + همان زنجیرهٔ فیلتر. */
  #emb{{position:absolute;left:26px;top:18px;width:104px;z-index:3;
    opacity:.92;mix-blend-mode:screen;pointer-events:none}}
  #emb img,#emb svg{{width:100%;height:auto;display:block;
    filter:grayscale(1) brightness(1.08) sepia(.6) hue-rotate(118deg)
           saturate(1.7) drop-shadow(0 0 7px {_AL.rgba(_AL.ICE, .28)})}}
  /* خودرو **وسط** می‌نشیند، نه راست و نه چپ: راست را عنوان گرفته و
     چپ را کارت‌های آمار. نوار کوتاه است و جای سومی نیست. */
  #car{{position:absolute;left:50%;transform:translateX(-50%);bottom:-16px;
    width:270px;max-width:26%;opacity:.45;z-index:1;pointer-events:none;
    filter:drop-shadow(0 10px 18px rgba(0,0,0,.22))}}
  #car img,#car svg{{width:100%;height:auto;display:block}}
  #rule{{position:absolute;left:34px;right:34px;top:46px;height:.5px;z-index:2;
    background:{_AL.rgba(_AL.DUST, .094)}}}
  /* حاشیهٔ انتهاییِ ۱۵۰ جا را برای نشان باز می‌کند؛ بدون آن اولین
     کارتِ آمار روی نشان می‌افتد. در راست‌به‌چپ، انتها یعنی چپ. */
  #ov{{position:absolute;inset:0;display:flex;align-items:center;
    justify-content:space-between;padding:26px 34px;
    padding-inline-end:150px;pointer-events:none;z-index:4}}
  #k{{font-size:11px;font-weight:500;letter-spacing:2px;opacity:.7;
    color:{_AL.ON_TEAL_2};margin-bottom:9px}}
  /* عنوان با همان حکِ قالب: متنِ طیفی و سایهٔ دولایه. */
  #t{{margin:0;font-size:32px;font-weight:900;line-height:1.08;
    color:{_AL.TITLE_TOP};
    background-image:linear-gradient({_AL.TITLE_ANGLE},
      {_AL.TITLE_TOP} 25%,{_AL.TITLE_BOT} 75%);
    -webkit-background-clip:text;background-clip:text;
    -webkit-text-fill-color:transparent;
    text-shadow:2px 4px 3px {_AL.rgba(_AL.ENGRAVE_DARK, .69)},
                -1px -1px 1.5px {_AL.rgba(_AL.ENGRAVE_LIGHT, .16)}}}
  #s{{margin:9px 0 0;font-size:13px;line-height:1.7;color:{_AL.ON_TEAL_2};
    opacity:.85}}
  #stats{{display:flex;gap:14px}}
  .st{{background:rgba(255,255,255,.13);backdrop-filter:blur(9px);
    -webkit-backdrop-filter:blur(9px);border:1px solid rgba(255,255,255,.22);
    border-radius:14px;padding:12px 16px;min-width:104px;text-align:center;
    transition:transform .45s cubic-bezier(.2,.8,.2,1),background .45s}}
  .st .v{{font-size:24px;font-weight:700;color:{_AL.ON_TEAL};line-height:1.15}}
  .st .l{{font-size:11px;color:{_AL.ON_TEAL_2};margin-top:3px}}
  .st .d{{width:22px;height:3px;border-radius:2px;margin:7px auto 0}}
  @media (prefers-reduced-motion:reduce){{ .st{{transition:none}} }}
  @media (max-width:820px){{
    #stats{{display:none}} #car{{opacity:.34}} #t{{font-size:24px}}
    #ov{{padding-inline-end:34px}} #emb{{opacity:.5}}
  }}
</style>
<script>
const D = {payload};
document.getElementById('k').textContent = '{kicker}';
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
  // هر ذره **خانهٔ خودش** را دارد: نقطهٔ قالب. حرکت یعنی انحراف حول
  // همان خانه و برگشت به آن، نه سرگردانیِ تصادفی.
  pts = D.seeds.map(function(s){{
    const hx = s[0]*W, hy = s[1]*H;
    return {{hx:hx, hy:hy, x:hx, y:hy,
             vx:(Math.random()-.5)*.18, vy:(Math.random()-.5)*.18,
             r:Math.max(.9, s[2]), o:s[3]}};
  }});
}}
addEventListener('resize', size);

const wrap = document.getElementById('wrap');
wrap.addEventListener('pointermove', function(e){{
  const r = cv.getBoundingClientRect();
  mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top;
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
    // فنرِ برگشت به خانه — بدون این، الگوی قالب بعد از چند ثانیه گم می‌شود
    p.vx += (p.hx - p.x)*0.0016; p.vy += (p.hy - p.y)*0.0016;
    p.vx *= 0.985; p.vy *= 0.985;
    const dx = mouse.x-p.x, dy = mouse.y-p.y, d = Math.hypot(dx,dy);
    if (d < 150 && d > 0.01){{ p.x += dx/d*0.55; p.y += dy/d*0.55; }}
  }}
  for (let i=0;i<pts.length;i++){{
    for (let j=i+1;j<pts.length;j++){{
      const a=pts[i], b=pts[j], d=Math.hypot(a.x-b.x, a.y-b.y);
      if (d < 74){{
        const mx=(a.x+b.x)/2, my=(a.y+b.y)/2;
        const near = Math.max(0, 1 - Math.hypot(mouse.x-mx, mouse.y-my)/190);
        ctx.strokeStyle = 'rgba(209,240,229,'+((1-d/74)*(0.06+near*0.34)).toFixed(3)+')';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
      }}
    }}
  }}
  for (const p of pts){{
    const near = Math.max(0, 1 - Math.hypot(mouse.x-p.x, mouse.y-p.y)/190);
    ctx.globalAlpha = Math.min(1, p.o*(0.85+near*0.9));
    ctx.fillStyle = D.dust;
    ctx.beginPath(); ctx.arc(p.x, p.y, p.r*(1+near*0.7), 0, 6.2832); ctx.fill();
  }}
  ctx.globalAlpha = 1;
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
    if(!d || d.getElementById('hrperf-glow')) return;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var g = d.createElement('div');
    g.id = 'hrperf-glow';
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
