"""Precise entry zones ("نقطه‌زنی") on live Nobitex data.

Ranks support levels by confluence of independent methods and turns the best
ones into a limit-order ladder with stop, targets and a 1h entry trigger:

- Volume Profile on 1h candles (POC, value area high/low, high-volume nodes)
- Anchored VWAP from the impulse swing low (and from the latest swing high)
- Fibonacci retracements / extensions of the current impulse (daily and 4h)
- 4h fractal pivots, and old 4h resistances that price has since broken (flip zones)
- Ichimoku Kijun/Tenkan, EMA20 (1D and 4H), 4H Supertrend
- Live order-book bid walls
- Backtest on the coin's own daily history of buying the 0.5–0.618 Fibonacci pullback

Usage: python entry_zones.py AAVE
"""

import os
import random
import sys
import time

from deep_analysis import barrier_test, candles, orderbook, supertrend
from watchlist import binance_price, fmt, freshness_line, indicators, live_quote, nobitex_stats

WEIGHTS = {
    "POC": 3.0, "VAL": 2.0, "VAH": 1.5, "HVN": 1.5,
    "AVWAP_low": 2.5, "AVWAP_high": 1.5,
    "Fib0.382": 2.0, "Fib0.5": 2.0, "Fib0.618": 2.5, "Fib0.786": 1.5,
    "Kijun_1D": 2.0, "Tenkan_1D": 1.5, "EMA20_1D": 1.5,
    "Kijun_4H": 1.0, "EMA20_4H": 1.0, "Supertrend_4H": 1.5,
    "Pivot_low_4H": 1.5, "Flip_4H": 2.0, "BidWall": 1.0,
}


def volume_profile(cs, bins=80):
    lo, hi = min(c["low"] for c in cs), max(c["high"] for c in cs)
    step = (hi - lo) / bins or 1e-9
    vol = [0.0] * bins
    for c in cs:
        a = int((c["low"] - lo) / step)
        b = min(bins - 1, int((c["high"] - lo) / step))
        share = c["volume"] / (b - a + 1)
        for k in range(a, b + 1):
            vol[k] += share
    mid = lambda k: lo + (k + 0.5) * step
    poc = max(range(bins), key=lambda k: vol[k])
    total, inside, l, r = sum(vol), vol[poc], poc, poc
    while inside < 0.7 * total and (l > 0 or r < bins - 1):
        left = vol[l - 1] if l > 0 else -1
        right = vol[r + 1] if r < bins - 1 else -1
        if right >= left:
            r += 1
            inside += vol[r]
        else:
            l -= 1
            inside += vol[l]
    avg = total / bins
    hvn = [mid(k) for k in range(2, bins - 2)
           if vol[k] == max(vol[k - 2:k + 3]) and vol[k] > 1.3 * avg and k != poc]
    return {"POC": mid(poc), "VAH": mid(r), "VAL": mid(l), "HVN": hvn, "step": step}


def anchored_vwap(cs, start):
    pv = v = 0.0
    for c in cs[start:]:
        pv += (c["high"] + c["low"] + c["close"]) / 3 * c["volume"]
        v += c["volume"]
    return pv / v if v else None


def pivots(cs, k=2):
    highs, lows = [], []
    for i in range(k, len(cs) - k):
        w = cs[i - k:i + k + 1]
        if cs[i]["high"] == max(x["high"] for x in w):
            highs.append((i, cs[i]["high"]))
        if cs[i]["low"] == min(x["low"] for x in w):
            lows.append((i, cs[i]["low"]))
    return highs, lows


def impulse(cs, lookback):
    """Swing low -> highest high after it, within the lookback window."""
    seg = cs[-lookback:]
    hi_i = max(range(len(seg)), key=lambda i: seg[i]["high"])
    lo_i = min(range(hi_i + 1), key=lambda i: seg[i]["low"])
    off = len(cs) - lookback
    return off + lo_i, seg[lo_i]["low"], off + hi_i, seg[hi_i]["high"]


def rsi_series(cs):
    return [r.get("rsi") for r in indicators(cs)]


def trigger_1h(h1, zone_lo, zone_hi):
    """Entry trigger on 1h candles once price trades into the zone."""
    last = h1[-1]
    recent = h1[-12:]
    touched = any(c["low"] <= zone_hi for c in recent)
    if not touched:
        return "WAITING", f"price {(last['close'] / zone_hi - 1) * 100:+.1f}% above zone top"
    rsi = rsi_series(h1)
    signals = []
    # reclaim: a wick into the zone, then a 1h close back above the zone top
    if any(c["low"] <= zone_hi for c in h1[-6:-1]) and last["close"] > zone_hi:
        signals.append("1h reclaim of zone top")
    prev = h1[-2]
    if (last["close"] > last["open"] and prev["close"] < prev["open"]
            and last["close"] >= prev["open"] and last["open"] <= prev["close"]):
        signals.append("1h bullish engulfing")
    lows = [(i, h1[i]["low"]) for i in range(len(h1) - 30, len(h1))]
    a = min(lows[:15], key=lambda x: x[1])
    b = min(lows[15:], key=lambda x: x[1])
    if b[1] < a[1] and rsi[b[0]] and rsi[a[0]] and rsi[b[0]] > rsi[a[0]]:
        signals.append("1h bullish RSI divergence")
    if last["close"] < zone_lo:
        return "ZONE LOST", "1h close below zone: wait for the next zone"
    return ("TRIGGERED" if signals else "IN ZONE — no trigger yet"), ", ".join(signals) or "watch for reclaim/engulfing/divergence"


