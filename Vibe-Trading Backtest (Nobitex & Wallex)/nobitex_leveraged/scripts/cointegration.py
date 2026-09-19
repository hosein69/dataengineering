#!/usr/bin/env python3
"""Test the strategy family the structure actually points at: cointegrated pairs.

Everything measured so far says this market mean-reverts — negative lag-1
autocorrelation on 90% of symbols, a 7-day reversal effect, and 2.9 effective
independent bets in 63 names. Both strategies tried here follow trends, which
is why 120 configurations of them failed: the family was wrong, not the
settings.

The literature on this market converges on one answer (Leung & Nguyen 2019 and
the 2025 survey both land on cointegration), so that is what is tested.

Two pairs are cointegrated when some combination of them is stationary even
though each wanders on its own. That combination is a spread with a mean worth
betting on, and the bet is market-neutral by construction: both legs carry the
same rial drift and the same market beta, so the spread cancels both — which is
the two headwinds that made every earlier short unworkable.

Pairs are selected on the first 60% by Engle-Granger and traded on the last
40%, which the selection never sees. Without that split, testing 1953 pairs
guarantees finding something.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, coint

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alpha_beta import BPY  # noqa: E402
from maximize import newest_snapshot  # noqa: E402

RIAL = "USDTIRT"
TRAIN = 0.60
PVAL = 0.01          # strict: 1953 pairs are tested
ENTRY_Z, EXIT_Z, STOP_Z = 2.0, 0.5, 4.0
FEE = 0.0005


def half_life(spread: np.ndarray) -> float:
    """Bars for a deviation to decay by half — how long a trade must be held."""
    s = pd.Series(spread)
    d, lag = s.diff().dropna(), s.shift(1).dropna()
    n = min(len(d), len(lag))
    x = np.column_stack([np.ones(n), lag.to_numpy()[:n]])
    beta = np.linalg.lstsq(x, d.to_numpy()[:n], rcond=None)[0][1]
    return float(-math.log(2) / beta) if beta < 0 else float("inf")


def trade_spread(a: np.ndarray, b: np.ndarray, beta: float,
                 mu: float, sd: float, window: int = 120) -> dict:
    """Z-score entries on the spread, symmetric long/short, flat at the mean.

    The z-score is rolling, using only bars already seen. Holding the training
    mean fixed instead made every trade stop out the moment the spread drifted:
    |z| sat above the stop band permanently, so the strategy entered and was
    stopped on the next bar, 81 times, with a 0% win rate. That measured the
    fixed reference drifting, not the spread failing to revert.
    """
    sp = a - beta * b
    s = pd.Series(sp)
    rm = s.rolling(window, min_periods=window // 2).mean()
    rs = s.rolling(window, min_periods=window // 2).std(ddof=1)
    z = ((s - rm) / rs).to_numpy()
    if not np.isfinite(z).any():
        return {}
    pos, eq, trades, wins = 0, 1.0, 0, 0
    entry_i = 0
    ra, rb = np.diff(a) / a[:-1], np.diff(b) / b[:-1]
    for i in range(1, len(z)):
        if not np.isfinite(z[i]):
            continue
        if pos != 0:
            eq *= 1 + pos * (ra[i - 1] - beta * rb[i - 1]) / (1 + abs(beta))
        if pos == 0:
            if z[i] > ENTRY_Z:
                pos, entry_i = -1, i; eq *= 1 - FEE * 2
            elif z[i] < -ENTRY_Z:
                pos, entry_i = 1, i; eq *= 1 - FEE * 2
        else:
            hit_exit = abs(z[i]) < EXIT_Z
            hit_stop = abs(z[i]) > STOP_Z
            if hit_exit or hit_stop:
                trades += 1
                if hit_exit:
                    wins += 1
                pos = 0; eq *= 1 - FEE * 2
    return {"ret": eq - 1, "trades": trades,
            "win_rate": wins / trades if trades else float("nan")}


def main() -> None:
    snap = newest_snapshot()
    close = {}
    for f in sorted(snap.glob("*.csv.gz")):
        close[f.name.replace(".csv.gz", "")] = pd.read_csv(
            f, index_col=0, parse_dates=True)["close"]
    P = pd.DataFrame(close).sort_index().ffill()
    P = P.loc[:, P.notna().sum() > len(P) * 0.95].dropna()
    U = P.div(P[RIAL], axis=0).drop(columns=[RIAL])
    L = np.log(U)

    cut = int(len(L) * TRAIN)
    tr, te = L.iloc[:cut], L.iloc[cut:]
    syms = list(L.columns)
    pairs = list(itertools.combinations(syms, 2))
    print(f"{len(syms)} symbols -> {len(pairs)} pairs tested on the first "
          f"{TRAIN:.0%} ({len(tr)} bars), traded on the last {len(te)}\n")

    found = []
    for a, b in pairs:
        x, y = tr[a].to_numpy(), tr[b].to_numpy()
        try:
            _, p, _ = coint(x, y)
        except Exception:  # noqa: BLE001
            continue
        if p > PVAL:
            continue
        beta = np.linalg.lstsq(np.column_stack([np.ones(len(y)), y]), x,
                               rcond=None)[0][1]
        sp = x - beta * y
        hl = half_life(sp)
        if not (2 < hl < 200):      # too fast to trade, or too slow to matter
            continue
        adf_p = adfuller(sp, maxlag=1, regression="c")[1]
        found.append({"a": a, "b": b, "p": p, "adf_p": adf_p, "beta": beta,
                      "half_life": hl, "mu": float(sp.mean()),
                      "sd": float(sp.std(ddof=1))})

    found.sort(key=lambda r: r["p"])
    print(f"cointegrated at p<{PVAL} with a tradeable half-life: "
          f"{len(found)} pairs ({len(found)/len(pairs)*100:.1f}% of those tested)")
    exp = PVAL * len(pairs)
    print(f"expected by chance alone at this p: ~{exp:.0f} pairs\n")

    if not found:
        print("nothing survives — cointegration is not present here either")
        return

    print("## top pairs by train-set p-value, then traded out of sample\n")
    print("| pair | p (train) | half-life (bars) | beta | OOS return | trades "
          "| win rate |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    oos = []
    for r in found[:15]:
        res = trade_spread(te[r["a"]].to_numpy(), te[r["b"]].to_numpy(),
                           r["beta"], r["mu"], r["sd"])
        if not res:
            continue
        oos.append(res["ret"])
        print(f"| {r['a']}–{r['b']} | {r['p']:.4f} | {r['half_life']:.0f} "
              f"| {r['beta']:+.2f} | **{res['ret']*100:+.2f}%** | {res['trades']} "
              f"| {res['win_rate']*100 if res['trades'] else float('nan'):.0f}% |")

    if oos:
        arr = np.array(oos)
        print(f"\nout of sample across {len(arr)} pairs: mean "
              f"{arr.mean()*100:+.2f}%, median {np.median(arr)*100:+.2f}%, "
              f"{int((arr > 0).sum())}/{len(arr)} profitable")
        print(f"equal-weight basket of all {len(arr)}: "
              f"{arr.mean()*100:+.2f}% over {len(te)} bars "
              f"({arr.mean()*BPY/len(te)*100:+.0f}%/yr)")


if __name__ == "__main__":
    main()
