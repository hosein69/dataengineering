# -*- coding: utf-8 -*-
"""Small AnythingLLM API client.

Secrets stay server-side in environment variables.  Never embed an API key in
standalone HTML; HTML uses AnythingLLM's public embed widget configuration.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Dict, Optional
from urllib import request, error


@dataclass(frozen=True)
class AnythingLLMConfig:
    base_url: str = ""
    api_key: str = ""
    workspace_slug: str = ""
    embed_id: str = ""

    @classmethod
    def from_env(cls) -> "AnythingLLMConfig":
        return cls(
            base_url=os.getenv("ANYTHINGLLM_BASE_URL", "").rstrip("/"),
            api_key=os.getenv("ANYTHINGLLM_API_KEY", "").strip(),
            workspace_slug=os.getenv("ANYTHINGLLM_WORKSPACE_SLUG", "").strip(),
            embed_id=os.getenv("ANYTHINGLLM_EMBED_ID", "").strip(),
        )

    @property
    def api_ready(self) -> bool:
        return bool(self.base_url and self.api_key and self.workspace_slug)

    @property
    def embed_ready(self) -> bool:
        return bool(self.base_url and self.embed_id)

    def public_embed(self) -> Dict[str, str]:
        # Intentionally excludes api_key.
        return {"base_url": self.base_url, "embed_id": self.embed_id} if self.embed_ready else {}


class AnythingLLMClient:
    def __init__(self, cfg: Optional[AnythingLLMConfig] = None, timeout: int = 60):
        self.cfg = cfg or AnythingLLMConfig.from_env()
        self.timeout = timeout

    def _call(self, method: str, path: str, payload: Optional[Dict] = None) -> Dict:
        if not self.cfg.base_url or not self.cfg.api_key:
            raise RuntimeError("AnythingLLM تنظیم نشده است: BASE_URL/API_KEY لازم است.")
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.cfg.base_url}{path}", data=body, method=method,
            headers={"Authorization": f"Bearer {self.cfg.api_key}", "Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else {}
        except error.HTTPError as ex:
            msg = ex.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"AnythingLLM HTTP {ex.code}: {msg[:500]}") from ex
        except Exception as ex:
            raise RuntimeError(f"AnythingLLM connection failed: {ex}") from ex

    def health(self) -> Dict:
        return self._call("GET", "/api/v1/workspaces")

    def ask(self, question: str, lesson: Optional[Dict] = None, mode: str = "chat") -> Dict:
        """Raw API response. Neither query mode nor citations prove correctness.

        Use ask_evidence() for fail-closed presentation of cited answers.
        The optional public embed is managed independently by AnythingLLM.
        """
        if not self.cfg.workspace_slug:
            raise RuntimeError("ANYTHINGLLM_WORKSPACE_SLUG تنظیم نشده است.")
        message = question.strip()
        if lesson:
            context = "\n".join([
                f"عنوان آموزش: {lesson.get('title','')}",
                f"خلاصه: {lesson.get('summary','')}",
                f"متن آموزش:\n{lesson.get('body','')}",
            ])
            message = (
                "به سؤال زیر فقط بر اساس آموزش هفتگی و دانش موجود در Workspace پاسخ بده. "
                "اگر پاسخ از متن/منابع قابل استنتاج نیست صریح بگو.\n\n"
                + context + "\n\nسؤال کاربر: " + question.strip()
            )
        data = self._call("POST", f"/api/v1/workspace/{self.cfg.workspace_slug}/chat",
                          {"message": message, "mode": mode})
        return data

    def ask_evidence(self, question: str, lesson: Optional[Dict] = None) -> Dict:
        """Request retrieval and withhold text when citation metadata is absent.

        Citation presence is a transport check, not factual/financial validation.
        This method does not execute tools, send messages, or mutate the DWH.
        """
        data = self.ask(question, lesson=lesson, mode="query")
        if not self.has_sources(data):
            return {"status":"INSUFFICIENT_EVIDENCE",
                    "answer":"برای پاسخ قابل‌استناد، منبع کافی در پاسخ سرویس موجود نیست.",
                    "sources":[], "verified":False}
        sources = next(data[k] for k in ("sources","citations","sourceDocuments")
                       if self._valid_sources(data.get(k)))
        return {"status":"CITATIONS_PRESENT", "answer":self.answer_text(data),
                "sources":sources, "verified":False}

    @staticmethod
    def _valid_sources(value) -> bool:
        return isinstance(value, list) and any(
            (isinstance(x, str) and bool(x.strip())) or
            (isinstance(x, dict) and any(x.get(k) for k in
             ("id","title","url","source","text","pageContent"))) for x in value)

    @staticmethod
    def has_sources(data: Dict) -> bool:
        """True when the answer carried workspace citations.

        Without this, nothing in the pipeline distinguishes a grounded answer
        from one the model produced on its own - the instruction in ``ask`` is
        the only guarantee, and nothing checks it.
        """
        for key in ("sources", "citations", "sourceDocuments"):
            val = data.get(key)
            if AnythingLLMClient._valid_sources(val):
                return True
        return False

    @staticmethod
    def answer_text(data: Dict) -> str:
        for key in ("textResponse", "response", "text", "message"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return json.dumps(data, ensure_ascii=False, indent=2)[:6000]
