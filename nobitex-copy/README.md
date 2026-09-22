# Nobitex COPY Live

A Nobitex-specific live market adapter derived from the provider-oriented architecture of [lunarresearcher/copy](https://github.com/lunarresearcher/copy).

## Data paths

The provider tries official/public Nobitex market-data routes left-to-right:

1. `https://api.nobitex.ir`
2. `https://api.nobitex.net`
3. Optional user-controlled relay(s) from `NOBITEX_RELAY_BASES`

The legacy/public REST path shape remains:
- Order book: `GET /v3/orderbook/{SYMBOL}`
- Recent trades: `GET /v2/trades/{SYMBOL}`

WebSocket uses `wss://wss.nobitex.ir/connection/websocket` and subscribes to `public:orderbook-{SYMBOL}`.

`apiv2.nobitex.ir` is not treated as an interchangeable public order-book base because current examples use a different API surface (for example `/market/trades/list`) and may require authorization.

## Reliability additions

- Automatic REST fallback with per-route attempts
- Independent WebSocket smoke test (does not depend on REST first)
- Route health: successes, failures, latency, last error, last checked time
- Optional Iran/self-hosted relay bases without changing normalization logic
- Spread, spread bps, depth notional imbalance, recent trade imbalance
- Watch states: `MOMENTUM_BUY_WATCH`, `PULLBACK_WATCH`, `REVERSAL_WATCH`, `SELL_PRESSURE`, `NEUTRAL`
- No order placement or private account endpoint

## Run

```bash
cd nobitex-copy
npm install
npm test
npm run live
npm run ws
```

Default markets: `BTCIRT,ETHIRT,USDTIRT,ZECIRT`.

A live-data failure is reported as a route/network failure and never replaced with fabricated prices.
