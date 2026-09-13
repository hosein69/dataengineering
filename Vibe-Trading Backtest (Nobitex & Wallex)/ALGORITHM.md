# الگوریتم داخلی، معماری ماژول‌ها و فرمول‌های دقیق موتور بک‌تست Vibe-Trading

این سند دقیقاً بر اساس خواندن سورس‌کد واقعی ریپوی [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) نوشته شده (نه حدس)، با تمرکز روی مسیری که برای نمادهای **نوبیتکس (`source=nobitex`)** و **والکس (`source=wallex`)** طی می‌شود. فایل‌های مرجع:

- `agent/backtest/loaders/nobitex.py`, `agent/backtest/loaders/wallex.py`
- `agent/backtest/loaders/registry.py`
- `agent/backtest/runner.py` (روتینگ موتور)
- `agent/backtest/engines/base.py` (موتور پایه، مشترک بین همه بازارها)
- `agent/backtest/engines/crypto.py` (موتوری که برای نوبیتکس/والکس واقعاً اجرا می‌شود)
- `agent/backtest/metrics.py` (فرمول‌های عملکرد)
- `agent/backtest/models.py` (مدل‌های داده)

---

## ۱. نمودار جریان داده بین ماژول‌ها

```
config.json ──┐
              │
              ▼
┌─────────────────────────┐   fetch(codes, start, end, interval)
│  Loader (nobitex.py /    │ ───────────────────────────────────► خروجی: Dict[symbol -> DataFrame]
│  wallex.py)              │   ورودی: نماد + بازه‌ی زمانی + تایم‌فریم   (index=زمان, ستون‌ها: open/high/low/close/volume)
└─────────────────────────┘
              │  data_map
              ▼
┌─────────────────────────┐   generate(data_map)
│  SignalEngine            │ ───────────────────────────────────► خروجی: Dict[symbol -> pd.Series]
│  (کد پایتونی تولیدشده    │   ورودی: همان data_map بالا              (سیگنال خام، هر عددی می‌تواند باشد،
│  توسط ایجنت/LLM،         │                                           بعداً کلمپ می‌شود به [-1, +1])
│  code/signal_engine.py)  │
└─────────────────────────┘
              │  signal_map
              ▼
┌─────────────────────────┐   _align(data_map, signal_map, codes, optimizer)
│  Align + Optimizer       │ ───────────────────────────────────► خروجی: dates, close_df, close_val_df,
│  (تابع _align در         │   ورودی: data_map + signal_map           target_pos (وزن هدف هر نماد در هر بار),
│  engines/base.py)        │                                           ret_df (بازده هر نماد)
└─────────────────────────┘
              │  target_pos (ماتریس وزن هدف)
              ▼
┌─────────────────────────┐   run_backtest(...) → _execute_bars(...)
│  Engine (CryptoEngine    │ ───────────────────────────────────► خروجی: trades[], equity_snapshots[]
│  برای نوبیتکس/والکس،     │   ورودی: target_pos + close_df + قیمت‌ها
│  ارث‌بر از BaseEngine)    │   (شبیه‌سازی کندل‌به‌کندل: سفارش،
│                          │    کارمزد، اسلیپیج، PnL، مارجین)
└─────────────────────────┘
              │  equity_curve + trades
              ▼
┌─────────────────────────┐   calc_metrics(equity_curve, trades, initial_cash, bars_per_year, ...)
│  Metrics                 │ ───────────────────────────────────► خروجی: dict شاخص‌های عملکرد
│  (metrics.py)             │   ورودی: equity_curve، لیست معاملات        (Sharpe, MDD, Sortino, Calmar, ...)
└─────────────────────────┘
              │
              ▼
   artifacts: equity_curve.csv, trades.csv, metrics.json, config.json (کپی)
```

نکته‌ی کلیدی معماری: خودِ استراتژی (`signal_engine.py`) **کد پایتونی تولیدشده توسط ایجنت LLM** است، نه یک فرمت اعلانی ثابت؛ اما بعد از تولید سیگنال خام، تبدیل سیگنال به وزن پوزیشن، اجرای سفارش، محاسبه‌ی کارمزد/اسلیپیج/PnL و همه‌ی متریک‌ها توسط یک **موتور قطعی و غیر-LLM** (کد پایتون معمولی در `engines/base.py` و `engines/crypto.py`) انجام می‌شود — یعنی نتیجه‌ی بک‌تست از منطق مدل زبانی مستقل و قابل‌تکرار (deterministic) است.

