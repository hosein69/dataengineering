# -*- coding: utf-8 -*-
"""اجرای همه مجموعه‌های تست.    python run_all_tests.py"""
from __future__ import annotations

import os
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
SUITES = [
    ("۱) مدل، امتیازدهی و گروه همتا", "tests/test_model_and_scoring.py"),
    ("۲) علیت، خط لوله، پایگاه داده و گزارش", "tests/test_causal_and_pipeline.py"),
    ("۳) عدالت، گراف، ویرایش مدل و خروجی داینامیک",
     "tests/test_fairness_and_graph.py"),
    ("۴) موتور کلاستر، دفترچه سورس و نقشهٔ سیال",
     "tests/test_engine_and_studio.py"),
    ("۵) بسته‌بندی، کف خوانایی و ارسال", "tests/test_packaging.py"),
]


#: سقف زمان هر مجموعه — تست تولیدی نباید بدون سقف اجرا شود.
SUITE_TIMEOUT_S = int(os.environ.get("HRP_TEST_TIMEOUT", "600"))


def main() -> int:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    ok = fail = 0
    failed = []
    #: خودِ خطوط ❌ — تا کاربر برای دیدن ۴ خطا، ۲۰۰ خط را بالا نرود
    red: list = []
    for label, path in SUITES:
        print("\n" + "█" * 78)
        print(f"█  {label}")
        print("█" * 78)
        try:
            out = subprocess.run([sys.executable, path], cwd=ROOT, env=env,
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace",
                                 timeout=SUITE_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            print(f"\u23f1\ufe0f TIMEOUT — «{label}» پس از {SUITE_TIMEOUT_S} ثانیه "
                  f"تمام نشد.")
            failed.append(f"{label} (TIMEOUT)")
            continue
        print(out.stdout)
        red.extend(f"[{label.split(')')[0]})] {l.strip()}"
                   for l in out.stdout.splitlines() if l.lstrip().startswith("❌"))
        if out.stderr.strip():
            print(out.stderr)
        line = next((l for l in out.stdout.splitlines()
                     if l.startswith("نتیجه:")), "")
        if line:
            parts = line.split(":", 1)[1].split("|")
            ok += int(parts[0].split()[0])
            fail += int(parts[1].split()[0])
        if out.returncode != 0:
            failed.append(label)

    note = ""
    readme = os.path.join(ROOT, "README.md")
    if os.path.exists(readme):
        m = re.search(r"(\d+)\s*تست", open(readme, encoding="utf-8").read())
        if m and int(m.group(1)) != ok:
            note = (f"⚠️ README می‌گوید {m.group(1)} تست، ولی {ok} تست اجرا شد.")
            failed.append("ادعای تعداد تست در README")
        elif m:
            note = "✅ ادعای تعداد تست در README با واقعیت می‌خواند."

    print("\n" + "═" * 78)
    print(f"جمع کل: {ok} تست موفق | {fail} ناموفق")
    if note:
        print(note)
    if red:
        print("\nخطاهای دقیق (همین‌ها را بفرستید، نه کل خروجی):")
        for i, line in enumerate(red, 1):
            print(f"  {i:>2}. {line}")
        import platform
        print(f"\nمحیط: {platform.system()} {platform.release()} · "
              f"python {sys.version.split()[0]}")
    if failed:
        print("مجموعه‌های ناموفق: " + " ، ".join(failed))
    else:
        print("✅ همه تست‌ها سبز.")
    print("═" * 78)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
