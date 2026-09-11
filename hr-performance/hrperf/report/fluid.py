# -*- coding: utf-8 -*-
"""نقشهٔ سیال کلاسترها — یک فایل HTML مستقل، متحرک و قابل دستکاری.

## چرا «سیال»

جدول وزن‌ها می‌گوید مدل **چه هست**. نقشهٔ سیال می‌گوید مدل **چطور کار
می‌کند**: هر شاخص یک ذره است که به مرکز کلاستر خودش کشیده می‌شود و از
شاخص‌های ناهم‌خانواده دور می‌شود. وقتی شاخصی را جابه‌جا می‌کنید،
ذره‌ها دوباره جا می‌افتند و **می‌بینید** چه چیزی به هم خورد.

نیرو‌ها همان چیزی است که در `model_engine/vectors.py` محاسبه شده:
کشش بین دو ذره = همبستگی بردارهایشان. یعنی حرکت روی صفحه، تزئین نیست؛
همان عددی است که جدول نشان می‌دهد.

## قواعد بصری که رعایت شده

* رنگ، شناسهٔ **کلاستر** است و ترتیبش ثابت — هرگز چرخانده نمی‌شود.
  با فیلتر کردن، رنگِ بازمانده‌ها عوض نمی‌شود.
* هویت هرگز فقط با رنگ نیست: هر خوشه **برچسب مستقیم** روی صفحه دارد،
  ذره‌ها فضایی گروه می‌شوند، و راهنما همیشه هست. برای خواننده‌ای که
  رنگ‌ها را جدا نمی‌بیند، جای ذره و برچسب کافی است.
* پالت پیش‌فرض، همان پالت اعتبارسنجی‌شده است (هر شش بررسی، در هر دو
  حالت روشن و تاریک). رنگِ دلخواهِ کاربر روی همان جای ترتیبی می‌نشیند.
* `prefers-reduced-motion` حرکت را کاملاً خاموش می‌کند و چیدمان نهایی
  را یک‌باره نشان می‌دهد — حرکت، اطلاعات اضافه نمی‌دهد، فقط دنبال‌کردن
  تغییر را آسان می‌کند.
* نمای جدولی همیشه در دسترس است.
"""
from __future__ import annotations

__contract__ = 1

import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..config.model import PerformanceModel
from . import aqua
from . import alborz as _AL
from ..model_engine import vectors as ve

#: پالت آکوا — همان تعریفی که اکسل و HTML و داشبورد از آن می‌خوانند.
#: ترتیب ثابت، هرگز چرخانده نمی‌شود.
#: یک هویت، دو سطح: همان هفت رنگ روی سطح تیره هم سنجیده شد و رد شد.
CATEGORICAL_LIGHT = list(_AL.SERIES)
CATEGORICAL_DARK = list(_AL.SERIES)
OTHER_LIGHT, OTHER_DARK = aqua.OTHER_LIGHT, aqua.OTHER_DARK


def _cluster_colors(model: PerformanceModel) -> Dict[str, Dict[str, str]]:
    """رنگ هر کلاستر در دو حالت. رنگ دستیِ کاربر بر پالت مقدم است."""
    out: Dict[str, Dict[str, str]] = {}
    for i, (k, c) in enumerate(model.clusters.items()):
        # بدون چرخش — از اسلات هفتم که گذشت، «سایر».
        light = c.color or _AL.series_color(i)
        dark = c.color or _AL.series_color(i)
        out[k] = {"light": light, "dark": dark, "label": c.label,
                  "weight": round(c.weight, 4), "scored": c.scored}
    return out


