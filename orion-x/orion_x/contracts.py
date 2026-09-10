"""Input contract and point-in-time enforcement.

ORION-X v4's README promised "point-in-time / no-lookahead features" and its
code contained nothing that checked or enforced it. A dataclass with a
`timestamp` field is not a guarantee; it is a comment. v5 makes the guarantee
mechanical: every snapshot carries the observation time of its *latest*
constituent, `PointInTimeGuard` refuses any snapshot stamped after the decision
time, and the backtester constructs features exclusively from a trailing
window, so a leak has to get past both.

The dead fields from v4 are gone. `sentiment_score`, `staking_ratio`,
`long_short_ratio`, `basis`, `liquidation_long_1h`, `liquidation_short_1h`,
`beta_btc`, `beta_eth`, `correlation_btc`, `correlation_market`, `vix` and
`dxy_return_24h` were all declared and none of them was read anywhere in the
engine. Each one is either used now or removed; `unlock_next_7d_pct` in
particular was declared, ignored, and is one of the few genuinely
well-evidenced negative-return events in the asset class.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

from .version import CONTRACT_VERSION

__all__ = [
    "CONTRACT_VERSION",
    "MarketSnapshot",
    "AssetSnapshot",
    "EquityBenchmark",
    "ScheduledEvent",
    "PriceHistory",
    "EngineConfig",
    "PointInTimeGuard",
    "LookaheadError",
]


class LookaheadError(ValueError):
    """Raised when an input is stamped later than the decision timestamp."""


@dataclass
class PriceHistory:
    """Trailing observations used for volatility, factor and graph estimation.

    `hourly_log_returns` must be ordered oldest to newest and must end at or
    before the decision timestamp. `as_of` is the close time of the final bar.
    """

    as_of: datetime
    hourly_log_returns: np.ndarray = field(default_factory=lambda: np.zeros(0))
    hourly_volume: np.ndarray = field(default_factory=lambda: np.zeros(0))

    def __post_init__(self) -> None:
        self.hourly_log_returns = np.asarray(self.hourly_log_returns, dtype=float)
        self.hourly_volume = np.asarray(self.hourly_volume, dtype=float)

    @property
    def n(self) -> int:
        return int(self.hourly_log_returns.size)


@dataclass
class MarketSnapshot:
    """State of the crypto market as a whole at `timestamp`."""

    timestamp: datetime
    btc_price: float
    eth_price: float
    btc_return_1h: float = 0.0
    btc_return_4h: float = 0.0
    btc_return_24h: float = 0.0
    eth_return_1h: float = 0.0
    eth_return_4h: float = 0.0
    eth_return_24h: float = 0.0
    btc_realized_vol: float = 0.0      # annualized
    eth_realized_vol: float = 0.0
    btc_dominance: float = 0.0
    total3_market_cap: float = 0.0
    stablecoin_market_cap: float = 0.0
    stablecoin_flow_24h: float = 0.0
    total_volume_24h: float = 0.0
    btc_funding: float = 0.0
    eth_funding: float = 0.0
    btc_oi_change_24h: float = 0.0
    # Macro conditioning. `macro_risk_score` is retained for callers that only
    # have a composite, but VIX and DXY are now read directly when supplied.
    vix: float | None = None
    dxy_return_24h: float | None = None
    macro_risk_score: float = 0.5
    btc_history: PriceHistory | None = None
    eth_history: PriceHistory | None = None


@dataclass
class EquityBenchmark:
    """A single equity used to build the US and China/HK relative baskets."""

    symbol: str
    region: str  # "US" or "CHINA_HK"
    price: float
    return_1h: float = 0.0
    return_4h: float = 0.0
    return_24h: float = 0.0
    volume_ratio: float = 1.0
    market_open: bool = True  # a closed market contributes a stale zero return


@dataclass
class AssetSnapshot:
    """Point-in-time state of one tradeable asset."""

    symbol: str
    timestamp: datetime
    price: float

    # --- size and valuation -------------------------------------------------
    market_cap: float = 0.0
    fdv: float = 0.0

    # --- volume and volatility ---------------------------------------------
    spot_volume_24h: float = 0.0
    perp_volume_24h: float = 0.0
    volume_1h: float = 0.0
    expected_same_hour_volume: float = 0.0   # seasonal baseline for this hour
    atr_1h: float = 0.0
    realized_vol_1h: float = 0.0

    # --- microstructure -----------------------------------------------------
    cvd_1h: float = 0.0
    taker_buy_1h: float = 0.0
    taker_sell_1h: float = 0.0
    orderbook_imbalance: float = 0.0         # (bid - ask) / (bid + ask), [-1, 1]
    bid_depth_1pct: float = 0.0
    ask_depth_1pct: float = 0.0
    spread_bps: float = 0.0
    # Cont, Kukanov & Stoikov (2014) order flow imbalance and its depth scale.
    # If the adapter cannot supply true OFI, leave it at zero and the engine
    # falls back to the (weaker) taker imbalance.
    ofi_1h: float = 0.0
    avg_depth: float = 0.0

    # --- derivatives --------------------------------------------------------
    open_interest: float = 0.0
    oi_change_1h: float = 0.0
    oi_change_4h: float = 0.0
    oi_change_24h: float = 0.0
    funding_rate: float = 0.0                # per 8h interval, signed
    funding_change: float = 0.0
    predicted_funding: float = 0.0
    basis_annualized: float = 0.0
    long_short_ratio: float = 1.0
    liquidation_long_1h: float = 0.0
    liquidation_short_1h: float = 0.0

    # --- fundamentals and supply -------------------------------------------
    active_addresses_growth: float = 0.0
    new_addresses_growth: float = 0.0
    tvl_growth: float = 0.0
    fees_growth: float = 0.0
    protocol_revenue_growth: float = 0.0
    exchange_netflow_z: float = 0.0
    whale_flow_z: float = 0.0
    staking_ratio: float = 0.0
    circulating_ratio: float = 1.0           # circulating / total supply
    unlock_next_7d_pct: float = 0.0          # supply unlocking as % of float
    unlock_next_30d_pct: float = 0.0

    # --- attention and sentiment -------------------------------------------
    social_volume_z: float = 0.0
    sentiment_score: float = 0.0             # [-1, 1]
    search_interest_z: float = 0.0
    catalyst_score: float = 0.0              # [-1, 1]
    event_risk_score: float = 0.0            # [0, 1]

    # --- returns ------------------------------------------------------------
    price_return_5m: float = 0.0
    price_return_15m: float = 0.0
    price_return_1h: float = 0.0
    price_return_4h: float = 0.0
    price_return_24h: float = 0.0
    price_return_7d: float = 0.0
    price_return_30d: float = 0.0

    # --- levels -------------------------------------------------------------
    recent_high_24h: float = 0.0
    recent_low_24h: float = 0.0
    support_1h: float = 0.0
    resistance_1h: float = 0.0
    vwap_24h: float = 0.0                    # anchor for the disposition proxy

    history: PriceHistory | None = None

    def total_volume(self) -> float:
        return self.spot_volume_24h + self.perp_volume_24h


@dataclass
class ScheduledEvent:
    """A known future event inside or near the decision horizon."""

    timestamp: datetime
    event_type: str
    importance: float = 0.5        # [0, 1]
    expected_direction: float = 0.0
    priced_in: float = 0.5         # [0, 1]
    duration_hours: float = 2.0


@dataclass
class EngineConfig:
    """Everything the engine is allowed to tune, in one auditable place."""

    horizon_hours: float = 7.0

    # --- gates --------------------------------------------------------------
    # The edge hurdle is expressed as a fraction of horizon volatility, not as
    # an absolute return. An absolute hurdle is not comparable across horizons
    # or across assets: 35 basis points is a demanding 0.13 sigma over seven
    # hours on a mid-cap and a negligible 0.02 sigma over two weeks, so a fixed
    # number silently makes the engine strict at short horizons and permissive
    # at long ones. The absolute floor below only guards against accepting an
    # edge smaller than the fees themselves.
    min_net_edge_sigma: float = 0.04       # net edge >= 4% of horizon sigma
    min_net_edge_abs: float = 0.0009       # ... and at least ~2x round-trip fees
    # Reported on every card but no longer a gate; see `orion_x.engine`.
    min_expected_rr: float = 1.5
    # Directional confidence, defined in `orion_x.engine` as P(sign correct).
    # Its ceiling is set by the information coefficient: at IC = 0.03 even a
    # three-sigma view only reaches about 0.536, so a threshold above that can
    # never pass and silently converts the engine into a no-op. v4 shipped 0.55.
    min_confidence: float = 0.505
    max_event_risk: float = 0.80
    max_uncertainty: float = 0.60
    min_liquidity_score: float = 0.25
    min_dollar_volume_24h: float = 5e6
    max_participation: float = 0.02        # cap position at 2% of hourly volume

    # --- barriers -----------------------------------------------------------
    tp_atr_multiple: float = 2.0
    sl_atr_multiple: float = 1.2
    min_barrier_sigma: float = 0.6         # barriers at least 0.6 horizon sigma
    max_barrier_sigma: float = 3.0

    # --- alpha discipline ---------------------------------------------------
    # Grinold's forecasting rule: alpha = IC * sigma * z. `assumed_ic` is the
    # information coefficient the composite score is *assumed* to have until a
    # walk-forward run measures it. 0.03 is at the optimistic end of what
    # short-horizon crypto signals sustain out of sample after costs.
    assumed_ic: float = 0.03
    max_abs_ic: float = 0.08               # refuse to believe a larger IC
    ic_shrink_on_uncertainty: float = 0.5
    # How far to move block weights from their priors toward the measured-IC
    # optimum. 1.0 trusts the measurement completely; 0.0 ignores it. The
    # measurement is a correlation estimated from a few hundred overlapping
    # observations, so it deserves weight but not the whole vote.
    ic_weight_confidence: float = 0.7

    # --- sizing -------------------------------------------------------------
    kelly_fraction: float = 0.25           # quarter Kelly
    max_risk_per_trade: float = 0.0075
    leverage_ceiling: float = 1.5
    target_portfolio_vol: float = 0.35     # annualized

    # --- costs --------------------------------------------------------------
    taker_fee: float = 0.00045
    impact_prefactor: float = 0.8

    # --- direction ----------------------------------------------------------
    allow_short: bool = True

    def weights(self) -> dict[str, float]:
        """Evidence-block weights, normalized to 1.

        These are priors on where information lives, not fitted parameters.
        They are exposed so that `orion_x.backtest` can refit them per fold and
        so that a reviewer can see them without reading the source.
        """
        w = {
            "flow": 0.26,
            "momentum": 0.16,
            "carry": 0.16,
            "fundamental": 0.12,
            "psychology": 0.12,
            "relative": 0.10,
            "catalyst": 0.08,
        }
        s = sum(w.values())
        return {k: v / s for k, v in w.items()}


class PointInTimeGuard:
    """Rejects inputs that could not have been observed at the decision time.

    `tolerance` allows for clock skew between an exchange stamp and the
    decision clock; anything beyond it is treated as a leak, not a rounding
    error, and raises.
    """

    def __init__(self, decision_time: datetime, tolerance: timedelta = timedelta(seconds=90)):
        if decision_time.tzinfo is None:
            decision_time = decision_time.replace(tzinfo=timezone.utc)
        self.decision_time = decision_time
        self.tolerance = tolerance
        self.violations: list[str] = []

    def check(self, label: str, stamp: datetime | None) -> None:
        if stamp is None:
            return
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        if stamp > self.decision_time + self.tolerance:
            raise LookaheadError(
                f"{label} is stamped {stamp.isoformat()} but the decision time is "
                f"{self.decision_time.isoformat()}: this feature is not point-in-time."
            )

    def check_all(
        self,
        market: MarketSnapshot,
        asset: AssetSnapshot,
        equities: list[EquityBenchmark] | None = None,
    ) -> None:
        self.check("market snapshot", market.timestamp)
        self.check("asset snapshot", asset.timestamp)
        for h, name in ((market.btc_history, "btc history"), (market.eth_history, "eth history"), (asset.history, "asset history")):
            if h is not None:
                self.check(name, h.as_of)
