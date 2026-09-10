//! Transaction cost model.
//!
//! Port of `orion_x/costs.py`. Three things distinguish it from the v4 model:
//!
//! * Funding is signed by side. A long pays a positive funding rate and
//!   *receives* a negative one; v4 charged `abs(funding_rate)` and therefore
//!   billed a position for income it was collecting.
//! * Impact follows the square-root law, `Y * sigma * sqrt(Q / V)`, which is
//!   the most robustly replicated regularity in market microstructure
//!   (Almgren et al. 2005; Toth et al. 2011, *Physical Review X* 1). A flat
//!   spread charge is only correct for a size that never walks the book.
//! * Both legs are charged. For a multi-hour crypto trade the exit is usually
//!   the more expensive one.

use serde::{Deserialize, Serialize};

use crate::barriers::{safe_div, EPS};

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct CostModel {
    pub taker_fee: f64,
    pub maker_fee: f64,
    pub maker_fill_ratio: f64,
    pub impact_prefactor: f64,
    pub slippage_floor: f64,
    pub borrow_rate_per_hour: f64,
}

impl Default for CostModel {
    fn default() -> Self {
        Self {
            taker_fee: 0.000_45,
            maker_fee: 0.000_15,
            maker_fill_ratio: 0.0,
            impact_prefactor: 0.8,
            slippage_floor: 0.000_05,
            borrow_rate_per_hour: 0.0,
        }
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct CostBreakdown {
    pub fees: f64,
    pub spread: f64,
    pub impact: f64,
    pub funding: f64,
    pub total: f64,
}

pub struct CostInputs {
    pub side: i32,
    pub notional: f64,
    pub hourly_volume: f64,
    pub sigma_per_hour: f64,
    pub spread_bps: f64,
    pub funding_rate_8h: f64,
    pub holding_hours: f64,
}

/// Round-trip cost as a fraction of notional. `funding` may be negative when
/// funding is being received; every other component is always a cost.
pub fn estimate_costs(inp: &CostInputs, model: &CostModel) -> CostBreakdown {
    let fee_rate = model.maker_fill_ratio * model.maker_fee
        + (1.0 - model.maker_fill_ratio) * model.taker_fee;
    let fees = 2.0 * fee_rate;
    let spread = 2.0 * (inp.spread_bps.max(0.0) / 10_000.0) / 2.0;

    let participation = safe_div(inp.notional.abs(), inp.hourly_volume.max(EPS), 0.0);
    let impact = 2.0 * model.impact_prefactor * inp.sigma_per_hour.max(EPS) * participation.max(0.0).sqrt()
        + 2.0 * model.slippage_floor;

    let intervals = inp.holding_hours.max(0.0) / 8.0;
    let funding = inp.side as f64 * inp.funding_rate_8h * intervals
        + model.borrow_rate_per_hour * inp.holding_hours.max(0.0);

    CostBreakdown { fees, spread, impact, funding, total: fees + spread + impact + funding }
}
