"""Synthetic market with the stylized facts that matter.

This exists because the validation has to be honest about what it can and
cannot establish. Exchange APIs are not reachable from this environment, so
there is no real price history to validate against here. Rather than skip
validation or fake a result, the harness runs on a generator whose statistical
properties are matched to documented crypto market behaviour, in two modes:

* **Null mode** (`alpha_strength=0`). Returns are unpredictable by construction.
  Any strategy that appears profitable here after costs is overfitting, leaking,
  or has a bug. This is the more important of the two tests: it is a test of the
  *harness*, not of the strategy, and almost every published backtest would fail
  it.

* **Planted-alpha mode** (`alpha_strength>0`). A known, deliberately small
  predictive relation is injected between order flow imbalance and the next
  hour's idiosyncratic return, sized to an information coefficient in the 0.03
  to 0.06 range -- the region where real short-horizon microstructure signals
  live. The engine should recover part of it, not all of it, and should recover
  it with roughly the right confidence.

Stylized facts reproduced:
    * Volatility clustering: GARCH(1,1) with persistence ~0.97 (Bollerslev 1986).
    * Fat tails: Student-t innovations with 4 degrees of freedom, which is the
      range repeatedly estimated for crypto (Chu et al. 2017; Gkillas & Katsiampa 2018).
    * Leverage effect: negative shocks raise next-period variance more than
      positive ones (Black 1976; Glosten, Jagannathan & Runkle 1993).
    * A dominant common factor: most altcoin variance is BTC beta.
    * Intraday seasonality in both volume and volatility.
    * Spread inversely related to volume; depth proportional to volume.
    * Funding rates that mean-revert and respond to trailing returns, which is
      what makes funding a crowding measure rather than a price measure.

To validate against real data instead, feed the same `MarketPath` structure
from an exchange adapter; nothing downstream knows the difference.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

__all__ = ["MarketPath", "simulate_market"]


@dataclass
class MarketPath:
    """A generated history, in the shape the engine's adapters produce."""

    timestamps: list[datetime]
    btc_price: np.ndarray
    btc_return: np.ndarray
    eth_price: np.ndarray
    eth_return: np.ndarray
    assets: dict[str, dict[str, np.ndarray]] = field(default_factory=dict)
    truth: dict[str, float] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.timestamps)


def _garch_t_path(n: int, rng: np.random.Generator, omega: float, alpha: float, beta: float,
                  leverage: float, df: float, ito_correct: bool = True) -> np.ndarray:
    """GJR-GARCH(1,1) with Student-t innovations, returned as log returns.

    With `ito_correct`, the conditional variance halved is subtracted from each
    log return so that the *price* is a martingale in arithmetic terms:
    E[P_{t+1} / P_t] = 1. Without it, a driftless log return implies an
    arithmetic drift of sigma^2 / 2 per period -- the Ito/Jensen term -- which a
    barrier strategy books as free profit. On this generator's volatilities that
    artefact is worth tens of basis points per trade, which is large enough to
    make a null market look like a tradeable one and to invalidate the whole
    point of testing against it.
    """
    var = np.empty(n)
    r = np.empty(n)
    long_run = omega / max(1.0 - alpha - beta - leverage / 2.0, 1e-6)
    var[0] = long_run
    scale = math.sqrt((df - 2.0) / df)  # unit-variance t
    for i in range(n):
        z = rng.standard_t(df) * scale
        r[i] = math.sqrt(var[i]) * z - (var[i] / 2.0 if ito_correct else 0.0)
        if i + 1 < n:
            asym = leverage if r[i] < 0 else 0.0
            var[i + 1] = omega + (alpha + asym) * r[i] ** 2 + beta * var[i]
    return r


def _seasonal_profile(strength: float = 0.35) -> np.ndarray:
    """Volume/volatility multiplier by UTC hour.

    Two humps at the European and US session opens, a trough through the
    Asian night. The engine must *estimate* this from data rather than assume
    it, so it is deliberately not the profile v4 hard-coded.
    """
    hours = np.arange(24)
    hump = np.exp(-0.5 * ((hours - 8) / 2.6) ** 2) + 1.25 * np.exp(-0.5 * ((hours - 14.5) / 2.8) ** 2)
    hump += 0.55 * np.exp(-0.5 * ((hours - 1.5) / 2.2) ** 2)
    hump = hump / hump.mean()
    return 1.0 + strength * (hump - 1.0)