def build_payload(scores: pd.DataFrame, model: PerformanceModel,
                  people: Optional[pd.DataFrame] = None) -> Dict:
    """همه چیزی که صفحه لازم دارد — یک دیکشنری، بدون فراخوان بیرونی."""
    member = {k: m.cluster for k, m in model.metrics.items() if m.scored}
    cols = [c for c in scores.columns if c in member]
    vec = ve.vectors(scores[cols], model)
    sim = ve.similarity(vec) if not vec.empty else pd.DataFrame()
    lay = ve.layout(sim, member) if not sim.empty else pd.DataFrame()

    nodes = []
    for mk in (list(sim.columns) if not sim.empty else cols):
        m = model.metrics[mk]
        row = lay.loc[mk] if mk in lay.index else None
        s = scores[mk] if mk in scores.columns else pd.Series(dtype=float)
        nodes.append({
            "key": mk, "label": m.label, "cluster": m.cluster,
            "scope": m.scope, "weight": round(model.effective_weight(mk), 5),
            "x": float(row["x"]) if row is not None else 0.0,
            "y": float(row["y"]) if row is not None else 0.0,
            "mean": None if s.empty else round(float(s.mean(skipna=True)), 1),
            "spread": None if s.empty else round(float(s.std(ddof=0) or 0), 1),
            "citation": m.citation, "field": m.aibl_field,
        })

    links = []
    if not sim.empty:
        ks = list(sim.columns)
        for i, a in enumerate(ks):
            for b in ks[i + 1:]:
                r = sim.loc[a, b]
                if np.isfinite(r) and abs(r) >= 0.25:
                    links.append({"a": a, "b": b, "r": round(float(r), 3)})

    fits = [{"metric": f.metric, "cluster": f.cluster,
             "own": None if not np.isfinite(f.own) else round(f.own, 3),
             "other": f.best_other,
             "otherSim": None if not np.isfinite(f.best_other_sim)
             else round(f.best_other_sim, 3),
             "verdict": f.verdict}
            for f in (ve.fit_table(vec, member) if not vec.empty else [])]

    coh = [{"cluster": c.cluster, "n": c.n,
            "within": None if not np.isfinite(c.mean_within) else round(c.mean_within, 3),
            "between": None if not np.isfinite(c.mean_between) else round(c.mean_between, 3),
            "verdict": c.verdict}
           for c in (ve.cohesion(sim, member) if not sim.empty else [])]

    sugg = [{"kind": s.kind, "title": s.title, "metric": s.metric,
             "detail": s.detail, "reason": s.reason, "to": s.to_cluster,
             "strength": round(s.strength, 3)}
            for s in ve.suggest(scores, model)]

    return {"clusters": _cluster_colors(model), "nodes": nodes, "links": links,
            "fits": fits, "cohesion": coh, "suggestions": sugg,
            "version": model.model_version,
            "people": 0 if people is None else int(len(people))}


def write(payload: Dict, path: str | Path, title: str = "نقشهٔ سیال مدل عملکرد") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(payload, title), encoding="utf-8")
    return p


def render(payload: Dict, title: str = "نقشهٔ سیال مدل عملکرد") -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return (_TEMPLATE.replace("__DATA__", data).replace("__TITLE__", title)
            .replace("__AQUA_LIGHT__", aqua.css_vars(False))
            .replace("__AQUA_DARK__", aqua.css_vars(True)))


_TEMPLATE = r"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  color-scheme: light;
__AQUA_LIGHT__
}
:root[data-theme="dark"], :root.dark{
  color-scheme: dark;
__AQUA_DARK__
}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--text);
  font:14px/1.7 var(--font,"Vazirmatn","IRANSans",Tahoma,system-ui,sans-serif)}
header{padding:18px 22px 10px;border-bottom:1px solid var(--border)}
h1{margin:0 0 4px;font-size:19px;font-weight:700}
.sub{color:var(--text-2);font-size:12.5px}
.wrap{display:grid;grid-template-columns:1fr 340px;gap:0;min-height:calc(100vh - 74px)}
@media(max-width:900px){.wrap{grid-template-columns:1fr}}
#stage{position:relative;overflow:hidden}
canvas{display:block;width:100%;height:100%}
aside{border-inline-start:1px solid var(--border);background:var(--raised);
  padding:14px 16px;overflow:auto;max-height:calc(100vh - 74px)}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  padding:10px 22px;border-bottom:1px solid var(--border);background:var(--raised)}
button,select{font:inherit;color:var(--text);background:var(--surface);
  border:1px solid var(--border);border-radius:8px;padding:5px 11px;cursor:pointer}
button:hover{border-color:var(--text-3)}
button[aria-pressed="true"]{background:var(--text);color:var(--surface);border-color:var(--text)}
h2{font-size:13px;margin:16px 0 8px;color:var(--text-2);font-weight:700;
  letter-spacing:.02em;text-transform:none}
.legend{display:flex;flex-direction:column;gap:6px}
.lg{display:flex;align-items:center;gap:8px;font-size:12.5px;cursor:pointer;
  padding:4px 6px;border-radius:7px}
