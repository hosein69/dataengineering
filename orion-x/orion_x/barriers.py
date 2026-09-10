"""Triple-barrier first-passage probabilities.

ORION-X v4 assigned scenario probabilities with three hand-tuned logit
equations. Those constants were never estimated from anything, they were not
dimensionally consistent (a funding rate entered a logit linearly and
unbounded), and they had no relationship to the take-profit and stop-loss
levels the same engine emitted a few lines later. A signal could report
P(continuation) = 0.47 while its stop sat 0.4 sigma away, which is nonsense:
at that distance the stop is hit first with high probability whatever the
evidence says.

v5 replaces them with the actual physics of the trade. Log price is modelled as
arithmetic Brownian motion with drift,

    dX_t = mu dt + sigma dW_t,     X_0 = 0,

absorbed at an upper barrier u = ln(TP/entry) > 0 and a lower barrier
-l = ln(SL/entry) < 0, over a finite horizon T (the third barrier). All the
evidence in the engine now enters through exactly one channel: the drift mu.
Barrier geometry and volatility do the rest.

Shift to y = X + l on [0, L] with L = u + l, y_0 = l, absorbing at both ends.
The transition density of absorbed Brownian motion on an interval has the
classical eigenfunction expansion (Kolmogorov backward equation; see e.g.
Borodin & Salminen, *Handbook of Brownian Motion*, 2nd ed., formula 1.1.15.8,
or Cox & Miller 1965 sec. 5.7):

    p(y, t | y0) = (2/L) exp( mu (y - y0) / sigma^2 - mu^2 t / (2 sigma^2) )
                   * sum_n sin(n pi y0 / L) sin(n pi y / L) exp(-lambda_n t)

with lambda_n = n^2 pi^2 sigma^2 / (2 L^2). The absorption rate at a boundary
is the probability current, J = mu p - (sigma^2/2) dp/dy, which at an absorbing
boundary reduces to the diffusive term alone because p vanishes there.
Integrating that flux to T gives closed-form barrier probabilities:

    P(hit upper first, by T) = (sigma^2 pi / L^2) e^{ mu (L - y0)/sigma^2 }
        * sum_n n (-1)^{n+1} sin(n pi y0 / L) (1 - e^{-beta_n T}) / beta_n

    P(hit lower first, by T) = (sigma^2 pi / L^2) e^{ -mu y0 / sigma^2 }
        * sum_n n sin(n pi y0 / L) (1 - e^{-beta_n T}) / beta_n

    beta_n = lambda_n + mu^2 / (2 sigma^2)

and P(timeout) = 1 - P(upper) - P(lower). In the driftless, infinite-horizon
limit these collapse to the gambler's-ruin result y0/L and 1 - y0/L, which
`tests/test_barriers.py` checks directly.

Convergence is governed by sigma^2 T / L^2. When the horizon is short relative
to the barrier distance the series needs many terms, so `barrier_probs` picks
the term count adaptively and falls back to a Brownian-bridge Monte Carlo
estimate if the truncated series fails its own consistency checks.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .mathx import EPS, clamp

__all__ = ["BarrierProbs", "barrier_probs", "barrier_probs_mc", "implied_drift_for_edge"]


@dataclass(frozen=True)
class BarrierProbs:
    """Probabilities of the three mutually exclusive triple-barrier outcomes."""

    take_profit: float
    stop_loss: float
    timeout: float
    method: str = "series"
    residual: float = 0.0

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.take_profit, self.stop_loss, self.timeout)



def _ruin_probability(mu: float, sigma: float, L: float, y0: float) -> float:
    """P(hit L before 0) for drifted Brownian motion started at y0 in [0, L].

    Uses the scale function s(y) = exp(-2 mu y / sigma^2); the driftless limit
    y0 / L is taken explicitly to avoid a 0/0 evaluation.
    """
    a = 2.0 * mu / (sigma * sigma)
    if abs(a * L) < 1e-9:
        return y0 / L
    # expm1 keeps full precision when a*L is small but not negligible.
    return float(np.expm1(-a * y0) / np.expm1(-a * L))


def _series_terms(sigma2_t_over_l2: float) -> int:
    """Term count that drives the truncation error below ~1e-10.

    The n-th term decays like exp(-n^2 pi^2 sigma^2 T / (2 L^2)); solving for a
    1e-10 tail and adding a safety margin gives the expression below.
    """
    x = max(sigma2_t_over_l2, 1e-9)
    n = math.sqrt(2.0 * 23.0 / (math.pi**2 * x)) + 8.0
    return int(min(max(math.ceil(n), 16), 20000))


def barrier_probs(
    mu: float,
    sigma: float,
    horizon: float,
    up_log: float,
    down_log: float,
    force_mc: bool = False,
    mc_paths: int = 40000,
    seed: int = 0,
) -> BarrierProbs:
    """Exact triple-barrier probabilities for arithmetic BM with drift.

    Args:
        mu: drift of *log* price per unit time (same time unit as `horizon`).
        sigma: diffusion of log price per sqrt(unit time), strictly positive.
        horizon: time limit T > 0, the third barrier.
        up_log: ln(take_profit / entry), must be > 0.
        down_log: ln(entry / stop_loss), must be > 0 (a positive distance).

    Returns:
        BarrierProbs summing to 1.
    """
    if sigma <= EPS or horizon <= EPS:
        # Degenerate diffusion: the outcome is decided by drift alone.
        drift_move = mu * max(horizon, 0.0)
        if drift_move >= up_log:
            return BarrierProbs(1.0, 0.0, 0.0, "degenerate")
        if drift_move <= -down_log:
            return BarrierProbs(0.0, 1.0, 0.0, "degenerate")
        return BarrierProbs(0.0, 0.0, 1.0, "degenerate")
    if up_log <= EPS or down_log <= EPS:
        # A barrier at or through the entry price is hit immediately.
        if up_log <= EPS and down_log <= EPS:
            return BarrierProbs(0.5, 0.5, 0.0, "degenerate")
        return BarrierProbs(1.0, 0.0, 0.0, "degenerate") if up_log <= EPS else BarrierProbs(0.0, 1.0, 0.0, "degenerate")

    L = up_log + down_log
    y0 = down_log
    s2 = sigma * sigma

    if not force_mc:
        # The raw eigenfunction series converges only like O(1/n) because the
        # (1 - e^{-beta_n T}) / beta_n factor saturates at 1/beta_n ~ 1/n^2
        # against an O(n) numerator. Splitting it into the infinite-horizon
        # limit plus an exponentially damped correction fixes that:
        #
        #   (1 - e^{-beta_n T}) / beta_n  =  1 / beta_n  -  e^{-beta_n T} / beta_n
        #
        # The first half sums in closed form to the classical drifted
        # gambler's-ruin probability via the scale function
        # s(y) = exp(-2 mu y / sigma^2) (Karlin & Taylor 1981, ch. 15):
        #
        #   P(hit upper before lower) = (1 - e^{-2 mu y0 / sigma^2})
        #                             / (1 - e^{-2 mu L  / sigma^2})
        #
        # and the second half now carries an e^{-beta_n T} factor, so it decays
        # like exp(-n^2), which is what `_series_terms` is calibrated for.
        p_up_inf = _ruin_probability(mu, sigma, L, y0)
        p_dn_inf = 1.0 - p_up_inf

        n_max = _series_terms(s2 * horizon / (L * L))
        n = np.arange(1, n_max + 1, dtype=float)
        lam = (n * n) * (math.pi**2) * s2 / (2.0 * L * L)
        beta = lam + mu * mu / (2.0 * s2)
        sin0 = np.sin(n * math.pi * y0 / L)
        damped = np.exp(-np.clip(beta * horizon, 0.0, 700.0)) / beta
        pref = s2 * math.pi / (L * L)
        alt = np.where(n.astype(int) % 2 == 1, 1.0, -1.0)

        e_up_arg = mu * (L - y0) / s2
        e_dn_arg = -mu * y0 / s2
        if abs(e_up_arg) > 500.0 or abs(e_dn_arg) > 500.0:
            return barrier_probs_mc(mu, sigma, horizon, up_log, down_log, mc_paths, seed)

        corr_up = pref * math.exp(e_up_arg) * float(np.sum(n * alt * sin0 * damped))
        corr_dn = pref * math.exp(e_dn_arg) * float(np.sum(n * sin0 * damped))

        p_up = p_up_inf - corr_up
        p_dn = p_dn_inf - corr_dn

        ok = (
            math.isfinite(p_up)
            and math.isfinite(p_dn)
            and p_up > -1e-7
            and p_dn > -1e-7
            and p_up + p_dn < 1.0 + 1e-7
        )
        if ok:
            p_up = clamp(p_up, 0.0, 1.0)
            p_dn = clamp(p_dn, 0.0, 1.0)
            total = p_up + p_dn
            if total > 1.0:
                p_up, p_dn = p_up / total, p_dn / total
            residual = float(n_max)
            return BarrierProbs(p_up, p_dn, max(0.0, 1.0 - p_up - p_dn), "series", residual)

    return barrier_probs_mc(mu, sigma, horizon, up_log, down_log, mc_paths, seed)


def barrier_probs_mc(
    mu: float,
    sigma: float,
    horizon: float,
    up_log: float,
    down_log: float,
    paths: int = 40000,
    seed: int = 0,
    steps: int = 128,
) -> BarrierProbs:
    """Monte Carlo cross-check with a Brownian-bridge continuity correction.

    Discretely monitoring a continuous barrier systematically under-counts
    crossings. The bridge correction removes that bias exactly for a single
    barrier (Baldi/Beaglehole; see Glasserman, *Monte Carlo Methods in
    Financial Engineering*, sec. 6.4): between two observed points y_a, y_b the
    probability that the path touched a level b in between is
    exp(-2 (b - y_a)(b - y_b) / (sigma^2 dt)).

    This is the independent implementation the series solution is validated
    against in the test suite; it is not used on the hot path.
    """
    rng = np.random.default_rng(seed)
    dt = horizon / steps
    sd = sigma * math.sqrt(dt)
    L_up, L_dn = up_log, -down_log
    s2dt = sigma * sigma * dt

    y = np.zeros(paths)
    alive = np.ones(paths, dtype=bool)
    hit_up = np.zeros(paths, dtype=bool)
    hit_dn = np.zeros(paths, dtype=bool)

    for _ in range(steps):
        idx = np.flatnonzero(alive)
        if idx.size == 0:
            break
        prev = y[idx]
        nxt = prev + mu * dt + sd * rng.standard_normal(idx.size)

        crossed_up = nxt >= L_up
        crossed_dn = nxt <= L_dn
        # Continuity correction for paths that ended inside the corridor.
        inside = ~(crossed_up | crossed_dn)
        u = rng.random(idx.size)
        p_bridge_up = np.exp(-2.0 * np.maximum(L_up - prev, 0.0) * np.maximum(L_up - nxt, 0.0) / s2dt)
        p_bridge_dn = np.exp(-2.0 * np.maximum(prev - L_dn, 0.0) * np.maximum(nxt - L_dn, 0.0) / s2dt)
        touched_up = inside & (u < p_bridge_up)
        touched_dn = inside & (~touched_up) & (u < p_bridge_up + p_bridge_dn)

        up_now = crossed_up | touched_up
        dn_now = (crossed_dn | touched_dn) & ~up_now
        # A step that breaches both barriers is resolved by which is nearer.
        both = crossed_up & crossed_dn
        if both.any():
            nearer_up = (L_up - prev[both]) <= (prev[both] - L_dn)
            up_now[both] = nearer_up
            dn_now[both] = ~nearer_up

        hit_up[idx[up_now]] = True
        hit_dn[idx[dn_now]] = True
        alive[idx[up_now | dn_now]] = False
        y[idx] = nxt

    p_up = float(hit_up.mean())
    p_dn = float(hit_dn.mean())
    se = math.sqrt(max(p_up * (1 - p_up), EPS) / paths)
    return BarrierProbs(p_up, p_dn, max(0.0, 1.0 - p_up - p_dn), "monte-carlo", se)


def implied_drift_for_edge(
    sigma: float,
    horizon: float,
    up_log: float,
    down_log: float,
    target_edge: float,
    tol: float = 1e-7,
) -> float:
    """Drift that makes the trade's expected log return equal `target_edge`.

    Reported on every signal card as a falsifiable break-even statement: the
    trade only pays if the true drift exceeds this number, which lets a
    reviewer judge the thesis in units they can argue about.
    """
    def edge(mu: float) -> float:
        p = barrier_probs(mu, sigma, horizon, up_log, down_log)
        return p.take_profit * up_log - p.stop_loss * down_log + p.timeout * mu * horizon

    lo, hi = -5.0 * sigma / math.sqrt(max(horizon, EPS)), 5.0 * sigma / math.sqrt(max(horizon, EPS))
    if edge(lo) > target_edge:
        return lo
    if edge(hi) < target_edge:
        return hi
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if edge(mid) < target_edge:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def survival_moment(
    mu: float,
    sigma: float,
    horizon: float,
    up_log: float,
    down_log: float,
    grid: int = 129,
) -> tuple[float, float]:
    """P(survive to T) and E[X_T * 1{survive}] for the absorbed process.

    The timeout branch of a triple-barrier trade cannot be valued at the
    unconditional drift. Conditioning on having touched neither barrier is a
    strong conditioning: when the stop is nearer than the target, the paths that
    survive are exactly the ones that drifted *away* from the stop, so the
    surviving population is skewed toward the target. Approximating that branch
    by `mu * T` therefore understates every trade's expected value by a fixed
    amount -- around 23 basis points at this engine's default geometry, which is
    the same order as its entire cost budget.

    The correct quantity comes from the same absorbed density used above,

        p(y, T | y0) = (2/L) exp( mu (y - y0)/sigma^2 - mu^2 T/(2 sigma^2) )
                       * sum_n sin(n pi y0/L) sin(n pi y/L) exp(-lambda_n T)

    integrated over the corridor. Composite Simpson quadrature on a fixed grid
    is used rather than the closed form for the trigonometric-exponential
    integral, because the closed form loses precision through cancellation for
    the small mu / sigma^2 ratios this engine produces.

    Consistency check, exercised in the test suite: with mu = 0 the process is a
    martingale, so

        P(tp) * up_log - P(sl) * down_log + E[X_T * 1{survive}] = 0.
    """
    if sigma <= EPS or horizon <= EPS or up_log <= EPS or down_log <= EPS:
        return 0.0, 0.0

    L = up_log + down_log
    y0 = down_log
    s2 = sigma * sigma

    n_max = _series_terms(s2 * horizon / (L * L))
    n = np.arange(1, n_max + 1, dtype=float)
    lam = (n * n) * (math.pi**2) * s2 / (2.0 * L * L)
    decay = np.exp(-np.clip(lam * horizon, 0.0, 700.0))
    sin0 = np.sin(n * math.pi * y0 / L)
    coef = sin0 * decay                                   # shape (n_max,)

    if grid % 2 == 0:
        grid += 1
    y = np.linspace(0.0, L, grid)
    sin_y = np.sin(np.outer(n * math.pi / L, y))          # (n_max, grid)
    series = coef @ sin_y                                 # (grid,)

    drift_arg = np.clip(mu * (y - y0) / s2 - mu * mu * horizon / (2.0 * s2), -700.0, 700.0)
    dens = (2.0 / L) * np.exp(drift_arg) * series
    dens = np.maximum(dens, 0.0)

    h = L / (grid - 1)
    w = np.ones(grid)
    w[1:-1:2] = 4.0
    w[2:-1:2] = 2.0
    w *= h / 3.0

    p_survive = float(np.dot(w, dens))
    e_x = float(np.dot(w, dens * (y - y0)))
    return p_survive, e_x


def outcome_moments(
    mu: float,
    sigma: float,
    horizon: float,
    up_log: float,
    down_log: float,
) -> tuple[float, float, BarrierProbs]:
    """Mean and variance of the trade's log return under the barrier model.

    Both moments are needed because the barrier geometry cannot be chosen on
    expected value alone. For Brownian motion with drift, optional stopping
    gives E[X_tau] = mu * E[tau], so expected value is monotone in how long the
    position stays open: the widest possible barriers always maximise it, and an
    engine that optimises raw edge will conclude it should never use a stop.
    That is a real property of the model rather than a bug -- a stop does cost
    expected return -- but it is the wrong objective, because it ignores what
    the stop buys.

    The variance returned here lets the caller optimise the Kelly growth rate
    E[X]^2 / (2 Var[X]) instead, which has an interior optimum.
    """
    probs = barrier_probs(mu, sigma, horizon, up_log, down_log)
    if sigma <= EPS or horizon <= EPS or up_log <= EPS or down_log <= EPS:
        return 0.0, 1.0, probs

    L = up_log + down_log
    y0 = down_log
    s2 = sigma * sigma
    n_max = _series_terms(s2 * horizon / (L * L))
    n = np.arange(1, n_max + 1, dtype=float)
    lam = (n * n) * (math.pi**2) * s2 / (2.0 * L * L)
    coef = np.sin(n * math.pi * y0 / L) * np.exp(-np.clip(lam * horizon, 0.0, 700.0))

    grid = 129
    y = np.linspace(0.0, L, grid)
    dens = (2.0 / L) * np.exp(np.clip(mu * (y - y0) / s2 - mu * mu * horizon / (2.0 * s2), -700.0, 700.0)) * (
        coef @ np.sin(np.outer(n * math.pi / L, y))
    )
    dens = np.maximum(dens, 0.0)

    h = L / (grid - 1)
    w = np.ones(grid)
    w[1:-1:2] = 4.0
    w[2:-1:2] = 2.0
    w *= h / 3.0

    d = y - y0
    mean = probs.take_profit * up_log - probs.stop_loss * down_log + float(np.dot(w, dens * d))
    second = probs.take_profit * up_log**2 + probs.stop_loss * down_log**2 + float(np.dot(w, dens * d * d))
    var = max(second - mean * mean, 1e-12)
    return mean, var, probs
