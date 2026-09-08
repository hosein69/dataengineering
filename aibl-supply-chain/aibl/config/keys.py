# -*- coding: utf-8 -*-
"""رجیستری کلیدها — بارگذار ``config/keys.yaml``.

هر «کلید منطقی» (BL، ORDER، REG، MATERIAL، PR، EMP) اینجا تعریف می‌شود:
از کدام سورس‌ها ساخته شود، با چه تابعی نرمال شود، و چه الگویی معتبر است.
کلیدهای مرکب (دو یا چند جزء) هم پشتیبانی می‌شوند.

بنابراین «تغییر کلید یک جدول» یا «استفاده از دو کلید» فقط ویرایش YAML است.
"""
from __future__ import annotations

__contract__ = 1

import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
import yaml

from ..core.text import (clean_bl, clean_employee_code, clean_key,
                         clean_order_ref, clean_part_no, is_empty_val)
from ..dataio.logging_setup import log

_DEFAULT_YAML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.yaml")

#: توابع نرمال‌سازی مجاز — نام YAML → تابع
NORMALIZERS: Dict[str, Callable[[Any], str]] = {
    "clean_bl": clean_bl,
    "clean_key": clean_key,
    "clean_order_ref": clean_order_ref,
    "clean_part_no": clean_part_no,
    "clean_employee_code": clean_employee_code,
    "passthrough": lambda v: "" if is_empty_val(v) else str(v).strip(),
}


def _yaml_path() -> str:
    return os.environ.get("AIBL_KEYS_YAML", _DEFAULT_YAML)


@dataclass(frozen=True)
class KeySpec:
    name: str
    column: str
    fa: str = ""
    normalizer: str = "clean_key"
    pattern: Optional[str] = None
    min_length: int = 0
    sources: List[Dict[str, str]] = field(default_factory=list)
    forbidden_columns: List[str] = field(default_factory=list)
    #: اجزای کلید مرکب — خالی یعنی کلید ساده
    parts: List[str] = field(default_factory=list)
    separator: str = "|"

    @property
    def is_composite(self) -> bool:
        return bool(self.parts)

    def normalize(self, value: Any) -> str:
        fn = NORMALIZERS.get(self.normalizer, NORMALIZERS["clean_key"])
        return fn(value)

    def is_valid(self, value: str) -> bool:
        if not value:
            return False
        if self.min_length and len(value) < self.min_length:
            return False
        if self.pattern and not re.match(self.pattern, value):
            return False
        return True