.lg:hover{background:var(--surface)}
.lg.off{opacity:.35}
.sw{width:13px;height:13px;border-radius:4px;flex:0 0 auto;
  box-shadow:0 0 0 2px var(--raised)}
.lg input[type=color]{width:22px;height:20px;padding:0;border:none;background:none;cursor:pointer}
.lg .w{margin-inline-start:auto;color:var(--text-3);font-size:11.5px;
  font-variant-numeric:tabular-nums}
.card{border:1px solid var(--border);border-radius:10px;padding:9px 11px;
  margin-bottom:8px;background:var(--surface)}
.card .k{font-size:11px;color:var(--text-3)}
.card .t{font-weight:700;font-size:12.5px;margin:2px 0 4px}
.card .r{font-size:12px;color:var(--text-2);line-height:1.65}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{text-align:right;padding:5px 6px;border-bottom:1px solid var(--border)}
th{color:var(--text-3);font-weight:600}
td.num{font-variant-numeric:tabular-nums}
.tip{position:absolute;pointer-events:none;background:var(--raised);
  border:1px solid var(--border);border-radius:9px;padding:8px 10px;font-size:12px;
  box-shadow:0 6px 20px rgba(0,0,0,.14);max-width:270px;opacity:0;transition:opacity .12s}
.tip b{display:block;margin-bottom:3px}
.tip .m{color:var(--text-2)}
.hidden{display:none !important}
.note{font-size:11.5px;color:var(--text-3);margin-top:10px;line-height:1.65}
@media (prefers-reduced-motion: reduce){ canvas{transition:none} }
</style></head><body>
<header>
  <h1>__TITLE__</h1>
  <div class="sub" id="sub"></div>
</header>
<div class="bar">
  <button id="btnPlay" aria-pressed="true">⏸ توقف حرکت</button>
  <button id="btnTable" aria-pressed="false">نمای جدولی</button>
  <button id="btnTheme">🌗 تم</button>
  <label style="font-size:12.5px;color:var(--text-2)">
    کشش هم‌بستگی
    <input id="pull" type="range" min="0" max="100" value="55" style="vertical-align:middle">
  </label>
  <span class="sub" id="hint">ذره‌ها را بکشید؛ رها کنید تا دوباره جا بیفتند.</span>
</div>
<div class="wrap">
  <div id="stage"><canvas id="cv"></canvas><div class="tip" id="tip"></div></div>
  <aside>
    <h2>کلاسترها — رنگ را عوض کنید</h2>
    <div class="legend" id="legend"></div>
    <h2>پیشنهاد موتور کلاستر</h2>
    <div id="sugg"></div>
    <h2>انسجام</h2>
    <div id="coh"></div>
    <div class="note" id="note"></div>
  </aside>
</div>
<div id="tableView" class="hidden" style="padding:14px 22px">
  <h2>نمای جدولی — همان داده، بدون رنگ</h2>
  <table id="tbl"></table>
</div>
<script>
const D = __DATA__;
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
const stage = document.getElementById("stage"), tip = document.getElementById("tip");
let W=0, H=0, dpr=Math.min(devicePixelRatio||1, 2);
let running = !REDUCED, pull = .55, dragging = null, hover = null;
const off = new Set();               // کلاسترهای خاموش‌شده

function isDark(){
  const t = document.documentElement.getAttribute("data-theme");
  if (t) return t === "dark";
  return matchMedia("(prefers-color-scheme: dark)").matches;
}
function colorOf(ck){
  const c = D.clusters[ck]; if(!c) return isDark()?"#8a8a85":"#6e6e66";
  return c.custom || (isDark() ? c.dark : c.light);
}
// ذره‌ها: مختصات اولیه از MDS همان ماتریس همبستگی می‌آید.
// ذره‌ها. جای هر ذره = مرکز کلاسترش + جای نسبی‌اش درون کلاستر (از MDS).
// چیدمان لنگردار است، نه شبیه‌سازی آزاد: نقشه‌ای که گاهی از هم می‌پاشد،
// هر بار چیز دیگری می‌گوید و دیگر قابل استناد نیست.
const N = D.nodes.map(n => ({...n, px:0, py:0, tx:0, ty:0, vx:0, vy:0,
                             ph: Math.random()*Math.PI*2}));
