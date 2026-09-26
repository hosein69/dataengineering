# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from typing import Dict, List

from .config import KnowledgeDeskConfig
from .indexer import _connect, init_db, validate_paths
from .lessons import discover_lessons
from .operational import operational_chunks


def _public_source(path: str, cfg: KnowledgeDeskConfig) -> str:
    """Return a user-facing source label without exposing UNC/local roots."""
    raw = str(path or "")
    p = Path(raw)
    for root in (cfg.knowledge_path, cfg.lessons_path):
        if not str(root or "").strip():
            continue
        try:
            return str(p.relative_to(Path(root))).replace("\\", "/")
        except Exception:
            pass
    return p.name or raw.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]


def path_to_file_uri(path: str) -> str:
    """Convert a Windows UNC/drive path (or POSIX absolute path) to a file URI.

    The URI is intended only as the target of the report's visible button. The
    knowledge source paths themselves are never exported to the static index.
    """
    s = str(path or "").strip()
    if not s:
        return ""
    s = s.replace("\\", "/")
    if s.startswith("//"):
        # //SERVER/Share/path -> file://SERVER/Share/path
        return "file:" + quote(s, safe="/:~!$&'()*+,;=@")
    if re.match(r"^[A-Za-z]:/", s):
        return "file:///" + quote(s, safe="/:~!$&'()*+,;=@")
    try:
        return Path(path).resolve().as_uri()
    except Exception:
        return ""


def _active_chunks(cfg: KnowledgeDeskConfig) -> List[Dict]:
    conn = _connect(cfg.db_path); init_db(conn)
    rows = conn.execute("""
        SELECT c.chunk_id,c.chunk_no,c.body,d.title,d.path,d.source_type,d.file_hash
        FROM kb_chunks c
        JOIN kb_documents d ON d.document_id=c.document_id
        WHERE d.status='ACTIVE'
        ORDER BY d.document_id,c.chunk_no
    """).fetchall()
    out=[]
    for r in rows:
        out.append({
            "id": int(r["chunk_id"]),
            "title": str(r["title"] or ""),
            "source": _public_source(str(r["path"] or ""), cfg),
            "source_type": str(r["source_type"] or "knowledge"),
            "chunk_no": int(r["chunk_no"] or 0),
            "body": str(r["body"] or ""),
        })
    conn.close(); return out


def _safe_lessons(cfg: KnowledgeDeskConfig) -> List[Dict]:
    out=[]
    for x in discover_lessons(cfg.lessons_path):
        out.append({
            "id": str(x.get("id") or ""),
            "week": str(x.get("week") or ""),
            "title": str(x.get("title") or ""),
            "summary": str(x.get("summary") or ""),
            "body": str(x.get("body") or ""),
            "questions": list(x.get("questions") or []),
        })
    return out


