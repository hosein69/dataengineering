"""Scale tests/make_synthetic.py data by cloning key-bearing rows with consistently shifted keys.

    python tools/ab/make_scaled.py <out_dir> <clones>     # 0 = the plain synthetic set

Every clone shifts every business key (BL, order, registration, part) and every
6+-digit number by the same deterministic amount across all workbooks, so joins
stay intact and amounts vary. Writes <out_dir>/env.sh for the A/B runners.
"""
import os, re, sys, glob
_PKG = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_PKG, "tests"))
sys.path.insert(0, _PKG)
import pandas as pd
import make_synthetic as M

root, clones = sys.argv[1], int(sys.argv[2])
dirs = M.build(root)
explicit = sorted(set(M.BLS + M.ORDERS + M.REGS + M.PARTS), key=len, reverse=True)
pat = re.compile("|".join(re.escape(t) for t in explicit) + r"|\d{6,}")
tok_row = re.compile("|".join(re.escape(t) for t in explicit))

def shift_digits(run, c):
    n = len(run)
    return f"{(int(run) + c * 1000003) % 10**n:0{n}d}"

def map_cell(v, c):
    if not isinstance(v, str):
        return v
    def rep(m):
        t = m.group(0)
        if t in explicit:
            runs = list(re.finditer(r"\d+", t))
            last = runs[-1]
            return t[:last.start()] + shift_digits(last.group(0), c) + t[last.end():]
        return shift_digits(t, c)
    return pat.sub(rep, v)

for path in glob.glob(os.path.join(root, "**", "*.xlsx"), recursive=True):
    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object, keep_default_na=False)
    out = {}
    for name, g in sheets.items():
        g = g.astype(object).map(lambda v: v if not isinstance(v, float) or v == v else "")
        hits = [i for i in range(len(g)) if any(isinstance(v, str) and tok_row.search(v) for v in g.iloc[i])]
        if not hits or clones <= 0:
            out[name] = g
            continue
        head, body = g.iloc[:hits[0]], g.iloc[hits[0]:]
        parts = [head, body] + [body.map(lambda v, c=c: map_cell(v, c)) for c in range(1, clones + 1)]
        out[name] = pd.concat(parts, ignore_index=True)
    with pd.ExcelWriter(path) as w:
        for name, g in out.items():
            g.to_excel(w, sheet_name=name, index=False, header=False)
env = {"GSI_FOREIGN": dirs["foreign"], "GSI_BLS": dirs["bls"], "GSI_CLEARANCE": dirs["clearance"],
       "GSI_HR": dirs["hr"], "GSI_ESMAEILI": dirs["esmaeili"], "GSI_GS_COMBINE": dirs["gs_combine"],
       "GSI_MOHAMADI": dirs["mohamadi"], "GSI_LOGS": dirs["logs"]}
with open(os.path.join(root, "env.sh"), "w", encoding="utf-8") as f:
    for k, v in env.items():
        f.write(f"export {k}='{v}'\n")
print("ok", root)
