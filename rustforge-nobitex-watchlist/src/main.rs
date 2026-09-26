use risk::garch::{GarchEstimator, GarchState};
use serde_json::Value;
use std::{collections::HashMap, error::Error, thread, time::{Duration, SystemTime, UNIX_EPOCH}};

const API: &str = "https://apiv2.nobitex.ir";
const MAX_AGE_MS: u64 = 180_000;

fn get(path: &str) -> Result<Value, Box<dyn Error>> {
    let url = format!("{API}{path}");
    let response = ureq::get(&url).timeout(Duration::from_secs(15)).call()?;
    Ok(response.into_json()?)
}
fn num(v: &Value) -> Option<f64> {
    v.as_f64().or_else(|| v.as_str()?.parse::<f64>().ok()).filter(|n| n.is_finite())
}
fn field(v: &Value, names: &[&str]) -> Option<f64> {
    names.iter().find_map(|k| num(&v[*k]))
}
fn main() -> Result<(), Box<dyn Error>> {
    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis() as u64;
    let markets = get("/margin/markets/list")?;
    let listings = markets["markets"].as_object().ok_or("invalid margin markets response")?;
    let stats = get("/market/stats")?;
    let stats = stats["stats"].as_object().ok_or("invalid stats response")?;
    let mut ranked: Vec<(String, f64, f64, f64)> = Vec::new();
    for (symbol, info) in listings {
        if !symbol.ends_with("USDT") || info["active"] == false || info["isActive"] == false || (info["buyEnabled"] == false && info["sellEnabled"] == false) { continue; }
        let max_lev = field(info, &["maxLeverage"]).unwrap_or(0.0);
        if max_lev <= 1.0 { continue; }
        let src = symbol.trim_end_matches("USDT").to_lowercase();
        let key = format!("{src}-usdt");
        let Some(s) = stats.get(&key).or_else(|| stats.get(symbol)) else { continue; };
        if s["isClosed"] == true { continue; }
        let turnover = field(s, &["volumeDst", "volumeQuote"]).unwrap_or(0.0);
        let change = field(s, &["dayChange", "dayChangePercent"]).unwrap_or(0.0);
        if turnover > 0.0 { ranked.push((symbol.clone(), turnover, change, max_lev)); }
    }
    ranked.sort_by(|a, b| b.1.total_cmp(&a.1));
    let mut output = Vec::new();
    let mut errors = HashMap::new();
    for (symbol, turnover, change, max_lev) in ranked.into_iter().take(20) {
        thread::sleep(Duration::from_millis(1200)); // OHLC: under 60 requests/minute
        let ob = match get(&format!("/v3/orderbook/{symbol}")) {
            Ok(v) => v, Err(e) => { errors.insert(symbol, e.to_string()); continue; }
        };
        let updated = field(&ob, &["lastUpdate"]).unwrap_or(0.0) as u64;
        if updated == 0 || now.abs_diff(updated) > MAX_AGE_MS { continue; }
        let bid = ob["bids"].as_array().and_then(|a| a.first()).and_then(|a| num(&a[0]));
        let ask = ob["asks"].as_array().and_then(|a| a.first()).and_then(|a| num(&a[0]));
        let (Some(bid), Some(ask)) = (bid, ask) else { continue; };
        if bid <= 0.0 || ask < bid { continue; }
        let spread_bp = (ask - bid) / ((ask + bid) / 2.0) * 10_000.0;
        if spread_bp > 35.0 { continue; }
        let to = now / 1000;
        let from = to - 90 * 86400;
        let candles = match get(&format!("/market/udf/history?symbol={symbol}&resolution=D&from={from}&to={to}")) {
            Ok(v) => v, Err(e) => { errors.insert(symbol, e.to_string()); continue; }
        };
        if candles["s"] != "ok" { continue; }
        let (Some(close), Some(times)) = (candles["c"].as_array(), candles["t"].as_array()) else { continue; };
        if close.len() < 51 || times.len() != close.len() { continue; }
        let last_time = times.last().and_then(num).unwrap_or(0.0) as u64;
        if to.abs_diff(last_time) > 2 * 86400 { continue; }
        let prices: Vec<f64> = close.iter().filter_map(num).collect();
        if prices.len() != close.len() || prices.iter().any(|p| *p <= 0.0) { continue; }
        let returns: Vec<f64> = prices.windows(2).map(|p| (p[1] / p[0]).ln()).collect();
        let Some((params, _log_likelihood)) = GarchEstimator::fit(&returns) else { continue; };
        if !params.is_stationary() { continue; }
        let mut model = GarchState::from_returns(params, &returns);
        for value in &returns { model.update(*value); }
        let variance = model.forecast(1);
        if !variance.is_finite() || variance <= 0.0 { continue; }
        let vol_1d_pct = variance.sqrt() * 100.0;
        if vol_1d_pct > 12.0 { continue; }
        output.push((symbol, turnover, change, max_lev, spread_bp, vol_1d_pct));
    }
    output.sort_by(|a, b| b.1.total_cmp(&a.1));
    println!("واچ‌لیست تعهدی نوبیتکس | زمان دریافت: {to} UTC", to=now/1000);
    println!("نماد | گردش ۲۴ساعته USDT | تغییر روزانه % | سقف اهرم عمومی | اسپرد bp | نوسان روزانه GARCH %");
    for (symbol, turnover, change, max_lev, spread, vol) in output.iter().take(10) {
        println!("{symbol} | {turnover:.0} | {change:.2} | {max_lev:.1}× | {spread:.1} | {vol:.2}");
    }
    if output.is_empty() {
        eprintln!("هیچ نمادی از فیلتر دادهٔ تازه، نقدشوندگی و ریسک عبور نکرد؛ خطاهای API: {errors:?}");
        std::process::exit(2);
    }
    Ok(())
}
