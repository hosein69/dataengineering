#!/usr/bin/env python3
"""Full workup on the five long candidates, in USDT.

Four questions, each answered from the 1080 bars and their volume rather than
from anything external, since on-chain data is not available here.

TECHNICAL: where price sits relative to its own trend and range.

CAUSALITY: lagged cross-correlation against the market decides whether a
symbol leads it or follows it. A follower's alpha is mostly the market arriving
late and will not survive the market turning; a leader's might.

HISTORY: the same three phases, per symbol. The middle phase is the only time
this market fell, so how each name behaved in it is the single most informative
number available — a symbol that held up when everything dropped has shown
something that 180 days of rising price cannot.

BUYER BEHAVIOUR: volume is the only footprint of size available here. Whether
volume concentrates on up bars or down bars separates accumulation from
distribution; volume rising while price stalls is absorption; and the largest
bars say which side was willing to be aggressive.
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
FIVE = ["ZECIRT", "ARBIRT", "BICOIRT", "NEARIRT", "UNIIRT"]
PHASES = 3


def load():
    snap = newest_snapshot()
    px, vol = {}, {}
    for f in sorted(snap.glob("*.csv.gz")):
        s = f.name.replace(".csv.gz", "")
        d = pd.read_csv(f, index_col=0, parse_dates=True)
        px[s], vol[s] = d["close"], d.get("volume")
    P = pd.DataFrame(px).sort_index().ffill()
    V = pd.DataFrame({k: v for k, v in vol.items() if v is not None}).sort_index()
    rial = P[RIAL]
    U = P.div(rial, axis=0).drop(columns=[RIAL])
    return U, V, P


def main() -> None:
    U, V, P = load()
    mkt = U.pct_change().mean(axis=1).dropna()
    cuts = np.array_split(np.arange(len(U)), PHASES)

    print(f"window {U.index[0]:%Y-%m-%d} -> {U.index[-1]:%Y-%m-%d}, "
          f"{len(U)} bars, all prices in USDT\n")

    # ---------- 1. technical ----------
    print("## 1. TECHNICAL — where price sits in its own trend\n")
    print("| symbol | vs EMA10 | vs EMA30 | 180d high | 180d low | in range "
          "| from peak | 7d | 30d | ATR% |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in FIVE:
        p = U[s].dropna()
        e10 = p.ewm(span=10, adjust=False).mean().iloc[-1]
        e30 = p.ewm(span=30, adjust=False).mean().iloc[-1]
        hi, lo, last = p.max(), p.min(), p.iloc[-1]
        rng = (last - lo) / (hi - lo) if hi > lo else float("nan")
        r = p.pct_change()
        atr = float(r.rolling(14).std().iloc[-1] * 100)
        d7 = last / p.iloc[-42] - 1 if len(p) > 42 else float("nan")
        d30 = last / p.iloc[-180] - 1 if len(p) > 180 else float("nan")
        print(f"| **{s}** | {(last/e10-1)*100:+.1f}% | {(last/e30-1)*100:+.1f}% "
              f"| {(last/hi-1)*100:+.1f}% | {(last/lo-1)*100:+.0f}% "
              f"| {rng*100:.0f}% | {(last/hi-1)*100:.1f}% "
              f"| {d7*100:+.1f}% | {d30*100:+.1f}% | {atr:.1f}% |")

    # ---------- 2. causality ----------
    print("\n\n## 2. CAUSALITY — does the market lead it, or does it lead the market\n")
    print("| symbol | best lag | corr at best | corr same-bar | reading |")
    print("|---|---:|---:|---:|---|")
    for s in FIVE:
        r = U[s].pct_change().dropna()
        j = pd.concat([r, mkt], axis=1).dropna()
        a, b = j.iloc[:, 0], j.iloc[:, 1]
        best, bl = -9, 0
        for k in range(-6, 7):
            c = a.corr(b.shift(k))
            if np.isfinite(c) and c > best:
                best, bl = c, k
        same = a.corr(b)
        if bl > 0:
            read = f"market leads by {bl} bars -> it FOLLOWS"
        elif bl < 0:
            read = f"it leads market by {-bl} bars -> it LEADS"
        else:
            read = "moves with the market, no lead either way"
        print(f"| **{s}** | {bl:+d} | {best:.3f} | {same:.3f} | {read} |")

    # ---------- 3. history by phase ----------
    print("\n\n## 3. HISTORY — how each behaved in the three phases (USDT)\n")
    print("| symbol | P1 Mar-May | **P2 May-Jul (market fell)** | P3 Jul-Sep (now) "
          "| worst DD | P2 vs market |")
    print("|---|---:|---:|---:|---:|---:|")
    for s in FIVE:
        p = U[s]
        cells, p2rel = [], float("nan")
        for i, idx in enumerate(cuts):
            sub = p.iloc[idx].dropna()
            ret = float(sub.iloc[-1] / sub.iloc[0] - 1) if len(sub) > 2 else float("nan")
            cells.append(ret)
            if i == 1:
                msub = (1 + mkt.iloc[idx]).prod() - 1
                p2rel = ret - float(msub)
        eq = p / p.iloc[0]
        dd = float((eq / eq.cummax() - 1).min())
        print(f"| **{s}** | {cells[0]*100:+.1f}% | **{cells[1]*100:+.1f}%** "
              f"| {cells[2]*100:+.1f}% | {dd*100:.1f}% | {p2rel*100:+.1f}% |")

    # ---------- 4. volume / who is buying ----------
    print("\n\n## 4. BUYER BEHAVIOUR — what the volume footprint shows\n")
    print("| symbol | up-vol / down-vol | vol trend 30d | biggest bar | "
          "price-vol corr | reading |")
    print("|---|---:|---:|---:|---:|---|")
    for s in FIVE:
        if s not in V:
            continue
        v = V[s].reindex(U.index).astype(float)
        r = U[s].pct_change()
        j = pd.concat([r, v], axis=1).dropna()
        j.columns = ["r", "v"]
        uv = j.loc[j.r > 0, "v"].mean()
        dv = j.loc[j.r < 0, "v"].mean()
        ratio = uv / dv if dv > 0 else float("nan")
        recent = j["v"].iloc[-180:].mean() / j["v"].iloc[:-180].mean()
        big = j.loc[j.v.nlargest(20).index]
        big_up = float((big.r > 0).mean())
        pvc = float(j["r"].abs().corr(j["v"]))
        if ratio > 1.15 and big_up > 0.55:
            read = "buyers aggressive — accumulation"
        elif ratio < 0.9:
            read = "sellers heavier — distribution"
        elif big_up < 0.45:
            read = "size shows up on down bars"
        else:
            read = "balanced"
        print(f"| **{s}** | {ratio:.2f} | {recent:.2f}x | {big_up*100:.0f}% up "
              f"| {pvc:+.2f} | {read} |")

    print("\n  up-vol/down-vol > 1 means more volume trades on rising bars.")
    print("  'biggest bar' is the share of the 20 highest-volume bars that were up.")
    print("  price-vol corr is |return| against volume: high means moves need volume,")
    print("  low means price drifts without participation.")


if __name__ == "__main__":
    main()
