"""Live Nobitex watchlist with the Aria Futures Demo indicator set.

Pulls real prices from Nobitex (apiv2.nobitex.ir) for the watchlist coins,
computes the same indicators as khodemadi/aria-futures-demo-source
(app/advanced-chart.tsx: SMA20, EMA20, Bollinger, Ichimoku 9/26/52, RSI14,
MACD 12/26/9, ATR14, Stochastic 14/3, OBV) on daily candles, cross-checks
the price against Binance the way the Aria demo does, and writes a Markdown
watchlist. Stdlib only, so it runs on a bare GitHub-hosted runner.
"""

import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

NOBITEX = "https://apiv2.nobitex.ir"
BINANCE_ENDPOINTS = [
    ("Binance USDⓈ-M futures", "https://fapi.binance.com/fapi/v1/ticker/price?symbol={s}USDT"),
    ("Binance spot", "https://data-api.binance.vision/api/v3/ticker/price?symbol={s}USDT"),
]

# Level each coin was said to have broken (or needs to break) in the old analysis.
WATCHLIST = [
    ("SOL", ["SOL"], 75.0, "claimed breakout above ~75"),
    ("AAVE", ["AAVE"], 87.0, "claimed exit from Kumo at ~87"),
    ("POL", ["POL", "MATIC"], 0.075, "claimed higher lows above ~0.075"),
    ("ARB", ["ARB"], None, "claimed ~+10% day"),
    ("WLD", ["WLD"], None, "needs resistance breakout"),
    ("TRX", ["TRX"], None, "added for comparison"),
]
LEADERS = [("BTC", ["BTC"]), ("ETH", ["ETH"])]


def get_json(url, timeout=15):
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "watchlist/1.0"}
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            last_error = error
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{url}: {last_error}")


def nobitex_daily(symbol, days=220):
    now = int(time.time())
    url = (
        f"{NOBITEX}/market/udf/history?symbol={symbol}USDT&resolution=D"
        f"&from={now - days * 86400}&to={now}"
    )
    data = get_json(url)
    if data.get("s") != "ok" or not data.get("c"):
        raise RuntimeError(f"no candles for {symbol}USDT: {data.get('s')}")
    return [
        {"t": t, "open": float(o), "high": float(h), "low": float(l),
         "close": float(c), "volume": float(v)}
        for t, o, h, l, c, v in zip(data["t"], data["o"], data["h"], data["l"],
                                    data["c"], data["v"])
    ]


def nobitex_stats(symbols):
    src = ",".join(s.lower() for s in symbols)
    data = get_json(f"{NOBITEX}/market/stats?srcCurrency={src}&dstCurrency=usdt")
    return data.get("stats", {})


def binance_price(symbol):
    for name, template in BINANCE_ENDPOINTS:
        try:
            return name, float(get_json(template.format(s=symbol), timeout=8)["price"])
        except Exception:  # geo-blocked (451) or unlisted: try the next source
            continue
    return None, None


# --- Indicators, ported 1:1 from aria-futures-demo-source/app/advanced-chart.tsx ---

def sma(values, period):
    out, window = [None] * len(values), []
    for i, v in enumerate(values):
        if v is None:
            window = []
            continue
        window.append(v)
        if len(window) > period:
            window.pop(0)
        if len(window) == period:
            out[i] = sum(window) / period
    return out


def ema(values, period):
    out, seed, prev = [None] * len(values), [], None
    k = 2 / (period + 1)
    for i, v in enumerate(values):
        if v is None:
            continue
        if prev is None:
            seed.append(v)
            if len(seed) < period:
                continue
            seed = seed[-period:]
            prev = sum(seed) / period
        else:
            prev = v * k + prev * (1 - k)
        out[i] = prev
    return out


def midpoint(candles, i, period):
    if i < period - 1:
        return None
    rng = candles[i - period + 1:i + 1]
    return (max(c["high"] for c in rng) + min(c["low"] for c in rng)) / 2


