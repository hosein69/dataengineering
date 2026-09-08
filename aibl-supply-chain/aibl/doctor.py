# -*- coding: utf-8 -*-
"""بازرس نصب (Doctor) — قبل از هر اجرا، محیط را عیب‌یابی می‌کند.

اجرا:  python -m aibl.doctor

این ماژول دقیقاً همان خطایی را می‌گیرد که در اجرای اول روی شبکه IKCO رخ داد:
فایل‌ها به‌صورت تخت کپی شده بودند، `calendar.py` روی ماژول استاندارد پایتون
سایه انداخته بود و pandas هنگام import شکست می‌خورد.
"""
from __future__ import annotations

import glob
import importlib.util
import os
import sys
from typing import List, Tuple

OK, WARN, ERR = "✅", "⚠️ ", "❌"

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


#: ماژول‌هایی که اگر فایلی هم‌نامشان در مسیر جستجو باشد، پایتون یا pandas می‌شکند.
CRITICAL_STDLIB = [
    "calendar", "io", "types", "copy", "random", "select", "token", "code",
    "string", "queue", "platform", "secrets", "signal", "socket", "stat",
    "abc", "enum", "json", "csv", "time", "datetime", "math", "re", "os",
    "collections", "logging", "typing", "functools", "operator", "warnings",
    "email", "hashlib", "struct", "array", "numbers", "test", "parser",
]

REQUIRED_PACKAGES = [
    ("pandas", "pip install pandas"),
    ("numpy", "pip install numpy"),
    ("openpyxl", "pip install openpyxl"),
    ("yaml", "pip install pyyaml"),
]
OPTIONAL_PACKAGES = [
    ("jdatetime", "اختیاری — مبدل شمسی داخلی جایگزین آن است"),
    ("sklearn", "اختیاری — برای تشخیص آنومالی"),
]

_findings: List[Tuple[str, str]] = []


def _say(level: str, msg: str) -> None:
    _findings.append((level, msg))
    print(f"{level} {msg}")


# ═══════════ ۱) سایه‌اندازی روی کتابخانه استاندارد ═══════════
def _user_search_dirs() -> List[str]:
    """فقط پوشه‌هایی از sys.path که «مال کاربر» هستند — نه stdlib و نه site-packages.

    اینها همان مسیرهایی‌اند که می‌توانند روی کتابخانه استاندارد سایه بیندازند،
    چون در sys.path جلوتر از stdlib قرار دارند.
    """
    import sysconfig
    system = {os.path.realpath(p) for p in sysconfig.get_paths().values() if p}
    out = []
    for d in sys.path:
        if not d or not os.path.isdir(d):
            continue
        real = os.path.realpath(d)
        if real in system:
            continue
        if any(tok in real.replace("\\", "/") for tok in
               ("site-packages", "dist-packages", "/lib/python", "\\Lib\\")):
            continue
        if real not in out:
            out.append(real)
    return out


def check_shadowing() -> None:
    print("\n── ۱) بررسی سایه‌اندازی روی کتابخانه استاندارد پایتون ──")
    hits = 0
    dirs = _user_search_dirs()
    for d in dirs:
        for name in CRITICAL_STDLIB:
            for cand in (os.path.join(d, name + ".py"),
                         os.path.join(d, name, "__init__.py")):
                if os.path.exists(cand):
                    hits += 1
                    _say(ERR, f"فایل «{cand}» روی ماژول استاندارد «{name}» سایه انداخته است.")
                    _say(ERR, "   ← علت خطای «attempted relative import» هنگام import pandas. "
                              "این فایل را جابه‌جا یا حذف کنید.")

    # بررسی مضاعف: ماژول‌های حیاتی واقعاً از کجا بارگذاری می‌شوند؟
    import sysconfig
    stdlib = os.path.realpath(sysconfig.get_paths()["stdlib"])
    for name in ("calendar", "io", "datetime", "json", "csv"):
        try:
            spec = importlib.util.find_spec(name)
            origin = getattr(spec, "origin", None)
            if origin and origin not in ("built-in", "frozen"):
                if not os.path.realpath(origin).startswith(stdlib):
                    hits += 1
                    _say(ERR, f"ماژول «{name}» از مسیر غیراستاندارد بارگذاری می‌شود: {origin}")
        except Exception:
            continue

    if not hits:
        _say(OK, f"هیچ فایلی روی ماژول‌های استاندارد سایه نینداخته است "
                 f"({len(dirs)} مسیر کاربر بررسی شد).")


