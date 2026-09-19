#!/usr/bin/env python3
"""Position sizes and entry levels for the two-sided book.

Two decisions the per-symbol tables leave open.

WEIGHTS. Equal weight is equal MONEY, not equal risk: a symbol with three
times another's volatility then drives three times the swing, and the book's
result comes down to whichever name happens to be wildest. Weights here are
inverse-volatility within each side, so every position contributes about the
same risk.

NET BETA. This is the one that decides what the book actually is. The longs
carry beta around +0.6 and the shorts only about -0.25, so equal money on each
side leaves a large net long — a directional bet on the market wearing the
costume of a hedged book, which is exactly the confusion the alpha work was
meant to end. The short side is therefore scaled until the two betas cancel,
and the residual is printed rather than assumed to be zero.

Entries are the current price with a limit at the fast EMA, which the signal
is already above (long) or below (short): it is the level the position can be
entered at without paying up, and it is where the trade is invalidated soonest
if the move has already run.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alpha_beta import BPY, OURS_STOP, OURS_TAKE  # noqa: E402
from maximize import newest_snapshot  # noqa: E402

CAPITAL = 100_000_000.0        # 100m IRT, the engine's own starting balance
SHORTS = ["CVXIRT", "DOGSIRT", "XAUTIRT", "TRXIRT", "USDTIRT"]
LONGS = ["ZECIRT", "BTCIRT", "ARBIRT", "ETHIRT", "PENDLEIRT"]


def money(v: float) -> str:
    return f"{v:,.0f}"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("alloc_out")
    out.mkdir(parents=True, exist_ok=True)
    snap = newest_snapshot()
    man = json.loads((snap / "manifest.json").read_text())
    lev = float(man["venue_leverage_cap"])
    stats = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 else []
    by_sym = {r["symbol"]: r for r in stats}

    info = {}
    for s in SHORTS + LONGS:
        d = pd.read_csv(snap / f"{s}.csv.gz", index_col=0, parse_dates=True)
        r = d["close"].pct_change().dropna()
        ema_fast = d["close"].ewm(span=10, adjust=False).mean()
        info[s] = {"price": float(d["close"].iloc[-1]),
                   "vol_ann": float(r.std(ddof=1) * math.sqrt(BPY)),
                   "ema_fast": float(ema_fast.iloc[-1]),
                   "beta": float(by_sym.get(s, {}).get(
                       "short_beta" if s in SHORTS else "long_beta", float("nan")))}

    def inv_vol(names):
        w = {n: 1.0 / info[n]["vol_ann"] for n in names if info[n]["vol_ann"] > 1e-9}
        t = sum(w.values())
        return {n: v / t for n, v in w.items()}

    ws, wl = inv_vol(SHORTS), inv_vol(LONGS)
    beta_s = sum(ws[n] * info[n]["beta"] for n in ws)   # already negative
    beta_l = sum(wl[n] * info[n]["beta"] for n in wl)

    # Scale the sides so the betas cancel. The long book is the smaller lever
    # here only because the short book's beta is weak, so it takes more short
    # notional to offset a unit of long.
    k = abs(beta_l / beta_s) if abs(beta_s) > 1e-9 else 1.0
    gross_l, gross_s = 1.0 / (1.0 + k), k / (1.0 + k)
    net_beta = gross_l * beta_l + gross_s * beta_s

    L = [f"\n===== WEIGHTS AND ENTRIES — {lev:g}x, capital {money(CAPITAL)} IRT =====",
         f"last bar {pd.read_csv(snap / 'BTCIRT.csv.gz', index_col=0).index[-1]}",
         "",
         f"long book beta {beta_l:+.2f}, short book beta {beta_s:+.2f}",
         f"-> {gross_l:.0%} of capital long, {gross_s:.0%} short "
         f"leaves net beta {net_beta:+.3f}",
         f"total exposure at {lev:g}x = {money(CAPITAL*lev)} IRT",
         ""]

    rows = []
    for side, names, w, gross in (("SHORT", SHORTS, ws, gross_s),
                                  ("LONG", LONGS, wl, gross_l)):
        L += [f"\n## {side}\n",
              "| symbol | weight | capital (IRT) | notional at "
              f"{lev:g}x | entry now | limit (fast EMA) | stop | target "
              "| ann vol | beta |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for n in names:
            if n not in w:
                continue
            cap = CAPITAL * gross * w[n]
            p, e = info[n]["price"], info[n]["ema_fast"]
            if side == "SHORT":
                stop, tgt = p * (1 + OURS_STOP), p * (1 - OURS_TAKE)
            else:
                stop, tgt = p * (1 - OURS_STOP), p * (1 + OURS_TAKE)
            rows.append({"side": side, "symbol": n, "weight_in_side": w[n],
                         "capital": cap, "notional": cap * lev, "price": p,
                         "limit": e, "stop": stop, "target": tgt,
                         "vol_ann": info[n]["vol_ann"], "beta": info[n]["beta"]})
            L.append(f"| **{n}** | {w[n]*100:.1f}% | {money(cap)} "
                     f"| {money(cap*lev)} | {money(p)} | {money(e)} "
                     f"| {money(stop)} | {money(tgt)} "
                     f"| {info[n]['vol_ann']*100:.0f}% | {info[n]['beta']:+.2f} |")

    worst = CAPITAL * lev * OURS_STOP
    L += ["\n\n## What the book risks\n",
          f"- every position stopped out at once: −{money(worst)} IRT "
          f"({lev*OURS_STOP*100:.0f}% of capital)",
          f"- one position stopped out: −{lev*OURS_STOP*100:.0f}% of ITS capital, "
          f"which is {lev*OURS_STOP*100/len(rows):.1f}% of the book per name on average",
          f"- both sides cannot stop out together unless the market gaps, since "
          f"they carry opposite signs; that is what the {net_beta:+.3f} net beta buys"]

    text = "\n".join(L)
    (out / "ALLOCATION.md").write_text(text + "\n")
    (out / "allocation.json").write_text(json.dumps(
        {"net_beta": net_beta, "gross_long": gross_l, "gross_short": gross_s,
         "leverage": lev, "capital": CAPITAL, "positions": rows}, indent=2))
    print(text)


if __name__ == "__main__":
    main()