const byKey = Object.fromEntries(N.map(n=>[n.key,n]));
const CK = Object.keys(D.clusters);
const anchors = {};
function placeAnchors(){
  const live = CK.filter(k => !off.has(k) && N.some(n=>n.cluster===k));
  live.forEach((k,i)=>{
    const a = (i / Math.max(live.length,1)) * Math.PI*2 - Math.PI/2;
    const rad = live.length <= 2 ? .40 : .74;
    anchors[k] = {x: Math.cos(a)*rad, y: Math.sin(a)*rad};
  });
  // جای نسبی درون هر کلاster: ترتیب از MDS، فاصله از وزن
  for(const k of live){
    const mem = N.filter(n=>n.cluster===k);
    const cx = mem.reduce((s,n)=>s+n.x,0)/mem.length;
    const cy = mem.reduce((s,n)=>s+n.y,0)/mem.length;
    mem.sort((a,b)=>Math.atan2(a.y-cy,a.x-cx)-Math.atan2(b.y-cy,b.x-cx));
    const R = mem.length===1 ? 0 : 0.085 + 0.017*mem.length;
    mem.forEach((n,i)=>{
      const a = mem.length===1 ? 0 : (i/mem.length)*Math.PI*2;
      const sx = Math.max(SX(),1), sy = Math.max(SY(),1);
      n.tx = anchors[k].x + Math.cos(a)*R*(S()/sx);
      n.ty = anchors[k].y + Math.sin(a)*R*(S()/sy);
      if(!n.seeded){ n.px = n.tx; n.py = n.ty; n.seeded = true; }
    });
  }
}
function resize(){
  W = stage.clientWidth; H = stage.clientHeight || 520;
  cv.width = W*dpr; cv.height = H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
}
addEventListener("resize", ()=>{resize(); placeAnchors();});
// دو مقیاس جدا برای x و y: نقشه تمام عرض صفحه را می‌گیرد، به‌جای اینکه
// در یک مربع وسطِ یک مستطیل پهن بنشیند و نیمی از فضا هدر برود.
const SX = () => Math.max(W/2 - 96, 120);
const SY = () => Math.max(H/2 - 74, 100);
const S  = () => Math.min(SX(), SY());
const toPx = n => ({x: W/2 + n.px*SX(), y: H/2 + n.py*SY()});
const rOf  = n => 6 + Math.sqrt(Math.max(n.weight,0))*40;

let t = 0;
function step(){
  t += 0.016;
  for(const n of N){
    if(off.has(n.cluster) || n===dragging) continue;
    // شناور بودن: نوسان کوچک و آرام دور جای خودش — «فضای سیال»،
    // نه شبیه‌سازیِ ناپایدار.
    const dx = (n.tx + Math.cos(t*0.55 + n.ph)*0.013*pull) - n.px;
    const dy = (n.ty + Math.sin(t*0.47 + n.ph)*0.019*pull) - n.py;
    n.vx = n.vx*0.86 + dx*0.055;
    n.vy = n.vy*0.86 + dy*0.055;
    n.px += n.vx; n.py += n.vy;
  }
}
function draw(){
  ctx.clearRect(0,0,W,H);
  const dark = isDark();
  // پیوندها: فقط همبستگی‌های قوی، بسیار کم‌رنگ تا ذره‌ها خوانده شوند
  for(const l of D.links){
    const a=byKey[l.a], b=byKey[l.b];
    if(!a||!b||off.has(a.cluster)||off.has(b.cluster)) continue;
    if(Math.abs(l.r)<0.45) continue;
    const pa=toPx(a), pb=toPx(b);
    ctx.strokeStyle = (l.r>0? (dark?"rgba(200,200,190,":"rgba(90,90,84,")
                            : (dark?"rgba(230,103,103,":"rgba(201,60,55,"))
                     + (0.04+Math.abs(l.r)*0.16) + ")";
    ctx.lineWidth = 1 + Math.abs(l.r)*1.2;
    ctx.beginPath(); ctx.moveTo(pa.x,pa.y); ctx.lineTo(pb.x,pb.y); ctx.stroke();
  }
  for(const n of N){
    if(off.has(n.cluster)) continue;
    const p = toPx(n), r = rOf(n);
    ctx.beginPath(); ctx.arc(p.x,p.y,r+2,0,7);       // حلقهٔ سطح: فاصلهٔ ۲ پیکسلی
    ctx.fillStyle = dark? "#1a1a19":"#fcfcfb"; ctx.fill();
    ctx.beginPath(); ctx.arc(p.x,p.y,r,0,7);
    ctx.fillStyle = colorOf(n.cluster);
    ctx.globalAlpha = (hover && hover!==n)? .55 : 1; ctx.fill(); ctx.globalAlpha=1;
    if(hover===n){ ctx.lineWidth=2; ctx.strokeStyle=dark?"#fff":"#0b0b0b"; ctx.stroke(); }
  }
  // برچسب مستقیم هر خوشه — هویت هرگز فقط با رنگ نیست
  for(const ck of CK){
    if(off.has(ck)) continue;
    const mem = N.filter(n=>n.cluster===ck); if(!mem.length) continue;
    const pts = mem.map(toPx);
    const cx = pts.reduce((s,p)=>s+p.x,0)/pts.length;
    const cy = Math.min(...pts.map((p,i)=>p.y - rOf(mem[i])));
    ctx.font = "700 12.5px Vazirmatn, Tahoma, sans-serif";
    ctx.textAlign="center"; ctx.textBaseline="middle";
    const tx = D.clusters[ck].label, w = ctx.measureText(tx).width;
    ctx.fillStyle = dark? "rgba(35,35,34,.86)":"rgba(255,255,255,.88)";
    ctx.beginPath(); ctx.roundRect(cx-w/2-7, cy-26, w+14, 20, 7); ctx.fill();
    ctx.fillStyle = colorOf(ck); ctx.fillText(tx, cx, cy-16);
  }
}
function frame(){ if(running) step(); draw(); requestAnimationFrame(frame); }

