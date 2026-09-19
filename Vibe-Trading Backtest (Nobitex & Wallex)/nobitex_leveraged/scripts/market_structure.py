#!/usr/bin/env python3
"""What the 180 days say about how this market actually behaves.

Four measurements, each chosen because it changes how a result should be read
rather than because it is interesting on its own.

1. THE QUOTE CURRENCY. Every pair here is priced in rial. USDTIRT has no
   crypto content, so its rise is the rial falling, and it is the part of every
   other pair's return that was never a crypto move at all. Deflating by it
   separates the two.

2. CO-MOVEMENT. If the average pairwise correlation is high, these are not 63
   opportunities; they are one position held 63 times, and diversification
   across them buys much less than the count suggests.

3. MOMENTUM OR REVERSAL. The sign of return autocorrelation says which kind of
   system can work here at all. A trend follower needs positive autocorrelation
   and is fighting the data without it.

4. ASYMMETRY. Whether up and down bars differ in size and frequency, which is
   what a short seller is actually trading against.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alpha_beta import BPY  # noqa: E402
from maximize import newest_snapshot  # noqa: E402

RIAL_PROXY = "USDTIRT"


def main() -> None:
    snap = newest_snapshot()
    files = sorted(snap.glob("*.csv.gz"))
    close = {}
    for f in files:
        s = f.name.replace(".csv.gz", "")
        d = pd.read_csv(f, index_col=0, parse_dates=True)
        close[s] = d["close"]
    px = pd.DataFrame(close).sort_index()
    px = px.loc[:, px.notna().sum() > len(px) * 0.8].ffill().dropna(how="all")
    rets = px.pct_change().dropna(how="all")
    days = (px.index[-1] - px.index[0]).total_seconds() / 86400

    print(f"window: {px.index[0]} -> {px.index[-1]}  ({days:.0f} days, {len(px)} bars)")
    print(f"symbols with usable history: {px.shape[1]}\n")

    # 1. the quote currency
    rial = float(px[RIAL_PROXY].iloc[-1] / px[RIAL_PROXY].iloc[0] - 1)
    mkt_irt = float((1 + rets.mean(axis=1)).prod() - 1)
    px_usd = px.div(px[RIAL_PROXY], axis=0)
    rets_usd = px_usd.drop(columns=[RIAL_PROXY]).pct_change().dropna(how="all")
    mkt_usd = float((1 + rets_usd.mean(axis=1)).prod() - 1)
    print("== 1. how much of the rise was crypto, and how much was the rial ==")
    print(f"  USDTIRT (the rial falling):        {rial*100:+.1f}%")
    print(f"  equal-weight market, in rial:      {mkt_irt*100:+.1f}%")
    print(f"  equal-weight market, in USDT:      {mkt_usd*100:+.1f}%")
    share = rial / mkt_irt if abs(mkt_irt) > 1e-9 else float("nan")
    print(f"  -> the rial accounts for {share*100:.0f}% of the headline gain")
    beat = int((px_usd.drop(columns=[RIAL_PROXY]).iloc[-1]
                / px_usd.drop(columns=[RIAL_PROXY]).iloc[0] - 1 > 0).sum())
    n_usd = px_usd.shape[1] - 1
    print(f"  -> in USDT terms only {beat}/{n_usd} symbols actually rose\n")

    # 2. co-movement
    c = rets.corr()
    iu = np.triu_indices_from(c.to_numpy(), k=1)
    pair = c.to_numpy()[iu]
    ev = np.linalg.eigvalsh(np.nan_to_num(c.to_numpy(), nan=0.0))[::-1]
    pc1 = float(ev[0] / ev.sum())
    print("== 2. is this 63 bets or one bet held 63 times ==")
    print(f"  average pairwise correlation: {np.nanmean(pair):.2f} "
          f"(median {np.nanmedian(pair):.2f})")
    print(f"  first principal component explains {pc1*100:.0f}% of all variance")
    print(f"  effective independent bets ~ {1/np.nanmean(pair):.1f} "
          f"out of {px.shape[1]}\n")

    # 3. momentum or reversal
    m = rets.mean(axis=1)
    ac = [float(m.autocorr(lag=k)) for k in (1, 2, 3, 6, 12, 30)]
    per_sym = [float(rets[s].autocorr(lag=1)) for s in rets.columns]
    print("== 3. does a trend persist, or snap back ==")
    print("  market autocorrelation  lag1 {:+.3f}  lag2 {:+.3f}  lag3 {:+.3f}  "
          "lag6 {:+.3f}  lag12 {:+.3f}  lag30 {:+.3f}".format(*ac))
    print(f"  per-symbol lag-1, median {np.nanmedian(per_sym):+.3f}, "
          f"{sum(1 for v in per_sym if v < 0)}/{len(per_sym)} negative\n")

    # 4. asymmetry
    up, dn = m[m > 0], m[m < 0]
    print("== 4. what a short seller is trading against ==")
    print(f"  bars up {len(up)/len(m)*100:.1f}%, mean +{up.mean()*100:.3f}%")
    print(f"  bars down {len(dn)/len(m)*100:.1f}%, mean {dn.mean()*100:.3f}%")
    print(f"  drift per bar {m.mean()*100:+.4f}%  "
          f"(annualised {m.mean()*BPY*100:+.0f}%)")
    print(f"  a short pays that drift: {-m.mean()*BPY*100:+.0f}% a year before any skill")
    vol = m.rolling(60).std() * math.sqrt(BPY)
    print(f"  60-bar vol: now {vol.iloc[-1]*100:.0f}%, "
          f"median {vol.median()*100:.0f}%, max {vol.max()*100:.0f}%")


if __name__ == "__main__":
    main()