---

## ۲. کدام موتور برای نوبیتکس/والکس اجرا می‌شود؟

در `registry.py`، هر دو لودر با `markets = {"crypto"}` ثبت شده‌اند. در `runner.py` (تابع انتخاب موتور)، منطق روتینگ چنین است:

```python
if source in ("okx", "ccxt"):
    return CryptoEngine(config)
elif source in ("tushare", "akshare"):
    ...  # چین
elif source == "yfinance":
    ...
else:
    # نوبیتکس و والکس دقیقاً از همین شاخه عبور می‌کنند
    if markets & {"us_equity", "hk_equity", "ca_equity", "uk_equity"}:
        return GlobalEquityEngine(...)
    return CryptoEngine(config)   # ← نوبیتکس/والکس اینجا فرود می‌آیند
```

پس **`CryptoEngine`** (فایل `engines/crypto.py`، ارث‌بر از `BaseEngine`) دقیقاً همان موتوری است که بک‌تست‌های نوبیتکس/والکس را اجرا می‌کند — همان موتوری که برای OKX/Binance/CCXT هم استفاده می‌شود.

---

## ۳. ورودی/خروجی دقیق هر ماژول

| ماژول | ورودی | خروجی |
|---|---|---|
| `Loader.fetch()` | `codes: List[str]`, `start_date`, `end_date` (رشته YYYY-MM-DD)، `interval` | `Dict[str, pd.DataFrame]` — هر DataFrame با ایندکس زمانی و ستون‌های `open, high, low, close, volume` |
| `SignalEngine.generate()` | همان `data_map` بالا | `Dict[str, pd.Series]` — یک سری زمانی سیگنال خام برای هر نماد (باید هم‌ایندکس با DataFrame ورودی باشد) |
| `_align()` | `data_map`, `signal_map`, `codes`, `optimizer` (اختیاری) | `(dates, close_df, close_val_df, target_pos, ret_df)` |
| `Engine.run_backtest()` | `config` (شامل `codes/interval/start_date/end_date/leverage/...`), `loader`, `signal_engine`, `run_dir` | `metrics: dict` + فایل‌های خروجی در `run_dir` |
| `metrics.calc_metrics()` | `equity_curve: pd.Series`, `trades: List[TradeRecord]`, `initial_cash`, `bars_per_year`, `bench_ret` (اختیاری) | `dict` شامل ۱۹ شاخص عملکردی |

### مدل‌های داده (`models.py`)

```python
Position(symbol, direction, entry_price, entry_time, size, leverage=1.0, entry_bar_idx=0, entry_commission=0.0)
TradeRecord(symbol, direction, entry_price, exit_price, entry_time, exit_time,
            size, leverage, pnl, pnl_pct, exit_reason, holding_bars, commission,
            entry_margin=0.0, exit_margin=0.0)
FillRecord(symbol, timestamp, bar_idx, action, signed_quantity, notional,
           execution_price, fee, margin, reason, holding_bars=None)
EquitySnapshot(timestamp, capital, unrealized, equity, positions)
```

`direction`: ‎`+1` = لانگ/خرید، `-1` = شورت/فروش.

---

## ۴. فرمول‌های دقیق — گام به گام

### ۴.۱. از سیگنال خام تا وزن هدف (تابع `_align`، فایل `engines/base.py`)

برای هر نماد `i` در بار زمانی `t`:

```
1) sig_clipped[i,t] = clip(raw_signal[i,t], -1, +1)          # کلمپ به بازه [-1, 1]
2) sig_shifted[i,t] = sig_clipped[i, t-1]                     # شیفت یک بار به عقب
                                                               # (بدون نگاه به آینده؛ اجرا در باز شدن کندل بعدی)
3) pos[i,t] = ffill(sig_shifted[i,t], limit=ffill_limit)      # پر کردن رو به جلو تا حداکثر ۵ بار
                                                               # (یا ۱۰ بار برای اجرای چند-بازاره)
4) اگر optimizer تنظیم شده باشد:
       pos = optimizer(ret_df, pos, dates)                    # مثلا MVO / equal-vol / risk-parity

5) نرمال‌سازی نهایی (اطمینان از Σ|وزن‌ها| ≤ 1):
       scale[t]   = max(1.0, Σ_i |pos[i,t]|)
       weight[i,t] = pos[i,t] / scale[t]
```

