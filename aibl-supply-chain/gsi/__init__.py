# -*- coding: utf-8 -*-
"""GSI — مغز شناختی لجستیک ایران خودرو.

⚠️ این یک **پکیج** است، نه یک فایل تکی. کل پوشه gsi/ باید با ساختار درختی
   کپی شود. اگر فایل‌ها تخت کپی شوند، `python -m gsi.doctor` علت را می‌گوید.

اجرا:
    python -m gsi.doctor              # عیب‌یابی محیط (اول این را بزنید)
    python -m gsi.rulebook.validate   # اعتبارسنجی کتابخانه قوانین
    python -m gsi.pipeline            # اجرای کامل
"""
from __future__ import annotations

__all__ = ["__version__"]


def __getattr__(name: str):
    """نسخه به‌صورت تنبل خوانده می‌شود.

    ``from .factsheet import VERSION`` در سطح پکیج باعث می‌شد
    ``python -m gsi.factsheet`` با این هشدار اجرا شود:

        RuntimeWarning: 'gsi.factsheet' found in sys.modules after import
        of package 'gsi', but prior to execution of 'gsi.factsheet'

    یعنی ماژول دو بار در دو هویت اجرا می‌شد. با PEP 562 نسخه فقط وقتی
    خوانده می‌شود که واقعاً بخواهندش، و ``gsi.factsheet`` تمیز اجرا می‌شود.
    """
    if name == "__version__":
        from .factsheet import VERSION
        return VERSION
    raise AttributeError(f"module 'gsi' has no attribute '{name}'")
