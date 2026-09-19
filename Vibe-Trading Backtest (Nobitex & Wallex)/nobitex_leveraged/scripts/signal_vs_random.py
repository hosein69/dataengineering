#!/usr/bin/env python3
"""Does the signal beat entering at random? The leverage question reduces to this.

The first-passage test measured the win rate conditional on a long signal and
found 67%, comfortably above the 61.5% a 5% target against an 8% stop needs.
But it was measured over a window where the market rose 87%, and any
long-conditioned sample inherits that. The number the signal has to beat is not
the breakeven — it is the win rate of entering on a random bar and using the
same stop and target.

The difference between those two is everything leverage can amplify. If it is
zero, leverage is multiplying the market's drift and nothing else, and every
apparent edge in this project was the regime.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alpha_beta import OURS_STOP, OURS_TAKE, ema_long_short  # noqa: E402
from maximize import newest_snapshot  # noqa: E402
from nobitex_leveraged_backtest import add_indicators  # noqa: E402

RIAL = "USDTIRT"
LEV, HORIZON = 5.0, 90
BREAKEVEN = OURS_STOP / (OURS_TAKE + OURS_STOP)


def passage(close, high, low, starts, horizon=HORIZON):
    win = loss = 0
    for i in starts:
        if i + 2 >= len(close):
            continue
        e = close[i]
        tp, sl = e * (1 + OURS_TAKE), e * (1 - OURS_STOP)
        for j in range(i + 1, min(i + 1 + horizon, len(close))):
            if low[j] <= sl:
                loss += 1; break
            if high[j] >= tp:
                win += 1; break
    tot = win + loss
    return win / tot if tot else float("nan"), tot


def main() -> None:
    snap = newest_snapshot()
    px = {f.name.replace(".csv.gz", ""): pd.read_csv(f, index_col=0, parse_dates=True)
          for f in sorted(snap.glob("*.csv.gz"))}
    rial = px[RIAL]["close"]
    rng = np.random.default_rng(0)

    print(f"stop {OURS_STOP:.0%}, target {OURS_TAKE:.0%}, breakeven "
          f"{BREAKEVEN:.1%}, leverage {LEV:g}x\n")
    print("| symbol | P(win) on signal | P(win) random entry | **edge** "
          "| signal n | random n |")
    print("|---|---:|---:|---:|---:|---:|")

    edges = []
    for s in ["UNIIRT", "NEARIRT", "ZECIRT", "ARBIRT", "BTCIRT", "ETHIRT"]:
        d = px[s].copy()
        r = rial.reindex(d.index).ffill()
        for c in ("open", "high", "low", "close"):
            d[c] = d[c] / r
        di = add_indicators(d, 10, 30, 14, 3)
        c_, h_, l_ = (di["close"].to_numpy(), di["high"].to_numpy(),
                      di["low"].to_numpy())
        sig = ema_long_short(di).to_numpy()
        on = np.where(sig == 1)[0]
        p_sig, n_sig = passage(c_, h_, l_, on)
        # random entries: same count, drawn from every bar regardless of signal
        allbars = np.arange(40, len(c_) - 2)
        pick = rng.choice(allbars, size=min(len(on), len(allbars)), replace=False)
        p_rnd, n_rnd = passage(c_, h_, l_, pick)
        edge = p_sig - p_rnd
        edges.append(edge)
        print(f"| **{s}** | {p_sig*100:.1f}% | {p_rnd*100:.1f}% "
              f"| **{edge*100:+.1f} pts** | {n_sig} | {n_rnd} |")

    e = np.array(edges)
    print(f"\nmean edge of the signal over random entry: **{e.mean()*100:+.2f} pts**")
    print(f"symbols where the signal beat random: {int((e > 0).sum())}/{len(e)}")
    print(f"\nrandom entry already clears breakeven ({BREAKEVEN:.1%}) because the")
    print("market rose over this window; that is drift, not signal.")


if __name__ == "__main__":
    main()
