//! Correctness and cross-language parity.
//!
//! The closed-form checks below are the same ones `tests/test_barriers.py`
//! runs, with the same tolerances, so the two implementations cannot drift
//! apart without a test going red in one language or the other.

use orion_x::barriers::{barrier_probs, outcome_moments, survival_moment};
use orion_x::costs::{estimate_costs, CostInputs, CostModel};
use orion_x::sizing::{size_position, SizeInputs, SizingConfig};

#[test]
fn driftless_symmetric_is_a_coin_flip() {
    let p = barrier_probs(0.0, 0.02, 10_000.0, 0.05, 0.05);
    assert!((p.take_profit - 0.5).abs() < 1e-6);
    assert!((p.stop_loss - 0.5).abs() < 1e-6);
}

#[test]
fn gamblers_ruin_limit() {
    for (up, down) in [(0.03, 0.06), (0.01, 0.09), (0.07, 0.02)] {
        let p = barrier_probs(0.0, 0.02, 500_000.0, up, down);
        assert!((p.take_profit - down / (up + down)).abs() < 1e-5, "up={up} down={down}");
    }
}

#[test]
fn drifted_ruin_matches_scale_function() {
    let (mu, sigma, up, down) = (0.001_f64, 0.01_f64, 0.04_f64, 0.04_f64);
    let a = 2.0 * mu / (sigma * sigma);
    let expected = (-a * down).exp_m1() / (-a * (up + down)).exp_m1();
    let p = barrier_probs(mu, sigma, 1_000_000.0, up, down);
    assert!((p.take_profit - expected).abs() < 1e-4);
}

#[test]
fn martingale_identity_holds() {
    for (up, down) in [(0.0285, 0.0171), (0.05, 0.05), (0.02, 0.06), (0.08, 0.02)] {
        let p = barrier_probs(0.0, 0.012, 7.0, up, down);
        let (_, e_x) = survival_moment(0.0, 0.012, 7.0, up, down);
        let resid = p.take_profit * up - p.stop_loss * down + e_x;
        assert!(resid.abs() < 1e-9, "up={up} down={down} residual={resid:e}");
    }
}

#[test]
fn survival_probability_agrees_between_methods() {
    for (up, down) in [(0.03, 0.02), (0.05, 0.05), (0.01, 0.08)] {
        let p = barrier_probs(0.0008, 0.013, 7.0, up, down);
        let (ps, _) = survival_moment(0.0008, 0.013, 7.0, up, down);
        assert!((p.timeout - ps).abs() < 1e-6, "up={up} down={down}");
    }
}

#[test]
fn probabilities_form_a_distribution() {
    for mu in [-0.01, 0.0, 0.01] {
        for t in [1.0, 7.0, 100.0] {
            let p = barrier_probs(mu, 0.015, t, 0.03, 0.02);
            assert!((p.sum() - 1.0).abs() < 1e-9);
            for v in [p.take_profit, p.stop_loss, p.timeout] {
                assert!((0.0..=1.0).contains(&v));
            }
        }
    }
}

#[test]
fn positive_drift_gives_positive_expected_value() {
    for up in [0.01, 0.03, 0.09] {
        let (mean, var, _) = outcome_moments(0.0006, 0.012, 7.0, up, 0.03);
        assert!(mean > 0.0, "up={up}");
        assert!(var > 0.0);
    }
}

#[test]
fn wider_barriers_widen_the_outcome_distribution() {
    let narrow = outcome_moments(0.0005, 0.012, 7.0, 0.02, 0.02).1;
    let wide = outcome_moments(0.0005, 0.012, 7.0, 0.08, 0.08).1;
    assert!(narrow < wide);
}

#[test]
fn funding_is_income_for_a_long_when_negative() {
    let model = CostModel::default();
    let inp = |f: f64| CostInputs {
        side: 1,
        notional: 250_000.0,
        hourly_volume: 100e6,
        sigma_per_hour: 0.012,
        spread_bps: 5.0,
        funding_rate_8h: f,
        holding_hours: 4.6,
    };
    assert!(estimate_costs(&inp(-0.0002), &model).funding < 0.0);
    assert!(estimate_costs(&inp(0.0002), &model).funding > 0.0);
}

#[test]
fn every_cost_component_except_funding_is_a_cost() {
    let c = estimate_costs(
        &CostInputs {
            side: 1,
            notional: 250_000.0,
            hourly_volume: 100e6,
            sigma_per_hour: 0.012,
            spread_bps: 5.0,
            funding_rate_8h: -0.001,
            holding_hours: 4.0,
        },
        &CostModel::default(),
    );
    assert!(c.fees > 0.0 && c.spread > 0.0 && c.impact > 0.0);
}

#[test]
fn size_responds_to_edge_and_respects_caps() {
    let cfg = SizingConfig::default();
    let mk = |edge: f64| SizeInputs {
        edge,
        sigma_horizon: 0.032,
        stop_distance: 0.037,
        hourly_volume: 100e6,
        portfolio_equity: 1_000_000.0,
        breadth: 3.0,
    };
    let small = size_position(&mk(0.0002), &cfg);
    let large = size_position(&mk(0.02), &cfg);
    assert!(small.fraction < large.fraction);
    assert!(large.fraction <= cfg.leverage_ceiling);
    assert_eq!(small.binding_constraint, "kelly");
}

#[test]
fn a_non_positive_edge_gets_no_size() {
    let d = size_position(
        &SizeInputs {
            edge: -0.001,
            sigma_horizon: 0.03,
            stop_distance: 0.03,
            hourly_volume: 100e6,
            portfolio_equity: 1_000_000.0,
            breadth: 3.0,
        },
        &SizingConfig::default(),
    );
    assert_eq!(d.fraction, 0.0);
}
