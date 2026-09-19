#!/usr/bin/env python3
"""Separate skill from market direction, and test the short side on its own.

"Beats buy-and-hold" was the wrong test and it was leaned on far too hard. A
strategy with 60% exposure mechanically trails buy-and-hold in a rising market
however good its timing is, and mechanically beats it in a falling one however
bad. Over a window where nearly everything rose, that statistic measured the
regime, not the strategy.

The regime-free question is whether anything survives once the market's own
move is removed:

    r_strategy,t = alpha + beta * r_market,t + e_t

beta is the exposure the strategy happened to carry; alpha is what is left, and
it is what "skill" has to mean. It is reported annualised with the t-statistic
from the regression, so it can be read against the same significance bar as
everything else here.

The market is the equal-weight return of the same universe, which is the
portfolio a trader with no view would hold.

Also tests long and short separately. If the strategy were merely a long
position in disguise, its short side would have no edge at all — and if the
short side works, the up-market alibi for its losses does not hold.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maximize import load_history, newest_snapshot  # noqa: E402
from nobitex_leveraged_backtest import (  # noqa: E402
    add_indicators, equity_returns, run_symbol, warmup_bars,
)
from watchlist_compare import (  # noqa: E402
    EXT_FEE, FT_BUY, FT_SELL, FT_STOP, FT_TAKE, LIQ_SLIP, MAINT, RESOLUTION,
    signal_supertrend_ft, supertrend_direction,
)

BPY = (365 * 24 * 60) / float(RESOLUTION)
OURS_STOP, OURS_TAKE = 0.08, 0.05


def ema_long_short(df: pd.DataFrame) -> pd.Series:
    """The project's own signal: +1 above the slow EMA, -1 below."""
    fast, slow = df["ema_fast"], df["ema_slow"]
    return pd.Series(np.where(fast > slow, 1, -1), index=df.index)


def short_only(df: pd.DataFrame) -> pd.Series:
    s = ema_long_short(df)
    return pd.Series(np.where(s.to_numpy() == -1, -1, 0), index=df.index)


def long_only_ema(df: pd.DataFrame) -> pd.Series:
    s = ema_long_short(df)
    return pd.Series(np.where(s.to_numpy() == 1, 1, 0), index=df.index)


def run(df: pd.DataFrame, sig: pd.Series, stop: float, take: float,
        warmup: int, fee: float):
    import nobitex_leveraged_backtest as engine
    original = engine.signal
    engine.signal = lambda _d: sig
    try:
        eq, trades, m = run_symbol(
            df, "x", leverage=1.0, risk_pct=1.0, stop_pct=stop, take_pct=take,
            fee_rate=fee, extension_fee_daily=EXT_FEE, maintenance_ratio=MAINT,
            max_hold_bars=10**9, liq_slippage=LIQ_SLIP, warmup=warmup)
    except Exception:  # noqa: BLE001
        return None, None
    finally:
        engine.signal = original
    if not len(eq):
        return None, None
    c = pd.Series(eq["equity"].astype(float).to_numpy(),
                  index=pd.to_datetime(eq["timestamp"], utc=True))
    return c, trades