class KeyRegistry:
    """تنها مرجع تعریف کلیدها."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or _yaml_path()
        self.keys: Dict[str, KeySpec] = {}
        self.policy: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        with open(self.path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for name, cfg in (data.get("keys") or {}).items():
            self.keys[name] = KeySpec(
                name=name,
                column=cfg.get("column", f"KEY_{name}"),
                fa=cfg.get("fa", name),
                normalizer=cfg.get("normalizer", "clean_key"),
                pattern=cfg.get("pattern"),
                min_length=int(cfg.get("min_length", 0)),
                sources=list(cfg.get("sources") or []),
                forbidden_columns=list(cfg.get("forbidden_columns") or []),
            )
        for name, cfg in (data.get("composite_keys") or {}).items():
            self.keys[name] = KeySpec(
                name=name,
                column=cfg.get("column", f"KEY_{name}"),
                fa=cfg.get("fa", name),
                parts=list(cfg.get("parts") or []),
                separator=cfg.get("separator", "|"),
            )
        self.policy = dict(data.get("merge_policy") or {})

    # ═══════ دسترسی ═══════
    def get(self, name: str) -> KeySpec:
        if name not in self.keys:
            raise KeyError(
                f"کلید «{name}» در config/keys.yaml تعریف نشده است. "
                f"کلیدهای موجود: {sorted(self.keys)}")
        return self.keys[name]

    def column_of(self, name: str) -> str:
        return self.get(name).column

    def simple_keys(self) -> List[str]:
        return [k for k, v in self.keys.items() if not v.is_composite]

    def composite_keys(self) -> List[str]:
        return [k for k, v in self.keys.items() if v.is_composite]

    # ═══════ ساخت ستون کلید روی یک DataFrame ═══════
    def build(self, df: pd.DataFrame, name: str,
              sources: Optional[Dict[str, pd.DataFrame]] = None) -> pd.DataFrame:
        """ستون کلید را می‌سازد و به df اضافه می‌کند.

        برای کلید ساده: نخستین ستون تعریف‌شده در ``sources`` که در df موجود و
        غیرتهی باشد، نرمال و اعتبارسنجی می‌شود.
        برای کلید مرکب: اجزا ساخته و با ``separator`` به هم چسبانده می‌شوند.
        """
        spec = self.get(name)
        if spec.is_composite:
            return self._build_composite(df, spec)
        return self._build_simple(df, spec)

    def _build_simple(self, df: pd.DataFrame, spec: KeySpec) -> pd.DataFrame:
        out = pd.Series([""] * len(df), index=df.index, dtype="object")
        used: List[str] = []
        for src in spec.sources:
            col = src.get("column")
            if not col or col not in df.columns:
                continue
            if col in spec.forbidden_columns:
                log.error(f"❌ [{spec.name}] ستون «{col}» در فهرست ممنوعه است "
                          f"و به‌عنوان کلید استفاده نشد.")
                continue
            need = out.map(lambda v: not v)
            if not need.any():
                break
            vals = df.loc[need, col].map(spec.normalize)
            vals = vals.map(lambda v: v if spec.is_valid(v) else "")
            if vals.astype(str).str.strip().ne("").any():
                out.loc[need] = vals
                used.append(f"{src.get('source', '?')}.{col}")
        df[spec.column] = out
        n = int(out.astype(str).str.strip().ne("").sum())
        log.info(f"   🔑 [{spec.name}] {spec.fa}: {n} از {len(df)} ردیف "
                 f"({out.nunique()} مقدار یکتا) — منابع: {' → '.join(used) or 'هیچ'}")
        return df

    def _build_composite(self, df: pd.DataFrame, spec: KeySpec) -> pd.DataFrame:
        cols: List[str] = []
        for part in spec.parts:
            if part in self.keys:
                pcol = self.get(part).column
                if pcol not in df.columns:
                    df = self.build(df, part)
                cols.append(pcol)
            elif part in df.columns:
                cols.append(part)       # ستون خام، نه کلید تعریف‌شده
            else:
                log.warning(f"⚠️ [{spec.name}] جزء «{part}» در داده نیست؛ "
                            f"کلید مرکب ناقص ساخته می‌شود.")
        if not cols:
            df[spec.column] = ""
            return df
        joined = df[cols[0]].astype(str)
        for c in cols[1:]:
            joined = joined + spec.separator + df[c].astype(str)
        # اگر همه اجزا تهی باشند، کلید هم باید تهی باشد
        all_empty = df[cols].apply(
            lambda r: all(is_empty_val(x) for x in r), axis=1)
        df[spec.column] = joined.where(~all_empty, "")
        n = int(df[spec.column].astype(str).str.strip().ne("").sum())
        log.info(f"   🔗 [{spec.name}] کلید مرکب {' + '.join(spec.parts)}: "
                 f"{n} ردیف، {df[spec.column].nunique()} ترکیب یکتا")
        return df

    # ═══════ اعتبارسنجی ═══════
    def validate(self) -> List[str]:
        issues: List[str] = []
        for name, spec in self.keys.items():
            if spec.is_composite:
                for p in spec.parts:
                    if p not in self.keys:
                        issues.append(f"کلید مرکب «{name}»: جزء «{p}» تعریف نشده "
                                      f"(اگر ستون خام است، اشکالی ندارد).")
                continue
            if spec.normalizer not in NORMALIZERS:
                issues.append(f"کلید «{name}»: تابع نرمال‌سازی «{spec.normalizer}» "
                              f"وجود ندارد. مجازها: {sorted(NORMALIZERS)}")
            if spec.pattern:
                try:
                    re.compile(spec.pattern)
                except re.error as ex:
                    issues.append(f"کلید «{name}»: الگوی نامعتبر — {ex}")
            if not spec.sources:
                issues.append(f"کلید «{name}»: هیچ سورسی تعریف نشده است.")
        return issues

    def summary(self) -> pd.DataFrame:
        rows = []
        for name, s in self.keys.items():
            rows.append({
                "کلید": name, "شرح": s.fa, "ستون": s.column,
                "نوع": "مرکب" if s.is_composite else "ساده",
                "اجزا / منابع": (" + ".join(s.parts) if s.is_composite else
                                  " → ".join(f"{x.get('source')}.{x.get('column')}"
                                             for x in s.sources)),
                "الگو": s.pattern or "—",
                "نرمال‌ساز": "—" if s.is_composite else s.normalizer,
            })
        return pd.DataFrame(rows)


_REGISTRY: Optional[KeyRegistry] = None


def get_keys(reload: bool = False) -> KeyRegistry:
    global _REGISTRY
    if _REGISTRY is None or reload:
        _REGISTRY = KeyRegistry()
    return _REGISTRY
