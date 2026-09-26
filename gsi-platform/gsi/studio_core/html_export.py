# -*- coding: utf-8 -*-
"""خروجی HTML خودبسنده — ساخته‌شده روی سیستم طراحی GSI.

## جریان کاربر (UX Flow)

صفحه به ترتیبی چیده شده که تصمیم‌گیرنده واقعاً می‌خواند، نه به ترتیبی که
داده تولید می‌شود:

    ۱ سربرگ        کجاییم، چه تاریخی، چقدر بحرانی           (زمینه)
    ۲ مسیر تصمیم   سرخط ← وضعیت/گره/اقدام ← یافته‌ها        (چه خبر است)
    ۳ فیلتر        برش بزن                                   (کنترل)
    ۴ سنجه         عدد کلیدی همین برش                        (چقدر)
    ۵ نمودار       شکل مسئله                                 (چرا)
    ۶ فرآیند       کجا کند می‌شود                            (کجا)
    ۷ جدول         ردیف‌ها، برای پیگیری                       (چه کسی/کدام)

هر لایه پاسخ یک سؤال است و تا سؤال قبلی جواب نگیرد، لایه بعد معنا ندارد.

## معماری این فایل پس از بازطراحی

نشانه‌گذاری، شیوه‌نامه و نمودارها هرکدام یک منبع دارند:

    gsi/design/tokens.py      رنگ، فاصله، تایپ، حرکت، نقاط شکست
    gsi/design/css.py         Auto Layout، Responsive، دسترس‌پذیری، چاپ
    gsi/design/components.py  کامپوننت‌ها و واریانت‌ها
    gsi/design/charts_js.py   نشانه‌های SVG داخل مرورگر

پیش از این، نسخه‌ای از این فایل **دو پیاده‌سازی رقیب** از یک runtime داشت و
هر دو emit می‌شدند؛ مرورگر با ``Identifier 'S' has already been declared``
کل بلوک دوم را رها می‌کرد و گزارش خالی بالا می‌آمد. حالا فقط یک بلوک
اجرایی وجود دارد و تست رگرسیون JS را در **scope مشترک** می‌سنجد.

## قاعده‌های تغییرناپذیر

* جمع‌ها **دانه‌ای** هستند: کلید دانه هر ستون به JS می‌رود و پیش از تجمیع
  یکتاسازی می‌شود، وگرنه فیلتر کردن «جمع مانده تعهد» را چند برابر می‌کند.
* هیچ منبع بیرونی بارگذاری نمی‌شود — گزارش از داخل Outlook و شبکه اداری
  باز می‌شود.
* رنگ هرگز تنها حامل معنا نیست؛ هر وضعیت آیکن و برچسب دارد.
"""
from __future__ import annotations

__contract__ = 3

import html
import json
from typing import Dict, List, Optional

import pandas as pd
from ..factsheet import VERSION as GSI_RUNTIME_VERSION

from ..design import charts_js as CJ
from ..design import components as C
from ..design import css as CSS
from .. import audience as AUD
from .. import voice as V
from ..design import tokens as T
from .grain import (GRAIN_KEYS, KIND_ADDITIVE, KIND_RATIO, column_grain,
                    measure_kind, prefix_grain_map, safe_agg)
from .composer import (normalize_tabs, HEADER_PRESETS, PROCESS_VIEWS,
                       KANBAN_MODES, KANBAN_CARD_FIELDS)
from . import html_customizer as HC

#: پالت وضعیت — از سیستم طراحی. ساختار قدیمی (رنگ، آیکن) حفظ شده تا
#: مصرف‌کننده‌های موجود تغییری نبینند.
BANDS: Dict[str, tuple] = {s.label: (s.fill, s.icon) for s in T.STATUS_SCALE}
BAND_INK: Dict[str, str] = {s.label: s.ink for s in T.STATUS_SCALE}
BAND_ORDER: List[str] = list(BANDS)

BRAND, BRAND_DEEP = T.BRAND_TEAL, T.BRAND_NAVY
SURFACE, RAISED, BORDER = T.SURFACE_PAGE, T.SURFACE_RAISED, T.BORDER
TEXT, TEXT2, TEXT3 = T.TEXT, T.TEXT_SECONDARY, T.TEXT_MUTED

#: مراحل زنجیره تأمین — لنگر ذهنی «الان کجای مسیریم».
SUPPLY_FLOW = ("تأمین قطعه", "ثبت سفارش و ارز", "حمل بین‌الملل",
               "گمرک و ترخیص", "ورود قطعه", "پشتیبانی تولید خودرو")


def _inline_json(value, **kwargs) -> str:
    """Serialize JSON safely for direct embedding inside an HTML ``<script>``.

    JSON itself allows the literal sequence ``</script>`` inside strings, but an
    HTML parser terminates the surrounding script element before JavaScript ever
    sees that string. Escape every closing-tag opener, plus the two Unicode line
    separators that have historically been problematic in inline JS contexts.
    """
    kwargs.setdefault("ensure_ascii", False)
    out = json.dumps(value, **kwargs)
    return (out.replace("</", "<\\/")
               .replace("\u2028", "\\u2028")
               .replace("\u2029", "\\u2029"))


def _measure_cols(df: pd.DataFrame, cols: List[str]) -> Dict[str, str]:
    """{ستون عددی: تجمیع بامعنا}.

    شناسه‌ها (شماره سفارش، کد متریال) کنار گذاشته می‌شوند — جمع زدنشان
    بی‌معناست. ستون نسبتی (مقاومت، درصد، امتیاز) میانگین می‌گیرد، نه جمع.
    """
    out: Dict[str, str] = {}
    for c in cols:
        if c not in df.columns:
            continue
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        if not (s.notna().mean() > 0.5 and s.notna().any()):
            continue
        kind = measure_kind(c, df[c])
        if kind == KIND_ADDITIVE:
            out[c] = "sum"
        elif kind == KIND_RATIO:
            out[c] = "mean"
    return out




