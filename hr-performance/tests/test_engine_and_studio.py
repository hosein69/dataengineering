# -*- coding: utf-8 -*-
"""تست موتور کلاستر، دفترچه سورس، ویرایش رنگ/جابه‌جایی و نقشهٔ سیال.

هرجا ممکن بوده، داده با **پاسخ معلوم** ساخته شده: می‌دانیم کدام شاخص
عمداً در کلاستر غلط گذاشته شده، پس تست می‌سنجد که موتور آن را پیدا
می‌کند — نه فقط اینکه کد بدون خطا اجرا می‌شود.
"""
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
os.environ.setdefault("HRP_HOME", tempfile.mkdtemp(prefix="hrp_eng_"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from hrperf.config import editor as ed  # noqa: E402
from hrperf.config.model import Cluster, Metric, PerformanceModel, load_model  # noqa: E402
from hrperf.dataio import registry as reg  # noqa: E402
from hrperf.model_engine import vectors as ve  # noqa: E402
from hrperf.report import fluid  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  → {detail}" if detail else ""))


def _planted(n=90, seed=4):
    """داده با پاسخ معلوم: دو خانواده شاخص، و یک شاخص در کلاستر غلط.

    a1..a3 با هم حرکت می‌کنند، b1..b3 هم. شاخص ``stray`` عملاً یکی از
    خانوادهٔ B است ولی در کلاستر A گذاشته شده — موتور باید پیدایش کند.
    """
    rng = np.random.default_rng(seed)
    fa, fb = rng.normal(0, 1, n), rng.normal(0, 1, n)

    def near(f, sd):
        return 50 + 12 * f + rng.normal(0, sd, n)

    df = pd.DataFrame({
        "a1": near(fa, 3), "a2": near(fa, 3.5), "a3": near(fa, 4),
        "b1": near(fb, 3), "b2": near(fb, 3.5), "b3": near(fb, 4),
        "stray": near(fb, 3.2),              # ← عضو خانوادهٔ B، در کلاستر A
        "flat": 50 + rng.normal(0, 0.4, n),  # تقریباً ثابت برای همه
    })
    member = {"a1": "A", "a2": "A", "a3": "A", "stray": "A",
              "b1": "B", "b2": "B", "b3": "B", "flat": "A"}
    return df, member


def _model_from(member):
    keys = sorted(set(member.values()))
    clusters = {ck: Cluster(ck, f"کلاستر {ck}", 1.0 / len(keys), True, "برای تست")
                for ck in keys}
    metrics = {}
    for mk, ck in member.items():
        sibs = [x for x, c in member.items() if c == ck]
        metrics[mk] = Metric(mk, f"شاخص {mk}", ck, 1.0 / len(sibs), "higher",
                             "ratio", "direct", "scored", citation="تست")
    return PerformanceModel(clusters, metrics, "1.0")


def test_vectors() -> None:
    print("\n── ۱) فضای برداری ──")
    df, member = _planted()
    model = _model_from(member)
    vec = ve.vectors(df, model)
    check("ماتریس بردار ساخته می‌شود", vec.shape[1] >= 7, str(vec.shape))

    sim = ve.similarity(vec)
    check("هم‌خانواده‌ها همبستگی بالا دارند", sim.loc["a1", "a2"] > 0.7,
          f"{sim.loc['a1','a2']:.2f}")
    check("ناهم‌خانواده‌ها همبستگی پایین دارند", abs(sim.loc["a1", "b1"]) < 0.3,
          f"{sim.loc['a1','b1']:.2f}")

    m2 = _model_from(member)
    m2.metrics["b1"] = Metric(**{**m2.metrics["b1"].__dict__, "direction": "lower"})
    flipped = ve.similarity(ve.vectors(df, m2)).loc["b1", "b2"]
    check("شاخص «کمتر بهتر» قرینه می‌شود",
          np.sign(flipped) != np.sign(sim.loc["b1", "b2"]),
          f"{flipped:+.2f} در برابر {sim.loc['b1','b2']:+.2f}")

    fits = {f.metric: f for f in ve.fit_table(vec, member)}
    check("شاخصِ عمداً بدجا، «به کلاستر دیگری نزدیک‌تر» تشخیص داده می‌شود",
          fits["stray"].verdict == "به کلاستر دیگری نزدیک‌تر است",
          f"{fits['stray'].own:+.2f} در برابر {fits['stray'].best_other_sim:+.2f}")
    check("و کلاستر درست را نام می‌برد", fits["stray"].best_other == "B",
          fits["stray"].best_other)
    check("شاخصِ درست‌جا، «در جای خودش» است",
          fits["b1"].verdict == "در جای خودش", fits["b1"].verdict)

    coh = {c.cluster: c for c in ve.cohesion(sim, member)}
    check("کلاستر آلوده، انسجام کمتری از کلاستر سالم دارد",
          coh["A"].mean_within < coh["B"].mean_within,
          f"A={coh['A'].mean_within:+.2f} B={coh['B'].mean_within:+.2f}")
    check("کلاستر سالم «منسجم» اعلام می‌شود", coh["B"].verdict == "منسجم",
          coh["B"].verdict)

    lay = ve.layout(sim, member)
    check("نقشه دوبعدی ساخته می‌شود", lay.shape[0] == len(sim.columns))
    check("مختصات نرمال است",
          float(np.abs(lay[["x", "y"]].to_numpy()).max()) <= 1.001)
    d_in = float(np.hypot(*(lay.loc["a1", ["x", "y"]] - lay.loc["a2", ["x", "y"]])))
    d_out = float(np.hypot(*(lay.loc["a1", ["x", "y"]] - lay.loc["b1", ["x", "y"]])))
    check("هم‌خانواده روی نقشه نزدیک‌تر می‌نشیند", d_in < d_out,
          f"{d_in:.2f} < {d_out:.2f}")


def test_suggestions() -> None:
    print("\n── ۲) پیشنهاد با دلیل ──")
    df, member = _planted()
    model = _model_from(member)
    sug = ve.suggest(df, model)
    check("موتور پیشنهاد می‌دهد", len(sug) > 0, f"{len(sug)} پیشنهاد")
    check("هر پیشنهاد دلیل دارد", all(len(s.reason) > 30 for s in sug))
    moves = [s for s in sug if s.kind == "move"]
    check("جابه‌جایی شاخص بدجا پیشنهاد می‌شود",
          any(s.metric == "stray" and s.to_cluster == "B" for s in moves),
          str([(s.metric, s.to_cluster) for s in moves]))
    check("دلیل، هر دو عدد را می‌گوید",
          any(s.metric == "stray" and "+" in s.reason for s in moves))
    check("شاخصی که تفکیک ایجاد نمی‌کند، برای کاهش وزن علامت می‌خورد",
          any(s.kind == "reweight" and s.metric == "flat" for s in sug),
          str([s.metric for s in sug if s.kind == "reweight"]))

    df2 = df.copy()
    df2["a1_copy"] = df2["a1"] + np.random.default_rng(1).normal(0, .2, len(df2))
    m2 = dict(member)
    m2["a1_copy"] = "A"
    check("هم‌پوشانی دو شاخصِ تقریباً یکسان اعلام می‌شود",
          any(s.kind == "redundant" for s in ve.suggest(df2, _model_from(m2))))

    clean = {k: v for k, v in member.items() if k not in ("stray", "flat")}
    sug3 = ve.suggest(df[list(clean)], _model_from(clean))
    check("روی مدل سالم، جابه‌جایی پیشنهاد نمی‌شود",
          not any(s.kind == "move" for s in sug3), str([s.kind for s in sug3]))


def test_editor_moves_and_colors() -> None:
    print("\n── ۳) جابه‌جایی و رنگ ──")
    m = load_model()
    src = m.metrics["status_traceability"].cluster
    m2 = ed.move_metric(m, "status_traceability", "reliability")
    check("شاخص جابه‌جا می‌شود",
          m2.metrics["status_traceability"].cluster == "reliability")
    check("مدل پس از جابه‌جایی معتبر می‌ماند", m2.validate() == [], str(m2.validate()))
    for ck in (src, "reliability"):
        s = sum(x.weight for x in m2.cluster_metrics(ck))
        check(f"وزن آیتم‌های «{m2.clusters[ck].label}» دوباره ۱ می‌شود",
              abs(s - 1) < 1e-9, f"{s:.6f}")
    check("جابه‌جایی در diff دیده می‌شود",
          any("ردیاب" in d or "status_traceability" in d for d in ed.diff(m, m2)),
          str(ed.diff(m, m2)[:2]))
    for label, fn in [
        ("شاخص ناموجود", lambda: ed.move_metric(m, "no_such", "reliability")),
        ("کلاستر ناموجود", lambda: ed.move_metric(m, "status_traceability", "no_such")),
        ("جابه‌جایی به همان کلاستر",
         lambda: ed.move_metric(m, "status_traceability", src)),
    ]:
        try:
            fn()
            check(f"جلوگیری از «{label}»", False, "اجازه داد!")
        except ed.EditError as ex:
            check(f"جلوگیری از «{label}»", True, str(ex)[:46] + "…")

    m3 = ed.set_color(m, "reliability", "#0d6e66")
    check("رنگ کلاستر ذخیره می‌شود", m3.clusters["reliability"].color == "#0d6e66")
    check("رنگ در خروجی YAML می‌ماند",
          ed.to_dict(m3)["clusters"]["reliability"].get("color") == "#0d6e66")
    check("رنگ خالی، برگشت به پالت است",
          ed.set_color(m3, "reliability", "").clusters["reliability"].color == "")
    try:
        ed.set_color(m, "reliability", "سبز")
        check("رنگ نامعتبر رد می‌شود", False, "اجازه داد!")
    except ed.EditError as ex:
        check("رنگ نامعتبر رد می‌شود", True, str(ex)[:46] + "…")
    try:
        ed.add_metric(m, "zz", "زد", "reliability", 0.2)
        check("شاخص امتیازی بدون مرجع رد می‌شود", False, "اجازه داد!")
    except ed.EditError as ex:
        check("شاخص امتیازی بدون مرجع رد می‌شود",
              "علمی" in str(ex) or "citation" in str(ex), str(ex)[:46] + "…")


def test_registry() -> None:
    print("\n── ۴) دفترچه سورس ──")
    model = load_model()
    with tempfile.TemporaryDirectory() as td:
        y = Path(td) / "sources.yaml"
        y.write_text(yaml.safe_dump({"version": 1, "custom": {"bazresi": {
            "label": "خروجی واحد بازرسی", "match": "*بازرسی*",
            "person_key": "کد پرسنلی",
            "metrics": {"نرخ تطابق": {"metric": "conformance_score",
                                      "sample": "تعداد پرونده"}}}}},
            allow_unicode=True), encoding="utf-8")
        specs = reg.load(y)
        check("سورس کاربر خوانده می‌شود", "bazresi" in specs)
        check("الگوی نام فایل کار می‌کند",
              specs["bazresi"].accepts("گزارش بازرسی 1405.xlsx")
              and not specs["bazresi"].accepts("other.xlsx"))
        check("سورس سالم، ایراد ندارد", reg.validate(specs, model) == [])

        bad = dict(specs)
        bad["x"] = reg.SourceSpec("x", "X", metrics=[reg.MetricMap("c", "no_such")])
        check("نگاشت به شاخص ناشناخته رد می‌شود",
              any("no_such" in i for i in reg.validate(bad, model)))

        df = pd.DataFrame({"کد پرسنلی": ["GS-1001", "GS-1002"],
                           "نرخ تطابق": [0.9, "خطا"], "تعداد پرونده": [40, 55]})
        out, notes = reg.read(df, specs["bazresi"])
        check("کلید فرد متعارف می‌شود", set(out["person_key"]) == {"00001001"},
              str(sorted(set(out["person_key"]))))
        check("کد خوانا نگه داشته می‌شود", "GS-1001" in set(out["person_code"]))
        check("مقدار غیرعددی صفر نمی‌شود بلکه کنار می‌رود",
              len(out) == 1 and any("عدد نبود" in n for n in notes), str(notes))

        _, notes2 = reg.read(df.drop(columns=["نرخ تطابق"]), specs["bazresi"])
        check("ستون نبود ⇒ سکوت نمی‌کنیم", any("نبود" in n for n in notes2),
              str(notes2))

        p = reg.save(specs, y)
        back = reg.load(p)
        check("دفترچه ذخیره و دوباره خوانده می‌شود",
              "bazresi" in back and back["bazresi"].match == "*بازرسی*")


def test_fluid_html() -> None:
    print("\n── ۵) نقشهٔ سیال ──")
    df, member = _planted()
    model = _model_from(member)
    pay = fluid.build_payload(df, model)
    check("بار داده ساخته می‌شود", len(pay["nodes"]) >= 7, str(len(pay["nodes"])))
    check("هر کلاستر رنگ روشن و تاریک دارد",
          all(c.get("light") and c.get("dark") for c in pay["clusters"].values()))
    check("پیشنهادها همراه بار داده می‌آیند", len(pay["suggestions"]) > 0)
    check("پیوندها فقط همبستگی محسوس‌اند",
          all(abs(l["r"]) >= 0.25 for l in pay["links"]))

    html = fluid.render(pay)
    check("سند راست‌به‌چپ و فارسی است", 'dir="rtl"' in html and 'lang="fa"' in html)
    check("بدون کتابخانه بیرونی است",
          "<script src" not in html and "cdn" not in html.lower())
    check("حرکت با prefers-reduced-motion خاموش می‌شود",
          "prefers-reduced-motion" in html)
    check("نمای جدولی دارد (هویت فقط با رنگ نیست)", 'id="tableView"' in html)
    check("انتخاب رنگ در خودِ صفحه هست", 'type="color"' in html)
    check("تم روشن و تاریک، هر دو تعریف شده",
          'data-theme="dark"' in html and "--surface:#E1F2E9" in html
          and "--surface:#0C1F1A" in html)
    check("پالت آکوای اعتبارسنجی‌شده به‌کار رفته",
          "#008E82" in html and "#22A797" in html)
    check("برچسب مستقیم خوشه کشیده می‌شود", "fillText" in html)

    with tempfile.TemporaryDirectory() as td:
        p = fluid.write(pay, Path(td) / "map.html")
        check("فایل نوشته می‌شود", p.exists() and p.stat().st_size > 8000,
              f"{p.stat().st_size // 1024} KB")

    m2 = ed.set_color(model, "A", "#123456")
    check("رنگ دستی کاربر بر پالت مقدم است",
          fluid.build_payload(df, m2)["clusters"]["A"]["light"] == "#123456")


def test_dispatch() -> None:
    """ارسال گزارش: پیوست دلخواه، گیرندهٔ دلخواه، بدنهٔ امن روی موتور Word."""
    print("\n── ۶) ارسال گزارش ──")
    from hrperf.report import dispatch as dp

    ppl = pd.DataFrame({
        "person_key": ["1", "2", "3", "4"],
        "full_name": ["الف", "ب", "ج", "د"],
        "department": ["اداره ترخیص", "اداره اعتبارات", "اداره ترخیص", "اداره ترخیص"],
        "role": ["کارشناس", "رئیس", "کارشناس", "کارشناس"],
        "active": [1, 1, 0, 1],
        "email": ["a@x.invalid", "b@x.invalid", "c@x.invalid", "بدون‌نشانی"]})
    d = dp.directory(ppl)
    check("فقط افراد فعالِ دارای نشانی معتبر می‌آیند",
          {p.name for p in d} == {"الف", "ب"}, str(sorted(p.name for p in d)))
    check("برچسب انتخابگر، نشانی را نشان نمی‌دهد",
          all("@" not in p.label for p in d), str([p.label for p in d]))
    check("نشانی نقاب‌دار است", all("*" in p.masked for p in d),
          str([p.masked for p in d]))
    check("نشانی واقعی فقط در لحظهٔ ارسال درمی‌آید",
          dp.addresses(d) == ["a@x.invalid", "b@x.invalid"], str(dp.addresses(d)))
    check("جدول بدون ستون ایمیل، فهرست خالی می‌دهد",
          dp.directory(ppl.drop(columns=["email"])) == [])

    body = dp.outlook_body(
        "آزمون", "1405/06/09",
        kpis=[("نفرات", "۶۱", "#14332C"), ("بحرانی", "۵", "#B3261E")],
        headers=["کد", "نام", "عملکرد"],
        rows=[["E1", "الف", "۷۵٫۴"], ["E2", "ب", "۵۱٫۲"]],
        note="یادداشت", attachments=["a.xlsx"], live_url="https://x.invalid/r")

    low = body.lower()
    for token in ("<script", "flex", "display:grid", "<svg", "position:absolute"):
        check(f"بدنه بدون «{token}» است", token not in low)
    check("چیدمان جدول‌محور است", body.count("<table") >= 5, str(body.count("<table")))
    check("CSS درون‌خطی است", 'style="' in body)
    check("VML برای دکمه هست (گوشهٔ گرد روی اتلوک کلاسیک)",
          "v:roundrect" in body and "mso" in body)
    check("ارتقای تدریجی فقط در @media است",
          "prefers-color-scheme" in body and "@media" in body)
    check("راست‌به‌چپ و فارسی", 'dir="rtl"' in body and 'lang="fa"' in body)
    check("پالت آکوا به‌کار رفته", "#005349" in body and "#E1F2E9" in body)
    check("توضیح صادقانه دربارهٔ نبودِ داینامیک هست", "جاوااسکریپت" in body)
    check("تراشهٔ وضعیت با آیکن می‌آید، نه فقط رنگ",
          "▲" in dp._chip("برجسته", "#2E7D32", "▲"))

    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "a.xlsx"
        f.write_bytes(b"x")
        raw = dp.eml("موضوع", body, ["a@x.invalid"], ["b@x.invalid"], [f])
        check("پروندهٔ eml ساخته می‌شود", b"Subject" in raw)
        check("eml رونوشت و پیوست دارد", b"Cc:" in raw and b"a.xlsx" in raw)

    r = dp.Dispatch(to_count=3, cc_count=2, attachments=["a.xlsx"])
    check("خلاصهٔ ارسال فقط تعداد می‌گوید، نه نشانی",
          "3 گیرنده" in r.summary and "@" not in r.summary, r.summary)
    try:
        dp.send("x", body, [])
        check("ارسال بدون گیرنده رد می‌شود", False, "اجازه داد!")
    except Exception as ex:
        check("ارسال بدون گیرنده رد می‌شود", "گیرنده" in str(ex),
              str(ex)[:40] + "…")


if __name__ == "__main__":
    print("=" * 78)
    print("HRPerf — تست موتور کلاستر، دفترچه سورس و نقشهٔ سیال")
    print("=" * 78)
    test_vectors()
    test_suggestions()
    test_editor_moves_and_colors()
    test_registry()
    test_fluid_html()
    test_dispatch()
    print("\n" + "=" * 78)
    print(f"نتیجه: {len(PASS)} موفق | {len(FAIL)} ناموفق")
    if FAIL:
        print("ناموفق: " + " ، ".join(FAIL))
    print("=" * 78)
    sys.exit(1 if FAIL else 0)
