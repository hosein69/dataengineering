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
from hrperf.report.email import (NoRecipients, hr_recipients,  # noqa: E402
                                 recipients)
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


def _hr_people():
    """جدول پرسنلی نمونه — عمداً شامل موارد مرزی."""
    return pd.DataFrame([
        # فعال، مدیر، نشانی سالم  → باید بیاید
        dict(person_key="p1", email="a.manager@x.invalid", active=1,
             role="مدیر", management="مواد اولیه", department="خرید"),
        # فعال، رئیس  → باید بیاید
        dict(person_key="p2", email="b.head@x.invalid", active=1,
             role="رئیس اداره", management="قطعات", department="ترخیص"),
        # غیرفعال با پست مدیریتی → نباید بیاید
        dict(person_key="p3", email="c.left@x.invalid", active=0,
             role="مدیر", management="مواد اولیه", department="خرید"),
        # کارشناس فعال → با پیش‌فرض نباید بیاید
        dict(person_key="p4", email="d.expert@x.invalid", active=1,
             role="کارشناس خرید", management="مواد اولیه", department="خرید"),
        # نشانی ناقص → هرگز نباید بیاید
        dict(person_key="p5", email="not-an-email", active=1,
             role="مدیر", management="قطعات", department="خرید"),
        # نشانی خالی → هرگز نباید بیاید
        dict(person_key="p6", email="", active=1,
             role="مدیر", management="قطعات", department="خرید"),
    ])


def test_email_from_hr():
    print("\n── ۸) گیرنده از سورس HR ──")
    ppl = _hr_people()
    keys = ["HRP_EMAIL_TO", "HRP_RECIPIENTS_FILE", "HRP_EMAIL_FROM_HR",
            "HRP_EMAIL_HR_ROLES", "HRP_EMAIL_HR_MANAGEMENTS",
            "HRP_EMAIL_HR_DEPARTMENTS", "HRP_EMAIL_HR_MAX"]
    saved = {k: os.environ.pop(k, None) for k in keys}
    try:
        got = hr_recipients(ppl)
        check("پیش‌فرض فقط سطوح مدیریتیِ فعال است",
              got == ["a.manager@x.invalid", "b.head@x.invalid"], str(got))
        check("پرسنل غیرفعال حذف می‌شود", "c.left@x.invalid" not in got)
        check("نشانی نامعتبر حذف می‌شود",
              not any("not-an-email" in g for g in got))
        check("ردیف بدون نشانی حذف می‌شود", "" not in got)

        os.environ["HRP_EMAIL_HR_ROLES"] = "کارشناس"
        got = hr_recipients(ppl)
        check("فیلتر نقش کار می‌کند", got == ["d.expert@x.invalid"], str(got))

        os.environ["HRP_EMAIL_HR_MANAGEMENTS"] = "قطعات"
        got = hr_recipients(ppl)
        check("فیلترها با هم AND می‌شوند (کارشناسِ قطعات نداریم)",
              got == [], str(got))
        os.environ.pop("HRP_EMAIL_HR_MANAGEMENTS")

        os.environ["HRP_EMAIL_HR_ROLES"] = "مدیر,رئیس,کارشناس"
        os.environ["HRP_EMAIL_HR_MAX"] = "2"
        check("سقف تعداد رعایت می‌شود", len(hr_recipients(ppl)) == 2)
        os.environ.pop("HRP_EMAIL_HR_MAX")
        os.environ.pop("HRP_EMAIL_HR_ROLES")

        check("جدول خالی ⇒ فهرست خالی", hr_recipients(pd.DataFrame()) == [])
        check("None ⇒ فهرست خالی", hr_recipients(None) == [])
        check("جدول بدون ستون ایمیل ⇒ فهرست خالی",
              hr_recipients(pd.DataFrame({"person_key": ["p1"]})) == [])
        check("ستون فارسی «ایمیل» هم شناخته می‌شود",
              hr_recipients(pd.DataFrame({"ایمیل": ["z@x.invalid"]}))
              == ["z@x.invalid"])

        # ── زنجیره حل ──
        check("بدون HRP_EMAIL_FROM_HR، سورس HR خوانده نمی‌شود",
              recipients(ppl) == [])
        os.environ["HRP_EMAIL_FROM_HR"] = "1"
        check("با فعال‌سازی، از سورس HR خوانده می‌شود",
              recipients(ppl) == ["a.manager@x.invalid", "b.head@x.invalid"])
        os.environ["HRP_EMAIL_TO"] = "override@x.invalid"
        check("متغیر محیطی صریح بر سورس HR اولویت دارد",
              recipients(ppl) == ["override@x.invalid"])
        os.environ.pop("HRP_EMAIL_TO")

        # ── نشانی‌ها نباید لاگ شوند ──
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            hr_recipients(ppl)
        printed = buf.getvalue()
        check("هیچ نشانی‌ای چاپ/لاگ نمی‌شود",
              "@x.invalid" not in printed, printed[:80])
    finally:
        for k in keys:
            os.environ.pop(k, None)
            if saved.get(k) is not None:
                os.environ[k] = saved[k]



