"""Confounder removal and lead-lag structure.

ORION-X v4 called itself "causal" in its module docstring and its README. What
it actually did was add up correlated features. The single largest confounder
in crypto -- that essentially every altcoin's one-hour return is mostly its beta
times BTC's one-hour return -- was never removed, so "the asset has strong
momentum and strong flow" was, most of the time, a restatement of "BTC moved".

This module does the minimum that makes a causal claim defensible: it
conditions on the known common cause before measuring anything asset-specific,
and it reports which drivers survive that conditioning.

Nothing here recovers a causal graph from observational data on its own. The
lag-based screen is Granger-style predictive structure (Granger 1969), which is
evidence about information flow, not about intervention. Where the distinction
matters, the signal card says so.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .linalg import ridge_regress
from .mathx import EPS

__all__ = ["FactorModel", "fit_factor_model", "residualize", "partial_correlation", "lead_lag_matrix"]


@dataclass
class FactorModel:
    """Exposures of an asset to common risk factors."""

    betas: dict[str, float] = field(default_factory=dict)
    r_squared: float = 0.0
    idio_vol: float = 0.0
    n_obs: int = 0

    def predict(self, factor_returns: dict[str, float]) -> float:
        return sum(self.betas.get(k, 0.0) * v for k, v in factor_returns.items())


def fit_factor_model(
    asset_returns: np.ndarray,
    factor_returns: dict[str, np.ndarray],
    ridge_alpha: float = 1e-3,
) -> FactorModel:
    """Regress an asset on common factors with ridge regularization.

    The factor set is the caller's choice. The default in `orion_x.engine` is
    the BTC and ETH returns plus an equity-basket return, which is the crypto
    analogue of the three-factor structure documented by Liu, Tsyvinski & Wu
    (2022), "Common Risk Factors in Cryptocurrency", *Journal of Finance* 77(2)
    -- a market factor plus size and momentum. Their factors are constructed
    cross-sectionally at weekly frequency; at the hourly frequency this engine
    operates on, the market factor dominates and is what actually needs
    removing.
    """
    y = np.asarray(asset_returns, dtype=float)
    names = [k for k in factor_returns if np.asarray(factor_returns[k]).size == y.size]
    if y.size < 12 or not names:
        return FactorModel({}, 0.0, float(np.std(y)) if y.size else 0.0, int(y.size))

    x = np.column_stack([np.asarray(factor_returns[k], dtype=float) for k in names])
    xc = x - x.mean(axis=0, keepdims=True)
    yc = y - y.mean()
    beta = ridge_regress(xc, yc, ridge_alpha)

    fitted = xc @ beta
    resid = yc - fitted
    ss_tot = float(np.dot(yc, yc))
    r2 = 1.0 - float(np.dot(resid, resid)) / ss_tot if ss_tot > EPS else 0.0
    return FactorModel(
        betas={n: float(b) for n, b in zip(names, beta)},
        r_squared=float(np.clip(r2, 0.0, 1.0)),
        idio_vol=float(np.std(resid, ddof=1)) if resid.size > 1 else 0.0,
        n_obs=int(y.size),
    )


def residualize(asset_returns: np.ndarray, factor_returns: dict[str, np.ndarray], model: FactorModel) -> np.ndarray:
    """Strip the factor-explained component out of a return series."""
    y = np.asarray(asset_returns, dtype=float)
    if not model.betas:
        return y - y.mean()
    names = [k for k in model.betas if k in factor_returns]
    if not names:
        return y - y.mean()
    x = np.column_stack([np.asarray(factor_returns[k], dtype=float) for k in names])
    xc = x - x.mean(axis=0, keepdims=True)
    beta = np.array([model.betas[k] for k in names])
    return (y - y.mean()) - xc @ beta


def partial_correlation(x: np.ndarray, y: np.ndarray, controls: np.ndarray | None = None) -> float:
    """Correlation of x and y after linearly removing `controls` from both.

    This is the conditional-independence test at the heart of constraint-based
    causal discovery (Spirtes, Glymour & Scheines 2000; Runge et al. 2019,
    *Nature Communications* 10, PCMCI). A driver whose partial correlation with
    forward returns collapses once the market factor is controlled for was never
    an independent driver, and the engine down-weights it accordingly.
    """
    a = np.asarray(x, dtype=float).reshape(-1)
    b = np.asarray(y, dtype=float).reshape(-1)
    if a.size != b.size or a.size < 6:
        return 0.0
    if controls is not None:
        c = np.asarray(controls, dtype=float)
        if c.ndim == 1:
            c = c.reshape(-1, 1)
        if c.shape[0] == a.size and c.shape[1] > 0:
            cc = c - c.mean(axis=0, keepdims=True)
            a = a - cc @ ridge_regress(cc, a - a.mean(), 1e-6) - a.mean()
            b = b - cc @ ridge_regress(cc, b - b.mean(), 1e-6) - b.mean()
    a = a - a.mean()
    b = b - b.mean()
    denom = math.sqrt(float(np.dot(a, a)) * float(np.dot(b, b)))
    if denom <= EPS:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, -1.0, 1.0))


def lead_lag_matrix(series: dict[str, np.ndarray], max_lag: int = 3) -> tuple[list[str], np.ndarray]:
    """Directed lead-lag strengths between series.

    Entry [i, j] is the strongest positive cross-correlation of series i at a
    lag that *precedes* series j, minus the same quantity in the reverse
    direction. A positive entry means i leads j. The result is fed to
    `orion_x.graph` as the edge weights of a directed information-flow graph.

    This is a predictive relation, not proof of causation: a common driver
    observed with different latencies produces exactly this pattern. It is used
    only to discount evidence, never to justify a trade.
    """
    names = [k for k in series if np.asarray(series[k]).size > max_lag + 8]
    n = len(names)
    m = np.zeros((n, n))
    if n < 2:
        return names, m
    length = min(np.asarray(series[k]).size for k in names)
    data = {k: np.asarray(series[k], dtype=float)[-length:] for k in names}
    data = {k: (v - v.mean()) / (v.std(ddof=1) + EPS) for k, v in data.items()}

    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if i == j:
                continue
            best_fwd = max(
                (float(np.dot(data[a][: length - L], data[b][L:])) / (length - L) for L in range(1, max_lag + 1)),
                default=0.0,
            )
            best_bwd = max(
                (float(np.dot(data[b][: length - L], data[a][L:])) / (length - L) for L in range(1, max_lag + 1)),
                default=0.0,
            )
            m[i, j] = best_fwd - best_bwd
    return names, m
