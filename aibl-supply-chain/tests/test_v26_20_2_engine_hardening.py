# -*- coding: utf-8 -*-
"""V26.20.2 — سه شکافی که عمداً باز مانده بودند و حالا بسته شده‌اند.

هر سه مورد در گزارش دیباگ قبلی **علامت خورده و به تصمیم کاربر واگذار شده
بود**، نه اینکه دیده نشده باشد. این فایل قفلشان می‌کند:

۱) **برداری‌سازی مرحله ۳۸** — حلقه ردیف‌به‌ردیف روی ``to_dict("records")``
   حذف شد. خطر واقعی چنین بازنویسی‌ای این است که «معادل به‌نظر» باشد ولی
   نباشد؛ پس اینجا خروجی نسخه برداری با **همان منطق مرجع** روی مقادیر
   لبه‌ای مقایسه می‌شود، نه با یک قضاوت چشمی.

۲) **سامانه جامع انبارها** — آخرین حلقه زنجیره شاهد. کالای ترخیص‌شده باید
   قبض انبار بگیرد؛ تا پیش از این، ستون ``WAREHOUSE_RECEIPT`` در فریم مبدأ
   می‌ماند و به هیچ خروجی نمی‌رسید.

۳) **پنجره اعتبار قوانین** — ``expires_on`` نوشته می‌شد ولی هیچ‌جا خوانده
   نمی‌شد. یعنی یک بخشنامه منقضی تا ابد «آخرین نسخه معتبر» می‌ماند.
"""
from __future__ import annotations