یعنی وزن نهایی هر نماد همیشه در بازه‌ی معناداری می‌ماند و مجموع قدرمطلق وزن‌های همه‌ی نمادها در هر لحظه حداکثر ۱ (=۱۰۰٪ سرمایه) است.

### ۴.۲. قیمت اجرا با اسلیپیج (`apply_slippage`, در `CryptoEngine`)

```
price_exec = price_open_bar × (1 + direction × slippage_rate)
```
- `slippage_rate` پیش‌فرض = `0.0005` (۰.۰۵٪)
- برای خرید (`direction=+1`) قیمت اجرا کمی **بالاتر** از قیمت بازار، برای فروش (`direction=-1`) کمی **پایین‌تر** می‌شود (شبیه‌سازی هزینه‌ی نقدشوندگی).
- اجرای هر معامله همیشه روی **قیمت باز (Open) کندلِ بعد از سیگنال** انجام می‌شود، نه قیمت بسته‌شدن همان کندل (برای جلوگیری از look-ahead bias).

### ۴.۳. اندازه‌ی سفارش (`_plan_open_order`)

```
target_notional[i,t] = |weight[i,t]| × equity[t] × leverage
raw_size              = target_notional / price_exec
size                  = round_size(raw_size)     # برای کریپتو: رند به ۶ رقم اعشار
```
اگر `size <= 0`، سفارش رد می‌شود (`zero_size`).

### ۴.۴. مارجین لازم (`_calc_margin`)

```
margin = size × |price_exec| / leverage
```
برای نوبیتکس/والکس (چون این دو فقط داده‌ی بک‌تست هستند، نه بروکر واقعی)، معمولاً `leverage = 1` (اسپات، بدون اهرم) در نظر گرفته می‌شود مگر در `config.json` مقدار دیگری تنظیم شود.

### ۴.۵. کارمزد (`calc_commission`, در `CryptoEngine`)

```
commission = size × price_exec × rate
rate = taker_rate   اگر (perpetual_strict باشد) یا (سفارش باز‌کننده‌ی پوزیشن باشد)
rate = maker_rate   در غیر این صورت (بستن پوزیشن)
```
پیش‌فرض‌ها: `taker_rate = 0.0005` (۰.۰۵٪)، `maker_rate = 0.0002` (۰.۰۲٪) — این‌ها اعداد فرضی موتور هستند، نه کارمزد واقعی نوبیتکس/والکس (که می‌توانید در `config.json` با کارمزد واقعی هر صرافی بازنویسی‌شان کنید).

### ۴.۶. سود/زیان محقق‌شده هنگام بستن پوزیشن (`_calc_pnl`)

```
pnl = direction × size × (exit_price − entry_price)
```

### ۴.۷. ارزش پرتفوی در هر کندل (Equity)

```
unrealized[i,t] = direction_i × size_i × (mark_price[t] − entry_price_i)
equity[t] = capital[t] + Σ_i margin_i + Σ_i unrealized[i,t]
```
که `capital` = نقد آزاد (پس از کسر مارجین قفل‌شده و کارمزدها).

### ۴.۸. بازده هر بار (`bar_returns`, در `metrics.py`)

```
r[t] = close[t] / close[t-1] − 1     اگر close[t-1] > 0 و متناهی باشد
r[t] = 0                              در غیر این صورت (برای جلوگیری از inf/nan)
```

### ۴.۹. بازده کل و بازده سالانه‌شده

```
total_return = equity[end] / initial_cash − 1

n   = تعداد بارهای بک‌تست
bpy = bars_per_year   (نگاه کنید به بخش ۵)

annual_return = (1 + total_return)^(bpy / n) − 1
```

### ۴.۱۰. نوسان و نسبت شارپ

