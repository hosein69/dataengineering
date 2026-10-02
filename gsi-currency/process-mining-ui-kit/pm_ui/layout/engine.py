# -*- coding: utf-8 -*-
"""موتور چیدمان قابل‌تنظیم — همان چیدمان، هم برای صفحهٔ Streamlit و هم برای خروجی HTML.

## چرا این لایه لازم است

خواستهٔ کارفرما این بود: «تمام المان‌ها در Streamlit قابل تغییر باشند —
چه از لحاظ مکان، چه نوع، چه جایگاه و اندازه — که بتوان خروجی HTML را
متناسب نیاز ارسال کرد». اگر هر صفحه مستقیماً توابع رندر را صدا بزند،
تغییر ترتیب یا اندازه یعنی ویرایش کد پایتون. این‌جا برعکس است: صفحه یک
فهرست از ``BlockSpec`` (پیکربندی، نه کد) می‌خواند و موتور آن را هم در
Streamlit و هم در HTML رندر می‌کند — یک منبع چیدمان، دو مقصد خروجی.

``REGISTRY`` نگاشت «نوع بلوک» → تابع رندر Streamlit است. برای افزودن
جزء تازه، فقط باید در ``REGISTRY`` ثبتش کرد؛ موتور خودش عرض ستون،
مرتب‌سازی، و فیلتر مخاطب را مدیریت می‌کند.
"""
from __future__ import annotations

__contract__ = 1

import copy
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypedDict

#: اندازهٔ بلوک → تعداد بلوک در هر ردیف (چیدمان ستونی Streamlit)
SIZE_TO_COLS: Dict[str, int] = {"full": 1, "half": 2, "third": 3, "quarter": 4}


class BlockSpec(TypedDict, total=False):
    id: str                 # شناسهٔ یکتا — برای ذخیره/بارگذاری و اشاره در گزارش
    type: str                # کلید در REGISTRY (مثلاً "kpi_row", "process_flow")
    title: str                # عنوان بخش (اختیاری — برخی بلوک‌ها عنوان داخلی خودشان را دارند)
    size: str                  # "full" | "half" | "third" | "quarter"
    order: int                  # ترتیب نمایش — کوچک‌تر، بالاتر
    visible_for: List[str]        # فهرست سطوح مخاطب مجاز؛ خالی یعنی برای همه
    props: Dict[str, Any]          # پارامترهای اختصاصیِ همان نوع بلوک


RenderFn = Callable[[Dict[str, Any], Any], None]

REGISTRY: Dict[str, RenderFn] = {}


def register(block_type: str) -> Callable[[RenderFn], RenderFn]:
    """دکوراتور ثبت یک تابع رندر Streamlit برای یک نوع بلوک."""
    def deco(fn: RenderFn) -> RenderFn:
        REGISTRY[block_type] = fn
        return fn
    return deco


def visible_blocks(blocks: List[BlockSpec], audience: str) -> List[BlockSpec]:
    ordered = sorted(blocks, key=lambda b: b.get("order", 0))
    return [b for b in ordered
            if not b.get("visible_for") or audience in b["visible_for"]]


def render_layout(blocks: List[BlockSpec], data: Any, *, audience: str = "manager") -> None:
    """چیدمان را در Streamlit رندر می‌کند؛ بلوک‌های هم‌ردیف بر اساس ``size`` گروه می‌شوند."""
    import streamlit as st

    shown = visible_blocks(blocks, audience)
    i = 0
    while i < len(shown):
        current = shown[i]
        cols_n = SIZE_TO_COLS.get(current.get("size", "full"), 1)
        row = shown[i:i + cols_n]
        i += len(row)
        cols = st.columns(len(row))
        for block, col in zip(row, cols):
            fn = REGISTRY.get(block.get("type", ""))
            with col:
                if block.get("title"):
                    st.markdown(f"##### {block['title']}")
                if fn is None:
                    st.warning(f"نوع بلوک ناشناخته: {block.get('type')}")
                else:
                    fn(block.get("props", {}), data)


def load_layout(path: str | Path) -> List[BlockSpec]:
    """پیکربندی چیدمان را از یک فایل JSON روی فولدر شبکه می‌خواند."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"فایل چیدمان یافت نشد: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_layout(blocks: List[BlockSpec], path: str | Path) -> None:
    """پیکربندی چیدمان را روی فولدر شبکه ذخیره می‌کند (بدون نیاز به دیتابیس)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(blocks, ensure_ascii=False, indent=2), encoding="utf-8")


def move_block(blocks: List[BlockSpec], block_id: str, *, delta: int) -> List[BlockSpec]:
    """یک بلوک را در ترتیب چیدمان بالا/پایین می‌برد — برای کنترل «جابه‌جایی» در رابط."""
    out = copy.deepcopy(blocks)
    ordered = sorted(out, key=lambda b: b.get("order", 0))
    idx = next((i for i, b in enumerate(ordered) if b.get("id") == block_id), None)
    if idx is None:
        return out
    new_idx = max(0, min(len(ordered) - 1, idx + delta))
    ordered[idx], ordered[new_idx] = ordered[new_idx], ordered[idx]
    for rank, b in enumerate(ordered):
        b["order"] = rank
    return ordered


def set_block_size(blocks: List[BlockSpec], block_id: str, size: str) -> List[BlockSpec]:
    """اندازهٔ نمایشی یک بلوک را تغییر می‌دهد (full/half/third/quarter)."""
    out = copy.deepcopy(blocks)
    for b in out:
        if b.get("id") == block_id:
            b["size"] = size
    return out
