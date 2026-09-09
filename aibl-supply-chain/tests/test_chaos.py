# -*- coding: utf-8 -*-
"""آزمون آشوب — نقاط تاریک معماری.

هر تست یک سناریوی شکست عینی است که **قبلاً روی همین کد بازتولید شده**،
نه یک حالت فرضی. عنوان هر بخش، شناسه نقطه تاریک است.

اجرا:  python tests/test_chaos.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pandas as pd  # noqa: E402

from aibl import health  # noqa: E402
from aibl.core.text import num_parse, num_safe  # noqa: E402
from aibl.engines.criticality import CriticalityEngine  # noqa: E402
from aibl.report.extracts import write_expert_extracts  # noqa: E402
from aibl.resolve import part_status as ps  # noqa: E402
from aibl.resolve.expert_scope import (STAGE_TO_SCOPE,  # noqa: E402
                                       UNOBSERVABLE_STAGES)
from aibl.rulebook import get_rulebook  # noqa: E402
from aibl.runlock import (RunLock, RunLocked, clear_marker,  # noqa: E402
                          read_marker, write_marker)

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


def _engine() -> CriticalityEngine:
    return CriticalityEngine(get_rulebook())


# ═══════════ DC-01 ═══════════
def test_dc01_scientific_notation() -> None:
    print("\n── DC-01 | نماد علمی اکسل، عددِ اشتباه می‌ساخت (Critical) ──")
    # اکسل برای اعداد بزرگ خودکار 4.5E+09 می‌نویسد. نسخه قبل حرف E و
    # علامت توان را دور می‌ریخت و «4.509» می‌ساخت — نه صفر، یک عدد غلط،
    # که هیچ گاردی نمی‌گرفتش و مستقیم وارد جمع تعهد ارزی می‌شد.
    for raw, want in (("4.5E+09", 4.5e9), ("1.23E+15", 1.23e15),
                      ("1e-12", 1e-12), ("2E5", 2e5), ("-3.5E+03", -3500.0)):
        got = num_parse(raw)
        ok = got is not None and abs(got - want) <= abs(want) * 1e-9
        check(f"«{raw}» درست خوانده می‌شود", ok, f"{got!r} (انتظار {want!r})")

    # رفتارهای قدیمی نباید بشکنند
    for raw, want in (("1,234.56", 1234.56), ("1.234.567", 1234567.0),
                      ("۱۲۳۴", 1234.0), ("(500)", -500.0), ("12 عدد", 12.0)):
        check(f"رفتار قبلی «{raw}» حفظ شده", num_parse(raw) == want,
              repr(num_parse(raw)))


# ═══════════ DC-02 ═══════════
def test_dc02_false_stockout() -> None:
    print("\n── DC-02 | سلول غیرعددی، هشدار «توقف خط» می‌ساخت (Critical) ──")
    e = _engine()
    # سلولی که متن نامفهوم دارد، صفر خوانده می‌شد؛ صفرِ موجودی یعنی
    # توقف خط — یک اضطرارِ ساختگی از روی یک سلول خراب.
    for bad in ("abc", "???", "نامعلوم", float("inf"), float("-inf")):
        r = e.evaluate(dict(STOCK_IKCO=bad, STOCK_SAPCO=0, DAILY_NEED=10))
        check(f"موجودی {bad!r} ⇒ «نامشخص»، نه توقف خط",
              r.band == "UNKNOWN", r.band)

    # صفرِ واقعی همچنان باید توقف خط بدهد — گارد نباید هشدار واقعی را بخورد
    r = e.evaluate(dict(STOCK_IKCO=0, STOCK_SAPCO=0, DAILY_NEED=10))
    check("موجودی واقعاً صفر همچنان «توقف خط» است", r.band == "STOCKOUT", r.band)
    r = e.evaluate(dict(STOCK_IKCO=100, STOCK_SAPCO=0, DAILY_NEED=10))
    check("حالت عادی دست‌نخورده", r.resistance_days == 10.0, str(r.resistance_days))

    # NaN در یک ستون + صفر واقعی در ستون دیگر
    r = e.evaluate(dict(STOCK_IKCO=float("nan"), STOCK_SAPCO=0, DAILY_NEED=10))
    check("NaN در موجودی، وضعیت را بی‌اعتبار نمی‌کند",
          r.band in ("UNKNOWN", "STOCKOUT"), r.band)

    health.reset()
    e2 = _engine()
    for _ in range(3):
        e2.evaluate(dict(STOCK_IKCO="abc", STOCK_SAPCO=0, DAILY_NEED=10))
    check("سلول‌های ناخوانا شمرده می‌شوند",
          sum(getattr(e2, "unreadable_cells", {}).values()) == 3,
          str(getattr(e2, "unreadable_cells", {})))


# ═══════════ DC-03 ═══════════
def test_dc03_negative_resistance() -> None:
    print("\n── DC-03 | مقاومت منفی (Medium) ──")
    e = _engine()
    r = e.evaluate(dict(STOCK_IKCO=-50, STOCK_SAPCO=0, DAILY_NEED=10))
    # اضافه‌برداشت انبار عدد منفی می‌سازد؛ «مقاومت ‑۵ روز» بی‌معناست و
    # در مرتب‌سازی بحرانی‌ترین‌ها هم رفتار عجیب می‌سازد.
    check("موجودی منفی ⇒ مقاومت صفر، نه منفی",
          r.resistance_days is not None and r.resistance_days >= 0,
          str(r.resistance_days))
    check("و طبقه‌اش توقف خط می‌ماند", r.band == "STOCKOUT", r.band)


# ═══════════ DC-04 / DC-05 ═══════════
def test_dc04_zombie_extracts() -> None:
    print("\n── DC-04/05 | فایل کارشناسِ منسوخ و نام nan (High) ──")
    with tempfile.TemporaryDirectory() as d:
        zombie = os.path.join(d, "قدیمی__کارشناس_رفته.xlsx")
        open(zombie, "wb").close()
        df = pd.DataFrame({
            "KEY_EMP": ["1001", float("nan")],
            "CANONICAL_EXPERT": ["الف", "ب"],
            "KEY_MATERIAL": ["M1", "M2"],
        })
        health.reset()
        write_expert_extracts(df, d)
        names = sorted(f for f in os.listdir(d) if f.endswith(".xlsx"))
        check("فایل اجرای قبلی از پوشه اصلی برداشته می‌شود",
              "قدیمی__کارشناس_رفته.xlsx" not in names, str(names))
        check("ولی حذف نمی‌شود — بایگانی می‌شود",
              os.path.exists(os.path.join(d, "_archive",
                                          "قدیمی__کارشناس_رفته.xlsx")))
        check("کد پرسنلی nan به «بدون_کد_پرسنلی» تبدیل می‌شود",
              any(n.startswith("بدون_کد_پرسنلی") for n in names), str(names))
        check("فایل کارشناس معتبر ساخته شده", any(n.startswith("1001") for n in names))


# ═══════════ DC-06 ═══════════
def test_dc06_concurrent_runs() -> None:
    print("\n── DC-06 | دو اجرای هم‌زمان روی یک پوشه (High) ──")
    with tempfile.TemporaryDirectory() as d:
        with RunLock(d):
            # شبیه‌سازی اجرای دوم: قفلِ زنده باید جلویش را بگیرد
            blocked = False
            try:
                with RunLock(d):
                    pass
            except RunLocked as ex:
                blocked = True
                msg = str(ex)
            check("اجرای دوم رد می‌شود", blocked)
            check("پیام، راه خروج را می‌گوید",
                  blocked and "AIBL_FORCE_RUN=1" in msg)
            check("پیام، شناسه فرآیندِ قفل‌کننده را می‌گوید",
                  blocked and str(os.getpid()) in msg)
        check("قفل پس از پایان برداشته می‌شود",
              not os.path.exists(os.path.join(d, ".aibl_run.lock")))

        # قفلِ بازمانده از فرآیند مرده نباید سیستم را قفل نگه دارد
        with open(os.path.join(d, ".aibl_run.lock"), "w", encoding="utf-8") as f:
            json.dump({"pid": 999999, "epoch": time.time(),
                       "started": "x"}, f)
        got = False
        try:
            with RunLock(d):
                got = True
        except RunLocked:
            got = False
        check("قفل بازمانده از فرآیند مرده خودکار نادیده گرفته می‌شود", got)


# ═══════════ DC-07 ═══════════
def test_dc07_unreachable_states() -> None:
    print("\n── DC-07 | حالت‌های غیرقابل‌رسیدن ماشین وضعیت (Medium) ──")
    from aibl.stages.s80_eventlog import ACTIVITIES
    observable = {a[4] for a in ACTIVITIES}
    owned = set(STAGE_TO_SCOPE)
    unreachable = owned - observable
    check("هر مرحله بی‌رویداد، صریح اعلام شده است",
          unreachable == set(UNOBSERVABLE_STAGES),
          f"اعلام‌نشده: {sorted(unreachable - set(UNOBSERVABLE_STAGES))}")
    check("هر مرحله اعلام‌شده، دلیل دارد",
          all(v.strip() for v in UNOBSERVABLE_STAGES.values()))
    check("مرحله اعلام‌شده واقعاً بی‌رویداد است",
          not (set(UNOBSERVABLE_STAGES) & observable),
          str(set(UNOBSERVABLE_STAGES) & observable))
    check("هر مرحله قابل مشاهده، حوزه مسئول دارد",
          not (observable - owned), str(observable - owned))


# ═══════════ DC-08 ═══════════
def test_dc08_partial_output_set() -> None:
    print("\n── DC-08 | مجموعه خروجی ناتمام قابل تشخیص نبود (Medium) ──")
    with tempfile.TemporaryDirectory() as d:
        check("پوشه بدون نشانه ⇒ مجموعه ناتمام", read_marker(d) is None)
        write_marker(d, {"report": os.path.join(d, "r.xlsx")}, "26.12.0")
        m = read_marker(d)
        check("نشانه پس از تکمیل نوشته می‌شود", bool(m))
        check("نشانه نسخه سازنده را دارد", m.get("version") == "26.12.0")
        check("نشانه فایل‌های مجموعه را فهرست می‌کند", "report" in (m.get("files") or {}))
        clear_marker(d)
        check("شروع اجرای بعدی، نشانه را برمی‌دارد", read_marker(d) is None)


# ═══════════ آشوب سطح فرآیند ═══════════
def test_process_chaos() -> None:
    print("\n── آشوب سطح فرآیند ──")
    health.reset()
    # ترتیب زمانی معکوس + تاریخ آینده، هم‌زمان روی یک ردیف
    out = ps.resolve(pd.DataFrame({
        "COT_DATE": ["1405/06/10"], "FULL_CLEAR_DATE": ["1405/06/03"],
        "BL_DATE": ["1410/01/01"],
    }), today=pd.Timestamp("2026-09-08"))
    check("ترتیب معکوس و تاریخ آینده هم‌زمان، هر دو ثبت می‌شوند",
          out[ps.ANOMALY].iloc[0] != "" and out[ps.PLANNED].iloc[0] != "")
    check("و وضعیت از تاریخ آینده ساخته نمی‌شود",
          "1410" not in str(out[ps.WHEN].iloc[0]))

    # ردیف کاملاً خالی نباید بترکاند
    blank = ps.resolve(pd.DataFrame({"KEY_MATERIAL": [""]}))
    check("ردیف کاملاً بی‌داده استثنا نمی‌دهد", len(blank) == 1)

    # داده تک‌ردیفی با همه ستون‌های تاریخ خالی
    empty_dates = ps.resolve(pd.DataFrame({"BL_DATE": [""], "COT_DATE": [""]}))
    check("همه تاریخ‌ها خالی ⇒ «نامشخص»، بدون حدس",
          empty_dates[ps.WHERE].iloc[0] == "نامشخص")


# ═══════════ بهداشت CLI ═══════════
def test_cli_lock_wiring() -> None:
    print("\n── اتصال قفل به نقطه ورود ──")
    src = open(os.path.join(ROOT, "aibl", "__main__.py"), encoding="utf-8").read()
    check("دستور run زیر قفل اجرا می‌شود", "RunLock" in src and "RunLocked" in src)
    check("خروجِ ناموفق کد وضعیت غیرصفر می‌دهد", "return 2" in src)
    pipe = open(os.path.join(ROOT, "aibl", "pipeline.py"), encoding="utf-8").read()
    check("خروجی‌ها به‌صورت یک مجموعه نوشته می‌شوند", "emit_outputs" in pipe)


if __name__ == "__main__":
    print("=" * 78)
    print("AIBL — آزمون آشوب و نقاط تاریک معماری")
    print("=" * 78)
    test_dc01_scientific_notation()
    test_dc02_false_stockout()
    test_dc03_negative_resistance()
    test_dc04_zombie_extracts()
    test_dc06_concurrent_runs()
    test_dc07_unreachable_states()
    test_dc08_partial_output_set()
    test_process_chaos()
    test_cli_lock_wiring()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
