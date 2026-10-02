# -*- coding: utf-8 -*-
"""متن منبع در Excel متن بماند، نه فرمول.

openpyxl هر رشته‌ای را که با «=» شروع شود فرمول ذخیره می‌کند و رشته‌ای مثل «#N/A»
را مقدار خطا. متن منبع (شرح کالا، شماره سفارش، یادداشت کارشناس) ممکن است چنین
باشد و Excel آن را اجرا می‌کند؛ مثلاً ``=HYPERLINK(...)`` به نشانی بیرونی یا فرمولی
که داده برگه دیگری را می‌خواند. ``keep_text`` پیش از ذخیره، این خانه‌ها را متن
(با پیشوند نقل‌قول Excel) می‌کند، به‌جز فرمول‌هایی که خود گزارش عمداً نوشته است.
"""
from __future__ import annotations

#: نسخه قرارداد این ماژول — gsi/version.py آن را می‌سنجد.
__contract__ = 1

from typing import Any, Collection, Iterable, Tuple

#: نوع خانه در openpyxl: f فرمول، e مقدار خطا
_ACTIVE = ("f", "e")


def _worksheets(target: Any) -> Iterable[Any]:
    if hasattr(target, "worksheets"):          # Workbook
        return list(target.worksheets)
    return [target]                            # Worksheet


def _cells(ws: Any) -> Iterable[Any]:
    cells = getattr(ws, "_cells", None)        # فقط خانه‌های موجود؛ iter_rows خانه خالی می‌سازد
    if isinstance(cells, dict):
        return list(cells.values())
    return [c for row in ws.iter_rows() for c in row]


#: نام ویژگی روی Workbook که فرمول‌های نوشته‌شده با ``write_formula`` را نگه می‌دارد
_REGISTRY = "_gsi_formulas"


def write_formula(ws: Any, row: int, column: int, formula: str) -> Any:
    """فرمولی که خود گزارش می‌نویسد (``=SUBTOTAL``، ``=COUNTIF``)؛ ``keep_text`` آن را متن نمی‌کند."""
    cell = ws.cell(row=row, column=column, value=formula)
    book = getattr(ws, "parent", None)
    if book is not None:
        reg = getattr(book, _REGISTRY, None)
        if reg is None:
            reg = set()
            setattr(book, _REGISTRY, reg)
        reg.add((ws.title, cell.coordinate))
    return cell


def keep_text(target: Any, allowed: Collection[Tuple[str, str]] = ()) -> int:
    """خانه‌های فرمول/خطای ساخته‌شده از متن را متن می‌کند و شمارشان را برمی‌گرداند.

    ``target`` کتاب کار یا یک برگه openpyxl است. ``allowed`` مجموعه
    ``(عنوان برگه، نشانی خانه)`` فرمول‌هایی است که گزارش خودش نوشته (مثلاً
    ``=SUBTOTAL`` ردیف جمع) و دست نمی‌خورند؛ فرمول‌های ``write_formula`` خودکار
    در این مجموعه‌اند.
    """
    allowed = set(allowed or ())
    changed = 0
    for ws in _worksheets(target):
        title = getattr(ws, "title", "")
        allowed |= set(getattr(getattr(ws, "parent", None), _REGISTRY, None) or ())
        for cell in _cells(ws):
            if cell.data_type not in _ACTIVE or not isinstance(cell.value, str):
                continue
            if (title, cell.coordinate) in allowed:
                continue
            cell.data_type = "s"
            cell.quotePrefix = True             # Excel هنگام ویرایش هم آن را متن نگه دارد
            changed += 1
    return changed
