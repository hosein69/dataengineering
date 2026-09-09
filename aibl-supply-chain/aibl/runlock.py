# -*- coding: utf-8 -*-
"""قفل اجرا و نشانه‌گذاری مجموعه خروجی.

## مسئله ۱ — دو اجرای هم‌زمان

خط لوله چند فایل می‌سازد: گزارش رسمی، فایل هر کارشناس، گزارش ممیزی و
دفتر سلامت. هیچ‌کدام از هم خبر ندارند.

بازتولید واقعی روی همین ماشین: دو اجرای هم‌زمان روی یک پوشه خروجی، هر
دو «🏆 داشبورد ذخیره شد» گفتند و هر دو موفق گزارش شدند. روی لینوکس
``os.replace`` اتمیک است پس فایل خراب نمی‌شود، ولی **مجموعه** مخلوط
می‌شود: گزارش از اجرای الف، دفتر سلامت از اجرای ب، فایل‌های کارشناس
درهم. هیچ‌کس نمی‌فهمد.

این در عمل نادر نیست: زمان‌بند ویندوز دیر اجرا می‌شود و کاربر هم دستی
اجرا می‌کند؛ یا دو نفر هم‌زمان دکمه «اجرای مجدد خط لوله» را در داشبورد
می‌زنند.

## مسئله ۲ — مجموعه خروجی اتمیک نیست

اگر اجرا وسط کار بمیرد (قطعی شبکه، بسته شدن ترمینال)، پوشه خروجی
فایل‌های نیمه‌کاره از دو نسل مختلف دارد و از بیرون قابل تشخیص نیست.

## راه‌حل

یک قفل توصیه‌ای مبتنی بر فایل با شناسه فرآیند، و یک «نشانه اجرا» که
پس از **کامل شدن** همه خروجی‌ها نوشته می‌شود. نبودِ نشانه یعنی مجموعه
ناتمام است.

قفل عمداً **توصیه‌ای** است، نه اجباری در سطح سیستم‌عامل: هدف جلوگیری از
اشتباه رایج است، نه ساختن یک مکانیزم پیچیده که خودش خراب شود. قفلِ
مانده از فرآیندی که دیگر زنده نیست، خودکار پاک می‌شود.
"""
from __future__ import annotations

__contract__ = 1

import json
import os
import time
from datetime import datetime
from typing import Optional

from .dataio.logging_setup import log

LOCK_NAME = ".aibl_run.lock"
MARKER_NAME = "AIBL_Run_Complete.json"

#: قفلی که از این قدیمی‌تر باشد، بازمانده یک اجرای مرده است.
STALE_AFTER_S = 3 * 3600


class RunLocked(RuntimeError):
    """اجرای دیگری روی همین پوشه خروجی در جریان است."""


def _alive(pid: int) -> bool:
    """آیا فرآیندی با این شناسه هنوز زنده است؟"""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)          # سیگنال ۰ = فقط بررسی وجود
    except ProcessLookupError:
        return False
    except PermissionError:
        return True              # هست ولی مال کاربر دیگری است
    except Exception:
        return True
    return True


def _read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class RunLock:
    """قفل توصیه‌ای اجرا. با ``with`` استفاده می‌شود."""

    def __init__(self, folder: str, force: bool = False) -> None:
        self.folder = folder
        self.path = os.path.join(folder, LOCK_NAME)
        self.force = force or os.environ.get("AIBL_FORCE_RUN") == "1"
        self.acquired = False

    def __enter__(self) -> "RunLock":
        os.makedirs(self.folder, exist_ok=True)
        held = _read(self.path)
        if held:
            pid = int(held.get("pid", 0) or 0)
            age = time.time() - float(held.get("epoch", 0) or 0)
            if _alive(pid) and age < STALE_AFTER_S and not self.force:
                raise RunLocked(
                    f"اجرای دیگری از AIBL روی همین پوشه خروجی در جریان است "
                    f"(شناسه فرآیند {pid}، از {held.get('started', '؟')}).\n"
                    f"    دو اجرای هم‌زمان، مجموعه خروجی را مخلوط می‌کنند: گزارش از "
                    f"یکی و فایل‌های کارشناس از دیگری.\n"
                    f"    یا صبر کنید تا تمام شود، یا اگر مطمئن‌اید آن اجرا مرده است:\n"
                    f"        AIBL_FORCE_RUN=1 python -m aibl run\n"
                    f"    (فایل قفل: {self.path})")
            reason = "قفل بازمانده از اجرای مرده" if not _alive(pid) else "اجبار کاربر"
            log.warning(f"⚠️ قفل قبلی نادیده گرفته شد — {reason} (pid {pid}).")
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "epoch": time.time(),
                       "started": datetime.now().isoformat(timespec="seconds")},
                      f, ensure_ascii=False)
        self.acquired = True
        return self

    def __exit__(self, *exc) -> None:
        if not self.acquired:
            return
        try:
            # فقط قفل خودمان را برمی‌داریم، نه قفل اجرای دیگری
            if int(_read(self.path).get("pid", -1)) == os.getpid():
                os.remove(self.path)
        except OSError:
            pass


def write_marker(folder: str, files: dict, version: str = "") -> str:
    """نشانه «این مجموعه کامل است» — پس از نوشتن همه خروجی‌ها.

    نبودِ این فایل یعنی اجرا وسط کار مرده و فایل‌های پوشه از یک نسل
    نیستند. ابزار بعدی (ایمیل، داشبورد) می‌تواند همین را بررسی کند.
    """
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, MARKER_NAME)
    payload = {
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "pid": os.getpid(),
        "version": version,
        "files": {k: os.path.basename(v) for k, v in files.items() if v},
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return path


def read_marker(folder: str) -> Optional[dict]:
    """نشانه اجرای کامل، یا ``None`` اگر مجموعه ناتمام باشد."""
    data = _read(os.path.join(folder, MARKER_NAME))
    return data or None


def clear_marker(folder: str) -> None:
    """نشانه را پیش از شروع نوشتن برمی‌دارد: تا کامل نشده، کامل نیست."""
    try:
        os.remove(os.path.join(folder, MARKER_NAME))
    except OSError:
        pass


def emit_outputs(res, build_report) -> None:
    """همه خروجی‌های یک اجرا، به‌عنوان یک مجموعه.

    نشانه اول برداشته می‌شود و آخر نوشته: تا کامل نشده، کامل نیست. اگر
    اجرا وسط کار بمیرد، نبودِ نشانه همان چیزی است که به بیرون می‌گوید
    فایل‌های این پوشه از یک نسل نیستند.
    """
    from .config.settings import SETTINGS
    from .factsheet import VERSION
    from .report.extracts import write_audit_report, write_expert_extracts

    clear_marker(SETTINGS.OUTPUT_DIR)
    res.dashboard_path = build_report(res)
    res.extract_paths = write_expert_extracts(res.main, SETTINGS.expert_extracts_dir)
    audit = os.path.join(SETTINGS.OUTPUT_DIR, "AIBL_Data_Conflicts_Audit.xlsx")
    write_audit_report(res.audit, audit)
    write_marker(SETTINGS.OUTPUT_DIR,
                 {"report": res.dashboard_path, "audit": audit}, VERSION)