```
vol    = std(r[t])                       # با ddof=1 (نمونه‌ای)
Sharpe = mean(r[t]) / (vol + 1e-10) × sqrt(bpy)
```
(نرخ بدون ریسک صفر فرض شده — یعنی این‌جا Sharpe نسبت به صفر است، نه نسبت به نرخ سپرده.)

### ۴.۱۱. نسبت سورتینو

```
downside[t]  = r[t]  فقط برای r[t] < 0
Sortino      = mean(r[t]) / (std(downside) + 1e-10) × sqrt(bpy)
```

### ۴.۱۲. بیشترین افت سرمایه (Max Drawdown)

```
peak[t] = max(cummax(equity[0..t]), initial_cash)     # مبنای اول، سرمایه‌ی اولیه است
dd[t]   = (equity[t] − peak[t]) / peak[t]
max_dd  = min(dd[t])       (عددی منفی، مثلاً -0.23 یعنی ۲۳٪ افت)
```

### ۴.۱۳. نسبت کلمار

```
Calmar = annual_return / |max_dd|
```

### ۴.۱۴. گردش سرمایه (Turnover)

```
turnover[t] = 0.5 × Σ_i |weight[i,t] − weight[i,t-1]|
```
(چرخش کامل سرمایه از یک دارایی به دارایی دیگر = ۱٫۰)

### ۴.۱۵. نسبت اطلاعات (IR)، ردیابی خطا و بتا نسبت به بنچمارک

اگر بنچمارک تعریف شده باشد:

```
active_ret[t]   = r[t] − bench_r[t]
tracking_error  = std(active_ret) × sqrt(bpy)
IR              = mean(active_ret) / (std(active_ret) + 1e-10) × sqrt(bpy)
beta            = Cov(r, bench_r) / Var(bench_r)
excess_return   = total_return − bench_total_return
```

---

## ۵. عامل سالانه‌سازی (`bars_per_year`) برای نوبیتکس/والکس

چون نوبیتکس و والکس بازارهای ۲۴/۷ کریپتو هستند (نه بورس با ساعت محدود)، جدول `metrics.py` این‌طور تعریف‌شان کرده:

```
trading_days_per_year["nobitex"] = 365
trading_days_per_year["wallex"]  = 365

bars_per_day:
    1m  → 1440
    5m  → 288
    15m → 96
    30m → 48
    1H  → 24
    4H  → 6
    1D  → 1

bars_per_year = trading_days_per_year × bars_per_day[interval]
```
مثال: برای تایم‌فریم `1h` روی نوبیتکس → `bars_per_year = 365 × 24 = 8760`.
همین عدد در فرمول‌های Sharpe/Sortino/annual_return (بخش‌های ۴.۹ تا ۴.۱۱) به‌عنوان `bpy` استفاده می‌شود.

---

## ۶. ورودی/خروجی دقیق لودرهای نوبیتکس و والکس

### نوبیتکس (`agent/backtest/loaders/nobitex.py`)

```
ورودی fetch():
    codes    = ["BTCIRT", "USDTIRT", ...]   (خودکار نرمال می‌شود: حذف "-" و "/")
    start_date, end_date = "YYYY-MM-DD"
    interval ∈ {1m,5m,15m,30m,1h,3h,4h,6h,12h,1d}

درخواست HTTP واقعی:
    GET https://apiv2.nobitex.ir/market/udf/history
        ?symbol=BTCIRT&resolution=<map(interval)>&from=<epoch>&to=<epoch>&page=<n>

    نگاشت interval → resolution:
        1m→"1", 5m→"5", 15m→"15", 30m→"30",
        1h→"60", 3h→"180", 4h→"240", 6h→"360", 12h→"720", 1d→"D"

صفحه‌بندی: هر صفحه حداکثر ۵۰۰ کندل؛ تا ۴۰ صفحه با ۰.۵ ثانیه فاصله بین درخواست‌ها (محدودیت ۶۰ req/min).

خروجی: DataFrame با ایندکس trade_date و ستون‌های [open, high, low, close, volume]،
        فقط ردیف‌هایی که OHLC معتبر دارند (validate_ohlc)، به‌صورت float64.
```

### والکس (`agent/backtest/loaders/wallex.py`)

