# -*- coding: utf-8 -*-
"""RC03 diagnostic: concurrent writer processes against one non-WAL warehouse."""
import sys, os, json, multiprocessing as mp
def worker(n):
    sys.path.insert(0, os.environ["PKG"])
    import pandas as pd
    from gsi.warehouse.store import Warehouse
    from gsi.warehouse.business_dwh import build as build_dwh
    wh = Warehouse()
    for i in range(6):
        df = pd.DataFrame([{"KEY_ORDER": f"O{n}-{i}-{j}", "KEY_MATERIAL": f"M{j}"} for j in range(40)])
        try:
            with wh.run({"w": n, "i": i}) as rid:
                wh.frame(df, "mart", f"w{n}_{i}")
                build_dwh(wh, {"moghavemat": {"lines": df}}, rid)
        except Exception as ex:
            return f"worker{n}: {type(ex).__name__}: {str(ex)[:120]}"
    return f"worker{n}: ok"

if __name__ == "__main__":
    mp.set_start_method("spawn")
    with mp.Pool(4) as pool:
        results = pool.map(worker, range(4))
    sys.path.insert(0, os.environ["PKG"])
    import sqlite3
    c = sqlite3.connect(os.environ["GSI_DWH_PATH"])
    integ = c.execute("PRAGMA integrity_check").fetchall()
    fk = c.execute("PRAGMA foreign_key_check").fetchall()
    jm = c.execute("PRAGMA journal_mode").fetchone()
    print(json.dumps({"workers": results, "journal_mode": jm[0],
                      "integrity_check": integ[:10], "foreign_key_violations": len(fk)},
                     ensure_ascii=False, indent=1))
