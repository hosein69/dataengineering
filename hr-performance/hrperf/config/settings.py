# -*- coding: utf-8 -*-
"""پیکربندی مرکزی — مسیرها **کشف** می‌شوند، نه حدس زده.

پکیج قبلی مسیر ورودی را ثابت روی ``D:\\HRPerf\\input_files`` می‌گذاشت. هرکس
پکیج را جای دیگری باز می‌کرد (مثلاً ``G:\\000\\hru``) خطای «هیچ فردی برای
سنجش پیدا نشد» می‌گرفت، بدون آنکه بفهمد کد کجا را گشته است. پیامی که
نمی‌گوید کجا را گشته، دیباگ را به حدس تبدیل می‌کند.

ترتیب جست‌وجو برای ``input_files`` (اولین موردی که **فایل داده** دارد):

1. متغیر محیطی ``HRP_INPUT`` — همیشه مقدم است
2. پوشه جاری (جایی که فرمان اجرا شده)
3. کنار خود پکیج (جایی که فایل زیپ باز شده)
4. ``HRP_HOME`` (پیش‌فرض ``~/.hrperf``)
5. مسیر تولید ویندوز — فقط روی ویندوز

خروجی/لاگ/دیتابیس هم **کنار همان ورودیِ پیداشده** ساخته می‌شوند تا نتیجه
اجرا جایی باشد که کاربر انتظارش را دارد، نه در درایو دیگری.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional

_IS_WINDOWS = sys.platform.startswith("win")

#: پسوندهایی که «فایل داده» شمرده می‌شوند (README تنها، پوشه را پر نمی‌کند)
DATA_SUFFIXES = (".xlsx", ".xlsm", ".xls", ".csv", ".json")

#: مسیر تولید روی ویندوز — پیش‌فرض تاریخی، حالا فقط یک نامزد از چند نامزد
WINDOWS_BASE = r"D:\HRPerf"


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _home() -> Path:
    return Path(os.environ.get("HRP_HOME") or (Path.home() / ".hrperf"))


def _pkg_root() -> Path:
    """پوشه‌ای که پکیج در آن باز شده (والدِ بستهٔ ``hrperf``)."""
    return Path(__file__).resolve().parents[2]


def bases() -> List[Path]:
    """پایه‌های جست‌وجو، به ترتیب اولویت و بدون تکرار."""
    out: List[Path] = []
    for p in (Path.cwd(), _pkg_root(), _home(),
              Path(WINDOWS_BASE) if _IS_WINDOWS else None):
        if p is None:
            continue
        try:
            q = p.resolve()
        except OSError:
            continue
        if q not in out:
            out.append(q)
    return out


def input_candidates() -> List[Path]:
    """همان مسیرهایی که واقعاً بررسی می‌شوند — برای نمایش در پیام خطا."""
    return [b / "input_files" for b in bases()]


def has_data(p: Path) -> bool:
    """آیا این پوشه دست‌کم یک فایل دادهٔ خواندنی دارد؟"""
    try:
        if not p.is_dir():
            return False
        return any(f.is_file() and not f.name.startswith("~$")
                   and f.suffix.lower() in DATA_SUFFIXES for f in p.iterdir())
    except OSError:
        return False


def resolve_input() -> str:
    """اولین نامزدی که داده دارد؛ وگرنه اولین نامزدی که وجود دارد."""
    env = os.environ.get("HRP_INPUT")
    if env:
        return env
    cands = input_candidates()
    for c in cands:
        if has_data(c):
            return str(c)
    for c in cands:
        if c.is_dir():
            return str(c)
    return str(cands[0])


def _beside_input(env_key: str, leaf: str) -> str:
    """خروجی کنار ورودی — نه در درایوی که کاربر هرگز آنجا را نگاه نمی‌کند."""
    env = os.environ.get(env_key)
    return env if env else str(Path(resolve_input()).resolve().parent / leaf)


@dataclass(frozen=True)
class Settings:
    INPUT_DIR: str = field(default_factory=resolve_input)
    OUTPUT_DIR: str = field(
        default_factory=lambda: _beside_input("HRP_OUTPUT", "output"))
    LOG_DIR: str = field(
        default_factory=lambda: _beside_input("HRP_LOGS", "logs"))
    DB_PATH: str = field(
        default_factory=lambda: _beside_input("HRP_DB", "hrperf.sqlite"))
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
    def searched(self) -> List[Path]:
        """مسیرهایی که برای ورودی بررسی شدند — پیام خطا از همین می‌آید."""
        return input_candidates()

    @property
    def rules_dir(self) -> Path:
        if self.RULES_DIR:
            return Path(self.RULES_DIR)
        return Path(__file__).resolve().parent


SETTINGS = Settings()
