#!/usr/bin/env python3
"""The rial leg's behaviour, and what it does to a leveraged book.

A pair's USDT price on Nobitex is close to its global price, because tether is
fungible across venues. So the gap between a symbol's rial return and its USDT
return is not a per-symbol premium at all — it is one shared rial move applied
to every pair, and that move is what USDTIRT prices directly.

That makes two things measurable without any external data.

Does the rial lead crypto or follow it? Lagged cross-correlation answers it. If
the rial move arrives first, it is capital leaving the currency and crypto is
the destination; if it follows, crypto is being sold into rial.

And does the rial accelerate when crypto falls? That is the question a short
book depends on. A short in a Toman pair is long rial, so a rial that
strengthens its drift exactly when crypto drops removes the payoff the short
was taken for.
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
PHASES = 3


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

    r_rial = rial.pct_change().dropna()
    r_cry = U.pct_change().mean(axis=1).dropna()
    j = pd.concat([r_rial, r_cry], axis=1).dropna()
    j.columns = ["rial", "crypto"]

    print(f"snapshot {snap.name}, {len(j)} bars\n")

    # 1. phases
    print("## 1. the rial leg by phase, beside the crypto it is quoted against\n")
    print("| phase | rial (USDTIRT) | crypto in USDT | rial vol | crypto vol "
          "| rial share of the rial-priced move |")
    print("|---|---:|---:|---:|---:|---:|")
    cuts = np.array_split(np.arange(len(P)), PHASES)
    for i, idx in enumerate(cuts, 1):
        sub_r = rial.iloc[idx]
        rr = float(sub_r.iloc[-1] / sub_r.iloc[0] - 1)
        cc = float((1 + r_cry.iloc[[k for k in idx if k < len(r_cry)]]).prod() - 1)
        irt = (1 + rr) * (1 + cc) - 1
        share = rr / irt if abs(irt) > 1e-9 else float("nan")
        vr = float(sub_r.pct_change().std(ddof=1) * math.sqrt(BPY))
        vc = float(r_cry.iloc[[k for k in idx if k < len(r_cry)]].std(ddof=1)
                   * math.sqrt(BPY))
        lab = f"P{i}" + (" **(now)**" if i == PHASES else "")
        print(f"| {lab} | {rr*100:+.1f}% | {cc*100:+.1f}% | {vr*100:.0f}% "
              f"| {vc*100:.0f}% | {share*100:.0f}% |")

    # 2. lead-lag
    print("\n\n## 2. does the rial lead crypto, or follow it\n")
    print("| lag (bars) | corr(rial_t, crypto_t-lag) | reading |")
    print("|---:|---:|---|")
    best, bl = 0.0, 0          # start at zero: -9 was being printed as the result
    for k in range(-6, 7):
        c = j["rial"].corr(j["crypto"].shift(k))
        if np.isfinite(c) and abs(c) > abs(best):
            best, bl = c, k
        if abs(k) <= 3:
            tag = ("crypto leads" if k > 0 else
                   "rial leads" if k < 0 else "same bar")
            print(f"| {k:+d} | {c:+.3f} | {tag} |")
    print(f"\n-> strongest at lag {bl:+d}, corr {best:+.3f}")

    # 3. what the rial does when crypto falls — the short book's question
    print("\n\n## 3. what the rial does when crypto falls\n")
    q = j["crypto"].quantile([0.1, 0.25, 0.75, 0.9])
    buckets = [("crypto worst 10%", j[j.crypto <= q[0.1]]),
               ("crypto worst 25%", j[j.crypto <= q[0.25]]),
               ("crypto middle", j[(j.crypto > q[0.25]) & (j.crypto < q[0.75])]),
               ("crypto best 25%", j[j.crypto >= q[0.75]]),
               ("crypto best 10%", j[j.crypto >= q[0.9]])]
    print("| when | mean rial move | annualised | bars |")
    print("|---|---:|---:|---:|")
    for name, b in buckets:
        print(f"| {name} | {b['rial'].mean()*100:+.4f}% "
              f"| {b['rial'].mean()*BPY*100:+.0f}% | {len(b)} |")

    down = j[j.crypto < 0]["rial"].mean() * BPY
    up = j[j.crypto > 0]["rial"].mean() * BPY
    print(f"\n-> on down-crypto bars the rial leg runs {down*100:+.0f}%/yr; "
          f"on up bars {up*100:+.0f}%/yr")
    print(f"-> a rial-pair SHORT is long rial, so on exactly the bars it wants "
          f"to win it pays {down*100:+.0f}%/yr against itself")


if __name__ == "__main__":
    main()
