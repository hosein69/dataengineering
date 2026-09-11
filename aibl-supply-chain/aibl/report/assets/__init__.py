# -*- coding: utf-8 -*-
"""تصویرهای قالب — نشانِ حک‌شده و خودرو.

## چرا پوشه، نه کد

دو تصویر در قالب فیگما **رستر**ند، نه وکتور: نشانِ لیزریِ ایران‌خودرو و
تصویر پیکان. اینجا بازسازی‌شان نمی‌کنیم؛ خودِ همان پرونده‌ها اینجا
می‌نشینند و گزارش‌ها به‌صورت ``data:`` درونشان می‌برند تا خروجی
خودبسنده بماند و چیزی از شبکه نخواهد.

## چه بگذاریم

    report/assets/emblem.png      نشان ایران‌خودرو — حک لیزری (۱۵۰×۱۴۰)
    report/assets/paykan.png      پیکان، نمای سه‌رخ  (۵۰۰×۲۲۰)

خروجی مستقیم از همان فریم‌های فیگما:
«نشان ایران‌خودرو - حک‌شده» و «قاب پیکان (برش‌خورده)».

## اگر نبودند

هیچ‌چیز نمی‌شکند. نشان اصلاً نمایش داده نمی‌شود — **جعل نمی‌شود** — و
جای خودرو به نقش‌مایهٔ برداری (``paykan.py``) برمی‌گردد. این عمدی است:
نشانِ سازمانیِ تقریبی، بدتر از نبودِ نشان است.
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent

#: نام پرونده → (عرض نمایش، توضیح)
SLOTS = {
    "emblem": (150, "نشان ایران‌خودرو — حک لیزری"),
    "paykan": (500, "پیکان — نمای سه‌رخ"),
}


def path(name: str) -> Optional[Path]:
    """مسیر پروندهٔ موجود برای این جایگاه، یا ``None``."""
    for suffix in (".png", ".webp", ".jpg", ".jpeg", ".svg"):
        p = HERE / f"{name}{suffix}"
        if p.exists() and p.stat().st_size:
            return p
    return None


def has(name: str) -> bool:
    return path(name) is not None


def data_uri(name: str) -> str:
    """پرونده به‌صورت ``data:`` — خروجی خودبسنده می‌ماند."""
    p = path(name)
    if p is None:
        return ""
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def img(name: str, width: Optional[int] = None, alt: str = "") -> str:
    """برچسب ``<img>`` آمادهٔ درج، یا رشتهٔ خالی اگر پرونده نباشد."""
    uri = data_uri(name)
    if not uri:
        return ""
    w = width or SLOTS.get(name, (None, ""))[0]
    wa = f' width="{w}"' if w else ""
    a = alt or SLOTS.get(name, ("", ""))[1]
    return (f'<img src="{uri}"{wa} alt="{a}" '
            f'style="display:block;max-width:100%;height:auto">')


def missing() -> list:
    """جایگاه‌های خالی — برای گزارشِ صادقانه، نه شکستِ خاموش."""
    return [f"{n}  ({d})" for n, (_w, d) in SLOTS.items() if not has(n)]
