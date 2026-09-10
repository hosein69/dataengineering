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
    validation means anything.

    The test is on the *mean* predictive correlation across the panel, not on
    each series. With fat tails and volatility clustering the sampling standard
    deviation of a single autocorrelation estimate is roughly twice the
    textbook 1/sqrt(n), so per-series thresholds either flake or are set so wide
    they detect nothing. Pooling across series is both the correct test and a
    small illustration of the same point the harness makes about t-statistics
    on financial data.
    """
    corrs = {"own lag": [], "ofi": [], "funding": []}
    for seed in (3, 4, 5):
        mp = simulate_market(n_hours=3000, n_assets=6, alpha_strength=0.0, seed=seed)
        for d in mp.assets.values():
            r = d["log_return"]
            corrs["own lag"].append(float(np.corrcoef(r[:-1], r[1:])[0, 1]))
            corrs["ofi"].append(float(np.corrcoef(d["ofi"][:-1], r[1:])[0, 1]))
            corrs["funding"].append(float(np.corrcoef(d["funding"][:-1], r[1:])[0, 1]))
    # Exogenous predictors must be indistinguishable from noise.
    for name in ("ofi", "funding"):
        a = np.asarray(corrs[name])
        t = a.mean() / (a.std(ddof=1) / math.sqrt(a.size))
        assert abs(t) < 3.0, f"{name} predicts the next-hour return across the panel (t={t:.2f})"

    # The return's own lag is a different case and is checked on magnitude
    # rather than significance. Making the price an arithmetic martingale
    # requires a drift of -var[t+1]/2, and under the leverage effect var[t+1]
    # depends asymmetrically on the sign of r[t]; the two together imply a small
    # positive autocorrelation. That is a property of arithmetic martingales
    # with asymmetric volatility, not a leak, and it cannot be removed without
    # breaking the martingale property. What matters is that it stays far below
    # anything the cost model would let a strategy reach.
    own = np.asarray(corrs["own lag"])
    assert abs(own.mean()) < 0.05, f"lag-1 autocorrelation is economically large ({own.mean():+.4f})"


def test_planted_alpha_is_actually_present():
    mp = simulate_market(n_hours=8000, n_assets=6, alpha_strength=1.0, seed=3)
    assert 0.015 < mp.truth["planted_ic"] < 0.10


def test_planted_alpha_decays_and_the_horizon_matters():
    """A signal with a longer half-life is weaker at one hour and stronger over
    a day. A planted signal that is exhausted after one bar is untradeable at
    any horizon this engine operates on, so it cannot test anything."""
    short = simulate_market(n_hours=8000, n_assets=6, alpha_strength=1.0,
                            alpha_halflife_hours=4.0, horizon_for_truth=24, seed=4)
    long_ = simulate_market(n_hours=8000, n_assets=6, alpha_strength=1.0,
                            alpha_halflife_hours=16.0, horizon_for_truth=24, seed=4)
    assert short.truth["planted_ic_1h"] > long_.truth["planted_ic_1h"]
    assert long_.truth["planted_ic"] > short.truth["planted_ic"]


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


def test_ic_shrinkage_kills_a_noisy_measurement():
    """A correlation measured on a couple of hundred effective observations has
    a standard error near 0.07; a raw 0.13 must not survive as a 0.13."""
    from orion_x.alpha import shrink_ic

    assert abs(shrink_ic(0.13, 235, 0.03)) < 0.03
    # With enough independent observations the measurement is believed.
    assert shrink_ic(0.04, 20_000, 0.03) > 0.03
    # And shrinkage is monotone in sample size.
    assert shrink_ic(0.05, 200, 0.03) < shrink_ic(0.05, 2000, 0.03) < shrink_ic(0.05, 20_000, 0.03)


def test_ic_weights_concentrate_on_the_informative_block():
    """Fixed prior weights average one informative signal with six noise ones
    and dilute its IC roughly in proportion to its weight."""
    from orion_x.alpha import optimal_block_weights

    w = optimal_block_weights({
        "flow": 0.037, "momentum": 0.002, "carry": -0.01,
        "fundamental": 0.001, "psychology": 0.0, "relative": 0.003, "catalyst": 0.0,
    })
    assert w["flow"] > 0.5
    assert sum(w.values()) == pytest.approx(1.0)


def test_ic_weights_never_hand_everything_to_one_block():
    from orion_x.alpha import optimal_block_weights

    w = optimal_block_weights({"flow": 0.20, "momentum": 0.001, "carry": 0.001})
    assert max(w.values()) <= 0.70 + 1e-9


def test_negative_measured_ic_gets_no_weight_rather_than_a_flipped_sign():
    """A sign that only shows up out of sample is far more likely to be noise
    than a discovery."""
    from orion_x.alpha import optimal_block_weights

    w = optimal_block_weights({"flow": 0.03, "psychology": -0.09})
    assert "psychology" not in w
