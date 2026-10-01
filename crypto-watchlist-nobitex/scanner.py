"""Scan every Nobitex USDT market and pick a high-probability long watchlist.

1. Universe: all *USDT books from /v3/orderbook/all, stablecoins removed.
2. Liquidity filter: spread and order-book depth within ±2% of mid.
3. Per coin, on daily candles: trend gate (above Kumo, Tenkan >= Kijun,
   ADX > 20 with +DI > -DI, Supertrend up, not over-extended) and a
   barrier backtest of all trend-long setups on the coin's own history.
4. Ranking with empirical Bayes: each coin's win rate and expectancy are
   shrunk toward the market-wide average, so a coin with 3 lucky trades
   does not outrank one with 30 good ones.
5. The top N go through the full entry-zone analysis (entry_zones.py).

Usage: python scanner.py [N]
"""

import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

import entry_zones
from deep_analysis import adx, candles, setups, supertrend
from watchlist import NOBITEX, fmt, get_json, indicators, nobitex_stats

STABLES = {"USDC", "DAI", "TUSD", "BUSD", "FDUSD", "USDE", "USDD", "USDP", "PYUSD", "USDS", "EURT", "EURC"}
TREND_SETUPS = {"PULLBACK_TO_KIJUN", "BREAKOUT_20D", "MOMENTUM", "UPTREND_CORRECTION"}
MAX_SPREAD = 0.6       # %
MIN_DEPTH = 1500.0     # USDT within ±2% on each side
PRIOR_STRENGTH = 10    # pseudo-trades of the market-wide prior


def universe():
    data = get_json(f"{NOBITEX}/v3/orderbook/all", timeout=30)
    out = {}
    for sym, book in data.items():
        if not sym.endswith("USDT") or not isinstance(book, dict):
            continue
        base = sym[:-4]
        if base in STABLES:
            continue
        bids = sorted(((float(p), float(q)) for p, q in book.get("bids", [])), reverse=True)
        asks = sorted((float(p), float(q)) for p, q in book.get("asks", []))
        if not bids or not asks or bids[0][0] >= asks[0][0]:
            continue
        mid = (bids[0][0] + asks[0][0]) / 2
        out[base] = {
            "spread": (asks[0][0] - bids[0][0]) / mid * 100,
            "bid2": sum(p * q for p, q in bids if p >= mid * 0.98),
            "ask2": sum(p * q for p, q in asks if p <= mid * 1.02),
            "mid": mid,
        }
    return out


def trend_backtest(rows, stop_atr=1.5, target_atr=3.0, horizon=20):
    rs, i = [], 60
    while i < len(rows) - 1:
        if not (setups(rows, i) & TREND_SETUPS):
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
            if j >= len(rows):
                break
            result = (rows[j]["close"] - e) / risk
        rs.append(result)
        i = j + 1
    return rs


def evaluate(base):
    d = candles(base, "D", 700)
    if len(d) < 120:
        return None
    rows = indicators(d)
    r = rows[-1]
    spans = [x for x in (r.get("spanA"), r.get("spanB")) if x is not None]
    if len(spans) < 2 or r.get("atr") is None or r.get("kijun") is None:
        return None
    ad, pdi, mdi = adx(d)
    st = supertrend(rows)[-1]
    ext = (r["close"] - r["kijun"]) / r["atr"]
    gate = {
        "above_kumo": r["close"] > max(spans),
        "tk_cross": r["tenkan"] >= r["kijun"],
        "adx": (ad[-1] or 0) > 20 and (pdi[-1] or 0) > (mdi[-1] or 0),
        "supertrend": bool(st and st[0] == "up"),
        "not_extended": ext < 3.0 and (r.get("rsi") or 50) < 75,
    }
    rs = trend_backtest(rows)
    vol_usdt = sum(c["volume"] * c["close"] for c in d[-8:-1]) / 7
    return {"base": base, "price": r["close"], "rsi": r.get("rsi"), "adx": ad[-1], "ext": ext,
            "atrPct": r["atr"] / r["close"] * 100, "gate": gate, "pass": all(gate.values()),
            "gates": sum(gate.values()), "rs": rs, "days": len(d), "volUsdt": vol_usdt,
            "active": sorted(setups(rows, len(rows) - 1) & TREND_SETUPS)}


