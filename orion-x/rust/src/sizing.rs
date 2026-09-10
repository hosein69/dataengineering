//! Position sizing: the binding one of four independent caps.
//!
//! Port of `orion_x/sizing.py`. v4 sized with `risk_per_trade / stop_distance`
//! scaled by confidence, which has no dependence on the edge at all: a one
//! basis point edge and a hundred basis point edge produced identical size
//! whenever their stops were the same distance away.

use serde::{Deserialize, Serialize};

use crate::barriers::{clamp, safe_div, EPS};

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct SizingConfig {
    pub kelly_fraction: f64,
    pub max_risk_per_trade: f64,
    pub leverage_ceiling: f64,
    pub target_portfolio_vol: f64,
    pub max_participation: f64,
    pub horizon_hours: f64,
}

impl Default for SizingConfig {
    fn default() -> Self {
        Self {
            kelly_fraction: 0.25,
            max_risk_per_trade: 0.0075,
            leverage_ceiling: 1.5,
            target_portfolio_vol: 0.35,
            max_participation: 0.02,
            horizon_hours: 7.0,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SizeDecision {
    pub fraction: f64,
    pub binding_constraint: String,
    pub kelly_full: f64,
    pub vol_target_cap: f64,
    pub liquidity_cap: f64,
    pub risk_cap: f64,
}

pub struct SizeInputs {
    pub edge: f64,
    pub sigma_horizon: f64,
    pub stop_distance: f64,
    pub hourly_volume: f64,
    pub portfolio_equity: f64,
    pub breadth: f64,
}

/// Growth-optimal size, reduced to whichever constraint binds first.
///
/// Fractional Kelly is not decoration. With estimated rather than known
/// parameters, full Kelly sits above the growth optimum and can be growth
/// negative (MacLean, Thorp & Ziemba 2011).
pub fn size_position(inp: &SizeInputs, cfg: &SizingConfig) -> SizeDecision {
    let kelly_full = safe_div(inp.edge, inp.sigma_horizon.max(EPS).powi(2), 0.0);
    let breadth_scale = (0.5 + 0.5 * (inp.breadth.max(1.0) / 4.0).sqrt()).min(1.0);
    let kelly_used = (cfg.kelly_fraction * kelly_full * breadth_scale).max(0.0);

    let sigma_annual = inp.sigma_horizon * (8760.0 / cfg.horizon_hours.max(EPS)).sqrt();
    let vol_cap = safe_div(cfg.target_portfolio_vol, sigma_annual.max(EPS), 0.0);

    let max_notional = cfg.max_participation * inp.hourly_volume.max(0.0);
    let liq_cap = safe_div(max_notional, inp.portfolio_equity.max(EPS), 0.0);
    let risk_cap = safe_div(cfg.max_risk_per_trade, inp.stop_distance.max(1e-4), 0.0);

    let caps: [(&str, f64); 5] = [
        ("kelly", kelly_used),
        ("vol_target", vol_cap),
        ("liquidity", liq_cap),
        ("risk_limit", risk_cap),
        ("leverage_ceiling", cfg.leverage_ceiling),
    ];
    let (name, value) = caps
        .iter()
        .fold(("kelly", f64::INFINITY), |acc, &(n, v)| if v < acc.1 { (n, v) } else { acc });

    SizeDecision {
        fraction: clamp(value, 0.0, cfg.leverage_ceiling),
        binding_constraint: name.to_string(),
        kelly_full,
        vol_target_cap: vol_cap,
        liquidity_cap: liq_cap,
        risk_cap,
    }
}
