"""Turning evidence into a drift.

This is the module that decides how much the engine is allowed to believe.

ORION-X v4 summed eight weighted [0, 1] scores into a 0-100 number and then, in
a completely disconnected step, asserted scenario probabilities from three
hand-written logit equations. Nothing tied the score to a return, so a score of
67 meant nothing that could be checked, and the reported `net_edge_estimate` of
0.0054 on the shipped example was an artefact of the take-profit level rather
than a forecast of anything.

v5 uses Grinold's forecasting rule, which is the standard way to convert an
opinion into a return forecast without inventing magnitude:

    alpha = IC * sigma * z

Grinold (1994), "Alpha is Volatility Times IC Times Score", *Journal of
Portfolio Management* 20(4); Grinold & Kahn, *Active Portfolio Management*, 2nd
ed. ch. 10. `z` is the standardized composite score, `sigma` is the forecast
volatility over the horizon, and `IC` is the information coefficient -- the
realized correlation between the score and subsequent returns.

The discipline this imposes is the point. IC for a short-horizon crypto signal
that survives out of sample is realistically 0.02 to 0.05. At IC = 0.03 and a
7-hour sigma of 3%, a two-sigma score buys a drift forecast of about 18 basis
points. Round-trip costs on a mid-cap perp are 20 to 25 basis points. That
arithmetic -- which v4 never performed -- is why most of these signals should
be, and now are, no-trades.

The fundamental law of active management (Grinold 1989; Clarke, de Silva &
Thorley 2002 with the transfer-coefficient correction) gives the same result
from the other direction: IR = IC * sqrt(breadth) * TC. Breadth here is the
number of genuinely independent bets, which `orion_x.linalg` measures rather
than assumes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .contracts import EngineConfig
from .features import Block
from .mathx import EPS, clamp

__all__ = ["AlphaForecast", "combine_blocks", "grinold_drift", "DEFAULT_COMPOSITE_DISPERSION"]

# Prior for the cross-sectional standard deviation of the composite score,
# measured on the reference panel in `orion_x.backtest.simulate`. A caller with
# a live universe should measure it and pass it in rather than rely on this.
DEFAULT_COMPOSITE_DISPERSION = 0.18


@dataclass
class AlphaForecast:
    composite_z: float
    information_coefficient: float
    drift_per_hour: float
    drift_horizon: float
    breadth: float
    transfer_coefficient: float
    implied_information_ratio: float
    block_contributions: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def combine_blocks(blocks: dict[str, Block], config: EngineConfig) -> tuple[float, dict[str, float], list[str]]:
    """Reliability-weighted, correlation-aware combination of evidence blocks.

    Two adjustments distinguish this from v4's weighted sum:

    * Each block is weighted by its own reliability, so a block running on
      fallback data contributes less rather than contributing a confident zero.
    * The combined score is divided by the square root of the effective number
      of independent blocks rather than by the number of blocks. Summing seven
      correlated views and dividing by seven understates the score; summing them
      and not dividing at all overstates it. Neither is right, and v4 did the
      second.
    """
    weights = config.weights()
    notes: list[str] = []
    contributions: dict[str, float] = {}

    active = {k: b for k, b in blocks.items() if k in weights}
    if not active:
        return 0.0, {}, ["no evidence blocks available"]

    total_w = 0.0
    raw = 0.0
    for name, block in active.items():
        w = weights[name] * block.reliability
        contributions[name] = w * block.score
        raw += w * block.score
        total_w += w
        notes.extend(f"[{name}] {n}" for n in block.notes)

    if total_w <= EPS:
        return 0.0, contributions, notes + ["every evidence block is unreliable"]

    weighted_mean = raw / total_w

    # Effective independence of the blocks that actually spoke. Blocks pointing
    # the same way carry less joint information than their count suggests.
    scores = np.array([b.score for b in active.values()])
    speaking = scores[np.abs(scores) > 0.02]
    if speaking.size >= 2:
        agreement = abs(float(np.mean(np.sign(speaking))))
        # agreement 1.0 = unanimous (highly correlated), 0.0 = evenly split.
        eff_n = speaking.size * (1.0 - 0.55 * agreement)
        boost = math.sqrt(max(eff_n, 1.0)) / math.sqrt(max(speaking.size, 1))
    else:
        boost = 1.0
        agreement = 0.0

    composite = clamp(weighted_mean * (1.0 + 0.6 * (1.0 - boost)), -1.0, 1.0)
    contributions["_agreement"] = agreement
    contributions["_reliability"] = total_w / max(sum(weights[k] for k in active), EPS)
    return composite, contributions, notes


def grinold_drift(
    composite: float,
    sigma_horizon: float,
    horizon_hours: float,
    config: EngineConfig,
    uncertainty: float,
    breadth: float,
    transfer_coefficient: float,
    measured_ic: float | None = None,
    composite_dispersion: float | None = None,
) -> AlphaForecast:
    """Convert a composite score into a log-return drift over the horizon.

    Args:
        composite: signed composite evidence score in [-1, 1].
        sigma_horizon: forecast log-return volatility over the whole horizon.
        horizon_hours: T.
        uncertainty: [0, 1]; shrinks the IC toward zero.
        breadth: effective number of independent bets available now.
        transfer_coefficient: [0, 1]; how much of the forecast survives
            constraints and costs (Clarke, de Silva & Thorley 2002).
        measured_ic: walk-forward-measured IC, when one exists. Overrides the
            assumed IC, still bounded by `config.max_abs_ic`.
        composite_dispersion: standard deviation of the composite across the
            universe (or across its own recent history). Required for the score
            to be a z-score at all; see below.
    """
    notes: list[str] = []

    # `z` in Grinold's rule is a *standardized* score -- zero mean and unit
    # variance across the universe -- not a raw opinion on some arbitrary
    # scale. The composite produced by `combine_blocks` lives in [-1, 1] but its
    # actual cross-sectional dispersion is around 0.15 to 0.2, so feeding it in
    # raw understates every forecast by roughly a factor of five. That is the
    # same class of dimensional error as v4's `tanh(funding / 0.001)`: a
    # quantity used at a scale it does not have.
    dispersion = composite_dispersion if composite_dispersion and composite_dispersion > 1e-4 else DEFAULT_COMPOSITE_DISPERSION
    if composite_dispersion is None:
        notes.append(
            f"no measured composite dispersion: standardizing with the prior {DEFAULT_COMPOSITE_DISPERSION:.2f}"
        )
    z = clamp(composite / dispersion, -3.0, 3.0)
    if abs(composite / dispersion) > 3.0:
        notes.append("composite score exceeds 3 standard deviations: clipped before forecasting")

    ic = config.assumed_ic if measured_ic is None else measured_ic
    if measured_ic is not None:
        notes.append(f"using walk-forward measured IC = {measured_ic:+.4f}")
    else:
        notes.append(f"no measured IC available: using the assumed prior IC = {ic:.4f}")

    ic = clamp(ic, -config.max_abs_ic, config.max_abs_ic)
    # Uncertainty shrinks the IC, not the score: an uncertain view is not a
    # smaller view, it is a less reliable one, and only the IC represents
    # reliability in this formula.
    ic_eff = ic * (1.0 - config.ic_shrink_on_uncertainty * clamp(uncertainty))

    drift_horizon = ic_eff * sigma_horizon * z
    drift_per_hour = drift_horizon / max(horizon_hours, EPS)

    ir = ic_eff * math.sqrt(max(breadth, 1.0)) * clamp(transfer_coefficient)
    if abs(ir) > 0.5:
        notes.append("implied information ratio above 0.5 per horizon is implausible: capped")
        ir = math.copysign(0.5, ir)

    return AlphaForecast(
        composite_z=z,
        information_coefficient=ic_eff,
        drift_per_hour=drift_per_hour,
        drift_horizon=drift_horizon,
        breadth=breadth,
        transfer_coefficient=transfer_coefficient,
        implied_information_ratio=ir,
        notes=notes,
    )
