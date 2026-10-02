# -*- coding: utf-8 -*-
"""GSI Design System — نشانه‌های نموداری (SVG) داخل مرورگر.

این ماژول جاوااسکریپتِ رسم را به‌عنوان **یک رشته** می‌دهد. هیچ کتابخانه‌ای
بارگذاری نمی‌شود: گزارش از داخل Outlook و روی شبکه اداری باز می‌شود و هر
``<script src>`` بیرونی یعنی صفحه‌ای که ممکن است بی‌نمودار بالا بیاید.

## قاعده‌های رسم

**۱) هر نمودار محور دارد.** ابری از نقطه بدون مقیاس، تصمیمی را عوض نمی‌کند.
**۲) هر نمودار حالت خالی دارد** که می‌گوید چرا خالی است.
**۳) برچسب‌ها از قاعده `unicode-bidi:plaintext` پیروی می‌کنند** — بدون آن،
   در سند راست‌به‌چپ هر برچسب زیر میله پنهان می‌شود.
**۴) مرز روی هر سطح رنگی** — زرد و نارنجی روی سفید لبه ندارند (WCAG 1.4.11).

## چرا این یک فایل جداست

``html_export.py`` پیش از این دو پیاده‌سازی رقیب از همین توابع داشت و هر
دو emit می‌شدند؛ مرورگر با ``Identifier 'S' has already been declared`` کل
بلوک دوم را رها می‌کرد و گزارش خالی بالا می‌آمد. با یک منبع واحد، آن
شکست ساختاری ممکن نیست.
"""
from __future__ import annotations

__contract__ = 1

from . import tokens as T

#: بیشینه نقطه‌ای که در یک پراکنش رسم می‌شود. فراتر از این، هم مرورگر کند
#: می‌شود و هم چشم چیزی نمی‌بیند؛ تعداد کل در زیرنویس اعلام می‌شود.
SCATTER_CAP = 600

