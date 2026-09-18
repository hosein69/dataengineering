#!/usr/bin/env python3
"""
Nobitex isolated-margin research backtester — debugged.

Liquidation remains a configurable research proxy, not a reconstruction of
Nobitex's internal risk engine. That framing from the original is kept.

Fixes applied (see DEBUG_REPORT.md for reproductions):
  F1  paginate the UDF endpoint. It returns at most 500 candles per request,
      so the original silently delivered 5.2 days when asked for 30 at 15m.
  F2  stop charging the entry fee twice.
  F3  fill a liquidation at the breach price (or the open, on a gap through),
      not at the bar's most adverse extreme.
  F4  return the metrics computed in run_symbol instead of discarding them.
  F5  one shared returns helper, so the two code paths cannot disagree.
  F6  Sortino over strictly negative returns, not clip(upper=0).
  F7  explicit indicator warm-up instead of a hardcoded loop start of 31.
  F8  stamp a signal flip at the bar it actually fills on.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

NOBITEX = "https://apiv2.nobitex.ir/market/udf/history"

# Endpoint facts, verified against the vibe-trading-ai loader and live probes.
MAX_PER_REQUEST = 500        # hard server-side cap per call
MAX_PAGES = 60               # 60 * 500 = 30k bars ceiling
PAGE_SLEEP_S = 0.5           # endpoint allows 60 req/min
REQUEST_TIMEOUT_S = 12       # the venue throttles by stalling, so fail fast
REQUEST_RETRIES = 3
CACHE_DIR = Path(os.environ.get("NOBITEX_CACHE", ".nobitex_cache"))

RESOLUTION_SECONDS = {
    "1": 60, "5": 300, "15": 900, "30": 1800, "60": 3600,
    "180": 10800, "240": 14400, "360": 21600, "720": 43200,
    "D": 86400, "1D": 86400,
}


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


# ─────────────────────────── data ───────────────────────────

def _request_page(symbol: str, resolution: str, start: int, end: int, page: int) -> dict:
    """One page, with backoff.

    The venue throttles by making a connection hang rather than by returning
    429, so a long timeout turns throttling into a stalled job: 37 symbols x 3
    pages x a 30s timeout is most of an hour with nothing to show. A short
    timeout plus backoff fails fast and recovers when the throttle lifts.
    """
    delay = 1.0
    last: Exception | None = None
    for attempt in range(REQUEST_RETRIES):
        try:
            r = requests.get(
                NOBITEX,
                params={"symbol": symbol.upper(), "resolution": resolution,
                        "from": start, "to": end, "page": page},
                timeout=REQUEST_TIMEOUT_S,
            )
            if r.status_code == 429:
                raise requests.HTTPError("429 rate limited", response=r)
            r.raise_for_status()
            return r.json()
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            last = exc
            if attempt < REQUEST_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
    raise RuntimeError(f"{symbol}: {REQUEST_RETRIES} attempts failed: {last}")


def fetch_raw(symbol: str, resolution: str, lookback_days: int) -> pd.DataFrame:
    """Cover the requested window with consecutive ≤500-bar requests.

    F1. The endpoint caps a response at MAX_PER_REQUEST candles. The original
    issued a single request, so any window needing more than 500 bars was
    truncated to the newest 500 with no warning: `--lookback-days 180
    --resolution 15` returned 5.2 days and reported it as a 180-day study.

    Chunking the [from, to] window client-side is used rather than the `page`
    parameter because it does not depend on the server honouring page
    semantics: each chunk is an independent, self-verifying range request. A
    stall guard still covers the case where a chunk comes back outside its own
    requested range.
    """
    # Within one run the watchlist, the entry levels and the search each want
    # the same history. Fetching it three times triples the load on a venue
    # that is already the bottleneck, so the first fetch wins and the rest read
    # from disk. The key carries the hour, so a later run still gets fresh data.
    now = int(datetime.now(timezone.utc).timestamp())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    cache_file = CACHE_DIR / f"{symbol.upper()}_{resolution}_{lookback_days}_{stamp}.pkl"
    if cache_file.exists():
        try:
            cached = pd.read_pickle(cache_file)
            # Callers read .attrs["coverage"]; a frame that lost it on the
            # round trip is not a usable substitute, so refetch instead.
            if len(cached) and "coverage" in getattr(cached, "attrs", {}):
                return cached
        except Exception:  # noqa: BLE001
            pass

    start = now - lookback_days * 86400
    step = RESOLUTION_SECONDS.get(str(resolution))
    if step is None:
        raise RuntimeError(f"unsupported resolution {resolution!r}; "
                           f"supported: {sorted(RESOLUTION_SECONDS)}")

    expected = max(1, (now - start) // step)
    chunk_seconds = (MAX_PER_REQUEST - 1) * step      # stay strictly under the cap
    frames: list[pd.DataFrame] = []

    cursor = start
    for _ in range(MAX_PAGES):
        if cursor >= now:
            break
        chunk_end = min(cursor + chunk_seconds, now)
        payload = _request_page(symbol, str(resolution), cursor, chunk_end, 1)
        status = payload.get("s")
        if status == "no_data":
            cursor = chunk_end                         # gap, keep walking forward
            continue
        if status != "ok":
            raise RuntimeError(f"{symbol}: Nobitex UDF error: {payload}")

        times = payload.get("t") or []
        n = min(len(payload.get(k, [])) for k in ("t", "o", "h", "l", "c", "v")) if times else 0
        if n == 0:
            cursor = chunk_end
            continue

        frames.append(pd.DataFrame({
            "timestamp": payload["t"][:n],
            "open": payload["o"][:n],
            "high": payload["h"][:n],
            "low": payload["l"][:n],
            "close": payload["c"][:n],
            "volume": payload["v"][:n],
        }))

        newest = int(max(times[:n]))
        # Stall guard: if the server hands back nothing newer than where this
        # chunk started, advancing by the response would loop forever.
        cursor = max(newest + step, chunk_end)
        if cursor < chunk_end:
            cursor = chunk_end
        time.sleep(PAGE_SLEEP_S)

    if not frames:
        raise RuntimeError(f"{symbol}: no data returned for the requested window")

    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = (df.dropna()
            .drop_duplicates("timestamp")
            .sort_values("timestamp")
            .set_index("timestamp"))

    # Structural OHLC validation. Dirty bars are rejected, not silently repaired.
    bad = (
        (df["low"] > df["high"])
        | (df["open"] > df["high"]) | (df["open"] < df["low"])
        | (df["close"] > df["high"]) | (df["close"] < df["low"])
        | (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    )
    df = df.loc[~bad].copy()

    got = len(df)
    coverage = got / expected if expected else 0.0
    df.attrs["coverage"] = {
        "requested_days": lookback_days,
        "expected_bars": int(expected),
        "delivered_bars": int(got),
        "coverage_ratio": round(float(coverage), 4),
        "pages_walked": len(frames),
        "actual_span_days": round(
            (df.index[-1] - df.index[0]).total_seconds() / 86400, 3) if got > 1 else 0.0,
    }

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_pickle(cache_file)
    except Exception:  # noqa: BLE001
        pass          # a cache that cannot be written must not fail the fetch

    return df


def add_indicators(df: pd.DataFrame, fast: int, slow: int, atr_n: int,
                   slope_lag: int) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=slow, adjust=False).mean()
    df["atr"] = atr(df, atr_n)
    df["ema_slope"] = df["ema_fast"].pct_change(slope_lag)
    return df


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def warmup_bars(slow: int, atr_n: int, slope_lag: int) -> int:
    """F7. An EMA seeded on the first observation needs roughly 3 spans to
    forget that seed; the original hardcoded a loop start of 31, which is
    below that for span=30 and unrelated to the ATR window."""
    return max(3 * slow, atr_n + 1, slope_lag + 1)


def signal(df: pd.DataFrame) -> pd.Series:
    """Trend state: +1 long, -1 short, 0 flat. Defined at bar t, filled at t+1 open."""
    s = pd.Series(0, index=df.index, dtype=int)
    long_ok = ((df["ema_fast"] > df["ema_slow"])
               & (df["ema_slope"] > 0)
               & (df["close"] > df["ema_slow"]))
    short_ok = ((df["ema_fast"] < df["ema_slow"])
                & (df["ema_slope"] < 0)
                & (df["close"] < df["ema_slow"]))
    s.loc[long_ok] = 1
    s.loc[short_ok] = -1
    return s


# ─────────────────────────── accounting ───────────────────────────

def mark_pnl(pos: Position, price: float) -> float:
    return pos.direction * pos.qty * (price - pos.entry_price)


def close_position(pos: Position, exit_time: pd.Timestamp, exit_price: float,
                   equity: float, fee_rate: float, reason: str,
                   extension_fee: float) -> tuple[float, dict]:
    """F2. The entry fee left the account when the position opened, so the
    equity update must not subtract it again. The ledger still reports the
    true round-trip net, which is why the two differ by exactly entry_fee."""
    exit_notional = pos.qty * exit_price
    exit_fee = exit_notional * fee_rate
    pnl = mark_pnl(pos, exit_price)

    still_owed = pnl - extension_fee - exit_fee      # applied to equity now
    round_trip_net = still_owed - pos.entry_fee      # reported in the ledger

    new_equity = equity + still_owed
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
        "net_pnl": round_trip_net,
        "return_on_collateral": round_trip_net / pos.collateral if pos.collateral else np.nan,
        "bars_held": pos.bars_held,
        "reason": reason,
    }


def liquidation_proxy(pos: Position, bar: pd.Series, maintenance_ratio: float,
                      slippage: float) -> tuple[bool, float]:
    """Breach when collateral + unrealized <= maintenance_ratio * collateral.

    F3. The original returned the bar's low (long) or high (short) as the fill,
    i.e. it assumed every liquidation printed at the single worst tick of the
    bar. The fill here is the breach price itself, except when the bar gapped
    straight through it, in which case the open is the first available price.
    Adverse slippage is then applied on top.
    """
    threshold = maintenance_ratio * pos.collateral
    if pos.direction == 1:
        breach = pos.entry_price + (threshold - pos.collateral) / pos.qty
        if bar["low"] > breach:
            return False, 0.0
        fill = min(breach, float(bar["open"]))       # gap-through protection
        return True, max(fill * (1.0 - slippage), 0.0)
    breach = pos.entry_price + (pos.collateral - threshold) / pos.qty
    if bar["high"] < breach:
        return False, 0.0
    fill = max(breach, float(bar["open"]))
    return True, fill * (1.0 + slippage)


# ─────────────────────────── metrics ───────────────────────────

def equity_returns(eqv: pd.Series) -> pd.Series:
    """F5. One definition, used by every consumer. A blown account clips at
    zero, and pct_change off zero is non-finite, so the guard is mandatory."""
    return (eqv.pct_change()
               .replace([np.inf, -np.inf], np.nan)
               .fillna(0.0))


def compute_metrics(eq: pd.DataFrame, tr: pd.DataFrame, bars_per_year: float,
                    starting_cash: float) -> dict:
    eqv = eq["equity"].astype(float)
    rets = equity_returns(eqv)
    n = len(rets)

    ann = float(rets.mean() * bars_per_year)
    vol = float(rets.std(ddof=1) * math.sqrt(bars_per_year)) if n > 2 else 0.0
    neg = rets[rets < 0]                              # F6: strictly negative
    downside_vol = (float(neg.std(ddof=1) * math.sqrt(bars_per_year))
                    if len(neg) > 2 else 0.0)

    peak = eqv.cummax().clip(lower=starting_cash)
    dd = eqv / peak - 1.0
    mdd = float(dd.min())

    span_years = max(
        (pd.Timestamp(eqv.index[-1]) - pd.Timestamp(eqv.index[0])).total_seconds()
        / (365.25 * 86400), 1 / 365.25)
    cagr = float((max(float(eqv.iloc[-1]), 0.0) / max(starting_cash, 1e-12))
                 ** (1 / span_years) - 1.0)

    wins = tr.loc[tr["net_pnl"] > 0, "net_pnl"].sum() if len(tr) else 0.0
    losses = abs(tr.loc[tr["net_pnl"] < 0, "net_pnl"].sum()) if len(tr) else 0.0

    return {
        "initial_equity": starting_cash,
        "final_equity": float(eqv.iloc[-1]),
        "total_return": float(eqv.iloc[-1] / starting_cash - 1.0),
        "cagr": cagr,
        "annualized_mean_return_proxy": ann,
        "sharpe": ann / vol if vol > 1e-12 else None,
        "sortino": ann / downside_vol if downside_vol > 1e-12 else None,
        "calmar": cagr / abs(mdd) if mdd < 0 else None,
        "annualized_vol": vol,
        "max_drawdown": mdd,
        "trades": int(len(tr)),
        "win_rate": float((tr["net_pnl"] > 0).mean()) if len(tr) else None,
        "profit_factor": float(wins / losses) if losses > 0 else None,
        "median_trade_return": float(tr["return_on_collateral"].median()) if len(tr) else None,
        "liquidations_proxy": int((tr["reason"] == "LIQUIDATION_PROXY").sum()) if len(tr) else 0,
        "exit_reasons": tr["reason"].value_counts().to_dict() if len(tr) else {},
    }


# ─────────────────────────── engine ───────────────────────────

def run_symbol(df: pd.DataFrame, symbol: str, leverage: float, risk_pct: float,
               stop_pct: float, take_pct: float, fee_rate: float,
               extension_fee_daily: float, maintenance_ratio: float,
               max_hold_bars: int, liq_slippage: float, warmup: int,
               starting_cash: float = 100_000_000.0):
    """F4. Returns (equity_curve, trades, metrics) — the original computed a
    full metrics dict here and then returned only the first two, so sortino,
    calmar, cagr, profit_factor and median_trade_return were unreachable."""
    sig = signal(df)
    equity = starting_cash
    pos: Position | None = None
    trades: list[dict] = []
    curve: list[dict] = []

    if len(df) <= warmup + 2:
        raise RuntimeError(
            f"{symbol}: {len(df)} bars is not enough for a {warmup}-bar warm-up; "
            f"widen --lookback-days or use a finer --resolution")

    for i in range(warmup, len(df) - 1):
        ts = df.index[i]
        row = df.iloc[i]
        next_row = df.iloc[i + 1]
        target = int(sig.iloc[i])

        if pos is not None:
            elapsed = max((ts - pos.last_fee_time).total_seconds(), 0.0)
            if elapsed > 0:
                pos.extension_fee += pos.collateral * extension_fee_daily * elapsed / 86400.0
                pos.last_fee_time = ts

            pos.bars_held += 1
            liq, liq_price = liquidation_proxy(pos, row, maintenance_ratio, liq_slippage)
            stop_hit = (row["low"] <= pos.stop_price if pos.direction == 1
                        else row["high"] >= pos.stop_price)
            take_hit = (row["high"] >= pos.take_price if pos.direction == 1
                        else row["low"] <= pos.take_price)

            # Conservative intrabar priority: liquidation > stop > target.
            exit_reason = exit_price = exit_time = None
            if liq:
                exit_reason, exit_price, exit_time = "LIQUIDATION_PROXY", liq_price, ts
            elif stop_hit:
                exit_reason, exit_price, exit_time = "STOP", pos.stop_price, ts
            elif take_hit:
                exit_reason, exit_price, exit_time = "TAKE", pos.take_price, ts
            elif max_hold_bars and pos.bars_held >= max_hold_bars:
                exit_reason, exit_price, exit_time = "TIME", float(row["close"]), ts
            elif target != pos.direction:
                # F8. A flip fills at the next open, so it is stamped there.
                exit_reason = "SIGNAL_FLIP"
                exit_price = float(next_row["open"])
                exit_time = next_row.name

            if exit_reason:
                equity, trade = close_position(pos, exit_time, float(exit_price),
                                               equity, fee_rate, exit_reason,
                                               pos.extension_fee)
                trades.append(trade)
                pos = None

        # Open at the NEXT bar's open only.
        if pos is None and target != 0:
            entry_price = float(next_row["open"])
            atr_pct = float(row["atr"] / row["close"]) if row["close"] else np.nan
            if np.isfinite(entry_price) and entry_price > 0:
                dist = max(stop_pct, 1.5 * atr_pct if np.isfinite(atr_pct) else stop_pct)
                stop_distance_abs = entry_price * dist

                risk_budget = max(equity, 0.0) * risk_pct
                qty_risk = risk_budget / stop_distance_abs if stop_distance_abs else 0.0
                qty_cap = max(equity, 0.0) * leverage / entry_price
                qty = min(qty_risk, qty_cap)

                notional = qty * entry_price
                collateral = notional / leverage
                entry_fee = notional * fee_rate

                if collateral + entry_fee > equity and (1 / leverage + fee_rate) > 0:
                    # Solve collateral + fee <= equity for notional. The exact
                    # solution lands on the boundary, where rounding can leave
                    # the sum a few ulps above equity and silently reject every
                    # trade, so take a hair under it.
                    notional = max(equity, 0.0) / (1 / leverage + fee_rate) * (1 - 1e-12)
                    qty = notional / entry_price
                    collateral = notional / leverage
                    entry_fee = notional * fee_rate

                # Relative tolerance: an absolute 1e-9 is far below float64
                # resolution at realistic Toman equity values (~1e8).
                tol = max(1e-9, abs(equity) * 1e-12)
                if qty > 0 and collateral > 0 and collateral + entry_fee <= equity + tol:
                    tp_dist = max(take_pct, 2 * dist)
                    equity -= entry_fee
                    pos = Position(
                        symbol=symbol, direction=target,
                        entry_time=next_row.name.isoformat(),
                        entry_price=entry_price, qty=qty, notional=notional,
                        leverage=leverage, collateral=collateral,
                        stop_price=(entry_price * (1 - dist) if target == 1
                                    else entry_price * (1 + dist)),
                        take_price=(entry_price * (1 + tp_dist) if target == 1
                                    else entry_price * (1 - tp_dist)),
                        last_fee_time=next_row.name, entry_fee=entry_fee,
                    )

        mark = equity + (mark_pnl(pos, float(row["close"])) - pos.extension_fee
                         if pos else 0.0)
        curve.append({"timestamp": ts.isoformat(), "equity": max(mark, 0.0)})

    if pos is not None:
        final = df.iloc[-1]
        equity, trade = close_position(pos, df.index[-1], float(final["close"]),
                                       equity, fee_rate, "END_OF_SAMPLE",
                                       pos.extension_fee)
        trades.append(trade)
        curve.append({"timestamp": df.index[-1].isoformat(),
                      "equity": max(equity, 0.0)})

    eq = pd.DataFrame(curve).drop_duplicates("timestamp").set_index("timestamp")
    if eq.empty:
        raise RuntimeError(f"{symbol}: empty equity curve")
    tr = pd.DataFrame(trades)

    bars_per_year = 365 * 24 * 60 / max(infer_minutes(df.index), 1)
    metrics = compute_metrics(eq, tr, bars_per_year, starting_cash)
    eqv = eq["equity"].astype(float)
    eq["drawdown"] = (eqv / eqv.cummax().clip(lower=starting_cash) - 1.0).values
    return eq.reset_index(), tr, metrics


def infer_minutes(idx: pd.DatetimeIndex) -> int:
    if len(idx) < 3:
        return 1440
    diffs = pd.Series(idx[1:] - idx[:-1]).dt.total_seconds().div(60)
    return int(max(1, round(float(diffs.median()))))


def bootstrap_block(returns: np.ndarray, n=2000, block=32, seed=42) -> dict:
    rng = np.random.default_rng(seed)
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 20:
        return {}
    horizon = len(r)
    paths = np.empty(n)
    for k in range(n):
        out: list[float] = []
        while len(out) < horizon:
            start = int(rng.integers(0, horizon))
            out.extend(r[[(start + j) % horizon for j in range(block)]])
        paths[k] = float(np.prod(1.0 + np.array(out[:horizon])) - 1.0)
    q = np.quantile(paths, [0.01, 0.05, 0.50, 0.95, 0.99])
    return {
        "bootstrap_paths": n, "block_bars": block,
        "p01_total_return": float(q[0]), "p05_total_return": float(q[1]),
        "median_total_return": float(q[2]), "p95_total_return": float(q[3]),
        "p99_total_return": float(q[4]),
        "probability_of_loss": float(np.mean(paths < 0)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCIRT")
    ap.add_argument("--resolution", default="15")
    ap.add_argument("--lookback-days", type=int, default=30)
    ap.add_argument("--leverage", type=float, default=3.0)
    ap.add_argument("--risk-pct", type=float, default=0.005)
    ap.add_argument("--stop-pct", type=float, default=0.008)
    ap.add_argument("--take-pct", type=float, default=0.016)
    ap.add_argument("--fee-rate", type=float, default=0.0025)
    ap.add_argument("--extension-fee-daily", type=float, default=0.001)
    ap.add_argument("--maintenance-ratio", type=float, default=0.50)
    ap.add_argument("--max-hold-bars", type=int, default=96)
    ap.add_argument("--liq-slippage", type=float, default=0.001)
    ap.add_argument("--ema-fast", type=int, default=10)
    ap.add_argument("--ema-slow", type=int, default=30)
    ap.add_argument("--atr-n", type=int, default=14)
    ap.add_argument("--slope-lag", type=int, default=3)
    ap.add_argument("--min-coverage", type=float, default=0.80,
                    help="fail the symbol if delivered bars / expected bars is below this")
    ap.add_argument("--output-dir", default="gh_run_output/nobitex_margin")
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    warmup = warmup_bars(args.ema_slow, args.atr_n, args.slope_lag)

    all_metrics = []
    for raw_symbol in [x.strip().upper() for x in args.symbols.split(",") if x.strip()]:
        try:
            raw = fetch_raw(raw_symbol, args.resolution, args.lookback_days)
            coverage = raw.attrs["coverage"]
            # A truncated window must fail loudly rather than be graded as if
            # it were the window that was asked for.
            if coverage["coverage_ratio"] < args.min_coverage:
                raise RuntimeError(
                    f"{raw_symbol}: only {coverage['delivered_bars']} of "
                    f"~{coverage['expected_bars']} expected bars "
                    f"({coverage['coverage_ratio']:.1%}) — refusing to grade a "
                    f"{coverage['actual_span_days']}-day sample as "
                    f"{args.lookback_days} days")

            df = add_indicators(raw, args.ema_fast, args.ema_slow,
                                args.atr_n, args.slope_lag)
            eq, trades, metrics = run_symbol(
                df, raw_symbol, args.leverage, args.risk_pct, args.stop_pct,
                args.take_pct, args.fee_rate, args.extension_fee_daily,
                args.maintenance_ratio, args.max_hold_bars, args.liq_slippage,
                warmup)

            rets = equity_returns(eq["equity"].astype(float))
            metrics.update({
                "symbol": raw_symbol,
                "resolution": args.resolution,
                "leverage_requested": args.leverage,
                "data_start": raw.index[0].isoformat(),
                "data_end": raw.index[-1].isoformat(),
                "bars": int(len(raw)),
                "warmup_bars": warmup,
                "coverage": coverage,
                "bootstrap": bootstrap_block(
                    rets.to_numpy(), n=2000,
                    block=max(8, int(240 / max(infer_minutes(raw.index), 1)))),
            })
            eq.to_csv(out / f"{raw_symbol}_equity.csv", index=False)
            trades.to_csv(out / f"{raw_symbol}_trades.csv", index=False)
            (out / f"{raw_symbol}_metrics.json").write_text(
                json.dumps(metrics, indent=2, ensure_ascii=False, default=str))
            all_metrics.append(metrics)
        except Exception as e:
            err = {"symbol": raw_symbol, "error": f"{type(e).__name__}: {e}"}
            (out / f"{raw_symbol}_ERROR.json").write_text(
                json.dumps(err, indent=2, ensure_ascii=False))
            print(json.dumps(err, ensure_ascii=False))

    summary = {
        "engine": "nobitex_isolated_margin_research_proxy",
        "warning": "Liquidation/maintenance is a research proxy, not an official "
                   "historical reconstruction of the Nobitex risk engine.",
        "assumptions": {
            "execution": "signal at close t -> entry/flip at open t+1",
            "fees_per_side": args.fee_rate,
            "extension_fee_daily": args.extension_fee_daily,
            "maintenance_ratio_proxy": args.maintenance_ratio,
            "liquidation_fill": "breach price, or bar open on a gap through, "
                                "plus adverse slippage",
            "risk_budget_per_trade": args.risk_pct,
            "leverage_cap": args.leverage,
            "warmup_bars": warmup,
        },
        "results": all_metrics,
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