function pick(mx,my){
  let best=null, bd=1e9;
  for(const n of N){
    if(off.has(n.cluster)) continue;
    const p=toPx(n), d=Math.hypot(p.x-mx,p.y-my);
    if(d < rOf(n)+6 && d<bd){bd=d; best=n;}
  }
  return best;
}
cv.addEventListener("pointermove", e=>{
  const b=cv.getBoundingClientRect(), mx=e.clientX-b.left, my=e.clientY-b.top;
  if(dragging){ dragging.px=(mx-W/2)/SX(); dragging.py=(my-H/2)/SY(); return; }
  const n = pick(mx,my); hover = n;
  if(n){
    tip.innerHTML = `<b>${n.label}</b>
      <span class="m">کلاستر: ${D.clusters[n.cluster]?.label||"—"} ·
      وزن مؤثر ${(n.weight*100).toFixed(1)}٪</span>
      ${n.mean!=null? `<span class="m">میانگین ${n.mean} · پراکندگی ${n.spread}</span>`:""}
      ${n.field? `<span class="m">سرچشمه: ${n.field}</span>`:""}
      ${n.citation? `<span class="m">مبنا: ${n.citation}</span>`:""}`;
    tip.style.opacity=1;
    tip.style.left = Math.min(mx+14, W-280)+"px"; tip.style.top = (my+14)+"px";
    cv.style.cursor="grab";
  } else { tip.style.opacity=0; cv.style.cursor="default"; }
});
cv.addEventListener("pointerdown", e=>{
  const b=cv.getBoundingClientRect();
  dragging = pick(e.clientX-b.left, e.clientY-b.top);
  if(dragging){ dragging.vx=dragging.vy=0; cv.setPointerCapture(e.pointerId); }
});
addEventListener("pointerup", ()=>{ dragging=null; });
cv.addEventListener("pointerleave", ()=>{ tip.style.opacity=0; hover=null; });

