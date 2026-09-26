# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .config import KnowledgeDeskConfig
from .parsers import extract_text, chunk_text

SUPPORTED={".txt",".md",".log",".sql",".py",".htm",".html",".json",".csv",".xlsx",".xlsm",".pdf",".docx"}
GENERATED_ARTIFACTS={"chatbot.html","knowledge_index.json","chatbot_content.json","weekly_lessons.json","manifest.json"}


def _connect(db_path: str) -> sqlite3.Connection:
    p=Path(db_path); p.parent.mkdir(parents=True, exist_ok=True)
    conn=sqlite3.connect(str(p), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory=sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS kb_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS kb_documents(
      document_id INTEGER PRIMARY KEY AUTOINCREMENT,
      path TEXT NOT NULL UNIQUE,
      source_type TEXT NOT NULL,
      title TEXT NOT NULL,
      file_hash TEXT NOT NULL,
      mtime_ns INTEGER NOT NULL,
      size_bytes INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'ACTIVE',
      indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      error TEXT
    );
    CREATE TABLE IF NOT EXISTS kb_chunks(
      chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
      document_id INTEGER NOT NULL,
      chunk_no INTEGER NOT NULL,
      body TEXT NOT NULL,
      FOREIGN KEY(document_id) REFERENCES kb_documents(document_id) ON DELETE CASCADE,
      UNIQUE(document_id, chunk_no)
    );
    CREATE TABLE IF NOT EXISTS kb_quarantine(
      quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT,
      path TEXT NOT NULL,
      source_type TEXT,
      reason_code TEXT NOT NULL,
      detail TEXT,
      detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS kb_questions(
      question_id INTEGER PRIMARY KEY AUTOINCREMENT,
      question TEXT NOT NULL,
      answer TEXT,
      sources_json TEXT,
      status TEXT NOT NULL DEFAULT 'ANSWERED',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(chunk_id UNINDEXED, title, path, body, tokenize='unicode61')")
        conn.execute("INSERT OR REPLACE INTO kb_meta(key,value) VALUES('fts5','1')")
    except sqlite3.OperationalError:
        conn.execute("INSERT OR REPLACE INTO kb_meta(key,value) VALUES('fts5','0')")


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()


def _iter_files(root: str, exclude_root: str = ""):
    p=Path(root)
    if not p.exists() or not p.is_dir(): return
    ex=None
    if str(exclude_root or "").strip():
        try: ex=Path(exclude_root).resolve()
        except Exception: ex=Path(exclude_root)
    for f in p.rglob("*"):
        if ex is not None:
            try:
                f.resolve().relative_to(ex)
                continue
            except Exception:
                pass
        if f.is_file() and f.suffix.lower() in SUPPORTED and not f.name.startswith("~$") and f.name.lower() not in GENERATED_ARTIFACTS:
            yield f


def _source_roots(cfg: KnowledgeDeskConfig):
    if cfg.knowledge_path.strip(): yield "knowledge", cfg.knowledge_path.strip()
    if cfg.lessons_path.strip() and Path(cfg.lessons_path.strip()) != Path(cfg.knowledge_path.strip() or "."):
        yield "lesson", cfg.lessons_path.strip()



def _norm_path(path: str) -> Path:
    return Path(path).expanduser().resolve(strict=False)

def validate_paths(cfg: KnowledgeDeskConfig, require_publish: bool = False) -> Dict:
    """Validate source/output topology before indexing.

    Output may be a child of a source root (the indexer excludes it), but it may
    not be the exact source root or an ancestor containing the source roots.
    """
    issues=[]
    k=str(cfg.knowledge_path or '').strip(); l=str(cfg.lessons_path or '').strip(); o=str(cfg.publish_path or '').strip()
    roots=[('knowledge',k),('lessons',l)]
    if not k and not l:
        issues.append({'code':'NO_SOURCE_ROOT','severity':'BLOCKER','detail':'هیچ مسیر دانش یا آموزش تعیین نشده است.'})
    if require_publish and not o:
        issues.append({'code':'NO_PUBLISH_ROOT','severity':'BLOCKER','detail':'مسیر انتشار چت‌بات تعیین نشده است.'})
    if o:
        op=_norm_path(o)
        for name,val in roots:
            if not val: continue
            rp=_norm_path(val)
            if op == rp:
                issues.append({'code':'PUBLISH_EQUALS_SOURCE','severity':'BLOCKER','source':name,'detail':'مسیر خروجی نباید دقیقاً همان مسیر منبع باشد.'})
            else:
                try:
                    rp.relative_to(op)
                    issues.append({'code':'PUBLISH_CONTAINS_SOURCE','severity':'BLOCKER','source':name,'detail':'مسیر خروجی نباید والد مسیر منبع باشد.'})
                except ValueError:
                    pass
    return {'ok': not any(i['severity']=='BLOCKER' for i in issues), 'issues':issues}

def build_index(cfg: KnowledgeDeskConfig) -> Dict:
    v=validate_paths(cfg)
    if not v["ok"]:
        codes=",".join(i["code"] for i in v["issues"] if i.get("severity")=="BLOCKER")
        raise RuntimeError(f"INVALID_KNOWLEDGE_PATH_TOPOLOGY:{codes}")
    stats={"scanned":0,"indexed":0,"unchanged":0,"quarantined":0,"deleted":0,"chunks":0}
    conn=_connect(cfg.db_path); init_db(conn)
    seen=set()
    scanned_roots=[]
    with conn:
        for source_type, root in _source_roots(cfg):
            rp=Path(root)
            if not rp.exists() or not rp.is_dir():
                conn.execute("INSERT INTO kb_quarantine(path,source_type,reason_code,detail) VALUES(?,?,?,?)",
                             (str(rp),source_type,"ROOT_NOT_FOUND","Folder does not exist or is not accessible"))
                stats["quarantined"]+=1; continue
            scanned_roots.append(rp.resolve())
            for p in _iter_files(root, cfg.publish_path):
                stats["scanned"]+=1; key=str(p.resolve()); seen.add(key)
                try:
                    st=p.stat(); existing=conn.execute("SELECT * FROM kb_documents WHERE path=?",(key,)).fetchone()
                    if existing and int(existing["mtime_ns"])==st.st_mtime_ns and int(existing["size_bytes"])==st.st_size:
                        conn.execute("UPDATE kb_documents SET status='ACTIVE' WHERE document_id=?",(existing["document_id"],))
                        stats["unchanged"]+=1; continue
                    digest=_sha256(p)
                    if existing and existing["file_hash"]==digest:
                        conn.execute("UPDATE kb_documents SET mtime_ns=?,size_bytes=?,status='ACTIVE',error=NULL,indexed_at=CURRENT_TIMESTAMP WHERE document_id=?",
                                     (st.st_mtime_ns,st.st_size,existing["document_id"]))
                        conn.execute("UPDATE kb_documents SET status='ACTIVE' WHERE document_id=?",(existing["document_id"],))
                        stats["unchanged"]+=1; continue
                    text,_=extract_text(p); chunks=chunk_text(text)
                    if not chunks: raise RuntimeError("EMPTY_TEXT")
                    if existing:
                        doc_id=existing["document_id"]
                        conn.execute("DELETE FROM kb_fts WHERE chunk_id IN (SELECT chunk_id FROM kb_chunks WHERE document_id=?)",(doc_id,))
                        conn.execute("DELETE FROM kb_chunks WHERE document_id=?",(doc_id,))
                        conn.execute("UPDATE kb_documents SET source_type=?,title=?,file_hash=?,mtime_ns=?,size_bytes=?,status='ACTIVE',error=NULL,indexed_at=CURRENT_TIMESTAMP WHERE document_id=?",
                                     (source_type,p.stem,digest,st.st_mtime_ns,st.st_size,doc_id))
                    else:
                        cur=conn.execute("INSERT INTO kb_documents(path,source_type,title,file_hash,mtime_ns,size_bytes) VALUES(?,?,?,?,?,?)",
                                         (key,source_type,p.stem,digest,st.st_mtime_ns,st.st_size)); doc_id=cur.lastrowid
                    fts=int((conn.execute("SELECT value FROM kb_meta WHERE key='fts5'").fetchone() or ["0"])[0])
                    for n,body in enumerate(chunks):
                        cur=conn.execute("INSERT INTO kb_chunks(document_id,chunk_no,body) VALUES(?,?,?)",(doc_id,n,body)); cid=cur.lastrowid
                        if fts: conn.execute("INSERT INTO kb_fts(chunk_id,title,path,body) VALUES(?,?,?,?)",(cid,p.stem,key,body))
                    stats["indexed"]+=1; stats["chunks"]+=len(chunks)
                except Exception as ex:
                    stats["quarantined"]+=1
                    conn.execute("INSERT INTO kb_quarantine(path,source_type,reason_code,detail) VALUES(?,?,?,?)",
                                 (key,source_type,"PARSE_OR_INDEX_ERROR",str(ex)[:1500]))
                    if 'existing' in locals() and existing:
                        conn.execute("UPDATE kb_documents SET status='QUARANTINED',error=? WHERE document_id=?",(str(ex)[:1500],existing["document_id"]))
        # only mark files missing from configured roots as deleted; keep audit row
        for row in conn.execute("SELECT document_id,path FROM kb_documents WHERE status!='DELETED'").fetchall():
            if row["path"] not in seen and any(Path(row["path"]).is_relative_to(root) for root in scanned_roots):
                conn.execute("UPDATE kb_documents SET status='DELETED' WHERE document_id=?",(row["document_id"],)); stats["deleted"]+=1
        conn.execute("INSERT OR REPLACE INTO kb_meta(key,value) VALUES('last_indexed_at', datetime('now'))")
        # Composition of the resulting index, so a single file dominating the
        # knowledge base is visible before anything is published. A raw business
        # dump dropped into the knowledge folder indexes silently today and can
        # become almost the whole published chatbot.
        top = conn.execute(
            "SELECT d.path, count(*) AS n FROM kb_chunks c "
            "JOIN kb_documents d ON d.document_id=c.document_id "
            "WHERE d.status='ACTIVE' GROUP BY d.path ORDER BY n DESC LIMIT 1").fetchone()
        total = conn.execute(
            "SELECT count(*) FROM kb_chunks c JOIN kb_documents d ON d.document_id=c.document_id "
            "WHERE d.status='ACTIVE'").fetchone()[0]
        if top and total:
            stats["largest_source"] = Path(top["path"]).name
            stats["largest_source_share"] = round(top["n"] / total, 3)
    conn.close(); return stats


def status(cfg: KnowledgeDeskConfig) -> Dict:
    conn=_connect(cfg.db_path); init_db(conn)
    out={}
    for name,sql in {
        "documents":"SELECT COUNT(*) FROM kb_documents WHERE status='ACTIVE'",
        "chunks":"SELECT COUNT(*) FROM kb_chunks c JOIN kb_documents d ON d.document_id=c.document_id WHERE d.status='ACTIVE'",
        "quarantine":"SELECT COUNT(*) FROM kb_quarantine",
        "questions":"SELECT COUNT(*) FROM kb_questions"}.items():
        out[name]=int(conn.execute(sql).fetchone()[0])
    r=conn.execute("SELECT value FROM kb_meta WHERE key='last_indexed_at'").fetchone(); out["last_indexed_at"]=r[0] if r else "—"
    conn.close(); return out
