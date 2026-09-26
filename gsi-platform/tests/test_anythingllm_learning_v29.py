from __future__ import annotations

import os
import pandas as pd

from gsi.learning.anythingllm import AnythingLLMConfig
from gsi.studio_core.html_export import build_dynamic_html


def test_public_embed_never_exposes_api_key(monkeypatch):
    monkeypatch.setenv("ANYTHINGLLM_BASE_URL", "http://localhost:3001")
    monkeypatch.setenv("ANYTHINGLLM_API_KEY", "SECRET-DO-NOT-EMBED")
    monkeypatch.setenv("ANYTHINGLLM_WORKSPACE_SLUG", "gsi-academy")
    monkeypatch.setenv("ANYTHINGLLM_EMBED_ID", "embed-123")
    cfg = AnythingLLMConfig.from_env()
    public = cfg.public_embed()
    assert public == {"base_url": "http://localhost:3001", "embed_id": "embed-123"}
    assert "SECRET" not in repr(public)


def test_html_weekly_lesson_and_embed_are_optional_and_safe():
    df = pd.DataFrame([{"KEY_MATERIAL": "M1", "مقاومت (روز)": 12.0}])
    lesson = {
        "id": "w1", "week": "هفته ۱", "title": "Grain و کلید",
        "summary": "آموزش کوتاه", "body": "Order + Material همیشه کلید قطعی نیست.",
        "questions": ["Grain چیست؟"],
    }
    html = build_dynamic_html(
        df, "2026-09-21", selected_fields=["KEY_MATERIAL", "مقاومت (روز)"],
        tabs=[{"id":"t1","title":"اصلی","fields":["KEY_MATERIAL","مقاومت (روز)"],"blocks":["table"],"charts":[]}],
        learning_lesson=lesson,
        anythingllm_embed={"base_url":"http://localhost:3001","embed_id":"embed-123"},
    )
    assert "Grain و کلید" in html
    assert "Grain چیست؟" in html
    assert 'data-embed-id="embed-123"' in html
    assert 'data-base-api-url="http://localhost:3001/api/embed"' in html
    assert "ANYTHINGLLM_API_KEY" not in html
    assert "SECRET" not in html


def test_html_without_embed_stays_offline_for_qa():
    df = pd.DataFrame([{"KEY_MATERIAL": "M1"}])
    html = build_dynamic_html(
        df, "2026-09-21", selected_fields=["KEY_MATERIAL"],
        tabs=[{"id":"t1","title":"اصلی","fields":["KEY_MATERIAL"],"blocks":["table"],"charts":[]}],
        learning_lesson={"title":"درس","body":"متن","questions":[]},
        anythingllm_embed={},
    )
    assert "چت‌بات در این فایل هنوز فعال نیست" in html
    assert "anythingllm-chat-widget.min.js" not in html