def _html(payload: Dict, title: str) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    safe_title = html.escape(title or "دستیار دانش بازرگانی GSI")
    return rf'''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>{safe_title}</title>
<style>
:root{{--navy:#0b1f33;--teal:#0a7c86;--gold:#c79a4a;--bg:#f4f7f8;--card:#fff;--line:#dbe3e7;--muted:#607584;--ok:#1f6f5f}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);font-family:Tahoma,Arial,sans-serif;color:var(--navy)}}
.wrap{{max-width:920px;margin:auto;padding:20px}}.head{{background:linear-gradient(135deg,#0b1f33,#0a7c86);color:#fff;padding:20px;border-radius:18px;box-shadow:0 10px 30px #0b1f3318}}
.head h1{{margin:0 0 7px;font-size:22px}}.head p{{margin:0;line-height:1.8;font-size:13px;opacity:.92}}.stats{{margin-top:8px;font-size:11px;opacity:.8}}
.lesson{{margin-top:14px;background:#fff8e8;border:1px solid #ead7aa;border-radius:16px;padding:14px}}.lesson h2{{font-size:16px;margin:0 0 6px}}.lesson p{{margin:0;line-height:1.8;color:#5b4c2d;font-size:13px}}
.chat{{margin-top:14px;background:var(--card);border:1px solid var(--line);border-radius:18px;min-height:52vh;padding:14px;box-shadow:0 8px 24px #0b1f330c}}
.msg{{max-width:88%;padding:11px 13px;border-radius:13px;margin:9px 0;line-height:1.95;white-space:pre-wrap}}.user{{margin-right:auto;background:#e5f4f2}}.bot{{margin-left:auto;background:#f7f9fa;border:1px solid var(--line)}}
.sources{{margin-top:9px;border-top:1px dashed var(--line);padding-top:7px;font-size:11px;color:var(--muted)}}.src{{display:block;margin:3px 0}}
.bar{{display:flex;gap:8px;margin-top:12px}}.bar textarea{{flex:1;min-height:64px;max-height:150px;border:1px solid var(--line);border-radius:14px;padding:12px;font:inherit;resize:vertical}}.bar button{{border:0;background:var(--teal);color:#fff;border-radius:14px;padding:0 20px;font:inherit;font-weight:700;cursor:pointer}}
.quick{{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}}.quick button{{border:1px solid var(--line);background:#fff;border-radius:999px;padding:7px 10px;color:var(--navy);font:inherit;font-size:12px;cursor:pointer}}.quick button:hover{{border-color:var(--teal)}}
.note{{font-size:11px;color:var(--muted);margin-top:9px;line-height:1.8}}.badge{{display:inline-block;border-radius:999px;background:#e5f4f2;color:var(--ok);padding:3px 8px;font-size:10px;font-weight:700}}
@media(max-width:600px){{.wrap{{padding:10px}}.msg{{max-width:96%}}.bar{{flex-direction:column}}.bar button{{height:44px}}}}
</style></head><body><div class="wrap">
<div class="head"><h1>💬 {safe_title}</h1><p>جست‌وجوی آفلاین در دانش تأییدشده داخلی؛ بدون اینترنت، بدون سرور و بدون ارسال داده به بیرون.</p><div class="stats" id="stats"></div></div>
<div id="lesson" class="lesson" hidden></div>
<div id="chat" class="chat"><div class="msg bot">سؤال بازرگانی خود را بنویسید. پاسخ‌ها از متن اسناد داخلی استخراج می‌شوند و منبع نشان داده می‌شود. اگر مدرک کافی نباشد، سیستم صریحاً اعلام می‌کند.</div></div>
<div class="quick" id="quick"></div>
<div class="bar"><textarea id="q" placeholder="مثلاً برای تمدید ثبت سفارش چه مدارکی لازم است؟"></textarea><button id="send">ارسال</button></div>
<div class="note"><span class="badge">OFFLINE</span> این نسخه بدون ارسال داده به بیرون کار می‌کند؛ سؤال‌های شناسه‌محور را از Semantic DWH و سؤال‌های رویه‌ای را از دانش مستند پاسخ می‌دهد و منبع را نمایش می‌دهد.</div>
</div>
<script id="gsi-data" type="application/json">{data}</script>
<script>
const DB=JSON.parse(document.getElementById('gsi-data').textContent);const CH=DB.chunks||[], LS=DB.lessons||[];
const STOP=new Set(['از','به','در','با','برای','که','را','و','یا','این','آن','چه','چطور','چگونه','یک','روی','است','هست','می','شود','شده','کرد','کردن']);
function norm(s){{return String(s||'').toLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[ةۀ]/g,'ه').replace(/[ؤ]/g,'و').replace(/[إأ]/g,'ا').replace(/\u200c/g,' ').replace(/[\u064b-\u065f\u0670]/g,' ').replace(/[^\w\u0600-\u06ff]+/g,' ').replace(/\s+/g,' ').trim()}}
function toks(s){{return [...new Set(norm(s).split(' ').filter(x=>x.length>1&&!STOP.has(x)))].slice(0,14)}}
function esc(s){{return String(s||'').replace(/[&<>\"]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[m]))}}
function count(h,n){{if(!n)return 0;let c=0,p=0;while((p=h.indexOf(n,p))>=0){{c++;p+=n.length}}return c}}
function score(c,ts){{const b=norm(c.body),t=norm(c.title);let s=0,hit=0;for(const x of ts){{let k=count(b,x);if(k){{hit++;s+=Math.min(k,6)*2}}if(t.includes(x))s+=8}}if(hit===ts.length&&ts.length>1)s+=10;return s}}
function sentences(body){{return String(body||'').split(/(?<=[\.؟!])\s+|\n+/).map(x=>x.trim()).filter(x=>x.length>25)}}
function excerpt(c,ts){{let ss=sentences(c.body).map(s=>[ts.reduce((a,t)=>a+(norm(s).includes(t)?1:0),0),s]).filter(x=>x[0]>0).sort((a,b)=>b[0]-a[0]);return (ss.slice(0,2).map(x=>x[1]).join(' ')||String(c.body||'').slice(0,520)).slice(0,850)}}
function search(q){{const ts=toks(q);if(!ts.length)return[];return CH.map(c=>[score(c,ts),c]).filter(x=>x[0]>0).sort((a,b)=>b[0]-a[0]).slice(0,6).map(x=>({{...x[1],score:x[0]}}))}}
function add(cls,txt,sources){{const d=document.createElement('div');d.className='msg '+cls;d.innerHTML=esc(txt).replace(/\n/g,'<br>');if(sources&&sources.length){{const s=document.createElement('div');s.className='sources';s.innerHTML='<b>منابع</b>'+sources.map(x=>'<span class="src">• '+esc(x.title)+(x.source?' — '+esc(x.source):'')+'</span>').join('');d.appendChild(s)}}document.getElementById('chat').appendChild(d);d.scrollIntoView({{behavior:'smooth',block:'end'}})}}
function ask(q0){{const e=document.getElementById('q'),q=(q0||e.value).trim();if(!q)return;add('user',q);e.value='';const hits=search(q);if(!hits.length){{add('bot','در پایگاه دانش فعلی مدرک کافی برای پاسخ قابل‌استناد پیدا نشد. بهتر است سؤال برای کارشناس ثبت یا پایگاه دانش تکمیل شود.');return}}const top=hits[0].score;const useful=hits.filter(x=>x.score>=Math.max(2,top*.45)).slice(0,4);const answer=useful.map(x=>excerpt(x,toks(q))).filter((x,i,a)=>x&&a.indexOf(x)===i).slice(0,4).join('\n\n');add('bot',answer,useful.map(x=>({{title:x.title,source:x.source}})))}}
function init(){{document.getElementById('stats').textContent=(DB.meta?.documents||0)+' سند · '+CH.length+' قطعه دانش · آخرین ساخت: '+(DB.meta?.built_at||'—');if(LS.length){{const x=LS[0],d=document.getElementById('lesson');d.hidden=false;d.innerHTML='<h2>'+esc(x.title)+'</h2><p>'+esc(x.summary||x.body||'')+'</p>'}}const qk=['ثبت سفارش','تخصیص ارز','حمل و بارنامه','ترخیص','رفع تعهد'];document.getElementById('quick').innerHTML=qk.map(x=>'<button type="button">'+x+'</button>').join('');[...document.querySelectorAll('#quick button')].forEach(b=>b.onclick=()=>{{e=document.getElementById('q');e.value=b.textContent;e.focus()}});const qp=new URLSearchParams(location.search).get('q');if(qp){{document.getElementById('q').value=qp;setTimeout(()=>ask(qp),80)}}}}
document.getElementById('send').onclick=()=>ask();document.getElementById('q').addEventListener('keydown',e=>{{if(e.key==='Enter'&&!e.shiftKey){{e.preventDefault();ask()}}}});init();
</script></body></html>'''


