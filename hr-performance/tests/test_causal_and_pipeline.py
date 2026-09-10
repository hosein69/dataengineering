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
    responsiveness = -.5 * workload + .4 * tenure + rng.normal(0, .5, n)
    # کیفیت مستقیماً به سختی و تخصیص وابسته است، نه به حجم
    reliability = -.9 * difficulty - .8 * assignment + .5 * tenure + rng.normal(0, .5, n)
    stewardship = -.7 * reliability + rng.normal(0, .5, n)
    conformance = .5 * responsiveness + .5 * reliability + rng.normal(0, .5, n)
    data_quality = .6 * conformance + rng.normal(0, .5, n)
    return pd.DataFrame(dict(assignment=assignment, workload=workload,
                             difficulty=difficulty, tenure=tenure,
                             responsiveness=responsiveness,
                             reliability=reliability, stewardship=stewardship,
                             conformance=conformance, data_quality=data_quality))


def test_dag():
    print("\n── ۱) گراف علّی ──")
    check("DAG بدون دور است", not DEFAULT_DAG.has_cycle())
    bs = DEFAULT_DAG.backdoor_set("workload", "reliability")
    check("مجموعه تعدیل از DAG استخراج می‌شود", "assignment" in bs, str(sorted(bs)))
    check("نوادگانِ درمان وارد مجموعه تعدیل نمی‌شوند",
          not (bs & DEFAULT_DAG.descendants("workload")))
    med = DEFAULT_DAG.mediators("workload", "reliability")
    check("میانجی شناسایی می‌شود", "responsiveness" in med, str(sorted(med)))
    cyc = DAG().add("a", "b").add("b", "a")
    check("دور تشخیص داده می‌شود", cyc.has_cycle())


def test_confounding():
    print("\n── ۲) تفاوت همبستگی با اثر ──")
    df = _confounded()
    e = estimate(df, DEFAULT_DAG, "difficulty", "responsiveness")
    check("همبستگی خام «سختی → پاسخ‌گویی» قوی و منفی است",
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
    r = residualize(df, "reliability", ["difficulty"])
    check("باقی‌مانده با تعدیل‌گر ناهمبسته می‌شود",
          abs(float(pd.concat([r, df["difficulty"]], axis=1).corr().iloc[0, 1])) < .1)
    f = fair_score(df.assign(performance=df["reliability"]), "performance",
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
          "distinct_parts" not in r.metric_scores.columns
          or r.metric_scores["distinct_parts"].isna().all())
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
        # نظام البرز: بدنه روی زمینهٔ طوسی-کاهی می‌نشیند و آکوا فقط
        # سربرگ و سطح‌های تیره را رنگ می‌کند.
        from hrperf.report import alborz as _AL
        check("زمینهٔ گزارش از نظام البرز است",
              _AL.PAGE in res.html or _AL.CARD in res.html,
              f"{_AL.PAGE} / {_AL.CARD}")
        check("سربرگ گزارش طیف آکوا دارد",
              _AL.AQUA_700 in res.html or _AL.AQUA_900 in res.html,
              f"{_AL.AQUA_700} / {_AL.AQUA_900}")


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
                  org2.iloc[0]["person_key"] == "00000001"
                  and org2.iloc[0]["person_code"] == "E1",
                  str(org2.iloc[0].to_dict())[:70])

            # خط لوله باید ساختار را واقعاً بنشاند
            omap.write_text(json.dumps({"people": [
                {"person_key": "E1", "full_name": "الف",
                 "department": "اداره ترخیص", "job_family": "کارشناس ترخیص"}]},
                ensure_ascii=False), encoding="utf-8")
            pipe = Pipeline(input_dir=str(base / "input_files"))
            ppl = pipe._people_from(pd.DataFrame(
                {"person_key": ["E1", "E2"], "metric_key": ["q", "q"],
                 "value": [0.9, 0.8], "sample_n": [10, 10], "source": ["s", "s"]}))
            row = ppl.set_index("person_key").loc["00000001"]
            check("ساختار سازمانی روی افراد می‌نشیند (خط فرمان هم، نه فقط داشبورد)",
                  row["department"] == "اداره ترخیص" and row["full_name"] == "الف",
                  str(row.to_dict())[:70])
            check("فردِ خارج از نقشه حذف نمی‌شود",
                  "00000002" in set(ppl["person_key"]), str(list(ppl["person_key"])))
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