def fib_pullback_backtest(rows):
    """Daily uptrend; limit buy at Fib 0.5 of the 20D impulse when the day's low
    reaches it, stop at Fib 0.786, target the impulse high (or 2R if closer).
    Same-day stop and fill counts as a loss. No overlapping trades."""
    wins, rs, i = 0, [], 60
    while i < len(rows) - 1:
        r = rows[i]
        spans = [x for x in (r.get("spanA"), r.get("spanB")) if x is not None]
        if len(spans) < 2 or r.get("kijun") is None:
            i += 1
            continue
        lo_i, lo, hi_i, hi = impulse(rows[:i], 20)
        rng = hi - lo
        entry, stop = hi - 0.5 * rng, hi - 0.786 * rng
        uptrend = rows[i - 1]["close"] > max(spans) and rows[i - 1]["tenkan"] >= rows[i - 1]["kijun"]
        if not (uptrend and rng > 0 and hi_i > lo_i and rows[i]["low"] <= entry < rows[i - 1]["low"]):
            i += 1
            continue
        target = min(hi, entry + 2 * (entry - stop))
        result, j = None, i
        while j < len(rows) and j <= i + 20:
            if rows[j]["low"] <= stop:
                result = -1.0
                break
            if j > i and rows[j]["high"] >= target:
                result = (target - entry) / (entry - stop)
                break
            j += 1
        if result is None:
            if j >= len(rows):
                break
            result = (rows[j]["close"] - entry) / (entry - stop)
        rs.append(result)
        wins += result > 0
        i = j + 1
    n = len(rs)
    if not n:
        return {"n": 0}
    s = sorted(random.betavariate(1 + wins, 1 + n - wins) for _ in range(20000))
    return {"n": n, "wins": wins, "post": (1 + wins) / (2 + n), "lo": s[1000], "hi": s[19000],
            "expR": sum(rs) / n}