CHART_JS = r"""
/* ── ابزار مشترک ───────────────────────────────────────────────────────── */
const GSI_SERIES=__SERIES__, GSI_BAND_FILL=__BAND_FILL__, GSI_BAND_INK=__BAND_INK__;
const esc2=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;')
  .replaceAll('>','&gt;').replaceAll('"','&quot;');
function fmt(v){return (Math.round((Number(v)||0)*100)/100).toLocaleString('fa-IR')}
function fmtShort(v){const n=Number(v)||0,a=Math.abs(n);
 if(a>=1e9)return (n/1e9).toLocaleString('fa-IR',{maximumFractionDigits:1})+'G';
 if(a>=1e6)return (n/1e6).toLocaleString('fa-IR',{maximumFractionDigits:1})+'M';
 if(a>=1e4)return (n/1e3).toLocaleString('fa-IR',{maximumFractionDigits:0})+'K';
 return fmt(n)}
function ticks(min,max,count){if(!(max>min))return [min];
 const span=max-min,raw=span/count,p=Math.pow(10,Math.floor(Math.log10(raw)||0)),n=raw/p;
 const step=(n<=1?1:n<=2?2:n<=5?5:10)*p,start=Math.ceil(min/step)*step,out=[];
 for(let v=start;v<=max+step*0.001;v+=step)out.push(Math.round(v*1e6)/1e6);
 return out.length?out:[min,max]}
function median(a){if(!a.length)return 0;const s=a.slice().sort((x,y)=>x-y),m=s.length>>1;
 return s.length%2?s[m]:(s[m-1]+s[m])/2}

/* ── Tooltip سفارشی ────────────────────────────────────────────────────────
   <title> بومی SVG کار می‌کند و برای صفحه‌خوان نگه داشته می‌شود، اما جعبهٔ
   آن را مرورگر/سیستم‌عامل رسم می‌کند و دقیقاً شبیه هر نمودار پیش‌فرض
   اکسل/Chart.js است. این‌جا یک عنصر ثابت و به‌روزشونده جایگزینش می‌کند؛
   خودِ <title> برای صفحه‌خوان و چاپ (که جاوااسکریپت ندارد) باقی می‌ماند. */
let _tipEl=null;
function _tip(){if(_tipEl)return _tipEl;
 _tipEl=document.createElement('div');_tipEl.className='gsi-tip';
 document.body.appendChild(_tipEl);return _tipEl}
function tipShow(evt,html){const el=_tip();el.innerHTML=html;el.classList.add('show');
 tipMove(evt)}
function tipMove(evt){const el=_tip(),pad=14,vw=innerWidth,vh=innerHeight;
 el.style.left=Math.min(evt.clientX+pad,vw-el.offsetWidth-8)+'px';
 const top=evt.clientY-el.offsetHeight-pad;
 el.style.top=(top>4?top:evt.clientY+pad)+'px'}
function tipHide(){if(_tipEl)_tipEl.classList.remove('show')}
/* روی یک نشانهٔ SVG سه رویداد هاور را با یک HTML آماده وصل می‌کند؛
   <title> فرزند حذف نمی‌شود، فقط جعبهٔ بومی که کاربر با ماوس می‌بیند
   با این عنصر شخصی‌سازی‌شده جایگزین می‌شود (خودِ <title> غیرفعال نیست،
   صرفاً مرورگرها جعبهٔ آن را وقتی mousemove مدام رخ می‌دهد دیر نشان
   می‌دهند، بنابراین در عمل tipShow دیده می‌شود). */
function wireTip(html){return 'onmouseenter="tipShow(event,'+JSON.stringify(html).replace(/"/g,'&quot;')
 +')" onmousemove="tipMove(event)" onmouseleave="tipHide()"'}

function frame(title,inner,q,foot,i){
 return '<figure class="chartbox reveal" style="--i:'+(i||0)+'">'
  +'<figcaption><h4>'+esc2(title)+'</h4>'
  +(q?'<span class="ask">'+esc2(q)+'</span>':'')+'</figcaption>'+inner
  +(foot?'<div class="chartfoot">'+foot+'</div>':'')+'</figure>'}
function emptyBox(msg){return '<div class="emptybox"><span class="emptymark" aria-hidden="true">◇</span><p>'
  +esc2(msg)+'</p></div>'}

/* ── میله افقی: رتبه‌بندی دسته‌ها ──────────────────────────────────────── */
function barChart(rows,title,o){o=o||{};
 if(!rows||!rows.length)return frame(title,emptyBox('داده کافی برای این نمودار در برش فعلی نیست.'),o.q,'',o.i);
 let rs=rows.filter(x=>Number.isFinite(+x.v)).sort((a,b)=>b.v-a.v).slice(0,10);
 if(!rs.length)return frame(title,emptyBox('همه مقادیر این نمودار در برش فعلی تهی‌اند.'),o.q,'',o.i);
 const mx=Math.max(...rs.map(x=>+x.v),1),W=760,L=248,R=74,T0=14,B=26,BH=22,G=12;
 const H=T0+B+rs.length*(BH+G),plot=W-L-R;
 let g='';ticks(0,mx,4).forEach(tv=>{const x=L+tv/mx*plot;
  g+='<line x1="'+x+'" y1="'+T0+'" x2="'+x+'" y2="'+(H-B)+'" class="grid-line"></line>'
   +'<text x="'+x+'" y="'+(H-B+16)+'" text-anchor="middle" class="tick">'+fmtShort(tv)+'</text>'});
 let s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc2(title)+'" preserveAspectRatio="xMidYMid meet">'+g;
 s+='<line x1="'+L+'" y1="'+T0+'" x2="'+L+'" y2="'+(H-B)+'" class="axis-line"></line>';
 rs.forEach((x,i)=>{const y=T0+i*(BH+G),w=Math.max(3,+x.v/mx*plot);
  const fill=x.c||o.fill||'var(--teal)',ink=x.ink||o.ink||'var(--navy)';
  const tip='<b>'+esc2(x.k)+'</b><br><span class="gsi-tip-muted">'+fmt(x.v)+'</span>';
  s+='<text x="'+(L-10)+'" y="'+(y+BH*0.72)+'" class="chart-label">'+esc2(x.k)+'</text>'
   +'<rect x="'+L+'" y="'+y+'" width="'+w+'" height="'+BH+'" rx="4" class="bar-mark" '
   +'style="--i:'+i+';fill:'+fill+';stroke:'+ink+'" '+wireTip(tip)+'><title>'+esc2(x.k)+' — '+fmt(x.v)+'</title></rect>'
   +'<text x="'+(L+w+7)+'" y="'+(y+BH*0.72)+'" class="chart-value">'+fmtShort(x.v)+'</text>'});
 return frame(title,s+'</svg>',o.q,o.foot,o.i)}

/* ── دونات: ترکیب یک کل ───────────────────────────────────────────────── */
function donutChart(rows,title,o){o=o||{};
 const total=rows.reduce((s,x)=>s+(+x.v||0),0);
 if(!total)return frame(title,emptyBox('هیچ دسته‌ای در این برش مقدار ندارد.'),o.q,'',o.i);
 rows=rows.slice().sort((a,b)=>b.v-a.v);
 const cx=124,cy=124,R=88,r=52;let a=-Math.PI/2,path='';
 /* فاصلهٔ ۲ درجه‌ای بین قطعه‌ها: بدون آن دونات یک دایرهٔ توپر رنگی است که
    فقط با استروک سفید بریده شده — با این فاصله، هر قطعه واقعاً «شیء»
    مستقل به‌نظر می‌رسد، نه برش یک کیک تخت. سهم خیلی کوچک (<۲٫۵٪) فاصله
    نمی‌گیرد تا در آن قطعه‌ها ناپدید نشود. */
 const gapDeg=rows.length>1?2:0,gapRad=gapDeg*Math.PI/180;
 rows.forEach((x,i)=>{const v=+x.v||0,frac=v/total,full=a+frac*Math.PI*2;
  const tiny=frac<0.025,g=tiny?0:gapRad/2,a0=a+g,b=full-g,la=(b-a0)>Math.PI?1:0,
  p1=[cx+R*Math.cos(a0),cy+R*Math.sin(a0)],p2=[cx+R*Math.cos(b),cy+R*Math.sin(b)],
  q1=[cx+r*Math.cos(b),cy+r*Math.sin(b)],q2=[cx+r*Math.cos(a0),cy+r*Math.sin(a0)];
  const fill=x.c||GSI_SERIES[i%GSI_SERIES.length];
  const tip='<b>'+esc2(x.k)+'</b><br><span class="gsi-tip-muted">'+fmt(v)+' — '+(frac*100).toFixed(1)+'٪</span>';
  path+='<path d="M'+p1+' A'+R+' '+R+' 0 '+la+' 1 '+p2+' L'+q1+' A'+r+' '+r+' 0 '+la+' 0 '+q2
   +' Z" class="slice-mark" fill="'+fill+'" '+wireTip(tip)+'><title>'
   +esc2(x.k)+' — '+fmt(v)+' ('+(frac*100).toFixed(1)+'٪)</title></path>';a=full});
 const leg=rows.map((x,i)=>{const fill=x.c||GSI_SERIES[i%GSI_SERIES.length];
  return '<div class="legend-item" onmouseenter="this.closest(&quot;.chartbox&quot;).querySelectorAll(&quot;.slice-mark&quot;)['+i+'].dispatchEvent(new Event(&quot;mouseenter&quot;))" '
  +'onmouseleave="this.closest(&quot;.chartbox&quot;).querySelectorAll(&quot;.slice-mark&quot;)['+i+'].dispatchEvent(new Event(&quot;mouseleave&quot;))">'
  +'<i style="background:'+fill+'"></i><span class="lk">'+esc2(x.k)
  +'</span><b>'+fmt(x.v)+'</b><span class="note">'+((+x.v||0)/total*100).toFixed(0)+'٪</span></div>'}).join('');
 const svg='<div class="cluster cluster-lg" style="justify-content:center">'
  +'<svg viewBox="0 0 248 248" role="img" aria-label="'+esc2(title)+'" style="max-width:248px">'
  +'<g class="donut-group">'+path+'</g><text x="124" y="120" text-anchor="middle" style="font:800 25px var(--font);fill:var(--navy)">'
  +fmtShort(total)+'</text><text x="124" y="142" text-anchor="middle" class="tick">ردیف</text></svg>'
  +'<div class="stack stack-3xs grow">'+leg+'</div></div>';
 return frame(title,svg,o.q,o.foot,o.i)}

/* ── پراکنش: رابطه دو متغیر، با چهار ربع و خط رگرسیون ─────────────────── */
function scatterChart(pts,title,o){o=o||{};
 if(!pts||pts.length<3)return frame(title,emptyBox('برای سنجش رابطه دست‌کم سه پرونده با هر دو مقدار لازم است.'),o.q,'',o.i);
 const W=760,H=340,L=64,T0=18,R=22,B=52,pw=W-L-R,ph=H-T0-B;
 const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);
 const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
 const xr=(x1-x0)||1,yr=(y1-y0)||1;
 const px=v=>L+(v-x0)/xr*pw,py=v=>T0+ph-(v-y0)/yr*ph;
 const mx=median(xs),my=median(ys);
 let s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc2(title)+'" preserveAspectRatio="xMidYMid meet">';
 s+='<rect x="'+px(mx)+'" y="'+py(my)+'" width="'+(L+pw-px(mx))+'" height="'+(T0+ph-py(my))
  +'" fill="var(--st-critical)" opacity=".07"></rect>';
 ticks(y0,y1,4).forEach(tv=>{const y=py(tv);s+='<line x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y
  +'" class="grid-line"></line><text x="'+(L-8)+'" y="'+(y+4)+'" text-anchor="end" class="tick">'+fmtShort(tv)+'</text>'});
 ticks(x0,x1,5).forEach(tv=>{const x=px(tv);s+='<line x1="'+x+'" y1="'+T0+'" x2="'+x+'" y2="'+(T0+ph)
  +'" class="grid-line"></line><text x="'+x+'" y="'+(T0+ph+18)+'" text-anchor="middle" class="tick">'+fmtShort(tv)+'</text>'});
 s+='<line x1="'+px(mx)+'" y1="'+T0+'" x2="'+px(mx)+'" y2="'+(T0+ph)+'" class="median-line"></line>'
  +'<line x1="'+L+'" y1="'+py(my)+'" x2="'+(W-R)+'" y2="'+py(my)+'" class="median-line"></line>'
  +'<line x1="'+L+'" y1="'+(T0+ph)+'" x2="'+(W-R)+'" y2="'+(T0+ph)+'" class="axis-line"></line>'
  +'<line x1="'+L+'" y1="'+T0+'" x2="'+L+'" y2="'+(T0+ph)+'" class="axis-line"></line>';
 const n=pts.length,mxa=xs.reduce((a,b)=>a+b,0)/n,mya=ys.reduce((a,b)=>a+b,0)/n;
 let sxy=0,sxx=0,syy=0;
 for(const p of pts){sxy+=(p.x-mxa)*(p.y-mya);sxx+=(p.x-mxa)**2;syy+=(p.y-mya)**2}
 const shown=pts.slice(0,__CAP__);
 shown.forEach((p,i)=>{const c=GSI_BAND_FILL[p.b]||'var(--teal)';
  const tip='<b>'+esc2(p.k||'—')+'</b><br>'+esc2(o.xlabel||'')+': '+fmt(p.x)
   +'<br>'+esc2(o.ylabel||'')+': '+fmt(p.y);
  s+='<circle cx="'+px(p.x).toFixed(1)+'" cy="'+py(p.y).toFixed(1)+'" r="4.5" class="dot-mark" style="--i:'
   +(i%60)+';fill:'+c+'" '+wireTip(tip)+'><title>'+esc2(p.k||'—')+'\n'+esc2(o.xlabel||'')+': '+fmt(p.x)
   +'\n'+esc2(o.ylabel||'')+': '+fmt(p.y)+'</title></circle>'});
 let stat='';
 if(sxx>0&&syy>0){const slope=sxy/sxx,inter=mya-slope*mxa,r=sxy/Math.sqrt(sxx*syy);
  const cl=v=>Math.min(Math.max(v,y0),y1);
  s+='<line x1="'+px(x0)+'" y1="'+py(cl(slope*x0+inter))+'" x2="'+px(x1)+'" y2="'+py(cl(slope*x1+inter))
   +'" class="line-mark" style="--dash:900"></line>';
  stat='<span class="note">همبستگی r = '+r.toFixed(2)+'</span><span class="note">'
   +(Math.abs(r)<0.2?'رابطه‌ای دیده نمی‌شود':Math.abs(r)<0.5?'رابطه ضعیف':Math.abs(r)<0.75?'رابطه متوسط':'رابطه قوی')+'</span>'}
 s+='<text x="'+(L+pw/2)+'" y="'+(H-10)+'" text-anchor="middle" class="axis-title">'+esc2(o.xlabel||'')+'</text>'
  +'<text transform="translate(16,'+(T0+ph/2)+') rotate(-90)" text-anchor="middle" class="axis-title">'+esc2(o.ylabel||'')+'</text>';
 const more=pts.length>shown.length?'<span class="note">نمایش '+fmt(shown.length)+' از '+fmt(pts.length)+' نقطه</span>':'';
 const foot='<span class="note">ربع تیره = '+esc2(o.quad||'ناحیه پرخطر')+'</span>'+stat+more;
 return frame(title,s+'</svg>',o.q,foot,o.i)}

/* ── پارتو: تمرکز ۸۰/۲۰ ───────────────────────────────────────────────── */
function paretoChart(rows,title,o){o=o||{};
 let rs=(rows||[]).filter(x=>Number.isFinite(+x.v)&&+x.v>0).sort((a,b)=>b.v-a.v);
 if(rs.length<2)return frame(title,emptyBox('برای تحلیل تمرکز دست‌کم دو دسته با مقدار مثبت لازم است.'),o.q,'',o.i);
 const total=rs.reduce((s,x)=>s+ +x.v,0);rs=rs.slice(0,12);
 const W=760,H=310,L=58,T0=20,R=52,B=74,pw=W-L-R,ph=H-T0-B,bw=pw/rs.length,mx=Math.max(...rs.map(x=>+x.v));
 let s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc2(title)+'" preserveAspectRatio="xMidYMid meet">';
 ticks(0,mx,4).forEach(tv=>{const y=T0+ph-tv/mx*ph;s+='<line x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y
  +'" class="grid-line"></line><text x="'+(L-8)+'" y="'+(y+4)+'" text-anchor="end" class="tick">'+fmtShort(tv)+'</text>'});
 const y80=T0+ph-0.8*ph;
 s+='<line x1="'+L+'" y1="'+y80+'" x2="'+(W-R)+'" y2="'+y80+'" stroke="var(--st-serious-ink)" stroke-width="1.2" stroke-dasharray="6 4"></line>'
  +'<text x="'+(W-R+4)+'" y="'+(y80-5)+'" class="tick">۸۰٪</text>';
 let cum=0,pathD='',reach=0;
 rs.forEach((x,i)=>{const h=(+x.v)/mx*ph,X=L+i*bw+bw*0.16,Y=T0+ph-h;
  const tip='<b>'+esc2(x.k)+'</b><br><span class="gsi-tip-muted">'+fmt(x.v)+' — '+((+x.v/total)*100).toFixed(1)+'٪ از کل</span>';
  s+='<rect x="'+X+'" y="'+Y+'" width="'+(bw*0.68)+'" height="'+Math.max(h,1)+'" rx="3" class="col-mark" style="--i:'
   +i+'" '+wireTip(tip)+'><title>'+esc2(x.k)+' — '+fmt(x.v)+'</title></rect>';
  cum+=+x.v;const cy=T0+ph-(cum/total)*ph,cx2=X+bw*0.34;
  pathD+=(i?' L':'M')+cx2+' '+cy;
  if(!reach&&cum/total>=0.8)reach=i+1;
  s+='<text x="'+cx2+'" y="'+(T0+ph+16)+'" text-anchor="middle" class="tick" transform="rotate(-28 '
   +cx2+' '+(T0+ph+16)+')">'+esc2(String(x.k).slice(0,16))+'</text>'});
 s+='<path d="'+pathD+'" class="line-mark" style="--dash:1400"></path>'
  +'<line x1="'+L+'" y1="'+(T0+ph)+'" x2="'+(W-R)+'" y2="'+(T0+ph)+'" class="axis-line"></line>';
 const msg=reach?('۸۰٪ از کل روی '+fmt(reach)+' دسته نخست متمرکز است — همان‌جا بیشترین بازده اقدام است.')
  :'تمرکز کمتر از قاعده ۸۰/۲۰ است؛ اثر روی دسته‌های زیادی پخش شده.';
 return frame(title,s+'</svg>',o.q,'<span class="note">'+esc2(msg)+'</span>',o.i)}

/* ── روند: تنها شکلی که به «بهتر یا بدتر؟» جواب می‌دهد ────────────────── */
function trendChart(dates,vals,title,o){o=o||{};
 const ok=(vals||[]).filter(v=>v!==null&&v!==undefined);
 if(ok.length<2)return frame(title,emptyBox('برای نمودار روند دست‌کم دو اجرای ثبت‌شده لازم است. با اجرای روزانه، تاریخچه ساخته می‌شود.'),o.q,'',o.i);
 const lo=Math.min(...ok),hi=Math.max(...ok),span=(hi-lo)||Math.abs(hi)||1;
 const W=760,H=250,L=62,T0=22,R=20,B=44,pw=W-L-R,ph=H-T0-B,n=vals.length;
 const px=i=>L+(n<2?pw/2:i/(n-1)*pw),py=v=>T0+ph-(v-lo+span*0.08)/(span*1.16)*ph;
 /* منحنی نرم (Bezier) به‌جای پاره‌خط شکسته: خط شکسته دقیقاً همان چیزی است
    که یک نمودار خطی پیش‌فرض اکسل رسم می‌کند. نقطهٔ کنترل هر پاره میانهٔ
    X دو نقطهٔ همسایه است — بدون overshoot، فقط انحنای بصری. */
 let line='',area='',first=true,prev=null,prevX=null,prevY=null;
 vals.forEach((v,i)=>{if(v===null||v===undefined)return;const X=px(i),Y=py(v);
  if(first){line='M'+X+' '+Y;area='M'+X+' '+(T0+ph)+' L'+X+' '+Y;first=false}
  else{const mx2=(prevX+X)/2;
   line+=' C'+mx2+' '+prevY+','+mx2+' '+Y+','+X+' '+Y;
   area+=' C'+mx2+' '+prevY+','+mx2+' '+Y+','+X+' '+Y}
  prev=X;prevX=X;prevY=Y});
 if(prev!==null)area+=' L'+prev+' '+(T0+ph)+' Z';
 let g='';ticks(lo,hi,3).forEach(tv=>{const Y=py(tv);
  g+='<line x1="'+L+'" y1="'+Y+'" x2="'+(W-R)+'" y2="'+Y+'" class="grid-line"></line>'
   +'<text x="'+(L-8)+'" y="'+(Y+4)+'" text-anchor="end" class="tick">'+fmtShort(tv)+'</text>'});
 let lab='';const step=Math.max(1,Math.ceil(n/6));
 (dates||[]).forEach((d,i)=>{if(i%step&&i!==n-1)return;
  lab+='<text x="'+px(i)+'" y="'+(T0+ph+18)+'" text-anchor="middle" class="tick">'+esc2(String(d).slice(5))+'</text>'});
 const lastI=vals.map((v,i)=>(v===null||v===undefined)?-1:i).filter(i=>i>=0).pop();
 const lastTip=lastI>=0?'<b>'+esc2(String((dates||[])[lastI]??''))+'</b><br><span class="gsi-tip-muted">'+fmt(vals[lastI])+'</span>':'';
 const dot=lastI>=0?'<circle cx="'+px(lastI)+'" cy="'+py(vals[lastI])+'" r="5" class="dot-mark" fill="var(--navy)" stroke="#fff" stroke-width="2" '+wireTip(lastTip)+'></circle>':'';
 const svg='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc2(title)+'" preserveAspectRatio="xMidYMid meet">'
  +g+lab+'<path d="'+area+'" class="area-mark"></path><path d="'+line+'" class="line-mark" style="--dash:1800"></path>'
  +dot+'<line x1="'+L+'" y1="'+(T0+ph)+'" x2="'+(W-R)+'" y2="'+(T0+ph)+'" class="axis-line"></line></svg>';
 return frame(title,svg,o.q,o.foot||('<span class="note">'+fmt(n)+' اجرای ثبت‌شده</span>'),o.i)}

/* ── مقایسه دو معیار روی یک محور دسته‌ای ──────────────────────────────── */
function groupedChart(rows,title,o){o=o||{};
 rows=(rows||[]).filter(x=>Number.isFinite(+x.a)||Number.isFinite(+x.b)).slice(0,10);
 if(!rows.length)return frame(title,emptyBox('دو معیار لازم برای مقایسه در این برش وجود ندارد.'),o.q,'',o.i);
 const mx=Math.max(...rows.flatMap(x=>[+x.a||0,+x.b||0]),1),W=760,L=248,R=70,T0=14,B=26,RH=30,G=12;
 const H=T0+B+rows.length*(RH+G),plot=W-L-R;
 let g='';ticks(0,mx,4).forEach(tv=>{const x=L+tv/mx*plot;
  g+='<line x1="'+x+'" y1="'+T0+'" x2="'+x+'" y2="'+(H-B)+'" class="grid-line"></line>'
   +'<text x="'+x+'" y="'+(H-B+16)+'" text-anchor="middle" class="tick">'+fmtShort(tv)+'</text>'});
 let s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc2(title)+'" preserveAspectRatio="xMidYMid meet">'+g;
 rows.forEach((x,i)=>{const y=T0+i*(RH+G),wa=(+x.a||0)/mx*plot,wb=(+x.b||0)/mx*plot;
  const tipA='<b>'+esc2(x.k)+'</b><br>'+esc2(o.a||'الف')+': '+fmt(x.a);
  const tipB='<b>'+esc2(x.k)+'</b><br>'+esc2(o.b||'ب')+': '+fmt(x.b);
  s+='<text x="'+(L-10)+'" y="'+(y+20)+'" class="chart-label">'+esc2(x.k)+'</text>'
   +'<rect x="'+L+'" y="'+y+'" width="'+Math.max(wa,1)+'" height="12" rx="3" class="bar-mark" style="--i:'+i+';fill:var(--series-8);stroke:var(--navy)" '+wireTip(tipA)+'><title>'+esc2(o.a||'الف')+' — '+fmt(x.a)+'</title></rect>'
   +'<rect x="'+L+'" y="'+(y+16)+'" width="'+Math.max(wb,1)+'" height="12" rx="3" class="bar-mark" style="--i:'+i+';fill:var(--teal);stroke:var(--navy)" '+wireTip(tipB)+'><title>'+esc2(o.b||'ب')+' — '+fmt(x.b)+'</title></rect>'});
 const foot='<span class="legend-item"><i style="background:var(--series-8)"></i>'+esc2(o.a||'الف')+'</span>'
  +'<span class="legend-item"><i style="background:var(--teal)"></i>'+esc2(o.b||'ب')+'</span>';
 return frame(title,s+'</svg>',o.q,foot,o.i)}
"""


def chart_runtime(series_json: str, band_fill_json: str, band_ink_json: str) -> str:
    """جاوااسکریپت رسم، با پالت تزریق‌شده از توکن‌ها."""
    return (CHART_JS
            .replace("__SERIES__", series_json)
            .replace("__BAND_FILL__", band_fill_json)
            .replace("__BAND_INK__", band_ink_json)
            .replace("__CAP__", str(SCATTER_CAP)))
