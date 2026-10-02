# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import socket
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "knowledge_desk.json"


@dataclass
class KnowledgeDeskConfig:
    knowledge_path: str = ""
    lessons_path: str = ""
    db_path: str = str(ROOT / "data" / "knowledge_desk.sqlite")
    publish_path: str = ""
    host: str = "0.0.0.0"
    port: int = 8765
    public_url: str = ""
    enabled: bool = False
    title: str = "دستیار دانش بازرگانی GSI"

    @property
    def chatbot_path(self) -> str:
        return str(Path(self.publish_path) / "chatbot.html") if self.publish_path.strip() else ""

    @property
    def effective_public_url(self) -> str:
        if self.public_url.strip():
            return self.public_url.strip().rstrip("/")
        return f"http://{socket.gethostname()}:{int(self.port)}"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["public_url"] = self.effective_public_url
        return d


def load_config(path: Path = DEFAULT_CONFIG) -> KnowledgeDeskConfig:
    p = Path(path)
    if not p.exists():
        return KnowledgeDeskConfig()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        known = {k: raw.get(k) for k in KnowledgeDeskConfig.__dataclass_fields__ if k in raw}
        return KnowledgeDeskConfig(**known)
    except Exception:
        return KnowledgeDeskConfig()


def save_config(cfg: KnowledgeDeskConfig, path: Path = DEFAULT_CONFIG) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
