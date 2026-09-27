# -*- coding: utf-8 -*-
"""کشف خودکار adapterها.

افزودن یک سورس جدید = ساختن یک فایل .py در همین پوشه با کلاسی که از
``SourceAdapter`` ارث می‌برد و با ``@register`` علامت‌گذاری شده است.
حذف یک سورس = حذف همان فایل. هیچ فایل دیگری نیاز به ویرایش ندارد.
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Dict, Type

from .base import REGISTRY, SourceAdapter, register  # noqa: F401

_SKIP = {"base"}


def discover() -> Dict[str, Type[SourceAdapter]]:
    """تمام ماژول‌های این پکیج را import می‌کند تا @register اجرا شود."""
    for mod in pkgutil.iter_modules(__path__):
        if mod.name.startswith("_") or mod.name in _SKIP:
            continue
        importlib.import_module(f"{__name__}.{mod.name}")
    return REGISTRY


__all__ = ["REGISTRY", "SourceAdapter", "register", "discover"]
