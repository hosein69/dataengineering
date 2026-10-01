"""Deep single-asset analysis on live Nobitex data.

Adds to watchlist.py: 4h timeframe, ADX/DMI, Supertrend, Donchian 20/55,
volume regime, live order-book depth/imbalance, a per-coin barrier backtest
of each setup (win rate with a Beta posterior and 90% credible interval,
expectancy in R) and a concrete trade plan with position size and the
highest leverage whose liquidation stays well beyond the stop.

Usage: python deep_analysis.py AAVE ZEC
"""

import os
import random
import sys
import time

from watchlist import NOBITEX, binance_price, classify, fmt, get_json, indicators, nobitex_stats

RISK_PER_TRADE = 0.01      # 1% of account per trade
LIQ_BUFFER = 2.0           # liquidation must be >= 2x the stop distance away
MAINT_MARGIN = 0.01        # rough maintenance-margin allowance


def candles(symbol, resolution, bars):
    seconds = {"D": 86400, "240": 14400, "60": 3600}[resolution]
    now = int(time.time())
    data = get_json(f"{NOBITEX}/market/udf/history?symbol={symbol}USDT&resolution={resolution}"
                    f"&from={now - bars * seconds}&to={now}")
    if data.get("s") != "ok" or not data.get("c"):
        raise RuntimeError(f"no {resolution} candles for {symbol}USDT")
    return [{"t": t, "open": float(o), "high": float(h), "low": float(l), "close": float(c),
             "volume": float(v)}
            for t, o, h, l, c, v in zip(data["t"], data["o"], data["h"], data["l"], data["c"], data["v"])]


def wilder(values, period):
    out, acc = [None] * len(values), None
    for i, v in enumerate(values):
        if i < period:
            continue
        if acc is None:
            acc = sum(values[1:period + 1]) / period
        else:
            acc = (acc * (period - 1) + v) / period
        out[i] = acc
    return out


def adx(cs, period=14):
    n = len(cs)
    tr, pdm, mdm = [0.0] * n, [0.0] * n, [0.0] * n
    for i in range(1, n):
        h, l, pc = cs[i]["high"], cs[i]["low"], cs[i - 1]["close"]
        up, dn = h - cs[i - 1]["high"], cs[i - 1]["low"] - l
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
        pdm[i] = up if up > dn and up > 0 else 0.0
        mdm[i] = dn if dn > up and dn > 0 else 0.0
    atr_, p_, m_ = wilder(tr, period), wilder(pdm, period), wilder(mdm, period)
    pdi = [100 * p / a if a else None for p, a in zip(p_, atr_)]
    mdi = [100 * m / a if a else None for m, a in zip(m_, atr_)]
    dx = [100 * abs(p - m) / (p + m) if p is not None and m is not None and p + m else 0.0
          for p, m in zip(pdi, mdi)]
    first = next((i for i, v in enumerate(pdi) if v is not None), n)
    adx_, acc = [None] * n, None
    for i in range(first + period, n):
        acc = (sum(dx[first + 1:first + period + 1]) / period if acc is None
               else (acc * (period - 1) + dx[i]) / period)
        adx_[i] = acc
    return adx_, pdi, mdi


def supertrend(rows, mult=3.0):
    """Supertrend on the ATR14 already computed by indicators()."""
    trend, upper, lower = [None] * len(rows), None, None
    for i, r in enumerate(rows):
        a = r.get("atr")
        if a is None:
            continue
        mid = (r["high"] + r["low"]) / 2
        bu, bl = mid + mult * a, mid - mult * a
        prev_close = rows[i - 1]["close"]
        upper = bu if upper is None or bu < upper or prev_close > upper else upper
        lower = bl if lower is None or bl > lower or prev_close < lower else lower
        prev = trend[i - 1] if i else None
        if prev is None:
            trend[i] = ("up", lower) if r["close"] > upper else ("down", upper)
        elif prev[0] == "up":
            trend[i] = ("down", upper) if r["close"] < lower else ("up", lower)
        else:
            trend[i] = ("up", lower) if r["close"] > upper else ("down", upper)
    return trend


