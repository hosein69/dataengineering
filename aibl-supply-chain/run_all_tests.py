# -*- coding: utf-8 -*-
"""اجرای هر سه مجموعه تست.

    python run_all_tests.py
"""
from __future__ import annotations

import os
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
SUITES = [
    ("۱) الگوریتمی و بیزینسی", "tests/test_validation.py"),
    ("۲) کتابخانه قوانین و سورس مقاومت", "tests/test_rules_and_moghavemat.py"),
    ("۳) مقاومت قطعه و بحرانی بودن", "tests/test_criticality.py"),
    ("۴) معماری، اختلاف نسخه و لاگ رویداد", "tests/test_architecture.py"),
    ("۵) قرارداد گزارش (باگ موجودی/مقاومت)", "tests/test_contracts_report.py"),
    ("۶) منطق داشبورد و خروجی‌ها", "tests/test_dashboard.py"),
    ("۷) سیستمی و استقرار", "tests/test_import_hygiene.py"),
    ("۸) ادعاهای مستندات", "tests/test_doc_claims.py"),
    ("۹) بسته ایمیل مدیریتی", "tests/test_email_report.py"),
    ("۱۰) AIBL Studio ماژولار", "tests/test_studio.py"),
    ("۱۱) سازنده گزارش و صحت دانه‌ای", "tests/test_report_builder.py"),
    ("۱۲) حوزه مسئولیت، مالکیت قطعه و نماهای تأمین", "tests/test_supply_views.py"),
    ("۱۳) نقاط کور سیستمی و فرآیندی", "tests/test_system_health.py"),
    ("۱۴) آشوب و نقاط تاریک معماری", "tests/test_chaos.py"),
    ("۱۵) گزارش تحلیلی و نمودار داینامیک", "tests/test_analytics.py"),
    ("۱۶) ارسال گزارش و بدنهٔ ایمیل", "tests/test_dispatch.py"),
    ("۱۷) بسته‌بندی، کف خوانایی و ارسال", "tests/test_packaging.py"),
]


#: سقف زمان هر مجموعه. تست تولیدی نباید بدون سقف اجرا شود: یک حلقه
#: بی‌پایان یا یک I/O معلق، اجرای CI را تا ابد نگه می‌دارد و کسی نمی‌فهمد
#: کدام مجموعه گیر کرده. با سقف، خروجی صریح TIMEOUT می‌شود.
SUITE_TIMEOUT_S = int(os.environ.get("AIBL_TEST_TIMEOUT", "600"))


def main() -> int:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    total_ok = total_fail = 0
    failed_suites = []
    timed_out = []
    for label, path in SUITES:
        print("\n" + "\u2588" * 78)
        print(f"\u2588  {label}")
        print("\u2588" * 78)
        # یک بار اجرا، خروجی هم چاپ و هم تحلیل می‌شود
        try:
            out = subprocess.run([sys.executable, path], cwd=ROOT, env=env,
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace",
                                 timeout=SUITE_TIMEOUT_S)
        except subprocess.TimeoutExpired as ex:
            print((ex.stdout or "") if isinstance(ex.stdout, str)
                  else (ex.stdout or b"").decode("utf-8", "replace"))
            print(f"\u23f1\ufe0f TIMEOUT — «{label}» پس از {SUITE_TIMEOUT_S} ثانیه "
                  f"تمام نشد و متوقف شد.")
            timed_out.append(label)
            failed_suites.append(f"{label} (TIMEOUT)")
            total_fail += 1
            continue
        print(out.stdout)
        if out.stderr.strip():
            print(out.stderr)
        line = next((l for l in out.stdout.splitlines()
                     if l.startswith("\u0646\u062a\u06cc\u062c\u0647:")), "")
        if line:
            parts = line.split(":", 1)[1].split("|")
            total_ok += int(parts[0].split()[0])
            total_fail += int(parts[1].split()[0])
        if out.returncode != 0:
            failed_suites.append(label)

    # ── ادعای README درباره تعداد تست، همین‌جا سنجیده می‌شود ──
    # (نه در test_doc_claims، چون آنجا خودارجاع و کند می‌شد)
    import re
    _FA = "۰۱۲۳۴۵۶۷۸۹"
    readme = os.path.join(ROOT, "README.md")
    doc_note = ""
    if os.path.exists(readme):
        m = re.search(r"\*\*(\S+) تست صحت", open(readme, encoding="utf-8").read())
        if m:
            claimed = "".join(str(_FA.index(c)) if c in _FA else c for c in m.group(1))
            if claimed.isdigit() and int(claimed) != total_ok:
                doc_note = (f"⚠️ README می‌گوید {m.group(1)} تست، ولی واقعاً "
                            f"{total_ok} تست اجرا شد — README را هماهنگ کنید.")
                failed_suites.append("ادعای تعداد تست در README")
            else:
                doc_note = "✅ ادعای تعداد تست در README با واقعیت می‌خواند."

    print("\n" + "═" * 78)
    print(f"جمع کل: {total_ok} تست موفق | {total_fail} ناموفق"
          + (f" | {len(timed_out)} TIMEOUT" if timed_out else ""))
    if doc_note:
        print(doc_note)
    if failed_suites:
        print("مجموعه‌های ناموفق: " + " ، ".join(failed_suites))
    else:
        print("✅ همه تست‌ها سبز — سیستم آماده اجرا روی داده واقعی است.")
    print("═" * 78)
    return 1 if failed_suites else 0


if __name__ == "__main__":
    sys.exit(main())
