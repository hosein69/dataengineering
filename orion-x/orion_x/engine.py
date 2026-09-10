"""The decision engine.

Everything upstream produces inputs to one calculation:

    barriers  <- forecast volatility and the asset's own geometry
    drift     <- evidence, scaled by a defensible information coefficient
    P(tp), P(sl), P(timeout)  <- first-passage under those barriers
    edge      <- probability-weighted return minus modelled costs
    size      <- the binding one of four caps

The decision is a mechanical consequence of that edge and a set of gates. There
is no separate "score" driving the trade; the 0-100 score still exists but it is
a *presentation* of the composite evidence and is explicitly not what the gates
read, which was one of v4's structural confusions.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

from .alpha import AlphaForecast, combine_blocks, grinold_drift
from .barriers import BarrierProbs, barrier_probs, implied_drift_for_edge, outcome_moments, survival_moment
from .causal import FactorModel, fit_factor_model, residualize
from .contracts import (
    AssetSnapshot,
    EngineConfig,
    EquityBenchmark,
    MarketSnapshot,
    PointInTimeGuard,
    ScheduledEvent,
)
from .costs import CostBreakdown, CostModel, estimate_costs
from .features import (
    Block,
    RegimeState,
    carry_block,
    catalyst_block,
    event_risk,
    flow_block,
    fundamental_block,
    kyle_lambda,
    liquidity_block,
    momentum_block,
    psychology_block,
    regime_block,
    relative_block,
)
from .graph import GraphContext
from .mathx import EPS, clamp, safe_div
from .sizing import SizeDecision, size_position
from .version import CONTRACT_VERSION, VERSION
from .vol import VolForecast, har_rv_forecast

__all__ = ["SignalCard", "TradePlan", "decide", "signal_to_dict"]


@dataclass
class TradePlan:
    """Barriers and timing. Levels are prices; distances are fractions."""

    side: int                       # +1 long, -1 short, 0 no position
    reference_price: float
    entry_limit: float
    take_profit: float
    stop_loss: float
    scale_out_1: float
    scale_out_2: float
    tp_distance: float
    sl_distance: float
    horizon_hours: float
    window_start: datetime | None
    window_end: datetime | None
    window_rationale: str
    expected_holding_hours: float


@dataclass
class SignalCard:
    """A complete, replayable record of one decision."""

    symbol: str
    version: str
    contract_version: str
    decision_time: datetime
    decision: str                   # LONG | SHORT | NO_TRADE
    score: float                    # 0-100 presentation of the composite
    composite: float                # signed [-1, 1], what the model actually uses
    confidence: float
    uncertainty: float

    regime: str
    regime_probabilities: dict[str, float]
    risk_appetite: float
    market_stress: float

    volatility: dict[str, float]
    barriers: dict[str, float]
    probabilities: dict[str, float]
    alpha: dict[str, float]
    costs: dict[str, float]
    blocks: dict[str, float]
    block_reliability: dict[str, float]
    factor_model: dict[str, float]
    structure: dict[str, float]

    expected_return_gross: float
    expected_return_net: float
    expected_rr: float
    edge_to_risk: float
    edge_hurdle: float
    breakeven_drift_per_hour: float

    plan: TradePlan
    size: dict[str, float]

    sensitivity: dict[str, float]
    horizon_curve: dict[str, float]
    gates: dict[str, bool]
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_quality: dict[str, float] = field(default_factory=dict)


def _volume_seasonality(history_volume: np.ndarray, as_of: datetime) -> np.ndarray:
    """Average traded volume by UTC hour, estimated from the caller's history.

    v4 hard-coded a liquidity bonus for 08:00-10:00 and 14:00-16:00 UTC and a
    penalty for 00:00-05:00. Those windows are a plausible guess at the
    London open and the US open, but they were never estimated, they are wrong
    for assets whose flow is Asia-dominated, and they are wrong on weekends.
    Estimating the profile from the asset's own history costs nothing and is
    correct by construction.
    """
    profile = np.ones(24)
    v = np.asarray(history_volume, dtype=float)
    if v.size < 48:
        return profile
    hours = [(as_of - timedelta(hours=int(v.size - 1 - i))).hour for i in range(v.size)]
    sums = np.zeros(24)
    counts = np.zeros(24)
    for h, val in zip(hours, v):
        if val > 0:
            sums[h] += val
            counts[h] += 1
    mean_all = float(v[v > 0].mean()) if (v > 0).any() else 1.0
    for h in range(24):
        profile[h] = (sums[h] / counts[h]) / mean_all if counts[h] >= 2 and mean_all > EPS else 1.0
    return np.clip(profile, 0.25, 4.0)


def _choose_window(
    now: datetime,
    horizon_hours: float,
    seasonality: np.ndarray,
    sigma_per_hour: float,
    notional: float,
    hourly_volume: float,
    cost_model: CostModel,
    alpha_halflife_hours: float,
    step_minutes: int = 15,
) -> tuple[datetime, datetime, str]:
    """Pick the entry slot that maximises alpha net of expected entry cost.

    v4's window search evaluated a score in which every term except a hard-coded
    hour bonus was constant across the loop, so it always returned the first
    slot inside the bonus hours regardless of the asset or the market. The
    search had no objective.

    The real trade-off is genuine: waiting for a deeper hour reduces impact cost
    but the signal decays while you wait. Impact scales as sqrt(1/volume) and
    alpha decays exponentially, so the optimum is interior and asset-specific.
    """
    n_steps = max(int(horizon_hours * 60 / step_minutes) // 2, 1)  # only enter in the first half
    best = None
    for i in range(n_steps):
        t = now + timedelta(minutes=i * step_minutes)
        delay_h = i * step_minutes / 60.0
        vol_mult = float(seasonality[t.hour])
        impact = cost_model.impact_prefactor * sigma_per_hour * math.sqrt(
            safe_div(abs(notional), max(hourly_volume * vol_mult, EPS), 0.0)
        )
        decay = 0.5 ** (delay_h / max(alpha_halflife_hours, EPS))
        objective = decay - impact / max(sigma_per_hour, EPS) * 0.15
        if best is None or objective > best[0]:
            best = (objective, t, vol_mult, impact, decay)
    _, start, vol_mult, impact, decay = best
    end = start + timedelta(minutes=step_minutes)
    rationale = (
        f"expected volume {vol_mult:.2f}x baseline, entry impact ~{impact*10000:.1f}bps, "
        f"{decay:.0%} of the signal remaining"
    )
    return start, end, rationale


def _optimize_barriers(
    mu: float,
    sigma_h: float,
    horizon: float,
    fixed_cost: float,
    funding_per_hour: float,
    config: EngineConfig,
) -> tuple[float, float, float]:
    """Choose (tp_sigma, sl_sigma) maximising the Kelly growth rate.

    v4 placed barriers at fixed ATR multiples -- 1.1x, 2.0x and 3.2x for the
    targets and a stop 0.45 ATR below the defensive entry. Those numbers appear
    nowhere else in the model and were never checked against the probabilities
    the same engine reported two fields later.

    Here the geometry is derived. For each candidate pair the engine computes the
    exact first-passage moments, subtracts the costs that geometry implies
    (funding accrues with expected holding time, everything else is per round
    trip) and scores it by the growth rate an optimally-sized position would
    earn, E[X]^2 / (2 Var[X]). Maximising expected value alone would push the
    stop to infinity; maximising growth does not.
    """
    sigma_T = sigma_h * math.sqrt(horizon)
    lo_tp, hi_tp = config.min_barrier_sigma, config.max_barrier_sigma
    lo_sl, hi_sl = config.min_barrier_sigma, min(config.max_barrier_sigma, 2.2)

    def evaluate(tp_s: float, sl_s: float) -> float:
        up = math.log1p(tp_s * sigma_T)
        down = -math.log1p(-min(sl_s * sigma_T, 0.5))
        mean, var, probs = outcome_moments(mu, sigma_h, horizon, up, down)
        expected_hold = horizon * (0.35 + 0.65 * probs.timeout)
        net = mean - fixed_cost - funding_per_hour * expected_hold
        # For a profitable geometry the objective is the Kelly growth rate,
        # which has an interior maximum: net edge saturates once the expected
        # holding time reaches the horizon, while variance keeps growing with
        # barrier width. For an unprofitable one, rank by the loss itself --
        # dividing by the standard deviation there would reward the *widest*
        # geometry, since a fixed loss spread over a larger variance scores
        # closer to zero.
        return (net * net) / (2.0 * var) if net > 0 else net

    # Coarse-to-fine search. The objective is smooth and single-peaked in both
    # arguments, so a 5x5 sweep followed by a local 3x3 refinement finds the
    # same optimum as a dense grid for a twentieth of the first-passage
    # evaluations, which is what makes a full walk-forward tractable.
    best = None
    for tp_s in np.linspace(lo_tp, hi_tp, 5):
        for sl_s in np.linspace(lo_sl, hi_sl, 5):
            score = evaluate(float(tp_s), float(sl_s))
            if best is None or score > best[0]:
                best = (score, float(tp_s), float(sl_s))

    step_tp = (hi_tp - lo_tp) / 8.0
    step_sl = (hi_sl - lo_sl) / 8.0
    for dtp in (-step_tp, 0.0, step_tp):
        for dsl in (-step_sl, 0.0, step_sl):
            tp_s = min(max(best[1] + dtp, lo_tp), hi_tp)
            sl_s = min(max(best[2] + dsl, lo_sl), hi_sl)
            score = evaluate(tp_s, sl_s)
            if score > best[0]:
                best = (score, tp_s, sl_s)
    return best[1], best[2], best[0]


def minimum_viable_horizon(
    sigma_per_hour: float,
    ic: float,
    z: float,
    fixed_cost: float,
    funding_per_hour: float,
    config: EngineConfig,
    candidates: tuple[float, ...] = (2.0, 4.0, 7.0, 12.0, 24.0, 48.0, 96.0, 168.0, 336.0, 720.0),
) -> tuple[float, dict[float, float]]:
    """Shortest horizon at which this signal can pay for its own costs.

    This is the most useful single number the engine produces on a no-trade, and
    it follows from an asymmetry v4 never confronted. Under Grinold's rule the
    forecastable move scales with horizon volatility,

        alpha(T) = IC * sigma_h * sqrt(T) * z,

    while the fixed part of the cost -- fees, spread, both legs of market impact
    -- does not scale with T at all. The ratio of edge to cost therefore grows
    like sqrt(T), and a signal that cannot clear its costs over seven hours may
    clear them comfortably over seven days on exactly the same information.

    Only the funding leg pushes the other way, growing linearly in T, so the
    viable region is bounded above as well when funding is against the position.

    Returns the shortest viable horizon (inf when none is) and the net edge at
    each candidate horizon, both of which go on the signal card.
    """
    curve: dict[float, float] = {}
    best: float = float("inf")
    for T in candidates:
        sigma_T = sigma_per_hour * math.sqrt(T)
        mu = ic * sigma_T * z / T
        tp_s, sl_s, _ = _optimize_barriers(mu, sigma_per_hour, T, fixed_cost, funding_per_hour, config)
        up = math.log1p(tp_s * sigma_T)
        down = -math.log1p(-min(sl_s * sigma_T, 0.5))
        mean, _var, probs = outcome_moments(mu, sigma_per_hour, T, up, down)
        hold = T * (0.35 + 0.65 * probs.timeout)
        net = mean - fixed_cost - funding_per_hour * hold
        curve[T] = net
        if net >= max(config.min_net_edge_sigma * sigma_T, config.min_net_edge_abs) and T < best:
            best = T
    return best, curve


def decide(
    market: MarketSnapshot,
    asset: AssetSnapshot,
    equities: list[EquityBenchmark] | None = None,
    events: list[ScheduledEvent] | None = None,
    config: EngineConfig | None = None,
    *,
    now: datetime | None = None,
    graph: GraphContext | None = None,
    previous_regime: str | None = None,
    measured_ic: float | None = None,
    composite_dispersion: float | None = None,
    block_ics: dict[str, float] | None = None,
    block_correlation: tuple[list[str], np.ndarray] | None = None,
    funding_history: np.ndarray | None = None,
    portfolio_equity: float = 1_000_000.0,
    enforce_point_in_time: bool = True,
    horizon_diagnostics: bool = True,
) -> SignalCard:
    """Produce one auditable decision for one asset."""
    config = config or EngineConfig()
    equities = equities or []
    events = events or []
    now = now or market.timestamp
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    warnings: list[str] = []
    reasons: list[str] = []

    if enforce_point_in_time:
        PointInTimeGuard(now).check_all(market, asset, equities)

    # ---------------- volatility ------------------------------------------
    hist = asset.history
    hist_returns = hist.hourly_log_returns if hist is not None else np.zeros(0)
    atr_sigma = safe_div(asset.atr_1h, max(asset.price, EPS), 0.0)
    vol: VolForecast = har_rv_forecast(hist_returns, config.horizon_hours, atr_sigma)
    if vol.source == "fallback":
        warnings.append("no price history supplied: volatility is an ATR fallback, barriers are less reliable")
    sigma_h = max(vol.sigma_per_hour, 1e-4)
    sigma_T = max(vol.sigma_horizon, 1e-4)

    # ---------------- causal: strip the market factor ----------------------
    factor_model = FactorModel()
    idio = None
    factors: dict[str, np.ndarray] = {}
    if market.btc_history is not None and hist is not None and hist.n >= 48:
        n = min(hist.n, market.btc_history.n)
        factors["BTC"] = market.btc_history.hourly_log_returns[-n:]
        if market.eth_history is not None and market.eth_history.n >= n:
            factors["ETH"] = market.eth_history.hourly_log_returns[-n:]
        factor_model = fit_factor_model(hist_returns[-n:], factors)
        idio = residualize(hist_returns[-n:], factors, factor_model)
    else:
        warnings.append("no factor history: market beta could not be removed, evidence may be a disguised BTC call")

    # ---------------- evidence blocks --------------------------------------
    regime: RegimeState = regime_block(market, previous_regime)
    same_hour = asset.expected_same_hour_volume if asset.expected_same_hour_volume > EPS else max(asset.total_volume() / 24.0, EPS)
    volume_ratio = safe_div(asset.volume_1h, same_hour, 1.0)

    b_flow = flow_block(asset)
    b_liq = liquidity_block(asset, sigma_h)
    b_mom = momentum_block(asset, b_flow, volume_ratio, idio)
    b_carry = carry_block(asset, funding_history)
    b_fund = fundamental_block(asset)
    b_psy = psychology_block(asset, regime)
    b_rel = relative_block(asset, equities, market)
    b_cat = catalyst_block(asset)

    blocks: dict[str, Block] = {
        "flow": b_flow,
        "momentum": b_mom,
        "carry": b_carry,
        "fundamental": b_fund,
        "psychology": b_psy,
        "relative": b_rel,
        "catalyst": b_cat,
    }
    epen, event_notes = event_risk(asset, events, now, config.horizon_hours)
    warnings.extend(event_notes)

    composite, contributions, combine_notes = combine_blocks(blocks, config, block_ics, block_correlation)
    if block_ics:
        combine_notes.append(
            "block weights set by measured information coefficients rather than priors"
        )
    reasons.extend(combine_notes)

    # The regime does not vote on direction; it scales conviction. A long thesis
    # in a capitulation regime and a short thesis in an expansion regime are
    # both fighting the tape, and that is what this term encodes.
    regime_alignment = 1.0 + 0.35 * math.copysign(1.0, composite or 1.0) * regime.risk_appetite
    composite = clamp(composite * clamp(regime_alignment, 0.4, 1.5), -1.0, 1.0)

    # ---------------- structure: breadth and uniqueness --------------------
    uniqueness = graph.uniqueness_of(asset.symbol) if graph else 0.5
    breadth = graph.effective_rank if graph else 2.0
    if graph and uniqueness < 0.25:
        warnings.append("asset sits at the centre of the correlation graph: this thesis is largely a market call")

    # ---------------- uncertainty ------------------------------------------
    reliability = float(np.mean([b.reliability for b in blocks.values()]))
    disagreement = float(np.std([b.score for b in blocks.values()]))
    uncertainty = clamp(
        0.30 * (1.0 - reliability)
        + 0.22 * epen
        + 0.18 * (1.0 - b_liq.score)
        + 0.15 * clamp(disagreement / 0.45)
        + 0.15 * (1.0 - uniqueness)
    )

    # ---------------- direction and barriers -------------------------------
    side = 1 if composite > 0 else (-1 if composite < 0 else 0)
    if side < 0 and not config.allow_short:
        side = 0
        warnings.append("evidence points short but shorting is disabled by configuration")

    # Barriers are placed in units of forecast horizon volatility, not raw ATR.
    # An ATR-multiple stop is a volatility bet in disguise: the same multiple
    # means a very different probability of being hit depending on the regime.
    # The multiples themselves are then optimised against the actual first-
    # passage moments rather than being asserted.

    # The barriers are placed in units of sigma_horizon, which carries the jump
    # widening and the mean-reversion-aware time exponent from `orion_x.vol`.
    # The first-passage solution assumes plain sqrt(t) scaling, so it is fed the
    # per-hour sigma that reproduces sigma_horizon over this horizon --
    # otherwise the barriers and the probabilities describe two different
    # volatilities and every touch probability comes out too low.
    sigma_eff_h = sigma_T / math.sqrt(max(config.horizon_hours, EPS))

    drift_side = side if side != 0 else 1
    alpha_pre = grinold_drift(
        composite, sigma_T, config.horizon_hours, config, uncertainty,
        breadth, transfer_coefficient=clamp(1.0 - uncertainty), measured_ic=measured_ic,
        composite_dispersion=composite_dispersion,
    )
    reasons.extend(alpha_pre.notes)

    # First-passage probabilities are always computed in the direction of the
    # trade, so `take_profit` means "the trade won" for a short as well.
    mu_signed = alpha_pre.drift_per_hour * drift_side

    hourly_volume = max(asset.total_volume() / 24.0, EPS)
    provisional_notional = min(0.10 * portfolio_equity, config.max_participation * hourly_volume)
    cost_model = CostModel(taker_fee=config.taker_fee, impact_prefactor=config.impact_prefactor)
    fixed_cost = estimate_costs(
        side=drift_side, notional=provisional_notional, hourly_volume=hourly_volume,
        sigma_per_hour=sigma_eff_h, spread_bps=asset.spread_bps,
        funding_rate_8h=0.0, holding_hours=0.0, model=cost_model,
    ).total
    funding_per_hour = drift_side * asset.funding_rate / 8.0

    tp_sigma, sl_sigma, _growth = _optimize_barriers(
        mu_signed, sigma_eff_h, config.horizon_hours, fixed_cost, funding_per_hour, config
    )
    tp_distance = tp_sigma * sigma_T
    sl_distance = sl_sigma * sigma_T
    if side > 0 and asset.support_1h > 0 and asset.support_1h < asset.price:
        structural = (asset.price - asset.support_1h) / asset.price
        if 0.3 * sl_distance < structural < sl_distance:
            sl_distance = structural + 0.25 * sigma_T
            reasons.append("stop widened just beyond visible 1h support")
    if side < 0 and asset.resistance_1h > asset.price:
        structural = (asset.resistance_1h - asset.price) / asset.price
        if 0.3 * sl_distance < structural < sl_distance:
            sl_distance = structural + 0.25 * sigma_T
            reasons.append("stop widened just beyond visible 1h resistance")
    up_log = math.log1p(tp_distance)
    down_log = -math.log1p(-min(sl_distance, 0.5))

    probs: BarrierProbs = barrier_probs(mu_signed, sigma_eff_h, config.horizon_hours, up_log, down_log)

    # ---------------- expected value ---------------------------------------
    # The timeout branch is valued at the *conditional* expectation of the
    # terminal log price given that neither barrier was touched, not at the
    # unconditional drift. See `orion_x.barriers.survival_moment` for why the
    # difference is material rather than cosmetic.
    _mean_check, outcome_var, _ = outcome_moments(mu_signed, sigma_eff_h, config.horizon_hours, up_log, down_log)
    p_survive, e_timeout = survival_moment(mu_signed, sigma_eff_h, config.horizon_hours, up_log, down_log)
    timeout_return = safe_div(e_timeout, max(p_survive, EPS), 0.0)
    gross = probs.take_profit * up_log - probs.stop_loss * down_log + e_timeout

    holding = config.horizon_hours * (0.35 + 0.65 * probs.timeout)
    costs: CostBreakdown = estimate_costs(
        side=drift_side,
        notional=provisional_notional,
        hourly_volume=hourly_volume,
        sigma_per_hour=sigma_h,
        spread_bps=asset.spread_bps,
        funding_rate_8h=asset.funding_rate,
        holding_hours=holding,
        model=cost_model,
    )
    net = gross - costs.total

    expected_rr = safe_div(
        probs.take_profit * up_log + probs.timeout * max(timeout_return, 0.0),
        probs.stop_loss * down_log + costs.total,
        0.0,
    )
    breakeven = implied_drift_for_edge(sigma_eff_h, config.horizon_hours, up_log, down_log, costs.total)

    # ---------------- sizing ------------------------------------------------
    size: SizeDecision = size_position(
        edge=net,
        sigma_horizon=sigma_T,
        stop_distance=sl_distance,
        hourly_volume=hourly_volume,
        portfolio_equity=portfolio_equity,
        breadth=breadth,
        config=config,
    )

    # ---------------- confidence -------------------------------------------
    # Confidence is the probability that the *direction* of the call is right,
    # derived rather than asserted. Model the standardized forecast z and the
    # standardized outcome y as jointly normal with correlation IC, which is the
    # definition of the information coefficient. Then y | z ~ N(IC z, 1 - IC^2)
    # and
    #
    #     P(sign correct | z) = Phi( IC |z| / sqrt(1 - IC^2) ).
    #
    # This is a much smaller number than it is comfortable to publish. At an IC
    # of 0.03 and a two-sigma view it is about 52%, and no amount of feature
    # engineering makes a single short-horizon crypto call a 70% proposition.
    # v4's `confidence` reached 0.71 on its shipped example while its own
    # scenario probabilities said 0.47 -- two numbers describing the same belief
    # and disagreeing by 24 points, because neither was derived from anything.
    #
    # The consequence is that a minimum-confidence gate has to be set in the
    # low fifties or it can never pass. A systematic strategy of this kind earns
    # from breadth, not from per-trade conviction; demanding 55% per trade is a
    # discretionary trader's gate applied to a statistical process.
    ic_eff = abs(alpha_pre.information_coefficient)
    directional = 0.5 * (1.0 + math.erf(
        ic_eff * abs(alpha_pre.composite_z) / math.sqrt(2.0 * max(1.0 - ic_eff**2, EPS))
    )) if ic_eff > EPS else 0.5
    # Data quality and model disagreement can only pull it back toward a coin
    # flip; they can never raise it above what the IC supports.
    confidence = 0.5 + (directional - 0.5) * clamp(reliability) * clamp(1.0 - uncertainty)

    # ---------------- gates -------------------------------------------------
    edge_hurdle = max(config.min_net_edge_sigma * sigma_T, config.min_net_edge_abs)
    # `expected_rr` is reported but not gated. A risk/reward ratio built from
    # barrier probabilities is not a meaningful constraint once the barriers are
    # chosen by maximising the growth rate: that optimiser deliberately favours
    # geometries where most paths time out, and a ratio of P(target) to P(stop)
    # over such a geometry is small by construction while the trade may still be
    # sound. Gating on it would veto exactly the geometries the model just
    # selected. The volatility-relative edge hurdle below already is the
    # risk-adjusted test -- requiring net edge above 4% of horizon sigma is a
    # per-trade information-ratio floor.
    gates = {
        "net_edge": net >= edge_hurdle,
        "confidence": confidence >= config.min_confidence,
        "event_risk": epen <= config.max_event_risk,
        "uncertainty": uncertainty <= config.max_uncertainty,
        "liquidity": b_liq.score >= config.min_liquidity_score,
        "dollar_volume": asset.total_volume() >= config.min_dollar_volume_24h,
        "has_direction": side != 0,
        "positive_size": size.fraction > 1e-4,
    }
    for name, ok in gates.items():
        if not ok:
            warnings.append(f"gate failed: {name}")

    if all(gates.values()):
        decision = "LONG" if side > 0 else "SHORT"
        reasons.append(
            f"net edge {net*10000:.1f}bps clears the {edge_hurdle*10000:.1f}bps hurdle "
            f"({config.min_net_edge_sigma:.0%} of a {sigma_T*100:.1f}% horizon sigma) "
            f"with P(target)={probs.take_profit:.2f} vs P(stop)={probs.stop_loss:.2f}"
        )
    else:
        decision = "NO_TRADE"
        size = SizeDecision(0.0, size.binding_constraint, size.kelly_full, size.kelly_used, size.vol_target_cap, size.liquidity_cap, size.risk_cap, size.notes)

    # ---------------- horizon diagnostics ----------------------------------
    # Computed on every decision, but it is on a NO_TRADE that it earns its
    # place: it separates "this signal is worthless" from "this signal is real
    # but the horizon is too short to pay for the spread".
    # The horizon sweep costs another ten barrier optimisations, so a caller
    # running hundreds of thousands of decisions can turn it off.
    if horizon_diagnostics:
        min_horizon, horizon_curve = minimum_viable_horizon(
            sigma_eff_h, abs(alpha_pre.information_coefficient), abs(alpha_pre.composite_z),
            fixed_cost, abs(funding_per_hour), config,
        )
    else:
        min_horizon, horizon_curve = float("inf"), {}
    if decision == "NO_TRADE" and math.isfinite(min_horizon) and min_horizon > config.horizon_hours:
        reasons.append(
            f"the same evidence clears the cost hurdle at a {min_horizon:.0f}h horizon "
            f"but not at {config.horizon_hours:.0f}h: costs are fixed per round trip while "
            f"the forecastable move grows with sqrt(T)"
        )

    # ---------------- entry window -----------------------------------------
    seasonality = _volume_seasonality(hist.hourly_volume if hist is not None else np.zeros(0), now)
    alpha_halflife = max(config.horizon_hours * 0.5, 1.0)
    ws, we, rationale = _choose_window(
        now, config.horizon_hours, seasonality, sigma_h,
        max(size.fraction * portfolio_equity, 1.0), hourly_volume, cost_model, alpha_halflife,
    )

    ref = asset.price
    plan = TradePlan(
        side=side if decision != "NO_TRADE" else 0,
        reference_price=ref,
        entry_limit=ref * (1 - 0.15 * sigma_h) if side > 0 else ref * (1 + 0.15 * sigma_h),
        take_profit=ref * (1 + drift_side * tp_distance),
        stop_loss=ref * (1 - drift_side * sl_distance),
        scale_out_1=ref * (1 + drift_side * tp_distance * 0.45),
        scale_out_2=ref * (1 + drift_side * tp_distance * 0.75),
        tp_distance=tp_distance,
        sl_distance=sl_distance,
        horizon_hours=config.horizon_hours,
        window_start=ws,
        window_end=we,
        window_rationale=rationale,
        expected_holding_hours=holding,
    )

    # ---------------- local sensitivity ------------------------------------
    sensitivity = _sensitivity(asset, blocks, config, block_ics, block_correlation)

    score = 50.0 * (1.0 + composite)

    return SignalCard(
        symbol=asset.symbol,
        version=VERSION,
        contract_version=CONTRACT_VERSION,
        decision_time=now,
        decision=decision,
        score=score,
        composite=composite,
        confidence=confidence,
        uncertainty=uncertainty,
        regime=regime.label,
        regime_probabilities={k: round(v, 4) for k, v in regime.probabilities.items()},
        risk_appetite=regime.risk_appetite,
        market_stress=regime.stress,
        volatility={
            "sigma_per_hour": sigma_h,
            "sigma_horizon": sigma_T,
            "annualized": sigma_h * math.sqrt(8760.0),
            "jump_share": vol.jump_share,
            "persistence": vol.persistence,
            "source": 1.0 if vol.source == "har-rv" else 0.0,
        },
        barriers={"up_log": up_log, "down_log": down_log, "tp_sigma": tp_sigma, "sl_sigma": sl_sigma},
        probabilities={
            "take_profit": probs.take_profit,
            "stop_loss": probs.stop_loss,
            "timeout": probs.timeout,
            "method": 1.0 if probs.method == "series" else 0.0,
        },
        alpha={
            "composite_z": alpha_pre.composite_z,
            "information_coefficient": alpha_pre.information_coefficient,
            "drift_per_hour": alpha_pre.drift_per_hour,
            "drift_horizon": alpha_pre.drift_horizon,
            "implied_ir": alpha_pre.implied_information_ratio,
            "breadth": breadth,
        },
        costs=costs.as_dict(),
        blocks={k: round(v.score, 5) for k, v in blocks.items()} | {"liquidity": round(b_liq.score, 5)},
        block_reliability={k: round(v.reliability, 3) for k, v in blocks.items()},
        factor_model={**{f"beta_{k}": round(v, 4) for k, v in factor_model.betas.items()},
                      "r_squared": factor_model.r_squared, "idio_vol": factor_model.idio_vol},
        structure={"uniqueness": uniqueness, "effective_rank": breadth,
                   "kyle_lambda": kyle_lambda(hist_returns, hist.hourly_volume) if hist is not None else 0.0},
        expected_return_gross=gross,
        expected_return_net=net,
        expected_rr=expected_rr,
        edge_to_risk=safe_div(net, math.sqrt(max(outcome_var, EPS)), 0.0),
        edge_hurdle=edge_hurdle,
        breakeven_drift_per_hour=breakeven,
        plan=plan,
        size={
            "fraction": size.fraction,
            "binding_constraint_kelly": 1.0 if size.binding_constraint == "kelly" else 0.0,
            "kelly_full": size.kelly_full,
            "vol_target_cap": size.vol_target_cap,
            "liquidity_cap": size.liquidity_cap,
            "risk_cap": size.risk_cap,
        },
        sensitivity=sensitivity,
        horizon_curve={f"{int(k)}h": round(v, 6) for k, v in horizon_curve.items()} | {
            "minimum_viable_hours": min_horizon if math.isfinite(min_horizon) else -1.0
        },
        gates=gates,
        reasons=reasons,
        warnings=warnings + size.notes,
        data_quality={
            "block_reliability_mean": reliability,
            "history_bars": float(hist.n if hist is not None else 0),
            "has_factor_model": 1.0 if factor_model.betas else 0.0,
            "has_graph_context": 1.0 if graph else 0.0,
        },
    )


def _sensitivity(
    asset: AssetSnapshot,
    blocks: dict[str, Block],
    config: EngineConfig,
    block_ics: dict[str, float] | None = None,
    block_correlation: tuple[list[str], np.ndarray] | None = None,
) -> dict[str, float]:
    """d(composite) / d(block score), published so the decision is auditable.

    A reviewer can read straight off the card which evidence the trade rests on
    rather than trusting the declared weights, which are only the *nominal*
    weights: reliability scaling and the agreement adjustment both change the
    effective ones.
    """
    base, _, _ = combine_blocks(blocks, config, block_ics, block_correlation)
    out: dict[str, float] = {}
    h = 1e-4
    for name, blk in blocks.items():
        bumped = dict(blocks)
        bumped[name] = Block(clamp(blk.score + h, -1.0, 1.0), blk.reliability, blk.diagnostics, [])
        up, _, _ = combine_blocks(bumped, config, block_ics, block_correlation)
        bumped[name] = Block(clamp(blk.score - h, -1.0, 1.0), blk.reliability, blk.diagnostics, [])
        dn, _, _ = combine_blocks(bumped, config, block_ics, block_correlation)
        out[name] = round((up - dn) / (2 * h), 4)
    out["_base"] = round(base, 5)
    return out


def signal_to_dict(card: SignalCard) -> dict:
    d = asdict(card)
    d["decision_time"] = card.decision_time.isoformat()
    p = d["plan"]
    p["window_start"] = card.plan.window_start.isoformat() if card.plan.window_start else None
    p["window_end"] = card.plan.window_end.isoformat() if card.plan.window_end else None
    return d
