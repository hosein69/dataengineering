#!/usr/bin/env python3
"""Discover which Toman pairs Nobitex actually lists, instead of guessing.

Every watchlist in this project so far scanned a hand-written symbol list. That
is a selection bug with no error message: a symbol nobody thought of is absent
from the results in exactly the same way as a symbol that was scanned and
failed, so absence carried no information. ZEC was never in either list.

This enumerates the venue's own market list, then checks which of those pairs
the UDF history endpoint will actually serve over the study window, and reports
the three categories apart: listed and usable, listed but no usable history,
and never-considered-before symbols that turn out to be tradeable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nobitex_leveraged_backtest import fetch_raw  # noqa: E402

# Symbols the project scanned before this script existed.
PREVIOUSLY_SCANNED = {
    "BTCIRT", "ETHIRT", "SOLIRT", "XRPIRT", "DOGEIRT", "ADAIRT", "TRXIRT",
    "LTCIRT", "BNBIRT", "USDTIRT", "DOTIRT", "AVAXIRT", "SHIBIRT", "LINKIRT",
    "ATOMIRT",
}

RESOLUTION = "240"
LOOKBACK_DAYS = 180
MIN_COVERAGE = 0.80

DISCOVERY_ENDPOINTS = [
    ("v3/orderbook/all", "https://api.nobitex.ir/v3/orderbook/all"),
    ("v2/options", "https://api.nobitex.ir/v2/options"),
]


def discover() -> tuple[list[str], str]:
    """Return (IRT symbols, which endpoint produced them)."""
    for name, url in DISCOVERY_ENDPOINTS:
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            payload = r.json()
        except Exception as exc:  # noqa: BLE001
            print(f"discovery via {name} failed: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            continue

        found: set[str] = set()
        # orderbook/all: top-level keys are symbols such as "BTCIRT".
        for key in payload if isinstance(payload, dict) else []:
            k = str(key).upper()
            if k.endswith("IRT") and k != "IRT":
                found.add(k)
        # v2/options: nested currency lists.
        if not found and isinstance(payload, dict):
            for container in ("nobitex", "amounts", "coins"):
                block = payload.get(container)
                if isinstance(block, dict):
                    for key in block:
                        k = str(key).upper()
                        if k.endswith("IRT") and k != "IRT":
                            found.add(k)
                elif isinstance(block, list):
                    for item in block:
                        k = f"{str(item).upper()}IRT"
                        found.add(k)
        if found:
            return sorted(found), name
    return [], "none"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("universe_out")
    out.mkdir(parents=True, exist_ok=True)

    symbols, source = discover()
    print(f"\ndiscovery endpoint: {source}")
    print(f"IRT pairs listed by Nobitex: {len(symbols)}")
    if not symbols:
        print("could not enumerate the venue's markets", file=sys.stderr)
        sys.exit(1)

    # Always check ZEC explicitly — it is the symbol that exposed the bug.
    for extra in ("ZECIRT",):
        if extra not in symbols:
            print(f"note: {extra} not in the discovered list; probing anyway")
            symbols.append(extra)

    usable, unusable = [], []
    for sym in symbols:
        try:
            raw = fetch_raw(sym, RESOLUTION, LOOKBACK_DAYS)
            cov = raw.attrs["coverage"]
            row = {
                "symbol": sym,
                "bars": cov["delivered_bars"],
                "coverage": cov["coverage_ratio"],
                "span_days": cov["actual_span_days"],
                "new_to_project": sym not in PREVIOUSLY_SCANNED,
            }
            (usable if cov["coverage_ratio"] >= MIN_COVERAGE else unusable).append(row)
        except Exception as exc:  # noqa: BLE001
            unusable.append({"symbol": sym, "error": f"{type(exc).__name__}: {exc}",
                             "new_to_project": sym not in PREVIOUSLY_SCANNED})

    usable.sort(key=lambda r: r["symbol"])
    newly = [r for r in usable if r["new_to_project"]]

    print(f"\nusable over {LOOKBACK_DAYS}d @ {RESOLUTION}m: {len(usable)}")
    print(f"not usable: {len(unusable)}")
    print(f"NEVER SCANNED BEFORE but usable: {len(newly)}\n")

    print("| symbol | bars | coverage | span (d) | new to this project? |")
    print("|---|---:|---:|---:|:--:|")
    for r in usable:
        print(f"| {r['symbol']} | {r['bars']} | {r['coverage']:.0%} "
              f"| {r['span_days']:.1f} | {'**YES**' if r['new_to_project'] else 'no'} |")

    if unusable:
        print("\n### not usable\n")
        for r in unusable:
            why = r.get("error") or f"coverage {r.get('coverage', 0):.0%}"
            print(f"- {r['symbol']}: {why}")

    zec = next((r for r in usable + unusable if r["symbol"] == "ZECIRT"), None)
    print("\n### ZECIRT verdict\n")
    if zec is None:
        print("ZECIRT: not returned by discovery and not probed.")
    elif "error" in zec:
        print(f"ZECIRT: listed? {'ZECIRT' in symbols}. No usable history — {zec['error']}")
    else:
        print(f"ZECIRT: tradeable, {zec['bars']} bars, {zec['coverage']:.0%} coverage "
              f"over {zec['span_days']:.1f} days. It was simply never in the scan list.")

    (out / "universe.json").write_text(json.dumps(
        {"source": source, "usable": usable, "unusable": unusable}, indent=2))


if __name__ == "__main__":
    main()
