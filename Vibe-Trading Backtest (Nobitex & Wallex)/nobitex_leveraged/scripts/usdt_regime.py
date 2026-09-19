#!/usr/bin/env python3
"""The same market seen in USDT, and now against its own earlier phases.

Pricing in rial mixes two moves: the crypto and the currency. Dividing every
pair by USDTIRT removes the second and leaves what a tether-denominated trader
actually experiences, which is the book most of these conclusions should have
been drawn in. The rial view is kept alongside so the difference is visible
rather than asserted.

Judging "now" needs something to judge it against, so the window is cut into
equal phases and each is measured the same way. A single number for 180 days
hides whether the market is doing what it did before or something new, and the
drift, the correlation and the mean reversion are the three that decide whether
a strategy family has any chance.
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


def describe(px: pd.DataFrame, label: str) -> dict:
    rets = px.pct_change().dropna(how="all")
    m = rets.mean(axis=1).dropna()
    if len(m) < 40:
        return {}
    eq = (1 + m).cumprod()
    c = rets.corr().to_numpy()
    iu = np.triu_indices_from(c, k=1)
    ac1 = [rets[s].autocorr(lag=1) for s in rets.columns]
    ac1 = [v for v in ac1 if np.isfinite(v)]
    up, dn = m[m > 0], m[m < 0]
    winners = int((px.iloc[-1] / px.iloc[0] - 1 > 0).sum())
    return {
        "label": label, "bars": len(m), "symbols": px.shape[1],
        "total": float(eq.iloc[-1] - 1),
        "drift_ann": float(m.mean() * BPY),
        "vol_ann": float(m.std(ddof=1) * math.sqrt(BPY)),
        "sharpe": float(m.mean() * BPY / (m.std(ddof=1) * math.sqrt(BPY)))
        if m.std(ddof=1) > 1e-12 else float("nan"),
        "max_dd": float((eq / eq.cummax() - 1).min()),
        "corr": float(np.nanmean(c[iu])),
        "ac1_median": float(np.median(ac1)),
        "ac1_neg_frac": float(sum(1 for v in ac1 if v < 0) / len(ac1)),
        "up_frac": float(len(up) / len(m)),
        "up_mean": float(up.mean()), "dn_mean": float(dn.mean()),
        "winners": winners, "winner_frac": winners / px.shape[1],
    }


def row(d: dict) -> str:
    return (f"| {d['label']} | {d['total']*100:+.1f}% | {d['drift_ann']*100:+.0f}% "
            f"| {d['vol_ann']*100:.0f}% | {d['sharpe']:.2f} | {d['max_dd']*100:.1f}% "
            f"| {d['corr']:.2f} | {d['ac1_median']:+.3f} | {d['ac1_neg_frac']*100:.0f}% "
            f"| {d['up_frac']*100:.1f}% | {d['winner_frac']*100:.0f}% |")


HDR = ("| phase | total | drift (ann) | vol | Sharpe | maxDD | corr "
       "| lag-1 AC | % AC<0 | % bars up | % symbols up |")
SEP = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"


def main() -> None:
    snap = newest_snapshot()
    close = {}
    for f in sorted(snap.glob("*.csv.gz")):
        close[f.name.replace(".csv.gz", "")] = pd.read_csv(
            f, index_col=0, parse_dates=True)["close"]
    px = pd.DataFrame(close).sort_index()
    px = px.loc[:, px.notna().sum() > len(px) * 0.8].ffill().dropna(how="all")

    irt = px.drop(columns=[RIAL])
    usd = px.div(px[RIAL], axis=0).drop(columns=[RIAL])

    print(f"window {px.index[0]:%Y-%m-%d} -> {px.index[-1]:%Y-%m-%d}, "
          f"{len(px)} bars, {irt.shape[1]} symbols")
    print(f"rial leg over the window: {float(px[RIAL].iloc[-1]/px[RIAL].iloc[0]-1)*100:+.1f}%\n")

    print("## whole window, both denominations\n")
    print(HDR); print(SEP)
    print(row(describe(irt, "in rial")))
    print(row(describe(usd, "**in USDT**")))

    cut = np.array_split(np.arange(len(px)), PHASES)
    for name, frame in (("in rial", irt), ("in USDT", usd)):
        print(f"\n## phases, {name}\n")
        print(HDR); print(SEP)
        for i, idx in enumerate(cut, 1):
            sub = frame.iloc[idx]
            lab = f"P{i}  {sub.index[0]:%b %d} - {sub.index[-1]:%b %d}"
            if i == PHASES:
                lab = f"**{lab} (now)**"
            d = describe(sub, lab)
            if d:
                print(row(d))

    # what a short pays in each denomination, which is the whole short question
    print("\n## the cost of being short, before any skill\n")
    for name, frame in (("rial", irt), ("USDT", usd)):
        m = frame.pct_change().mean(axis=1).dropna()
        print(f"  {name}: drift {m.mean()*BPY*100:+.0f}%/yr "
              f"-> a short pays {-m.mean()*BPY*100:+.0f}%/yr")
        for i, idx in enumerate(np.array_split(np.arange(len(frame)), PHASES), 1):
            mm = frame.iloc[idx].pct_change().mean(axis=1).dropna()
            tag = " (now)" if i == PHASES else ""
            print(f"     P{i}{tag}: {-mm.mean()*BPY*100:+.0f}%/yr")


if __name__ == "__main__":
    main()