// ── راهنما: خاموش/روشن + رنگ دلخواه ──
const legend = document.getElementById("legend");
for(const ck of CK){
  const c = D.clusters[ck];
  const row = document.createElement("div"); row.className="lg";
  row.innerHTML = `<span class="sw" style="background:${colorOf(ck)}"></span>
    <span>${c.label}</span>
    <input type="color" value="${isDark()?c.dark:c.light}" title="رنگ این کلاستر">
    <span class="w">${c.scored? (c.weight*100).toFixed(0)+"٪" : "بدون امتیاز"}</span>`;
  const sw = row.querySelector(".sw"), inp = row.querySelector("input");
  row.addEventListener("click", e=>{
    if(e.target===inp) return;
    off.has(ck)? off.delete(ck) : off.add(ck);
    row.classList.toggle("off", off.has(ck)); placeAnchors();
  });
  inp.addEventListener("input", ()=>{
    c.custom = inp.value; sw.style.background = inp.value; draw();
  });
  legend.appendChild(row);
}
// ── پیشنهادها ──
const sug = document.getElementById("sugg");
if(!D.suggestions.length) sug.innerHTML = '<div class="card"><div class="r">موتور پیشنهادی ندارد — مدل با دادهٔ این اجرا می‌خواند.</div></div>';
for(const s of D.suggestions.slice(0,6)){
  const el = document.createElement("div"); el.className="card";
  el.innerHTML = `<div class="k">${s.title}</div>
    <div class="t">${s.metric? (byKey[s.metric]?.label||s.metric) : s.detail}</div>
    <div class="r">${s.metric? s.detail+"<br>":""}${s.reason}</div>`;
  sug.appendChild(el);
}
// ── انسجام ──
const coh = document.getElementById("coh");
for(const c of D.cohesion){
  const el = document.createElement("div"); el.className="card";
  const v = c.verdict, cls = v==="منسجم"? "good" : (v.startsWith("تک")? "warning":"critical");
  el.innerHTML = `<div class="t">${D.clusters[c.cluster]?.label||c.cluster}</div>
    <div class="r">درونی ${c.within??"—"} · بیرونی ${c.between??"—"} ·
    <span style="color:var(--${cls})">${v}</span></div>`;
  coh.appendChild(el);
}
// ── نمای جدولی ──
const tbl = document.getElementById("tbl");
tbl.innerHTML = "<thead><tr><th>شاخص</th><th>کلاستر</th><th>وزن مؤثر</th>"
  + "<th>میانگین</th><th>پراکندگی</th><th>نزدیک‌ترین کلاستر دیگر</th><th>داوری</th></tr></thead><tbody>"
  + D.nodes.map(n=>{
      const f = D.fits.find(x=>x.metric===n.key) || {};
      return `<tr><td>${n.label}</td><td>${D.clusters[n.cluster]?.label||"—"}</td>
        <td class="num">${(n.weight*100).toFixed(1)}٪</td>
        <td class="num">${n.mean??"—"}</td><td class="num">${n.spread??"—"}</td>
        <td>${f.other? (D.clusters[f.other]?.label||f.other)+" ("+(f.otherSim??"—")+")":"—"}</td>
        <td>${f.verdict||"—"}</td></tr>`; }).join("") + "</tbody>";

document.getElementById("sub").textContent =
  `نسخه مدل ${D.version} · ${D.nodes.length} شاخص · ${Object.keys(D.clusters).length} کلاستر`
  + (D.people? ` · ${D.people} نفر` : "");
document.getElementById("note").innerHTML =
  "کشش بین ذره‌ها همان همبستگی بردار شاخص‌هاست؛ حرکت، تزئین نیست. "
  + "پیشنهادها از دادهٔ <b>همین اجرا</b> می‌آیند و با دادهٔ دوره بعد عوض می‌شوند."
  + (REDUCED? "<br>حرکت به‌خاطر تنظیم «کاهش حرکت» سیستم شما خاموش است." : "");

document.getElementById("btnPlay").addEventListener("click", e=>{
  running = !running; e.target.setAttribute("aria-pressed", running);
  e.target.textContent = running? "⏸ توقف حرکت" : "▶ ادامه حرکت";
});
document.getElementById("btnTable").addEventListener("click", e=>{
  const on = document.getElementById("tableView").classList.toggle("hidden");
  e.target.setAttribute("aria-pressed", String(!on));
});
document.getElementById("btnTheme").addEventListener("click", ()=>{
  const now = isDark()? "light":"dark";
  document.documentElement.setAttribute("data-theme", now);
  document.querySelectorAll(".lg").forEach((row,i)=>{
    const ck = CK[i], c = D.clusters[ck];
    if(!c.custom){ row.querySelector("input").value = now==="dark"? c.dark : c.light;
                   row.querySelector(".sw").style.background = colorOf(ck); }
  });
  draw();
});
document.getElementById("pull").addEventListener("input", e=>{ pull = e.target.value/100; });

resize(); placeAnchors(); frame();
if(REDUCED){ for(let i=0;i<60;i++) step(); draw(); }
</script></body></html>
"""
