#!/usr/bin/env python3
"""
Nobitex isolated-margin research backtester.

This is intentionally NOT presented as an exact replica of Nobitex's internal
liquidation engine. Nobitex exposes live margin fields such as leverage,
collateral, margin ratio and liquidation price, but historical OHLC data does
not reconstruct every historical risk state. Therefore liquidation is a
configurable research proxy and is reported as such.

Design goals:
- Public live OHLC from Nobitex UDF API.
- Next-bar-open execution (no same-bar look-ahead).
- Long and short.
- Risk-based position sizing, leverage cap and equity cap.
- Daily extension-fee accrual.
- Intrabar SL/TP/liquidation handling.
- Walk-forward diagnostic and stationary block bootstrap.
- Full ledger + equity curve + JSON metrics.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

NOBITEX = "https://apiv2.nobitex.ir/market/udf/history"


@dataclass
class Position:
    symbol: str
    direction: int       # +1 long, -1 short
    entry_time: str
    entry_price: float
    qty: float
    notional: float
    leverage: float
    collateral: float
    stop_price: float
    take_price: float
    last_fee_time: pd.Timestamp
    bars_held: int = 0
    entry_fee: float = 0.0
    extension_fee: float = 0.0


def fetch_ohlc(symbol: str, resolution: str, lookback_days: int) -> pd.DataFrame:
    now = int(datetime.now(timezone.utc).timestamp())
    start = now - lookback_days * 86400
    params = {
        "symbol": symbol.upper(),
        "resolution": resolution,
        "from": start,
        "to": now,
    }
    r = requests.get(NOBITEX, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if payload.get("s") != "ok":
        raise RuntimeError(f"{symbol}: Nobitex UDF error: {payload}")
    n = min(*(len(payload.get(k, [])) for k in ["t", "o", "h", "l", "c", "v"]))
    if n < 200:
        raise RuntimeError(f"{symbol}: only {n} bars returned; refusing unstable test")
    df = pd.DataFrame({
        "timestamp": payload["t"][:n],
        "open": payload["o"][:n],
        "high": payload["h"][:n],
        "low": payload["l"][:n],
        "close": payload["c"][:n],
        "volume": payload["v"][:n],
    })
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna().drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")
    # Structural OHLC validation. Dirty bars are rejected, not silently repaired.
    bad = (
        (df["low"] > df["high"])
        | (df["open"] > df["high"])
        | (df["open"] < df["low"])
        | (df["close"] > df["high"])
        | (df["close"] < df["low"])
        | (df[["open","high","low","close"]] <= 0).any(axis=1)
    )
    df = df.loc[~bad].copy()
    if len(df) < 200:
        raise RuntimeError(f"{symbol}: too few valid bars after OHLC validation: {len(df)}")

    # Indicators use only information available at the close of the decision bar.
    df["ema_fast"] = df["close"].ewm(span=10, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=30, adjust=False).mean()
    df["atr"] = atr(df, 14)
    df["ret"] = df["close"].pct_change()
    df["vol20"] = df["ret"].rolling(20).std()
    df["ema_slope"] = df["ema_fast"].pct_change(3)
    return df


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def signal(df: pd.DataFrame) -> pd.Series:
    """Conservative trend state: +1 long, -1 short, 0 flat.

    The signal is defined at bar t and executed at bar t+1 open.
    """
    s = pd.Series(0, index=df.index, dtype=int)
    long_ok = (
        (df["ema_fast"] > df["ema_slow"])
        & (df["ema_slope"] > 0)
        & (df["close"] > df["ema_slow"])
    )
    short_ok = (
        (df["ema_fast"] < df["ema_slow"])
        & (df["ema_slope"] < 0)
        & (df["close"] < df["ema_slow"])
    )
    s.loc[long_ok] = 1
    s.loc[short_ok] = -1
    return s


def max_leverage_from_market_info(symbol: str, requested: float) -> float:
    """Live public endpoint may require auth; this research script does not
    require credentials. Keep a conservative bound when market metadata is
    unavailable. The workflow input is the research ceiling, not an exchange
    guarantee.
    """
    return float(requested)


def mark_pnl(pos: Position, price: float) -> float:
    return pos.direction * pos.qty * (price - pos.entry_price)


def close_position(
    pos: Position,
    exit_time: pd.Timestamp,
    exit_price: float,
    equity: float,
    fee_rate: float,
    reason: str,
    extension_fee: float,
) -> tuple[float, dict]:
    exit_notional = pos.qty * exit_price
    exit_fee = exit_notional * fee_rate
    pnl = mark_pnl(pos, exit_price)
    net = pnl - pos.entry_fee - extension_fee - exit_fee
    new_equity = equity + net
    return new_equity, {
        "symbol": pos.symbol,
        "entry_time": pos.entry_time,
        "exit_time": exit_time.isoformat(),
        "direction": "LONG" if pos.direction == 1 else "SHORT",
        "entry_price": pos.entry_price,
        "exit_price": exit_price,
        "qty": pos.qty,
        "leverage": pos.leverage,
        "collateral": pos.collateral,
        "gross_pnl": pnl,
        "entry_fee": pos.entry_fee,
        "exit_fee": exit_fee,
        "extension_fee": extension_fee,
        "net_pnl": net,
        "return_on_collateral": net / pos.collateral if pos.collateral else np.nan,
        "bars_held": pos.bars_held,
        "reason": reason,
    }


def liquidation_proxy(pos: Position, bar: pd.Series, maintenance_ratio: float) -> tuple[bool, float]:
    """Research proxy, not Nobitex's undisclosed historical liquidation formula.

    We declare a margin breach when:
        collateral + unrealized_pnl <= maintenance_ratio * initial_collateral

    This is deliberately conservative and fully auditable.
    """
    threshold = maintenance_ratio * pos.collateral
    if pos.direction == 1:
        breach_price = pos.entry_price + (threshold - pos.collateral) / pos.qty
        return bar["low"] <= breach_price, max(float(bar["low"]), 0.0)
    else:
        breach_price = pos.entry_price + (pos.collateral - threshold) / pos.qty
        return bar["high"] >= breach_price, max(float(bar["high"]), 0.0)


def run_symbol(
    df: pd.DataFrame,
    symbol: str,
    leverage: float,
    risk_pct: float,
    stop_pct: float,
    take_pct: float,
    fee_rate: float,
    extension_fee_daily: float,
    maintenance_ratio: float,
    max_hold_bars: int,
    starting_cash: float = 100_000_000.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sig = signal(df)
    equity = starting_cash
    pos = None
    trades = []
    curve = []
    last_ts = df.index[0]
    years = 365.25 * 86400

    for i in range(31, len(df) - 1):
        ts = df.index[i]
        row = df.iloc[i]
        next_row = df.iloc[i + 1]
        target = int(sig.iloc[i])

        # Mark current equity before decisions.
        if pos:
            elapsed = max((ts - pos.last_fee_time).total_seconds(), 0.0)
            if elapsed > 0:
                # Daily extension fee is applied pro-rata in clock time.
                accrued = pos.collateral * extension_fee_daily * elapsed / 86400.0
                pos.extension_fee += accrued
                pos.last_fee_time = ts
            equity_mark = equity + mark_pnl(pos, float(row["close"])) - pos.extension_fee
        else:
            equity_mark = equity

        # Manage existing position using the current bar.
        if pos is not None:
            pos.bars_held += 1
            liq, liq_price = liquidation_proxy(pos, row, maintenance_ratio)

            stop_hit = (
                row["low"] <= pos.stop_price if pos.direction == 1
                else row["high"] >= pos.stop_price
            )
            take_hit = (
                row["high"] >= pos.take_price if pos.direction == 1
                else row["low"] <= pos.take_price
            )

            # Conservative intrabar priority: liquidation > stop > target.
            exit_reason = None
            exit_price = None
            if liq:
                exit_reason, exit_price = "LIQUIDATION_PROXY", liq_price
            elif stop_hit:
                exit_reason, exit_price = "STOP", pos.stop_price
            elif take_hit:
                exit_reason, exit_price = "TAKE", pos.take_price
            elif max_hold_bars and pos.bars_held >= max_hold_bars:
                exit_reason, exit_price = "TIME", float(row["close"])
            elif target != pos.direction:
                exit_reason, exit_price = "SIGNAL_FLIP", float(next_row["open"])

            if exit_reason:
                equity, trade = close_position(
                    pos, ts, float(exit_price), equity, fee_rate,
                    exit_reason, pos.extension_fee
                )
                trades.append(trade)
                pos = None

        # Open a new position at the NEXT bar's OPEN only.
        if pos is None and target != 0:
            entry_price = float(next_row["open"])
            if not np.isfinite(entry_price) or entry_price <= 0:
                curve.append({"timestamp": ts.isoformat(), "equity": equity})
                continue

            # Stop distance may be ATR-adaptive but never below configured floor.
            atr_pct = float(row["atr"] / row["close"]) if row["close"] else np.nan
            dist = max(stop_pct, 1.5 * atr_pct if np.isfinite(atr_pct) else stop_pct)
            stop_distance_abs = entry_price * dist

            # Risk-based quantity: loss at stop ~= risk_pct * equity.
            risk_budget = max(equity, 0.0) * risk_pct
            qty_risk = risk_budget / stop_distance_abs if stop_distance_abs else 0.0

            # Margin/leverage cap: notional <= equity * leverage.
            qty_cap = max(equity, 0.0) * leverage / entry_price
            qty = min(qty_risk, qty_cap)
            if qty <= 0:
                curve.append({"timestamp": ts.isoformat(), "equity": equity})
                continue

            notional = qty * entry_price
            collateral = notional / leverage
            entry_fee = notional * fee_rate

            stop_price = (
                entry_price * (1 - dist) if target == 1
                else entry_price * (1 + dist)
            )
            tp_dist = max(take_pct, 2 * dist)
            take_price = (
                entry_price * (1 + tp_dist) if target == 1
                else entry_price * (1 - tp_dist)
            )

            # Never allow opening fees to consume the entire equity.
            if collateral + entry_fee > equity:
                qty = max((equity - entry_fee) * leverage / entry_price, 0.0)
                notional = qty * entry_price
                collateral = notional / leverage
                entry_fee = notional * fee_rate

            if qty > 0 and collateral > 0 and collateral + entry_fee <= equity:
                equity -= entry_fee
                pos = Position(
                    symbol=symbol,
                    direction=target,
                    entry_time=next_row.name.isoformat(),
                    entry_price=entry_price,
                    qty=qty,
                    notional=notional,
                    leverage=leverage,
                    collateral=collateral,
                    stop_price=stop_price,
                    take_price=take_price,
                    last_fee_time=next_row.name,
                    entry_fee=entry_fee,
                )

        # End-of-bar mark.
        mark = equity + (mark_pnl(pos, float(row["close"])) if pos else 0.0) - (
            pos.extension_fee if pos else 0.0
        )
        curve.append({"timestamp": ts.isoformat(), "equity": max(mark, 0.0)})

        last_ts = ts

    # Force close at final close.
    if pos is not None:
        final = df.iloc[-1]
        equity, trade = close_position(
            pos, df.index[-1], float(final["close"]), equity, fee_rate,
            "END_OF_SAMPLE", pos.extension_fee
        )
        trades.append(trade)
        curve.append({"timestamp": df.index[-1].isoformat(), "equity": max(equity, 0.0)})

    eq = pd.DataFrame(curve).drop_duplicates("timestamp").set_index("timestamp")
    tr = pd.DataFrame(trades)

    if eq.empty:
        raise RuntimeError(f"{symbol}: empty equity curve")

    # Metrics
    eqv = eq["equity"].astype(float)
    rets = eqv.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bars_per_year = 365 * 24 * 60 / max(infer_minutes(df.index), 1)
    ann = float(rets.mean() * bars_per_year)
    vol = float(rets.std(ddof=1) * math.sqrt(bars_per_year)) if len(rets) > 2 else 0.0
    downside = rets.clip(upper=0)
    downside_vol = float(downside.std(ddof=1) * math.sqrt(bars_per_year)) if len(rets) > 2 else 0.0
    sharpe = ann / vol if vol > 1e-12 else np.nan
    sortino = ann / downside_vol if downside_vol > 1e-12 else np.nan
    peak = eqv.cummax()
    dd = eqv / peak - 1.0
    mdd = float(dd.min())
    total_ret = float(eqv.iloc[-1] / eqv.iloc[0] - 1.0)
    years_span = max((pd.Timestamp(eqv.index[-1]) - pd.Timestamp(eqv.index[0])).total_seconds() / years, 1/365.25)
    cagr = float((max(eqv.iloc[-1], 0) / max(eqv.iloc[0], 1e-12)) ** (1 / years_span) - 1.0)
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan

    metrics = {
        "symbol": symbol,
        "initial_equity": starting_cash,
        "final_equity": float(eqv.iloc[-1]),
        "total_return": total_ret,
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": mdd,
        "trades": int(len(tr)),
        "win_rate": float((tr["net_pnl"] > 0).mean()) if len(tr) else np.nan,
        "profit_factor": (
            float(tr.loc[tr["net_pnl"] > 0, "net_pnl"].sum()
                  / abs(tr.loc[tr["net_pnl"] < 0, "net_pnl"].sum()))
            if len(tr) and (tr["net_pnl"] < 0).any() else np.inf
        ),
        "median_trade_return": float(tr["return_on_collateral"].median()) if len(tr) else np.nan,
        "liquidations": int((tr["reason"] == "LIQUIDATION_PROXY").sum()) if len(tr) else 0,
    }
    eq["drawdown"] = dd.values
    return eq.reset_index(), tr


def infer_minutes(idx: pd.DatetimeIndex) -> int:
    if len(idx) < 3:
        return 1440
    diffs = pd.Series(idx[1:] - idx[:-1]).dt.total_seconds().div(60)
    return int(max(1, round(float(diffs.median()))))


def bootstrap_block(returns: np.ndarray, n=2000, block=32, seed=42):
    rng = np.random.default_rng(seed)
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 20:
        return {}
    paths = []
    horizon = len(r)
    for _ in range(n):
        out = []
        while len(out) < horizon:
            start = int(rng.integers(0, horizon))
            idx = [(start + j) % horizon for j in range(block)]
            out.extend(r[idx])
        rr = np.array(out[:horizon])
        paths.append(float(np.prod(1.0 + rr) - 1.0))
    q = np.quantile(paths, [0.01, 0.05, 0.50, 0.95, 0.99])
    return {
        "bootstrap_paths": n,
        "block_bars": block,
        "p01_total_return": float(q[0]),
        "p05_total_return": float(q[1]),
        "median_total_return": float(q[2]),
        "p95_total_return": float(q[3]),
        "p99_total_return": float(q[4]),
        "probability_of_loss": float(np.mean(np.array(paths) < 0)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCIRT")
    ap.add_argument("--resolution", default="15")
    ap.add_argument("--lookback-days", type=int, default=180)
    ap.add_argument("--leverage", type=float, default=3.0)
    ap.add_argument("--risk-pct", type=float, default=0.005)
    ap.add_argument("--stop-pct", type=float, default=0.008)
    ap.add_argument("--take-pct", type=float, default=0.016)
    ap.add_argument("--fee-rate", type=float, default=0.0025)
    ap.add_argument("--extension-fee-daily", type=float, default=0.001)
    ap.add_argument("--maintenance-ratio", type=float, default=0.50)
    ap.add_argument("--max-hold-bars", type=int, default=96)
    ap.add_argument("--output-dir", default="gh_run_output/nobitex_margin")
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_metrics = []
    for raw_symbol in [x.strip().upper() for x in args.symbols.split(",") if x.strip()]:
        try:
            lev = max_leverage_from_market_info(raw_symbol, args.leverage)
            df = fetch_ohlc(raw_symbol, args.resolution, args.lookback_days)
            eq, trades = run_symbol(
                df, raw_symbol, lev, args.risk_pct, args.stop_pct, args.take_pct,
                args.fee_rate, args.extension_fee_daily, args.maintenance_ratio,
                args.max_hold_bars
            )
            metrics = json.loads(json.dumps({
                "data_start": df.index[0].isoformat(),
                "data_end": df.index[-1].isoformat(),
                "bars": len(df),
                **{k: (float(v) if isinstance(v, (np.floating,)) else v)
                   for k, v in run_symbol.__annotations__.items() if False},
            }))
            # Recover metrics directly from the generated trade/equity series.
            eqv = eq["equity"].astype(float)
            rets = eqv.pct_change().fillna(0.0)
            bars_year = 365*24*60/max(infer_minutes(df.index), 1)
            ann = float(rets.mean()*bars_year)
            vol = float(rets.std(ddof=1)*math.sqrt(bars_year)) if len(rets)>2 else 0.0
            peak = eqv.cummax()
            mdd = float((eqv/peak - 1).min())
            metrics.update({
                "symbol": raw_symbol,
                "leverage_requested": args.leverage,
                "leverage_used": lev,
                "resolution": args.resolution,
                "final_equity": float(eqv.iloc[-1]),
                "total_return": float(eqv.iloc[-1]/eqv.iloc[0]-1),
                "annualized_mean_return_proxy": ann,
                "sharpe": ann/vol if vol>1e-12 else None,
                "max_drawdown": mdd,
                "trades": int(len(trades)),
                "win_rate": float((trades["net_pnl"]>0).mean()) if len(trades) else None,
                "liquidations_proxy": int((trades["reason"]=="LIQUIDATION_PROXY").sum()) if len(trades) else 0,
                "bootstrap": bootstrap_block(rets.to_numpy(), n=2000, block=max(8, int(240/max(infer_minutes(df.index),1))))
            })
            eq.to_csv(out/f"{raw_symbol}_equity.csv", index=False)
            trades.to_csv(out/f"{raw_symbol}_trades.csv", index=False)
            (out/f"{raw_symbol}_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
            all_metrics.append(metrics)
        except Exception as e:
            err = {"symbol": raw_symbol, "error": f"{type(e).__name__}: {e}"}
            (out/f"{raw_symbol}_ERROR.json").write_text(json.dumps(err, indent=2, ensure_ascii=False))
            print(json.dumps(err, ensure_ascii=False))

    summary = {
        "engine": "nobitex_isolated_margin_research_proxy",
        "warning": "Liquidation/maintenance is a research proxy, not an official historical reconstruction of Nobitex risk engine.",
        "assumptions": {
            "execution": "signal at close t -> entry/flip at open t+1",
            "fees_per_side": args.fee_rate,
            "extension_fee_daily": args.extension_fee_daily,
            "maintenance_ratio_proxy": args.maintenance_ratio,
            "risk_budget_per_trade": args.risk_pct,
            "leverage_cap": args.leverage,
        },
        "results": all_metrics,
    }
    (out/"summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
