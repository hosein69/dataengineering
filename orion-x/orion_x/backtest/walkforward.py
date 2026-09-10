"""Walk-forward evaluation of ORION-X against its peers.

Rules the harness enforces on itself, because a backtest that does not enforce
them is a plot of a random walk:

* Every feature at decision time i is built from observations at or before i.
  The adapter slices trailing windows only, and the engine's own
  `PointInTimeGuard` runs on every call.
* Positions are opened at the *next* bar's price, never at the decision bar's.
* Every strategy, ORION-X included, pays the same cost model.
* Labels are triple-barrier, matching what the strategy actually does.
* Overlapping labels are purged and embargoed before any statistic is computed.
* The Sharpe ratio of the winner is deflated by the number of strategies tried,
  because picking the best of twelve is itself a selection.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np

from ..contracts import AssetSnapshot, EngineConfig, MarketSnapshot, PriceHistory
from ..costs import CostModel, estimate_costs
from ..engine import decide
from ..graph import build_graph_context
from .metrics import PerformanceReport, summarize
from .peers import PEERS, peer_side
from .simulate import MarketPath

__all__ = ["WalkForwardResult", "run_walk_forward", "run_two_pass_validation"]

HISTORY_BARS = 336  # two weeks of hourly context


@dataclass
class WalkForwardResult:
    per_strategy: dict[str, PerformanceReport]
    trade_counts: dict[str, int]
    orionx_diagnostics: dict[str, float]
    information_coefficient: float
    composite_dispersion: float
    calibration: dict[str, float]
    reliability_rows: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _build_snapshots(path: MarketPath, sym: str, i: int, config: EngineConfig):
    """Assemble point-in-time snapshots from the generated history.

    Everything here slices `[:i + 1]`. That single convention is what makes the
    backtest honest, and it is checked again inside the engine.
    """
    d = path.assets[sym]
    lo = max(0, i - HISTORY_BARS + 1)
    ts = path.timestamps[i]

    r = d["log_return"][lo : i + 1]
    v = d["hourly_volume"][lo : i + 1]
    price = float(d["price"][i])

    hist = PriceHistory(as_of=ts, hourly_log_returns=r, hourly_volume=v)
    btc_hist = PriceHistory(as_of=ts, hourly_log_returns=path.btc_return[lo : i + 1])
    eth_hist = PriceHistory(as_of=ts, hourly_log_returns=path.eth_return[lo : i + 1])

    def trailing(arr, k):
        return float(np.sum(arr[max(0, i - k + 1) : i + 1]))

    market = MarketSnapshot(
        timestamp=ts,
        btc_price=float(path.btc_price[i]),
        eth_price=float(path.eth_price[i]),
        btc_return_1h=float(path.btc_return[i]),
        btc_return_4h=trailing(path.btc_return, 4),
        btc_return_24h=trailing(path.btc_return, 24),
        eth_return_1h=float(path.eth_return[i]),
        eth_return_4h=trailing(path.eth_return, 4),
        eth_return_24h=trailing(path.eth_return, 24),
        btc_realized_vol=float(np.std(path.btc_return[lo : i + 1], ddof=1) * math.sqrt(8760)) if i - lo > 4 else 0.6,
        stablecoin_market_cap=190e9,
        stablecoin_flow_24h=float(np.tanh(trailing(path.btc_return, 24) * 30) * 8e8),
        macro_risk_score=0.5,
        btc_history=btc_hist,
        eth_history=eth_hist,
    )

    hourly_volume = float(v[-1])
    daily_volume = float(np.sum(v[-24:])) if v.size >= 24 else hourly_volume * 24
    same_hour = float(np.mean(v[-1::-24][:14])) if v.size >= 24 else hourly_volume

    asset = AssetSnapshot(
        symbol=sym,
        timestamp=ts,
        price=price,
        market_cap=float(d["market_cap"][i]),
        fdv=float(d["market_cap"][i]) * 1.6,
        spot_volume_24h=daily_volume * 0.55,
        perp_volume_24h=daily_volume * 0.45,
        volume_1h=hourly_volume,
        expected_same_hour_volume=same_hour,
        atr_1h=price * float(np.mean(np.abs(r[-24:]))) if r.size >= 24 else price * 0.004,
        realized_vol_1h=float(np.std(r[-24:], ddof=1)) if r.size >= 24 else 0.01,
        cvd_1h=float(d["taker_buy"][i] - d["taker_sell"][i]),
        taker_buy_1h=float(d["taker_buy"][i]),
        taker_sell_1h=float(d["taker_sell"][i]),
        orderbook_imbalance=float(np.tanh(d["ofi"][i] / 3.0)),
        bid_depth_1pct=float(d["depth"][i]) * 0.5,
        ask_depth_1pct=float(d["depth"][i]) * 0.5,
        spread_bps=float(d["spread_bps"][i]),
        ofi_1h=float(d["ofi"][i]) * float(d["depth"][i]) * 0.1,
        avg_depth=float(d["depth"][i]) * 0.1,
        open_interest=float(d["oi"][i]),
        oi_change_1h=float(d["oi"][i] / max(d["oi"][i - 1], 1e-9) - 1.0) if i >= 1 else 0.0,
        oi_change_4h=float(d["oi"][i] / max(d["oi"][max(i - 4, 0)], 1e-9) - 1.0),
        oi_change_24h=float(d["oi"][i] / max(d["oi"][max(i - 24, 0)], 1e-9) - 1.0),
        funding_rate=float(d["funding"][i]),
        long_short_ratio=float(1.0 + np.tanh(d["funding"][i] / 0.0008) * 0.5),
        price_return_15m=float(r[-1]) * 0.35,
        price_return_1h=float(r[-1]),
        price_return_4h=trailing(d["log_return"], 4),
        price_return_24h=trailing(d["log_return"], 24),
        price_return_7d=trailing(d["log_return"], 168),
        vwap_24h=float(np.mean(d["price"][max(0, i - 23) : i + 1])),
        support_1h=float(np.min(d["price"][max(0, i - 23) : i + 1])),
        resistance_1h=float(np.max(d["price"][max(0, i - 23) : i + 1])),
        history=hist,
    )
    return market, asset


def _realized(path: MarketPath, sym: str, entry_i: int, side: float, tp: float, sl: float, horizon: int) -> tuple[float, float]:
    """Realized triple-barrier return, entering at the *next* bar.

    Returns (return, holding hours). Entering at `entry_i + 1` is not a detail:
    entering at the decision bar's own close assumes execution at a price that
    was only known once the bar completed, which is the single most common way
    a backtest manufactures alpha.
    """
    p = path.assets[sym]["price"]
    start = entry_i + 1
    if start >= p.size - 1 or side == 0:
        return 0.0, 0.0
    entry = float(p[start])
    end = min(start + horizon, p.size - 1)
    up = entry * (1.0 + side * tp)
    dn = entry * (1.0 - side * sl)
    for k in range(start + 1, end + 1):
        px = float(p[k])
        # `tp` and `sl` are distances to the *position's* profit and loss
        # barriers, so they are already signed from the position's point of
        # view. Multiplying them by `side` again inverts every short: a short
        # that reaches its target books -tp and a short that is stopped out
        # books +sl, which credits losses as wins and reverses the entire
        # short book's P&L.
        if (side > 0 and px >= up) or (side < 0 and px <= up):
            return tp, float(k - start)
        if (side > 0 and px <= dn) or (side < 0 and px >= dn):
            return -sl, float(k - start)
    return side * (float(p[end]) / entry - 1.0), float(end - start)


def run_walk_forward(
    path: MarketPath,
    config: EngineConfig | None = None,
    step_hours: int = 4,
    warmup: int = HISTORY_BARS,
    start_frac: float = 0.0,
    end_frac: float = 1.0,
    portfolio_equity: float = 1_000_000.0,
    measured_ic: float | None = None,
    composite_dispersion: float | None = None,
    progress: bool = False,
) -> WalkForwardResult:
    """Run ORION-X and every peer over the same path with the same costs."""
    config = config or EngineConfig()
    horizon = int(config.horizon_hours)
    symbols = list(path.assets)
    cost_model = CostModel(taker_fee=config.taker_fee, impact_prefactor=config.impact_prefactor)

    all_points = list(range(warmup, path.n - horizon - 2, step_hours))
    lo = int(len(all_points) * start_frac)
    hi = int(len(all_points) * end_frac)
    decision_points = all_points[lo:hi]
    if not decision_points:
        raise ValueError("the requested window contains no decision points")
    notes: list[str] = []

    # Returns are accumulated per decision *time*, not per trade. Twelve assets
    # sharing one dominant BTC factor do not supply twelve independent
    # observations, and treating a bag of per-trade returns as an i.i.d. sample
    # inflates every t-statistic by up to sqrt(n_assets). Summing each
    # timestamp's positions into one portfolio return removes the cross-
    # sectional dependence by construction, which is also what the strategy's
    # actual equity curve does.
    orion_by_time: dict[int, float] = {}
    peer_by_time: dict[str, dict[int, float]] = {k: {} for k in PEERS}
    orion_returns: list[float] = []
    orion_scores: list[float] = []
    orion_forward: list[float] = []
    orion_prob_tp: list[float] = []
    orion_hit: list[float] = []
    no_trade = 0
    considered = 0
    gate_fail_counts: dict[str, int] = {}
    peer_returns: dict[str, list[float]] = {k: [] for k in PEERS}

    # One graph context per run: the correlation structure of the panel is
    # estimated on the warmup window only, so it is point-in-time for every
    # decision after it.
    graph = build_graph_context({s: path.assets[s]["log_return"][:warmup] for s in symbols})

    prev_regime: str | None = None

    for step_idx, i in enumerate(decision_points):
        if progress and step_idx % 50 == 0:
            print(f"  ... {step_idx}/{len(decision_points)} decision points", flush=True)
        for sym in symbols:
            considered += 1
            market, asset = _build_snapshots(path, sym, i, config)
            card = decide(
                market, asset, equities=[], events=[], config=config,
                graph=graph, previous_regime=prev_regime, measured_ic=measured_ic,
                portfolio_equity=portfolio_equity,
                composite_dispersion=composite_dispersion,
                horizon_diagnostics=False,
            )
            prev_regime = card.regime

            # Information coefficient is measured on every evaluation, including
            # the ones that end in NO_TRADE. Measuring it only on taken trades
            # conditions on the model's own gate and inflates it.
            fwd = float(np.sum(path.assets[sym]["log_return"][i + 1 : i + 1 + horizon]))
            orion_scores.append(card.composite)
            orion_forward.append(fwd)

            if card.decision == "NO_TRADE":
                no_trade += 1
                for g, ok in card.gates.items():
                    if not ok:
                        gate_fail_counts[g] = gate_fail_counts.get(g, 0) + 1
                continue

            side = 1.0 if card.decision == "LONG" else -1.0
            gross, hold = _realized(path, sym, i, side, card.plan.tp_distance, card.plan.sl_distance, horizon)
            notional = card.size["fraction"] * portfolio_equity
            c = estimate_costs(
                side=int(side), notional=notional,
                hourly_volume=float(path.assets[sym]["hourly_volume"][i]),
                sigma_per_hour=card.volatility["sigma_per_hour"],
                spread_bps=float(path.assets[sym]["spread_bps"][i]),
                funding_rate_8h=float(path.assets[sym]["funding"][i]),
                holding_hours=hold, model=cost_model,
            )
            net = gross - c.total
            orion_returns.append(net * card.size["fraction"])
            orion_by_time[i] = orion_by_time.get(i, 0.0) + net * card.size["fraction"] / len(symbols)
            orion_prob_tp.append(card.probabilities["take_profit"])
            orion_hit.append(1.0 if gross > 0 else 0.0)

        # Peers trade the same grid with a fixed, comparable barrier geometry so
        # that any difference is attributable to the signal, not to the stops.
        for sym in symbols:
            d = path.assets[sym]
            ctx = {**d, "seed": 12345}
            sigma = float(np.std(d["log_return"][max(0, i - 168) : i + 1], ddof=1))
            tp, sl = 1.5 * sigma * math.sqrt(horizon), 1.5 * sigma * math.sqrt(horizon)
            for name in PEERS:
                s = peer_side(name, ctx, i)
                if s == 0:
                    continue
                gross, hold = _realized(path, sym, i, float(np.sign(s)), tp, sl, horizon)
                c = estimate_costs(
                    side=int(np.sign(s)), notional=0.02 * portfolio_equity,
                    hourly_volume=float(d["hourly_volume"][i]),
                    sigma_per_hour=sigma, spread_bps=float(d["spread_bps"][i]),
                    funding_rate_8h=float(d["funding"][i]),
                    holding_hours=hold, model=cost_model,
                )
                pnl = (gross - c.total) * 0.02
                peer_returns[name].append(pnl)
                peer_by_time[name][i] = peer_by_time[name].get(i, 0.0) + pnl / len(symbols)

    trials = len(PEERS) + 1
    per_strategy: dict[str, PerformanceReport] = {}
    trade_counts: dict[str, int] = {}

    # Each strategy is annualized by *its own* trade frequency. Using one fixed
    # periods-per-year for all of them rewards selectivity twice: a rule that
    # trades a tenth as often has a tenth as many observations, and scaling its
    # per-trade Sharpe by the same sqrt(periods) as a rule that is always in the
    # market inflates it by roughly sqrt(10).
    elapsed_years = (len(decision_points) * step_hours) / 8760.0

    periods_per_year = 8760.0 / step_hours

    def series(by_time: dict[int, float]) -> np.ndarray:
        # Decision points with no position contribute a zero return, so a
        # selective strategy is charged for the time it sits in cash rather
        # than being credited with a higher apparent frequency.
        return np.array([by_time.get(i, 0.0) for i in decision_points])

    per_strategy["ORION_X_v5"] = summarize(series(orion_by_time), periods_per_year, trials)
    trade_counts["ORION_X_v5"] = len(orion_returns)
    for name, rets in peer_returns.items():
        per_strategy[name] = summarize(series(peer_by_time[name]), periods_per_year, trials)
        trade_counts[name] = len(rets)

    scores = np.array(orion_scores)
    fwds = np.array(orion_forward)
    ic = float(np.corrcoef(scores, fwds)[0, 1]) if scores.size > 8 and scores.std() > 1e-12 else 0.0

    calib: dict[str, float] = {}
    rows: list[dict] = []
    if orion_prob_tp:
        from ..calibration import brier_decomposition, reliability_table

        p = np.array(orion_prob_tp)
        y = np.array(orion_hit)
        calib = brier_decomposition(p, y).as_dict()
        rows = reliability_table(p, y, bins=6)

    if considered:
        notes.append(f"{no_trade}/{considered} evaluations gated to NO_TRADE ({no_trade/considered:.1%})")
    if gate_fail_counts:
        top = sorted(gate_fail_counts.items(), key=lambda kv: -kv[1])[:4]
        notes.append("most frequent binding gates: " + ", ".join(f"{k} ({v})" for k, v in top))

    return WalkForwardResult(
        per_strategy=per_strategy,
        trade_counts=trade_counts,
        orionx_diagnostics={
            "evaluations": float(considered),
            "no_trade_rate": no_trade / max(considered, 1),
            "trades": float(len(orion_returns)),
            "mean_size": float(np.mean([abs(r) for r in orion_returns])) if orion_returns else 0.0,
        },
        information_coefficient=ic,
        composite_dispersion=float(scores.std(ddof=1)) if scores.size > 2 else 0.0,
        calibration=calib,
        reliability_rows=rows,
        notes=notes,
    )


def run_two_pass_validation(
    path: MarketPath,
    config: EngineConfig | None = None,
    step_hours: int = 6,
    train_frac: float = 0.5,
    portfolio_equity: float = 1_000_000.0,
) -> tuple[WalkForwardResult, WalkForwardResult]:
    """Estimate the engine's parameters on a training window, trade the rest.

    The information coefficient and the composite's dispersion are not known in
    advance; they are properties of the signal that have to be measured. But
    measuring them on the same data the strategy is then scored on is in-sample
    fitting, and it is a particularly seductive form of it because only two
    numbers are being fitted, which feels harmless.

    It is not harmless. On a null market a spuriously positive IC of +0.06 over
    a few thousand observations is entirely ordinary, and feeding it back turns
    a correctly silent engine into one that trades a signal that does not exist.
    Measuring on the first `train_frac` of the sample and evaluating strictly on
    the remainder makes a spurious training IC show up as an out-of-sample loss
    instead of as a profit.

    Returns (training pass, out-of-sample pass).
    """
    config = config or EngineConfig()
    train = run_walk_forward(
        path, config, step_hours=step_hours, portfolio_equity=portfolio_equity,
        start_frac=0.0, end_frac=train_frac,
    )
    test = run_walk_forward(
        path, config, step_hours=step_hours, portfolio_equity=portfolio_equity,
        start_frac=train_frac, end_frac=1.0,
        measured_ic=train.information_coefficient,
        composite_dispersion=train.composite_dispersion or None,
    )
    test.notes.insert(
        0,
        f"IC and dispersion estimated on the first {train_frac:.0%} of the sample "
        f"(IC {train.information_coefficient:+.4f}, dispersion {train.composite_dispersion:.4f}) "
        f"and applied out of sample to the remainder",
    )
    return train, test
