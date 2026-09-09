# -*- coding: utf-8 -*-
"""خط فرمان: ``python -m hrperf.cli {demo|run|report|validate}``"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config.model import load_model
from .config.settings import SETTINGS
from .pipeline import NoInputData, Pipeline
from .report import templates as tpl
from .report.builder import ReportSpec, build
from .version import VERSION


def _run(demo: bool, ref_date: str, persist: bool):
    """اجرا، و اعلام صریحِ اینکه عددها از کجا آمده‌اند.

    گزارشی که نمی‌گوید داده‌اش واقعی است یا نمونه، بدتر از نبودنش است.
    """
    if demo:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from tests.make_synthetic import build as make
        people, long = make()
        print("🧪 داده نمونه (ساختگی) — این اعداد مبنای تصمیم نیستند.")
        return Pipeline().run(long=long, people=people, ref_date=ref_date,
                              persist=persist)
    pipe = Pipeline()
    print(f"📂 پوشه ورودی: {pipe.input_dir}")
    r = pipe.run(ref_date=ref_date, persist=persist)
    org = getattr(pipe, "org_map_path", "")
    print(f"🗺 نقشه سازمانی: {org or '— پیدا نشد'}")
    return r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hrperf", description=f"HRPerf {VERSION}")
    ap.add_argument("command", choices=["demo", "run", "report", "validate"])
    ap.add_argument("--date", default=str(SETTINGS.today))
    ap.add_argument("--template", default=tpl.DEFAULT_TEMPLATE,
                    choices=list(tpl.TEMPLATES))
    ap.add_argument("--formats", default="excel,html,pdf,email")
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--demo", action="store_true",
                    help="استفاده از داده نمونه به‌جای پوشه ورودی")
    a = ap.parse_args(argv)

    if a.command == "validate":
        m = load_model()
        issues = m.validate()
        print("✅ مدل سالم است." if not issues else "❌ " + "\n❌ ".join(issues))
        print(f"   کلاستر: {len(m.clusters)} | شاخص: {len(m.metrics)} | "
              f"امتیازی: {len(m.scored_metrics)}")
        print(f"   مجموع وزن مؤثر: "
              f"{sum(m.effective_weight(k) for k in m.metrics)*100:.2f}%")
        return 1 if issues else 0

    try:
        r = _run(a.command == "demo" or a.demo, a.date, not a.no_db)
    except NoInputData as ex:
        print(f"⚠️ {ex}")
        return 2
    print(f"✅ اجرا انجام شد — {len(r.people)} نفر"
          + (f" · run_id={r.run_id}" if r.run_id else ""))
    for w in r.warnings:
        print(f"   ⚠️ {w}")
    lb = r.leaderboard
    print("\nده نفر برتر (درون گروه همتای خودشان):")
    cols = [c for c in ["کد پرسنلی", "نام", "اداره", "نوع کار", "عملکرد",
                        "رتبه در گروه", "اطمینان"] if c in lb.columns]
    print(lb[cols].head(10).to_string(index=False))

    if a.command == "report":
        out = Path(SETTINGS.OUTPUT_DIR) / a.date / "reports"
        spec = ReportSpec(template=a.template, ref_date=a.date,
                          title=f"عملکرد منابع انسانی — {tpl.get(a.template).title}",
                          formats=[x.strip() for x in a.formats.split(",") if x.strip()],
                          file_stem=f"HR {tpl.get(a.template).title}")
        res = build(r, spec, out)
        print()
        for m in res.messages:
            print("   " + m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