# ═══════════ ۱۰) مقاومت کلید فرد (کد پرسنلی با پیشوند GS-) ═══════════
def test_person_key_robustness() -> None:
    """«GS-1234» و «1234» و «1234.0» یک نفرند — نه سه نفر."""
    print("\n── ۱۰) مقاومت کد پرسنلی ──")
    import json
    from hrperf.identity import keys as km

    forms = ["GS-1234", "1234", "1234.0", "GS\u2011\u06f1\u06f2\u06f3\u06f4",
             "gs-01234", "  GS-1234  ", "GS_1234"]
    got = {km.clean_person_key(f) for f in forms}
    check("هفت شکل مختلف کد، یک کلید می‌شوند", got == {"00001234"}, str(got))
    check("پیشوند حرفی جدا می‌شود", km.key_prefix("GS-1234") == "GS")
    check("کد بی‌پیشوند، پیشوند خالی دارد", km.key_prefix("1234") == "")
    check("کلید بدون رقم حذف نمی‌شود (هیچ‌کس نباید گم شود)",
          km.clean_person_key("AHMADI") == "AHMADI")
    check("خالی، خالی می‌ماند و به «0» تبدیل نمی‌شود",
          km.clean_person_key(None) == "" and km.clean_person_key("  ") == "")
    check("کد بلندتر از ۸ رقم بریده نمی‌شود",
          km.clean_person_key("123456789") == "123456789")
    check("قاعده با clean_employee_code پکیج زنجیره تأمین یکی است",
          km.clean_person_key("10201069_GS") == "10201069")
    # نام با عدد، کد پرسنلی نیست — وگرنه دو نفر یکی می‌شوند
    check("نام فارسیِ شماره‌دار، کد پرسنلی شمرده نمی‌شود",
          km.clean_person_key("بازرگانی 1") != km.clean_person_key("ترخیص 1"),
          f'{km.clean_person_key("بازرگانی 1")} vs {km.clean_person_key("ترخیص 1")}')
    check("حروف فارسی در کلید نگه داشته می‌شوند",
          "بازرگانی" in km.clean_person_key("بازرگانی 1"),
          km.clean_person_key("بازرگانی 1"))
    check("تیرهٔ نشکن یونیکد، کد را از کد جدا نمی‌کند",
          km.clean_person_key("GS\u20111234") == "00001234",
          km.clean_person_key("GS\u20111234"))
    check("شکل نمایشی، همانی است که کاربر می‌شناسد",
          km.display_code(pd.Series(["1234", "GS-1234", "1234.0"])) == "GS-1234")

    # ابهام واقعی گزارش می‌شود، ابهام قلابی نه
    check("دو پیشوند متفاوت روی یک شماره، اعلام می‌شود",
          set(km.collisions(["GS-1234", "IK-1234"])) == {"00001234"})
    check("نبودِ پیشوند، «تعارض پیشوند» شمرده نمی‌شود (هشدار کاذب)",
          km.collisions(["GS-1234", "1234", "1234.0"]) == {})
    msg = " ".join(km.notes(["GS-1234", "1234", "IK-1234"]))
    check("هشدار ادغام، به زبان آدمیزاد است", "یک نفر نسبت داده شد" in msg, msg[:60])
    check("هشدار تعارض پیشوند، خطر را می‌گوید",
          "دو پیشوند متفاوت" in msg and "اشتباه" in msg, msg[-70:])

    df = km.attach(pd.DataFrame({"person_key": ["GS-1234", "1234"]}))
    check("کلید متعارف می‌نشیند و شکل خام نگه داشته می‌شود",
          list(df["person_key"]) == ["00001234", "00001234"]
          and list(df["person_code"]) == ["GS-1234", "1234"],
          str(df.to_dict("list")))

    # ── سنجه واقعی: دو فایل، دو شکل کد، یک نفر ──
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "input_files"
        d.mkdir()
        codes = [10200000 + i for i in range(1, 13)]
        pd.DataFrame([{"کد پرسنلی": f"GS-{c}", "نام": f"کارمند {c}",
                       "conformance_score": 0.90, "conformance_score_n": 40,
                       "status_traceability": 0.85, "status_traceability_n": 40}
                      for c in codes]).to_csv(d / "a.csv", index=False,
                                              encoding="utf-8-sig")
        pd.DataFrame([{"کد پرسنلی": float(c),          # اکسل عددی خوانده
                       "on_time_stage_rate": 0.80, "on_time_stage_rate_n": 40,
                       "ball_in_court_days": 12, "ball_in_court_days_n": 40}
                      for c in codes]).to_csv(d / "b.csv", index=False,
                                              encoding="utf-8-sig")
        json.dump({"people": [
            {"person_key": f"GS-{c}", "full_name": f"کارمند {c}",
             "management": "مدیریت خرید خارجی قطعات تولیدی",
             "department": "اداره ترخیص", "job_family": "کارشناس ترخیص"}
            for c in codes]},
            open(d / "organization_map.json", "w", encoding="utf-8"),
            ensure_ascii=False)

        r = Pipeline(input_dir=str(d)).run(persist=False, ref_date="2026-08-31")
        check("دو شکل کد، یک نفر می‌شوند نه دو نفر",
              len(r.people) == len(codes), f"{len(r.people)} به‌جای {len(codes)}")
        lb = r.leaderboard
        check("کد خوانا در گزارش می‌آید، نه کلید صفرچین",
              "کد پرسنلی" in lb.columns
              and str(lb["کد پرسنلی"].iloc[0]).startswith("GS-"),
              str(lb["کد پرسنلی"].iloc[0]) if "کد پرسنلی" in lb.columns else "—")
        check("شاخص هر دو فایل به یک نفر می‌چسبد (پوشش کامل‌تر)",
              float(r.scores.coverage.min()) > 0.6,
              f"کمینه پوشش {float(r.scores.coverage.min()):.2f}")
        check("نقشه سازمانی با کد GS- به سورس عددی می‌چسبد",
              (r.people["department"].astype(str).ne("")).all(),
              str(r.people["department"].head(2).tolist()))
        check("رکورد شبح (نیمه‌خالی) ساخته نمی‌شود",
              not r.scores.coverage.isna().any()
              and float(r.scores.coverage.min()) > 0)



