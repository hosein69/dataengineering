#!/usr/bin/env python3
"""How much history does the Nobitex UDF endpoint actually retain per resolution?

The fixed backtester refused a 30-day 15m request because only 22.9% of the
expected bars came back. That is either a client bug or an exchange retention
limit, and the two need separating before anyone tunes a strategy around it.

Requests the same calendar window at every supported resolution, with the same
chunked fetch the backtester uses, and reports what the server actually served.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nobitex_leveraged_backtest import RESOLUTION_SECONDS, fetch_raw  # noqa: E402

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "BTCIRT"
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("retention_probe.json")

rows = []
for res in ["1", "5", "15", "30", "60", "180", "240", "360", "720", "D"]:
    step = RESOLUTION_SECONDS[res]
    expected = (DAYS * 86400) // step
    try:
        df = fetch_raw(SYMBOL, res, DAYS)
        cov = df.attrs["coverage"]
        oldest = df.index[0]
        age_days = (datetime.now(timezone.utc) - oldest.to_pydatetime()).total_seconds() / 86400
        rows.append({
            "resolution": res,
            "expected_bars": int(expected),
            "delivered_bars": cov["delivered_bars"],
            "coverage": cov["coverage_ratio"],
            "span_days": cov["actual_span_days"],
            "oldest_bar": oldest.isoformat(),
            "retention_days": round(age_days, 2),
            "requests": cov["pages_walked"],
            "covers_window": cov["coverage_ratio"] >= 0.80,
        })
    except Exception as exc:  # noqa: BLE001
        rows.append({"resolution": res, "expected_bars": int(expected),
                     "error": f"{type(exc).__name__}: {exc}"})

print(f"\n===== Nobitex history retention probe: {SYMBOL}, {DAYS}-day window =====\n")
print("| resolution | expected | delivered | coverage | span (d) | retention (d) | covers 30d? |")
print("|---|---:|---:|---:|---:|---:|:--:|")
for r in rows:
    if "error" in r:
        print(f"| {r['resolution']} | {r['expected_bars']} | — | — | — | — | ERROR |")
        continue
    print(f"| {r['resolution']} | {r['expected_bars']} | {r['delivered_bars']} "
          f"| {r['coverage']:.1%} | {r['span_days']:.2f} | {r['retention_days']:.2f} "
          f"| {'YES' if r['covers_window'] else 'no'} |")

errs = [r for r in rows if "error" in r]
if errs:
    print("\nerrors:")
    for r in errs:
        print(f"- res={r['resolution']}: {r['error']}")

usable = [r for r in rows if not r.get("error") and r.get("covers_window")]
print(f"\nresolutions that actually cover a {DAYS}-day window: "
      f"{[r['resolution'] for r in usable] or 'NONE'}")

OUT.write_text(json.dumps({"symbol": SYMBOL, "window_days": DAYS, "rows": rows},
                          indent=2, default=str))