def orderbook(symbol, price):
    data = get_json(f"{NOBITEX}/v3/orderbook/{symbol}USDT")
    bids = sorted(((float(p), float(q)) for p, q in data.get("bids", [])), reverse=True)
    asks = sorted((float(p), float(q)) for p, q in data.get("asks", []))
    if not bids or not asks:
        return None
    def depth(side, pct, is_bid):
        lim = price * (1 - pct) if is_bid else price * (1 + pct)
        return sum(p * q for p, q in side if (p >= lim if is_bid else p <= lim))
    out = {"bestBid": bids[0][0], "bestAsk": asks[0][0],
           "spreadPct": (asks[0][0] - bids[0][0]) / price * 100}
    for pct in (0.01, 0.02, 0.05):
        b, a = depth(bids, pct, True), depth(asks, pct, False)
        out[f"bid{int(pct*100)}"], out[f"ask{int(pct*100)}"] = b, a
        out[f"imb{int(pct*100)}"] = (b - a) / (b + a) if b + a else 0
    # biggest single walls within 5%
    out["bidWall"] = max((x for x in bids if x[0] >= price * 0.95), key=lambda x: x[0] * x[1], default=None)
    out["askWall"] = max((x for x in asks if x[0] <= price * 1.05), key=lambda x: x[0] * x[1], default=None)
    return out


# --- setups and barrier backtest ------------------------------------------------

def kumo_top(r):
    v = [x for x in (r.get("spanA"), r.get("spanB")) if x is not None]
    return max(v) if len(v) == 2 else None


def setups(rows, i):
    r = rows[i]
    a, top = r.get("atr"), kumo_top(r)
    if a is None or top is None or r.get("kijun") is None or r.get("tenkan") is None or i < 21:
        return set()
    hi20 = max(x["high"] for x in rows[i - 20:i])
    s = set()
    if r["close"] > top and r["tenkan"] >= r["kijun"] and abs(r["close"] - r["kijun"]) <= a:
        s.add("PULLBACK_TO_KIJUN")
    if r["close"] > hi20 and r["close"] > top:
        s.add("BREAKOUT_20D")
    if (r["close"] > top and r["close"] > (r.get("ema20") or 1e18) and (r.get("macdHist") or 0) > 0
            and 50 <= (r.get("rsi") or 0) <= 70):
        s.add("MOMENTUM")
    if r["close"] > top and r["close"] < r["tenkan"] and (r.get("macdHist") or 0) < 0:
        s.add("UPTREND_CORRECTION")
    if r["close"] < top and r["close"] < r["kijun"]:
        s.add("BELOW_KIJUN_OR_CLOUD")
    return s


def barrier_test(rows, name, stop_atr=1.5, target_atr=3.0, horizon=20):
    """Long at close; stop = -stop_atr*ATR, target = +target_atr*ATR (2R).
    Same-bar hit of both counts as a loss. No overlapping trades."""
    wins = losses = 0
    rs, i = [], 60
    while i < len(rows) - 1:
        if name not in setups(rows, i):
            i += 1
            continue
        e, a = rows[i]["close"], rows[i]["atr"]
        stop, tgt, risk = e - stop_atr * a, e + target_atr * a, stop_atr * a
        result, j = None, i + 1
        while j < len(rows) and j <= i + horizon:
            if rows[j]["low"] <= stop:
                result = -1.0
                break
            if rows[j]["high"] >= tgt:
                result = target_atr / stop_atr
                break
            j += 1
        if result is None:
            if j >= len(rows):  # still open: ignore
                break
            result = (rows[min(j, len(rows) - 1)]["close"] - e) / risk
        rs.append(result)
        wins += result > 0
        losses += result <= 0
        i = j + 1
    n = wins + losses
    if not n:
        return {"n": 0}
    samples = sorted(random.betavariate(1 + wins, 1 + losses) for _ in range(20000))
    return {"n": n, "wins": wins, "post": (1 + wins) / (2 + n),
            "lo": samples[1000], "hi": samples[19000], "expR": sum(rs) / n}


