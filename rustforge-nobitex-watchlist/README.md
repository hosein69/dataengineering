# RustForge × Nobitex watchlist

GitHub Actions executes a read-only Rust adapter against live, public Nobitex endpoints. It links the pinned RustForge `risk` crate for GARCH estimation. It does not run RustForge's daemon or execution code and has no trading credentials. It makes GET calls only. Results appear in the Actions job log; an empty or stale result fails the job.

Source: https://github.com/Ashutosh0x/rust-finance at df13eb8dd8e18481790f3417f570d4380cee7764 (MIT). APIs: `/margin/markets/list`, `/market/stats`, `/v3/orderbook/:symbol`, `/market/udf/history` at `apiv2.nobitex.ir`. Public maxLeverage is informational and can differ by user. Candidate markets must be active USDT margin markets, have positive 24-hour quote turnover, a recent book, at most 35 basis points of spread, at least 51 daily candles and GARCH daily volatility at most 12%. Rankings are by 24-hour quote turnover; no side or trade entry is implied.

Run the workflow manually from Actions, or edit this directory to trigger it by push. No secrets required. This is a watchlist for monitoring, not an order or recommendation.

## Conditional entry levels

For each liquid eligible market, the latest 60-minute OHLC series is checked for recent closed bars. If the last four-hour close has risen at least 0.2%, the watchlist presents a long trigger above the preceding 12 closed hourly highs. If it has fallen at least 0.2%, it presents a short trigger below the 12-hour lows. The trigger includes a 5-basis-point or half-spread buffer. Invalidation is 1.5 times the 14-hour true-range average (at least three spreads), and the illustrative target is 1.8 times that distance. A trigger over 2.5% away or with over 5% stop distance is omitted. These are conditional levels, not executable orders; recalculate when the snapshot becomes stale. Quotes, position fees, financing, slippage, and user-specific leverage can change the actual outcome.
