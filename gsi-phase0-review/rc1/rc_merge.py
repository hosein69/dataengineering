# -*- coding: utf-8 -*-
"""RC re-run of OP-01 against 29.7.7 RC1."""
import sys, json, os
import numpy as np, pandas as pd
sys.path.insert(0, os.environ["PKG"])
from gsi.dataio.merge import safe_merge, dedupe_on_key, RowExplosionError
res = {}
def matched(out, col):
    return int(out[col].notna().sum()) if col in out.columns else 0

L = pd.DataFrame({"A": ["", "O1"], "B": ["", "B1"], "L": ["l0", "l1"]})
R = pd.DataFrame({"A": [""], "B": [""], "RVAL": ["LEAKED"]})
res["blank_composite_matched"] = matched(safe_merge(L, R, ["A", "B"], "blank_composite"), "RVAL")

L2 = pd.DataFrame({"K": pd.Series([np.nan, "K1"], dtype=object), "L": ["l0", "l1"]})
R2 = pd.DataFrame({"K": pd.Series([np.nan, "Z9"], dtype=object), "RVAL": ["NAN_LEAK", "ok"]})
res["nan_single_key_matched"] = matched(safe_merge(L2, R2, "K", "nan_key"), "RVAL")

L3 = pd.DataFrame({"A": ["A|B"], "B": [""], "L": ["left"]})
R3 = pd.DataFrame({"A": ["A"], "B": ["B|"], "RVAL": ["COLLIDED"]})
res["delimiter_collision_matched"] = matched(safe_merge(L3, R3, ["A", "B"], "delimiter"), "RVAL")

# partial composite key: one component present, one blank
L4 = pd.DataFrame({"A": ["O1"], "B": [""], "L": ["left"]})
R4 = pd.DataFrame({"A": ["O1"], "B": [""], "RVAL": ["PARTIAL"]})
res["partial_composite_matched"] = matched(safe_merge(L4, R4, ["A", "B"], "partial"), "RVAL")

L5 = pd.DataFrame({"KEY_BL": ["BL1"], "L": ["order"]})
R5 = pd.DataFrame({"KEY_BL": ["BL1"] * 3, "LC_NO": ["LC-1", "LC-2", "LC-3"]})
out5 = safe_merge(L5, R5, "KEY_BL", "multi_lc")
res["many_to_one_rhs_values_kept"] = sorted(set(out5["LC_NO"].dropna())) if "LC_NO" in out5 else []
raised = False
try: safe_merge(L5, R5, "KEY_BL", "explosion_probe", strict=True)
except RowExplosionError: raised = True
res["row_explosion_raised_on_duplicate_rhs"] = raised
print(json.dumps(res, ensure_ascii=False, indent=1))