import os
import sys
from datetime import date

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════════════════
#  ۱) مرحله ۳۸ — برداری، ولی دقیقاً همان معنا
# ═══════════════════════════════════════════════════════════════════════════
def test_s38_vectorised() -> None:
    print("\n── ۱) مرحله ۳۸: برداری‌سازی بدون تغییر معنا ──")
    from gsi.stages.s38_supply_position import (SupplyPositionStage,
                                                _num_or_none, _numeric_or_nan,
                                                _text_or_blank)
    from gsi.stages.base import PipelineContext
    from gsi.rulebook import get_rulebook

    # این را با grep روی متن فایل نمی‌سنجیم: خودِ docstring عمداً درباره
    # «حلقه قبلی» توضیح می‌دهد و یک grep ساده، تاریخچه را با کد اشتباه
    # می‌گیرد. پس AST را می‌خوانیم و فقط **کد اجراشدنی** را می‌سنجیم.
    import ast
    tree = ast.parse(open(os.path.join(ROOT, "gsi/stages/s38_supply_position.py"),
                          encoding="utf-8").read())
    row_calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr in ("to_dict", "iterrows", "itertuples", "apply")
    ]
    check("هیچ پیمایش ردیف‌به‌ردیفی در کد مرحله نمانده", not row_calls,
          "، ".join(f"{c.func.attr}@{c.lineno}" for c in row_calls) or "پاک")

    # ── معادل بودن روی مقادیر لبه‌ای ──
    #
    # اینها همان‌هایی‌اند که در فایل اکسل واقعی دیده می‌شوند: رقم فارسی،
    # رقم عربی، جداکننده هزارگان، توکن‌های تهی فارسی، و صفرِ واقعی که
    # **تهی نیست**.
    edge = [0, 1, 12.5, -3, "  7 ", "1,234", "۱۲۳", "٣٤٥", "１２３", "۱,۲۳۴",
            None, np.nan, "", " ", "nan", "-", "نامشخص", "n/a", "N/A", "ندارد",
            "abc", True, False, "0", "0.0", 1e6, "12.5", "1e3", "  -4.25  ", "۰"]
    vec = _numeric_or_nan(pd.Series(edge, dtype=object))
    bad = []
    for v, got in zip(edge, vec):
        want = _num_or_none(v)
        same = ((want is None and pd.isna(got))
                or (want is not None and not pd.isna(got) and abs(want - got) < 1e-9))
        if not same:
            bad.append(f"{v!r}: {want} ≠ {got}")
    check("تبدیل عددی برداری با منطق مرجع یکی است", not bad,
          "؛ ".join(bad[:3]) or f"{len(edge)} مقدار لبه‌ای")

    # ارقام فارسی: تله‌ای که یک بازنویسی ساده در آن می‌افتد
    check("عدد فارسی‌نویس «نامشخص» شمرده نمی‌شود",
          float(_numeric_or_nan(pd.Series(["۱۲۳"], dtype=object)).iloc[0]) == 123.0)
    check("عدد عربی‌نویس هم درست خوانده می‌شود",
          float(_numeric_or_nan(pd.Series(["٣٤٥"], dtype=object)).iloc[0]) == 345.0)

    # Missing ≠ Zero — قاعده‌ای که کل مرحله روی آن بنا شده
    got = _numeric_or_nan(pd.Series(["", "0", "نامشخص", 0], dtype=object))
    check("Missing با Zero یکی نمی‌شود",
          pd.isna(got.iloc[0]) and got.iloc[1] == 0.0
          and pd.isna(got.iloc[2]) and got.iloc[3] == 0.0,
          list(got))

    check("NaN به رشته 'nan' تبدیل نمی‌شود",
          list(_text_or_blank(pd.Series([np.nan, None, "  x  ", ""], dtype=object)))
          == ["", "", "x", ""])

    # ── اجرای واقعی مرحله روی قابی که هر چهار وضعیت را دارد ──
    df = pd.DataFrame({
        "STOCK_IKCO":     [100, 100, "", 50, 10],
        "STOCK_SAPCO":    [50, 50, "", "", 5],
        "SUPPLIER_QTY":   [300, "", "", "", 1],
        "IN_TRANSIT_QTY": [20, 20, "", "", 1],
        "IN_CUSTOMS_QTY": [10, 10, "", "", 1],
        "EXPERT_INV_CONFLICT": ["", "", "", "", "دو snapshot متعارض"],
        "EXPERT_INV_ASOF": [np.nan, "", "", "", "1405/06/15"],
    })
    ctx = PipelineContext(rb=get_rulebook(), today=date(2026, 8, 31))
    out = SupplyPositionStage().run(df.copy(), ctx)
    check("جمع قطعی فقط وقتی هر پنج مؤلفه هست ساخته می‌شود",
          out["SUPPLY_TOTAL_CONFIRMED"].iloc[0] == 480
          and pd.isna(out["SUPPLY_TOTAL_CONFIRMED"].iloc[1]),
          str(list(out["SUPPLY_TOTAL_CONFIRMED"])))
    check("حداقل قابل اثبات از مؤلفه‌های موجود ساخته می‌شود",
          out["SUPPLY_TOTAL_LOWER_BOUND"].iloc[1] == 180
          and pd.isna(out["SUPPLY_TOTAL_LOWER_BOUND"].iloc[2]))
    check("وضعیت‌ها درست تفکیک می‌شوند",
          list(out["SUPPLY_POSITION_STATUS"])
          == ["COMPLETE", "PARTIAL", "MISSING", "PARTIAL", "CONFLICT"],
          str(list(out["SUPPLY_POSITION_STATUS"])))
    check("ردیف بدون تعارض، CONFLICT اعلام نمی‌شود",
          out["SUPPLY_POSITION_CONFLICT"].iloc[0] == ""
          and out["SUPPLY_POSITION_STATUS"].iloc[0] != "CONFLICT")
    check("شکاف‌ها با نام و ترتیب درست گزارش می‌شوند",
          out["SUPPLY_POSITION_GAPS"].iloc[3]
          == "Oracle/SAPCO، Expert/نزد سازنده، Expert/در راه، Expert/گمرک",
          out["SUPPLY_POSITION_GAPS"].iloc[3])
    check("پوشش داده درصد درست می‌دهد",
          list(out["SUPPLY_POSITION_COVERAGE_PCT"]) == [100.0, 80.0, 0.0, 20.0, 100.0],
          str(list(out["SUPPLY_POSITION_COVERAGE_PCT"])))


