"""Covariance estimation and multi-dimensional structure.

Three separate jobs live here, all of them things ORION-X v4 claimed in its
README and never did:

1. Estimating a correlation matrix that is usable at all. With ~200 assets and
   a few hundred hourly observations the sample correlation matrix is mostly
   noise; its smallest eigenvalues are near zero and its inverse is garbage.
2. Separating signal from noise in that matrix using random matrix theory.
3. Turning the eigenstructure into a single honest number: how many genuinely
   independent bets a portfolio or an evidence set actually contains.

Point 3 is what replaces v4's `independence_score`, which counted how many of
three feature groups were non-zero and therefore returned 1.0 on essentially
every real input.
"""
from __future__ import annotations

import math

import numpy as np

from .mathx import EPS

__all__ = [
    "ledoit_wolf_shrinkage",
    "marchenko_pastur_denoise",
    "effective_rank",
    "effective_number_of_bets",
    "pca",
    "ridge_regress",
    "orthogonalize",
]


def ledoit_wolf_shrinkage(returns: np.ndarray) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf shrinkage of a covariance matrix toward constant correlation.

    Ledoit & Wolf (2004), "Honey, I Shrunk the Sample Covariance Matrix",
    *Journal of Portfolio Management*. Returns (covariance, shrinkage intensity).
    """
    x = np.asarray(returns, dtype=float)
    t, n = x.shape
    if t < 3 or n < 2:
        return np.cov(x, rowvar=False, ddof=1) if t > 1 else np.eye(n), 1.0
    xc = x - x.mean(axis=0, keepdims=True)
    sample = (xc.T @ xc) / t

    var = np.diag(sample)
    sd = np.sqrt(np.maximum(var, EPS))
    corr = sample / np.outer(sd, sd)
    off = corr[~np.eye(n, dtype=bool)]
    rbar = float(off.mean()) if off.size else 0.0
    target = rbar * np.outer(sd, sd)
    np.fill_diagonal(target, var)

    # pi: asymptotic variance of the sample covariance entries
    y = xc**2
    phi_mat = (y.T @ y) / t - sample**2
    phi = float(phi_mat.sum())

    # rho: covariance between sample entries and the shrinkage target
    term = ((xc**3).T @ xc) / t - var * sample
    rho = float(np.diag(phi_mat).sum())
    rho += rbar * float((np.outer(1.0 / sd, sd) * term)[~np.eye(n, dtype=bool)].sum())

    gamma = float(((target - sample) ** 2).sum())
    kappa = (phi - rho) / gamma if gamma > EPS else 0.0
    shrink = max(0.0, min(1.0, kappa / t))
    return shrink * target + (1.0 - shrink) * sample, shrink


def marchenko_pastur_denoise(corr: np.ndarray, t_obs: int) -> tuple[np.ndarray, float]:
    """Clip eigenvalues that fall inside the Marchenko-Pastur noise band.

    Marchenko & Pastur (1967); applied to finance by Laloux, Cizeau, Bouchaud &
    Potters (1999), *Physical Review Letters* 83, and Plerou et al. (1999). For
    a pure-noise correlation matrix with q = n/T, eigenvalues lie in
    [(1 - sqrt(q))^2, (1 + sqrt(q))^2]. Anything inside that band carries no
    information and is replaced by their common average, which preserves the
    trace and leaves the matrix positive definite.

    Returns (denoised correlation, fraction of variance in signal eigenvalues).
    """
    c = np.asarray(corr, dtype=float)
    n = c.shape[0]
    if n < 2 or t_obs < 2:
        return c, 1.0
    q = n / float(t_obs)
    lam_max = (1.0 + math.sqrt(q)) ** 2
    vals, vecs = np.linalg.eigh(c)
    noise = vals < lam_max
    if noise.all():
        # Every mode is indistinguishable from noise: fall back to identity.
        return np.eye(n), 0.0
    if noise.any():
        avg = vals[noise].mean()
        vals = np.where(noise, avg, vals)
    denoised = vecs @ np.diag(vals) @ vecs.T
    d = np.sqrt(np.maximum(np.diag(denoised), EPS))
    denoised = denoised / np.outer(d, d)
    signal_share = float(vals[~noise].sum() / max(vals.sum(), EPS))
    return denoised, signal_share


def pca(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Eigen-decomposition sorted by descending eigenvalue."""
    vals, vecs = np.linalg.eigh(np.asarray(matrix, dtype=float))
    order = np.argsort(vals)[::-1]
    return vals[order], vecs[:, order]