# ═══════════ ۹) کشف مسیر ورودی و نقشه سازمانی ═══════════
def test_input_discovery() -> None:
    """خطایی که نمی‌گوید کجا را گشته، دیباگ را به حدس تبدیل می‌کند."""
    print("\n── ۹) کشف مسیر ورودی و نقشه سازمانی ──")
    import json
    from hrperf.config import settings as cfg
    from hrperf.dataio.sources import (explain_missing, find_org_map,
                                       read_org_map)

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        (base / "input_files").mkdir()
        old_cwd = os.getcwd()
        saved = os.environ.pop("HRP_INPUT", None)
        try:
            os.chdir(base)
            cands = [str(x) for x in cfg.input_candidates()]
            check("پوشه جاری اولین نامزد جست‌وجوست",
                  cands[0] == str((base / "input_files").resolve()), cands[0])
            check("مسیر ثابت ویندوزی دیگر تنها نامزد نیست", len(cands) >= 2,
                  str(len(cands)))

            # پوشه هست ولی خالی — نباید «داده‌دار» شمرده شود
            check("پوشه بدون فایل داده، «داده‌دار» نیست",
                  not cfg.has_data(base / "input_files"))
            (base / "input_files" / "README.txt").write_text("x", encoding="utf-8")
            check("فایل متنی، پوشه را داده‌دار نمی‌کند",
                  not cfg.has_data(base / "input_files"))
            (base / "input_files" / "u.csv").write_text(
                "person_key,metric_key,value,sample_n\nE1,q,0.9,10\n",
                encoding="utf-8")
            check("فایل csv پوشه را داده‌دار می‌کند",
                  cfg.has_data(base / "input_files"))
            check("ورودی، همان پوشه کنار محل اجراست",
                  Path(cfg.resolve_input()).resolve()
                  == (base / "input_files").resolve(), cfg.resolve_input())
            check("خروجی کنار ورودی ساخته می‌شود، نه در درایو دیگر",
                  Path(cfg.Settings().OUTPUT_DIR).resolve()
                  == (base / "output").resolve(), cfg.Settings().OUTPUT_DIR)

            os.environ["HRP_INPUT"] = str(base / "elsewhere")
            check("متغیر محیطی بر همه نامزدها مقدم است",
                  cfg.resolve_input() == str(base / "elsewhere"))
            os.environ.pop("HRP_INPUT")

            msg = explain_missing(base / "input_files")
            check("پیام خطا هر مسیر بررسی‌شده را نام می‌برد",
                  str((base / "input_files").resolve()) in msg
                  and "HRP_INPUT" in msg, msg[:60])
            check("پیام خطا مسیر انتخاب‌شده را علامت می‌زند",
                  "انتخاب‌شده" in msg)
            check("پیام خطا راه دمو را هم می‌گوید", "hrperf.cli demo" in msg)

            # نقشه سازمانی: هم قالب فهرستی، هم قالب دیکشنری
            omap = base / "input_files" / "organization_map.json"
            omap.write_text(json.dumps({"people": [
                {"person_key": "E1", "full_name": "الف", "department": "اداره ترخیص",
                 "job_family": "کارشناس ترخیص"}]}, ensure_ascii=False),
                encoding="utf-8")
            check("نقشه سازمانی در پوشه ورودی پیدا می‌شود",
                  find_org_map(base / "input_files") == omap)
            org = read_org_map(omap)
            check("قالب فهرستی نقشه خوانده می‌شود (نه فقط دیکشنری)",
                  len(org) == 1 and org.iloc[0]["department"] == "اداره ترخیص")

            omap.write_text(json.dumps({"people": {
                "الف": {"personnel_id": "E1", "department": "اداره ترخیص"}}},
                ensure_ascii=False), encoding="utf-8")
            org2 = read_org_map(omap)
            check("در قالب دیکشنری، کلید فرد از کد پرسنلی پر می‌شود",
                  org2.iloc[0]["person_key"] == "E1", str(org2.iloc[0].to_dict())[:60])

            # خط لوله باید ساختار را واقعاً بنشاند
            omap.write_text(json.dumps({"people": [
                {"person_key": "E1", "full_name": "الف",
                 "department": "اداره ترخیص", "job_family": "کارشناس ترخیص"}]},
                ensure_ascii=False), encoding="utf-8")
            pipe = Pipeline(input_dir=str(base / "input_files"))
            ppl = pipe._people_from(pd.DataFrame(
                {"person_key": ["E1", "E2"], "metric_key": ["q", "q"],
                 "value": [0.9, 0.8], "sample_n": [10, 10], "source": ["s", "s"]}))
            row = ppl.set_index("person_key").loc["E1"]
            check("ساختار سازمانی روی افراد می‌نشیند (خط فرمان هم، نه فقط داشبورد)",
                  row["department"] == "اداره ترخیص" and row["full_name"] == "الف",
                  str(row.to_dict())[:70])
            check("فردِ خارج از نقشه حذف نمی‌شود",
                  "E2" in set(ppl["person_key"]))
            check("پوشش ناقص نقشه، هشدار می‌دهد",
                  any("نقشه سازمانی" in w for w in pipe._org_notes(2)),
                  str(pipe._org_notes(2))[:60])
            blind = Pipeline(input_dir=str(base / "none"))
            blind._people_from(pd.DataFrame(
                {"person_key": ["E1"], "metric_key": ["q"], "value": [0.9],
                 "sample_n": [10], "source": ["s"]}))
            check("نبودِ نقشه سازمانی هشدار می‌دهد، نه سکوت",
                  any("پیدا نشد" in w for w in blind._org_notes(1)),
                  str(blind._org_notes(1))[:70])
        finally:
            os.chdir(old_cwd)
            if saved is not None:
                os.environ["HRP_INPUT"] = saved
            else:
                os.environ.pop("HRP_INPUT", None)



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
    test_email_from_hr()
    test_input_discovery()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
