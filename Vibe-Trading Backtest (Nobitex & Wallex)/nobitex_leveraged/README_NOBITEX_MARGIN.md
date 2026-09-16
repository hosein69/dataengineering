# Vibe-Trading + Nobitex Leveraged Long/Short

این بسته برای بک‌تست **تعهدی/مارجین نوبیتکس** طراحی شده و عمداً آن را با
`Vibe-Trading Crypto perpetual engine` یکی نمی‌کند.

## چرا دو موتور؟

Vibe-Trading در نسخه‌های جدید موتور `CryptoEngine` برای perpetual دارد:
long/short، leverage، funding، isolated/cross margin، maintenance tiers و liquidation.
اما مدل margin نوبیتکس API متفاوت است: بازار تعهدی، leverage، collateral، liability،
position fee/extension fee و liquidation price دارد.

پس:

- Vibe-Trading = baseline / research / strategy generation
- `nobitex_leveraged_backtest.py` = exchange-specific margin research layer

## اجرا در GitHub

Workflow:
`.github/workflows/nobitex-leveraged-backtest.yml`

از GitHub:
Actions → Nobitex Leveraged Long-Short Backtest → Run workflow

پیشنهاد شروع:

- Symbols: `BTCIRT,ETHIRT,SOLIRT,XRPIRT,DOGEIRT`
- Resolution: `15`
- Lookback: `180`
- Leverage: `2` یا `3`
- Risk/trade: `0.5%`
- Stop: `0.8%`
- Take: `1.6%`
- Max hold: `96` bars

برای 15 دقیقه، 96 bar تقریباً 24 ساعت است.

## خروجی

Artifact شامل:

- `*_equity.csv`
- `*_trades.csv`
- `*_metrics.json`
- `summary.json`
- `research_summary.md`

## نکتهٔ مهم دربارهٔ liquidation

این نسخه عمداً نمی‌گوید liquidation آن دقیقاً برابر مدل داخلی نوبیتکس است.
فرمول تاریخی کامل liquidation از OHLC عمومی بازسازی‌پذیر نیست.

در عوض یک proxy شفاف داریم:

`equity_position <= maintenance_ratio * initial_collateral`

پارامتر `maintenance_ratio` قابل تغییر است و تمام liquidationهای proxy در ledger ثبت می‌شوند.

## محدودیت داده

OHLC عمومی نوبیتکس شامل O/H/L/C/V است. این برای signal و stress test خوب است،
اما order-book depth، spread، queue position و latency تاریخی را نمی‌دهد.
برای strategyهای خیلی کوتاه‌مدت، این‌ها باید در مرحلهٔ بعد اضافه شوند.

## معیار پذیرش یک استراتژی اهرمی

استراتژی را فقط وقتی نامزد بررسی بیشتر بدان:

1. Walk-forward مثبت باشد.
2. سود پس از fee + extension fee + slippage باقی بماند.
3. proxy liquidation صفر یا بسیار نادر باشد.
4. Max drawdown قابل تحمل باشد.
5. bootstrap بدبینانه شکست سیستماتیک نشان ندهد.
6. نتیجه در چند نماد و چند regime باقی بماند.
7. نسبت به long-only و buy-and-hold مزیت risk-adjusted داشته باشد.

## معماری causal

برای signal خام:

`trend/volatility -> signal -> position`
و برای P&L:

`signal -> entry -> exposure -> price path -> pnl -> equity -> drawdown/liquidation`

هزینه‌ها و leverage نباید بعداً به performance تزریق شوند؛ باید داخل همان مسیر علی قرار گیرند.

## نتیجهٔ مهم از اجرای قبلی

MA(10/30) در تست روزانهٔ BTCIRT روی نمونهٔ تاریخی قبلی عالی بود،
ولی این به معنی آمادگی برای leverage intraday نیست. این workflow دقیقاً برای
کشف همین فاصله ساخته شده است.
