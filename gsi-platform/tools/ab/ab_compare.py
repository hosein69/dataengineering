"""Compare arm A vs arm B cell by cell; print every difference, classified.

    python tools/ab/ab_compare.py <out> <dataset> <runs>   # reads <out>/A_<dataset>, <out>/B_<dataset>

Additions a newer version is expected to make are listed at the top
(EXPECTED_*) and not reported; everything else is. Excel diffs that are only
row/column shifts are resolved with xls_align.py.
"""
import json, pickle, sys, os, re, difflib
import pandas as pd
sys.path.insert(0, os.environ.get("GSI_AB_UNPICKLE_PKG", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
base = sys.argv[1]; ds = sys.argv[2]; runs = int(sys.argv[3]) if len(sys.argv) > 3 else 4
EXPECTED_NEW_FRAMES = {"extras/anomaly_inquiries", "extras/heal_applied", "extras/heal_stale"}
EXPECTED_NEW_COLS = {"HEALED_FIELDS"}
EXPECTED_NEW_EXTRAS = {"anomaly_summary", "anomaly_headline"}
EXPECTED_NEW_TRUST = {"observations", "anomalies", "anomaly_counts"}
VOLATILE = re.compile(r"(run_id|_at$|^at$|time|duration|elapsed|_ms$|_s$|seconds|timestamp|created|started|finished|path|dashboard)", re.I)
STAMP = re.compile(r"29\.1[45]\.[01]|\d{4}-\d\d-\d\d[ T]\d\d:\d\d(:\d\d(\.\d+)?)?|\d\d:\d\d:\d\d")


def norm(v):
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def cmp_frame(name, a, b, out):
    if a.shape[0] != b.shape[0]:
        out.append(f"  ROWS {name}: A={a.shape[0]} B={b.shape[0]}")
    ca, cb = list(a.columns), list(b.columns)
    only_a = [c for c in ca if c not in cb]
    only_b = [c for c in cb if c not in ca and c not in EXPECTED_NEW_COLS]
    if only_a: out.append(f"  COLS only in A {name}: {only_a[:10]}")
    if only_b: out.append(f"  COLS only in B {name}: {only_b[:10]}")
    common = [c for c in ca if c in cb]
    if [c for c in ca if c in common] != [c for c in cb if c in common]:
        out.append(f"  COL ORDER differs {name}")
    n = min(len(a), len(b))
    for c in common:
        if VOLATILE.search(str(c)):
            continue
        va = [norm(x) for x in a[c].iloc[:n].tolist()]
        vb = [norm(x) for x in b[c].iloc[:n].tolist()]
        bad = [i for i in range(n) if va[i] != vb[i] and STAMP.sub("", str(va[i])) != STAMP.sub("", str(vb[i]))]
        if bad:
            i = bad[0]
            out.append(f"  CELLS {name}[{c}]: {len(bad)} differ; e.g. row {i}: A={str(va[i])[:120]!r} B={str(vb[i])[:120]!r}")


def cmp_dict(prefix, a, b, out, skip=()):
    for k in sorted(set(a) | set(b), key=str):
        if k in skip or VOLATILE.search(str(k)):
            continue
        if k not in a: out.append(f"  EXTRA only in B {prefix}{k}"); continue
        if k not in b: out.append(f"  EXTRA only in A {prefix}{k}"); continue
        if isinstance(a[k], dict) and isinstance(b[k], dict):
            cmp_dict(prefix + str(k) + ".", a[k], b[k], out,
                     skip=EXPECTED_NEW_TRUST if k == "trust_summary" else ())
        else:
            ja = STAMP.sub("", json.dumps(a[k], sort_keys=True, default=str, ensure_ascii=False))
            jb = STAMP.sub("", json.dumps(b[k], sort_keys=True, default=str, ensure_ascii=False))
            if ja != jb:
                out.append(f"  VALUE {prefix}{k}: A={ja[:200]} | B={jb[:200]}")


for r in range(runs):
    pa, pb = f"{base}/A_{ds}/run{r}.pkl", f"{base}/B_{ds}/run{r}.pkl"
    if not (os.path.exists(pa) and os.path.exists(pb)):
        print(f"[{ds} run{r}] missing pickle A={os.path.exists(pa)} B={os.path.exists(pb)}"); continue
    A = pickle.load(open(pa, "rb")); B = pickle.load(open(pb, "rb"))
    out = []
    fa, fb = A["frames"], B["frames"]
    for n in sorted(set(fa) | set(fb)):
        if n not in fb: out.append(f"  FRAME only in A: {n}"); continue
        if n not in fa:
            if n not in EXPECTED_NEW_FRAMES: out.append(f"  FRAME only in B: {n}")
            continue
        cmp_frame(n, fa[n], fb[n], out)
    cmp_dict("counts.", A["counts"], B["counts"], out)
    cmp_dict("extras.", A["extras_other"], B["extras_other"], out, skip=EXPECTED_NEW_EXTRAS)
    xa, xb = A["xls"], B["xls"]
    if set(xa) != set(xb): out.append(f"  XLS sheets A-B={set(xa)-set(xb)} B-A={set(xb)-set(xa)}")
    for s in sorted(set(xa) & set(xb)):
        a, b = xa[s].astype(object), xb[s].astype(object)
        if a.shape != b.shape:
            out.append(f"  XLS shape {s}: A={a.shape} B={b.shape}")
        n0, n1 = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
        av, bv = a.values, b.values
        diffs = []
        for i in range(n0):
            for j in range(n1):
                va, vb = norm(av[i, j]), norm(bv[i, j])
                if va != vb and STAMP.sub("", str(va)) != STAMP.sub("", str(vb)):
                    diffs.append((i, j, va, vb))
        if diffs:
            i, j, va, vb = diffs[0]
            out.append(f"  XLS cells {s}: {len(diffs)} differ; e.g. ({i},{j}) A={str(va)[:100]!r} B={str(vb)[:100]!r}")
    ha, hb = STAMP.sub("", A["html"]), STAMP.sub("", B["html"])
    if ha != hb:
        la, lb = ha.replace(">", ">\n").splitlines(), hb.replace(">", ">\n").splitlines()
        d = [x for x in difflib.unified_diff(la, lb, lineterm="", n=0)
             if x[:1] in "+-" and x[:3] not in ("+++", "---")]
        out.append(f"  HTML differs: A={len(ha)} B={len(hb)} changed-lines={len(d)} e.g. "
                   + " || ".join(x[:140] for x in d[:4]))
    print(f"[{ds} run{r}] " + ("IDENTICAL (modulo expected additions)" if not out else f"{len(out)} finding(s)"))
    for line in out[:60]:
        print(line)
