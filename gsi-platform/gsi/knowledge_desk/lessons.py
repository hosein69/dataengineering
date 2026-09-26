# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional
from .parsers import extract_text

GENERATED_ARTIFACTS={"chatbot.html","knowledge_index.json","chatbot_content.json","weekly_lessons.json","manifest.json"}


def discover_lessons(folder: str) -> List[Dict]:
    # Blank optional-content path means "no extra content". Path("") points to
    # the current working directory and previously caused the whole GSI package
    # to be scanned and embedded as pseudo-lessons.
    if not str(folder or "").strip():
        return []
    p=Path(str(folder).strip())
    if not p.exists() or not p.is_dir(): return []
    out=[]
    for f in sorted((x for x in p.iterdir() if x.is_file() and x.name.lower() not in GENERATED_ARTIFACTS), key=lambda x:x.stat().st_mtime, reverse=True):
        try:
            text,_=extract_text(f)
            if not text: continue
            lines=[x.strip() for x in text.splitlines() if x.strip()]
            title=(lines[0][:120] if lines else f.stem)
            body="\n".join(lines[:25])[:5000]
            out.append({"id":f.name,"week":"","title":title,"summary":body[:260],"body":body,"questions":[],"source_path":str(f)})
        except Exception:
            continue
    return out


def current_lesson(folder: str) -> Optional[Dict]:
    x=discover_lessons(folder); return x[0] if x else None
