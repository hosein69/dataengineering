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

__all__ = ["__version__"]


def __getattr__(name: str):
    """نسخه به‌صورت تنبل خوانده می‌شود.

    ``from .factsheet import VERSION`` در سطح پکیج باعث می‌شد
    ``python -m aibl.factsheet`` با این هشدار اجرا شود:

        RuntimeWarning: 'aibl.factsheet' found in sys.modules after import
        of package 'aibl', but prior to execution of 'aibl.factsheet'

    یعنی ماژول دو بار در دو هویت اجرا می‌شد. با PEP 562 نسخه فقط وقتی
    خوانده می‌شود که واقعاً بخواهندش، و ``aibl.factsheet`` تمیز اجرا می‌شود.
    """
    if name == "__version__":
        from .factsheet import VERSION
        return VERSION
    raise AttributeError(f"module 'aibl' has no attribute '{name}'")
