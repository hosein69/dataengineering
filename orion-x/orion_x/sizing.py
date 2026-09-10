"""Position sizing.

v4 sized with `max_risk_per_trade / risk_distance`, scaled by confidence and
(1 - uncertainty), capped at a leverage ceiling of 2. That is a fixed-fractional
rule wearing a Kelly costume: it has no dependence on the *edge*, only on the
stop distance, so a trade with a 1 basis point edge and a trade with a 100 basis
point edge get the same size whenever their stops are the same distance away.

v5 takes the binding constraint among four caps that each answer a different
question:

1. Kelly: how much does the edge justify?
2. Volatility target: how much does the risk budget allow?
3. Liquidity: how much can actually be traded without paying the edge away?
4. Loss limit: how much can be lost if the stop is honoured?
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .contracts import EngineConfig
from .mathx import EPS, clamp, safe_div

__all__ = ["SizeDecision", "size_position"]


@dataclass
class SizeDecision:
    fraction: float
    binding_constraint: str
    kelly_full: float
    kelly_used: float
    vol_target_cap: float
    liquidity_cap: float
    risk_cap: float
    notes: list[str]


def size_position(
    *,
    edge: float,
    sigma_horizon: float,
    stop_distance: float,
    hourly_volume: float,
    portfolio_equity: float,
    breadth: float,
    config: EngineConfig,
) -> SizeDecision:
    """Return the fraction of equity to commit, and which cap bound it.

    Args:
        edge: expected log return over the horizon, net of costs.
        sigma_horizon: forecast volatility over the horizon.
        stop_distance: |entry - stop| / entry.
        hourly_volume: quote-currency volume per hour.
        portfolio_equity: account equity in quote currency.
        breadth: effective number of independent bets currently held.
    """
    notes: list[str] = []

    # 1. Kelly. For a roughly Gaussian return the growth-optimal fraction is
    # mu / sigma^2. Fractional Kelly is not conservatism for its own sake: with
    # estimated rather than known parameters, full Kelly is above the growth
    # optimum and can be growth-negative (MacLean, Thorp & Ziemba 2011).
    kelly_full = safe_div(edge, max(sigma_horizon, EPS) ** 2, 0.0)
    kelly_used = config.kelly_fraction * kelly_full
    # Diversification lets a *portfolio* run closer to Kelly than any single
    # position; with one effective bet, do not.
    kelly_used *= min(1.0, 0.5 + 0.5 * math.sqrt(max(breadth, 1.0) / 4.0))
    if kelly_full <= 0:
        notes.append("edge is non-positive: Kelly fraction is zero or negative")

    # 2. Volatility target.
    sigma_annual = sigma_horizon * math.sqrt(8760.0 / max(config.horizon_hours, EPS))
    vol_cap = safe_div(config.target_portfolio_vol, max(sigma_annual, EPS), 0.0)

    # 3. Liquidity: never take a position larger than a fixed share of hourly
    # volume, because the cost model's square-root impact term is only
    # calibrated in that region and blows up beyond it.
    max_notional = config.max_participation * max(hourly_volume, 0.0)
    liq_cap = safe_div(max_notional, max(portfolio_equity, EPS), 0.0)
    if liq_cap < 0.05:
        notes.append("position capped hard by available liquidity")

    # 4. Loss limit at the stop.
    risk_cap = safe_div(config.max_risk_per_trade, max(stop_distance, 1e-4), 0.0)

    caps = {
        "kelly": max(kelly_used, 0.0),
        "vol_target": vol_cap,
        "liquidity": liq_cap,
        "risk_limit": risk_cap,
        "leverage_ceiling": config.leverage_ceiling,
    }
    binding = min(caps, key=caps.get)
    fraction = clamp(caps[binding], 0.0, config.leverage_ceiling)

    return SizeDecision(
        fraction=fraction,
        binding_constraint=binding,
        kelly_full=kelly_full,
        kelly_used=kelly_used,
        vol_target_cap=vol_cap,
        liquidity_cap=liq_cap,
        risk_cap=risk_cap,
        notes=notes,
    )
