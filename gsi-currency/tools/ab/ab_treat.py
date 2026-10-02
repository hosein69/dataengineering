"""Treatment arm: injected anomalies, approvals before run 3 (if the package can), source loss before run 4.

    python tools/ab/ab_treat.py <extracted_pkg_dir> <dataset_dir> <out/ARM_treat>

Copies the dataset per arm, runs five times: runs 0–2 build history; before
run 3 every proposed repair is approved (a package without the feature just
runs); before run 4 half of «BLs Tracking» is removed to simulate a capture
failure. Compare two arms with ab_compare.py <out> treat 5.
"""
import json, os, pickle, shutil, sys, time, logging, glob
pkg, src_data, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
data = os.path.join(out, "data")
shutil.rmtree(data, ignore_errors=True); shutil.copytree(src_data, data)
env = {}
for line in open(os.path.join(src_data, "env.sh"), encoding="utf-8"):
    k, v = line[7:].strip().split("=", 1)
    os.environ[k] = v.strip("'\"").replace(src_data, data)
os.environ.update({"GSI_TODAY": "2026-08-31", "GSI_DWH_PATH": os.path.join(out, "wh.sqlite"),
                   "GSI_OUTPUT": os.path.join(out, "output"), "GSI_DATA_ROOT": out})
sys.path.insert(0, pkg); os.chdir(pkg); logging.disable(logging.WARNING)
import pandas as pd
from gsi.pipeline import Pipeline
from gsi.factsheet import VERSION
meta = []
for r in range(5):
    note = ""
    if r == 3:
        try:
            from gsi.trust import inquiry as Q
            from gsi.trust.anomaly import Anomaly
            from gsi.trust.trend import load_payloads
            # 29.15.1+: the published run's own frame; 29.15.0 kept a copy in the snapshot
            anomalies = (Q._latest_anomalies() if hasattr(Q, "_latest_anomalies") else []) or \
                [Anomaly.from_dict(a) for a in load_payloads(limit=1)[-1].get("anomalies", [])]
            reg = Q.InquiryRegister()
            for a in anomalies:
                if a.repair:
                    reg.record(Q.make_decision(a, Q.APPROVE, "A/B: تأیید آزمایشی ترمیم پیشنهادی", "ab-tester",
                                               standing=a.repair["kind"] == "ALIAS"))
                    note += f"approved {a.kind}:{a.field}:{a.key}; "
        except ImportError:
            note = "no inquiry feature"
    if r == 4:
        p = glob.glob(os.path.join(data, "**", "BLs Tracking.xlsx"), recursive=True)[0]
        g = pd.read_excel(p, sheet_name=None, header=None, dtype=object, keep_default_na=False)
        name = list(g)[0]; body = g[name]
        g[name] = body.iloc[: 1 + (len(body) - 1) // 2]
        with pd.ExcelWriter(p) as w:
            for n, x in g.items():
                x.to_excel(w, sheet_name=n, index=False, header=False)
        note += f"dropped half of {name}; "
    t = time.perf_counter()
    res = Pipeline().run(build_report=True)
    meta.append({"run": r, "wall_s": round(time.perf_counter() - t, 2), "note": note})
    frames = {n: getattr(res, n) for n in ("df", "main", "to_resolve", "excluded", "audit", "mogh_lines")}
    frames.update({"extras/" + k: v for k, v in res.extras.items() if isinstance(v, pd.DataFrame)})
    other = {k: v for k, v in res.extras.items() if not isinstance(v, pd.DataFrame)}
    xls = pd.read_excel(res.dashboard_path, sheet_name=None, header=None) if res.dashboard_path else {}
    from gsi.studio_core.html_export import build_dynamic_html
    html = build_dynamic_html(res.main, "2026-08-31", title="AB")
    pickle.dump({"version": VERSION, "frames": frames, "counts": res.counts,
                 "extras_other": json.loads(json.dumps(other, default=str, ensure_ascii=False)),
                 "xls": xls, "html": html}, open(os.path.join(out, f"run{r}.pkl"), "wb"))
json.dump(meta, open(os.path.join(out, "meta.json"), "w"), ensure_ascii=False, indent=1)
print(VERSION, json.dumps(meta, ensure_ascii=False))
