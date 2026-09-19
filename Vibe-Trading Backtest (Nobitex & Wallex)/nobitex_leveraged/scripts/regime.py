#!/usr/bin/env python3
"""A different question: not which coin, but whether to be in the market at all.

Three strategy families have failed here, and all three asked the same thing —
which symbol, which direction, which parameters — while staying in the market
throughout. But only one of the three phases lost money. If that phase can be
recognised while it is happening rather than afterwards, avoiding it matters
more than any symbol choice, and it matters most at leverage, where the losing
phase is what ends the account.

So the state is inferred rather than the signal. A two-state Markov switching
model fits a high-mean and a low-mean regime to market returns and returns a
filtered probability that uses only bars already seen — Bayesian updating, one
bar at a time, with no knowledge of what follows.

Three things have to hold for this to be worth anything, and each is tested
separately: the states must be economically distinct rather than a relabelling
of volatility; the filter must have flagged the falling phase while it was
falling; and it has to beat staying invested out of sample, after the
transaction costs that switching incurs.

USDTIRT is fitted the same way and separately. It is the one series here driven
by local capital flow rather than global crypto, it is tradeable at 5x, and
nothing so far has tested whether it carries structure of its own.
"""
from __future__ import annotations

import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from alpha_beta import BPY  # noqa: E402
from maximize import newest_snapshot  # noqa: E402
from statsmodels.tsa.regime_switching.markov_regression import (  # noqa: E402
    MarkovRegression,
)

RIAL = "USDTIRT"
TRAIN = 0.60
LEV = 5.0
SWITCH_COST = 0.0005 * 2       # in and out


def fit_regimes(r: pd.Series, label: str):
    m = MarkovRegression(r.to_numpy(), k_regimes=2, trend="c",
                         switching_variance=True)
    res = m.fit(disp=False)
    # params starts with the transition probabilities, so slicing the first two
    # returned p00 and p10 and called them regime means — which annualised to
    # +163779%/yr and, worse, decided which regime counted as "high". Select by
    # name instead.
    names = list(res.model.param_names)
    mu = np.array([res.params[names.index(n)] for n in names
                   if n.startswith("const")])
    var = np.array([res.params[names.index(n)] for n in names
                    if "sigma2" in n])
    hi = int(np.argmax(mu))
    fp = np.asarray(res.filtered_marginal_probabilities)
    if fp.shape[0] == 2:          # (regimes, obs) in some versions
        fp = fp.T
    prob_hi = pd.Series(fp[:, hi][-len(r):], index=r.index)
    sig = np.sqrt(var)
    print(f"\n### {label}")
    for k in range(2):
        tag = "HIGH" if k == hi else "LOW "
        print(f"  regime {k} ({tag}): mean {mu[k]*BPY*100:+.0f}%/yr, "
              f"vol {sig[k]*math.sqrt(BPY)*100:.0f}%/yr, "
              f"time in it {float((prob_hi if k==hi else 1-prob_hi).mean())*100:.0f}%")
    p = res.regime_transition[:, :, 0]
    print(f"  persistence: stay in 0 {p[0,0]:.2f}, stay in 1 {p[1,1]:.2f}")
    return prob_hi, res


def main() -> None:
    snap = newest_snapshot()
    close = {}
    for f in sorted(snap.glob("*.csv.gz")):
        close[f.name.replace(".csv.gz", "")] = pd.read_csv(
            f, index_col=0, parse_dates=True)["close"]
    P = pd.DataFrame(close).sort_index().ffill()
    P = P.loc[:, P.notna().sum() > len(P) * 0.9]
    rial = P[RIAL]
    U = P.div(rial, axis=0).drop(columns=[RIAL])
    mkt = U.pct_change().mean(axis=1).dropna()
    rl = rial.pct_change().dropna()

    print(f"snapshot {snap.name}; {len(mkt)} bars\n")
    print("## 1. are the states economically distinct")
    p_mkt, _ = fit_regimes(mkt, "crypto market (USDT)")
    p_rial, _ = fit_regimes(rl, "the rial leg (USDTIRT)")

    # 2. did it see the falling phase while it was falling?
    print("\n\n## 2. did the filter flag the losing phase in time\n")
    cuts = np.array_split(np.arange(len(mkt)), 3)
    print("| phase | market return | mean P(high regime) | reading |")
    print("|---|---:|---:|---|")
    for i, idx in enumerate(cuts, 1):
        seg = mkt.iloc[idx]
        pr = float(p_mkt.iloc[idx].mean())
        tot = float((1 + seg).prod() - 1)
        read = ("**flagged risk-off**" if pr < 0.45 else
                "stayed risk-on" if pr > 0.55 else "mixed")
        lab = f"P{i}" + (" (now)" if i == 3 else "")
        print(f"| {lab} | {tot*100:+.1f}% | {pr:.2f} | {read} |")

    # 3. out of sample: be in when the high regime is likely, else flat
    print("\n\n## 3. out of sample — does acting on it beat staying invested\n")
    cut = int(len(mkt) * TRAIN)
    te = mkt.iloc[cut:]
    pte = p_mkt.iloc[cut:]
    print("| threshold | exposure | switches | strategy (1x) | buy&hold (1x) "
          f"| at {LEV:g}x | maxDD at {LEV:g}x |")
    print("|---:|---:|---:|---:|---:|---:|---:|")
    bh = float((1 + te).prod() - 1)
    for thr in (0.5, 0.6, 0.7, 0.8):
        pos = (pte.shift(1) > thr).astype(float).fillna(0.0)
        sw = int((pos.diff().abs() > 0).sum())
        r = te * pos - SWITCH_COST * (pos.diff().abs().fillna(0))
        eq = (1 + r).cumprod()
        rl5 = te * pos * LEV - SWITCH_COST * LEV * (pos.diff().abs().fillna(0))
        eq5 = (1 + rl5).cumprod()
        dd5 = float((eq5 / eq5.cummax() - 1).min())
        print(f"| {thr:.1f} | {float(pos.mean())*100:.0f}% | {sw} "
              f"| {float(eq.iloc[-1]-1)*100:+.1f}% | {bh*100:+.1f}% "
              f"| **{float(eq5.iloc[-1]-1)*100:+.1f}%** | {dd5*100:.1f}% |")
    bh5 = float((1 + te * LEV).cumprod().iloc[-1] - 1)
    dd5bh = float(((1 + te * LEV).cumprod() /
                   (1 + te * LEV).cumprod().cummax() - 1).min())
    print(f"| — always in | 100% | 0 | {bh*100:+.1f}% | {bh*100:+.1f}% "
          f"| **{bh5*100:+.1f}%** | {dd5bh*100:.1f}% |")

    print(f"\ncurrent filtered P(high regime): crypto {float(p_mkt.iloc[-1]):.2f}, "
          f"rial {float(p_rial.iloc[-1]):.2f}")


if __name__ == "__main__":
    main()
