#!/usr/bin/env python3
"""Five shorts and five longs, sized at the venue's maximum leverage.

Ranking is per-symbol alpha against the equal-weight market, not raw return.
Raw return ranks the market's direction: over this window everything rose, so
it would put the worst shorts on top and call the best ones failures. Alpha is
what is left after the symbol's own move is removed, which is the only ranking
that means the same thing on both sides.

Sizing is the venue cap of 5x. The strategy's 8% stop then costs 40% of the
position's equity, and liquidation sits near a 20% adverse move — so the stop
is reached first and the loss stays bounded. Both numbers are printed per row
rather than described, because at 5x they are the trade.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alpha_beta import (  # noqa: E402
    BPY, OURS_STOP, OURS_TAKE, ema_long_short, long_only_ema, ols_alpha, run,
    short_only,
)  # noqa: E402
from maximize import load_history, newest_snapshot  # noqa: E402
from nobitex_leveraged_backtest import (  # noqa: E402
    add_indicators, equity_returns, warmup_bars,
)

TOP = 5
MAINTENANCE = 0.005
RIAL = "USDTIRT"


def to_usdt(frames: dict) -> dict:
    """Re-price every pair in USDT by dividing out the rial leg.

    Rial pricing adds the same currency move to every symbol, which lifts
    losers into apparent winners and charges a short that drift on every
    position. Ranking has to happen on the move that is actually the symbol's
    own, so signals, alpha and the market are all computed here instead.
    """
    if RIAL not in frames:
        return frames
    rial = frames[RIAL]["close"]
    out = {}
    for s, d in frames.items():
        if s == RIAL:
            continue
        q = d.copy()
        r = rial.reindex(q.index).ffill()
        for c in ("open", "high", "low", "close"):
            if c in q:
                q[c] = q[c] / r
        out[s] = q
    return out


def money(v: float) -> str:
    return f"{v:,.0f}"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("watch5x_out")
    out.mkdir(parents=True, exist_ok=True)
    snap = newest_snapshot()
    man = json.loads((snap / "manifest.json").read_text())
    fee, lev = float(man["fee_per_side"]), float(man["venue_leverage_cap"])
    warmup = warmup_bars(30, 14, 3)

    usdt = "--usdt" in sys.argv
    raw, src = load_history()
    base = {}
    for s, d in raw.items():
        base[s] = d
    irt_price = {s: float(d["close"].iloc[-1]) for s, d in base.items()}

    if usdt:
        base = to_usdt(base)
    frames = {}
    for s, d in base.items():
        try:
            frames[s] = add_indicators(d, 10, 30, 14, 3)
        except Exception:  # noqa: BLE001
            pass
    rm = pd.DataFrame({s: d["close"].pct_change()
                       for s, d in frames.items()}).mean(axis=1).dropna()

    rows = []
    for s, d in frames.items():
        sig = ema_long_short(d)
        live = int(sig.iloc[-1])
        bars_since = 1
        v = sig.to_numpy()
        while bars_since < len(v) and v[-1 - bars_since] == v[-1]:
            bars_since += 1

        rec = {"symbol": s, "live": live, "bars_since_flip": bars_since,
               "price": irt_price.get(s, float(d["close"].iloc[-1])),
               "price_basis": float(d["close"].iloc[-1]),
               "atr": float(d["atr"].iloc[-1])}
        for side, fn in (("short", short_only), ("long", long_only_ema)):
            c, _t = run(d, fn(d), OURS_STOP, OURS_TAKE, warmup, fee)
            if c is None:
                continue
            reg = ols_alpha(equity_returns(c), rm)
            rec[f"{side}_alpha"] = reg.get("alpha_ann", float("nan"))
            rec[f"{side}_t"] = reg.get("alpha_t", float("nan"))
            rec[f"{side}_beta"] = reg.get("beta", float("nan"))
        rows.append(rec)

    def pick(side: str, want: int) -> list[dict]:
        c = [r for r in rows if r["live"] == want
             and np.isfinite(r.get(f"{side}_t", float("nan")))]
        c.sort(key=lambda r: -r[f"{side}_t"])
        return c[:TOP]

    liq_move = 1.0 / lev - MAINTENANCE          # adverse move that wipes margin
    denom = "USDT" if usdt else "rial"
    mdrift = rm.mean() * BPY
    L = [f"\n===== FIVE SHORTS, FIVE LONGS AT {lev:g}x, priced in {denom} =====",
         f"data: {src}; last bar {frames[list(frames)[0]].index[-1]}",
         f"fee {fee:.4%}/side; stop {OURS_STOP:.0%}; target {OURS_TAKE:.0%}",
         f"at {lev:g}x the {OURS_STOP:.0%} stop costs {lev*OURS_STOP:.0%} of equity; "
         f"liquidation needs a {liq_move:.1%} adverse move, so the stop comes first",
         f"market drift {mdrift*100:+.0f}%/yr in {denom} -> a short pays "
         f"{-mdrift*100:+.0f}%/yr before any skill",
         "ranked by alpha vs the equal-weight market, not by raw return\n"]

    for side, want, label in (("short", -1, "SHORT"), ("long", 1, "LONG")):
        sel = pick(side, want)
        L += [f"\n## {label} — top {len(sel)} by {side}-side alpha\n",
              f"| # | symbol | entry (IRT) | stop | target | bars in signal "
              f"| alpha (ann) | t | beta | loss at {lev:g}x | gain at {lev:g}x |",
              "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for i, r in enumerate(sel, 1):
            p = r["price"]
            if want == -1:
                stop_p, tgt_p = p * (1 + OURS_STOP), p * (1 - OURS_TAKE)
            else:
                stop_p, tgt_p = p * (1 - OURS_STOP), p * (1 + OURS_TAKE)
            L.append(
                f"| {i} | **{r['symbol']}** | {money(p)} | {money(stop_p)} "
                f"| {money(tgt_p)} | {r['bars_since_flip']} "
                f"| {r[f'{side}_alpha']*100:+.1f}% | {r[f'{side}_t']:.2f} "
                f"| {r[f'{side}_beta']:+.2f} | **−{lev*OURS_STOP*100:.0f}%** "
                f"| +{lev*OURS_TAKE*100:.0f}% |")

    text = "\n".join(L)
    (out / "WATCH_5X.md").write_text(text + "\n")
    (out / "watch_5x.json").write_text(json.dumps(rows, indent=2, default=str))
    print(text)


if __name__ == "__main__":
    main()