def indicators(candles):
    n = len(candles)
    closes = [c["close"] for c in candles]
    out = [dict(c) for c in candles]
    s20, e20, e12, e26 = sma(closes, 20), ema(closes, 20), ema(closes, 12), ema(closes, 26)
    macd = [a - b if a is not None and b is not None else None for a, b in zip(e12, e26)]
    signal = ema(macd, 9)
    gain = loss = atr = 0.0
    obv = 0.0
    stoch = [None] * n
    for i, c in enumerate(candles):
        o = out[i]
        o["sma20"], o["ema20"] = s20[i], e20[i]
        if i >= 19:
            window = closes[i - 19:i + 1]
            dev = math.sqrt(sum((x - s20[i]) ** 2 for x in window) / 20)
            o["bbUpper"], o["bbLower"] = s20[i] + 2 * dev, s20[i] - 2 * dev
        o["tenkan"], o["kijun"] = midpoint(candles, i, 9), midpoint(candles, i, 26)
        span_b = midpoint(candles, i, 52)
        # Cloud under today's candle = spans computed 26 bars ago.
        j = i - 26
        if j >= 0:
            t, k = midpoint(candles, j, 9), midpoint(candles, j, 26)
            o["spanA"] = (t + k) / 2 if t is not None and k is not None else None
            o["spanB"] = midpoint(candles, j, 52)
        # Cloud 26 bars ahead (from today's values).
        if o["tenkan"] is not None and o["kijun"] is not None:
            o["futureSpanA"] = (o["tenkan"] + o["kijun"]) / 2
        o["futureSpanB"] = span_b
        if i > 0:
            ch = c["close"] - candles[i - 1]["close"]
            g, l = max(0, ch), max(0, -ch)
            if i <= 14:
                gain += g
                loss += l
                if i == 14:
                    gain /= 14
                    loss /= 14
            else:
                gain = (gain * 13 + g) / 14
                loss = (loss * 13 + l) / 14
            if i >= 14:
                o["rsi"] = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
            obv += c["volume"] if ch > 0 else -c["volume"] if ch < 0 else 0
        o["obv"] = obv
        prev = candles[i - 1]["close"] if i else c["close"]
        tr = max(c["high"] - c["low"], abs(c["high"] - prev), abs(c["low"] - prev))
        if i < 14:
            atr += tr
            if i == 13:
                atr /= 14
                o["atr"] = atr
        else:
            atr = (atr * 13 + tr) / 14
            o["atr"] = atr
        if i >= 13:
            rng = candles[i - 13:i + 1]
            hi, lo = max(x["high"] for x in rng), min(x["low"] for x in rng)
            stoch[i] = 50 if hi == lo else (c["close"] - lo) / (hi - lo) * 100
            o["stochK"] = stoch[i]
        o["macd"], o["macdSignal"] = macd[i], signal[i]
        if macd[i] is not None and signal[i] is not None:
            o["macdHist"] = macd[i] - signal[i]
    for i, v in enumerate(sma(stoch, 3)):
        out[i]["stochD"] = v
    return out


# --- Bayesian read of the trend -------------------------------------------------

def beta_up_probability(candles, prior_days=90, recent_days=14):
    """Beta-Binomial: prior from the last ~90 days of up/down closes, updated
    with the last 14 days as the evidence. Returns (prior mean, posterior mean)."""
    ups = [candles[i]["close"] > candles[i - 1]["close"] for i in range(1, len(candles))]
    prior, recent = ups[-(prior_days + recent_days):-recent_days], ups[-recent_days:]
    a0, b0 = 1 + sum(prior), 1 + len(prior) - sum(prior)
    a1, b1 = a0 + sum(recent), b0 + len(recent) - sum(recent)
    return a0 / (a0 + b0), a1 / (a1 + b1)


def classify(last, candles):
    close = last["close"]
    cloud = [x for x in (last.get("spanA"), last.get("spanB")) if x is not None]
    if len(cloud) == 2:
        top, bottom = max(cloud), min(cloud)
        kumo = "above" if close > top else "below" if close < bottom else "inside"
    else:
        top = bottom = None
        kumo = "n/a"
    prior_high = max(c["high"] for c in candles[-21:-1])
    prior_low = min(c["low"] for c in candles[-21:-1])
    score = 0
    score += {"above": 2, "inside": 0, "below": -2}.get(kumo, 0)
    score += 1 if (last.get("tenkan") or 0) > (last.get("kijun") or 0) else -1
    score += 1 if close > (last.get("ema20") or close) else -1
    score += 1 if (last.get("macdHist") or 0) > 0 else -1
    rsi = last.get("rsi") or 50
    score += 1 if rsi > 55 else -1 if rsi < 45 else 0
    if close > prior_high:
        structure = "20-day breakout"
    elif close < prior_low:
        structure = "20-day breakdown"
    else:
        structure = "inside 20-day range"
    if score >= 4:
        bias = "Bullish (long bias; wait for a pullback)"
    elif score >= 1:
        bias = "Leaning bullish / needs confirmation"
    elif score > -2:
        bias = "Neutral / range"
    elif score > -4:
        bias = "Leaning bearish"
    else:
        bias = "Bearish (shorts not invalidated)"
    return {"kumo": kumo, "kumoTop": top, "kumoBottom": bottom, "score": score,
            "bias": bias, "structure": structure, "high20": prior_high, "low20": prior_low}


def fmt(x, ref=None):
    if x is None:
        return "–"
    ref = abs(ref if ref is not None else x)
    digits = 2 if ref >= 10 else 4 if ref >= 0.1 else 6
    return f"{x:,.{digits}f}"


