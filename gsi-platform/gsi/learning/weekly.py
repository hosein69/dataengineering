# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "config" / "weekly_lessons.json"


def _default_lessons() -> List[Dict]:
    return [{
        "id": "gsi-week-01",
        "week": "هفته ۱",
        "title": "از داده تا تصمیم در زنجیره تأمین",
        "summary": "چطور Grain، کلید و کیفیت داده روی تصمیم مدیریتی اثر می‌گذارند.",
        "body": "هر عدد مدیریتی باید Grain مشخص، منبع قابل ردگیری و Rule قابل توضیح داشته باشد. Missing با Zero یکی نیست و Join بدون کنترل cardinality می‌تواند KPI را چندبرابر کند.",
        "questions": ["Grain چیست؟", "چرا Missing با Zero فرق دارد؟", "چطور از double-counting جلوگیری می‌کنیم؟"],
        "active": True,
        "start_date": str(date.today()),
    }]


def load_lessons(path: Path = DEFAULT_PATH) -> List[Dict]:
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        lessons = _default_lessons()
        path.write_text(json.dumps(lessons, ensure_ascii=False, indent=2), encoding="utf-8")
        return lessons
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else _default_lessons()
    except Exception:
        return _default_lessons()


def save_lessons(lessons: List[Dict], path: Path = DEFAULT_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(lessons, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def lesson_by_id(lesson_id: str, lessons: Optional[List[Dict]] = None) -> Optional[Dict]:
    for lesson in lessons or load_lessons():
        if str(lesson.get("id")) == str(lesson_id):
            return lesson
    return None


def current_lesson(on_date: Optional[date] = None, lessons: Optional[List[Dict]] = None) -> Optional[Dict]:
    lessons = lessons or load_lessons()
    active = [x for x in lessons if x.get("active", True)]
    if not active:
        return None
    d = on_date or date.today()
    eligible = []
    for item in active:
        try:
            sd = date.fromisoformat(str(item.get("start_date") or ""))
        except Exception:
            sd = date.min
        if sd <= d:
            eligible.append((sd, item))
    if eligible:
        return sorted(eligible, key=lambda x: x[0], reverse=True)[0][1]
    return active[0]
