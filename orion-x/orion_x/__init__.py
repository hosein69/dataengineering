"""ORION-X v5 -- a regime-gated, cost-aware crypto decision engine.

The engine's contract in one sentence: given point-in-time market and asset
snapshots, it returns a signal card containing a decision, the barrier geometry
that decision assumes, the first-passage probabilities of that geometry, the
expected value net of a fully specified cost model, and the size that the
binding risk constraint permits.

Typical use:

    from orion_x import EngineConfig, decide, signal_to_dict

    card = decide(market_snapshot, asset_snapshot, config=EngineConfig())
    print(card.decision, card.expected_return_net)

This is a research and decision-support engine. It does not place orders, and
nothing in it should be connected directly to an exchange. See README.md.
"""
from .alpha import AlphaForecast, combine_blocks, grinold_drift
from .barriers import BarrierProbs, barrier_probs, outcome_moments, survival_moment
from .contracts import (
    AssetSnapshot,
    EngineConfig,
    EquityBenchmark,
    LookaheadError,
    MarketSnapshot,
    PointInTimeGuard,
    PriceHistory,
    ScheduledEvent,
)
from .costs import CostModel, estimate_costs
from .engine import SignalCard, TradePlan, decide, minimum_viable_horizon, signal_to_dict
from .graph import build_graph_context
from .sizing import size_position
from .version import CONTRACT_VERSION, VERSION

__all__ = [
    "VERSION", "CONTRACT_VERSION",
    "MarketSnapshot", "AssetSnapshot", "EquityBenchmark", "ScheduledEvent",
    "PriceHistory", "EngineConfig", "PointInTimeGuard", "LookaheadError",
    "decide", "signal_to_dict", "SignalCard", "TradePlan", "minimum_viable_horizon",
    "barrier_probs", "outcome_moments", "survival_moment", "BarrierProbs",
    "CostModel", "estimate_costs", "size_position", "build_graph_context",
    "AlphaForecast", "combine_blocks", "grinold_drift",
]
