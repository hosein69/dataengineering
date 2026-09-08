# -*- coding: utf-8 -*-
"""سیستم لاگ (فایل + کنسول، UTF-8).

اصلاح: نسخه ۲۰.۱ هم در سطح ماژول و هم داخل ``main()`` تابع را صدا می‌زد و
در هر اجرا دو فایل لاگ می‌ساخت. اینجا idempotent است.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

from ..config.settings import SETTINGS

_LOGGER_NAME = "AIBL"
_configured = False


def get_logger() -> logging.Logger:
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")

    # ویندوز هنگام redirect از cp1252 استفاده می‌کند و روی متن فارسی می‌شکند
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    try:
        os.makedirs(SETTINGS.LOG_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fh = logging.FileHandler(os.path.join(SETTINGS.LOG_DIR, f"AIBL_{stamp}.log"), encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as ex:  # مسیر لاگ در دسترس نیست → فقط کنسول
        logger.warning(f"⚠️ فایل لاگ ساخته نشد ({ex}); فقط خروجی کنسول فعال است.")

    _configured = True
    return logger


log = get_logger()