def _safe_records(df: Optional[pd.DataFrame], limit: int = 60) -> List[Dict[str, str]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    x = df.head(limit).copy()
    for c in x.columns:
        if pd.api.types.is_datetime64_any_dtype(x[c]):
            x[c] = x[c].dt.strftime("%Y-%m-%d %H:%M")
    x = x.astype("object").where(x.notna(), "")
    return [{str(k): str(v) for k, v in r.items()} for r in x.to_dict(orient="records")]

def _pick_col(columns, candidates):
    for c in candidates:
        if c in columns:
            return c
    return None


def _fmt_num(v, digits: int = 0) -> str:
    try:
        n = float(v)
        if pd.isna(n):
            return "—"
        return f"{n:,.{digits}f}" if digits else f"{n:,.0f}"
    except Exception:
        return "—"


def _panel(title: str, body: str, note: str = "", cls: str = "") -> str:
    return (f'<section class="process-viz {cls}"><div class="pv-head"><div>'
            f'<h3>{html.escape(title)}</h3>'
            + (f'<p>{html.escape(note)}</p>' if note else '')
            + f'</div></div>{body}</section>')


def _process_flow_html(extras: Dict, uid: str) -> str:
    from .process_diagrams import flow_html
    return flow_html(extras, uid)


def _stage_aging_html(extras: Dict) -> str:
    q = extras.get("stage_queue")
    if not isinstance(q, pd.DataFrame) or q.empty:
        return _panel("Aging مراحل", '<div class="empty">صف جاری برای Aging موجود نیست.</div>')
    rows = q.copy()
    med = "میانه انتظار (روز)"
    if med not in rows.columns:
        return _panel("Aging مراحل", '<div class="empty">ستون میانه انتظار موجود نیست.</div>')
    rows[med] = pd.to_numeric(rows[med], errors="coerce")
    rows = rows.sort_values(med, ascending=False).head(12)
    mx = max(float(rows[med].max() or 0), 1.0)
    bars = []
    for r in rows.to_dict("records"):
        v = float(r.get(med) or 0)
        pct = min(100, max(3, v / mx * 100))
        bars.append(f'<div class="rank-row"><div class="rank-label">{html.escape(str(r.get("مرحله جاری","")))}</div>'
                    f'<div class="rank-track"><span style="width:{pct:.1f}%"></span></div>'
                    f'<b>{_fmt_num(v)} روز</b><small>{_fmt_num(r.get("تعداد پرونده"))} پرونده</small></div>')
    return _panel("Aging مراحل / انتظار جاری", '<div class="rank-list">'+''.join(bars)+'</div>',
                  "میانه انتظار پرونده‌های باز؛ میانگین استفاده نمی‌شود.")


def _bottleneck_html(extras: Dict) -> str:
    b = extras.get("bottlenecks")
    if not isinstance(b, pd.DataFrame) or b.empty:
        return _panel("گلوگاه گذارها", '<div class="empty">گذار کامل‌شده کافی نیست.</div>')
    x = b.copy().head(12)
    med = pd.to_numeric(x.get("میانه روز"), errors="coerce")
    mx = max(float(med.max() or 0), 1.0)
    rows=[]
    for pos,r in enumerate(x.to_dict("records"),1):
        v=float(r.get("میانه روز") or 0); pct=min(100,max(3,v/mx*100))
        label=f'{r.get("از فعالیت","")} ← {r.get("به فعالیت","")}'
        rows.append(f'<article class="bn-card"><span class="bn-rank">{pos}</span><div class="bn-main">'
                    f'<strong>{html.escape(label)}</strong><div class="rank-track"><span style="width:{pct:.1f}%"></span></div>'
                    f'<small>میانه {_fmt_num(v,1)} روز · P90 {_fmt_num(r.get("صدک ۹۰ روز"),1)} · {_fmt_num(r.get("تعداد پرونده"))} پرونده</small>'
                    '</div></article>')
    return _panel("رتبه‌بندی گلوگاه‌های فرآیند", '<div class="bn-list">'+''.join(rows)+'</div>',
                  "گذارهای کامل‌شده؛ رتبه بر اساس میانه زمان.")


def _transition_heatmap_html(extras: Dict) -> str:
    b = extras.get("bottlenecks")
    if not isinstance(b, pd.DataFrame) or b.empty:
        return _panel("Heatmap گذارها", '<div class="empty">گذار کافی برای Heatmap موجود نیست.</div>')
    x=b.copy(); x["میانه روز"]=pd.to_numeric(x.get("میانه روز"),errors="coerce")
    # Keep the matrix readable: activities participating in the most cases.
    score={}
    for r in x.to_dict("records"):
        n=float(r.get("تعداد پرونده") or 0)
        score[str(r.get("از فعالیت",""))]=score.get(str(r.get("از فعالیت","")),0)+n
        score[str(r.get("به فعالیت",""))]=score.get(str(r.get("به فعالیت","")),0)+n
    acts=[k for k,_ in sorted(score.items(),key=lambda kv:kv[1],reverse=True)[:8] if k]
    if not acts:return _panel("Heatmap گذارها", '<div class="empty">فعالیت کافی نیست.</div>')
    lookup={(str(r.get("از فعالیت","")),str(r.get("به فعالیت",""))):r for r in x.to_dict("records")}
    vals=[float(r.get("میانه روز") or 0) for r in lookup.values()]
    mx=max(vals or [1]) or 1
    head='<th></th>'+''.join(f'<th title="{html.escape(a)}">{html.escape(a[:18])}</th>' for a in acts)
    body=[]
    for fr in acts:
        cells=[f'<th title="{html.escape(fr)}">{html.escape(fr[:18])}</th>']
        for to in acts:
            r=lookup.get((fr,to))
            if not r: cells.append('<td class="hm-empty">—</td>'); continue
            v=float(r.get("میانه روز") or 0); alpha=.10+.72*min(1,v/mx)
            cells.append(f'<td style="background:rgba(10,124,134,{alpha:.3f})" title="{_fmt_num(r.get("تعداد پرونده"))} پرونده"><b>{_fmt_num(v,1)}</b><small>روز</small></td>')
        body.append('<tr>'+''.join(cells)+'</tr>')
    table='<div class="heatmap-wrap"><table class="heatmap"><thead><tr>'+head+'</tr></thead><tbody>'+''.join(body)+'</tbody></table></div>'
    return _panel("Transition Heatmap", table, "شدت رنگ = میانه زمان گذار؛ tooltip = تعداد پرونده.")


def _variants_html(extras: Dict) -> str:
    from .process_diagrams import variants_html
    return variants_html(extras.get("variants"))


def _conformance_html(extras: Dict) -> str:
    c=extras.get("conformance_cases")
    if not isinstance(c,pd.DataFrame) or c.empty:
        return _panel("Conformance", '<div class="empty">پرونده قابل ارزیابی موجود نیست.</div>')
    dev=_pick_col(c.columns,["deviation","انحراف فرآیند"])
    score=_pick_col(c.columns,["score","امتیاز انطباق (٪)"])
    if not dev:
        return _panel("Conformance", '<div class="empty">ستون انحراف موجود نیست.</div>')
    vc=c[dev].fillna("نامشخص").astype(str).value_counts()
    total=int(vc.sum())
    cards=''.join(f'<div class="conf-card"><b>{n:,}</b><span>{html.escape(k)}</span><small>{(n/max(total,1)*100):.1f}٪</small></div>' for k,n in vc.items())
    score_note=''
    if score:
        mean=pd.to_numeric(c[score],errors="coerce").mean()
        if pd.notna(mean): score_note=f'<div class="conf-score"><span>میانگین انطباق پرونده‌های قابل ارزیابی</span><b>{mean:.1f}٪</b></div>'
    return _panel("Conformance / انحراف فرآیند", '<div class="conf-grid">'+cards+'</div>'+score_note,
                  "Unknown با «بدون انحراف» یکی نیست.")


def _funnel_html(extras: Dict) -> str:
    ev=extras.get("eventlog")
    if not isinstance(ev,pd.DataFrame) or ev.empty:
        return _panel("Funnel", '<div class="empty">Event Log کافی نیست.</div>')
    act=_pick_col(ev.columns,["ACTIVITY_FA","ACTIVITY_EN"]); case=_pick_col(ev.columns,["_CASE_KEY","CASE_KEY"])
    if not act or not case:return _panel("Funnel", '<div class="empty">کلید فعالیت/پرونده موجود نیست.</div>')
    x=ev.copy();
    if "_SORTING" in x.columns:
        order=(x[[act,"_SORTING"]].sort_values("_SORTING").drop_duplicates(act)[act].astype(str).tolist())
    else: order=list(dict.fromkeys(x[act].astype(str)))
    cnt=x.groupby(act)[case].nunique().to_dict(); mx=max([cnt.get(a,0) for a in order] or [1]) or 1
    items=[]
    for a in order[:14]:
        n=int(cnt.get(a,0)); pct=max(10,n/mx*100)
        items.append(f'<div class="funnel-step" style="width:{pct:.1f}%"><strong>{html.escape(a)}</strong><span>{n:,} پرونده</span></div>')
    return _panel("Funnel پوشش رویدادهای فرآیند", '<div class="process-funnel">'+''.join(items)+'</div>',
                  "پوشش رویداد در پرونده‌ها؛ این نمودار به‌تنهایی نرخ تبدیل تجاری نیست.")


def _timeline_html(extras: Dict, uid: str) -> str:
    ev=extras.get("eventlog")
    if not isinstance(ev,pd.DataFrame) or ev.empty:
        return _panel("Case Timeline", '<div class="empty">Event Log کافی نیست.</div>')
    case=_pick_col(ev.columns,["_CASE_KEY","CASE_KEY"]); act=_pick_col(ev.columns,["ACTIVITY_FA","ACTIVITY_EN"])
    if not case or not act:return _panel("Case Timeline", '<div class="empty">کلید پرونده/فعالیت موجود نیست.</div>')
    x=ev.copy();time=_pick_col(x.columns,["EVENTTIME","EVENT_DATE"])
    if time:x[time]=pd.to_datetime(x[time],errors="coerce")
    cases=list(x[case].dropna().astype(str).value_counts().head(120).index)
    payload={}
    for k in cases:
        z=x[x[case].astype(str)==k].copy()
        if time:z=z.sort_values(time)
        payload[k]=[{"a":str(r.get(act,"")),"t":(r.get(time).strftime("%Y-%m-%d") if time and pd.notna(r.get(time)) else ""),"s":str(r.get("SOURCE_SYSTEM",r.get("SOURCE","")))} for r in z.to_dict("records")]
    if not payload:return _panel("Case Timeline", '<div class="empty">پرونده‌ای برای Timeline نیست.</div>')
    opts=''.join(f'<option value="{html.escape(k)}">{html.escape(k)}</option>' for k in cases)
    jsdata=_inline_json(payload)
    sid='timeline_'+''.join(ch for ch in uid if ch.isalnum() or ch=='_')
    # This script lives inside the pane before the shared runtime is parsed, so it
    # MUST NOT depend on runtime helpers such as ``esc2``.  Keep a local encoder.
    body=(f'<div class="timeline-toolbar"><label>پرونده<select id="sel_{sid}" onchange="render_{sid}(this.value)">{opts}</select></label></div>'
          f'<div id="{sid}" class="case-timeline"></div><script>(function(){{const D={jsdata};'
          f'const E=s=>String(s??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\\x22/g,"&quot;").replace(/\\x27/g,"&#39;");'
          f'window.render_{sid}=function(k){{const e=document.getElementById("{sid}");const a=D[k]||[];e.innerHTML=a.map((x,i)=>`<div class="tl-item"><span class="tl-dot"></span><div><b>${{E(x.a)}}</b><small>${{E(x.t)}}${{x.s?" · "+E(x.s):""}}</small></div></div>`).join("")||"<div class=empty>رویدادی نیست.</div>";}};'
          f'const s=document.getElementById("sel_{sid}");if(s)render_{sid}(s.value);}})();</script>')
    return _panel("Case Timeline تعاملی", body, "پرونده را انتخاب کنید؛ ترتیب از Event Log واقعی است.")


def _process_suite_html(extras: Optional[Dict], views: List[str], uid: str, sizes: Optional[Dict[str, str]] = None) -> str:
    from .process_views_html import CHART_CSS as _KANBAN_CSS, RENDERERS as _KANBAN_VIEWS
    extras=extras or {}; sizes=sizes or {}; parts=[]
    # CSS نماهای Kanban یک بار برای کل مجموعه می‌آید، نه به‌ازای هر پنل.
    if any(v in _KANBAN_VIEWS for v in views): parts.append(_KANBAN_CSS)
    # همین‌طور CSS نقشهٔ فرآیند/Variant Explorer — یک بار، حتی اگر هر دو نما فعال باشند.
    if any(v in ("flow_map", "variants") for v in views):
        from .process_diagrams import STYLE as _PM_STYLE
        parts.append(_PM_STYLE)
    for v in views:
        piece = ""
        if v=="flow_map": piece=_process_flow_html(extras,uid)
        elif v=="stage_aging": piece=_stage_aging_html(extras)
        elif v=="bottleneck": piece=_bottleneck_html(extras)
        elif v=="transition_heatmap": piece=_transition_heatmap_html(extras)
        elif v=="variants": piece=_variants_html(extras)
        elif v=="conformance": piece=_conformance_html(extras)
        elif v=="funnel": piece=_funnel_html(extras)
        elif v=="case_timeline": piece=_timeline_html(extras,uid)
        else:
            from .process_views_html import render as _kanban_view
            piece=_kanban_view(v, extras) or ""
        if piece:
            parts.append(f'<div class="gsi-process-item" data-gsi-process-view="{html.escape(v, quote=True)}" data-gsi-item-key="process:{html.escape(v, quote=True)}" data-gsi-size="{html.escape(str(sizes.get(v, "full")), quote=True)}">{piece}</div>')
    if not parts:
        return C.panel('<div class="empty">برای این تب Process View انتخاب نشده است.</div>',
                       title='⛓ فرآیند و گلوگاه‌ها — Process Mining Studio')
    factor_note = ''
    rc = extras.get("conformance_root_causes")
    if isinstance(rc, pd.DataFrame) and not rc.empty:
        factor_note = '<div class="alert" style="--tone-ink:var(--teal-ink);--tone-wash:var(--teal-wash)"><b>عوامل همراه با انحراف:</b> این بخش همبستگی نشان می‌دهد، نه علت؛ قبل از اقدام ترکیب پرونده‌ها بررسی شود.</div>'
    return ('<div class="process-suite-head"><div><span class="t-overline">PROCESS MINING STUDIO</span>'
            '<h2 class="t-h2">⛓ فرآیند و گلوگاه‌ها</h2><p class="process-scope-note">دامنه این تحلیل = Scope همین خروجی و همین مخاطب؛ فیلتر مرورگر فقط جدول/نمودار تعاملی را تغییر می‌دهد.</p></div>'
            '<span class="badge badge--quiet">Event Log واقعی</span></div>'
            '<div class="process-suite">'+''.join(parts)+factor_note+'</div>')


def _priority_tone(p: str) -> str:
    p=str(p or '').upper()
    return 'critical' if p in {'CRITICAL','URGENT'} else ('serious' if p=='HIGH' else ('warning' if p=='MEDIUM' else 'neutral'))


def _kanban_board_html(extras: Optional[Dict], mode: str = "due_window",
                       card_fields: Optional[List[str]] = None) -> str:
    extras=extras or {}; a=extras.get("case_actions")
    if not isinstance(a,pd.DataFrame) or a.empty:
        return C.panel('<div class="empty">Action Queue واقعی برای این دامنه موجود نیست.</div>',
                       title='▦ کانبان / Scrum Action Board', note='Board فقط از case_actions واقعی ساخته می‌شود.')
    raw=a.copy().astype('object').where(a.notna(), '').to_dict('records')
    flds=list(card_fields or ["title","owner","due","priority","evidence"])
    def first(r,*names):
        for n in names:
            v=r.get(n,'')
            if str(v).strip(): return v
        return ''
    rows=[]
    for r0 in raw:
        r=dict(r0)
        r['_CASE']=first(r,'KEY_REG','CASE_KEY','_CASE_KEY','FX_CASE_KEY','CANONICAL_ORDER','CANONICAL_BL')
        r['_TITLE']=first(r,'TITLE','NEXT_ACTION','NEXT_ACTION_TITLE','ACTION','اقدام پیشنهادی','عنوان اقدام','SUGGESTION')
        r['_OWNER']=first(r,'OWNER_ROLE','OWNER','ACTION_OWNER','NEXT_ACTION_OWNER','مسئول')
        r['_PRIORITY']=str(first(r,'PRIORITY','NEXT_ACTION_PRIORITY','اولویت') or 'نامشخص')
        r['_STATUS']=str(first(r,'STATUS','ACTION_STATUS','STATE','وضعیت') or 'نامشخص')
        r['_DUE']=first(r,'DUE_DATE','NEXT_ACTION_DUE_DATE','DEADLINE','موعد')
        r['_DAYS']=first(r,'DAYS_REMAINING','NEXT_ACTION_DAYS','AGING_DAYS','WAIT_DAYS')
        r['_RATIONALE']=first(r,'RATIONALE','REASON','علت')
        r['_EVIDENCE']=first(r,'EVIDENCE_GAPS','NEXT_ACTION_EVIDENCE_GAPS','شواهد ناقص')
        r['_BASIS']=first(r,'RULE_BASIS','NEXT_ACTION_RULE_BASIS','مبنای پیشنهاد')
        rows.append(r)
    def daynum(r):
        try:return float(r.get('_DAYS'))
        except Exception:return None
    def bucket(r):
        pr=str(r.get('_PRIORITY','')).upper(); st=str(r.get('_STATUS','') or '')
        owner=str(r.get('_OWNER','') or 'بدون مالک'); d=daynum(r)
        if mode=='priority': return pr or 'نامشخص'
        if mode=='owner': return owner or 'بدون مالک'
        if mode=='status': return st or 'نامشخص'
        if mode=='action_code': return str(r.get('ACTION_CODE') or r.get('_TITLE') or 'نامشخص')
        if mode=='evidence':
            return 'مسدود — شکاف شاهد' if str(r.get('_EVIDENCE') or '').strip() else 'آماده اقدام'
        if (d is not None and d<0) or pr in {'CRITICAL','URGENT'}: return 'معوق / فوری'
        if d is not None and d<=7: return 'این هفته'
        if d is not None and d<=30: return 'بعدی'
        return 'Backlog'
    # Within each lane: highest business priority first, then nearest/overdue due date.
    prank={'CRITICAL':5,'URGENT':5,'HIGH':4,'MEDIUM':3,'LOW':2,'NORMAL':1}
    rows.sort(key=lambda r:(-prank.get(str(r.get('_PRIORITY','')).upper(),0),
                            daynum(r) if daynum(r) is not None else 10**9,
                            str(r.get('_CASE',''))))
    buckets={}
    for r in rows:buckets.setdefault(bucket(r),[]).append(r)
    pref=['معوق / فوری','این هفته','بعدی','Backlog','مسدود — شکاف شاهد','آماده اقدام',
          'CRITICAL','HIGH','MEDIUM','LOW','PENDING_REVIEW','مسدود','نیازمند اقدام']
    keys=sorted(buckets,key=lambda k:(pref.index(k) if k in pref else 99,-len(buckets[k]),k))[:6]
    overdue=sum(1 for r in rows if daynum(r) is not None and daynum(r)<0)
    critical=sum(1 for r in rows if str(r.get('_PRIORITY','')).upper() in {'CRITICAL','URGENT'})
    cases=len({str(r.get('_CASE','')).strip() for r in rows if str(r.get('_CASE','')).strip()})
    owners=len({str(r.get('_OWNER','')).strip() for r in rows if str(r.get('_OWNER','')).strip()})
    metrics=(f'<div class="kanban-metrics"><div><b>{len(rows):,}</b><span>اقدام</span></div><div><b>{cases:,}</b><span>پرونده</span></div>'
             f'<div data-tone="critical"><b>{overdue:,}</b><span>معوق</span></div><div data-tone="serious"><b>{critical:,}</b><span>فوری</span></div><div><b>{owners:,}</b><span>مالک</span></div></div>')
    cols=[]
    for key in keys:
        items=buckets[key]
        cards=[]
        lane_tone = ('critical' if key in {'معوق / فوری','CRITICAL','URGENT','مسدود','مسدود — شکاف شاهد'}
                     else ('warning' if key in {'این هفته','بعدی','HIGH','MEDIUM','نیازمند اقدام'} else 'neutral'))
        for r in items[:7]:
            case=html.escape(str(r.get('_CASE') or 'پرونده'))
            pr=str(r.get('_PRIORITY') or 'نامشخص'); tone=_priority_tone(pr)
            parts=[f'<div class="kc-top"><b>{case}</b><span class="priority" data-tone="{tone}">{html.escape(pr)}</span></div>']
            if 'title' in flds: parts.append(f'<h4>{html.escape(str(r.get("_TITLE") or "اقدام بعدی"))}</h4>')
            meta=[]
            if 'owner' in flds and r.get('_OWNER'):
                owner=str(r.get('_OWNER'))
                # حروف اول برای آواتار دایره‌ای — همان الگوی «نام اول توکن»،
                # چون نقش‌ها معمولاً «رفع تعهد/بانک عامل» یا «کارشناس ترخیص»‌اند.
                initials=html.escape((owner.replace('/',' ').split() or [owner])[0][:2])
                meta.append(f'<span class="kc-avatar">{initials}</span> '+html.escape(owner))
            if 'due' in flds:
                due=str(r.get('_DUE') or ''); days=r.get('_DAYS','')
                if due or str(days)!='':
                    d=daynum(r)
                    due_tone=('overdue' if (d is not None and d<0) else
                              'soon' if (d is not None and d<=7) else
                              'future' if d is not None else None)
                    due_txt=html.escape(due)+(f' · {html.escape(str(days))} روز' if str(days)!='' else '')
                    if due_tone:
                        meta.append(f'<span class="kc-due" data-tone="{due_tone}">◷ {due_txt}</span>')
                    else:
                        meta.append('◷ '+due_txt)
            if meta:parts.append('<div class="kc-meta">'+' · '.join(meta)+'</div>')
            if 'reason' in flds and r.get('_RATIONALE'): parts.append(f'<p>{html.escape(str(r.get("_RATIONALE")))}</p>')
            if 'evidence' in flds and r.get('_EVIDENCE'): parts.append(f'<div class="kc-gap">شاهد ناقص: {html.escape(str(r.get("_EVIDENCE")))}</div>')
            if 'basis' in flds and r.get('_BASIS'): parts.append(f'<details><summary>مبنای پیشنهاد</summary><small>{html.escape(str(r.get("_BASIS")))}</small></details>')
            cards.append('<article class="kanban-card" data-tone="'+tone+'">'+''.join(parts)+'</article>')
        more = max(len(items)-len(cards), 0)
        more_html = f'<div class="kanban-more">+ {more:,} مورد دیگر</div>' if more else ''
        cols.append(f'<section class="kanban-col" data-tone="{lane_tone}"><header><h3>{html.escape(key)}</h3><span>{len(items):,}</span></header><div class="kanban-stack">'+''.join(cards)+f'</div>{more_html}</section>')
    board=metrics+'<div class="kanban-board">'+''.join(cols)+'</div>'
    return C.panel(board,title='▦ کانبان / Scrum Action Board — Operational Kanban',
                   note='WIP، Owner، Priority، موعد و Evidence از Action Queue واقعی؛ velocity/burndown ساختگی تولید نمی‌شود.')

def _quality_block_html(df: pd.DataFrame, fields: List[str], labels: Dict[str,str]) -> str:
    rows=[]
    for c in fields:
        if c not in df.columns: continue
        z=df[c]; filled=int((z.notna() & z.astype(str).str.strip().ne('')).sum())
        pct=100*filled/max(len(df),1)
        rows.append((labels.get(c,c),pct,filled))
    rows=sorted(rows,key=lambda x:x[1])[:12]
    if not rows:return C.panel('<div class="empty">فیلدی برای کیفیت داده انتخاب نشده است.</div>',title='◍ کیفیت داده')
    body=''.join(f'<div class="dq-row"><span>{html.escape(str(n))}</span><div><i style="width:{p:.1f}%"></i></div><b>{p:.0f}٪</b></div>' for n,p,_ in rows)
    return C.panel('<div class="dq-list">'+body+'</div>',title='◍ کیفیت داده و پوشش',note='کم‌پوشش‌ترین فیلدهای همین تب.')


def _story_shell(i: int) -> str:
    return (f'<section id="story_{i}" class="story reveal" data-section="story" aria-labelledby="story_h_{i}">'
            '<div class="t-overline" style="color:var(--gold-ink)">◈ مسیر تصمیم</div>'
            f'<h2 class="t-h2" id="story_h_{i}" style="margin:4px 0 12px"></h2>'
            f'<p class="note" id="story_q_{i}"></p>'
            f'<div class="grid-auto" style="--col:250px" id="story_scr_{i}"></div>'
            f'<div class="grid-auto" style="--col:272px;margin-top:12px" id="story_findings_{i}"></div></section>')

def build_dynamic_html(df: pd.DataFrame, ref_date: str, title: str = "GSI",
                       max_rows: int = 2500, selected_fields=None,
                       labels: Optional[Dict[str, str]] = None,
                       template_title: str = "", subtitle: str = "",
                       show_visuals: bool = True, show_tables: bool = True,
                       show_process: bool = True, tabs: Optional[List[Dict]] = None,
                       charts: Optional[List[str]] = None,
                       process_extras: Optional[Dict] = None,
                       max_payload_cells: int = 0,
                       lineage: Optional[Dict[str, str]] = None,
                       audience: Optional[str] = None,
                       header_title: str = "", header_subtitle: str = "",
                       header_preset: str = "figma_aqua",
                       learning_lesson: Optional[Dict] = None,
                       anythingllm_embed: Optional[Dict] = None,
                       knowledge_chat: Optional[Dict] = None,
                       material_supply_view: Optional[pd.DataFrame] = None,
                       include_material_view: bool = True) -> str:
    """HTML خودبسنده با تب‌های واقعی، فیلتر زنده و نمای مخاطب‌محور.

    ``audience`` تعیین می‌کند این artifact برای چه Persona ساخته شود؛ هر
    فایل فقط یک مخاطب دارد. تب‌های داخل فایل صرفاً نماهای مستقل همان مخاطب‌اند
    و هر تب مالک Blockها، نمودارها، Process Viewها، Kanban و فیلدهای خودش است.
    بنابراین هیچ محتوایی به‌طور ضمنی از یک تب یا Persona به دیگری نشت نمی‌کند.
    """
    from .report_builder import _filtered_process_extras
    process_extras = _filtered_process_extras(process_extras or {}, df)
    aud = AUD.get(audience)
    default_cols = ["KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_REG",
                    "CANONICAL_EXPERT", "ORG_DEPT", "TRANSPORT_MODE",
                    "بحرانی (کوتاه)", "مقاومت (روز)"]
    requested = list(selected_fields or default_cols)
    labels = labels or {}
    raw_tabs = normalize_tabs(tabs, requested, aud.key, charts or [])
    norm_tabs = []
    for i, tab in enumerate(raw_tabs):
        title_i = str(tab.get("title") or f"تب {i+1}")
        fields_i = [c for c in tab.get("fields", requested) if c in df.columns]
        if not fields_i:
            fields_i = [c for c in requested if c in df.columns] or list(df.columns[:12])
        tab_id = str(tab.get("id") or f"tab_{i}")
        norm_tabs.append({"id": f"pane_{tab_id}", "tab_id": tab_id,
                          "title": title_i, "fields": fields_i,
                          "max_rows": int(tab.get("max_rows") or max_rows),
                          "blocks": list(tab.get("blocks") or []),
                          "block_sizes": dict(tab.get("block_sizes") or {}),
                          "charts": list(tab.get("charts") or []),
                          "chart_sizes": dict(tab.get("chart_sizes") or {}),
                          "process_views": list(tab.get("process_views") or []),
                          "process_sizes": dict(tab.get("process_sizes") or {}),
                          "kanban_mode": str(tab.get("kanban_mode") or "due_window"),
                          "kanban_card_fields": list(tab.get("kanban_card_fields") or [])})

    # KEY_MATERIAL is a first-class business identity in the certified HTML.
    # Saved Composer tabs may predate the material field; in that case the
    # Streamlit supply view can show material while the exported HTML silently
    # loses it.  Keep each tab self-contained: when real material evidence is
    # present, inject KEY_MATERIAL into *that tab's* field list.  This gives the
    # tab its own column and its own filter and deliberately avoids any global
    # table outside the pane hierarchy.
    if norm_tabs and "KEY_MATERIAL" in df.columns:
        _mat = df["KEY_MATERIAL"].fillna("").astype(str).str.strip()
        if _mat.ne("").any():
            for _tab in norm_tabs:
                if "KEY_MATERIAL" not in _tab["fields"]:
                    _tab["fields"] = ["KEY_MATERIAL"] + list(_tab["fields"])

    pm = prefix_grain_map()
    band_col = "بحرانی (کوتاه)" if "بحرانی (کوتاه)" in df.columns else None
    all_needed: List[str] = []
    for tab in norm_tabs:
        for c in tab["fields"]:
            if c not in all_needed:
                all_needed.append(c)
    for k in GRAIN_KEYS.values():
        if k in df.columns and k not in all_needed:
            all_needed.append(k)
    if band_col and band_col not in all_needed:
        all_needed.append(band_col)
    # وابستگی نمودارها hidden وارد payload می‌شود: نمودار presentation است و
    # نباید کاربر را مجبور کند فیلد پشتیبان را به جدول اضافه کند.
    for c in ("روزهای رسوب", "مقاومت (روز)", "مانده تعهد", "روزهای تأخیر",
              "FX_NTSW_BALANCE_EUR_EQ", "FX_NTSW_BALANCE_RIAL_EQ", "FX_NTSW_CURRENCY",
              "مقاومت انبار (روز)", "STAGE_FA", "ORDER_STAGE_FA", "CASE_KEY"):
        if c in df.columns and c not in all_needed:
            all_needed.append(c)

    cap = max(t["max_rows"] for t in norm_tabs)
    data = df[all_needed].copy()
    for c in data.columns:
        if pd.api.types.is_datetime64_any_dtype(data[c]):
            data[c] = data[c].dt.strftime("%Y-%m-%d")
    # Avoid pandas silent-downcast semantics: JSON payload is presentation data.
    data = data.astype("object").where(data.notna(), "")
    # Compact row-array payload: field names are stored once in COL_INDEX rather
    # than repeated for every row.  For wide reports this cuts standalone HTML
    # size dramatically without dropping rows or fields.  Runtime helper S()
    # transparently supports both this compact form and legacy object records.
    records = _inline_json(data.to_numpy(dtype=object).tolist(), default=str)

    # ── شفافیت پوشش داده ──
    # payload همه ردیف‌ها را نگه می‌دارد، ولی فقط ستون‌های لازمِ تب‌ها/نمودارها را.
    # اگر این انتخاب اعلام نشود، خواننده نمی‌داند چه شواهدی در فایل نیست و ممکن
    # است نبودِ یک ستون را «نبودِ داده» بخواند. هر حذف باید در خود فایل اعلام شود.
    _source_columns = [str(c) for c in df.columns]
    _payload_columns = [str(c) for c in all_needed]
    _payload_set = set(_payload_columns)
    excluded_columns = [c for c in _source_columns if c not in _payload_set]
    coverage_truncations: List[Dict[str, object]] = []

    # The Streamlit “Supply View — Material” is a derived decision view, not just
    # the KEY_MATERIAL column.  Carry that exact view as a dedicated per-artifact
    # dataset so HTML can render it as one real, filterable tab without polluting
    # every authored Composer tab or changing their grain.
    # Enforce the contract even if an old caller supplies a precomputed view.
    # Do not hide failures: a missing advisory view must not look successful.
    from ..report.supply_views import build_material_html_view
    material_view = build_material_html_view(df, today=ref_date) if include_material_view else pd.DataFrame()
    if not material_view.empty:
        # Keep the complete material view in the searchable payload. max_rows is
        # a presentation cap applied by rows(t) *after* filters/search; truncating
        # here made late material rows impossible to find.
        material_view = material_view.copy()
        for c in material_view.columns:
            if pd.api.types.is_datetime64_any_dtype(material_view[c]):
                material_view[c] = material_view[c].dt.strftime("%Y-%m-%d")
        material_view = material_view.astype("object").where(material_view.notna(), "")
    material_records = _inline_json(material_view.to_dict(orient="records"), default=str)

    def tab_meta(tab):
        cols = tab["fields"]
        measures = _measure_cols(df, cols)
        grain_of = {c: (GRAIN_KEYS.get(column_grain(c, pm)) or "") for c in cols}
        filters = []
        identity_text_filters = {
            "KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_REG",
            "KEY_PR", "CANONICAL_EXPERT",
        }
        for c in cols:
            vals = sorted({str(x) for x in data[c].tolist() if str(x).strip()})
            if 1 < len(vals) <= 40:
                filters.append((c, labels.get(c, c), vals, "select"))
            elif len(vals) > 40 and c in identity_text_filters:
                # High-cardinality business identities must remain directly
                # filterable inside their owning tab. A select with hundreds
                # of values is unusable, so use contains-text semantics.
                filters.append((c, labels.get(c, c), [], "text"))
            if len(filters) >= 5:
                break
        return measures, grain_of, filters

    # ── ۱) سربرگ ──
    stats = []
    if band_col:
        vc = df[band_col].astype(str).value_counts()
        for b in ("توقف خط", "بحرانی"):
            n = int(vc.get(b, 0))
            if n:
                stats.append((b, f"{n:,}"))
    actions = C.button("چاپ / ذخیره PDF", variant="secondary", icon="🖨",
                       onclick="window.print()")
    hp = HEADER_PRESETS.get(header_preset, HEADER_PRESETS["figma_aqua"])
    hdr_title = (header_title or hp.get("title") or title).strip()
    hdr_sub = (header_subtitle or hp.get("subtitle") or "").strip()
    full_sub = " · ".join(x for x in [hdr_sub, template_title, f"تاریخ مرجع {ref_date}", subtitle] if x)
    header = C.app_bar(
        hdr_title,
        eyebrow="GSI · GLOBAL SOURCING INTELLIGENCE · DATA • PROCESS • DECISION",
        subtitle=full_sub, stats=stats, actions=actions)

    legend_html = C.legend(T.STATUS_SCALE)
    flow_html = C.flow(SUPPLY_FLOW)

    # ── مخاطب artifact ──
    # هر artifact فقط برای یک persona ساخته می‌شود. نسخه‌های قبلی سه نمای
    # کارشناس/مدیر/مدیر ارشد را در یک HTML می‌گذاشتند؛ این رفتار برای ارسال
    # رسمی مبهم بود و اکنون حذف شده است.
    shown = [aud.key]
    persona_html = (
        '<div class="cluster cluster-xs no-print" aria-label="مخاطب گزارش">'
        '<span class="t-overline">مخاطب این خروجی</span>'
        f'<span class="chip persona" aria-pressed="true">{html.escape(aud.fa)}</span>'
        '</div>')
    aud_json = _inline_json({
        aud.key: {"fa": aud.fa, "question": aud.question, "sections": list(aud.sections),
                  "max_findings": aud.max_findings, "table_rows": aud.table_rows,
                  "depth": aud.narrative_depth, "charts": list(aud.charts),
                  "quality": aud.show_data_quality, "provenance": aud.show_provenance,
                  "closing": aud.closing}
    })


    buttons = "".join(
        f'<button class="tabbtn" type="button" role="tab" id="tab_{i}" '
        f'aria-selected="{str(i == 0).lower()}" aria-controls="{t["id"]}" '
        f'data-pane="{t["id"]}">{html.escape(t["title"])}</button>'
        for i, t in enumerate(norm_tabs))

    # ── پنل‌های تب / Composer ──
    panes, metas = [], []
    for i, tab in enumerate(norm_tabs):
        cols = tab["fields"]
        measures, grain_of, filters = tab_meta(tab)
        head = "".join(f'<th scope="col">{html.escape(labels.get(c, c))}</th>' for c in cols)
        _filter_controls = []
        for j, (c, lab, vals, mode) in enumerate(filters):
            if mode == "text":
                _filter_controls.append(
                    f'<label for="f_{i}_{j}">{html.escape(lab)}'
                    f'<input id="f_{i}_{j}" type="search" data-f="{html.escape(c)}" '
                    f'data-filter-mode="contains" data-pane="{tab["id"]}" '
                    f'placeholder="جستجو در {html.escape(lab)}"></label>'
                )
            else:
                _filter_controls.append(
                    f'<label for="f_{i}_{j}">{html.escape(lab)}'
                    f'<select id="f_{i}_{j}" data-f="{html.escape(c)}" '
                    f'data-filter-mode="exact" data-pane="{tab["id"]}">'
                    f'<option value="">همه</option>'
                    + "".join(f"<option>{html.escape(v)}</option>" for v in vals)
                    + "</select></label>"
                )
        fhtml = "".join(_filter_controls)
        toolbar = (f'<div class="toolbar cluster cluster-sm no-print">{fhtml}'
                   f'<div class="cluster cluster-xs hug">'
                   + C.button("استخراج داده فیلترشده (Excel)", variant="secondary", icon="⬇",
                              onclick="downloadFilteredXlsx()", attrs='data-role="export"')
                   + "</div></div>") if fhtml else ""
        hidden = ' hidden' if i else ''
        block_html=[]
        block_sizes=dict(tab.get("block_sizes") or {})
        def _block_open(name):
            size=block_sizes.get(name,"full")
            return f'<section data-composer-block="{html.escape(name,quote=True)}" data-gsi-size="{html.escape(str(size),quote=True)}">'
        for block in tab.get("blocks", []):
            if block == "story":
                block_html.append(_block_open('story')+_story_shell(i)+'</section>')
            elif block == "kpi":
                block_html.append(_block_open('kpi')+f'<div class="grid-auto" style="--col:190px" id="cards_{i}"></div></section>')
            elif block == "charts" and show_visuals:
                block_html.append(_block_open('charts')+f'<div class="grid-auto" style="--col:370px" id="charts_{i}"></div></section>')
            elif block == "cashflow":
                try:
                    from ..cashflow.process_design import build_cashflow_process_html
                    _cf=build_cashflow_process_html(extras=process_extras or {}, instance_id=f'cashflow_tab_{i}', compact=True)
                except Exception:
                    _cf='<section class="panel reveal process-fx"><div class="empty">شواهد کافی برای نقشه جریان پول موجود نیست.</div></section>'
                block_html.append(_block_open('cashflow')+_cf+'</section>')
            elif block == "process":
                block_html.append(_block_open('process')+_process_suite_html(process_extras, tab.get("process_views", []), tab.get("tab_id", str(i)), tab.get("process_sizes", {}))+'</section>')
            elif block == "kanban":
                block_html.append(_block_open('kanban')+_kanban_board_html(process_extras, tab.get("kanban_mode", "due_window"), tab.get("kanban_card_fields", []))+'</section>')
            elif block == "quality":
                block_html.append(_block_open('quality')+_quality_block_html(df, cols, labels)+'</section>')
            elif block == "table" and show_tables:
                table = C.panel(
                    f'<div class="tablewrap"><table><caption class="sr-only">{html.escape(tab["title"])}</caption><thead><tr>{head}</tr></thead>'
                    f'<tbody id="tb_{i}"></tbody></table></div><div class="pager no-print" id="pager_{i}"></div>',
                    title=tab["title"],
                    aside=f'<span class="note" id="cnt_{i}" role="status" aria-live="polite"></span>',
                    section="table")
                block_html.append(_block_open('table')+table+'</section>')
        panes.append(
            f'<section id="{tab["id"]}" class="pane stack stack-md" role="tabpanel" aria-labelledby="tab_{i}"{hidden}>'
            f'{toolbar}{"".join(block_html)}</section>')
        metas.append({"id": tab["id"], "tab_id": tab.get("tab_id"),
                      "fields": cols, "max_rows": tab["max_rows"],
                      "grain": grain_of, "agg": measures, "title": tab["title"],
                      "blocks": list(tab.get("blocks", [])),
                      "block_sizes": dict(tab.get("block_sizes") or {}),
                      "charts": list(tab.get("charts", [])),
                      "chart_sizes": dict(tab.get("chart_sizes") or {}),
                      "process_views": list(tab.get("process_views", [])),
                      "process_sizes": dict(tab.get("process_sizes") or {}),
                      "kanban_mode": tab.get("kanban_mode", "due_window")})

    # Keep unsupported expert identities visible as warnings, outside the
    # operational material count. An empty operational view is never silent.
    material_gap_html = ""
    if include_material_view and any(c in df for c in ("MOGH_MATERIAL", "MOGH_MFR_PART_NO")):
        from ..report.supply_views import _s, _expert_advisory, _ntsw_advisory
        missing = _s(df, "ORC_PART_NO").eq("")
        gaps = df.loc[missing].copy().reset_index(drop=True)
        if not gaps.empty:
            ea, ec = _expert_advisory(gaps)
            na, nc = _ntsw_advisory(gaps)
            alerts = pd.DataFrame({
                "متریال اعلامی (تأیید نشده)": _s(gaps, "KEY_MATERIAL"),
                "هشدار کارشناسان": ea + " ؛ ⚠ مرجع مستقل متریال موجود نیست",
                "کامنت کارشناسان": ec, "هشدار NTSW": na, "کامنت NTSW": nc,
            }).drop_duplicates()
            material_gap_html = ('<details><summary>هشدارهای فاقد مرجع مستقل — خارج از شمارش عملیاتی</summary>'
                                 + '<div class="tablewrap">' + alerts.to_html(index=False, escape=True, classes="advisory-gaps") + '</div></details>')
    # ONE dedicated material tab, including its explicit empty state.
    if not material_view.empty or material_gap_html:
        mi = len(metas)
        mid = "pane_supply_material"
        mcols = list(material_view.columns)
        mhead = "".join(f'<th scope="col">{html.escape(str(c))}</th>' for c in mcols)
        mf = []
        preferred = ["متریال", "شرح متریال", "هشدار کارشناسان", "هشدار NTSW", "موقعیت فعلی", "معطل حوزه", "مرحله فعلی"]
        for j, c in enumerate([x for x in preferred if x in material_view.columns][:5]):
            vals = sorted({str(x) for x in material_view[c].tolist() if str(x).strip()})
            if c in ("متریال", "شرح متریال") or len(vals) > 40:
                mf.append(f'<label for="mf_{j}">{html.escape(c)}<input id="mf_{j}" type="search" data-f="{html.escape(c)}" data-filter-mode="contains" data-pane="{mid}" placeholder="جستجو در {html.escape(c)}"></label>')
            elif 1 < len(vals) <= 40:
                opts = '<option value="">همه</option>' + ''.join(f'<option>{html.escape(v)}</option>' for v in vals)
                mf.append(f'<label for="mf_{j}">{html.escape(c)}<select id="mf_{j}" data-f="{html.escape(c)}" data-filter-mode="exact" data-pane="{mid}">{opts}</select></label>')
        mtoolbar = '<div class="toolbar cluster cluster-sm no-print">' + ''.join(mf) + '<div class="cluster cluster-xs hug">' + C.button("استخراج داده فیلترشده (Excel)", variant="secondary", icon="⬇", onclick="downloadFilteredXlsx()", attrs='data-role="export"') + '</div></div>'
        mtable = C.panel(
            f'<div class="tablewrap material-table"><table><caption class="sr-only">دید تأمین — متریال محور</caption><thead><tr>{mhead}</tr></thead><tbody id="tb_{mi}"></tbody></table></div><div class="material-mobile" id="mc_{mi}"></div><div class="pager no-print" id="pager_{mi}"></div>',
            title="دید تأمین — متریال محور",
            note="کارشناسان و NTSW فقط Advisory: هشدار و کامنت. اتصال متریال به سفارش/بارنامه بدون شاهد مستقل، تأیید نشده است. شمارش این نما مربوط به متریال‌های دارای مرجع مستقل در داده انتخاب‌شده است.",
            aside=f'<span class="note" id="cnt_{mi}" role="status" aria-live="polite"></span>',
            section="table")
        panes.append(f'<section id="{mid}" class="pane stack stack-md" role="tabpanel" aria-labelledby="tab_{mi}" hidden>{mtoolbar}{material_gap_html}<section data-composer-block="table">{mtable}</section></section>')
        metas.append({"id": mid, "tab_id": "supply_material", "fields": mcols,
                      "max_rows": int(max_rows), "grain": {}, "agg": {},
                      "title": "دید تأمین — متریال محور", "blocks": ["table"],
                      "charts": [], "process_views": [], "kanban_mode": "due_window",
                      "data_source": "material_supply"})
        buttons += (f'<button class="tabbtn" type="button" role="tab" id="tab_{mi}" '
                    f'aria-selected="false" aria-controls="{mid}" data-pane="{mid}">'
                    'دید تأمین — متریال محور</button>')

    # ── نمودارها و لاگ فرآیند ──
    chart_keys = (list(dict.fromkeys(k for t in norm_tabs for k in t.get("charts", [])))
                  if show_visuals else [])
    # Old callers may still pass a global chart list; it is used only when a
    # migrated tab has no explicit chart selection.
    if show_visuals and not chart_keys:
        chart_keys = list(charts or [])
    try:
        from .designs import CHART_QUESTIONS, EMAIL_CHARTS
        chart_labels = {k: EMAIL_CHARTS.get(k, k) for k in chart_keys}
        chart_questions = {k: CHART_QUESTIONS.get(k, "") for k in chart_keys}
    except Exception:
        chart_labels = {k: k for k in chart_keys}
        chart_questions = {k: "" for k in chart_keys}
    proc_payload = {}
    # V28.5 compact runtime payload.  Process/Kanban views are rendered server-side
    # into the owning tab, so re-embedding eventlog/case_actions/FX ledgers in JS
    # duplicates the same information and can add several megabytes.  Only the
    # small datasets still consumed by browser-side Story or a process-backed
    # chart are shipped at runtime.
    need_story_runtime = any("story" in t.get("blocks", []) for t in norm_tabs)
    need_bottleneck_runtime = "bottlenecks" in chart_keys
    runtime_keys = set()
    if need_story_runtime:
        runtime_keys.update({"stage_queue", "bottlenecks", "fx_control_summary",
                             "warehouse_declaration"})
    if need_bottleneck_runtime:
        runtime_keys.add("bottlenecks")
    # Compact compatibility for FX Traceability: keep a capped ledger only
    # when the caller actually supplied it. This preserves drill-down without
    # reintroducing the multi-MB payload regression fixed in V28.5.
    if isinstance((process_extras or {}).get("fx_ledger"), pd.DataFrame) and not (process_extras or {}).get("fx_ledger").empty:
        runtime_keys.add("fx_ledger")

    runtime_columns = {
        "stage_queue": ["مرحله جاری", "تعداد پرونده", "میانه انتظار (روز)", "بیشترین انتظار (روز)"],
        "bottlenecks": ["از فعالیت", "به فعالیت", "میانه روز", "صدک ۹۰ روز", "تعداد پرونده"],
        "fx_control_summary": ["KEY_REG", "FX_DEADLINE_STATUS", "FX_UNAUTHORIZED_REALLOCATION_COUNT",
                               "FX_CONTROL_RISK_BAND", "FX_CONTROL_RISK_SCORE", "FX_CURRENT_STAGE",
                               "FX_DEADLINE_DATE", "FX_DAYS_REMAINING", "FX_CONVERSION_STATUS",
                               "FX_CONVERSION_IMPACT_RIAL"],
        "warehouse_declaration": ["CANONICAL_BL", "WH_STATUS", "WH_STATUS_FA", "WH_CLEAR_DATE",
                                  "WH_RECEIPT_DATE", "WH_LAG_DAYS", "WH_AGE_DAYS", "WH_CLEAR_BASIS"],
        "fx_ledger": ["KEY_REG", "FX_MONEY_STAGE", "FX_PURCHASED_NATIVE_DISPLAY",
                      "FX_EUR_EQUIVALENT", "FX_RIAL_OUTFLOW_REPORTED",
                      "FX_NTSW_BALANCE", "FX_NTSW_CURRENCY", "FX_NTSW_BALANCE_EUR_EQ",
                      "FX_NTSW_BALANCE_RIAL_EQ", "FX_NTSW_EUR_EQ_BASIS", "FX_NTSW_RIAL_EQ_BASIS",
                      "FX_TRACE_SCORE", "FX_ANOMALY_COUNT", "FX_CONTROL_RISK_SCORE", "FX_CURRENT_STAGE",
                      "FX_DEADLINE_DATE", "FX_DAYS_REMAINING", "FX_CONVERSION_IMPACT_RIAL",
                      "FX_UNAUTHORIZED_REALLOCATION_COUNT"],
    }
    for key in sorted(runtime_keys):
        t = (process_extras or {}).get(key)
        if isinstance(t, pd.DataFrame) and not t.empty:
            keep = [c for c in runtime_columns.get(key, []) if c in t.columns]
            x = t[keep].copy() if keep else t.iloc[:, :0].copy()
            if key == "fx_ledger" and len(x) > 250:
                # سقف نمایشی دفتر ارزی. حذف بی‌اعلام ممنوع است: در مانیفست پوشش ثبت می‌شود.
                coverage_truncations.append({"section": key, "source_rows": int(len(x)),
                                             "embedded_rows": 250})
                x = x.head(250).copy()
            if x.empty and len(t):
                continue
            for c in x.columns:
                if pd.api.types.is_datetime64_any_dtype(x[c]):
                    x[c] = x[c].dt.strftime("%Y-%m-%d %H:%M:%S")
            proc_payload[key] = x.astype("object").where(x.notna(), "").to_dict(orient="records")


    chart_json = _inline_json({"keys": chart_keys, "labels": chart_labels,
                               "questions": chart_questions})
    proc_json = _inline_json(proc_payload, default=str)
    series_json = _inline_json(list(T.CATEGORICAL))
    band_fill_json = _inline_json({s.label: s.fill for s in T.STATUS_SCALE})
    band_ink_json = _inline_json(BAND_INK)

    runtime = _runtime(chart_json, proc_json, series_json, band_fill_json, band_ink_json)

    # ── بخش «فهرست محتوای این خروجی» ──
    # این بخش چاپ می‌شود و پشت تب پنهان نیست: تصمیم‌گیرنده باید بدون باز کردن
    # کد منبع بداند این فایل چه چیزی دارد و چه چیزی ندارد.
    _cov_rows = [
        ("ردیف در این خروجی", f"{len(data):,} از {len(df):,}"),
        ("ستون در این خروجی", f"{len(_payload_columns):,} از {len(_source_columns):,}"),
        ("نمای تأمین متریال", f"{len(material_view):,} ردیف"),
        ("تاریخ مرجع", str(ref_date)),
    ]
    _cov_cells = "".join(
        f'<div class="kpi"><div class="l">{html.escape(k)}</div><b>{html.escape(v)}</b></div>'
        for k, v in _cov_rows)
    _trunc_html = ""
    if coverage_truncations:
        _items = "".join(
            f'<li>{html.escape(str(t["section"]))}: '
            f'{int(t["embedded_rows"]):,} از {int(t["source_rows"]):,} ردیف در فایل است</li>'
            for t in coverage_truncations)
        _trunc_html = ('<p class="note" style="color:var(--warn-ink,#8a5a12)">'
                       'بخش‌های زیر سقف نمایشی دارند و کامل در فایل نیستند:</p>'
                       f'<ul class="note">{_items}</ul>')
    _excl_html = ""
    if excluded_columns:
        _chips = "".join(f'<code class="cov-col">{html.escape(c)}</code>' for c in excluded_columns)
        _excl_html = (
            f'<details class="stack stack-xs"><summary class="t-overline">'
            f'{len(excluded_columns):,} ستون در این خروجی نیست — فهرست کامل</summary>'
            f'<p class="note">این ستون‌ها در انبار داده موجودند ولی در تب‌های این artifact '
            f'انتخاب نشده‌اند. نبودِ یک ستون در اینجا به معنای نبودِ داده در سامانه نیست.</p>'
            f'<div class="cluster cluster-xs" style="max-height:240px;overflow:auto">{_chips}</div>'
            f'</details>')
    coverage_html = (
        '<section id="gsi_manifest" class="card stack stack-sm" data-section="coverage" '
        'aria-labelledby="gsi_manifest_h">'
        '<style>#gsi_manifest .cov-col{display:inline-block;margin:2px;padding:2px 7px;'
        'border:1px solid var(--border,#dbe3e7);border-radius:6px;background:var(--surface,#f7f9fa);'
        'font:11px/1.7 ui-monospace,Consolas,monospace;direction:ltr;unicode-bidi:plaintext}'
        '#gsi_manifest summary{cursor:pointer}</style>'
        '<div class="t-overline">◈ فهرست محتوای این خروجی</div>'
        '<h2 class="t-h2" id="gsi_manifest_h" style="margin:2px 0 6px">چه چیزی در این فایل هست و چه چیزی نیست</h2>'
        '<p class="note">ردیف‌ها کامل‌اند؛ جدول‌ها فقط تعداد محدودی را هم‌زمان نشان می‌دهند و '
        'خروجی Excel همان ستون‌های تب فعال را برای همه ردیف‌های فیلترشده می‌دهد.</p>'
        f'<div class="grid-auto" style="--col:200px">{_cov_cells}</div>'
        f'{_trunc_html}{_excl_html}</section>')

    lesson_html = ""
    embed_script = ""
    chat_href = ""
    static_chat = False
    if isinstance(knowledge_chat, dict):
        chat_href = str(knowledge_chat.get("chatbot_href") or "").strip()
        static_chat = bool(chat_href)

    # Legacy AnythingLLM remains readable for old saved designs, but V29.3
    # defaults to the zero-server static Shared-Folder chatbot.
    legacy_embed = (not static_chat and isinstance(anythingllm_embed, dict)
                    and anythingllm_embed.get("base_url") and anythingllm_embed.get("embed_id"))
    if legacy_embed:
        base = str(anythingllm_embed.get("base_url")).rstrip("/")
        embed_id = html.escape(str(anythingllm_embed.get("embed_id")), quote=True)
        api = html.escape(base + "/api/embed", quote=True)
        src = html.escape(base + "/embed/anythingllm-chat-widget.min.js", quote=True)
        embed_script = f'<script data-embed-id="{embed_id}" data-base-api-url="{api}" src="{src}"></script>'

    has_content = isinstance(learning_lesson, dict) and bool(learning_lesson)
    lt = html.escape(str((learning_lesson or {}).get("title") or "دستیار دانش بازرگانی GSI"))
    ls = html.escape(str((learning_lesson or {}).get("summary") or ""))
    lb = html.escape(str((learning_lesson or {}).get("body") or "")).replace("\n", "<br>")
    qs = (learning_lesson or {}).get("questions") or []
    qhtml = "".join(
        '<button class="lesson-q no-print" type="button" data-q="%s" onclick="openGsiChat(this.dataset.q)">%s</button>'
        % (html.escape(str(q), quote=True), html.escape(str(q))) for q in qs[:6]
    )
    if static_chat:
        safe_href = html.escape(chat_href, quote=True)
        ask_note = "دستیار کاملاً آفلاین است و از فایل‌های Shared Folder ساخته شده؛ هیچ سرویس شبکه‌ای لازم نیست."
        chat_box = (f'<div class="gsi-chat no-print" data-chat-href="{safe_href}">'
                    '<div class="gsi-chat-row"><textarea id="gsi_chat_q" placeholder="سؤال بازرگانی خود را بنویسید…"></textarea>'
                    '<button type="button" onclick="askGsiKnowledge()">پرسیدن</button></div>'
                    f'<a class="gsi-chat-link" target="_blank" rel="noopener" href="{safe_href}">باز کردن چت‌بات آفلاین ↗</a></div>')
    elif legacy_embed:
        ask_note = "برای پرسیدن سؤال، ویجت چت پایین صفحه را باز کنید."
        chat_box = ""
    else:
        ask_note = "چت‌بات در این فایل هنوز فعال نیست؛ از محیط دستیار دانش آن را ایجاد کنید."
        chat_box = ""

    # Chat is independent from optional curated content. Previously the whole
    # block was hidden unless a lesson file existed, which made a valid static
    # chatbot disappear from report HTML.
    if static_chat or legacy_embed or has_content:
        content_html = ""
        if has_content:
            content_html = (f'<h2>{lt}</h2>'
                            f'<p class="learning-summary">{ls}</p>'
                            f'<div class="learning-body">{lb}</div>'
                            f'<div class="learning-qs">{qhtml}</div>')
        else:
            content_html = '<h2>دستیار دانش بازرگانی GSI</h2><p class="learning-summary">سؤال خود را از پایگاه دانش داخلی بپرسید.</p>'
        lesson_html = (f'<section class="learning-panel reveal" id="gsi_learning">'
                       f'<div class="learning-kicker">💬 چت‌بات</div>{content_html}'
                       f'<p class="note">{html.escape(ask_note)}</p>{chat_box}</section>')

    return f"""<!doctype html><html lang="fa" dir="rtl"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>{html.escape(title)}</title>
<style>{CSS.stylesheet()}
{HC.CSS}
.learning-panel{{background:linear-gradient(135deg,var(--raised,#fff),rgba(10,124,134,.055));border:1px solid var(--border,#dbe3e7);border-radius:16px;padding:22px;box-shadow:0 8px 24px rgba(11,31,51,.06)}}
.learning-kicker{{font-size:12px;font-weight:800;color:var(--brand,#0a7c86);letter-spacing:.02em}}
.learning-panel h2{{margin:6px 0 8px;color:var(--text,#0b1f33)}}
.learning-summary{{color:var(--text-2,#3d5163);font-weight:600}}
.learning-body{{line-height:2;color:var(--text,#0b1f33);max-width:1000px}}
.learning-qs{{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}}
.lesson-q{{border:1px solid var(--border,#dbe3e7);background:var(--raised,#fff);color:var(--brand-deep,#0b1f33);border-radius:999px;padding:8px 12px;cursor:pointer;font:inherit}}
.lesson-q:hover{{border-color:var(--brand,#0a7c86)}}
.gsi-chat{{margin-top:16px;border-top:1px solid var(--border,#dbe3e7);padding-top:14px}}
.gsi-chat-log{{max-height:280px;overflow:auto;background:#f7f9fa;border-radius:12px;padding:10px}}
.gsi-user,.gsi-bot{{margin:7px 0;padding:9px 11px;border-radius:10px;line-height:1.8;white-space:pre-wrap}}
.gsi-user{{background:#e7f4f3;margin-right:12%}} .gsi-bot{{background:white;border:1px solid var(--border,#dbe3e7);margin-left:12%}}
.gsi-chat-row{{display:flex;gap:8px;margin-top:8px}} .gsi-chat-row textarea{{flex:1;min-height:58px;border:1px solid var(--border,#dbe3e7);border-radius:10px;padding:9px;font:inherit}}
.gsi-chat-row button{{border:0;background:var(--brand,#0a7c86);color:white;border-radius:10px;padding:0 18px;font:inherit;font-weight:700}} .gsi-chat-link{{display:inline-block;margin-top:8px;font-size:12px;color:var(--brand,#0a7c86)}}
</style>
</head><body>
{C.skip_link()}
<div class="shell stack stack-md">
{header}
{persona_html}
<div class="cluster cluster-sm">{flow_html}</div>
{legend_html}
<nav class="tabbar no-print" role="tablist" aria-label="تب‌های گزارش">{buttons}</nav>
<div class="toolbar split no-print">
  <label for="q" class="grow" style="max-width:460px">جستجوی سراسری تب فعال
    <input id="q" type="search" placeholder="جستجو در فیلدهای همان تب"
           aria-describedby="q_hint"></label>
  <span id="q_hint" class="sr-only">نتیجه بلافاصله روی سنجه‌ها، نمودارها و جدول اعمال می‌شود.</span>
  <div class="cluster cluster-xs hug">
  {C.button("استخراج داده فیلترشده (Excel)", variant="decision", icon="⬇", onclick="downloadFilteredXlsx()")}
  {C.button("PDF / چاپ", variant="secondary", icon="🖨", onclick="exportPdf()")}
  <button class="btn btn--secondary" type="button" data-gsi-custom-action="toggle" aria-pressed="false">✥ شخصی‌سازی HTML</button>
  </div>
</div>
{HC.TOOLBAR_HTML}
<main id="main" class="stack stack-md">
<span id="story" hidden></span><span id="story_scr" hidden></span><span id="process_variants" hidden></span><span id="process_roots" hidden></span>
{''.join(panes)}
{lesson_html}
{coverage_html}
</main>
<footer class="note" style="padding:8px 0 0">
<span id="aud_closing"></span>
GSI · Global Sourcing Intelligence · AUTOMOTIVE SUPPLY CHAIN · <strong>Build {html.escape(GSI_RUNTIME_VERSION)}</strong> — هسته گزارش خودبسنده است؛ دستیار دانش در حالت آفلاین Shared-Folder-only اجرا می‌شود.
</footer>
</div>
{HC.SEED_HTML}
<script>
const DATA={records};
const MATERIAL_SUPPLY_DATA={material_records};
const COL_INDEX={_inline_json({c:i for i,c in enumerate(all_needed)})};
const PAGE_SIZE=100; /* compatibility/default; audience profile may override at render time */
const REPORT_META={_inline_json({**(lineage or {}), "payload_rows": len(df), "embedded_rows": len(data), "payload_encoding": "row_array_v1", "material_supply_embedded_rows": len(material_view), "ref_date": ref_date, "gsi_build": GSI_RUNTIME_VERSION, "source_columns": len(_source_columns), "payload_columns": len(_payload_columns), "excluded_columns": excluded_columns, "truncated_sections": coverage_truncations})};
const TAB_META={_inline_json(metas)};
const LABELS={_inline_json({c: labels.get(c, c) for c in all_needed})};
const AUDIENCES={aud_json};
let AUD={_inline_json(aud.key)};
</script>
{runtime}
<script>{HC.JS}</script>
<script>
function openGsiChat(q){{const box=document.querySelector('.gsi-chat');if(!box)return;const e=document.getElementById('gsi_chat_q');if(e)e.value=q;box.scrollIntoView({{behavior:'smooth'}});}}
function askGsiKnowledge(){{const box=document.querySelector('.gsi-chat'),e=document.getElementById('gsi_chat_q');if(!box||!e)return;const q=e.value.trim();if(!q)return;const href=box.dataset.chatHref;if(!href)return;window.open(href+(href.includes('?')?'&':'?')+'q='+encodeURIComponent(q),'_blank','noopener');}}
</script>
{embed_script}
</body></html>"""


def _runtime(chart_json: str, proc_json: str, series_json: str,
             band_fill_json: str, band_ink_json: str) -> str:
    """تنها بلوک اجرایی صفحه.

    همه توابع اینجا یک‌بار تعریف می‌شوند. هر تعریف دوباره در scope سراسری،
    مرورگر را با ``Identifier ... has already been declared`` متوقف می‌کند و
    گزارش را خالی بالا می‌آورد؛ تست ۲۱ دقیقاً همین را می‌سنجد.
    """
    charts_lib = CJ.chart_runtime(series_json, band_fill_json, band_ink_json)
    body = r"""
const CHART_CFG=__CHART_CFG__; const PROC=__PROC__;
__CHARTS_LIB__
__REVEAL_JS__

let active=Math.max(0,TAB_META.findIndex(t=>t.data_source==='material_supply'));
const PAGE={};
function exportPdf(){window.print()}
/* اندازه صفحه از پروفایل مخاطب می‌آید: مدیر ارشد ۱۰ ردیف
   می‌بیند و کارشناس ۲۰۰ — همان جدول، دو نیاز متفاوت. */
function pageSize(){return audCfg().table_rows||100}
const q=document.getElementById('q');
function S(r,c){
 if(Array.isArray(r)){const i=COL_INDEX[c];return String(i===undefined?'':(r[i]??''))}
 return String(r?.[c]??'')}
function N(r,c){const v=parseFloat(S(r,c));return Number.isFinite(v)?v:null}

/* ── فیلتر: تنها نقطه‌ای که «برش فعال» تعریف می‌شود ── */
function searchText(v){return String(v??'').toLowerCase().replace(/[۰-۹]/g,c=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c)))
 .replace(/[٠-٩]/g,c=>String('٠١٢٣٤٥٦٧٨٩'.indexOf(c))).replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/[\u200c\u200e\u200f]/g,'').trim()}
function rows(t){
 let a=(t&&t.data_source==='material_supply')?MATERIAL_SUPPLY_DATA:DATA;
 const n=searchText(q&&q.value?q.value:'');
 if(n)a=a.filter(r=>t.fields.some(c=>searchText(S(r,c)).includes(n)));
 document.querySelectorAll('[data-f][data-pane="'+t.id+'"]').forEach(s=>{
  const v=(s.value||'').trim();if(!v)return;
  if(s.dataset.filterMode==='contains'){const n=searchText(v);
   a=a.filter(r=>searchText(S(r,s.dataset.f)).includes(n))}
  else a=a.filter(r=>S(r,s.dataset.f)===v)});
 return a}

/* ── تجمیع دانه‌ای: بدون این، فیلتر کردن جمع‌ها را چند برابر می‌کند ── */
function gvals(a,c,grain){const k=grain[c],seen=new Set(),out=[];
 for(const r of a){if(k){const key=S(r,k).trim();if(key){if(seen.has(key))continue;seen.add(key)}}
 const v=parseFloat(S(r,c));if(Number.isFinite(v))out.push(v)}return out}
function gagg(a,c,grain,agg){const v=gvals(a,c,grain);if(!v.length)return 0;
 if(agg[c]==='mean')return v.reduce((s,x)=>s+x,0)/v.length;
 return v.reduce((s,x)=>s+x,0)}

function countBy(a,fields){const m={};a.forEach(r=>{let v='';
 for(const f of fields){v=S(r,f).trim();if(v)break}v=v||'نامشخص';m[v]=(m[v]||0)+1});
 return Object.entries(m).map(([k,v])=>({k,v}))}
function topCount(a,fields){return countBy(a,fields).sort((x,y)=>y.v-x.v).slice(0,12)}
function bandRows(a,fields){return countBy(a,fields).map(x=>({k:x.k,v:x.v,
 c:GSI_BAND_FILL[x.k]||null,ink:GSI_BAND_INK[x.k]||null}))}
function sumUnique(a,valCol,keyFields){const seen=new Set();let sum=0;
 for(const r of a){let key='';for(const f of keyFields){key=S(r,f).trim();if(key)break}
 if(key){if(seen.has(key))continue;seen.add(key)}
 const v=parseFloat(S(r,valCol));if(Number.isFinite(v))sum+=v}return sum}
function stageRows(a){return topCount(a,['STAGE_FA','ORDER_STAGE_FA','LIFECYCLE_STAGE'])}

/* ── انتخاب نمودار ── */
function chartFor(k,a,i){
 const title=CHART_CFG.labels[k]||k,o={q:(CHART_CFG.questions||{})[k]||'',i:i};
 if(k==='low_resistance')return barChart(a.map(r=>({k:S(r,'KEY_MATERIAL'),
   v:parseFloat(S(r,'مقاومت (روز)'))})),title,Object.assign({fill:'var(--st-critical)',
   ink:'var(--st-critical-ink)'},o));
 if(k==='criticality')return donutChart(bandRows(a,['بحرانی (کوتاه)','کد طبقه بحرانی']),title,o);
 if(k==='risk_mix')return donutChart(countBy(a,['طبقه ریسک']),title,o);
 if(k==='org_workload')return barChart(topCount(a,['ORG_DEPT','ORG_VICE']),title,o);
 if(k==='expert_workload')return barChart(topCount(a,['CANONICAL_EXPERT']),title,o);
 if(k==='transport_mix')return donutChart(countBy(a,['TRANSPORT_MODE']),title,o);
 if(k==='stage_distribution')return barChart(stageRows(a),title,o);
 if(k==='top_orders')return barChart(topCount(a,['CANONICAL_ORDER','KEY_ORDER']),title,o);
 if(k==='top_bl')return barChart(topCount(a,['CANONICAL_BL','KEY_BL']),title,o);
 if(k==='supplier_mix')return barChart(topCount(a,['SUPPLIER','VENDOR_CODE']),title,o);
 if(k==='sediment_vs_resistance'||k==='stock_vs_total'){
  const pts=[];for(const r of a){const x=N(r,'روزهای رسوب'),y=N(r,'مقاومت (روز)');
   if(x===null||y===null)continue;pts.push({x,y,k:S(r,'KEY_MATERIAL'),b:S(r,'بحرانی (کوتاه)')})}
  return scatterChart(pts,title,Object.assign({xlabel:'روزهای رسوب',ylabel:'مقاومت (روز)',
   quad:'رسوب بالا و مقاومت بالا'},o))}
 if(k==='delay_vs_commitment'){
  const pts=[];for(const r of a){const x=N(r,'روزهای تأخیر'),y=N(r,'FX_NTSW_BALANCE_EUR_EQ');
   if(x===null||y===null)continue;pts.push({x,y,k:S(r,'CANONICAL_ORDER'),b:S(r,'بحرانی (کوتاه)')})}
  return scatterChart(pts,title,Object.assign({xlabel:'روزهای تأخیر',ylabel:'مانده تعهد — معادل EUR',
   quad:'تأخیر و معادل یورویی، هر دو بالا'},o))}
 if(k==='pareto_delay'){const m={};for(const r of a){const d=N(r,'روزهای تأخیر');
   if(d===null||d<=0)continue;const key=S(r,'CANONICAL_ORDER').trim()||S(r,'KEY_REG').trim();
   if(!key)continue;m[key]=Math.max(m[key]||0,d)}
  return paretoChart(Object.entries(m).map(([k2,v])=>({k:k2,v})),title,o)}
 if(k==='commitment'){
  const eligible=a.filter(r=>N(r,'FX_NTSW_BALANCE_EUR_EQ')!==null);
  const over=eligible.filter(r=>(parseFloat(S(r,'روزهای تأخیر'))||0)>0);
  const open=eligible.filter(r=>(parseFloat(S(r,'روزهای تأخیر'))||0)<=0&&(parseFloat(S(r,'مانده تعهد'))||0)>0);
  const done=eligible.filter(r=>(parseFloat(S(r,'مانده تعهد'))||0)<=0);
  return barChart([
   {k:'معوق',v:sumUnique(over,'FX_NTSW_BALANCE_EUR_EQ',['KEY_REG','CANONICAL_ORDER']),
    c:'var(--st-critical)',ink:'var(--st-critical-ink)'},
   {k:'در مهلت',v:sumUnique(open,'FX_NTSW_BALANCE_EUR_EQ',['KEY_REG','CANONICAL_ORDER']),
    c:'var(--st-warning)',ink:'var(--st-warning-ink)'},
   {k:'تسویه‌شده',v:sumUnique(done,'FX_NTSW_BALANCE_EUR_EQ',['KEY_REG','CANONICAL_ORDER']),
    c:'var(--st-good)',ink:'var(--st-good-ink)'}],title+' — معادل EUR',o)}
 if(k==='overdue_bucket'){const bins={'بدون تأخیر':0,'۱ تا ۷ روز':0,'۸ تا ۳۰ روز':0,
   '۳۱ تا ۶۰ روز':0,'بیش از ۶۰ روز':0};
  a.forEach(r=>{const d=parseFloat(S(r,'روزهای تأخیر'));
   if(!Number.isFinite(d)||d<=0)bins['بدون تأخیر']++;else if(d<=7)bins['۱ تا ۷ روز']++;
   else if(d<=30)bins['۸ تا ۳۰ روز']++;else if(d<=60)bins['۳۱ تا ۶۰ روز']++;
   else bins['بیش از ۶۰ روز']++});
  return barChart(Object.entries(bins).map(([k2,v])=>({k:k2,v})),title,o)}
 if(k==='bottlenecks'){const b=PROC.bottlenecks||[];
  if(b.length)return barChart(b.slice(0,10).map(x=>({k:S(x,'از فعالیت')+' ← '+S(x,'به فعالیت'),
   v:+x['میانه روز']||0})),title,Object.assign({fill:'var(--st-serious)',
   ink:'var(--st-serious-ink)'},o));
  return barChart(stageRows(a),title+' — جایگزین: توزیع مرحله فعلی',o)}
 return frame(title,emptyBox('فیلد لازم برای این نمودار در برش فعلی وجود ندارد.'),'','',i)}

/* نمودار هم مخاطب دارد: مدیر ارشد یک نمودار می‌بیند و تحلیل‌گر شش تا.
   نمودارِ بی‌ربط، بی‌ضرر نیست — جای نمودار مربوط را می‌گیرد و خواننده را
   وامی‌دارد خودش فیلتر کند. اگر پروفایل نموداری نخواسته، هیچ‌کدام از
   نمودارهای موجود حذف نمی‌شود؛ فقط همان‌هایی می‌مانند که خواسته شده‌اند. */
function chartsFor(t){
 /* Each tab owns its chart selection. Global CHART_CFG.keys exists only as a
    backward-compatibility fallback for old saved designs. */
 return (t&&Array.isArray(t.charts)&&t.charts.length)?t.charts:(CHART_CFG.keys||[]);
}
function renderCharts(i,a){const e=document.getElementById('charts_'+i),t=TAB_META[i];
 if(!e)return;const sizes=(t&&t.chart_sizes)||{};e.innerHTML=chartsFor(t).map((k,j)=>'<div class="gsi-chart-item" data-gsi-item-key="chart:'+esc2(k)+'" data-gsi-chart="'+esc2(k)+'" data-gsi-size="'+esc2(sizes[k]||'half')+'">'+chartFor(k,a,j)+'</div>').join('');
 gsiReveal(e)}

/* ── Process Explorer ── */
function processStats(a){
 const ev=PROC.eventlog||[];
 if(!ev.length)return {events:[],transitions:[],cases:0};
 const cases=new Set();
 for(const r of a){for(const k of ['CASE_KEY','_CASE_KEY','KEY_REG']){const v=S(r,k).trim();if(v){cases.add(v);break}}}
 const scoped=cases.size?ev.filter(e=>cases.has(S(e,'_CASE_KEY').trim())||cases.has(S(e,'CASE_KEY').trim())):ev;
 const by={};for(const e of scoped){const k=S(e,'_CASE_KEY').trim()||S(e,'CASE_KEY').trim();if(!k)continue;(by[k]||(by[k]=[])).push(e)}
 const waits={};
 for(const arr of Object.values(by)){arr.sort((x,y)=>String(x.EVENTTIME||'').localeCompare(String(y.EVENTTIME||'')));
  for(let i=0;i<arr.length-1;i++){const x=arr[i],y=arr[i+1],f=S(x,'ACTIVITY_FA'),t=S(y,'ACTIVITY_FA');if(!f||!t||f===t)continue;
   const d=(Date.parse(y.EVENTTIME)-Date.parse(x.EVENTTIME))/86400000;if(!Number.isFinite(d)||d<0)continue;
   const k=f+'\u001f'+t;(waits[k]||(waits[k]=[])).push(d)}}
 const transitions=Object.entries(waits).map(([k,v])=>{v.sort((a,b)=>a-b);const q=p=>v[Math.min(v.length-1,Math.floor((v.length-1)*p))];const z=k.split('\u001f');return {'از فعالیت':z[0],'به فعالیت':z[1],'میانه روز':q(.5),'صدک ۹۰ روز':q(.9),'تعداد پرونده':v.length}}).sort((x,y)=>y['میانه روز']-x['میانه روز']);
 return {events:scoped,transitions,cases:Object.keys(by).length};
}
function renderProcess(a){
 const cfg=audCfg();
 const ps=processStats(a);
 const b=ps.transitions.length?ps.transitions:(PROC.bottlenecks||[]),v=PROC.variants||[],rc=PROC.conformance_root_causes||[];
 const q=PROC.stage_queue||[];

 /* صداقت دامنه: این جدول‌ها روی **کل** داده محاسبه شده‌اند، نه روی برش
    فیلترشده. محاسبه دوبارهٔ فرآیند در مرورگر یعنی دو منطق موازی که با هم
    فرق می‌کنند. پس به‌جای تظاهر، دامنه صریح اعلام می‌شود. */
 const scoped=(PROC.eventlog&&PROC.eventlog.length)
  ?'<span class="badge badge--quiet" data-tone="neutral">Event Log — همگام با فیلتر فعلی</span>'
  :((a.length&&DATA.length&&a.length<DATA.length)?'<span class="badge badge--quiet" data-tone="neutral">کل سازمان — مستقل از فیلتر فعلی</span>':'');

 /* صف جاری: چیزی که جدول گذار هرگز نشان نمی‌داد.
    گذار وقتی ثبت می‌شود که پرونده از مرحله خارج شده باشد؛ پرونده‌ای که
    هشت ماه گیر کرده و خارج نشده، در آن جدول هیچ ردیفی ندارد. */
 const map=document.getElementById('process_map');
 if(map){map.innerHTML=q.length?(barChart(q.slice(0,10).map(x=>({
   k:S(x,'مرحله جاری'),v:+x['تعداد پرونده']||0})),
   'صف جاری — چند پرونده در هر مرحله منتظرند',
   {q:'الان کجا پرونده جمع شده است؟'})+scoped)
  :(b.length?barChart(b.slice(0,10).map(x=>({
    k:S(x,'از فعالیت')+' ← '+S(x,'به فعالیت'),v:+x['میانه روز']||0})),
    'گذارهای مشاهده‌شده — میانه انتظار',{q:'کدام گذار بیشترین زمان را می‌خورد؟'})+scoped
   :(stageRows(a).length?barChart(stageRows(a),'توزیع مرحله فعلی',
    {q:'پرونده‌ها اکنون در کدام مرحله‌اند؟'})
    :emptyBox('لاگ تاریخی برای اندازه‌گیری هنوز کافی نیست. با اجرای روزانه، Transition Log ساخته می‌شود.')));
  gsiReveal(map)}

 const t=document.getElementById('process_bottlenecks');
 if(t){
  let html_='';
  if(q.length)html_+='<div class="tablewrap" style="margin-top:12px"><table>'
   +'<caption class="note">صف جاری: پرونده‌هایی که همین حالا در هر مرحله منتظرند. '
   +'«انتظار» زمان سپری‌شده از آخرین رویداد است، نه زمان کار.</caption>'
   +'<thead><tr><th scope="col">مرحله جاری</th><th scope="col">پرونده منتظر</th>'
   +'<th scope="col">میانه انتظار</th><th scope="col">بیشترین انتظار</th></tr></thead><tbody>'
   +q.slice(0,10).map(x=>'<tr><td>'+esc2(S(x,'مرحله جاری'))+'</td><td class="num">'
    +fmt(x['تعداد پرونده'])+'</td><td class="num">'+fmt(x['میانه انتظار (روز)'])
    +' روز</td><td class="num">'+fmt(x['بیشترین انتظار (روز)'])+' روز</td></tr>').join('')
   +'</tbody></table></div>';
  if(b.length&&cfg.depth>1)html_+='<div class="tablewrap" style="margin-top:12px"><table>'
   +'<caption class="note">گذارهای کامل‌شده. میانه و صدک ۹۰ گزارش می‌شوند چون '
   +'توزیع دُم‌دار است و میانگین با یک پرونده طولانی جابه‌جا می‌شود.</caption>'
   +'<thead><tr><th scope="col">از</th><th scope="col">به</th>'
   +'<th scope="col">میانه</th><th scope="col">صدک ۹۰</th>'
   +'<th scope="col">پرونده</th></tr></thead><tbody>'
   +b.slice(0,10).map(x=>'<tr><td>'+esc2(S(x,'از فعالیت'))+'</td><td>'+esc2(S(x,'به فعالیت'))
    +'</td><td class="num">'+fmt(x['میانه روز'])+' روز</td><td class="num">'
    +fmt(x['صدک ۹۰ روز'])+' روز</td><td class="num">'+fmt(x['تعداد پرونده'])
    +'</td></tr>').join('')+'</tbody></table></div>';
  t.innerHTML=html_||'<p class="note">تا زمانی که Event Log کافی شود، توزیع مرحله فعلی '
   +'به‌عنوان نمای جایگزین نمایش داده می‌شود و هیچ گلوگاه فرضی ساخته نمی‌شود.</p>';
 }

 const pv=document.getElementById('process_variants');
 if(pv)pv.innerHTML=(v.length&&cfg.sections.includes('variants'))?(
  '<h4 class="t-h4" style="margin-top:16px">مسیرهای مشاهده‌شده</h4>'
  /* نسخه قبلی اینجا می‌نوشت «سهم کم یعنی فرآیند هر بار از نو اجرا می‌شود».
     تنوع مسیر سه علت کاملاً متفاوت دارد و این جمله یکی را قطعی می‌گرفت. */
  +'<p class="note">تنوع مسیر به‌تنهایی خوب یا بد نیست: می‌تواند از تفاوت مشروع '
  +'خریدها (هوایی/دریایی، برات/دیداری)، از نقص داده، یا از بی‌انضباطی بیاید. '
  +'ستون «پرونده بسته» می‌گوید میانه بر چند نمونه بنا شده است.</p>'
  +'<div class="tablewrap"><table><thead><tr><th scope="col">مسیر</th>'
  +'<th scope="col">پرونده</th><th scope="col">سهم</th>'
  +'<th scope="col">پرونده بسته</th><th scope="col">میانه چرخه</th></tr></thead><tbody>'
  +v.slice(0,12).map(x=>'<tr><td style="white-space:normal;max-width:520px">'+esc2(S(x,'VARIANT'))
  +'</td><td class="num">'+fmt(x['تعداد پرونده'])+'</td><td class="num">'+fmt(x['سهم (٪)'])
  +'٪</td><td class="num">'+fmt(x['پرونده بسته'])+'</td><td class="num">'
  +(((+x['پرونده بسته']||0)>0)?(fmt(x['میانه چرخه'])+' روز'):'—')+'</td></tr>').join('')
  +'</tbody></table></div>'):'';

 const pr=document.getElementById('process_roots');
 /* «علت ریشه‌ای» نبود، همبستگی بود. نام و متن هر دو اصلاح شده‌اند. */
 if(pr)pr.innerHTML=(rc.length&&cfg.depth>2)?(
  '<h4 class="t-h4" style="margin-top:16px">عوامل همراه با انحراف — نیازمند بررسی</h4>'
  +'<p class="note">این نمودار همبستگی نشان می‌دهد، نه علت. گروهی که پرونده‌های '
  +'دشوارتری به آن سپرده شده هم اینجا بالا می‌آید؛ پیش از هر اقدامی، ترکیب '
  +'پرونده‌های گروه بررسی شود.</p>'
  +barChart(rc.slice(0,8).map(x=>({k:S(x,'بُعد')+': '+S(x,'مقدار'),
    v:+x['اثر تفاضلی (واحد درصد)']||0})),
   'اختلاف نرخ انحراف نسبت به پایه (واحد درصد)',
   {q:'کدام گروه‌ها نرخ انحراف بالاتری دارند؟'})):'';
 renderFx();
 renderWarehouse();
}

/* ── اظهار انبار / سامانه جامع انبارها ──
   آخرین حلقه زنجیره شاهد: کالا ترخیص شد، ولی به انبار رسید؟
   عمداً «تخلف» نمی‌گوید — مهلت قانونی needs_verification است. */
function renderWarehouse(){
 const el=document.getElementById('process_wh');if(!el)return;
 const wh=PROC.warehouse_declaration||[];
 if(!wh.length){el.innerHTML='';return}
 const by=k=>wh.filter(x=>S(x,'WH_STATUS')===k).length;
 const gap=by('OVERDUE')+by('CRITICAL_GAP');
 const cards=[['اظهار شده',by('DECLARED'),'good'],['اظهار با تأخیر',by('LATE'),'warning'],
  ['شکاف شاهد انبار',gap,'serious'],['شکاف کهنه',by('CRITICAL_GAP'),'critical'],
  ['تناقض ترتیب تاریخ',by('SEQUENCE_CONFLICT'),'warning'],
  ['در مهلت پایش',by('PENDING'),''],['هنوز ترخیص نشده',by('NOT_CLEARED'),'']]
  .map((x,i)=>'<div class="kpi reveal" style="--i:'+i
   +(x[2]?';--tone:var(--st-'+x[2]+'-ink)':'')+'"'+(x[2]?' data-tone="'+x[2]+'"':'')
   +'><div class="l">'+esc2(x[0])+'</div><b>'+fmt(x[1])+'</b></div>').join('');
 /* بدترین‌ها بالا: شکاف کهنه، بعد شکاف، بعد تأخیر — با عمر شکاف نزولی. */
 const rank={CRITICAL_GAP:0,OVERDUE:1,SEQUENCE_CONFLICT:2,LATE:3,PENDING:4,
             DECLARED:5,NOT_CLEARED:6,UNKNOWN:7};
 const rows=wh.slice().sort((a,b)=>{
  const d=(rank[S(a,'WH_STATUS')]??9)-(rank[S(b,'WH_STATUS')]??9);
  return d||((+b['WH_AGE_DAYS']||0)-(+a['WH_AGE_DAYS']||0))}).slice(0,15);
 const num=v=>{const s=String(v??'').trim();return s===''||s==='nan'?'—':fmt(v)};
 const tab='<div class="tablewrap"><table>'
  +'<caption class="note">'+fmt(rows.length)+' از '+fmt(wh.length)
  +' ردیف · گرین: بارنامه × کالا · مبنای ترخیص در ستون آخر اعلام شده است.</caption>'
  +'<thead><tr><th scope="col">بارنامه</th><th scope="col">وضعیت اظهار</th>'
  +'<th scope="col">تاریخ ترخیص</th><th scope="col">قبض انبار</th>'
  +'<th scope="col">فاصله (روز)</th><th scope="col">عمر شکاف (روز)</th>'
  +'<th scope="col">مبنا</th></tr></thead><tbody>'
  +rows.map(x=>'<tr><td>'+esc2(S(x,'CANONICAL_BL'))+'</td><td>'
   +esc2(S(x,'WH_STATUS_FA'))+'</td><td>'+esc2(S(x,'WH_CLEAR_DATE')||'—')+'</td><td>'
   +esc2(S(x,'WH_RECEIPT_DATE')||'—')+'</td><td class="num">'+num(x['WH_LAG_DAYS'])
   +'</td><td class="num">'+num(x['WH_AGE_DAYS'])+'</td><td>'
   +esc2(S(x,'WH_CLEAR_BASIS')||'—')+'</td></tr>').join('')
  +'</tbody></table></div>';
 el.innerHTML='<h4 class="t-h4" style="margin-top:16px">اظهار انبار — سامانه جامع انبارها</h4>'
  +'<p class="note">زنجیره شاهد با ترخیص تمام نمی‌شود: کالای ترخیص‌شده باید قبض انبار '
  +'الکترونیکی بگیرد. مهلت قانونی اظهار needs_verification است و خودکار اعمال نمی‌شود؛ '
  +'آنچه اینجا می‌بینید شکاف <em>شاهد</em> است، نه حکم تخلف.</p>'
  +'<div class="grid-auto" style="--col:180px">'+cards+'</div>'+tab;
}

/* ── برج کنترل جریان پول / FX Traceability ── */
function renderFx(){
 const targets=[...document.querySelectorAll('.process-fx')];if(!targets.length)return;
 const fx=PROC.fx_ledger||[],fxc=PROC.fx_control_summary||[];
 if(!fx.length&&!fxc.length){el.innerHTML='';return}
 const bad=fx.filter(x=>(+x['FX_ANOMALY_COUNT']||0)>0).length;
 const open=fx.filter(x=>(+x['FX_NTSW_BALANCE']||0)>0).length;
 const high=fxc.filter(x=>['HIGH','CRITICAL'].includes(S(x,'FX_CONTROL_RISK_BAND'))).length;
 const overdue=fxc.filter(x=>S(x,'FX_DEADLINE_STATUS')==='OVERDUE').length;
 const unauth=fxc.reduce((s,x)=>s+(+x['FX_UNAUTHORIZED_REALLOCATION_COUNT']||0),0);
 const cgap=fxc.filter(x=>S(x,'FX_CONVERSION_STATUS')==='EVIDENCE_GAP').length;
 const cards=[['پرونده ارزی',fx.length,''],['ریسک بالا/بحرانی جریان پول',high,'critical'],
  ['Deadline عبورکرده',overdue,'stockout'],['جابجایی بدون شاهد مجوز',unauth,'serious'],
  ['شکاف شاهد تبدیل ارز',cgap,'warning'],['مانده تعهد مثبت',open,''],
  ['ناهنجاری ثبت‌شده',bad,'warning']]
  .map((x,i)=>'<div class="kpi reveal" style="--i:'+i
   +(x[2]?';--tone:var(--st-'+x[2]+'-ink)':'')+'"'+(x[2]?' data-tone="'+x[2]+'"':'')
   +'><div class="l">'+esc2(x[0])+'</div><b>'+fmt(x[1])+'</b></div>').join('');
 /* جدول از دفترکل FX می‌آید و با امتیاز ریسک کنترلی مرتب می‌شود. */
 const byReg={};fxc.forEach(x=>{byReg[S(x,'KEY_REG')]=x});
 const src=fx.length?fx:fxc;
 const rowsFx=src.slice().sort((a,b)=>
  (+b['FX_CONTROL_RISK_SCORE']||0)-(+a['FX_CONTROL_RISK_SCORE']||0)).slice(0,15);
 const tab=rowsFx.length?('<div class="tablewrap"><table><thead><tr>'
  +'<th scope="col">ثبت سفارش</th><th scope="col">مرحله جاری</th><th scope="col">ریسک</th>'
  +'<th scope="col">روز باقی</th><th scope="col">مانده Native</th>'
  +'<th scope="col">معادل EUR</th><th scope="col">معادل IRR</th>'
  +'<th scope="col">اثر تبدیل (ریال)</th><th scope="col">جابجایی بدون مجوز</th>'
  +'</tr></thead><tbody>'
  +rowsFx.map(x=>{const c=byReg[S(x,'KEY_REG')]||x;
   /* «۰ روز باقی» برای پرونده‌ای که اصلاً مهلتی ندارد گمراه‌کننده است:
      بدون تاریخ مهلت «—» نشان داده می‌شود، نه صفر. */
   const hasDue=String(c['FX_DEADLINE_DATE']||'').trim()!=='';
   return '<tr><td>'+esc2(S(x,'KEY_REG'))+'</td><td>'+esc2(S(c,'FX_CURRENT_STAGE')||S(x,'FX_MONEY_STAGE'))
    +'</td><td class="num">'+fmt(c['FX_CONTROL_RISK_SCORE'])+'</td><td class="num">'
    +(hasDue?fmt(c['FX_DAYS_REMAINING']):'—')+'</td><td class="num">'+fmt(x['FX_NTSW_BALANCE'])+' '+esc2(S(x,'FX_NTSW_CURRENCY'))
    +'</td><td class="num">'+fmt(x['FX_NTSW_BALANCE_EUR_EQ'])
    +'</td><td class="num">'+fmt(x['FX_NTSW_BALANCE_RIAL_EQ'])
    +'</td><td class="num">'+fmt(c['FX_CONVERSION_IMPACT_RIAL'])+'</td><td class="num">'
    +fmt(c['FX_UNAUTHORIZED_REALLOCATION_COUNT'])+'</td></tr>'}).join('')
  +'</tbody></table></div>'):'<p class="note">دفترکل FX در این اجرا موجود نیست.</p>';
 const fxHtml='<div class="split panel-head"><div><span class="t-overline">MONEY FLOW CONTROL TOWER</span><h3 class="t-h3">رهگیری مالی-ارزی / FX Traceability</h3></div><span class="badge badge--quiet">Evidence-based</span></div>'
  +'<p class="note">مرحله جاری، ریسک کنترلی، نزدیک‌ترین مهلت و جابه‌جایی بدون مجوز هر پرونده.</p>'
  +'<div class="grid-auto" style="--col:180px">'+cards+'</div>'+tab;
 targets.forEach(el=>{el.innerHTML=fxHtml;gsiReveal(el)})}

/* ── روایت این برش ──
   سه چیز که نسخه قبلی اشتباه می‌کرد و اینجا اصلاح شده:
   ۱) «هیچ ریسک فعالی نیست» فقط از بحرانی‌بودن موجودی نتیجه گرفته می‌شد؛
      حالا همه ابعاد ریسکِ در دسترس سنجیده می‌شوند.
   ۲) گلوگاه از میانگین می‌آمد؛ حالا میانه، و کنارش شمار پرونده.
   ۳) عمق و تعداد یافته‌ها ثابت بود؛ حالا از پروفایل مخاطب می‌آید. */
function audCfg(){return AUDIENCES[AUD]||AUDIENCES[Object.keys(AUDIENCES)[0]]}

/* شمارش ابعاد ریسک — نه فقط موجودی. */
function riskFacets(a){
 const f=[];
 const band=r=>S(r,'بحرانی (کوتاه)')||S(r,'کد طبقه بحرانی');
 const crit=a.filter(r=>['توقف خط','بحرانی','STOCKOUT','CRITICAL'].includes(band(r)));
 const critM=new Set(crit.map(r=>S(r,'KEY_MATERIAL').trim()).filter(Boolean));
 if(crit.length)f.push({k:'موجودی',n:critM.size||crit.length,
   t:'قطعه در طبقه بحرانی یا توقف خط',tone:'critical'});
 const fxc=PROC.fx_control_summary||[];
 const over=fxc.filter(x=>S(x,'FX_DEADLINE_STATUS')==='OVERDUE').length;
 if(over)f.push({k:'مهلت ارزی',n:over,t:'پرونده با مهلت عبورکرده',tone:'stockout'});
 const unauth=fxc.reduce((s,x)=>s+(+x['FX_UNAUTHORIZED_REALLOCATION_COUNT']||0),0);
 if(unauth)f.push({k:'مجوز جابه‌جایی',n:unauth,t:'جابه‌جایی بدون شاهد مجوز',tone:'serious'});
 const wh=PROC.warehouse_declaration||[];
 const gap=wh.filter(x=>['OVERDUE','CRITICAL_GAP'].includes(S(x,'WH_STATUS'))).length;
 if(gap)f.push({k:'اظهار انبار',n:gap,t:'شکاف شاهد پس از ترخیص',tone:'serious'});
 const waits=a.map(r=>N(r,'انتظار جاری (روز)')).filter(v=>v!==null);
 const stuck=waits.filter(v=>v>60).length;
 if(stuck)f.push({k:'توقف طولانی',n:stuck,t:'پرونده بیش از ۶۰ روز بدون رویداد',tone:'warning'});
 return f;
}

function renderStory(a,i){
 const cfg=audCfg(),depth=cfg.depth,maxF=cfg.max_findings;
 const band=r=>S(r,'بحرانی (کوتاه)')||S(r,'کد طبقه بحرانی');
 const crit=a.filter(r=>['توقف خط','بحرانی','STOCKOUT','CRITICAL'].includes(band(r)));
 const mats=new Set(),critMats=new Set();
 for(const r of a){const m=S(r,'KEY_MATERIAL').trim();if(m)mats.add(m)}
 for(const r of crit){const m=S(r,'KEY_MATERIAL').trim();if(m)critMats.add(m)}
 const rs=a.map(r=>N(r,'مقاومت (روز)')).filter(v=>v!==null).sort((x,y)=>x-y);
 const med=rs.length?(rs.length%2?rs[rs.length>>1]:(rs[(rs.length>>1)-1]+rs[rs.length>>1])/2):null;
 const nCrit=critMats.size||crit.length;
 const unit=critMats.size?' قطعه':' ردیف';
 const facets=riskFacets(a);

 const q=document.getElementById('story_q_'+i);
 if(q)q.textContent=cfg.question;

 const h=document.getElementById('story_h_'+i);
 if(h){
  if(nCrit)h.textContent='ریسک توقف خط: '+fmt(nCrit)+unit+' بحرانی در این برش';
  else if(facets.length)h.textContent='ریسک فعال این برش: '
   +facets.map(x=>x.k+' ('+fmt(x.n)+')').join(' · ');
  /* صادق: «موجودی بحرانی نداریم» با «هیچ ریسکی نیست» یکی نیست. */
  else h.textContent='در ابعادی که این گزارش می‌سنجد، ریسک فعالی دیده نشد.';
 }

 let situation='این برش '+fmt(a.length)+' ردیف'
  +(mats.size?('، '+fmt(mats.size)+' قطعه یکتا'):'')+' دارد.';
 let complication=nCrit?(fmt(nCrit)+unit+' در وضعیت بحرانی یا توقف خط است'
  +(mats.size?(' — '+(nCrit/mats.size*100).toFixed(1)+'٪ از قطعات این برش'):'')+'.')
  :'قطعه‌ای در طبقه بحرانی نیست.';
 if(facets.length>1)complication+=' ابعاد دیگر ریسک: '
  +facets.filter(x=>x.k!=='موجودی').map(x=>x.k+' '+fmt(x.n)).join('، ')+'.';
 if(med!==null&&depth>1)complication+=' میانه مقاومت '+fmt(med)
  +' روز است (میانه، نه میانگین — توزیع راست‌چوله است).';

 const bn=(PROC.bottlenecks||[])[0];
 const qs=(PROC.stage_queue||[])[0];
 let resolution;
 if(nCrit){const worst=a.filter(r=>N(r,'مقاومت (روز)')!==null)
   .sort((x,y)=>N(x,'مقاومت (روز)')-N(y,'مقاومت (روز)'))[0];
  resolution='پیگیری امروز از کم‌مقاومت‌ترین قطعه شروع شود'
   +(worst?(': '+S(worst,'KEY_MATERIAL')):'')+'.'}
 else if(facets.length)resolution='اقدام امروز روی «'+facets[0].k+'» است: '
   +fmt(facets[0].n)+' '+facets[0].t+'.';
 else resolution='این برش اقدام فوری نمی‌خواهد؛ ظرفیت پیگیری صرف تعهد معوق یا صف طولانی شود.';
 if(depth>1){
  if(qs)resolution+=' بزرگ‌ترین صف فعلی «'+S(qs,'مرحله جاری')+'» با '
   +fmt(qs['تعداد پرونده'])+' پرونده و میانه انتظار '+fmt(qs['میانه انتظار (روز)'])+' روز است.';
  else if(bn)resolution+=' طولانی‌ترین گذار «'+S(bn,'از فعالیت')+' ← '+S(bn,'به فعالیت')
   +'» با میانه '+fmt(bn['میانه روز'])+' روز است.';
 }

 const scr=document.getElementById('story_scr_'+i);
 if(scr){scr.innerHTML=[['وضعیت',situation],['گره',complication],['اقدام',resolution]]
  .map(x=>'<div class="scr"><b>'+x[0]+'</b><p>'+esc2(x[1])+'</p></div>').join('')}

 const box=document.getElementById('story_findings_'+i);
 if(box){const items=[];
  if(nCrit)items.push(['ریسک توقف خط',fmt(nCrit)+unit+' بحرانی',
   mats.size?((nCrit/mats.size*100).toFixed(1)+'٪ از قطعات این برش'):'',
   'پیگیری از کم‌مقاومت‌ترین قطعه شروع شود.','critical']);
  facets.filter(x=>x.k!=='موجودی').forEach(x=>items.push(
   [x.k,fmt(x.n)+' مورد',x.t,'بررسی و رفع شکاف شاهد یا مهلت، پیش از رسیدن به مرحله بعد.',x.tone]));
  if(med!==null&&depth>1)items.push(['پوشش مقاومت','میانه '+fmt(med)+' روز',
   'میانه گزارش می‌شود چون توزیع راست‌چوله است',
   'قطعات دهک پایین پیش از رسیدن به طبقه بحرانی سفارش‌گذاری شوند.',
   med<15?'warning':'good']);
  if(qs&&depth>1)items.push(['بزرگ‌ترین صف','«'+S(qs,'مرحله جاری')+'»',
   fmt(qs['تعداد پرونده'])+' پرونده منتظر · میانه '+fmt(qs['میانه انتظار (روز)'])
   +' روز · بیشترین '+fmt(qs['بیشترین انتظار (روز)'])+' روز',
   'ظرفیت پیگیری به همین مرحله داده شود؛ بیشترین اثر بر زمان چرخه اینجاست.','serious']);
  box.innerHTML=items.slice(0,maxF).map((x,i)=>'<article class="finding reveal" style="--i:'+i
   +';--tone:var(--st-'+x[4]+');--tone-ink:var(--st-'+x[4]+'-ink);--tone-wash:var(--st-'+x[4]+'-wash)">'
   +'<h5>'+esc2(x[0])+'</h5><p class="mag">'+esc2(x[1])+'</p>'
   +(x[2]?'<p class="cmp">'+esc2(x[2])+'</p>':'')
   +'<p class="sow"><span aria-hidden="true">←</span> '+esc2(x[3])+'</p></article>').join('');
  gsiReveal(box)}}

/* ── جابه‌جایی مخاطب ── */
function setAudience(k){
 if(!AUDIENCES[k])return;
 AUD=k;
 document.querySelectorAll('.persona').forEach(b=>
  b.setAttribute('aria-pressed',String(b.dataset.aud===k)));
 const cfg=audCfg();
 document.querySelectorAll('[data-section]').forEach(el=>{
  el.hidden=!cfg.sections.includes(el.dataset.section)});
 const cl=document.getElementById('aud_closing');
 if(cl)cl.textContent=cfg.closing?cfg.closing+' ':'';
 try{localStorage.setItem('gsi_aud',k)}catch(e){}
 render(active);
}

/* ── جدول و سنجه‌ها ── */
function pageMove(i,d){PAGE[i]=Math.max(0,(PAGE[i]||0)+d);render(i)}
function render(i){
 const t=TAB_META[i],a=rows(t);
 renderStory(a,i);
 const cards=[{l:'ردیف',v:a.length.toLocaleString('fa-IR'),g:''}];
 Object.keys(t.agg).slice(0,4).forEach(c=>cards.push({
  l:(t.agg[c]==='mean'?'میانگین ':'جمع ')+(LABELS[c]||c),
  v:fmt(gagg(a,c,t.grain,t.agg)),
  g:t.grain[c]?('یکتا بر '+t.grain[c]):'دانه ردیف'}));
 const cb=document.getElementById('cards_'+i);
 if(cb){cb.innerHTML=cards.map((x,j)=>'<div class="kpi reveal" style="--i:'+j+'">'
  +'<div class="l">'+esc2(x.l)+'</div><b>'+x.v+'</b><div class="g">'+esc2(x.g)+'</div></div>').join('');
  gsiReveal(cb)}
 const PAGE_SIZE=pageSize();
 const visible=a.slice(0,Math.max(1,t.max_rows||a.length));
 const pages=Math.max(1,Math.ceil(visible.length/PAGE_SIZE));
 PAGE[i]=Math.min(PAGE[i]||0,pages-1);
 const start=PAGE[i]*PAGE_SIZE,view=visible.slice(start,start+PAGE_SIZE);
 const cnt=document.getElementById('cnt_'+i);
 if(cnt)cnt.textContent=a.length.toLocaleString('fa-IR')+' ردیف · صفحه '
  +(PAGE[i]+1).toLocaleString('fa-IR')+' از '+pages.toLocaleString('fa-IR')+(a.length>visible.length?' · جدول فقط '+visible.length.toLocaleString('fa-IR')+' ردیف را نشان می‌دهد؛ دکمه Excel همین تب، همه '+a.length.toLocaleString('fa-IR')+' ردیف فیلترشده را با ستون‌های همین تب می‌دهد':'');
 const tb=document.getElementById('tb_'+i);
 if(tb)tb.innerHTML=view.map(r=>'<tr>'+t.fields.map(c=>'<td>'+esc2(S(r,c))+'</td>').join('')+'</tr>').join('');
 const mobile=document.getElementById('mc_'+i);
 if(mobile)mobile.innerHTML=view.map(r=>'<article class="material-card"><strong>'+esc2(S(r,'متریال'))+'</strong>'
  +'<p>'+esc2(S(r,'شرح متریال'))+'</p><p>موقعیت: '+esc2(S(r,'موقعیت فعلی'))+'</p><dl>'
  +['هشدار کارشناسان','کامنت کارشناسان','هشدار NTSW','کامنت NTSW'].filter(c=>S(r,c).trim()).map(c=>
  '<dt>'+esc2(c)+'</dt><dd>'+esc2(S(r,c))+'</dd>').join('')+'</dl></article>').join('');
 const pg=document.getElementById('pager_'+i);
 if(pg)pg.innerHTML='<button class="btn btn--secondary btn--sm" type="button"'
  +(PAGE[i]<=0?' disabled':'')+' onclick="pageMove('+i+',-1)">صفحه قبل</button>'
  +'<span>نمایش '+Math.min(start+1,visible.length).toLocaleString('fa-IR')+' تا '
  +Math.min(start+PAGE_SIZE,visible.length).toLocaleString('fa-IR')+' از '
  +a.length.toLocaleString('fa-IR')+'</span>'
  +'<button class="btn btn--secondary btn--sm" type="button"'
  +(PAGE[i]>=pages-1?' disabled':'')+' onclick="pageMove('+i+',1)">صفحه بعد</button>';
 renderCharts(i,a);renderFx();gsiReveal();if(typeof window.gsiCustomizerRefresh==='function')window.gsiCustomizerRefresh()}

function activate(i){active=i;PAGE[i]=0;
 const t=TAB_META[i];
 document.querySelectorAll('.tabbtn').forEach((b,j)=>{b.setAttribute('aria-selected',j===i);b.tabIndex=j===i?0:-1});
 TAB_META.forEach((m,j)=>{const p=document.getElementById(m.id);if(p)p.hidden=j!==i});
 if(q)q.value='';render(i)}

__XLSX__

document.querySelectorAll('.tabbtn').forEach((b,i)=>{
 b.addEventListener('click',()=>activate(i));
 b.addEventListener('keydown',e=>{let next=i;
 if(e.key==='ArrowLeft')next=(i+1)%TAB_META.length;
 else if(e.key==='ArrowRight')next=(i-1+TAB_META.length)%TAB_META.length;
 else if(e.key==='Home')next=0;else if(e.key==='End')next=TAB_META.length-1;else return;
 e.preventDefault();activate(next);document.querySelectorAll('.tabbtn')[next].focus()})});
if(q)q.addEventListener('input',()=>{PAGE[active]=0;render(active)});
document.querySelectorAll('[data-f]').forEach(s=>{
 const ev=s.tagName==='SELECT'?'change':'input';
 s.addEventListener(ev,()=>{PAGE[active]=0;render(active)})});
document.querySelectorAll('.persona').forEach(b=>{b.onclick=()=>setAudience(b.dataset.aud)});
/* نمای انتخابی هر خواننده یادش می‌ماند — ولی فقط در مرورگر خودش. */
try{const k=localStorage.getItem('gsi_aud');if(k&&AUDIENCES[k])AUD=k}catch(e){}
setAudience(AUD);
activate(active);
"""
    body = (body
            .replace("__CHART_CFG__", chart_json)
            .replace("__PROC__", proc_json)
            .replace("__CHARTS_LIB__", charts_lib)
            .replace("__REVEAL_JS__", CSS.REVEAL_JS)
            .replace("__XLSX__", _XLSX_JS))
    return "<script>" + body + "</script>"


#: خروجی Excel داخل مرورگر — بدون سرور، بدون کتابخانه.
#: ZIP با ذخیره‌سازی بدون فشرده‌سازی (method 0) ساخته می‌شود تا نیازی به
#: پیاده‌سازی deflate در جاوااسکریپت نباشد.
_XLSX_JS = r"""
function crc32(b){let t=window._crcT;if(!t){t=[];for(let n=0;n<256;n++){let c=n;
 for(let k=0;k<8;k++)c=(c&1)?0xEDB88320^(c>>>1):c>>>1;t[n]=c>>>0}window._crcT=t}
 let c=0xFFFFFFFF;for(const x of b)c=t[(c^x)&255]^(c>>>8);return (c^0xFFFFFFFF)>>>0}
const u8=s=>new TextEncoder().encode(s);
function zipStore(files){let chunks=[],central=[],offset=0;
 for(const [name,data] of files){const nb=u8(name),db=typeof data==='string'?u8(data):data,
  crc=crc32(db),head=new Uint8Array(30+nb.length),dv=new DataView(head.buffer);
  dv.setUint32(0,0x04034b50,true);dv.setUint16(4,20,true);dv.setUint32(14,crc,true);
  dv.setUint32(18,db.length,true);dv.setUint32(22,db.length,true);dv.setUint16(26,nb.length,true);
  head.set(nb,30);chunks.push(head,db);
  const cd=new Uint8Array(46+nb.length),cv=new DataView(cd.buffer);
  cv.setUint32(0,0x02014b50,true);cv.setUint16(4,20,true);cv.setUint16(6,20,true);
  cv.setUint32(16,crc,true);cv.setUint32(20,db.length,true);cv.setUint32(24,db.length,true);
  cv.setUint16(28,nb.length,true);cv.setUint32(42,offset,true);cd.set(nb,46);
  central.push(cd);offset+=head.length+db.length}
 const csize=central.reduce((s,x)=>s+x.length,0),end=new Uint8Array(22),ed=new DataView(end.buffer);
 ed.setUint32(0,0x06054b50,true);ed.setUint16(8,files.length,true);ed.setUint16(10,files.length,true);
 ed.setUint32(12,csize,true);ed.setUint32(16,offset,true);
 return new Blob(chunks.concat(central,[end]),
  {type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})}
function xmlEsc(s){return String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;')
 .replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&apos;')}
function colName(n){let s='';while(n){const r=(n-1)%26;s=String.fromCharCode(65+r)+s;
 n=Math.floor((n-1)/26)}return s}
function excelSerial(v){const d=new Date(v);if(!Number.isFinite(+d))return null;
 return (+d-Date.UTC(1899,11,30))/86400000}
function cellXml(v,ref,header,forceText=false){
 if(header)return '<c r="'+ref+'" s="1" t="inlineStr"><is><t>'+xmlEsc(v)+'</t></is></c>';
 const n=parseFloat(v);
 if(!forceText&&v!==''&&v!==null&&Number.isFinite(n)&&Math.abs(n)<1e15&&String(v).trim()===String(n))
  return '<c r="'+ref+'" s="2"><v>'+n+'</v></c>';
 if(!forceText&&typeof v==='string'&&/^\d{4}-\d{2}-\d{2}/.test(v)){const sv=excelSerial(v);
  if(sv!==null)return '<c r="'+ref+'" s="3"><v>'+sv+'</v></c>'}
 return '<c r="'+ref+'" t="inlineStr"><is><t>'+xmlEsc(v)+'</t></is></c>'}
function makeXlsx(rowsIn,fields,sheet){
 const safe=String(sheet||'Data').replace(/[\\/*?:\[\]]/g,' ').slice(0,31)||'Data';
 const head=fields.map((c,i)=>cellXml(LABELS[c]||c,colName(i+1)+'1',true)).join('');
 const body=rowsIn.map((r,i)=>'<row r="'+(i+2)+'">'
  +fields.map((c,j)=>cellXml(S(r,c),colName(j+1)+(i+2),false,/^(KEY_|CANONICAL_)|متریال|^سفارش$|^بارنامه$|^ثبت سفارش$/.test(c))).join('')+'</row>').join('');
 const last=colName(Math.max(fields.length,1))+(rowsIn.length+1);
 const sh='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:'+last+'"/><sheetViews><sheetView workbookViewId="0" rightToLeft="1"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData><row r="1">'+head+'</row>'+body+'</sheetData><autoFilter ref="A1:'+last+'"/></worksheet>';
 const wb='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="'+xmlEsc(safe)+'" sheetId="1" r:id="rId1"/></sheets></workbook>';
 const styles='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-mm-dd"/></numFmts><fonts count="2"><font><sz val="11"/><name val="IRANSans"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="IRANSans"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0B1F33"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment horizontal="right"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"><alignment horizontal="right"/></xf><xf numFmtId="4" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"><alignment horizontal="right"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"><alignment horizontal="right"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';
 const rel='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>';
 const wrel='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>';
 const ct='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>';
 return zipStore([['[Content_Types].xml',ct],['_rels/.rels',rel],['xl/workbook.xml',wb],
  ['xl/_rels/workbook.xml.rels',wrel],['xl/styles.xml',styles],['xl/worksheets/sheet1.xml',sh]])}
function downloadFilteredXlsx(){const t=TAB_META[active],a=rows(t);
 const blob=makeXlsx(a,t.fields,t.title),url=URL.createObjectURL(blob),
  x=document.createElement('a');
 x.href=url;x.download='GSI_filtered_'+new Date().toISOString().slice(0,10)+'.xlsx';
 x.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
"""
