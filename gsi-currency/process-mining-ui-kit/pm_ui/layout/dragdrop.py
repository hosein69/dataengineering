# -*- coding: utf-8 -*-
"""درگ‌اند‌درپ واقعی برای ترتیب بلوک‌ها — بدون هیچ بستهٔ npm/pip بیرونی.

## چرا یک کامپوننت سفارشی، نه یک بستهٔ آماده (مثل streamlit-sortables)

محیط این محصول صراحتاً آفلاین است (فولدر شبکه + ایمیل اوتلوک سازمانی؛
هیچ فایل فونت باینری هم در بسته توزیع نمی‌شود — همان قاعده در سراسر
``pm_ui`` تکرار شده). یک بستهٔ npm/pip بیرونی یعنی یک وابستگی نصب‌شده از
اینترنت که در یک استقرار سازمانی بدون اینترنت مستقیم ممکن است اصلاً قابل
نصب نباشد. راه‌حل: پروتکل «Streamlit Components v1» — که خودِ Streamlit
داخلی پیاده‌سازی کرده — با ``postMessage`` خام پیاده‌سازی می‌شود (بدون
کتابخانهٔ کمکی ``streamlit-component-lib``، دقیقاً همان الگویی که
:mod:`pm_ui.components` برای هاور نمودار جریان با ``components.v1.html``
به‌کار می‌برد، فقط این‌جا با ``declare_component`` دوطرفه است تا مقدار
هم به پایتون برگردد).

## دسترس‌پذیری

درگ‌اند‌درپ (Drag and Drop) با ماوس، با صفحه‌کلید قابل‌استفاده نیست.
به همین دلیل این کامپوننت جایگزین دکمه‌های ▲/▼ موجود در نوار کناری
(``app.py``) نمی‌شود؛ **افزوده** می‌شود — کاربری که با کیبورد کار می‌کند
یا موس ندارد، همچنان می‌تواند با همان دکمه‌ها ترتیب را عوض کند.
"""
from __future__ import annotations

__contract__ = 1

from pathlib import Path
from typing import Dict, List, Optional, Sequence, TypedDict

import streamlit.components.v1 as components

_FRONTEND_DIR = Path(__file__).parent / "dragdrop_frontend"

# ``declare_component`` با ``path`` یک سرور استاتیک محلی برای همین پوشه بالا
# می‌آورد (بدون اینترنت، بدون build step — یک index.html خام کافی است).
_component = components.declare_component("pm_ui_dragdrop", path=str(_FRONTEND_DIR))


class DragItem(TypedDict, total=False):
    id: str
    label: str
    badge: str        # زیرنویس کوتاه اختیاری، مثلاً نوع بلوک


def draggable_block_list(items: Sequence[DragItem], *, key: str) -> Optional[List[str]]:
    """فهرست قابل‌درگ را رندر می‌کند؛ فقط وقتی کاربر واقعاً رهاسازی کرده،
    فهرست شناسه‌ها را به همان ترتیب تازه برمی‌گرداند — در غیر این صورت
    ``None`` (یعنی «چیزی عوض نشده، رندر قبلی/اولیه است»).

    فراخوان معمولی در ``app.py``::

        new_order = draggable_block_list(items, key="layout_dnd")
        if new_order:
            st.session_state.layout = reorder_blocks(st.session_state.layout, new_order)
            st.rerun()
    """
    theme = {
        "ink": "#0b1f33", "inkMuted": "#5a6b79", "border": "#dbe3e7",
        "borderStrong": "#7d919e", "surfaceRaised": "#ffffff", "surfaceSunken": "#eef2f4",
        "teal": "#0a7c86", "tealWash": "#e7f1f2", "radius": 10,
        "font": ("'IRANSansWeb','IRANSansX','IRANSans','YekanBakh','Yekan Bakh',"
                "'Vazirmatn',Tahoma,'Segoe UI',Arial,sans-serif"),
    }
    value = _component(items=list(items), theme=theme, key=key, default=None)
    if not value or not isinstance(value, list):
        return None
    return [str(v) for v in value]
