#!/usr/bin/env python3
"""Fetch the margin universe once and write it down, so nothing needs the venue again.

Every parameter search so far has re-fetched the same 180 days from a venue
that rate-limits at 60 requests a minute and throttles by stalling connections.
That put the slowest, least reliable component in the inner loop of the fastest,
most repeated one, and two runs died of it.

Separating acquisition from computation fixes that permanently. This writes the
history to disk once; the search then reads local files, runs in seconds instead
of tens of minutes, can be iterated on without limit, and — because the data is
pinned — produces the same answer every time it is asked. A snapshot is dated,
so refreshing is a deliberate act rather than a side effect of every run.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd  # noqa: E402

from nobitex_leveraged_backtest import fetch_raw  # noqa: E402
from watchlist_compare import (  # noqa: E402
    LOOKBACK_DAYS, RESOLUTION, load_fee, load_lev_cap, load_symbols,
)

MIN_COVERAGE = 0.80


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data_snapshot")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = root / day
    out.mkdir(parents=True, exist_ok=True)

    # The margin list is the default universe, but spot lists far more, so an
    # explicit set can be requested — a spot-only name is invisible otherwise.
    extra = [x for x in (sys.argv[2].split(",") if len(sys.argv) > 2 else []) if x]
    if extra:
        symbols, src = extra, "named on the command line"
    else:
        symbols, src = load_symbols()
    fee, fee_src = load_fee()
    cap, cap_src = load_lev_cap()
    print(f"universe: {len(symbols)} ({src})")
    print(f"fee {fee:.4%}/side ({fee_src}); venue cap {cap:g}x ({cap_src})")

    # Resume rather than restart. Capturing 60+ symbols from a throttled venue
    # takes half an hour, and this used to be all-or-nothing: a single failure
    # at the end discarded every symbol already fetched, which cost three full
    # captures before the data landed. A symbol already on disk is skipped, so
    # a re-run only pays for what is missing.
    kept, skipped = [], []
    for s in symbols:
        target = out / f"{s}.csv.gz"
        if target.exists() and target.stat().st_size > 0:
            try:
                have = pd.read_csv(target, index_col=0, parse_dates=True)
                if len(have) > 50:
                    span = (have.index[-1] - have.index[0]).total_seconds() / 86400
                    kept.append({"symbol": s, "requested_days": LOOKBACK_DAYS,
                                 "expected_bars": len(have), "delivered_bars": len(have),
                                 "coverage_ratio": 1.0, "pages_walked": 0,
                                 "actual_span_days": round(span, 3), "resumed": True})
                    print(f"  {s}: already captured ({len(have)} bars), skipping")
                    continue
            except Exception:  # noqa: BLE001
                pass          # unreadable file: fall through and refetch
        try:
            df = fetch_raw(s, RESOLUTION, LOOKBACK_DAYS)
            cov = df.attrs["coverage"]
            if cov["coverage_ratio"] < MIN_COVERAGE and not extra:
                skipped.append({"symbol": s, "why": f"coverage {cov['coverage_ratio']:.0%}"})
                continue
            if cov["coverage_ratio"] < MIN_COVERAGE:
                print(f"  {s}: only {cov['coverage_ratio']:.0%} coverage "
                      f"({cov['delivered_bars']} bars) — kept because it was "
                      f"asked for by name", file=sys.stderr)
            df.to_csv(out / f"{s}.csv.gz", compression="gzip")
            kept.append({"symbol": s, **cov})
            print(f"  {s}: {cov['delivered_bars']} bars, "
                  f"{cov['coverage_ratio']:.0%} over {cov['actual_span_days']:.1f}d")
        except Exception as exc:  # noqa: BLE001
            skipped.append({"symbol": s, "why": f"{type(exc).__name__}: {exc}"})
            print(f"  {s}: FAILED {type(exc).__name__}: {exc}", file=sys.stderr)

    # Named symbols extend the snapshot; they must not replace its record of
    # what is already captured. Writing a fresh manifest for a two-symbol run
    # erased the entry for all 63 already on disk, leaving the CSVs orphaned.
    mf = out / "manifest.json"
    if extra and mf.exists():
        prev = json.loads(mf.read_text())
        have = {r["symbol"] for r in kept}
        kept = [r for r in prev.get("symbols", []) if r["symbol"] not in have] + kept
        prev_skip = {r["symbol"] for r in skipped}
        skipped = [r for r in prev.get("skipped", []) if r["symbol"] not in prev_skip] + skipped

    manifest = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "complete": len(skipped) == 0,
        "resolution": RESOLUTION, "lookback_days": LOOKBACK_DAYS,
        "universe_source": src, "fee_per_side": fee, "fee_source": fee_src,
        "venue_leverage_cap": cap, "cap_source": cap_src,
        "symbols": kept, "skipped": skipped,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nsnapshot {day}: {len(kept)} symbols written, {len(skipped)} skipped")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
