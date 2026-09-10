"""Evidence blocks.

Every block returns a *signed* score in [-1, 1] giving the direction and
strength of the expected idiosyncratic move, together with a diagnostic dict.
This is a structural change from v4, where every block returned a [0, 1]
"goodness" and the engine could only ever express a long. A [0, 1] block cannot
say "this is a short"; it can only say "this is a weak long", which is why v4's
decision set was {BUY, WAIT} and why its scoring was systematically
long-biased in an asset class that spends half its life falling.

Literature choices that differ from v4, with reasons:

* **Short-horizon momentum is conditional, not unconditional.** v4 rewarded a
  positive 15-minute return as evidence of continuation. The published crypto
  momentum results -- Liu & Tsyvinski (2021), *Review of Financial Studies*
  34(6), and Liu, Tsyvinski & Wu (2022), *Journal of Finance* 77(2) -- are at
  one-week to four-week horizons. At intraday horizons the robust effect is the
  opposite one: short-horizon reversal (Lehmann 1990, *QJE*; Lo & MacKinlay
  1990, *RFS*), amplified in crypto by inventory effects around liquidations.
  v5 therefore only treats an impulse as continuation when participation
  confirms it, and treats an unconfirmed impulse as a reversal signal.

* **Open interest is read as four quadrants, not one blend.** v4 computed
  `0.55 * price * oi_coherence + 0.45 * tanh(-oi_change / 0.20)`, where the
  second term rewards falling open interest unconditionally and directly
  contradicts the first. The standard reading is: price up with OI up is new
  long positioning; price up with OI down is short covering, which is a flow
  that exhausts itself; price down with OI up is new shorts; price down with OI
  down is long liquidation, which is forced and mean-reverting.

* **Funding is a crowding measure.** Positive perpetual funding means longs pay
  shorts, which means leveraged long positioning is crowded. Sustained extreme
  funding predicts negative forward returns, and this is one of the few crypto
  anomalies with a clear economic mechanism rather than a data-mined pattern.
  v4 had the sign right; v5 makes it percentile-conditional so that a mildly
  positive funding rate is not treated as bearish evidence.

* **Attention is contrarian at extremes.** Barber & Odean (2008), *RFS* 21(2),
  "All That Glitters": retail buys attention-grabbing assets, producing
  temporary price pressure that reverses. Social and search spikes therefore
  raise reversal risk rather than confirming a trend.

* **Unrealized profit creates supply.** The disposition effect (Shefrin &
  Statman 1985; Odean 1998, *Journal of Finance* 53) means holders sitting on
  gains sell into strength. Distance above an anchor price proxies the
  unrealized-gain overhang.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .contracts import AssetSnapshot, EquityBenchmark, MarketSnapshot, ScheduledEvent
from .mathx import EPS, clamp, rank_pct, safe_div, tanh_norm

__all__ = ["Block", "regime_block", "flow_block", "momentum_block", "carry_block", "fundamental_block", "psychology_block", "relative_block", "catalyst_block", "event_risk", "RegimeState"]


@dataclass
class Block:
    """A signed piece of evidence with its own reliability."""

    score: float                                    # [-1, 1], signed
    reliability: float = 1.0                        # [0, 1], data quality
    diagnostics: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def clipped(self) -> "Block":
        self.score = clamp(self.score, -1.0, 1.0)
        self.reliability = clamp(self.reliability, 0.0, 1.0)
        return self


@dataclass
class RegimeState:
    label: str
    risk_appetite: float        # [-1, 1]: appetite for long crypto risk
    stress: float               # [0, 1]
    probabilities: dict[str, float]
    diagnostics: dict[str, float]


# --------------------------------------------------------------------------
# Regime
# --------------------------------------------------------------------------

def regime_block(m: MarketSnapshot, previous: str | None = None) -> RegimeState:
    """Soft regime classification with hysteresis.

    v4 used five hard thresholds on a single hand-weighted score, so a market
    at score 0.579 was labelled SIDEWAYS and at 0.581 BULL_TREND, with all the
    downstream gating changing discontinuously. Regime labels that flip on a
    third decimal place produce whipsaw in every downstream decision.

    v5 keeps the same five states but assigns them soft probabilities via a
    temperature-scaled distance to each state's centre, adds a hysteresis bonus
    to the incumbent state, and passes a continuous `risk_appetite` downstream
    so nothing depends on the hard label.
    """
    trend_fast = tanh_norm(m.btc_return_4h, 0.03)
    trend_slow = tanh_norm(m.btc_return_24h, 0.08)
    trend = 0.62 * trend_fast + 0.38 * trend_slow

    # Breadth: ETH outperforming BTC is the classic risk-on tell inside crypto.
    breadth = tanh_norm(m.eth_return_4h - m.btc_return_4h, 0.02)

    # Stablecoin issuance is the sector's net capital inflow.
    liq = tanh_norm(safe_div(m.stablecoin_flow_24h, m.stablecoin_market_cap * 0.002, 0.0), 1.0) if m.stablecoin_market_cap > EPS else 0.0

    # Macro. Use VIX and DXY directly when supplied; fall back to the composite.
    if m.vix is not None:
        macro = -tanh_norm(m.vix - 18.0, 8.0)
    else:
        macro = 1.0 - 2.0 * clamp(m.macro_risk_score)
    if m.dxy_return_24h is not None:
        macro -= 0.5 * tanh_norm(m.dxy_return_24h, 0.005)
    macro = clamp(macro, -1.0, 1.0)

    # Volatility stress. Annualized realized vol above ~80% is the regime where
    # cross-asset correlations converge to one and single-name theses stop
    # working, independent of direction.
    vol_stress = clamp((m.btc_realized_vol - 0.55) / 0.75) if m.btc_realized_vol > EPS else 0.0
    funding_stress = clamp(abs(m.btc_funding) / 0.0008)

    risk_appetite = clamp(0.42 * trend + 0.18 * breadth + 0.15 * liq + 0.25 * macro, -1.0, 1.0)
    stress = clamp(0.55 * vol_stress + 0.25 * funding_stress + 0.20 * clamp(-risk_appetite))

    centres = {
        "BULL_EXPANSION": (0.75, 0.25),
        "BULL_TREND": (0.35, 0.30),
        "SIDEWAYS": (0.00, 0.30),
        "BEAR_TREND": (-0.40, 0.45),
        "CAPITULATION": (-0.80, 0.85),
    }
    temp = 0.28
    logits = {}
    for name, (ra, st) in centres.items():
        d2 = ((risk_appetite - ra) ** 2 + 0.6 * (stress - st) ** 2) / (2 * temp**2)
        logits[name] = -d2
    if previous in logits:
        logits[previous] += 0.35  # hysteresis: do not flip on noise
    mx = max(logits.values())
    exps = {k: math.exp(v - mx) for k, v in logits.items()}
    tot = sum(exps.values())
    probs = {k: v / tot for k, v in exps.items()}
    label = max(probs, key=probs.get)

    return RegimeState(
        label=label,
        risk_appetite=risk_appetite,
        stress=stress,
        probabilities=probs,
        diagnostics={"trend": trend, "breadth": breadth, "liquidity": liq, "macro": macro, "vol_stress": vol_stress},
    )


# --------------------------------------------------------------------------
# Order flow
# --------------------------------------------------------------------------

def flow_block(a: AssetSnapshot) -> Block:
    """Order flow imbalance and book pressure.

    The primary measure is OFI as defined by Cont, Kukanov & Stoikov (2014),
    "The Price Impact of Order Book Events", *Journal of Financial Econometrics*
    12(1): the contemporaneous relation between price change and order flow is
    approximately linear in OFI *normalized by depth*, not in raw traded volume.
    Depth normalization is the part v4 was missing -- it compared taker
    imbalance across assets with wildly different book sizes as though the
    numbers were commensurable.

    When an adapter cannot supply true OFI, the block degrades to taker
    imbalance and CVD and reports lower reliability rather than pretending.
    """
    notes: list[str] = []
    total_taker = a.taker_buy_1h + a.taker_sell_1h
    reliability = 1.0

    if abs(a.ofi_1h) > EPS and a.avg_depth > EPS:
        ofi_norm = a.ofi_1h / a.avg_depth
        primary = math.tanh(ofi_norm / 0.5)
        notes.append("depth-normalized OFI available")
    elif total_taker > EPS:
        primary = safe_div(a.taker_buy_1h - a.taker_sell_1h, total_taker, 0.0)
        reliability = 0.65
        notes.append("no OFI: degraded to taker imbalance")
    else:
        primary = 0.0
        reliability = 0.2
        notes.append("no usable flow data")

    cvd = math.tanh(safe_div(a.cvd_1h, max(total_taker, EPS), 0.0)) if total_taker > EPS else 0.0
    book = clamp(a.orderbook_imbalance, -1.0, 1.0)

    # Book imbalance is the least reliable of the three: it is trivially spoofed
    # and it mean-reverts within seconds, so it gets the smallest weight.
    score = 0.55 * primary + 0.30 * cvd + 0.15 * book

    # Persistent one-sided flow into a thin book moves price; the same flow into
    # a deep book does not. Scale by how large the flow is relative to depth.
    if a.avg_depth > EPS and total_taker > EPS:
        pressure = clamp(total_taker / (a.avg_depth * 20.0), 0.0, 1.5)
        score *= 0.6 + 0.4 * min(pressure, 1.0)

    return Block(score, reliability, {"ofi": primary, "cvd": cvd, "book": book}, notes).clipped()


def kyle_lambda(history_returns: np.ndarray, history_volume: np.ndarray) -> float:
    """Kyle's price-impact coefficient, estimated as |return| per unit volume.

    Kyle (1985), *Econometrica* 53(6). A high lambda means a small order moves
    the price a lot, which is a liquidity risk and not, as a naive reading of
    "volatility with volume" would have it, a sign of interest.
    """
    r = np.asarray(history_returns, dtype=float)
    v = np.asarray(history_volume, dtype=float)
    n = min(r.size, v.size)
    if n < 12:
        return 0.0
    r, v = np.abs(r[-n:]), v[-n:]
    mask = v > EPS
    if mask.sum() < 8:
        return 0.0
    return float(np.median(r[mask] / np.sqrt(v[mask])))


def liquidity_block(a: AssetSnapshot, sigma_per_hour: float) -> Block:
    """Executability, on a scale where 0 means "do not trade this".

    Amihud (2002), *Journal of Financial Markets* 5(1), defines illiquidity as
    |return| per dollar of volume; the depth and spread terms below are the
    order-book-visible counterparts of the same idea.
    """
    dollar_vol = a.total_volume()
    depth = a.bid_depth_1pct + a.ask_depth_1pct

    # Depth expressed in hours of trading, which is the unit that matters for
    # exiting a position inside the horizon.
    hourly = max(dollar_vol / 24.0, EPS)
    depth_hours = clamp(safe_div(depth, hourly, 0.0) / 0.5)
    spread_ok = 1.0 - clamp(a.spread_bps / 25.0)

    # Amihud-style: how much price moves per dollar traded, normalized by the
    # asset's own volatility so that it compares across names.
    amihud = safe_div(abs(a.price_return_1h), max(a.volume_1h, EPS), 0.0)
    amihud_norm = 1.0 - clamp(amihud / max(safe_div(sigma_per_hour, hourly, EPS), EPS) / 3.0)

    score = clamp(0.40 * depth_hours + 0.35 * spread_ok + 0.25 * amihud_norm)
    notes = []
    if dollar_vol < 5e6:
        notes.append("24h dollar volume below 5M: execution assumptions unreliable")
    # Liquidity is a magnitude, not a direction: returned as a [0,1] gate.
    return Block(score, 1.0, {"depth_hours": depth_hours, "spread_ok": spread_ok, "amihud": amihud_norm}, notes)


# --------------------------------------------------------------------------
# Momentum
# --------------------------------------------------------------------------

def momentum_block(a: AssetSnapshot, flow: Block, volume_ratio: float, idio_returns: np.ndarray | None = None) -> Block:
    """Multi-scale momentum with a conditional short-horizon sign.

    Three separate horizons with genuinely different signs of evidence:

    * 5m-1h: reversal by default, continuation only under confirmation.
    * 4h-24h: the crossover zone, weakly trending.
    * 7d-30d: the horizon where the published crypto momentum premium lives.

    Confirmation is participation: volume above its own same-hour seasonal
    baseline *and* order flow pointing the same way as price. An impulse
    without participation is one participant, and one participant reverts.
    """
    notes: list[str] = []

    impulse_raw = tanh_norm(a.price_return_15m, 0.01)
    participation = clamp(
        0.55 * clamp(0.5 + 0.5 * math.tanh(math.log(max(volume_ratio, 1e-6))), 0.0, 1.0)
        + 0.45 * clamp(0.5 + 0.5 * flow.score, 0.0, 1.0)
    )
    flow_agrees = (impulse_raw * flow.score) > 0

    # Confirmation strength in [-1, 1]: +1 fully confirmed, -1 fully unconfirmed.
    confirm = (2.0 * participation - 1.0) * (1.0 if flow_agrees else -1.0)
    short_horizon = impulse_raw * confirm
    if confirm < 0:
        notes.append("short-horizon impulse is unconfirmed: treated as reversal risk")

    mid = 0.6 * tanh_norm(a.price_return_4h, 0.05) + 0.4 * tanh_norm(a.price_return_24h, 0.10)

    # Long horizon on idiosyncratic returns when available, so the momentum is
    # the asset's own and not a restatement of BTC's trend.
    if idio_returns is not None and idio_returns.size >= 72:
        cum = float(np.sum(idio_returns[-168:])) if idio_returns.size >= 168 else float(np.sum(idio_returns))
        sd = float(np.std(idio_returns, ddof=1)) * math.sqrt(min(idio_returns.size, 168))
        long_horizon = tanh_norm(cum, max(sd, EPS))
        notes.append("long-horizon momentum measured on idiosyncratic returns")
    else:
        long_horizon = 0.35 * tanh_norm(a.price_return_7d, 0.20) + 0.25 * tanh_norm(a.price_return_30d, 0.45)

    # Weighting reflects where the evidence actually is: the weekly/monthly
    # horizon carries the documented premium, the intraday horizon is mostly
    # microstructure.
    score = 0.22 * short_horizon + 0.30 * mid + 0.48 * long_horizon

    # Exhaustion: a move already several sigma extended has spent its fuel.
    sigma_1h = max(a.realized_vol_1h, 0.002)
    extension = abs(a.price_return_4h) / (sigma_1h * 2.0)
    if extension > 2.5:
        score *= 0.6
        notes.append("move is more than 2.5 sigma extended: momentum discounted")

    return Block(score, flow.reliability * 0.5 + 0.5, {"short": short_horizon, "mid": mid, "long": long_horizon, "participation": participation, "extension": extension}, notes).clipped()


# --------------------------------------------------------------------------
# Carry: funding, basis, open interest
# --------------------------------------------------------------------------

def carry_block(a: AssetSnapshot, funding_history: np.ndarray | None = None) -> Block:
    """Funding, basis and the four open-interest quadrants.

    Funding is treated as a crowding measure and is percentile-conditional: the
    signal is in the tails, not in the level. A funding rate of 0.01% per 8h is
    the market's resting state and carries no information, but v4's
    `tanh(funding / 0.001)` read it as bearish evidence worth 2.4 points of
    score.
    """
    notes: list[str] = []

    if funding_history is not None and funding_history.size >= 48:
        pct = rank_pct(a.funding_rate, funding_history)
        # Only the tails speak. Maps [0,1] percentile to a signed contrarian
        # score that is ~0 across the middle two quartiles.
        extreme = 0.0
        if pct > 0.85:
            extreme = -(pct - 0.85) / 0.15
        elif pct < 0.15:
            extreme = (0.15 - pct) / 0.15
        funding_score = extreme
        notes.append(f"funding at the {pct:.0%} percentile of its own history")
    else:
        # Without history, fall back to an absolute scale anchored on the
        # economically meaningful level: 0.01%/8h is neutral, 0.1%/8h is extreme.
        funding_score = -tanh_norm(a.funding_rate - 0.0001, 0.0006)
        notes.append("no funding history: absolute-scale fallback")

    # Basis: a rich basis is leveraged long demand, same crowding logic.
    basis_score = -tanh_norm(a.basis_annualized - 0.05, 0.15) if abs(a.basis_annualized) > EPS else 0.0

    # Open interest quadrants.
    dp = a.price_return_4h
    doi = a.oi_change_4h
    quadrant = "flat"
    oi_score = 0.0
    if abs(dp) > 0.002 and abs(doi) > 0.005:
        if dp > 0 and doi > 0:
            quadrant, oi_score = "new_longs", 0.5 * tanh_norm(doi, 0.08)
        elif dp > 0 and doi < 0:
            quadrant, oi_score = "short_covering", -0.4 * tanh_norm(-doi, 0.08)
        elif dp < 0 and doi > 0:
            quadrant, oi_score = "new_shorts", -0.5 * tanh_norm(doi, 0.08)
        else:
            quadrant, oi_score = "long_liquidation", 0.45 * tanh_norm(-doi, 0.08)
        notes.append(f"open interest quadrant: {quadrant}")

    score = 0.45 * funding_score + 0.20 * basis_score + 0.35 * oi_score
    return Block(score, 1.0, {"funding": funding_score, "basis": basis_score, "oi": oi_score, "quadrant_code": {"flat": 0, "new_longs": 1, "short_covering": 2, "new_shorts": 3, "long_liquidation": 4}[quadrant]}, notes).clipped()


# --------------------------------------------------------------------------
# Fundamentals and supply
# --------------------------------------------------------------------------

def fundamental_block(a: AssetSnapshot) -> Block:
    """On-chain growth net of supply overhang.

    Growth metrics follow the network-factor evidence in Liu & Tsyvinski (2021)
    -- address growth and transaction activity predict returns at weekly-plus
    horizons -- and are therefore weighted as slow-moving context rather than as
    a trading trigger.

    The supply side is what v4 omitted entirely. `unlock_next_7d_pct` was in
    v4's dataclass and never read. Token unlocks are one of the few reliably
    negative scheduled events in the asset class: a cliff releasing several
    percent of float into a market whose daily volume is a fraction of that
    float is mechanical selling pressure with a known date.
    """
    notes: list[str] = []
    growth = [
        tanh_norm(a.active_addresses_growth, 0.20),
        tanh_norm(a.new_addresses_growth, 0.20),
        tanh_norm(a.tvl_growth, 0.20),
        tanh_norm(a.fees_growth, 0.25),
        tanh_norm(a.protocol_revenue_growth, 0.25),
    ]
    growth_score = float(np.mean(growth))

    # Exchange inflows are supply arriving at the point of sale.
    flow_score = -tanh_norm(a.exchange_netflow_z, 2.0) * 0.6 + tanh_norm(a.whale_flow_z, 2.0) * 0.4

    # Unlock overhang, scaled by how many days of volume it represents.
    unlock_score = 0.0
    if a.unlock_next_7d_pct > EPS and a.market_cap > EPS:
        unlock_notional = a.unlock_next_7d_pct * a.market_cap
        days_of_volume = safe_div(unlock_notional, max(a.total_volume(), EPS), 0.0)
        unlock_score = -clamp(days_of_volume / 2.0) * clamp(a.unlock_next_7d_pct / 0.03)
        if unlock_score < -0.15:
            notes.append(f"unlock of {a.unlock_next_7d_pct:.1%} of float within 7d (~{days_of_volume:.2f} days of volume)")
    if a.unlock_next_30d_pct > 0.10:
        unlock_score -= 0.15
        notes.append(f"large 30d unlock schedule ({a.unlock_next_30d_pct:.0%} of float)")

    # A very low circulating ratio means the float is small relative to the
    # eventual supply, i.e. the FDV/market-cap gap is future dilution.
    dilution = 0.0
    if a.fdv > EPS and a.market_cap > EPS:
        ratio = a.market_cap / a.fdv
        if ratio < 0.30:
            dilution = -0.20 * (0.30 - ratio) / 0.30
            notes.append(f"market cap is only {ratio:.0%} of FDV: structural dilution overhang")

    score = 0.45 * growth_score + 0.25 * flow_score + 0.30 * (unlock_score + dilution)
    reliability = 1.0 if any(abs(g) > EPS for g in growth) else 0.4
    return Block(score, reliability, {"growth": growth_score, "chain_flow": flow_score, "unlock": unlock_score, "dilution": dilution}, notes).clipped()


# --------------------------------------------------------------------------
# Behavioural
# --------------------------------------------------------------------------

def psychology_block(a: AssetSnapshot, regime: RegimeState) -> Block:
    """Crowding, attention, disposition overhang and liquidation reflexivity.

    Every term here is contrarian at its extreme and near-silent in the middle,
    which is the empirically supported shape: crowding does not predict returns
    until it is crowded.
    """
    notes: list[str] = []

    # Crowding: positioning that is one-sided in both the derivative and the
    # sentiment dimension.
    ls_skew = tanh_norm(a.long_short_ratio - 1.0, 0.6)
    crowding = 0.5 * ls_skew + 0.3 * tanh_norm(a.sentiment_score, 0.6) + 0.2 * tanh_norm(a.oi_change_24h, 0.30)
    crowd_score = -crowding * clamp(abs(crowding))  # quadratic: silent when mild
    if abs(crowding) > 0.6:
        notes.append("positioning and sentiment are one-sided: contrarian discount applied")

    # Attention. Barber & Odean (2008): attention-driven buying is temporary
    # price pressure, so a spike is a fade signal, not a confirmation.
    attention = 0.6 * tanh_norm(a.social_volume_z, 2.5) + 0.4 * tanh_norm(a.search_interest_z, 2.5)
    attention_score = -attention * clamp(abs(attention))
    if attention > 0.7:
        notes.append("attention spike: elevated short-horizon reversal risk")

    # Disposition overhang. Holders in profit relative to a 24h VWAP anchor
    # supply into strength; holders underwater create overhead resistance.
    disposition_score = 0.0
    if a.vwap_24h > EPS:
        gain = (a.price - a.vwap_24h) / a.vwap_24h
        sigma = max(a.realized_vol_1h * math.sqrt(24.0), 0.01)
        z = gain / sigma
        disposition_score = -tanh_norm(z, 2.0) * 0.5
        if abs(z) > 2.0:
            notes.append(f"price is {z:+.1f} sigma from 24h VWAP: disposition-effect supply/overhead")

    # Liquidation reflexivity. Forced flow is not information; it overshoots
    # and reverts. A large one-sided liquidation print is a fade of that side.
    liq_total = a.liquidation_long_1h + a.liquidation_short_1h
    liq_score = 0.0
    if liq_total > EPS and a.total_volume() > EPS:
        intensity = clamp(liq_total / (a.total_volume() / 24.0) / 0.15)
        imbalance = safe_div(a.liquidation_long_1h - a.liquidation_short_1h, liq_total, 0.0)
        liq_score = imbalance * intensity * 0.7   # longs liquidated -> bounce
        if intensity > 0.5:
            notes.append("liquidation cascade in progress: forced flow, expect overshoot and revert")

    # In a stressed regime, behavioural effects dominate fundamentals.
    stress_gain = 0.7 + 0.6 * regime.stress
    score = stress_gain * (0.35 * crowd_score + 0.25 * attention_score + 0.20 * disposition_score + 0.20 * liq_score)

    reliability = 0.5
    if abs(a.social_volume_z) > EPS or abs(a.search_interest_z) > EPS:
        reliability += 0.25
    if liq_total > EPS:
        reliability += 0.25
    return Block(score, reliability, {"crowding": crowd_score, "attention": attention_score, "disposition": disposition_score, "liquidation": liq_score}, notes).clipped()


# --------------------------------------------------------------------------
# Relative value
# --------------------------------------------------------------------------

def relative_block(a: AssetSnapshot, equities: list[EquityBenchmark], m: MarketSnapshot) -> Block:
    """Relative momentum against equity baskets and against crypto majors.

    v4 subtracted a raw mean of equity one-hour returns from the asset's own
    one-hour return and reported the difference as a signal. Two problems: a
    closed market contributes a zero return that is mistaken for flat
    performance, and comparing a 4%-vol asset to a 0.3%-vol basket without
    scaling makes the crypto leg the only thing the difference ever measures.

    v5 excludes closed markets and standardizes both legs by their own
    volatility before differencing, which is what makes the comparison mean
    anything.
    """
    notes: list[str] = []

    def basket(region: str) -> tuple[float, int]:
        members = [e for e in equities if e.region == region and e.market_open]
        if not members:
            return 0.0, 0
        return float(np.mean([e.return_1h for e in members])), len(members)

    us_ret, us_n = basket("US")
    cn_ret, cn_n = basket("CHINA_HK")
    if us_n == 0 and cn_n == 0:
        notes.append("all equity markets closed: relative-equity evidence unavailable")

    asset_sigma = max(a.realized_vol_1h, 0.004)
    equity_sigma = 0.0035  # typical 1h sigma for a large-cap equity basket

    us_rel = safe_div(a.price_return_1h, asset_sigma, 0.0) - safe_div(us_ret, equity_sigma, 0.0) if us_n else 0.0
    cn_rel = safe_div(a.price_return_1h, asset_sigma, 0.0) - safe_div(cn_ret, equity_sigma, 0.0) if cn_n else 0.0

    # Relative to crypto majors: the strength that actually matters intraday.
    vs_btc = safe_div(a.price_return_4h - m.btc_return_4h, asset_sigma * 2.0, 0.0)
    vs_eth = safe_div(a.price_return_4h - m.eth_return_4h, asset_sigma * 2.0, 0.0)

    score = 0.20 * math.tanh(us_rel / 2.0) + 0.10 * math.tanh(cn_rel / 2.0) + 0.45 * math.tanh(vs_btc) + 0.25 * math.tanh(vs_eth)
    reliability = 0.5 + 0.25 * (us_n > 0) + 0.25 * (cn_n > 0)
    return Block(score, reliability, {"us_rel": us_rel, "cn_rel": cn_rel, "vs_btc": vs_btc, "vs_eth": vs_eth, "us_members": float(us_n), "cn_members": float(cn_n)}, notes).clipped()


def catalyst_block(a: AssetSnapshot) -> Block:
    """Discretionary catalyst input, discounted by how priced-in it likely is."""
    raw = clamp(a.catalyst_score, -1.0, 1.0)
    # A catalyst accompanied by a large recent move is already in the price.
    already_moved = clamp(abs(a.price_return_24h) / 0.15)
    score = raw * (1.0 - 0.6 * already_moved)
    notes = ["catalyst discounted: much of the move may already be priced"] if already_moved > 0.5 else []
    return Block(score, 0.5, {"raw": raw, "already_moved": already_moved}, notes).clipped()


def event_risk(a: AssetSnapshot, events: list[ScheduledEvent], now, horizon_hours: float) -> tuple[float, list[str]]:
    """Probability-weighted event risk over the horizon, in [0, 1]."""
    from datetime import timedelta

    notes: list[str] = []
    risk = clamp(a.event_risk_score)
    end = now + timedelta(hours=horizon_hours)
    for e in events:
        if not (now <= e.timestamp <= end):
            continue
        # An event nearer the start of the horizon has more of the horizon left
        # to express its consequences, so proximity raises risk.
        remaining = (end - e.timestamp).total_seconds() / (horizon_hours * 3600.0)
        contribution = clamp(e.importance * (0.4 + 0.6 * remaining) * (0.4 + 0.6 * (1.0 - clamp(e.priced_in))))
        if contribution > risk:
            risk = contribution
            notes.append(f"{e.event_type} at {e.timestamp:%H:%M} UTC dominates event risk ({contribution:.2f})")
    return risk, notes
