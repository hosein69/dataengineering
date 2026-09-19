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

_LOGGER_NAME = "GSI"
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

    from ..warehouse.log_sink import WarehouseHandler
    logger.addHandler(WarehouseHandler())

    _configured = True
    return logger


log = get_logger()
