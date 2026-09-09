# -*- coding: utf-8 -*-
"""تست عدالت، گراف، ویرایش مدل، و خروجی داینامیک.

هرجا ممکن بوده، داده با **پاسخ معلوم** ساخته شده: می‌دانیم توزیع چوله
است یا نه، می‌دانیم سیستم پرکارها را جریمه می‌کند یا نه. پس می‌شود سنجید
که تشخیص درست است، نه فقط اینکه کد بدون خطا اجرا می‌شود.

اجرا:  python tests/test_fairness_and_graph.py
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from hrperf.analytics.evidence import (cliffs_delta, mean_ci,  # noqa: E402
                                       rank_corr, wilson)
from hrperf.config import editor as ed  # noqa: E402
from hrperf.config.model import load_model  # noqa: E402
from hrperf.fairness import audit, skew  # noqa: E402
from hrperf.graph import org  # noqa: E402
from hrperf.report.dynamic import build_dynamic_html  # noqa: E402

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


# ═══════════ ۱) چولگی بار ═══════════
def test_skew() -> None:
    print("\n── ۱) چولگی توزیع بار ──")
    equal = pd.Series([10.0] * 40)
    check("توزیع کاملاً برابر ⇒ جینی صفر", abs(skew.gini(equal)) < 1e-9,
          f"{skew.gini(equal):.6f}")

    one = pd.Series([0.0] * 39 + [400.0])
    g_one = skew.gini(one)
    check("همه بار روی یک نفر ⇒ جینی نزدیک یک", g_one > 0.95, f"{g_one:.3f}")

    rng = np.random.default_rng(3)
    bal = pd.Series(rng.normal(50, 5, 80).clip(1))
    sk = pd.Series(np.concatenate([rng.normal(12, 3, 70), rng.normal(220, 20, 10)]).clip(1))
    check("متوازن از چوله تفکیک می‌شود",
          skew.gini(bal) < 0.20 < skew.gini(sk),
          f"{skew.gini(bal):.2f} در برابر {skew.gini(sk):.2f}")
    check("برچسب متوازن درست است", skew.band_of(skew.gini(bal))[0] == "متوازن")
    check("برچسب چوله درست است", "چوله" in skew.band_of(skew.gini(sk))[0])

    check("نمونه خیلی کوچک ⇒ جینی نامعتبر",
          not np.isfinite(skew.gini(pd.Series([5.0]))))
    check("بار صفر برای همه ⇒ نامعتبر، نه صفرِ گمراه‌کننده",
          not np.isfinite(skew.gini(pd.Series([0.0] * 10))))
    check("مقدار منفی کنار گذاشته می‌شود (بار منفی وجود ندارد)",
          np.isfinite(skew.gini(pd.Series([-5.0, 10.0, 20.0, 30.0, 40.0]))))

    lz = skew.lorenz(sk)
    check("منحنی لورنتس از (۰,۰) تا (۱,۱) می‌رود",
          lz and abs(lz[0][0]) < 1e-9 and abs(lz[-1][1] - 1) < 1e-6)
    check("منحنی چوله زیر قطر است", all(y <= x + 1e-9 for x, y in lz))
    check("سهم ۲۰٪ پرکار در توزیع چوله بالاست", skew.top_share(sk) > 0.5,
          f"{skew.top_share(sk):.0%}")


# ═══════════ ۲) وضعیت بار فرد ═══════════
def test_individual_load() -> None:
    print("\n── ۲) بیش‌بار و کم‌بار نسبت به گروه همتا ──")
    rng = np.random.default_rng(5)
    load = np.concatenate([rng.normal(30, 3, 30), [120.0], [2.0]])
    df = pd.DataFrame({"load": load, "grp": ["الف"] * 32})
    f = skew.flag_individuals(df, "load", "grp")
    check("فردِ آشکارا پرکار «بیش‌بار» علامت می‌خورد",
          f["وضعیت بار"].iloc[30] == skew.OVER, f["وضعیت بار"].iloc[30])
    check("فردِ آشکارا کم‌کار «کم‌بار» علامت می‌خورد",
          f["وضعیت بار"].iloc[31] == skew.UNDER, f["وضعیت بار"].iloc[31])
    check("بقیه متوازن می‌مانند",
          (f["وضعیت بار"].iloc[:30] == skew.BALANCED).mean() > 0.9)

    # همان داده با انحراف معیار: فرد پرت خودش سیگما را بزرگ می‌کند
    z_sigma = (120 - load.mean()) / load.std()
    z_mad = f["انحراف نسبی"].iloc[30]
    check("MAD نسبت به انحراف معیار، فرد پرت را بهتر می‌گیرد",
          abs(z_mad) > abs(z_sigma), f"MAD z={z_mad:.1f} در برابر σ z={z_sigma:.1f}")

    small = pd.DataFrame({"load": [1.0, 2.0], "grp": ["ب", "ب"]})
    check("گروه خیلی کوچک ⇒ «نامشخص»، نه قضاوت",
          set(skew.flag_individuals(small, "load", "grp")["وضعیت بار"]) == {"نامشخص"})

    hint = skew.rebalance_hint(f)
    check("پیشنهاد توازن، عدد اجرایی می‌دهد",
          hint.get("نفرات بیش‌بار") == 1 and hint.get("قابل جابه‌جایی", 0) > 0,
          str(hint))


# ═══════════ ۳) ممیزی اجحاف ═══════════
def test_load_penalty() -> None:
    print("\n── ۳) آیا امتیاز، پرکارها را جریمه می‌کند؟ ──")
    rng = np.random.default_rng(9)
    n = 300
    load = rng.gamma(3, 10, n)
    penal = pd.DataFrame({"s": 80 - 0.25 * load + rng.normal(0, 4, n), "w": load})
    neutral = pd.DataFrame({"s": 60 + rng.normal(0, 8, n), "w": load})
    reward = pd.DataFrame({"s": 30 + 0.30 * load + rng.normal(0, 4, n), "w": load})

    a = audit.load_penalty(penal, "s", "w")
    check("سیستمِ جریمه‌کنندهٔ بار تشخیص داده می‌شود", a.penalised, a.verdict)
    check("و همبستگی منفی گزارش می‌شود", a.corr < -0.3, f"{a.corr:+.2f}")

    b = audit.load_penalty(neutral, "s", "w")
    check("سیستم خنثی، به‌غلط متهم نمی‌شود", not b.penalised, b.verdict)

    c = audit.load_penalty(reward, "s", "w")
    check("سیستمی که به پرکارها پاداش می‌دهد هم تفکیک می‌شود",
          not c.penalised and "سود" in c.verdict, c.verdict)

    tiny = audit.load_penalty(penal.head(5), "s", "w")
    check("نمونه کوچک ⇒ داوری نمی‌کند", not tiny.enough, tiny.verdict)

    resid = audit.residual_score(penal["s"], penal["w"])
    check("امتیاز تعدیل‌شده، اثر بار را برمی‌دارد",
          abs(rank_corr(resid, penal["w"])) < 0.15,
          f"{rank_corr(resid, penal['w']):+.2f}")
    check("و میانگین را جابه‌جا نمی‌کند",
          abs(resid.mean() - penal["s"].mean()) < 1e-6)


# ═══════════ ۴) شکاف گروهی ═══════════
def test_group_gap() -> None:
    print("\n── ۴) شکاف گروهی، خام و پس از کنترل بار ──")
    rng = np.random.default_rng(4)
    n = 400
    grp = rng.choice(["الف", "ب"], n)
    # گروه ب فقط بارِ بیشتری دارد؛ کیفیت واقعی یکسان است
    load = np.where(grp == "ب", rng.gamma(6, 9, n), rng.gamma(2, 9, n))
    score = 70 - 0.25 * load + rng.normal(0, 5, n)
    df = pd.DataFrame({"score": score, "grp": grp, "load": load})

    raw = audit.group_gaps(df, "score", "grp")
    b_raw = next(g for g in raw if g.group == "ب")
    check("شکاف خام دیده می‌شود", b_raw.gap < -3, f"{b_raw.gap:+.1f}")

    adj = audit.group_gaps(df, "score", "grp", load_col="load")
    b_adj = next(g for g in adj if g.group == "ب")
    check("پس از حذف اثر بار، شکاف فرو می‌ریزد",
          b_adj.survives is False, b_adj.verdict)
    check("داوری صریح می‌گوید شکاف از بار می‌آید",
          "بار" in b_adj.verdict, b_adj.verdict)
    check("نسبت تأثیر محاسبه می‌شود", np.isfinite(b_adj.ratio), f"{b_adj.ratio:.2f}")

    thin = audit.thin_evidence(pd.DataFrame({"n": [2, 3, 40, 50, 60]}), "n",
                               threshold=10)
    check("شواهد نازک شمرده می‌شود", thin.thin == 2, str(thin.thin))
    check("و حذف نمی‌شود — فقط اعلام", thin.n_people == 5)


# ═══════════ ۵) گراف ═══════════
def test_graph() -> None:
    print("\n── ۵) گراف سازمانی و بارِ پنهان ──")
    rows = [("اداره الف", f"الف{i}", 20.0) for i in range(6)]
    rows += [("اداره ب", f"ب{i}", 20.0) for i in range(6)]
    # «پل» عمداً بارِ کمی دارد ولی تنها مسیر بین دو اداره است
    rows += [("اداره الف", "پل", 3.0), ("اداره ب", "پل", 3.0)]
    df = pd.DataFrame(rows, columns=["office", "person", "load"])
    g = org.build(df, "office", "person", weight="load")

    check("گراف ساخته می‌شود", g.n == 15 and len(g.edges) == 14,
          f"{g.n} گره، {len(g.edges)} یال")
    check("شبکه یکپارچه است (یک مؤلفه)",
          len({v.component for v in g.nodes.values()}) == 1)
    check("درجه وزنی بار را جمع می‌زند",
          abs(g.nodes["اداره الف"].w_degree - 123.0) < 1e-6,
          str(g.nodes["اداره الف"].w_degree))
    check("«پل» مرکزیت بینابینی مثبت دارد", g.nodes["پل"].betweenness > 0,
          f"{g.nodes['پل'].betweenness:.3f}")
    check("برگ‌ها مرکزیت صفر دارند", g.nodes["الف0"].betweenness == 0)

    hid = org.hidden_load(g, min_gap=2)
    check("بارِ پنهان شناسایی می‌شود", any(h.label == "پل" for h in hid),
          str([h.label for h in hid]))
    bridge = next(h for h in hid if h.label == "پل")
    check("و رتبه بارش خیلی پایین‌تر از رتبه مرکزیتش است",
          bridge.load_rank > bridge.between_rank + 5,
          f"بار {bridge.load_rank} در برابر مرکزیت {bridge.between_rank}")

    tiny = org.build(pd.DataFrame({"a": ["x", "y"], "b": ["p", "q"]}), "a", "b")
    check("شبکه خیلی کوچک ⇒ مرکزیت گزارش نمی‌شود",
          all(v.betweenness == 0 for v in tiny.nodes.values()))
    check("ستون ناموجود ⇒ گراف خالی، نه استثنا",
          org.build(df, "nope", "person").n == 0)
    check("جدول گراف ساخته می‌شود", not g.table().empty)


# ═══════════ ۶) ویرایش مدل ═══════════
def test_model_editor() -> None:
    print("\n── ۶) افزودن کلاستر و وزن، با محافظ ──")
    m = load_model()
    n0 = len(m.clusters)

    m2 = ed.add_cluster(m, "compliance", "انطباق رویه", 0.10,
                        "خطای رویه‌ای بعداً به جریمه ارزی تبدیل می‌شود.")
    check("کلاستر تازه افزوده می‌شود", len(m2.clusters) == n0 + 1)
    check("مدل اصلی دست‌نخورده می‌ماند", len(m.clusters) == n0)

    m3 = ed.add_metric(m2, "proc_err", "خطای رویه‌ای", "compliance", 1.0,
                       direction="lower", kind="count")
    check("شاخص تازه به کلاستر وصل می‌شود", "proc_err" in m3.metrics)

    for label, fn in (
        ("دلیل خالی", lambda: ed.add_cluster(m, "safety", "ایمنی", 0.1, "")),
        ("کلید فارسی", lambda: ed.add_cluster(m, "ایمنی", "ایمنی", 0.1, "دلیل")),
        ("کلاستر تکراری", lambda: ed.add_cluster(m, "quality", "ک", 0.1, "دلیل")),
        ("وزن بیرون از بازه", lambda: ed.add_cluster(m, "safety", "ایمنی", 3.0, "دلیل")),
        ("کلاستر ناموجود", lambda: ed.add_metric(m, "x1", "ایکس", "ghost", 1.0)),
        ("جهت نامعتبر", lambda: ed.add_metric(m, "x2", "ایکس", "quality", 1.0,
                                              direction="sideways")),
        ("حذف کلاستر دارای شاخص", lambda: ed.remove_cluster(m, "quality")),
    ):
        try:
            fn()
            check(f"جلوگیری از «{label}»", False, "اجازه داد!")
        except ed.EditError as ex:
            check(f"جلوگیری از «{label}»", True, str(ex)[:52] + "…")

    d = ed.diff(m, m3)
    check("تفاوت دو مدل به زبان آدمیزاد گزارش می‌شود",
          any("کلاستر تازه" in x for x in d), str(d[:2]))

    # ذخیره در مسیر موقت، با پشتیبان و نسخه تازه
    with tempfile.TemporaryDirectory() as t:
        target = Path(t) / "model.yaml"
        target.write_text("model_version: '1.0'\nclusters: {}\nmetrics: {}\n",
                          encoding="utf-8")
        path, backup = ed.save(m3, target)
        check("فایل ذخیره می‌شود", path.exists())
        check("پشتیبان نسخه قبلی ساخته می‌شود", backup.exists())
        body = path.read_text(encoding="utf-8")
        check("نسخه مدل جلو می‌رود", "1.1" in body.split("\n")[0] or "1.1" in body)
        check("سربرگ، نسخه قبلی را نام می‌برد", backup.name in body)
        check("تاریخچه نسخه‌ها خوانده می‌شود", len(ed.history(target)) >= 1)

    check("جهش نسخه درست است", ed.bump("1.0") == "1.1" and ed.bump("2.7") == "2.8")


# ═══════════ ۷) خروجی داینامیک ═══════════
def test_dynamic_html() -> None:
    print("\n── ۷) خروجی HTML داینامیک و متحرک ──")
    rng = np.random.default_rng(2)
    n = 120
    df = pd.DataFrame({
        "نام": [f"همکار {i}" for i in range(n)],
        "عملکرد": np.clip(rng.normal(62, 12, n), 5, 99).round(1),
        "بار کاری": rng.gamma(3, 11, n).round(0),
        "مدیریت": rng.choice(["مواد اولیه", "قطعات"], n),
        "اداره": rng.choice(["خرید", "ترخیص", "اعتبارات"], n),
    })
    h = build_dynamic_html(df, "2026-09-09", score_col="عملکرد", name_col="نام",
                           load_col="بار کاری", dims=["مدیریت", "اداره"])
    for probe in ("مقایسه گروهی", "توزیع امتیاز", "منحنی لورنتس", "drawBar",
                  "drawHist", "drawLorenz", 'id="cdim"', 'id="cmeas"'):
        check(f"«{probe}» در خروجی هست", probe in h)
    check("هیچ اسکریپت/استایل بیرونی بارگذاری نمی‌شود",
          not re.search(r"<(script|link)[^>]+(src|href)\s*=\s*[\"']https?://", h))
    check("SVG خام است", "createElementNS" in h)
    check("حرکت دارد", "transition" in h and "@keyframes" in h)
    check("حرکت با prefers-reduced-motion خاموش می‌شود",
          "prefers-reduced-motion" in h)
    check("تولتیپ دارد", "mousemove" in h)
    check("رسته هشتم به «سایر» می‌رود", "سایر (" in h)
    check("سند راست‌به‌چپ و فارسی است", 'dir="rtl"' in h and 'lang="fa"' in h)
    check("منحنی لورنتس داده دارد", "LZ=[[" in h.replace(" ", ""))

    empty = build_dynamic_html(pd.DataFrame({"x": [1]}), "2026-09-09")
    check("داده بدون ستون امتیاز ⇒ صفحه سالم با توضیح",
          "ستون امتیاز" in empty)


# ═══════════ ۸) پایه‌های آماری ═══════════
def test_evidence_extras() -> None:
    print("\n── ۸) افزوده‌های آماری ──")
    m, lo, hi = mean_ci(pd.Series([10.0, 12, 14, 16, 18]))
    check("میانگین با بازه اطمینان", lo < m < hi, f"{lo:.1f}<{m:.1f}<{hi:.1f}")
    check("تک‌مقدار، بازه صفر می‌دهد نه خطا", mean_ci(pd.Series([5.0]))[0] == 5.0)
    check("سری خالی خطا نمی‌دهد", not np.isfinite(mean_ci(pd.Series([], dtype=float))[0]))

    x = pd.Series(range(50))
    check("همبستگی رتبه‌ای کامل = ۱", abs(rank_corr(x, x) - 1) < 1e-9)
    check("همبستگی معکوس = ‑۱", abs(rank_corr(x, -x) + 1) < 1e-9)
    check("سری ثابت ⇒ نامعتبر، نه صفرِ گمراه‌کننده",
          not np.isfinite(rank_corr(x, pd.Series([7] * 50))))

    a, b = pd.Series(range(30)), pd.Series(range(100, 130))
    check("اندازه اثر Cliff برای جدایی کامل = ‑۱",
          abs(cliffs_delta(a, b) + 1) < 1e-9, f"{cliffs_delta(a, b):.2f}")
    check("توزیع یکسان ⇒ اندازه اثر نزدیک صفر",
          abs(cliffs_delta(a, a)) < 0.05, f"{cliffs_delta(a, a):.3f}")
    check("Wilson همچنان کار می‌کند", 0 <= wilson(5, 40).lo <= wilson(5, 40).hi <= 1)


if __name__ == "__main__":
    print("=" * 78)
    print("HRPerf — عدالت، گراف، ویرایش مدل و خروجی داینامیک")
    print("=" * 78)
    test_skew()
    test_individual_load()
    test_load_penalty()
    test_group_gap()
    test_graph()
    test_model_editor()
    test_dynamic_html()
    test_evidence_extras()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