def simulate_market(
    n_hours: int = 4400,
    n_assets: int = 14,
    seed: int = 20260910,
    alpha_strength: float = 0.0,
    start: datetime | None = None,
) -> MarketPath:
    """Generate a full market history.

    Args:
        n_hours: length of the history (4400h ~ six months of hourly bars).
        n_assets: number of tradeable alt assets.
        alpha_strength: 0 for a null market; ~1.0 injects an OFI -> next-hour
            idiosyncratic return relation with an information coefficient near
            0.05.
    """
    rng = np.random.default_rng(seed)
    start = start or datetime(2026, 3, 1, tzinfo=timezone.utc)
    timestamps = [start + timedelta(hours=i) for i in range(n_hours)]
    hour_of_day = np.array([t.hour for t in timestamps])
    season = _seasonal_profile()[hour_of_day]

    # --- market factor -----------------------------------------------------
    btc_r = _garch_t_path(n_hours, rng, omega=2.2e-7, alpha=0.055, beta=0.925, leverage=0.03, df=4.0)
    btc_r *= season ** 0.5
    btc_price = 68000.0 * np.exp(np.cumsum(btc_r))

    eth_specific = _garch_t_path(n_hours, rng, omega=1.6e-7, alpha=0.05, beta=0.93, leverage=0.03, df=4.5)
    eth_r = 1.12 * btc_r + 0.55 * eth_specific
    eth_price = 2900.0 * np.exp(np.cumsum(eth_r))

    assets: dict[str, dict[str, np.ndarray]] = {}
    for k in range(n_assets):
        sym = f"SIM{k:02d}"
        # 24h dollar volume, log-uniform across the real range: a major perp
        # turns over billions a day while a small cap turns over single-digit
        # millions, and cost per trade differs by an order of magnitude across
        # that range. Sampling uniformly in levels, as an earlier version did,
        # produces a universe of uniformly illiquid names in which nothing can
        # clear a cost hurdle and the test says nothing.
        base_volume = float(np.exp(rng.uniform(math.log(1.2e7), math.log(4.0e9))))
        hourly_vol_base = base_volume / 24.0

        beta = float(rng.uniform(0.7, 1.9))
        # Larger names are less volatile: idiosyncratic scale falls with size,
        # which is the crypto counterpart of the equity size-volatility relation
        # and is what makes the liquid end of the universe tradeable at all.
        size_rank = (math.log(base_volume) - math.log(1.2e7)) / (math.log(4.0e9) - math.log(1.2e7))
        idio_scale = float(rng.uniform(0.7, 1.9)) * (1.35 - 0.7 * size_rank)
        idio = _garch_t_path(n_hours, rng, omega=6e-7, alpha=0.06, beta=0.915, leverage=0.04, df=4.0) * idio_scale
        idio *= season ** 0.5

        # Order flow. The mechanical part is contemporaneous with the return;
        # the planted part leads it by one hour.
        planted = rng.standard_normal(n_hours)
        ofi_noise = rng.standard_normal(n_hours)

        if alpha_strength > 0:
            lead = np.empty(n_hours)
            lead[0] = 0.0
            lead[1:] = planted[:-1]
            idio = idio + alpha_strength * 0.055 * lead * np.std(idio)
        ofi = 0.62 * planted + 0.78 * ofi_noise

        r = beta * btc_r + idio
        price = float(rng.uniform(0.4, 1800.0)) * np.exp(np.cumsum(r))

        # Volume responds to |return| and to the session profile.
        vol_shock = np.exp(0.9 * np.abs(r) / max(np.std(r), 1e-9) * 0.35 + rng.standard_normal(n_hours) * 0.28)
        hourly_volume = hourly_vol_base * season * vol_shock

        depth = hourly_volume * rng.uniform(0.06, 0.22)
        spread_bps = np.clip(2.5 * (hourly_vol_base / np.maximum(hourly_volume, 1.0)) ** 0.45 * rng.uniform(0.8, 3.5), 0.8, 90.0)

        # Funding: mean-reverting, pushed by trailing 24h return (crowding).
        # Causal trailing mean. `mode="same"` centres the window and would let
        # funding at time i depend on returns after i, which is exactly the
        # lookahead this harness exists to catch -- in the generator it would
        # hand the engine a free forecast and invalidate the whole exercise.
        trailing = np.convolve(r, np.ones(24) / 24.0, mode="full")[: r.size]
        funding = np.zeros(n_hours)
        for i in range(1, n_hours):
            funding[i] = 0.965 * funding[i - 1] + 0.02 * np.tanh(trailing[i] / 0.004) * 0.0004 + rng.standard_normal() * 3e-5
        funding = np.clip(funding, -0.0035, 0.0035)

        oi = np.maximum(np.cumsum(rng.standard_normal(n_hours) * 0.012 + 0.35 * r) + 3.0, 0.4)

        taker_buy = hourly_volume * (0.5 + 0.18 * np.tanh(ofi / 1.6))
        taker_sell = hourly_volume - taker_buy

        assets[sym] = {
            "price": price,
            "log_return": r,
            "idio_return": idio,
            "beta": np.full(n_hours, beta),
            "hourly_volume": hourly_volume,
            "depth": depth,
            "spread_bps": spread_bps,
            "funding": funding,
            "oi": oi,
            "ofi": ofi,
            "taker_buy": taker_buy,
            "taker_sell": taker_sell,
            "market_cap": np.full(n_hours, base_volume * rng.uniform(20.0, 140.0)),
        }

    truth = {"alpha_strength": alpha_strength, "n_hours": float(n_hours), "n_assets": float(n_assets)}
    if alpha_strength > 0:
        # Report the realized IC of the planted relation so the walk-forward
        # result can be compared to the ceiling rather than to zero.
        ics = []
        for sym, d in assets.items():
            x, y = d["ofi"][:-1], d["idio_return"][1:]
            ics.append(float(np.corrcoef(x, y)[0, 1]))
        truth["planted_ic"] = float(np.mean(ics))
    return MarketPath(timestamps, btc_price, btc_r, eth_price, eth_r, assets, truth)
