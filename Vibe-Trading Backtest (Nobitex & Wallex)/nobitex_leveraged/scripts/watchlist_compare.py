#!/usr/bin/env python3
"""Two live Nobitex watchlists, side by side, with a leverage suggestion each.

Strategy A — "ours": the EMA(10/30) trend engine from the uploaded script,
after the debug. Long AND short. Exits: its own stop/take defaults.

Strategy B — "freqtrade Supertrend": the published strategy from the official
freqtrade/freqtrade-strategies repo (user_data/strategies/Supertrend.py, by
@juankysoriano). Entry when three Supertrend indicators are all up, exit when
three differently-parameterised Supertrends are all down. LONG ONLY. Its
parameters are the repo's committed hyperopt output, produced with
`freqtrade hyperopt --hyperopt-loss ShortTradeDurHyperOptLoss
--timerange=20210101- --timeframe=1h --spaces all`.

Fidelity notes, stated rather than buried:
  * The Supertrend indicator here is the canonical formula, not a vendored copy
    of `technical.indicators.supertrend`. The strategy's own docstring warns its
    implementation "is not validated" against the original paper.
  * freqtrade's trailing stop (5% triggered after 14.4% profit) has no equivalent
    in this execution engine and is omitted. Its stoploss (-26.5%) and the first
    rung of its ROI ladder (+8.7%) are mapped onto the engine's stop/take.
  * Both strategies run through the SAME execution engine, the same fee model
    and the same live data, so the comparison isolates the signal rather than
    the surrounding machinery.

Leverage is not taken from either author. It is derived per symbol from that
strategy's own UNLEVERED equity curve, because the growth rate under leverage
is g(L) = L*mu - L^2*sigma^2/2, which is concave with its maximum at the Kelly
fraction mu/sigma^2. Reported is quarter-Kelly, floored against a drawdown
budget, because mu is estimated with large error on a sample this size.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nobitex_leveraged_backtest import (  # noqa: E402
    add_indicators, atr, equity_returns, fetch_raw, infer_minutes, run_symbol,
    signal as signal_ema_trend, warmup_bars,
)

SYMBOLS = ["BTCIRT", "ETHIRT", "SOLIRT", "XRPIRT", "DOGEIRT",
           "ADAIRT", "TRXIRT", "LTCIRT", "BNBIRT", "USDTIRT"]
RESOLUTION = "240"          # 4h: the only setting with both long retention and low churn
LOOKBACK_DAYS = 180
FEE = 0.0025
EXT_FEE = 0.001
MAINT = 0.50
LIQ_SLIP = 0.001

# freqtrade Supertrend.py committed hyperopt params
FT_BUY = [(4, 8), (7, 9), (1, 8)]        # (multiplier, period)
FT_SELL = [(1, 16), (3, 18), (6, 18)]
FT_STOP = 0.265                           # stoploss = -0.265
FT_TAKE = 0.087                           # minimal_roi "0": 0.087

# ours, as published in the uploaded script's defaults
OURS_STOP = 0.008
OURS_TAKE = 0.016

DD_BUDGET = 0.50
LEV_HARD_CAP = 5.0
KELLY_FRACTION = 0.25
LIQ_HORIZON_DAYS = 20


def supertrend_direction(df: pd.DataFrame, period: int, multiplier: float) -> pd.Series:
    """Canonical Supertrend direction: +1 while price is above the band, -1 below."""
    hl2 = (df["high"] + df["low"]) / 2.0
    a = atr(df, period)
    upper = hl2 + multiplier * a
    lower = hl2 - multiplier * a
    close = df["close"].to_numpy()
    up, lo = upper.to_numpy(), lower.to_numpy()
    n = len(df)
    f_up, f_lo = np.full(n, np.nan), np.full(n, np.nan)
    direction = np.zeros(n, dtype=int)

    for i in range(n):
        if i == 0 or np.isnan(up[i]) or np.isnan(f_up[i - 1]):
            f_up[i], f_lo[i] = up[i], lo[i]
            direction[i] = 1
            continue
        f_up[i] = up[i] if (up[i] < f_up[i - 1] or close[i - 1] > f_up[i - 1]) else f_up[i - 1]
        f_lo[i] = lo[i] if (lo[i] > f_lo[i - 1] or close[i - 1] < f_lo[i - 1]) else f_lo[i - 1]
        if direction[i - 1] == 1:
            direction[i] = -1 if close[i] < f_lo[i] else 1
        else:
            direction[i] = 1 if close[i] > f_up[i] else -1
    return pd.Series(direction, index=df.index)


def signal_supertrend_ft(df: pd.DataFrame) -> pd.Series:
    """freqtrade Supertrend: long while entry fired and exit has not. No shorts."""
    buys = [supertrend_direction(df, p, m) for m, p in FT_BUY]
    sells = [supertrend_direction(df, p, m) for m, p in FT_SELL]
    enter = (buys[0] == 1) & (buys[1] == 1) & (buys[2] == 1) & (df["volume"] > 0)
    exit_ = (sells[0] == -1) & (sells[1] == -1) & (sells[2] == -1) & (df["volume"] > 0)

    state = np.zeros(len(df), dtype=int)
    held = 0
    e, x = enter.to_numpy(), exit_.to_numpy()
    for i in range(len(df)):
        if held == 0 and e[i]:
            held = 1
        elif held == 1 and x[i]:
            held = 0
        state[i] = held
    return pd.Series(state, index=df.index)


def sharpe_se(sr_annual: float, n_obs: int, bpy: float) -> float:
    """Lo (2002) asymptotic standard error of an annualised Sharpe ratio."""
    if n_obs < 3:
        return float("nan")
    sr_p = sr_annual / math.sqrt(bpy)
    return math.sqrt((1 + sr_p ** 2 / 2) / n_obs) * math.sqrt(bpy)


def p_liquidation(leverage: float, sigma_daily: float, horizon_days: int,
                  maint: float = 0.005) -> float:
    """First-passage probability to the isolated-margin liquidation barrier.

    Driftless Brownian motion, reflection principle. A lower bound: jumps and
    volatility clustering both push the true probability up.
    """
    if leverage <= 0 or sigma_daily <= 0:
        return float("nan")
    adverse = 1.0 / leverage - maint
    if adverse <= 0:
        return 1.0
    a = -math.log(max(1e-12, 1 - adverse))
    s = sigma_daily * math.sqrt(horizon_days)
    return float(2 * norm.cdf(-a / s))


def evaluate(df_ind: pd.DataFrame, symbol: str, sig: pd.Series, stop: float,
             take: float, warmup: int) -> dict:
    """Backtest this signal UNLEVERED, then derive what leverage it could carry."""
    import nobitex_leveraged_backtest as engine

    original = engine.signal
    engine.signal = lambda _df: sig          # inject the strategy under test
    try:
        eq, trades, m = run_symbol(
            df_ind, symbol, leverage=1.0, risk_pct=1.0, stop_pct=stop,
            take_pct=take, fee_rate=FEE, extension_fee_daily=EXT_FEE,
            maintenance_ratio=MAINT, max_hold_bars=0, liq_slippage=LIQ_SLIP,
            warmup=warmup)
    finally:
        engine.signal = original

    # Buy-and-hold over the SAME graded window. On Toman pairs this is the
    # decisive control: they carry a structural upward drift from currency
    # debasement, so a long-only strategy that simply stays in the market will
    # print a large return with no alpha in it whatsoever.
    graded = df_ind.iloc[warmup:]
    bh = float(graded["close"].iloc[-1] / graded["close"].iloc[0] - 1.0)
    exposure = float((sig.iloc[warmup:] != 0).mean())

    bpy = 365 * 24 * 60 / max(infer_minutes(df_ind.index), 1)
    rets = equity_returns(eq["equity"].astype(float))
    mu = float(rets.mean() * bpy)
    sigma = float(rets.std(ddof=1) * math.sqrt(bpy)) if len(rets) > 2 else 0.0
    sr = mu / sigma if sigma > 1e-12 else float("nan")
    se = sharpe_se(sr, len(rets), bpy) if np.isfinite(sr) else float("nan")
    mdd = abs(float(m["max_drawdown"]))

    kelly = mu / sigma ** 2 if sigma > 1e-12 else float("nan")
    frac_kelly = kelly * KELLY_FRACTION if np.isfinite(kelly) else float("nan")
    dd_cap = DD_BUDGET / mdd if mdd > 1e-9 else float("inf")
    raw = min(frac_kelly, dd_cap) if np.isfinite(frac_kelly) else float("nan")
    suggested = float(np.clip(raw, 0.0, LEV_HARD_CAP)) if np.isfinite(raw) else float("nan")

    return {
        "total_return": m["total_return"], "sharpe": sr, "sharpe_se": se,
        "t_stat": sr / se if se and np.isfinite(se) and se > 0 else float("nan"),
        "mu": mu, "sigma": sigma, "max_dd": -mdd, "trades": m["trades"],
        "win_rate": m["win_rate"], "profit_factor": m["profit_factor"],
        "kelly": kelly, "quarter_kelly": frac_kelly, "dd_cap": dd_cap,
        "suggested_leverage": suggested, "n_obs": len(rets),
        "buy_hold": bh, "excess_vs_bh": m["total_return"] - bh, "exposure": exposure,
    }


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("watchlist_out")
    out_dir.mkdir(parents=True, exist_ok=True)
    warmup = warmup_bars(30, 14, 3)

    strategies = {
        "A_ema_trend_ours": dict(fn=signal_ema_trend, stop=OURS_STOP, take=OURS_TAKE,
                                 sides="long+short"),
        "B_supertrend_freqtrade": dict(fn=signal_supertrend_ft, stop=FT_STOP,
                                       take=FT_TAKE, sides="long only"),
    }

    rows: list[dict] = []
    for symbol in SYMBOLS:
        try:
            raw = fetch_raw(symbol, RESOLUTION, LOOKBACK_DAYS)
            cov = raw.attrs["coverage"]
            if cov["coverage_ratio"] < 0.80:
                print(f"skip {symbol}: coverage {cov['coverage_ratio']:.1%}", file=sys.stderr)
                continue
            df = add_indicators(raw, 10, 30, 14, 3)
            close_rets = df["close"].pct_change().dropna()
            bars_per_day = 86400 / (infer_minutes(df.index) * 60)
            sigma_daily = float(close_rets.std(ddof=1) * math.sqrt(bars_per_day))
        except Exception as exc:  # noqa: BLE001
            print(f"skip {symbol}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue

        for name, cfg in strategies.items():
            try:
                sig = cfg["fn"](df)
                live = int(sig.iloc[-1])
                prev = sig.iloc[warmup:]
                flips = (prev != prev.shift(1)).to_numpy()
                bars_since = int(len(prev) - 1 - np.where(flips)[0][-1])
                res = evaluate(df, symbol, sig, cfg["stop"], cfg["take"], warmup)
                lev = res["suggested_leverage"]
                res.update({
                    "symbol": symbol, "strategy": name, "sides": cfg["sides"],
                    "live_signal": {1: "LONG", -1: "SHORT", 0: "FLAT"}[live],
                    "bars_since_flip": bars_since,
                    "sigma_daily": sigma_daily,
                    "p_liquidation_20d": (p_liquidation(lev, sigma_daily, LIQ_HORIZON_DAYS)
                                          if np.isfinite(lev) and lev >= 1 else None),
                    "last_bar": str(df.index[-1]),
                })
                rows.append(res)
            except Exception as exc:  # noqa: BLE001
                print(f"{symbol}/{name} failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    def fmt(v, pct=False, nd=2):
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return "n/a"
        return f"{v*100:.{nd}f}%" if pct else f"{v:.{nd}f}"

    lines = [f"\n===== LIVE NOBITEX WATCHLISTS — {RESOLUTION}m bars, "
             f"{LOOKBACK_DAYS}-day evidence window =====",
             f"last bar: {rows[0]['last_bar'] if rows else 'n/a'}\n"]

    for name, cfg in strategies.items():
        sub = [r for r in rows if r["strategy"] == name]
        sub.sort(key=lambda r: (r["live_signal"] == "FLAT", -(r["t_stat"] if np.isfinite(r["t_stat"]) else -9)))
        lines.append(f"\n## Watchlist {name}  ({cfg['sides']})\n")
        lines.append("| symbol | live signal | bars since flip | 180d return | buy&hold | "
                     "excess | exposure | Sharpe | t | maxDD | trades | **suggested lev** | P(liq) 20d |")
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in sub:
            lines.append(
                f"| {r['symbol']} | {r['live_signal']} | {r['bars_since_flip']} "
                f"| {fmt(r['total_return'], True)} | {fmt(r['buy_hold'], True)} "
                f"| {fmt(r['excess_vs_bh'], True)} | {fmt(r['exposure'], True, 0)} "
                f"| {fmt(r['sharpe'])} | {fmt(r['t_stat'])} "
                f"| {fmt(r['max_dd'], True)} | {r['trades']} "
                f"| **{fmt(r['suggested_leverage'],nd=1)}x** "
                f"| {fmt(r['p_liquidation_20d'], True, 3)} |")

    # ── comparison ──
    lines.append("\n\n## Where the two disagree\n")
    lines.append("| symbol | A (ours, L/S) | B (freqtrade ST, long only) | agree? "
                 "| A lev | B lev | A 180d | B 180d |")
    lines.append("|---|---|---|:--:|---:|---:|---:|---:|")
    agree = disagree = 0
    for symbol in SYMBOLS:
        a = next((r for r in rows if r["symbol"] == symbol and r["strategy"].startswith("A")), None)
        b = next((r for r in rows if r["symbol"] == symbol and r["strategy"].startswith("B")), None)
        if not a or not b:
            continue
        same = a["live_signal"] == b["live_signal"]
        agree += same
        disagree += (not same)
        lines.append(f"| {symbol} | {a['live_signal']} | {b['live_signal']} "
                     f"| {'YES' if same else 'no'} | {fmt(a['suggested_leverage'],nd=1)}x "
                     f"| {fmt(b['suggested_leverage'],nd=1)}x "
                     f"| {fmt(a['total_return'], True)} | {fmt(b['total_return'], True)} |")
    lines.append(f"\nagreement: {agree}/{agree+disagree} symbols")

    for name in strategies:
        sub = [r for r in rows if r["strategy"] == name and np.isfinite(r["t_stat"])]
        if not sub:
            continue
        best = max(sub, key=lambda r: r["t_stat"])
        se = best["sharpe_se"]
        g = 0.5772156649
        N = len(sub)
        emax = se * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * math.e)))
        dsr = norm.cdf((best["sharpe"] - emax) / se) if se > 0 else float("nan")
        ex = [r["excess_vs_bh"] for r in sub]
        beat = sum(1 for e in ex if e > 0)
        lines.append(f"\n{name}: best Sharpe {best['sharpe']:.2f} ({best['symbol']}), "
                     f"SE {se:.2f}, E[max|no edge] across N={N} = {emax:.2f}, "
                     f"deflated Sharpe = {dsr:.3f}")
        lines.append(f"  vs buy-and-hold: beats it on {beat}/{len(sub)} symbols, "
                     f"mean excess {np.mean(ex)*100:+.2f}%, median {np.median(ex)*100:+.2f}%")

    text = "\n".join(lines)
    (out_dir / "WATCHLIST_COMPARE.md").write_text(text + "\n")
    (out_dir / "watchlists.json").write_text(json.dumps(rows, indent=2, default=str))
    print(text)


if __name__ == "__main__":
    main()
