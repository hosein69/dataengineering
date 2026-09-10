//! Triple-barrier first-passage probabilities.
//!
//! A direct port of `orion_x/barriers.py`. The two implementations are checked
//! against each other by `tests/parity.rs`, which fails the build if they ever
//! disagree by more than 1e-9 -- the Rust core is meant to be the same model
//! running faster, not a second model that happens to share a name.
//!
//! Log price is arithmetic Brownian motion with drift,
//!
//! ```text
//!     dX_t = mu dt + sigma dW_t,   X_0 = 0
//! ```
//!
//! absorbed at `up_log > 0` and `-down_log < 0` over a finite horizon `T`.
//! Shifting to `y = X + down_log` on `[0, L]`, the absorbed density has the
//! classical eigenfunction expansion and the absorption rate at each boundary
//! is the diffusive part of the probability current. Integrating that flux to
//! `T`, and splitting the result into its infinite-horizon limit (the drifted
//! gambler's-ruin probability, available in closed form through the scale
//! function) plus an exponentially damped correction, gives a series that
//! converges like `exp(-n^2)` instead of like `1/n`.

use serde::{Deserialize, Serialize};

pub const EPS: f64 = 1e-12;

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct BarrierProbs {
    pub take_profit: f64,
    pub stop_loss: f64,
    pub timeout: f64,
}

impl BarrierProbs {
    pub fn sum(&self) -> f64 {
        self.take_profit + self.stop_loss + self.timeout
    }
}

pub fn clamp(x: f64, lo: f64, hi: f64) -> f64 {
    x.max(lo).min(hi)
}

pub fn safe_div(a: f64, b: f64, default: f64) -> f64 {
    if b.abs() > EPS {
        a / b
    } else {
        default
    }
}

/// Term count that drives the truncated tail below ~1e-10.
///
/// The n-th correction term decays like `exp(-n^2 pi^2 sigma^2 T / (2 L^2))`.
fn series_terms(sigma2_t_over_l2: f64) -> usize {
    let x = sigma2_t_over_l2.max(1e-9);
    let n = (2.0 * 23.0 / (std::f64::consts::PI.powi(2) * x)).sqrt() + 8.0;
    (n.ceil() as usize).clamp(16, 20_000)
}

/// `P(hit L before 0)` for drifted Brownian motion started at `y0` in `[0, L]`,
/// via the scale function `s(y) = exp(-2 mu y / sigma^2)`.
fn ruin_probability(mu: f64, sigma: f64, l: f64, y0: f64) -> f64 {
    let a = 2.0 * mu / (sigma * sigma);
    if (a * l).abs() < 1e-9 {
        return y0 / l;
    }
    (-a * y0).exp_m1() / (-a * l).exp_m1()
}

/// Exact triple-barrier probabilities.
///
/// * `mu` -- drift of log price per unit time.
/// * `sigma` -- diffusion per sqrt(unit time), strictly positive.
/// * `horizon` -- the time barrier.
/// * `up_log` -- `ln(take_profit / entry)`, positive.
/// * `down_log` -- `ln(entry / stop_loss)`, positive.
pub fn barrier_probs(mu: f64, sigma: f64, horizon: f64, up_log: f64, down_log: f64) -> BarrierProbs {
    if sigma <= EPS || horizon <= EPS {
        let m = mu * horizon.max(0.0);
        return if m >= up_log {
            BarrierProbs { take_profit: 1.0, stop_loss: 0.0, timeout: 0.0 }
        } else if m <= -down_log {
            BarrierProbs { take_profit: 0.0, stop_loss: 1.0, timeout: 0.0 }
        } else {
            BarrierProbs { take_profit: 0.0, stop_loss: 0.0, timeout: 1.0 }
        };
    }
    if up_log <= EPS || down_log <= EPS {
        return if up_log <= EPS && down_log <= EPS {
            BarrierProbs { take_profit: 0.5, stop_loss: 0.5, timeout: 0.0 }
        } else if up_log <= EPS {
            BarrierProbs { take_profit: 1.0, stop_loss: 0.0, timeout: 0.0 }
        } else {
            BarrierProbs { take_profit: 0.0, stop_loss: 1.0, timeout: 0.0 }
        };
    }

    let l = up_log + down_log;
    let y0 = down_log;
    let s2 = sigma * sigma;
    let pi = std::f64::consts::PI;

    let p_up_inf = ruin_probability(mu, sigma, l, y0);
    let p_dn_inf = 1.0 - p_up_inf;

    let n_max = series_terms(s2 * horizon / (l * l));
    let pref = s2 * pi / (l * l);
    let e_up = (mu * (l - y0) / s2).exp();
    let e_dn = (-mu * y0 / s2).exp();

    let mut corr_up = 0.0;
    let mut corr_dn = 0.0;
    for k in 1..=n_max {
        let n = k as f64;
        let lam = n * n * pi * pi * s2 / (2.0 * l * l);
        let beta = lam + mu * mu / (2.0 * s2);
        let damped = (-(beta * horizon).clamp(0.0, 700.0)).exp() / beta;
        let sin0 = (n * pi * y0 / l).sin();
        let alt = if k % 2 == 1 { 1.0 } else { -1.0 };
        corr_up += n * alt * sin0 * damped;
        corr_dn += n * sin0 * damped;
    }

    let mut p_up = p_up_inf - pref * e_up * corr_up;
    let mut p_dn = p_dn_inf - pref * e_dn * corr_dn;

    p_up = clamp(p_up, 0.0, 1.0);
    p_dn = clamp(p_dn, 0.0, 1.0);
    let total = p_up + p_dn;
    if total > 1.0 {
        p_up /= total;
        p_dn /= total;
    }
    BarrierProbs { take_profit: p_up, stop_loss: p_dn, timeout: (1.0 - p_up - p_dn).max(0.0) }
}

