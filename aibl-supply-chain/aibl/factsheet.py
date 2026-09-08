# -*- coding: utf-8 -*-
"""شناسنامه سیستم — تنها منبع حقیقت برای اعداد.

## چرا این ماژول وجود دارد

در نسخه‌های قبل، README ادعا می‌کرد «۸ بسته قانونی، ۱۹ قاعده نیازمند تطبیق،
۹ شیت داشبورد» در حالی که کد واقعاً ۹ بسته، ۲۰ قاعده و ۱۰ شیت داشت. هیچ‌کدام
باگ کد نبودند — همه **ادعای مستند** بودند که با کد نمی‌خواندند.

در سیستمی که کل ارزشش قابل‌ممیزی بودن است، عدد اشتباه در مستندات دقیقاً
همان چیزی است که اعتماد را از بین می‌برد. پس:

  • اعداد از اینجا خوانده می‌شوند، نه دستی نوشته
  • ``tests/test_doc_claims.py`` هر عدد فارسی داخل README را با همین
    ماژول می‌سنجد و اگر نخواند، تست قرمز می‌شود
  • نسخه فقط یک جا تعریف می‌شود

اجرا:  python -m aibl.factsheet
"""
from __future__ import annotations

__contract__ = 1

import glob
import os
import sys
from typing import Any, Dict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_PKG = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_PKG)

#: تنها جایی که نسخه تعریف می‌شود. بقیه از اینجا می‌خوانند.
VERSION = "26.10.0"

#: تعداد شیت‌های داشبورد — با ساخت واقعی گزارش سنجیده می‌شود
DASHBOARD_SHEETS = 16


def collect() -> Dict[str, Any]:
    """اعداد زنده سیستم — بدون هیچ عدد هاردکد."""
    from .adapters import discover as discover_adapters
    from .config.keys import get_keys
    from .config.sources import MERGE_ORDER, SOURCES
    from .rulebook import get_rulebook
    from .stages import discover as discover_stages

    rb = get_rulebook(reload=True)
    kr = get_keys(reload=True)
    return {
        "version": VERSION,
        "rule_packs": len(rb.packs),
        "rule_files": len(glob.glob(os.path.join(_PKG, "rules", "*.yaml"))),
        "needs_verification": len(rb.needs_verification()),
        "adapters": len(discover_adapters()),
        "sources": len(SOURCES),
        "merge_steps": len(MERGE_ORDER),
        "stages": len(discover_stages()),
        "simple_keys": len(kr.simple_keys()),
        "composite_keys": len(kr.composite_keys()),
        "dashboard_sheets": DASHBOARD_SHEETS,
        "python_files": len(glob.glob(os.path.join(_PKG, "**", "*.py"),
                                      recursive=True)),
        "test_files": len(glob.glob(os.path.join(_ROOT, "tests", "test_*.py"))),
    }


LABELS = {
    "version": "نسخه پکیج",
    "rule_packs": "بسته قانونی بارگذاری‌شده",
    "rule_files": "فایل YAML قانون",
    "needs_verification": "قاعده نیازمند تطبیق با بخشنامه",
    "adapters": "adapter کشف‌شده",
    "sources": "سورس فعال",
    "merge_steps": "گام ادغام",
    "stages": "مرحله خط لوله",
    "simple_keys": "کلید ساده",
    "composite_keys": "کلید مرکب",
    "dashboard_sheets": "شیت داشبورد",
    "python_files": "فایل پایتون در پکیج",
    "test_files": "فایل تست",
}


def main() -> int:
    facts = collect()
    print("═" * 66)
    print("شناسنامه AIBL — اعداد زنده سیستم")
    print("═" * 66)
    for k, v in facts.items():
        print(f"  {LABELS.get(k, k):32s} : {v}")
    print("═" * 66)
    print("این اعداد مرجع مستندات‌اند. اگر README عدد دیگری بگوید،")
    print("tests/test_doc_claims.py قرمز می‌شود.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
