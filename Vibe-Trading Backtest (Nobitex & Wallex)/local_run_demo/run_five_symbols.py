"""Five-symbol Nobitex backtest, run twice: raw strategy vs debugged strategy.

Runs on a GitHub Actions runner (real outbound internet) against the live
Nobitex UDF endpoint. No HTTP mocking anywhere.

Strategy under test: MA(10/30) crossover — the mode that won the earlier live
single-symbol run on BTCIRT.

State A ("raw")       signal_engines/nobitex_ma_10_30.py, engine defaults
                      (taker 0.05% / maker 0.02% / slippage 0.05% — perpetual
                      -swap style), no warm-up boundary.

State B ("debugged")  signal_engines/ma_10_30_debugged.py plus config fixes:
    D1  warmup_bars=30 with the fetch window extended by the same 30 bars, so
        the graded window is identical to State A's but every bar in it is
        scored with a fully warmed MA30. In State A the first 30 bars are
        structurally flat cash inside the graded window, which drags total
        return and distorts the annualisation.
    D2  spot-realistic costs: this is an Iranian SPOT venue, but the engine's
        defaults are perpetual-swap fees an order of magnitude too low. Set to
        0.25% per side plus 0.10% slippage. These are conservative ASSUMPTIONS
        for a Toman order book, not scraped from an official fee table.
    D3  explicit no-position during indicator warm-up (see the engine file).
    D4  1/N position sizing (inert at N=1, active in the portfolio run).

Each symbol is also run standalone so per-symbol numbers are comparable, and a
combined five-symbol portfolio run is done in each state to exercise D4.

Usage:
    pip install vibe-trading-ai
    python run_five_symbols.py
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
OUT_DIR = Path(os.environ.get("OUT_DIR", HERE / "five_symbol_output")).resolve()
RUN_ROOT = Path.home() / ".vibe-trading" / "runs"

SYMBOLS = ["BTCIRT", "ETHIRT", "USDTIRT", "XRPIRT", "DOGEIRT"]

GRADED_DAYS = 400          # length of the window both states are graded over
WARMUP_BARS = 30           # MA30 lookback, State B only

STATES = {
    "raw": {
        "engine_file": "nobitex_ma_10_30.py",
        "extra_config": {},
    },
    "debugged": {
        "engine_file": "ma_10_30_debugged.py",
        "extra_config": {
            "warmup_bars": WARMUP_BARS,
            "taker_rate": 0.0025,
            "maker_rate": 0.0025,
            "slippage": 0.001,
            "leverage": 1.0,
        },
    },
}

REPORT_FIELDS = ["total_return", "annual_return", "sharpe", "max_drawdown",
                 "win_rate", "trade_count"]


def make_config(state: str, codes: list[str]) -> dict:
    end = date.today()
    # State B fetches WARMUP_BARS extra bars so that, after the warm-up prefix is
    # dropped, both states grade the exact same GRADED_DAYS window.
    lookback = GRADED_DAYS + (WARMUP_BARS if state == "debugged" else 0)
    config = {
        "source": "nobitex",
        "codes": codes,
        "start_date": (end - timedelta(days=lookback)).isoformat(),
        "end_date": end.isoformat(),
        "interval": "1D",
        "initial_cash": 100000000,
    }
    config.update(STATES[state]["extra_config"])
    return config


def run_one(state: str, label: str, codes: list[str]) -> dict | None:
    from backtest.runner import main as runner_main

    run_dir = RUN_ROOT / f"five_{state}_{label}"
    code_dir = run_dir / "code"
    code_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(SIGNAL_DIR / STATES[state]["engine_file"], code_dir / "signal_engine.py")
    (run_dir / "config.json").write_text(json.dumps(make_config(state, codes), indent=2))

    print(f"--- {state}/{label}: {codes} (live apiv2.nobitex.ir) ---", file=sys.stderr)
    try:
        runner_main(run_dir)
    except SystemExit as exc:
        print(f"{state}/{label} exited with sys.exit({exc.code})", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — one bad symbol must not kill the sweep
        print(f"{state}/{label} raised {type(exc).__name__}: {exc}", file=sys.stderr)

    dest = OUT_DIR / state / label
    dest.mkdir(parents=True, exist_ok=True)
    for fname in ("config.json", "run_card.md", "run_card.json"):
        src = run_dir / fname
        if src.exists():
            shutil.copy(src, dest / fname)
    if (run_dir / "artifacts").exists():
        shutil.copytree(run_dir / "artifacts", dest / "artifacts", dirs_exist_ok=True)

    metrics_csv = run_dir / "artifacts" / "metrics.csv"
    if not metrics_csv.exists():
        return None
    with open(metrics_csv) as f:
        return list(csv.DictReader(f))[0]


def fmt(row: dict | None) -> list[str]:
    if row is None:
        return ["n/a"] * len(REPORT_FIELDS)
    cells = []
    for field in REPORT_FIELDS:
        v = float(row[field])
        if field in ("total_return", "annual_return", "max_drawdown", "win_rate"):
            cells.append(f"{v*100:.2f}%")
        elif field == "trade_count":
            cells.append(str(int(v)))
        else:
            cells.append(f"{v:.3f}")
    return cells


def table(title: str, rows: list[tuple[str, dict | None]]) -> str:
    lines = [f"### {title}",
             "| symbol | " + " | ".join(REPORT_FIELDS) + " |",
             "|---" * (len(REPORT_FIELDS) + 1) + "|"]
    for name, row in rows:
        lines.append(f"| {name} | " + " | ".join(fmt(row)) + " |")
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = []

    for state in ("raw", "debugged"):
        per_symbol = [(sym, run_one(state, sym, [sym])) for sym in SYMBOLS]
        report.append(table(f"State: {state} — five symbols, standalone runs", per_symbol))
        portfolio = run_one(state, "portfolio5", SYMBOLS)
        report.append(table(f"State: {state} — combined 5-symbol portfolio",
                            [("PORTFOLIO(5)", portfolio)]))

    out = "\n\n".join(report)
    (OUT_DIR / "FIVE_SYMBOL_RESULTS.md").write_text(out + "\n")
    print("\n\n===== FIVE SYMBOL RESULTS =====\n")
    print(out)


if __name__ == "__main__":
    main()
