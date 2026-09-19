#!/usr/bin/env python3
"""Can the rial leg itself be traded, and does leverage survive the carry?

USDTIRT is the one series here that is not global crypto. It is priced by local
capital flow, it has the highest regime persistence measured (0.87 against
crypto's 0.75), and it is listed at 5x — and no strategy family has been
pointed at it.

For a Toman-based account the baseline is not cash, it is holding tether, which
is what the +40% over this window already is. So the question is whether timing
adds anything to simply holding, and whether leverage survives being held.

That second part is what nothing so far has had to face. Every earlier test
resolved trades in days. A leveraged bet on currency depreciation is held for
months, and the daily extension fee compounds against it the whole time: at 5x
notional, a 0.1% daily charge costs 0.5% of equity a day, which over 180 days is
larger than the move being captured. The fee is therefore varied rather than
assumed, so the break-even carry is visible instead of buried.
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
BARS_PER_DAY = 6
LEV = 5.0


def main() -> None:
    snap = newest_snapshot()
    d = pd.read_csv(snap / f"{RIAL}.csv.gz", index_col=0, parse_dates=True)
    p = d["close"]
    r = p.pct_change().dropna()
    days = (p.index[-1] - p.index[0]).total_seconds() / 86400
    total = float(p.iloc[-1] / p.iloc[0] - 1)

    print(f"USDTIRT over {days:.0f} days: {total*100:+.1f}%, "
          f"vol {float(r.std(ddof=1)*math.sqrt(BPY))*100:.0f}%/yr\n")

    # 1. is it predictable at all
    print("## 1. structure of the rial series\n")
    print("| lag | autocorrelation |")
    print("|---:|---:|")
    for k in (1, 2, 3, 6, 12, 42):
        print(f"| {k} | {float(r.autocorr(lag=k)):+.3f} |")
    up = float((r > 0).mean())
    print(f"\nbars up {up*100:.1f}%; largest single-bar move "
          f"{float(r.abs().max())*100:.1f}%")
    eq = p / p.iloc[0]
    print(f"worst drawdown unlevered: {float((eq/eq.cummax()-1).min())*100:.1f}%")

    # 2. does a signal beat holding, and beat random
    print("\n\n## 2. timing the rial against simply holding it\n")
    e10 = p.ewm(span=10, adjust=False).mean()
    e30 = p.ewm(span=30, adjust=False).mean()
    sig = (e10 > e30).astype(float).shift(1).fillna(0.0).reindex(r.index).fillna(0.0)
    rng = np.random.default_rng(0)
    # One random draw is a sample of one. The comparison that matters is the
    # signal against the DISTRIBUTION of random exposures at the same rate, so
    # the same draw is repeated and the result read as a percentile.
    N_DRAWS = 1000
    exp_rate = float(sig.mean())
    draws = []
    for _ in range(N_DRAWS):
        pos = rng.choice([0.0, 1.0], size=len(r), p=[1 - exp_rate, exp_rate])
        draws.append(float((1 + r.to_numpy() * pos).prod() - 1))
    draws = np.array(draws)
    rnd = pd.Series(rng.choice([0.0, 1.0], size=len(r), p=[1 - exp_rate, exp_rate]),
                    index=r.index)
    print("| approach | exposure | return | vol | worst DD |")
    print("|---|---:|---:|---:|---:|")
    for name, pos in (("hold tether (always in)", pd.Series(1.0, index=r.index)),
                      ("EMA 10/30 timing", sig),
                      ("random, same exposure", rnd)):
        rr = r * pos
        e = (1 + rr).cumprod()
        print(f"| {name} | {float(pos.mean())*100:.0f}% "
              f"| {float(e.iloc[-1]-1)*100:+.1f}% "
              f"| {float(rr.std(ddof=1)*math.sqrt(BPY))*100:.0f}% "
              f"| {float((e/e.cummax()-1).min())*100:.1f}% |")

    sig_ret = float((1 + r * sig).cumprod().iloc[-1] - 1)
    pct = float((draws < sig_ret).mean())
    print(f"\nagainst {N_DRAWS} random exposures at the same {exp_rate*100:.0f}% rate:")
    print(f"  random mean {draws.mean()*100:+.1f}%, "
          f"5th-95th {np.percentile(draws,5)*100:+.1f}% to "
          f"{np.percentile(draws,95)*100:+.1f}%")
    print(f"  the signal's {sig_ret*100:+.1f}% sits at the "
          f"**{pct*100:.1f}th percentile** (p = {1-pct:.3f} one-sided)")
    print(f"  holding throughout returned {total*100:+.1f}%, which is at the "
          f"{float((draws < total).mean())*100:.0f}th percentile of the same draws")

    # 3. leverage vs the carry — the part nothing else had to pay
    print(f"\n\n## 3. {LEV:g}x long the rial, held, against the daily extension fee\n")
    print("| daily fee on notional | cost over the window | net at 5x | verdict |")
    print("|---:|---:|---:|---|")
    gross = float((1 + r * LEV).cumprod().iloc[-1] - 1)
    for fee_d in (0.0, 0.0002, 0.0005, 0.001, 0.0015, 0.002):
        per_bar = fee_d / BARS_PER_DAY * LEV
        net = float((1 + r * LEV - per_bar).cumprod().iloc[-1] - 1)
        cost = fee_d * LEV * days
        verdict = "profitable" if net > 0 else "**wiped out**"
        print(f"| {fee_d*100:.2f}%/day | {cost*100:.0f}% of equity "
              f"| **{net*100:+.1f}%** | {verdict} |")
    print(f"\ngross at {LEV:g}x with no carry: {gross*100:+.1f}%")
    # break-even daily fee
    lo, hi = 0.0, 0.01
    for _ in range(60):
        mid = (lo + hi) / 2
        n = float((1 + r * LEV - mid / BARS_PER_DAY * LEV).cumprod().iloc[-1] - 1)
        lo, hi = (mid, hi) if n > 0 else (lo, mid)
    print(f"break-even daily fee: **{lo*100:.3f}%/day** "
          f"({lo*365*100:.0f}%/yr on notional)")
    e5 = (1 + r * LEV).cumprod()
    print(f"worst drawdown at {LEV:g}x before any fee: "
          f"{float((e5/e5.cummax()-1).min())*100:.1f}%")


if __name__ == "__main__":
    main()
