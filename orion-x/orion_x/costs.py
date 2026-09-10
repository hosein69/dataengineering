"""Transaction cost model.

ORION-X v4 charged a flat 8 bps of fees, one spread, and `abs(funding_rate)`.
Each of those is wrong in a way that flatters the strategy:

* `abs(funding_rate)` charges a long for *receiving* funding. Negative funding
  pays the long side. In the shipped v4 example the asset had funding of
  -0.0002 -- a genuine income of about 5 bps over the holding period -- and the
  engine booked it as a 5 bps cost, a 10 bps error on a 40 bps edge.
* A flat spread ignores size. A position that is 3% of hourly volume does not
  cross the spread, it walks the book.
* Nothing accounted for the market impact of the exit, which for a 7-hour
  crypto trade in a mid-cap is usually the largest single cost.

v5 uses the square-root impact law, which is the most robustly replicated
empirical regularity in market microstructure: impact grows like the square
root of participation, with a prefactor of order the asset's volatility
(Almgren, Thum, Hauptmann & Li 2005; Toth et al. 2011, *Physical Review X* 1,
"Anomalous Price Impact and the Critical Nature of Liquidity"; Bouchaud,
Bonart, Donier & Gould 2018).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .mathx import EPS, safe_div

__all__ = ["CostModel", "CostBreakdown", "estimate_costs"]


@dataclass(frozen=True)
class CostModel:
    """Venue and execution assumptions. All rates are fractions, not bps."""

    taker_fee: float = 0.00045          # typical perp taker fee, one side
    maker_fee: float = 0.00015
    maker_fill_ratio: float = 0.0       # 0 = assume we always cross
    impact_prefactor: float = 0.8       # Y in the square-root law, ~0.5-1
    slippage_floor: float = 0.00005     # residual latency/queue cost
    borrow_rate_per_hour: float = 0.0   # for spot shorts; perps use funding


@dataclass(frozen=True)
class CostBreakdown:
    fees: float
    spread: float
    impact: float
    funding: float
    total: float

    def as_dict(self) -> dict[str, float]:
        return {
            "fees": self.fees,
            "spread": self.spread,
            "impact": self.impact,
            "funding": self.funding,
            "total": self.total,
        }


def estimate_costs(
    *,
    side: int,
    notional: float,
    hourly_volume: float,
    sigma_per_hour: float,
    spread_bps: float,
    funding_rate_8h: float,
    holding_hours: float,
    model: CostModel = CostModel(),
) -> CostBreakdown:
    """Round-trip cost of a position, as a fraction of notional.

    Args:
        side: +1 for long, -1 for short. Determines the sign of funding.
        notional: position size in quote currency.
        hourly_volume: recent traded volume per hour in quote currency.
        sigma_per_hour: volatility used as the impact scale.
        spread_bps: quoted bid-ask spread in basis points.
        funding_rate_8h: perpetual funding rate per 8-hour interval, signed.
            Positive means longs pay shorts, the usual convention.
        holding_hours: expected time in the position.

    Returns:
        CostBreakdown whose `total` is always a cost to subtract from a gross
        return, except that `funding` may be negative when funding is income.
    """
    fee_rate = model.maker_fill_ratio * model.maker_fee + (1.0 - model.maker_fill_ratio) * model.taker_fee
    fees = 2.0 * fee_rate  # entry and exit

    # Crossing costs half the quoted spread on each side.
    spread = 2.0 * (max(spread_bps, 0.0) / 10000.0) / 2.0

    # Square-root law: impact = Y * sigma * sqrt(Q / V). Both legs pay it.
    participation = safe_div(abs(notional), max(hourly_volume, EPS), 0.0)
    impact = 2.0 * model.impact_prefactor * max(sigma_per_hour, EPS) * math.sqrt(max(participation, 0.0))
    impact += 2.0 * model.slippage_floor

    # Funding accrues per 8h interval and is signed by side: a long pays a
    # positive funding rate and receives a negative one.
    intervals = max(holding_hours, 0.0) / 8.0
    funding = side * funding_rate_8h * intervals
    funding += model.borrow_rate_per_hour * max(holding_hours, 0.0)

    total = fees + spread + impact + funding
    return CostBreakdown(fees, spread, impact, funding, total)
