# -*- coding: utf-8 -*-
"""قرارداد مرحله‌های خط لوله — قلب طراحی «هر تغییر، یک فایل».

## مسئله‌ای که این لایه حل می‌کند

تا نسخه ۲۲، افزودن یک قابلیت (مثلاً «مقاومت قطعه») سه فایل را عوض می‌کرد:
موتور جدید + ``pipeline.py`` برای صدا زدنش + ``dashboard.py`` برای نمایش
ستون‌هایش. هر اصلاح هم همین‌طور. نتیجه: اختلاف نسخه فایل‌ها و خطاهایی مثل
``AttributeError: 'SourceSpec' object has no attribute 'frame_map'``.

## راه‌حل

هر مرحله یک فایل مستقل در ``aibl/stages/`` است که سه چیز را خودش اعلام می‌کند:

    requires   ستون‌هایی که برای اجرا لازم دارد   (شرط علّی ورودی)
    provides   ستون‌هایی که تولید می‌کند          (اثر علّی خروجی)
    columns    ستون‌هایی که باید در گزارش بیایند  (نمایش)

خط لوله پیش از اجرا، گراف علّی این وابستگی‌ها را می‌سازد و **اگر مرحله‌ای
ستونی بخواهد که هیچ مرحله قبلی تولید نمی‌کند، پیش از خواندن حتی یک فایل
اکسل با پیام صریح متوقف می‌شود.** این همان رویکرد conformance checking است:
مدل فرآیند اعلام‌شده با اجرای واقعی تطبیق داده می‌شود.

نتیجه عملی:
    افزودن قابلیت  = یک فایل جدید در stages/
    حذف قابلیت     = حذف همان فایل (یا enabled = False)
    اصلاح قابلیت   = ویرایش همان یک فایل
    هیچ‌کدام pipeline.py یا dashboard.py را لمس نمی‌کنند.
"""
from __future__ import annotations

#: نسخه قرارداد این ماژول — aibl/version.py آن را می‌سنجد.
__contract__ = 1

import importlib
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Type

import pandas as pd

from ..dataio.logging_setup import log

# ═══════════════════════════════════════════════════════════════════════════
#  ستون گزارش — هر مرحله ستون‌های خودش را معرفی می‌کند
# ═══════════════════════════════════════════════════════════════════════════
GROUP_MAIN = 0      # همیشه دیده می‌شود
GROUP_DETAIL = 1    # لایه دوم آکاردئون
GROUP_ANALYTIC = 2  # لایه سوم آکاردئون

FMT_TEXT = "text"
FMT_INT = "int"
FMT_DECIMAL = "decimal"
FMT_CURRENCY = "currency"


@dataclass(frozen=True)
class ColumnSpec:
    """معرفی یک ستون گزارش توسط مرحله سازنده‌اش."""
    key: str                      # نام ستون در DataFrame
    title: str                    # عنوان فارسی در اکسل
    width: int = 18
    group: int = GROUP_MAIN
    fmt: str = FMT_TEXT
    wrap: bool = False
    order: int = 100              # کوچک‌تر = چپ‌تر (در RTL: راست‌تر)
    color_rule: Optional[str] = None   # none | scale_low_bad | scale_high_bad | flag_nonempty


# ═══════════════════════════════════════════════════════════════════════════
#  زمینه اجرا — هر چیزی که مرحله‌ها ممکن است لازم داشته باشند
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class PipelineContext:
    rb: Any                                  # RuleBook
    today: date
    sources: Dict[str, Dict[str, pd.DataFrame]] = field(default_factory=dict)
    resolver: Any = None
    extras: Dict[str, Any] = field(default_factory=dict)

    def sheet(self, source: str, frame: str = "main") -> Optional[pd.DataFrame]:
        return self.sources.get(source, {}).get(frame)


# ═══════════════════════════════════════════════════════════════════════════
#  قرارداد مرحله
# ═══════════════════════════════════════════════════════════════════════════
class Stage(ABC):
    """یک گام از فرآیند. ترتیب اجرا با ``order`` تعیین می‌شود."""

    name: str = ""
    title: str = ""
    order: int = 100
    enabled: bool = True

    #: ستون‌های ورودی لازم. اگر تولید نشده باشند، اجرا متوقف می‌شود.
    requires: List[str] = []
    #: ستون‌های تولیدی. مبنای اعتبارسنجی گراف و مستندسازی.
    provides: List[str] = []
    #: اگر True، نبود ستون‌های requires فقط هشدار است نه خطا.
    tolerant: bool = False

    @abstractmethod
    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        ...

    def columns(self) -> List[ColumnSpec]:
        """ستون‌های گزارش که این مرحله مسئول آن‌هاست."""
        return []

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        """KPIهای خلاصه اجرایی که این مرحله تولید می‌کند: {عنوان: (مقدار, شرح)}."""
        return {}

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict[str, Any]]:
        """مستندسازی مدل ریاضی این مرحله برای شیت «پشتیبان ریاضی».

        هر مرحله فرمول و پارامترهای خودش را معرفی می‌کند تا ارکستراتور
        هیچ دانش کسب‌وکاری نداشته باشد.
        """
        return {}

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Stage {self.order}:{self.name}>"


