# Nobitex COPY Live v0.3

Resilient Nobitex market-data adapter inspired by `lunarresearcher/copy`.

Current official documentation uses `https://apiv2.nobitex.ir` for public REST and `wss://ws.nobitex.ir/connection/websocket` for WebSocket. Legacy domains remain fallbacks only.

Implemented:
- REST route fallback and per-route health
- system DNS first, DNS-over-HTTPS fallback on DNS failure
- TLS remains bound to the true Nobitex hostname
- order-book sorting, stale/crossed-book guards
- recent trades with notional imbalance
- spread, microprice and depth imbalance
- 5m / 30m / daily OHLC features
- independent REST and WebSocket diagnostics
- monitoring labels without fabricating prices
- no private account API and no order placement

Run:
```bash
cd nobitex-copy
npm install
npm test
npm run live
npm run watch
npm run ws
```

Watch states are monitoring labels only, not trade recommendations.

## Full-market scanner

`npm run scan` discovers the live Nobitex universe from `/v3/orderbook/all`, ranks liquidity/spread within each quote currency, shortlists a configurable number per quote, then enriches only that shortlist with recent trades and 5m/30m/D OHLC. This avoids comparing IRT and USDT notionals directly and reduces API pressure.

`attentionScore` is a monitoring-priority score, not a buy/sell score.