# ═══════════════════════════════════════════════════════════════════════════
#  ۲) سامانه جامع انبارها
# ═══════════════════════════════════════════════════════════════════════════
def test_warehouse_declaration() -> None:
    print("\n── ۲) سامانه جامع انبارها ──")
    from gsi.rulebook import get_rulebook
    from gsi.stages.base import PipelineContext
    from gsi.stages.s39_warehouse_declaration import WarehouseDeclarationStage

    rb = get_rulebook(reload=True)
    check("بسته قوانین انبار بارگذاری می‌شود", bool(rb.pack("warehouse")))
    states = [s["code"] for s in rb.get("warehouse.states", [])]
    check("هشت وضعیت اظهار تعریف شده است", len(states) == 8, str(states))

    # حاکمیت: هیچ مهلت قانونی‌ای خودکار اعمال نمی‌شود تا verified شود
    deadlines = rb.get("warehouse.deadlines", {}) or {}
    check("هیچ مهلت انبار خودکار اعمال نمی‌شود",
          all(not d.get("automatic_apply", False) for d in deadlines.values()),
          str({k: d.get("automatic_apply") for k, d in deadlines.items()}))
    check("مهلت‌های قانونی needs_verification علامت خورده‌اند",
          all(d.get("status") == "needs_verification" for d in deadlines.values()))
    check("آستانه‌های پایش صریحاً internal‌اند، نه قاعده قانونی",
          all(m.get("status") == "internal"
              for m in (rb.get("warehouse.monitoring", {}) or {}).values()))

    check("قبض انبار به فریم اصلی می‌رسد",
          '"WAREHOUSE_RECEIPT"' in
          open(os.path.join(ROOT, "gsi/stages/s20_derive.py"), encoding="utf-8").read())

    # ── شش سناریو، شش وضعیت ──
    df = pd.DataFrame({
        "FULL_CLEAR_DATE":   ["1405/01/01", "1405/01/01", "1405/01/01",
                              "1405/06/05", "", "1405/01/01"],
        "WAREHOUSE_RECEIPT": ["1405/01/03", "1405/02/20", "",
                              "", "1405/01/05", "1404/12/01"],
    })
    ctx = PipelineContext(rb=rb, today=date(2026, 8, 31))   # ۱۴۰۵/۰۶/۰۹
    out = WarehouseDeclarationStage().run(df.copy(), ctx)
    got = list(out["WH_STATUS"])
    check("هر شش سناریو وضعیت درست می‌گیرند",
          got == ["DECLARED", "LATE", "CRITICAL_GAP", "PENDING",
                  "DECLARED", "SEQUENCE_CONFLICT"], str(got))
    check("فاصله اظهار برای ردیف به‌موقع محاسبه می‌شود",
          out["WH_LAG_DAYS"].iloc[0] == 2, str(out["WH_LAG_DAYS"].iloc[0]))
    check("عمر شکاف فقط برای ردیف بدون قبض انبار پر می‌شود",
          pd.isna(out["WH_AGE_DAYS"].iloc[0]) and out["WH_AGE_DAYS"].iloc[2] > 30)
    check("فاصله منفی هرگز به‌عنوان مدت گزارش نمی‌شود",
          pd.isna(out["WH_LAG_DAYS"].iloc[5]),
          str(out["WH_LAG_DAYS"].iloc[5]))
    check("ردیف بدون تاریخ ترخیص، شکاف شمرده نمی‌شود",
          out["WH_STATUS"].iloc[4] != "OVERDUE")
    check("هر وضعیت برچسب فارسی دارد",
          all(isinstance(x, str) and x for x in out["WH_STATUS_FA"]))
    check("مبنای تاریخ ترخیص در خروجی ثبت می‌شود",
          out["WH_CLEAR_BASIS"].iloc[0] == "FULL_CLEAR_DATE")
    check("پایه قاعده در خروجی اعلام می‌شود که خودکار نیست",
          "needs_verification" in out["WH_RULE_BASIS"].iloc[0])

    # بدون هیچ ستون تاریخی: باید UNKNOWN بدهد، نه صفر و نه تخلف
    blank = WarehouseDeclarationStage().run(
        pd.DataFrame({"WAREHOUSE_RECEIPT": ["", ""]}), ctx)
    check("بدون داده، Unknown اعلام می‌شود نه شکاف",
          list(blank["WH_STATUS"]) == ["NOT_CLEARED", "NOT_CLEARED"],
          str(list(blank["WH_STATUS"])))

    tones = WarehouseDeclarationStage.STATE_TONE
    from gsi.design import tokens as T
    check("آهنگ رنگی هر وضعیت در سیستم طراحی وجود دارد",
          all(v in T.STATUS for v in tones.values()), str(set(tones.values())))
    check("هر وضعیت YAML آهنگ رنگی دارد",
          {s["code"] for s in rb.get("warehouse.states", [])} == set(tones))


