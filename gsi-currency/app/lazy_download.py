# -*- coding: utf-8 -*-
"""دکمه دانلودی که فایل را فقط هنگام نیاز می‌سازد؛ روی Streamlit 1.49 به بالا.

Streamlit از نسخه 1.52 به ``download_button`` یک callable می‌پذیرد و آن را فقط
وقتی کاربر کلیک کرد اجرا می‌کند. نسخه‌های قبل (مثل 1.51) همان callable را با خطای
``Invalid binary data format: <class 'functools.partial'>`` رد می‌کنند و کل صفحه
می‌ایستد؛ در حالی که ``requirements.txt`` از 1.49 را مجاز می‌داند.

روی نسخه قدیمی دکمه دو قدم دارد:

1. دکمه «آماده‌سازی …» فایل را یک‌بار می‌سازد و بایت‌ها با امضای ورودی‌ها در
   ``session_state`` می‌مانند؛
2. دکمه دانلود واقعی با همان برچسب جای آن می‌آید.

اگر ورودی‌ها (مرحله، ثبت سفارش، سطوح بحرانی، زبان یا Snapshot) عوض شوند امضا فرق
می‌کند و دوباره دکمه «آماده‌سازی» نشان داده می‌شود؛ پس فایل کهنه هرگز دانلود
نمی‌شود. ساختن همه فایل‌ها در هر بازاجرای صفحه هم پیش نمی‌آید.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Hashable, Optional

import streamlit as st

#: اولین نسخه‌ای که ``data`` را callable می‌پذیرد
CALLABLE_SINCE = (1, 52)

#: جای بایت‌های ساخته‌شده روی نسخه قدیمی: ``{key: (امضا, بایت‌ها)}``
STORE = "_gsi_lazy_downloads"


def version_tuple(text: str) -> tuple:
    """``"1.51.0"`` → ``(1, 51)``؛ رشته نامفهوم → ``(0, 0)`` یعنی مسیر امن دو قدمی."""
    nums = re.findall(r"\d+", str(text or ""))
    return (int(nums[0]), int(nums[1])) if len(nums) >= 2 else (0, 0)


#: آیا Streamlit نصب‌شده callable را برای ``data`` می‌پذیرد؛ آزمون‌ها عوضش می‌کنند
CALLABLE_DATA = version_tuple(getattr(st, "__version__", "")) >= CALLABLE_SINCE


def download(container: Any, label: str, make: Callable[[], Any], *, file_name: str, mime: str, key: str,
             sig: Hashable = (), icon: Optional[str] = ":material/download:", primary: bool = False,
             width: str = "stretch") -> None:
    """یک دکمه دانلود با ساخت فایل فقط هنگام نیاز.

    ``make`` بدون آرگومان صدا زده می‌شود و ``bytes`` یا ``str`` برمی‌گرداند. ``sig``
    هر چیزی است که محتوای فایل به آن بستگی دارد و در نام فایل نیامده (زبان، سطوح،
    شناسه Snapshot)؛ نام فایل خودش جزو امضاست.
    """
    kind = "primary" if primary else "secondary"
    opts: dict = {"file_name": file_name, "mime": mime, "key": key, "type": kind, "width": width}
    if icon:
        opts["icon"] = icon
    if CALLABLE_DATA:
        container.download_button(label, data=make, **opts)
        return

    store = st.session_state.setdefault(STORE, {})
    token = (file_name, sig)
    held = store.get(key)
    if held is not None and held[0] != token:
        store.pop(key, None)
        held = None
    if held is None:
        # دکمه آماده‌سازی، نشانگر ساخت و دکمه دانلود یکی‌یکی در همین یک جا می‌آیند
        slot = container.empty()
        if not slot.button(f"آماده‌سازی {label}", key=f"{key}__build", type=kind, width=width,
                           icon=":material/build:"):
            return
        with slot, st.spinner("در حال ساخت فایل…"):
            held = store[key] = (token, make())
        container = slot
    # ``ignore``: دانلود صفحه را دوباره اجرا نمی‌کند و بایت‌ها برای دانلود دوباره می‌مانند
    container.download_button(label, data=held[1], on_click="ignore", **opts)
