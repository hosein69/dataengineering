#!/usr/bin/env python3
"""Fetch the same coins from a global venue, to separate the coin from the venue.

A Nobitex series cannot answer whether a move belongs to the asset or to the
listing. The global price is the asset; the difference between the two is
everything local — the rial, the listing itself, and whatever premium a closed
market carries. Both are needed, and only one of them is in the snapshot.

Binance is used as the reference because its klines go back far past any
Nobitex listing date, which is the whole point: the comparison needs history
from before the local listing to see what the listing did.

This runs on a GitHub runner. The working environment reaches neither Nobitex
nor any global exchange, so both sides of the comparison have to be captured
here and committed.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://api.binance.com/api/v3/klines"
INTERVAL = "4h"
LIMIT = 1000
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
        "qav", "trades", "tbb", "tbq", "ignore"]


def fetch(symbol: str, days: int) -> pd.DataFrame | None:
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    start = end - days * 86400 * 1000
    frames, cursor = [], start
    for _ in range(20):
        try:
            r = requests.get(BASE, params={"symbol": symbol, "interval": INTERVAL,
                                           "startTime": cursor, "limit": LIMIT},
                             timeout=20)
            if r.status_code != 200:
                print(f"  {symbol}: HTTP {r.status_code} {r.text[:120]}", file=sys.stderr)
                return None
            rows = r.json()
        except Exception as exc:  # noqa: BLE001
            print(f"  {symbol}: {type(exc).__name__}", file=sys.stderr)
            return None
        if not rows:
            break
        frames.append(pd.DataFrame(rows, columns=COLS))
        nxt = int(rows[-1][0]) + 1
        if nxt <= cursor or nxt >= end:
            break
        cursor = nxt
        time.sleep(0.2)
    if not frames:
        return None
    df = pd.concat(frames, ignore_index=True).drop_duplicates("open_time")
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return (df[["timestamp", "open", "high", "low", "close", "volume"]]
            .dropna().set_index("timestamp").sort_index())


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("global_ref")
    syms = [s for s in (sys.argv[2].split(",") if len(sys.argv) > 2 else []) if s]
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 540
    out.mkdir(parents=True, exist_ok=True)
    if not syms:
        print("no symbols given", file=sys.stderr)
        return

    kept = []
    for s in syms:
        df = fetch(s, days)
        if df is None or df.empty:
            print(f"{s}: unavailable")
            continue
        df.to_csv(out / f"{s}.csv.gz", compression="gzip")
        span = (df.index[-1] - df.index[0]).total_seconds() / 86400
        kept.append({"symbol": s, "bars": len(df), "span_days": round(span, 1),
                     "first": str(df.index[0]), "last": str(df.index[-1])})
        print(f"{s}: {len(df)} bars, {span:.0f} days "
              f"({df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d})")

    (out / "manifest.json").write_text(json.dumps(
        {"source": "binance", "interval": INTERVAL,
         "captured_utc": datetime.now(timezone.utc).isoformat(),
         "symbols": kept}, indent=2))


if __name__ == "__main__":
    main()