# ═══════════ ۱۱) کلاسترها از خروجی AIBL ═══════════
def _aibl_cases(n=240, seed=5) -> pd.DataFrame:
    """جدولی به شکل خروجی واقعی AIBL — سه حوزه روی یک پرونده."""
    rng = np.random.default_rng(seed)
    stages = ["PR", "PO", "ORDER_REG", "ALLOCATION", "FX_SUPPLY",
              "SHIPMENT", "CUSTOMS", "DOCS", "RELEASE"]
    fa = {"PR": "کارشناس خرید", "PO": "کارشناس خرید", "RELEASE": "کارشناس خرید",
          "ORDER_REG": "کارشناس بازرگانی", "ALLOCATION": "کارشناس بازرگانی",
          "FX_SUPPLY": "کارشناس بازرگانی", "DOCS": "کارشناس بازرگانی",
          "SHIPMENT": "کارشناس حمل و لجستیک", "CUSTOMS": "کارشناس حمل و لجستیک"}
    st = rng.choice(stages, n)
    return pd.DataFrame({
        "MOGH_KEY_EMP": rng.choice([f"GS-1020{i:04d}" for i in range(1, 7)], n),
        "EXPERT_PURCHASING": rng.choice([f"GS-1020{i:04d}" for i in range(1, 7)], n),
        "EXPERT_COMMERCIAL": rng.choice([f"بازرگانی {i}" for i in range(1, 5)], n),
        "EXPERT_LOGISTICS": rng.choice([f"ترخیص {i}" for i in range(1, 4)], n),
        "STATUS_STAGE": st,
        "WAITING_ON_SCOPE": [fa[x] for x in st],
        "STATUS_AGE_DAYS": rng.integers(1, 120, n),
        "STATUS_MISSING": rng.choice(["", "تاریخ تخلیه"], n, p=[.8, .2]),
        "امتیاز انطباق (٪)": rng.integers(45, 100, n),
        "فعالیت‌های جاافتاده": rng.choice(["", "تخصیص ارز"], n, p=[.8, .2]),
        "نقض ترتیب": rng.choice(["", "ترخیص پیش از کوتاژ"], n, p=[.9, .1]),
        "روزهای تأخیر": rng.choice([0, 0, 0, 5, 40], n),
        "روزهای رسوب": rng.integers(0, 150, n),
        "NTSW_ALLOC_DATE": "1404/09/10",
        "BUY_DATE": rng.choice(["1404/09/20", "1404/10/15"], n),
        "FULL_CLEAR_DATE": rng.choice(["", "1405/01/05"], n, p=[.35, .65]),
        "PARTIAL_CLEAR_DATE": rng.choice(["", "1405/01/02"], n, p=[.7, .3]),
        "SATA_NO": rng.choice(["", "S1"], n, p=[.2, .8]),
        "COT_DATE": rng.choice(["", "1405/01/03"], n, p=[.25, .75]),
        "FIN_RECEIPT_DATE": rng.choice(["", "1405/02/01"], n, p=[.4, .6]),
        "CANONICAL_PART_NO": rng.choice([f"P{i}" for i in range(30)], n),
        "کد طبقه بحرانی": rng.choice(["SAFE", "WATCH", "CRITICAL"], n, p=[.6, .25, .15]),
        "CB_VALUE": rng.integers(5000, 900000, n),
        "TRANSPORT_MODE": rng.choice(["دریایی", "زمینی"], n, p=[.7, .3]),
        "PART_OWNER_DATA_GAP": rng.choice(["", "شماره بارنامه"], n, p=[.7, .3]),
    })


