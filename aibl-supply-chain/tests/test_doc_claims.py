# -*- coding: utf-8 -*-
"""تست ادعاهای مستندات — عدد README باید با کد بخواند.

## اشتباهی که این فایل می‌بندد

README می‌گفت «۸ بسته قانونی، ۱۹ قاعده نیازمند تطبیق، ۹ شیت داشبورد»
در حالی که کد ۹ بسته، ۲۰ قاعده و ۱۳ شیت داشت. هیچ‌کدام باگ کد نبودند —
همه **ادعای مستند** بودند که با واقعیت نمی‌خواندند، و کاربر مجبور شد
خودش تست کند.

در سیستمی که کل ارزشش قابل‌ممیزی بودن است، عدد اشتباه در مستندات
اعتماد را دقیقاً همان‌قدر خراب می‌کند که باگ محاسباتی.

اجرا:  python tests/test_doc_claims.py
"""
from __future__ import annotations

import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from aibl.factsheet import collect  # noqa: E402

PASS, FAIL = [], []
_FA = "۰۱۲۳۴۵۶۷۸۹"


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


def fa(n: int) -> str:
    return "".join(_FA[int(d)] for d in str(n))


def read(name: str) -> str:
    p = os.path.join(ROOT, name)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


#: (الگو در متن، کلید در شناسنامه، شرح)
# ⚠️ ادعای «تعداد تست» عمداً اینجا نیست: سنجیدنش یعنی اجرای همه مجموعه‌ها
# از داخل یک مجموعه — بازگشتی و کند. آن یکی را run_all_tests.py می‌سنجد،
# چون همان‌جا عدد واقعی را در دست دارد.
CLAIMS = [
    (r"(\S+) بسته YAML", "rule_packs", "بسته قانونی"),
    (r"\*\*(\S+) قاعده\*\* که باید", "needs_verification", "قاعده نیازمند تطبیق"),
    (r"داشبورد — (\S+) شیت", "dashboard_sheets", "شیت داشبورد"),
]


def test_readme_numbers() -> None:
    print("\n── ۱) اعداد README در برابر کد ──")
    facts = collect()
    txt = read("README.md")
    if not txt:
        check("README پیدا شد", False)
        return

    for pattern, key, label in CLAIMS:
        m = re.search(pattern, txt)
        if not m:
            check(f"ادعای «{label}» در README یافت شد", False,
                  "الگو تطبیق نخورد — README را بررسی کنید")
            continue
        claimed_fa = m.group(1)
        claimed = int("".join(str(_FA.index(c)) if c in _FA else c
                              for c in claimed_fa)) if claimed_fa.strip("۰۱۲۳۴۵۶۷۸۹0123456789") == "" else None
        actual = facts[key]
        check(f"«{label}»: README می‌گوید {claimed_fa}، کد می‌گوید {fa(actual)}",
              claimed == actual,
              "" if claimed == actual else "README را با python -m aibl.factsheet هماهنگ کنید")


def test_version_single_source() -> None:
    print("\n── ۲) نسخه تنها یک منبع دارد ──")
    import aibl
    import aibl.version as V
    from aibl.factsheet import VERSION

    check("aibl.__version__ با شناسنامه یکی است", aibl.__version__ == VERSION,
          f"{aibl.__version__} / {VERSION}")
    check("version.PACKAGE_VERSION با شناسنامه یکی است",
          V.PACKAGE_VERSION == VERSION, f"{V.PACKAGE_VERSION} / {VERSION}")
    # هیچ نسخه هاردکد دیگری در پکیج نمانده باشد
    hard = []
    for root, _, files in os.walk(os.path.join(ROOT, "aibl")):
        for f in files:
            if not f.endswith(".py") or f == "factsheet.py":
                continue
            s = open(os.path.join(root, f), encoding="utf-8").read()
            for m in re.finditer(r'(?:__version__|PACKAGE_VERSION)\s*=\s*"(\d+\.\d+\.\d+)"', s):
                hard.append(f"{f}: {m.group(1)}")
    check("هیچ نسخه هاردکدی در پکیج نمانده", not hard, "؛ ".join(hard) or "پاک")


def test_factsheet_runs() -> None:
    print("\n── ۳) شناسنامه اجرا می‌شود ──")
    import subprocess
    r = subprocess.run([sys.executable, "-m", "aibl.factsheet"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    check("python -m aibl.factsheet بدون خطا اجرا می‌شود", r.returncode == 0,
          (r.stderr or "").strip()[-90:])
    check("همه کلیدهای شناسنامه چاپ می‌شوند",
          all(k in r.stdout for k in ("بسته قانونی", "شیت داشبورد", "نسخه پکیج")))


if __name__ == "__main__":
    print("=" * 78)
    print("AIBL — تست ادعاهای مستندات")
    print("=" * 78)
    test_readme_numbers()
    test_version_single_source()
    test_factsheet_runs()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
