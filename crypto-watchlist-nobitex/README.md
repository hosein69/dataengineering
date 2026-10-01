# Nobitex Live Watchlist

Watchlist for SOL, AAVE, POL, ARB, WLD and TRX (plus BTC/ETH as leaders) built from
live `apiv2.nobitex.ir` data (`market/stats` + daily UDF candles). The
indicators are ported one-for-one from
[khodemadi/aria-futures-demo-source](https://github.com/khodemadi/aria-futures-demo-source)
(`app/advanced-chart.tsx`): SMA20, EMA20, Bollinger, Ichimoku 9/26/52,
RSI14, MACD 12/26/9, ATR14, Stochastic 14/3, OBV. Prices are cross-checked
against Binance the same way the Aria demo reads its market data.

A Beta-Binomial update gives P(up day): the prior comes from the last 90 daily
closes, and the last 14 days are the evidence.

## Run

```bash
python watchlist.py          # writes output/watchlist.md and output/watchlist.json
```

On GitHub, the `Nobitex Live Watchlist` workflow runs it on every push to this
folder, or by hand with workflow_dispatch. The table appears in the job summary.

## Deep analysis

`python deep_analysis.py AAVE ZEC` (the workflow runs it for the symbols in
`DEEP_SYMBOLS`) adds:

- a 4h timeframe next to the daily one, with ADX/DMI, Supertrend (10, 3) and Donchian 20/55
- the last closed day's volume compared with its 20-day average
- live order-book depth at ±1/2/5%, bid/ask imbalance and the largest walls
- a backtest of each setup on the coin's own daily history: long entries with
  a stop at 1.5 ATR and a target at 3 ATR (2R) over 20 days, reporting a Beta
  posterior win rate with a 90% credible interval and the expectancy in R
- a trade plan: entry zone, stop, invalidation, three targets, position size
  for 1% account risk, and the highest leverage that keeps liquidation at
  least twice the stop distance away

## Entry zones

`python entry_zones.py AAVE` (the workflow runs it for the symbols in
`ENTRY_SYMBOLS`) looks for exact entry levels. It finds the support levels
below price where several independent methods agree:

- 1h volume profile: POC, value area and high-volume nodes
- anchored VWAP from the impulse low and from the latest high
- Fibonacci retracements of the daily and 4h impulses
- 4h pivot lows, and old 4h resistances that price has since broken
- Kijun, Tenkan, EMA20 and the 4h Supertrend
- live bid walls in the order book

Each method counts once per zone, and zones are ranked by a weighted score.
The best three become a 30/40/30 limit-order ladder with a stop, extension
targets, position size and a leverage cap. The script also reports a 1h entry
trigger for the first zone (reclaim, bullish engulfing or RSI divergence) and
backtests the Fibonacci 0.5 limit entry against chasing on the coin's own
history.

## Market scanner

`python scanner.py 5` (the workflow runs it with `SCAN_TOP`) builds the watchlist automatically:

1. Takes every USDT market from `/v3/orderbook/all` and drops stablecoins.
2. Keeps markets with a spread of at most 0.6% and at least 1,500 USDT on each side within ±2%.
3. Applies a daily trend gate: price above the Kumo, Tenkan ≥ Kijun, ADX above 20 with
   +DI over −DI, Supertrend up, and not over-extended (less than 3 ATR above the Kijun, RSI below 75).
4. Backtests all trend-long setups on each coin's own history (2R barrier, 20 days).
5. Ranks coins by an empirical-Bayes win rate: each coin's record is shrunk toward the
   market-wide average with 10 pseudo-trades, so coins with only a few trades are not overrated.
6. Runs the top N through `entry_zones.py`.

## Snapshot — 2026-09-23 03:06 UTC

| Asset | Nobitex (USDT) | 24h % | Binance | Kumo | Tenkan/Kijun | RSI14 | 20d range | P(up) prior→post | Score |
|---|---|---|---|---|---|---|---|---|---|
| BTC | 86,333.18 | +0.29% | 86,470.01 | above (71,592–73,442) | 81,050/81,050 | 70.7 | 74,401–87,700 | 0.53→0.55 | +4 |
| ETH | 2,764.14 | +0.31% | 2,760.06 | above (2,135.86–2,270.17) | 2,575.50/2,569.50 | 69.1 | 2,352–2,799 | 0.55→0.58 | +6 |
| SOL | 118.48 | +0.26% | 118.24 | above (90.13–93.52) | 107.86/107.86 | 68.4 | 96.00–119.71 | 0.53→0.54 | +4 |
| AAVE | 146.55 | +1.66% | 147.25 | above (114.96–116.96) | 131.43/131.43 | 64.0 | 113.46–149.40 | 0.52→0.54 | +4 |
| POL | 0.1096 | +0.55% | 0.1093 | above (0.0993–0.1019) | 0.1028/0.1010 | 63.6 | 0.0907–0.1150 | 0.53→0.55 | +6 |
| ARB | 0.2464 | +13.03% | 0.2498 | above (0.0907–0.0933) | 0.1898/0.1652 | 76.3 | 0.1210–0.2468 | 0.46→0.48 | +6 |
| WLD | 0.4600 | -1.94% | 0.4654 | above (0.3774–0.3922) | 0.4174/0.4320 | 62.4 | 0.3569–0.5105 | 0.47→0.49 | +4 |
| TRX | 0.3447 | +0.72% | 0.3443 | above (0.3315–0.3405) | 0.3416/0.3356 | 58.2 | 0.3238–0.3512 | 0.52→0.53 | +6 |

Educational only, not financial advice.
