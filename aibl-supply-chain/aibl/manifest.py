# -*- coding: utf-8 -*-
"""مانیفست فایل‌ها — تشخیص «کدام فایل قدیمی مانده».

پس از خطای واقعی ``'SourceSpec' object has no attribute 'frame_map'`` که از
کپی جزئی فایل‌ها ناشی شد، این ماژول اثر انگشت (SHA-256) هر فایل پکیج را
نگه می‌دارد. ``python -m aibl.doctor`` دقیقاً می‌گوید کدام فایل‌ها تغییر
کرده، غایب‌اند یا اضافه‌اند — بنابراین برای رفع یک باگ فقط همان چند فایل
جایگزین می‌شود، نه کل پکیج.

    ساخت مانیفست:   python -m aibl.manifest
    بررسی:          python -m aibl.doctor
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(PKG_DIR, "MANIFEST.json")
TRACKED_EXT = (".py", ".yaml", ".yml")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def scan() -> Dict[str, str]:
    """{مسیر نسبی: هش} برای همه فایل‌های پکیج."""
    out: Dict[str, str] = {}
    for root, dirs, files in os.walk(PKG_DIR):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in sorted(files):
            if not f.endswith(TRACKED_EXT):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, PKG_DIR).replace("\\", "/")
            out[rel] = _sha256(full)
    return out


def write() -> str:
    from .version import PACKAGE_VERSION
    data = {"package_version": PACKAGE_VERSION, "files": scan()}
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    return MANIFEST_PATH


@dataclass
class FileIssue:
    kind: str        # missing | changed | extra
    path: str

    @property
    def message(self) -> str:
        where = f"aibl/{self.path}"
        return {
            "missing": f"فایل «{where}» وجود ندارد — کپی ناقص بوده است.",
            "changed": f"فایل «{where}» با نسخه رسمی این پکیج یکی نیست "
                       f"(قدیمی یا دست‌کاری‌شده).",
            "extra": f"فایل «{where}» در مانیفست نیست — احتمالاً بازمانده نسخه قبلی.",
        }[self.kind]


def verify() -> List[FileIssue]:
    if not os.path.exists(MANIFEST_PATH):
        return []
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        expected = json.load(f).get("files", {})
    actual = scan()
    issues: List[FileIssue] = []
    for rel, h in expected.items():
        if rel not in actual:
            issues.append(FileIssue("missing", rel))
        elif actual[rel] != h:
            issues.append(FileIssue("changed", rel))
    for rel in actual:
        if rel not in expected and rel != "MANIFEST.json":
            issues.append(FileIssue("extra", rel))
    return issues


def main() -> int:
    path = write()
    with open(path, encoding="utf-8") as f:
        n = len(json.load(f)["files"])
    print(f"✅ مانیفست {n} فایل نوشته شد: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
