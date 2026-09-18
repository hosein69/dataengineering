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

    symbols, src = load_symbols()
    fee, fee_src = load_fee()
    cap, cap_src = load_lev_cap()
    print(f"universe: {len(symbols)} ({src})")
    print(f"fee {fee:.4%}/side ({fee_src}); venue cap {cap:g}x ({cap_src})")

    kept, skipped = [], []
    for s in symbols:
        try:
            df = fetch_raw(s, RESOLUTION, LOOKBACK_DAYS)
            cov = df.attrs["coverage"]
            if cov["coverage_ratio"] < MIN_COVERAGE:
                skipped.append({"symbol": s, "why": f"coverage {cov['coverage_ratio']:.0%}"})
                continue
            df.to_csv(out / f"{s}.csv.gz", compression="gzip")
            kept.append({"symbol": s, **cov})
            print(f"  {s}: {cov['delivered_bars']} bars, "
                  f"{cov['coverage_ratio']:.0%} over {cov['actual_span_days']:.1f}d")
        except Exception as exc:  # noqa: BLE001
            skipped.append({"symbol": s, "why": f"{type(exc).__name__}: {exc}"})
            print(f"  {s}: FAILED {type(exc).__name__}: {exc}", file=sys.stderr)

    manifest = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
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
