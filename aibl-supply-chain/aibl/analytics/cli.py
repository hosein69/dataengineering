# -*- coding: utf-8 -*-
"""‏‏‪python -m aibl analyze‬ — گزارش تحلیلی، بدون ساخت مجدد گزارش رسمی."""
from __future__ import annotations

import argparse
import os
from typing import List, Optional

from ..config.settings import SETTINGS
from ..dataio.logging_setup import log


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aibl analyze",
                                 description="گزارش تحلیلی سبک و قابل استناد")
    ap.add_argument("--out", default="", help="مسیر فایل خروجی HTML")
    ap.add_argument("--control", default="", help="ستون کنترل مخدوش‌کننده")
    a = ap.parse_args(argv)

    from ..analytics.report import write_analysis
    from ..pipeline import Pipeline
    from ..studio_core.field_catalog import build_catalog, unique_labels

    res = Pipeline().run(build_report=False)
    out = a.out or os.path.join(SETTINGS.OUTPUT_DIR, "AIBL_Analysis.html")
    labels = unique_labels(build_catalog(res.main))
    path = write_analysis(res.main, out, str(SETTINGS.today), labels)
    log.info(f"✅ گزارش تحلیلی آماده است: {path}")
    print(path)
    return 0
