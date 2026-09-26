# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List

from .config import KnowledgeDeskConfig
from .indexer import _connect, init_db
from .operational import operational_search

STOP={"از","به","در","با","برای","که","را","و","یا","این","آن","چه","چطور","چگونه","یک","روی","است","هست","می","شود","شده"}


def _tokens(q:str)->List[str]:
    q=str(q or "").translate(str.maketrans({"ي":"ی","ى":"ی","ك":"ک","ة":"ه","ۀ":"ه","ؤ":"و","إ":"ا","أ":"ا"})).replace("\u200c"," ")
    t=re.findall(r"[\w\u0600-\u06FF]+", str(q).lower())
    return [x for x in t if len(x)>1 and x not in STOP][:12]


def search(cfg: KnowledgeDeskConfig, question: str, limit: int=6) -> List[Dict]:
    conn=_connect(cfg.db_path); init_db(conn); tokens=_tokens(question)
    if not tokens: conn.close(); return []
    fts=(conn.execute("SELECT value FROM kb_meta WHERE key='fts5'").fetchone() or ["0"])[0]=="1"
    rows=[]
    if fts:
        # OR gives better recall for Persian business vocabulary while BM25 ranks it.
        expr=" OR ".join('"'+x.replace('"','')+'"' for x in tokens)
        try:
            rows=conn.execute("""
              SELECT f.chunk_id,f.title,f.path,f.body,bm25(kb_fts) score
              FROM kb_fts f JOIN kb_chunks c ON c.chunk_id=f.chunk_id
              JOIN kb_documents d ON d.document_id=c.document_id
              WHERE kb_fts MATCH ? AND d.status='ACTIVE'
              ORDER BY score LIMIT ?""",(expr,int(limit))).fetchall()
        except sqlite3.OperationalError: rows=[]
    if not rows:
        clauses=[]; params=[]
        for x in tokens:
            clauses.append("c.body LIKE ?"); params.append(f"%{x}%")
        sql=f"""SELECT c.chunk_id,d.title,d.path,c.body,0 score FROM kb_chunks c
                 JOIN kb_documents d ON d.document_id=c.document_id
                 WHERE d.status='ACTIVE' AND ({' OR '.join(clauses)}) LIMIT ?"""
        rows=conn.execute(sql,(*params,int(limit))).fetchall()
    out=[dict(r) for r in rows]; conn.close(); return out


def _best_sentences(body:str, tokens:List[str], n:int=2)->List[str]:
    sents=[x.strip() for x in re.split(r"(?<=[\.؟!])\s+|\n+", body) if len(x.strip())>20]
    scored=[]
    for s in sents:
        score=sum(1 for t in tokens if t in s.lower())
        if score: scored.append((score, -len(s), s))
    return [x[2] for x in sorted(scored, reverse=True)[:n]]


def answer(cfg: KnowledgeDeskConfig, question: str, limit:int=6) -> Dict:
    # Operational DWH evidence has precedence for explicit business identifiers;
    # documentary knowledge remains the authority for policies/how-to questions.
    policy = any(word in question.lower() for word in ("policy", "procedure", "how to", "رویه", "آیین نامه", "دستورالعمل"))
    operational = not policy and bool(re.search(r"(?<!\d)\d{6,16}(?!\d)|\b(?:ORDER|BL|MATERIAL|PO|PR|REG)\s*[:#]?\s*[A-Za-z0-9]", question, re.I))
    try:
        op_hits=operational_search(question,limit) if operational else []
    except RuntimeError:
        return {"answer":"منبع عملیاتی در دسترس نیست؛ وضعیت پرونده قابل تأیید نیست.", "sources":[], "status":"SOURCE_UNAVAILABLE"}
    doc_hits=[] if operational else search(cfg,question,limit)
    hits=op_hits + doc_hits; toks=_tokens(question)
    if not hits:
        ans="در پایگاه دانش و Business DWH منتشرشده مدرک کافی برای پاسخ قابل‌استناد پیدا نشد. سؤال برای تکمیل دانش ثبت شد."
        status="UNANSWERED"; sources=[]
    else:
        lines=[]; sources=[]; seen=set()
        # Operational bodies are already structured semantic answers; documents
        # are excerpted sentence-wise. This avoids blending a fact with guidance.
        for h in hits[:4]:
            if h.get("source_type") == "operational_dwh":
                parts=[str(h.get("body") or "").strip()]
            else:
                parts=_best_sentences(h["body"],toks,2) or [h["body"][:420].strip()]
            for part in parts:
                if part and part not in lines: lines.append(part)
            key=h["path"]
            if key not in seen:
                sources.append({"title":h["title"],"path":h["path"],"source_type":h.get("source_type","knowledge")}); seen.add(key)
        ans="\n\n".join(lines[:5])
        status="ANSWERED_OPERATIONAL" if op_hits else ("ANSWERED" if ans else "UNANSWERED")
    conn=_connect(cfg.db_path); init_db(conn)
    with conn:
        conn.execute("INSERT INTO kb_questions(question,answer,sources_json,status) VALUES(?,?,?,?)",
                     (question,ans,json.dumps(sources,ensure_ascii=False),status))
    conn.close()
    return {"answer":ans,"sources":sources,"status":status}