REGISTRY: Dict[str, Type[Stage]] = {}


def register(cls: Type[Stage]) -> Type[Stage]:
    if not cls.name:
        raise ValueError(f"مرحله {cls.__name__} فیلد name ندارد.")
    if cls.name in REGISTRY:
        raise ValueError(f"مرحله تکراری «{cls.name}» — دو فایل هم‌نام در stages/؟")
    REGISTRY[cls.name] = cls
    return cls


def discover(package: str = "aibl.stages") -> List[Stage]:
    """کشف خودکار همه مرحله‌ها و برگرداندن نمونه‌های مرتب‌شده."""
    pkg = importlib.import_module(package)
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name.startswith("_") or mod.name == "base":
            continue
        importlib.import_module(f"{package}.{mod.name}")
    stages = [cls() for cls in REGISTRY.values() if cls.enabled]
    return sorted(stages, key=lambda s: s.order)


# ═══════════════════════════════════════════════════════════════════════════
#  اعتبارسنجی گراف علّی — پیش از خواندن هر داده‌ای
# ═══════════════════════════════════════════════════════════════════════════
class StageContractError(RuntimeError):
    """وقتی زنجیره علّی مرحله‌ها ناقص است."""


def validate_graph(stages: List[Stage], base_columns: List[str]) -> List[str]:
    """بررسی می‌کند هر ستون requires توسط مرحله‌ای قبل‌تر یا جدول پایه تولید شود.

    خروجی: فهرست هشدارها. خطاهای قطعی استثنا می‌دهند.
    """
    available = set(base_columns)
    warnings: List[str] = []
    seen_orders: Dict[int, str] = {}

    for st in stages:
        if st.order in seen_orders:
            warnings.append(
                f"دو مرحله با ترتیب یکسان {st.order}: «{seen_orders[st.order]}» و «{st.name}» "
                f"— ترتیب اجرا قطعی نیست.")
        seen_orders[st.order] = st.name

        missing = [c for c in st.requires if c not in available]
        if missing:
            producer_hint = {}
            for other in stages:
                for c in missing:
                    if c in other.provides:
                        producer_hint[c] = f"{other.name} (ترتیب {other.order})"
            msg = (f"مرحله «{st.name}» (ترتیب {st.order}) به ستون‌های {missing} نیاز دارد "
                   f"که تا این نقطه تولید نشده‌اند.")
            if producer_hint:
                msg += (" این ستون‌ها را مرحله‌های بعدی تولید می‌کنند: "
                        + "، ".join(f"{c} ← {p}" for c, p in producer_hint.items())
                        + " ⇒ ترتیب (order) مرحله‌ها را اصلاح کنید.")
            else:
                msg += " هیچ مرحله‌ای این ستون‌ها را تولید نمی‌کند."
            if st.tolerant:
                warnings.append(msg)
            else:
                raise StageContractError(msg)
        available.update(st.provides)

    return warnings


def collect_columns(stages: List[Stage]) -> List[ColumnSpec]:
    """ستون‌های گزارش همه مرحله‌ها، مرتب‌شده و بدون تکرار."""
    seen: Dict[str, ColumnSpec] = {}
    for st in stages:
        for col in st.columns():
            if col.key not in seen:
                seen[col.key] = col
    return sorted(seen.values(), key=lambda c: (c.order, c.title))


def describe(stages: List[Stage]) -> pd.DataFrame:
    """مستندسازی خودکار فرآیند — برای شیت «نقشه فرآیند»."""
    rows = []
    for st in stages:
        rows.append({
            "ترتیب": st.order,
            "مرحله": st.name,
            "عنوان": st.title or st.name,
            "ورودی لازم": "، ".join(st.requires) or "—",
            "خروجی تولیدی": "، ".join(st.provides) or "—",
            "ستون‌های گزارش": len(st.columns()),
        })
    return pd.DataFrame(rows)


def log_plan(stages: List[Stage]) -> None:
    log.info("🗺️ نقشه اجرای فرآیند:")
    for st in stages:
        log.info(f"   {st.order:>3} │ {st.name:<16} │ {st.title}")
