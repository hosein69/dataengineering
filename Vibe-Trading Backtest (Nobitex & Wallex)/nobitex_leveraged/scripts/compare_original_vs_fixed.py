#!/usr/bin/env python3
"""Print the original-vs-fixed comparison the debug is actually about.

The headline is not the P&L difference — it is that the two runs graded
different amounts of history while both being asked for the same window.
"""
import json
import sys
from pathlib import Path


def load(root: Path) -> dict:
    out = {}
    for p in sorted(root.glob("*_metrics.json")):
        try:
            m = json.loads(p.read_text())
            out[m.get("symbol", p.stem)] = m
        except Exception as exc:  # noqa: BLE001
            print(f"  ! unreadable {p.name}: {exc}", file=sys.stderr)
    for p in sorted(root.glob("*_ERROR.json")):
        try:
            e = json.loads(p.read_text())
            out.setdefault(e.get("symbol", p.stem), {"error": e.get("error")})
        except Exception:  # noqa: BLE001
            pass
    return out


def span_days(m: dict) -> str:
    cov = m.get("coverage")
    if isinstance(cov, dict) and cov.get("actual_span_days") is not None:
        return f"{cov['actual_span_days']:.2f}"
    start, end = m.get("data_start"), m.get("data_end")
    if start and end:
        from datetime import datetime
        d = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
        return f"{d/86400:.2f}"
    return "n/a"


def fmt(v, pct=False):
    if v is None:
        return "n/a"
    try:
        return f"{float(v)*100:.2f}%" if pct else f"{float(v):.3f}"
    except (TypeError, ValueError):
        return str(v)


def main() -> None:
    orig_dir, fixed_dir = Path(sys.argv[1]), Path(sys.argv[2])
    orig, fixed = load(orig_dir), load(fixed_dir)
    symbols = sorted(set(orig) | set(fixed))

    print("\n===== ORIGINAL vs FIXED =====\n")
    print("## Window actually graded (this is the bug)\n")
    print("| symbol | original bars | original span (d) | fixed bars | fixed span (d) |")
    print("|---|---:|---:|---:|---:|")
    for s in symbols:
        o, f = orig.get(s, {}), fixed.get(s, {})
        print(f"| {s} | {o.get('bars','n/a')} | {span_days(o)} "
              f"| {f.get('bars','n/a')} | {span_days(f)} |")

    print("\n## Results on the window each one actually used\n")
    print("| symbol | orig return | orig Sharpe | orig trades "
          "| fixed return | fixed Sharpe | fixed trades | fixed maxDD | liq |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in symbols:
        o, f = orig.get(s, {}), fixed.get(s, {})
        if "error" in o and "error" in f:
            print(f"| {s} | ERROR | | | ERROR | | | | |")
            continue
        print(f"| {s} | {fmt(o.get('total_return'), True)} | {fmt(o.get('sharpe'))} "
              f"| {o.get('trades','n/a')} | {fmt(f.get('total_return'), True)} "
              f"| {fmt(f.get('sharpe'))} | {f.get('trades','n/a')} "
              f"| {fmt(f.get('max_drawdown'), True)} | {f.get('liquidations_proxy','n/a')} |")

    print("\n## Fixed-run coverage audit\n")
    print("| symbol | requested days | expected bars | delivered | coverage | requests |")
    print("|---|---:|---:|---:|---:|---:|")
    for s in symbols:
        cov = (fixed.get(s) or {}).get("coverage")
        if not isinstance(cov, dict):
            print(f"| {s} | n/a | n/a | n/a | n/a | n/a |")
            continue
        print(f"| {s} | {cov['requested_days']} | {cov['expected_bars']} "
              f"| {cov['delivered_bars']} | {cov['coverage_ratio']:.1%} "
              f"| {cov['pages_walked']} |")

    errs = {s: (fixed.get(s) or {}).get("error") for s in symbols
            if (fixed.get(s) or {}).get("error")}
    if errs:
        print("\n## Errors in the fixed run\n")
        for s, e in errs.items():
            print(f"- **{s}**: {e}")


if __name__ == "__main__":
    main()
