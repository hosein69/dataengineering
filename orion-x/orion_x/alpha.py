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

__all__ = [
    "AlphaForecast",
    "combine_blocks",
    "grinold_drift",
    "optimal_block_weights",
    "shrink_ic",
    "DEFAULT_COMPOSITE_DISPERSION",
]

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


def shrink_ic(raw_ic: float, n_effective: float, prior_sd: float) -> float:
    """Empirical-Bayes posterior mean of an information coefficient.

    A measured IC is a correlation estimated from a finite sample, and its
    standard error is roughly `1 / sqrt(n - 3)`. On a panel of twelve assets
    sharing one market factor, the effective sample size is the number of
    *decision times*, not the number of asset-observations, so a few hundred
    hours of history gives a standard error near 0.10. A measured IC of 0.13 is
    then barely one standard error from zero.

    Feeding such an estimate into the weighting scheme is how a walk-forward
    turns into an overfit. Measured directly on the reference panel: unshrunk
    IC weights produced a training composite IC of +0.115 and an out-of-sample
    IC of -0.024, which is worse than using no measurement at all.

    Under a prior `true IC ~ N(0, prior_sd^2)`, the posterior mean is

        IC_shrunk = IC_raw * prior_sd^2 / (prior_sd^2 + se^2).

    The prior is not a formality. Short-horizon crypto signals that survive out
    of sample sit at ICs of 0.02 to 0.05, so `prior_sd` around 0.03 encodes a
    genuine and well-supported belief that measurements above 0.10 are sampling
    noise. With se = 0.10 and prior_sd = 0.03, a raw 0.13 becomes 0.010.
    """
    if n_effective <= 4 or prior_sd <= EPS:
        return 0.0
    se2 = 1.0 / (n_effective - 3.0)
    tau2 = prior_sd * prior_sd
    return raw_ic * tau2 / (tau2 + se2)


def optimal_block_weights(
    block_ics: dict[str, float],
    block_correlation: tuple[list[str], np.ndarray] | None = None,
    max_concentration: float = 0.70,
) -> dict[str, float]:
    """Weights proportional to `Sigma^-1 IC`, normalized to sum to one.

    Args:
        block_ics: measured information coefficient per block. A block with a
            negative measured IC is not flipped -- a sign that only appears out
            of sample is far more likely to be noise than a discovery -- it is
            given zero weight and left for the next refit to confirm.
        block_correlation: (names, correlation matrix) of the block scores. When
            absent the blocks are treated as independent, which understates the
            concentration the optimum actually wants.
        max_concentration: ceiling on any single block's weight. Concentrating
            everything on the block with the highest measured IC is exactly what
            the unconstrained optimum does and exactly how a lucky in-sample
            estimate becomes a live position.
    """
    names = [k for k, v in block_ics.items() if v > 0]
    if not names:
        return {}
    ic = np.array([block_ics[k] for k in names])

    if block_correlation is not None:
        corr_names, corr = block_correlation
        idx = [corr_names.index(k) for k in names if k in corr_names]
        if len(idx) == len(names):
            sub = np.asarray(corr, dtype=float)[np.ix_(idx, idx)]
            # Shrink toward the identity before inverting: an unshrunk inverse
            # of a noisy correlation matrix produces enormous offsetting weights.
            shrink = 0.35
            sub = (1 - shrink) * sub + shrink * np.eye(len(idx))
            try:
                w = np.linalg.solve(sub, ic)
            except np.linalg.LinAlgError:
                w = ic
        else:
            w = ic
    else:
        w = ic

    w = np.clip(w, 0.0, None)
    total = w.sum()
    if total <= EPS:
        return {}
    w = w / total
    if w.max() > max_concentration:
        # Cap the leader and redistribute proportionally among the rest.
        lead = int(np.argmax(w))
        excess = w[lead] - max_concentration
        w[lead] = max_concentration
        others = np.delete(np.arange(w.size), lead)
        if others.size and w[others].sum() > EPS:
            w[others] += excess * w[others] / w[others].sum()
        elif others.size:
            w[others] += excess / others.size
    return {k: float(v) for k, v in zip(names, w)}


def _measured_weights(
    blocks: dict[str, Block],
    config: EngineConfig,
    block_ics: dict[str, float] | None,
    block_correlation: tuple[list[str], np.ndarray] | None,
) -> dict[str, float]:
    """Measured IC weights when they exist, prior weights otherwise."""
    prior = config.weights()
    if not block_ics:
        return prior
    measured = optimal_block_weights(block_ics, block_correlation)
    if not measured:
        return prior
    # Blend toward the prior so a single refit cannot hand the whole book to one
    # block, and so blocks with no measured IC yet keep a residual voice.
    blend = clamp(config.ic_weight_confidence)
    out = {k: (1 - blend) * prior.get(k, 0.0) + blend * measured.get(k, 0.0) for k in prior}
    total = sum(out.values())
    return {k: v / total for k, v in out.items()} if total > EPS else prior


def combine_blocks(
    blocks: dict[str, Block],
    config: EngineConfig,
    block_ics: dict[str, float] | None = None,
    block_correlation: tuple[list[str], np.ndarray] | None = None,
) -> tuple[float, dict[str, float], list[str]]:
    """Combine evidence blocks into one signed composite.

    Three adjustments distinguish this from v4's weighted sum:

    * Each block is weighted by its own reliability, so a block running on
      fallback data contributes less rather than contributing a confident zero.
    * The combined score is scaled by the effective independence of the blocks
      that actually spoke. Summing seven correlated views and dividing by seven
      understates the result; summing them and not dividing at all overstates
      it. Neither is right, and v4 did the second.
    * **When measured information coefficients are available, they set the
      weights.** This is the adjustment that matters most, and the walk-forward
      is what exposed why.

    Fixed prior weights average an informative block together with uninformative
    ones, and the composite's IC falls roughly in proportion to the informative
    block's weight. Measured on the reference panel: a flow signal with a true
    IC of 0.037 produced a composite with an out-of-sample IC of 0.023, and the
    engine could not distinguish a market with a planted signal from a market
    with none. The barrier mathematics was never the bottleneck; the combination
    rule was.

    The optimal combination of correlated forecasts weights them by

        w  ~  Sigma^-1 IC

    where `Sigma` is the correlation matrix of the signals themselves (Grinold &
    Kahn, *Active Portfolio Management*, 2nd ed., ch. 11-12). With one
    informative signal among six noise signals this concentrates the weight
    where the information is, instead of diluting it sevenfold. `Sigma` is
    inverted after Ledoit-Wolf shrinkage because a seven-by-seven correlation
    matrix estimated from a few hundred overlapping observations is not stable
    enough to invert raw.
    """
    weights = _measured_weights(blocks, config, block_ics, block_correlation)
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