def plan(rows, rows4h, ob):
    r, a = rows[-1], rows[-1]["atr"]
    price = r["close"]
    kij, ten, ema20 = r["kijun"], r["tenkan"], r["ema20"]
    hi20 = max(x["high"] for x in rows[-21:-1])
    lo20 = min(x["low"] for x in rows[-21:-1])
    # Entry: confluence of Kijun / EMA20 under price, otherwise a reclaim of the higher one.
    supports = sorted([x for x in (kij, ema20, ten) if x and x < price], reverse=True)
    if supports and (price - supports[0]) <= 0.6 * a:
        entry_lo, entry_hi = supports[0] - 0.25 * a, price
        kind = "buy the support zone"
    elif supports:
        entry_lo, entry_hi = supports[0] - 0.25 * a, supports[0] + 0.25 * a
        kind = "limit at pullback"
    else:
        trig = max(x for x in (kij, ema20) if x)
        entry_lo, entry_hi = trig, trig + 0.3 * a
        kind = "only after a daily close back above"
    entry = (entry_lo + entry_hi) / 2
    structural = min(kij, ema20) - 0.5 * a
    stop = min(structural, entry - 1.0 * a)
    stop = max(stop, entry - 2.0 * a)
    risk = (entry - stop) / entry
    t1 = ten if ten and ten > entry * 1.02 else hi20
    t2 = hi20 if hi20 > t1 * 1.01 else hi20 + a
    t3 = hi20 + 2 * a
    max_lev = max(1, int(1 / (LIQ_BUFFER * risk + MAINT_MARGIN)))
    return {"kind": kind, "entryLo": entry_lo, "entryHi": entry_hi, "entry": entry, "stop": stop,
            "riskPct": risk * 100, "t1": t1, "t2": t2, "t3": t3,
            "rr1": (t1 - entry) / (entry - stop), "rr2": (t2 - entry) / (entry - stop),
            "rr3": (t3 - entry) / (entry - stop),
            "sizePct": RISK_PER_TRADE / risk * 100, "maxLev": min(max_lev, 5),
            "hi20": hi20, "lo20": lo20, "invalid": min(kij, ema20) - 0.5 * a}


def analyse(sym, stats):
    d = candles(sym, "D", 700)
    h4 = candles(sym, "240", 300)
    live = stats.get(f"{sym.lower()}-usdt", {})
    price = float(live["latest"]) if live.get("latest") else d[-1]["close"]
    for cs in (d, h4):
        cs[-1]["close"] = price
        cs[-1]["high"], cs[-1]["low"] = max(cs[-1]["high"], price), min(cs[-1]["low"], price)
    rd, r4 = indicators(d), indicators(h4)
    ad, pdi, mdi = adx(d)
    a4, p4, m4 = adx(h4)
    st, st4 = supertrend(rd), supertrend(r4)
    vols = [c["volume"] for c in d]
    vol_ratio = vols[-2] / (sum(vols[-22:-2]) / 20) if sum(vols[-22:-2]) else None  # last closed day
    try:
        ob = orderbook(sym, price)
    except Exception as error:
        print(f"[warn] orderbook {sym}: {error}", file=sys.stderr)
        ob = None
    bt = {name: barrier_test(rd, name) for name in
          ("PULLBACK_TO_KIJUN", "BREAKOUT_20D", "MOMENTUM", "UPTREND_CORRECTION", "BELOW_KIJUN_OR_CLOUD")}
    return {"sym": sym, "price": price, "live": live, "d": rd, "h4": r4, "adx": (ad[-1], pdi[-1], mdi[-1]),
            "adx4": (a4[-1], p4[-1], m4[-1]), "st": st[-1], "st4": st4[-1], "volRatio": vol_ratio,
            "don55": (max(c["high"] for c in d[-56:-1]), min(c["low"] for c in d[-56:-1])),
            "ob": ob, "bt": bt, "active": setups(rd, len(rd) - 1), "view": classify(rd[-1], d),
            "view4": classify(r4[-1], h4), "plan": plan(rd, r4, ob), "binance": binance_price(sym)[1],
            "days": len(d)}


