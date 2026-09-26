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
fn price(p: f64) -> String {
    if p >= 10.0 { format!("{p:.2}") }
    else if p >= 1.0 { format!("{p:.4}") }
    else { format!("{p:.7}") }
}
fn entry_levels(candles: &Value, now: u64, bid: f64, ask: f64, buy_enabled: bool, sell_enabled: bool)
    -> Option<(&'static str, f64, f64, f64, f64)> {
    let (times, highs, lows, closes) = (
        candles["t"].as_array()?, candles["h"].as_array()?,
        candles["l"].as_array()?, candles["c"].as_array()?,
    );
    if times.len() != highs.len() || highs.len() != lows.len() || lows.len() != closes.len() { return None; }
    let bars: Vec<(u64, f64, f64, f64)> = (0..times.len()).filter_map(|i| {
        let (t, h, l, c) = (num(&times[i])? as u64, num(&highs[i])?, num(&lows[i])?, num(&closes[i])?);
        (t + 3600 <= now && h >= l && l > 0.0 && c > 0.0).then_some((t, h, l, c))
    }).collect();
    if bars.len() < 20 || now.abs_diff(bars.last()?.0 + 3600) > 7200 { return None; }
    let recent = &bars[bars.len()-15..];
    let mut tr = Vec::new();
    for w in recent.windows(2) {
        tr.push((w[1].1-w[1].2).max((w[1].1-w[0].3).abs()).max((w[1].2-w[0].3).abs()));
    }
    let atr = tr.iter().sum::<f64>() / tr.len() as f64;
    let momentum = bars.last()?.3 / bars[bars.len()-5].3 - 1.0;
    let window = &bars[bars.len()-12..];
    let high = window.iter().map(|bar| bar.1).fold(0.0, f64::max);
    let low = window.iter().map(|bar| bar.2).fold(f64::INFINITY, f64::min);
    let mid = (ask + bid) / 2.0;
    let buffer = (mid * 0.0005).max((ask-bid) / 2.0);
    let risk = (1.5 * atr).max(3.0 * (ask-bid));
    if !risk.is_finite() || risk <= 0.0 { return None; }
    let (side, entry, stop, target, distance) = if momentum >= 0.002 && buy_enabled {
        let entry = high.max(ask) + buffer;
        ("خرید مشروط", entry, entry-risk, entry+1.8*risk, (entry/ask-1.0)*100.0)
    } else if momentum <= -0.002 && sell_enabled {
        let entry = low.min(bid) - buffer;
        ("فروش مشروط", entry, entry+risk, entry-1.8*risk, (1.0-entry/bid)*100.0)
    } else { return None; };
    (entry > 0.0 && stop > 0.0 && target > 0.0 && distance <= 2.5 && risk/entry <= 0.05)
        .then_some((side, entry, stop, target, distance))
}
fn main() -> Result<(), Box<dyn Error>> {
    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis() as u64;
    let markets = get("/margin/markets/list")?;
    let listings = markets["markets"].as_object().ok_or("invalid margin markets response")?;
    let stats = get("/market/stats")?;
    let stats = stats["stats"].as_object().ok_or("invalid stats response")?;
    let mut ranked: Vec<(String, f64, f64, f64, bool, bool)> = Vec::new();
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
        if turnover > 0.0 { ranked.push((symbol.clone(), turnover, change, max_lev,
            info["buyEnabled"] != false, info["sellEnabled"] != false)); }
    }
    ranked.sort_by(|a, b| b.1.total_cmp(&a.1));
    let mut output = Vec::new();
    let mut errors = HashMap::new();
    for (symbol, turnover, change, max_lev, buy_enabled, sell_enabled) in ranked.into_iter().take(20) {
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
        let hourly_from = to - 72 * 3600;
        let hourly = match get(&format!("/market/udf/history?symbol={symbol}&resolution=60&from={hourly_from}&to={to}")) {
            Ok(v) => v, Err(e) => { errors.insert(symbol, e.to_string()); continue; }
        };
        if hourly["s"] != "ok" { continue; }
        let Some((side, entry, stop, target, distance)) = entry_levels(
            &hourly, to, bid, ask, buy_enabled, sell_enabled) else { continue; };
        output.push((symbol, turnover, change, max_lev, spread_bp, vol_1d_pct,
            side, entry, stop, target, distance));
    }
    output.sort_by(|a, b| b.1.total_cmp(&a.1));
    println!("واچ‌لیست تعهدی نوبیتکس | زمان دریافت: {to} UTC", to=now/1000);
    println!("ورودها فقط پس از عبور قیمت از سطح و تأیید حرکت‌اند؛ اعتبار داده حداکثر چند دقیقه است.");
    println!("نماد | سمت | ورود پس از عبور | فاصله تا ورود % | حد ابطال | هدف ۱٫۸R | گردش USDT | اسپرد bp | نوسان GARCH % | سقف اهرم عمومی");
    for (symbol, turnover, _change, max_lev, spread, vol, side, entry, stop, target, distance) in output.iter().take(10) {
        println!("{symbol} | {side} | {} | {distance:.2} | {} | {} | {turnover:.0} | {spread:.1} | {vol:.2} | {max_lev:.1}×",
            price(*entry), price(*stop), price(*target));
    }
    if output.is_empty() {
        eprintln!("هیچ نمادی از فیلتر دادهٔ تازه، نقدشوندگی و ریسک عبور نکرد؛ خطاهای API: {errors:?}");
        std::process::exit(2);
    }
    Ok(())
}