# ═══════════ ۲) ساختار پکیج ═══════════
def check_versions() -> None:
    """اختلاف نسخه فایل‌ها — علت خطای 'SourceSpec' has no attribute 'frame_map'."""
    print("\n── ۲) بررسی هم‌نسخه بودن فایل‌های پکیج ──")
    try:
        from .version import PACKAGE_VERSION, check_contracts
        print(f"   نسخه پکیج: {PACKAGE_VERSION}")
        issues = check_contracts()
        if issues:
            for i in issues:
                _say(ERR, i.message)
            _say(ERR, "   ← فقط همین فایل‌ها را با نسخه جدید جایگزین کنید؛ "
                      "نیازی به کپی مجدد کل پکیج نیست.")
        else:
            _say(OK, "تمام قراردادهای بین‌ماژولی سازگارند.")
    except Exception as ex:
        _say(ERR, f"بررسی نسخه ممکن نشد: {ex}")

    try:
        from .manifest import verify
        file_issues = verify()
        if not file_issues:
            _say(OK, "اثر انگشت همه فایل‌ها با مانیفست رسمی می‌خواند.")
        else:
            for fi in file_issues[:15]:
                _say(ERR if fi.kind != "extra" else WARN, fi.message)
            changed = [f.path for f in file_issues if f.kind in ("changed", "missing")]
            if changed:
                _say(ERR, f"   ← فایل‌های نیازمند به‌روزرسانی ({len(changed)} عدد): "
                          + "، ".join(changed[:8]))
                _say(ERR, "   ← فقط همین فایل‌ها را جایگزین کنید؛ "
                          "نیازی به کپی مجدد کل پکیج نیست.")
    except Exception as ex:
        _say(WARN, f"مانیفست بررسی نشد: {ex}")


def check_stages() -> None:
    """گراف علّی مرحله‌ها — آیا هر مرحله ورودی لازمش را دارد؟"""
    print("\n── ۲.۵) بررسی گراف فرآیند ──")
    try:
        from .adapters.base import KEY_BL, KEY_EMP, KEY_MATERIAL, KEY_ORDER, KEY_REG
        from .stages import discover, validate_graph
        stages = discover()
        base = [KEY_BL, KEY_ORDER, KEY_REG, KEY_EMP, KEY_MATERIAL,
                "MOGH_PRESENT", "COT_DATE", "NTSW_ALLOC_DATE", "ORC_STATUS"]
        warns = validate_graph(stages, base)
        _say(OK, f"{len(stages)} مرحله کشف و زنجیره علّی آن‌ها تأیید شد: "
                 + " → ".join(s.name for s in stages))
        for w in warns:
            _say(WARN, w)
    except Exception as ex:
        _say(ERR, f"گراف مرحله‌ها نامعتبر است: {ex}")


def check_layout() -> None:
    print("\n── ۳) بررسی ساختار پکیج ──")
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)

    expected = ["core", "config", "dataio", "adapters", "engines", "stages",
                "narrate", "report", "resolve", "rulebook", "rules"]
    missing = [p for p in expected
               if not os.path.isdir(os.path.join(here, p))]
    if missing:
        _say(ERR, f"زیرپوشه‌های غایب در پکیج: {missing}")
        _say(ERR, "   ← احتمالاً فایل‌ها تخت کپی شده‌اند. کل پوشه aibl/ را با ساختار درخت کپی کنید.")
    else:
        _say(OK, f"هر {len(expected)} زیرپوشه پکیج موجود است ({here})")

    no_init = [p for p in expected if p != "rules"
               and os.path.isdir(os.path.join(here, p))
               and not os.path.exists(os.path.join(here, p, "__init__.py"))]
    if no_init:
        _say(ERR, f"فایل __init__.py غایب در: {no_init}")
    else:
        _say(OK, "تمام زیرپکیج‌ها __init__.py دارند.")

    # فایل تخت در ریشه اجرا
    flat = [os.path.basename(f) for f in glob.glob(os.path.join(root, "*.py"))
            if os.path.basename(f) in
            {"jalali.py", "text.py", "partition.py", "narrator.py", "merge.py",
             "reader.py", "dashboard.py", "commitment.py", "risk.py", "loader.py"}]
    if flat:
        _say(ERR, f"فایل‌های پکیج به‌صورت تخت در {root} پیدا شدند: {flat}")
        _say(ERR, "   ← اینها باید داخل زیرپوشه‌های aibl/ باشند، نه کنار آن.")
    else:
        _say(OK, "هیچ فایل پکیجی به‌صورت تخت رها نشده است.")

    # نسخه قدیمی
    legacy = os.path.join(root, "aibl.py")
    if os.path.exists(legacy):
        _say(ERR, f"نسخه تک‌فایلی قدیمی «{legacy}» هنوز موجود است.")
        _say(ERR, "   ← «python -m aibl.pipeline» اول به همین فایل می‌رسد. "
                  "آن را به aibl_legacy_v20.py.bak تغییر نام دهید.")
    else:
        _say(OK, "نسخه تک‌فایلی قدیمی aibl.py در مسیر نیست.")


