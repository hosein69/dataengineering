#!/usr/bin/env python3
"""Spot, unleveraged, short horizon — which is a different question again.

Without leverage the constraints that shaped every earlier answer disappear:
no liquidation, no stop distance, no margin fee. What replaces them is a
benchmark that only exists for a Toman-based holder — tether itself. USDTIRT
returned 40% over the window at almost no volatility, so a spot pick has to
beat simply holding tether before it has done anything at all.

The ranking question is settled by the data rather than assumed. This market
mean-reverts on 90% of symbols, so buying what just rose may be exactly wrong.
Every bar is bucketed by its trailing return and scored by what followed, which
says empirically whether strength or weakness pays at this horizon. The current
names are then ranked by whichever signal the test actually supports.
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
HORIZONS = {"2d": 12, "7d": 42, "14d": 84}


def main() -> None:
    snap = newest_snapshot()
    close = {}
    for f in sorted(snap.glob("*.csv.gz")):
        close[f.name.replace(".csv.gz", "")] = pd.read_csv(
            f, index_col=0, parse_dates=True)["close"]
    P = pd.DataFrame(close).sort_index().ffill()
    P = P.loc[:, P.notna().sum() > len(P) * 0.9]
    rial = P[RIAL]
    U = P.div(rial, axis=0).drop(columns=[RIAL])      # what is really the coin
    I = P.drop(columns=[RIAL])                        # what a Toman holder banks

    print(f"snapshot {snap.name}; {I.shape[1]} symbols; "
          f"tether itself returned {float(rial.iloc[-1]/rial.iloc[0]-1)*100:+.1f}% "
          f"over the window at {float(rial.pct_change().std(ddof=1)*math.sqrt(BPY))*100:.0f}% vol\n")

    # ---- does strength or weakness pay at a short horizon? ----
    print("## does buying strength pay here, or buying weakness (USDT)\n")
    print("| horizon | decile of trailing return | mean forward return | n |")
    print("|---|---|---:|---:|")
    verdicts = {}
    for name, h in HORIZONS.items():
        # Forward return is simply where price is h bars later against today.
        # Chaining shift/pct_change/shift instead made the "forward" window
        # overlap the trailing one, so the test was partly correlating a return
        # with itself and momentum was guaranteed before any data was read.
        past = U / U.shift(h) - 1
        fwd = U.shift(-h) / U - 1
        a = past.stack(); b = fwd.stack()
        j = pd.concat([a, b], axis=1).dropna()
        j.columns = ["past", "fwd"]
        if len(j) < 500:
            continue
        j["d"] = pd.qcut(j["past"], 10, labels=False, duplicates="drop")
        g = j.groupby("d")["fwd"].agg(["mean", "size"])
        lo, hi = g.iloc[0], g.iloc[-1]
        verdicts[name] = float(hi["mean"] - lo["mean"])
        print(f"| {name} | **weakest 10%** | {lo['mean']*100:+.2f}% | {int(lo['size'])} |")
        print(f"| {name} | **strongest 10%** | {hi['mean']*100:+.2f}% | {int(hi['size'])} |")
        edge = "momentum" if verdicts[name] > 0 else "reversal"
        print(f"| {name} | *spread strong−weak* | *{verdicts[name]*100:+.2f}%* "
              f"| **{edge} wins** |")

    best_h = min(verdicts, key=lambda k: verdicts[k])     # most negative = reversal
    rev = verdicts[best_h] < 0
    h = HORIZONS[best_h]
    print(f"\n-> strongest effect at {best_h}: "
          f"{'REVERSAL — buy what fell' if rev else 'MOMENTUM — buy what rose'}\n")

    # ---- rank today's names by whatever the test supports ----
    trail = U.pct_change(h).iloc[-1].dropna()
    ranked = trail.sort_values(ascending=rev)
    vol = U.pct_change().std(ddof=1) * math.sqrt(BPY)
    eq = U / U.iloc[0]
    dd = (eq / eq.cummax() - 1).min()
    irt_ret = I.iloc[-1] / I.iloc[0] - 1
    usd_ret = U.iloc[-1] / U.iloc[0] - 1
    rial_leg = float(rial.iloc[-1] / rial.iloc[0] - 1)

    print(f"## top 8 for the next ~{best_h}, by the effect that actually pays\n")
    print(f"| # | symbol | trailing {best_h} (USDT) | 180d USDT | 180d IRT "
          "| vol | worst DD | beat tether? |")
    print("|---:|---|---:|---:|---:|---:|---:|:--:|")
    for i, (s, v) in enumerate(list(ranked.items())[:8], 1):
        beat = "yes" if irt_ret[s] > rial_leg else "**no**"
        print(f"| {i} | **{s}** | {v*100:+.1f}% | {usd_ret[s]*100:+.1f}% "
              f"| {irt_ret[s]*100:+.1f}% | {vol[s]*100:.0f}% | {dd[s]*100:.0f}% "
              f"| {beat} |")

    print(f"\n## for contrast, the other end of the same ranking\n")
    print(f"| symbol | trailing {best_h} (USDT) | 180d IRT | beat tether? |")
    print("|---|---:|---:|:--:|")
    for s, v in list(ranked.items())[-5:]:
        beat = "yes" if irt_ret[s] > rial_leg else "**no**"
        print(f"| {s} | {v*100:+.1f}% | {irt_ret[s]*100:+.1f}% | {beat} |")

    n_beat = int((irt_ret > rial_leg).sum())
    print(f"\n-> over the whole window {n_beat}/{len(irt_ret)} symbols beat "
          f"simply holding tether ({rial_leg*100:+.1f}%)")


if __name__ == "__main__":
    main()
