#!/usr/bin/env python3
"""Lowest risk, best odds, and most profit at 5x are three different questions.

Ranking by alpha answered none of them, so each gets its own measurement, all
in USDT and all from the same bars.

ODDS come from first passage, not from a win rate. Every historical bar where
the signal was long starts a hypothetical trade, and the forward path decides
whether +5% or -8% arrives first. That is the question a stop-and-target trade
actually poses, and it accounts for the path rather than the endpoint.

RISK is what the position does when it is wrong: how far adverse moves reach
within the holding horizon, how often the 19.5% move that liquidates a 5x
position occurred at all, and how the name behaved in the one phase this market
fell.

PROFIT at 5x is expectancy, not upside. P(win)*25% - P(loss)*40% per trade,
multiplied by how often the setup appears. A name with better odds and a worse
payout can still win, and leverage multiplies a negative expectancy just as
faithfully as a positive one.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alpha_beta import BPY, OURS_STOP, OURS_TAKE, ema_long_short  # noqa: E402
from maximize import newest_snapshot  # noqa: E402
from nobitex_leveraged_backtest import add_indicators  # noqa: E402

RIAL = "USDTIRT"
THREE = ["UNIIRT", "NEARIRT", "ZECIRT"]
LEV = 5.0
MAINT = 0.005
HORIZON = 90          # bars to resolve a trade (15 days at 4h)
LIQ = 1.0 / LEV - MAINT


def first_passage(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                  starts: np.ndarray) -> dict:
    """From each signal bar, does +take or -stop arrive first within HORIZON?"""
    win = loss = neither = 0
    liq_hits = 0
    mae, mfe, bars_to = [], [], []
    n = len(close)
    for i in starts:
        if i + 2 >= n:
            continue
        entry = close[i]
        tp, sl = entry * (1 + OURS_TAKE), entry * (1 - OURS_STOP)
        liq_px = entry * (1 - LIQ)
        end = min(i + 1 + HORIZON, n)
        worst = 0.0
        best = 0.0
        hit = None
        for j in range(i + 1, end):
            worst = min(worst, low[j] / entry - 1)
            best = max(best, high[j] / entry - 1)
            if low[j] <= liq_px:
                liq_hits += 1
            if low[j] <= sl and high[j] >= tp:
                hit = "loss"        # both in one bar: assume the adverse first
                bars_to.append(j - i)
                break
            if high[j] >= tp:
                hit = "win"; bars_to.append(j - i); break
            if low[j] <= sl:
                hit = "loss"; bars_to.append(j - i); break
        mae.append(worst); mfe.append(best)
        if hit == "win":
            win += 1
        elif hit == "loss":
            loss += 1
        else:
            neither += 1
    tot = win + loss + neither
    resolved = win + loss
    return {"n": tot, "win": win, "loss": loss, "open": neither,
            "p_win": win / resolved if resolved else float("nan"),
            "p_liq": liq_hits / tot if tot else float("nan"),
            "mae_med": float(np.median(mae)) if mae else float("nan"),
            "mfe_med": float(np.median(mfe)) if mfe else float("nan"),
            "bars_med": float(np.median(bars_to)) if bars_to else float("nan")}


def main() -> None:
    snap = newest_snapshot()
    px = {}
    for f in sorted(snap.glob("*.csv.gz")):
        px[f.name.replace(".csv.gz", "")] = pd.read_csv(
            f, index_col=0, parse_dates=True)
    rial = px[RIAL]["close"]

    print(f"snapshot {snap.name}, all prices in USDT, "
          f"stop {OURS_STOP:.0%} / target {OURS_TAKE:.0%}, "
          f"leverage {LEV:g}x (liquidation at {LIQ:.1%})\n")

    res = {}
    for s in THREE:
        d = px[s].copy()
        r = rial.reindex(d.index).ffill()
        for c in ("open", "high", "low", "close"):
            d[c] = d[c] / r
        di = add_indicators(d, 10, 30, 14, 3)
        sig = ema_long_short(di).to_numpy()
        starts = np.where(sig == 1)[0]
        fp = first_passage(di["close"].to_numpy(), di["high"].to_numpy(),
                           di["low"].to_numpy(), starts)
        ret = di["close"].pct_change().dropna()
        eq = di["close"] / di["close"].iloc[0]
        dd = float((eq / eq.cummax() - 1).min())
        vol = float(ret.std(ddof=1) * math.sqrt(BPY))
        # downside-only volatility: what the position feels when wrong
        dvol = float(ret[ret < 0].std(ddof=1) * math.sqrt(BPY))
        ev = fp["p_win"] * LEV * OURS_TAKE - (1 - fp["p_win"]) * LEV * OURS_STOP
        freq = len(starts) / len(sig)
        res[s] = {**fp, "vol": vol, "dvol": dvol, "dd": dd, "ev": ev,
                  "freq": freq, "last": float(di["close"].iloc[-1]),
                  "ema10": float(di["close"].ewm(span=10, adjust=False).mean().iloc[-1])}

    print("## odds — first passage from every historical signal bar\n")
    print("| symbol | trades | wins | losses | unresolved | **P(win)** | median bars "
          "| median MAE | median MFE |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s, r in res.items():
        print(f"| **{s}** | {r['n']} | {r['win']} | {r['loss']} | {r['open']} "
              f"| **{r['p_win']*100:.1f}%** | {r['bars_med']:.0f} "
              f"| {r['mae_med']*100:.1f}% | {r['mfe_med']*100:+.1f}% |")

    print("\n\n## risk — what it does when it is wrong\n")
    print("| symbol | ann vol | downside vol | worst DD | P(touch liquidation) "
          f"| loss at {LEV:g}x |")
    print("|---|---:|---:|---:|---:|---:|")
    for s, r in res.items():
        print(f"| **{s}** | {r['vol']*100:.0f}% | {r['dvol']*100:.0f}% "
              f"| {r['dd']*100:.1f}% | {r['p_liq']*100:.2f}% "
              f"| −{LEV*OURS_STOP*100:.0f}% |")

    print(f"\n\n## profit — expectancy per trade at {LEV:g}x\n")
    print("| symbol | P(win) | win pays | loss costs | **EV per trade** "
          "| signal on | **EV per year** |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for s, r in res.items():
        trades_yr = (BPY / r["bars_med"]) * r["freq"] if r["bars_med"] > 0 else 0
        print(f"| **{s}** | {r['p_win']*100:.1f}% | +{LEV*OURS_TAKE*100:.0f}% "
              f"| −{LEV*OURS_STOP*100:.0f}% | **{r['ev']*100:+.2f}%** "
              f"| {r['freq']*100:.0f}% | **{r['ev']*trades_yr*100:+.0f}%** |")

    print("\n\n## where each sits right now\n")
    print("| symbol | price (USDT) | vs EMA10 | breakeven P(win) needed |")
    print("|---|---:|---:|---:|")
    be = LEV * OURS_STOP / (LEV * OURS_TAKE + LEV * OURS_STOP)
    for s, r in res.items():
        print(f"| **{s}** | {r['last']:.6g} | {(r['last']/r['ema10']-1)*100:+.1f}% "
              f"| {be*100:.1f}% |")


if __name__ == "__main__":
    main()