def publish_static(cfg: KnowledgeDeskConfig) -> Dict:
    v=validate_paths(cfg, require_publish=True)
    if not v["ok"]:
        codes=",".join(i["code"] for i in v["issues"] if i.get("severity")=="BLOCKER")
        raise RuntimeError(f"INVALID_KNOWLEDGE_PATH_TOPOLOGY:{codes}")
    out_dir = Path(str(cfg.publish_path or "").strip())
    if not str(out_dir):
        raise ValueError("publish_path is required")
    out_dir.mkdir(parents=True, exist_ok=True)
    document_chunks = _active_chunks(cfg)
    operational = operational_chunks()
    chunks = document_chunks + operational
    lessons = _safe_lessons(cfg)
    if not chunks:
        raise RuntimeError("BLOCKED_EMPTY_KNOWLEDGE: هیچ قطعه دانش مستندی یا Snapshot عملیاتی DWH قابل استفاده نیست.")
    conn = _connect(cfg.db_path); init_db(conn)
    doc_count = int(conn.execute("SELECT COUNT(*) FROM kb_documents WHERE status='ACTIVE'").fetchone()[0])
    q_count = int(conn.execute("SELECT COUNT(*) FROM kb_quarantine").fetchone()[0])
    conn.close()
    built_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    payload = {
        "meta": {"built_at": built_at, "documents": doc_count, "chunks": len(chunks),
                 "document_chunks": len(document_chunks), "operational_chunks": len(operational),
                 "quarantine": q_count, "version": "static_v2_semantic_dwh"},
        "chunks": chunks,
        "lessons": lessons,
    }
    # Audit/readable sidecars. chatbot.html remains self-contained for file:// reliability.
    (out_dir / "knowledge_index.json").write_text(json.dumps({"meta":payload["meta"],"chunks":chunks}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out_dir / "chatbot_content.json").write_text(json.dumps(lessons, ensure_ascii=False, indent=2), encoding="utf-8")
    # Backward-compatible sidecar for saved designs from V29.3/V29.4; not user-facing.
    (out_dir / "weekly_lessons.json").write_text(json.dumps(lessons, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps({
        "built_at": built_at, "documents": doc_count, "chunks": len(chunks), "lessons": len(lessons), "quarantine": q_count,
        "document_chunks": len(document_chunks), "operational_chunks": len(operational),
        "mode": "shared-folder-static-zero-server", "entrypoint": "chatbot.html"
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    h = _html(payload, cfg.title)
    entry = out_dir / "chatbot.html"
    entry.write_text(h, encoding="utf-8")
    return {
        "publish_path": str(out_dir),
        "entrypoint": str(entry),
        "chatbot_href": path_to_file_uri(str(entry)),
        "documents": doc_count,
        "chunks": len(chunks),
        "lessons": len(lessons),
        "quarantine": q_count,
        "html_bytes": len(h.encode("utf-8")),
    }
