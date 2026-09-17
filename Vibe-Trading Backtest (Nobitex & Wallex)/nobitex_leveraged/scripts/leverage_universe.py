#!/usr/bin/env python3
"""Ask the venue which pairs can actually be traded with leverage.

The universe filter asked only whether Nobitex serves candles for a pair. That
is spot availability, and it is not the question this project needs: every
watchlist here sizes a LEVERAGED position, and a pair with a perfect 180-day
candle history may still have no margin market at all. EGLDIRT is exactly that
case — it cleared the old filter and should never have been quoted.

So probe the margin endpoints and keep only what they list. Nobitex has moved
this path around between API versions, so try the known spellings and report
which one answered, rather than hardcoding one and silently getting nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

BASE = "https://apiv2.nobitex.ir"
CANDIDATES = [
    f"{BASE}/margin/markets/list",
    f"{BASE}/margin/markets",
    f"{BASE}/v2/margin/markets/list",
    f"{BASE}/v2/options",
]


def fetch(url: str) -> tuple[bool, object, str]:
    try:
        r = requests.get(url, timeout=25)
        if r.status_code != 200:
            return False, None, f"HTTP {r.status_code}"
        return True, r.json(), "ok"
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


def symbols_from(payload: object) -> set[str]:
    """Pull every *IRT pair name out of whatever shape the endpoint returned."""
    found: set[str] = set()

    def walk(node, key_hint: str = ""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, str(k))
        elif isinstance(node, list):
            for v in node:
                walk(v, key_hint)
        elif isinstance(node, str):
            s = node.replace("-", "").replace("/", "").upper()
            if s.endswith("IRT") and 5 <= len(s) <= 20:
                found.add(s)

    walk(payload)
    # Keys themselves can carry the pair name (e.g. {"BTCIRT": {...}}).
    if isinstance(payload, dict):
        for k in payload:
            s = str(k).replace("-", "").replace("/", "").upper()
            if s.endswith("IRT"):
                found.add(s)
    return found


def leverage_map(payload: object) -> dict[str, float]:
    """Pull per-pair max leverage where the endpoint carries it.

    The venue caps leverage per market, so the cap is data to be read, never a
    number to remember. Shapes differ between endpoints, so look for any object
    that names a pair and carries a leverage-ish field beside it.
    """
    caps: dict[str, float] = {}
    lev_keys = ("maxleverage", "leverage", "maxlev")

    def pair_of(node: dict) -> str | None:
        for k in ("symbol", "market", "name", "pair"):
            v = node.get(k)
            if isinstance(v, str):
                s = v.replace("-", "").replace("/", "").upper()
                if s.endswith("IRT"):
                    return s
        src, dst = node.get("src"), node.get("dst")
        if isinstance(src, str) and isinstance(dst, str):
            s = f"{src}{dst}".replace("-", "").upper()
            if s.endswith("IRT"):
                return s
        return None

    def walk(node):
        if isinstance(node, dict):
            sym = pair_of(node)
            if sym:
                for k, v in node.items():
                    if str(k).lower().replace("_", "") in lev_keys:
                        try:
                            caps[sym] = max(caps.get(sym, 0.0), float(v))
                        except (TypeError, ValueError):
                            pass
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload)
    return caps


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("universe_out")
    out.mkdir(parents=True, exist_ok=True)

    report: list[dict] = []
    margin: set[str] = set()
    caps: dict[str, float] = {}
    answered = None
    for url in CANDIDATES:
        ok, payload, why = fetch(url)
        syms = symbols_from(payload) if ok else set()
        report.append({"url": url, "ok": ok, "why": why, "irt_pairs_seen": len(syms)})
        print(f"{url} -> {why}, {len(syms)} IRT pairs")
        if ok and syms and answered is None:
            answered, margin = url, syms
            caps = leverage_map(payload)

    if answered is None:
        print("\nNo margin endpoint answered. NOT falling back to the spot "
              "universe: that is the very conflation this script exists to stop.")
        (out / "leverage.json").write_text(json.dumps(
            {"resolved": False, "probes": report, "margin_symbols": []}, indent=2))
        return

    print(f"\nmargin universe resolved from {answered}: {len(margin)} pairs")
    if caps:
        print(f"per-pair leverage caps reported for {len(caps)} pairs; "
              f"observed range {min(caps.values()):g}x - {max(caps.values()):g}x")
        for sym in sorted(caps, key=lambda k: (-caps[k], k)):
            print(f"  {sym}: max {caps[sym]:g}x")
    else:
        print("endpoint carried no per-pair leverage cap; "
              "treating membership alone as the signal")

    spot_path = out / "universe.json"
    if spot_path.exists():
        spot = {r["symbol"] for r in json.loads(spot_path.read_text()).get("usable", [])}
        both = sorted(spot & margin)
        spot_only = sorted(spot - margin)
        print(f"\nspot-usable: {len(spot)}   margin-listed: {len(margin)}   "
              f"BOTH (the real tradeable universe): {len(both)}")
        print(f"\n### spot-usable but NOT leverageable — {len(spot_only)} symbols "
              f"that the old filter would have quoted anyway\n")
        print(", ".join(spot_only) if spot_only else "(none)")
        for probe in ("EGLDIRT", "LDOIRT", "ZECIRT"):
            verdict = "leverageable" if probe in margin else "NOT leverageable"
            print(f"\n{probe}: {verdict}")
    else:
        both, spot_only = sorted(margin), []

    (out / "leverage.json").write_text(json.dumps(
        {"resolved": True, "source": answered, "probes": report,
         "margin_symbols": sorted(margin), "leverage_caps": caps, "tradeable": both,
         "spot_only": spot_only}, indent=2))


if __name__ == "__main__":
    main()