def analyse(name, candidates, stats):
    for sym in candidates:
        try:
            candles = nobitex_daily(sym)
            break
        except Exception as error:
            print(f"[warn] {sym}: {error}", file=sys.stderr)
    else:
        return {"name": name, "error": "no Nobitex USDT market data"}
    live = stats.get(f"{sym.lower()}-usdt", {})
    latest = float(live["latest"]) if live.get("latest") else candles[-1]["close"]
    # Replace today's close by the live last trade so indicators use the live price.
    candles[-1]["close"] = latest
    candles[-1]["high"] = max(candles[-1]["high"], latest)
    candles[-1]["low"] = min(candles[-1]["low"], latest)
    rows = indicators(candles)
    last = rows[-1]
    view = classify(last, candles)
    prior, posterior = beta_up_probability(candles)
    src, bn = binance_price(sym)
    day_change = float(live["dayChange"]) if live.get("dayChange") else (
        (latest / candles[-2]["close"] - 1) * 100)
    return {"name": name, "symbol": f"{sym}USDT", "price": latest, "dayChange": day_change,
            "dayHigh": float(live.get("dayHigh") or candles[-1]["high"]),
            "dayLow": float(live.get("dayLow") or candles[-1]["low"]),
            "volume": float(live.get("volumeDst") or 0), "last": last,
            "prior": prior, "posterior": posterior, "binance": bn, "binanceSource": src,
            "candles": len(candles), "lastCandle": candles[-1]["t"], **view}


HEADER = ("| Asset | Nobitex (USDT) | 24h % | Binance | Kumo (bottom–top) | Tenkan/Kijun | EMA20 | "
          "RSI14 | MACD hist | ATR14 | 20d range | Structure | P(up) prior→post | Score | Bias |")
SEP = "|" + "---|" * 15


def row(r):
    if "error" in r:
        return f"| {r['name']} | {r['error']} |" + " |" * 13
    l, p = r["last"], r["price"]
    bn = f"{fmt(r['binance'], p)} ({(p / r['binance'] - 1) * 100:+.2f}%)" if r["binance"] else "n/a"
    return (
        f"| {r['name']} | {fmt(p)} | {r['dayChange']:+.2f}% | {bn} | {r['kumo']} "
        f"({fmt(r['kumoBottom'], p)}–{fmt(r['kumoTop'], p)}) | {fmt(l.get('tenkan'), p)}/"
        f"{fmt(l.get('kijun'), p)} | {fmt(l.get('ema20'), p)} | {l.get('rsi', 0):.1f} | "
        f"{fmt(l.get('macdHist'), p)} | {fmt(l.get('atr'), p)} | {fmt(r['low20'], p)}–{fmt(r['high20'], p)} | "
        f"{r['structure']} | {r['prior']:.2f}→{r['posterior']:.2f} | {r['score']:+d} | {r['bias']} |")


def render(results, leaders):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# Live Nobitex watchlist — {now}", "",
             "Source: apiv2.nobitex.ir (market/stats + daily UDF candles). Indicators "
             "ported from aria-futures-demo-source. Binance cross-check as in the Aria demo.", "",
             "## Leaders", "", HEADER, SEP]
    lines += [row(r) for r in leaders]
    lines += ["", "## Watchlist", "", HEADER, SEP]
    lines += [row(r) for r in results]
    lines += ["", "## Claims from the previous write-up vs live data", ""]
    for (name, _, level, claim), r in zip(WATCHLIST, results):
        if "error" in r:
            continue
        verdict = ""
        if level is not None:
            verdict = f"price {'ABOVE' if r['price'] > level else 'BELOW'} {level} ({(r['price'] / level - 1) * 100:+.1f}%)"
        elif name == "ARB":
            verdict = f"24h change is {r['dayChange']:+.2f}%"
        elif name == "TRX":
            verdict = f"20d range {fmt(r['low20'])}–{fmt(r['high20'])}; {r['structure']}"
        elif name == "WLD":
            verdict = f"20d high (resistance) {fmt(r['high20'])}; {r['structure']}"
        lines.append(f"- **{name}** — {claim}: {verdict}; Kumo {r['kumo']}, bias {r['bias']}.")
    lines += ["", "Educational only, not financial advice."]
    return "\n".join(lines)


def main():
    symbols = sorted({s for _, c, *_ in WATCHLIST for s in c} | {s for _, c in LEADERS for s in c})
    try:
        stats = nobitex_stats(symbols)
    except Exception as error:
        print(f"[warn] stats: {error}", file=sys.stderr)
        stats = {}
    results = [analyse(name, cands, stats) for name, cands, *_ in WATCHLIST]
    leaders = [analyse(name, cands, stats) for name, cands in LEADERS]
    report = render(results, leaders)
    print(report)
    out_dir = os.environ.get("WATCHLIST_OUT", "output")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "watchlist.md"), "w") as f:
        f.write(report + "\n")
    with open(os.path.join(out_dir, "watchlist.json"), "w") as f:
        json.dump({"stats": stats, "watchlist": results, "leaders": leaders}, f, indent=2, default=str)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(report + "\n")
    if all("error" in r for r in results):
        sys.exit("No live data could be fetched from Nobitex")


if __name__ == "__main__":
    main()
