#!/usr/bin/env python3
"""Search for the highest-return configuration, and then report what it is worth.

Asked to maximise return, the tempting move is to sweep parameters over the
whole 180 days and quote the winner. That number is not a return, it is the
maximum of a few hundred draws from noise, and this project has spent its whole
life measuring exactly that inflation. So the search is run under two rules:

  1. TRAIN/TEST SPLIT. Parameters are chosen on the first 60% of the window and
     scored on the last 40%, which the search never sees. The test figure is
     the only one that means anything.

  2. ONE CONFIG FOR THE WHOLE UNIVERSE. Selection maximises the mean excess
     over buy-and-hold ACROSS symbols, rather than fitting each symbol its own
     parameters. Per-symbol fitting turns 37 searches into 37 chances to be
     lucky; a single config has to work everywhere to win.

The multiple-testing correction then uses the real number of configurations
tried, not the number of symbols, because the search space is what inflates the
winner. A config that survives that is worth trading; one that does not is a
plot of noise.

Also measures the lever the per-symbol tables miss entirely: holding several
symbols at once. Concentration is what a single-symbol table optimises by
accident, and it is the most expensive way to buy return.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nobitex_leveraged_backtest import (  # noqa: E402
    add_indicators, equity_returns, fetch_raw, run_symbol, warmup_bars,
)
from watchlist_compare import (  # noqa: E402
    EXT_FEE, FT_BUY, FT_SELL, FT_STOP, FT_TAKE, LIQ_SLIP, LOOKBACK_DAYS, MAINT,
    RESOLUTION, load_fee, load_lev_cap, load_symbols, sharpe_se,
    supertrend_direction as supertrend,
)

TRAIN_FRAC = 0.60
# A deliberately small grid. Every extra axis multiplies the search space and
# raises the bar the winner must clear, so only parameters with a mechanical
# reason to matter are swept.
MULTS = [1.5, 2.0, 3.0, 4.0, 5.0]
PERIODS = [7, 10, 14, 20]
TAKES = [0.05, 0.087, 0.15]
STOPS = [0.10, 0.265]
GAMMA = 0.5772156649


def st_dir(df: pd.DataFrame, mult: float, period: int,
           cache: dict) -> np.ndarray:
    key = (mult, period)
    if key not in cache:
        cache[key] = supertrend(df, period, mult).to_numpy()
    return cache[key]


def make_signal(df: pd.DataFrame, mult: float, period: int,
                cache: dict) -> pd.Series:
    """Long while the Supertrend is up. One band, not three: the freqtrade
    strategy used six with committed hyperopt values, and re-fitting six here
    would be fitting 12 numbers to 648 bars."""
    return pd.Series(np.where(st_dir(df, mult, period, cache) == 1, 1, 0),
                     index=df.index)


def score(df: pd.DataFrame, sig: pd.Series, stop: float, take: float,
          warmup: int, fee: float) -> dict | None:
    import nobitex_leveraged_backtest as engine
    original = engine.signal
    engine.signal = lambda _df: sig
    try:
        eq, _tr, m = run_symbol(
            df, "opt", leverage=1.0, risk_pct=1.0, stop_pct=stop,
            take_pct=take, fee_rate=fee, extension_fee_daily=EXT_FEE,
            maintenance_ratio=MAINT, max_hold_bars=10**9,
            liq_slippage=LIQ_SLIP, warmup=warmup)
    except Exception:  # noqa: BLE001
        return None
    finally:
        engine.signal = original
    if not len(eq):
        return None
    bh = float(df["close"].iloc[-1] / df["close"].iloc[warmup] - 1)
    return {"ret": m["total_return"], "bh": bh,
            "excess": m["total_return"] - bh, "trades": m["trades"],
            "eq": pd.Series([r["equity"] for r in eq],
                            index=[r["time"] for r in eq])}


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("max_out")
    out.mkdir(parents=True, exist_ok=True)

    symbols, src = load_symbols()
    fee, fee_src = load_fee()
    lev_cap, cap_src = load_lev_cap()
    warmup = warmup_bars(30, 14, 3)
    print(f"universe: {len(symbols)} ({src})", file=sys.stderr)
    print(f"fee {fee:.4%}/side ({fee_src}); venue cap {lev_cap:g}x ({cap_src})",
          file=sys.stderr)

    frames: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    caches: dict[str, dict] = {}
    for s in symbols:
        try:
            raw = fetch_raw(s, RESOLUTION, LOOKBACK_DAYS)
            if raw.attrs["coverage"]["coverage_ratio"] < 0.80:
                continue
            df = add_indicators(raw, 10, 30, 14, 3)
            cut = int(len(df) * TRAIN_FRAC)
            if cut <= warmup + 10 or len(df) - cut <= warmup + 10:
                continue
            frames[s] = (df.iloc[:cut].copy(), df.iloc[cut:].copy())
            caches[s] = {"train": {}, "test": {}}
        except Exception as exc:  # noqa: BLE001
            print(f"{s}: {type(exc).__name__}: {exc}", file=sys.stderr)
    print(f"usable: {len(frames)} symbols", file=sys.stderr)
    if not frames:
        raise SystemExit("no usable symbols")

    grid = list(itertools.product(MULTS, PERIODS, TAKES, STOPS))
    print(f"grid: {len(grid)} configurations", file=sys.stderr)

    rows = []
    for n, (mult, per, take, stop) in enumerate(grid, 1):
        ex = []
        for s, (tr, _te) in frames.items():
            sig = make_signal(tr, mult, per, caches[s]["train"])
            r = score(tr, sig, stop, take, warmup, fee)
            if r:
                ex.append(r["excess"])
        if ex:
            rows.append({"mult": mult, "period": per, "take": take,
                         "stop": stop, "train_mean_excess": float(np.mean(ex)),
                         "train_median_excess": float(np.median(ex)),
                         "train_beat": int(sum(1 for e in ex if e > 0)),
                         "n": len(ex)})
        if n % 20 == 0:
            print(f"  {n}/{len(grid)} configs", file=sys.stderr)

    rows.sort(key=lambda r: -r["train_mean_excess"])
    best = rows[0]
    print(f"\nbest on TRAIN: {best}", file=sys.stderr)

    # Score the winner, and the incumbent, on data the search never saw.
    def test_all(sig_fn, stop, take, label):
        per_sym, curves = [], {}
        for s, (_tr, te) in frames.items():
            r = score(te, sig_fn(s, te), stop, take, warmup, fee)
            if r:
                per_sym.append({"symbol": s, **{k: v for k, v in r.items()
                                                if k != "eq"}})
                curves[s] = r["eq"]
        return label, per_sym, curves

    def best_sig(s, d):
        return make_signal(d, best["mult"], best["period"], caches[s]["test"])

    def ft_sig(_s, d):
        buy = np.ones(len(d), dtype=bool)
        for m, p in FT_BUY:
            buy &= supertrend(d, p, m).to_numpy() == 1
        sell = np.ones(len(d), dtype=bool)
        for m, p in FT_SELL:
            sell &= supertrend(d, p, m).to_numpy() == -1
        state, cur = np.zeros(len(d), dtype=int), 0
        for i in range(len(d)):
            cur = 1 if buy[i] else (0 if sell[i] else cur)
            state[i] = cur
        return pd.Series(state, index=d.index)

    results = {}
    for label, per_sym, curves in [
            test_all(best_sig, best["stop"], best["take"], "optimised"),
            test_all(ft_sig, FT_STOP, FT_TAKE, "incumbent_freqtrade")]:
        ex = [r["excess"] for r in per_sym]
        rets = [r["ret"] for r in per_sym]
        results[label] = {
            "per_symbol": per_sym,
            "mean_excess": float(np.mean(ex)) if ex else float("nan"),
            "median_excess": float(np.median(ex)) if ex else float("nan"),
            "beat": int(sum(1 for e in ex if e > 0)), "n": len(ex),
            "mean_return": float(np.mean(rets)) if rets else float("nan"),
            "curves": curves,
        }

    # Portfolio: hold every symbol the config is long, equal weight. This is the
    # return lever a per-symbol table cannot show, and the only one here that
    # does not come from picking a winner after the fact.
    bpy = (365 * 24 * 60) / float(RESOLUTION)     # bars per year at this resolution
    port = {}
    for label in results:
        cur = results[label]["curves"]
        if not cur:
            continue
        rets = pd.DataFrame({s: equity_returns(c) for s, c in cur.items()})
        pr = rets.mean(axis=1).dropna()          # equal weight, daily rebalance
        if len(pr) < 3:
            continue
        total = float((1 + pr).prod() - 1)
        mu = float(pr.mean() * bpy)
        sd = float(pr.std(ddof=1) * math.sqrt(bpy))
        sr = mu / sd if sd > 1e-12 else float("nan")
        se = sharpe_se(sr, len(pr), bpy) if np.isfinite(sr) else float("nan")
        eqc = (1 + pr).cumprod()
        mdd = float((eqc / eqc.cummax() - 1).min())
        port[label] = {
            "unlevered_return": total, "sharpe": sr, "t": sr / se if se else float("nan"),
            "max_dd": mdd, "n_symbols": len(cur),
            "levered_return": float((1 + pr * lev_cap).prod() - 1),
            "levered_max_dd": float(((1 + pr * lev_cap).cumprod() /
                                     (1 + pr * lev_cap).cumprod().cummax() - 1).min()),
        }

    # The correction that matters: the winner was the best of len(grid) tries.
    N = len(rows)
    sr_best = port.get("optimised", {}).get("sharpe", float("nan"))
    se_best = (sharpe_se(sr_best, len(frames) and 400, bpy)
               if np.isfinite(sr_best) else float("nan"))
    if np.isfinite(sr_best) and np.isfinite(se_best) and se_best > 0 and N > 1:
        emax = se_best * ((1 - GAMMA) * norm.ppf(1 - 1 / N)
                          + GAMMA * norm.ppf(1 - 1 / (N * math.e)))
        dsr = float(norm.cdf((sr_best - emax) / se_best))
    else:
        emax = dsr = float("nan")

    L = [f"\n===== MAXIMISING RETURN, HONESTLY ({RESOLUTION}m, {LOOKBACK_DAYS}d) =====",
         f"universe {len(frames)} margin-tradeable symbols; fee {fee:.4%}/side; "
         f"venue cap {lev_cap:g}x",
         f"train = first {TRAIN_FRAC:.0%} of the window, test = the rest "
         f"(the search never sees it)\n",
         f"## Grid: {len(grid)} configurations\n",
         "| rank | mult | period | take | stop | train mean excess | beats B&H |",
         "|---:|---:|---:|---:|---:|---:|---:|"]
    for i, r in enumerate(rows[:10], 1):
        L.append(f"| {i} | {r['mult']} | {r['period']} | {r['take']:.1%} "
                 f"| {r['stop']:.1%} | {r['train_mean_excess']*100:+.2f}% "
                 f"| {r['train_beat']}/{r['n']} |")
    L.append(f"\nworst of the {len(rows)}: "
             f"{rows[-1]['train_mean_excess']*100:+.2f}% mean excess — the spread "
             f"between best and worst is what the search had to choose from.\n")

    L += ["\n## Out of sample (the only numbers that count)\n",
          "| config | mean return | mean excess vs B&H | median excess | beats B&H |",
          "|---|---:|---:|---:|---:|"]
    for label, r in results.items():
        L.append(f"| {label} | {r['mean_return']*100:+.2f}% "
                 f"| {r['mean_excess']*100:+.2f}% | {r['median_excess']*100:+.2f}% "
                 f"| {r['beat']}/{r['n']} |")

    if port:
        L += ["\n\n## Holding all of them at once, equal weight\n",
              "| config | unlevered | Sharpe | t | maxDD "
              f"| at {lev_cap:g}x | maxDD at {lev_cap:g}x |",
              "|---|---:|---:|---:|---:|---:|---:|"]
        for label, p in port.items():
            L.append(f"| {label} | {p['unlevered_return']*100:+.2f}% "
                     f"| {p['sharpe']:.2f} | {p['t']:.2f} "
                     f"| {p['max_dd']*100:.2f}% | {p['levered_return']*100:+.2f}% "
                     f"| {p['levered_max_dd']*100:.2f}% |")

    L += [f"\n\n## What the search cost\n",
          f"best out-of-sample portfolio Sharpe: {sr_best:.2f}",
          f"E[max Sharpe | no skill] over N={N} configurations: {emax:.2f}",
          f"**deflated Sharpe: {dsr:.3f}**",
          "",
          "The correction uses the number of CONFIGURATIONS, not symbols: the",
          "search space is what inflates a winner. Below ~0.95 the configuration",
          "is not distinguishable from the best of that many coin flips."]

    text = "\n".join(L)
    (out / "MAXIMISE.md").write_text(text + "\n")
    (out / "maximise.json").write_text(json.dumps(
        {"grid": rows, "best": best, "portfolio": port,
         "out_of_sample": {k: {kk: vv for kk, vv in v.items() if kk != "curves"}
                           for k, v in results.items()},
         "deflated_sharpe": dsr, "n_configs": N}, indent=2, default=str))
    print(text)


if __name__ == "__main__":
    main()
