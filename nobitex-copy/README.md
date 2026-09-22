# Nobitex COPY Live

A Nobitex-specific live market adapter derived from the provider-oriented architecture of [lunarresearcher/copy](https://github.com/lunarresearcher/copy).

## What changed

The Robinhood/DexScreener/Fomo market inputs are replaced by a dedicated `NobitexProvider`.

- Public REST order book: `GET /v3/orderbook/{SYMBOL}`
- Public recent trades: `GET /v2/trades/{SYMBOL}`
- Public WebSocket: `wss://wss.nobitex.ir/connection/websocket`
- WebSocket order-book channels: `public:orderbook-{SYMBOL}`
- REST bootstrap + WebSocket live update
- Correct v3 bid/ask semantics
- Timeouts, explicit errors and freshness metrics
- Spread, spread bps, top-depth notional imbalance and recent-trade imbalance
- No API key required for the public market-data path
- No order placement or private-account endpoint is implemented

## Run

```bash
cd nobitex-copy
npm install
npm test
npm run live
npm run ws
```

Default markets: `BTCIRT,ETHIRT,USDTIRT,ZECIRT`. Override with `NOBITEX_MARKETS`.

## Safety / scope

This branch is market-data only. It deliberately does not submit trades. A live data feed proves connectivity and parsing; it is not evidence that a trading strategy is profitable.
