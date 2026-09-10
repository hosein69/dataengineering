"""Probability calibration.

A model that says 60% must be right 60% of the time. ORION-X v4 emitted
`scenario.continuation = 0.4666` with four decimal places of precision and no
mechanism anywhere that could have made that number correspond to a frequency.

Murphy (1973), "A New Vector Partition of the Probability Score", *Journal of
Applied Meteorology* 12(4), decomposes the Brier score into

    Brier = reliability - resolution + uncertainty

where reliability is calibration error (lower is better), resolution is the
ability to separate outcomes (higher is better), and uncertainty is the
irreducible base rate. Reporting only the Brier score hides which of the two
a model is failing at.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["BrierDecomposition", "brier_decomposition", "reliability_table", "isotonic_fit", "isotonic_apply"]


@dataclass
class BrierDecomposition:
    brier: float
    reliability: float
    resolution: float
    uncertainty: float
    n: int

    def as_dict(self) -> dict[str, float]:
        return self.__dict__.copy()


def brier_decomposition(probabilities: np.ndarray, outcomes: np.ndarray, bins: int = 10) -> BrierDecomposition:
    p = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    y = np.asarray(outcomes, dtype=float)
    n = p.size
    if n == 0:
        return BrierDecomposition(0.0, 0.0, 0.0, 0.0, 0)
    base = float(y.mean())
    brier = float(np.mean((p - y) ** 2))

    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    rel = res = 0.0
    for b in range(bins):
        m = idx == b
        nb = int(m.sum())
        if nb == 0:
            continue
        pb = float(p[m].mean())
        ob = float(y[m].mean())
        rel += nb * (pb - ob) ** 2
        res += nb * (ob - base) ** 2
    return BrierDecomposition(brier, rel / n, res / n, base * (1 - base), n)


def reliability_table(probabilities: np.ndarray, outcomes: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    """Rows of (bin, count, mean forecast, observed frequency)."""
    p = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    y = np.asarray(outcomes, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    rows = []
    for b in range(bins):
        m = idx == b
        if not m.any():
            continue
        rows.append({
            "bin_low": float(edges[b]),
            "bin_high": float(edges[b + 1]),
            "count": int(m.sum()),
            "forecast": float(p[m].mean()),
            "observed": float(y[m].mean()),
        })
    return rows


def isotonic_fit(probabilities: np.ndarray, outcomes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pool-adjacent-violators isotonic regression (Ayer et al. 1955).

    Non-parametric and monotone, so recalibration cannot reorder the model's
    own ranking -- it only corrects the levels. Must be fitted on validation
    folds, never on the data the probabilities are then scored on.
    """
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    order = np.argsort(p)
    x, v = p[order], y[order].astype(float)
    w = np.ones_like(v)
    i = 0
    while i < v.size - 1:
        if v[i] <= v[i + 1]:
            i += 1
            continue
        total_w = w[i] + w[i + 1]
        pooled = (v[i] * w[i] + v[i + 1] * w[i + 1]) / total_w
        v[i] = pooled
        w[i] = total_w
        v = np.delete(v, i + 1)
        w = np.delete(w, i + 1)
        x = np.delete(x, i + 1)
        i = max(i - 1, 0)
    return x, v


def isotonic_apply(knots_x: np.ndarray, knots_y: np.ndarray, probabilities: np.ndarray) -> np.ndarray:
    if knots_x.size == 0:
        return np.asarray(probabilities, dtype=float)
    return np.interp(np.asarray(probabilities, dtype=float), knots_x, knots_y)