def test_aibl_clusters() -> None:
    """سنجه‌ها از پروندهٔ زنجیره تأمین، هرکس در حوزهٔ خودش."""
    print("\n── ۱۱) کلاسترها از خروجی AIBL ──")
    from hrperf.config.model import load_model
    from hrperf.core.calendar import CalendarEngine
    from hrperf.dataio import aibl as ad
    from hrperf.dataio.sources import is_aibl
    from hrperf.identity import scopes

    check("تاریخ شمسی با موتور تقویم خوانده می‌شود، نه pandas",
          str(CalendarEngine.parse("1405/01/29")) == "2026-04-18",
          str(CalendarEngine.parse("1405/01/29")))

    df = _aibl_cases()
    check("جدول AIBL از روی ستون حوزه تشخیص داده می‌شود", is_aibl(df))
    ex = ad.to_long(df)
    check("هر سه حوزه استخراج می‌شوند", len(ex.by_scope) == 3, str(ex.by_scope))
    check("هیچ سنجه‌ای بی‌ستون نماند", not ex.missing, str(ex.missing))

    got = ex.long.groupby("metric_key")["scope"].apply(set).to_dict()
    only = {
        "customs_dwell_days": "EXPERT_LOGISTICS",
        "in_full_rate": "EXPERT_LOGISTICS",
        "overdue_commitment_rate": "EXPERT_COMMERCIAL",
        "allocation_lag_days": "EXPERT_COMMERCIAL",
        "owner_field_completeness": "EXPERT_PURCHASING",
        "part_criticality_mix": "EXPERT_PURCHASING",
    }
    for mk, sc in only.items():
        check(f"«{mk}» فقط برای {scopes.BY_KEY[sc].fa} ساخته می‌شود",
              got.get(mk) == {sc}, str(got.get(mk)))
    check("سنجهٔ مشترک برای هر سه حوزه ساخته می‌شود",
          len(got.get("conformance_score", set())) == 3,
          str(got.get("conformance_score")))

    # ستون نبود ⇒ سنجه ساخته نشود، نه اینکه صفر شود
    thin = ad.to_long(df.drop(columns=["روزهای رسوب"]))
    check("نبودِ ستون، سنجه را صفر نمی‌کند بلکه حذفش می‌کند",
          "customs_dwell_days" not in set(thin.long["metric_key"])
          and "customs_dwell_days" in thin.missing,
          str(thin.missing.get("customs_dwell_days")))

    # مدل: حوزه و مرجع اجباری
    m = load_model()
    check("همه سنجه‌های امتیازی مرجع علمی دارند",
          all(x.citation for x in m.scored_metrics))
    check("حوزهٔ همه سنجه‌ها معتبر است",
          all(x.scope in ({scopes.ANY} | set(scopes.BY_KEY))
              for x in m.metrics.values()))
    check("سنجه‌های AIBL به ستون سرچشمه اشاره می‌کنند",
          all(x.aibl_field for x in m.scored_metrics),
          str([x.key for x in m.scored_metrics if not x.aibl_field]))

    # خط لوله سرتاسری روی همین داده
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "input_files"
        d.mkdir()
        df.to_csv(d / "AIBL_cases.csv", index=False, encoding="utf-8-sig")
        r = Pipeline(input_dir=str(d)).run(persist=False, ref_date="2026-08-31")
        check("خط لوله روی پروندهٔ AIBL اجرا می‌شود",
              len(r.people) == 13, f"{len(r.people)} نفر")
        cs = r.scores.cluster_scores
        for ck in ("reliability", "conformance", "responsiveness"):
            check(f"کلاستر «{m.clusters[ck].label}» امتیاز می‌گیرد",
                  ck in cs.columns and cs[ck].notna().any())
        check("امتیاز همه در بازه معتبر است",
              bool(r.scores.performance.between(0, 100).all()))
        check("کارشناس حمل، امتیاز «تعهد ارزی» نمی‌گیرد",
              r.metric_scores.loc[
                  r.people.set_index("person_key")["job_family"]
                  .eq("کارشناس حمل و لجستیک").reindex(
                      r.metric_scores.index).fillna(False).to_numpy(),
                  "overdue_commitment_rate"].isna().all()
              if "overdue_commitment_rate" in r.metric_scores.columns else True)



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
    test_person_key_robustness()
    test_aibl_clusters()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
