"""Performance statistics that account for how they were selected.

A Sharpe ratio computed on the best of two hundred configurations is not a
Sharpe ratio, it is the maximum of two hundred draws from a noise distribution.
ORION-X v4 shipped no metrics at all, but its README asked the reader to trust
its weights; this module is what would be needed to earn that trust.

References:
    Bailey & Lopez de Prado (2012), "The Sharpe Ratio Efficient Frontier",
        *Journal of Risk* 15(2) -- the Probabilistic Sharpe Ratio.
    Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio", *Journal of
        Portfolio Management* 40(5) -- correcting for selection under multiple
        testing and non-normal returns.
    Bailey, Borwein, Lopez de Prado & Zhu (2014), "Pseudo-Mathematics and
        Financial Charlatanism", *Notices of the AMS* 61(5) -- the minimum
        backtest length needed before a Sharpe ratio means anything.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

EULER_MASCHERONI = 0.5772156649015329


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Acklam's rational approximation to the inverse normal CDF (|err| < 1.15e-9)."""
    p = min(max(p, 1e-15), 1 - 1e-15)
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


@dataclass
class PerformanceReport:
    n: int
    total_return: float
    mean: float
    stdev: float
    sharpe: float
    sharpe_annual: float
    skew: float
    kurtosis: float
    max_drawdown: float
    hit_rate: float
    profit_factor: float
    psr: float
    deflated_sharpe: float
    min_track_record_years: float
    trials: int

    def as_dict(self) -> dict[str, float]:
        return {k: (v if isinstance(v, (int, float)) else v) for k, v in self.__dict__.items()}


def _moments(r: np.ndarray) -> tuple[float, float, float, float]:
    n = r.size
    mu = float(r.mean())
    sd = float(r.std(ddof=1)) if n > 1 else 0.0
    if sd <= 1e-15 or n < 3:
        return mu, sd, 0.0, 3.0
    z = (r - mu) / sd
    skew = float((z**3).mean())
    kurt = float((z**4).mean())
    return mu, sd, skew, kurt


def probabilistic_sharpe_ratio(returns: np.ndarray, benchmark_sr: float = 0.0) -> float:
    """P(true Sharpe > benchmark), correcting for skew and excess kurtosis."""
    r = np.asarray(returns, dtype=float)
    n = r.size
    if n < 8:
        return 0.5
    mu, sd, skew, kurt = _moments(r)
    if sd <= 1e-15:
        return 0.5
    sr = mu / sd
    denom = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    if denom <= 1e-12:
        return 0.5
    return norm_cdf((sr - benchmark_sr) * math.sqrt(n - 1) / math.sqrt(denom))


def expected_max_sharpe(trials: int, sharpe_variance: float) -> float:
    """Expected maximum Sharpe from `trials` independent noise strategies.

    This is the null that a selected strategy must beat. It grows like
    sqrt(2 log N), which is why testing two hundred variants and reporting the
    best one produces an impressive Sharpe from pure noise.
    """
    if trials <= 1 or sharpe_variance <= 0:
        return 0.0
    g = EULER_MASCHERONI
    return math.sqrt(sharpe_variance) * (
        (1.0 - g) * norm_ppf(1.0 - 1.0 / trials) + g * norm_ppf(1.0 - 1.0 / (trials * math.e))
    )


def deflated_sharpe_ratio(returns: np.ndarray, trials: int, sharpe_variance: float | None = None) -> float:
    """PSR evaluated against the expected maximum Sharpe under selection."""
    r = np.asarray(returns, dtype=float)
    if r.size < 8:
        return 0.5
    if sharpe_variance is None:
        # Under the null of no skill, the sampling variance of an estimated
        # Sharpe over n observations is approximately 1 / (n - 1).
        sharpe_variance = 1.0 / max(r.size - 1, 1)
    return probabilistic_sharpe_ratio(r, expected_max_sharpe(trials, sharpe_variance))


def min_track_record_length(returns: np.ndarray, target_confidence: float = 0.95) -> float:
    """Observations needed before the Sharpe is distinguishable from zero."""
    r = np.asarray(returns, dtype=float)
    if r.size < 8:
        return float("inf")
    mu, sd, skew, kurt = _moments(r)
    if sd <= 1e-15:
        return float("inf")
    sr = mu / sd
    if abs(sr) < 1e-9:
        return float("inf")
    return 1.0 + (1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr) * (norm_ppf(target_confidence) / sr) ** 2


def max_drawdown(returns: np.ndarray) -> float:
    r = np.asarray(returns, dtype=float)
    if r.size == 0:
        return 0.0
    equity = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(equity)
    return float(np.max(1.0 - equity / np.maximum(peak, 1e-12)))


def summarize(returns: np.ndarray, periods_per_year: float, trials: int = 1) -> PerformanceReport:
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return PerformanceReport(0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0.5, 0.5, float("inf"), trials)
    mu, sd, skew, kurt = _moments(r)
    sr = mu / sd if sd > 1e-15 else 0.0
    wins = r[r > 0]
    losses = r[r < 0]
    return PerformanceReport(
        n=int(r.size),
        total_return=float(np.prod(1.0 + r) - 1.0),
        mean=mu,
        stdev=sd,
        sharpe=sr,
        sharpe_annual=sr * math.sqrt(periods_per_year),
        skew=skew,
        kurtosis=kurt,
        max_drawdown=max_drawdown(r),
        hit_rate=float((r > 0).mean()),
        profit_factor=float(wins.sum() / abs(losses.sum())) if losses.size and abs(losses.sum()) > 1e-12 else float("inf"),
        psr=probabilistic_sharpe_ratio(r, 0.0),
        deflated_sharpe=deflated_sharpe_ratio(r, trials),
        min_track_record_years=min_track_record_length(r) / periods_per_year,
        trials=trials,
    )