def render(x):
    p, r, r4, pl = x["price"], x["d"][-1], x["h4"][-1], x["plan"]
    f = lambda v: fmt(v, p)
    ch = x["live"].get("dayChange")
    L = [f"## {x['sym']}/USDT — {f(p)}" + (f" ({float(ch):+.2f}% 24h)" if ch else ""), ""]
    if x["binance"]:
        L.append(f"Binance {f(x['binance'])} → Nobitex premium {(p / x['binance'] - 1) * 100:+.2f}%  ")
    L.append(f"History: {x['days']} daily candles on Nobitex")
    L += ["", "| Timeframe | Kumo | Tenkan/Kijun | EMA20 | RSI | MACD hist | ATR | ADX (+DI/−DI) | Supertrend | Score |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for tf, row, v, ad, st in (("1D", r, x["view"], x["adx"], x["st"]), ("4H", r4, x["view4"], x["adx4"], x["st4"])):
        L.append(f"| {tf} | {v['kumo']} ({f(v['kumoBottom'])}–{f(v['kumoTop'])}) | {f(row.get('tenkan'))}/"
                 f"{f(row.get('kijun'))} | {f(row.get('ema20'))} | {row.get('rsi', 0):.1f} | "
                 f"{f(row.get('macdHist'))} | {f(row.get('atr'))} ({row['atr'] / p * 100:.1f}%) | "
                 f"{(ad[0] or 0):.1f} ({(ad[1] or 0):.1f}/{(ad[2] or 0):.1f}) | "
                 f"{st[0] if st else '–'} @ {f(st[1]) if st else '–'} | {v['score']:+d} |")
    L += ["", f"- Donchian 20D: {f(x['view']['low20'])}–{f(x['view']['high20'])}; 55D: "
          f"{f(x['don55'][1])}–{f(x['don55'][0])}",
          f"- Last closed day volume vs 20D avg: {x['volRatio']:.2f}×" if x["volRatio"] else "- Volume: n/a",
          f"- Future Kumo (26 bars ahead): {f(r.get('futureSpanA'))} / {f(r.get('futureSpanB'))}",
          f"- Active setups now: {', '.join(sorted(x['active'])) or 'none'}"]
    ob = x["ob"]
    if ob:
        L += ["", "**Order book (live)**", "",
              f"- Spread {ob['spreadPct']:.3f}% (bid {f(ob['bestBid'])} / ask {f(ob['bestAsk'])})",
              f"- Depth ±1%: bids {ob['bid1']:,.0f} vs asks {ob['ask1']:,.0f} USDT (imbalance {ob['imb1']:+.2f})",
              f"- Depth ±2%: bids {ob['bid2']:,.0f} vs asks {ob['ask2']:,.0f} USDT (imbalance {ob['imb2']:+.2f})",
              f"- Depth ±5%: bids {ob['bid5']:,.0f} vs asks {ob['ask5']:,.0f} USDT (imbalance {ob['imb5']:+.2f})"]
        if ob["bidWall"]:
            L.append(f"- Largest bid wall ≤5%: {f(ob['bidWall'][0])} ({ob['bidWall'][0] * ob['bidWall'][1]:,.0f} USDT)")
        if ob["askWall"]:
            L.append(f"- Largest ask wall ≤5%: {f(ob['askWall'][0])} ({ob['askWall'][0] * ob['askWall'][1]:,.0f} USDT)")
    L += ["", "**Setup backtest on this coin's own daily history** (long, stop 1.5 ATR, target 3 ATR = 2R, 20-day horizon)", "",
          "| Setup | Active now | Trades | Wins | Win-rate posterior (90% CI) | Expectancy (R) |", "|---|---|---|---|---|---|"]
    for name, b in x["bt"].items():
        act = "✅" if name in x["active"] else ""
        if b["n"]:
            L.append(f"| {name} | {act} | {b['n']} | {b['wins']} | {b['post']:.2f} ({b['lo']:.2f}–{b['hi']:.2f}) | {b['expR']:+.2f} |")
        else:
            L.append(f"| {name} | {act} | 0 | – | – | – |")
    L += ["", "**Trade plan (long)**", "",
          f"- Entry: {pl['kind']} {f(pl['entryLo'])}–{f(pl['entryHi'])} (mid {f(pl['entry'])})",
          f"- Stop: {f(pl['stop'])} ({pl['riskPct']:.1f}% from entry); daily close below {f(pl['invalid'])} invalidates",
          f"- Targets: T1 {f(pl['t1'])} ({pl['rr1']:.1f}R), T2 {f(pl['t2'])} ({pl['rr2']:.1f}R), T3 {f(pl['t3'])} ({pl['rr3']:.1f}R)",
          f"- Size for 1% account risk: {pl['sizePct']:.1f}% of account notional",
          f"- Max leverage keeping liquidation ≥2× stop distance: {pl['maxLev']}×", ""]
    return "\n".join(L)


def main():
    syms = [s.upper() for s in (sys.argv[1:] or os.environ.get("DEEP_SYMBOLS", "AAVE ZEC").split())]
    random.seed(7)
    stats = nobitex_stats(syms)
    out = ["# Deep analysis (live Nobitex)", ""]
    for s in syms:
        try:
            out.append(render(analyse(s, stats)))
        except Exception as error:
            out.append(f"## {s}\n\nfailed: {error}\n")
    report = "\n".join(out)
    print(report)
    os.makedirs("output", exist_ok=True)
    with open("output/deep_analysis.md", "w") as fh:
        fh.write(report + "\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(report + "\n")


if __name__ == "__main__":
    main()
