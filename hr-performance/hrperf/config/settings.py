# -*- coding: utf-8 -*-
"""پیکربندی مرکزی — همه مسیرها از متغیر محیطی قابل تغییرند.

پیش‌فرض‌ها متناسب با سیستم‌عامل انتخاب می‌شوند: روی ویندوز مسیر تولید،
روی لینوکس/مک زیر ``HRP_HOME`` (پیش‌فرض ``~/.hrperf``). پکیج قبلی مسیر
ویندوزی را روی لینوکس هم برمی‌گرداند و پوشه‌ای به نام ``D:\\...`` می‌ساخت.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

_IS_WINDOWS = sys.platform.startswith("win")


def _home() -> Path:
    return Path(os.environ.get("HRP_HOME")
                or (Path.home() / ".hrperf"))


def _default(win: str, leaf: str) -> str:
    return win if _IS_WINDOWS else str(_home() / leaf)


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    INPUT_DIR: str = field(default_factory=lambda: _env(
        "HRP_INPUT", _default(r"D:\HRPerf\input_files", "input_files")))
    OUTPUT_DIR: str = field(default_factory=lambda: _env(
        "HRP_OUTPUT", _default(r"D:\HRPerf\output", "output")))
    LOG_DIR: str = field(default_factory=lambda: _env(
        "HRP_LOGS", _default(r"D:\HRPerf\logs", "logs")))
    DB_PATH: str = field(default_factory=lambda: _env(
        "HRP_DB", _default(r"D:\HRPerf\hrperf.sqlite", "hrperf.sqlite")))
    RULES_DIR: str = field(default_factory=lambda: _env("HRP_RULES", ""))

    #: تاریخ مرجع ثابت برای بازتولید یک اجرای قدیمی
    TODAY_OVERRIDE: Optional[str] = field(
        default_factory=lambda: os.environ.get("HRP_TODAY"))

    #: حداقل اندازه گروه همتا برای مقایسه معنادار
    MIN_PEER_GROUP: int = 4
    #: اگر گروه کوچک‌تر بود، به سطح بالاتر سلسله‌مراتب صعود می‌کند
    PEER_FALLBACK: bool = True

    @property
    def today(self) -> date:
        if self.TODAY_OVERRIDE:
            try:
                return date.fromisoformat(self.TODAY_OVERRIDE[:10])
            except ValueError:
                pass
        return date.today()

    @property
    def rules_dir(self) -> Path:
        if self.RULES_DIR:
            return Path(self.RULES_DIR)
        return Path(__file__).resolve().parent


SETTINGS = Settings()
