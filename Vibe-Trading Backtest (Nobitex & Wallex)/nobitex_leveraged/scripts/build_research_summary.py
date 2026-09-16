#!/usr/bin/env python3
import json, sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for p in sorted(root.glob("*_metrics.json")):
    try:
        rows.append(json.loads(p.read_text()))
    except Exception:
        pass

print("# Nobitex leveraged long/short research summary\n")
print("> **Important:** liquidation is a configurable research proxy. It is not a claim about Nobitex's internal historical liquidation calculation.\n")
print("| Symbol | Return | Sharpe | Max DD | Win rate | Trades | Liq. proxy |")
print("|---|---:|---:|---:|---:|---:|---:|")
for r in rows:
    print(
        f"| {r.get('symbol','?')} "
        f"| {r.get('total_return', float('nan')):.2%} "
        f"| {r.get('sharpe', float('nan')) if r.get('sharpe') is not None else 'NA'} "
        f"| {r.get('max_drawdown', float('nan')):.2%} "
        f"| {r.get('win_rate', float('nan')):.2%} "
        f"| {r.get('trades', 0)} "
        f"| {r.get('liquidations_proxy', 0)} |"
    )

print("\n## Interpretation rules")
print("1. Do not rank strategies by return alone.")
print("2. Reject runs with proxy liquidations unless the liquidation mechanism is independently validated.")
print("3. Require walk-forward degradation checks before trusting leverage.")
print("4. Compare against buy-and-hold and an unleveraged long-only baseline.")
print("5. Treat a single 180-day sample as evidence, not proof.")