def analyse(sym, stats):
    d, h4, h1 = candles(sym, "D", 700), candles(sym, "240", 400), candles(sym, "60", 720)
    live = stats.get(f"{sym.lower()}-usdt", {})
    try:
        quote = live_quote(sym)
    except Exception as error:
        print(f"[warn] live quote {sym}: {error}", file=sys.stderr)
        quote = {"price": None, "last": None, "bid": None, "ask": None, "bookAge": None, "fetched": time.time()}
    price = quote["price"] or (float(live["latest"]) if live.get("latest") else h1[-1]["close"])
    fresh = freshness_line(quote, (("1h", h1, 2 * 3600), ("1D", d, 2 * 86400)))
    for cs in (d, h4, h1):
        cs[-1]["close"] = price
        cs[-1]["high"], cs[-1]["low"] = max(cs[-1]["high"], price), min(cs[-1]["low"], price)
    rd, r4 = indicators(d), indicators(h4)
    atr_d, atr_4 = rd[-1]["atr"], r4[-1]["atr"]
    levels = []

    def add(name, value, weight=None):
        if value and value < price and value > price - 4 * atr_d:
            levels.append((name, value, WEIGHTS[name] if weight is None else weight))

    vp = volume_profile(h1)
    for k in ("POC", "VAH", "VAL"):
        add(k, vp[k])
    for v in vp["HVN"]:
        add("HVN", v)
    # impulses: major (daily 55D) and minor (4h ~10 days)
    imps = {}
    for label, cs, lb, unit in (("1D", d, 55, atr_d), ("4H", h4, 60, atr_4)):
        for look in (lb, lb * 2, lb * 4):
            lo_i, lo, hi_i, hi = impulse(cs, min(look, len(cs)))
            if hi - lo >= 3 * unit:
                break
        imps[label] = (lo, hi, cs[lo_i]["t"], cs[hi_i]["t"])
        for f in (0.382, 0.5, 0.618, 0.786):
            add(f"Fib{f}", hi - f * (hi - lo), WEIGHTS[f"Fib{f}"] * (1.0 if label == "1D" else 0.8))
    # anchored VWAPs on 1h data from the minor swing low and the latest swing high
    lo_t, hi_t = imps["4H"][2], imps["4H"][3]
    in_h1 = lambda t: t >= h1[0]["t"]
    idx_lo = next((i for i, c in enumerate(h1) if c["t"] >= lo_t), None) if in_h1(lo_t) else None
    idx_hi = next((i for i, c in enumerate(h1) if c["t"] >= hi_t), None) if in_h1(hi_t) else None
    avwap_lo = anchored_vwap(h1, idx_lo) if idx_lo is not None else None
    avwap_hi = anchored_vwap(h1, idx_hi) if idx_hi is not None else None
    add("AVWAP_low", avwap_lo)
    add("AVWAP_high", avwap_hi)
    r = rd[-1]
    add("Kijun_1D", r.get("kijun"))
    add("Tenkan_1D", r.get("tenkan"))
    add("EMA20_1D", r.get("ema20"))
    add("Kijun_4H", r4[-1].get("kijun"))
    add("EMA20_4H", r4[-1].get("ema20"))
    st4 = supertrend(r4)[-1]
    if st4 and st4[0] == "up":
        add("Supertrend_4H", st4[1])
    ph, pl = pivots(h4)
    for i, v in pl[-8:]:
        add("Pivot_low_4H", v)
    for i, v in ph[:-1]:
        # old pivot high that was later exceeded by a close: resistance flipped to support
        if any(c["close"] > v for c in h4[i + 3:]) and v < price:
            add("Flip_4H", v, WEIGHTS["Flip_4H"] * (1 if i > len(h4) - 120 else 0.5))
    ob = None
    try:
        ob = orderbook(sym, price)
        if ob and ob["bidWall"]:
            add("BidWall", ob["bidWall"][0])
    except Exception as error:
        print(f"[warn] orderbook {sym}: {error}", file=sys.stderr)

    # cluster
    tol = 0.5 * atr_4
    levels.sort(key=lambda x: -x[1])
    zones = []
    for name, v, w in levels:
        if zones and zones[-1]["top"] - v <= tol:
            z = zones[-1]
        else:
            z = {"members": [], "top": v}
            zones.append(z)
        z["members"].append((name, v, w))
    for z in zones:
        vs = [m[1] for m in z["members"]]
        ws = [m[2] for m in z["members"]]
        best = {}
        for name, _, w in z["members"]:
            best[name] = max(best.get(name, 0), w)
        # each method counts once; repeats of the same method add only a small bonus
        z["score"] = sum(best.values()) + 0.25 * (len(z["members"]) - len(best))
        z["center"] = sum(a * b for a, b in zip(vs, ws)) / sum(ws)
        z["lo"], z["hi"] = min(vs) - 0.1 * atr_4, max(vs) + 0.1 * atr_4
        z["kinds"] = len({m[0].split("_")[0].replace("Fib0.", "Fib") for m in z["members"]})
    strong = [z for z in zones if z["score"] >= 5 and z["kinds"] >= 2]
    weak = len(strong) < 2
    if weak:
        strong = [z for z in zones if z["score"] >= 3]
    ladder = sorted(sorted(strong, key=lambda z: -z["score"])[:3], key=lambda z: -z["center"])
    plan = None
    if ladder:
        alloc = [0.3, 0.4, 0.3][:len(ladder)]
        alloc = [a / sum(alloc) for a in alloc]
        avg = sum(a * z["center"] for a, z in zip(alloc, ladder))
        deepest = ladder[-1]
        stop = deepest["lo"] - 0.35 * atr_d
        lo1, hi1 = imps["1D"][0], imps["1D"][1]
        targets = [("swing high", hi1), ("ext 1.272", lo1 + 1.272 * (hi1 - lo1)),
                   ("ext 1.618", lo1 + 1.618 * (hi1 - lo1))]
        risk = (avg - stop) / avg
        plan = {"alloc": alloc, "avg": avg, "stop": stop, "risk": risk, "targets": targets,
                "first_fill_rr": (hi1 - ladder[0]["center"]) / (ladder[0]["center"] - stop),
                "size": 0.01 / risk, "lev": max(1, min(5, int(1 / (2 * risk + 0.01))))}
    trig = trigger_1h(h1, ladder[0]["lo"], ladder[0]["hi"]) if ladder else ("n/a", "")
    random.seed(11)
    bt_fib = fib_pullback_backtest(rd)
    bt_pull = barrier_test(rd, "PULLBACK_TO_KIJUN")
    bt_mom = barrier_test(rd, "MOMENTUM")
    return {"fresh": fresh, "weak": weak, "sym": sym, "price": price, "live": live, "atr_d": atr_d, "atr_4": atr_4, "vp": vp,
            "imps": imps, "avwap": (avwap_lo, avwap_hi), "zones": zones, "ladder": ladder,
            "plan": plan, "trigger": trig, "ob": ob, "bt": {"FIB_0.5_PULLBACK (limit)": bt_fib,
            "PULLBACK_TO_KIJUN (close)": bt_pull, "MOMENTUM / chase (close)": bt_mom},
            "binance": binance_price(sym)[1], "h1_bars": len(h1)}


