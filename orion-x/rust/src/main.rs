//! Demonstration binary for the ORION-X v5 core.
//!
//! Prints the same barrier, cost and sizing numbers the Python engine reports,
//! plus the mathematical identities the model has to satisfy. Run with
//! `cargo run --release`.

use orion_x::barriers::{barrier_probs, survival_moment};
use orion_x::costs::{estimate_costs, CostInputs, CostModel};
use orion_x::sizing::{size_position, SizeInputs, SizingConfig};
use orion_x::{minimum_viable_horizon, optimize_barriers, VERSION};

fn main() {
    println!("ORION-X v{VERSION} core (Rust)\n{}", "=".repeat(70));

    // --- identities the model must satisfy --------------------------------
    println!("\nMathematical identities");
    let p = barrier_probs(0.0, 0.02, 500_000.0, 0.03, 0.06);
    println!(
        "  gambler's ruin      P(target) = {:.6}   expected {:.6}",
        p.take_profit,
        0.06 / 0.09
    );
    let p = barrier_probs(0.0, 0.012, 7.0, 0.0285, 0.0171);
    let (p_surv, e_x) = survival_moment(0.0, 0.012, 7.0, 0.0285, 0.0171);
    println!(
        "  martingale residual {:+.3e}   (P(tp)*up - P(sl)*down + E[X 1_surv])",
        p.take_profit * 0.0285 - p.stop_loss * 0.0171 + e_x
    );
    println!(
        "  P(timeout): flux {:.8} vs quadrature {:.8}",
        p.timeout, p_surv
    );

    // --- a worked trade ----------------------------------------------------
    let sigma_h = 0.0102_f64;
    let horizon = 7.0_f64;
    let sigma_t = sigma_h * horizon.sqrt();
    let model = CostModel::default();
    let fixed = estimate_costs(
        &CostInputs {
            side: 1,
            notional: 250_000.0,
            hourly_volume: 90e6,
            sigma_per_hour: sigma_h,
            spread_bps: 3.0,
            funding_rate_8h: 0.0,
            holding_hours: 0.0,
        },
        &model,
    );
    let funding_8h = 0.000_08_f64;
    let ic = 0.03_f64;
    let z = 1.4_f64;
    let mu = ic * sigma_t * z / horizon;

    let (tp_s, sl_s, _) = optimize_barriers(mu, sigma_h, horizon, fixed.total, funding_8h / 8.0, 0.6, 3.0);
    let up = (tp_s * sigma_t).ln_1p();
    let down = -(-(sl_s * sigma_t).min(0.5)).ln_1p();
    let (mean, var, probs) = orion_x::outcome_moments(mu, sigma_h, horizon, up, down);
    let hold = horizon * (0.35 + 0.65 * probs.timeout);
    let costs = estimate_costs(
        &CostInputs {
            side: 1,
            notional: 250_000.0,
            hourly_volume: 90e6,
            sigma_per_hour: sigma_h,
            spread_bps: 3.0,
            funding_rate_8h: funding_8h,
            holding_hours: hold,
        },
        &model,
    );
    let net = mean - costs.total;

    println!("\nWorked trade  (sigma_1h {sigma_h:.4}, horizon {horizon:.0}h, IC {ic}, z {z})");
    println!("  optimised barriers  take profit {tp_s:.2} sigma, stop {sl_s:.2} sigma");
    println!(
        "  probabilities       target {:.3}  stop {:.3}  timeout {:.3}",
        probs.take_profit, probs.stop_loss, probs.timeout
    );
    println!("  gross expected      {:+.1} bps", mean * 1e4);
    println!(
        "  costs               {:.1} bps  (fees {:.1} spread {:.1} impact {:.1} funding {:+.1})",
        costs.total * 1e4,
        costs.fees * 1e4,
        costs.spread * 1e4,
        costs.impact * 1e4,
        costs.funding * 1e4
    );
    println!("  net expected        {:+.1} bps", net * 1e4);
    println!("  outcome sd          {:.1} bps", var.sqrt() * 1e4);

    let size = size_position(
        &SizeInputs {
            edge: net,
            sigma_horizon: sigma_t,
            stop_distance: sl_s * sigma_t,
            hourly_volume: 90e6,
            portfolio_equity: 1_000_000.0,
            breadth: 3.0,
        },
        &SizingConfig::default(),
    );
    println!(
        "  size                {:.4} of equity, bound by {}",
        size.fraction, size.binding_constraint
    );

    // The hurdle is 4% of horizon volatility, matching the Python config, so it
    // grows like sqrt(T) alongside the forecast. Extending the horizon dilutes
    // the fixed cost and nothing else: in the long-horizon limit the ratio of
    // edge to hurdle tends to IC * |z| / h, independent of T.
    let hurdle_sigma = 0.04_f64;
    let (min_h, curve) = minimum_viable_horizon(sigma_h, ic, z, fixed.total, funding_8h / 8.0, hurdle_sigma, sigma_h);
    println!("\nNet edge by horizon  (fixed costs do not scale with T; the forecast grows like sqrt(T))");
    for (t, v) in &curve {
        let hurdle = (hurdle_sigma * sigma_h * t.sqrt()).max(0.0009);
        let mark = if *v >= hurdle { "  <- clears its hurdle" } else { "" };
        println!("  {:5.0}h  {:+7.1} bps   hurdle {:5.1} bps{}", t, v * 1e4, hurdle * 1e4, mark);
    }
    println!(
        "  long-horizon limit of edge/hurdle = IC*|z|/h = {:.2}  ({})",
        ic * z / hurdle_sigma,
        if ic * z / hurdle_sigma > 1.0 { "viable given enough horizon" } else { "no horizon rescues this IC" }
    );
    println!(
        "  minimum viable horizon: {}",
        if min_h.is_finite() { format!("{min_h:.0}h") } else { "none in range".into() }
    );
}
