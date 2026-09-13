import json, sys, traceback
from pathlib import Path

sys.path.insert(0, "/tmp/claude-0/-home-user-dataengineering/16e701aa-9a2a-5ada-bfcf-2eb0908ea5c0/scratchpad/vt-run")
import mock_nobitex_transport
mock_nobitex_transport.install()

from backtest.runner import main as runner_main

runs = [
    "nobitex_buyhold",
    "nobitex_ma_20_50",
    "nobitex_ma_10_30",
    "nobitex_rsi_meanrev",
]

RUNROOT = Path("/root/.vibe-trading/runs")
results = {}
for name in runs:
    run_dir = RUNROOT / name
    print(f"=== running {name} ===", file=sys.stderr)
    try:
        runner_main(run_dir)
    except SystemExit as e:
        print(f"{name} exited with sys.exit({e.code})", file=sys.stderr)
    metrics_path = run_dir / "metrics.json"
    if metrics_path.exists():
        results[name] = json.loads(metrics_path.read_text())
    else:
        results[name] = {"error": "no metrics.json produced"}

print(json.dumps(results, indent=2, ensure_ascii=False))
