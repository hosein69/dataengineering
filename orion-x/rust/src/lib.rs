//! ORION-X v5 core.
//!
//! This crate carries the parts of the engine where speed matters and where
//! correctness is checkable against closed forms: the triple-barrier
//! first-passage solution, the cost model, the barrier optimiser and position
//! sizing. It is a port of the Python package in the parent directory, not an
//! independent design, and `tests/parity.rs` pins the two together.
//!
//! What deliberately does *not* live here is the feature layer. Evidence
//! blocks change with research; the mathematics does not.

pub mod barriers;
pub mod costs;
pub mod sizing;

pub use barriers::{barrier_probs, outcome_moments, survival_moment, BarrierProbs};
pub use costs::{estimate_costs, CostBreakdown, CostInputs, CostModel};
pub use sizing::{size_position, SizeDecision, SizeInputs, SizingConfig};

pub const VERSION: &str = "5.0.0";

/// Choose the barrier geometry that maximises the Kelly growth rate.
///
/// Returns `(tp_sigma, sl_sigma, score)` in units of horizon volatility. The
/// coarse-to-fine sweep matches the Python implementation exactly so that both
/// languages pick the same geometry for the same inputs.
pub fn optimize_barriers(
    mu: f64,
    sigma_h: f64,
    horizon: f64,
    fixed_cost: f64,
    funding_per_hour: f64,
    min_sigma: f64,
    max_sigma: f64,
) -> (f64, f64, f64) {
    let sigma_t = sigma_h * horizon.sqrt();
    let (lo_tp, hi_tp) = (min_sigma, max_sigma);
    let (lo_sl, hi_sl) = (min_sigma, max_sigma.min(2.2));

    let evaluate = |tp_s: f64, sl_s: f64| -> f64 {
        let up = (tp_s * sigma_t).ln_1p();
        let down = -(-(sl_s * sigma_t).min(0.5)).ln_1p();
        let (mean, var, probs) = outcome_moments(mu, sigma_h, horizon, up, down);
        let hold = horizon * (0.35 + 0.65 * probs.timeout);
        let net = mean - fixed_cost - funding_per_hour * hold;
        if net > 0.0 {
            (net * net) / (2.0 * var)
        } else {
            net
        }
    };

    let lin = |lo: f64, hi: f64, i: usize, n: usize| lo + (hi - lo) * i as f64 / (n - 1) as f64;
    let mut best = (f64::NEG_INFINITY, lo_tp, lo_sl);
    for i in 0..5 {
        for j in 0..5 {
            let (tp_s, sl_s) = (lin(lo_tp, hi_tp, i, 5), lin(lo_sl, hi_sl, j, 5));
            let s = evaluate(tp_s, sl_s);
            if s > best.0 {
                best = (s, tp_s, sl_s);
            }
        }
    }
    let step_tp = (hi_tp - lo_tp) / 8.0;
    let step_sl = (hi_sl - lo_sl) / 8.0;
    for dtp in [-step_tp, 0.0, step_tp] {
        for dsl in [-step_sl, 0.0, step_sl] {
            let tp_s = (best.1 + dtp).clamp(lo_tp, hi_tp);
            let sl_s = (best.2 + dsl).clamp(lo_sl, hi_sl);
            let s = evaluate(tp_s, sl_s);
            if s > best.0 {
                best = (s, tp_s, sl_s);
            }
        }
    }
    (best.1, best.2, best.0)
}

/// Shortest horizon at which a signal of this strength pays for its own costs.
///
/// Under Grinold's rule the forecastable move grows like `sqrt(T)` while fees,
/// spread and impact do not grow with `T` at all, so extending the horizon
/// dilutes the fixed cost. The hurdle is expressed as a fraction of horizon
/// volatility and therefore grows like `sqrt(T)` too, so in the long-horizon
/// limit the ratio of edge to hurdle tends to `IC |z| / h`: horizon extension
/// buys freedom from fixed costs, never information.
pub fn minimum_viable_horizon(
    sigma_per_hour: f64,
    ic: f64,
    z: f64,
    fixed_cost: f64,
    funding_per_hour: f64,
    hurdle_sigma_fraction: f64,
    sigma_per_hour_for_hurdle: f64,
) -> (f64, Vec<(f64, f64)>) {
    let candidates: [f64; 10] = [2.0, 4.0, 7.0, 12.0, 24.0, 48.0, 96.0, 168.0, 336.0, 720.0];
    let mut curve = Vec::new();
    let mut best = f64::INFINITY;
    for &t in candidates.iter() {
        let sigma_t = sigma_per_hour * t.sqrt();
        let mu = ic * sigma_t * z / t;
        let (tp_s, sl_s, _) = optimize_barriers(mu, sigma_per_hour, t, fixed_cost, funding_per_hour, 0.6, 3.0);
        let up = (tp_s * sigma_t).ln_1p();
        let down = -(-(sl_s * sigma_t).min(0.5)).ln_1p();
        let (mean, _, probs) = outcome_moments(mu, sigma_per_hour, t, up, down);
        let net = mean - fixed_cost - funding_per_hour * t * (0.35 + 0.65 * probs.timeout);
        curve.push((t, net));
        let hurdle = (hurdle_sigma_fraction * sigma_per_hour_for_hurdle * t.sqrt()).max(0.0009);
        if net >= hurdle && t < best {
            best = t;
        }
    }
    (best, curve)
}
