#!/usr/bin/env python3
"""Concrete entry / invalidation / sizing levels for the surviving symbols.

The five symbols that cleared the buy-and-hold filter are all ones strategy B
is ALREADY holding, entered 28-75 days ago. So there is no "the strategy is
about to enter" level to quote. What can be quoted honestly is:

  * where the strategy's own exit rule sits right now — the price at which all
    three sell-Supertrends would be down and B would close. That is the
    invalidation level for anyone entering today.
  * how far today's price is from it, in percent and in ATR.
  * the leverage that distance permits, under two separate binding constraints:
      - risk budget: at leverage L, hitting the stop costs L * d of equity.
      - liquidation ordering: isolated margin liquidates near a 1/L adverse
        move, so L must satisfy 1/L > d or the position is liquidated BEFORE
        its own stop is reached, which converts a planned loss into a total one.
  * what the trade risks versus what B's own ROI rung targets.

It also reports how far price has already run since B entered, because entering
a trend 28-75 days late is not the trade the backtest measured.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nobitex_leveraged_backtest import add_indicators, atr, fetch_raw  # noqa: E402
from watchlist_compare import (  # noqa: E402
    FT_BUY, FT_SELL, FT_TAKE, LOOKBACK_DAYS, RESOLUTION, signal_supertrend_ft,
)

SURVIVORS = ["ETHIRT", "ADAIRT", "DOGEIRT", "XRPIRT", "BTCIRT"]
MAX_LOSS_PER_TRADE = 0.20      # most of equity a single stop-out may cost
MAINTENANCE = 0.005
LEV_HARD_CAP = 5.0


def supertrend_bands(df: pd.DataFrame, period: int, multiplier: float):
    """Return (direction, final_lower, final_upper) for one Supertrend."""
    hl2 = (df["high"] + df["low"]) / 2.0
    a = atr(df, period)
    up = (hl2 + multiplier * a).to_numpy()
    lo = (hl2 - multiplier * a).to_numpy()
    close = df["close"].to_numpy()
    n = len(df)
    f_up, f_lo = np.full(n, np.nan), np.full(n, np.nan)
    direction = np.zeros(n, dtype=int)
    for i in range(n):
        if i == 0 or np.isnan(up[i]) or np.isnan(f_up[i - 1]):
            f_up[i], f_lo[i] = up[i], lo[i]
            direction[i] = 1
            continue
        f_up[i] = up[i] if (up[i] < f_up[i - 1] or close[i - 1] > f_up[i - 1]) else f_up[i - 1]
        f_lo[i] = lo[i] if (lo[i] > f_lo[i - 1] or close[i - 1] < f_lo[i - 1]) else f_lo[i - 1]
        direction[i] = (-1 if close[i] < f_lo[i] else 1) if direction[i - 1] == 1 \
            else (1 if close[i] > f_up[i] else -1)
    return direction, f_lo, f_up


def analyse(symbol: str) -> dict:
    raw = fetch_raw(symbol, RESOLUTION, LOOKBACK_DAYS)
    cov = raw.attrs["coverage"]
    df = add_indicators(raw, 10, 30, 14, 3)
    price = float(df["close"].iloc[-1])

    # Where does B's exit rule sit? Exit needs ALL THREE sell-Supertrends down.
    # A sell-ST that is currently 'up' flips down when price crosses under its
    # lower band, so the trigger is the lowest of those still-up bands.
    still_up_bands = []
    already_down = 0
    for mult, per in FT_SELL:
        d, f_lo, _ = supertrend_bands(df, per, mult)
        if d[-1] == 1:
            still_up_bands.append(float(f_lo[-1]))
        else:
            already_down += 1

    if still_up_bands:
        invalidation = min(still_up_bands)
    else:
        invalidation = price       # all three already down: exit is imminent

    dist = (price - invalidation) / price          # fractional distance to stop
    a14 = float(df["atr"].iloc[-1])
    dist_atr = (price - invalidation) / a14 if a14 > 0 else float("nan")

    # How long has B been in, and at what price?
    sig = signal_supertrend_ft(df)
    in_pos = int(sig.iloc[-1]) == 1
    entry_price = entry_time = None
    bars_in = 0
    if in_pos:
        s = sig.to_numpy()
        i = len(s) - 1
        while i > 0 and s[i - 1] == 1:
            i -= 1
        bars_in = len(s) - i
        entry_price = float(df["open"].iloc[min(i + 1, len(df) - 1)])
        entry_time = str(df.index[i])

    # Leverage bounds
    lev_risk = MAX_LOSS_PER_TRADE / dist if dist > 1e-9 else float("inf")
    lev_liq = 1.0 / (dist + MAINTENANCE) if dist > 1e-9 else float("inf")
    lev = float(min(lev_risk, lev_liq, LEV_HARD_CAP))

    target = price * (1 + FT_TAKE)
    rr = FT_TAKE / dist if dist > 1e-9 else float("nan")

    return {
        "symbol": symbol,
        "last_bar": str(df.index[-1]),
        "price": price,
        "coverage": cov["coverage_ratio"],
        "in_position": in_pos,
        "bars_in_position": bars_in,
        "entry_price": entry_price,
        "entry_time": entry_time,
        "run_since_entry": (price / entry_price - 1) if entry_price else None,
        "sell_st_already_down": already_down,
        "invalidation": invalidation,
        "stop_distance": dist,
        "stop_distance_atr": dist_atr,
        "atr14": a14,
        "lev_from_risk_budget": lev_risk,
        "lev_before_liquidation": lev_liq,
        "suggested_leverage": lev,
        "target_price": target,
        "reward_risk": rr,
    }


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("entry_out")
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for s in SURVIVORS:
        try:
            rows.append(analyse(s))
        except Exception as exc:  # noqa: BLE001
            print(f"{s} failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    def money(v):
        return f"{v:,.0f}" if v and np.isfinite(v) else "n/a"

    lines = [f"\n===== ENTRY / INVALIDATION LEVELS ({RESOLUTION}m bars) =====",
             f"last bar: {rows[0]['last_bar'] if rows else 'n/a'}\n",
             "| symbol | price (IRT) | B entered at | run since entry | bars held "
             "| invalidation | distance | in ATR | target (+8.7%) | R:R |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(
            f"| {r['symbol']} | {money(r['price'])} | {money(r['entry_price'])} "
            f"| {r['run_since_entry']*100:+.1f}% | {r['bars_in_position']} "
            f"| {money(r['invalidation'])} | {r['stop_distance']*100:.2f}% "
            f"| {r['stop_distance_atr']:.1f} | {money(r['target_price'])} "
            f"| {r['reward_risk']:.2f} |")

    lines += ["\n\n## Leverage the stop distance actually permits\n",
              "| symbol | stop distance | max lev from 20% risk budget "
              "| max lev before liquidation precedes the stop | **usable** |",
              "|---|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(
            f"| {r['symbol']} | {r['stop_distance']*100:.2f}% "
            f"| {r['lev_from_risk_budget']:.2f}x | {r['lev_before_liquidation']:.2f}x "
            f"| **{r['suggested_leverage']:.2f}x** |")

    text = "\n".join(lines)
    (out / "ENTRY_POINTS.md").write_text(text + "\n")
    (out / "entry_points.json").write_text(json.dumps(rows, indent=2, default=str))
    print(text)


if __name__ == "__main__":
    main()
