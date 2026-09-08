# -*- coding: utf-8 -*-
"""اعتبارسنجی کتابخانه قوانین.

اجرا:  python -m aibl.rulebook.validate
"""
from __future__ import annotations

import sys

from .loader import get_rulebook

def _force_utf8_stdio() -> None:
    """ویندوز هنگام redirect خروجی از cp1252 استفاده می‌کند و متن فارسی
    را نمی‌تواند encode کند (UnicodeEncodeError: 'charmap' codec).
    این تابع خروجی را روی UTF-8 قفل می‌کند."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_force_utf8_stdio()



def main() -> int:
    rb = get_rulebook(reload=True)
    print("═" * 78)
    print("اعتبارسنجی کتابخانه قوانین AIBL")
    print("═" * 78)
    s = rb.summary()
    print(f"مسیر قوانین : {s['rules_dir']}")
    print(f"تاریخ مرجع  : {s['as_of']}")
    print("بسته‌های بارگذاری‌شده:")
    for name, ver in s["packs"].items():
        print(f"   • {name:<16} نسخه {ver}")

    issues = rb.validate()
    errors = [i for i in issues if i.level == "error"]
    print(f"\nخطاهای ساختاری: {len(errors)}")
    for i in errors:
        print(f"   ❌ [{i.pack}] {i.path}: {i.message}")

    pending = rb.needs_verification()
    print(f"\nقواعد نیازمند تطبیق با آخرین بخشنامه: {len(pending)}")
    for i in pending:
        print(f"   ⚠️  [{i.pack}] {i.path} — {i.message}")

    print("═" * 78)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
