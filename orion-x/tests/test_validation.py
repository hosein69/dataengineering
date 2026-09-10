"""Tests for the validation machinery itself.

A backtest harness that is not tested is a random number generator with
opinions. These check the parts most likely to manufacture a result.
"""
import math

import numpy as np
import pytest

from orion_x.backtest.cv import PurgedKFold, sample_uniqueness
from orion_x.backtest.labeling import triple_barrier_labels
from orion_x.backtest.metrics import deflated_sharpe_ratio, expected_max_sharpe, summarize
from orion_x.backtest.simulate import simulate_market
from orion_x.calibration import brier_decomposition, isotonic_apply, isotonic_fit
from orion_x.linalg import effective_number_of_bets, marchenko_pastur_denoise


def test_purged_folds_never_leak_across_the_label_window():
    kf = PurgedKFold(n_splits=5, label_horizon=7, embargo_frac=0.01)
    n = 500
    for train, test in kf.split(n):
        assert not set(train) & set(test)
        # no training index may reach into the test block through its label
        assert all(i + 7 < test.min() or i - 7 > test.max() for i in train)


def test_sample_uniqueness_falls_with_overlap():
    n = 100
    isolated = sample_uniqueness(np.arange(n), n)          # zero-length labels
    overlapping = sample_uniqueness(np.arange(n) + 20, n)  # heavy overlap
    assert overlapping.mean() < isolated.mean()


def test_short_labels_are_not_inverted():
    """A short that reaches its target must book a gain, not a loss."""
    prices = np.array([100.0, 99.0, 98.0, 97.0, 96.0])
    lab = triple_barrier_labels(prices, np.array([-1.0] * 5), np.full(5, 0.02), np.full(5, 0.02), 4)
    assert lab.outcome[0] == 1.0
    assert lab.realized_return[0] > 0


def test_long_labels_are_signed_correctly():
    prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0])
    lab = triple_barrier_labels(prices, np.array([1.0] * 5), np.full(5, 0.02), np.full(5, 0.02), 4)
    assert lab.outcome[0] == 1.0
    assert lab.realized_return[0] > 0


def test_stopped_out_trades_lose_on_both_sides():
    up = np.array([100.0, 103.0, 104.0, 105.0, 106.0])
    short = triple_barrier_labels(up, np.array([-1.0] * 5), np.full(5, 0.02), np.full(5, 0.02), 4)
    assert short.outcome[0] == -1.0 and short.realized_return[0] < 0
    down = np.array([100.0, 97.0, 96.0, 95.0, 94.0])
    long_ = triple_barrier_labels(down, np.array([1.0] * 5), np.full(5, 0.02), np.full(5, 0.02), 4)
    assert long_.outcome[0] == -1.0 and long_.realized_return[0] < 0


def test_expected_max_sharpe_grows_with_trials():
    v = 1.0 / 999
    assert expected_max_sharpe(1000, v) > expected_max_sharpe(10, v) > 0


def test_deflated_sharpe_punishes_selection():
    rng = np.random.default_rng(0)
    r = rng.standard_normal(1200) * 0.01 + 0.0015
    assert deflated_sharpe_ratio(r, 1) > deflated_sharpe_ratio(r, 500)


def test_null_market_gives_no_strategy_a_real_edge():
    """The generator must be unpredictable. If this fails, nothing else in the
    validation means anything."""
    mp = simulate_market(n_hours=3000, n_assets=6, alpha_strength=0.0, seed=3)
    for sym, d in mp.assets.items():
        r = d["log_return"]
        for name, x in (("own lag", r[:-1]), ("ofi", d["ofi"][:-1]), ("funding", d["funding"][:-1])):
            c = float(np.corrcoef(x, r[1:])[0, 1])
            t = abs(c) * math.sqrt(r.size - 1)
            assert t < 3.5, f"{sym}: {name} predicts next-hour return (t={t:.2f})"


def test_planted_alpha_is_actually_present():
    mp = simulate_market(n_hours=3000, n_assets=6, alpha_strength=1.0, seed=3)
    assert 0.02 < mp.truth["planted_ic"] < 0.10


def test_prices_are_arithmetic_martingales():
    """Without the Ito correction a driftless log return implies a positive
    arithmetic drift, which a barrier strategy books as free profit."""
    mp = simulate_market(n_hours=6000, n_assets=8, alpha_strength=0.0, seed=9)
    for sym, d in mp.assets.items():
        simple = np.exp(d["log_return"]) - 1.0
        t = simple.mean() / simple.std() * math.sqrt(simple.size)
        assert abs(t) < 3.5, f"{sym} has an arithmetic drift (t={t:.2f})"


def test_brier_reliability_detects_miscalibration():
    rng = np.random.default_rng(1)
    p = rng.random(4000)
    y = (rng.random(4000) < p).astype(float)
    good = brier_decomposition(p, y)
    bad = brier_decomposition(np.clip(p * 0.5 + 0.25, 0, 1), y)
    assert bad.reliability > good.reliability * 5


def test_isotonic_recalibration_is_monotone():
    rng = np.random.default_rng(2)
    p = rng.random(600)
    y = (rng.random(600) < p * 0.6 + 0.2).astype(float)
    kx, ky = isotonic_fit(p, y)
    out = isotonic_apply(kx, ky, np.linspace(0, 1, 50))
    assert np.all(np.diff(out) >= -1e-12)


def test_effective_bets_collapses_under_one_factor():
    rng = np.random.default_rng(4)
    f = rng.standard_normal((400, 1))
    x = f @ np.ones((1, 12)) * 0.02 + rng.standard_normal((400, 12)) * 0.0005
    cov = np.cov(x, rowvar=False)
    assert effective_number_of_bets(np.ones(12) / 12, cov) < 1.5
    independent = np.cov(rng.standard_normal((400, 12)), rowvar=False)
    assert effective_number_of_bets(np.ones(12) / 12, independent) > 8.0


def test_marchenko_pastur_clips_pure_noise():
    rng = np.random.default_rng(5)
    x = rng.standard_normal((150, 60))
    corr = np.corrcoef(x, rowvar=False)
    denoised, share = marchenko_pastur_denoise(corr, 150)
    assert share < 0.35
    assert np.allclose(np.diag(denoised), 1.0, atol=1e-8)
