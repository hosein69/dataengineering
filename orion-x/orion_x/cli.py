"""Command line entry point.

    python -m orion_x.cli signal      one decision on a worked example
    python -m orion_x.cli validate    full walk-forward against the peer panel
    python -m orion_x.cli selftest    the mathematical identities, checked live
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

from .backtest.simulate import simulate_market
from .backtest.walkforward import run_two_pass_validation, run_walk_forward
from .contracts import EngineConfig
from .engine import decide, signal_to_dict
from .version import VERSION

BAR = "=" * 78


def _fmt_bps(x: float) -> str:
    return f"{x * 10000:+.1f}bps"


def _worked_example():
    """A realistic mid-cap perp, built from the reference generator so that the
    volatility, liquidity and flow are internally consistent."""
    from .backtest.walkforward import _build_snapshots

    path = simulate_market(n_hours=1400, n_assets=8, alpha_strength=1.0, seed=20260910)
    # Pick the most liquid name: the one where the economics have a chance.
    sym = max(path.assets, key=lambda s: float(path.assets[s]["hourly_volume"][-200:].mean()))
    return _build_snapshots(path, sym, 1200, EngineConfig()), path, sym


def cmd_signal(args) -> int:
    (market, asset), path, sym = _worked_example()
    cfg = EngineConfig(horizon_hours=args.horizon)
    card = decide(market, asset, config=cfg, portfolio_equity=args.equity)

    print(BAR)
    print(f"ORION-X v{VERSION}   signal card   {card.symbol}   {card.decision_time:%Y-%m-%d %H:%M} UTC")
    print(BAR)
    print(f"decision            {card.decision}")
    print(f"composite evidence  {card.composite:+.4f}   (score {card.score:.1f}/100, dispersion-standardized z = {card.alpha['composite_z']:+.2f})")
    print(f"directional conf.   {card.confidence:.3f}      uncertainty {card.uncertainty:.3f}")
    print(f"regime              {card.regime}  (risk appetite {card.risk_appetite:+.2f}, stress {card.market_stress:.2f})")
    print(f"                    " + "  ".join(f"{k}:{v:.2f}" for k, v in sorted(card.regime_probabilities.items(), key=lambda kv: -kv[1])[:3]))

    print(f"\n-- volatility " + "-" * 62)
    v = card.volatility
    print(f"sigma 1h {v['sigma_per_hour']:.5f}   sigma {cfg.horizon_hours:.0f}h {v['sigma_horizon']:.5f}   "
          f"annualized {v['annualized']:.0%}   jump share {v['jump_share']:.2f}   persistence {v['persistence']:.2f}")

    print(f"\n-- evidence blocks (signed, -1 to +1) " + "-" * 38)
    for k, s in sorted(card.blocks.items(), key=lambda kv: -abs(kv[1])):
        rel = card.block_reliability.get(k, 1.0)
        sens = card.sensitivity.get(k, 0.0)
        bar = "#" * int(abs(s) * 22)
        side = "long " if s > 0 else ("short" if s < 0 else "     ")
        print(f"  {k:14}{s:+7.3f} {side} rel {rel:.2f}  d(composite)/d = {sens:+.3f}  {bar}")

    print(f"\n-- barriers and first-passage " + "-" * 46)
    b, p, pl = card.barriers, card.probabilities, card.plan
    print(f"  take profit {pl.take_profit:12.6g}  ({b['tp_sigma']:.2f} horizon sigma)   P = {p['take_profit']:.3f}")
    print(f"  stop loss   {pl.stop_loss:12.6g}  ({b['sl_sigma']:.2f} horizon sigma)   P = {p['stop_loss']:.3f}")
    print(f"  timeout at  {cfg.horizon_hours:.0f}h                                  P = {p['timeout']:.3f}")
    print(f"  scale out   {pl.scale_out_1:.6g} / {pl.scale_out_2:.6g}     reference {pl.reference_price:.6g}")

    print(f"\n-- economics " + "-" * 63)
    c = card.costs
    print(f"  forecast drift      {_fmt_bps(card.alpha['drift_per_hour'])}/hour "
          f"(IC {card.alpha['information_coefficient']:+.4f} x sigma x z)")
    print(f"  breakeven drift     {_fmt_bps(card.breakeven_drift_per_hour)}/hour  <- what the trade needs")
    print(f"  gross expected      {_fmt_bps(card.expected_return_gross)}")
    print(f"  costs               {_fmt_bps(-c['total'])}   "
          f"(fees {c['fees']*10000:.1f} spread {c['spread']*10000:.1f} impact {c['impact']*10000:.1f} funding {c['funding']*10000:+.1f})")
    print(f"  net expected        {_fmt_bps(card.expected_return_net)}   hurdle {card.edge_hurdle*10000:.1f}bps")
    print(f"  edge / outcome sd   {card.edge_to_risk:+.4f}   (per-trade information ratio)")
    print(f"  expected R:R        {card.expected_rr:.2f}   (reported, not gated)")

    print(f"\n-- sizing " + "-" * 66)
    sz = card.size
    print(f"  position fraction   {sz['fraction']:.4f} of equity")
    print(f"  full Kelly would be {sz['kelly_full']:.3f}; caps -> vol target {sz['vol_target_cap']:.3f}, "
          f"liquidity {sz['liquidity_cap']:.3f}, risk limit {sz['risk_cap']:.3f}")

    if card.horizon_curve:
        print(f"\n-- net edge by horizon " + "-" * 53)
        curve = [(int(k[:-1]), val) for k, val in card.horizon_curve.items() if k.endswith("h")]
        sigma_h = card.volatility["sigma_per_hour"]
        for h, val in sorted(curve):
            # The hurdle scales with horizon volatility, so it has to be
            # recomputed per row rather than compared against this trade's.
            hurdle = max(cfg.min_net_edge_sigma * sigma_h * math.sqrt(h), cfg.min_net_edge_abs)
            mark = " <-- clears its hurdle" if val >= hurdle else ""
            print(f"  {h:4d}h  {_fmt_bps(val)}   hurdle {hurdle*10000:5.1f}bps{mark}")
        mv = card.horizon_curve["minimum_viable_hours"]
        print(f"  minimum viable horizon: {'none in range' if mv < 0 else f'{mv:.0f}h'}")

    print(f"\n-- gates " + "-" * 67)
    for k, ok in card.gates.items():
        print(f"  [{'x' if ok else ' '}] {k}")
    if card.reasons:
        print("\n-- reasoning " + "-" * 63)
        for r in card.reasons[:12]:
            print(f"  . {r}")
    if card.warnings:
        print("\n-- warnings " + "-" * 64)
        for w in card.warnings[:12]:
            print(f"  ! {w}")
    print(BAR)

    if args.json:
        print(json.dumps(signal_to_dict(card), indent=2, default=str))
    return 0


def cmd_validate(args) -> int:
    print(BAR)
    print(f"ORION-X v{VERSION}   walk-forward validation")
    print(BAR)
    for alpha, label in ((0.0, "NULL MARKET (unpredictable by construction)"),
                         (1.0, "PLANTED ALPHA (OFI leads idiosyncratic return)")):
        path = simulate_market(n_hours=args.hours, n_assets=args.assets, alpha_strength=alpha, seed=args.seed)
        cfg = EngineConfig(horizon_hours=args.horizon)
        step = max(int(args.horizon / 2), 6)
        first, res = run_two_pass_validation(path, cfg, step_hours=step, train_frac=0.5)

        print(f"\n{label}")
        if path.truth.get("planted_ic"):
            print(f"  planted IC (the ceiling any model could reach): {path.truth['planted_ic']:+.4f}")
        print(f"  ORION-X composite IC on the training half: {first.information_coefficient:+.4f}")
        print(f"  ORION-X composite IC on the held-out half:  {res.information_coefficient:+.4f}")
        for n in res.notes:
            print(f"  {n}")
        print(f"\n  {'strategy':22}{'trades':>8}{'SR/yr':>8}{'DSR':>8}{'PSR':>8}{'maxDD':>8}{'total':>9}")
        for k, v in sorted(res.per_strategy.items(), key=lambda kv: -kv[1].sharpe_annual):
            flag = "  <-- ORION-X" if k.startswith("ORION") else ""
            print(f"  {k:22}{res.trade_counts[k]:8d}{v.sharpe_annual:8.2f}{v.deflated_sharpe:8.3f}"
                  f"{v.psr:8.3f}{v.max_drawdown:8.1%}{v.total_return:9.2%}{flag}")
        if res.calibration:
            c = res.calibration
            print(f"\n  calibration of P(target): brier {c['brier']:.4f} = reliability {c['reliability']:.4f} "
                  f"- resolution {c['resolution']:.4f} + uncertainty {c['uncertainty']:.4f}")
        print(f"\n  Deflated Sharpe is the probability the true Sharpe exceeds the best of "
              f"{len(res.per_strategy)} noise strategies.\n  Anything below ~0.90 is not evidence of skill.")
    print(BAR)
    return 0


def cmd_selftest(args) -> int:
    from .barriers import barrier_probs, barrier_probs_mc, survival_moment

    print(BAR)
    print(f"ORION-X v{VERSION}   mathematical self-test")
    print(BAR)
    ok = True

    print("\n1. Gambler's ruin limit: driftless, no time limit -> P(target) = down / (up + down)")
    for up, dn in ((0.03, 0.06), (0.07, 0.02)):
        p = barrier_probs(0.0, 0.02, 500_000.0, up, dn)
        want = dn / (up + dn)
        good = abs(p.take_profit - want) < 1e-5
        ok &= good
        print(f"   up={up} down={dn}: got {p.take_profit:.6f} want {want:.6f}  [{'ok' if good else 'FAIL'}]")

    print("\n2. Martingale identity: P(tp)*up - P(sl)*down + E[X 1_survive] = 0")
    for up, dn in ((0.0285, 0.0171), (0.02, 0.06), (0.08, 0.02)):
        p = barrier_probs(0.0, 0.012, 7.0, up, dn)
        _, ex = survival_moment(0.0, 0.012, 7.0, up, dn)
        resid = p.take_profit * up - p.stop_loss * dn + ex
        good = abs(resid) < 1e-9
        ok &= good
        print(f"   up={up} down={dn}: residual {resid:+.3e}  [{'ok' if good else 'FAIL'}]")

    print("\n3. Analytic series vs independent Monte Carlo (bridge-corrected)")
    for mu, sg, T, up, dn in ((0.0005, 0.012, 7, 0.05, 0.037), (0.004, 0.010, 7, 0.03, 0.03)):
        a = barrier_probs(mu, sg, T, up, dn)
        b = barrier_probs_mc(mu, sg, T, up, dn, paths=200_000, seed=11, steps=256)
        d = max(abs(x - y) for x, y in zip(a.as_tuple(), b.as_tuple()))
        good = d < 0.006
        ok &= good
        print(f"   mu={mu}: series {tuple(round(x,4) for x in a.as_tuple())} "
              f"mc {tuple(round(x,4) for x in b.as_tuple())} maxdiff {d:.4f}  [{'ok' if good else 'FAIL'}]")

    print("\n4. Two independent computations of P(timeout) must agree")
    p = barrier_probs(0.0008, 0.013, 7.0, 0.03, 0.02)
    ps, _ = survival_moment(0.0008, 0.013, 7.0, 0.03, 0.02)
    good = abs(p.timeout - ps) < 1e-6
    ok &= good
    print(f"   absorption flux {p.timeout:.8f} vs density quadrature {ps:.8f}  [{'ok' if good else 'FAIL'}]")

    print(BAR)
    print("ALL CHECKS PASSED" if ok else "SELF-TEST FAILED")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="orion_x", description=f"ORION-X v{VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("signal", help="produce one signal card")
    s.add_argument("--horizon", type=float, default=7.0)
    s.add_argument("--equity", type=float, default=1_000_000.0)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_signal)

    v = sub.add_parser("validate", help="walk-forward against the peer panel")
    v.add_argument("--hours", type=int, default=4400)
    v.add_argument("--assets", type=int, default=12)
    v.add_argument("--horizon", type=float, default=7.0)
    v.add_argument("--seed", type=int, default=20260910)
    v.set_defaults(func=cmd_validate)

    t = sub.add_parser("selftest", help="check the mathematical identities")
    t.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
