# -*- coding: utf-8 -*-
"""پیکربندی مرکزی سیستم.

تمام مسیرها از متغیرهای محیطی قابل override هستند تا همین کد بدون تغییر
روی لپ‌تاپ کارشناس، سرور Streamlit و محیط تست اجرا شود.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

#: ویندوز است یا نه — پیش‌فرض‌های مسیر به همین وابسته‌اند.
_IS_WINDOWS = sys.platform.startswith("win")
_IS_MAC = sys.platform == "darwin"

#: ریشهٔ اشتراک سازمانی.
#:
#: روی ویندوز مسیر UNC است. مک همان اشتراک SMB را زیر ``/Volumes`` سوار
#: می‌کند، پس رشتهٔ UNC آنجا اصلاً وجود ندارد؛ اگر همان را نگه داریم، هر
#: هفت سورس «پیدا نشد» می‌دهند و کاربر فکر می‌کند داده‌ها رفته‌اند.
#: نام نقطهٔ اتصال روی هر مک فرق می‌کند، پس ``AIBL_NET`` بالاترین حرف
#: را می‌زند و بقیهٔ مسیرها از همین یکی ساخته می‌شوند.
_NET = os.environ.get(
    "AIBL_NET",
    "/Volumes/data-share/Global Sourcing" if _IS_MAC
    else r"\\ikco.com\data-share\Global Sourcing")


def _net(*parts: str) -> str:
    r"""زیرمسیرِ اشتراک، با جداکنندهٔ همین سیستم‌عامل.

    پیش از این مسیرها با ``\`` به هم چسبانده می‌شدند. روی مک ``\`` یک
    کاراکتر معمولیِ نام فایل است، نه جداکننده — یعنی کل مسیر یک نامِ
    واحدِ بی‌معنا می‌شد.
    """
    sep = "\\" if _IS_WINDOWS else "/"
    return sep.join((_NET.rstrip("\\/"),) + parts)


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _local_default(win_path: str, posix_leaf: str) -> str:
    r"""پیش‌فرض مسیر محلی، متناسب با سیستم‌عامل.

    روی ویندوز همان مسیر تولید (``D:\of\blstotal\...``) برمی‌گردد.
    روی لینوکس/مک آن رشته یک *نام فایل* است، نه مسیر؛ اگر همان را برگردانیم
    پکیج پوشه‌ای به اسم ``D:\of\blstotal\logs`` کنار کد می‌سازد. به‌جای آن
    زیر ``AIBL_HOME`` (پیش‌فرض ``~/.aibl``) می‌نویسیم.
    """
    if _IS_WINDOWS:
        return win_path
    home = os.environ.get("AIBL_HOME") or os.path.join(os.path.expanduser("~"), ".aibl")
    return os.path.join(home, posix_leaf)


@dataclass(frozen=True)
class Settings:
    # ── ریشه‌های شبکه ──
    FOREIGN_DIR: str = field(default_factory=lambda: _env("AIBL_FOREIGN", _net("03-Data", "01-Foreign")))
    BLS_TOTAL_DIR: str = field(default_factory=lambda: _env("AIBL_BLS", _net("03-Data", "01-Foreign", "BLs TOTAL")))
    CLEARANCE_DIR: str = field(default_factory=lambda: _env("AIBL_CLEARANCE", _net("03-Data", "01-Foreign", "BLs TOTAL", "Clearance")))
    HR_DIR: str = field(default_factory=lambda: _env("AIBL_HR", _net("11-Governance & Integration", "03-Reports", "01-HR")))
    # مسیر واقعی فایل مقاومت (تأییدشده در HEADERS_MAP) — نه پوشه اسماعیلی
    GS_COMBINE_OUT_DIR: str = field(default_factory=lambda: _env("AIBL_GS_COMBINE", _net("11-Governance & Integration", "DataTeam", "Data_Ware_House", "GS_Combine", "OUTPUT")))
    ESMAEILI_DIR: str = field(default_factory=lambda: _env("AIBL_ESMAEILI", _net("11-Governance & Integration", "25-H.Esmaeili")))
    MOHAMADI_DIR: str = field(default_factory=lambda: _env("AIBL_MOHAMADI", _net("11-Governance & Integration", "26-M.Mohamadi")))

    # ── خروجی و لاگ ──
    OUTPUT_DIR: str = field(default_factory=lambda: _env("AIBL_OUTPUT", _local_default(r"D:\of\blstotal\output", "output")))
    LOG_DIR: str = field(default_factory=lambda: _env("AIBL_LOGS", _local_default(r"D:\of\blstotal\logs", "logs")))
    # خروجی روزانه رسمی داشبورد: پوشه تاریخ‌دار + نام ثابت برای استفاده سازمانی/ایمیل
    DAILY_REPORT_ROOT: str = field(default_factory=lambda: _env("AIBL_DAILY_REPORT_ROOT", ""))
    SYSTEMMATIC_MATERIAL_BASENAME: str = "Systemmatic Material.xlsx"

    # ── پارامترهای اجرا ──
    # FIX-4: تاریخ هاردکد "2026-07-26" حذف شد.
    # اگر AIBL_TODAY ست شود (برای تست بازتولیدپذیر) همان استفاده می‌شود.
    TODAY_OVERRIDE: Optional[str] = field(default_factory=lambda: os.environ.get("AIBL_TODAY"))

    # FIX-8: شروع سال ۱۴۰۵ = ۲۰۲۶-۰۳-۲۱ (نه ۲۰۲۶-۰۱-۰۱)
    FISCAL_YEAR_START: date = date(2026, 3, 21)

    FUZZY_THRESHOLD: float = 0.80
    STUCK_CRITICAL_DAYS: int = 45

    @property
    def today(self) -> date:
        if self.TODAY_OVERRIDE:
            from ..core.jalali import CalendarEngine
            parsed = CalendarEngine.parse(self.TODAY_OVERRIDE)
            if parsed:
                return parsed
        return date.today()

    @property
    def daily_report_root(self) -> str:
        return self.DAILY_REPORT_ROOT or self.OUTPUT_DIR

    def daily_report_path(self, day: Optional[date] = None) -> str:
        d = day or self.today
        stamp = d.strftime("%Y-%m-%d")
        folder = os.path.join(self.daily_report_root, stamp)
        return os.path.join(folder, f"{stamp}_{self.SYSTEMMATIC_MATERIAL_BASENAME}")

    @property
    def expert_extracts_dir(self) -> str:
        return os.path.join(self.OUTPUT_DIR, "expert_extracts")


SETTINGS = Settings()
