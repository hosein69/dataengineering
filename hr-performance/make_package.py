# -*- coding: utf-8 -*-
"""ساخت بستهٔ توزیع HRPerf.

## چرا این فایل وجود دارد

بستهٔ AIBL نسخهٔ ۲۶٫۱۵٫۰ با یک دستور فوریِ پوسته ساخته شد و آن دستور
**فایل‌های نقطه‌دار را برنداشت**؛ `.streamlit/config.toml` در بسته نبود.
بدون آن، Streamlit تم خودش را می‌گذارد و آن تم از حالت روشن/تاریکِ
مرورگر پیروی می‌کند: روی ویندوزِ تاریک، متن سفید شد روی پس‌زمینهٔ روشن —
نوار کناری و فیلترها نامرئی شدند. بسته‌های HRPerf با همان دستور ساخته
شده بودند و همان نقص را داشتند.

پس دو قاعده اینجا قفل است: فهرست محتوا **صریح** است، و بعد از ساخت،
بسته **بازرسی** می‌شود.
"""
from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

TREES = ["hrperf", "app", "tests", ".streamlit"]
FILES = ["README.md", "requirements.txt", "run_all_tests.py", "make_package.py"]
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".ruff_cache", ".venv"}
SKIP_SUFFIX = {".pyc", ".pyo", ".zip", ".log"}

REQUIRED = [
    ".streamlit/config.toml",   # نبودنش تم را به مرورگر می‌سپارد → متن نامرئی
    "app/dashboard.py", "app/styles.py",
    "hrperf/pipeline.py", "hrperf/report/aqua.py", "hrperf/report/theme.py",
    "hrperf/report/dispatch.py", "run_all_tests.py", "requirements.txt",
]


def refresh_theme_config() -> None:
    from hrperf.report.theme import config_toml
    out = ROOT / ".streamlit" / "config.toml"
    out.parent.mkdir(exist_ok=True)
    text = config_toml()
    if not out.exists() or out.read_text(encoding="utf-8").strip() != text.strip():
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
                if p.suffix.lower() not in SKIP_SUFFIX:
                    out.append(p)
    return sorted(set(out))


def build(version: str) -> Path:
    refresh_theme_config()
    target = ROOT / f"HRPerf_V{version.replace('.', '_')}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in members():
            z.write(p, p.relative_to(ROOT).as_posix())
        for note in sorted(ROOT.glob("RELEASE_NOTES_*.md")):
            z.write(note, note.name)

    inside = set(zipfile.ZipFile(target).namelist())
    missing = [r for r in REQUIRED if r not in inside]
    if missing:
        target.unlink(missing_ok=True)
        raise SystemExit("بسته ناقص بود و ساخته نشد. غایب: " + "، ".join(missing))
    print(f"✅ {target.name} — {len(inside)} پرونده، "
          f"{target.stat().st_size / 1024:,.0f} کیلوبایت")
    print(f"   بازرسی: هر {len(REQUIRED)} پروندهٔ الزامی داخل بسته هست.")
    return target


if __name__ == "__main__":
    from hrperf.version import VERSION
    build(sys.argv[1] if len(sys.argv) > 1 else VERSION)
