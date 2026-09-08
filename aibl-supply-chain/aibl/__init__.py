# -*- coding: utf-8 -*-
"""AIBL — مغز شناختی لجستیک ایران خودرو.

⚠️ این یک **پکیج** است، نه یک فایل تکی. کل پوشه aibl/ باید با ساختار درختی
   کپی شود. اگر فایل‌ها تخت کپی شوند، `python -m aibl.doctor` علت را می‌گوید.

اجرا:
    python -m aibl.doctor              # عیب‌یابی محیط (اول این را بزنید)
    python -m aibl.rulebook.validate   # اعتبارسنجی کتابخانه قوانین
    python -m aibl.pipeline            # اجرای کامل
"""
from __future__ import annotations

from .factsheet import VERSION as __version__   # تنها منبع نسخه
__all__ = ["__version__"]
