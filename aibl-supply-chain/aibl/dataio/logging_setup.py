# -*- coding: utf-8 -*-
"""سیستم لاگ (فایل + کنسول، UTF-8).

اصلاح: نسخه ۲۰.۱ هم در سطح ماژول و هم داخل ``main()`` تابع را صدا می‌زد و
در هر اجرا دو فایل لاگ می‌ساخت. اینجا idempotent است.
"""
from __future__ import annotations

import logging
import os
import sys
import json
import sqlite3
import threading
import contextvars
from datetime import datetime

from ..config.settings import SETTINGS

_LOGGER_NAME = "AIBL"
_configured = False
_RUN_ID = contextvars.ContextVar("aibl_run_id", default=None)

def set_run_id(run_id: str | None) -> None:
    _RUN_ID.set(run_id or None)

def get_run_id() -> str | None:
    return _RUN_ID.get()



class SQLiteAuditLogHandler(logging.Handler):
    """Mirror runtime logs into the warehouse audit log.

    The handler is dependency-free and creates only the audit table lazily, so it
    is safe during very early imports before the warehouse package is initialised.
    Logging must never be allowed to fail the pipeline; database lock/errors are
    therefore swallowed by design.
    """
    _DDL = """CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, run_id TEXT,
        actor TEXT, action TEXT NOT NULL, entity_type TEXT, entity_id TEXT,
        level TEXT NOT NULL DEFAULT 'INFO', message TEXT, payload_json TEXT)"""

    def __init__(self, path: str):
        super().__init__(logging.INFO)
        self.path = path
        self._lock = threading.RLock()
        self._con = None

    def _connection(self):
        if self._con is None:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            self._con = sqlite3.connect(self.path, timeout=5, check_same_thread=False, isolation_level=None)
            self._con.execute("PRAGMA busy_timeout=5000")
            try: self._con.execute("PRAGMA journal_mode=WAL")
            except Exception: pass
            self._con.execute(self._DDL)
        return self._con

    def emit(self, record):
        try:
            msg = self.format(record)
            run_id = getattr(record, "run_id", None) or get_run_id()
            payload = getattr(record, "payload", None)
            raw = json.dumps(payload, ensure_ascii=False, default=str) if payload is not None else None
            with self._lock:
                self._connection().execute(
                    "INSERT INTO audit_log(created_at,run_id,actor,action,entity_type,entity_id,level,message,payload_json) "
                    "VALUES(datetime('now'),?,?,?,?,?,?,?,?)",
                    (run_id, "python", "APP_LOG", getattr(record, "entity_type", ""),
                     getattr(record, "entity_id", ""), record.levelname, msg, raw))
        except Exception:
            pass


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

    # Log warehouse: on by default, disable with AIBL_SQLITE_LOG=0.
    if os.environ.get("AIBL_SQLITE_LOG", "1").strip().lower() not in ("0", "false", "no", "off"):
        try:
            wh = SQLiteAuditLogHandler(SETTINGS.WAREHOUSE_PATH)
            wh.setFormatter(fmt)
            logger.addHandler(wh)
        except Exception:
            pass

    _configured = True
    return logger


log = get_logger()
