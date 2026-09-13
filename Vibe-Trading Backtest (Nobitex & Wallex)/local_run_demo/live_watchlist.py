"""Live daily-timeframe watchlist for Nobitex IRT pairs.

Reports, per symbol, what the MA(10/30) rule says RIGHT NOW on live daily bars,
alongside how that same rule was actually graded by the backtest engine on the
same symbol — separately for the long-only and the symmetric long/short
variant, so the short leg is evidenced rather than assumed.

Nothing here is a recommendation. It is the current state of a mechanical rule
plus its historical scorecard, and the risk columns exist to make the cost of
leverage explicit.

Usage (needs real network — GitHub Actions runner, not a sandboxed session):
    pip install vibe-trading-ai
    python live_watchlist.py
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SIGNAL_DIR = HERE / "signal_engines"
OUT_DIR = Path(os.environ.get("OUT_DIR", HERE / "watchlist_output")).resolve()
RUN_ROOT = Path.home() / ".vibe-trading" / "runs"

CANDIDATES = [
    "BTCIRT", "ETHIRT", "USDTIRT", "XRPIRT", "DOGEIRT",
    "ADAIRT", "TRXIRT", "LTCIRT", "BNBIRT", "SOLIRT",
    "DOTIRT", "AVAXIRT", "SHIBIRT", "LINKIRT", "ATOMIRT",
]

FAST, SLOW = 10, 30
GRADED_DAYS = 400
WARMUP_BARS = 30
# Spot-realistic assumptions for a Toman order book, not an official fee table.
COST_CONFIG = {"taker_rate": 0.0025, "maker_rate": 0.0025,
               "slippage": 0.001, "leverage": 1.0}
# Leverage is capped where the strategy's own worst historical drawdown on that
# symbol would still have left half the account standing.
DD_BUDGET = 0.50
LEVERAGE_CAP = 5.0


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0.0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0.0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0)


def atr_pct(df: pd.DataFrame, period: int = 14) -> float:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    return float(atr.iloc[-1] / close.iloc[-1] * 100)


def fetch_live() -> dict[str, pd.DataFrame]:
    from backtest.loaders.nobitex import DataLoader

    end = date.today()
    start = end - timedelta(days=GRADED_DAYS + WARMUP_BARS)
    loader = DataLoader()
    print(f"fetching {len(CANDIDATES)} symbols from live apiv2.nobitex.ir", file=sys.stderr)
    return loader.fetch(CANDIDATES, start.isoformat(), end.isoformat(), interval="1D")


def indicator_state(df: pd.DataFrame) -> dict:
    close = df["close"]
    fast_ma = close.rolling(FAST, min_periods=FAST).mean()
    slow_ma = close.rolling(SLOW, min_periods=SLOW).mean()
    long_state = (fast_ma > slow_ma)
    valid = long_state[fast_ma.notna() & slow_ma.notna()]
    if valid.empty:
        return {}

    now = bool(valid.iloc[-1])
    # bars since the state last flipped
    flipped = valid != valid.shift(1)
    flip_idx = np.where(flipped.to_numpy())[0]
    bars_since = int(len(valid) - 1 - flip_idx[-1]) if len(flip_idx) else len(valid)

    rsi = wilder_rsi(close)
    spread = float((fast_ma.iloc[-1] - slow_ma.iloc[-1]) / slow_ma.iloc[-1] * 100)
    high30 = float(close.tail(30).max())
    low30 = float(close.tail(30).min())
    last = float(close.iloc[-1])
    return {
        "direction": "LONG" if now else "SHORT",
        "bars_since_flip": bars_since,
        "ma_spread_pct": spread,
        "rsi14": float(rsi.iloc[-1]),
        "atr14_pct": atr_pct(df),
        "last_close": last,
        "off_30d_high_pct": (last / high30 - 1) * 100,
        "off_30d_low_pct": (last / low30 - 1) * 100,
        "last_bar": str(df.index[-1].date()),
        "bars_loaded": len(df),
    }


def backtest(symbol: str, engine_file: str, tag: str) -> dict | None:
    from backtest.runner import main as runner_main

    end = date.today()
    run_dir = RUN_ROOT / f"watch_{tag}_{symbol}"
    (run_dir / "code").mkdir(parents=True, exist_ok=True)
    shutil.copy(SIGNAL_DIR / engine_file, run_dir / "code" / "signal_engine.py")
    config = {
        "source": "nobitex",
        "codes": [symbol],
        "start_date": (end - timedelta(days=GRADED_DAYS + WARMUP_BARS)).isoformat(),
        "end_date": end.isoformat(),
        "interval": "1D",
        "initial_cash": 100000000,
        "warmup_bars": WARMUP_BARS,
        **COST_CONFIG,
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2))
    try:
        runner_main(run_dir)
    except SystemExit as exc:
        print(f"{tag}/{symbol} exit({exc.code})", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"{tag}/{symbol} {type(exc).__name__}: {exc}", file=sys.stderr)

    metrics = run_dir / "artifacts" / "metrics.csv"
    if not metrics.exists():
        return None
    dest = OUT_DIR / tag / symbol
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir / "artifacts", dest / "artifacts", dirs_exist_ok=True)
    with open(metrics) as f:
        return list(csv.DictReader(f))[0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data_map = fetch_live()
    if not data_map:
        print("no live data returned", file=sys.stderr)
        sys.exit(1)

    rows = []
    for symbol in CANDIDATES:
        df = data_map.get(symbol)
        if df is None or len(df) < SLOW + 5:
            print(f"skip {symbol}: no usable live data", file=sys.stderr)
            continue
        state = indicator_state(df)
        if not state:
            continue
        long_only = backtest(symbol, "ma_10_30_debugged.py", "longonly")
        long_short = backtest(symbol, "ma_10_30_longshort.py", "longshort")
        state["symbol"] = symbol
        for tag, m in (("lo", long_only), ("ls", long_short)):
            state[f"{tag}_return"] = float(m["total_return"]) * 100 if m else None
            state[f"{tag}_sharpe"] = float(m["sharpe"]) if m else None
            state[f"{tag}_maxdd"] = float(m["max_drawdown"]) * 100 if m else None
            state[f"{tag}_trades"] = int(float(m["trade_count"])) if m else None

        # Which variant actually governs the side the rule is pointing at now.
        # A live SHORT is only evidenced by the symmetric long/short run; the
        # long-only backtest never took that side and says nothing about it.
        governing = long_short if state["direction"] == "SHORT" else long_only
        dd = abs(float(governing["max_drawdown"])) if governing else None
        raw_lev = DD_BUDGET / dd if dd and dd > 0 else None
        # Below 1x is not a leverage setting, it is the budget refusing even an
        # unleveraged position — surface that instead of printing "0.7x".
        state["lev_budget_breached"] = bool(raw_lev is not None and raw_lev < 1.0)
        state["max_lev"] = (
            round(min(LEVERAGE_CAP, max(raw_lev, 1.0)), 1) if raw_lev else None
        )
        if state["max_lev"] and state["atr14_pct"] > 0:
            # isolated-margin liquidation sits near a 1/L adverse move
            state["liq_atrs"] = round(
                (100.0 / state["max_lev"]) / state["atr14_pct"], 1)
        else:
            state["liq_atrs"] = None

        gov_sharpe = (
            state["ls_sharpe"] if state["direction"] == "SHORT" else state["lo_sharpe"]
        )
        state["gov_sharpe"] = gov_sharpe
        if gov_sharpe is None:
            state["verdict"] = "no data"
        elif gov_sharpe >= 0.5:
            state["verdict"] = f"watch {state['direction'].lower()}"
        elif gov_sharpe > 0:
            state["verdict"] = "weak"
        else:
            state["verdict"] = "no edge"
        rows.append(state)

    rows.sort(key=lambda r: (r["ls_sharpe"] if r["ls_sharpe"] is not None else -9))
    rows.reverse()

    def cell(v, suffix="", nd=2):
        return "n/a" if v is None else f"{v:.{nd}f}{suffix}"

    lines = [
        "| symbol | live signal | verdict | bars since flip | MA spread | RSI14 | ATR14 | "
        "long-only ret / Sharpe / maxDD | long-short ret / Sharpe / maxDD | max lev | liq dist |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lev = cell(r["max_lev"], "x", 1)
        if r["lev_budget_breached"]:
            lev += " (breached)"
        lines.append(
            f"| {r['symbol']} | {r['direction']} | {r['verdict']} | {r['bars_since_flip']} | "
            f"{cell(r['ma_spread_pct'], '%')} | {cell(r['rsi14'], '', 1)} | "
            f"{cell(r['atr14_pct'], '%')} | "
            f"{cell(r['lo_return'], '%')} / {cell(r['lo_sharpe'], '', 2)} / {cell(r['lo_maxdd'], '%')} | "
            f"{cell(r['ls_return'], '%')} / {cell(r['ls_sharpe'], '', 2)} / {cell(r['ls_maxdd'], '%')} | "
            f"{lev} | {cell(r['liq_atrs'], ' ATR', 1)} |"
        )

    table = "\n".join(lines)
    (OUT_DIR / "WATCHLIST.md").write_text(table + "\n")
    (OUT_DIR / "watchlist.json").write_text(json.dumps(rows, indent=2, default=str))
    print("\n\n===== LIVE WATCHLIST =====\n")
    print(f"as of last bar: {rows[0]['last_bar'] if rows else 'n/a'}\n")
    print(table)


if __name__ == "__main__":
    main()
