"""Drive real vibe-trading-ai backtests against the live Nobitex API.

Meant to run on a GitHub Actions runner (real outbound internet), not in a
sandboxed dev session. Builds one run_dir per strategy under
~/.vibe-trading/runs/, copies the matching signal_engine.py from
signal_engines/, writes config.json with a rolling date window ending
"today", invokes the installed package's real backtest.runner.main()
(no network/HTTP mocking of any kind), and writes a combined comparison
table plus each run's raw artifacts to OUT_DIR (default: ./gh_run_output).

Usage:
    pip install vibe-trading-ai
    python run_on_github.py
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIGNAL_DIR = HERE / "signal_engines"
OUT_DIR = Path(os.environ.get("OUT_DIR", HERE / "gh_run_output")).resolve()
RUN_ROOT = Path.home() / ".vibe-trading" / "runs"

MODES = {
    "nobitex_buyhold": "Buy & Hold",
    "nobitex_ma_20_50": "MA Crossover 20/50",
    "nobitex_ma_10_30": "MA Crossover 10/30",
    "nobitex_rsi_meanrev": "RSI(14) Mean-Reversion",
}

WINDOW_DAYS = 400  # under Nobitex's 500-candles-per-page UDF limit for 1D bars


def build_run_dirs() -> dict[str, Path]:
    end = date.today()
    start = end - timedelta(days=WINDOW_DAYS)
    config = {
        "source": "nobitex",
        "codes": ["BTCIRT"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "interval": "1D",
        "initial_cash": 100000000,
    }
    dirs = {}
    for mode in MODES:
        run_dir = RUN_ROOT / mode
        code_dir = run_dir / "code"
        code_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(SIGNAL_DIR / f"{mode}.py", code_dir / "signal_engine.py")
        (run_dir / "config.json").write_text(json.dumps(config, indent=2))
        dirs[mode] = run_dir
    return dirs


def main() -> None:
    from backtest.runner import main as runner_main

    run_dirs = build_run_dirs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for mode, run_dir in run_dirs.items():
        print(f"=== running {mode} against LIVE apiv2.nobitex.ir ===", file=sys.stderr)
        try:
            runner_main(run_dir)
        except SystemExit as exc:
            print(f"{mode} exited with sys.exit({exc.code})", file=sys.stderr)

        dest = OUT_DIR / mode
        dest.mkdir(parents=True, exist_ok=True)
        for fname in ("config.json", "run_card.md", "run_card.json"):
            src = run_dir / fname
            if src.exists():
                shutil.copy(src, dest / fname)
        artifacts_src = run_dir / "artifacts"
        if artifacts_src.exists():
            shutil.copytree(artifacts_src, dest / "artifacts", dirs_exist_ok=True)

        metrics_csv = artifacts_src / "metrics.csv"
        if metrics_csv.exists():
            with open(metrics_csv) as f:
                row = list(csv.DictReader(f))[0]
            row["_mode"] = MODES[mode]
            rows.append(row)
        else:
            rows.append({"_mode": MODES[mode], "error": "no metrics.csv produced"})

    fields = ["total_return", "annual_return", "sharpe", "sortino", "calmar",
              "max_drawdown", "win_rate", "trade_count", "avg_turnover"]
    lines = ["| Mode | " + " | ".join(fields) + " |",
             "|---" * (len(fields) + 1) + "|"]
    for row in rows:
        if "error" in row:
            lines.append(f"| {row['_mode']} | {row['error']} |" + " |" * (len(fields) - 1))
            continue
        cells = []
        for f in fields:
            v = float(row[f])
            if f in ("total_return", "annual_return", "max_drawdown", "win_rate", "avg_turnover"):
                cells.append(f"{v*100:.2f}%")
            elif f == "trade_count":
                cells.append(str(int(v)))
            else:
                cells.append(f"{v:.3f}")
        lines.append(f"| {row['_mode']} | " + " | ".join(cells) + " |")

    combined = "\n".join(lines)
    (OUT_DIR / "COMBINED_RESULTS.md").write_text(combined + "\n")
    print(combined)


if __name__ == "__main__":
    main()