def ols_alpha(rs: pd.Series, rm: pd.Series) -> dict:
    """Annualised alpha and beta, with the t-statistic on alpha."""
    j = pd.concat([rs, rm], axis=1, sort=True).dropna()
    if len(j) < 30:
        return {}
    y, x = j.iloc[:, 0].to_numpy(), j.iloc[:, 1].to_numpy()
    X = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    n, dof = len(y), len(y) - 2
    XtX_inv = np.linalg.inv(X.T @ X)

    s2 = float(resid @ resid) / dof
    a_se_ols = math.sqrt((s2 * XtX_inv)[0, 0])

    # Newey-West. These positions are held for tens of bars, so residuals are
    # strongly autocorrelated and the OLS standard error is too small — it would
    # report significance the data does not support. The lag follows the usual
    # 4(n/100)^(2/9) rule.
    L = max(1, int(round(4 * (n / 100) ** (2 / 9))))
    S = (X * resid[:, None]).T @ (X * resid[:, None])
    for lag in range(1, L + 1):
        w = 1 - lag / (L + 1)
        A = (X[lag:] * resid[lag:, None]).T @ (X[:-lag] * resid[:-lag, None])
        S += w * (A + A.T)
    cov_hac = XtX_inv @ S @ XtX_inv
    a_se = math.sqrt(max(cov_hac[0, 0], 0.0))

    return {"alpha_ann": float(coef[0] * BPY), "beta": float(coef[1]),
            "alpha_t_ols": float(coef[0] / a_se_ols) if a_se_ols > 0 else float("nan"),
            "alpha_t": float(coef[0] / a_se) if a_se > 0 else float("nan"),
            "nw_lag": L,
            "r2": float(1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))),
            "n": n}


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("alpha_out")
    out.mkdir(parents=True, exist_ok=True)
    snap = newest_snapshot()
    man = json.loads((snap / "manifest.json").read_text())
    fee = float(man["fee_per_side"])
    warmup = warmup_bars(30, 14, 3)

    raw, src = load_history()
    print(f"data: {src}; fee {fee:.4%}/side", file=sys.stderr)

    frames = {}
    for s, d in raw.items():
        try:
            frames[s] = add_indicators(d, 10, 30, 14, 3)
        except Exception:  # noqa: BLE001
            pass

    # The market: equal-weight return of the same universe.
    mkt = pd.DataFrame({s: d["close"].pct_change() for s, d in frames.items()})
    rm = mkt.mean(axis=1).dropna()
    mkt_total = float((1 + rm).prod() - 1)
    up_bars = float((rm > 0).mean())
    print(f"market: {mkt_total*100:+.1f}% over {len(rm)} bars, "
          f"{up_bars:.0%} of bars up", file=sys.stderr)

    variants = {
        "B_supertrend_long_only": (signal_supertrend_ft, FT_STOP, FT_TAKE),
        "A_ema_long_short": (ema_long_short, OURS_STOP, OURS_TAKE),
        "A_ema_LONG_side_only": (long_only_ema, OURS_STOP, OURS_TAKE),
        "A_ema_SHORT_side_only": (short_only, OURS_STOP, OURS_TAKE),
    }

    rows, curves = [], {}
    for name, (fn, stop, take) in variants.items():
        per = {}
        for s, d in frames.items():
            c, tr = run(d, fn(d), stop, take, warmup, fee)
            if c is not None:
                per[s] = equity_returns(c)
        if not per:
            continue
        pr = pd.DataFrame(per).mean(axis=1).dropna()
        curves[name] = pr
        eqc = (1 + pr).cumprod()
        total = float(eqc.iloc[-1] - 1)
        mdd = float((eqc / eqc.cummax() - 1).min())
        sd = float(pr.std(ddof=1) * math.sqrt(BPY))
        sr = float(pr.mean() * BPY) / sd if sd > 1e-12 else float("nan")
        reg = ols_alpha(pr, rm)
        rows.append({"variant": name, "symbols": len(per), "total": total,
                     "sharpe": sr, "max_dd": mdd, **reg})

    L = ["\n===== SKILL OR DIRECTION? =====",
         f"market (equal weight, {len(frames)} symbols): {mkt_total*100:+.1f}% "
         f"over the window, {up_bars:.0%} of bars up\n",
         "| portfolio | total | Sharpe | maxDD | beta | **alpha (ann)** "
         "| t naive | **t Newey-West** | R² |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        L.append(f"| {r['variant']} | {r['total']*100:+.2f}% | {r['sharpe']:.2f} "
                 f"| {r['max_dd']*100:.2f}% | {r.get('beta', float('nan')):.2f} "
                 f"| **{r.get('alpha_ann', float('nan'))*100:+.2f}%** "
                 f"| {r.get('alpha_t_ols', float('nan')):.2f} "
                 f"| **{r.get('alpha_t', float('nan')):.2f}** "
                 f"| {r.get('r2', float('nan')):.2f} |")
    L += ["",
          "beta is the market exposure the variant carried; alpha is what is left",
          "after the market's own move is removed. |t| under about 2 means the",
          "alpha is not distinguishable from zero, whichever way the market went."]
    text = "\n".join(L)
    (out / "ALPHA_BETA.md").write_text(text + "\n")
    (out / "alpha_beta.json").write_text(json.dumps(rows, indent=2, default=str))
    print(text)


if __name__ == "__main__":
    main()