# ═══════════ ۳) وابستگی‌ها ═══════════
def check_packages() -> None:
    print("\n── ۴) بررسی کتابخانه‌ها ──")
    print(f"   پایتون {sys.version.split()[0]} — {sys.executable}")
    for name, hint in REQUIRED_PACKAGES:
        if importlib.util.find_spec(name) is None:
            _say(ERR, f"کتابخانه الزامی «{name}» نصب نیست → {hint}")
        else:
            try:
                mod = importlib.import_module(name)
                ver = getattr(mod, "__version__", "?")
                _say(OK, f"{name} {ver}")
            except Exception as ex:
                _say(ERR, f"«{name}» نصب است ولی import نمی‌شود: {ex}")
    for name, note in OPTIONAL_PACKAGES:
        state = "نصب است" if importlib.util.find_spec(name) else "نصب نیست"
        _say(OK if importlib.util.find_spec(name) else WARN, f"{name}: {state} — {note}")


# ═══════════ ۴) قوانین و رجیستری ═══════════
def check_rules_and_sources() -> None:
    print("\n── ۵) بررسی کتابخانه قوانین و رجیستری سورس‌ها ──")
    try:
        from .rulebook import get_rulebook
        rb = get_rulebook(reload=True)
        errors = [i for i in rb.validate() if i.level == "error"]
        if errors:
            for e in errors:
                _say(ERR, f"قانون نامعتبر [{e.pack}] {e.path}: {e.message}")
        else:
            _say(OK, f"{len(rb.packs)} بسته قانونی سالم بارگذاری شد.")
        _say(WARN, f"{len(rb.needs_verification())} قاعده نیازمند تطبیق با آخرین بخشنامه است "
                   f"(python -m aibl.rulebook.validate)")
    except Exception as ex:
        _say(ERR, f"بارگذاری کتابخانه قوانین شکست خورد: {ex}")

    try:
        from .adapters import discover
        from .config.sources import SOURCES
        reg = discover()
        _say(OK, f"{len(reg)} adapter کشف شد برای {len(SOURCES)} سورس فعال.")
        orphan = set(SOURCES) - set(reg)
        if orphan:
            _say(ERR, f"سورس‌های بدون adapter: {sorted(orphan)}")
    except Exception as ex:
        _say(ERR, f"کشف adapterها شکست خورد: {ex}")


# ═══════════ ۵) مسیرهای شبکه ═══════════
def check_paths() -> None:
    print("\n── ۶) بررسی دسترسی به مسیرهای شبکه ──")
    from .config.settings import SETTINGS
    from .config.sources import SOURCES
    seen = set()
    for spec in SOURCES.values():
        if spec.folder in seen:
            continue
        seen.add(spec.folder)
        if os.path.isdir(spec.folder):
            n = len([f for f in glob.glob(os.path.join(spec.folder, spec.pattern + ".xls*"))
                     if not os.path.basename(f).startswith("~$")])
            _say(OK if n else WARN,
                 f"{spec.key:<15} {n} فایل منطبق — {spec.folder}")
        else:
            _say(WARN, f"{spec.key:<15} پوشه در دسترس نیست — {spec.folder}")
    for label, path in (("خروجی", SETTINGS.OUTPUT_DIR), ("لاگ", SETTINGS.LOG_DIR)):
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".aibl_write_test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            _say(OK, f"مسیر {label} قابل نوشتن است: {path}")
        except Exception as ex:
            _say(ERR, f"مسیر {label} قابل نوشتن نیست ({path}): {ex}")


def main() -> int:
    print("═" * 78)
    print("AIBL Doctor — بازرس نصب و محیط اجرا")
    print("═" * 78)
    print(f"پوشه جاری: {os.getcwd()}")

    check_shadowing()
    check_versions()
    check_stages()
    check_layout()
    check_packages()
    check_rules_and_sources()
    check_paths()

    errors = [m for lvl, m in _findings if lvl == ERR]
    warns = [m for lvl, m in _findings if lvl == WARN]
    print("\n" + "═" * 78)
    print(f"نتیجه: {len(errors)} خطا | {len(warns)} هشدار")
    if errors:
        print("\nخطاهایی که باید پیش از اجرا رفع شوند:")
        for m in errors:
            print(f"  ❌ {m}")
        print("\nپس از رفع، دوباره اجرا کنید: python -m aibl.doctor")
    else:
        print("✅ محیط سالم است. اکنون اجرا کنید:  python -m aibl.pipeline")
        print("💡 اگر KPIها صفر یا غیرمنطقی بودند، اول این را بزنید:")
        print("   python -m aibl.diagnose --excel     ← می‌گوید کدام رابطه برقرار نشده")
    print("═" * 78)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
