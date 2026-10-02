"""Lightweight weekly learning + AnythingLLM integration for GSI."""
from .weekly import load_lessons, save_lessons, current_lesson, lesson_by_id
from .anythingllm import AnythingLLMClient, AnythingLLMConfig

__all__ = ["load_lessons", "save_lessons", "current_lesson", "lesson_by_id", "AnythingLLMClient", "AnythingLLMConfig"]