```
ورودی fetch(): مشابه بالا، نماد نرمال می‌شود به فرمت بدون جداکننده مثل USDTTMN

درخواست HTTP واقعی:
    GET https://api.wallex.ir/v1/udf/history
        ?symbol=<SYMBOL>&resolution=<map(interval)>&from=<epoch>&to=<epoch>

    نگاشت interval → resolution (فقط سه‌تا واقعاً پشتیبانی می‌شوند):
        1m → "1"
        1h → "60"
        1d → "1D"
    (سایر تایم‌فریم‌ها [] خالی برمی‌گردانند تا زنجیره‌ی fallback ادامه یابد، نه داده‌ی غلط‌لیبل‌خورده)

پنجره‌بندی درخواست (به‌خاطر سقف بک‌اند):
        1m → حداکثر ۲۰ روز در هر درخواست
        1h → حداکثر ۲ سال در هر درخواست
        1d → حداکثر ۴۰ سال در هر درخواست

خروجی: همان فرمت [open, high, low, close, volume] با ایندکس زمانی.
```

---

## ۷. مثال عددی کامل (گام‌به‌گام روی داده‌ی فرضی BTCIRT)

فرض کنید:
- `initial_cash = 100,000,000` تومان
- `leverage = 1`
- سیگنال استراتژی روی کندل `t-1` مثبت شده (`raw_signal = 1`)
- `price_open[t] = 4,000,000,000` ریال معادل تومان یا هرچه (برای سادگی فقط عدد `price = 4,000,000,000`)
- `slippage_rate = 0.0005`, `taker_rate = 0.0005`

محاسبه:
```
weight[t]        = 1 / max(1, 1) = 1.0        (۱۰۰٪ سرمایه روی BTCIRT)
price_exec        = 4,000,000,000 × (1 + 1×0.0005) = 4,002,000,000
target_notional   = 1.0 × 100,000,000 × 1 = 100,000,000
raw_size           = 100,000,000 / 4,002,000,000 ≈ 0.024988
size (رند ۶ رقم)  = 0.024988
margin             = 0.024988 × 4,002,000,000 / 1 ≈ 99,999,976
commission (باز)  = 0.024988 × 4,002,000,000 × 0.0005 ≈ 49,999.99
capital بعد از باز کردن = 100,000,000 − margin − commission ≈ 23
```
اگر بعداً قیمت به `4,200,000,000` برسد و پوزیشن بسته شود:
```
pnl = 1 × 0.024988 × (4,200,000,000 − 4,002,000,000) ≈ 4,947,624
```

---

## ۸. جمع‌بندی رابطه‌ی ماژول‌ها (خلاصه‌ی یک‌خطی هرکدام)

| ماژول | نقش |
|---|---|
| `loaders/nobitex.py`, `loaders/wallex.py` | فقط **دیتا** می‌دهند: OHLCV تاریخی؛ هیچ منطق معاملاتی ندارند |
| `loaders/registry.py` | نگاشت نام `source` به کلاس Loader + اعتبارسنجی `VALID_SOURCES` |
| `signal_engine.py` (تولیدشده توسط LLM) | فقط سیگنال خام تولید می‌کند؛ به قیمت اجرا، کارمزد یا مارجین کاری ندارد |
| `engines/base.py::_align` | سیگنال خام → وزن پوزیشن نرمال‌شده (بدون look-ahead) |
| `engines/base.py::BaseEngine` | چرخه‌ی اصلی شبیه‌سازی: تصمیم بر اساس وزن، ساخت سفارش، بروزرسانی equity |
| `engines/crypto.py::CryptoEngine` | قوانین بازار کریپتو: کارمزد Maker/Taker، اسلیپیج، (و برای فیوچرز: فاندینگ/لیکوییدیشن که برای اسپات نوبیتکس/والکس معمولاً غیرفعال است) |
| `metrics.py` | equity_curve + trades → Sharpe/Sortino/Calmar/MDD/IR/... |
| `runner.py` | orchestrator: کدام Loader، کدام Engine، به چه ترتیبی اجرا شوند |

---

## منابع

- سورس اصلی: https://github.com/HKUDS/Vibe-Trading
- فایل‌های مرجع این سند: `agent/backtest/{loaders/nobitex.py, loaders/wallex.py, loaders/registry.py, runner.py, engines/base.py, engines/crypto.py, metrics.py, models.py}`
