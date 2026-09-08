# -*- coding: utf-8 -*-
"""تست لایه علّی، خط لوله، پایگاه داده و گزارش‌ها."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("HRP_HOME", tempfile.mkdtemp(prefix="hrp_cp_"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from hrperf.causal.dag import DAG, DEFAULT_DAG  # noqa: E402
from hrperf.causal.effects import (e_value, effect_table, estimate,  # noqa: E402
                                   fair_score, residualize)
from hrperf.dataio import db as dbmod  # noqa: E402
from hrperf.dataio.sources import melt_wide, normalize_long  # noqa: E402
from hrperf.pipeline import Pipeline  # noqa: E402
from hrperf.report import templates as tpl  # noqa: E402
from hrperf.report.builder import ReportSpec, build  # noqa: E402
from hrperf.report.email import NoRecipients, recipients  # noqa: E402
from tests.make_synthetic import build as make  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


def _confounded(n=200, seed=3):
    rng = np.random.default_rng(seed)
    assignment = rng.normal(0, 1, n)
    difficulty = 1.0 * assignment + rng.normal(0, .4, n)
    tenure = rng.normal(0, 1, n)
    workload = 1.1 * assignment + rng.normal(0, .5, n)
    speed = -.5 * workload + .4 * tenure + rng.normal(0, .5, n)
    # کیفیت مستقیماً به سختی و تخصیص وابسته است، نه به حجم
    quality = -.9 * difficulty - .8 * assignment + .5 * tenure + rng.normal(0, .5, n)
    rework = -.7 * quality + rng.normal(0, .5, n)
    efficiency = .5 * speed + .5 * quality + rng.normal(0, .5, n)
    return pd.DataFrame(dict(assignment=assignment, workload=workload,
                             difficulty=difficulty, tenure=tenure, speed=speed,
                             quality=quality, rework=rework, efficiency=efficiency))


def test_dag():
    print("\n── ۱) گراف علّی ──")
    check("DAG بدون دور است", not DEFAULT_DAG.has_cycle())
    bs = DEFAULT_DAG.backdoor_set("workload", "quality")
    check("مجموعه تعدیل از DAG استخراج می‌شود", "assignment" in bs, str(sorted(bs)))
    check("نوادگانِ درمان وارد مجموعه تعدیل نمی‌شوند",
          not (bs & DEFAULT_DAG.descendants("workload")))
    med = DEFAULT_DAG.mediators("workload", "quality")
    check("میانجی شناسایی می‌شود", "speed" in med, str(sorted(med)))
    cyc = DAG().add("a", "b").add("b", "a")
    check("دور تشخیص داده می‌شود", cyc.has_cycle())


def test_confounding():
    print("\n── ۲) تفاوت همبستگی با اثر ──")
    df = _confounded()
    e = estimate(df, DEFAULT_DAG, "difficulty", "speed")
    check("همبستگی خام «سختی → سرعت» قوی و منفی است",
          e.raw < -0.3, f"{e.raw:.3f}")
    check("اثر تعدیل‌شده تقریباً صفر می‌شود (همبستگی مخدوش بود)",
          abs(e.adjusted) < 0.15, f"{e.adjusted:.3f}")
    check("این مورد به‌عنوان گمراه‌کننده علامت می‌خورد", e.misleading)

    t = effect_table(df, DEFAULT_DAG)
    check("جدول اثر برای همه یال‌ها ساخته می‌شود", len(t) >= 8, str(len(t)))
    check("ستون E-value موجود است", "E-value" in t.columns)
    check("E-value برای اثر بزرگ‌تر، بزرگ‌تر است",
          e_value(0.6) > e_value(0.2), f"{e_value(0.6):.2f} > {e_value(0.2):.2f}")
    check("E-value اثر صفر برابر ۱ است", abs(e_value(0.0) - 1.0) < 1e-9)


def test_residual_and_fair():
    print("\n── ۳) امتیاز منصفانه ──")
    df = _confounded()
    r = residualize(df, "quality", ["difficulty"])
    check("باقی‌مانده با تعدیل‌گر ناهمبسته می‌شود",
          abs(float(pd.concat([r, df["difficulty"]], axis=1).corr().iloc[0, 1])) < .1)
    f = fair_score(df.assign(performance=df["quality"]), "performance",
                   ["workload", "difficulty", "assignment", "tenure"])
    check("انتظار محاسبه می‌شود", f["expected"].notna().any())
    check("امتیاز منصفانه در بازه ۵ تا ۹۵ می‌ماند",
          float(f["fair"].min()) >= 5 and float(f["fair"].max()) <= 95,
          f"{float(f['fair'].min()):.1f}..{float(f['fair'].max()):.1f}")
    hard = df["difficulty"].idxmax()
    check("فردِ با سخت‌ترین شرایط، در امتیاز منصفانه جریمه نمی‌شود",
          float(f.loc[hard, "fair"]) > float(f["fair"].min()))


def test_sources():
    print("\n── ۴) خواندن سورس ──")
    wide = pd.DataFrame({"personnel_id": ["a", "b"], "fpy": [.9, .8],
                         "fpy_n": [100, 50], "نام": ["x", "y"]})
    lg = melt_wide(wide, "s")
    check("جدول عریض به بلند تبدیل می‌شود", len(lg) == 2, str(len(lg)))
    check("اندازه نمونه از ستون _n برداشته می‌شود",
          set(lg["sample_n"]) == {100.0, 50.0}, str(sorted(lg["sample_n"])))
    long = pd.DataFrame({"کد پرسنلی": ["a"], "شاخص": ["fpy"],
                         "مقدار": [.95], "مخرج": [10]})
    nl = normalize_long(long, "s")
    check("نام ستون فارسی شناسایی می‌شود",
          not nl.empty and float(nl["value"].iloc[0]) == .95)


def test_pipeline_and_db():
    print("\n── ۵) خط لوله و پایگاه داده ──")
    people, long = make()
    dbp = str(Path(tempfile.mkdtemp()) / "t.sqlite")
    r = Pipeline(db_path=dbp).run(long=long, people=people, ref_date="2026-08-31")
    check("خط لوله بدون خطا اجرا می‌شود", r.run_id is not None, f"run_id={r.run_id}")
    check("همه افراد امتیاز می‌گیرند",
          int(r.scores.performance.notna().sum()) == len(people),
          f"{int(r.scores.performance.notna().sum())}/{len(people)}")
    check("امتیازها در بازه معتبرند",
          float(r.scores.performance.min()) >= 0 and float(r.scores.performance.max()) <= 100)
    check("شاخص کاملاً خالی خط لوله را نمی‌شکند",
          "open_bill_rate" not in r.metric_scores.columns
          or r.metric_scores["open_bill_rate"].isna().all())
    check("گروه همتا برای همه تعیین شده",
          r.people["peer_group"].notna().all())
    check("کالیبراسیون k ثبت شده", not r.calibration.empty)

    perf = dbmod.read("SELECT * FROM performance", path=dbp)
    check("امتیازها در پایگاه داده نوشته شد", len(perf) == len(people), str(len(perf)))
    w = dbmod.read("SELECT * FROM weights WHERE level='cluster'", path=dbp)
    check("وزن‌ها ثبت شد", not w.empty, f"{len(w)} کلاستر")
    ce = dbmod.read("SELECT * FROM causal_effects", path=dbp)
    check("اثرهای علّی ثبت شد", not ce.empty, f"{len(ce)} یال")
    runs = dbmod.runs(path=dbp)
    check("اجرا در جدول runs ثبت شد", len(runs) == 1)

    # اجرای دوم نباید اجرای اول را پاک کند
    Pipeline(db_path=dbp).run(long=long, people=people, ref_date="2026-09-30")
    check("اجرای دوم تاریخچه را حفظ می‌کند",
          len(dbmod.runs(path=dbp)) == 2, str(len(dbmod.runs(path=dbp))))
    return r


def test_reports(r):
    print("\n── ۶) گزارش‌ها ──")
    with tempfile.TemporaryDirectory() as td:
        for key in tpl.TEMPLATES:
            spec = ReportSpec(template=key, ref_date="2026-08-31",
                              formats=["excel", "html", "email"],
                              file_stem=f"t_{key}")
            res = build(r, spec, td)
            check(f"قالب «{tpl.get(key).title}» ساخته می‌شود",
                  {"excel", "html", "email"} <= set(res.files),
                  " | ".join(res.messages))
        spec = ReportSpec(template="executive", ref_date="2026-08-31",
                          formats=["html"], file_stem="rtl")
        res = build(r, spec, td)
        check("HTML راست‌به‌چپ و فارسی است",
              'dir="rtl"' in res.html and 'lang="fa"' in res.html)
        check("دکمه چاپ/PDF دارد", "window.print()" in res.html)
        check("پالت اعتبارسنجی‌شده استفاده شده", "#0ca30c" in res.html)


def test_email_config():
    print("\n── ۷) محرمانگی فهرست گیرندگان ──")
    saved = os.environ.pop("HRP_EMAIL_TO", None)
    try:
        check("بدون پیکربندی، فهرست خالی است (نه فهرست جاسازی‌شده)",
              recipients() == [])
    finally:
        if saved:
            os.environ["HRP_EMAIL_TO"] = saved
    os.environ["HRP_EMAIL_TO"] = "a@x.invalid; b@y.invalid"
    check("فهرست از متغیر محیطی خوانده می‌شود",
          recipients() == ["a@x.invalid", "b@y.invalid"], str(recipients()))
    os.environ.pop("HRP_EMAIL_TO", None)

    leaked = []
    import re
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git"}]
        for f in files:
            if not f.endswith((".py", ".yaml", ".yml", ".md", ".txt")):
                continue
            if f == "recipients.example.yaml":
                continue
            try:
                body = open(os.path.join(base, f), encoding="utf-8").read()
            except Exception:
                continue
            for m in re.finditer(r"[\w.+-]+@[\w-]+\.[\w.]+", body):
                a = m.group(0)
                if not a.lower().endswith((".invalid", ".example", "@example.com")):
                    leaked.append(f"{f}: {a}")
    check("هیچ نشانی ایمیل واقعی در سورس نیست", not leaked, str(leaked[:3]))


if __name__ == "__main__":
    print("=" * 78)
    print("HRPerf — تست علیت، خط لوله، پایگاه داده و گزارش")
    print("=" * 78)
    test_dag()
    test_confounding()
    test_residual_and_fair()
    test_sources()
    r = test_pipeline_and_db()
    test_reports(r)
    test_email_config()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
