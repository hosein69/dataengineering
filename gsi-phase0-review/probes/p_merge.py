# -*- coding: utf-8 -*-
"""OP-01 merge/key probes: blank composite keys, NaN keys, delimiter collision,
   many-to-one silent loss, and reachability of the RowExplosionError guard."""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, '/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/gsi/v29/gsi_2976')
from gsi.dataio.merge import safe_merge, dedupe_on_key, RowExplosionError

res = {}

# 1) blank composite key ("","") -> "|" matches
L = pd.DataFrame({"A": ["", "O1"], "B": ["", "B1"], "L": ["l0", "l1"]})
R = pd.DataFrame({"A": [""], "B": [""], "RVAL": ["LEAKED"]})
out = safe_merge(L, R, ["A", "B"], "blank_composite")
res["blank_composite_matched"] = out["RVAL"].notna().sum().item()

# 2) NaN keys on a SINGLE key merge -> astype(str) == "nan" matches
L2 = pd.DataFrame({"K": pd.Series([np.nan, "K1"], dtype=object), "L": ["l0", "l1"]})
R2 = pd.DataFrame({"K": pd.Series([np.nan, "Z9"], dtype=object), "RVAL": ["NAN_LEAK", "ok"]})
out2 = safe_merge(L2, R2, "K", "nan_key")
res["nan_single_key_matched"] = int(out2["RVAL"].notna().sum())

# 3) delimiter collision: ("A|B","") vs ("A","B|")
L3 = pd.DataFrame({"A": ["A|B"], "B": [""], "L": ["left"]})
R3 = pd.DataFrame({"A": ["A"], "B": ["B|"], "RVAL": ["COLLIDED"]})
out3 = safe_merge(L3, R3, ["A", "B"], "delimiter")
res["delimiter_collision_matched"] = int(out3["RVAL"].notna().sum())

# 4) many-to-one: 3 BL declarations on one BL -> how many survive?
L4 = pd.DataFrame({"KEY_BL": ["BL1"], "L": ["order"]})
R4 = pd.DataFrame({"KEY_BL": ["BL1"] * 3, "LC_NO": ["LC-1", "LC-2", "LC-3"]})
out4 = safe_merge(L4, R4, "KEY_BL", "multi_lc")
res["many_to_one_rhs_rows_in"] = len(R4)
res["many_to_one_rhs_values_kept"] = sorted(set(out4["LC_NO"].dropna()))

# 5) is the RowExplosionError guard reachable at all?
raised = False
try:
    safe_merge(L4, R4, "KEY_BL", "explosion_probe", strict=True)
except RowExplosionError:
    raised = True
res["row_explosion_raised_on_duplicate_rhs"] = raised

# 6) dedupe_on_key keeps blank-component composite but drops fully empty scalar
res["dedupe_drops_empty_scalar"] = len(dedupe_on_key(pd.DataFrame({"K": ["", "x"]}), "K"))
print(json.dumps(res, ensure_ascii=False, indent=1))
