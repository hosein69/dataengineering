# -*- coding: utf-8 -*-
"""Regenerate samples/release_html from the real GSI pipeline on synthetic data.

The 29.8.2 samples were produced by a script that was excluded from the package
(``generate_demo_html.py``), so they could not be reproduced after a code change.
This generator uses only shipped code:

    tests/make_synthetic.py  → realistic-header synthetic workbooks (no company data)
    gsi.pipeline.Pipeline    → the production ETL path, into a throw-away DWH
    gsi.studio_core.report_builder.build → the same HTML export users get

Usage:  python tools/make_release_samples.py [output_dir]
"""
from __future__ import annotations

import importlib.util
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: sample file → (report template, access persona, audience title)
SAMPLES = {
    "GSI_SAMPLE_EXECUTIVE.html": ("executive", "executive", "مدیر ارشد"),
    "GSI_SAMPLE_MANAGER.html": ("operational", "manager", "مدیر / رئیس اداره"),
    "GSI_SAMPLE_EXPERT.html": ("operational", "expert", "کارشناس"),
    "GSI_SAMPLE_ANALYST.html": ("process", "expert", "تحلیلگر فرآیند"),
}


def _synthetic_sources(tmp: Path) -> None:
    spec = importlib.util.spec_from_file_location("gsi_make_synthetic", ROOT / "tests" / "make_synthetic.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    dirs = mod.build(str(tmp / "src"))
    os.environ.update({
        "GSI_FOREIGN": dirs["foreign"], "GSI_BLS": dirs["bls"], "GSI_CLEARANCE": dirs["clearance"],
        "GSI_HR": dirs["hr"], "GSI_ESMAEILI": dirs["esmaeili"], "GSI_GS_COMBINE": dirs["gs_combine"],
        "GSI_MOHAMADI": dirs["mohamadi"], "GSI_OUTPUT": dirs["output"], "GSI_LOGS": dirs["logs"],
        "GSI_TODAY": "2026-08-31", "GSI_DWH_PATH": str(tmp / "warehouse.sqlite"),
        "GSI_DATA_ROOT": str(tmp),
    })


def main(out_dir: str | Path = ROOT / "samples" / "release_html") -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.WARNING)
    written: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="gsi_samples_") as td:
        tmp = Path(td)
        _synthetic_sources(tmp)
        from gsi.pipeline import Pipeline
        from gsi.studio_core.report_builder import ReportSpec, build
        res = Pipeline().run(build_report=False)
        for name, (template, persona, audience) in SAMPLES.items():
            spec = ReportSpec(template=template, ref_date="2026-08-31", formats=["html"],
                              persona=persona, file_stem=name[:-5],
                              title="هوشمندی زنجیره تأمین — نمونه ساختگی",
                              html_header="هوشمندی زنجیره تأمین — نمونه ساختگی",
                              html_subtitle=f"داده ساختگی برای نمایش قالب — نه داده واقعی سازمان · مخاطب: {audience}")
            result = build(res.df, res.extras, spec, {}, tmp / "out")
            target = out_dir / name
            shutil.copyfile(result.files["html"], target)
            written.append(target)
    from tools.make_customizable_html_sample import main as customizable
    written.append(Path(customizable(str(out_dir / "GSI_SAMPLE_CUSTOMIZABLE_CASHFLOW.html"))))
    return written


if __name__ == "__main__":
    for path in main(*(sys.argv[1:2] or [])):
        print(path)
