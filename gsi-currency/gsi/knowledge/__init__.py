# -*- coding: utf-8 -*-
"""دانش انتقال‌یافته از منابع قدیمی — فقط مرجع، نه قانون جاری."""
from .legacy import (LegacyKnowledgeCatalog, LegacyKnowledgeItem,
                     can_auto_enforce, load_legacy_catalog)

__all__ = [
    "LegacyKnowledgeCatalog", "LegacyKnowledgeItem",
    "can_auto_enforce", "load_legacy_catalog",
]
