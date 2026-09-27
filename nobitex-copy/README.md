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


## Temporal stability scanner

`npm run stable` performs a full first-pass scan, then rechecks only the shortlisted symbols for several cycles. Slow OHLC features are reused from cycle 1; later cycles refresh market-wide order books plus recent trades. A state is promoted to `CONFIRMED` only when the actionable state persists for at least two-thirds of cycles and microstructure direction is sufficiently consistent.

This reduces single-snapshot false positives while keeping API usage bounded.


Stablecoin-base markets (for example USDC/USDT, DAI/USDT and USDT/IRT) are retained as `referenceMarkets` for liquidity/FX context but are separated from `confirmedOpportunities`.
