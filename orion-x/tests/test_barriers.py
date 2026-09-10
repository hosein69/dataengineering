"""The barrier module is the engine's mathematical core, so it is checked
against closed forms and against an independent Monte Carlo implementation
rather than against recorded outputs."""
import math

import numpy as np
import pytest

from orion_x.barriers import barrier_probs, barrier_probs_mc, outcome_moments, survival_moment


def test_driftless_symmetric_is_a_coin_flip():
    p = barrier_probs(0.0, 0.02, 10_000.0, 0.05, 0.05)
    assert p.take_profit == pytest.approx(0.5, abs=1e-6)
    assert p.stop_loss == pytest.approx(0.5, abs=1e-6)
    assert p.timeout == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("up,down", [(0.03, 0.06), (0.01, 0.09), (0.07, 0.02)])
def test_gamblers_ruin_limit(up, down):
    """With no drift and no time limit, P(target) is the distance ratio."""
    p = barrier_probs(0.0, 0.02, 500_000.0, up, down)
    assert p.take_profit == pytest.approx(down / (up + down), abs=1e-5)


def test_drifted_ruin_matches_scale_function():
    """P(target) must match (1 - e^{-2 mu y0/s^2}) / (1 - e^{-2 mu L/s^2})."""
    mu, sigma, up, down = 0.001, 0.01, 0.04, 0.04
    a = 2 * mu / sigma**2
    L, y0 = up + down, down
    expected = np.expm1(-a * y0) / np.expm1(-a * L)
    p = barrier_probs(mu, sigma, 1_000_000.0, up, down)
    assert p.take_profit == pytest.approx(float(expected), abs=1e-4)


@pytest.mark.parametrize(
    "mu,sigma,T,up,down",
    [(0.0005, 0.012, 7, 0.05, 0.037), (0.0, 0.015, 7, 0.04, 0.010),
     (0.004, 0.010, 7, 0.03, 0.030), (-0.002, 0.02, 24, 0.06, 0.04)],
)
def test_series_agrees_with_monte_carlo(mu, sigma, T, up, down):
    a = barrier_probs(mu, sigma, T, up, down)
    b = barrier_probs_mc(mu, sigma, T, up, down, paths=200_000, seed=11, steps=256)
    for x, y in zip(a.as_tuple(), b.as_tuple()):
        assert x == pytest.approx(y, abs=0.006)


@pytest.mark.parametrize(
    "up,down", [(0.0285, 0.0171), (0.05, 0.05), (0.02, 0.06), (0.08, 0.02)]
)
def test_martingale_identity(up, down):
    """With zero drift the process is a martingale, so the three branches of
    the triple barrier must have expectations that sum to exactly zero.

    This ties the flux-integral probabilities and the quadrature-based
    conditional expectation together: an error in either one breaks it.
    """
    sigma, T = 0.012, 7.0
    p = barrier_probs(0.0, sigma, T, up, down)
    _, e_x = survival_moment(0.0, sigma, T, up, down)
    assert p.take_profit * up - p.stop_loss * down + e_x == pytest.approx(0.0, abs=1e-9)


def test_survival_probability_agrees_between_methods():
    """P(timeout) from the absorption flux and from integrating the density."""
    for up, down in [(0.03, 0.02), (0.05, 0.05), (0.01, 0.08)]:
        p = barrier_probs(0.0008, 0.013, 7.0, up, down)
        p_surv, _ = survival_moment(0.0008, 0.013, 7.0, up, down)
        assert p.timeout == pytest.approx(p_surv, abs=1e-6)


def test_probabilities_are_a_distribution():
    for mu in (-0.01, 0.0, 0.01):
        for T in (1.0, 7.0, 100.0):
            p = barrier_probs(mu, 0.015, T, 0.03, 0.02)
            assert all(0.0 <= x <= 1.0 for x in p.as_tuple())
            assert sum(p.as_tuple()) == pytest.approx(1.0, abs=1e-9)


def test_variance_is_positive_and_ordered():
    """Wider barriers must produce a wider outcome distribution."""
    narrow = outcome_moments(0.0005, 0.012, 7.0, 0.02, 0.02)[1]
    wide = outcome_moments(0.0005, 0.012, 7.0, 0.08, 0.08)[1]
    assert 0 < narrow < wide


def test_expected_value_is_drift_times_expected_stopping_time():
    """Optional stopping: E[X_tau] = mu * E[tau], so a positive drift cannot
    produce a negative expected value at any barrier geometry."""
    for up in (0.01, 0.03, 0.09):
        mean, _, _ = outcome_moments(0.0006, 0.012, 7.0, up, 0.03)
        assert mean > 0
