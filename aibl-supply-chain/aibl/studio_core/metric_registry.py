# -*- coding: utf-8 -*-
"""رجیستری معنایی سنجه‌ها — مرجع نوع، تجمیع، دانه و واحد.

اصل طراحی v26.16: نوع یک سنجه هرگز از «شکل مقادیر» حدس زده نمی‌شود.
عددی که یکتا و صحیح است ممکن است مبلغ واقعی باشد، نه شناسه. Registry ابتدا
exact rules و سپس الگوهای نام را اعمال می‌کند؛ fallback محافظه‌کارانه است.
"""
from __future__ import annotations

__contract__ = 1

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

import yaml

_CONFIG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "metrics.yaml")


@dataclass(frozen=True)
class MetricSpec:
    name: str
    kind: str = "additive"
    agg: str = "sum"
    grain: str = "AUTO"
    unit: str = ""
    description: str = ""
    source: str = "fallback"


@lru_cache(maxsize=1)
def _load() -> tuple[Dict[str, dict], List[tuple[re.Pattern, dict]]]:
    try:
        with open(_CONFIG, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception:
        raw = {}
    exact = {str(k): (v or {}) for k, v in (raw.get("exact") or {}).items()}
    patterns = []
    for row in raw.get("patterns") or []:
        try:
            patterns.append((re.compile(str(row.get("regex", "")), re.I), row))
        except re.error:
            continue
    return exact, patterns


def clear_cache() -> None:
    _load.cache_clear()


def metric_spec(column: str) -> MetricSpec:
    col = str(column)
    exact, patterns = _load()
    if col in exact:
        x = exact[col]
        return MetricSpec(col, str(x.get("kind", "additive")), str(x.get("agg", "sum")),
                          str(x.get("grain", "AUTO")), str(x.get("unit", "")),
                          str(x.get("description", "")), "exact")
    for rx, x in patterns:
        if rx.search(col):
            return MetricSpec(col, str(x.get("kind", "additive")), str(x.get("agg", "sum")),
                              str(x.get("grain", "AUTO")), str(x.get("unit", "")),
                              str(x.get("description", "")), "pattern")
    # مهم: fallback به additive است، ولی هیچ تحلیل آماری از مقدار انجام نمی‌شود.
    return MetricSpec(col, "additive", "sum", "AUTO", "", "", "fallback")
