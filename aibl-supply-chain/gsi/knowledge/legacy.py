# -*- coding: utf-8 -*-
"""مدل دانش قدیمی و گارد حاکمیتی انتقال تجربه.

این ماژول یک اصل را enforce می‌کند: «دانش تاریخی» هرچقدر هم مفید باشد،
بدون ترفیع صریح به منبع رسمی/تأییدشده، Rule الزام‌آور امروز نیست.

منابع V26.19 شامل گزارش قدیمی OF، فایل‌های BL/NTSW/ZMM58/Rates/ETS/Append،
Notebook قدیمی و PDF «نکات رفع تعهد» هستند. محتوا به اشیای versioned و
قابل ممیزی تبدیل می‌شود؛ فرمول/مهلت قدیمی مستقیماً به موتور قانونی تزریق
نمی‌شود.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence


LEGACY_SOURCE_CLASSES = {"legacy_internal", "legacy_training", "legacy_code"}
BINDING_SOURCE_CLASSES = {"official_binding", "official_operational"}


def _text(v: Any) -> str:
    return "" if v is None else str(v).strip()


@dataclass(frozen=True)
class LegacyKnowledgeItem:
    id: str
    kind: str
    title: str
    description: str = ""
    source_id: str = ""
    source_class: str = "legacy_internal"
    source_date: str = ""
    source_location: str = ""
    status: str = "legacy_reference"
    binding: bool = False
    confidence: str = "medium"
    effective_from: str = ""
    effective_to: str = ""
    tags: Sequence[str] = field(default_factory=tuple)
    patterns: Sequence[str] = field(default_factory=tuple)
    evidence_requirements: Sequence[str] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LegacyKnowledgeItem":
        known = {
            "id", "kind", "title", "description", "source_id", "source_class",
            "source_date", "source_location", "status", "binding", "confidence",
            "effective_from", "effective_to", "tags", "patterns",
            "evidence_requirements",
        }
        return cls(
            id=_text(d.get("id")), kind=_text(d.get("kind")),
            title=_text(d.get("title")), description=_text(d.get("description")),
            source_id=_text(d.get("source_id")),
            source_class=_text(d.get("source_class") or "legacy_internal"),
            source_date=_text(d.get("source_date")),
            source_location=_text(d.get("source_location")),
            status=_text(d.get("status") or "legacy_reference"),
            binding=bool(d.get("binding", False)),
            confidence=_text(d.get("confidence") or "medium"),
            effective_from=_text(d.get("effective_from")),
            effective_to=_text(d.get("effective_to")),
            tags=tuple(d.get("tags") or ()), patterns=tuple(d.get("patterns") or ()),
            evidence_requirements=tuple(d.get("evidence_requirements") or ()),
            metadata={k: v for k, v in d.items() if k not in known},
        )


def can_auto_enforce(item: LegacyKnowledgeItem) -> bool:
    """فقط قاعده تأییدشده با کلاس منبع رسمی اجازه enforce خودکار دارد.

    حتی اگر فایل قدیمی به اشتباه ``binding: true`` داشته باشد، source_class
    legacy آن را fail-closed نگه می‌دارد.
    """
    return bool(
        item.binding
        and item.status == "verified"
        and item.source_class in BINDING_SOURCE_CLASSES
    )


class LegacyKnowledgeCatalog:
    def __init__(self, items: Iterable[LegacyKnowledgeItem],
                 sources: Optional[List[Dict[str, Any]]] = None,
                 rate_semantics: Optional[List[Dict[str, Any]]] = None,
                 promotion_policy: Optional[Dict[str, Any]] = None) -> None:
        self.items = list(items)
        self.sources = list(sources or [])
        self.rate_semantics = list(rate_semantics or [])
        self.promotion_policy = dict(promotion_policy or {})
        self._by_id = {x.id: x for x in self.items}

    def get(self, item_id: str) -> Optional[LegacyKnowledgeItem]:
        return self._by_id.get(str(item_id))

    def by_kind(self, kind: str) -> List[LegacyKnowledgeItem]:
        return [x for x in self.items if x.kind == kind]

    def match_text(self, text: Any, kinds: Optional[Sequence[str]] = None) -> List[LegacyKnowledgeItem]:
        """کاندیدهای دانش را از روی متن برمی‌گرداند؛ «تشخیص قطعی» نیست."""
        s = _text(text).lower()
        if not s:
            return []
        allowed = set(kinds or ())
        out: List[LegacyKnowledgeItem] = []
        for item in self.items:
            if allowed and item.kind not in allowed:
                continue
            if any(_text(p).lower() in s for p in item.patterns if _text(p)):
                out.append(item)
        return out

    def evidence_for(self, item_ids: Iterable[str]) -> List[str]:
        seen: List[str] = []
        for item_id in item_ids:
            item = self.get(item_id)
            if not item:
                continue
            for ev in item.evidence_requirements:
                if ev and ev not in seen:
                    seen.append(ev)
        return seen

    def rows(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for x in self.items:
            rows.append({
                "KNOWLEDGE_ID": x.id,
                "KIND": x.kind,
                "TITLE": x.title,
                "DESCRIPTION": x.description,
                "SOURCE_ID": x.source_id,
                "SOURCE_CLASS": x.source_class,
                "SOURCE_DATE": x.source_date,
                "SOURCE_LOCATION": x.source_location,
                "STATUS": x.status,
                "BINDING": x.binding,
                "AUTO_ENFORCE": can_auto_enforce(x),
                "CONFIDENCE": x.confidence,
                "EFFECTIVE_FROM": x.effective_from,
                "EFFECTIVE_TO": x.effective_to,
                "TAGS": " | ".join(map(str, x.tags)),
                "EVIDENCE_REQUIREMENTS": " | ".join(map(str, x.evidence_requirements)),
            })
        return rows


def load_legacy_catalog(rb: Any) -> LegacyKnowledgeCatalog:
    pack = rb.pack("legacy_knowledge") if hasattr(rb, "pack") else {}
    items = [LegacyKnowledgeItem.from_dict(x) for x in (pack.get("items") or [])]
    return LegacyKnowledgeCatalog(
        items,
        sources=pack.get("sources") or [],
        rate_semantics=pack.get("rate_semantics") or [],
        promotion_policy=pack.get("promotion_policy") or {},
    )
