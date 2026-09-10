"""Behavioural tests for the decision engine.

These assert *properties* the engine must have -- symmetry, monotonicity,
gating, no-lookahead -- rather than exact numbers, so they keep their meaning
when the parameters are refitted.
"""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from orion_x.contracts import (
    AssetSnapshot,
    EngineConfig,
    LookaheadError,
    MarketSnapshot,
    PriceHistory,
    ScheduledEvent,
)
from orion_x.engine import decide

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def _history(n=336, seed=0, scale=0.012):
    rng = np.random.default_rng(seed)
    return PriceHistory(
        as_of=NOW,
        hourly_log_returns=rng.standard_normal(n) * scale,
        hourly_volume=np.abs(rng.standard_normal(n)) * 4e6 + 8e6,
    )


def _market(**kw):
    base = dict(
        timestamp=NOW, btc_price=68000.0, eth_price=2900.0,
        btc_return_4h=0.004, btc_return_24h=0.01, eth_return_4h=0.005,
        btc_realized_vol=0.55, stablecoin_market_cap=190e9, stablecoin_flow_24h=6e8,
        btc_history=_history(seed=1), eth_history=_history(seed=2),
    )
    base.update(kw)
    return MarketSnapshot(**base)


def _asset(**kw):
    base = dict(
        symbol="TEST", timestamp=NOW, price=100.0,
        market_cap=2.4e9, fdv=3.2e9,
        spot_volume_24h=6e8, perp_volume_24h=5e8, volume_1h=5.2e7,
        expected_same_hour_volume=4.6e7,
        atr_1h=0.9, realized_vol_1h=0.011,
        cvd_1h=9e6, taker_buy_1h=3.1e7, taker_sell_1h=2.1e7,
        orderbook_imbalance=0.12, bid_depth_1pct=9e6, ask_depth_1pct=8e6,
        spread_bps=3.0, ofi_1h=1.6e6, avg_depth=8.5e6,
        oi_change_4h=0.03, funding_rate=0.00008,
        price_return_15m=0.002, price_return_1h=0.006, price_return_4h=0.017,
        price_return_24h=0.03, price_return_7d=0.07,
        support_1h=97.5, resistance_1h=102.0, vwap_24h=99.2,
        history=_history(seed=3),
    )
    base.update(kw)
    return AssetSnapshot(**base)


def test_lookahead_is_refused():
    a = _asset(timestamp=NOW + timedelta(minutes=30))
    with pytest.raises(LookaheadError):
        decide(_market(), a, now=NOW)


def test_lookahead_can_be_disabled_for_replay():
    a = _asset(timestamp=NOW + timedelta(minutes=30))
    card = decide(_market(), a, now=NOW, enforce_point_in_time=False)
    assert card.decision in {"LONG", "SHORT", "NO_TRADE"}


def test_probabilities_sum_to_one():
    card = decide(_market(), _asset())
    p = card.probabilities
    assert p["take_profit"] + p["stop_loss"] + p["timeout"] == pytest.approx(1.0, abs=1e-6)


def test_direction_flips_with_the_evidence():
    """The engine must be able to express a short. v4 could only ever say BUY
    or WAIT, which is the structural consequence of scoring every block in
    [0, 1] instead of [-1, 1]."""
    bullish = decide(_market(), _asset(taker_buy_1h=4.4e7, taker_sell_1h=0.8e7, ofi_1h=6e6,
                                       price_return_4h=0.03, price_return_7d=0.14, cvd_1h=2.2e7))
    bearish = decide(_market(), _asset(taker_buy_1h=0.8e7, taker_sell_1h=4.4e7, ofi_1h=-6e6,
                                       price_return_4h=-0.03, price_return_7d=-0.14, cvd_1h=-2.2e7))
    assert bullish.composite > 0 > bearish.composite


def test_event_risk_gate_blocks_trading():
    event = ScheduledEvent(timestamp=NOW + timedelta(hours=2), event_type="FOMC",
                           importance=1.0, priced_in=0.0)
    card = decide(_market(), _asset(), events=[event])
    assert card.decision == "NO_TRADE"
    assert card.gates["event_risk"] is False


def test_illiquid_asset_is_refused():
    card = decide(_market(), _asset(spot_volume_24h=6e5, perp_volume_24h=4e5,
                                    volume_1h=4e4, spread_bps=120.0,
                                    bid_depth_1pct=2e4, ask_depth_1pct=2e4))
    assert card.decision == "NO_TRADE"
    assert not (card.gates["liquidity"] and card.gates["dollar_volume"])


def test_no_trade_implies_no_size():
    card = decide(_market(), _asset(spread_bps=90.0))
    if card.decision == "NO_TRADE":
        assert card.size["fraction"] == 0.0


def test_costs_are_never_a_subsidy():
    """Fees, spread and impact must always be costs. Only funding may be
    income, and only when it is genuinely being received."""
    card = decide(_market(), _asset(funding_rate=-0.0009))
    assert card.costs["fees"] > 0 and card.costs["spread"] >= 0 and card.costs["impact"] > 0
    assert card.costs["funding"] < 0  # a long receives negative funding


def test_funding_sign_is_directional():
    """v4 charged abs(funding), which bills a long for income it receives."""
    pays = decide(_market(), _asset(funding_rate=0.0012))
    earns = decide(_market(), _asset(funding_rate=-0.0012))
    assert pays.costs["funding"] > 0 > earns.costs["funding"]


def test_unlock_overhang_is_read():
    """`unlock_next_7d_pct` was declared in v4's contract and never used."""
    clean = decide(_market(), _asset(unlock_next_7d_pct=0.0))
    cliff = decide(_market(), _asset(unlock_next_7d_pct=0.06))
    assert cliff.blocks["fundamental"] < clean.blocks["fundamental"]


def test_wider_barriers_lower_the_touch_probabilities():
    cfg_tight = EngineConfig(min_barrier_sigma=0.5, max_barrier_sigma=0.6)
    cfg_wide = EngineConfig(min_barrier_sigma=2.6, max_barrier_sigma=3.0)
    tight = decide(_market(), _asset(), config=cfg_tight)
    wide = decide(_market(), _asset(), config=cfg_wide)
    assert wide.probabilities["timeout"] > tight.probabilities["timeout"]


def test_confidence_cannot_exceed_what_the_ic_supports():
    """At a plausible IC, per-trade directional confidence lives in the low
    fifties. Anything claiming 70% is not measuring what it says it is."""
    card = decide(_market(), _asset(), measured_ic=0.03)
    assert 0.5 <= card.confidence < 0.60


def test_horizon_curve_is_monotone_in_the_useful_region():
    """Fixed costs do not scale with the horizon while the forecastable move
    grows like sqrt(T), so net edge must improve with horizon until funding
    dominates."""
    card = decide(_market(), _asset(funding_rate=0.0))
    curve = {int(k[:-1]): v for k, v in card.horizon_curve.items() if k.endswith("h")}
    assert curve[168] > curve[7]


def test_signal_card_is_serializable():
    from orion_x.engine import signal_to_dict
    import json

    d = signal_to_dict(decide(_market(), _asset()))
    json.dumps(d)  # must not raise
    assert d["version"].startswith("5.")