# ═══════════════════════════════════════════════════════════════════════════
#  ۳) پنجره اعتبار قوانین
# ═══════════════════════════════════════════════════════════════════════════
def test_rule_expiry() -> None:
    print("\n── ۳) پنجره اعتبار قوانین (expires_on) ──")
    from gsi.rulebook import RuleBook
    from gsi.rulebook.loader import EXPIRY_WARN_DAYS

    SATA = "customs.emergency_sata_waiver_1405"        # expires_on 2026-09-22

    before = RuleBook(as_of=date(2026, 9, 18))
    after = RuleBook(as_of=date(2026, 9, 23))

    check("قاعده معتبر با active() برگردانده می‌شود",
          bool(before.active(SATA)))
    check("قاعده منقضی با active() برگردانده نمی‌شود",
          after.active(SATA) is None)
    check("get() همچنان قاعده منقضی را برای نمایش می‌دهد",
          bool(after.get(SATA)),
          "ممیزی باید بتواند قاعده منقضی را ببیند، وگرنه ناپدید می‌شود")
    check("is_expired تاریخ مرجع را می‌سنجد",
          not before.is_expired(SATA) and after.is_expired(SATA))
    check("شمارش روز تا انقضا درست است",
          before.days_to_expiry(SATA) == 4 and after.days_to_expiry(SATA) == -1,
          f"{before.days_to_expiry(SATA)} / {after.days_to_expiry(SATA)}")
    check("قاعده بی‌انقضا همیشه معتبر است",
          before.days_to_expiry("customs.demurrage") is None
          and before.in_window(before.get("customs.demurrage")))

    check("ممیزی انقضا در تاریخ گذشته خالی و در آینده پر است",
          not before.expired() and len(after.expired()) >= 2,
          f"{len(before.expired())} / {len(after.expired())}")
    check("قاعده منقضی سطح error دارد، نه warning",
          all(i.level == "error" for i in after.expired()))
    check("پیش‌هشدار انقضا پیش از تاریخ انقضا می‌آید",
          len(before.expiring_soon()) >= 2 and not after.expiring_soon())
    check("پیش‌هشدار سطح warning دارد",
          all(i.level == "warning" for i in before.expiring_soon()))
    check("پنجره پیش‌هشدار یک عدد مستند است",
          isinstance(EXPIRY_WARN_DAYS, int) and 7 <= EXPIRY_WARN_DAYS <= 90,
          str(EXPIRY_WARN_DAYS))
    check("پیام انقضا تاریخ و فاصله را می‌گوید",
          all("2026-09-22" in i.message for i in after.expired()))

    # نسخه‌بندی زمانی: نسخه منقضی نباید «آخرین نسخه معتبر» بماند
    node = {"value": "پیش‌فرض", "versions": [
        {"effective_from": "2026-01-01", "value": "قدیمی"},
        {"effective_from": "2026-05-01", "expires_on": "2026-06-30", "value": "موقت"},
    ]}
    rb_in = RuleBook(as_of=date(2026, 6, 15))
    rb_out = RuleBook(as_of=date(2026, 7, 15))
    check("داخل پنجره، نسخه موقت انتخاب می‌شود",
          rb_in._resolve_versions(node) == "موقت")
    check("پس از انقضا، به نسخه پیشین برمی‌گردد نه نسخه منقضی",
          rb_out._resolve_versions(node) == "قدیمی",
          str(rb_out._resolve_versions(node)))

    # بازتاب در خروجی‌های انسانی
    from gsi.report.system_health import rule_window_table, summary_rows
    t = rule_window_table()
    check("جدول پنجره اعتبار ساخته می‌شود و ستون‌های لازم را دارد",
          not t.empty and {"وضعیت", "روز باقی‌مانده", "تا تاریخ"} <= set(t.columns),
          str(list(t.columns)))
    check("جدول از نزدیک‌ترین انقضا مرتب می‌شود",
          list(t["روز باقی‌مانده"]) == sorted(t["روز باقی‌مانده"]))
    check("خلاصه سلامت، انقضای نزدیک را اعلام می‌کند",
          any("انقضا" in k for k, _ in summary_rows()),
          str([k for k, _ in summary_rows()]))
    check("doctor پنجره اعتبار را بررسی می‌کند",
          "expiring_soon" in open(os.path.join(ROOT, "gsi/doctor.py"),
                                  encoding="utf-8").read())


def main() -> int:
    print("=" * 78)
    print("V26.20.2 — برداری‌سازی ۳۸، سامانه انبار، پنجره اعتبار قوانین")
    print("=" * 78)
    test_s38_vectorised()
    test_warehouse_declaration()
    test_rule_expiry()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        for f in FAIL:
            print(f"   ❌ {f}")
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
