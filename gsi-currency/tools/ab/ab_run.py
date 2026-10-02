"""One A/B arm: run package <pkg> on dataset <env> N times into <out>; dump everything.

    python tools/ab/ab_run.py <extracted_pkg_dir> <dataset/env.sh> <out/ARM_dataset> <runs>

Isolated per arm: its own warehouse, output dir and fixed GSI_TODAY, so two
arms fed the same env.sh see byte-identical inputs. Each run is pickled
(every frame, every extras frame, counts, scalar extras, every Excel sheet,
and one HTML export) for tools/ab/ab_compare.py.
"""
import json, os, pickle, sys, time, logging
pkg, envfile, out, runs = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
os.makedirs(out, exist_ok=True)
for line in open(envfile, encoding="utf-8"):
    if line.startswith("export "):
        k, v = line[7:].strip().split("=", 1)
        os.environ[k] = v.strip("'\"")
os.environ["GSI_TODAY"] = "2026-08-31"
os.environ["GSI_DWH_PATH"] = os.path.join(out, "wh.sqlite")
os.environ["GSI_OUTPUT"] = os.path.join(out, "output")
os.environ["GSI_DATA_ROOT"] = out
sys.path.insert(0, pkg)
os.chdir(pkg)
logging.disable(logging.WARNING)
import pandas as pd
from gsi.pipeline import Pipeline
from gsi.factsheet import VERSION
res_meta = []
for r in range(runs):
    t = time.perf_counter()
    try:
        res = Pipeline().run(build_report=True)
        err = ""
    except Exception:                # a blocked gate still leaves diagnostics
        import traceback
        err = traceback.format_exc()
        res = None
    wall = time.perf_counter() - t
    res_meta.append({"run": r, "wall_s": round(wall, 2), "error": err[-3000:]})
    if res is None:
        continue
    frames = {n: getattr(res, n) for n in ("df", "main", "to_resolve", "excluded", "audit", "mogh_lines")}
    frames.update({"extras/" + k: v for k, v in res.extras.items() if isinstance(v, pd.DataFrame)})
    other = {k: v for k, v in res.extras.items() if not isinstance(v, pd.DataFrame)}
    xls = {}
    if res.dashboard_path and os.path.exists(res.dashboard_path):
        xls = pd.read_excel(res.dashboard_path, sheet_name=None, header=None)
    html = ""
    try:
        from gsi.studio_core.html_export import build_dynamic_html
        html = build_dynamic_html(res.main, "2026-08-31", title="AB")
    except Exception as ex:
        html = "HTML_ERROR " + repr(ex)
    with open(os.path.join(out, f"run{r}.pkl"), "wb") as f:
        pickle.dump({"version": VERSION, "frames": frames, "counts": res.counts,
                     "extras_other": json.loads(json.dumps(other, default=str, ensure_ascii=False)),
                     "xls": xls, "html": html}, f)
json.dump(res_meta, open(os.path.join(out, "meta.json"), "w"), ensure_ascii=False, indent=1)
print(VERSION, json.dumps(res_meta, ensure_ascii=False)[:600])
