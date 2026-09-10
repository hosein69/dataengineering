# -*- coding: utf-8 -*-
"""ساخت بستهٔ توزیع AIBL.

## چرا این فایل وجود دارد

بستهٔ نسخهٔ ۲۶٫۱۵٫۰ با یک دستور فوریِ پوسته ساخته شد و آن دستور
**فایل‌های نقطه‌دار را برنداشت**. نتیجه: `.streamlit/config.toml` در بسته
نبود. بدون آن، Streamlit تم خودش را می‌گذارد و آن تم از حالت روشن/تاریکِ
مرورگر پیروی می‌کند؛ روی ویندوزِ تاریک، متن سفید شد روی پس‌زمینهٔ سبزِ
روشنِ ما — نوار کناری و فیلترها نامرئی شدند و کاربر فکر کرد امکانات از
بین رفته‌اند. هیچ تستی این را نمی‌گرفت، چون همهٔ تست‌ها روی درخت کد اجرا
می‌شدند نه روی بسته.

پس دو قاعده اینجا قفل است:

1. فهرست محتوا **صریح** است، نه حاصل یک الگوی پوسته.
2. بعد از ساخت، بسته **بازرسی** می‌شود؛ اگر پروندهٔ لازمی نبود، خطا
   می‌دهد و فایل ناقص را دور می‌ریزد.
"""
from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

#: پوشه‌هایی که کامل داخل بسته می‌روند
TREES = ["aibl", "app", "tests", ".streamlit", "poster"]

#: پرونده‌های تکیِ ریشه
FILES = ["README.md", "INSTALL.md", "INSTALL_MAC.md", "requirements.txt",
         "run_all_tests.py", "make_package.py", "recipients.example.yaml",
         "run_mac.command", "DESIGN_SYSTEM_ALBORZ.md"]

#: هرچه با این‌ها بخواند، داخل بسته نمی‌رود
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".ruff_cache", ".venv"}
SKIP_SUFFIX = {".pyc", ".pyo", ".zip", ".log"}

#: بدون این‌ها بسته معیوب است — بازرسی پس از ساخت روی همین‌هاست
#: باید با بیت اجرا داخل بسته بروند
EXECUTABLE = ["run_mac.command"]

REQUIRED = [
    "run_mac.command",         # بدون این، مک راه‌اندازی ندارد
    "INSTALL_MAC.md",
    ".streamlit/config.toml",   # نبودنش تم را به مرورگر می‌سپارد → متن نامرئی
    "aibl/report/alborz.py", "aibl/report/paykan.py",
    "poster/make_poster.py", "DESIGN_SYSTEM_ALBORZ.md",
    "app/studio.py", "app/styles.py", "app/theme.py",
    "aibl/pipeline.py", "aibl/report/aqua.py", "aibl/report/dispatch.py",
    "run_all_tests.py", "requirements.txt",
]


def refresh_theme_config() -> None:
    """`.streamlit/config.toml` را از `app/theme.py` بازتولید می‌کند."""
    from app.theme import config_toml
    out = ROOT / ".streamlit" / "config.toml"
    out.parent.mkdir(exist_ok=True)
    text = config_toml()
    if out.exists() and out.read_text(encoding="utf-8").strip() == text.strip():
        return
    out.write_text(text, encoding="utf-8")
    print(f"  · {out.relative_to(ROOT)} بازتولید شد")


def members() -> list[Path]:
    out: list[Path] = []
    for name in FILES:
        p = ROOT / name
        if p.exists():
            out.append(p)
    for tree in TREES:
        base = ROOT / tree
        if not base.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in sorted(filenames):
                p = Path(dirpath) / fn
                if p.suffix.lower() in SKIP_SUFFIX:
                    continue
                out.append(p)
    return sorted(set(out))


def build(version: str) -> Path:
    refresh_theme_config()
    target = ROOT / f"AIBL_V{version.replace('.', '_')}.zip"
    picked = members()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in picked:
            z.write(p, p.relative_to(ROOT).as_posix())
        for note in sorted(ROOT.glob("RELEASE_NOTES_*.md")):
            z.write(note, note.name)
        patch = ROOT / "PATCH_EMAIL_FROM_HR.patch"
        if patch.exists():
            z.write(patch, patch.name)

    inside = set(zipfile.ZipFile(target).namelist())
    missing = [r for r in REQUIRED if r not in inside]
    if missing:
        target.unlink(missing_ok=True)
        raise SystemExit("بسته ناقص بود و ساخته نشد. غایب: " + "، ".join(missing))

    # مک بدون بیت اجرا، راه‌انداز را اصلاً باز نمی‌کند: دوبار کلیک هیچ
    # نمی‌کند و کاربر نتیجه می‌گیرد بسته خراب است. همان درسِ
    # ‏`.streamlit/config.toml`‏ — چیزی که تست‌های درختِ کد نمی‌بینند،
    # اینجا روی خودِ بسته سنجیده می‌شود.
    with zipfile.ZipFile(target) as z:
        for name in EXECUTABLE:
            mode = (z.getinfo(name).external_attr >> 16) & 0o777
            if not mode & 0o111:
                target.unlink(missing_ok=True)
                raise SystemExit(
                    f"{name} بدون بیت اجرا بسته‌بندی شد؛ روی مک کار نمی‌کند.")

    size = target.stat().st_size / 1024
    print(f"✅ {target.name} — {len(inside)} پرونده، {size:,.0f} کیلوبایت")
    print(f"   بازرسی: هر {len(REQUIRED)} پروندهٔ الزامی داخل بسته هست.")
    return target


if __name__ == "__main__":
    from aibl.factsheet import VERSION
    build(sys.argv[1] if len(sys.argv) > 1 else VERSION)
