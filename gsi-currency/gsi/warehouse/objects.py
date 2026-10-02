# -*- coding: utf-8 -*-
"""پوشه بایگانی با اثرانگشت محتوا، کنار فایل SQLite انبار داده.

هر شیء (بایت‌های اصلی فایل منبع، فریم Parquet، بایگانی خانه‌های فیزیکی یک کاربرگ)
یک‌بار با نام ``<sha256>.<ext>`` در ``<db>.objects/<دو حرف اول>/`` نوشته می‌شود. محتوای
تکراری دوباره نوشته نمی‌شود و هیچ شیئی بازنویسی یا پاک نمی‌شود؛ نام هر فایل همان
اثرانگشت محتوایش است، پس خرابی یا جابه‌جایی با یک مقایسه ساده پیدا می‌شود.

چرا بیرون از SQLite: بایت‌های بزرگ داخل پایگاه داده، هر بررسی سلامت SQLite را به
خواندن گیگابایت‌ها داده کشانده بود (بررسی سریع ۴۸۲ ثانیه در اجرای واقعی). حالا فایل
SQLite فقط فهرست‌ها، سوابق و دفتر تغییرات را نگه می‌دارد.
"""
from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path

_SAFE_EXT = re.compile(r"[a-z0-9][a-z0-9.]{0,15}")


def objects_root(db_path: Path) -> Path:
    db_path = Path(db_path)
    return db_path.with_name(db_path.name + ".objects")


def clean_ext(ext: str) -> str:
    text = str(ext or "").strip().lower().lstrip(".")
    return text if _SAFE_EXT.fullmatch(text) else "bin"


class ObjectStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path(self, sha: str, ext: str) -> Path:
        sha = str(sha)
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError(f"اثرانگشت نامعتبر: {sha!r}")
        return self.root / sha[:2] / f"{sha}.{clean_ext(ext)}"

    def put(self, data: bytes, ext: str) -> str:
        """بایت‌ها را یک‌بار می‌نویسد و اثرانگشت را برمی‌گرداند."""
        data = bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        target = self.path(sha, ext)
        if target.exists() and target.stat().st_size == len(data):
            return sha
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f"{target.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            with open(tmp, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.replace(tmp, target)
            except PermissionError:
                # ویندوز: نویسنده دیگری همین محتوا را همین حالا گذاشته و باز نگه داشته است
                if not (target.exists() and target.stat().st_size == len(data)):
                    raise
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
        return sha

    def get(self, sha: str, ext: str, *, verify: bool = True) -> bytes:
        target = self.path(sha, ext)
        if not target.exists():
            raise FileNotFoundError(f"شیء بایگانی پیدا نشد: {target}")
        data = target.read_bytes()
        if verify and hashlib.sha256(data).hexdigest() != sha:
            raise RuntimeError(f"شیء بایگانی خراب است (اثرانگشت نمی‌خواند): {target}")
        return data

    def exists(self, sha: str, ext: str, size: int | None = None) -> bool:
        target = self.path(sha, ext)
        if not target.exists():
            return False
        return size is None or target.stat().st_size == int(size)

    def verify(self, sha: str, ext: str) -> bool:
        try:
            self.get(sha, ext, verify=True)
            return True
        except (FileNotFoundError, RuntimeError):
            return False

    def link_or_copy(self, sha: str, ext: str, other: "ObjectStore") -> bool:
        """شیء را در پوشه بایگانی دیگری (پشتیبان) می‌گذارد؛ اول hardlink، بعد کپی."""
        src = self.path(sha, ext)
        dst = other.path(sha, ext)
        if dst.exists() and dst.stat().st_size == src.stat().st_size:
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(src, dst)
        except OSError:
            other.put(src.read_bytes(), ext)
        return True
