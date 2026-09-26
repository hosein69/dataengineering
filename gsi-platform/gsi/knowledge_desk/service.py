# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import KnowledgeDeskConfig, load_config
from .query import answer

_LOCK=threading.Lock(); _SERVER=None; _THREAD=None; _CFG=None

UI=r'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GSI Knowledge Desk</title><style>
:root{--navy:#0b1f33;--teal:#0a7c86;--bg:#f4f7f8;--line:#dbe3e7}*{box-sizing:border-box}body{margin:0;background:var(--bg);font-family:Tahoma,Arial,sans-serif;color:var(--navy)}.wrap{max-width:850px;margin:0 auto;padding:24px}.head{background:linear-gradient(135deg,#0b1f33,#0a7c86);color:white;padding:22px;border-radius:18px}.head h1{font-size:22px;margin:0 0 8px}.chat{margin-top:14px;background:white;border:1px solid var(--line);border-radius:18px;min-height:55vh;padding:16px}.msg{max-width:85%;padding:12px 14px;border-radius:14px;margin:10px 0;line-height:1.9;white-space:pre-wrap}.user{margin-right:auto;background:#e7f4f3}.bot{margin-left:auto;background:#f4f6f7;border:1px solid var(--line)}.sources{font-size:11px;color:#536777;margin-top:8px}.bar{display:flex;gap:8px;margin-top:12px}.bar textarea{flex:1;min-height:58px;border:1px solid var(--line);border-radius:14px;padding:12px;font:inherit}.bar button{background:var(--teal);color:white;border:0;border-radius:14px;padding:0 20px;font:inherit;font-weight:700;cursor:pointer}.hint{font-size:12px;color:#607584;margin-top:8px}</style></head><body><div class="wrap"><div class="head"><h1>💬 دستیار دانش بازرگانی GSI</h1><div>پاسخ‌ها فقط از پایگاه دانش داخلی و منابع قابل‌استناد استخراج می‌شوند.</div></div><div id="chat" class="chat"><div class="msg bot">سؤال بازرگانی خود را بپرسید. اگر مدرک کافی وجود نداشته باشد، سیستم صریحاً اعلام می‌کند.</div></div><div class="bar"><textarea id="q" placeholder="مثلاً برای تمدید ثبت سفارش چه مدارکی لازم است؟"></textarea><button onclick="ask()">ارسال</button></div><div class="hint">GSI Knowledge Desk · شبکه داخلی</div></div><script>
const qp=new URLSearchParams(location.search).get('q'); if(qp)document.getElementById('q').value=qp;
function esc(s){return String(s||'').replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]))}function add(cls,txt,src){const d=document.createElement('div');d.className='msg '+cls;d.innerHTML=esc(txt).replace(/\n/g,'<br>')+(src&&src.length?'<div class="sources">منابع: '+src.map(x=>esc(x.title)).join(' · ')+'</div>':'');document.getElementById('chat').appendChild(d);d.scrollIntoView({behavior:'smooth'});}async function ask(){const e=document.getElementById('q'),q=e.value.trim();if(!q)return;add('user',q);e.value='';add('bot','در حال جست‌وجو در پایگاه دانش…');const c=document.getElementById('chat'),wait=c.lastChild;try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});const j=await r.json();wait.remove();add('bot',j.answer,j.sources)}catch(err){wait.remove();add('bot','ارتباط با سرویس دانش برقرار نشد.')}}document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask()}});</script></body></html>'''


def _handler(cfg):
    class H(BaseHTTPRequestHandler):
        def _headers(self,code=200,ctype="application/json; charset=utf-8"):
            self.send_response(code); self.send_header("Content-Type",ctype)
            self.send_header("Access-Control-Allow-Origin","*")
            self.send_header("Access-Control-Allow-Headers","Content-Type")
            self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS"); self.end_headers()
        def log_message(self,*args): return
        def do_OPTIONS(self): self._headers(204)
        def do_GET(self):
            u=urlparse(self.path)
            if u.path=="/health":
                self._headers(); self.wfile.write(json.dumps({"ok":True,"service":"gsi-knowledge-desk"}).encode())
            else:
                self._headers(200,"text/html; charset=utf-8"); self.wfile.write(UI.encode("utf-8"))
        def do_POST(self):
            if urlparse(self.path).path!="/api/chat": self._headers(404); return
            try:
                n=int(self.headers.get("Content-Length","0") or 0); raw=self.rfile.read(min(n,200000))
                q=str(json.loads(raw or b"{}").get("question","")).strip()
                if not q: raise ValueError("question is required")
                result=answer(cfg,q); self._headers(); self.wfile.write(json.dumps(result,ensure_ascii=False).encode("utf-8"))
            except Exception as ex:
                self._headers(400); self.wfile.write(json.dumps({"answer":"خطا در پردازش سؤال.","error":str(ex)},ensure_ascii=False).encode("utf-8"))
    return H


def start_service(cfg: KnowledgeDeskConfig):
    global _SERVER,_THREAD,_CFG
    with _LOCK:
        if _SERVER is not None:
            return {"started":False,"url":cfg.effective_public_url,"message":"already running"}
        _CFG=cfg
        _SERVER=ThreadingHTTPServer((cfg.host,int(cfg.port)),_handler(cfg))
        _THREAD=threading.Thread(target=_SERVER.serve_forever,name="gsi-knowledge-desk",daemon=True); _THREAD.start()
        return {"started":True,"url":cfg.effective_public_url,"message":"started"}


def stop_service():
    global _SERVER,_THREAD,_CFG
    with _LOCK:
        if _SERVER is not None:
            _SERVER.shutdown(); _SERVER.server_close()
        _SERVER=None; _THREAD=None; _CFG=None


def service_running()->bool:
    return bool(_SERVER is not None and _THREAD is not None and _THREAD.is_alive())
