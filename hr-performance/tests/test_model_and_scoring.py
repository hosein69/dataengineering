# -*- coding: utf-8 -*-
"""تست مدل، امتیازدهی و گروه همتا.

هر تست یک ایراد واقعی پکیج قبلی را قفل می‌کند.

اجرا:  python tests/test_model_and_scoring.py
"""
from __future__ import annotations

import os
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("HRP_HOME", tempfile.mkdtemp(prefix="hrp_test_"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from hrperf.config.model import Cluster, Metric, ModelError, PerformanceModel, load_model  # noqa: E402
from hrperf.identity.peers import assign, summary  # noqa: E402
from hrperf.score.aggregate import aggregate, contribution  # noqa: E402
from hrperf.score.normalize import (build_reference, calibrate_k,  # noqa: E402
                                    percentile_context, robust_score, shrink)

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


def test_model() -> None:
    print("\n── ۱) مدل دو سطحی ──")
    m = load_model()
    check("مدل بدون ایراد بارگذاری می‌شود", m.validate() == [], str(m.validate()))
    cw = sum(c.weight for c in m.clusters.values() if c.scored)
    check("مجموع وزن کلاسترها ۱ است", abs(cw - 1) < 1e-9, f"{cw:.6f}")
    for k, c in m.clusters.items():
        if not c.scored:
            continue
        s = sum(x.weight for x in m.cluster_metrics(k))
        check(f"مجموع وزن آیتم‌های «{c.label}» ۱ است", abs(s - 1) < 1e-9, f"{s:.6f}")
    tot = sum(m.effective_weight(k) for k in m.metrics)
    check("مجموع وزن مؤثر ۱ است", abs(tot - 1) < 1e-9, f"{tot:.6f}")

    # حجم کار نباید سنگین باشد؛ مواجهه مالی نباید امتیاز بگیرد
    wl = sum(m.effective_weight(x.key) for x in m.cluster_metrics("workload"))
    check("وزن «حجم و پیچیدگی» حداکثر ۱۰٪ است (ضدانگیزه کمّی‌کاری)",
          wl <= 0.10 + 1e-9, f"{wl*100:.1f}%")
    check("«مسئولیت مالی» امتیاز نمی‌گیرد (تخصیص است نه عملکرد)",
          m.effective_weight("financial_responsibility") == 0.0)

    # ساختار نامعتبر باید رد شود
    bad = PerformanceModel(
        clusters={"a": Cluster("a", "A", 0.5)},
        metrics={"x": Metric("x", "X", "a", 0.4, "higher", "ratio", "direct", "scored")})
    check("مدل با وزن ناهماهنگ رد می‌شود", len(bad.validate()) >= 2,
          f"{len(bad.validate())} ایراد")


def test_renormalize() -> None:
    print("\n── ۲) بازنرمال‌سازی پس از ویرایش کاربر ──")
    m = load_model()
    cl = dict(m.clusters)
    cl["quality"] = Cluster("quality", cl["quality"].label, 0.9, True, "")
    edited = PerformanceModel(cl, dict(m.metrics), m.model_version)
    check("ویرایش خام مجموع را از ۱ خارج می‌کند",
          abs(sum(c.weight for c in edited.clusters.values() if c.scored) - 1) > 1e-6)
    fixed = edited.renormalize()
    s = sum(c.weight for c in fixed.clusters.values() if c.scored)
    check("پس از بازنرمال‌سازی مجموع دوباره ۱ می‌شود", abs(s - 1) < 1e-9, f"{s:.6f}")
    check("نسبت‌ها حفظ می‌شوند (کیفیت همچنان سنگین‌ترین)",
          max(fixed.clusters.values(), key=lambda c: c.weight).key == "quality")


def test_shrinkage() -> None:
    print("\n── ۳) انقباض — ایراد اصلی پکیج قبلی ──")
    v = pd.Series([1.00, 0.97, 0.95, 0.93, 0.96, 0.98])
    n = pd.Series([2, 300, 150, 200, 180, 120])
    k = calibrate_k(v, n)
    check("k از داده کالیبره می‌شود و None نیست", k is not None and k > 0, f"k={k:.2f}")
    check("k در بازه معقول است", 1.0 <= k <= 500.0, f"k={k:.2f}")

    no_shrink = robust_score(v, "higher")
    mu = float(np.average(v, weights=n))
    with_shrink = robust_score(shrink(v, n, mu, k), "higher")
    check("بدون انقباض، نمونه ریز (n=2) رتبه اول می‌شود",
          int(no_shrink.idxmax()) == 0)
    check("با انقباض، نمونه ریز دیگر رتبه اول نیست",
          int(with_shrink.idxmax()) != 0,
          f"رتبه اول = ایندکس {int(with_shrink.idxmax())} با n={int(n[with_shrink.idxmax()])}")
    check("امتیاز نمونه ریز به میانه نزدیک می‌شود",
          abs(float(with_shrink.iloc[0]) - 50) < abs(float(no_shrink.iloc[0]) - 50),
          f"{float(no_shrink.iloc[0]):.1f} → {float(with_shrink.iloc[0]):.1f}")


def test_absolute_scoring() -> None:
    print("\n── ۴) امتیاز مطلق، نه حاصل‌جمع صفر ──")
    base = pd.Series([0.90, 0.92, 0.94, 0.96])
    ref = build_reference(base)
    better = base + 0.04                     # کل تیم بهتر شده
    s_base = robust_score(base, "higher", ref)
    s_better = robust_score(better, "higher", ref)
    check("بهبود کل تیم، امتیاز همه را بالا می‌برد (رتبه‌ای نیست)",
          float(s_better.mean()) > float(s_base.mean()) + 1,
          f"{float(s_base.mean()):.1f} → {float(s_better.mean()):.1f}")
    p_base = percentile_context(base, "higher")
    p_better = percentile_context(better, "higher")
    check("رتبه درصدی برعکس، بی‌حرکت می‌ماند (چرا امتیاز نیست)",
          abs(float(p_base.mean()) - float(p_better.mean())) < 1e-9)


def test_peers() -> None:
    print("\n── ۵) گروه همتا ──")
    ppl = pd.DataFrame({
        "person_key": [f"p{i}" for i in range(9)],
        "management": ["م۱"] * 5 + ["م۲"] * 4,
        "department": ["اداره الف"] * 5 + ["اداره ب"] * 4,
        "job_family": ["ترخیص"] * 5 + ["اعتبارات"] * 4,
        "role": ["کارشناس"] * 9,
    })
    a = assign(ppl, min_size=4)
    check("گروه‌ها در دقیق‌ترین سطح ساخته می‌شوند",
          (~a["peer_is_fallback"]).all(), a["peer_level_fa"].unique().tolist())
    check("افراد دو مدیریت در یک گروه نمی‌افتند",
          a["peer_group"].nunique() == 2, str(a["peer_group"].nunique()))

    tiny = pd.concat([ppl, pd.DataFrame([{
        "person_key": "solo", "management": "م۳", "department": "اداره ج",
        "job_family": "بازرسی", "role": "کارشناس"}])], ignore_index=True)
    a2 = assign(tiny, min_size=4)
    solo = a2[a2["person_key"] == "solo"].iloc[0]
    check("گروه زیر حد نصاب صعود می‌کند", bool(solo["peer_is_fallback"]))
    check("سطح صعود در خروجی ثبت می‌شود", bool(str(solo["peer_level_fa"])))
    check("خلاصه گروه‌ها ساخته می‌شود", not summary(a2).empty)


def test_coverage() -> None:
    print("\n── ۶) پوشش داده ──")
    m = load_model()
    keys = [x.key for x in m.scored_metrics]
    sc = pd.DataFrame(50.0, index=["full", "partial"], columns=keys)
    qcols = [x.key for x in m.cluster_metrics("quality")]
    sc.loc["partial", qcols] = np.nan
    r = aggregate(sc, m)
    check("فرد کامل پوشش ۱ دارد", abs(float(r.coverage["full"]) - 1) < 1e-9)
    check("نبودِ یک کلاستر کامل، پوشش را پایین می‌آورد",
          float(r.coverage["partial"]) < 0.95,
          f"{float(r.coverage['partial']):.2f}")
    check("کمبود داده امتیاز را بی‌صدا صفر نمی‌کند",
          pd.notna(r.performance["partial"]))


def test_job_families() -> None:
    print("\n── ۸) نقش کاری — هفت شغل، نه یک شغل ──")
    from hrperf.identity.roles import (FAMILIES, applicable, classify,
                                       coverage, metrics_for)
    check("هفت نقش کاری تعریف شده است", len(FAMILIES) == 7, str(len(FAMILIES)))
    for txt, want in [("کارشناس ترخیص", "clearance"),
                      ("اعتبارات", "credit"),
                      ("رفع تعهد", "settlement"),
                      ("EXPERT_BUYER", "buyer"),
                      ("کنترل اسناد", "doc_control")]:
        check(f"«{txt}» به نقش درست نگاشت می‌شود", classify(txt) == want,
              str(classify(txt)))
    check("متن ناشناخته نقش نمی‌گیرد (حدس زده نمی‌شود)",
          classify("چیز نامربوط") is None)

    cl = set(metrics_for("clearance") or [])
    cr = set(metrics_for("credit") or [])
    check("مجموعه شاخص هر نقش متفاوت است", cl != cr)
    check("«نرخ بارنامه باز» برای ترخیص هست", "open_bill_rate" in cl)
    check("«نرخ بارنامه باز» برای اعتبارات نیست", "open_bill_rate" not in cr)

    ppl = pd.DataFrame({"person_key": ["a", "b"],
                        "job_family": ["کارشناس ترخیص", "کارشناس اعتبارات"]})
    lg = pd.DataFrame({
        "person_key": ["a", "a", "b", "b"],
        "metric_key": ["open_bill_rate", "fpy", "open_bill_rate", "fpy"],
        "value": [0.2, 0.9, 0.3, 0.8], "sample_n": [10, 10, 10, 10],
        "source": ["s"] * 4})
    out = applicable(lg, ppl)
    kept_b = set(out[out["person_key"] == "b"]["metric_key"])
    check("شاخص بی‌ربط به نقش، برای آن فرد کنار گذاشته می‌شود",
          "open_bill_rate" not in kept_b and "fpy" in kept_b, str(sorted(kept_b)))
    kept_a = set(out[out["person_key"] == "a"]["metric_key"])
    check("شاخص مرتبط با نقش حفظ می‌شود",
          {"open_bill_rate", "fpy"} <= kept_a, str(sorted(kept_a)))
    check("توزیع نقش‌ها گزارش می‌شود", not coverage(ppl).empty)


def test_peer_group_by_role() -> None:
    print("\n── ۹) گروه همتا روی نقش کاری ──")
    ppl = pd.DataFrame({
        "person_key": [f"p{i}" for i in range(12)],
        "management": ["م۱"] * 12,
        "department": ["اداره ترخیص"] * 6 + ["اداره اعتبارات"] * 6,
        "job_family": ["کارشناس ترخیص"] * 6 + ["کارشناس اعتبارات"] * 6,
        "role": ["کارشناس"] * 12,
    })
    a = assign(ppl, min_size=4)
    check("کارشناس ترخیص و اعتبارات در یک گروه نمی‌افتند",
          a["peer_group"].nunique() == 2, str(a["peer_group"].nunique()))
    groups = a.groupby("peer_group")["person_key"].apply(set).to_dict()
    mixed = [g for g, members in groups.items()
             if len(members & set(ppl["person_key"][:6])) not in (0, len(members))]
    check("هیچ گروهی دو نقش کاری را قاطی نکرده است", not mixed, str(mixed))


def test_contribution() -> None:
    print("\n── ۷) توضیح‌پذیری ──")
    m = load_model()
    keys = [x.key for x in m.scored_metrics]
    sc = pd.DataFrame(50.0, index=["a"], columns=keys)
    sc.loc["a", "fpy"] = 90.0
    c = contribution(sc, m, "a")
    check("سهم هر شاخص محاسبه می‌شود", not c.empty)
    check("شاخص با بیشترین انحراف، بالاترین سهم را دارد",
          str(c.iloc[0]["کلید"]) == "fpy", str(c.iloc[0]["کلید"]))
    check("سهم شاخصِ روی میانه صفر است",
          abs(float(c[c["کلید"] != "fpy"]["سهم"].abs().max())) < 1e-9)


if __name__ == "__main__":
    print("=" * 78)
    print("HRPerf — تست مدل، امتیازدهی و گروه همتا")
    print("=" * 78)
    test_model()
    test_renormalize()
    test_shrinkage()
    test_absolute_scoring()
    test_peers()
    test_coverage()
    test_job_families()
    test_peer_group_by_role()
    test_contribution()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