def main():
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("SCAN_TOP", "5"))
    uni = universe()
    liquid = {b: m for b, m in uni.items()
              if m["spread"] <= MAX_SPREAD and min(m["bid2"], m["ask2"]) >= MIN_DEPTH}
    print(f"[scan] {len(uni)} USDT markets, {len(liquid)} pass liquidity", file=sys.stderr)

    def safe(b):
        try:
            return evaluate(b)
        except Exception as error:
            print(f"[warn] {b}: {error}", file=sys.stderr)
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = [x for x in pool.map(safe, sorted(liquid)) if x]

    all_r = [v for x in results for v in x["rs"]]
    p0 = sum(v > 0 for v in all_r) / len(all_r) if all_r else 0.5
    e0 = sum(all_r) / len(all_r) if all_r else 0.0
    k = PRIOR_STRENGTH
    random.seed(13)
    for x in results:
        n, w = len(x["rs"]), sum(v > 0 for v in x["rs"])
        a, b = p0 * k + w, (1 - p0) * k + n - w
        x["n"], x["wins"] = n, w
        x["pWin"] = a / (a + b)
        s = sorted(random.betavariate(a, b) for _ in range(4000))
        x["pLo"], x["pHi"] = s[200], s[3800]
        x["expR"] = (k * e0 + sum(x["rs"])) / (k + n)
        x["score"] = x["pWin"] * (1 + max(-0.5, min(1.0, x["expR"])))
        x.update(liquid[x["base"]])

    ranked = sorted(results, key=lambda x: (x["pass"], x["gates"], x["score"]), reverse=True)
    pick = ranked[:top_n]

    L = ["# High-probability watchlist (live Nobitex scan)", "",
         f"Universe: {len(uni)} USDT markets → {len(liquid)} liquid (spread ≤ {MAX_SPREAD}%, "
         f"≥ {MIN_DEPTH:,.0f} USDT each side within ±2%) → {sum(x['pass'] for x in results)} pass every trend gate.  ",
         f"Market-wide prior for trend-long setups: win rate {p0:.2f}, expectancy {e0:+.2f}R "
         f"({len(all_r)} trades). Coin stats are shrunk toward it with {k} pseudo-trades.", "",
         "| # | Coin | Price | Gates | Trades | Wins | P(win) shrunk (90% CI) | Exp. (R) | ADX | RSI | Kijun dist (ATR) | ATR % | Spread % | Depth ±2% bid/ask | Active setups |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, x in enumerate(ranked[:15], 1):
        L.append(f"| {i} | **{x['base']}** | {fmt(x['price'])} | {x['gates']}/5 | {x['n']} | {x['wins']} | "
                 f"{x['pWin']:.2f} ({x['pLo']:.2f}–{x['pHi']:.2f}) | {x['expR']:+.2f} | {(x['adx'] or 0):.0f} | "
                 f"{(x['rsi'] or 0):.0f} | {x['ext']:+.1f} | {x['atrPct']:.1f} | {x['spread']:.2f} | "
                 f"{x['bid2']:,.0f}/{x['ask2']:,.0f} | {', '.join(x['active']) or '–'} |")
    failed = [f"{x['base']} ({', '.join(g for g, ok in x['gate'].items() if not ok)})" for x in pick if not x["pass"]]
    if failed:
        L += ["", "Picked without passing every gate: " + "; ".join(failed)]
    L.append("")
    stats = nobitex_stats([x["base"] for x in pick])
    for x in pick:
        try:
            L.append(entry_zones.render(entry_zones.analyse(x["base"], stats)))
        except Exception as error:
            L.append(f"## {x['base']}\n\nentry-zone analysis failed: {error!r}\n")
    report = "\n".join(L)
    print(report)
    os.makedirs("output", exist_ok=True)
    with open("output/scanner.md", "w") as fh:
        fh.write(report + "\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(report + "\n")


if __name__ == "__main__":
    main()
