#!/usr/bin/env python3
"""Find out empirically which Toman pairs Nobitex will actually serve.

Every watchlist in this project scanned a symbol list typed by hand. That is a
selection bug that produces no error: a symbol nobody thought of is absent from
the results in exactly the same way as one that was scanned and rejected, so
absence carried no information. ZEC was never in any list.

A first attempt asked api.nobitex.ir for its market list. That host does not
resolve from a GitHub runner — only apiv2.nobitex.ir, the UDF host this project
already uses, does. So discovery is done against the host that works: probe a
broad ticker set with one cheap request each, keep whatever answers, and only
then measure history coverage for the survivors.

The ticker set is still written down rather than enumerated, but every entry is
verified against the venue, and the point is to be wide enough that the answer
to "is X missing because it is bad, or because nobody asked?" is always the
former.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nobitex_leveraged_backtest import NOBITEX, fetch_raw  # noqa: E402

PREVIOUSLY_SCANNED = {
    "BTCIRT", "ETHIRT", "SOLIRT", "XRPIRT", "DOGEIRT", "ADAIRT", "TRXIRT",
    "LTCIRT", "BNBIRT", "USDTIRT", "DOTIRT", "AVAXIRT", "SHIBIRT", "LINKIRT",
    "ATOMIRT",
}

TICKERS = [
    # majors / previously scanned
    "BTC", "ETH", "USDT", "USDC", "BNB", "XRP", "ADA", "DOGE", "SOL", "TRX",
    "DOT", "LTC", "SHIB", "AVAX", "LINK", "ATOM", "MATIC", "UNI",
    # privacy — the family ZEC belongs to, and the reason this script exists
    "ZEC", "XMR", "DASH",
    # large/mid caps plausibly listed on an Iranian venue
    "BCH", "ETC", "XLM", "FIL", "NEAR", "APT", "ARB", "OP", "INJ", "SUI",
    "TON", "ICP", "HBAR", "ALGO", "VET", "EGLD", "FTM", "THETA", "EOS", "XTZ",
    "NEO", "IOTA", "WAVES", "ZIL", "QNT", "IMX", "FLOW", "GRT", "AAVE", "MKR",
    "CRV", "COMP", "SNX", "YFI", "SUSHI", "BAT", "ENJ", "CHZ", "AXS", "SAND",
    "MANA", "APE", "GMT", "GAL", "LDO", "ENS", "MASK", "BLUR", "PEPE", "FLOKI",
    "1M_PEPE", "1B_BABYDOGE", "100K_FLOKI", "PAXG", "DAI", "WLD", "SEI", "STRK",
    "NOT", "BOME", "JUP", "PYTH", "TIA", "RNDR", "FET", "AGIX", "OCEAN",
]

RESOLUTION = "240"
LOOKBACK_DAYS = 180
MIN_COVERAGE = 0.80
PROBE_SLEEP = 0.25


def listed(symbol: str) -> tuple[bool, str]:
    """One cheap request: does the venue serve any recent candles for this pair?"""
    now = int(datetime.now(timezone.utc).timestamp())
    try:
        r = requests.get(NOBITEX, params={
            "symbol": symbol, "resolution": "240",
            "from": now - 7 * 86400, "to": now, "page": 1}, timeout=20)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        payload = r.json()
        status = payload.get("s")
        if status == "ok" and payload.get("t"):
            return True, f"{len(payload['t'])} recent bars"
        return False, str(status)
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("universe_out")
    out.mkdir(parents=True, exist_ok=True)

    symbols = [f"{t}IRT" for t in TICKERS]
    print(f"probing {len(symbols)} candidate Toman pairs against {NOBITEX}\n")

    live, dead = [], []
    for sym in symbols:
        ok, why = listed(sym)
        (live if ok else dead).append((sym, why))
        time.sleep(PROBE_SLEEP)

    print(f"listed and serving candles: {len(live)}")
    print(f"no data: {len(dead)}\n")

    usable, thin = [], []
    for sym, _ in live:
        try:
            raw = fetch_raw(sym, RESOLUTION, LOOKBACK_DAYS)
            cov = raw.attrs["coverage"]
            row = {"symbol": sym, "bars": cov["delivered_bars"],
                   "coverage": cov["coverage_ratio"],
                   "span_days": cov["actual_span_days"],
                   "new": sym not in PREVIOUSLY_SCANNED}
            (usable if cov["coverage_ratio"] >= MIN_COVERAGE else thin).append(row)
        except Exception as exc:  # noqa: BLE001
            thin.append({"symbol": sym, "error": f"{type(exc).__name__}: {exc}",
                         "new": sym not in PREVIOUSLY_SCANNED})

    usable.sort(key=lambda r: r["symbol"])
    newly = [r for r in usable if r["new"]]

    print(f"usable over {LOOKBACK_DAYS}d @ {RESOLUTION}m: {len(usable)}")
    print(f"NEVER SCANNED BEFORE but perfectly tradeable: {len(newly)}\n")
    print("| symbol | bars | coverage | span (d) | missed by the old hand-written list? |")
    print("|---|---:|---:|---:|:--:|")
    for r in usable:
        print(f"| {r['symbol']} | {r['bars']} | {r['coverage']:.0%} "
              f"| {r['span_days']:.1f} | {'**YES**' if r['new'] else 'no'} |")

    if thin:
        print("\n### listed but not enough history\n")
        for r in thin:
            why = r.get("error") or f"coverage {r.get('coverage', 0):.0%}"
            print(f"- {r['symbol']}: {why}")

    print("\n### ZECIRT verdict\n")
    z_live = next((w for s, w in live if s == "ZECIRT"), None)
    z_use = next((r for r in usable if r["symbol"] == "ZECIRT"), None)
    z_thin = next((r for r in thin if r["symbol"] == "ZECIRT"), None)
    if z_use:
        print(f"ZECIRT IS listed and fully usable: {z_use['bars']} bars, "
              f"{z_use['coverage']:.0%} coverage over {z_use['span_days']:.1f} days.")
        print("It was absent purely because it was never in the scan list.")
    elif z_thin:
        print(f"ZECIRT is listed but history is short: {z_thin}")
    elif z_live:
        print(f"ZECIRT responds ({z_live}) but failed the coverage fetch.")
    else:
        why = next((w for s, w in dead if s == "ZECIRT"), "not probed")
        print(f"ZECIRT is NOT served by the venue's history endpoint ({why}).")
        print("In that case its absence from the watchlist was correct, not a bug.")

    (out / "universe.json").write_text(json.dumps(
        {"usable": usable, "thin": thin,
         "dead": [{"symbol": s, "why": w} for s, w in dead]}, indent=2))


if __name__ == "__main__":
    main()
