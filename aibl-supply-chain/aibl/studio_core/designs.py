# -*- coding: utf-8 -*-
"""ذخیره و بازیابی «طرح گزارش» برای AIBL Studio.

طرح فقط تنظیمات گزارش است، نه داده حساس. به‌صورت JSON ذخیره می‌شود:
قالب، فیلدها، تب‌های HTML/Excel و نمودارهای ایمیل.
"""
from __future__ import annotations
__contract__ = 2

import json, os, re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_DESIGNS_DIR = Path(
    os.environ.get("AIBL_DESIGNS", str(Path.home() / ".aibl" / "designs"))
)

@dataclass
class ReportDesign:
    name: str
    template: str = "executive"
    fields: List[str] = field(default_factory=list)
    tabs: List[Dict[str, Any]] = field(default_factory=list)
    formats: List[str] = field(default_factory=lambda: ["excel", "html", "pdf"])
    visuals: bool = True
    tables: bool = True
    max_rows: int = 5000
    file_stem: str = "AIBL Report"
    html_charts: List[str] = field(default_factory=list)
    email_charts: List[str] = field(default_factory=list)
    email_to: str = ""
    email_cc: str = ""
    email_subject: str = ""
    email_header: str = ""
    email_intro: str = ""
    title: str = "AIBL"

def designs_dir() -> Path:
    p = Path(os.environ.get("AIBL_DESIGNS", str(DEFAULT_DESIGNS_DIR))).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p

def _safe_name(name: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', "_", str(name).strip())
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:120] or "گزارش"

def path_for(name: str) -> Path:
    return designs_dir() / f"{_safe_name(name)}.json"

def save_design(design: ReportDesign | Dict[str, Any]) -> Path:
    if isinstance(design, dict):
        design = ReportDesign(**design)
    p = path_for(design.name)
    payload = asdict(design)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p

def load_design(name: str) -> ReportDesign:
    p = path_for(name)
    data = json.loads(p.read_text(encoding="utf-8"))
    return ReportDesign(**data)

def list_designs() -> List[str]:
    return sorted(p.stem for p in designs_dir().glob("*.json"))

def delete_design(name: str) -> bool:
    p = path_for(name)
    if not p.exists():
        return False
    p.unlink()
    return True


# کاتالوگ نمودار مشترک HTML / Email / Excel.
# alias قدیمی برای سازگاری با افزونه‌ها و طرح‌های ذخیره‌شده حفظ شده است.
from .chart_catalog import CHART_TITLES as EMAIL_CHARTS

# سازگاری مستندات قدیمی: «وضعیت بحرانی متریال — توزیع» اکنون در chart_catalog.py با عنوان دقیق‌تر نگهداری می‌شود.
