"""Numerical primitives shared by the whole engine.

Everything here is deliberately small, pure and side-effect free so it can be
unit-tested in isolation and mirrored one-to-one by the Rust core.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np

EPS = 1e-12


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if abs(b) > EPS else default


def tanh_norm(x: float, scale: float) -> float:
    """Map an unbounded signed quantity into (-1, 1) at a stated scale.

    `scale` is the value of `x` that maps to tanh(1) ~ 0.76, so it must always
    be an economically meaningful unit (a typical move, one standard
    deviation, ...) rather than a tuning knob.
    """
    return math.tanh(safe_div(x, scale, 0.0))


def logit(p: float) -> float:
    p = clamp(p, 1e-9, 1 - 1e-9)
    return math.log(p / (1 - p))


def expit(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-clamp(x, -60.0, 60.0)))


def softmax(xs: Sequence[float]) -> list[float]:
    m = max(xs)
    e = [math.exp(clamp(x - m, -60.0, 60.0)) for x in xs]
    s = sum(e) or 1.0
    return [v / s for v in e]


def ewma(values: Sequence[float], halflife: float) -> float:
    """Exponentially weighted mean, most recent value last."""
    if len(values) == 0:
        return 0.0
    lam = 0.5 ** (1.0 / max(halflife, EPS))
    w = lam ** np.arange(len(values) - 1, -1, -1, dtype=float)
    w /= w.sum()
    return float(np.dot(w, np.asarray(values, dtype=float)))


def ewma_vol(returns: Sequence[float], halflife: float) -> float:
    """RiskMetrics-style EWMA volatility of a return series (per period)."""
    r = np.asarray(returns, dtype=float)
    if r.size == 0:
        return 0.0
    lam = 0.5 ** (1.0 / max(halflife, EPS))
    w = lam ** np.arange(r.size - 1, -1, -1, dtype=float)
    w /= w.sum()
    mu = float(np.dot(w, r))
    return float(math.sqrt(max(np.dot(w, (r - mu) ** 2), 0.0)))


def robust_z(x: float, sample: Sequence[float]) -> float:
    """Median/MAD z-score. Fat tails make the plain mean/std z-score unusable
    on crypto features; MAD is the standard robust substitute (Huber 1981)."""
    s = np.asarray(sample, dtype=float)
    if s.size < 4:
        return 0.0
    med = float(np.median(s))
    mad = float(np.median(np.abs(s - med)))
    scale = 1.4826 * mad  # consistency constant for the normal distribution
    if scale <= EPS:
        std = float(np.std(s))
        return safe_div(x - med, std, 0.0)
    return (x - med) / scale


def rank_pct(x: float, sample: Sequence[float]) -> float:
    """Empirical percentile of `x` inside `sample`, in [0, 1]."""
    s = np.asarray(sample, dtype=float)
    if s.size == 0:
        return 0.5
    return float((s <= x).mean())


def winsorize(values: Iterable[float], lo_q: float = 0.01, hi_q: float = 0.99) -> np.ndarray:
    v = np.asarray(list(values), dtype=float)
    if v.size == 0:
        return v
    lo, hi = np.quantile(v, [lo_q, hi_q])
    return np.clip(v, lo, hi)


def entropy(p: Sequence[float]) -> float:
    """Shannon entropy in nats, ignoring zero-mass atoms."""
    a = np.asarray(p, dtype=float)
    a = a[a > EPS]
    if a.size == 0:
        return 0.0
    a = a / a.sum()
    return float(-(a * np.log(a)).sum())


def finite_difference_gradient(fn, x: dict[str, float], step_frac: float = 1e-4) -> dict[str, float]:
    """Central-difference gradient of a scalar function of named inputs.

    Used by `orion_x.engine` to publish d(score)/d(feature) with every signal so
    that a reviewer can see which inputs the decision actually rests on, rather
    than trusting the declared weights.
    """
    grad: dict[str, float] = {}
    for k, v in x.items():
        h = max(abs(v) * step_frac, 1e-6)
        up = dict(x)
        dn = dict(x)
        up[k] = v + h
        dn[k] = v - h
        grad[k] = (fn(up) - fn(dn)) / (2 * h)
    return grad
