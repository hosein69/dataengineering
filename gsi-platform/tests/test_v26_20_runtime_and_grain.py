# -*- coding: utf-8 -*-
"""V26.20 — تست‌هایی که نبودشان اجازه داد گزارش تعاملی خالی منتشر شود.

## چرا این فایل ساخته شد

۵۱۷ تست سبز بودند در حالی که گزارش HTML در مرورگر **کاملاً خالی** بالا
می‌آمد: نه ردیفی، نه نموداری، نه KPIای. علت این بود که هیچ تستی
جاوااسکریپت خروجی را در **یک scope مشترک** نمی‌سنجید.

فایل ``html_export.py`` دو پیاده‌سازی کامل و رقیب از یک runtime داشت — یکی
داخل f-string و یکی در ``dynamic_js`` — و هر دو emit می‌شدند. هر بلوک
جداگانه معتبر بود، ولی مرورگر هر دو را در یک scope سراسری اجرا می‌کند:

    SyntaxError: Identifier 'S' has already been declared

و با آن، کل بلوک دوم — یعنی تمام توابع رسم، فیلتر و جدول — هرگز اجرا
نمی‌شد. تست ایستا که فقط دنبال رشته می‌گردد، این را نمی‌بیند.

قاعده‌ای که اینجا قفل می‌شود: **خروجی اجراشدنی باید اجرا شود، نه grep.**
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# همان قرارداد بقیه تست‌های این پکیج: ریشه پروژه پیش از import از gsi روی
# sys.path می‌نشیند، چون run_all_tests.py هر فایل را مستقیم اجرا می‌کند.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from gsi.stages.s58_case_actions import _rank  # noqa: E402
from gsi.studio_core.grain import (DERIVED_GRAIN, column_grain,  # noqa: E402
                                   safe_agg)
from gsi.studio_core.html_export import build_dynamic_html  # noqa: E402

PASS: list = []
FAIL: list = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(("✅ " if ok else "❌ ") + name + (f" → {detail}" if detail else ""))


def _sample(n: int = 120) -> pd.DataFrame:
    return pd.DataFrame({
        "KEY_MATERIAL": [f"MAT-{i%12:03d}" for i in range(n)],
        "CANONICAL_ORDER": [f"ORD-{i%9:04d}" for i in range(n)],
        "ORG_DEPT": [["خرید خارجی", "گمرک و ترخیص", "حمل"][i % 3] for i in range(n)],
        "بحرانی (کوتاه)": [["توقف خط", "بحرانی", "تحت نظر", "ایمن"][i % 4] for i in range(n)],
        "مقاومت (روز)": [float(i % 40) for i in range(n)],
        "مانده تعهد": [float((i % 20) * 1000) for i in range(n)],
    })


def _scripts(html: str) -> str:
    """همه بلوک‌های script، همان‌طور که مرورگر در یک scope می‌بیند."""
    return "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))


def _declared(js: str) -> dict:
    """شناسه‌های اعلام‌شده در **سطح سراسری**.

    فقط خطوطی که از ستون صفر شروع می‌شوند شمرده می‌شوند: متغیر محلیِ داخل
    یک تابع می‌تواند آزادانه هم‌نام متغیر تابع دیگر باشد و تداخلی ندارد.
    چیزی که مرورگر را می‌شکند، دو اعلام هم‌نام در همان scope سراسری است.
    """
    out: dict = {}
    for line in js.split("\n"):
        if line[:1] in (" ", "\t", ""):
            continue
        m = re.match(r"(function|const|let)\s+([A-Za-z_$][\w$]*)\s*[\(=]", line)
        if m:
            out.setdefault(m.group(2), []).append(m.group(1))
    return out


def main() -> int:
    html = build_dynamic_html(
        _sample(), "2026-09-17", selected_fields=list(_sample().columns),
        charts=["criticality", "low_resistance", "org_workload"], max_rows=120)
    js = _scripts(html)

    # ── ۱) قرارداد اصلی: JS در scope مشترک معتبر است ──
    node = shutil.which("node")
    if node:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "all.js"
            p.write_text(js, encoding="utf-8")
            r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
        check("جاوااسکریپت خروجی در scope مشترک معتبر است", r.returncode == 0,
              r.stderr.strip().splitlines()[-1] if r.returncode else "")
    else:
        check("جاوااسکریپت خروجی در scope مشترک معتبر است", True, "node در محیط نیست")

    # ── ۲) هیچ شناسه‌ای دوبار با const/let/function اعلام نشده ──
    dup = {n: k for n, k in _declared(js).items()
           if len(k) > 1 and any(x in ("const", "let", "function") for x in k)}
    check("هیچ شناسه‌ای دوبار در سطح سراسری اعلام نشده", not dup,
          ", ".join(sorted(dup)) if dup else "")

    # ── ۳) هر تابعی که فراخوانی می‌شود، تعریف هم شده ──
    defined = set(_declared(js)) | {
        "document", "window", "Math", "Number", "String", "Array", "Object", "JSON",
        "Date", "Set", "Map", "parseFloat", "parseInt", "isNaN", "setTimeout", "Blob",
        "URL", "TextEncoder", "Uint8Array", "DataView", "matchMedia", "IntersectionObserver",
    }
    called = set(re.findall(r"(?<![.\w])([_A-Za-z$][\w$]*)\s*\(", js))
    kw = {"if", "for", "while", "switch", "catch", "function", "return", "typeof",
          "new", "await", "throw", "else", "do"}
    missing = sorted(c for c in called - defined - kw if c.startswith("_"))
    check("هیچ تابع داخلی فراخوانی‌شده‌ای تعریف‌نشده نیست", not missing,
          ", ".join(missing) if missing else "")

    # ── ۴) دانه ستون‌های موجودی V26.20 ثبت شده است ──
    # بدون این، یک قطعه که روی سه بارنامه پخش است سه برابر جمع می‌خورد.
    inv = ["SUPPLY_TOTAL_CONFIRMED", "SUPPLY_TOTAL_LOWER_BOUND", "SUPPLY_ORACLE_STOCK",
           "SUPPLY_EXPERT_STOCK", "SUPPLIER_QTY", "IN_TRANSIT_QTY", "IN_CUSTOMS_QTY",
           "STOCK_IKCO", "STOCK_SAPCO", "DAILY_NEED"]
    unreg = [c for c in inv if c not in DERIVED_GRAIN]
    check("ستون‌های موجودی در رجیستری دانه ثبت شده‌اند", not unreg,
          ", ".join(unreg) if unreg else "")
    check("دانه ستون‌های موجودی متریال است",
          all(column_grain(c) == "MATERIAL" for c in inv if c in DERIVED_GRAIN))

    fan = pd.DataFrame({
        "KEY_BL": ["B1", "B2", "B3"], "KEY_MATERIAL": ["M1", "M1", "M1"],
        "SUPPLY_TOTAL_CONFIRMED": [100.0, 100.0, 100.0],
        "IN_TRANSIT_QTY": [40.0, 40.0, 40.0],
    })
    check("جمع موجودی روی fan-out بارنامه دوباره‌شماری نمی‌کند",
          safe_agg(fan, "SUPPLY_TOTAL_CONFIRMED", "sum") == 100.0
          and safe_agg(fan, "IN_TRANSIT_QTY", "sum") == 40.0,
          f"confirmed={safe_agg(fan,'SUPPLY_TOTAL_CONFIRMED','sum')}")

    # ── ۵) صف اقدام بر رتبه مرتب می‌شود، نه بر الفبا ──
    # الفبایی «LOW» پیش از «MEDIUM» می‌نشیند و صف وارونه می‌شود.
    order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    check("رتبه اولویت نزولی و بدون گره است",
          [_rank(p) for p in order] == sorted([_rank(p) for p in order], reverse=True)
          and len({_rank(p) for p in order}) == 4)
    src = (Path(__file__).resolve().parents[1] / "gsi" / "stages"
           / "s58_case_actions.py").read_text(encoding="utf-8")
    check("خروجی صف اقدام بر PRIORITY رشته‌ای مرتب نمی‌شود",
          '"KEY_REG", "PRIORITY", "ACTION_ID"' not in src and "_RANK" in src)

    # ── ۶) هات‌فیکس COM روی هر سه مسیر Outlook ──
    mail = (Path(__file__).resolve().parents[1] / "gsi" / "integrations"
            / "daily_email.py").read_text(encoding="utf-8")
    check("COM روی نخ جاری مقداردهی می‌شود", "pythoncom.CoInitialize()" in mail)
    check("COM در مسیر خطا هم آزاد می‌شود",
          "finally:" in mail and "CoUninitialize" in mail)
    # Both quote styles are valid Python; count actual AST calls and ensure
    # each call is nested inside its owning Outlook session.
    import ast
    tree = ast.parse(mail)
    dispatches = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute) and n.func.attr == "Dispatch"
                  and n.args and isinstance(n.args[0], ast.Constant)
                  and n.args[0].value == "Outlook.Application"]
    sessions = [n for n in ast.walk(tree) if isinstance(n, ast.With)
                and any(isinstance(i.context_expr, ast.Call)
                        and isinstance(i.context_expr.func, ast.Name)
                        and i.context_expr.func.id == "_outlook_session" for i in n.items)]
    n_dispatch = len(dispatches)
    enclosed = all(any(d in list(ast.walk(w)) for w in sessions) for d in dispatches)
    n_session = mail.count("with _outlook_session()")
    check("هیچ فراخوانی Outlook خارج از مدیر زمینه نمانده",
          enclosed and n_dispatch == n_session and n_dispatch >= 3,
          f"{n_dispatch} dispatch / {n_session} session")

    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
