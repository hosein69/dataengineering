# -*- coding: utf-8 -*-
"""بارگذار رجیستری سورس‌ها از ``sources.yaml``.

هیچ مسیر، الگو یا نام شیتی در کد پایتون نیست؛ همه از YAML می‌آید.
"""
from __future__ import annotations

#: نسخه قرارداد این ماژول — aibl/version.py آن را می‌سنجد.
#: با هر تغییر در رابط عمومی، این عدد یکی زیاد می‌شود.
__contract__ = 3


import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

from .settings import SETTINGS

_DEFAULT_YAML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.yaml")


def _yaml_path() -> str:
    """مسیر رجیستری — در هر بار فراخوانی از محیط خوانده می‌شود تا
    ``reload_sources()`` بتواند به فایل دیگری سوئیچ کند."""
    return os.environ.get("AIBL_SOURCES_YAML", _DEFAULT_YAML)

_PLACEHOLDERS = {
    "FOREIGN_DIR": SETTINGS.FOREIGN_DIR,
    "BLS_TOTAL_DIR": SETTINGS.BLS_TOTAL_DIR,
    "CLEARANCE_DIR": SETTINGS.CLEARANCE_DIR,
    "HR_DIR": SETTINGS.HR_DIR,
    "ESMAEILI_DIR": SETTINGS.ESMAEILI_DIR,
    "GS_COMBINE_OUT_DIR": SETTINGS.GS_COMBINE_OUT_DIR,
    "MOHAMADI_DIR": SETTINGS.MOHAMADI_DIR,
}


def _expand(value: str) -> str:
    out = str(value)
    for k, v in _PLACEHOLDERS.items():
        out = out.replace("${" + k + "}", v)
    return out


@dataclass(frozen=True)
class SourceSpec:
    """مشخصات یک سورس.

    ⚠️ قرارداد سازگاری رو به جلو: هر کلیدی که در sources.yaml باشد و اینجا
    فیلد صریح نداشته باشد، به ``extra`` می‌رود و با ``spec.opt("name")``
    قابل خواندن است. بنابراین افزودن یک کلید جدید به YAML **هرگز** نیازمند
    ویرایش این فایل نیست. این دقیقاً همان اتفاقی بود که با افزودن ``frames``
    رخ داد و باعث AttributeError شد.
    """
    key: str
    folder: str
    pattern: str
    sheets: List[Optional[str]]
    role: str = ""
    join_on: str = "BL"
    weight: float = 0.5
    multi_file: bool = False
    required: bool = False
    enabled: bool = True
    dedupe_by: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    frames: Dict[str, str] = field(default_factory=dict)
    notes: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def opt(self, name: str, default: Any = None) -> Any:
        """خواندن هر کلید YAML — چه فیلد صریح باشد چه نباشد."""
        if name in self.extra:
            return self.extra[name]
        return getattr(self, name, default)

    def frame_map(self) -> Dict[str, str]:
        """{نام فریم: کلید اتصال} — پیش‌فرض فقط فریم main با join_on."""
        frames = self.frames or self.extra.get("frames") or {}
        return dict(frames) if frames else {"main": self.join_on}

    @property
    def primary_sheet(self) -> Optional[str]:
        return self.sheets[0] if self.sheets else None


#: کلیدهایی که فیلد صریح دارند؛ بقیه به extra می‌روند.
_KNOWN_KEYS = {"folder", "pattern", "sheets", "role", "join_on", "weight",
               "multi_file", "required", "enabled", "dedupe_by", "aliases",
               "frames", "notes"}


def _load() -> tuple[Dict[str, SourceSpec], Dict[str, str], List[str]]:
    with open(_yaml_path(), "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    specs: Dict[str, SourceSpec] = {}
    aliases: Dict[str, str] = {}
    for key, cfg in (data.get("sources") or {}).items():
        if not cfg.get("enabled", True):
            continue
        spec = SourceSpec(
            key=key,
            folder=_expand(cfg.get("folder", "")),
            pattern=cfg.get("pattern", "*"),
            sheets=cfg.get("sheets", [None]),
            role=cfg.get("role", ""),
            join_on=cfg.get("join_on", "BL"),
            weight=float(cfg.get("weight", 0.5)),
            multi_file=bool(cfg.get("multi_file", False)),
            required=bool(cfg.get("required", False)),
            enabled=True,
            dedupe_by=cfg.get("dedupe_by"),
            aliases=list(cfg.get("aliases") or []),
            frames=dict(cfg.get("frames") or {}),
            notes=cfg.get("notes", ""),
            extra={k: v for k, v in cfg.items() if k not in _KNOWN_KEYS},
        )
        specs[key] = spec
        for a in spec.aliases:
            aliases[a] = key
    return specs, aliases, list(data.get("merge_order") or [])


SOURCES, SOURCE_ALIASES, MERGE_ORDER = _load()
SOURCE_WEIGHTS: Dict[str, float] = {k: v.weight for k, v in SOURCES.items()}


def get_source(key: str) -> SourceSpec:
    real = SOURCE_ALIASES.get(key, key)
    if real not in SOURCES:
        raise KeyError(f"سورس «{key}» در sources.yaml تعریف یا فعال نشده است.")
    return SOURCES[real]


def reload_sources() -> None:
    global SOURCES, SOURCE_ALIASES, MERGE_ORDER, SOURCE_WEIGHTS
    SOURCES, SOURCE_ALIASES, MERGE_ORDER = _load()
    SOURCE_WEIGHTS = {k: v.weight for k, v in SOURCES.items()}
