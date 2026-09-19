#!/usr/bin/env python3
"""What happens to a coin after Nobitex lists it.

TAO has 26 days of local history, which is far too little to judge on its own
but is exactly enough to place against a coin further along the same path.
BANKIRT was listed about 68 days ago, so its days 1-26 are directly comparable
to all of TAO's, and its days 27-68 are the part of TAO's future that can
actually be observed somewhere.

Everything is priced in USDT. In rial both would show a gain that is mostly the
currency, and the question here is what the asset did.

The market over each coin's own window is the control: a listing that rose
while everything rose has shown nothing, and the comparison has to be made over
matching calendar bars rather than matching returns.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alpha_beta import BPY  # noqa: E402
from maximize import newest_snapshot  # noqa: E402

RIAL = "USDTIRT"
NEW = ["TAOIRT", "BANKIRT"]
BARS_PER_DAY = 6


def main() -> None:
    snap = newest_snapshot()
    raw = {f.name.replace(".csv.gz", ""): pd.read_csv(f, index_col=0, parse_dates=True)
           for f in sorted(snap.glob("*.csv.gz"))}
    rial = raw[RIAL]["close"]
    est = {k: v for k, v in raw.items() if k not in NEW}
    P = pd.DataFrame({k: v["close"] for k, v in est.items()}).sort_index().ffill()
    U = P.div(P[RIAL], axis=0).drop(columns=[RIAL])
    mkt_r = U.pct_change().mean(axis=1)

    print("## when each was listed, and what it did since\n")
    print("| symbol | first bar | days live | USDT return | vs market (same bars) "
          "| vol | maxDD |")
    print("|---|---|---:|---:|---:|---:|---:|")
    series = {}
    for s in NEW:
        d = raw[s]
        u = (d["close"] / rial.reindex(d.index).ffill()).dropna()
        series[s] = (u, d)
        days = (u.index[-1] - u.index[0]).total_seconds() / 86400
        ret = float(u.iloc[-1] / u.iloc[0] - 1)
        m = float((1 + mkt_r.reindex(u.index).dropna()).prod() - 1)
        r = u.pct_change().dropna()
        eq = u / u.iloc[0]
        print(f"| **{s}** | {u.index[0]:%Y-%m-%d} | {days:.0f} | {ret*100:+.1f}% "
              f"| **{(ret-m)*100:+.1f} pts** "
              f"| {float(r.std(ddof=1)*math.sqrt(BPY))*100:.0f}% "
              f"| {float((eq/eq.cummax()-1).min())*100:.1f}% |")

    print("\n\n## the same elapsed days since listing, side by side\n")
    print("| days since listing | TAO (USDT) | BANK (USDT) | market over TAO's bars "
          "| market over BANK's bars |")
    print("|---:|---:|---:|---:|---:|")
    for dd in (1, 3, 7, 14, 21, 26, 40, 60, 68):
        row = [f"| {dd} "]
        cells = {}
        for s in NEW:
            u, _ = series[s]
            n = dd * BARS_PER_DAY
            if n >= len(u):
                cells[s] = None
                continue
            cells[s] = float(u.iloc[n] / u.iloc[0] - 1)
        for s in NEW:
            row.append(f"| {cells[s]*100:+.1f}% " if cells[s] is not None else "| — ")
        for s in NEW:
            u, _ = series[s]
            n = min(dd * BARS_PER_DAY, len(u) - 1)
            seg = mkt_r.reindex(u.index[:n + 1]).dropna()
            mv = float((1 + seg).prod() - 1) if len(seg) else float("nan")
            row.append(f"| {mv*100:+.1f}% " if cells[s] is not None else "| — ")
        print("".join(row) + "|")

    print("\n\n## the shape of the first weeks\n")
    for s in NEW:
        u, d = series[s]
        peak_i = int(np.argmax(u.to_numpy()))
        trough_i = int(np.argmin(u.to_numpy()))
        v = d["volume"].astype(float).reindex(u.index)
        first_wk = v.iloc[:7 * BARS_PER_DAY].mean()
        later = v.iloc[7 * BARS_PER_DAY:].mean()
        r = u.pct_change()
        j = pd.concat([r, v], axis=1).dropna(); j.columns = ["r", "v"]
        uv = j.loc[j.r > 0, "v"].mean() / j.loc[j.r < 0, "v"].mean()
        print(f"**{s}**")
        print(f"  high on day {peak_i/BARS_PER_DAY:.1f} at "
              f"{float(u.iloc[peak_i]/u.iloc[0]-1)*100:+.1f}% from listing")
        print(f"  low  on day {trough_i/BARS_PER_DAY:.1f} at "
              f"{float(u.iloc[trough_i]/u.iloc[0]-1)*100:+.1f}%")
        print(f"  now {float(u.iloc[-1]/u.iloc[0]-1)*100:+.1f}%, "
              f"{float(u.iloc[-1]/u.max()-1)*100:+.1f}% from its high")
        print(f"  volume: first week {first_wk:,.0f} -> since {later:,.0f} "
              f"({later/first_wk:.2f}x)")
        print(f"  up-volume / down-volume: {uv:.2f}\n")


if __name__ == "__main__":
    main()
