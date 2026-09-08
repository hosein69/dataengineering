# -*- coding: utf-8 -*-
"""قرارداد پایه adapterها.

هر سورس دقیقاً یک adapter دارد که:
  ۱. فایل و شیت خود را می‌خواند،
  ۲. ستون‌های خام را با ``find_col`` پیدا می‌کند،
  ۳. آن‌ها را به نام‌های **استاندارد و صریح** (با پیشوند سورس) rename می‌کند،
  ۴. کلید اتصال (KEY_BL / KEY_ORDER / KEY_REG / KEY_EMP) را می‌سازد.

نتیجه: pipeline هرگز نام ستون خام یا suffix خودکار pandas را نمی‌بیند.
افزودن سورس شانزدهم = یک فایل جدید + یک خط در REGISTRY.
"""
from __future__ import annotations

#: نسخه قرارداد این ماژول — aibl/version.py آن را می‌سنجد.
#: با هر تغییر در رابط عمومی، این عدد یکی زیاد می‌شود.
__contract__ = 3


import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type

import pandas as pd

from ..config.sources import SourceSpec, get_source
from ..core.columns import find_col
from ..core.text import clean_bl, clean_employee_code, clean_key, clean_part_no
from ..dataio.logging_setup import log
from ..dataio.reader import read_source

KEY_BL = "KEY_BL"
KEY_ORDER = "KEY_ORDER"
KEY_REG = "KEY_REG"
KEY_EMP = "KEY_EMP"
KEY_MATERIAL = "KEY_MATERIAL"   # کد متریال / شماره فنی — کلید اتصال موجودی و مقاومت
KEY_PR = "KEY_PR"               # شماره درخواست خرید — کلید اتصال گردش کار SAP

_BL_CANDIDATES = ["شماره بارنامه", "بارنامه", "b/l", "bl no", "bl", "bill of lading"]
_ORDER_CANDIDATES = ["شماره سفارش", "سفارش", "order no", "our reference", "po no"]
_REG_CANDIDATES = ["کد ثبت سفارش", "شماره ثبت سفارش", "ثبت سفارش", "registration no"]
_MATERIAL_CANDIDATES = ["material", "کد متریال", "کد کالا", "شماره فنی", "part no",
                        "part number", "کد قطعه", "material code", "item code"]
_KEY_EXCLUDE = ["توضیح", "شرح", "تاریخ", "وضعیت"]


class SourceAdapter(ABC):
    """پایه همه adapterها."""

    key: str = ""
    prefix: str = ""

    def __init__(self) -> None:
        self.spec: SourceSpec = get_source(self.key)

    # ── API عمومی ──
    def load(self) -> Dict[str, pd.DataFrame]:
        """خروجی: {نام منطقی: DataFrame استانداردشده}."""
        sheets = read_source(self.key)
        if not sheets:
            if self.spec.required:
                raise FileNotFoundError(f"سورس الزامی «{self.key}» در دسترس نیست.")
            log.warning(f"⏭️ سورس «{self.key}» ({self.spec.role}) در دسترس نیست؛ رد شد.")
            return {}
        try:
            return self.transform(sheets)
        except Exception as ex:
            log.error(f"❌ خطا در adapter «{self.key}»: {ex}", exc_info=True)
            if self.spec.required or os.environ.get("AIBL_STRICT_ADAPTERS") == "1":
                raise
            log.critical(
                f"🚨 سورس «{self.key}» به دلیل خطای بالا از خط لوله حذف شد. "
                f"خروجی این اجرا ناقص است — برای توقف در چنین حالتی "
                f"AIBL_STRICT_ADAPTERS=1 را تنظیم کنید.")
            return {}

    @abstractmethod
    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        ...

    # ── کمک‌کننده‌ها ──
    def _first(self, sheets: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
        return next(iter(sheets.values()), None)

    def p(self, name: str) -> str:
        """نام استاندارد با پیشوند سورس."""
        return f"{self.prefix}_{name}"

    def std(self, df: pd.DataFrame, mapping: Dict[str, List[str]],
            exclude: Optional[List[str]] = None) -> pd.DataFrame:
        """rename صریح: {نام استاندارد بدون پیشوند: [کاندیدها]}."""
        out = pd.DataFrame(index=df.index)
        for std_name, candidates in mapping.items():
            col = find_col(df, candidates, exclude=exclude)
            target = self.p(std_name)
            if col is not None:
                out[target] = df[col]
            else:
                out[target] = ""
                log.warning(f"   ⚠️ [{self.key}] ستون «{std_name}» یافت نشد "
                            f"(کاندیدها: {candidates[:3]}) — با مقدار خالی پر شد.")
        return out

    def add_bl_key(self, out: pd.DataFrame, src: pd.DataFrame,
                   candidates: Optional[List[str]] = None) -> pd.DataFrame:
        col = find_col(src, candidates or _BL_CANDIDATES, exclude=_KEY_EXCLUDE)
        out[KEY_BL] = src[col].map(clean_bl) if col else ""
        return out

    def add_order_key(self, out: pd.DataFrame, src: pd.DataFrame,
                      candidates: Optional[List[str]] = None) -> pd.DataFrame:
        col = find_col(src, candidates or _ORDER_CANDIDATES, exclude=_KEY_EXCLUDE)
        out[KEY_ORDER] = src[col].map(clean_key) if col else ""
        return out

    def add_reg_key(self, out: pd.DataFrame, src: pd.DataFrame,
                    candidates: Optional[List[str]] = None) -> pd.DataFrame:
        col = find_col(src, candidates or _REG_CANDIDATES, exclude=["توضیح", "تاریخ", "وضعیت"])
        out[KEY_REG] = src[col].map(clean_key) if col else ""
        return out

    def add_material_key(self, out: pd.DataFrame, src: pd.DataFrame,
                         candidates: Optional[List[str]] = None) -> pd.DataFrame:
        """کلید متریال — با clean_part_no نرمال می‌شود تا 'PN-001' و 'pn 001' یکی شوند."""
        col = find_col(src, candidates or _MATERIAL_CANDIDATES, exclude=["description", "شرح"])
        out[KEY_MATERIAL] = src[col].map(clean_part_no) if col else ""
        return out

    def add_pr_key(self, out: pd.DataFrame, src: pd.DataFrame,
                   candidates: Optional[List[str]] = None) -> pd.DataFrame:
        col = find_col(src, candidates or ["purchase requisition", "pr no", "شماره درخواست خرید"],
                       exclude=["item", "status", "workflow"])
        out[KEY_PR] = src[col].map(clean_key) if col else ""
        return out

    def add_emp_key(self, out: pd.DataFrame, src: pd.DataFrame,
                    candidates: Optional[List[str]] = None,
                    as_key: bool = True) -> pd.DataFrame:
        """``as_key=True`` ⇒ ستون KEY_EMP (فقط برای HR).

        برای سورس‌های دیگر ستون با پیشوند سورس نوشته می‌شود تا هنگام ادغام
        روی کلید دیگری (بارنامه/سفارش) حذف نشود — باگی که باعث می‌شد کد
        پرسنلی مقاومت و IL هرگز به pipeline نرسد.
        """
        col = find_col(src, candidates or ["employee code", "کد پرسنلی", "شماره پرسنلی", "پرسنلی"])
        target = KEY_EMP if as_key else self.p("KEY_EMP")
        out[target] = src[col].map(clean_employee_code) if col else ""
        return out


REGISTRY: Dict[str, Type[SourceAdapter]] = {}


def register(cls: Type[SourceAdapter]) -> Type[SourceAdapter]:
    REGISTRY[cls.key] = cls
    return cls