def effective_rank(matrix: np.ndarray) -> float:
    """Roy & Vetterli (2007) effective rank: exp of the spectral entropy.

    A market whose correlation matrix has effective rank 1.2 out of 40 assets
    is a single factor wearing forty tickers; every "diversified" basket in it
    is one bet. This is reported on the signal card as a regime-fragility
    measure.
    """
    vals, _ = pca(matrix)
    vals = np.clip(vals, 0.0, None)
    s = vals.sum()
    if s <= EPS:
        return 0.0
    p = vals / s
    p = p[p > EPS]
    return float(math.exp(-(p * np.log(p)).sum()))


def effective_number_of_bets(weights: np.ndarray, cov: np.ndarray) -> float:
    """Meucci's effective number of bets on the principal-component basis.

    Meucci (2009), "Managing Diversification", *Risk* 22(5). Portfolio risk is
    decomposed onto the eigenvectors of the covariance matrix; the diversifica-
    tion distribution p_k is each mode's share of total variance, and the
    effective number of bets is exp(H(p)). It equals N only for genuinely
    uncorrelated equal-risk positions and collapses toward 1 as the positions
    load on one common factor.

    This is the quantity v4's `independence_score` was gesturing at.
    """
    w = np.asarray(weights, dtype=float).reshape(-1)
    s = np.asarray(cov, dtype=float)
    if w.size == 0 or s.shape[0] != w.size:
        return 1.0
    vals, vecs = pca(s)
    vals = np.clip(vals, 0.0, None)
    w_tilde = vecs.T @ w
    contrib = (w_tilde**2) * vals
    total = contrib.sum()
    if total <= EPS:
        return 1.0
    p = contrib / total
    p = p[p > EPS]
    return float(math.exp(-(p * np.log(p)).sum()))


def ridge_regress(x: np.ndarray, y: np.ndarray, alpha: float = 1e-3) -> np.ndarray:
    """Ridge coefficients (no intercept; centre the inputs beforehand).

    Ridge rather than OLS because factor returns in crypto are strongly
    collinear -- BTC, ETH and a total-market index share most of their variance,
    so the OLS betas are unstable and can flip sign between windows.
    """
    a = np.asarray(x, dtype=float)
    b = np.asarray(y, dtype=float).reshape(-1)
    if a.ndim == 1:
        a = a.reshape(-1, 1)
    if a.shape[0] != b.shape[0] or a.shape[0] == 0:
        return np.zeros(a.shape[1])
    gram = a.T @ a
    # Scale the penalty by the average diagonal of the Gram matrix so that
    # `alpha` is dimensionless. Using alpha * n_obs directly makes the penalty
    # depend on the units of the regressors: with hourly crypto returns
    # (sd ~ 1e-2) it swamps the signal by two orders of magnitude and shrinks
    # every beta to zero.
    scale = float(np.trace(gram)) / max(a.shape[1], 1)
    g = gram + alpha * max(scale, EPS) * np.eye(a.shape[1])
    try:
        return np.linalg.solve(g, a.T @ b)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(g) @ (a.T @ b)


def orthogonalize(blocks: np.ndarray) -> np.ndarray:
    """Symmetric (Lowdin) orthogonalization of correlated evidence blocks.

    Given a T x K matrix of standardized evidence series, returns the K columns
    rotated to be mutually orthogonal while staying as close as possible to the
    originals in the least-squares sense (Lowdin 1950): Z = X S^{-1/2} with
    S the column correlation matrix. Unlike Gram-Schmidt this does not privilege
    whichever block happens to be listed first, which matters because the
    ordering of "flow", "momentum" and "fundamental" is arbitrary.
    """
    x = np.asarray(blocks, dtype=float)
    if x.ndim != 2 or x.shape[1] < 2 or x.shape[0] < 3:
        return x
    xc = x - x.mean(axis=0, keepdims=True)
    sd = xc.std(axis=0, ddof=1)
    sd = np.where(sd > EPS, sd, 1.0)
    xs = xc / sd
    s = np.corrcoef(xs, rowvar=False)
    s = np.nan_to_num(s, nan=0.0)
    np.fill_diagonal(s, 1.0)
    vals, vecs = np.linalg.eigh(s)
    vals = np.clip(vals, 1e-8, None)
    s_inv_sqrt = vecs @ np.diag(vals**-0.5) @ vecs.T
    return xs @ s_inv_sqrt
