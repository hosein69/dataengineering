import pickle, sys, os, re, difflib
sys.path.insert(0, os.environ.get("GSI_AB_UNPICKLE_PKG", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import pandas as pd
base, ds, r = sys.argv[1], sys.argv[2], sys.argv[3]
A = pickle.load(open(f"{base}/A_{ds}/run{r}.pkl", "rb"))["xls"]; B = pickle.load(open(f"{base}/B_{ds}/run{r}.pkl", "rb"))["xls"]
STAMP = re.compile(r"29\.1[45]\.[01]|\d{4}-\d\d-\d\d[ T]\d\d:\d\d(:\d\d(\.\d+)?)?|\d\d:\d\d:\d\d")
def rows(df, drop_cols=()):
    out = []
    for i in range(len(df)):
        vals = [df.iat[i, j] for j in range(df.shape[1]) if j not in drop_cols]
        out.append(tuple("" if pd.isna(v) else STAMP.sub("", str(v)) for v in vals))
    return out
for s in sorted(set(A) & set(B)):
    a, b = A[s], B[s]
    if a.shape == b.shape and rows(a) == rows(b):
        continue
    drop = ()
    if a.shape[1] != b.shape[1]:   # find the inserted column in B via header row 0..3
        for j in range(b.shape[1]):
            if j >= a.shape[1] or str(b.iat[0, j]) != str(a.iat[0, j]):
                drop = (j,); break
    ra, rb = rows(a), rows(b, drop)
    sm = difflib.SequenceMatcher(None, ra, rb, autojunk=False)
    print(f"== {s}: A{a.shape} B{b.shape} dropB={drop}")
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal": continue
        for k in range(max(i2 - i1, j2 - j1))[:6]:
            ea = ra[i1 + k] if i1 + k < i2 else None
            eb = rb[j1 + k] if j1 + k < j2 else None
            if ea and eb:
                cells = [(x, y) for x, y in zip(ea, eb) if x != y]
                print(f"   {tag} A{i1+k}/B{j1+k}: {cells[:4]}")
            else:
                print(f"   {tag} A:{ea and [c for c in ea if c][:5]} B:{eb and [c for c in eb if c][:5]}")
