# -*- coding: utf-8 -*-
"""تست‌های سلامت import و استقرار (System / Deployment).

این مجموعه دقیقاً برای جلوگیری از تکرار خطای اجرای اول روی شبکه IKCO نوشته شده:
    ImportError: attempted relative import with no known parent package
که وقتی رخ داد که فایل‌های پکیج تخت کپی شدند و `calendar.py` روی ماژول
استاندارد پایتون سایه انداخت، و pandas هنگام import شکست خورد.

اجرا:  python tests/test_import_hygiene.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import sysconfig
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "aibl")
sys.path.insert(0, ROOT)

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


def _module_names() -> list[str]:
    """نام تمام ماژول‌ها و زیرپکیج‌های AIBL (بدون مسیر)."""
    names = []
    for root, dirs, files in os.walk(PKG):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for d in dirs:
            names.append(d)
        for f in files:
            if f.endswith(".py") and not f.startswith("__"):
                names.append(f[:-3])
    return sorted(set(names))


# ═══════════ ۱) هیچ ماژولی هم‌نام کتابخانه استاندارد نباشد ═══════════
def test_no_stdlib_collision() -> None:
    print("\n── ۱) تصادم نام با کتابخانه استاندارد ──")
    stdlib = set(sys.stdlib_module_names)
    ours = _module_names()
    collisions = sorted(set(ours) & stdlib)

    check("هیچ ماژول AIBL هم‌نام ماژول استاندارد پایتون نیست",
          not collisions,
          f"تصادم: {collisions}" if collisions else
          f"{len(ours)} ماژول بررسی شد، ۰ تصادم")

    check("ماژول تقویم به jalali تغییر نام یافته (نه calendar)",
          os.path.exists(os.path.join(PKG, "core", "jalali.py"))
          and not os.path.exists(os.path.join(PKG, "core", "calendar.py")))
    check("پکیج ورودی/خروجی dataio است (نه io)",
          os.path.isdir(os.path.join(PKG, "dataio"))
          and not os.path.isdir(os.path.join(PKG, "io")))


# ═══════════ ۲) بازتولید و رفع خطای واقعی ═══════════
def test_reproduce_and_fix() -> None:
    print("\n── ۲) بازتولید خطای واقعی شبکه IKCO ──")
    tmp = tempfile.mkdtemp(prefix="aibl_flat_")

    # حالت خراب: فایل تقویم تخت، هم‌نام calendar
    # Reproduce deterministically: cwd alone does not necessarily shadow stdlib
    # calendar on every Python launcher. Put the temporary module first on PYTHONPATH.
    bad_calendar = os.path.join(tmp, "calendar.py")
    with open(bad_calendar, "w", encoding="utf-8") as fh:
        fh.write("from .jalali import CalendarEngine\n")
    bad_env = dict(os.environ, PYTHONPATH=tmp + os.pathsep + ROOT)
    r = subprocess.run([sys.executable, "-c", "import calendar"],
                       cwd=tmp, capture_output=True, text=True, env=bad_env)
    reproduced = "attempted relative import" in r.stderr
    check("خطای اصلی با فایل تخت calendar.py بازتولید شد", reproduced,
          r.stderr.strip().splitlines()[-1][:70] if r.stderr else "بدون خطا!")

    # Doctor باید همین را بگیرد
    env = dict(os.environ, PYTHONPATH=ROOT)
    d = subprocess.run([sys.executable, "-m", "aibl.doctor"],
                       cwd=tmp, capture_output=True, text=True, env=env)
    check("Doctor این حالت را تشخیص می‌دهد و کد خروجی ۱ می‌دهد",
          d.returncode == 1 and "سایه انداخته" in d.stdout)

    # حالت سالم: فایل حذف شود
    os.remove(os.path.join(tmp, "calendar.py"))
    r2 = subprocess.run([sys.executable, "-c", "import pandas; print('ok')"],
                        cwd=tmp, capture_output=True, text=True)
    check("پس از حذف فایل متصادم، pandas سالم import می‌شود",
          "ok" in r2.stdout, r2.stderr.strip()[-70:] if r2.stderr else "")
    shutil.rmtree(tmp, ignore_errors=True)


# ═══════════ ۳) اجرا از هر پوشه‌ای ═══════════
def test_runs_from_any_cwd() -> None:
    print("\n── ۳) اجرا از پوشه‌های مختلف ──")
    env = dict(os.environ, PYTHONPATH=ROOT)
    for label, cwd in (("ریشه پروژه", ROOT),
                       ("پوشه موقت", tempfile.mkdtemp(prefix="aibl_cwd_")),
                       ("داخل خود پکیج", PKG)):
        r = subprocess.run(
            [sys.executable, "-c",
             "import aibl.pipeline as p; print('IMPORT_OK', p.Pipeline is not None)"],
            cwd=cwd, capture_output=True, text=True, env=env)
        check(f"import پکیج از «{label}» موفق است", "IMPORT_OK" in r.stdout,
              r.stderr.strip().splitlines()[-1][:80] if r.stderr else "")


# ═══════════ ۴) نقاط ورود ═══════════
def test_entry_points() -> None:
    print("\n── ۴) نقاط ورود ──")
    env = dict(os.environ, PYTHONPATH=ROOT)
    for label, args in (("python -m aibl.doctor", ["-m", "aibl.doctor"]),
                        ("python -m aibl.rulebook.validate", ["-m", "aibl.rulebook.validate"]),
                        ("python -m aibl rules", ["-m", "aibl", "rules"])):
        r = subprocess.run([sys.executable] + args, cwd=ROOT,
                           capture_output=True, text=True, env=env)
        check(f"«{label}» بدون استثنا اجرا می‌شود",
              "Traceback" not in r.stderr,
              r.stderr.strip().splitlines()[-1][:70] if r.stderr else f"exit={r.returncode}")


# ═══════════ ۵) کامل بودن ساختار ═══════════
def test_structure() -> None:
    print("\n── ۵) کامل بودن ساختار پکیج ──")
    subs = ["core", "config", "dataio", "adapters", "engines",
            "narrate", "report", "resolve", "rulebook"]
    missing = [s for s in subs
               if not os.path.exists(os.path.join(PKG, s, "__init__.py"))]
    check("تمام زیرپکیج‌ها __init__.py دارند", not missing, f"غایب: {missing}")

    rules = os.path.join(PKG, "rules")
    yamls = sorted(f for f in os.listdir(rules) if f.endswith(".yaml"))
    check("هر ۱۰ فایل قانون در پکیج هستند", len(yamls) == 10, ", ".join(yamls))

    check("__main__.py برای «python -m aibl» موجود است",
          os.path.exists(os.path.join(PKG, "__main__.py")))
    check("doctor.py موجود است", os.path.exists(os.path.join(PKG, "doctor.py")))

    import aibl
    import aibl.version as V
    from aibl.factsheet import VERSION
    check("نسخه در همه‌جا یکی است (تنها منبع: factsheet)",
          aibl.__version__ == VERSION and V.PACKAGE_VERSION == VERSION,
          f"{aibl.__version__} / {V.PACKAGE_VERSION} / {VERSION}")


# ═══════════ ۶) استقلال از jdatetime ═══════════
def test_no_hard_dependency() -> None:
    print("\n── ۶) وابستگی‌های اختیاری ──")
    code = (
        "import sys\n"
        "sys.modules['jdatetime'] = None\n"
        "import importlib\n"
        "m = importlib.import_module('aibl.core.jalali')\n"
        "print('JD', m.HAS_JDATETIME, m.CalendarEngine.parse('1404/01/15'))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                       capture_output=True, text=True,
                       env=dict(os.environ, PYTHONPATH=ROOT))
    check("بدون jdatetime هم تاریخ شمسی درست تبدیل می‌شود",
          "2025-04-04" in r.stdout, r.stdout.strip() or r.stderr.strip()[-80:])

    stdlib = os.path.realpath(sysconfig.get_paths()["stdlib"])
    import calendar as std_cal
    check("ماژول استاندارد calendar از stdlib بارگذاری می‌شود",
          os.path.realpath(std_cal.__file__).startswith(stdlib),
          std_cal.__file__)


if __name__ == "__main__":
    print("=" * 78)
    print("AIBL V22 — تست سلامت import و استقرار")
    print("=" * 78)
    test_no_stdlib_collision()
    test_reproduce_and_fix()
    test_runs_from_any_cwd()
    test_entry_points()
    test_structure()
    test_no_hard_dependency()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
