# Nobitex Live Watchlist

Watchlist for SOL, AAVE, POL, ARB and WLD (plus BTC/ETH as leaders) built from
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

## Snapshot — 2026-09-23 02:51 UTC

| Asset | Nobitex (USDT) | 24h % | Binance | Kumo | Tenkan/Kijun | RSI14 | 20d range | P(up) prior→post | Score |
|---|---|---|---|---|---|---|---|---|---|
| BTC | 86,396.81 | +0.37% | – | above | – | 70.8 | – | – | – |
| ETH | 2,757.97 | +0.08% | – | above | – | 68.8 | – | – | – |
| SOL | 118.48 | +0.26% | 118.24 | above (90.13–93.52) | 107.86/107.86 | 68.4 | 96.00–119.71 | 0.53→0.54 | +4 |
| AAVE | 146.55 | +1.66% | 147.25 | above (114.96–116.96) | 131.43/131.43 | 64.0 | 113.46–149.40 | 0.52→0.54 | +4 |
| POL | 0.1096 | +0.55% | 0.1093 | above (0.0993–0.1019) | 0.1028/0.1010 | 63.6 | 0.0907–0.1150 | 0.53→0.55 | +6 |
| ARB | 0.2464 | +13.03% | 0.2498 | above (0.0907–0.0933) | 0.1898/0.1652 | 76.3 | 0.1210–0.2468 | 0.46→0.48 | +6 |
| WLD | 0.4600 | -1.94% | 0.4654 | above (0.3774–0.3922) | 0.4174/0.4320 | 62.4 | 0.3569–0.5105 | 0.47→0.49 | +4 |

Educational only, not financial advice.