/// `P(survive to T)` and `E[X_T * 1{survive}]`, by Simpson quadrature of the
/// absorbed density over the corridor.
///
/// The timeout branch of a triple-barrier trade cannot be valued at the
/// unconditional drift: conditioning on having touched neither barrier skews
/// the surviving paths toward whichever barrier is further away.
pub fn survival_moment(mu: f64, sigma: f64, horizon: f64, up_log: f64, down_log: f64) -> (f64, f64) {
    if sigma <= EPS || horizon <= EPS || up_log <= EPS || down_log <= EPS {
        return (0.0, 0.0);
    }
    let l = up_log + down_log;
    let y0 = down_log;
    let s2 = sigma * sigma;
    let pi = std::f64::consts::PI;
    let n_max = series_terms(s2 * horizon / (l * l));

    let coef: Vec<f64> = (1..=n_max)
        .map(|k| {
            let n = k as f64;
            let lam = n * n * pi * pi * s2 / (2.0 * l * l);
            (n * pi * y0 / l).sin() * (-(lam * horizon).clamp(0.0, 700.0)).exp()
        })
        .collect();

    const GRID: usize = 129;
    let h = l / (GRID - 1) as f64;
    let mut p_survive = 0.0;
    let mut e_x = 0.0;
    for i in 0..GRID {
        let y = i as f64 * h;
        let mut series = 0.0;
        for (k, c) in coef.iter().enumerate() {
            let n = (k + 1) as f64;
            series += c * (n * pi * y / l).sin();
        }
        let arg = (mu * (y - y0) / s2 - mu * mu * horizon / (2.0 * s2)).clamp(-700.0, 700.0);
        let dens = ((2.0 / l) * arg.exp() * series).max(0.0);
        // Composite Simpson weights.
        let w = if i == 0 || i == GRID - 1 {
            1.0
        } else if i % 2 == 1 {
            4.0
        } else {
            2.0
        } * h / 3.0;
        p_survive += w * dens;
        e_x += w * dens * (y - y0);
    }
    (p_survive, e_x)
}

/// Mean and variance of the trade's log return under the barrier model.
///
/// Both are needed because expected value alone is monotone in barrier width --
/// by optional stopping `E[X_tau] = mu E[tau]` -- so optimising it pushes the
/// stop to infinity. The variance is what gives the growth-rate objective an
/// interior optimum.
pub fn outcome_moments(
    mu: f64,
    sigma: f64,
    horizon: f64,
    up_log: f64,
    down_log: f64,
) -> (f64, f64, BarrierProbs) {
    let probs = barrier_probs(mu, sigma, horizon, up_log, down_log);
    if sigma <= EPS || horizon <= EPS || up_log <= EPS || down_log <= EPS {
        return (0.0, 1.0, probs);
    }
    let (_, e_x) = survival_moment(mu, sigma, horizon, up_log, down_log);
    let (_, e_x2) = survival_second_moment(mu, sigma, horizon, up_log, down_log);
    let mean = probs.take_profit * up_log - probs.stop_loss * down_log + e_x;
    let second =
        probs.take_profit * up_log * up_log + probs.stop_loss * down_log * down_log + e_x2;
    (mean, (second - mean * mean).max(1e-12), probs)
}

fn survival_second_moment(
    mu: f64,
    sigma: f64,
    horizon: f64,
    up_log: f64,
    down_log: f64,
) -> (f64, f64) {
    let l = up_log + down_log;
    let y0 = down_log;
    let s2 = sigma * sigma;
    let pi = std::f64::consts::PI;
    let n_max = series_terms(s2 * horizon / (l * l));
    let coef: Vec<f64> = (1..=n_max)
        .map(|k| {
            let n = k as f64;
            let lam = n * n * pi * pi * s2 / (2.0 * l * l);
            (n * pi * y0 / l).sin() * (-(lam * horizon).clamp(0.0, 700.0)).exp()
        })
        .collect();

    const GRID: usize = 129;
    let h = l / (GRID - 1) as f64;
    let mut p = 0.0;
    let mut e2 = 0.0;
    for i in 0..GRID {
        let y = i as f64 * h;
        let mut series = 0.0;
        for (k, c) in coef.iter().enumerate() {
            series += c * (((k + 1) as f64) * pi * y / l).sin();
        }
        let arg = (mu * (y - y0) / s2 - mu * mu * horizon / (2.0 * s2)).clamp(-700.0, 700.0);
        let dens = ((2.0 / l) * arg.exp() * series).max(0.0);
        let w = if i == 0 || i == GRID - 1 {
            1.0
        } else if i % 2 == 1 {
            4.0
        } else {
            2.0
        } * h / 3.0;
        p += w * dens;
        e2 += w * dens * (y - y0) * (y - y0);
    }
    (p, e2)
}