def render(x):
    p, f = x["price"], (lambda v: fmt(v, x["price"]))
    L = [f"## {x['sym']}/USDT entry zones — price {f(p)}", "", x["fresh"] + "  "]
    if x["binance"]:
        L.append(f"Binance {f(x['binance'])} (Nobitex premium {(p / x['binance'] - 1) * 100:+.2f}%)  ")
    L.append(f"ATR 1D {f(x['atr_d'])} ({x['atr_d'] / p * 100:.1f}%), ATR 4H {f(x['atr_4'])} ({x['atr_4'] / p * 100:.1f}%)")
    vp = x["vp"]
    L += ["", f"- Volume profile ({x['h1_bars']} × 1h): POC {f(vp['POC'])}, value area {f(vp['VAL'])}–{f(vp['VAH'])}, "
          f"HVNs {', '.join(f(v) for v in vp['HVN'][:6]) or '–'}"]
    for k, (lo, hi, *_rest) in x["imps"].items():
        L.append(f"- Impulse {k}: {f(lo)} → {f(hi)} | 0.382 {f(hi - .382 * (hi - lo))} · 0.5 {f(hi - .5 * (hi - lo))} · "
                 f"0.618 {f(hi - .618 * (hi - lo))} · 0.786 {f(hi - .786 * (hi - lo))}")
    L.append(f"- Anchored VWAP (only when the anchor is inside the 1h history): from swing low {f(x['avwap'][0])}, "
             f"from swing high {f(x['avwap'][1])}")
    L += ["", "**Confluence zones below price** (score = weighted count of agreeing methods)", "",
          "| Zone | Center | Score | Methods |", "|---|---|---|---|"]
    for z in sorted(x["zones"], key=lambda z: -z["center"])[:10]:
        mark = " ⭐" if z in x["ladder"] else ""
        L.append(f"| {f(z['lo'])}–{f(z['hi'])}{mark} | {f(z['center'])} | {z['score']:.1f} | "
                 f"{', '.join(sorted({m[0] for m in z['members']}))} |")
    pl = x["plan"]
    if pl:
        L += ["", "**Limit-order ladder**" + (" (weak confluence: no zone has ≥2 strong agreeing methods)" if x["weak"] else ""), ""]
        for i, (z, a) in enumerate(zip(x["ladder"], pl["alloc"]), 1):
            L.append(f"{i}. {a * 100:.0f}% at {f(z['center'])} (zone {f(z['lo'])}–{f(z['hi'])}, "
                     f"{(z['center'] / p - 1) * 100:+.1f}% from price, score {z['score']:.1f})")
        L += [f"- Average entry if all fill: {f(pl['avg'])}",
              f"- Stop: {f(pl['stop'])} ({pl['risk'] * 100:.1f}% below average entry)",
              "- Targets: " + ", ".join(f"{n} {f(v)} ({(v - pl['avg']) / (pl['avg'] - pl['stop']):.1f}R)" for n, v in pl["targets"]),
              f"- R:R if only order 1 fills (to swing high): {pl['first_fill_rr']:.1f}R",
              f"- Size for 1% account risk: {pl['size'] * 100:.1f}% of account; leverage cap {pl['lev']}×"]
    L += ["", f"**1h trigger on zone 1:** {x['trigger'][0]} — {x['trigger'][1]}", "",
          "**Entry-method backtest on this coin's daily history** (2R barrier, 20 days)", "",
          "| Method | Trades | Wins | Win-rate posterior (90% CI) | Expectancy (R) |", "|---|---|---|---|---|"]
    for n, b in x["bt"].items():
        L.append(f"| {n} | {b['n']} | {b.get('wins', '–')} | " +
                 (f"{b['post']:.2f} ({b['lo']:.2f}–{b['hi']:.2f}) | {b['expR']:+.2f} |" if b["n"] else "– | – |"))
    return "\n".join(L) + "\n"


def main():
    syms = [s.upper() for s in (sys.argv[1:] or os.environ.get("ENTRY_SYMBOLS", "AAVE").split())]
    stats = nobitex_stats(syms)
    out = ["# Entry zones (live Nobitex)", ""]
    for s in syms:
        try:
            out.append(render(analyse(s, stats)))
        except Exception as error:
            out.append(f"## {s}\n\nfailed: {error!r}\n")
    report = "\n".join(out)
    print(report)
    os.makedirs("output", exist_ok=True)
    with open("output/entry_zones.md", "w") as fh:
        fh.write(report + "\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(report + "\n")


if __name__ == "__main__":
    main()
